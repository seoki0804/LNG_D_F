"""공통 롤링 평가 코드 — 모든 모델은 이 코드로 평가한다 (누수 방지·결과 일관성).

방식: 평가 구간(기본 2023-01~2025-12)의 매달 t에 대해
  1) train_start ~ t-1 자료로 모델을 다시 추정하고
  2) t 한 달을 예측한다 (36회).
표준화 등 전처리는 fit_predict 안에서 학습 구간으로만 적합해야 한다.

모델은 fit_predict(train, test, features, target) -> 예측값 배열 형태의 함수로 넘긴다.

사용 예:
    from rolling_eval import load_country, rolling_forecast, metrics, BASE_FEATURES
    df = load_country("DE")
    res = rolling_forecast(df, my_fit_predict, BASE_FEATURES)
    print(metrics(res, df))
"""
import numpy as np
import pandas as pd

from config import EVAL_END, EVAL_START, PROCESSED

TARGET = "gas_pj"

# 사전 실험의 AI 모델 입력 9개
BASE_FEATURES = ["hdd", "cdd", "hicp_gas", "ttf_lag1", "ip", "msin", "mcos", "lag1", "lag12"]
# 독일 외부 변수 최종 후보
EXTRA_FEATURES = ["workdays", "ip_chem", "nuclear_gwh"]


def add_features(df, target=TARGET):
    """시차·달 변수 추가. 월이 연속(빈 달 없음)이라고 가정한다."""
    df = df.sort_values("month").reset_index(drop=True).copy()
    assert len(df) == len(pd.period_range(df.month.iloc[0], df.month.iloc[-1], freq="M")), "빈 달 있음"
    m = df.month.str[5:7].astype(int)
    df["msin"] = np.sin(2 * np.pi * m / 12)
    df["mcos"] = np.cos(2 * np.pi * m / 12)
    df["lag1"] = df[target].shift(1)
    df["lag12"] = df[target].shift(12)
    df["ttf_lag1"] = df["ttf_usd"].shift(1)
    df["coal_lag1"] = df["coal_usd"].shift(1)
    df["gas_coal_lag1"] = (df["ttf_usd"] / df["coal_usd"]).shift(1)
    df["ip_chem_lag1"] = df["ip_chem"].shift(1)
    return df


def load_country(geo, target=TARGET):
    df = pd.read_csv(PROCESSED / f"{geo}.csv", dtype={"month": str})
    return add_features(df, target)


def eval_months(start=EVAL_START, end=EVAL_END):
    return pd.period_range(start, end, freq="M").strftime("%Y-%m").tolist()


def rolling_forecast(df, fit_predict, features, target=TARGET, train_start="2015-01",
                     eval_start=EVAL_START, eval_end=EVAL_END):
    """매달 재추정 후 1개월 앞 예측. 반환: month, actual, pred."""
    need = list(dict.fromkeys(list(features) + [target]))
    rows = []
    for t in eval_months(eval_start, eval_end):
        train = df[(df.month >= train_start) & (df.month < t)].dropna(subset=need)
        test = df[df.month == t]
        if len(test) != 1 or test[need].isna().any().any():
            raise ValueError(f"{t}: 평가 달 자료 결측")
        pred = np.asarray(fit_predict(train, test, list(features), target), dtype=float).ravel()[0]
        rows.append({"month": t, "actual": float(test[target].iloc[0]), "pred": float(pred),
                     "n_train": len(train)})
    return pd.DataFrame(rows)


def metrics(res, df, target=TARGET, train_start="2015-01", eval_start=EVAL_START):
    """MAPE(%), RMSE(목표 단위), MASE(계절 naive 기준, 첫 추정 구간으로 척도 계산)."""
    e = res.actual - res.pred
    hist = df[(df.month >= train_start) & (df.month < eval_start)][target].to_numpy()
    scale = np.mean(np.abs(hist[12:] - hist[:-12]))
    return {
        "MAPE": float((e.abs() / res.actual).mean() * 100),
        "RMSE": float(np.sqrt((e ** 2).mean())),
        "MASE": float(e.abs().mean() / scale),
    }


def mape_by_year(res):
    r = res.assign(year=res.month.str[:4], ape=(res.actual - res.pred).abs() / res.actual * 100)
    return r.groupby("year").ape.mean().to_dict()
