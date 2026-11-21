"""논문·발표용 그림 (영문 라벨). 모든 그림은 같은 스타일·색 규칙을 따른다.

색 규칙 (모델군마다 고정, 색각 이상 검증 통과 팔레트 — dataviz 기준 팔레트 1~5번 슬롯):
  회귀(위기 변수 포함) = 파랑, SARIMAX = 주황, ML(GBM·LightGBM 등) = 청록, Chronos-2 = 노랑, 앙상블 = 분홍,
  기준 회귀 = 회색(비교 기준), 실제값 = 검정. 크기(MAPE 등)는 한 가지 색(파랑) 명도 단계.
출력: outputs/figures/paper/figN_*.png (300 dpi) + .pdf (벡터)

실행: python python/figures.py           (전부)
      python python/figures.py fig4 fig7  (일부)
"""
import json
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import Patch

from config import ALL_GEOS, OUTPUTS, PROCESSED

FIG = OUTPUTS / "figures" / "paper"
FIG.mkdir(parents=True, exist_ok=True)

# ---------------- 스타일 ----------------
INK, INK2, MUTED, GRID, BASE = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
C = {"reg": "#2a78d6", "sarimax": "#eb6834", "ml": "#1baf7a", "chronos": "#eda100", "ens": "#e87ba4",
     "bench": "#898781", "actual": INK}
BLUES = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
SEQ = LinearSegmentedColormap.from_list("seq_blue", BLUES)
COUNTRY = {"DE": "Germany", "IT": "Italy", "FR": "France", "ES": "Spain", "NL": "Netherlands", "KR": "Korea"}
UNIT = {g: "PJ" for g in ALL_GEOS} | {"KR": "kt LNG"}
NAME = {
    "회귀 √Y~HDD+가격": "Benchmark regression", "단순회귀 Y~HDD": "Simple regression (Y ~ HDD)",
    "회귀 + 위기 변수": "Regression + crisis terms", "SARIMAX+HDD·가격": "SARIMAX (tuned)",
    "Holt-Winters": "Holt–Winters (tuned)", "계절 naive": "Seasonal naïve", "Ridge": "Ridge", "Lasso": "Lasso",
    "Random Forest": "Random forest", "Gradient Boosting": "Gradient boosting", "LightGBM": "LightGBM",
    "SVR": "SVR", "MLP (16-8)": "MLP (16-8)", "Ridge + 위기 변수": "Ridge + crisis terms",
    "GBM + 위기 변수": "GBM + crisis terms", "하이브리드 (회귀+GBM 잔차)": "Hybrid (regression + GBM residual)",
    "통합 LightGBM (6개국)": "Global LightGBM (pooled)", "Chronos-2 단변량": "Chronos-2 (univariate)",
    "Chronos-2 + 공변량": "Chronos-2 (covariates)", "TimesFM 2.5 단변량": "TimesFM 2.5 (univariate)",
    "TimesFM 2.5 + 공변량(XReg)": "TimesFM 2.5 (XReg covariates)",
    "앙상블: 회귀(위기)+ML+Chronos": "Ensemble: regression + ML + Chronos", "앙상블 (회귀·ML·Chronos)":
        "Ensemble: regression + ML + Chronos", "앙상블: 회귀(위기)+ML": "Ensemble: regression + ML",
    "앙상블: ML 평균": "Ensemble: ML average", "앙상블: 검증 상위 3": "Ensemble: validation top-3",
}
FAMILY = [  # (그룹 이름, 모델 순서)
    ("Statistical", ["회귀 √Y~HDD+가격", "단순회귀 Y~HDD", "회귀 + 위기 변수", "SARIMAX+HDD·가격", "Holt-Winters",
                     "계절 naive"]),
    ("Machine learning", ["Ridge", "Ridge + 위기 변수", "Lasso", "Random Forest", "Gradient Boosting",
                          "GBM + 위기 변수", "LightGBM", "통합 LightGBM (6개국)", "SVR", "MLP (16-8)",
                          "하이브리드 (회귀+GBM 잔차)"]),
    ("Foundation (zero-shot)", ["Chronos-2 단변량", "Chronos-2 + 공변량", "TimesFM 2.5 단변량",
                                "TimesFM 2.5 + 공변량(XReg)"]),
    ("Ensemble", ["앙상블: 회귀(위기)+ML+Chronos", "앙상블: 회귀(위기)+ML", "앙상블: ML 평균", "앙상블: 검증 상위 3"]),
]

