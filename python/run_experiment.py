"""본 실험: 국가별 모델 비교 (계획서 분석 절차 7~8, 12단계 / 연구 과제 R4·R5).

절차
  1) 튜닝: 2020-01~2022-12 검증 구간에서 롤링 1개월 앞 사후예측 MAPE로 하이퍼파라미터를 고른다.
     (평가 구간 2023~2025 자료는 쓰지 않는다 → 튜닝 누수 없음)
  2) 고정: 고른 설정으로 2023-01~2025-12 롤링 평가 (36회), 사후·사전예측을 같은 적합 모델로 함께 낸다.
  3) 랜덤성이 있는 모델(RF, MLP, subsample<1인 GBM)은 시드 5개의 예측을 평균하고, 시드 간 MAPE 표준편차를 함께 보고한다.
  4) Diebold-Mariano 검정(HLN 보정): 각 모델 vs 기준 회귀(√Y~HDD+가격), 손실 APE·SE.

추정 시작은 모든 국가 2015-01 (계획서 사전 실험과 같음).
한국은 수요가 2016-01부터라 실제 학습은 2016-01(12개월 전 수요를 쓰는 모델은 2017-01)부터다.

출력: outputs/experiment/
  report.md         국가×모델 표, 국가별 상세, DM 검정, 선택된 하이퍼파라미터
  summary.csv       국가·모델·모드별 MAPE·RMSE·MASE·시드 표준편차·검증 MAPE·설정
  predictions.csv   월별 예측값 (시드 평균 후)
  dm_tests.csv      DM 검정 결과
  tuning.csv        그리드 전체의 검증 MAPE

실행: python python/run_experiment.py                # 6개국 (유럽 5 + 한국)
      python python/run_experiment.py --geos DE      # 독일만
"""
import argparse
import itertools
import json
import os
import time
from dataclasses import dataclass, field
from typing import Callable

os.environ.setdefault("LOKY_MAX_CPU_COUNT", str(os.cpu_count() or 4))

import lightgbm
import numpy as np
import pandas as pd
import sklearn
import statsmodels
from joblib import Parallel, delayed

import models as M
from config import ALL_GEOS, EVAL_END, EVAL_START, GEO_NAMES, INTERIM, OUTPUTS
from dm_test import dm_test
from rolling_eval import BASE_FEATURES, TRAIN_START, load_country, metrics, rolling_forecast

VAL_START, VAL_END = "2020-01", "2022-12"
SEEDS = [0, 1, 2, 3, 4]
MODES = ("ex_post", "ex_ante")
MODE_KO = {"ex_post": "사후예측", "ex_ante": "사전예측"}
REG = ["hdd", "price_retail"]
BENCH = "회귀 √Y~HDD+가격"
OUT = OUTPUTS / "experiment"


def grid(**axes):
    return [dict(zip(axes, v)) for v in itertools.product(*axes.values())]


@dataclass
class Spec:
    name: str
    features: list
    fixed: Callable = None            # 튜닝 없는 모델의 fit_predict
    build: Callable = None            # build(params, seeds) -> fit_predict
    grid: list = field(default_factory=list)
    stochastic: Callable = lambda p: False   # 설정 p에서 시드 평균이 필요한가

    def make(self, params, seeds=None):
        return self.fixed if self.fixed is not None else self.build(params, seeds)


SPECS = [
    Spec("계절 naive", ["lag12"], fixed=M.seasonal_naive),
    Spec("단순회귀 Y~HDD", ["hdd"], fixed=M.ols()),
    Spec(BENCH, REG, fixed=M.ols(sqrt=True)),
    Spec("SARIMAX+HDD·가격", REG, fixed=M.sarimax),
    Spec("Holt-Winters", [], fixed=M.holt_winters),
    Spec("Ridge", BASE_FEATURES, build=M.build_ridge,
         grid=grid(alpha=[0.1, 1, 10, 100], target=[None, "sqrt"])),
    Spec("Lasso", BASE_FEATURES, build=M.build_lasso,
         grid=grid(alpha=[0.01, 0.1, 0.5, 1, 2], target=[None, "sqrt"])),
    Spec("Random Forest", BASE_FEATURES, build=M.build_rf,
         grid=grid(max_features=[1.0, 0.5, 0.33], min_samples_leaf=[1, 3, 5]),
         stochastic=lambda p: True),
    Spec("Gradient Boosting", BASE_FEATURES, build=M.build_gbm,
         grid=grid(learning_rate=[0.03, 0.1], n_estimators=[100, 300], max_depth=[2, 3],
                   subsample=[1.0, 0.8]),
         stochastic=lambda p: p["subsample"] < 1.0),
    Spec("LightGBM", BASE_FEATURES, build=M.build_lgbm,
         grid=grid(num_leaves=[7, 15], min_child_samples=[5, 10, 20])),
    Spec("SVR", BASE_FEATURES, build=M.build_svr, grid=grid(C=[1, 10, 100], epsilon=[0.01, 0.1])),
    Spec("MLP (16-8)", BASE_FEATURES, build=M.build_mlp, grid=grid(alpha=[1e-4, 1e-2, 1.0]),
         stochastic=lambda p: True),
    Spec("하이브리드 (회귀+GBM 잔차)", BASE_FEATURES, build=M.build_hybrid(REG),
         grid=grid(learning_rate=[0.05], n_estimators=[50, 100], max_depth=[2, 3])),
]
SPEC = {s.name: s for s in SPECS}


