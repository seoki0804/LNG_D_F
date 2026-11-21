"""Diebold-Mariano 검정 (Harvey-Leybourne-Newbold 소표본 보정).

H0: 두 예측의 기대 손실이 같다. 손실차 d_t = L(e1_t) − L(e2_t).
통계량이 음수면 모델 1의 손실이 작다(더 정확하다).
R의 forecast::dm.test(..., h=1, power=2)와 같은 방식이다.
"""
import numpy as np
from scipy import stats


def loss(actual, pred, kind):
    e = np.asarray(actual, float) - np.asarray(pred, float)
    if kind == "se":        # 제곱오차 (RMSE에 대응)
        return e ** 2
    if kind == "ae":        # 절대오차
        return np.abs(e)
    if kind == "ape":       # 절대백분율오차 (MAPE에 대응)
        return np.abs(e) / np.asarray(actual, float)
    raise ValueError(kind)


def dm_test(actual, pred1, pred2, h=1, kind="se"):
    """반환: (HLN 보정 DM 통계량, 양측 p값). 손실차가 모두 0이면 (0, 1)."""
    d = loss(actual, pred1, kind) - loss(actual, pred2, kind)
    n = len(d)
    dbar = d.mean()
    dc = d - dbar
    gamma = [np.sum(dc[k:] * dc[:n - k]) / n for k in range(h)]
    var = gamma[0] + 2 * sum(gamma[1:])
    if var <= 0:
        return 0.0, 1.0
    dm = dbar / np.sqrt(var / n)
    hln = np.sqrt((n + 1 - 2 * h + h * (h - 1) / n) / n)
    stat = dm * hln
    return float(stat), float(2 * stats.t.sf(abs(stat), df=n - 1))