plt.rcParams.update({
    "font.family": ["Arial", "DejaVu Sans"], "font.size": 8, "axes.titlesize": 9, "axes.labelsize": 8,
    "xtick.labelsize": 7.5, "ytick.labelsize": 7.5, "legend.fontsize": 7.5, "axes.edgecolor": BASE,
    "axes.linewidth": 0.6, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "xtick.major.width": 0.6, "ytick.major.width": 0.6, "xtick.major.size": 2.5, "ytick.major.size": 2.5,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.5, "axes.axisbelow": True,
    "axes.spines.top": False, "axes.spines.right": False, "legend.frameon": False, "lines.linewidth": 1.2,
    "savefig.dpi": 300, "figure.dpi": 150, "axes.titleweight": "bold", "axes.titlelocation": "left",
    "axes.titlecolor": INK, "text.color": INK, "pdf.fonttype": 42,
})
W1, W2 = 3.5, 7.2   # 단단·양단 폭 (inch)


def save(fig, name):
    fig.savefig(FIG / f"{name}.png", bbox_inches="tight", facecolor="white")
    fig.savefig(FIG / f"{name}.pdf", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  {name}")


def load(g):
    d = pd.read_csv(PROCESSED / f"{g}.csv", dtype={"month": str})
    d["date"] = pd.to_datetime(d.month + "-01")
    return d


def shade(ax, start, end, color, label=None):
    ax.axvspan(pd.Timestamp(start), pd.Timestamp(end) + pd.offsets.MonthEnd(0), color=color, lw=0, zorder=0,
               label=label)


# ---------------- Fig 1: 자료 개요 ----------------
def fig1():
    fig, axes = plt.subplots(2, 3, figsize=(W2, 3.9), sharex=True)
    for ax, g in zip(axes.ravel(), ALL_GEOS):
        d = load(g)
        d = d[d.y.notna()].copy()
        d.loc[d.y <= 0, "y"] = np.nan   # 스페인 2026-08 = 0 (Eurostat 자료 오류) — 그리지 않는다
        shade(ax, "2023-01", "2025-12", "#eceae4")
        shade(ax, "2026-01", "2026-09", "#d9d7cf")
        ax.axvline(pd.Timestamp("2022-03-01"), color=MUTED, lw=0.6)
        ax.plot(d.date, d.y, color=C["reg"], lw=0.8)
        ax.plot(d.date, d.y.rolling(12, center=True).mean(), color=INK, lw=1.1)
        ax.set_title(COUNTRY[g], loc="left", fontsize=8.5)
        ax.set_ylabel(UNIT[g])
        ax.set_ylim(bottom=0)
        ax.xaxis.set_major_locator(mdates.YearLocator(4))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
        ax.grid(axis="x", visible=False)
    axes[0, 0].text(pd.Timestamp("2022-03-01"), 12, "Mar 2022 ", rotation=90, ha="right", va="bottom",
                    fontsize=6.3, color=INK2)
    handles = [plt.Line2D([], [], color=C["reg"], lw=0.8, label="Monthly demand"),
               plt.Line2D([], [], color=INK, lw=1.1, label="12-month centred mean"),
               Patch(color="#eceae4", label="Test period 2023–2025"),
               Patch(color="#d9d7cf", label="Hold-out 2026")]
    fig.legend(handles=handles, loc="lower center", ncol=4, bbox_to_anchor=(0.5, -0.03))
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    save(fig, "fig1_demand")


# ---------------- Fig 2: 평가 설계 ----------------
def fig2():
    rows = [("Main evaluation", [("2015-01", "2019-12", "train"), ("2020-01", "2022-12", "val"),
                                 ("2023-01", "2025-12", "test")]),
            ("Long evaluation (EU)", [("2009-01", "2014-12", "train"), ("2015-01", "2017-12", "val"),
                                      ("2018-01", "2025-12", "test")]),
            ("Long evaluation (Korea)", [("2016-01", "2018-12", "train"), ("2019-01", "2019-12", "val"),
                                         ("2020-01", "2025-12", "test")]),
            ("Hold-out 2026", [("2015-01", "2025-12", "train"), ("2026-01", "2026-09", "hold")])]
    col = {"train": "#e1e0d9", "val": "#86b6ef", "test": "#256abf", "hold": "#0d366b"}
    lab = {"train": "Training (expanding window)", "val": "Validation (hyper-parameter selection)",
           "test": "Test (rolling one-step-ahead)", "hold": "Hold-out (no re-selection)"}
    fig, ax = plt.subplots(figsize=(W2, 2.0))
    for i, (name, segs) in enumerate(rows):
        for a, b, k in segs:
            x0 = mdates.date2num(pd.Timestamp(a))
            x1 = mdates.date2num(pd.Timestamp(b) + pd.offsets.MonthEnd(0))
            ax.barh(i, x1 - x0, left=x0, height=0.56, color=col[k], edgecolor="white", linewidth=1.5)
            if k == "hold":
                ax.text(x1 + 40, i, "2026 (Jan–Sep)", ha="left", va="center", fontsize=6.8, color=INK)
            if k != "train" and (x1 - x0) > 300:
                ax.text((x0 + x1) / 2, i, f"{a[:4]}–{b[:4]}" if a[:4] != b[:4] else a[:4], ha="center",
                        va="center", fontsize=6.8, color="white" if k in ("test", "hold") else INK)
    ax.set_yticks(range(len(rows)), [r[0] for r in rows])
    ax.invert_yaxis()
    ax.xaxis_date()
    ax.xaxis.set_major_locator(mdates.YearLocator(2))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.grid(axis="y", visible=False)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.legend(handles=[Patch(color=col[k], label=lab[k]) for k in col], loc="upper center", ncol=2,
              bbox_to_anchor=(0.45, -0.18))
    save(fig, "fig2_design")


# ---------------- Fig 3: 국가별 난방 민감도 ----------------
def fig3():
    t = pd.read_csv(OUTPUTS / "r5_country_regression.csv").set_index("geo").loc[ALL_GEOS]
    t = t.sort_values("hdd10_pre", ascending=True)
    fig, ax = plt.subplots(figsize=(W1, 2.6))
    y = np.arange(len(t))
    for off, pre_post, color, lab in ((0.14, "pre", C["bench"], "Before Mar 2022"),
                                      (-0.14, "post", C["reg"], "After Mar 2022")):
        v = t[f"hdd10_{pre_post}"]
        ax.errorbar(v, y + off, xerr=[v - t[f"hdd10_{pre_post}_lo"], t[f"hdd10_{pre_post}_hi"] - v], fmt="o",
                    ms=4.5, color=color, ecolor=color, elinewidth=1, capsize=0, label=lab,
                    markeredgecolor="white", markeredgewidth=0.6)
    for i, (g, r) in enumerate(t.iterrows()):
        if r.p_hdd_change < 0.05:
            ax.text(r.hdd10_post_hi + 0.08, i - 0.14, f"Δ p<0.001" if r.p_hdd_change < 0.001 else
                    f"Δ p={r.p_hdd_change:.2f}", va="center", fontsize=6.5, color=INK2)
    ax.set_yticks(y, [COUNTRY[g] for g in t.index])
    ax.set_xlabel("Demand increase per +10 HDD (%)")
    ax.set_xlim(0, None)
    ax.grid(axis="y", visible=False)
    ax.legend(handles=[plt.Line2D([], [], marker="o", ls="", color=C["bench"], ms=4.5, label="Before Mar 2022"),
                       plt.Line2D([], [], marker="o", ls="", color=C["reg"], ms=4.5, label="After Mar 2022")],
              loc="lower right")
    ax.text(0.0, -0.22, "Points: log-linear regression coefficient; bars: 95% CI (Newey–West).",
            transform=ax.transAxes, fontsize=6.3, color=INK2)
    save(fig, "fig3_hdd_sensitivity")


# ---------------- Fig 4: 정확도 히트맵 + MCS ----------------
def heat(ax, mat, mcs=None, vmin=3, vmax=14, show_y=True, title="", best_cols=None, fs=6.3):
    """mcs: 점으로 표시할 칸(bool). best_cols: 열마다 최저값을 굵게 표시할 열 번호."""
    im = ax.imshow(mat.values, cmap=SEQ, vmin=vmin, vmax=vmax, aspect="auto")
    for i in range(mat.shape[0]):
        for j in range(mat.shape[1]):
            v = mat.values[i, j]
            if np.isnan(v):
                continue
            dark = (v - vmin) / (vmax - vmin) > 0.55
            best = best_cols is not None and j in best_cols and np.isclose(v, np.nanmin(mat.values[:, j]))
            ax.text(j, i, f"{v:.1f}", ha="center", va="center", fontsize=fs + (0.6 if best else 0),
                    color="white" if dark else INK, fontweight="bold" if best else "normal")
            if mcs is not None and bool(mcs.values[i, j]):
                ax.plot(j + 0.38, i, marker="o", ms=2.6, color="white" if dark else INK, mew=0)
    ax.set_xticks(range(mat.shape[1]), mat.columns, rotation=0)
    ax.set_yticks(range(mat.shape[0]), mat.index if show_y else [""] * mat.shape[0])
    ax.tick_params(length=0)
    ax.grid(False)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_title(title, fontsize=8.5)
    return im


def fig4():
    m = pd.read_csv(OUTPUTS / "r4_mcs.csv")
    order = [x for _, ms in FAMILY for x in ms if x in set(m.model)]
    cols = ALL_GEOS + ["ALL"]
    fig, axes = plt.subplots(1, 2, figsize=(W2, 5.4), gridspec_kw={"wspace": 0.04})
    for ax, mode, title in zip(axes, ("ex_post", "ex_ante"), ("(a) Ex-post (observed weather)",
                                                             "(b) Ex-ante (climatological HDD)")):
        s = m[m["mode"] == mode]
        mat = s.pivot(index="model", columns="geo", values="MAPE").reindex(index=order, columns=cols)
        inm = s.pivot(index="model", columns="geo", values="in_mcs").reindex(index=order, columns=cols)
        inm.loc[:, ALL_GEOS] = False   # 나라별 MCS는 대부분 포함이라 표시하지 않음 (부록 표) — 6개국 통합 열만
        mat.columns = [c if c != "ALL" else "Mean" for c in cols]
        mat.index = [NAME[x] for x in order]
        im = heat(ax, mat, inm.fillna(False).astype(bool), show_y=ax is axes[0], title=title,
                  best_cols=set(range(len(cols))))
        ax.axvline(len(ALL_GEOS) - 0.5, color="white", lw=3)
        k = 0
        for fam, ms in FAMILY:
            n = sum(1 for x in ms if x in order)
            if k > 0:
                ax.axhline(k - 0.5, color="white", lw=3)
            if ax is axes[0]:
                ax.text(-0.02, (k + k + n - 1) / 2, "", transform=ax.get_yaxis_transform())
            k += n
        ax.xaxis.tick_top()
        ax.tick_params(axis="x", labelsize=6.8)
    cb = fig.colorbar(im, ax=axes, orientation="horizontal", fraction=0.03, pad=0.02, aspect=50)
    cb.set_label("MAPE (%), rolling one-month-ahead, 2023–2025 (36 forecasts per country)", fontsize=7)
    cb.outline.set_visible(False)
    fig.text(0.5, -0.04, "Bold: lowest MAPE in the column. Dot (Mean column): model is in the 90% model confidence "
             "set (Hansen et al., 2011)\nbased on the six-country average loss. DE Germany, IT Italy, FR France, "
             "ES Spain, NL Netherlands, KR Korea.", ha="center", fontsize=6.6, color=INK2)
    save(fig, "fig4_accuracy_heatmap")


# ---------------- Fig 7: 예측구간 보정 ----------------
# 라벨 위치 (데이터 좌표, 정렬) — 겹치지 않도록 빈 곳에 두고 가는 선으로 잇는다
OFF7 = {(0.8, "Regression PI"): (33.0, 98.0, "left"), (0.8, "Conformal (regression)"): (31.0, 66.0, "left"),
        (0.8, "Conformal (LightGBM)"): (23.5, 99.5, "center"), (0.8, "Chronos-2 quantiles"): (14.0, 91.0, "left"),
        (0.8, "Quantile GBM"): (25.0, 56.0, "left"), (0.95, "Conformal (LightGBM)"): (36.0, 88.5, "left"),
        (0.95, "Regression PI"): (75.0, 92.0, "left"), (0.95, "Conformal (regression)"): (80.0, 99.0, "left"),
        (0.95, "Quantile GBM"): (115.0, 81.0, "left")}


def fig7():
    t = pd.read_csv(OUTPUTS / "r9_intervals.csv")
    lab = {"회귀 PI (위기 변수)": "Regression PI", "분위수 GBM": "Quantile GBM",
           "Conformal (회귀 위기 변수)": "Conformal (regression)", "Conformal (LightGBM)": "Conformal (LightGBM)",
           "Chronos-2 + 공변량 분위수": "Chronos-2 quantiles"}
    sty = {"Regression PI": (C["reg"], "o"), "Conformal (regression)": (C["reg"], "s"),
           "Quantile GBM": (C["ml"], "^"), "Conformal (LightGBM)": (C["ml"], "D"),
           "Chronos-2 quantiles": (C["chronos"], "P")}
    fig, axes = plt.subplots(1, 2, figsize=(W2, 2.7), sharey=False)
    for ax, lv in zip(axes, (0.80, 0.95)):
        s = t[np.isclose(t.level, lv)]
        ax.axhline(lv * 100, color=INK2, lw=0.8)
        ax.text(1.0, lv * 100, f" nominal {lv:.0%}", transform=ax.get_yaxis_transform(), va="bottom",
                ha="right", fontsize=6.5, color=INK2)
        for meth, q in s.groupby("method"):
            name = lab[meth]
            color, mk = sty[name]
            ax.scatter(q.width, q.cover, s=10, color=color, marker=mk, alpha=0.35, lw=0)
            ax.scatter(q.width.mean(), q.cover.mean(), s=48, color=color, marker=mk, edgecolor="white", lw=0.8,
                       zorder=3, label=name)
            tx, ty, ha = OFF7[(lv, name)]
            ax.annotate(name, (q.width.mean(), q.cover.mean()), xytext=(tx, ty), textcoords="data",
                        fontsize=6.5, color=INK, ha=ha, va="center",
                        arrowprops={"arrowstyle": "-", "color": MUTED, "lw": 0.5, "shrinkA": 1, "shrinkB": 4})
        ax.set_xlabel("Mean interval width (% of actual)")
        ax.set_ylabel("Empirical coverage (%)")
        ax.set_title(f"({'a' if lv == 0.8 else 'b'}) {lv:.0%} intervals", fontsize=8.5)
        ax.set_ylim(25 if lv == 0.8 else 60, 102)
        if lv == 0.95:
            ax.set_xlim(30, 175)
    fig.text(0.5, -0.04, "Large markers: six-country mean; small markers: individual countries. Rolling "
             "one-month-ahead, 2023–2025.", ha="center", fontsize=6.8, color=INK2)
    fig.tight_layout()
    save(fig, "fig7_interval_calibration")


# ---------------- 부록 A1: 단순회귀 진단 ----------------
def figA1():
    d = load("DE")
    d = d[(d.month >= "2008-01") & (d.month <= "2025-12")].reset_index(drop=True)
    X = sm.add_constant(d.hdd)
    fits = {"Y": sm.OLS(d.gas_pj, X).fit(), "√Y": sm.OLS(np.sqrt(d.gas_pj), X).fit()}
    fig, axes = plt.subplots(2, 3, figsize=(W2, 4.0))
    for row, (nm, f) in enumerate(fits.items()):
        e = f.resid / np.sqrt(f.scale)
        a = axes[row]
        a[0].scatter(f.fittedvalues, e, s=5, color=C["reg"], lw=0)
        a[0].axhline(0, color=INK2, lw=0.6)
        a[0].set_xlabel("Fitted value")
        a[0].set_ylabel(f"Standardised residual\n(model: {nm} ~ HDD)")
        a[1].plot(d.date, e, color=C["reg"], lw=0.6)
        a[1].axhline(0, color=INK2, lw=0.6)
        a[1].set_xlabel("Month")
        a[1].xaxis.set_major_locator(mdates.YearLocator(4))
        a[1].xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
        sm.qqplot(e, line="45", ax=a[2], markersize=2.2, markerfacecolor=C["reg"], markeredgewidth=0)
        a[2].get_lines()[1].set_color(INK2)
        a[2].get_lines()[1].set_linewidth(0.7)
        a[2].set_xlabel("Theoretical quantile")
        a[2].set_ylabel("Sample quantile")
    titles = ["(a) Residual vs fitted", "(b) Residual over time", "(c) Normal Q–Q"]
    for ax, ti in zip(axes[0], titles):
        ax.set_title(ti, fontsize=8.5)
    for ax, ti in zip(axes[1], ["(d)", "(e)", "(f)"]):
        ax.set_title(ti, fontsize=8.5)
    fig.tight_layout()
    save(fig, "figA1_diagnostics")


# ---------------- 부록 A2: SHAP 비교 ----------------
def figA2():
    t = pd.read_csv(OUTPUTS / "r3_shap.csv")
    lab = {"hdd": "HDD", "cdd": "CDD", "price_retail": "Retail price", "price_wholesale_lag1": "Wholesale price (t−1)",
           "ip": "Industrial production", "msin": "Month (sin)", "mcos": "Month (cos)", "lag1": "Demand (t−1)",
           "lag12": "Demand (t−12)"}
    feats = list(lab)
    fig, axes = plt.subplots(2, 3, figsize=(W2, 4.4), sharex=True, sharey=True)
    y = np.arange(len(feats))
    for ax, g in zip(axes.ravel(), ALL_GEOS):
        s = t[t.geo == g].set_index("feature").loc[feats]
        ax.barh(y - 0.19, s.ridge_shap_pct, height=0.36, color=C["reg"], label="Ridge (linear)")
        ax.barh(y + 0.19, s.lgbm_shap_pct, height=0.36, color=C["ml"], label="LightGBM (trees)")
        ax.set_title(f"{COUNTRY[g]}  (ρ = {s.spearman.iloc[0]:.2f})", fontsize=8)
        ax.grid(axis="y", visible=False)
        ax.tick_params(axis="y", length=0)
    axes[0, 0].set_yticks(y, [lab[f] for f in feats])
    axes[0, 0].invert_yaxis()
    for ax in axes[1]:
        ax.set_xlabel("Share of mean |SHAP| (%)")
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=2, bbox_to_anchor=(0.5, -0.02))
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    save(fig, "figA2_shap")