def tune_task(geo, name, params):
    s = SPEC[name]
    df = load_country(geo)
    res = rolling_forecast(df, s.make(params), s.features, train_start=TRAIN_START,
                           eval_start=VAL_START, eval_end=VAL_END)
    return {"geo": geo, "model": name, "params": json.dumps(params, ensure_ascii=False),
            "val_MAPE": metrics(res, df, eval_start=VAL_START)["MAPE"]}


def final_task(geo, name, params, seed):
    s = SPEC[name]
    df = load_country(geo)
    fp = s.make(params, seeds=[seed] if seed is not None else None)
    res = rolling_forecast(df, fp, s.features, train_start=TRAIN_START, modes=MODES)
    return res.assign(geo=geo, model=name, seed=-1 if seed is None else seed)


def run(geos, n_jobs):
    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    # 1) 튜닝
    tasks = [(g, s.name, p) for g in geos for s in SPECS if s.grid for p in s.grid]
    print(f"[1/3] 튜닝: {len(tasks)}개 설정 × 36회 (검증 {VAL_START}~{VAL_END})", flush=True)
    tun = pd.DataFrame(Parallel(n_jobs=n_jobs)(delayed(tune_task)(*t) for t in tasks))
    tun.to_csv(OUT / "tuning.csv", index=False, encoding="utf-8-sig")
    best = (tun.sort_values("val_MAPE").groupby(["geo", "model"]).head(1)
            .set_index(["geo", "model"]))
    print(f"      완료 {time.time() - t0:.0f}s", flush=True)

    # 2) 최종 평가
    jobs = []
    for g in geos:
        for s in SPECS:
            p = json.loads(best.loc[(g, s.name), "params"]) if s.grid else {}
            seeds = SEEDS if s.stochastic(p) else [None]
            jobs += [(g, s.name, p, sd) for sd in seeds]
    print(f"[2/3] 평가: {len(jobs)}개 작업 (국가×모델×시드) × 36회, 사후·사전예측", flush=True)
    raw = pd.concat(Parallel(n_jobs=n_jobs)(delayed(final_task)(*j) for j in jobs), ignore_index=True)
    print(f"      완료 {time.time() - t0:.0f}s", flush=True)

    # 시드 간 MAPE 표준편차, 시드 평균 예측
    ape = raw.assign(ape=(raw.actual - raw.pred).abs() / raw.actual * 100)
    seed_sd = (ape.groupby(["geo", "model", "mode", "seed"]).ape.mean()
               .groupby(["geo", "model", "mode"]).std().fillna(0.0))
    pred = (raw.groupby(["geo", "model", "mode", "month"], as_index=False)
            .agg(actual=("actual", "first"), pred=("pred", "mean"), n_seeds=("seed", "nunique")))
    pred.to_csv(OUT / "predictions.csv", index=False, encoding="utf-8-sig")

    # 3) 지표와 DM 검정
    rows, dms = [], []
    for g in geos:
        df = load_country(g)
        for (name, mode), r in pred[pred.geo == g].groupby(["model", "mode"]):
            m = metrics(r, df)
            rows.append({"geo": g, "model": name, "mode": mode, **m,
                         "MAPE_seed_sd": seed_sd.get((g, name, mode), 0.0),
                         "n_seeds": int(r.n_seeds.iloc[0]),
                         "val_MAPE": best.loc[(g, name), "val_MAPE"] if SPEC[name].grid else np.nan,
                         "params": best.loc[(g, name), "params"] if SPEC[name].grid else ""})
        for mode in MODES:
            p = pred[(pred.geo == g) & (pred["mode"] == mode)].pivot(index="month", columns="model",
                                                                      values="pred")
            act = pred[(pred.geo == g) & (pred["mode"] == mode)].groupby("month").actual.first()
            for name in p.columns:
                if name == BENCH:
                    continue
                for kind in ("ape", "se"):
                    stat, pv = dm_test(act, p[name], p[BENCH], kind=kind)
                    dms.append({"geo": g, "mode": mode, "model": name, "vs": BENCH, "loss": kind,
                                "DM": stat, "p": pv})
    summ = pd.DataFrame(rows)
    summ.to_csv(OUT / "summary.csv", index=False, encoding="utf-8-sig")
    dmt = pd.DataFrame(dms)
    dmt.to_csv(OUT / "dm_tests.csv", index=False, encoding="utf-8-sig")
    write_report(summ, dmt, geos, time.time() - t0)
    print(f"[3/3] 저장: {OUT} ({time.time() - t0:.0f}s)")


