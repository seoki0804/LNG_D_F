"""연구 과제 R1 (변수 설계), 독일: 외부 변수를 하나씩·조합으로 더했을 때 정확도가 바뀌는가.

본 실험(run_experiment.py)과 같은 절차를 변수 조합마다 반복한다.
  - 변수 조합마다 2020~2022 검증 구간에서 하이퍼파라미터를 새로 골라 고정
  - 2023~2025 롤링 평가, 사후·사전예측 (사전예측에서 같은 달 화학 생산·원자력은 직전 달 값)
  - 랜덤 모델은 시드 5개 평균
  - DM 검정: 같은 모델의 '기존 변수' 대비 (손실 APE, 사후예측)

출력: outputs/r1_de_variables.csv, outputs/r1_de_variables.md
실행: python python/r1_variables_de.py
"""
import json
import os
import time

os.environ.setdefault("LOKY_MAX_CPU_COUNT", str(os.cpu_count() or 4))

import pandas as pd
from joblib import Parallel, delayed

from config import OUTPUTS
from dm_test import dm_test
from rolling_eval import BASE_FEATURES, load_country, metrics
from run_experiment import BENCH, MODES, REG, SEEDS, SPEC, final_task, tune_task

GEO = "DE"
MODELS = [BENCH, "Ridge", "Lasso", "Gradient Boosting", "LightGBM"]
CANDIDATES = [
    ("기존 변수", []),
    ("영업일 수", ["workdays"]),
    ("화학 생산지수", ["ip_chem"]),
    ("화학 생산지수(전월)", ["ip_chem_lag1"]),
    ("원자력 발전량", ["nuclear_gwh"]),
    ("풍력 발전량", ["wind_gwh"]),
    ("가스/석탄 가격비(전월)", ["gas_coal_lag1"]),
    ("석탄 가격(전월)", ["coal_lag1"]),
    ("달의 일수", ["days"]),
    ("영업일 + 화학(전월)", ["workdays", "ip_chem_lag1"]),
    ("화학 + 영업일 + 원자력", ["ip_chem", "workdays", "nuclear_gwh"]),
]


def feats(model, extra):
    base = REG if model == BENCH else BASE_FEATURES
    return base + extra


def main():
    t0 = time.time()
    # 1) 튜닝: (모델, 변수 조합, 설정)
    tasks = [(m, c, p) for m in MODELS if SPEC[m].grid for c, _ in CANDIDATES for p in SPEC[m].grid]
    extra = dict(CANDIDATES)
    print(f"[1/2] 튜닝 {len(tasks)}개", flush=True)
    out = Parallel(n_jobs=-1)(delayed(tune_task)(GEO, m, p, feats(m, extra[c])) for m, c, p in tasks)
    tun = pd.DataFrame(out).assign(cand=[c for _, c, _ in tasks])
    best = (tun.assign(_k=tun.val_MAPE.round(10)).sort_values(["_k", "params"], kind="mergesort")
            .groupby(["model", "cand"]).head(1).set_index(["model", "cand"]))

    # 2) 최종 평가
    jobs = []
    for m in MODELS:
        for c, ex in CANDIDATES:
            p = json.loads(best.loc[(m, c), "params"]) if SPEC[m].grid else {}
            for sd in (SEEDS if SPEC[m].stochastic(p) else [None]):
                jobs.append((m, c, p, sd, feats(m, ex)))
    print(f"[2/2] 평가 {len(jobs)}개 ({time.time() - t0:.0f}s)", flush=True)
    res = Parallel(n_jobs=-1)(delayed(final_task)(GEO, m, p, sd, f) for m, c, p, sd, f in jobs)
    raw = pd.concat([r.assign(cand=j[1]) for r, j in zip(res, jobs)], ignore_index=True)
    pred = (raw.groupby(["model", "cand", "mode", "month"], as_index=False)
            .agg(actual=("actual", "first"), pred=("pred", "mean")))

    df = load_country(GEO)
    rows = []
    for m in MODELS:
        base_post = pred[(pred.model == m) & (pred.cand == "기존 변수") & (pred["mode"] == "ex_post")]
        for c, ex in CANDIDATES:
            r = {"모델": m, "후보": c, "추가 변수": ", ".join(ex)}
            for mode in MODES:
                sub = pred[(pred.model == m) & (pred.cand == c) & (pred["mode"] == mode)]
                r[f"MAPE_{mode}"] = metrics(sub, df)["MAPE"]
            sub = pred[(pred.model == m) & (pred.cand == c) & (pred["mode"] == "ex_post")]
            stat, p = dm_test(sub.actual.values, sub.pred.values, base_post.pred.values, kind="ape")
            r["DM_vs_기존"], r["p_vs_기존"] = (stat, p) if c != "기존 변수" else (float("nan"), float("nan"))
            r["설정"] = best.loc[(m, c), "params"] if SPEC[m].grid else ""
            rows.append(r)
    tab = pd.DataFrame(rows)
    tab.to_csv(OUTPUTS / "r1_de_variables.csv", index=False, encoding="utf-8-sig")

    short = {BENCH: "회귀", "Ridge": "Ridge", "Lasso": "Lasso", "Gradient Boosting": "GBM", "LightGBM": "LightGBM"}
    L = ["# R1 변수 설계 (독일)", "",
         "롤링 1개월 앞 MAPE % (2023~2025, 36회). 변수 조합마다 2020~2022 검증 구간에서 튜닝 후 고정. "
         "회귀는 √Y ~ HDD + 소비자가격 + 추가 변수, AI 모델은 기본 9개 + 추가 변수.",
         "* 같은 모델의 기존 변수 대비 DM 검정 p < 0.05 (▲ 더 정확, ▼ 덜 정확).", ""]
    for mode, title in (("ex_post", "사후예측"), ("ex_ante", "사전예측 (같은 달 화학·원자력은 직전 달 값)")):
        L += [f"## {title}", "", "| 후보 | " + " | ".join(short[m] for m in MODELS) + " |",
              "| --- |" + " --- |" * len(MODELS)]
        for c, _ in CANDIDATES:
            cells = []
            for m in MODELS:
                r = tab[(tab.모델 == m) & (tab.후보 == c)].iloc[0]
                txt = f"{r[f'MAPE_{mode}']:.1f}"
                if mode == "ex_post" and r.p_vs_기존 < 0.05:
                    txt += (" ▲" if r.DM_vs_기존 < 0 else " ▼") + "*"
                cells.append(txt)
            L.append(f"| {c} | " + " | ".join(cells) + " |")
        L.append("")
    (OUTPUTS / "r1_de_variables.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))
    print(f"\n저장: outputs/r1_de_variables.md ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
