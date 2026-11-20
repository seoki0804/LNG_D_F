"""연구 과제 R8 (파운데이션 모델): Chronos-2·TimesFM 2.5를 학습 없이(zero-shot) 쓰면 학습한 모델을 이기는가.

실행 환경: 별도 가상환경 .venv-fm (Python 3.12, CPU torch, chronos-forecasting 2.3.2, timesfm 3.0.2)
    py -3.12 -m venv .venv-fm
    .venv-fm\\Scripts\\python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
    .venv-fm\\Scripts\\python -m pip install chronos-forecasting==2.3.2 "timesfm[torch]==3.0.2" pandas scipy
    .venv-fm\\Scripts\\python python\\r8_foundation.py
  가중치는 처음 실행할 때 Hugging Face에서 받는다 (Chronos-2 약 0.5GB, TimesFM 2.5 약 0.8GB).

방식 (본 실험과 같은 평가: 2023-01~2025-12 매달 1개월 앞, 사후·사전예측)
  - 문맥(context): 예측 달 직전까지의 수요 전체 (유럽 2008-01~, 한국 2016-01~). 학습·미세조정은 하지 않는다.
  - 단변량: 수요 이력만 넣는다.
  - 공변량: HDD·CDD·소비자요금·전월 도매가·산업생산을 과거와 예측 달 값으로 넣는다.
      사후예측 = 예측 달 실제값, 사전예측 = 평년 HDD·CDD와 직전 달 요금·산업생산 (rolling_eval.EX_ANTE).
    Chronos-2는 future_df로 넘긴 열을 '미래에 아는 공변량'으로 쓴다. TimesFM 2.5는 XReg(선형 회귀 + TimesFM 잔차)를 쓴다.
  - 점예측은 중앙값(Chronos-2 0.5 분위수, TimesFM 점예측).
  - DM 검정: 기준 회귀(√Y~HDD+가격), 그리고 그 나라 본 실험 최고 모델 대비 (APE, 사후예측).

출력: outputs/r8_foundation.md, outputs/r8_foundation.csv, outputs/r8_foundation_predictions.csv
다른 기간: --geos DE --start 2026-01 --end 2026-09 --tag de2026 → outputs/r8_foundation_de2026_predictions.csv
"""
import time
import warnings

warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import torch

from config import ALL_GEOS, EVAL_END, EVAL_START, GEO_NAMES, OUTPUTS
from dm_test import dm_test
from rolling_eval import EX_ANTE, eval_months, load_country, metrics

COVS = ["hdd", "cdd", "price_retail", "price_wholesale_lag1", "ip"]
MODES = ("ex_post", "ex_ante")
BENCH = "회귀 √Y~HDD+가격"
torch.manual_seed(0)
MONTHS = eval_months()   # 평가 달 (명령행 --start/--end로 바꿀 수 있다)


def history(df):
    """수요가 있는 첫 달부터의 연속 구간."""
    first = df.loc[df.y.notna(), "month"].min()
    return df[df.month >= first].reset_index(drop=True)


def future_row(row, mode):
    r = row.copy()
    if mode == "ex_ante":
        for c in COVS:
            if c in EX_ANTE:
                r[c] = row[EX_ANTE[c]]
    return r


# ---------------- Chronos-2 ----------------
def run_chronos(frames):
    from chronos import Chronos2Pipeline
    pipe = Chronos2Pipeline.from_pretrained("amazon/chronos-2", device_map="cpu")
    out = []
    for covariates in (False, True):
        for mode in MODES:
            if not covariates and mode == "ex_ante":
                continue   # 단변량은 사후·사전이 같다
            ctx, fut = [], []
            for g, df in frames.items():
                for t in MONTHS:
                    item = f"{g}|{t}"
                    h = df[df.month < t].copy()
                    h["item_id"], h["timestamp"] = item, pd.to_datetime(h.month + "-01")
                    cols = ["item_id", "timestamp", "y"] + (COVS if covariates else [])
                    ctx.append(h[cols])
                    if covariates:
                        f = future_row(df[df.month == t].iloc[0], mode)
                        fut.append(pd.DataFrame([{"item_id": item, "timestamp": pd.Timestamp(t + "-01"),
                                                  **{c: f[c] for c in COVS}}]))
            ctx = pd.concat(ctx, ignore_index=True)
            fut = pd.concat(fut, ignore_index=True) if covariates else None
            pred = pipe.predict_df(ctx, future_df=fut, id_column="item_id", timestamp_column="timestamp",
                                   target="y", prediction_length=1, quantile_levels=[0.1, 0.5, 0.9], freq="MS")
            name = "Chronos-2 + 공변량" if covariates else "Chronos-2 단변량"
            for m in (MODES if not covariates else (mode,)):
                out.append(pd.DataFrame({"geo": pred.item_id.str[:2], "month": pred.item_id.str[3:],
                                         "mode": m, "model": name, "pred": pred["0.5"].to_numpy(),
                                         "lo": pred["0.1"].to_numpy(), "hi": pred["0.9"].to_numpy()}))
            print(f"  {name} {mode}: {len(pred)}개", flush=True)
    return pd.concat(out, ignore_index=True)


