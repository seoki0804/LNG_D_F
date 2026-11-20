"""국가별 월 분석 데이터셋 생성.

입력: data/interim/europe_long.csv (fetch_europe.py 결과)
출력: data/processed/<geo>.csv, data/processed/panel.csv

열 설명
  gas_tj, gas_pj      수요 Y (Eurostat 내수 소비, GCV)
  gas_flag            Eurostat 플래그 (p=잠정, e=추정 등)
  hdd, cdd            Eurostat 난방·냉방 도일
  hicp_gas            소비자 가스 요금 지수 (2015=100)
  ip, ip_chem         산업생산(B-D), 화학 생산(C20) 지수 (2021=100, 계절조정)
  nuclear_gwh         원자력 발전량
  ttf_usd, lng_asia_usd, coal_usd   FRED 국제 가격 (같은 달 값; 전월 값은 모델에서 shift)
  workdays            영업일 수 (월~금 − 국가 공휴일)
  days                달의 일수

실행: python python/build_dataset.py
"""
import holidays
import numpy as np
import pandas as pd

from config import EU_GEOS, INTERIM, PROCESSED, START, END

COUNTRY_SERIES = ["gas_tj", "hdd", "cdd", "hicp_gas", "ip", "ip_chem", "nuclear_gwh"]
WORLD_SERIES = ["ttf_usd", "lng_asia_usd", "coal_usd"]


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


def build():
    long = pd.read_csv(INTERIM / "europe_long.csv", dtype={"month": str})
    world = (long[long.series.isin(WORLD_SERIES)]
             .pivot(index="month", columns="series", values="value")
             .reset_index())

    frames = []
    for geo in EU_GEOS:
        sub = long[(long.geo == geo) & long.series.isin(COUNTRY_SERIES)]
        wide = sub.pivot(index="month", columns="series", values="value").reset_index()
        flags = (sub[sub.series == "gas_tj"][["month", "flag"]]
                 .rename(columns={"flag": "gas_flag"}))
        wide = wide.merge(flags, on="month", how="left")
        last = wide.loc[wide.gas_tj.notna(), "month"].max()
        months = pd.period_range(START, last, freq="M").strftime("%Y-%m").tolist()
        df = pd.DataFrame({"month": months})
        df = (df.merge(wide, on="month", how="left")
                .merge(world, on="month", how="left")
                .merge(calendar_features(geo, months), on="month", how="left"))
        df.insert(0, "geo", geo)
        df["gas_pj"] = df["gas_tj"] / 1000
        df["gas_flag"] = df["gas_flag"].fillna("")
        cols = (["geo", "month", "gas_tj", "gas_pj", "gas_flag"]
                + [c for c in COUNTRY_SERIES if c != "gas_tj"]
                + WORLD_SERIES + ["workdays", "days"])
        df = df[cols]
        df.to_csv(PROCESSED / f"{geo}.csv", index=False, encoding="utf-8")
        frames.append(df)

        core = df[(df.month >= START) & (df.month <= END)]
        miss = core.drop(columns=["geo", "month", "gas_flag"]).isna().sum()
        miss = miss[miss > 0]
        y25 = core[core.month.str[:4] == "2025"]
        print(f"{geo}: {df.month.min()}~{df.month.max()} ({len(df)}개월), "
              f"2025년 소비 {y25.gas_tj.sum() / 3600:.0f} TWh, "
              f"2025년 최대월/최소월 {y25.gas_pj.max() / y25.gas_pj.min():.1f}, "
              f"{START}~{END} 결측 {dict(miss) if len(miss) else '없음'}")

    panel = pd.concat(frames, ignore_index=True)
    panel.to_csv(PROCESSED / "panel.csv", index=False, encoding="utf-8")
    print(f"\n저장: {PROCESSED} (국가별 CSV + panel.csv, {len(panel)}행)")


if __name__ == "__main__":
    build()
