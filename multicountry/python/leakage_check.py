"""데이터 누수 자동 점검 (계획서 3주차 '누수 점검').

방법: 예측 달 t보다 뒤의 자료를 일부러 망가뜨려도 t의 예측값이 그대로인지 본다.
  - 수요 y: t 이후(t 포함) 전부 ×10        (t의 수요는 예측 대상이라 쓰면 안 된다)
  - 다른 변수(기온·가격·산업 등): t+1 이후 전부 ×10 (사후예측은 t의 실제 기온·가격을 쓰는 것이 정의상 허용)
  - 망가뜨린 원자료로 시차·평년 변수를 다시 만들고(add_features), 같은 모델·설정으로 다시 예측
  예측이 1e-6 이상 달라지면 미래 정보가 새는 것이다.
대상: 6개국 × 본 실험 13개 모델(본 실험 설정) × 평가 달 3개(2023-01, 2024-06, 2025-12) × 사후·사전, 그리고 실시간 입력.

출력: outputs/leakage_check.md
실행: python python/leakage_check.py   (run_experiment.py 결과 필요)
"""
import json
import os

os.environ.setdefault("LOKY_MAX_CPU_COUNT", str(os.cpu_count() or 4))

import numpy as np
import pandas as pd
from joblib import Parallel, delayed

from config import ALL_GEOS, OUTPUTS, PROCESSED
from rolling_eval import DEMAND_LAG, add_features, realtime_features, rolling_forecast
from run_experiment import MODES, OUT as EXP_OUT, SPECS

MONTHS = ["2023-01", "2024-06", "2025-12"]
KEEP = {"geo", "month", "y_unit", "gas_flag", "hdd_source"}


def corrupt(raw, t):
    bad = raw.copy()
    num = [c for c in bad.columns if c not in KEEP and pd.api.types.is_numeric_dtype(bad[c])]
    later = bad.month > t
    bad.loc[later, num] = bad.loc[later, num] * 10
    bad.loc[bad.month >= t, "y"] = bad.loc[bad.month >= t, "y"] * 10
    return bad


def check(geo, spec, params, realtime=False):
    raw = pd.read_csv(PROCESSED / f"{geo}.csv", dtype={"month": str})
    feats = realtime_features(geo) if realtime else spec.features
    gap = DEMAND_LAG[geo] - 1 if realtime else 0
    modes = ("ex_ante",) if realtime else MODES
    worst = 0.0
    for t in MONTHS:
        fp = spec.make(params)
        a = rolling_forecast(add_features(raw), fp, feats, eval_start=t, eval_end=t, modes=modes, gap=gap)
        b = rolling_forecast(add_features(corrupt(raw, t)), spec.make(params), feats, eval_start=t, eval_end=t,
                             modes=modes, gap=gap)
        worst = max(worst, float(np.max(np.abs(a.pred.values - b.pred.values))))
    return {"geo": geo, "model": spec.name, "realtime": realtime, "max_abs_diff": worst}


def main():
    s = pd.read_csv(EXP_OUT / "summary.csv")
    post = s[s["mode"] == "ex_post"].set_index(["geo", "model"])
    jobs = []
    for g in ALL_GEOS:
        for sp in SPECS:
            p = json.loads(post.loc[(g, sp.name), "params"]) if sp.grid else {}
            jobs.append(delayed(check)(g, sp, p))
            if sp.name in ("Ridge", "Gradient Boosting", "LightGBM"):
                jobs.append(delayed(check)(g, sp, p, True))
    tab = pd.DataFrame(Parallel(n_jobs=-1)(jobs))
    ok = (tab.max_abs_diff < 1e-6)
    L = ["# 데이터 누수 자동 점검", "",
         f"검사 {len(tab)}건 (6개국 × 13개 모델 사후·사전 + 3개 모델 실시간, 평가 달 {', '.join(MONTHS)}): "
         f"통과 {ok.sum()}건, 실패 {(~ok).sum()}건.",
         "예측 달 이후 자료를 ×10으로 망가뜨려도 예측이 바뀌지 않으면 통과 (허용 오차 1e-6).", ""]
    if (~ok).any():
        L += ["| 국가 | 모델 | 실시간 | 최대 차이 |", "| --- | --- | --- | --- |"]
        L += [f"| {r.geo} | {r.model} | {r.realtime} | {r.max_abs_diff:.3g} |" for r in tab[~ok].itertuples()]
    (OUTPUTS / "leakage_check.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
