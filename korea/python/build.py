"""원자료 → 분석 데이터셋 (data/processed/).

  national.csv   전국 월별: 도시가스용·발전용·합계 공급량(천 톤), 수요가중 HDD·CDD, 평년 HDD, 가격·산업·전력·달력 변수
  province.csv   17개 시도 월별: 도시가스 판매량(백만㎥), 시도 HDD·CDD·평년 HDD

자료 점검에서 고친 것 (자세한 근거는 README):
  - 전국 용도별 자료의 2019년 도시가스용은 계절 형태가 어긋나 있어 지역본부별 자료로 복원한다 (fix_city_2019).
  - 시도별 판매량은 2023년 1월부터 모든 시도가 약 25% 낮아지는 정의 변경이 있어 2022년 12월까지만 쓴다.

실행: python build.py   (fetch.py 결과 필요)
"""
import io

import holidays
import numpy as np
import pandas as pd

from config import INTERIM, PROCESSED, PROVINCE_STATIONS, RAW

PROVINCE_END = "2022-12"          # 시도별 판매량 정의 변경 직전
WEIGHT_YEARS = ("2016", "2018")   # 수요가중 HDD의 시도 가중치 (평가 구간 이전, 정의 변경 이전)


def latest(name):
    """data/raw/<호출일>/ 중 가장 최근 파일."""
    files = sorted(RAW.glob(f"*/{name}"))
    if not files:
        raise FileNotFoundError(f"{name} 없음 → python fetch.py 먼저 실행")
    return files[-1]


def ym(y, m):
    return y.astype(str) + "-" + m.astype(str).str.zfill(2)


# ---------------- 수요 ----------------
def fix_city_2019(city, region):
    """전국 2019년 도시가스용 = 지역본부 합계 / (지역본부 합계 ÷ 전국)의 달별 비율 (2020~2025, 이상월 제외)."""
    reg = region.groupby("month").city.sum()
    ratio = (reg / city).dropna()
    ok = ratio[(ratio.index >= "2020-01") & ((ratio - ratio.median()).abs() < 0.02)]
    by_m = ok.groupby(ok.index.str[5:]).mean()
    out = city.astype(float).copy()
    for m in [m for m in reg.index if m.startswith("2019")]:
        out[m] = reg[m] / by_m[m[5:]]
    print(f"2019 도시가스용 복원: 7월 {city['2019-07'] / 1e3:,.0f} → {out['2019-07'] / 1e3:,.0f} 천 톤")
    return out


def demand_national():
    n = pd.read_csv(latest("kogas_national.csv"))
    n["month"] = ym(n["연도"], n["월"])
    n = n.pivot(index="month", columns="용도", values="공급량").rename(columns={"도시가스": "city", "발전": "power"})
    r = pd.read_csv(latest("kogas_region.csv"))
    r["month"] = ym(r["년도"], r["월"])
    r = r.rename(columns={"도시가스 공급량": "city", "발전 공급량": "power"})
    n["city"] = fix_city_2019(n.city, r)
    out = (n[["city", "power"]] / 1000).astype(float)            # 천 톤
    out["total"] = out.city + out.power
    return out.reset_index()


def demand_province():
    p = pd.read_csv(latest("kogas_province.csv")).rename(columns={"연월": "month"})
    p = p.melt(id_vars="month", var_name="province", value_name="sales")
    p["sales"] = p.sales / 1000                                   # 백만㎥
    p.loc[p.sales <= 0, "sales"] = np.nan                         # 집계 시작 전 0
    return p[p.month <= PROVINCE_END]


# ---------------- 기온 ----------------
def degree_days(tm):
    """Eurostat 방식: HDD = Σ(18 − Tm) (Tm ≤ 15°C), CDD = Σ(Tm − 21) (Tm ≥ 24°C)."""
    return (18 - tm).where(tm <= 15, 0.0), (tm - 21).where(tm >= 24, 0.0)


def weather_province():
    d = sorted(p.parent for p in RAW.glob("*/kma/*.csv"))[-1]
    daily = pd.concat([pd.read_csv(f, dtype={"tm": str}) for f in d.glob("*.csv")], ignore_index=True)
    daily["avgTa"] = pd.to_numeric(daily.avgTa, errors="coerce")
    daily = daily.sort_values(["stnId", "tm"])
    daily["avgTa"] = daily.groupby("stnId").avgTa.transform(lambda s: s.interpolate(limit=3))   # 3일 이내 결측 보간
    daily = daily.dropna(subset=["avgTa"])
    daily["month"] = daily.tm.str[:7]
    daily["hdd"], daily["cdd"] = degree_days(daily.avgTa)
    st = daily.groupby(["stnId", "month"]).agg(hdd=("hdd", "sum"), cdd=("cdd", "sum"), n=("tm", "size"),
                                               tmean=("avgTa", "mean")).reset_index()
    st = st[st.n == st.month.map(lambda m: pd.Period(m).days_in_month)]     # 하루도 빠지지 않은 달만
    rows = []
    for prov, stns in PROVINCE_STATIONS.items():
        s = st[st.stnId.isin(stns)].groupby("month").agg(hdd=("hdd", "mean"), cdd=("cdd", "mean"),
                                                         tmean=("tmean", "mean"), k=("stnId", "nunique"))
        # 한 지점이 그달 결측이면 남은 지점 평균 (2016~2026년에 3번: 전북 2022-10, 강원 2024-12·2025-06)
        rows.append(s[s.k >= 1].drop(columns="k").assign(province=prov).reset_index())
    w = pd.concat(rows, ignore_index=True)
    # 마지막 관측 뒤 12개월까지 빈 행을 두어 평년값(예측 입력)을 계산해 둔다
    future = pd.period_range(w.month.min(), pd.Period(w.month.max(), "M") + 12, freq="M").astype(str)
    w = (w.set_index(["province", "month"])
         .reindex(pd.MultiIndex.from_product([PROVINCE_STATIONS, future], names=["province", "month"]))
         .reset_index())
    w = w[w.groupby("province").hdd.transform(lambda s: s.notna().cummax()).astype(bool)]   # 관측 시작 전은 버린다
    return add_climatology(w, "province")


