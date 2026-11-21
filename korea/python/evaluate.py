"""전국 용도별 다기간 예측 결과 정리: 앙상블, 예측 시계별 MAPE, DM 검정, 모델 신뢰집합(MCS), 기온 정보의 가치.

  - 앙상블: 평가 전에 정한 구성(회귀 √Y, SARIMAX, LightGBM, Chronos-2 + 공변량)의 단순 평균
  - DM 검정(HLN 보정, APE): 각 모델 vs 계절 naive, 예측 시계 h마다 (손실 자기상관 시차 h−1)
  - MCS(90%, 범위 통계량, 정상 부트스트랩 블록 3, 5,000회): h = 1, 3, 6, 12와 전체 평균 손실
  - 기온 정보의 가치: 사전예측(평년 기온) MAPE − 사후예측(실제 기온) MAPE

입력: outputs/national/predictions.csv (run_national.py), foundation.csv (foundation_mh.py)
출력: outputs/national/{all_predictions,summary_all,dm,mcs}.csv, report.md
"""
import numpy as np
import pandas as pd
from arch.bootstrap import MCS

from config import OUTPUTS
from dm_test import dm_test
from mh import HORIZONS, summary

D = OUTPUTS / "national"
ENS_PARTS = ["회귀 √Y", "SARIMAX", "LightGBM", "Chronos-2 + 공변량"]
ENS = "앙상블"
BENCH = "계절 naive"
KEYS = ["series", "info", "window", "origin", "month", "h"]
SERIES = {"total": "합계", "city": "도시가스용", "power": "발전용"}


def load():
    p = pd.read_csv(D / "predictions.csv")
    f = D / "foundation.csv"
    if f.exists():
        fm = pd.read_csv(f).rename(columns={"name": "series"})
        fm["window"] = np.where(fm.month >= "2026-01", "hold", "eval")
        fm = fm[(fm.month >= "2023-01") & fm.actual.notna()]
        p = pd.concat([p, fm[KEYS + ["model", "pred", "actual"]]], ignore_index=True)
    have = p.groupby(KEYS + ["model"]).size().unstack("model")
    ens = (p[p.model.isin(ENS_PARTS)].groupby(KEYS).agg(pred=("pred", "mean"), actual=("actual", "first"),
                                                         k=("pred", "size")).reset_index())
    ens = ens[ens.k == len(ENS_PARTS)].drop(columns="k").assign(model=ENS)
    return pd.concat([p, ens], ignore_index=True), have


def main():
    p, _ = load()
    p.to_csv(D / "all_predictions.csv", index=False, encoding="utf-8-sig")
    rows = [{"series": s, "model": m, "info": i, "window": w, **summary(g)}
            for (s, m, i, w), g in p.groupby(["series", "model", "info", "window"])]
    summ = pd.DataFrame(rows)
    summ.to_csv(D / "summary_all.csv", index=False, encoding="utf-8-sig")

    ev = p[p.window == "eval"].assign(ape=lambda d: (d.pred - d.actual).abs() / d.actual)
    # DM 검정: h마다 모델 vs 계절 naive (같은 목표월 36개)
    dm_rows = []
    for (s, i, h), g in ev.groupby(["series", "info", "h"]):
        w = g.pivot_table(index="month", columns="model", values="pred")
        a = g.groupby("month").actual.first().reindex(w.index)
        for m in w.columns.drop(BENCH, errors="ignore"):
            ok = w[m].notna() & w[BENCH].notna()
            stat, pv = dm_test(a[ok].values, w.loc[ok, m].values, w.loc[ok, BENCH].values, h=h, kind="ape")
            dm_rows.append({"series": s, "info": i, "h": h, "model": m, "dm": stat, "p": pv})
    pd.DataFrame(dm_rows).to_csv(D / "dm.csv", index=False, encoding="utf-8-sig")

    # MCS: h = 1, 3, 6, 12, 그리고 목표월별 전 시계 평균 손실
    mcs_rows = []
    for (s, i), g in ev.groupby(["series", "info"]):
        for hname, sub in [(f"h{h}", g[g.h == h]) for h in (1, 3, 6, 12)] + [("all", g)]:
            L = sub.groupby(["month", "model"]).ape.mean().unstack().dropna(axis=1)
            res = MCS(L, size=0.10, reps=5000, block_size=3, method="R", bootstrap="stationary", seed=0)
            res.compute()
            inc = set(res.included)
            for m in L.columns:
                mcs_rows.append({"series": s, "info": i, "horizon": hname, "model": m, "MAPE": L[m].mean() * 100,
                                 "in_mcs": m in inc})
    mcs = pd.DataFrame(mcs_rows)
    mcs.to_csv(D / "mcs.csv", index=False, encoding="utf-8-sig")

    # 보고서
    L = ["# 전국 용도별 1~12개월 앞 예측", "",
         "평가 목표월 2023-01~2025-12 (모든 h에서 같은 36개월), 설정은 2020~2022 목표월에서 선택. MAPE(%).", ""]
    for i, title in (("ex_ante", "사전예측 (평년 기온, 실제 예측과 같은 조건)"), ("ex_post", "사후예측 (실제 기온)")):
        for s, sname in SERIES.items():
            t = summ[(summ.series == s) & (summ["info"] == i) & (summ.window == "eval")].sort_values("all")
            inc = mcs[(mcs.series == s) & (mcs["info"] == i) & (mcs.horizon == "all") & mcs.in_mcs].model.tolist()
            L += [f"## {sname}: {title}", "", "| 모델 | h=1 | h=3 | h=6 | h=12 | 1~12 평균 | MCS |", "| --- | --- | --- | --- | --- | --- | --- |"]
            for r in t.itertuples():
                L.append(f"| {r.model} | {r.h1:.1f} | {r.h3:.1f} | {r.h6:.1f} | {r.h12:.1f} | {r.all:.1f} | "
                         f"{'✓' if r.model in inc else ''} |")
            L.append("")
    # 기온 정보의 가치
    L += ["## 기온 정보의 가치: 사전 − 사후 MAPE (%p, 1~12 평균)", "", "| 모델 | 합계 | 도시가스용 | 발전용 |", "| --- | --- | --- | --- |"]
    e = summ[summ.window == "eval"].pivot_table(index=["model", "series"], columns="info", values="all")
    gap = (e.ex_ante - e.ex_post).unstack("series")
    for m, r in gap.iterrows():
        L.append(f"| {m} | {r.get('total', np.nan):.1f} | {r.get('city', np.nan):.1f} | {r.get('power', np.nan):.1f} |")
    # 표본 외
    L += ["", "## 2026년 1~9월 표본 외 (사전예측, 1~12 평균)", "", "| 모델 | 합계 | 도시가스용 | 발전용 |", "| --- | --- | --- | --- |"]
    o = summ[(summ.window == "hold") & (summ["info"] == "ex_ante")].pivot_table(index="model", columns="series", values="all")
    for m, r in o.sort_values("total").iterrows():
        L.append(f"| {m} | {r.get('total', np.nan):.1f} | {r.get('city', np.nan):.1f} | {r.get('power', np.nan):.1f} |")
    (D / "report.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
