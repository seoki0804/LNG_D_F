"""파운데이션 모델 Chronos-2·TimesFM 2.5의 1~12개월 앞 예측 (학습·미세조정 없음).

예측 시점 T까지의 수요(과 공변량)를 문맥으로 넣고 12개월을 한 번에 예측한다. 미래 공변량은 mh.future_frame과 같다
(사전예측: 평년 기온·가격 유지, 사후예측: 실제 기온). 평가·표본 외 구간의 모든 예측 시점에 대해 실행한다.

실행 환경: 저장소 루트의 .venv-fm (multicountry/README.md 참고)
    ..\\.venv-fm\\Scripts\\python python\\foundation_mh.py              (korea/ 에서)
    ..\\.venv-fm\\Scripts\\python python\\foundation_mh.py --province   (시도별 도시가스, 계층 예측용)
출력: outputs/national/foundation.csv, outputs/province/foundation.csv
"""
import argparse
import time
import warnings

warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import torch

from config import OUTPUTS, PROCESSED
from mh import EVAL, HOLD, H, future_frame, origins

torch.manual_seed(0)
COVS = ["hdd", "cdd", "hdd_l1", "cdd_l1", "workdays", "coal_cap", "cpi_city_gas"]   # 있는 열만 쓴다 (전월 기온은 시도 판매량용)
SERIES = ["city", "power", "total"]


def items(frames, windows, info, covariates):
    """(문맥, 미래 공변량, 키) 목록. frames: {이름: 수요 열이 y인 데이터}."""
    ctx, fut, keys = [], [], []
    for name, df in frames.items():
        covs = [c for c in COVS if c in df]
        for window in windows:
            for T in origins(window):
                item = f"{name}|{T}"
                if item in keys:
                    continue
                h = df[(df.month <= T) & df.y.notna()].copy()
                h["item_id"], h["timestamp"] = item, pd.to_datetime(h.month + "-01")
                ctx.append(h[["item_id", "timestamp", "y"] + (covs if covariates else [])])
                if covariates:
                    f = future_frame(df, T, info)
                    f["item_id"], f["timestamp"] = item, pd.to_datetime(f.month + "-01")
                    fut.append(f[["item_id", "timestamp"] + covs])
                keys.append(item)
    return ctx, fut, keys


def chronos(frames, windows):
    from chronos import Chronos2Pipeline
    pipe = Chronos2Pipeline.from_pretrained("amazon/chronos-2", device_map="cpu")
    out = []
    for covariates, info in ((False, "ex_ante"), (True, "ex_ante"), (True, "ex_post")):
        ctx, fut, _ = items(frames, windows, info, covariates)
        pred = pipe.predict_df(pd.concat(ctx, ignore_index=True),
                               future_df=pd.concat(fut, ignore_index=True) if covariates else None,
                               id_column="item_id", timestamp_column="timestamp", target="y",
                               prediction_length=H, quantile_levels=[0.1, 0.5, 0.9], freq="MS")
        name = "Chronos-2 + 공변량" if covariates else "Chronos-2"
        infos = [info] if covariates else ["ex_ante", "ex_post"]      # 단변량은 기온 정보와 무관
        for i in infos:
            out.append(pd.DataFrame({"key": pred.item_id.to_numpy(), "month": pred.timestamp.dt.strftime("%Y-%m"),
                                     "model": name, "info": i, "pred": pred["0.5"].to_numpy(),
                                     "lo": pred["0.1"].to_numpy(), "hi": pred["0.9"].to_numpy()}))
        print(f"  {name} {info}: {len(pred)}개", flush=True)
    return pd.concat(out, ignore_index=True)


def timesfm_uni(frames, windows):
    import timesfm
    model = timesfm.TimesFM_2p5_200M_torch.from_pretrained("google/timesfm-2.5-200m-pytorch")
    model.compile(timesfm.ForecastConfig(max_context=512, max_horizon=128, normalize_inputs=True,
                                         use_continuous_quantile_head=True, force_flip_invariance=True,
                                         infer_is_positive=True, fix_quantile_crossing=True))
    ctx, _, keys = items(frames, windows, "ex_ante", False)
    inputs = [c.y.to_numpy(dtype=float) for c in ctx]
    point, quant = model.forecast(horizon=H, inputs=inputs)
    rows = []
    for k, item in enumerate(keys):
        T = item.split("|")[1]
        months = [(pd.Period(T, "M") + h).strftime("%Y-%m") for h in range(1, H + 1)]
        for i in ("ex_ante", "ex_post"):
            rows.append(pd.DataFrame({"key": item, "month": months, "model": "TimesFM 2.5", "info": i,
                                      "pred": point[k, :H], "lo": quant[k, :H, 1], "hi": quant[k, :H, 9]}))
    print(f"  TimesFM 2.5: {len(keys)}개 예측 시점", flush=True)
    return pd.concat(rows, ignore_index=True)


def finish(pred, frames):
    pred[["name", "origin"]] = pred.key.str.split("|", expand=True)
    pred["h"] = [(pd.Period(m, "M") - pd.Period(o, "M")).n for m, o in zip(pred.month, pred.origin)]
    act = pd.concat([d[["month", "y"]].assign(name=n) for n, d in frames.items()]).rename(columns={"y": "actual"})
    return pred.drop(columns="key").merge(act, on=["name", "month"], how="left")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--province", action="store_true")
    args = ap.parse_args()
    t0 = time.time()
    if args.province:
        from province_data import EVAL_P, VAL_P, load_frames
        frames, windows, out = load_frames(), (VAL_P, EVAL_P), OUTPUTS / "province" / "foundation.csv"
    else:
        df = pd.read_csv(PROCESSED / "national.csv")
        frames = {s: df.rename(columns={s: "y"}).query("month >= '2016-01'").reset_index(drop=True) for s in SERIES}
        windows, out = (EVAL, HOLD), OUTPUTS / "national" / "foundation.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    pred = pd.concat([chronos(frames, windows), timesfm_uni(frames, windows)], ignore_index=True)
    pred = finish(pred, frames)
    pred.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"저장: {out} ({len(pred)}행, {(time.time() - t0) / 60:.1f}분)")


if __name__ == "__main__":
    main()
