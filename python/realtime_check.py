"""실시간 예측 견고성 확인: 공표 지연을 반영해도 결론이 유지되는가.

사전예측(ex_ante)은 '예측 달 직전 달의 수요를 안다'고 가정했다. 실제로는 t-1월 말에
수요가 t-2(독일·이탈리아·스페인·네덜란드) 또는 t-3(프랑스·한국)까지만 공표되고, 산업생산은 t-3까지다.
여기서는 그 지연을 그대로 반영한다 (rolling_eval.DEMAND_LAG, IP_LAG; 2026-11-21 관측 기준).

  - 학습: 목표값을 아는 달까지만 (gap = 수요 지연 − 1)
  - 입력: 전월 수요 → k개월 전 수요, 산업생산 → 3개월 전 값, HDD·CDD → 평년값, 소비자요금 → 직전 달 값
  - 시계열 모델(Holt-Winters, 본 실험에서 고른 형태)은 k단계 앞 예측, Chronos-2는 .venv-fm에서 같은 방식으로 실행
  - SARIMAX는 k단계 사이 달의 외생변수 처리가 달라 여기서는 제외한다
        .venv-fm\\Scripts\\python python\\r8_foundation.py --realtime --tag realtime
  - 하이퍼파라미터는 본 실험 설정 그대로 (실시간 입력으로 다시 튜닝하지 않음)
  - 앙상블: 회귀(위기) + Ridge·GBM·LightGBM·MLP + Chronos-2(공변량)

출력: outputs/realtime_check.md, outputs/realtime_check.csv, outputs/realtime_predictions.csv
실행: python python/realtime_check.py
"""
import json
import os
import warnings

os.environ.setdefault("LOKY_MAX_CPU_COUNT", str(os.cpu_count() or 4))

import numpy as np
import pandas as pd
from joblib import Parallel, delayed
from statsmodels.tsa.holtwinters import ExponentialSmoothing

import models as M
from config import ALL_GEOS, GEO_NAMES, OUTPUTS
from dm_test import dm_test
from rolling_eval import DEMAND_LAG, load_country, metrics, realtime_features, rolling_forecast
from run_experiment import BENCH, OUT as EXP_OUT, REG, SEEDS, SPEC

CRISIS = ["crisis", "hdd_crisis"]
ML = ["Ridge", "Lasso", "Gradient Boosting", "LightGBM", "MLP (16-8)"]


def holt_winters_k(k, p):
    """본 실험에서 고른 Holt-Winters 형태로 k단계 앞 예측의 마지막 값."""
    def fit_predict(train, test, features, target):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            m = ExponentialSmoothing(train[target].to_numpy(), trend=p["trend"], seasonal=p["seasonal"],
                                     damped_trend=p["damped"] if p["trend"] else False,
                                     seasonal_periods=12).fit()
        return np.repeat(m.forecast(k)[-1], len(test))
    return fit_predict


def specs(geo, post):
    k = DEMAND_LAG[geo]
    rt = realtime_features(geo)
    par = {m: json.loads(post.loc[(geo, m), "params"]) for m in ML + ["하이브리드 (회귀+GBM 잔차)", "Holt-Winters"]}
    out = [("회귀 √Y~HDD+가격", M.ols(sqrt=True), REG, None),
           ("회귀 + 위기 변수", M.ols(sqrt=True), REG + CRISIS, None),
           ("계절 naive", M.seasonal_naive, ["lag12"], None),
           ("Holt-Winters", holt_winters_k(k, par["Holt-Winters"]), [], None),
           ("하이브리드 (회귀+GBM 잔차)", M.hybrid(REG, rt, par["하이브리드 (회귀+GBM 잔차)"]), rt, None),
           ("Ridge + 위기 변수", SPEC["Ridge"].make(par["Ridge"]), rt + CRISIS, None)]
    for m in ML:
        seeds = SEEDS if SPEC[m].stochastic(par[m]) else [None]
        out += [(m, SPEC[m].make(par[m], seeds=[s] if s is not None else None), rt, s) for s in seeds]
    return out


def task(geo, name, fp, feats, seed):
    df = load_country(geo)
    k = DEMAND_LAG[geo]
    res = rolling_forecast(df, fp, feats, modes=("ex_ante",), gap=k - 1)
    return res.assign(geo=geo, model=name, seed=-1 if seed is None else seed)


