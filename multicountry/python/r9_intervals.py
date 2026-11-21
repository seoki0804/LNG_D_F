"""연구 과제 R9 (예측구간): 회귀 예측구간·분위수 GBM·conformal 구간의 실제 포함률은 명목 수준에 맞는가.

평가: 6개국, 2023-01~2025-12 롤링 1개월 앞 (사후예측), 명목 80%·95%.
방법
  회귀 PI       : √Y ~ HDD + 소비자가격 + 위기 + HDD×위기 (R2 최선 회귀)의 OLS 예측구간을 제곱해 되돌림
  분위수 GBM    : GBM(loss=quantile)로 하한·상한 분위수를 직접 학습 (본 실험 GBM 설정)
  Conformal     : 점예측 모델의 과거 표본 외 상대오차 |e|/ŷ (2020-01부터 t-1까지 롤링 예측)의
                  (1-α)(1+1/n) 분위수 q로 ŷ(1 ± q). 점예측 = 회귀(위기 변수), LightGBM
  Chronos-2     : 0.1·0.9 분위수 (80%만, R8 결과)
지표: 포함률(%), 평균 폭(실제값 대비 %), interval score(Gneiting & Raftery 2007; 낮을수록 좋음, 실제값 대비 %).

출력: outputs/r9_intervals.md, outputs/r9_intervals.csv
실행: python python/r9_intervals.py   (run_experiment.py, r8_foundation.py 결과 필요)
"""
import json
import os
import warnings

os.environ.setdefault("LOKY_MAX_CPU_COUNT", str(os.cpu_count() or 4))
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import statsmodels.api as sm
from joblib import Parallel, delayed
from sklearn.ensemble import GradientBoostingRegressor

from config import ALL_GEOS, GEO_NAMES, OUTPUTS
from rolling_eval import BASE_FEATURES, eval_months, load_country, rolling_forecast
from run_experiment import OUT as EXP_OUT, SPEC

LEVELS = (0.80, 0.95)
REGC = ["hdd", "price_retail", "crisis", "hdd_crisis"]
CONF_START = "2020-01"


def reg_pi(geo):
    df = load_country(geo)
    rows = []
    for t in eval_months():
        tr = df[(df.month >= "2015-01") & (df.month < t)].dropna(subset=REGC + ["y"])
        te = df[df.month == t]
        m = sm.OLS(np.sqrt(tr.y), sm.add_constant(tr[REGC])).fit()
        X = sm.add_constant(te[REGC], has_constant="add")
        for lv in LEVELS:
            f = m.get_prediction(X).summary_frame(alpha=1 - lv)
            rows.append({"geo": geo, "month": t, "method": "회귀 PI (위기 변수)", "level": lv,
                         "actual": te.y.iloc[0], "lo": max(f.obs_ci_lower.iloc[0], 0) ** 2,
                         "hi": f.obs_ci_upper.iloc[0] ** 2})
    return rows


def qgbm(geo, params):
    df = load_country(geo)
    rows = []
    p = {k: v for k, v in params.items()}
    for t in eval_months():
        tr = df[(df.month >= "2015-01") & (df.month < t)].dropna(subset=BASE_FEATURES + ["y"])
        te = df[df.month == t]
        for lv in LEVELS:
            a = (1 - lv) / 2
            lo = GradientBoostingRegressor(loss="quantile", alpha=a, random_state=0, **p).fit(tr[BASE_FEATURES], tr.y)
            hi = GradientBoostingRegressor(loss="quantile", alpha=1 - a, random_state=0, **p).fit(tr[BASE_FEATURES],
                                                                                                  tr.y)
            rows.append({"geo": geo, "month": t, "method": "분위수 GBM", "level": lv, "actual": te.y.iloc[0],
                         "lo": lo.predict(te[BASE_FEATURES])[0], "hi": hi.predict(te[BASE_FEATURES])[0]})
    return rows


