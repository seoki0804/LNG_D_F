"""논문용 종합 평가: 여러 오차 지표, 평균 순위·Friedman/Nemenyi, 예측구간, Ensemble ablation, 연도별 강건성,
계산 비용, 하이퍼파라미터, LightGBM 특성 기여도(TreeSHAP).

모든 값은 이미 저장한 예측(평가 구간 2023~2025, 표본 외 2026)과 검증 구간 예측(2020~2022)에서 계산한다.
  - 점예측 지표: MAE·RMSE(천 톤), MAPE·sMAPE(%), MASE(척도 = 2016~2022년 계절 naive 1년 차 MAE),
                 RelMAE(= MAE / Seasonal Naive MAE), 평균 순위(목표월×시계마다 절대오차 순위)
  - MAPE 95% 신뢰구간: 목표월 단위 이동 블록 부트스트랩(블록 3개월, 2,000회)
  - 평균 순위 검정: Friedman 검정과 Nemenyi 임계차(CD, α = 0.05). 블록 = (목표월, 시계)
  - 예측구간(80%): 검증 구간의 로그 비율 오차 log(실제/예측)로 시계마다 split conformal 구간을 만들고
                   평가 구간에서 적중률·평균 폭·구간 점수(Gneiting & Raftery, 2007)를 잰다.
                   파운데이션 모델은 자체 분위수(10%·90%) 구간도 함께 본다.
  - Ensemble ablation: 구성원을 하나씩 뺀 평균, 전 모델 평균, 중앙값
  - 연도별 강건성: 2023·2024·2025년 MAPE와 순위 일치도(Kendall W)

출력: outputs/national/{metrics,ranks,intervals,intervals_h,ablation,by_year,compute,hyperparams,shap}.csv, paper_metrics.md
실행: python python/paper_metrics.py   (val_predictions.py, foundation_mh.py --val 다음)
"""
import json

import numpy as np
import pandas as pd
from scipy import stats

from config import OUTPUTS, PROCESSED
from mh import EVAL, HORIZONS, mshift

D = OUTPUTS / "national"
SERIES = {"city": "도시가스용", "power": "발전용", "total": "합계"}
ENS_PARTS = ["회귀 √Y", "SARIMAX", "LightGBM", "Chronos-2 + 공변량"]
ENS, BENCH = "앙상블", "계절 naive"
FM = ["Chronos-2", "Chronos-2 + 공변량", "TimesFM 2.5"]
ALPHA = 0.2          # 80% 예측구간
RNG = np.random.default_rng(0)


# ---------------- 점예측 지표 ----------------
def mase_scale(df, s):
    """2016-01~2022-12(평가 직전까지)의 계절 naive 1년 차 평균 절대오차."""
    y = df.set_index("month")[s]
    y = y[(y.index >= "2016-01") & (y.index <= mshift(EVAL[0], -1))]
    return (y - y.shift(12)).abs().dropna().mean()


def block_boot_mape(g, reps=2000, block=3):
    """목표월 단위 이동 블록 부트스트랩으로 MAPE(전 시계 평균) 95% 구간."""
    m = g.groupby("month").ape.agg(["sum", "count"])
    s, c = m["sum"].to_numpy(), m["count"].to_numpy()
    n = len(m)
    starts = np.arange(n - block + 1)
    k = int(np.ceil(n / block))
    out = np.empty(reps)
    for r in range(reps):
        idx = (RNG.choice(starts, k)[:, None] + np.arange(block)).ravel()[:n]
        out[r] = s[idx].sum() / c[idx].sum()
    return np.percentile(out, [2.5, 97.5])


