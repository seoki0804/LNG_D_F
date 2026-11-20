"""국가별 월 분석 데이터셋 생성 (유럽 5개국 + 한국).

입력: data/interim/europe_long.csv (fetch_europe.py), data/interim/korea_long.csv (fetch_korea.py)
출력: data/processed/<geo>.csv, data/processed/panel.csv

모델이 쓰는 공통 열 (국가마다 원자료가 달라도 이름은 같다)
  y                 수요 (유럽: PJ, Eurostat 내수 소비 GCV / 한국: 천 톤, KOGAS 도시가스용+발전용 공급량)
  y_unit            y의 단위
  hdd, cdd          난방·냉방 도일 (유럽: Eurostat / 한국: 기상청 ASOS 7개 도시 일평균기온으로 같은 방식 계산)
  price_retail      소비자 가스 요금 지수 (유럽: HICP CP0452, 2015=100 / 한국: CPI 도시가스, 2020=100)
  price_wholesale   도매가격 USD/MMBtu, 같은 달 (유럽: FRED EU 가스 / 한국: FRED 아시아 LNG)
  ip                산업생산 계절조정 (유럽: B-D, 2021=100 / 한국: 광공업 총지수, 2020=100)
  workdays, days    영업일 수(월~금 − 국가 공휴일), 달의 일수

국가별 추가 열
  유럽: gas_tj, gas_pj, gas_flag, hicp_gas, ip_chem, nuclear_gwh, wind_gwh, ttf_usd, lng_asia_usd, coal_usd
  독일: slp_pj, rlm_pj, the_total_pj (THE 부문별 소비, 2021-10~, fetch_the.py)
  hdd_source: eurostat 또는 dwd_calibrated (독일 2026~, Eurostat HDD 공개 전 DWD 보정값, fetch_dwd.py)
  price_retail은 2026~ ECOICOP ver.2 가스 지수(prc_hicp_minr)를 2025-12 비율로 이어 붙인 값
  한국: gas_kt, gas_city_kt, gas_power_kt, cpi_city_gas, lng_asia_usd, ttf_usd, coal_usd

실행: python python/build_dataset.py
"""
import holidays
import numpy as np
import pandas as pd

from config import EU_GEOS, INTERIM, PROCESSED, START, END

COUNTRY_SERIES = ["gas_tj", "hdd", "cdd", "hicp_gas", "hicp_gas_v2", "ip", "ip_chem", "nuclear_gwh", "wind_gwh"]
WORLD_SERIES = ["ttf_usd", "lng_asia_usd", "coal_usd"]
KR_START = "2006-01"   # 한국 수요는 2016-01부터. 그 앞 10년은 평년 HDD 계산용 기온·가격만 둔다.
COMMON = ["geo", "month", "y", "y_unit", "hdd", "cdd", "price_retail", "price_wholesale", "ip",
          "workdays", "days"]


def calendar_features(geo, months):
    years = sorted({int(m[:4]) for m in months})
    hol = holidays.country_holidays(geo, years=years)
    rows = []
    for m in months:
        days = pd.date_range(m + "-01", periods=pd.Period(m).days_in_month, freq="D")
        weekdays = days[days.dayofweek < 5]
        work = sum(1 for d in weekdays if d.date() not in hol)
        rows.append({"month": m, "workdays": work, "days": len(days)})
    return pd.DataFrame(rows)


def months_range(a, b):
    return pd.period_range(a, b, freq="M").strftime("%Y-%m").tolist()


def world_prices():
    long = pd.read_csv(INTERIM / "europe_long.csv", dtype={"month": str})
    return (long[long.series.isin(WORLD_SERIES)]
            .pivot(index="month", columns="series", values="value").reset_index())


def splice_hicp(df):
    """prc_hicp_midx(~2025-12) 뒤에 prc_hicp_minr(ECOICOP ver.2)를 마지막 겹치는 달의 비율로 이어 붙인다."""
    out = df["hicp_gas"].copy()
    if "hicp_gas_v2" not in df:
        return out
    both = df.dropna(subset=["hicp_gas", "hicp_gas_v2"])
    if both.empty:
        return out
    ratio = both.hicp_gas.iloc[-1] / both.hicp_gas_v2.iloc[-1]
    after = (df.month > both.month.iloc[-1]) & df.hicp_gas.isna()
    out[after] = df.loc[after, "hicp_gas_v2"] * ratio
    return out