def run_chronos_realtime(frames):
    """실시간: 공표된 수요(t-k까지)만 문맥으로 쓰고 k단계 앞을 예측해 마지막 단계(t)를 취한다.
    공변량은 t-1월 말에 아는 값만: 지난달까지 실제 HDD·CDD·요금·전월 도매가, 예측 달은 평년 HDD·CDD와 직전 달 요금.
    산업생산은 공표가 늦어(t-3) 뺀다."""
    from chronos import Chronos2Pipeline
    from rolling_eval import DEMAND_LAG
    pipe = Chronos2Pipeline.from_pretrained("amazon/chronos-2", device_map="cpu")
    covs = ["hdd", "cdd", "price_retail", "price_wholesale_lag1"]
    out = []
    for covariates in (False, True):
        for k in sorted({DEMAND_LAG[g] for g in frames}):
            ctx, fut = [], []
            for g, df in frames.items():
                if DEMAND_LAG[g] != k:
                    continue
                for t in MONTHS:
                    item = f"{g}|{t}"
                    last = (pd.Period(t, "M") - k).strftime("%Y-%m")
                    h = df[df.month <= last].copy()
                    h["item_id"], h["timestamp"] = item, pd.to_datetime(h.month + "-01")
                    ctx.append(h[["item_id", "timestamp", "y"] + (covs if covariates else [])])
                    if covariates:
                        for j in range(k - 1, -1, -1):
                            mth = (pd.Period(t, "M") - j).strftime("%Y-%m")
                            r = df[df.month == mth].iloc[0]
                            vals = ({c: r[c] for c in covs} if j > 0 else
                                    {"hdd": r["hdd_norm"], "cdd": r["cdd_norm"], "price_retail": r["price_retail_prev"],
                                     "price_wholesale_lag1": r["price_wholesale_lag1"]})
                            fut.append({"item_id": item, "timestamp": pd.Timestamp(mth + "-01"), **vals})
            if not ctx:
                continue
            pred = pipe.predict_df(pd.concat(ctx, ignore_index=True),
                                   future_df=pd.DataFrame(fut) if covariates else None, id_column="item_id",
                                   timestamp_column="timestamp", target="y", prediction_length=k,
                                   quantile_levels=[0.1, 0.5, 0.9], freq="MS")
            pred = pred.sort_values("timestamp").groupby("item_id").tail(1)
            name = "Chronos-2 + 공변량" if covariates else "Chronos-2 단변량"
            out.append(pd.DataFrame({"geo": pred.item_id.str[:2].to_numpy(), "month": pred.item_id.str[3:].to_numpy(),
                                     "mode": "ex_ante", "model": name, "pred": pred["0.5"].to_numpy(),
                                     "lo": pred["0.1"].to_numpy(), "hi": pred["0.9"].to_numpy()}))
            print(f"  {name} 실시간 k={k}: {len(pred)}개", flush=True)
    return pd.concat(out, ignore_index=True)


