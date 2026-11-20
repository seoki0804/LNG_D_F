"""장기 롤링 평가: 36개월보다 긴 평가 구간에서도 결론이 유지되는가 (검정력 보강).

설계 (본 실험과 같은 절차, 기간만 길게)
  유럽 5개국: 학습 2009-01~ (확장창), 검증 2015-01~2017-12에서 튜닝 → 평가 2018-01~2025-12 (96개월)
  한국      : 학습 2016-01~, 검증 2019-01~2019-12에서 튜닝 → 평가 2020-01~2025-12 (72개월)
  평가 구간이 위기 전(2018~2021)·위기(2022)·위기 후(2023~2025)를 모두 포함한다.

모델: 본 실험 13개 + 회귀/Ridge + 위기 변수 + Chronos-2(단변량·공변량, .venv-fm에서 먼저 실행) + 앙상블
      (앙상블 = 회귀(위기)·Ridge·GBM·LightGBM·MLP·Chronos-2(공변량) 단순 평균, 본 실험과 같은 구성)
검정: 국가별 MCS(90%), 6개국 평균 손실 MCS(공통 구간 2020-01~2025-12), 국면별 MAPE.

Chronos-2 장기 예측 (먼저):
    .venv-fm\\Scripts\\python python\\r8_foundation.py --geos DE IT FR ES NL --start 2018-01 --end 2025-12 --tag long_eu
    .venv-fm\\Scripts\\python python\\r8_foundation.py --geos KR --start 2020-01 --end 2025-12 --tag long_kr

출력: outputs/long_eval/ (summary.csv, predictions_all.csv, mcs.csv, regimes.csv, report.md)
실행: python python/long_eval.py            (본 실험 13개 재튜닝·평가 포함, 12코어 약 20분)
      python python/long_eval.py --reuse    (13개 모델 결과가 있으면 재사용)
"""
import json
import os
import sys
import time

os.environ.setdefault("LOKY_MAX_CPU_COUNT", str(os.cpu_count() or 4))

import numpy as np
import pandas as pd
from arch.bootstrap import MCS
from joblib import Parallel, delayed

from config import ALL_GEOS, EU_GEOS, GEO_NAMES, OUTPUTS
from rolling_eval import load_country, metrics
from run_experiment import BENCH, MODES, REG, SEEDS, SPEC, final_task, run

OUT = OUTPUTS / "long_eval"
CRISIS = ["crisis", "hdd_crisis"]
DESIGNS = {g: {"train_start": "2009-01", "val": ("2015-01", "2017-12"), "eval": ("2018-01", "2025-12")}
           for g in EU_GEOS}
DESIGNS["KR"] = {"train_start": "2016-01", "val": ("2019-01", "2019-12"), "eval": ("2020-01", "2025-12")}
REGIMES = {"위기 전 (~2021)": ("2018-01", "2021-12"), "위기 (2022)": ("2022-01", "2022-12"),
           "위기 후 (2023~2025)": ("2023-01", "2025-12")}
ENS = ["회귀 + 위기 변수", "Ridge", "Gradient Boosting", "LightGBM", "MLP (16-8)", "Chronos-2 + 공변량"]


def mape(p):
    return float(((p.actual - p.pred).abs() / p.actual).mean() * 100)


