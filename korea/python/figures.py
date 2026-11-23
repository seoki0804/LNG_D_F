"""논문·발표용 그림 (영문 라벨). 6개국 연구와 같은 스타일·색 규칙.

색 규칙 (모델군마다 고정, 색각 이상 검증 팔레트): 회귀 = 파랑, SARIMAX = 주황, 기계학습 = 청록, Chronos-2 = 노랑,
앙상블 = 분홍, 계절 naive(기준) = 회색, 실제값 = 검정. 크기(민감도 등)는 파랑 한 가지 명도 단계.
출력: outputs/figures/figN_*.png (300 dpi) + .pdf
실행: python python/figures.py [fig4 fig7 ...]
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
from matplotlib.patches import FancyBboxPatch, Rectangle

from config import FIGURES, OUTPUTS, PROCESSED, ROOT

INK, INK2, MUTED, GRID, BASE = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
C = {"reg": "#2a78d6", "sarimax": "#eb6834", "ml": "#1baf7a", "chronos": "#eda100", "ens": "#e87ba4", "bench": MUTED}
BLUES = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
SEQ = LinearSegmentedColormap.from_list("seq_blue", BLUES)
EN = {"계절 naive": "Seasonal Naive", "회귀 √Y": "OLS (√Y)", "SARIMAX": "SARIMAX", "ETS": "ETS",
      "Ridge": "Ridge (direct)", "LightGBM": "LightGBM (direct)", "하이브리드 (회귀+Ridge)": "Hybrid (OLS + Ridge)",
      "하이브리드 (회귀+LightGBM)": "Hybrid (OLS + LightGBM)", "Chronos-2": "Chronos-2 (univariate)",
      "Chronos-2 + 공변량": "Chronos-2 (covariates)", "TimesFM 2.5": "TimesFM 2.5", "앙상블": "Ensemble"}
SERIES_EN = {"total": "Total", "city": "City gas", "power": "Power generation"}
PROV_EN = {"서울": "Seoul", "인천": "Incheon", "경기": "Gyeonggi", "강원": "Gangwon", "충남": "Chungnam", "세종": "Sejong",
           "충북": "Chungbuk", "경북": "Gyeongbuk", "전북": "Jeonbuk", "대전": "Daejeon", "대구": "Daegu", "울산": "Ulsan",
           "광주": "Gwangju", "전남": "Jeonnam", "경남": "Gyeongnam", "부산": "Busan", "제주": "Jeju"}
TILES = {"서울": (1, 0), "인천": (0, 1), "경기": (1, 1), "강원": (2, 1), "충남": (0, 2), "세종": (1, 2), "충북": (2, 2),
         "경북": (3, 2), "전북": (0, 3), "대전": (1, 3), "대구": (2, 3), "울산": (3, 3), "광주": (0, 4), "전남": (1, 4),
         "경남": (2, 4), "부산": (3, 4), "제주": (1, 5)}

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
W1, W2 = 3.5, 7.2
NAT = OUTPUTS / "national"
PROV = OUTPUTS / "province"
REG = OUTPUTS / "regression"


def save(fig, name):
    fig.savefig(FIGURES / f"{name}.png", bbox_inches="tight", facecolor="white")
    fig.savefig(FIGURES / f"{name}.pdf", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  {name}")


def nat():
    d = pd.read_csv(PROCESSED / "national.csv")
    d["date"] = pd.to_datetime(d.month + "-01")
    return d


def shade(ax, start, end, color):
    ax.axvspan(pd.Timestamp(start), pd.Timestamp(end) + pd.offsets.MonthEnd(0), color=color, lw=0, zorder=0)


def best_ml():
    """기계학습 대표: 세 계열 사전예측 평균 MAPE가 가장 낮은 기계학습 변형 (평가 구간 기준, 그림 범례에 명시)."""
    s = pd.read_csv(NAT / "summary_all.csv")
    s = s[(s.window == "eval") & (s["info"] == "ex_ante") & s.model.isin(
        ["Ridge", "LightGBM", "하이브리드 (회귀+Ridge)", "하이브리드 (회귀+LightGBM)"])]
    return s.groupby("model")["all"].mean().idxmin()


def key_models():
    return [("계절 naive", C["bench"]), ("회귀 √Y", C["reg"]), ("SARIMAX", C["sarimax"]), (best_ml(), C["ml"]),
            ("Chronos-2 + 공변량", C["chronos"]), ("앙상블", C["ens"])]


# ---------------- Fig 1: 자료 ----------------
def fig1():
    d = nat()
    d = d[d.total.notna()]
    fig, axes = plt.subplots(1, 2, figsize=(W2, 2.6), gridspec_kw={"width_ratios": [1.7, 1], "wspace": 0.28})
    a = axes[0]
    shade(a, "2023-01", "2025-12", "#eceae4")
    shade(a, "2026-01", "2026-09", "#d9d7cf")
    a.plot(d.date, d.city, color=INK, lw=1.2)
    a.plot(d.date, d.power, color=BLUES[3], lw=1.2)
    a.text(pd.Timestamp("2016-03-01"), d.city.max() * 0.97, "City gas", color=INK, fontsize=7.5, va="top")
    a.text(pd.Timestamp("2016-03-01"), 520, "Power generation", color=INK2, fontsize=7.5)
    a.set_ylabel("Monthly supply (kt LNG)")
    a.set_ylim(0, None)
    a.set_title("(a) Monthly natural gas supply by use, Korea", fontsize=8.5)
    a.text(pd.Timestamp("2024-07-01"), d.city.max() * 1.02, "Evaluation", ha="center", fontsize=6.5, color=INK2)
    a.text(pd.Timestamp("2026-05-01"), d.city.max() * 1.02, "Hold-out", ha="center", fontsize=6.5, color=INK2)
    a.xaxis.set_major_locator(mdates.YearLocator(2))
    a.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    a.grid(axis="x", visible=False)
    b = axes[1]
    e = d[d.month <= "2025-12"]
    b.scatter(e.hdd, e.city, s=9, color=BLUES[4], alpha=0.75, lw=0)
    fit = sm.OLS(np.sqrt(e.city), sm.add_constant(e.hdd)).fit()
    x = np.linspace(0, e.hdd.max(), 100)
    b.plot(x, fit.predict(sm.add_constant(x)) ** 2, color=INK, lw=1.1)
    b.set_xlabel("Demand-weighted HDD (°C·day)")
    b.set_ylabel("City gas (kt LNG)")
    b.set_title("(b) City gas vs heating degree days", fontsize=8.5)
    b.text(0.04, 0.93, f"√Y ~ HDD, R² = {fit.rsquared:.3f}", transform=b.transAxes, fontsize=7, color=INK2)
    save(fig, "fig1_data")


# ---------------- Fig 2: 평가 설계 ----------------
def fig2():
    fig, axes = plt.subplots(2, 1, figsize=(W2, 2.5), sharex=False, gridspec_kw={"hspace": 0.9})
    rows = [("National supply by use (2016–2026)", "2016-01", [("Initial training", "2016-01", "2019-12", "#eceae4"),
                                                                 ("Validation targets", "2020-01", "2022-12", BLUES[1]),
                                                                 ("Evaluation targets", "2023-01", "2025-12", BLUES[3]),
                                                                 ("Hold-out", "2026-01", "2026-09", BLUES[5])],
             ["2021-06", "2023-03", "2024-09"]),
            ("Province city-gas sales (2006–2022)", "2006-01", [("Initial training", "2006-01", "2016-12", "#eceae4"),
                                                                ("Validation targets", "2017-01", "2019-12", BLUES[1]),
                                                                ("Evaluation targets", "2020-01", "2022-12", BLUES[3])],
             ["2018-03", "2020-06", "2021-09"])]
    for ax, (title, start, spans, origins) in zip(axes, rows):
        for lab, a, b, col in spans:
            x0, x1 = pd.Timestamp(a), pd.Timestamp(b) + pd.offsets.MonthEnd(0)
            ax.add_patch(Rectangle((mdates.date2num(x0), 0.25), mdates.date2num(x1) - mdates.date2num(x0), 0.5,
                                   lw=0, facecolor=col, edgecolor="none"))
            ax.text(x0 + (x1 - x0) / 2, 0.5, lab, ha="center", va="center", fontsize=6.5,
                    color="white" if col in (BLUES[3], BLUES[5]) else INK)
        for o in origins:   # 예측 시점에서 12개월 앞까지
            t0 = pd.Timestamp(o + "-01")
            ax.annotate("", xy=(t0 + pd.DateOffset(months=12), 1.05), xytext=(t0, 1.05),
                        arrowprops=dict(arrowstyle="-|>", color=INK2, lw=0.8))
            ax.plot([t0], [1.05], "o", color=INK, ms=2.5)
        ax.text(pd.Timestamp(origins[0] + "-01"), 1.3, "origin T → forecasts for T+1 … T+12", fontsize=6.3, color=INK2)
        ax.set_ylim(0.1, 1.5)
        ax.set_xlim(pd.Timestamp(start), pd.Timestamp("2027-01-01") if "National" in title else pd.Timestamp("2023-06-01"))
        ax.set_yticks([])
        ax.spines["left"].set_visible(False)
        ax.grid(False)
        ax.xaxis.set_major_locator(mdates.YearLocator(2 if "Province" in title else 1))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
        ax.set_title(title, fontsize=8.5)
    save(fig, "fig2_design")


# ---------------- Fig 3: 시도별 난방 민감도 ----------------
def fig3():
    s = pd.read_csv(REG / "province_sensitivity.csv")
    mid = s[s.period == "2010~2019"].set_index("province").pct_per10
    fig, axes = plt.subplots(1, 2, figsize=(W2, 3.4), gridspec_kw={"width_ratios": [1, 1.25], "wspace": 0.3})
    a = axes[0]
    lo, hi = mid.min(), mid.max()
    for p, (x, y) in TILES.items():
        v = mid.get(p, np.nan)
        col = SEQ((v - lo) / (hi - lo)) if np.isfinite(v) else "#eeeeee"
        a.add_patch(FancyBboxPatch((x + 0.04, -y + 0.04), 0.92, 0.92, boxstyle="round,pad=0,rounding_size=0.08",
                                   color=col, lw=0))
        dark = np.isfinite(v) and (v - lo) / (hi - lo) > 0.55
        a.text(x + 0.5, -y + 0.64, PROV_EN[p], ha="center", va="center", fontsize=5.3, color="white" if dark else INK)
        a.text(x + 0.5, -y + 0.33, f"{v:.1f}%", ha="center", va="center", fontsize=7, fontweight="bold",
               color="white" if dark else INK)
    a.set_xlim(-0.1, 4.1)
    a.set_ylim(-5.1, 1.1)
    a.set_aspect("equal")
    a.axis("off")
    a.set_title("(a) Demand increase per +10 HDD, 2010–2019", fontsize=8.5)
    b = axes[1]
    order = mid.sort_values().index
    per = [("2000~2009", BLUES[1], "2000–09"), ("2010~2019", BLUES[3], "2010–19"), ("2020~2022", BLUES[5], "2020–22")]
    for i, p in enumerate(order):
        vals = s[s.province == p].set_index("period").pct_per10
        b.plot([vals.min(), vals.max()], [i, i], color=GRID, lw=2, zorder=1)
        for per_name, col, lab in per:
            if per_name in vals:
                b.scatter(vals[per_name], i, s=16, color=col, zorder=3, label=lab if i == 0 else None, lw=0)
    b.set_yticks(range(len(order)), [PROV_EN[p] for p in order])
    b.set_xlabel("% sales per +10 HDD (current + previous month)")
    b.legend(loc="lower right", ncol=1, handletextpad=0.2)
    b.grid(axis="y", visible=False)
    t = pd.read_csv(REG / "province_tests.csv")
    f = t[t.test.str.contains("기울기 동일")].iloc[0]
    b.set_title(f"(b) By period (equal slopes rejected: F = {f.stat:.0f}, p < 0.001)", fontsize=8.5)
    save(fig, "fig3_province_sensitivity")


# ---------------- Fig 4: 예측 시계별 정확도 ----------------
def fig4():
    s = pd.read_csv(NAT / "summary_all.csv")
    s = s[(s.window == "eval") & (s["info"] == "ex_ante")]
    hcols = [f"h{h}" for h in range(1, 13)]
    fig, axes = plt.subplots(1, 3, figsize=(W2, 2.5), sharey=False, gridspec_kw={"wspace": 0.3})
    for ax, ser in zip(axes, ["total", "city", "power"]):
        for m, col in key_models():
            r = s[(s.series == ser) & (s.model == m)]
            if r.empty:
                continue
            ls = "--" if m == "계절 naive" else "-"
            ax.plot(range(1, 13), r[hcols].values[0], color=col, ls=ls, lw=1.3 if m == "앙상블" else 1.0,
                    marker="o", ms=2.2, label=EN[m])
        ax.set_title(f"{SERIES_EN[ser]}", fontsize=8.5)
        ax.set_xticks([1, 3, 6, 9, 12])
        ax.set_xlabel("Horizon (months ahead)")
        ax.set_ylim(0, None)
        ax.grid(axis="x", visible=False)
    axes[0].set_ylabel("MAPE (%), 2023–2025 targets")
    h, l = axes[0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=6, bbox_to_anchor=(0.5, -0.12), handlelength=1.6, columnspacing=1.0)
    save(fig, "fig4_horizon")


# ---------------- Fig 5: 기온 정보의 가치 ----------------
def fig5():
    s = pd.read_csv(NAT / "summary_all.csv")
    s = s[s.window == "eval"]
    hcols = [f"h{h}" for h in range(1, 13)]
    fig, axes = plt.subplots(1, 2, figsize=(W2, 2.2), gridspec_kw={"wspace": 0.25})
    for ax, ser in zip(axes, ["city", "power"]):
        m = "앙상블"
        ante = s[(s.series == ser) & (s.model == m) & (s["info"] == "ex_ante")][hcols].values[0]
        post = s[(s.series == ser) & (s.model == m) & (s["info"] == "ex_post")][hcols].values[0]
        x = np.arange(1, 13)
        ax.fill_between(x, post, ante, color=C["ens"], alpha=0.18, lw=0)
        ax.plot(x, ante, color=C["ens"], lw=1.3, marker="o", ms=2.2, label="Normal weather (ex-ante)")
        ax.plot(x, post, color=C["ens"], lw=1.0, ls="--", marker="o", ms=2.2, mfc="white", label="Actual weather (ex-post)")
        a_all = s[(s.series == ser) & (s.model == m) & (s["info"] == "ex_ante")]["all"].values[0]
        p_all = s[(s.series == ser) & (s.model == m) & (s["info"] == "ex_post")]["all"].values[0]
        ax.text(0.97, 0.06, f"Weather share of error: {(a_all - p_all) / a_all * 100:.0f}%\n"
                f"({a_all:.1f}% → {p_all:.1f}%, horizons 1–12)",
                transform=ax.transAxes, ha="right", va="bottom", fontsize=6.8, color=INK2)
        ax.set_title(f"{SERIES_EN[ser]}: Ensemble", fontsize=8.5)
        ax.set_xticks([1, 3, 6, 9, 12])
        ax.set_xlabel("Horizon (months ahead)")
        ax.set_ylim(0, None)
        ax.grid(axis="x", visible=False)
    axes[0].set_ylabel("MAPE (%)")
    h, l = axes[0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=2, bbox_to_anchor=(0.5, -0.17))
    save(fig, "fig5_weather_value")


# ---------------- Fig 6: 계층 예측 ----------------
def fig6():
    s = pd.read_csv(PROV / "summary.csv")
    models = [m for m in ["계절 naive", "ETS", "회귀 √Y", "Chronos-2 + 공변량"] if m in s.model.unique()]
    methods = [("기본", "Base (direct)", "o", "white", INK), ("상향식", "Bottom-up", "o", INK, INK),
               ("하향식", "Top-down", "^", MUTED, MUTED), ("MinT", "MinT (shrink)", "D", BLUES[4], BLUES[4])]
    fig, axes = plt.subplots(1, 2, figsize=(W2, 2.3), sharey=True, gridspec_kw={"wspace": 0.12})
    for ax, (level, title) in zip(axes, [("전국", "(a) National total"), ("시도 평균", "(b) Average over 17 provinces")]):
        for i, m in enumerate(models):
            vals = s[(s.model == m) & (s.level == level)].set_index("method")["all"]
            ax.plot([vals.min(), vals.max()], [i, i], color=GRID, lw=2, zorder=1)
            for j, (k, lab, mk, fc, ec) in enumerate(methods):
                ax.scatter(vals[k], i + (j - 1.5) * 0.08, marker=mk, s=22, facecolor=fc, edgecolor=ec, lw=0.9,
                           zorder=3, label=lab if i == 0 else None)
        ax.set_yticks(range(len(models)), [EN[m] for m in models])
        ax.set_xlabel("MAPE (%), mean over horizons 1–12, 2020–2022 targets")
        ax.set_title(title, fontsize=8.5)
        ax.grid(axis="y", visible=False)
    h, l = axes[0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=4, bbox_to_anchor=(0.5, -0.2), fontsize=7)
    save(fig, "fig6_hierarchy")


# ---------------- Fig 7: 2026년 표본 외 ----------------
def fig7():
    d = nat()
    p = pd.read_csv(NAT / "all_predictions.csv")
    fm = pd.read_csv(NAT / "foundation.csv")
    origin = "2025-12"
    fig, axes = plt.subplots(1, 2, figsize=(W2, 2.6), gridspec_kw={"wspace": 0.25})
    for ax, ser in zip(axes, ["city", "power"]):
        hist = d[(d.month >= "2024-07") & (d.month <= "2026-09")]
        band = fm[(fm.name == ser) & (fm.origin == origin) & (fm.model == "Chronos-2 + 공변량") & (fm["info"] == "ex_ante")
                  & (fm.month <= "2026-09")]
        bd = pd.to_datetime(band.month + "-01")
        ax.fill_between(bd, band.lo, band.hi, color=C["chronos"], alpha=0.22, lw=0, label="Chronos-2 80% interval")
        for m, col in [("계절 naive", C["bench"]), ("회귀 √Y", C["reg"]), ("Chronos-2 + 공변량", C["chronos"]),
                       ("앙상블", C["ens"])]:
            q = p[(p.series == ser) & (p.model == m) & (p.origin == origin) & (p["info"] == "ex_ante")].sort_values("month")
            ax.plot(pd.to_datetime(q.month + "-01"), q.pred, color=col, lw=1.3 if m == "앙상블" else 1.0,
                    ls="--" if m == "계절 naive" else "-", label=EN[m])
        ax.plot(hist.date, hist[ser], color=INK, lw=1.6, label="Actual", zorder=5)
        ax.axvline(pd.Timestamp("2025-12-15"), color=MUTED, lw=0.7)
        ax.text(pd.Timestamp("2025-12-05"), 40, "origin", fontsize=6.3, color=INK2, ha="right", va="bottom")
        ax.set_title(f"{SERIES_EN[ser]}: 1–9 months ahead from Dec 2025", fontsize=8.5)
        ax.set_ylabel("kt LNG")
        ax.set_ylim(0, None)
        ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[1, 7]))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b\n%Y"))
        ax.grid(axis="x", visible=False)
    h, l = axes[0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=6, bbox_to_anchor=(0.5, -0.1), columnspacing=1.0)
    save(fig, "fig7_holdout_2026")


# ---------------- Fig 8: 6개국 비교 ----------------
def fig8():
    f = ROOT.parent / "multicountry" / "report" / "numbers.json"
    N = json.loads(f.read_text(encoding="utf-8"))
    names = {"DE": "Germany", "IT": "Italy", "FR": "France", "ES": "Spain", "NL": "Netherlands", "KR": "Korea"}
    geos = sorted(N["r5"], key=lambda g: N["r5"][g]["hdd10_post"])
    fig, axes = plt.subplots(1, 2, figsize=(W2, 2.4), gridspec_kw={"wspace": 0.45})
    a = axes[0]
    for i, g in enumerate(geos):
        pre, post = N["r5"][g]["hdd10_pre"], N["r5"][g]["hdd10_post"]
        col = BLUES[5] if g == "KR" else BLUES[2]
        a.plot([pre, post], [i, i], color=GRID, lw=2, zorder=1)
        a.scatter(pre, i, s=18, facecolor="white", edgecolor=col, lw=1, zorder=3, label="Before 2022-03" if i == 0 else None)
        a.scatter(post, i, s=18, color=col, zorder=3, label="After 2022-03" if i == 0 else None)
    a.set_yticks(range(len(geos)), [names[g] for g in geos])
    a.set_xlabel("% demand per +10 HDD")
    a.set_title("(a) Heating sensitivity", fontsize=8.5)
    a.legend(loc="lower right", fontsize=6.5)
    a.grid(axis="y", visible=False)
    b = axes[1]
    main = N["main"]["ex_post"]
    best = {g: min(v[g] for v in main.values() if g in v and v[g] is not None) for g in geos}
    bench = {g: main["회귀 √Y~HDD+가격"][g] for g in geos}
    for i, g in enumerate(geos):
        col = BLUES[5] if g == "KR" else BLUES[2]
        b.plot([best[g], bench[g]], [i, i], color=GRID, lw=2, zorder=1)
        b.scatter(bench[g], i, s=18, color=MUTED, zorder=3, label="Benchmark regression" if i == 0 else None)
        b.scatter(best[g], i, s=18, color=col, zorder=3, label="Best model" if i == 0 else None)
    b.set_yticks(range(len(geos)), [names[g] for g in geos])
    b.set_xlabel("MAPE (%), 1 month ahead, 2023–2025")
    b.set_title("(b) Forecast error, same models in all countries", fontsize=8.5)
    b.legend(loc="lower right", fontsize=6.5)
    b.grid(axis="y", visible=False)
    save(fig, "fig8_six_countries")


# ---------------- 부록: 회귀 진단 ----------------
def figA1():
    r = pd.read_csv(REG / "national_resid.csv")
    r["date"] = pd.to_datetime(r.month + "-01")
    fig, axes = plt.subplots(1, 3, figsize=(W2, 2.2), gridspec_kw={"wspace": 0.35})
    axes[0].scatter(r.fitted, r.resid, s=8, color=BLUES[4], lw=0)
    axes[0].axhline(0, color=INK2, lw=0.7)
    axes[0].set_xlabel("Fitted √Y")
    axes[0].set_ylabel("Residual")
    axes[0].set_title("(a) Residuals vs fitted", fontsize=8.5)
    q = np.sort(r.rstudent)
    t = np.sort(np.random.default_rng(0).standard_normal(100000))[np.linspace(0, 99999, len(q)).astype(int)]
    axes[1].scatter(t, q, s=8, color=BLUES[4], lw=0)
    axes[1].plot([-3, 3], [-3, 3], color=INK2, lw=0.7)
    axes[1].set_xlabel("Normal quantile")
    axes[1].set_ylabel("Studentized residual")
    axes[1].set_title("(b) Normal Q–Q", fontsize=8.5)
    axes[2].plot(r.date, r.resid, color=BLUES[4], lw=0.9)
    axes[2].axhline(0, color=INK2, lw=0.7)
    axes[2].set_title("(c) Residuals over time", fontsize=8.5)
    axes[2].xaxis.set_major_locator(mdates.YearLocator(3))
    axes[2].xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    save(fig, "figA1_diagnostics")


ALL = {"fig1": fig1, "fig2": fig2, "fig3": fig3, "fig4": fig4, "fig5": fig5, "fig6": fig6, "fig7": fig7,
       "fig8": fig8, "figA1": figA1}

if __name__ == "__main__":
    for k in (sys.argv[1:] or ALL):
        try:
            ALL[k]()
        except FileNotFoundError as e:
            print(f"  {k} 건너뜀: {e.filename} 없음")