# ---------------- TimesFM 2.5 ----------------
def run_timesfm(frames):
    import timesfm
    model = timesfm.TimesFM_2p5_200M_torch.from_pretrained("google/timesfm-2.5-200m-pytorch")
    model.compile(timesfm.ForecastConfig(max_context=512, max_horizon=128, normalize_inputs=True,
                                         use_continuous_quantile_head=True, force_flip_invariance=True,
                                         infer_is_positive=True, fix_quantile_crossing=True,
                                         return_backcast=True))
    keys, inputs = [], []
    for g, df in frames.items():
        for t in MONTHS:
            keys.append((g, t))
            inputs.append(df[df.month < t].y.to_numpy(dtype=float))
    point, quant = model.forecast(horizon=1, inputs=inputs)
    # return_backcast=True(XReg에 필요)면 출력 = [문맥 구간 backcast …, 예측] → 예측은 마지막 칸.
    # 분위수 축: 0 = 평균, 1~9 = 0.1~0.9 분위수.
    out = [pd.DataFrame({"geo": [k[0] for k in keys], "month": [k[1] for k in keys], "mode": m,
                         "model": "TimesFM 2.5 단변량", "pred": point[:, -1], "lo": quant[:, -1, 1],
                         "hi": quant[:, -1, 9]}) for m in MODES]
    print(f"  TimesFM 단변량: {len(keys)}개", flush=True)
    try:
        out += timesfm_xreg(model, frames, inputs, keys)
    except Exception as e:   # XReg 의존성(timesfm[xreg]) 문제여도 단변량 결과는 남긴다
        print(f"  TimesFM + 공변량 실패: {type(e).__name__}: {e}")
    return pd.concat(out, ignore_index=True)


def timesfm_xreg(model, frames, inputs, keys):
    out = []
    for mode in MODES:
        dyn = {c: [] for c in COVS}
        for g, df in frames.items():
            for t in MONTHS:
                h = df[df.month < t]
                f = future_row(df[df.month == t].iloc[0], mode)
                for c in COVS:
                    dyn[c].append(list(h[c].to_numpy(dtype=float)) + [float(f[c])])
        pt, _ = model.forecast_with_covariates(inputs=inputs, dynamic_numerical_covariates=dyn,
                                               xreg_mode="xreg + timesfm", ridge=1.0, force_on_cpu=True)
        out.append(pd.DataFrame({"geo": [k[0] for k in keys], "month": [k[1] for k in keys], "mode": mode,
                                 "model": "TimesFM 2.5 + 공변량(XReg)",
                                 "pred": np.array([p[0] for p in pt]), "lo": np.nan, "hi": np.nan}))
        print(f"  TimesFM + 공변량 {mode}: {len(keys)}개", flush=True)
    return out


