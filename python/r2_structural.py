"""연구 과제 R2 (구조변화 대응): 추정창 길이·최근 가중치·위기 변수 중 무엇이 2022년 이후를 가장 잘 따라가는가.

전략 (모두 매달 재추정, 2023-01~2025-12 롤링 1개월 앞 예측)
  확장 2015~   : 2015-01부터 쌓는 확장창 (본 실험 기준)
  확장 2009~   : 2009-01부터 (한국은 자료가 2016-01부터라 기준과 같다)
  이동 60개월  : 직전 60개월만
  이동 36개월  : 직전 36개월만
  지수가중 24  : 확장창 2015~, 관측 가중치 0.5^(경과 개월/24) (반감기 24개월)
  위기 변수    : 확장창 2015~ + 위기 더미(2022-03~) + HDD×위기

모델: 기준 회귀(√Y~HDD+가격), Ridge, GBM. 하이퍼파라미터는 본 실험에서 고른 국가별 설정을 그대로 쓴다.
DM 검정: 같은 모델의 '확장 2015~' 대비 (APE, 사후예측).

출력: outputs/r2_structural.md, outputs/r2_structural.csv
실행: python python/r2_structural.py   (run_experiment.py 결과 필요)
"""
import json
import os
import time

os.environ.setdefault("LOKY_MAX_CPU_COUNT", str(os.cpu_count() or 4))

import numpy as np
import pandas as pd
import statsmodels.api as sm
from joblib import Parallel, delayed
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

from config import ALL_GEOS, GEO_NAMES, OUTPUTS
from dm_test import dm_test
from rolling_eval import BASE_FEATURES, load_country, metrics, rolling_forecast
from run_experiment import BENCH, MODES, OUT as EXP_OUT, REG, SEEDS, SPEC

MODELS = [BENCH, "Ridge", "Gradient Boosting"]
CRISIS = ["crisis", "hdd_crisis"]
STRATEGIES = {   # 이름: (train_start, window, 반감기, 위기 변수)
    "확장 2015~": ("2015-01", None, None, False),
    "확장 2009~": ("2009-01", None, None, False),
    "이동 60개월": ("2009-01", 60, None, False),
    "이동 36개월": ("2009-01", 36, None, False),
    "지수가중 24": ("2015-01", None, 24, False),
    "위기 변수": ("2015-01", None, None, True),
}
BASE = "확장 2015~"


def month_index(months):
    return months.str[:4].astype(int) * 12 + months.str[5:7].astype(int)


def weighted(model, params, halflife, seed):
    """최근 관측에 더 큰 가중치를 주는 적합. 다른 설정은 본 실험과 같다."""
    def fit_predict(train, test, features, target):
        age = month_index(train.month).max() - month_index(train.month)
        w = (0.5 ** (age / halflife)).to_numpy()
        if model == BENCH:
            m = sm.WLS(np.sqrt(train[target]), sm.add_constant(train[features]), weights=w).fit()
            return m.predict(sm.add_constant(test[features], has_constant="add")).to_numpy() ** 2
        if model == "Ridge":
            sc = StandardScaler().fit(train[features])
            sqrt = params.get("target") == "sqrt"
            y = np.sqrt(train[target]) if sqrt else train[target]
            r = Ridge(alpha=params["alpha"]).fit(sc.transform(train[features]), y, sample_weight=w)
            p = r.predict(sc.transform(test[features]))
            return p ** 2 if sqrt else p
        g = GradientBoostingRegressor(random_state=seed or 0, **params)
        return g.fit(train[features], train[target], sample_weight=w).predict(test[features])
    return fit_predict


def task(geo, model, params, strategy, seed):
    start, window, halflife, crisis = STRATEGIES[strategy]
    spec = SPEC[model]
    feats = list(spec.features) + (CRISIS if crisis else [])
    fp = (weighted(model, params, halflife, seed) if halflife
          else spec.make(params, seeds=[seed] if seed is not None else None))
    df = load_country(geo)
    res = rolling_forecast(df, fp, feats, train_start=start, window=window, modes=MODES)
    return res.assign(geo=geo, model=model, strategy=strategy, seed=-1 if seed is None else seed)


def main():
    t0 = time.time()
    s = pd.read_csv(EXP_OUT / "summary.csv")
    s = s[s["mode"] == "ex_post"].set_index(["geo", "model"])
    jobs = []
    for g in ALL_GEOS:
        for m in MODELS:
            p = json.loads(s.loc[(g, m), "params"]) if SPEC[m].grid else {}
            seeds = SEEDS if SPEC[m].stochastic(p) else [None]
            jobs += [(g, m, p, st, sd) for st in STRATEGIES for sd in seeds]
    print(f"작업 {len(jobs)}개", flush=True)
    raw = pd.concat(Parallel(n_jobs=-1)(delayed(task)(*j) for j in jobs), ignore_index=True)
    pred = (raw.groupby(["geo", "model", "strategy", "mode", "month"], as_index=False)
            .agg(actual=("actual", "first"), pred=("pred", "mean"), n_train=("n_train", "first")))

    rows = []
    for (g, m, st, mode), r in pred.groupby(["geo", "model", "strategy", "mode"]):
        df = load_country(g)
        base = pred[(pred.geo == g) & (pred.model == m) & (pred.strategy == BASE) & (pred["mode"] == mode)]
        stat, p = (np.nan, np.nan) if st == BASE else dm_test(r.actual.values, r.pred.values, base.pred.values,
                                                              kind="ape")
        rows.append({"geo": g, "model": m, "strategy": st, "mode": mode, "MAPE": metrics(r, df)["MAPE"],
                     "DM": stat, "p": p, "n_train_first": int(r.n_train.iloc[0])})
    tab = pd.DataFrame(rows)
    tab.to_csv(OUTPUTS / "r2_structural.csv", index=False, encoding="utf-8-sig")

    L = ["# R2 구조변화 대응: 추정창·가중치·위기 변수", "",
         "2023~2025 롤링 1개월 앞 MAPE(%). ▲/▼ = 같은 모델의 '확장 2015~' 대비 DM 검정(APE) p<0.05로 "
         "더 정확/덜 정확. 굵게 = 국가별 최저.", ""]
    for mode, title in (("ex_post", "사후예측"), ("ex_ante", "사전예측")):
        for m in MODELS:
            L += [f"## {m} — {title}", "", "| 전략 | " + " | ".join(GEO_NAMES[g] for g in ALL_GEOS) + " |",
                  "| --- |" + " --- |" * len(ALL_GEOS)]
            sub = tab[(tab.model == m) & (tab["mode"] == mode)]
            for st in STRATEGIES:
                cells = []
                for g in ALL_GEOS:
                    r = sub[(sub.geo == g) & (sub.strategy == st)].iloc[0]
                    txt = f"{r.MAPE:.1f}"
                    if r.p < 0.05:
                        txt += " ▲" if r.DM < 0 else " ▼"
                    if np.isclose(r.MAPE, sub[sub.geo == g].MAPE.min()):
                        txt = f"**{txt}**"
                    cells.append(txt)
                L.append(f"| {st} | " + " | ".join(cells) + " |")
            L.append("")
    (OUTPUTS / "r2_structural.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))
    print(f"저장: outputs/r2_structural.md ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