def point_metrics(p, df):
    rows = []
    for (s, i, w), g in p.groupby(["series", "info", "window"]):
        scale = mase_scale(df, s)
        g = g.assign(err=g.pred - g.actual, ae=lambda d: d.err.abs(), ape=lambda d: d.ae / d.actual * 100,
                     sape=lambda d: 2 * d.ae / (d.actual.abs() + d.pred.abs()) * 100)
        # 순위: (목표월, 시계)마다 절대오차 순위 (1 = 가장 정확)
        R = g.pivot_table(index=["month", "h"], columns="model", values="ae").dropna(axis=0)
        rk = R.rank(axis=1).mean()
        bench_mae = g[g.model == BENCH].ae.mean()
        for m, gm in g.groupby("model"):
            lo, hi = block_boot_mape(gm) if w == "eval" else (np.nan, np.nan)
            rows.append({"series": s, "info": i, "window": w, "model": m, "MAE": gm.ae.mean(),
                         "RMSE": np.sqrt((gm.err ** 2).mean()), "MAPE": gm.ape.mean(), "MAPE_lo": lo, "MAPE_hi": hi,
                         "sMAPE": gm.sape.mean(), "MASE": gm.ae.mean() / scale, "RelMAE": gm.ae.mean() / bench_mae,
                         "rank": rk.get(m, np.nan), "bias_pct": (gm.err / gm.actual).mean() * 100})
    return pd.DataFrame(rows)


def friedman_nemenyi(p):
    rows, tests = [], []
    for (s, i), g in p[p.window == "eval"].groupby(["series", "info"]):
        R = g.assign(ae=(g.pred - g.actual).abs()).pivot_table(index=["month", "h"], columns="model", values="ae").dropna()
        n, k = R.shape
        ranks = R.rank(axis=1)
        chi, pv = stats.friedmanchisquare(*[R[c].to_numpy() for c in R.columns])
        q = stats.studentized_range.ppf(0.95, k, 1e6) / np.sqrt(2)
        cd = q * np.sqrt(k * (k + 1) / (6 * n))
        tests.append({"series": s, "info": i, "n_blocks": n, "k": k, "friedman_chi2": chi, "friedman_p": pv, "CD": cd})
        for m, v in ranks.mean().items():
            rows.append({"series": s, "info": i, "model": m, "avg_rank": v})
    return pd.DataFrame(rows), pd.DataFrame(tests)


# ---------------- 예측구간 ----------------
def interval_score(lo, hi, y, a=ALPHA):
    return (hi - lo) + 2 / a * (lo - y) * (y < lo) + 2 / a * (y - hi) * (y > hi)


def conformal(val, ev):
    """검증 구간 로그 비율 오차의 분위수로 시계별 구간. 유한 표본 보정 분위수 수준."""
    v = val.assign(r=np.log(val.actual / val.pred))
    rows = []
    for (s, m, h), g in v.groupby(["series", "model", "h"]):
        r = np.sort(g.r.to_numpy())
        n = len(r)
        k_lo = max(int(np.floor((n + 1) * ALPHA / 2)), 1)
        k_hi = min(int(np.ceil((n + 1) * (1 - ALPHA / 2))), n)
        rows.append({"series": s, "model": m, "h": h, "q_lo": r[k_lo - 1], "q_hi": r[k_hi - 1], "n_cal": n})
    q = pd.DataFrame(rows)
    e = ev.merge(q, on=["series", "model", "h"], how="inner")
    return e.assign(lo=e.pred * np.exp(e.q_lo), hi=e.pred * np.exp(e.q_hi), method="conformal")


def interval_tables(ev_c, ev_n):
    both = pd.concat([ev_c, ev_n], ignore_index=True)
    both = both.assign(cover=(both.actual >= both.lo) & (both.actual <= both.hi),
                       width=(both.hi - both.lo) / both.actual * 100,
                       IS=interval_score(both.lo, both.hi, both.actual))
    keys = ["series", "model", "method"]
    tot = both.groupby(keys).apply(lambda g: pd.Series({
        "coverage": g.cover.mean() * 100, "width_pct": g.width.mean(), "IS_pct": g.IS.mean() / g.actual.mean() * 100}),
        include_groups=False).reset_index()
    byh = both.groupby(keys + ["h"]).agg(coverage=("cover", "mean"), width_pct=("width", "mean")).reset_index()
    byh["coverage"] *= 100
    return tot, byh


