"""공통 롤링 평가 코드 — 모든 모델은 이 코드로 평가한다 (누수 방지·결과 일관성).

방식: 평가 구간(기본 2023-01~2025-12)의 매달 t에 대해
  1) train_start ~ t-1 자료로 모델을 다시 추정하고
  2) t 한 달을 예측한다 (36회).
표준화 등 전처리는 fit_predict 안에서 학습 구간으로만 적합해야 한다.

예측 모드 (같은 적합 모델로 두 입력을 함께 예측한다)
  ex_post : 사후예측. 예측 달의 기상·가격·산업 변수 실제값을 넣는다.
  ex_ante : 사전예측. 예측 시점(t-1 말)에 알 수 있는 값만 넣는다.
            HDD·CDD → 평년값(직전 10년 같은 달 평균),
            같은 달 가격·산업·발전 변수 → 직전 달 값(지속 가정).
            달력·시차 변수(영업일, 월, 전월·12개월 전 수요, 전월 도매가)는 그대로.
            주의: 전월 수요(lag1)는 실제로는 공표가 1~2달 늦다. 계획서 정의를 따라 아는 값으로 둔다.

모델은 fit_predict(train, test, features, target) -> test 행 수만큼의 예측값 배열.

사용 예:
    from rolling_eval import load_country, rolling_forecast, metrics, BASE_FEATURES
    df = load_country("DE")
    res = rolling_forecast(df, my_fit_predict, BASE_FEATURES, modes=("ex_post", "ex_ante"))
    print(metrics(res[res["mode"] == "ex_post"], df))
"""
import numpy as np
import pandas as pd

from config import EVAL_END, EVAL_START, PROCESSED

TARGET = "y"            # 국가 공통 수요 열 (유럽 PJ, 한국 천 톤; build_dataset.py 참고)
TRAIN_START = "2015-01"

# AI 모델 입력 9개 (계획서 사전 실험과 같은 구성, 국가 공통 이름)
#   소비자 요금, 도매가격(전월), 산업생산, HDD·CDD, 월 sin·cos, 전월·12개월 전 수요
BASE_FEATURES = ["hdd", "cdd", "price_retail", "price_wholesale_lag1", "ip", "msin", "mcos", "lag1", "lag12"]
# 독일 외부 변수 최종 후보
EXTRA_FEATURES = ["workdays", "ip_chem", "nuclear_gwh"]

# 사전예측에서 바꿔 넣는 열: 원래 열 → 예측 시점에 아는 대체 열
SAME_MONTH_VARS = ["price_retail", "price_wholesale", "ip", "hicp_gas", "ip_chem", "nuclear_gwh", "wind_gwh",
                   "ttf_usd", "coal_usd", "lng_asia_usd", "cpi_city_gas"]
EX_ANTE = {"hdd": "hdd_norm", "cdd": "cdd_norm", "hdd_crisis": "hdd_crisis_norm", "hdd_crisis9": "hdd_crisis9_norm",
           **{v: f"{v}_prev" for v in SAME_MONTH_VARS}}
NORMAL_YEARS = 10
CRISIS_START = "2022-03"   # 러시아 침공(2022-02) 이후 가격 급등·수요 감축 (R2 구조변화 변수, 사전에 정한 시점)
CRISIS9_START = "2022-09"  # 견고성 확인용: EU 수요 감축 규정(2022/1369, 2022-08 시행) 직후

# 실시간 예측의 공표 지연 (개월). 2026-11-21에 관측한 최신 자료 시점 기준:
#   수요: 독일·이탈리아·스페인·네덜란드 2026-10, 프랑스·한국 2026-09 → 예측 달 t의 직전 달 말에 아는 최신 수요 = t-2 / t-3
#   산업생산: 2026-09 → t-3,  소비자요금·도매가: t-1 (속보·월평균),  기온: 평년값
DEMAND_LAG = {"DE": 2, "IT": 2, "ES": 2, "NL": 2, "FR": 3, "KR": 3}
IP_LAG = 3


def realtime_features(geo):
    """실시간 예측용 입력 9개: 전월 수요·같은 달 산업생산 대신 공표 지연을 반영한 시차를 쓴다."""
    return ["hdd", "cdd", "price_retail", "price_wholesale_lag1", f"ip_lag{IP_LAG}", "msin", "mcos",
            f"lag{DEMAND_LAG[geo]}", "lag12"]


