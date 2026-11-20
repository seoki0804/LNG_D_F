"""연구 과제 R6 (통합 대 국가별): 6개국을 한 모델로 학습하면 국가별 모델보다 정확한가.

통합(global) 모델 (Montero-Manso & Hyndman 2021)
  - 6개국 행을 쌓아 한 모델을 학습한다. 학습 표본이 약 6배.
  - 국가마다 수요 단위·규모가 달라 매 학습창에서 국가별로 정규화한다 (누수 없음):
      수요·전월·12개월 전 수요 → 그 나라 학습창 평균 수요로 나눔
      소비자요금·산업생산 → 그 나라 학습창 평균으로 나눔
      HDD·CDD(도일), 도매가(USD/MMBtu), 월 sin·cos → 그대로
      국가 원-핫 6개 추가
  - 예측값 × 그 나라 평균 수요 = 원 단위 예측.
  - 하이퍼파라미터: 2020~2022 검증 구간의 6개국 평균 MAPE로 고른 뒤 고정 (본 실험과 같은 절차).
  - 비교: 같은 종류의 국가별 모델(run_experiment.py 결과)과 국가마다 DM 검정(APE, 사후예측).

출력: outputs/r6_global.md, outputs/r6_global.csv, outputs/r6_global_predictions.csv
실행: python python/r6_global.py   (run_experiment.py 결과 필요)
"""
import itertools
import json
import os
import time

os.environ.setdefault("LOKY_MAX_CPU_COUNT", str(os.cpu_count() or 4))

import numpy as np
import pandas as pd
from joblib import Parallel, delayed
from lightgbm import LGBMRegressor
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

import models  # noqa: F401  (경고 필터 설정)
from config import ALL_GEOS, EVAL_END, EVAL_START, GEO_NAMES, OUTPUTS
from dm_test import dm_test
from rolling_eval import BASE_FEATURES, TRAIN_START, eval_months, load_country, make_test, metrics
from run_experiment import MODES, OUT as EXP_OUT, SEEDS

VAL_START, VAL_END = "2020-01", "2022-12"
Y_SCALED = ["y", "lag1", "lag12"]
X_SCALED = ["price_retail", "ip"]
ONEHOT = [f"is_{g}" for g in ALL_GEOS]
FEATS = BASE_FEATURES + ONEHOT


def grid(**axes):
    return [dict(zip(axes, v)) for v in itertools.product(*axes.values())]


MODELS = {   # 이름: (만들기(params, seed), 그리드, 랜덤 여부)
    "Ridge": (lambda p, s: make_pipeline(StandardScaler(), Ridge(alpha=p["alpha"])),
              grid(alpha=[0.1, 1, 10, 100]), False),
    "Gradient Boosting": (lambda p, s: GradientBoostingRegressor(random_state=s, **p),
                          grid(learning_rate=[0.05, 0.1], n_estimators=[200, 500], max_depth=[3, 4]), False),
    "LightGBM": (lambda p, s: LGBMRegressor(learning_rate=0.05, n_estimators=400, random_state=s, n_jobs=1,
                                            verbose=-1, **p),
                 grid(num_leaves=[7, 15, 31], min_child_samples=[10, 20]), False),
    "MLP (16-8)": (lambda p, s: make_pipeline(StandardScaler(), MLPRegressor(
        hidden_layer_sizes=(16, 8), alpha=p["alpha"], max_iter=5000, random_state=s)),
        grid(alpha=[1e-3, 1e-1, 1.0]), True),
}


def load_all():
    frames = []
    for g in ALL_GEOS:
        d = load_country(g)
        for h in ALL_GEOS:
            d[f"is_{h}"] = float(g == h)
        frames.append(d)
    return frames


def scale(train_g, rows):
    """그 나라 학습창 평균으로 수요·요금·산업생산을 나눈다."""
    rows = rows.copy()
    ym = train_g["y"].mean()
    for c in Y_SCALED:
        rows[c] = rows[c] / ym
    for c in X_SCALED:
        rows[c] = rows[c] / train_g[c].mean()
    return rows, ym


def run(name, params, seed, eval_start, eval_end, modes):
    make, _, _ = MODELS[name]
    frames = load_all()
    need = FEATS + ["y"]
    out = []
    for t in eval_months(eval_start, eval_end):
        tr_parts, te_parts = [], []
        for d in frames:
            tr = d[(d.month >= TRAIN_START) & (d.month < t)].dropna(subset=need)
            row = d[d.month == t]
            tr_s, ym = scale(tr, tr)
            for mode in modes:
                te = make_test(row, BASE_FEATURES, mode)
                te_s, _ = scale(tr, te)
                te_parts.append(te_s.assign(mode=mode, ym=ym, actual=row["y"].iloc[0]))
            tr_parts.append(tr_s)
        train = pd.concat(tr_parts, ignore_index=True)
        test = pd.concat(te_parts, ignore_index=True)
        model = make(params, seed).fit(train[FEATS], train["y"])
        test["pred"] = model.predict(test[FEATS]) * test["ym"]
        out.append(test[["geo", "month", "mode", "actual", "pred"]])
    return pd.concat(out, ignore_index=True).assign(model=name, seed=-1 if seed is None else seed)


