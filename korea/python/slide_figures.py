"""발표용 그림 (한글 라벨, 슬라이드 실제 크기·큰 글씨). 보고서 그림(figures.py)과 같은 결과를 발표에 맞게 다시 그린다.

원칙: 그림 하나에 메시지 하나, 슬라이드에 놓일 크기(인치) 그대로 그려 글자 크기(pt)가 화면에서도 같게 한다.
색: 도시가스용 = 파랑, 발전용 = 주황, Ensemble = 남색(강조), 파운데이션 모델 = 초록, 나머지 모델 = 회색,
    Seasonal Naive = 회색 점선, 실제값 = 검정.
출력: outputs/figures/slides/*.png
실행: python python/slide_figures.py [s_demand s_horizon ...]
"""
import json
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import font_manager
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.lines import Line2D
from matplotlib.patches import FancyBboxPatch, Patch

from config import FIGURES, OUTPUTS, PROCESSED, ROOT

for f in ["malgun.ttf", "malgunbd.ttf"]:
    try:
        font_manager.fontManager.addfont(f"C:/Windows/Fonts/{f}")
    except (FileNotFoundError, RuntimeError):
        pass

OUT = FIGURES / "slides"
OUT.mkdir(parents=True, exist_ok=True)
NAT, PROV, REG = OUTPUTS / "national", OUTPUTS / "province", OUTPUTS / "regression"

INK, INK2, MUTED, GRID, BASE = "#1b1b1b", "#4a4f5c", "#8a8f9c", "#e3e5ea", "#c5cad3"
NAVY, CITY, POWER, FMC, LIGHT = "#16213e", "#2a78d6", "#eb6834", "#1baf7a", "#c9ced8"
BLUES = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
SEQ = LinearSegmentedColormap.from_list("seq_blue", BLUES)
SER_KO = {"city": "도시가스용", "power": "발전용", "total": "합계"}
SER_C = {"city": CITY, "power": POWER, "total": NAVY}
SHORT = {"계절 naive": "Seasonal Naive", "회귀 √Y": "OLS(√Y)", "SARIMAX": "SARIMAX", "ETS": "ETS", "Ridge": "Ridge",
         "LightGBM": "LightGBM", "하이브리드 (회귀+Ridge)": "Hybrid(Ridge)", "하이브리드 (회귀+LightGBM)": "Hybrid(LGBM)",
         "Chronos-2": "Chronos-2", "Chronos-2 + 공변량": "Chronos-2(공변량)", "TimesFM 2.5": "TimesFM 2.5",
         "앙상블": "Ensemble"}
FM = {"Chronos-2", "Chronos-2 + 공변량", "TimesFM 2.5"}
PROV_ORDER_TILES = {"서울": (1, 0), "인천": (0, 1), "경기": (1, 1), "강원": (2, 1), "충남": (0, 2), "세종": (1, 2),
                    "충북": (2, 2), "경북": (3, 2), "전북": (0, 3), "대전": (1, 3), "대구": (2, 3), "울산": (3, 3),
                    "광주": (0, 4), "전남": (1, 4), "경남": (2, 4), "부산": (3, 4), "제주": (1, 5)}

plt.rcParams.update({
    "font.family": ["Malgun Gothic", "DejaVu Sans"], "axes.unicode_minus": False,
    "font.size": 14, "axes.titlesize": 16, "axes.labelsize": 14, "xtick.labelsize": 13, "ytick.labelsize": 13,
    "legend.fontsize": 13, "axes.edgecolor": BASE, "axes.linewidth": 0.9, "axes.labelcolor": INK2,
    "xtick.color": INK2, "ytick.color": INK2, "xtick.major.size": 4, "ytick.major.size": 0,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8, "axes.axisbelow": True,
    "axes.spines.top": False, "axes.spines.right": False, "axes.spines.left": False, "legend.frameon": False,
    "lines.linewidth": 2.2, "savefig.dpi": 220, "axes.titleweight": "bold", "axes.titlelocation": "left",
    "axes.titlecolor": INK, "text.color": INK, "axes.titlepad": 10,
})


def save(fig, name):
    fig.savefig(OUT / f"{name}.png", facecolor="white")
    plt.close(fig)
    print(f"  slides/{name}")


def nat():
    d = pd.read_csv(PROCESSED / "national.csv")
    d["date"] = pd.to_datetime(d.month + "-01")
    return d


