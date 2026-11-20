"""독일 사전 실험 재현 (계획서 '독일 사전 실험 결과', '추정 시작 시점별', '외부 변수 점검' 표).

설정: 기본값(튜닝 없음), 롤링 1개월 앞 예측 2023-01~2025-12(36회), 사후예측(기상·가격 실제값).
출력: outputs/de_pre_experiment.md, outputs/de_*.csv

실행: python python/pre_experiment_de.py
"""
import time

import pandas as pd

import models as M
from config import OUTPUTS
from rolling_eval import BASE_FEATURES, load_country, mape_by_year, metrics, rolling_forecast

REG = ["hdd", "hicp_gas"]  # 회귀 √Y ~ HDD + 소비자가격

# (이름, fit_predict, 특성, 계획서 MAPE: 전체/2023/2025)
MODELS = [
    ("Gradient Boosting", M.gbm, BASE_FEATURES, (5.6, 5.2, 7.2)),
    ("Ridge (전체 변수)", M.ridge, BASE_FEATURES, (6.4, 7.0, 5.5)),
    ("회귀 √Y ~ HDD + 소비자가격", M.ols(sqrt=True), REG, (6.5, 5.6, 8.6)),
    ("Lasso (전체 변수)", M.lasso, BASE_FEATURES, (6.7, 6.5, 6.5)),
    ("하이브리드 (회귀 + GBM 잔차)", M.hybrid(REG, BASE_FEATURES), BASE_FEATURES, (6.8, 7.0, 6.7)),
    ("Random Forest", M.rf, BASE_FEATURES, (6.8, 9.0, 7.3)),
    ("SARIMAX + HDD·소비자가격", M.sarimax, REG, (7.0, 8.2, 6.9)),
    ("SVR", M.svr, BASE_FEATURES, (8.1, 11.7, 6.9)),
    ("계절 naive", M.seasonal_naive, ["lag12"], (8.3, 8.4, 9.2)),
    ("Holt-Winters", M.holt_winters, [], (9.2, 8.9, 11.0)),
    ("MLP (16-8)", M.mlp, BASE_FEATURES, (9.3, 13.6, 7.9)),
    ("단순회귀 Y ~ HDD", M.ols(), ["hdd"], (11.8, 14.5, 12.5)),
]

START_MODELS = [
    ("회귀 √Y ~ HDD + 소비자가격", M.ols(sqrt=True), REG, (8.5, 6.5, 5.9)),
    ("Ridge (변수 9개)", M.ridge, BASE_FEATURES, (6.0, 6.4, 8.5)),
    ("Gradient Boosting", M.gbm, BASE_FEATURES, (7.2, 5.6, 6.7)),
    ("Random Forest", M.rf, BASE_FEATURES, (7.3, 6.8, 6.6)),
]
STARTS = ["2009-01", "2015-01", "2019-01"]

# (이름, 추가 변수, 계획서 MAPE OLS/Ridge/GBM)
CANDIDATES = [
    ("기존 변수", [], (6.5, 6.4, 5.6)),
    ("영업일 수", ["workdays"], (6.6, 6.0, 5.5)),
    ("화학 생산지수", ["ip_chem"], (6.4, 5.7, 5.1)),
    ("화학 생산지수(전월)", ["ip_chem_lag1"], (6.6, 6.6, 5.8)),
    ("원자력 발전량", ["nuclear_gwh"], (6.4, 6.0, 5.4)),
    ("가스/석탄 가격비(전월)", ["gas_coal_lag1"], (6.2, 6.7, 5.6)),
    ("석탄 가격(전월)", ["coal_lag1"], (6.7, 6.7, 5.2)),
    ("달의 일수", ["days"], (6.6, 6.4, 5.6)),
    ("화학 + 영업일 + 원자력", ["ip_chem", "workdays", "nuclear_gwh"], (6.5, 5.3, 5.0)),
]


def fmt(x):
    return f"{x:.1f}"