def add_features(df, target=TARGET):
    """시차·달·평년 변수 추가. 월이 연속(빈 달 없음)이라고 가정한다."""
    df = df.sort_values("month").reset_index(drop=True).copy()
    full = pd.period_range(df.month.iloc[0], df.month.iloc[-1], freq="M")
    assert len(df) == len(full), "빈 달이 있습니다"
    m = df.month.str[5:7].astype(int)
    df["msin"] = np.sin(2 * np.pi * m / 12)
    df["mcos"] = np.cos(2 * np.pi * m / 12)
    df["lag1"] = df[target].shift(1)
    df["lag2"] = df[target].shift(2)
    df["lag3"] = df[target].shift(3)
    df["lag12"] = df[target].shift(12)
    df["ip_lag2"] = df["ip"].shift(2)
    df["ip_lag3"] = df["ip"].shift(3)
    df["price_wholesale_lag1"] = df["price_wholesale"].shift(1)
    if "ttf_usd" in df:
        df["ttf_lag1"] = df["ttf_usd"].shift(1)
    if "coal_usd" in df:
        df["coal_lag1"] = df["coal_usd"].shift(1)
        df["gas_coal_lag1"] = (df["ttf_usd"] / df["coal_usd"]).shift(1)
    if "ip_chem" in df:
        df["ip_chem_lag1"] = df["ip_chem"].shift(1)
    for v in ("hdd", "cdd"):
        if v in df:
            past = pd.concat([df[v].shift(12 * k) for k in range(1, NORMAL_YEARS + 1)], axis=1)
            df[f"{v}_norm"] = past.mean(axis=1).where(past.notna().sum(axis=1) >= 5)
    for v in SAME_MONTH_VARS:
        if v in df:
            df[f"{v}_prev"] = df[v].shift(1)
    df["crisis"] = (df.month >= CRISIS_START).astype(float)
    df["hdd_crisis"] = df["hdd"] * df["crisis"]
    df["hdd_crisis_norm"] = df["hdd_norm"] * df["crisis"]
    df["crisis9"] = (df.month >= CRISIS9_START).astype(float)
    df["hdd_crisis9"] = df["hdd"] * df["crisis9"]
    df["hdd_crisis9_norm"] = df["hdd_norm"] * df["crisis9"]
    return df


def load_country(geo, target=TARGET):
    df = pd.read_csv(PROCESSED / f"{geo}.csv", dtype={"month": str})
    return add_features(df, target)


def eval_months(start=EVAL_START, end=EVAL_END):
    return pd.period_range(start, end, freq="M").strftime("%Y-%m").tolist()


def make_test(row, features, mode):
    """평가 달 한 행을 모드에 맞게 만든다."""
    test = row.copy()
    if mode == "ex_ante":
        for f in features:
            if f in EX_ANTE:
                test[f] = row[EX_ANTE[f]].to_numpy()
    elif mode != "ex_post":
        raise ValueError(mode)
    return test


def rolling_forecast(df, fit_predict, features, target=TARGET, train_start=TRAIN_START,
                     eval_start=EVAL_START, eval_end=EVAL_END, modes=("ex_post",), window=None, gap=0):
    """매달 재추정 후 1개월 앞 예측. 반환: month, mode, actual, pred, n_train.
    window: None이면 train_start부터 쌓는 확장창, 정수 N이면 직전 N개월만 쓰는 이동창.
    gap: 실시간 예측에서 아직 공표되지 않은 최근 gap개월을 학습에서 뺀다 (목표값을 모르므로)."""
    features = list(features)
    need = list(dict.fromkeys(features + [target]))
    rows = []
    for t in eval_months(eval_start, eval_end):
        start = train_start
        if window:
            start = max(train_start, (pd.Period(t, "M") - window).strftime("%Y-%m"))
        end = (pd.Period(t, "M") - gap).strftime("%Y-%m")
        train = df[(df.month >= start) & (df.month < end)].dropna(subset=need)
        row = df[df.month == t]
        tests = [make_test(row, features, mode) for mode in modes]
        test = pd.concat(tests, ignore_index=True)
        if len(row) != 1 or test[need].isna().any().any():
            bad = test[need].columns[test[need].isna().any()].tolist()
            raise ValueError(f"{t}: 평가 달 자료 결측 {bad}")
        pred = np.asarray(fit_predict(train, test, features, target), dtype=float).ravel()
        if len(pred) != len(modes):
            raise ValueError(f"예측값 개수 {len(pred)} ≠ 모드 수 {len(modes)}")
        for mode, p in zip(modes, pred):
            rows.append({"month": t, "mode": mode, "actual": float(row[target].iloc[0]),
                         "pred": float(p), "n_train": len(train)})
    return pd.DataFrame(rows)


def metrics(res, df, target=TARGET, train_start=TRAIN_START, eval_start=EVAL_START):
    """MAPE(%), RMSE(수요 단위: 유럽 PJ, 한국 천 톤), MASE(계절 naive 기준, 첫 추정 구간으로 척도 계산).
    res는 한 모드만."""
    if "mode" in res and res["mode"].nunique() > 1:
        raise ValueError("metrics에는 한 모드의 결과만 넣으세요")
    e = res.actual - res.pred
    hist = df[(df.month >= train_start) & (df.month < eval_start)][target].reset_index(drop=True)
    scale = (hist - hist.shift(12)).abs().mean()   # 구간 안의 12개월 차분, 결측(한국 2015년)은 제외
    return {
        "MAPE": float((e.abs() / res.actual).mean() * 100),
        "RMSE": float(np.sqrt((e ** 2).mean())),
        "MASE": float(e.abs().mean() / scale),
    }


def mape_by_year(res):
    r = res.assign(year=res.month.str[:4], ape=(res.actual - res.pred).abs() / res.actual * 100)
    return r.groupby("year").ape.mean().to_dict()
