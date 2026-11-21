"""전국 용도별(도시가스용·발전용·합계) 1~12개월 앞 예측: 검증 구간 튜닝 → 설정 고정 → 평가 구간 → 표본 외.

모든 모델은 같은 절차를 거친다: 2020~2022 목표월(검증)에서 설정을 고르고, 2023~2025 목표월에서 평가한다.
평가는 사전예측(평년 기온)과 사후예측(실제 기온) 둘 다. LightGBM이 들어간 모델은 시드 3개 평균. 2026년 1~9월은 2025년 12월 시점부터의 표본 외 검증.

출력: outputs/national/{tuning,predictions,summary}.csv
실행: python run_national.py [--jobs 8]
"""
import argparse
import itertools
import json
import time

import numpy as np
import pandas as pd
from joblib import Parallel, delayed

import models_mh as M
from config import OUTPUTS, PROCESSED
from mh import EVAL, HOLD, VAL, rolling, summary

OUT = OUTPUTS / "national"
OUT.mkdir(parents=True, exist_ok=True)
SERIES = {"city": "도시가스용", "power": "발전용", "total": "합계"}

REG_FEATS = {
    "city": [("hdd", "cdd"), ("hdd", "cdd", "workdays"), ("hdd", "cdd", "log_cpi"), ("hdd", "cdd", "log_cpi", "trend")],
    "power": [("hdd", "cdd"), ("hdd", "cdd", "coal_cap"), ("hdd", "cdd", "coal_cap", "log_lng"),
              ("hdd", "cdd", "coal_cap", "trend")],
    "total": [("hdd", "cdd"), ("hdd", "cdd", "coal_cap"), ("hdd", "cdd", "coal_cap", "log_cpi"),
              ("hdd", "cdd", "coal_cap", "trend")],
}
SARIMAX_EXOG = {"city": [("hdd",), ("hdd", "cdd")], "power": [("hdd", "cdd"), ("hdd", "cdd", "coal_cap")],
                "total": [("hdd", "cdd"), ("hdd", "cdd", "coal_cap")]}


def grid(series):
    g = {
        "계절 naive": (M.snaive, [{}]),
        "회귀 √Y": (M.reg, [{"feats": f} for f in REG_FEATS[series]]),
        "SARIMAX": (M.sarimax, [{"order": o, "seasonal": s, "exog": e} for o, s, e in itertools.product(
            [(1, 0, 0), (1, 0, 1), (2, 0, 0)], [(1, 0, 0), (0, 1, 1)], SARIMAX_EXOG[series])]),
        "ETS": (M.ets, [{"trend": None}, {"trend": "add"}, {"trend": "add", "damped": True}]),
        "Ridge": (M.ridge, [{"alpha": a} for a in (0.1, 1.0, 10.0, 100.0)]),
        "LightGBM": (M.lgbm, [{"num_leaves": nl, "n_estimators": ne, "min_child_samples": mc}
                              for nl, ne, mc in itertools.product([4, 7, 15], [200, 500], [10, 30])]),
        "하이브리드 (회귀+Ridge)": (M.hybrid_ridge, [{"feats": f, "alpha": a}
                                              for f, a in itertools.product(REG_FEATS[series], (1.0, 10.0, 100.0))]),
        "하이브리드 (회귀+LightGBM)": (M.hybrid_lgbm, [{"feats": f, "num_leaves": nl, "n_estimators": 300,
                                                  "min_child_samples": 20}
                                                 for f, nl in itertools.product(REG_FEATS[series], (4, 7))]),
    }
    return g


def key(p):
    return json.dumps(p, ensure_ascii=False, sort_keys=True, default=list)


def tune_one(df, series, model, fn, params):
    t = time.time()
    try:
        r = rolling(df, series, fn, VAL, **params)
        m = summary(r)["all"]
    except Exception as e:   # 수렴 실패 등은 그 설정만 제외
        print(f"  [제외] {series} {model} {key(params)}: {type(e).__name__}: {e}", flush=True)
        m = np.nan
    return {"series": series, "model": model, "params": key(params), "val_MAPE": m, "sec": time.time() - t}


def final_one(df, series, model, fn, params, info, window, seed=None):
    p = dict(params)
    if seed is not None:
        p["seed"] = seed
    r = rolling(df, series, fn, window, info=info, **p)
    return r.assign(series=series, model=model, info=info, seed=seed if seed is not None else 0,
                    window="eval" if window == EVAL else "hold")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", type=int, default=8)
    ap.add_argument("--reuse-tuning", action="store_true", help="outputs/national/tuning.csv를 다시 쓴다 (튜닝 생략)")
    args = ap.parse_args()
    df = pd.read_csv(PROCESSED / "national.csv")
    t0 = time.time()

    # 1) 튜닝 (검증 목표월 2020~2022, 사전예측)
    if args.reuse_tuning:
        tun = pd.read_csv(OUT / "tuning.csv")
    else:
        tasks = [(s, m, fn, p) for s in SERIES for m, (fn, ps) in grid(s).items() for p in ps]
        print(f"튜닝 {len(tasks)}개 설정", flush=True)
        tun = pd.DataFrame(Parallel(n_jobs=args.jobs)(delayed(tune_one)(df, *t) for t in tasks))
        tun.to_csv(OUT / "tuning.csv", index=False, encoding="utf-8-sig")
    # 동점이면 설정 문자열 순 (재실행해도 같은 선택)
    best = (tun.dropna(subset=["val_MAPE"]).assign(_k=lambda d: d.val_MAPE.round(8))
            .sort_values(["_k", "params"], kind="mergesort").groupby(["series", "model"]).first().reset_index())
    print(best[["series", "model", "params", "val_MAPE"]].to_string(index=False), flush=True)

    # 2) 평가·표본 외 (설정 고정). LightGBM은 시드 3개 평균
    fns = {s: {m: fn for m, (fn, _) in grid(s).items()} for s in SERIES}
    jobs = []
    for b in best.itertuples():
        params = json.loads(b.params)
        for k in ("feats", "order", "seasonal", "exog"):
            if k in params:
                params[k] = tuple(params[k])
        seeds = [0, 1, 2] if "LightGBM" in b.model else [None]
        for info in ("ex_ante", "ex_post"):
            for window in (EVAL, HOLD):
                for sd in seeds:
                    jobs.append((b.series, b.model, fns[b.series][b.model], params, info, window, sd))
    parts = Parallel(n_jobs=args.jobs)(delayed(final_one)(df, *j) for j in jobs)
    pred = pd.concat(parts, ignore_index=True)
    pred = (pred.groupby(["series", "model", "info", "window", "origin", "month", "h"], as_index=False)
            .agg(pred=("pred", "mean"), actual=("actual", "first")))
    pred.to_csv(OUT / "predictions.csv", index=False, encoding="utf-8-sig")
    rows = []
    for (s, m, i, w), g in pred.groupby(["series", "model", "info", "window"]):
        rows.append({"series": s, "model": m, "info": i, "window": w, **summary(g)})
    summ = pd.DataFrame(rows)
    summ.to_csv(OUT / "summary.csv", index=False, encoding="utf-8-sig")
    show = summ[(summ.window == "eval") & (summ["info"] == "ex_ante")]
    print(show[["series", "model", "h1", "h3", "h6", "h12", "all"]].round(1).to_string(index=False))
    print(f"완료 {(time.time() - t0) / 60:.1f}분")


if __name__ == "__main__":
    main()
