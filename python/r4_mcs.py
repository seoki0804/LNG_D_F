"""연구 과제 R4 보완: 모델 신뢰집합(Model Confidence Set, Hansen·Lunde·Nason 2011).

DM 검정을 모델·국가마다 여러 번 하면 우연히 유의한 결과가 섞인다(다중비교).
MCS는 '최고 모델과 통계적으로 구별되지 않는 모델 집합'을 신뢰수준 90%로 한 번에 고른다.

- 후보: 본 실험 13개 + 위기 변수 모형(R2) 3개 + 통합 LightGBM(R6) + 파운데이션 4개(R8) + 앙상블 4개(R10)
- 손실: 절대백분율오차(APE), 2023-01~2025-12 (36개월), 사후·사전예측 각각
- arch.bootstrap.MCS: 범위 통계량(method="R"), 정상(stationary) 부트스트랩 블록 길이 3, 반복 5,000, 시드 0

출력: outputs/r4_mcs.md, outputs/r4_mcs.csv
실행: python python/r4_mcs.py   (run_experiment·r2·r6·r8·r10 결과 필요)
"""
import pandas as pd
from arch.bootstrap import MCS

from config import ALL_GEOS, GEO_NAMES, OUTPUTS
from run_experiment import BENCH, MODES, OUT as EXP_OUT

SIZE = 0.10


def candidates():
    cols = ["geo", "model", "mode", "month", "actual", "pred"]
    parts = [pd.read_csv(EXP_OUT / "predictions.csv")[cols]]
    r2 = pd.read_csv(OUTPUTS / "r2_structural_predictions.csv")
    r2 = r2[r2.strategy == "위기 변수"].copy()
    r2["model"] = r2.model.map({BENCH: "회귀 + 위기 변수", "Ridge": "Ridge + 위기 변수",
                                "Gradient Boosting": "GBM + 위기 변수"})
    parts.append(r2[cols])
    r6 = pd.read_csv(OUTPUTS / "r6_global_predictions.csv")
    parts.append(r6[r6.model == "LightGBM"].assign(model="통합 LightGBM (6개국)")[cols])
    parts.append(pd.read_csv(OUTPUTS / "r8_foundation_predictions.csv")[cols])
    ens = pd.read_csv(OUTPUTS / "r10_ensemble_predictions.csv")
    parts.append(ens.assign(model="앙상블: " + ens.model)[cols])
    return pd.concat(parts, ignore_index=True)


def main():
    p = candidates()
    p["ape"] = (p.actual - p.pred).abs() / p.actual * 100
    rows, L = [], ["# R4 모델 신뢰집합 (MCS, 90%)", "",
                   "2023~2025 롤링 1개월 앞, 손실 APE. 'MCS 포함' = 그 나라 최고 모델과 통계적으로 구별되지 않는다 "
                   "(Hansen et al. 2011, 범위 통계량, 정상 부트스트랩 5,000회).", ""]
    for mode in MODES:
        for g in ALL_GEOS:
            loss = p[(p.geo == g) & (p["mode"] == mode)].pivot(index="month", columns="model", values="ape")
            loss = loss.dropna(axis=1)
            mcs = MCS(loss, size=SIZE, reps=5000, block_size=3, method="R", bootstrap="stationary", seed=0)
            mcs.compute()
            pv = mcs.pvalues["Pvalue"]
            for m in loss.columns:
                rows.append({"geo": g, "mode": mode, "model": m, "MAPE": loss[m].mean(),
                             "mcs_p": float(pv.get(m, float("nan"))), "in_mcs": m in mcs.included})
    tab = pd.DataFrame(rows)
    tab.to_csv(OUTPUTS / "r4_mcs.csv", index=False, encoding="utf-8-sig")

    for mode, title in (("ex_post", "사후예측"), ("ex_ante", "사전예측")):
        sub = tab[tab["mode"] == mode]
        L += [f"## {title}: 국가별 MCS 크기와 구성", "", "| 국가 | 후보 수 | MCS 크기 | MCS에 남은 모델 (MAPE %) |",
              "| --- | --- | --- | --- |"]
        for g in ALL_GEOS:
            s = sub[sub.geo == g].sort_values("MAPE")
            keep = s[s.in_mcs]
            L.append(f"| {GEO_NAMES[g]} | {len(s)} | {len(keep)} | "
                     + ", ".join(f"{r.model} ({r.MAPE:.1f})" for r in keep.itertuples()) + " |")
        cnt = (sub.groupby("model").agg(n=("in_mcs", "sum"), mape=("MAPE", "mean"))
               .sort_values(["n", "mape"], ascending=[False, True]))
        L += ["", f"### {title}: 모델별로 MCS에 포함된 나라 수 (6개국 중)", "", "| 모델 | 포함 국가 수 | 6개국 평균 MAPE |",
              "| --- | --- | --- |"]
        for m, r in cnt.iterrows():
            L.append(f"| {m} | {int(r.n)} | {r.mape:.1f} |")
        L.append("")
    (OUTPUTS / "r4_mcs.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