# ---------------- 부록 A3: 부문·기후 시나리오 ----------------
def figA3():
    sens = pd.read_csv(OUTPUTS / "r7_sector_sensitivity.csv")
    clim = pd.read_csv(OUTPUTS / "r11_climate.csv")
    fig, axes = plt.subplots(1, 2, figsize=(W2, 2.5), gridspec_kw={"width_ratios": [1, 1.25]})
    lab = {"총량": "Total", "SLP (가정·소규모)": "Germany SLP (households, small)",
           "RLM (산업·발전)": "Germany RLM (industry, power)", "도시가스용": "Korea city gas", "발전용": "Korea power"}
    s = sens[sens.부문 != "총량"].copy()
    s["name"] = s.부문.map(lab)
    s = s.sort_values("HDD 10당 %")
    axes[0].barh(s.name, s["HDD 10당 %"], color=C["reg"], height=0.55)
    for i, v in enumerate(s["HDD 10당 %"]):
        axes[0].text(v + 0.08, i, f"{v:.1f}", va="center", fontsize=6.8, color=INK)
    axes[0].set_xlabel("Demand increase per +10 HDD (%)")
    axes[0].set_title("(a) Sectoral heating sensitivity", fontsize=8.5)
    axes[0].grid(axis="y", visible=False)
    axes[0].tick_params(axis="y", length=0)
    c = clim.pivot(index="geo", columns="scenario", values="annual_change_pct").loc[ALL_GEOS]
    lo = clim.pivot(index="geo", columns="scenario", values="ci_low").loc[ALL_GEOS]
    hi = clim.pivot(index="geo", columns="scenario", values="ci_high").loc[ALL_GEOS]
    order = c.iloc[:, 0].sort_values().index
    yy = np.arange(len(order))
    scen = {"겨울(12~2월) HDD −10%": ("Winter (Dec–Feb) HDD −10%", BLUES[2]),
            "난방철(10~4월) HDD −10%": ("Heating season (Oct–Apr) HDD −10%", BLUES[5])}
    for k, (sname, (lb, colr)) in enumerate(scen.items()):
        v = c.loc[order, sname]
        axes[1].barh(yy + (k - 0.5) * 0.38, v, height=0.36, color=colr, label=lb,
                     xerr=[v - lo.loc[order, sname], hi.loc[order, sname] - v], ecolor=INK2, error_kw={"lw": 0.6})
    axes[1].set_yticks(yy, [COUNTRY[g] for g in order])
    axes[1].axvline(0, color=INK2, lw=0.6)
    axes[1].set_xlabel("Change in annual demand (%)")
    axes[1].set_title("(b) Warmer-winter scenarios", fontsize=8.5)
    axes[1].grid(axis="y", visible=False)
    axes[1].tick_params(axis="y", length=0)
    axes[1].legend(loc="upper center", bbox_to_anchor=(0.45, -0.22), ncol=1, fontsize=6.5)
    axes[1].invert_yaxis()
    fig.tight_layout()
    save(fig, "figA3_sector_climate")