def model_color(m):
    return NAVY if m == "앙상블" else FMC if m in FM else MUTED


# ---------------- 수요 시계열 ----------------
def s_demand():
    d = nat()
    d = d[d.total.notna()]
    fig, ax = plt.subplots(figsize=(8.2, 4.9), layout="constrained")
    for a, b, lab in [("2023-01", "2025-12", "평가 구간\n2023~2025"), ("2026-01", "2026-09", "표본 외\n2026")]:
        ax.axvspan(pd.Timestamp(a), pd.Timestamp(b) + pd.offsets.MonthEnd(0), color="#eef1f7", lw=0, zorder=0)
        ax.text(pd.Timestamp(a) + pd.Timedelta(days=20), 3350, lab, fontsize=12, color=INK2, va="top")
    ax.plot(d.date, d.city, color=CITY, lw=2.2)
    ax.plot(d.date, d.power, color=POWER, lw=2.2)
    ax.text(pd.Timestamp("2016-03"), 2900, "도시가스용", color=CITY, fontsize=15, fontweight="bold")
    ax.text(pd.Timestamp("2016-03"), 420, "발전용", color=POWER, fontsize=15, fontweight="bold")
    ax.set_ylim(0, 3400)
    ax.set_ylabel("월 공급량 (천 톤)")
    ax.xaxis.set_major_locator(mdates.YearLocator(2))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.grid(axis="x", visible=False)
    save(fig, "s_demand")


# ---------------- 기온과 수요 ----------------
def s_weather_scatter():
    d = nat()
    d = d[d.total.notna() & (d.month <= "2025-12")]
    h26 = nat()
    h26 = h26[(h26.month >= "2026-07") & (h26.month <= "2026-08")]
    reg = json.loads((ROOT / "report" / "numbers.json").read_text(encoding="utf-8"))["reg"]
    fig, axes = plt.subplots(1, 2, figsize=(12.1, 4.8), layout="constrained")
    a = axes[0]
    a.scatter(d.hdd, d.city, s=34, color=CITY, alpha=0.75, lw=0)
    b1, b0 = np.polyfit(d.hdd, np.sqrt(d.city), 1)
    xs = np.linspace(0, d.hdd.max(), 100)
    a.plot(xs, (b0 + b1 * xs) ** 2, color=NAVY, lw=2)
    a.text(0.04, 0.94, f"√Y ~ HDD   R² = {reg['r2_simple']:.3f}", transform=a.transAxes, fontsize=15,
           fontweight="bold", color=NAVY, va="top")
    a.set_title("도시가스용: 난방도일(HDD)로 거의 설명됨")
    a.set_xlabel("수요가중 난방도일 (°C·일)")
    a.set_ylabel("월 공급량 (천 톤)")
    b = axes[1]
    b.scatter(d.tmean, d.power, s=34, color=POWER, alpha=0.75, lw=0, label="2016~2025")
    b.scatter(h26.tmean, h26.power, s=90, facecolor="white", edgecolor=INK, lw=2, zorder=4, label="2026년 7~8월")
    b.annotate("2026년 7~8월" + chr(10) + "기온으로 설명되지 않음", (h26.tmean.min() - 0.4, h26.power.mean()), xytext=(18.5, 1800),
               textcoords="data", fontsize=12.5, color=INK, ha="center", va="center",
               arrowprops=dict(arrowstyle="->", color=INK, lw=1.2))
    b.text(0.5, 0.06, f"HDD·CDD 회귀   R² = {reg['r2_power_weather']:.2f}", transform=b.transAxes, fontsize=15,
           fontweight="bold", color="#b4471c", va="bottom", ha="center")
    b.set_title("발전용: 기온만으로는 절반 남짓")
    b.set_xlabel("월평균 기온 (°C)")
    b.legend(loc="lower right", fontsize=12, handletextpad=0.3, bbox_to_anchor=(1, 0.12))
    for ax in axes:
        ax.set_ylim(0, None)
        ax.spines["left"].set_visible(False)
    save(fig, "s_weather_scatter")


