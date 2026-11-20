"""2026년 HDD·CDD 보정 공통 코드 (fetch_dwd.py, fetch_openmeteo.py).

Eurostat 월 HDD·CDD는 2025-12에서 끝나서, 2026년 값은 도시·관측소 일평균기온으로 계산해 Eurostat에 맞춘다.
Eurostat 값은 국토 전체(산간·내륙 포함)의 격자 기준이라, 도시 기온으로 계산한 HDD와의 관계가 직선 하나로 맞지 않는다.
여름에 도시 HDD는 0인데 Eurostat HDD는 0보다 크고, 그 크기가 달마다 다르다. 직선 하나로 보정하면 여름 값이
절편 하나로 쏠린다(이탈리아 6~9월이 모두 21.9). 그래서

  1) 도시 기온을 δ°C 낮춰 HDD를 계산한다 (δ = 0~4, 도시보다 서늘한 고지대·내륙을 근사)
  2) Eurostat = 월별 절편 + β × 도시 HDD 로 보정한다 (월 고정효과)
  3) δ는 2014~2025년에서 한 해씩 빼고 맞춘 뒤 그 해를 맞히는 교차검증 MAE로 고른다 (2026년 자료는 쓰지 않는다)

CDD는 δ 없이 같은 월 고정효과 보정을 쓴다.
"""
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

CAL = ("2014-01", "2025-12")
DELTAS = (0, 1, 2, 3, 4)


def monthly_dd(daily, unit, delta=0.0):
    """daily(unit, date, tm) → 단위(도시·관측소)별 월합의 단위 평균. 하루라도 빠진 달·단위는 뺀다."""
    d = daily.dropna(subset=["tm"]).copy()
    t = d.tm - delta
    d["hdd"] = (18 - t).where(t <= 15, 0.0)
    d["cdd"] = (d.tm - 21).where(d.tm >= 24, 0.0)
    d["month"] = d.date.astype(str).str[:7]
    m = d.groupby([unit, "month"]).agg(hdd=("hdd", "sum"), cdd=("cdd", "sum"), n=("date", "size")).reset_index()
    m["days"] = m.month.map(lambda x: pd.Period(x).days_in_month)
    m = m[m.n == m.days]
    out = m.groupby("month").agg(hdd=("hdd", "mean"), cdd=("cdd", "mean"), units=(unit, "nunique")).reset_index()
    return out[out.units == daily[unit].nunique()]


def _fit(df, linear=False):
    return smf.ols("y ~ x" if linear else "y ~ x + C(mm)", df).fit()


def _cv_mae(df, linear=False):
    """한 해씩 빼고 적합 → 그 해 예측 오차(MAE). 전체와 6~9월."""
    err = []
    for yr in sorted(df.yr.unique()):
        tr, te = df[df.yr != yr], df[df.yr == yr]
        p = np.clip(_fit(tr, linear).predict(te).to_numpy(), 0, None)
        err.append(pd.DataFrame({"mm": te.mm.to_numpy(), "e": np.abs(p - te.y.to_numpy())}))
    e = pd.concat(err)
    return e.e.mean(), e[e.mm.isin(["06", "07", "08", "09"])].e.mean()


def _frame(x, target):
    df = x.merge(target, on="month", how="left")
    df["mm"], df["yr"] = df.month.str[5:], df.month.str[:4].astype(int)
    return df


def calibrate(daily, unit, target, label):
    """daily(unit, date, tm), target(month, eurostat_hdd, eurostat_cdd) →
    month, raw_hdd, raw_cdd, eurostat_hdd, eurostat_cdd, hdd_cal, cdd_cal, delta."""
    res = {}
    for v in ("hdd", "cdd"):
        best = None
        for delta in (DELTAS if v == "hdd" else (0,)):
            x = monthly_dd(daily, unit, delta)[["month", v]].rename(columns={v: "x"})
            df = _frame(x, target.rename(columns={f"eurostat_{v}": "y"})[["month", "y"]])
            cal = df[(df.month >= CAL[0]) & (df.month <= CAL[1])].dropna(subset=["y"])
            mae, mae_s = _cv_mae(cal)
            if best is None or mae < best[1] - 1e-9:
                best = (delta, mae, mae_s, df, cal)
        delta, mae, mae_s, df, cal = best
        x0 = monthly_dd(daily, unit, 0)[["month", v]].rename(columns={v: "x"})
        lin, lin_s = _cv_mae(_frame(x0, target.rename(columns={f"eurostat_{v}": "y"})[["month", "y"]])
                             .pipe(lambda d: d[(d.month >= CAL[0]) & (d.month <= CAL[1])].dropna(subset=["y"])),
                             linear=True)
        f = _fit(cal)
        df[f"{v}_cal"] = np.clip(f.predict(df).to_numpy(), 0, None)
        print(f"{label} {v.upper()} 보정: 월 고정효과 + {f.params['x']:.3f} × 도시 {v.upper()}"
              + (f" (기온 −{delta}°C)" if v == "hdd" else "")
              + f", 교차검증 MAE {mae:.1f} (6~9월 {mae_s:.1f}) — 직선 보정은 {lin:.1f} ({lin_s:.1f})")
        res[v] = df.rename(columns={"x": f"raw_{v}", "y": f"eurostat_{v}"})[
            ["month", f"raw_{v}", f"eurostat_{v}", f"{v}_cal"]].assign(
            **({"delta": delta, "cv_mae": round(mae, 2), "cv_mae_linear": round(lin, 2)} if v == "hdd" else {}))
    return res["hdd"].merge(res["cdd"], on="month")
