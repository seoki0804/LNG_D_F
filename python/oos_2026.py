"""2026년 표본 외 검증 (6개국): 2023~2025년으로 고른 모델·설정이 그 뒤 9개월(2026-01~09)에도 통하는가.

- 평가 달: 2026-01~2026-09 (매달 재추정, 1개월 앞). 2026-10은 도매가·산업생산이 아직 없다.
  스페인은 2026-08 수요가 0(자료 오류, 결측 처리)이라 2026-07까지만 평가한다.
- 2026년 HDD·CDD는 Eurostat 공개 전이라 보정값: 독일 DWD 관측소(fetch_dwd.py), 이탈리아·프랑스·스페인·네덜란드
  Open-Meteo ERA5(fetch_openmeteo.py), 한국은 원래 기상청 ASOS로 계산한 값.
- 2026년 소비자요금: 유럽은 HICP ECOICOP ver.2를 2025-12 비율로 이은 값, 한국은 KOSIS 도시가스 CPI.
- 모델·하이퍼파라미터는 본 실험(run_experiment.py)에서 고정한 것 그대로 + 위기 변수 모형 + Chronos-2 + 앙상블.
- 파운데이션 모델은 .venv-fm에서 먼저 실행한다:
    .venv-fm\\Scripts\\python python\\r8_foundation.py --start 2026-01 --end 2026-09 --tag oos2026

출력: outputs/oos_2026.md, outputs/oos_2026.csv, outputs/oos_2026_predictions.csv
실행: python python/oos_2026.py
"""
import json
import os

os.environ.setdefault("LOKY_MAX_CPU_COUNT", str(os.cpu_count() or 4))

import numpy as np
import pandas as pd
from joblib import Parallel, delayed
from scipy.stats import spearmanr

from config import ALL_GEOS, GEO_NAMES, OUTPUTS
from dm_test import dm_test
from rolling_eval import load_country, metrics, rolling_forecast
from run_experiment import BENCH, MODES, OUT as EXP_OUT, SEEDS, SPEC, SPECS

START, END = "2026-01", "2026-09"
CRISIS = ["crisis", "hdd_crisis"]
EXTRA = {"회귀 + 위기 변수": (BENCH, CRISIS), "Ridge + 위기 변수": ("Ridge", CRISIS)}
ENS = ["회귀 + 위기 변수", "Ridge", "Gradient Boosting", "LightGBM", "MLP (16-8)", "Chronos-2 + 공변량"]


def valid_end(geo):
    """START부터 수요와 전월 수요가 끊김 없이 있는 마지막 달 (스페인은 2026-08 자료 오류로 2026-07)."""
    d = load_country(geo).set_index("month")
    last = None
    for m in pd.period_range(START, END, freq="M").strftime("%Y-%m"):
        if m not in d.index or pd.isna(d.loc[m, "y"]) or pd.isna(d.loc[m, "lag1"]):
            break
        last = m
    return last


def task(geo, name, base, params, feats, seed):
    df = load_country(geo)
    fp = SPEC[base].make(params, seeds=[seed] if seed is not None else None)
    res = rolling_forecast(df, fp, feats, eval_start=START, eval_end=valid_end(geo), modes=MODES)
    return res.assign(geo=geo, model=name, seed=-1 if seed is None else seed)


def reference():
    """2023~2025 사후예측 MAPE (순위 비교용)."""
    summ = pd.read_csv(EXP_OUT / "summary.csv")
    ref = summ[summ["mode"] == "ex_post"][["geo", "model", "MAPE"]]
    r2 = pd.read_csv(OUTPUTS / "r2_structural.csv")
    r2 = r2[(r2.strategy == "위기 변수") & (r2["mode"] == "ex_post") & r2.model.isin([BENCH, "Ridge"])].copy()
    r2["model"] = r2.model.map({BENCH: "회귀 + 위기 변수", "Ridge": "Ridge + 위기 변수"})
    r8 = pd.read_csv(OUTPUTS / "r8_foundation.csv").rename(columns={"MAPE_ex_post": "MAPE"})
    r10 = pd.read_csv(OUTPUTS / "r10_ensemble.csv")
    r10 = r10[(r10.ensemble == "회귀(위기)+ML+Chronos") & (r10["mode"] == "ex_post")].assign(
        model="앙상블 (회귀·ML·Chronos)")
    return pd.concat([ref, r2[["geo", "model", "MAPE"]], r8[["geo", "model", "MAPE"]],
                      r10[["geo", "model", "MAPE"]]], ignore_index=True).set_index(["geo", "model"]).MAPE