# ---------------- 시도별 민감도 ----------------
def s_province():
    s = pd.read_csv(REG / "province_sensitivity.csv")
    mid = s[s.period == "2010~2019"].set_index("province").pct_per10
    fig, axes = plt.subplots(1, 2, figsize=(12.1, 5.0), gridspec_kw={"width_ratios": [1, 1.35], "wspace": 0.18},
                             layout="constrained")
    a = axes[0]
    lo, hi = mid.min(), mid.max()
    for p, (x, y) in PROV_ORDER_TILES.items():
        v = mid.get(p, np.nan)
        t = (v - lo) / (hi - lo)
        a.add_patch(FancyBboxPatch((x + 0.04, -y + 0.04), 0.92, 0.92, boxstyle="round,pad=0,rounding_size=0.08",
                                   color=SEQ(t), lw=0))
        dark = t > 0.5
        a.text(x + 0.5, -y + 0.66, p, ha="center", va="center", fontsize=12, color="white" if dark else INK)
        a.text(x + 0.5, -y + 0.32, f"{v:.1f}", ha="center", va="center", fontsize=14, fontweight="bold",
               color="white" if dark else INK)
    a.set_xlim(-0.1, 4.1)
    a.set_ylim(-5.1, 1.1)
    a.set_aspect("equal")
    a.axis("off")
    a.set_title("HDD 10 증가당 판매량 증가율 (%), 2010~2019", fontsize=14)
    b = axes[1]
    order = mid.sort_values().index
    per = [("2000~2009", BLUES[1], "2000년대"), ("2010~2019", BLUES[3], "2010년대"), ("2020~2022", BLUES[6], "2020~22년")]
    for i, p in enumerate(order):
        vals = s[s.province == p].set_index("period").pct_per10
        b.plot([vals.min(), vals.max()], [i, i], color=GRID, lw=3, zorder=1)
        for pn, col, lab in per:
            if pn in vals:
                b.scatter(vals[pn], i, s=60, color=col, zorder=3, label=lab if i == 0 else None, lw=0)
    b.set_yticks(range(len(order)), list(order), fontsize=12)
    b.set_xlabel("HDD 10 증가당 판매량 증가율 (%)")
    b.legend(loc="lower right", fontsize=12, handletextpad=0.2)
    b.grid(axis="y", visible=False)
    b.set_title("기간별 변화: 2020년대에 17곳 중 15곳 상승", fontsize=14)
    save(fig, "s_province")


# ---------------- 예측 시계별 MAPE ----------------
def s_horizon():
    s = pd.read_csv(NAT / "summary_all.csv")
    s = s[(s.window == "eval") & (s["info"] == "ex_ante")]
    hc = [f"h{h}" for h in range(1, 13)]
    x = np.arange(1, 13)
    fig, axes = plt.subplots(1, 2, figsize=(12.1, 4.8), sharey=True, layout="constrained")
    for ax, ser in zip(axes, ["city", "power"]):
        t = s[s.series == ser].set_index("model")
        for m in t.index:
            if m in ("앙상블", "계절 naive"):
                continue
            ax.plot(x, t.loc[m, hc], color=LIGHT, lw=1.4, zorder=1)
        ax.plot(x, t.loc["계절 naive", hc], color=MUTED, lw=2, ls="--", zorder=2)
        ax.plot(x, t.loc["앙상블", hc], color=NAVY, lw=3.2, marker="o", ms=6, zorder=3)
        ax.text(12.3, t.loc["앙상블", "h12"], f"Ensemble\n{t.loc['앙상블', 'all']:.1f}%", color=NAVY, fontsize=13,
                fontweight="bold", va="center")
        ax.text(12.3, t.loc["계절 naive", "h12"], f"Seasonal\nNaive {t.loc['계절 naive', 'all']:.1f}%", color=MUTED,
                fontsize=12, va="center")
        ax.set_title(f"{SER_KO[ser]}", color=SER_C[ser])
        ax.set_xticks([1, 3, 6, 9, 12])
        ax.set_xlim(0.6, 14.6)
        ax.set_xlabel("예측 시계 (개월 앞)")
        ax.grid(axis="x", visible=False)
        ax.set_ylim(0, 18)
    axes[0].set_ylabel("MAPE (%)")
    handles = [Line2D([], [], color=NAVY, lw=3.2, marker="o", ms=6), Line2D([], [], color=MUTED, lw=2, ls="--"),
               Line2D([], [], color=LIGHT, lw=1.4)]
    fig.legend(handles, ["Ensemble", "Seasonal Naive (작년 같은 달)", "나머지 10개 모델"], loc="outside lower center",
               ncol=3, fontsize=13)
    save(fig, "s_horizon")