# ---------------- Fig 5: 평가 설계별 견고성 ----------------
KEY = ["회귀 √Y~HDD+가격", "회귀 + 위기 변수", "SARIMAX+HDD·가격", "Holt-Winters", "Ridge + 위기 변수",
       "Gradient Boosting", "LightGBM", "MLP (16-8)", "하이브리드 (회귀+GBM 잔차)", "Chronos-2 단변량",
       "Chronos-2 + 공변량", "ENS"]
ENS_ALIASES = {"앙상블: 회귀(위기)+ML+Chronos": "ENS", "앙상블 (회귀·ML·Chronos)": "ENS"}


def design_table():
    """모델 × 평가 설계: 6개국 평균 MAPE와 통합 MCS 포함 여부."""
    cols, mcs = {}, {}
    m = pd.read_csv(OUTPUTS / "r4_mcs.csv").replace({"model": ENS_ALIASES})
    for mode, lab in (("ex_post", "Main\nex-post"), ("ex_ante", "Main\nex-ante")):
        a = m[(m.geo == "ALL") & (m["mode"] == mode)].set_index("model")
        cols[lab], mcs[lab] = a.MAPE, a.in_mcs
    rt = pd.read_csv(OUTPUTS / "realtime_check.csv").replace({"model": ENS_ALIASES})
    cols["Real-time"] = rt.groupby("model").MAPE_realtime.mean()
    le = OUTPUTS / "long_eval"
    if (le / "summary_all.csv").exists():
        sa = pd.read_csv(le / "summary_all.csv").replace({"model": ENS_ALIASES})
        lm = pd.read_csv(le / "mcs.csv").replace({"model": ENS_ALIASES})
        for mode, lab in (("ex_post", "Long\nex-post"), ("ex_ante", "Long\nex-ante")):
            cols[lab] = sa[sa["mode"] == mode].groupby("model").MAPE.mean()
            mcs[lab] = lm[(lm.geo == "ALL") & (lm["mode"] == mode)].set_index("model").in_mcs
    if (OUTPUTS / "oos_2026.csv").exists():
        oo = pd.read_csv(OUTPUTS / "oos_2026.csv").replace({"model": ENS_ALIASES})
        cols["Hold-out 2026\nex-post"] = oo.groupby("model").MAPE_ex_post.mean()
        cols["Hold-out 2026\nex-ante"] = oo.groupby("model").MAPE_ex_ante.mean()
    mat = pd.DataFrame(cols).reindex(KEY)
    dots = pd.DataFrame(mcs).reindex(index=KEY, columns=mat.columns).eq(True)
    return mat, dots


