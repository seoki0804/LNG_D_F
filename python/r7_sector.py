"""연구 과제 R7 (부문별 예측): 부문별로 예측해 더한 값이 총량을 바로 예측한 값보다 정확한가?

  독일: SLP(가정·소규모) + RLM(산업·발전) = THE 총량 (PJ), 자료 2021-10~ → 평가 2024-01~2025-12 (24회)
  한국: 도시가스용 + 발전용 = KOGAS 총 공급량 (천 톤), 자료 2016-01~ → 평가 2023-01~2025-12 (36회)

방식
  - 같은 모델·같은 설정으로 (a) 부문마다 따로 예측해 합산, (b) 총량을 바로 예측. 둘 다 매달 재추정.
  - 하이퍼파라미터는 본 실험(run_experiment.py)에서 그 나라 총수요로 고른 설정을 그대로 쓴다
    (독일은 부문 자료가 짧아 검증 구간을 따로 둘 수 없다). 먼저 run_experiment.py를 실행해야 한다.
  - 독일 총량은 Eurostat가 아니라 THE 합계(SLP+RLM)로 맞춘다 (같은 대상끼리 비교).
  - DM 검정: 합산 vs 직접, 손실 APE (사후예측).
  - 부문별 민감도: 학습 구간 전체로 log(Y) ~ HDD + log(소비자요금) → HDD 10당 %, 요금 탄력성.

출력: outputs/r7_sector.md, outputs/r7_sector.csv, outputs/r7_sector_predictions.csv
실행: python python/r7_sector.py
"""
import json
import os
import time

os.environ.setdefault("LOKY_MAX_CPU_COUNT", str(os.cpu_count() or 4))

import numpy as np
import pandas as pd
import statsmodels.api as sm
from joblib import Parallel, delayed

from config import OUTPUTS
from dm_test import dm_test
from rolling_eval import load_country, metrics, rolling_forecast
from run_experiment import BENCH, MODES, OUT as EXP_OUT, SEEDS, SPEC

SETUP = {
    "DE": dict(total="the_total_pj", sectors={"slp_pj": "SLP (가정·소규모)", "rlm_pj": "RLM (산업·발전)"},
               eval_start="2024-01", eval_end="2025-12", unit="PJ"),
    "KR": dict(total="gas_kt", sectors={"gas_city_kt": "도시가스용", "gas_power_kt": "발전용"},
               eval_start="2023-01", eval_end="2025-12", unit="천톤"),
}
MODELS = [BENCH, "SARIMAX+HDD·가격", "Ridge", "Gradient Boosting", "MLP (16-8)", "하이브리드 (회귀+GBM 잔차)"]


def best_params(geo):
    s = pd.read_csv(EXP_OUT / "summary.csv")
    s = s[(s.geo == geo) & (s["mode"] == "ex_post")].set_index("model")
    return {m: (json.loads(s.loc[m, "params"]) if isinstance(s.loc[m, "params"], str) and s.loc[m, "params"] else {})
            for m in MODELS}


def task(geo, model, params, target, seed):
    st = SETUP[geo]
    spec = SPEC[model]
    df = load_country(geo, target=target)
    fp = spec.make(params, seeds=[seed] if seed is not None else None)
    try:
        res = rolling_forecast(df, fp, spec.features, target=target, eval_start=st["eval_start"],
                               eval_end=st["eval_end"], modes=MODES)
    except Exception as e:   # 짧은 표본에서 SARIMAX 등이 실패하면 기록만 남긴다
        return pd.DataFrame({"error": [f"{type(e).__name__}: {e}"[:200]]}).assign(
            geo=geo, model=model, target=target, seed=-1)
    return res.assign(geo=geo, model=model, target=target, seed=-1 if seed is None else seed)


def sensitivity(geo):
    st = SETUP[geo]
    df = load_country(geo)
    rows = []
    for col, name in [(st["total"], "총량")] + list(st["sectors"].items()):
        d = df[(df.month < st["eval_start"]) & df[col].notna() & df.price_retail.notna()]
        X = sm.add_constant(pd.DataFrame({"hdd": d.hdd, "log_price": np.log(d.price_retail)}))
        m = sm.OLS(np.log(d[col]), X).fit(cov_type="HAC", cov_kwds={"maxlags": 4})
        rows.append({"geo": geo, "부문": name, "학습 기간": f"{d.month.min()}~{d.month.max()}",
                     "HDD 10당 %": 100 * (np.exp(10 * m.params.hdd) - 1),
                     "요금 탄력성": m.params.log_price, "요금 p(HAC)": m.pvalues.log_price,
                     "R2": m.rsquared, "평균 수요": d[col].mean()})
    return rows