# ---------------- 모델별 MAPE와 95% 신뢰구간 ----------------
def s_models():
    mt = pd.read_csv(NAT / "metrics.csv")
    mt = mt[(mt.window == "eval") & (mt["info"] == "ex_ante")]
    mc = pd.read_csv(NAT / "mcs.csv")
    mc = mc[(mc["info"] == "ex_ante") & (mc.horizon == "all")]
    fig, axes = plt.subplots(1, 2, figsize=(12.1, 5.0), layout="constrained")
    for ax, ser in zip(axes, ["city", "power"]):
        t = mt[mt.series == ser].sort_values("MAPE", ascending=False).reset_index(drop=True)
        inm = set(mc[(mc.series == ser) & mc.in_mcs].model)
        for i, r in t.iterrows():
            c = model_color(r.model)
            ax.plot([r.MAPE_lo, r.MAPE_hi], [i, i], color=c, lw=2.2, alpha=0.55, solid_capstyle="round")
            ax.scatter(r.MAPE, i, s=110 if r.model == "앙상블" else 75, zorder=3,
                       facecolor=c if r.model in inm else "white", edgecolor=c, lw=2)
            ax.text(r.MAPE_hi + 0.25, i, f"{r.MAPE:.1f}", va="center", fontsize=12,
                    color=NAVY if r.model == "앙상블" else INK2, fontweight="bold" if r.model == "앙상블" else None)
        ax.set_yticks(range(len(t)), [SHORT[m] for m in t.model])
        for lab, m in zip(ax.get_yticklabels(), t.model):
            lab.set_color(model_color(m) if m != "계절 naive" else INK2)
            if m == "앙상블":
                lab.set_fontweight("bold")
        ax.set_xlim(0, t.MAPE_hi.max() + 1.8)
        ax.set_xlabel("MAPE (%), 1~12개월 평균, 막대 = 95% 신뢰구간")
        ax.set_title(SER_KO[ser], color=SER_C[ser])
        ax.grid(axis="y", visible=False)
    handles = [Line2D([], [], ls="", marker="o", ms=10, color=MUTED), Line2D([], [], ls="", marker="o", ms=10,
               markerfacecolor="white", markeredgecolor=MUTED, markeredgewidth=2),
               Patch(color=NAVY), Patch(color=FMC)]
    fig.legend(handles, ["MCS(90%) 포함", "MCS 밖 (유의하게 나쁨)", "Ensemble", "파운데이션 모델"],
               loc="outside lower center", ncol=4, fontsize=13)
    save(fig, "s_models")


# ---------------- 평균 순위와 임계차 ----------------
def s_rank():
    rk = pd.read_csv(NAT / "ranks.csv")
    ft = pd.read_csv(NAT / "friedman.csv")
    rk, ft = rk[rk["info"] == "ex_ante"], ft[ft["info"] == "ex_ante"]
    fig, axes = plt.subplots(1, 3, figsize=(12.1, 4.9), layout="constrained")
    for ax, ser in zip(axes, ["city", "power", "total"]):
        r = rk[rk.series == ser].sort_values("avg_rank", ascending=False).reset_index(drop=True)
        cd = ft[ft.series == ser].CD.iloc[0]
        e = r[r.model == "앙상블"].avg_rank.iloc[0]
        ax.axvspan(e, e + cd, color="#e8eef9", lw=0, zorder=0)
        for i, row in r.iterrows():
            c = model_color(row.model)
            within = row.avg_rank - e < cd
            ax.scatter(row.avg_rank, i, s=90 if row.model == "앙상블" else 60, color=c if within else "white",
                       edgecolor=c, lw=2, zorder=3)
        ax.set_yticks(range(len(r)), [SHORT[m] for m in r.model], fontsize=12)
        for lab, m in zip(ax.get_yticklabels(), r.model):
            lab.set_color(model_color(m) if m != "계절 naive" else INK2)
            if m == "앙상블":
                lab.set_fontweight("bold")
        ax.set_xlim(4.6, 8.5)
        ax.set_ylim(-0.6, len(r) + 0.4)
        ax.set_xlabel("평균 순위 (1 = 최고)")
        ax.set_title(SER_KO[ser], color=SER_C[ser])
        ax.grid(axis="y", visible=False)
        ax.text(e + cd + 0.08, len(r) - 0.55, f"CD = {cd:.2f}", ha="left", va="center", fontsize=12, color=BLUES[5])
    handles = [Patch(color="#e8eef9"), Line2D([], [], ls="", marker="o", ms=10, color=MUTED),
               Line2D([], [], ls="", marker="o", ms=10, markerfacecolor="white", markeredgecolor=MUTED,
                      markeredgewidth=2)]
    fig.legend(handles, ["Ensemble + 임계차(CD) 범위", "Ensemble과 구별되지 않음", "Ensemble보다 유의하게 나쁨"],
               loc="outside lower center", ncol=3, fontsize=13)
    save(fig, "s_rank")