def main():
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    if not ("--reuse" in sys.argv and (OUT / "predictions.csv").exists()):
        run(ALL_GEOS, -1, designs=DESIGNS, out=OUT)
    summ = pd.read_csv(OUT / "summary.csv")
    post = summ[summ["mode"] == "ex_post"].set_index(["geo", "model"])

    # 위기 변수 모형 (장기 설계로)
    jobs = []
    for g in ALL_GEOS:
        jobs.append(("회귀 + 위기 변수", g, BENCH, {}, REG + CRISIS, None))
        jobs.append(("Ridge + 위기 변수", g, "Ridge", json.loads(post.loc[(g, "Ridge"), "params"]),
                     list(SPEC["Ridge"].features) + CRISIS, None))
    extra = Parallel(n_jobs=-1)(delayed(final_task)(g, base, p, sd, f, DESIGNS[g]) for _, g, base, p, f, sd in jobs)
    extra = pd.concat([r.assign(model=j[0]) for r, j in zip(extra, jobs)], ignore_index=True)
    extra = (extra.groupby(["geo", "model", "mode", "month"], as_index=False)
             .agg(actual=("actual", "first"), pred=("pred", "mean")))

    cols = ["geo", "model", "mode", "month", "actual", "pred"]
    parts = [pd.read_csv(OUT / "predictions.csv")[cols], extra[cols]]
    for tag in ("long_eu", "long_kr"):
        f = OUTPUTS / f"r8_foundation_{tag}_predictions.csv"
        if f.exists():
            fm = pd.read_csv(f)
            parts.append(fm[fm.model.str.startswith("Chronos")][cols])
        else:
            print(f"경고: {f.name} 없음 — Chronos-2 장기 예측을 먼저 실행하세요")
    pred = pd.concat(parts, ignore_index=True)
    ens = []
    for (g, mode), q in pred.groupby(["geo", "mode"]):
        w = q.pivot(index="month", columns="model", values="pred")
        a = q.groupby("month").actual.first()
        use = [m for m in ENS if m in w]
        ens.append(pd.DataFrame({"geo": g, "model": "앙상블 (회귀·ML·Chronos)", "mode": mode, "month": w.index,
                                 "actual": a.loc[w.index].values, "pred": w[use].mean(axis=1).values}))
    pred = pd.concat([pred] + ens, ignore_index=True)
    pred.to_csv(OUT / "predictions_all.csv", index=False, encoding="utf-8-sig")

    # 지표, 국면별 MAPE
    rows, reg_rows = [], []
    for (g, m, mode), p in pred.groupby(["geo", "model", "mode"]):
        d = DESIGNS[g]
        rows.append({"geo": g, "model": m, "mode": mode, "n": len(p),
                     **metrics(p, load_country(g), train_start=d["train_start"], eval_start=d["eval"][0])})
        for rname, (a, b) in REGIMES.items():
            s = p[(p.month >= a) & (p.month <= b)]
            if len(s):
                reg_rows.append({"geo": g, "model": m, "mode": mode, "regime": rname, "MAPE": mape(s), "n": len(s)})
    tab = pd.DataFrame(rows)
    tab.to_csv(OUT / "summary_all.csv", index=False, encoding="utf-8-sig")
    regimes = pd.DataFrame(reg_rows)
    regimes.to_csv(OUT / "regimes.csv", index=False, encoding="utf-8-sig")

    # MCS: 국가별 + 6개국 평균 손실 (공통 구간)
    pred["ape"] = (pred.actual - pred.pred).abs() / pred.actual * 100
    mcs_rows = []
    for mode in MODES:
        for g in ALL_GEOS + ["ALL"]:
            q = pred[pred["mode"] == mode]
            if g == "ALL":
                q = q[q.month >= DESIGNS["KR"]["eval"][0]]
                loss = q.groupby(["month", "model"]).ape.mean().unstack()
                loss = loss.loc[:, q.groupby("model").geo.nunique().reindex(loss.columns).eq(len(ALL_GEOS))]
            else:
                loss = q[q.geo == g].pivot(index="month", columns="model", values="ape")
            loss = loss.dropna(axis=1)
            mcs = MCS(loss, size=0.10, reps=5000, block_size=3, method="R", bootstrap="stationary", seed=0)
            mcs.compute()
            for m in loss.columns:
                mcs_rows.append({"geo": g, "mode": mode, "model": m, "MAPE": loss[m].mean(), "T": len(loss),
                                 "mcs_p": float(mcs.pvalues["Pvalue"].get(m, np.nan)), "in_mcs": m in mcs.included})
    mcs_tab = pd.DataFrame(mcs_rows)
    mcs_tab.to_csv(OUT / "mcs.csv", index=False, encoding="utf-8-sig")

    names = list(GEO_NAMES[g] for g in ALL_GEOS)
    L = ["# 장기 롤링 평가 (유럽 2018~2025 96개월, 한국 2020~2025 72개월)", "",
         "튜닝: 유럽 2015~2017, 한국 2019 검증 구간. MAPE(%), ✓ = 그 나라 MCS(90%)에 포함. "
         "'6개국 평균'은 공통 구간 2020~2025(72개월)의 국가 평균 손실로 계산한 MCS.", ""]
    for mode, title in (("ex_post", "사후예측"), ("ex_ante", "사전예측")):
        s = tab[tab["mode"] == mode].pivot(index="model", columns="geo", values="MAPE")[ALL_GEOS]
        inm = mcs_tab[mcs_tab["mode"] == mode].pivot(index="model", columns="geo", values="in_mcs")
        allm = mcs_tab[(mcs_tab["mode"] == mode) & (mcs_tab.geo == "ALL")].set_index("model")
        s["평균"] = s.mean(axis=1)
        s = s.sort_values("평균")
        L += [f"## {title}", "", "| 모델 | " + " | ".join(names) + " | 평균 | 6개국 평균 MCS |",
              "| --- |" + " --- |" * (len(names) + 2)]
        for m, r in s.iterrows():
            cells = [f"{r[g]:.1f}{' ✓' if inm.get(g, pd.Series()).get(m, False) else ''}" for g in ALL_GEOS]
            am = "✓" if m in allm.index and allm.loc[m, "in_mcs"] else ""
            L.append(f"| {m} | " + " | ".join(cells) + f" | {r['평균']:.1f} | {am} |")
        L.append("")
        rg = regimes[regimes["mode"] == mode].groupby(["model", "regime"]).MAPE.mean().unstack()[list(REGIMES)]
        rg = rg.loc[s.index]
        L += [f"### {title}: 국면별 평균 MAPE (6개국 평균, 한국은 2020~)", "", "| 모델 | " + " | ".join(REGIMES) + " |",
              "| --- |" + " --- |" * len(REGIMES)]
        L += [f"| {m} | " + " | ".join(f"{r[k]:.1f}" for k in REGIMES) + " |" for m, r in rg.iterrows()]
        L.append("")
    (OUT / "report.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))
    print(f"저장: {OUT} ({(time.time() - t0) / 60:.1f}분)")


if __name__ == "__main__":
    main()