def main():
    summ = pd.read_csv(EXP_OUT / "summary.csv")
    post = summ[summ["mode"] == "ex_post"].set_index(["geo", "model"])
    jobs = []
    for g in ALL_GEOS:
        for s in SPECS:
            p = json.loads(post.loc[(g, s.name), "params"]) if s.grid else {}
            jobs += [(g, s.name, s.name, p, s.features, sd) for sd in (SEEDS if s.stochastic(p) else [None])]
        for name, (base, extra) in EXTRA.items():
            p = json.loads(post.loc[(g, base), "params"]) if SPEC[base].grid else {}
            jobs.append((g, name, base, p, list(SPEC[base].features) + extra, None))
    raw = pd.concat(Parallel(n_jobs=-1)(delayed(task)(*j) for j in jobs), ignore_index=True)
    pred = (raw.groupby(["geo", "model", "mode", "month"], as_index=False)
            .agg(actual=("actual", "first"), pred=("pred", "mean")))
    fm = OUTPUTS / "r8_foundation_oos2026_predictions.csv"
    if fm.exists():
        f = pd.read_csv(fm)
        ends = {g: valid_end(g) for g in ALL_GEOS}
        f = f[f.month <= f.geo.map(ends)]   # 자료 오류 뒤의 달은 평가하지 않는다
        pred = pd.concat([pred, f[["geo", "model", "mode", "month", "actual", "pred"]]], ignore_index=True)
    ens = []
    for (g, mode), q in pred.groupby(["geo", "mode"]):
        w = q.pivot(index="month", columns="model", values="pred")
        a = q.groupby("month").actual.first()
        use = [m for m in ENS if m in w]
        ens.append(pd.DataFrame({"geo": g, "model": "앙상블 (회귀·ML·Chronos)", "mode": mode, "month": w.index,
                                 "actual": a.loc[w.index].values, "pred": w[use].mean(axis=1).values}))
    pred = pd.concat([pred] + ens, ignore_index=True)
    pred.to_csv(OUTPUTS / "oos_2026_predictions.csv", index=False, encoding="utf-8-sig")

    ref = reference()
    rows = []
    for (g, m), p in pred.groupby(["geo", "model"]):
        df = load_country(g)
        r = {"geo": g, "model": m, "MAPE_2023_2025": ref.get((g, m), np.nan)}
        for mode in MODES:
            q = p[p["mode"] == mode].sort_values("month")
            r[f"MAPE_{mode}"] = metrics(q, df, eval_start=START)["MAPE"]
        q = p[p["mode"] == "ex_post"].sort_values("month")
        b = pred[(pred.geo == g) & (pred.model == BENCH) & (pred["mode"] == "ex_post")].sort_values("month")
        r["DM"], r["p"] = (np.nan, np.nan) if m == BENCH else dm_test(q.actual.values, q.pred.values,
                                                                      b.pred.values, kind="ape")
        rows.append(r)
    tab = pd.DataFrame(rows)
    tab.to_csv(OUTPUTS / "oos_2026.csv", index=False, encoding="utf-8-sig")

    post26 = tab.pivot(index="model", columns="geo", values="MAPE_ex_post")[ALL_GEOS]
    ante26 = tab.pivot(index="model", columns="geo", values="MAPE_ex_ante")[ALL_GEOS]
    ref_avg = tab.groupby("model").MAPE_2023_2025.mean()
    post26["평균"] = post26.mean(axis=1)
    ante26["평균"] = ante26.mean(axis=1)
    post26 = post26.sort_values("평균")
    ok = ref_avg.reindex(post26.index).notna()
    rho = spearmanr(post26["평균"][ok], ref_avg.reindex(post26.index)[ok]).statistic
    per = {g: spearmanr(*tab[tab.geo == g][["MAPE_ex_post", "MAPE_2023_2025"]].dropna().T.values).statistic
           for g in ALL_GEOS}
    L = ["# 2026년 표본 외 검증 (6개국, 2026-01~2026-09, 국가당 9회; 스페인은 자료 오류로 7회)", "",
         "모델·설정은 2023~2025 평가 때 그대로. 2026년 HDD는 보정값(독일 DWD, 유럽 4개국 Open-Meteo ERA5, 한국 기상청). "
         "▲/▼ = 기준 회귀 대비 DM 검정(APE) p<0.05 — 9개월이라 검정력이 낮다.", "",
         "## 사후예측 MAPE (%)", "", "| 모델 | " + " | ".join(GEO_NAMES[g] for g in ALL_GEOS)
         + " | 평균 2026 | 평균 2023~2025 | 평균 사전예측 2026 |", "| --- |" + " --- |" * (len(ALL_GEOS) + 3)]
    for m, r in post26.iterrows():
        cells = []
        for g in ALL_GEOS:
            x = tab[(tab.geo == g) & (tab.model == m)].iloc[0]
            mk = (" ▲" if x.DM < 0 else " ▼") if x.p < 0.05 else ""
            cells.append(f"{r[g]:.1f}{mk}")
        L.append(f"| {m} | " + " | ".join(cells) + f" | {r['평균']:.1f} | {ref_avg.get(m, np.nan):.1f} | "
                 f"{ante26.loc[m, '평균']:.1f} |")
    L += ["", f"6개국 평균 MAPE 순위의 2023~2025 대비 Spearman 상관: {rho:.2f}. 국가별: "
          + ", ".join(f"{GEO_NAMES[g]} {per[g]:.2f}" for g in ALL_GEOS)]
    (OUTPUTS / "oos_2026.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