# ---------------- 달력월별 오차 ----------------
def s_error_month():
    em = pd.read_csv(NAT / "error_month.csv")
    e = em[(em.model == "앙상블") & (em["info"] == "ex_ante") & (em.window == "eval")]
    fig, axes = plt.subplots(1, 2, figsize=(12.1, 4.8), layout="constrained")
    x = np.arange(1, 13)
    w = 0.38
    for k, ser in enumerate(["city", "power"]):
        r = e[e.series == ser].set_index("cm").reindex(x)
        axes[0].bar(x + (k - 0.5) * w, r.MAPE, width=w, color=SER_C[ser], label=SER_KO[ser])
        axes[1].bar(x + (k - 0.5) * w, r.bias, width=w, color=SER_C[ser], label=SER_KO[ser])
    axes[0].set_title("월별 MAPE (%)")
    axes[1].set_title("월별 평균 오차 (%) : + 과대예측, − 과소예측")
    axes[1].axhline(0, color=INK2, lw=1)
    for ax in axes:
        ax.set_xticks(x, [f"{m}월" for m in x], fontsize=12)
        ax.grid(axis="x", visible=False)
    axes[0].legend(loc="upper left", fontsize=13)
    save(fig, "s_error_month")


# ---------------- 기온 정보의 가치 ----------------
def s_weather_value():
    s = pd.read_csv(NAT / "summary_all.csv")
    s = s[(s.window == "eval") & (s.model == "앙상블")]
    fig, ax = plt.subplots(figsize=(8.0, 4.9), layout="constrained")
    for i, ser in enumerate(["city", "power", "total"]):
        a = s[(s.series == ser) & (s["info"] == "ex_ante")]["all"].iloc[0]
        p = s[(s.series == ser) & (s["info"] == "ex_post")]["all"].iloc[0]
        ax.bar(i - 0.2, a, width=0.38, color=SER_C[ser])
        ax.bar(i + 0.2, p, width=0.38, color=SER_C[ser], alpha=0.35)
        ax.text(i - 0.2, a + 0.2, f"{a:.1f}", ha="center", fontsize=14, fontweight="bold")
        ax.text(i + 0.2, p + 0.2, f"{p:.1f}", ha="center", fontsize=14)
        ax.annotate("", xy=(i + 0.2, p + 1.0), xytext=(i - 0.05, a + 1.0),
                    arrowprops=dict(arrowstyle="->", color=INK2, lw=1.4))
        ax.text(i, max(a, p) + 1.55, f"−{(a - p) / a * 100:.0f}%", ha="center", fontsize=15, fontweight="bold",
                color=INK)
    ax.set_xticks(range(3), ["도시가스용", "발전용", "합계"], fontsize=14)
    ax.set_ylabel("MAPE (%), 1~12개월 평균")
    ax.set_ylim(0, 13)
    ax.grid(axis="x", visible=False)
    ax.legend([Patch(color=MUTED), Patch(color=MUTED, alpha=0.35)], ["사전예측 (평년 기온)", "사후예측 (실제 기온)"],
              loc="upper left", fontsize=13)
    save(fig, "s_weather_value")