# ---------------- Ensemble ablation ----------------
def ablation(p):
    base = p[p.model != ENS]
    variants = {"Ensemble (4)": ENS_PARTS}
    for m in ENS_PARTS:
        variants[f"− {m}"] = [x for x in ENS_PARTS if x != m]
    variants["통계 (OLS+SARIMAX)"] = ["회귀 √Y", "SARIMAX"]
    variants["AI (LightGBM+Chronos-2)"] = ["LightGBM", "Chronos-2 + 공변량"]
    allm = [m for m in base.model.unique() if m != BENCH]
    variants["전 모델 평균 (11)"] = allm
    keys = ["series", "info", "window", "origin", "month", "h"]
    rows = []
    for name, parts in variants.items():
        for agg in (["mean", "median"] if name == "Ensemble (4)" else ["mean"]):
            g = (base[base.model.isin(parts)].groupby(keys).agg(pred=("pred", agg), actual=("actual", "first"),
                                                               k=("pred", "size")).reset_index())
            g = g[g.k == len(parts)]
            label = name if agg == "mean" else "Ensemble (4, 중앙값)"
            for (s, i, w), gg in g.groupby(["series", "info", "window"]):
                rows.append({"variant": label, "series": s, "info": i, "window": w,
                             "MAPE": ((gg.pred - gg.actual).abs() / gg.actual).mean() * 100})
    return pd.DataFrame(rows)


# ---------------- 연도별 강건성 ----------------
def by_year(p):
    ev = p[(p.window == "eval") & (p["info"] == "ex_ante")].assign(
        year=lambda d: d.month.str[:4], ape=lambda d: (d.pred - d.actual).abs() / d.actual * 100)
    t = ev.groupby(["series", "model", "year"]).ape.mean().reset_index(name="MAPE")
    W = []
    for s, g in t.groupby("series"):
        M = g.pivot(index="model", columns="year", values="MAPE").rank()     # 모델 × 연도 순위
        m, n = M.shape[1], M.shape[0]
        S = ((M.sum(axis=1) - m * (n + 1) / 2) ** 2).sum()
        W.append({"series": s, "kendall_W": 12 * S / (m ** 2 * (n ** 3 - n))})
    return t, pd.DataFrame(W)


# ---------------- 계산 비용·하이퍼파라미터 ----------------
PARAMS = {"Chronos-2": "1.2억", "Chronos-2 + 공변량": "1.2억", "TimesFM 2.5": "2억"}


def compute_table():
    t = pd.read_csv(D / "timing.csv")
    rows = [{"model": r.model, "sec_per_origin": r.sec_per_origin * r.seeds, "training": "예측 시점마다 학습",
             "params": ""} for r in t.itertuples()]
    f = D / "timing_fm.csv"
    if f.exists():
        fm = pd.read_csv(f).groupby("model").sec_per_origin.mean()
        rows += [{"model": m, "sec_per_origin": v, "training": "없음 (zero-shot)", "params": PARAMS.get(m, "")}
                 for m, v in fm.items()]
    return pd.DataFrame(rows)


def hyper_table():
    from run_national import grid
    tun = pd.read_csv(D / "tuning.csv")
    best = (tun.dropna(subset=["val_MAPE"]).assign(_k=lambda d: d.val_MAPE.round(8))
            .sort_values(["_k", "params"], kind="mergesort").groupby(["series", "model"]).first().reset_index())
    best["n_grid"] = [len(grid(s)[m][1]) for s, m in zip(best.series, best.model)]
    return best[["series", "model", "n_grid", "params", "val_MAPE"]]


