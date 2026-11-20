"""독일 ML 모델의 설정 민감도: 입력 변수 정의·하이퍼파라미터·타깃 변환에 따라 MAPE가 얼마나 흔들리는가.

사전 실험의 ML 수치(GBM 5.6%, Ridge 6.4%)가 기본 설정으로 정확히 재현되지 않아,
결과가 설정에 얼마나 민감한지 기록한다. 모델 간 MAPE 차이(약 1%p)를 해석할 때 기준으로 쓴다.

출력: outputs/de_sensitivity.csv
실행: python python/sensitivity_de.py
"""
import os
import warnings

os.environ.setdefault("LOKY_MAX_CPU_COUNT", "4")
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor
from sklearn.compose import TransformedTargetRegressor
from sklearn.ensemble import GradientBoostingRegressor, HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBRegressor

import models as M
from config import OUTPUTS
from rolling_eval import BASE_FEATURES as B, load_country, metrics, rolling_forecast


def with_target(make_est, func, inv):
    def fit_predict(train, test, features, target):
        m = TransformedTargetRegressor(regressor=make_pipeline(StandardScaler(), make_est()),
                                       func=func, inverse_func=inv)
        m.fit(train[features], train[target])
        return m.predict(test[features])
    return fit_predict


def drop(*names):
    return [f for f in B if f not in names]


GBM = lambda **kw: M.sklearn_model(lambda: GradientBoostingRegressor(random_state=0, **kw))

# (구분, 설정, fit_predict, 특성)
CASES = [
    ("GBM", "기본 (sklearn)", M.gbm, B),
    ("GBM", "CDD 제외", M.gbm, drop("cdd")),
    ("GBM", "산업생산 제외", M.gbm, drop("ip")),
    ("GBM", "시차 수요 제외", M.gbm, drop("lag1", "lag12")),
    ("GBM", "도매가격 같은 달", M.gbm, [f if f != "ttf_lag1" else "ttf_usd" for f in B]),
    ("GBM", "n_estimators 300, lr 0.05", GBM(n_estimators=300, learning_rate=0.05), B),
    ("GBM", "subsample 0.8", GBM(subsample=0.8), B),
    ("GBM", "huber 손실", GBM(loss="huber"), B),
    ("GBM", "log Y", with_target(lambda: GradientBoostingRegressor(random_state=0), np.log, np.exp), B),
    ("GBM", "HistGradientBoosting", M.sklearn_model(lambda: HistGradientBoostingRegressor(random_state=0)), B),
    ("GBM", "XGBoost 기본", M.sklearn_model(lambda: XGBRegressor(random_state=0, n_jobs=1)), B),
    ("GBM", "LightGBM 기본", M.sklearn_model(lambda: LGBMRegressor(random_state=0, verbose=-1)), B),
    ("GBM", "LightGBM min_child_samples 5",
     M.sklearn_model(lambda: LGBMRegressor(min_child_samples=5, random_state=0, verbose=-1)), B),
    ("Ridge", "기본 (alpha 1)", M.ridge, B),
    ("Ridge", "alpha 0.1", M.sklearn_model(lambda: Ridge(alpha=0.1)), B),
    ("Ridge", "alpha 10", M.sklearn_model(lambda: Ridge(alpha=10)), B),
    ("Ridge", "월 sin·cos 대신 월 정수", M.ridge, drop("msin", "mcos") + ["month_int"]),
    ("Ridge", "√Y", with_target(lambda: Ridge(alpha=1.0), np.sqrt, np.square), B),
    ("Ridge", "log Y", with_target(lambda: Ridge(alpha=1.0), np.log, np.exp), B),
]


def main():
    df = load_country("DE")
    df["month_int"] = df.month.str[5:7].astype(int)
    rows = []
    for group, name, fp, feats in CASES:
        mape = metrics(rolling_forecast(df, fp, feats), df)["MAPE"]
        rows.append({"모델": group, "설정": name, "MAPE": round(mape, 2)})
        print(f"{group:6s} {name:30s} {mape:.2f}%", flush=True)
    out = pd.DataFrame(rows)
    out.to_csv(OUTPUTS / "de_sensitivity.csv", index=False, encoding="utf-8-sig")
    for g, s in out.groupby("모델").MAPE:
        print(f"{g}: {s.min():.1f}~{s.max():.1f}% (폭 {s.max() - s.min():.1f}%p)")


if __name__ == "__main__":
    main()
