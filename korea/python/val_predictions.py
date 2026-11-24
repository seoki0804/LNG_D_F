"""검증 구간(목표월 2020~2022) 사전예측과 계산 시간.

튜닝에서 고른 설정 그대로 검증 구간의 예측값을 저장한다. 이 예측의 오차로 예측 시계별 conformal 예측구간을 만든다
(paper_metrics.py). 평가 구간(2023~2025) 자료는 쓰지 않는다. 계산 시간은 도시가스용, 예측 시점 6개에서
모델마다 학습+12개월 예측 한 번에 걸린 시간을 순차 실행으로 잰다.

출력: outputs/national/val_predictions.csv, timing.csv
실행: python python/val_predictions.py [--jobs 8]
"""
import argparse
import json
import os
import time

os.environ.setdefault("LOKY_MAX_CPU_COUNT", str(os.cpu_count() or 4))   # joblib의 wmic 호출 경고 방지

import numpy as np
import pandas as pd
from joblib import Parallel, delayed

from config import OUTPUTS, PROCESSED
from mh import VAL, EVAL, future_frame, origins, rolling
from run_national import SERIES, grid

OUT = OUTPUTS / "national"


def best_configs():
    tun = pd.read_csv(OUT / "tuning.csv")
    best = (tun.dropna(subset=["val_MAPE"]).assign(_k=lambda d: d.val_MAPE.round(8))
            .sort_values(["_k", "params"], kind="mergesort").groupby(["series", "model"]).first().reset_index())
    out = []
    for b in best.itertuples():
        p = json.loads(b.params)
        for k in ("feats", "order", "seasonal", "exog"):
            if k in p:
                p[k] = tuple(p[k])
        out.append((b.series, b.model, p))
    return out


def val_one(df, series, model, params, seed):
    fn = grid(series)[model][0]
    p = dict(params)
    if seed is not None:
        p["seed"] = seed
    r = rolling(df, series, fn, VAL, info="ex_ante", **p)
    return r.assign(series=series, model=model, info="ex_ante", window="val")


def timing(df, cfgs, n=6):
    """도시가스용, 평가 구간 예측 시점 중 6개에서 학습+예측 1회 시간(초)의 중앙값."""
    d = df.rename(columns={"city": "y"})
    d = d[d.month >= "2016-01"].reset_index(drop=True)
    Ts = origins(EVAL)[::8][:n]
    rows = []
    for series, model, params in cfgs:
        if series != "city":
            continue
        fn = grid(series)[model][0]
        sec = []
        for T in Ts:
            train = d[(d.month <= T) & d.y.notna()]
            fut = future_frame(d, T, "ex_ante")
            t = time.perf_counter()
            fn(train, fut, **params)
            sec.append(time.perf_counter() - t)
        rows.append({"model": model, "sec_per_origin": float(np.median(sec)),
                     "seeds": 3 if "LightGBM" in model else 1})
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", type=int, default=8)
    args = ap.parse_args()
    df = pd.read_csv(PROCESSED / "national.csv")
    cfgs = best_configs()
    t0 = time.time()
    jobs = [(s, m, p, sd) for s, m, p in cfgs for sd in ([0, 1, 2] if "LightGBM" in m else [None])]
    parts = Parallel(n_jobs=args.jobs)(delayed(val_one)(df, *j) for j in jobs)
    pred = (pd.concat(parts, ignore_index=True)
            .groupby(["series", "model", "info", "window", "origin", "month", "h"], as_index=False)
            .agg(pred=("pred", "mean"), actual=("actual", "first")))
    pred.to_csv(OUT / "val_predictions.csv", index=False, encoding="utf-8-sig")
    print(f"검증 구간 예측 {len(pred)}행, {(time.time() - t0) / 60:.1f}분", flush=True)
    tm = timing(df, cfgs)
    tm.to_csv(OUT / "timing.csv", index=False, encoding="utf-8-sig")
    print(tm.to_string(index=False))


if __name__ == "__main__":
    main()
