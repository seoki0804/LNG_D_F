"""다기간(1~12개월 앞) 롤링 예측 평가 공통 코드.

예측 시점 T(마지막으로 수요를 아는 달)마다 T+1~T+12를 한 번에 예측한다. 평가 대상 달(목표월)이 같은 구간에 들어오는
예측만 모으므로, 모든 예측 시계(h)가 같은 목표월 집합으로 비교된다.

미래 입력(future)은 수요 열 없이 만들어 모델에 넘긴다 → 구조적으로 미래 수요를 볼 수 없다.
  정보 조건 ex_ante (기본, 실제 예측과 같음): 기온 = 평년값(직전 10년 같은 달 평균), 가격·산업 = 예측 시점 값 유지,
                                         달력·정책(석탄 상한제 기간) = 미리 아는 값
  정보 조건 ex_post (기온을 완벽히 안다고 가정): 기온만 실제값. ex_ante와의 차이 = 기온 예보가 줄일 수 있는 오차
"""
import numpy as np
import pandas as pd

H = 12
HORIZONS = list(range(1, H + 1))
TRAIN_START = "2016-01"
VAL = ("2020-01", "2022-12")       # 하이퍼파라미터·차수 선택용 목표월
EVAL = ("2023-01", "2025-12")      # 평가 목표월 (모든 h 공통 36개월)
HOLD = ("2026-01", "2026-09")      # 표본 외 (모델·설정 고정 후 한 번)

WEATHER = {"hdd": "hdd_clim", "cdd": "cdd_clim"}
FLAT = ["cpi_city_gas", "ip", "lng_usd", "elec_twh", "smp", "coal_usd"]          # 예측 시점 값을 그대로 둔다
KNOWN = ["days", "workdays", "seollal", "chuseok", "coal_cap"]  # 달력·정책: 미리 안다


def mshift(month, k):
    return (pd.Period(month, "M") + k).strftime("%Y-%m")


def origins(window):
    """목표월 구간 [a, b]를 덮는 예측 시점: a−12 … b−1."""
    a, b = window
    return [p.strftime("%Y-%m") for p in pd.period_range(mshift(a, -H), mshift(b, -1), freq="M")]


def future_frame(df, T, info="ex_ante"):
    """T 다음 12개월의 입력. 수요 열은 넣지 않는다."""
    months = [mshift(T, h) for h in HORIZONS]
    fut = df.set_index("month").reindex(months)
    last = df[df.month <= T].set_index("month")
    out = pd.DataFrame({"month": months, "h": HORIZONS})
    for c in KNOWN:
        if c in fut:
            out[c] = fut[c].values
    for c in FLAT:
        if c in last:
            s = last[c].dropna()
            out[c] = s.iloc[-1] if len(s) else np.nan
    for c, clim in WEATHER.items():
        if c in fut:
            out[c] = (fut[c] if info == "ex_post" else fut[clim]).values
            out[f"{c}_clim"] = fut[clim].values
    # 전월 기온(판매량은 검침 시점 기준이라 전월 기온에도 반응): 전월이 T 이하면 실제값, 아니면 정보 조건대로
    for c in ("hdd", "cdd"):
        if f"{c}_l1" in df:
            prev = [mshift(m, -1) for m in months]
            act = df.set_index("month")[c]
            nxt = out.set_index("month")[c]
            out[f"{c}_l1"] = [act.get(p) if p <= T else nxt.get(p, np.nan) for p in prev]
    # 1년 전 같은 달 수요는 h ≤ 12이면 이미 관측돼 있다 (계절 naive·모델 입력용)
    for c in [c for c in ("y",) if c in df]:
        out["y_lag12"] = [last[c].get(mshift(m, -12), np.nan) for m in months]
    return out


def rolling(df, target, fit_predict, window, info="ex_ante", train_start=TRAIN_START, **kw):
    """df: month 순 정렬, 수요 열 = target. fit_predict(train, future, **kw) → 길이 12 예측 배열."""
    d = df.rename(columns={target: "y"})
    d = d[d.month >= train_start].reset_index(drop=True)
    rows = []
    for T in origins(window):
        train = d[(d.month <= T) & d.y.notna()]
        fut = future_frame(d, T, info)
        fut = fut[fut.month <= window[1]].reset_index(drop=True)   # 평가 구간 뒤의 달은 예측하지 않는다 (입력이 없을 수 있다)
        keep = fut.month >= window[0]
        if not keep.any():
            continue
        pred = np.asarray(fit_predict(train, fut, **kw), dtype=float)
        act = d.set_index("month").y.reindex(fut.month).values
        rows.append(pd.DataFrame({"origin": T, "month": fut.month, "h": fut.h, "pred": pred, "actual": act})[keep])
    out = pd.concat(rows, ignore_index=True)
    return out[out.actual.notna()]


def ape(r):
    return (r.pred - r.actual).abs() / r.actual * 100


def mape_by_h(res, by=("h",)):
    r = res.assign(ape=ape(res))
    return r.groupby(list(by)).ape.mean()


def summary(res):
    """h별 MAPE와 묶음(1, 1~3, 4~6, 7~12, 전체)."""
    r = res.assign(ape=ape(res))
    out = {f"h{h}": r[r.h == h].ape.mean() for h in HORIZONS}
    out.update({"h1-3": r[r.h <= 3].ape.mean(), "h4-6": r[r.h.between(4, 6)].ape.mean(),
                "h7-12": r[r.h >= 7].ape.mean(), "all": r.ape.mean()})
    return out
