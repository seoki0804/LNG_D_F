"""연구 과제 R10 (하이브리드·앙상블): 여러 모델의 예측 평균이 단일 모델을 이기는가.

앙상블은 평가 구간을 보기 전에 정한 구성만 쓴다 (평가 결과로 고르면 낙관적으로 치우친다).
  ML 평균            : Ridge, GBM, LightGBM, MLP (본 실험 설정)
  회귀(위기)+ML      : 위 4개 + 회귀 √Y~HDD+가격+위기 변수 (R2)
  회귀(위기)+ML+Chronos : 위 5개 + Chronos-2 + 공변량 (R8)
  검증 상위 3        : 국가마다 2020~2022 검증 MAPE가 가장 낮은 튜닝 모델 3개 (평가 구간 미사용)
모두 단순 평균(같은 가중치). 비교 대상: 기준 회귀, 국가별 최고 단일 모델(평가 구간에서 고른 것이라 단일 모델에 유리).

출력: outputs/r10_ensemble.md, outputs/r10_ensemble.csv
실행: python python/r10_ensemble.py   (run_experiment.py, r2_structural.py, r8_foundation.py 결과 필요)
"""
import numpy as np
import pandas as pd

from config import ALL_GEOS, GEO_NAMES, OUTPUTS
from dm_test import dm_test
from rolling_eval import load_country, metrics
from run_experiment import BENCH, MODES, OUT as EXP_OUT

REGC = "회귀(위기 변수)"
CHRONOS = "Chronos-2 + 공변량"
ML = ["Ridge", "Gradient Boosting", "LightGBM", "MLP (16-8)"]
ENSEMBLES = {"ML 평균": ML, "회귀(위기)+ML": [REGC] + ML, "회귀(위기)+ML+Chronos": [REGC] + ML + [CHRONOS]}


def load_preds():
    exp = pd.read_csv(EXP_OUT / "predictions.csv")[["geo", "model", "mode", "month", "actual", "pred"]]
    r2 = pd.read_csv(OUTPUTS / "r2_structural_predictions.csv")
    r2 = r2[(r2.model == BENCH) & (r2.strategy == "위기 변수")].assign(model=REGC)
    r8 = pd.read_csv(OUTPUTS / "r8_foundation_predictions.csv")
    r8 = r8[r8.model == CHRONOS]
    cols = ["geo", "model", "mode", "month", "actual", "pred"]
    return pd.concat([exp, r2[cols], r8[cols]], ignore_index=True)


def main():
    p = load_preds()
    summ = pd.read_csv(EXP_OUT / "summary.csv")
    post = summ[summ["mode"] == "ex_post"]
    rows, ens_preds = [], []
    for g in ALL_GEOS:
        df = load_country(g)
        cand = post[(post.geo == g) & post.val_MAPE.notna()]
        top3 = (cand.assign(_k=cand.val_MAPE.round(10)).sort_values(["_k", "model"], kind="mergesort")
                .model.head(3).tolist())
        sets = {**ENSEMBLES, "검증 상위 3": top3}
        best = post[post.geo == g].sort_values("MAPE").model.iloc[0]
        for mode in MODES:
            q = p[(p.geo == g) & (p["mode"] == mode)]
            wide = q.pivot(index="month", columns="model", values="pred")
            act = q.groupby("month").actual.first()
            for name, members in sets.items():
                e = wide[members].mean(axis=1)
                ens_preds.append(pd.DataFrame({"geo": g, "model": name, "mode": mode, "month": e.index,
                                               "actual": act.loc[e.index].values, "pred": e.values}))
                r = {"geo": g, "ensemble": name, "mode": mode, "members": ", ".join(members),
                     "MAPE": metrics(pd.DataFrame({"actual": act, "pred": e}), df)["MAPE"],
                     "bench_MAPE": metrics(pd.DataFrame({"actual": act, "pred": wide[BENCH]}), df)["MAPE"],
                     "best_single": best,
                     "best_MAPE": metrics(pd.DataFrame({"actual": act, "pred": wide[best]}), df)["MAPE"]}
                r["DM_bench"], r["p_bench"] = dm_test(act.values, e.values, wide[BENCH].values, kind="ape")
                r["DM_best"], r["p_best"] = dm_test(act.values, e.values, wide[best].values, kind="ape")
                rows.append(r)
    tab = pd.DataFrame(rows)
    tab.to_csv(OUTPUTS / "r10_ensemble.csv", index=False, encoding="utf-8-sig")
    pd.concat(ens_preds).to_csv(OUTPUTS / "r10_ensemble_predictions.csv", index=False, encoding="utf-8-sig")

    def mark(r, k):
        return ("▲" if r[f"DM_{k}"] < 0 else "▼") if r[f"p_{k}"] < 0.05 else "·"
    L = ["# R10 앙상블 (단순 평균)", "",
         "2023~2025 롤링 1개월 앞 MAPE(%). (기준 회귀 대비 / 국가 최고 단일 모델 대비) DM 검정 APE p<0.05: "
         "▲ 더 정확, ▼ 덜 정확, · 차이 없음. 최고 단일 모델은 평가 구간에서 고른 것이라 단일 모델에 유리한 비교다.", ""]
    for mode, title in (("ex_post", "사후예측"), ("ex_ante", "사전예측")):
        sub = tab[tab["mode"] == mode]
        L += [f"## {title}", "", "| 앙상블 | " + " | ".join(GEO_NAMES[g] for g in ALL_GEOS) + " | 평균 |",
              "| --- |" + " --- |" * (len(ALL_GEOS) + 1)]
        for name in list(ENSEMBLES) + ["검증 상위 3"]:
            s = sub[sub.ensemble == name].set_index("geo")
            L.append(f"| {name} | " + " | ".join(
                f"{s.loc[g, 'MAPE']:.1f} ({mark(s.loc[g], 'bench')}/{mark(s.loc[g], 'best')})" for g in ALL_GEOS)
                + f" | {s.MAPE.mean():.1f} |")
        s = sub[sub.ensemble == "ML 평균"].set_index("geo")
        L.append("| 기준 회귀 | " + " | ".join(f"{s.loc[g, 'bench_MAPE']:.1f}" for g in ALL_GEOS)
                 + f" | {s.bench_MAPE.mean():.1f} |")
        L.append("| 국가 최고 단일 | " + " | ".join(f"{s.loc[g, 'best_MAPE']:.1f}" for g in ALL_GEOS)
                 + f" | {s.best_MAPE.mean():.1f} |")
        L.append("")
    top = tab[(tab.ensemble == "검증 상위 3") & (tab["mode"] == "ex_post")]
    L += ["검증 상위 3 구성: " + "; ".join(f"{GEO_NAMES[r.geo]} {r.members}" for r in top.itertuples())]
    (OUTPUTS / "r10_ensemble.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