def build_europe(geo, long, world):
    sub = long[(long.geo == geo) & long.series.isin(COUNTRY_SERIES)]
    wide = sub.pivot(index="month", columns="series", values="value").reset_index()
    flags = sub[sub.series == "gas_tj"][["month", "flag"]].rename(columns={"flag": "gas_flag"})
    wide = wide.merge(flags, on="month", how="left")
    last = wide.loc[wide.gas_tj.notna(), "month"].max()
    months = months_range(START, last)
    df = (pd.DataFrame({"month": months}).merge(wide, on="month", how="left")
          .merge(world, on="month", how="left")
          .merge(calendar_features(geo, months), on="month", how="left"))
    df["geo"] = geo
    df["gas_flag"] = df["gas_flag"].fillna("")
    bad = df["gas_tj"] <= 0   # 0 이하 수요는 자료 오류 (스페인 2026-08 = 0) → 결측 처리하고 표시
    if bad.any():
        print(f"  {geo}: 0 이하 수요 {df.loc[bad, 'month'].tolist()} → 결측 처리 (gas_flag = invalid_zero)")
        df.loc[bad, "gas_flag"] = "invalid_zero"
        df.loc[bad, "gas_tj"] = np.nan
    df["gas_pj"] = df["gas_tj"] / 1000
    df["y"], df["y_unit"] = df["gas_pj"], "PJ"
    df["price_retail"], df["price_wholesale"] = splice_hicp(df), df["ttf_usd"]
    df["hdd_source"] = np.where(df.hdd.notna(), "eurostat", "")
    if geo == "DE" and (INTERIM / "dwd_de_degree_days.csv").exists():   # 2026~ HDD·CDD (fetch_dwd.py)
        dwd = pd.read_csv(INTERIM / "dwd_de_degree_days.csv", dtype={"month": str}).set_index("month")
        gap = df.hdd.isna() & df.month.isin(dwd.index)
        df.loc[gap, "hdd"] = df.loc[gap, "month"].map(dwd.hdd_cal)
        df.loc[gap, "cdd"] = df.loc[gap, "month"].map(dwd.cdd_cal)
        df.loc[gap, "hdd_source"] = "dwd_calibrated"
    if geo != "DE" and (INTERIM / "openmeteo_degree_days.csv").exists():   # 2026~ (fetch_openmeteo.py)
        om = pd.read_csv(INTERIM / "openmeteo_degree_days.csv", dtype={"month": str})
        om = om[om.geo == geo].set_index("month")
        gap = df.hdd.isna() & df.month.isin(om.index)
        df.loc[gap, "hdd"] = df.loc[gap, "month"].map(om.hdd_cal)
        df.loc[gap, "cdd"] = df.loc[gap, "month"].map(om.cdd_cal)
        df.loc[gap, "hdd_source"] = "openmeteo_calibrated"
    extra = ["gas_tj", "gas_pj", "gas_flag", "hicp_gas", "ip_chem", "nuclear_gwh", "wind_gwh"] + WORLD_SERIES
    extra += ["hdd_source"]
    if geo == "DE" and (INTERIM / "the_sector.csv").exists():   # THE 부문별 (fetch_the.py), 2021-10~
        the = pd.read_csv(INTERIM / "the_sector.csv", dtype={"month": str})[["month", "slp_pj", "rlm_pj"]]
        df = df.merge(the, on="month", how="left")
        df["the_total_pj"] = df["slp_pj"] + df["rlm_pj"]
        extra += ["slp_pj", "rlm_pj", "the_total_pj"]
    return df[COMMON + extra]


def build_korea(world):
    long = pd.read_csv(INTERIM / "korea_long.csv", dtype={"month": str})
    wide = long.pivot(index="month", columns="series", values="value").reset_index()
    last = wide.loc[wide.gas_ton.notna(), "month"].max()
    months = months_range(KR_START, last)
    df = (pd.DataFrame({"month": months}).merge(wide, on="month", how="left")
          .merge(world, on="month", how="left")
          .merge(calendar_features("KR", months), on="month", how="left"))
    df["geo"] = "KR"
    df["gas_kt"] = df["gas_ton"] / 1000
    df["gas_city_kt"] = df["gas_city_ton"] / 1000
    df["gas_power_kt"] = df["gas_power_ton"] / 1000
    df["y"], df["y_unit"] = df["gas_kt"], "천톤"
    df["price_retail"], df["price_wholesale"] = df["cpi_city_gas"], df["lng_asia_usd"]
    extra = ["gas_kt", "gas_city_kt", "gas_power_kt", "cpi_city_gas"] + WORLD_SERIES
    return df[COMMON + extra]


def report(df, start, end):
    core = df[(df.month >= start) & (df.month <= end)]
    model_cols = ["y", "hdd", "cdd", "price_retail", "price_wholesale", "ip", "workdays"]
    miss = core[model_cols].isna().sum()
    miss = miss[miss > 0]
    y25 = core[core.month.str[:4] == "2025"]
    unit = df.y_unit.iloc[0]
    total = (f"{y25.gas_tj.sum() / 3600:.0f} TWh" if unit == "PJ" else f"{y25.gas_kt.sum() / 1000:.1f} 백만 톤")
    print(f"{df.geo.iloc[0]}: 수요 {df.loc[df.y.notna(), 'month'].min()}~{df.loc[df.y.notna(), 'month'].max()}, "
          f"2025년 {total}, 최대월/최소월 {y25.y.max() / y25.y.min():.1f}, "
          f"{start}~{end} 결측 {dict(miss) if len(miss) else '없음'}")


def build():
    long = pd.read_csv(INTERIM / "europe_long.csv", dtype={"month": str})
    world = world_prices()
    frames = []
    for geo in EU_GEOS:
        df = build_europe(geo, long, world)
        report(df, START, END)
        frames.append(df)
    if (INTERIM / "korea_long.csv").exists():
        kr = build_korea(world)
        report(kr, "2016-01", END)
        frames.append(kr)
    else:
        print("한국: data/interim/korea_long.csv 없음 → 건너뜀 (python fetch_korea.py all)")
    for df in frames:
        df.to_csv(PROCESSED / f"{df.geo.iloc[0]}.csv", index=False, encoding="utf-8")
    panel = pd.concat([f[COMMON] for f in frames], ignore_index=True)
    panel.to_csv(PROCESSED / "panel.csv", index=False, encoding="utf-8")
    print(f"\n저장: {PROCESSED} (국가별 CSV + panel.csv 공통 열, {len(panel)}행)")


if __name__ == "__main__":
    build()
