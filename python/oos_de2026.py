"""독일 2026년 표본 외 검증: 2023~2025년으로 고른 모델·설정이 그 뒤 9개월(2026-01~09)에도 통하는가.

- 평가 달: 2026-01~2026-09 (매달 재추정, 1개월 앞). 2026-10은 도매가·산업생산이 아직 없다.
- 2026년 HDD·CDD는 Eurostat 공개 전이라 DWD 일평균기온으로 계산해 보정한 값 (fetch_dwd.py, 보정 R² 0.999).
- 2026년 소비자요금은 HICP ECOICOP ver.2 가스 지수를 2025-12 비율로 이어 붙인 값 (build_dataset.py).
- 모델·하이퍼파라미터는 본 실험(run_experiment.py)에서 고정한 것 그대로 + R2의 위기 변수 모형.
- 파운데이션 모델은 .venv-fm에서 먼저 실행한다:
    .venv-fm\\Scripts\\python python\\r8_foundation.py --geos DE --start 2026-01 --end 2026-09 --tag de2026

출력: outputs/oos_de2026.md, outputs/oos_de2026.csv, outputs/oos_de2026_predictions.csv
실행: python python/oos_de2026.py
"""
import json
import os

os.environ.setdefault("LOKY_MAX_CPU_COUNT", str(os.cpu_count() or 4))

import numpy as np
import pandas as pd
from joblib import Parallel, delayed

from config import OUTPUTS
from dm_test import dm_test
from rolling_eval import load_country, metrics, rolling_forecast
from run_experiment import BENCH, MODES, OUT as EXP_OUT, SEEDS, SPEC, SPECS

GEO, START, END = "DE", "2026-01", "2026-09"
CRISIS = ["crisis", "hdd_crisis"]
EXTRA = {"회귀 √Y~HDD+가격 + 위기 변수": BENCH, "Ridge + 위기 변수": "Ridge"}


def task(name, base, params, feats, seed):
    df = load_country(GEO)
    fp = SPEC[base].make(params, seeds=[seed] if seed is not None else None)
    res = rolling_forecast(df, fp, feats, eval_start=START, eval_end=END, modes=MODES)
    return res.assign(model=name, seed=-1 if seed is None else seed)


def main():
    summ = pd.read_csv(EXP_OUT / "summary.csv")
    post = summ[(summ.geo == GEO) & (summ["mode"] == "ex_post")].set_index("model")
    jobs = []
    for s in SPECS:
        p = json.loads(post.loc[s.name, "params"]) if s.grid else {}
        jobs += [(s.name, s.name, p, s.features, sd) for sd in (SEEDS if s.stochastic(p) else [None])]
    for name, base in EXTRA.items():
        p = json.loads(post.loc[base, "params"]) if SPEC[base].grid else {}
        jobs.append((name, base, p, list(SPEC[base].features) + CRISIS, None))
    raw = pd.concat(Parallel(n_jobs=-1)(delayed(task)(*j) for j in jobs), ignore_index=True)
    pred = (raw.groupby(["model", "mode", "month"], as_index=False)
            .agg(actual=("actual", "first"), pred=("pred", "mean")))
    fm = OUTPUTS / "r8_foundation_de2026_predictions.csv"
    if fm.exists():
        f = pd.read_csv(fm)
        pred = pd.concat([pred, f[["model", "mode", "month", "actual", "pred"]]], ignore_index=True)
    pred.to_csv(OUTPUTS / "oos_de2026_predictions.csv", index=False, encoding="utf-8-sig")

    df = load_country(GEO)
    r2 = pd.read_csv(OUTPUTS / "r2_structural.csv")
    r8 = pd.read_csv(OUTPUTS / "r8_foundation.csv")
    ref = {**post.MAPE.to_dict(),
           "회귀 √Y~HDD+가격 + 위기 변수": r2[(r2.geo == GEO) & (r2.model == BENCH) & (r2.strategy == "위기 변수")
                                              & (r2["mode"] == "ex_post")].MAPE.iloc[0],
           "Ridge + 위기 변수": r2[(r2.geo == GEO) & (r2.model == "Ridge") & (r2.strategy == "위기 변수")
                                 & (r2["mode"] == "ex_post")].MAPE.iloc[0],
           **r8[r8.geo == GEO].set_index("model").MAPE_ex_post.to_dict()}
    rows = []
    bench = pred[(pred.model == BENCH) & (pred["mode"] == "ex_post")].sort_values("month")
    for m in pred.model.unique():
        r = {"model": m, "MAPE_2023_2025": ref.get(m, np.nan)}
        for mode in MODES:
            p = pred[(pred.model == m) & (pred["mode"] == mode)].sort_values("month")
            r[f"MAPE_{mode}"] = metrics(p, df, eval_start=START)["MAPE"]
            if mode == "ex_post":
                r["RMSE"] = metrics(p, df, eval_start=START)["RMSE"]
                r["DM"], r["p"] = (np.nan, np.nan) if m == BENCH else dm_test(p.actual.values, p.pred.values,
                                                                              bench.pred.values, kind="ape")
        rows.append(r)
    tab = pd.DataFrame(rows).sort_values("MAPE_ex_post")
    tab.to_csv(OUTPUTS / "oos_de2026.csv", index=False, encoding="utf-8-sig")
    rho = tab[["MAPE_ex_post", "MAPE_2023_2025"]].dropna().corr(method="spearman").iloc[0, 1]

    L = ["# 독일 2026년 표본 외 검증 (2026-01~2026-09, 9회)", "",
         "모델·설정은 2023~2025 평가 때 그대로. 2026년 HDD·CDD는 DWD 일평균기온 보정값(보정 R² 0.999), "
         "소비자요금은 HICP ECOICOP ver.2를 이어 붙인 값. DM 검정은 기준 회귀 대비(APE, 사후) — 9개월이라 검정력이 낮다.", "",
         "| 모델 | 2026 MAPE 사후 | 2026 MAPE 사전 | RMSE 사후 (PJ) | DM p vs 기준 | 2023~2025 MAPE 사후 |",
         "| --- | --- | --- | --- | --- | --- |"]
    for r in tab.itertuples():
        dmp = "기준" if r.model == BENCH else f"{r.p:.3f}{' (더 정확)' if r.DM < 0 else ''}"
        L.append(f"| {r.model} | {r.MAPE_ex_post:.1f} | {r.MAPE_ex_ante:.1f} | {r.RMSE:.1f} | {dmp} | "
                 f"{r.MAPE_2023_2025:.1f} |")
    L += ["", f"2023~2025 순위와 2026 순위의 Spearman 상관: {rho:.2f}"]
    (OUTPUTS / "oos_de2026.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