def conformal(geo, name, fp, feats):
    df = load_country(geo)
    res = rolling_forecast(df, fp, feats, eval_start=CONF_START, eval_end=eval_months()[-1])
    res["rel"] = (res.actual - res.pred).abs() / res.pred
    rows = []
    for t in eval_months():
        past = res[res.month < t].rel.to_numpy()
        cur = res[res.month == t].iloc[0]
        n = len(past)
        for lv in LEVELS:
            q = np.quantile(past, min(1.0, lv * (1 + 1 / n)), method="higher")
            rows.append({"geo": geo, "month": t, "method": f"Conformal ({name})", "level": lv,
                         "actual": cur.actual, "lo": cur.pred * (1 - q), "hi": cur.pred * (1 + q)})
    return rows


def main():
    summ = pd.read_csv(EXP_OUT / "summary.csv")
    post = summ[summ["mode"] == "ex_post"].set_index(["geo", "model"])
    jobs = []
    for g in ALL_GEOS:
        jobs.append(delayed(reg_pi)(g))
        gbm_p = json.loads(post.loc[(g, "Gradient Boosting"), "params"])
        gbm_p.pop("subsample", None)   # 분위수 GBM은 결정적으로 (subsample 1.0)
        jobs.append(delayed(qgbm)(g, gbm_p))
        jobs.append(delayed(conformal)(g, "회귀 위기 변수", SPEC["회귀 √Y~HDD+가격"].make({}), REGC))
        lp = json.loads(post.loc[(g, "LightGBM"), "params"])
        jobs.append(delayed(conformal)(g, "LightGBM", SPEC["LightGBM"].make(lp), BASE_FEATURES))
    rows = [r for part in Parallel(n_jobs=-1)(jobs) for r in part]
    iv = pd.DataFrame(rows)
    fm = pd.read_csv(OUTPUTS / "r8_foundation_predictions.csv")
    fm = fm[(fm.model == "Chronos-2 + 공변량") & (fm["mode"] == "ex_post")]
    iv = pd.concat([iv, fm.assign(method="Chronos-2 + 공변량 분위수", level=0.80)[
        ["geo", "month", "method", "level", "actual", "lo", "hi"]]], ignore_index=True)

    a = 1 - iv.level
    iv["cover"] = ((iv.actual >= iv.lo) & (iv.actual <= iv.hi)).astype(float)
    iv["width_pct"] = (iv.hi - iv.lo) / iv.actual * 100
    iv["score_pct"] = ((iv.hi - iv.lo) + 2 / a * (iv.lo - iv.actual).clip(lower=0)
                       + 2 / a * (iv.actual - iv.hi).clip(lower=0)) / iv.actual * 100
    tab = (iv.groupby(["method", "level", "geo"]).agg(cover=("cover", "mean"), width=("width_pct", "mean"),
                                                      score=("score_pct", "mean")).reset_index())
    tab["cover"] *= 100
    tab.to_csv(OUTPUTS / "r9_intervals.csv", index=False, encoding="utf-8-sig")

    methods = list(dict.fromkeys(iv.method))
    L = ["# R9 예측구간 포함률", "",
         "2023~2025 롤링 1개월 앞(사후예측, 36회). 칸 = 포함률 % (평균 폭 %). 명목 80%면 80, 95%면 95에 가까울수록 좋다. "
         "36회라 포함률의 표준오차는 약 ±7%p(80%)·±4%p(95%)다.", ""]
    for lv in LEVELS:
        L += [f"## 명목 {lv:.0%}", "", "| 방법 | " + " | ".join(GEO_NAMES[g] for g in ALL_GEOS)
              + " | 평균 포함률 | 평균 폭 | interval score |", "| --- |" + " --- |" * (len(ALL_GEOS) + 3)]
        for m in methods:
            sub = tab[(tab.method == m) & np.isclose(tab.level, lv)].set_index("geo")
            if sub.empty:
                continue
            cells = [f"{sub.loc[g, 'cover']:.0f} ({sub.loc[g, 'width']:.0f})" for g in ALL_GEOS]
            L.append(f"| {m} | " + " | ".join(cells) + f" | {sub.cover.mean():.0f} | {sub.width.mean():.1f}% | "
                     f"{sub.score.mean():.1f}% |")
        L.append("")
    (OUTPUTS / "r9_intervals.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