# ---------------- 예측구간 적중률 ----------------
def s_intervals():
    it = pd.read_csv(NAT / "intervals.csv")
    it = it[it.series == "total"]
    rows = [("Chronos-2(공변량) 자체", "Chronos-2 + 공변량", "native"), ("TimesFM 2.5 자체", "TimesFM 2.5", "native"),
            ("OLS(√Y) 보정", "회귀 √Y", "conformal"), ("SARIMAX 보정", "SARIMAX", "conformal"),
            ("Chronos-2(공변량) 보정", "Chronos-2 + 공변량", "conformal"), ("Ensemble 보정", "앙상블", "conformal")]
    fig, ax = plt.subplots(figsize=(8.0, 4.9), layout="constrained")
    for i, (lab, m, me) in enumerate(rows[::-1]):
        r = it[(it.model == m) & (it.method == me)].iloc[0]
        c = "#eda100" if me == "native" else CITY
        ax.barh(i, r.coverage, color=c, height=0.62)
        ax.text(r.coverage + 1, i, f"{r.coverage:.0f}%", va="center", fontsize=14, fontweight="bold")
    ax.set_yticks(range(len(rows)), [r[0] for r in rows[::-1]], fontsize=13)
    ax.axvline(80, color=INK, ls="--", lw=1.6)
    ax.text(80.5, len(rows) - 0.45, "명목 80%", fontsize=13, color=INK)
    ax.set_xlim(0, 108)
    ax.set_xlabel("실제값이 80% 구간 안에 든 비율 (%), 합계, 2023~2025")
    ax.grid(axis="y", visible=False)
    fig.legend([Patch(color="#eda100"), Patch(color=CITY)], ["자체 = 모델이 낸 분위수", "보정 = 검증 오차로 만든 구간 (conformal)"],
               loc="outside lower center", ncol=2, fontsize=13)
    save(fig, "s_intervals")


# ---------------- SHAP ----------------
FEAT_KO = {"h": "예측 시계 h", "msin": "달 (sin)", "mcos": "달 (cos)", "hdd": "목표월 HDD", "cdd": "목표월 CDD",
           "lag12": "1년 전 같은 달 수요", "last3": "최근 3개월 평균 수요", "log_cpi": "도시가스 요금 지수",
           "coal_cap": "석탄 상한제 기간", "workdays": "영업일 수"}


def s_shap():
    sh = pd.read_csv(NAT / "shap.csv")
    fig, axes = plt.subplots(1, 2, figsize=(12.1, 4.4), layout="constrained")
    for ax, ser in zip(axes, ["city", "power"]):
        r = sh[sh.series == ser].sort_values("share").tail(6)
        ax.barh(range(len(r)), r.share, color=SER_C[ser], height=0.62)
        for i, v in enumerate(r.share):
            ax.text(v + 1, i, f"{v:.0f}%", va="center", fontsize=14, fontweight="bold" if i == len(r) - 1 else None)
        ax.set_yticks(range(len(r)), [FEAT_KO[f] for f in r.feature], fontsize=13)
        ax.set_xlim(0, 85)
        ax.set_xlabel("평균 |SHAP| 비중 (%)")
        ax.set_title(SER_KO[ser], color=SER_C[ser])
        ax.grid(axis="y", visible=False)
    save(fig, "s_shap")


# ---------------- 계층 예측 ----------------
def s_hier():
    s = pd.read_csv(PROV / "summary.csv")
    models = ["계절 naive", "ETS", "Chronos-2 + 공변량", "회귀 √Y"]
    methods = [("기본", "전국 직접", "o", "white", INK), ("상향식", "상향식 (시도 합)", "o", INK, INK),
               ("하향식", "하향식", "^", MUTED, MUTED), ("MinT", "MinT 조정", "D", BLUES[4], BLUES[4])]
    fig, ax = plt.subplots(figsize=(12.1, 4.4), layout="constrained")
    for i, m in enumerate(models):
        vals = s[(s.model == m) & (s.level == "전국")].set_index("method")["all"]
        ax.plot([vals.min(), vals.max()], [i, i], color=GRID, lw=4, zorder=1)
        for k, lab, mk, fc, ec in methods:
            ax.scatter(vals[k], i, marker=mk, s=130, facecolor=fc, edgecolor=ec, lw=2, zorder=3 if k != "기본" else 4,
                       label=lab if i == 0 else None)
    ax.set_yticks(range(len(models)), [SHORT[m] for m in models], fontsize=14)
    ax.set_xlabel("전국 MAPE (%), 1~12개월 평균, 목표월 2020~2022")
    ax.grid(axis="y", visible=False)
    h, l = ax.get_legend_handles_labels()
    fig.legend(h, l, loc="outside lower center", ncol=4, fontsize=13)
    save(fig, "s_hier")


