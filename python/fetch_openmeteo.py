"""이탈리아·프랑스·스페인·네덜란드 2026년 HDD·CDD: Open-Meteo 과거 기상(ERA5 재분석) 도시 일평균기온 → Eurostat에 보정.

Eurostat nrg_chdd_m은 2025-12에서 끝나서 2026년 표본 외 검증에 쓸 HDD가 없다. 독일은 DWD 관측소(fetch_dwd.py),
나머지 유럽 4개국은 여기서 만든다. 키가 필요 없다 (https://open-meteo.com, 비상업적 이용 무료).
  1) 나라별 주요 6~8개 도시의 일평균기온(temperature_2m_mean)
  2) 도시별 Eurostat 방식 HDD = Σ(18 − Tm) (Tm ≤ 15°C), CDD = Σ(Tm − 21) (Tm ≥ 24°C) → 도시 단순평균
  3) 2014-01~2025-12 겹치는 기간에 Eurostat ~ Open-Meteo 선형회귀로 보정식을 만들고 2026년에 적용

출력: data/raw/<호출일>/openmeteo_daily.csv, data/interim/openmeteo_degree_days.csv
실행: python python/fetch_openmeteo.py
"""
import datetime as dt
import time

import pandas as pd
import requests
import statsmodels.api as sm

from config import INTERIM, RAW

URL = "https://archive-api.open-meteo.com/v1/archive"
CITIES = {
    "IT": {"Milano": (45.46, 9.19), "Roma": (41.90, 12.50), "Napoli": (40.85, 14.27), "Torino": (45.07, 7.69),
           "Bologna": (44.49, 11.34), "Firenze": (43.77, 11.25), "Venezia": (45.44, 12.33), "Palermo": (38.12, 13.36)},
    "FR": {"Paris": (48.86, 2.35), "Lyon": (45.76, 4.84), "Marseille": (43.30, 5.37), "Lille": (50.63, 3.06),
           "Toulouse": (43.60, 1.44), "Bordeaux": (44.84, -0.58), "Nantes": (47.22, -1.55), "Strasbourg": (48.57, 7.75)},
    "ES": {"Madrid": (40.42, -3.70), "Barcelona": (41.39, 2.17), "Valencia": (39.47, -0.38), "Sevilla": (37.39, -5.98),
           "Bilbao": (43.26, -2.93), "Zaragoza": (41.65, -0.89), "Valladolid": (41.65, -4.72), "Malaga": (36.72, -4.42)},
    "NL": {"Amsterdam": (52.37, 4.90), "Rotterdam": (51.92, 4.48), "Den Haag": (52.08, 4.30), "Utrecht": (52.09, 5.12),
           "Eindhoven": (51.44, 5.48), "Groningen": (53.22, 6.57)},
}
START = "2013-01-01"
CAL = ("2014-01", "2025-12")


def fetch(geo, cities, end):
    params = {"latitude": ",".join(str(c[0]) for c in cities.values()),
              "longitude": ",".join(str(c[1]) for c in cities.values()),
              "start_date": START, "end_date": end, "daily": "temperature_2m_mean", "timezone": "auto"}
    for i in range(4):
        r = requests.get(URL, params=params, timeout=180)
        if r.status_code == 200:
            break
        time.sleep(10 * (i + 1))
    r.raise_for_status()
    js = r.json()
    js = js if isinstance(js, list) else [js]
    frames = [pd.DataFrame({"geo": geo, "city": name, "date": loc["daily"]["time"],
                            "tm": loc["daily"]["temperature_2m_mean"]})
              for name, loc in zip(cities, js)]
    return pd.concat(frames, ignore_index=True)


def degree_days(daily):
    d = daily.copy()
    d["tm"] = pd.to_numeric(d.tm, errors="coerce")
    d["hdd"] = (18 - d.tm).where(d.tm <= 15, 0.0)
    d["cdd"] = (d.tm - 21).where(d.tm >= 24, 0.0)
    d["month"] = d.date.str[:7]
    m = d.dropna(subset=["tm"]).groupby(["geo", "city", "month"]).agg(hdd=("hdd", "sum"), cdd=("cdd", "sum"),
                                                                        n=("date", "size")).reset_index()
    m["days"] = m.month.map(lambda x: pd.Period(x).days_in_month)
    m = m[m.n == m.days]
    out = m.groupby(["geo", "month"]).agg(om_hdd=("hdd", "mean"), om_cdd=("cdd", "mean"),
                                          cities=("city", "nunique")).reset_index()
    ncity = {g: len(c) for g, c in CITIES.items()}
    return out[out.cities == out.geo.map(ncity)]


def main():
    end = (dt.date.today() - dt.timedelta(days=6)).isoformat()   # 과거 기상 자료는 약 5일 늦게 갱신
    daily = pd.concat([fetch(g, c, end) for g, c in CITIES.items()], ignore_index=True)
    today = dt.date.today().strftime("%Y%m%d")
    (RAW / today).mkdir(parents=True, exist_ok=True)
    daily.to_csv(RAW / today / "openmeteo_daily.csv", index=False, encoding="utf-8")
    dd = degree_days(daily)
    eu = pd.read_csv(INTERIM / "europe_long.csv", dtype={"month": str})
    eu = (eu[eu.series.isin(["hdd", "cdd"])].pivot_table(index=["geo", "month"], columns="series", values="value")
          .rename(columns={"hdd": "eurostat_hdd", "cdd": "eurostat_cdd"}).reset_index())
    dd = dd.merge(eu, on=["geo", "month"], how="left")
    parts = []
    for g, d in dd.groupby("geo"):
        d = d.copy()
        cal = d[(d.month >= CAL[0]) & (d.month <= CAL[1])]
        for v in ("hdd", "cdd"):
            m = sm.OLS(cal[f"eurostat_{v}"], sm.add_constant(cal[f"om_{v}"])).fit()
            d[f"{v}_cal"] = (m.params.iloc[0] + m.params.iloc[1] * d[f"om_{v}"]).clip(lower=0)
            fit = d.loc[cal.index]
            mae = (fit[f"{v}_cal"] - fit[f"eurostat_{v}"]).abs().mean()
            print(f"{g} {v.upper()} 보정: Eurostat = {m.params.iloc[0]:.2f} + {m.params.iloc[1]:.3f} × OM, "
                  f"R² {m.rsquared:.4f}, MAE {mae:.1f} ({len(cal)}개월)")
        parts.append(d)
    out = pd.concat(parts, ignore_index=True)
    out.to_csv(INTERIM / "openmeteo_degree_days.csv", index=False, encoding="utf-8")
    new = out[out.month > CAL[1]]
    print(f"저장: {INTERIM / 'openmeteo_degree_days.csv'} (2026: {new.month.min()}~{new.month.max()})")


if __name__ == "__main__":
    main()
