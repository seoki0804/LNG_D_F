"""독일 2026년 HDD·CDD: 독일 기상청(DWD) 일평균기온 → Eurostat 방식 도일 → Eurostat 값에 맞춰 보정.

Eurostat nrg_chdd_m은 2025-12에서 끝나서 2026년 표본 외 검증에 쓸 HDD가 없다 (계획서 보완 조치 1).
  1) DWD Open Data 일별 기후자료(KL)의 일평균기온(TMK), 주요 12개 도시 관측소
  2) 관측소별 Eurostat 방식 HDD = Σ(18 − Tm) (Tm ≤ 15°C), CDD = Σ(Tm − 21) (Tm ≥ 24°C) → 12개 관측소 단순평균
  3) 2014-01~2025-12에서 Eurostat에 맞춘 보정식(월 고정효과, 기온 오프셋 δ는 연도별 교차검증으로 선택)을 2026년에 적용
     — 보정 방법은 degree_days.py 참고. 저장한 원자료로 다시: python python/fetch_dwd.py --raw 20261121
     (Eurostat는 NUTS3 지역 인구가중이라 도시 관측소 평균과 수준이 다르다)

출력: data/raw/<호출일>/dwd_daily.csv, data/interim/dwd_de_degree_days.csv
실행: python python/fetch_dwd.py
"""
import datetime as dt
import io
import re
import sys
import zipfile

import numpy as np
import pandas as pd
import requests
from config import INTERIM, RAW
from degree_days import calibrate

BASE = "https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/daily/kl/"
STATIONS = {433: "Berlin-Tempelhof", 1975: "Hamburg-Fuhlsbüttel", 3379: "München-Stadt", 1420: "Frankfurt/Main",
            4931: "Stuttgart-Echterdingen", 1078: "Düsseldorf", 1303: "Essen-Bredeney", 2932: "Leipzig/Halle",
            1048: "Dresden-Klotzsche", 2014: "Hannover", 3668: "Nürnberg", 691: "Bremen"}
START = "2013-01-01"


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


def main():
    if "--raw" in sys.argv:
        daily = pd.read_csv(RAW / sys.argv[sys.argv.index("--raw") + 1] / "dwd_daily.csv", parse_dates=["date"])
    else:
        today = dt.date.today().strftime("%Y%m%d")
        daily = fetch_daily()
        (RAW / today).mkdir(parents=True, exist_ok=True)
        daily.to_csv(RAW / today / "dwd_daily.csv", index=False, encoding="utf-8")
    d = daily.sort_values(["stn", "date"]).copy()
    d["tm"] = d.groupby("stn").TMK.transform(lambda s: s.interpolate(limit=3))   # 관측소 결측 3일 이내는 보간
    d["date"] = d.date.dt.strftime("%Y-%m-%d")

    eu = pd.read_csv(INTERIM / "europe_long.csv", dtype={"month": str})
    eu = (eu[(eu.geo == "DE") & eu.series.isin(["hdd", "cdd"])].pivot(index="month", columns="series", values="value")
          .rename(columns={"hdd": "eurostat_hdd", "cdd": "eurostat_cdd"}).reset_index())
    dd = calibrate(d[["stn", "date", "tm"]], "stn", eu, "DE")
    dd.to_csv(INTERIM / "dwd_de_degree_days.csv", index=False, encoding="utf-8")
    new = dd[dd.month > "2025-12"]
    print(f"저장: {INTERIM / 'dwd_de_degree_days.csv'} (보정 HDD 2026: {new.month.min()}~{new.month.max()})")
    print(new[["month", "raw_hdd", "hdd_cal", "cdd_cal"]].round(1).to_string(index=False))


if __name__ == "__main__":
    main()