def main():
    global MONTHS
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--geos", nargs="+", default=ALL_GEOS)
    ap.add_argument("--start", default=EVAL_START)
    ap.add_argument("--end", default=EVAL_END)
    ap.add_argument("--tag", default="", help="주면 예측값만 outputs/r8_foundation_<tag>_predictions.csv로 저장")
    ap.add_argument("--realtime", action="store_true", help="공표 지연 반영 실시간 예측 (Chronos-2만)")
    args = ap.parse_args()
    MONTHS = eval_months(args.start, args.end)
    t0 = time.time()
    frames = {g: history(load_country(g)) for g in args.geos}
    for g, df in frames.items():   # 공변량 결측(문맥 앞부분 전월 도매가 등)은 가까운 값으로 채운다
        df[COVS] = df[COVS].bfill().ffill()
    parts = []
    if args.realtime:
        print("Chronos-2 실시간", flush=True)
        parts.append(run_chronos_realtime(frames))
    else:
        print("Chronos-2", flush=True)
        parts.append(run_chronos(frames))
    print(f"TimesFM 2.5 ({time.time() - t0:.0f}s)", flush=True)
    try:
        if not args.realtime:
            parts.append(run_timesfm(frames))
    except Exception as e:   # 설치·가중치 문제로 실패해도 Chronos 결과는 남긴다
        print(f"  TimesFM 실패: {type(e).__name__}: {e}")
    pred = pd.concat(parts, ignore_index=True)
    act = pd.concat([d[["month", "y"]].assign(geo=g) for g, d in frames.items()]).rename(columns={"y": "actual"})
    pred = pred.merge(act, on=["geo", "month"], how="left")
    if args.tag:   # 다른 평가 기간(예: 독일 2026 표본 외 검증) — 비교표는 그 스크립트가 만든다
        pred.to_csv(OUTPUTS / f"r8_foundation_{args.tag}_predictions.csv", index=False, encoding="utf-8-sig")
        print(f"저장: outputs/r8_foundation_{args.tag}_predictions.csv ({time.time() - t0:.0f}s)")
        return
    pred.to_csv(OUTPUTS / "r8_foundation_predictions.csv", index=False, encoding="utf-8-sig")

    exp = pd.read_csv(OUTPUTS / "experiment" / "predictions.csv")
    summ = pd.read_csv(OUTPUTS / "experiment" / "summary.csv")
    rows = []
    fm_models = list(dict.fromkeys(pred.model))
    for g in ALL_GEOS:
        df = load_country(g)
        best = summ[(summ.geo == g) & (summ["mode"] == "ex_post")].sort_values("MAPE").iloc[0].model
        for m in fm_models:
            r = {"geo": g, "model": m, "best_local": best}
            for mode in MODES:
                p = pred[(pred.geo == g) & (pred.model == m) & (pred["mode"] == mode)].sort_values("month")
                r[f"MAPE_{mode}"] = metrics(p, df)["MAPE"]
                if mode == "ex_post":
                    for ref, key in ((BENCH, "bench"), (best, "best")):
                        q = exp[(exp.geo == g) & (exp.model == ref) & (exp["mode"] == mode)].sort_values("month")
                        r[f"DM_{key}"], r[f"p_{key}"] = dm_test(p.actual.values, p.pred.values, q.pred.values,
                                                               kind="ape")
                    cov = p.dropna(subset=["lo", "hi"])
                    r["cover80"] = float(((cov.actual >= cov.lo) & (cov.actual <= cov.hi)).mean() * 100) \
                        if len(cov) else np.nan
            rows.append(r)
    tab = pd.DataFrame(rows)
    tab.to_csv(OUTPUTS / "r8_foundation.csv", index=False, encoding="utf-8-sig")

    ref = summ[summ["mode"] == "ex_post"]
    L = ["# R8 파운데이션 모델 (zero-shot)", "",
         f"2023~2025 롤링 1개월 앞 MAPE(%), 학습 없이 예측. CPU 실행 {(time.time() - t0) / 60:.1f}분. "
         "▲/▼ = DM 검정(APE, 사후) p<0.05로 더 정확/덜 정확. (기준 회귀 대비 / 국가 최고 모델 대비)", "",
         "## 사후예측", "", "| 모델 | " + " | ".join(GEO_NAMES[g] for g in ALL_GEOS) + " | 평균 |",
         "| --- |" + " --- |" * (len(ALL_GEOS) + 1)]

    def mark(r, key):
        return ("▲" if r[f"DM_{key}"] < 0 else "▼") if r[f"p_{key}"] < 0.05 else "·"
    for m in fm_models:
        sub = tab[tab.model == m]
        cells = []
        for g in ALL_GEOS:
            r = sub[sub.geo == g].iloc[0]
            cells.append(f"{r.MAPE_ex_post:.1f} ({mark(r, 'bench')}/{mark(r, 'best')})")
        L.append(f"| {m} | " + " | ".join(cells) + f" | {sub.MAPE_ex_post.mean():.1f} |")
    L.append("| 기준 회귀 (본 실험) | " + " | ".join(
        f"{ref[(ref.geo == g) & (ref.model == BENCH)].MAPE.iloc[0]:.1f}" for g in ALL_GEOS)
        + f" | {ref[ref.model == BENCH].MAPE.mean():.1f} |")
    L.append("| 국가 최고 모델 (본 실험) | " + " | ".join(
        f"{ref[ref.geo == g].MAPE.min():.1f} ({ref[ref.geo == g].sort_values('MAPE').model.iloc[0]})"
        for g in ALL_GEOS) + " | |")
    L += ["", "## 사전예측", "", "| 모델 | " + " | ".join(GEO_NAMES[g] for g in ALL_GEOS) + " | 평균 |",
          "| --- |" + " --- |" * (len(ALL_GEOS) + 1)]
    for m in fm_models:
        sub = tab[tab.model == m].set_index("geo")
        L.append(f"| {m} | " + " | ".join(f"{sub.loc[g, 'MAPE_ex_ante']:.1f}" for g in ALL_GEOS)
                 + f" | {sub.MAPE_ex_ante.mean():.1f} |")
    cov = tab.dropna(subset=["cover80"])
    if len(cov):
        L += ["", "80% 구간(0.1~0.9 분위수)의 실제 포함률(%): " + "; ".join(
            f"{m} " + ", ".join(f"{GEO_NAMES[r.geo]} {r.cover80:.0f}" for r in cov[cov.model == m].itertuples())
            for m in dict.fromkeys(cov.model))]
    (OUTPUTS / "r8_foundation.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))
    print(f"저장: outputs/r8_foundation.md ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