def fig5():
    mat, dots = design_table()
    mat.index = [NAME.get(k, "Ensemble: regression + ML + Chronos") for k in mat.index]
    fig, ax = plt.subplots(figsize=(W2, 3.6))
    heat(ax, mat, dots, vmin=3, vmax=13, title="", best_cols=set(range(mat.shape[1])), fs=6.8)
    for j in range(mat.shape[1]):
        for i in range(mat.shape[0]):
            if np.isnan(mat.values[i, j]):
                ax.text(j, i, "–", ha="center", va="center", fontsize=6.8, color=MUTED)
    ax.xaxis.tick_top()
    for x in (1.5, 2.5, 4.5):
        ax.axvline(x, color="white", lw=3)
    ax.tick_params(axis="x", labelsize=6.8)
    fig.text(0.5, -0.02, "Cells: six-country mean MAPE (%). Bold: best in column. Dot: in the 90% model confidence "
             "set on the six-country average loss (main and long designs).\nMain: 2023–2025; long: EU 2018–2025, "
             "Korea 2020–2025; real-time: published data only (demand lagged 2–3 months); hold-out: Jan–Sep 2026.",
             ha="center", fontsize=6.5, color=INK2)
    save(fig, "fig5_robustness")


# ---------------- Fig 6: 독일 예측 사례 ----------------
FIG6_MODELS = ["회귀 √Y~HDD+가격", "SARIMAX+HDD·가격", "Chronos-2 + 공변량", "ENS"]