# ---------------- LightGBM 특성 기여도 ----------------
def shap_lgbm():
    import models_mh as M
    from mh import EVAL as E, future_frame
    df = pd.read_csv(PROCESSED / "national.csv")
    best = hyper_table().set_index(["series", "model"])
    rows = []
    T = mshift(E[1], -1)                     # 마지막 평가 예측 시점(2025-11)
    for s in SERIES:
        p = json.loads(best.loc[(s, "LightGBM"), "params"])
        d = df.rename(columns={s: "y"})
        d = d[d.month >= "2016-01"].reset_index(drop=True)
        train = d[(d.month <= T) & d.y.notna()]
        X, Y, _ = M._direct_xy(train, future_frame(d, T, "ex_ante"))
        ok = np.isfinite(Y) & X.notna().all(axis=1).to_numpy()
        contrib = 0
        for seed in (0, 1, 2):
            mdl = M._lgb(seed=seed, **p)()
            mdl.fit(X[ok].to_numpy(), Y[ok])
            contrib = contrib + np.abs(mdl.booster_.predict(X[ok].to_numpy(), pred_contrib=True)[:, :-1]).mean(axis=0) / 3
        tot = contrib.sum()
        rows += [{"series": s, "feature": f, "mean_abs_shap": v, "share": v / tot * 100} for f, v in zip(X.columns, contrib)]
    return pd.DataFrame(rows)


def by_month(p):
    """달력월별 오차: MAPE와 평균 백분율 오차(편향, + = 과대예측). 사전·사후예측, 평가 구간과 2026년."""
    g = p.assign(cm=pd.to_datetime(p.month).dt.month, pe=(p.pred - p.actual) / p.actual * 100)
    out = g.groupby(["series", "model", "info", "window", "cm"]).agg(
        MAPE=("pe", lambda x: x.abs().mean()), bias=("pe", "mean"), n=("pe", "size")).reset_index()
    return out


def hold_summer(df):
    """2026년 6~9월 실제 수요·냉방도일을 직전 해들과 비교 (발전용 여름 과소예측 설명용)."""
    d = df.assign(y=df.month.str[:4].astype(int), cm=df.month.str[5:7].astype(int))
    d = d[d.cm.between(6, 9) & d.y.between(2022, 2026)]
    return d[["month", "y", "cm", "city", "power", "total", "cdd", "tmean"]]