def add_climatology(df, key):
    """평년 HDD·CDD = 직전 10년 같은 달 평균 (예측 시점에 알 수 있는 기온 정보)."""
    df = df.sort_values([key, "month"]).copy()
    df["mm"] = df.month.str[5:]
    for v in ("hdd", "cdd"):
        df[f"{v}_clim"] = df.groupby([key, "mm"])[v].transform(lambda s: s.shift(1).rolling(10, min_periods=10).mean())
    return df.drop(columns="mm")


# ---------------- 가격·산업·전력 ----------------
def kosis_monthly(name):
    k = pd.read_csv(latest(f"kosis_{name}.csv"), dtype={"PRD_DE": str})
    return pd.DataFrame({"month": k.PRD_DE.str[:4] + "-" + k.PRD_DE.str[4:6], name: pd.to_numeric(k.DT)})


def electricity():
    e = pd.read_csv(latest("kosis_elec_traded.csv"), dtype={"PRD_DE": str})
    e = e[e.C1_NM != "합계"].copy()
    e["month"] = e.PRD_DE + "-" + e.C1_NM.str.replace("월", "").str.zfill(2)
    return pd.DataFrame({"month": e.month, "elec_twh": pd.to_numeric(e.DT, errors="coerce") / 1000})   # GWh → TWh ("-" = 미공표)


def lng_price():
    f = pd.read_csv(latest("fred_PNGASJPUSDM.csv"))
    f.columns = ["date", "lng_usd"]
    return pd.DataFrame({"month": f.date.str[:7], "lng_usd": pd.to_numeric(f.lng_usd, errors="coerce")})


def calendar(months):
    kr = holidays.KR(years=range(1989, 2028))
    rows = []
    for m in months:
        days = pd.date_range(m + "-01", periods=pd.Period(m).days_in_month, freq="D")
        hol = [d for d in days if d in kr]
        names = " ".join(kr.get(d) for d in hol)
        rows.append({"month": m, "days": len(days), "workdays": sum(d.weekday() < 5 and d not in kr for d in days),
                     "seollal": int("Lunar New Year" in names or "설날" in names),
                     "chuseok": int("Chuseok" in names or "추석" in names)})
    return pd.DataFrame(rows)


def main():
    wp = weather_province()
    prov = wp.merge(demand_province(), on=["province", "month"], how="left")   # 기온은 판매량 이후에도 둔다
    prov.to_csv(PROCESSED / "province.csv", index=False, encoding="utf-8")

    # 전국 수요가중 HDD: 시도 HDD를 2016~2018년 시도별 도시가스 판매 비중으로 가중평균
    share = prov[prov.month.str[:4].between(*WEIGHT_YEARS)].groupby("province").sales.sum()
    share = share / share.sum()
    wide = {v: wp.pivot(index="month", columns="province", values=v) for v in ("hdd", "cdd", "tmean")}
    nat_w = pd.DataFrame({v: (w[share.index] * share).sum(axis=1, min_count=len(share)) for v, w in wide.items()})
    nat_w["hdd_simple"] = wide["hdd"].mean(axis=1)
    nat_w = add_climatology(nat_w.reset_index().assign(geo="KR"), "geo").drop(columns="geo")

    nat = demand_national()
    months = pd.period_range("2006-01", pd.Period(nat.month.max(), "M") + 12, freq="M").astype(str)   # +12: 예측 입력
    df = pd.DataFrame({"month": months})
    for part in (nat, nat_w, kosis_monthly("cpi_city_gas"), kosis_monthly("ip"), lng_price(), electricity(),
                 calendar(months)):
        df = df.merge(part, on="month", how="left")
    df["coal_cap"] = ((df.month >= "2019-12") & df.month.str[5:].isin(["12", "01", "02", "03"])).astype(int)
    df.to_csv(PROCESSED / "national.csv", index=False, encoding="utf-8")

    d = df[df.total.notna()]
    print(f"전국: {d.month.min()}~{d.month.max()} ({len(d)}개월), 결측 "
          f"{d[['city', 'power', 'hdd', 'cpi_city_gas', 'ip', 'lng_usd']].isna().sum().to_dict()}, "
          f"전력거래량 ~{df.loc[df.elec_twh.notna(), 'month'].max()}")
    s = prov[prov.sales.notna()]
    print(f"시도: 판매량 {s.month.min()}~{s.month.max()}, 17개 시도 {len(s)}행, 그중 HDD 결측 {s.hdd.isna().sum()}")
    print("수요가중 HDD 가중치(2016~2018):", share.round(3).sort_values(ascending=False).head(6).to_dict())


if __name__ == "__main__":
    main()