def forecast_panel(geo="DE"):
    """그림 6과 보고서의 연도별 수치가 같이 쓰는 사후예측 모음 (2023~2025 본 평가 + 2026 표본 외)."""
    main = pd.read_csv(OUTPUTS / "experiment" / "predictions.csv")
    r8 = pd.read_csv(OUTPUTS / "r8_foundation_predictions.csv")
    ens = pd.read_csv(OUTPUTS / "r10_ensemble_predictions.csv")
    ens = ens[ens.model == "회귀(위기)+ML+Chronos"].assign(model="ENS")   # 미리 정한 앙상블 (2023~2025)
    oo = pd.read_csv(OUTPUTS / "oos_2026_predictions.csv").replace({"model": ENS_ALIASES})
    allp = pd.concat([main, r8, ens, oo], ignore_index=True)
    allp = allp[(allp.geo == geo) & (allp["mode"] == "ex_post")].drop_duplicates(["model", "month"], keep="last")
    allp = allp.dropna(subset=["actual"]).copy()
    allp["date"] = pd.to_datetime(allp.month + "-01")
    allp["year"] = allp.month.str[:4]
    return allp


def yearly_mape(geo="DE", models=FIG6_MODELS):
    allp = forecast_panel(geo)
    return {k: {y: float(((g.pred - g.actual).abs() / g.actual).mean() * 100)
                for y, g in allp[allp.model == k].groupby("year")} for k in models}


