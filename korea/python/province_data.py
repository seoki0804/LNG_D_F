"""시도별 도시가스 판매량 계층 예측의 자료와 기간 (run_province.py, foundation_mh.py --province 공용, 가벼운 의존성만)."""
import pandas as pd

from config import PROCESSED, PROVINCES

TRAIN_P = "2006-01"
VAL_P = ("2017-01", "2019-12")
EVAL_P = ("2020-01", "2022-12")
TOTAL = "전국"
NODES = [TOTAL] + PROVINCES
WEATHER_END = "2023-12"


def add_lags(f):
    f["hdd_l1"], f["cdd_l1"] = f.hdd.shift(1), f.cdd.shift(1)
    return f


def load_frames():
    nat = pd.read_csv(PROCESSED / "national.csv")
    cal = nat[["month", "cpi_city_gas", "lng_usd", "ip", "days", "workdays", "seollal", "chuseok", "coal_cap"]]
    p = pd.read_csv(PROCESSED / "province.csv")
    p = p[(p.month >= TRAIN_P) & (p.month <= WEATHER_END)]     # 판매량은 2022-12까지, 기온은 예측 입력용으로 1년 더
    frames = {}
    for prov, g in p.groupby("province"):
        frames[prov] = add_lags(g[["month", "sales", "hdd", "cdd", "hdd_clim", "cdd_clim"]].rename(columns={"sales": "y"})
                                .merge(cal, on="month", how="left").sort_values("month").reset_index(drop=True))
    tot = p.groupby("month").sales.sum(min_count=1).rename("y").reset_index()     # 세종은 2013년부터
    w = nat[["month", "hdd", "cdd", "hdd_clim", "cdd_clim"]]                     # 전국 수요가중 기온
    w = w[(w.month >= TRAIN_P) & (w.month <= WEATHER_END)]
    frames[TOTAL] = add_lags(tot.merge(w, on="month", how="right").merge(cal, on="month")
                             .sort_values("month").reset_index(drop=True))
    return {k: frames[k] for k in NODES}