def main():
    df = pd.read_csv(PROCESSED / "national.csv")
    p = pd.read_csv(D / "all_predictions.csv")
    by_month(p).to_csv(D / "error_month.csv", index=False, encoding="utf-8-sig")
    hold_summer(df).to_csv(D / "summer_2022_2026.csv", index=False, encoding="utf-8-sig")

    met = point_metrics(p, df)
    met.to_csv(D / "metrics.csv", index=False, encoding="utf-8-sig")
    rk, ft = friedman_nemenyi(p)
    rk.to_csv(D / "ranks.csv", index=False, encoding="utf-8-sig")
    ft.to_csv(D / "friedman.csv", index=False, encoding="utf-8-sig")

    # 검증 구간 예측(학습 모델 + 파운데이션 모델) → Ensemble 검증 예측 → conformal
    val = pd.read_csv(D / "val_predictions.csv")
    fv = pd.read_csv(D / "foundation_val.csv").rename(columns={"name": "series"})
    fv = fv[(fv.month >= "2020-01") & (fv.month <= "2022-12") & (fv["info"] == "ex_ante") & fv.actual.notna()]
    val = pd.concat([val, fv[val.columns.intersection(fv.columns)]], ignore_index=True)
    keys = ["series", "origin", "month", "h"]
    ens = (val[val.model.isin(ENS_PARTS)].groupby(keys).agg(pred=("pred", "mean"), actual=("actual", "first"),
                                                            k=("pred", "size")).reset_index())
    val = pd.concat([val, ens[ens.k == len(ENS_PARTS)].drop(columns="k").assign(model=ENS)], ignore_index=True)
    ev = p[(p.window == "eval") & (p["info"] == "ex_ante")]
    ev_c = conformal(val, ev)
    fm = pd.read_csv(D / "foundation.csv").rename(columns={"name": "series"})
    ev_n = fm[(fm["info"] == "ex_ante") & (fm.month >= EVAL[0]) & (fm.month <= EVAL[1]) & fm.actual.notna()].assign(
        method="native")
    tot, byh = interval_tables(ev_c, ev_n[["series", "model", "h", "month", "pred", "actual", "lo", "hi", "method"]])
    tot.to_csv(D / "intervals.csv", index=False, encoding="utf-8-sig")
    byh.to_csv(D / "intervals_h.csv", index=False, encoding="utf-8-sig")
    # 재현 점검: 다시 만든 검증 구간 MAPE vs 튜닝 기록
    vm = val.assign(ape=(val.pred - val.actual).abs() / val.actual * 100).groupby(["series", "model"]).ape.mean()
    hp = hyper_table().set_index(["series", "model"])
    repro = pd.DataFrame({"val_MAPE_now": vm, "val_MAPE_tuning": hp.val_MAPE}).dropna()
    repro.to_csv(D / "repro_check.csv", encoding="utf-8-sig")

    ab = ablation(p)
    ab.to_csv(D / "ablation.csv", index=False, encoding="utf-8-sig")
    yr, kw = by_year(p)
    yr.to_csv(D / "by_year.csv", index=False, encoding="utf-8-sig")
    kw.to_csv(D / "by_year_W.csv", index=False, encoding="utf-8-sig")
    cp = compute_table()
    cp.to_csv(D / "compute.csv", index=False, encoding="utf-8-sig")
    hyper_table().to_csv(D / "hyperparams.csv", index=False, encoding="utf-8-sig")
    sh = shap_lgbm()
    sh.to_csv(D / "shap.csv", index=False, encoding="utf-8-sig")

    # 요약 (markdown)
    L = ["# 논문용 종합 평가 (평가 목표월 2023~2025, 사전예측)", ""]
    for s, sn in SERIES.items():
        t = met[(met.series == s) & (met["info"] == "ex_ante") & (met.window == "eval")].sort_values("MASE")
        L += [f"## {sn}", "", "| 모델 | MAE | RMSE | MAPE [95% CI] | sMAPE | MASE | RelMAE | 평균 순위 |", "|---|---|---|---|---|---|---|---|"]
        L += [f"| {r.model} | {r.MAE:.0f} | {r.RMSE:.0f} | {r.MAPE:.2f} [{r.MAPE_lo:.2f}, {r.MAPE_hi:.2f}] | {r.sMAPE:.2f} | "
              f"{r.MASE:.3f} | {r.RelMAE:.3f} | {r.rank:.2f} |" for r in t.itertuples()]
        L.append("")
    L += ["## Friedman / Nemenyi", "", ft.round(4).to_markdown(index=False), "",
          "## 80% 예측구간 (평가 구간)", "", tot.round(2).to_markdown(index=False), "",
          "## Ensemble ablation (MAPE)", "",
          ab.pivot_table(index="variant", columns=["window", "info", "series"], values="MAPE").round(2).to_markdown(), "",
          "## 연도별 순위 일치도 (Kendall W)", "", kw.round(3).to_markdown(index=False), "",
          "## 계산 비용 (도시가스용, 예측 시점 1개당 초)", "", cp.round(3).to_markdown(index=False), "",
          "## 재현 점검 (검증 구간 MAPE: 지금 vs 튜닝 기록)", "", repro.round(3).to_markdown(), "",
          "## LightGBM 특성 기여도 (평균 |SHAP| 비중 %)", "",
          sh.pivot_table(index="feature", columns="series", values="share").round(1).to_markdown()]
    (D / "paper_metrics.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
