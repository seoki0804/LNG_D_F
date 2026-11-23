"""다기간 예측 모델. 모두 fit_predict(train, fut, **params) → 12개 예측값.

train: 예측 시점 T까지의 자료(수요 y와 실제 기온·가격), fut: mh.future_frame(수요 없음).
"""
import os
import warnings

import lightgbm as lgb
import numpy as np
import pandas as pd
import statsmodels.api as sm
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from statsmodels.tsa.statespace.sarimax import SARIMAX

from mh import HORIZONS, mshift

warnings.filterwarnings("ignore")
os.environ.setdefault("LOKY_MAX_CPU_COUNT", str(os.cpu_count() or 4))   # joblib의 wmic 호출 경고 방지


def month_idx(months):
    p = pd.PeriodIndex(months, freq="M")
    return (p.year - 2016) * 12 + p.month - 1


def design(frame, feats):
    """특성 이름 → 설계행렬. 가격은 로그, trend는 2016-01부터의 개월 수."""
    X = pd.DataFrame(index=frame.index)
    m = frame.month.str[5:].astype(int)
    for f in feats:
        if f == "trend":
            X[f] = month_idx(frame.month)
        elif f == "msin":
            X[f] = np.sin(2 * np.pi * m / 12)
        elif f == "mcos":
            X[f] = np.cos(2 * np.pi * m / 12)
        elif f == "log_ratio":   # LNG/석탄 가격비 (발전 연료 전환)
            X[f] = np.log(frame["lng_usd"] / frame["coal_usd"])
        elif f.startswith("log_"):
            X[f] = np.log(frame[{"log_cpi": "cpi_city_gas", "log_lng": "lng_usd", "log_ip": "ip", "log_coal": "coal_usd",
                                 "log_smp": "smp"}[f]])
        else:
            X[f] = frame[f]
    return X


# ---------------- 기준선 ----------------
def snaive(train, fut):
    """1년 전 같은 달."""
    return fut.y_lag12.values


# ---------------- 회귀 (√Y, 강의 Ch1~6의 구조) ----------------
def reg(train, fut, feats=("hdd", "cdd"), sqrt=True, recent=None):
    """recent: 최근 N개월만으로 적합 (None이면 학습 자료 전체)."""
    feats = list(feats)
    if recent:
        train = train.tail(recent)
    X = design(train, feats)
    ok = X.notna().all(axis=1).values            # 첫 달 전월 기온처럼 계산할 수 없는 행은 뺀다
    y = (np.sqrt(train.y) if sqrt else train.y).values[ok]
    fit = sm.OLS(y, sm.add_constant(X.values[ok], has_constant="add")).fit()
    p = fit.predict(sm.add_constant(design(fut, feats).values, has_constant="add"))
    return np.maximum(p, 0) ** 2 if sqrt else p


# ---------------- 통계 시계열 ----------------
def sarimax(train, fut, order=(1, 0, 0), seasonal=(0, 1, 1), exog=("hdd",)):
    exog = list(exog)
    trend = "c" if seasonal[1] == 0 else "n"
    m = SARIMAX(np.log(train.y.values), exog=train[exog].values if exog else None, order=order,
                seasonal_order=(*seasonal, 12), trend=trend, enforce_stationarity=False,
                enforce_invertibility=False).fit(disp=False)
    f = m.forecast(len(fut), exog=fut[exog].values if exog else None)
    return np.exp(f)


def ets(train, fut, trend=None, damped=False):
    m = ExponentialSmoothing(np.log(train.y.values), trend=trend, damped_trend=damped if trend else False,
                             seasonal="add", seasonal_periods=12, initialization_method="estimated").fit()
    return np.exp(m.forecast(len(fut)))


# ---------------- 기계학습 (직접 다기간: 예측 시계 h를 특성으로 넣고 모든 (예측 시점, h) 쌍을 한 모델로) ----------------
# 학습 쌍은 학습 자료 안의 모든 가상 예측 시점 t와 h = 1~12로 만든다. 목표월 기온은 학습에서는 실제값,
# 예측에서는 fut의 값(사전예측이면 평년값)이다. 예측 시점 이후의 수요는 쓰지 않는다(목표월 1년 전 수요는 이미 관측).