# ---------------- 2026년 표본 외 ----------------
def s_hold():
    d = nat()
    p = pd.read_csv(NAT / "all_predictions.csv")
    fm = pd.read_csv(NAT / "foundation.csv")
    origin = "2025-12"
    fig, axes = plt.subplots(1, 2, figsize=(12.1, 3.95), layout="constrained")
    for ax, ser in zip(axes, ["city", "power"]):
        hist = d[(d.month >= "2024-07") & (d.month <= "2026-09")]
        band = fm[(fm.name == ser) & (fm.origin == origin) & (fm.model == "Chronos-2 + 공변량") & (fm["info"] == "ex_ante")
                  & (fm.month <= "2026-09")]
        ax.fill_between(pd.to_datetime(band.month + "-01"), band.lo, band.hi, color=FMC, alpha=0.15, lw=0)
        q = p[(p.series == ser) & (p.model == "앙상블") & (p.origin == origin) & (p["info"] == "ex_ante")].sort_values("month")
        sn = p[(p.series == ser) & (p.model == "계절 naive") & (p.origin == origin) & (p["info"] == "ex_ante")].sort_values("month")
        ax.plot(pd.to_datetime(sn.month + "-01"), sn.pred, color=MUTED, ls="--", lw=2)
        ax.plot(pd.to_datetime(q.month + "-01"), q.pred, color=NAVY, lw=3)
        ax.plot(hist.date, hist[ser], color=INK, lw=2.4, zorder=5)
        ax.axvline(pd.Timestamp("2025-12-15"), color=MUTED, lw=1)
        ax.text(pd.Timestamp("2025-12-01"), ax.get_ylim()[0] if False else 60, "예측 시점\n2025.12", fontsize=11,
                color=INK2, ha="right", va="bottom")
        ax.set_title(SER_KO[ser], color=SER_C[ser])
        ax.set_ylabel("월 공급량 (천 톤)")
        ax.set_ylim(0, None)
        ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[1, 7]))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y.%m"))
        ax.grid(axis="x", visible=False)
        if ser == "power":
            for mo in ["2026-07", "2026-08"]:
                a = d[d.month == mo][ser].iloc[0]
                f = q[q.month == mo].pred.iloc[0]
                x = pd.Timestamp(mo + "-01")
                ax.annotate("", xy=(x, a - 20), xytext=(x, f + 20),
                            arrowprops=dict(arrowstyle="<->", color="#c0392b", lw=1.8))
            a7 = d[d.month == "2026-07"][ser].iloc[0]
            f7 = q[q.month == "2026-07"].pred.iloc[0]
            ax.text(pd.Timestamp("2025-05-01"), 2110, f"7월 실제 {a7:,.0f}\n예측 {f7:,.0f} ({(f7 - a7) / a7 * 100:+.0f}%)",
                    fontsize=13, color="#c0392b", ha="center", va="top")
            ax.set_ylim(0, 2150)
    handles = [Line2D([], [], color=INK, lw=2.4), Line2D([], [], color=NAVY, lw=3),
               Line2D([], [], color=MUTED, lw=2, ls="--"), Patch(color=FMC, alpha=0.25)]
    fig.legend(handles, ["실제", "Ensemble 예측", "Seasonal Naive", "Chronos-2 80% 구간"], loc="outside lower center",
               ncol=4, fontsize=13)
    save(fig, "s_hold")


