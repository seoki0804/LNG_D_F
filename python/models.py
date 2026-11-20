"""사전 실험 모델 모음. 모두 fit_predict(train, test, features, target) 형태.

기본 설정(튜닝 없음). 표준화는 Pipeline 안에서 학습 구간으로만 적합한다.
"""
import warnings

import numpy as np
import statsmodels.api as sm
from sklearn.compose import TransformedTargetRegressor
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import Lasso, Ridge
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVR
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from statsmodels.tsa.statespace.sarimax import SARIMAX

SEED = 0


def sklearn_model(make_estimator, scale_y=False):
    def fit_predict(train, test, features, target):
        pipe = make_pipeline(StandardScaler(), make_estimator())
        if scale_y:
            pipe = TransformedTargetRegressor(regressor=pipe, transformer=StandardScaler())
        pipe.fit(train[features], train[target])
        return pipe.predict(test[features])
    return fit_predict


def ols(sqrt=False):
    """OLS. sqrt=True면 √Y에 적합하고 예측을 제곱해 되돌린다."""
    def fit_predict(train, test, features, target):
        y = np.sqrt(train[target]) if sqrt else train[target]
        m = sm.OLS(y, sm.add_constant(train[features])).fit()
        p = m.predict(sm.add_constant(test[features], has_constant="add")).to_numpy()
        return p ** 2 if sqrt else p
    return fit_predict


def seasonal_naive(train, test, features, target):
    return test["lag12"].to_numpy()


def holt_winters(train, test, features, target):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        m = ExponentialSmoothing(train[target].to_numpy(), trend="add", seasonal="add",
                                 seasonal_periods=12).fit()
    return m.forecast(1)


def sarimax(train, test, features, target):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        m = SARIMAX(train[target].to_numpy(), exog=train[features].to_numpy(), order=(1, 0, 0),
                    seasonal_order=(1, 0, 0, 12), trend="c").fit(disp=False)
    return m.forecast(1, exog=test[features].to_numpy())


def hybrid(reg_features, ml_features):
    """회귀(√Y ~ reg_features) + GBM이 회귀 잔차(원 단위)를 학습."""
    def fit_predict(train, test, features, target):
        base = ols(sqrt=True)
        fitted = base(train, train, reg_features, target)
        resid = train[target].to_numpy() - fitted
        gbm = GradientBoostingRegressor(random_state=SEED).fit(train[ml_features], resid)
        return base(train, test, reg_features, target) + gbm.predict(test[ml_features])
    return fit_predict


ridge = sklearn_model(lambda: Ridge(alpha=1.0))
lasso = sklearn_model(lambda: Lasso(alpha=1.0, max_iter=50000))
rf = sklearn_model(lambda: RandomForestRegressor(random_state=SEED, n_jobs=-1))
gbm = sklearn_model(lambda: GradientBoostingRegressor(random_state=SEED))
svr = sklearn_model(lambda: SVR(), scale_y=True)
mlp = sklearn_model(lambda: MLPRegressor(hidden_layer_sizes=(16, 8), max_iter=5000,
                                         random_state=SEED), scale_y=True)
