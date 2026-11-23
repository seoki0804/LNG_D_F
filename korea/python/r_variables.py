"""추가 변수 점검: 석탄 가격, LNG/석탄 가격비, 계통한계가격(SMP), 전력거래량, 산업생산을 넣으면 예측이 좋아지는가.

본 실험에서 튜닝한 설정(회귀 √Y, 하이브리드(회귀+Ridge), SARIMAX)에 후보 변수를 하나씩 더하고,
채택 여부는 검증 구간(목표월 2020~2022) MAPE로만 정한다. 평가 구간(2023~2025)은 결과 보고용이다.
미래 값은 다른 가격 변수처럼 예측 시점 값을 유지한다(사전예측).

출력: outputs/national/variables.csv, variables.md
실행: python python/r_variables.py
"""
import json

import pandas as pd
from joblib import Parallel, delayed

import models_mh as M
from config import OUTPUTS, PROCESSED
from dm_test import dm_test
from mh import EVAL, VAL, rolling, summary

OUT = OUTPUTS / "national"
CANDS = {"log_coal": "석탄 가격(로그)", "log_ratio": "LNG/석탄 가격비(로그)", "log_smp": "SMP(로그)",
         "elec_twh": "전력거래량", "log_ip": "산업생산(로그)"}
MODELS = {"회귀 √Y": (M.reg, "feats"), "하이브리드 (회귀+Ridge)": (M.hybrid_ridge, "feats"), "SARIMAX": (M.sarimax, "exog")}
SERIES = {"power": "발전용", "total": "합계", "city": "도시가스용"}
SARIMAX_MAP = {"log_coal": "coal_usd", "log_ratio": None, "log_smp": "smp", "elec_twh": "elec_twh", "log_ip": "ip"}


def best_params():
    t = pd.read_csv(OUT / "tuning.csv")
    b = (t.dropna(subset=["val_MAPE"]).assign(_k=lambda d: d.val_MAPE.round(8))
         .sort_values(["_k", "params"], kind="mergesort").groupby(["series", "model"]).first())
    return {k: {a: tuple(v) if isinstance(v, list) else v for a, v in json.loads(p).items()} for k, p in b.params.items()}


def with_var(model, params, var):
    p = dict(params)
    key = MODELS[model][1]
    if var is None:
        return p
    if model == "SARIMAX":
        col = SARIMAX_MAP[var]
        if col is None:
            return None
        p[key] = tuple(p[key]) + (col,)
    else:
        p[key] = tuple(p[key]) + (var,)
    return p


def run(df, series, model, params, var, window):
    r = rolling(df, series, MODELS[model][0], window, **params)
    return {"series": series, "model": model, "var": var or "기본", "window": "val" if window == VAL else "eval",
            "MAPE": summary(r)["all"], "pred": r}


def main():
    df = pd.read_csv(PROCESSED / "national.csv")
    df["coal_usd"] = df.coal_usd   # SARIMAX 외생변수는 원 단위로 (로그 효과는 log y 모형이 흡수)
    bp = best_params()
    jobs = []
    for s in SERIES:
        for m in MODELS:
            for v in [None, *CANDS]:
                p = with_var(m, bp[(s, m)], v)
                if p is not None:
                    jobs += [(s, m, p, v, VAL), (s, m, p, v, EVAL)]
    res = Parallel(n_jobs=8)(delayed(run)(df, *j) for j in jobs)
    tab = pd.DataFrame([{k: v for k, v in r.items() if k != "pred"} for r in res])
    tab.to_csv(OUT / "variables.csv", index=False, encoding="utf-8-sig")
    piv = tab.pivot_table(index=["series", "model", "var"], columns="window", values="MAPE").reset_index()
    base = piv[piv["var"] == "기본"].set_index(["series", "model"])
    piv["val_gain"] = [base.loc[(s, m), "val"] - v for s, m, v in zip(piv.series, piv.model, piv.val)]
    piv["eval_gain"] = [base.loc[(s, m), "eval"] - v for s, m, v in zip(piv.series, piv.model, piv["eval"])]
    # DM 검정 (평가 구간, 기본 vs 변수 추가, h를 모은 목표월 평균 APE)
    preds = {(r["series"], r["model"], r["var"], r["window"]): r["pred"] for r in res}
    dmp = []
    for row in piv.itertuples():
        if row.var == "기본":
            dmp.append(None)
            continue
        a = preds[(row.series, row.model, row.var, "eval")].assign(ape=lambda d: (d.pred - d.actual).abs() / d.actual)
        b = preds[(row.series, row.model, "기본", "eval")].assign(ape=lambda d: (d.pred - d.actual).abs() / d.actual)
        ma, mb = a.groupby("month").ape.mean(), b.groupby("month").ape.mean()
        act = a.groupby("month").actual.first()
        # 손실은 목표월별 평균 APE: dm_test에 맞춰 실제값 1, 예측 1−APE로 넣어 APE 손실을 재현
        stat, p = dm_test(act * 0 + 1, 1 - ma.values, 1 - mb.values, h=1, kind="ae")
        dmp.append(p)
    piv["dm_p"] = dmp
    adopted = piv[(piv["var"] != "기본") & (piv.val_gain > 0.1)]
    L = ["# 추가 변수 점검 (1~12개월 앞 사전예측, MAPE %)", "",
         "튜닝한 설정에 후보 변수를 하나씩 더함. 채택 기준: 검증 구간(2020~2022) MAPE가 0.1%p 넘게 줄 것. "
         "평가 구간(2023~2025)은 보고용, DM p는 평가 구간 목표월 평균 APE 기준.", "",
         "| 계열 | 모델 | 변수 | 검증 MAPE | 평가 MAPE | 평가 개선(%p) | DM p | 채택 |", "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for r in piv.sort_values(["series", "model", "val"]).itertuples():
        name = "기본 설정" if r.var == "기본" else CANDS[r.var]
        ok = "✓" if (r.var != "기본" and r.val_gain > 0.1) else ""
        L.append(f"| {SERIES[r.series]} | {r.model} | {name} | {r.val:.2f} | {r.eval:.2f} | "
                 f"{'' if r.var == '기본' else f'{r.eval_gain:+.2f}'} | {'' if pd.isna(r.dm_p) else f'{r.dm_p:.3f}'} | {ok} |")
    L += ["", f"검증 기준으로 채택된 조합: {len(adopted)}개"]
    for r in adopted.itertuples():
        L.append(f"- {SERIES[r.series]} {r.model} + {CANDS[r.var]}: 검증 {r.val_gain:+.2f}%p, 평가 {r.eval_gain:+.2f}%p")
    (OUT / "variables.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