def main():
    summ = pd.read_csv(EXP_OUT / "summary.csv")
    post = summ[summ["mode"] == "ex_post"].set_index(["geo", "model"])
    jobs = [(g, *s) for g in ALL_GEOS for s in specs(g, post)]
    raw = pd.concat(Parallel(n_jobs=-1)(delayed(task)(*j) for j in jobs), ignore_index=True)
    pred = (raw.groupby(["geo", "model", "month"], as_index=False)
            .agg(actual=("actual", "first"), pred=("pred", "mean"), n_train=("n_train", "first")))
    fm = OUTPUTS / "r8_foundation_realtime_predictions.csv"
    if fm.exists():
        f = pd.read_csv(fm)
        f = f[f["mode"] == "ex_ante"]
        pred = pd.concat([pred, f[["geo", "model", "month", "actual", "pred"]]], ignore_index=True)
    members = ["회귀 + 위기 변수", "Ridge", "Gradient Boosting", "LightGBM", "MLP (16-8)", "Chronos-2 + 공변량"]
    ens = []
    for g in ALL_GEOS:
        w = pred[pred.geo == g].pivot(index="month", columns="model", values="pred")
        a = pred[pred.geo == g].groupby("month").actual.first()
        use = [m for m in members if m in w]
        ens.append(pd.DataFrame({"geo": g, "model": "앙상블 (회귀·ML·Chronos)", "month": w.index,
                                 "actual": a.loc[w.index].values, "pred": w[use].mean(axis=1).values}))
    pred = pd.concat([pred] + ens, ignore_index=True)
    pred.to_csv(OUTPUTS / "realtime_predictions.csv", index=False, encoding="utf-8-sig")

    exante = summ[summ["mode"] == "ex_ante"].set_index(["geo", "model"]).MAPE
    r2 = pd.read_csv(OUTPUTS / "r2_structural.csv")
    r2 = r2[(r2.strategy == "위기 변수") & (r2["mode"] == "ex_ante")]
    r10 = pd.read_csv(OUTPUTS / "r10_ensemble.csv")
    r8 = pd.read_csv(OUTPUTS / "r8_foundation.csv")
    ref = {}
    for g in ALL_GEOS:
        for m in pred.model.unique():
            if (g, m) in exante.index:
                ref[(g, m)] = exante[(g, m)]
        ref[(g, "회귀 + 위기 변수")] = r2[(r2.geo == g) & (r2.model == BENCH)].MAPE.iloc[0]
        ref[(g, "Ridge + 위기 변수")] = r2[(r2.geo == g) & (r2.model == "Ridge")].MAPE.iloc[0]
        ref[(g, "앙상블 (회귀·ML·Chronos)")] = r10[(r10.geo == g) & (r10.ensemble == "회귀(위기)+ML+Chronos")
                                                 & (r10["mode"] == "ex_ante")].MAPE.iloc[0]
        for m in ("Chronos-2 단변량", "Chronos-2 + 공변량"):
            ref[(g, m)] = r8[(r8.geo == g) & (r8.model == m)].MAPE_ex_ante.iloc[0]

    rows = []
    for (g, m), p in pred.groupby(["geo", "model"]):
        p = p.sort_values("month")
        b = pred[(pred.geo == g) & (pred.model == BENCH)].sort_values("month")
        stat, pv = (np.nan, np.nan) if m == BENCH else dm_test(p.actual.values, p.pred.values, b.pred.values,
                                                               kind="ape")
        rows.append({"geo": g, "model": m, "MAPE_realtime": metrics(p, load_country(g))["MAPE"],
                     "MAPE_exante": ref.get((g, m), np.nan), "DM": stat, "p": pv})
    tab = pd.DataFrame(rows)
    tab.to_csv(OUTPUTS / "realtime_check.csv", index=False, encoding="utf-8-sig")
    order = (tab.groupby("model").MAPE_realtime.mean().sort_values().index.tolist())
    L = ["# 실시간 예측 견고성 확인 (공표 지연 반영)", "",
         "2023~2025 MAPE(%), '실시간 / 사전예측'. 실시간 = 예측 시점에 공표된 자료만 사용 "
         "(수요 t-2: 독일·이탈리아·스페인·네덜란드, t-3: 프랑스·한국, 산업생산 t-3, 평년 HDD). "
         "▲/▼ = 실시간 기준 회귀 대비 DM 검정(APE) p<0.05.", "",
         "| 모델 | " + " | ".join(GEO_NAMES[g] for g in ALL_GEOS) + " | 평균 실시간 | 평균 사전예측 |",
         "| --- |" + " --- |" * (len(ALL_GEOS) + 2)]
    for m in order:
        s = tab[tab.model == m].set_index("geo")
        cells = []
        for g in ALL_GEOS:
            r = s.loc[g]
            mk = (" ▲" if r.DM < 0 else " ▼") if r.p < 0.05 else ""
            cells.append(f"{r.MAPE_realtime:.1f} / {r.MAPE_exante:.1f}{mk}")
        L.append(f"| {m} | " + " | ".join(cells) + f" | {s.MAPE_realtime.mean():.1f} | {s.MAPE_exante.mean():.1f} |")
    (OUTPUTS / "realtime_check.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