def fig6(geo="DE"):
    r8 = pd.read_csv(OUTPUTS / "r8_foundation_predictions.csv")
    sel = {"회귀 √Y~HDD+가격": ("Benchmark regression", C["bench"]), "SARIMAX+HDD·가격": ("SARIMAX (tuned)", C["sarimax"]),
           "Chronos-2 + 공변량": ("Chronos-2 (covariates)", C["chronos"]),
           "ENS": ("Ensemble: regression + ML + Chronos", C["ens"])}
    allp = forecast_panel(geo)
    act = allp.groupby("date").actual.first()
    oofm = pd.read_csv(OUTPUTS / "r8_foundation_oos2026_predictions.csv")
    band = pd.concat([r8, oofm])
    band = band[(band.geo == geo) & (band["mode"] == "ex_post") & (band.model == "Chronos-2 + 공변량")].copy()
    band["date"] = pd.to_datetime(band.month + "-01")
    band = band.drop_duplicates("date").sort_values("date")
    fig, axes = plt.subplots(1, 2, figsize=(W2, 2.9), gridspec_kw={"width_ratios": [2.3, 1], "wspace": 0.28})
    a = axes[0]
    shade(a, "2026-01", "2026-09", "#eceae4")
    a.fill_between(band.date, band.lo, band.hi, color=C["chronos"], alpha=0.22, lw=0, label="Chronos-2 80% interval")
    a.plot(act.index, act.values, color=INK, lw=1.7, label="Actual", zorder=5)
    for k, (lab, col) in sel.items():
        q = allp[allp.model == k].sort_values("date")
        a.plot(q.date, q.pred, color=col, lw=1.0, label=lab)
    a.set_ylim(0, None)
    a.set_ylabel(f"Monthly demand ({UNIT[geo]})")
    a.set_title(f"(a) {COUNTRY[geo]}: one-month-ahead ex-post forecasts", fontsize=8.5)
    a.text(pd.Timestamp("2026-05-01"), 12, "Hold-out", ha="center", va="bottom", fontsize=6.5, color=INK2)
    a.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[1, 7]))
    a.xaxis.set_major_formatter(mdates.DateFormatter("%b\n%Y"))
    # (b) 연도별 MAPE
    b = axes[1]
    years = ["2023", "2024", "2025", "2026"]
    ym = yearly_mape(geo, list(sel))
    w = 0.19
    for i, (k, (lab, col)) in enumerate(sel.items()):
        v = [ym[k].get(y, np.nan) for y in years]
        b.bar(np.arange(len(years)) + (i - 1.5) * w, v, width=w - 0.02, color=col, label=lab)
    b.set_xticks(range(len(years)), ["2023", "2024", "2025", "2026\n(hold-out)"])
    b.set_ylabel("MAPE (%)")
    b.set_title("(b) MAPE by year", fontsize=8.5)
    b.grid(axis="x", visible=False)
    h, l = a.get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=3, bbox_to_anchor=(0.5, -0.1), fontsize=6.8)
    fig.subplots_adjust(bottom=0.24)
    save(fig, f"fig6_forecasts_{geo}")


ALL = {"fig1": fig1, "fig2": fig2, "fig3": fig3, "fig4": fig4, "fig7": fig7, "figA1": figA1, "figA2": figA2,
       "figA3": figA3, "fig5": fig5, "fig6": fig6}

if __name__ == "__main__":
    for k in (sys.argv[1:] or ALL):
        ALL[k]()