def _pairs(train, featfn, target):
    hs = train.set_index("month")
    months = list(hs.index)
    X, Y = [], []
    for i, t in enumerate(months):
        if i < 15:
            continue
        tgt = [mshift(t, h) for h in HORIZONS if mshift(t, h) <= months[-1]]
        if not tgt:
            continue
        info = pd.DataFrame({"month": tgt, "h": list(range(1, len(tgt) + 1))})
        for c in ("hdd", "cdd", "coal_cap", "workdays"):
            info[c] = hs[c].reindex(tgt).values
        X.append(featfn(t, info))
        Y.append(target(tgt))
    return pd.concat(X, ignore_index=True), np.concatenate(Y)


def _fit_predict(make, X, Y, Xf):
    ok = np.isfinite(Y) & X.notna().all(axis=1).values
    m = make()
    m.fit(X[ok].values, Y[ok])
    return m.predict(Xf.values)


def _season(month):
    m = int(month[5:])
    return np.sin(2 * np.pi * m / 12), np.cos(2 * np.pi * m / 12)


def _direct(train, fut, make):
    """수요 수준을 직접 예측: log y_목표 ~ h, 달, 목표월 기온, 1년 전 같은 달 수요, 최근 3개월 수요, 요금, 정책·달력."""
    hs = train.set_index("month")
    y = hs.y

    def feats(T, rows):
        last3 = np.log(y.reindex([mshift(T, -k) for k in range(3)]).mean())
        cpi = np.log(hs.cpi_city_gas.get(T, np.nan))
        return pd.DataFrame([{"h": r.h, **dict(zip(("msin", "mcos"), _season(r.month))), "hdd": r.hdd, "cdd": r.cdd,
                              "lag12": np.log(y.get(mshift(r.month, -12), np.nan)), "last3": last3, "log_cpi": cpi,
                              "coal_cap": r.coal_cap, "workdays": r.workdays} for r in rows.itertuples()])

    X, Y = _pairs(train, feats, lambda tgt: np.log(y.reindex(tgt).values))
    return np.exp(_fit_predict(make, X, Y, feats(train.month.max(), fut)))


def _hybrid(train, fut, make, feats=("hdd", "cdd")):
    """하이브리드: 회귀 √Y가 기온 효과를 잡고, ML이 회귀의 비율 잔차 log(y / 회귀 적합값)를 예측해 보정한다."""
    feats = list(feats)
    ols = sm.OLS(np.sqrt(train.y.values), sm.add_constant(design(train, feats).values, has_constant="add")).fit()
    res = pd.Series(np.log(train.y.values / np.maximum(ols.fittedvalues, 1e-9) ** 2), index=train.month.values)

    def rfeats(T, rows):
        lvl = res.reindex([mshift(T, -k) for k in range(3)]).mean()
        return pd.DataFrame([{"h": r.h, **dict(zip(("msin", "mcos"), _season(r.month))), "res_level": lvl,
                              "res_lag12": res.get(mshift(r.month, -12), np.nan), "hdd": r.hdd,
                              "coal_cap": r.coal_cap} for r in rows.itertuples()])

    X, Y = _pairs(train, rfeats, lambda tgt: res.reindex(tgt).values)
    base = np.maximum(ols.predict(sm.add_constant(design(fut, feats).values, has_constant="add")), 0) ** 2
    return base * np.exp(_fit_predict(make, X, Y, rfeats(train.month.max(), fut)))


class _Scaled:
    def __init__(self, est):
        self.est, self.sc = est, StandardScaler()

    def fit(self, X, y):
        self.est.fit(self.sc.fit_transform(X), y)
        return self

    def predict(self, X):
        return self.est.predict(self.sc.transform(X))


def _lgb(num_leaves=7, n_estimators=300, learning_rate=0.03, min_child_samples=20, seed=0):
    return lambda: lgb.LGBMRegressor(num_leaves=num_leaves, n_estimators=n_estimators, learning_rate=learning_rate,
                                     min_child_samples=min_child_samples, subsample=0.8, subsample_freq=1,
                                     colsample_bytree=0.8, random_state=seed, verbose=-1)


def ridge(train, fut, alpha=1.0):
    return _direct(train, fut, lambda: _Scaled(Ridge(alpha=alpha)))


def lgbm(train, fut, seed=0, **p):
    return _direct(train, fut, _lgb(seed=seed, **p))


def hybrid_ridge(train, fut, feats=("hdd", "cdd"), alpha=1.0):
    return _hybrid(train, fut, lambda: _Scaled(Ridge(alpha=alpha)), feats)


def hybrid_lgbm(train, fut, feats=("hdd", "cdd"), seed=0, **p):
    return _hybrid(train, fut, _lgb(seed=seed, **p), feats)