def stars(p):
    return "**" if p < 0.01 else ("*" if p < 0.05 else "")


def write_report(summ, dmt, geos, secs):
    fetched = pd.read_csv(INTERIM / "europe_long.csv", usecols=["fetched"]).fetched.iloc[0]
    order = [s.name for s in SPECS]
    L = ["# 본 실험 결과: 국가별 모델 비교", "",
         f"- 평가: {EVAL_START}~{EVAL_END} 롤링 1개월 앞 예측 36회, 추정 시작 {TRAIN_START}, 매달 재추정",
         f"- 튜닝: {VAL_START}~{VAL_END} 검증 구간 사후예측 MAPE 최소 설정을 고정 (평가 구간 미사용)",
         "- 사후예측: 예측 달 기상·가격 실제값 / 사전예측: HDD·CDD 평년값(직전 10년 같은 달 평균), "
         "같은 달 가격·산업 변수는 직전 달 값",
         f"- 랜덤 모델은 시드 {len(SEEDS)}개 예측 평균. ± 는 시드 간 MAPE 표준편차",
         f"- DM 검정: 기준 회귀({BENCH}) 대비, HLN 보정, 손실 APE. * p<0.05, ** p<0.01 "
         "(기준보다 유의하게 정확하면 ▲, 부정확하면 ▼)",
         f"- 데이터 호출일 {fetched}, scikit-learn {sklearn.__version__}, lightgbm {lightgbm.__version__}, "
         f"statsmodels {statsmodels.__version__}, 실행 {secs / 60:.1f}분", ""]

    def cell(g, name, mode):
        r = summ[(summ.geo == g) & (summ.model == name) & (summ["mode"] == mode)]
        if r.empty:
            return ""
        r = r.iloc[0]
        txt = f"{r.MAPE:.1f}"
        if r.n_seeds > 1:
            txt += f" ±{r.MAPE_seed_sd:.1f}"
        d = dmt[(dmt.geo == g) & (dmt["mode"] == mode) & (dmt.model == name) & (dmt.loss == "ape")]
        if not d.empty and d.p.iloc[0] < 0.05:
            txt += (" ▲" if d.DM.iloc[0] < 0 else " ▼") + stars(d.p.iloc[0])
        best = summ[(summ.geo == g) & (summ["mode"] == mode)].MAPE.min()
        return f"**{txt}**" if np.isclose(r.MAPE, best) else txt

    for mode in MODES:
        L += [f"## 국가 × 모델 MAPE (%) — {MODE_KO[mode]}", "",
              "| 모델 | " + " | ".join(GEO_NAMES[g] for g in geos) + " |",
              "| --- |" + " --- |" * len(geos)]
        for name in order:
            L.append(f"| {name} | " + " | ".join(cell(g, name, mode) for g in geos) + " |")
        L.append("")

    for g in geos:
        s = summ[summ.geo == g]
        L += [f"## {GEO_NAMES[g]} 상세", "",
              f"| 모델 | MAPE 사후 | MAPE 사전 | RMSE 사후 ({load_country(g).y_unit.iloc[0]}) | MASE 사후 | "
              "DM p (APE, 사후) | "
              "DM p (SE, 사후) | 검증 MAPE | 선택 설정 |",
              "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
        post = s[s["mode"] == "ex_post"].set_index("model")
        ante = s[s["mode"] == "ex_ante"].set_index("model")
        for name in post.sort_values("MAPE").index:
            r = post.loc[name]

            def dp(kind):
                d = dmt[(dmt.geo == g) & (dmt["mode"] == "ex_post") & (dmt.model == name) & (dmt.loss == kind)]
                return "기준" if d.empty else f"{d.p.iloc[0]:.3f}{' (더 정확)' if d.DM.iloc[0] < 0 else ''}"
            val = "" if pd.isna(r.val_MAPE) else f"{r.val_MAPE:.1f}"
            L.append(f"| {name} | {r.MAPE:.2f} | {ante.loc[name, 'MAPE']:.2f} | {r.RMSE:.1f} | {r.MASE:.2f} | "
                     f"{dp('ape')} | {dp('se')} | {val} | {r.params} |")
        L.append("")
    (OUT / "report.md").write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--geos", nargs="+", default=ALL_GEOS)
    ap.add_argument("--jobs", type=int, default=-1)
    a = ap.parse_args()
    run(a.geos, a.jobs)
