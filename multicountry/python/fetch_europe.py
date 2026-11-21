"""유럽 5개국 월자료 수집: Eurostat(JSON-stat) + FRED(CSV).

원자료는 data/raw/<호출일>/ 에 그대로 저장하고,
정리한 long 형식(series, geo, month, value)은 data/interim/europe_long.csv 로 저장한다.

실행: python python/fetch_europe.py
"""
import datetime as dt
import io
import itertools
import json
import sys
import time

import pandas as pd
import requests

from config import EU_GEOS, INTERIM, RAW, START

EUROSTAT = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/{code}"
FRED = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}"

# (이름, 데이터셋, 고정 파라미터, 시작월)
EUROSTAT_SERIES = [
    ("gas_tj", "nrg_cb_gasm", {"nrg_bal": "IC_CAL_MG", "siec": "G3000", "unit": "TJ_GCV"}, START),
    ("hdd", "nrg_chdd_m", {"indic_nrg": "HDD", "unit": "NR"}, START),
    ("cdd", "nrg_chdd_m", {"indic_nrg": "CDD", "unit": "NR"}, START),
    ("hicp_gas", "prc_hicp_midx", {"coicop": "CP0452", "unit": "I15"}, START),
    ("ip", "sts_inpr_m", {"nace_r2": "B-D", "s_adj": "SCA", "unit": "I21", "indic_bt": "PRD"}, START),
    ("ip_chem", "sts_inpr_m", {"nace_r2": "C20", "s_adj": "SCA", "unit": "I21", "indic_bt": "PRD"}, START),
    ("nuclear_gwh", "nrg_cb_pem", {"siec": "N9000", "unit": "GWH"}, START),
    ("wind_gwh", "nrg_cb_pem", {"siec": "RA300", "unit": "GWH"}, START),
    # HICP 가스 ECOICOP ver.2 (2026년부터는 이 데이터셋만 갱신된다; prc_hicp_midx는 2025-12에서 끝남)
    ("hicp_gas_v2", "prc_hicp_minr", {"coicop18": "CP0452", "unit": "I15"}, START),
]

FRED_SERIES = {
    "ttf_usd": "PNGASEUUSDM",     # EU 천연가스 도매가 (USD/MMBtu)
    "lng_asia_usd": "PNGASJPUSDM",  # 아시아 LNG (USD/MMBtu)
    "coal_usd": "PCOALAUUSDM",    # 호주 석탄 (USD/t)
}


def get(url, params=None, tries=4):
    for i in range(tries):
        try:
            r = requests.get(url, params=params, timeout=90)
            r.raise_for_status()
            return r
        except requests.RequestException as e:
            if i == tries - 1:
                raise
            print(f"  재시도 {i + 1}: {e}")
            time.sleep(3 * (i + 1))


def parse_jsonstat(js):
    """JSON-stat 2.0 → long DataFrame (차원별 코드 + value)."""
    ids, sizes = js["id"], js["size"]
    cats = []
    for d in ids:
        idx = js["dimension"][d]["category"]["index"]
        codes = sorted(idx, key=idx.get) if isinstance(idx, dict) else list(idx)
        cats.append(codes)
    values = js.get("value", {})
    if isinstance(values, list):
        values = {str(i): v for i, v in enumerate(values) if v is not None}
    status = js.get("status", {}) or {}
    rows = []
    for flat, combo in enumerate(itertools.product(*cats)):
        v = values.get(str(flat))
        if v is None:
            continue
        rec = dict(zip(ids, combo))
        rec["value"] = v
        rec["flag"] = status.get(str(flat), "") if isinstance(status, dict) else ""
        rows.append(rec)
    return pd.DataFrame(rows)


def fetch_eurostat(outdir, only=None):
    frames = []
    for name, code, fixed, since in EUROSTAT_SERIES:
        if only and name not in only:
            continue
        params = [("geo", g) for g in EU_GEOS] + list(fixed.items())
        params += [("sinceTimePeriod", since), ("lang", "EN")]
        print(f"Eurostat {code} → {name}")
        js = get(EUROSTAT.format(code=code), params=params).json()
        (outdir / f"eurostat_{name}.json").write_text(json.dumps(js), encoding="utf-8")
        df = parse_jsonstat(js)
        if df.empty:
            print(f"  경고: {name} 값 없음")
            continue
        df = df.rename(columns={"time": "month"})[["geo", "month", "value", "flag"]]
        df["series"] = name
        df["source_updated"] = js.get("updated", "")
        frames.append(df)
        print(f"  {len(df)}행, {df.month.min()}~{df.month.max()}, 국가 {sorted(df.geo.unique())}")
    return pd.concat(frames, ignore_index=True)


def fetch_fred(outdir):
    frames = []
    for name, sid in FRED_SERIES.items():
        print(f"FRED {sid} → {name}")
        text = get(FRED.format(sid=sid)).text
        (outdir / f"fred_{sid}.csv").write_text(text, encoding="utf-8")
        df = pd.read_csv(io.StringIO(text))
        df.columns = ["date", "value"]
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        df = df.dropna()
        df["month"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m")
        df = df[df.month >= START]
        df["geo"] = "WORLD"
        df["series"] = name
        df["flag"] = ""
        df["source_updated"] = ""
        frames.append(df[["geo", "month", "value", "flag", "series", "source_updated"]])
        print(f"  {len(df)}행, {df.month.min()}~{df.month.max()}")
    return pd.concat(frames, ignore_index=True)


def main():
    """인자 없이: 전부 다시 받는다. 계열 이름을 주면 그 Eurostat 계열만 받아 기존 파일에 끼워 넣는다
    (예: python fetch_europe.py wind_gwh) — 다른 계열이 새 수정치로 바뀌지 않게 할 때 쓴다."""
    only = sys.argv[1:]
    today = dt.date.today().strftime("%Y%m%d")
    outdir = RAW / today
    outdir.mkdir(parents=True, exist_ok=True)
    out = INTERIM / "europe_long.csv"
    if only:
        new = fetch_eurostat(outdir, only)
        new["fetched"] = today
        old = pd.read_csv(out, dtype={"month": str})
        long = pd.concat([old[~old.series.isin(only)], new], ignore_index=True)
    else:
        long = pd.concat([fetch_eurostat(outdir), fetch_fred(outdir)], ignore_index=True)
        long["fetched"] = today
    long = long[["series", "geo", "month", "value", "flag", "source_updated", "fetched"]]
    long.to_csv(out, index=False, encoding="utf-8")
    print(f"\n저장: {out} ({len(long)}행)")


if __name__ == "__main__":
    main()
