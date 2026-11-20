"""독일 2026년 HDD·CDD: 독일 기상청(DWD) 일평균기온 → Eurostat 방식 도일 → Eurostat 값에 맞춰 보정.

Eurostat nrg_chdd_m은 2025-12에서 끝나서 2026년 표본 외 검증에 쓸 HDD가 없다 (계획서 보완 조치 1).
  1) DWD Open Data 일별 기후자료(KL)의 일평균기온(TMK), 주요 12개 도시 관측소
  2) 관측소별 Eurostat 방식 HDD = Σ(18 − Tm) (Tm ≤ 15°C), CDD = Σ(Tm − 21) (Tm ≥ 24°C) → 12개 관측소 단순평균
  3) 2014-01~2025-12 겹치는 기간에 Eurostat HDD ~ DWD HDD 선형회귀로 보정식을 만들고 2026년에 적용
     (Eurostat는 NUTS3 지역 인구가중이라 도시 관측소 평균과 수준이 다르다)

출력: data/raw/<호출일>/dwd_daily.csv, data/interim/dwd_de_degree_days.csv
실행: python python/fetch_dwd.py
"""
import datetime as dt
import io
import re
import zipfile

import numpy as np
import pandas as pd
import requests
import statsmodels.api as sm

from config import INTERIM, RAW

BASE = "https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/daily/kl/"
STATIONS = {433: "Berlin-Tempelhof", 1975: "Hamburg-Fuhlsbüttel", 3379: "München-Stadt", 1420: "Frankfurt/Main",
            4931: "Stuttgart-Echterdingen", 1078: "Düsseldorf", 1303: "Essen-Bredeney", 2932: "Leipzig/Halle",
            1048: "Dresden-Klotzsche", 2014: "Hannover", 3668: "Nürnberg", 691: "Bremen"}
START = "2013-01-01"
CAL = ("2014-01", "2025-12")


def read_zip(url):
    z = zipfile.ZipFile(io.BytesIO(requests.get(url, timeout=120).content))
    name = next(n for n in z.namelist() if n.startswith("produkt_klima_tag"))
    df = pd.read_csv(z.open(name), sep=";", skipinitialspace=True, dtype={"MESS_DATUM": str})
    df.columns = [c.strip() for c in df.columns]
    df = df[["STATIONS_ID", "MESS_DATUM", "TMK"]].rename(columns={"STATIONS_ID": "stn", "MESS_DATUM": "date"})
    df["date"] = pd.to_datetime(df.date, format="%Y%m%d")
    df["TMK"] = df.TMK.where(df.TMK > -999)
    return df[df.date >= START]


def fetch_daily():
    listing = requests.get(BASE + "historical/", timeout=120).text
    frames = []
    for sid, name in STATIONS.items():
        hist = re.search(rf'href="(tageswerte_KL_{sid:05d}_\d+_\d+_hist\.zip)"', listing)
        parts = [read_zip(BASE + "recent/" + f"tageswerte_KL_{sid:05d}_akt.zip")]
        if hist:
            parts.insert(0, read_zip(BASE + "historical/" + hist.group(1)))
        d = pd.concat(parts).drop_duplicates("date", keep="first")   # 겹치면 품질검사를 마친 historical 우선
        frames.append(d)
        print(f"  {name}: {d.date.min():%Y-%m-%d}~{d.date.max():%Y-%m-%d}, 결측 {d.TMK.isna().sum()}일", flush=True)
    return pd.concat(frames, ignore_index=True)


def degree_days(daily):
    d = daily.sort_values(["stn", "date"]).copy()
    d["TMK"] = d.groupby("stn").TMK.transform(lambda s: s.interpolate(limit=3))
    d = d.dropna(subset=["TMK"])
    d["hdd"] = (18 - d.TMK).where(d.TMK <= 15, 0.0)
    d["cdd"] = (d.TMK - 21).where(d.TMK >= 24, 0.0)
    d["month"] = d.date.dt.strftime("%Y-%m")
    m = d.groupby(["stn", "month"]).agg(hdd=("hdd", "sum"), cdd=("cdd", "sum"), n=("date", "size")).reset_index()
    m["days"] = m.month.map(lambda x: pd.Period(x).days_in_month)
    m = m[m.n == m.days]
    out = m.groupby("month").agg(dwd_hdd=("hdd", "mean"), dwd_cdd=("cdd", "mean"), stations=("stn", "nunique"))
    return out[out.stations == len(STATIONS)].reset_index()


def main():
    today = dt.date.today().strftime("%Y%m%d")
    daily = fetch_daily()
    (RAW / today).mkdir(parents=True, exist_ok=True)
    daily.to_csv(RAW / today / "dwd_daily.csv", index=False, encoding="utf-8")
    dd = degree_days(daily)

    eu = pd.read_csv(INTERIM / "europe_long.csv", dtype={"month": str})
    eu = eu[eu.geo == "DE"].pivot(index="month", columns="series", values="value")[["hdd", "cdd"]]
    dd = dd.merge(eu.rename(columns={"hdd": "eurostat_hdd", "cdd": "eurostat_cdd"}).reset_index(),
                  on="month", how="left")
    cal = dd[(dd.month >= CAL[0]) & (dd.month <= CAL[1])]
    for v in ("hdd", "cdd"):
        m = sm.OLS(cal[f"eurostat_{v}"], sm.add_constant(cal[f"dwd_{v}"])).fit()
        dd[f"{v}_cal"] = (m.params.iloc[0] + m.params.iloc[1] * dd[f"dwd_{v}"]).clip(lower=0)
        fit = dd.loc[cal.index]
        mae = (fit[f"{v}_cal"] - fit[f"eurostat_{v}"]).abs().mean()
        print(f"{v.upper()} 보정: Eurostat = {m.params.iloc[0]:.2f} + {m.params.iloc[1]:.3f} × DWD, "
              f"R² {m.rsquared:.4f}, MAE {mae:.1f} ({CAL[0]}~{CAL[1]}, {len(cal)}개월)")
    dd.to_csv(INTERIM / "dwd_de_degree_days.csv", index=False, encoding="utf-8")
    new = dd[dd.month > CAL[1]]
    print(f"저장: {INTERIM / 'dwd_de_degree_days.csv'} (보정 HDD 2026: {new.month.min()}~{new.month.max()})")
    print(new[["month", "dwd_hdd", "hdd_cal", "cdd_cal"]].round(1).to_string(index=False))


if __name__ == "__main__":
    main()