def main():
    df = load_country("DE")
    t0 = time.time()
    md = ["# 독일 사전 실험 재현 결과", "",
          "롤링 1개월 앞 예측 2023-01~2025-12 (36회), 사후예측, 기본 설정. "
          "괄호 안은 계획서 값.", ""]

    # 1) 모델 비교 (추정 시작 2015-01)
    rows, preds = [], []
    for name, fp, feats, doc in MODELS:
        res = rolling_forecast(df, fp, feats, train_start="2015-01")
        m, y = metrics(res, df), mape_by_year(res)
        rows.append({"모델": name, "MAPE": m["MAPE"], "MAPE_2023": y["2023"], "MAPE_2024": y["2024"],
                     "MAPE_2025": y["2025"], "RMSE_PJ": m["RMSE"], "MASE": m["MASE"],
                     "계획서_MAPE": doc[0], "계획서_2023": doc[1], "계획서_2025": doc[2]})
        preds.append(res.assign(model=name))
        print(f"{name:28s} MAPE {m['MAPE']:.2f}% (계획서 {doc[0]}%)  [{time.time() - t0:.0f}s]")
    tab = pd.DataFrame(rows).sort_values("MAPE")
    tab.to_csv(OUTPUTS / "de_models.csv", index=False, encoding="utf-8-sig")
    pd.concat(preds).to_csv(OUTPUTS / "de_predictions.csv", index=False, encoding="utf-8-sig")
    md += ["## 1. 모델 비교 (추정 시작 2015-01)", "",
           "| 모델 | MAPE | 2023 | 2024 | 2025 | RMSE (PJ) | MASE |",
           "| --- | --- | --- | --- | --- | --- | --- |"]
    for r in tab.itertuples():
        md.append(f"| {r.모델} | {fmt(r.MAPE)}% ({r.계획서_MAPE}) | {fmt(r.MAPE_2023)} ({r.계획서_2023}) | "
                  f"{fmt(r.MAPE_2024)} | {fmt(r.MAPE_2025)} ({r.계획서_2025}) | {fmt(r.RMSE_PJ)} | "
                  f"{r.MASE:.2f} |")

    # 2) 추정 시작 시점
    rows = []
    for name, fp, feats, doc in START_MODELS:
        row = {"모델": name}
        for s, d in zip(STARTS, doc):
            res = rolling_forecast(df, fp, feats, train_start=s)
            row[s] = metrics(res, df, train_start=s)["MAPE"]
            row[f"계획서_{s}"] = d
        rows.append(row)
        print(f"시작 시점 {name}: " + ", ".join(f"{s} {row[s]:.1f}%" for s in STARTS))
    st = pd.DataFrame(rows)
    st.to_csv(OUTPUTS / "de_start_year.csv", index=False, encoding="utf-8-sig")
    md += ["", "## 2. 추정 시작 시점별 MAPE", "",
           "| 모델 | " + " | ".join(f"{s[:4]}년부터" for s in STARTS) + " |",
           "| --- | --- | --- | --- |"]
    for r in rows:
        md.append(f"| {r['모델']} | " + " | ".join(f"{fmt(r[s])}% ({r['계획서_' + s]})" for s in STARTS) + " |")

    # 3) 외부 변수
    rows = []
    for name, extra, doc in CANDIDATES:
        o = metrics(rolling_forecast(df, M.ols(sqrt=True), REG + extra), df)["MAPE"]
        r_ = metrics(rolling_forecast(df, M.ridge, BASE_FEATURES + extra), df)["MAPE"]
        g = metrics(rolling_forecast(df, M.gbm, BASE_FEATURES + extra), df)["MAPE"]
        rows.append({"후보": name, "OLS": o, "Ridge": r_, "GBM": g, "계획서": "/".join(map(str, doc))})
        print(f"외부 변수 {name}: {o:.1f} / {r_:.1f} / {g:.1f} (계획서 {rows[-1]['계획서']})")
    ex = pd.DataFrame(rows)
    ex.to_csv(OUTPUTS / "de_external_vars.csv", index=False, encoding="utf-8-sig")
    md += ["", "## 3. 외부 변수 추가 시 MAPE % (OLS / Ridge / GBM)", "",
           "| 후보 변수 | 재현 | 계획서 |", "| --- | --- | --- |"]
    for r in rows:
        md.append(f"| {r['후보']} | {fmt(r['OLS'])} / {fmt(r['Ridge'])} / {fmt(r['GBM'])} | {r['계획서']} |")

    (OUTPUTS / "de_pre_experiment.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"\n저장: {OUTPUTS / 'de_pre_experiment.md'}  ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