# ---------------- 6개국 ----------------
def s_six():
    N = json.loads((ROOT.parent / "multicountry" / "report" / "numbers.json").read_text(encoding="utf-8"))
    names = {"DE": "독일", "IT": "이탈리아", "FR": "프랑스", "ES": "스페인", "NL": "네덜란드", "KR": "한국"}
    geos = sorted(N["r5"], key=lambda g: N["r5"][g]["hdd10_post"])
    fig, axes = plt.subplots(1, 2, figsize=(12.1, 4.4), layout="constrained")
    a = axes[0]
    for i, g in enumerate(geos):
        pre, post = N["r5"][g]["hdd10_pre"], N["r5"][g]["hdd10_post"]
        col = NAVY if g == "KR" else BLUES[3]
        a.plot([pre, post], [i, i], color=GRID, lw=3, zorder=1)
        a.scatter(pre, i, s=80, facecolor="white", edgecolor=col, lw=2, zorder=3, label="2022년 3월 이전" if i == 0 else None)
        a.scatter(post, i, s=80, color=col, zorder=3, label="2022년 3월 이후" if i == 0 else None)
    a.set_yticks(range(len(geos)), [names[g] for g in geos], fontsize=14)
    a.set_xlabel("HDD 10 증가당 수요 증가율 (%)")
    a.set_title("난방 민감도")
    a.legend(loc="lower right", fontsize=12)
    a.grid(axis="y", visible=False)
    b = axes[1]
    main = N["main"]["ex_post"]
    best = {g: min(v[g] for v in main.values() if g in v and v[g] is not None) for g in geos}
    bench = {g: main["회귀 √Y~HDD+가격"][g] for g in geos}
    for i, g in enumerate(geos):
        col = NAVY if g == "KR" else BLUES[3]
        b.plot([best[g], bench[g]], [i, i], color=GRID, lw=3, zorder=1)
        b.scatter(bench[g], i, s=80, color=MUTED, zorder=3, label="기준 회귀" if i == 0 else None)
        b.scatter(best[g], i, s=80, color=col, zorder=3, label="최고 모델" if i == 0 else None)
    b.set_yticks(range(len(geos)), [names[g] for g in geos], fontsize=14)
    b.set_xlabel("1개월 앞 MAPE (%), 2023~2025")
    b.set_title("예측 오차")
    b.legend(loc="lower right", fontsize=12)
    b.grid(axis="y", visible=False)
    for ax in axes:
        for lab in ax.get_yticklabels():
            if lab.get_text() == "한국":
                lab.set_fontweight("bold")
                lab.set_color(NAVY)
    save(fig, "s_six")


# ---------------- 표지 배경 (투명, 축 없음) ----------------
def s_title():
    d = nat()
    d = d[d.total.notna()]
    fig, ax = plt.subplots(figsize=(7.0, 3.6))
    ax.plot(d.date, d.city, color="#6da7ec", lw=2.4, alpha=0.9)
    ax.plot(d.date, d.power, color="#f3a27a", lw=2.4, alpha=0.9)
    ax.axis("off")
    ax.set_ylim(0, 3200)
    fig.subplots_adjust(0, 0, 1, 1)
    fig.savefig(OUT / "s_title.png", transparent=True)
    plt.close(fig)
    print("  slides/s_title")


# ---------------- 자료 점검: 2019년 도시가스용 복원 ----------------
def s_fix2019():
    raw = pd.read_csv(sorted((ROOT / "data" / "raw").glob("*/kogas_national.csv"))[-1])
    r = raw[raw["용도"] == "도시가스"].assign(month=lambda x: x["연도"].astype(str) + "-" + x["월"].astype(str).str.zfill(2))
    r = r.set_index("month")["공급량"] / 1000
    d = nat().set_index("month")
    m = [f"{y}-{k:02d}" for y in (2018, 2019, 2020) for k in range(1, 13)]
    x = pd.to_datetime([k + "-01" for k in m])
    fig, ax = plt.subplots(figsize=(5.6, 3.3), layout="constrained")
    ax.plot(x, r.reindex(m).values, color="#c0392b", lw=2, ls="--", label="원자료")
    ax.plot(x, d.city.reindex(m).values, color=CITY, lw=2.6, label="복원값")
    ax.annotate("2019년 7월" + chr(10) + "원자료 1,750천 톤", (pd.Timestamp("2019-07-01"), r["2019-07"]), xytext=(pd.Timestamp("2019-05-01"), 2450),
                textcoords="data", fontsize=11, color="#c0392b", ha="center", va="center",
                arrowprops=dict(arrowstyle="->", color="#c0392b", lw=1.2))
    ax.set_ylim(0, 3300)
    ax.set_ylabel("천 톤", fontsize=12)
    ax.tick_params(labelsize=11)
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.grid(axis="x", visible=False)
    ax.legend(loc="upper right", fontsize=11, ncol=2)
    save(fig, "s_fix2019")


ALL = {f.__name__: f for f in [s_demand, s_weather_scatter, s_province, s_horizon, s_models, s_rank, s_error_month,
                                s_weather_value, s_intervals, s_shap, s_hier, s_hold, s_six, s_title, s_fix2019]}

if __name__ == "__main__":
    for k in (sys.argv[1:] or ALL):
        ALL[k]()
