"""모델 정의. 모두 fit_predict(train, test, features, target) -> test 행 수만큼의 예측값.

- 표준화는 Pipeline 안에서 학습 구간으로만 적합한다 (누수 방지).
- 랜덤성이 있는 모델은 seeds를 받아 시드별 예측을 평균한다.
- build_*(params, seeds) 함수는 run_experiment.py의 하이퍼파라미터 그리드에서 쓴다.
- 아래쪽의 ridge, gbm 등은 사전 실험 재현용 기본 설정이다 (pre_experiment_de.py).
"""
import os
import warnings

os.environ.setdefault("LOKY_MAX_CPU_COUNT", str(os.cpu_count() or 4))
# LightGBM이 Pipeline 안에서 받는 numpy 배열 때문에 생기는 무해한 경고
warnings.filterwarnings("ignore", message="X does not have valid feature names")

import numpy as np
import statsmodels.api as sm
from lightgbm import LGBMRegressor
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
TARGET_TF = {
    None: (None, None),
    "sqrt": (np.sqrt, np.square),
    "log": (np.log, np.exp),
}


# ---------------- 공통 빌더 ----------------
def sklearn_model(make_estimator, scale_y=False, target_tf=None, seeds=None):
    """make_estimator(seed) 또는 make_estimator() → 추정기. seeds가 있으면 시드별 예측 평균."""
    func, inv = TARGET_TF[target_tf]

    def one(train, test, features, target, seed):
        est = make_estimator(seed) if seeds is not None else make_estimator()
        pipe = make_pipeline(StandardScaler(), est)
        if scale_y or func is not None:
            if func is not None and scale_y:
                raise ValueError("scale_y와 target_tf는 함께 쓰지 않는다")
            pipe = (TransformedTargetRegressor(regressor=pipe, transformer=StandardScaler())
                    if scale_y else TransformedTargetRegressor(regressor=pipe, func=func, inverse_func=inv))
        pipe.fit(train[features], train[target])
        return pipe.predict(test[features])

    def fit_predict(train, test, features, target):
        if seeds is None:
            return one(train, test, features, target, None)
        return np.mean([one(train, test, features, target, s) for s in seeds], axis=0)

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
    return np.repeat(m.forecast(1), len(test))


def sarimax(train, test, features, target):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        m = SARIMAX(train[target].to_numpy(), exog=train[features].to_numpy(), order=(1, 0, 0),
                    seasonal_order=(1, 0, 0, 12), trend="c").fit(disp=False)
        return np.array([m.forecast(1, exog=test[features].iloc[[i]].to_numpy())[0]
                         for i in range(len(test))])


def build_hw(p, seeds=None):
    """Holt-Winters: 추세(가법/없음), 계절성(가법/승법), 감쇠 추세를 검증 구간에서 고른다."""
    def fit_predict(train, test, features, target):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            m = ExponentialSmoothing(train[target].to_numpy(), trend=p["trend"], seasonal=p["seasonal"],
                                     damped_trend=p["damped"] if p["trend"] else False,
                                     seasonal_periods=12).fit()
        return np.repeat(m.forecast(1), len(test))
    return fit_predict


def build_sarimax(p, seeds=None):
    """SARIMAX(p,0,q)(P,D,Q)12 + 외생변수: 차수를 검증 구간에서 고른다."""
    def fit_predict(train, test, features, target):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            m = SARIMAX(train[target].to_numpy(), exog=train[features].to_numpy(), order=tuple(p["order"]),
                        seasonal_order=tuple(p["seasonal"]) + (12,),
                        trend="c" if p["seasonal"][1] == 0 else "n").fit(disp=False)
            return np.array([m.forecast(1, exog=test[features].iloc[[i]].to_numpy())[0]
                             for i in range(len(test))])
    return fit_predict


def hybrid(reg_features, ml_features, gbm_params=None, seeds=None):
    """회귀(√Y ~ reg_features) + GBM이 회귀 잔차(원 단위)를 학습."""
    gbm_params = gbm_params or {}
    base = ols(sqrt=True)

    def fit_predict(train, test, features, target):
        fitted = base(train, train, reg_features, target)
        resid = train[target].to_numpy() - fitted
        preds = []
        for s in (seeds or [SEED]):
            g = GradientBoostingRegressor(random_state=s, **gbm_params).fit(train[ml_features], resid)
            preds.append(g.predict(test[ml_features]))
        return base(train, test, reg_features, target) + np.mean(preds, axis=0)

    return fit_predict


# ---------------- 그리드 탐색용 빌더: build(params, seeds) ----------------
def build_ridge(p, seeds=None):
    return sklearn_model(lambda: Ridge(alpha=p["alpha"]), target_tf=p.get("target"))


def build_lasso(p, seeds=None):
    return sklearn_model(lambda: Lasso(alpha=p["alpha"], max_iter=100000), target_tf=p.get("target"))


def build_rf(p, seeds=None):
    return sklearn_model(lambda s: RandomForestRegressor(
        n_estimators=300, max_features=p["max_features"], min_samples_leaf=p["min_samples_leaf"],
        random_state=s, n_jobs=1), seeds=seeds or [SEED])


def build_gbm(p, seeds=None):
    stochastic = p.get("subsample", 1.0) < 1.0
    return sklearn_model(lambda s: GradientBoostingRegressor(random_state=s, **p),
                         seeds=(seeds or [SEED]) if stochastic else [SEED])


def build_lgbm(p, seeds=None):
    return sklearn_model(lambda: LGBMRegressor(learning_rate=0.05, n_estimators=200, random_state=SEED,
                                               n_jobs=1, verbose=-1, **p))


def build_svr(p, seeds=None):
    return sklearn_model(lambda: SVR(C=p["C"], epsilon=p["epsilon"]), scale_y=True)


def build_mlp(p, seeds=None):
    return sklearn_model(lambda s: MLPRegressor(hidden_layer_sizes=(16, 8), alpha=p["alpha"], max_iter=5000,
                                                random_state=s), scale_y=True, seeds=seeds or [SEED])


def build_hybrid(reg_features):
    def build(p, seeds=None):
        from rolling_eval import BASE_FEATURES
        stochastic = p.get("subsample", 1.0) < 1.0
        return hybrid(reg_features, BASE_FEATURES, p, seeds=(seeds or [SEED]) if stochastic else [SEED])
    return build


# ---------------- 사전 실험 재현용 기본 설정 (튜닝 없음) ----------------
ridge = sklearn_model(lambda: Ridge(alpha=1.0))
lasso = sklearn_model(lambda: Lasso(alpha=1.0, max_iter=50000))
rf = sklearn_model(lambda: RandomForestRegressor(random_state=SEED, n_jobs=-1))
gbm = sklearn_model(lambda: GradientBoostingRegressor(random_state=SEED))
svr = sklearn_model(lambda: SVR(), scale_y=True)
mlp = sklearn_model(lambda: MLPRegressor(hidden_layer_sizes=(16, 8), max_iter=5000,
                                         random_state=SEED), scale_y=True)