def mape(df):
    return float(((df.actual - df.pred).abs() / df.actual).mean() * 100)


def tune_task(name, params):
    r = run(name, params, 0, VAL_START, VAL_END, ("ex_post",))
    return {"model": name, "params": json.dumps(params), "val_MAPE": r.groupby("geo").apply(mape).mean()}


def main():
    t0 = time.time()
    tasks = [(n, p) for n, (_, g, _) in MODELS.items() for p in g]
    print(f"[1/2] 튜닝 {len(tasks)}개", flush=True)
    tun = pd.DataFrame(Parallel(n_jobs=-1)(delayed(tune_task)(*t) for t in tasks))
    best = (tun.assign(_k=tun.val_MAPE.round(10)).sort_values(["_k", "params"], kind="mergesort")
            .groupby("model").head(1).set_index("model"))
    jobs = []
    for n, (_, _, stoch) in MODELS.items():
        p = json.loads(best.loc[n, "params"])
        jobs += [(n, p, sd) for sd in (SEEDS if stoch else [0])]
    print(f"[2/2] 평가 {len(jobs)}개 ({time.time() - t0:.0f}s)", flush=True)
    raw = pd.concat(Parallel(n_jobs=-1)(delayed(run)(n, p, sd, EVAL_START, EVAL_END, MODES)
                                        for n, p, sd in jobs), ignore_index=True)
    glob = (raw.groupby(["geo", "model", "mode", "month"], as_index=False)
            .agg(actual=("actual", "first"), pred=("pred", "mean")))
    glob.to_csv(OUTPUTS / "r6_global_predictions.csv", index=False, encoding="utf-8-sig")

    local = pd.read_csv(EXP_OUT / "predictions.csv")
    rows = []
    for g in ALL_GEOS:
        df = load_country(g)
        for n in MODELS:
            r = {"geo": g, "model": n, "params": best.loc[n, "params"]}
            for mode in MODES:
                gp = glob[(glob.geo == g) & (glob.model == n) & (glob["mode"] == mode)].sort_values("month")
                lp = local[(local.geo == g) & (local.model == n) & (local["mode"] == mode)].sort_values("month")
                r[f"global_{mode}"] = metrics(gp, df)["MAPE"]
                r[f"local_{mode}"] = metrics(lp, df)["MAPE"]
                if mode == "ex_post":
                    r["DM"], r["p"] = dm_test(gp.actual.values, gp.pred.values, lp.pred.values, kind="ape")
            rows.append(r)
    tab = pd.DataFrame(rows)
    tab.to_csv(OUTPUTS / "r6_global.csv", index=False, encoding="utf-8-sig")

    L = ["# R6 통합 모델 vs 국가별 모델", "",
         "2023~2025 롤링 1개월 앞 MAPE(%), '통합 / 국가별'. ▲/▼ = 통합이 국가별보다 DM 검정(APE) p<0.05로 "
         "더 정확/덜 정확. 하이퍼파라미터는 2020~2022 검증 구간에서 고정.", ""]
    for mode, title in (("ex_post", "사후예측"), ("ex_ante", "사전예측")):
        L += [f"## {title}", "", "| 모델 | " + " | ".join(GEO_NAMES[g] for g in ALL_GEOS) + " | 평균 |",
              "| --- |" + " --- |" * (len(ALL_GEOS) + 1)]
        for n in MODELS:
            cells = []
            for g in ALL_GEOS:
                r = tab[(tab.geo == g) & (tab.model == n)].iloc[0]
                txt = f"{r[f'global_{mode}']:.1f} / {r[f'local_{mode}']:.1f}"
                if mode == "ex_post" and r.p < 0.05:
                    txt += " ▲" if r.DM < 0 else " ▼"
                cells.append(txt)
            sub = tab[tab.model == n]
            cells.append(f"{sub[f'global_{mode}'].mean():.1f} / {sub[f'local_{mode}'].mean():.1f}")
            L.append(f"| {n} | " + " | ".join(cells) + " |")
        L.append("")
    L += ["선택된 통합 모델 설정: " + "; ".join(f"{n} {best.loc[n, 'params']}" for n in MODELS)]
    (OUTPUTS / "r6_global.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))
    print(f"저장: outputs/r6_global.md ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