def main():
    t0 = time.time()
    jobs = []
    for geo, st in SETUP.items():
        params = best_params(geo)
        for m in MODELS:
            seeds = SEEDS if SPEC[m].stochastic(params[m]) else [None]
            for target in [st["total"], *st["sectors"]]:
                jobs += [(geo, m, params[m], target, sd) for sd in seeds]
    print(f"작업 {len(jobs)}개", flush=True)
    raw = pd.concat(Parallel(n_jobs=-1)(delayed(task)(*j) for j in jobs), ignore_index=True)
    errors = raw[raw.get("error").notna()] if "error" in raw else pd.DataFrame()
    raw = raw[raw.get("error").isna()] if "error" in raw else raw
    pred = (raw.groupby(["geo", "model", "target", "mode", "month"], as_index=False)
            .agg(actual=("actual", "first"), pred=("pred", "mean")))
    pred.to_csv(OUTPUTS / "r7_sector_predictions.csv", index=False, encoding="utf-8-sig")

    rows, L = [], ["# R7 부문별 예측: 부문 합산 vs 총량 직접", ""]
    for geo, st in SETUP.items():
        L += [f"## {'독일' if geo == 'DE' else '한국'} — 평가 {st['eval_start']}~{st['eval_end']}, "
              f"총량 {st['total']} ({st['unit']})", "",
              "| 모델 | 직접 MAPE 사후 | 합산 MAPE 사후 | DM p (합산 vs 직접) | 직접 MAPE 사전 | 합산 MAPE 사전 | "
              + " | ".join(f"{v} MAPE" for v in st["sectors"].values()) + " |",
              "| --- " * (6 + len(st["sectors"])) + "|"]
        df = load_country(geo, target=st["total"])
        for m in MODELS:
            p = pred[(pred.geo == geo) & (pred.model == m)]
            if p[p.target == st["total"]].empty or any(p[p.target == s].empty for s in st["sectors"]):
                L.append(f"| {m} | 실패 | | | | | " + " | ".join("" for _ in st["sectors"]) + " |")
                continue
            r = {"geo": geo, "model": m}
            for mode in MODES:
                direct = p[(p.target == st["total"]) & (p["mode"] == mode)].set_index("month")
                summed = sum(p[(p.target == s) & (p["mode"] == mode)].set_index("month").pred
                             for s in st["sectors"])
                comb = direct[["actual"]].assign(pred=summed).reset_index()
                r[f"direct_{mode}"] = metrics(direct.reset_index(), df, target=st["total"],
                                              eval_start=st["eval_start"])["MAPE"]
                r[f"sum_{mode}"] = metrics(comb, df, target=st["total"], eval_start=st["eval_start"])["MAPE"]
                if mode == "ex_post":
                    r["DM"], r["p"] = dm_test(direct.actual.values, comb.pred.values, direct.pred.values, kind="ape")
            for s in st["sectors"]:
                sp = p[(p.target == s) & (p["mode"] == "ex_post")]
                r[f"mape_{s}"] = float(((sp.actual - sp.pred).abs() / sp.actual).mean() * 100)
            rows.append(r)
            mark = (" (합산 우세)" if r["DM"] < 0 else " (직접 우세)") if r["p"] < 0.05 else ""
            L.append(f"| {m} | {r['direct_ex_post']:.1f} | {r['sum_ex_post']:.1f} | {r['p']:.3f}{mark} | "
                     f"{r['direct_ex_ante']:.1f} | {r['sum_ex_ante']:.1f} | "
                     + " | ".join(f"{r[f'mape_{s}']:.1f}" for s in st["sectors"]) + " |")
        L.append("")

    sens = pd.DataFrame([x for geo in SETUP for x in sensitivity(geo)])
    L += ["## 부문별 민감도 (평가 전 학습 구간, log(Y) ~ HDD + log(소비자요금), HAC 표준오차)", "",
          "| 국가 | 부문 | 학습 기간 | HDD 10당 수요 % | 요금 탄력성 | 요금 p | R² |", "| --- " * 7 + "|"]
    for r in sens.itertuples():
        L.append(f"| {'독일' if r.geo == 'DE' else '한국'} | {r.부문} | {r._3} | {r._4:.2f} | {r._5:.2f} | "
                 f"{r._6:.3f} | {r.R2:.2f} |")
    if len(errors):
        L += ["", "실패한 작업: " + "; ".join(f"{e.geo} {e.model} {e.target}: {e.error}" for e in errors.itertuples())]
    tab = pd.DataFrame(rows)
    tab.to_csv(OUTPUTS / "r7_sector.csv", index=False, encoding="utf-8-sig")
    sens.to_csv(OUTPUTS / "r7_sector_sensitivity.csv", index=False, encoding="utf-8-sig")
    (OUTPUTS / "r7_sector.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))
    print(f"\n저장: outputs/r7_sector.md ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
