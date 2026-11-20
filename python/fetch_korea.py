"""한국 월자료 수집: KOGAS 용도별 공급량(키 불필요) + 기상청 ASOS 기온 → HDD·CDD(키 필요) + KOSIS(키 필요).

API 키는 저장소 루트의 .env 파일에 둔다 (.gitignore에 포함, 공개되지 않음):
    KMA_SERVICE_KEY=공공데이터포털 일반 인증키(Decoding)
    KOSIS_API_KEY=KOSIS 인증키

실행:
    python python/fetch_korea.py kogas          # KOGAS만
    python python/fetch_korea.py kma            # 기상청 (키 필요)
    python python/fetch_korea.py kosis-search 도시가스   # KOSIS 통계표 찾기 (키 필요)
    python python/fetch_korea.py all
출력: data/interim/korea_long.csv 형식은 europe_long.csv와 같다 (series, geo, month, value, ...).
"""
import datetime as dt
import io
import json
import os
import sys
import time

import pandas as pd
import requests

from config import INTERIM, RAW, ROOT

KOGAS_URL = ("https://www.data.go.kr/cmm/cmm/fileDownload.do"
             "?atchFileId={atch}&fileDetailSn=1&dataNm=kogas")
KOGAS_META = "https://www.data.go.kr/tcs/dss/selectFileDataDownload.do"
KOGAS_PK = {"publicDataPk": "15129906",
            "publicDataDetailPk": "uddi:6e91ab3f-2392-44fb-8481-e76a32cc1fa4"}

KMA_URL = "https://apis.data.go.kr/1360000/AsosDalyInfoService/getWthrDataList"
# 주요 도시 ASOS 지점 (서울·부산·대구·인천·광주·대전·울산)
KMA_STATIONS = {108: "서울", 159: "부산", 143: "대구", 112: "인천", 156: "광주", 133: "대전", 152: "울산"}
KMA_START_YEAR = 2006   # 평년 HDD(직전 10년 평균)를 위해 수요보다 10년 앞서 받는다

KOSIS_SEARCH = "https://kosis.kr/openapi/statisticsSearch.do"
KOSIS_DATA = "https://kosis.kr/openapi/Param/statisticsParameterData.do"
KOSIS_META = "https://kosis.kr/openapi/statisticsData.do"


def load_env():
    path = ROOT / ".env"
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def need_key(name):
    key = os.environ.get(name)
    if not key:
        sys.exit(f"{name}가 없습니다. 저장소 루트의 .env 파일에 {name}=키 를 적어 주세요 (README 'API 키' 참고).")
    return key


def raw_dir():
    d = RAW / dt.date.today().strftime("%Y%m%d")
    d.mkdir(parents=True, exist_ok=True)
    return d


# ---------------- KOGAS (키 불필요) ----------------
def fetch_kogas():
    meta = requests.post(KOGAS_META, data={**KOGAS_PK, "atchFileId": "", "fileDetailSn": "1",
                                           "publicDataTyCode": "PR0051"}, timeout=60).json()
    atch = meta["atchFileId"]
    raw = requests.get(KOGAS_URL.format(atch=atch), timeout=60).content
    text = raw.decode("cp949") if not raw.startswith(b"\xef\xbb\xbf") else raw.decode("utf-8-sig")
    (raw_dir() / "kogas_monthly_supply.csv").write_text(text, encoding="utf-8")
    df = pd.read_csv(io.StringIO(text), dtype=str)
    df.columns = ["year", "mon", "use", "value"]
    df["month"] = df.year + "-" + df.mon.str.zfill(2)
    df["value"] = pd.to_numeric(df.value)
    names = {"도시가스": "gas_city_ton", "발전": "gas_power_ton"}
    df["series"] = df["use"].map(names)
    if df.series.isna().any():
        raise ValueError(f"알 수 없는 용도: {df[df.series.isna()].use.unique()}")
    total = df.groupby("month", as_index=False).value.sum().assign(series="gas_ton")
    out = pd.concat([df[["series", "month", "value"]], total], ignore_index=True)
    print(f"KOGAS: {out.month.min()}~{out.month.max()}, 용도 {sorted(df['use'].unique())}, "
          f"파일 수정일 {meta.get('dataSetFileDetailInfo', {}).get('updtDt', '')}")
    return out


# ---------------- 기상청 ASOS → HDD·CDD (키 필요) ----------------
def kma_year(key, stn, year):
    end = min(dt.date(year, 12, 31), dt.date.today() - dt.timedelta(days=2))
    params = {"serviceKey": key, "pageNo": 1, "numOfRows": 999, "dataType": "JSON",
              "dataCd": "ASOS", "dateCd": "DAY", "startDt": f"{year}0101",
              "endDt": end.strftime("%Y%m%d"), "stnIds": stn}
    for i in range(4):
        try:
            r = requests.get(KMA_URL, params=params, timeout=60)
            js = r.json()
            break
        except (requests.RequestException, json.JSONDecodeError):
            if i == 3:
                raise RuntimeError(f"기상청 응답 오류 (지점 {stn}, {year}): {r.text[:300]}")
            time.sleep(2 * (i + 1))
    header = js["response"]["header"]
    if header["resultCode"] != "00":
        raise RuntimeError(f"기상청 오류 {header['resultCode']}: {header['resultMsg']} "
                           "(키 승인 직후라면 1~2시간 뒤 다시 시도)")
    items = js["response"]["body"]["items"]["item"]
    return pd.DataFrame(items)[["tm", "stnId", "avgTa"]]


def degree_days(tm):
    """Eurostat 방식: HDD = 18 − Tm (Tm ≤ 15°C인 날), CDD = Tm − 21 (Tm ≥ 24°C인 날)."""
    hdd = (18 - tm).where(tm <= 15, 0.0)
    cdd = (tm - 21).where(tm >= 24, 0.0)
    return hdd, cdd


def fetch_kma():
    key = need_key("KMA_SERVICE_KEY")
    last_year = (dt.date.today() - dt.timedelta(days=2)).year
    frames = []
    for stn, name in KMA_STATIONS.items():
        for y in range(KMA_START_YEAR, last_year + 1):
            frames.append(kma_year(key, stn, y))
        print(f"  기상청 {name}({stn}) {KMA_START_YEAR}~{last_year} 완료")
    daily = pd.concat(frames, ignore_index=True)
    daily.to_csv(raw_dir() / "kma_asos_daily.csv", index=False, encoding="utf-8")
    return kma_monthly(daily)


def kma_monthly(daily):
    """일평균기온 → 지점별 월 HDD·CDD → 지점 평균. 결측일은 지점 안에서 앞뒤 날로 선형보간(최대 3일)."""
    daily = daily.copy()
    daily["avgTa"] = pd.to_numeric(daily.avgTa, errors="coerce")
    daily = daily.sort_values(["stnId", "tm"])
    miss = daily[daily.avgTa.isna()]
    if len(miss):
        print(f"  일평균기온 결측 {len(miss)}일 보간: "
              + ", ".join(f"{r.tm}(지점 {r.stnId})" for r in miss.itertuples()))
        daily["avgTa"] = daily.groupby("stnId").avgTa.transform(lambda s: s.interpolate(limit=3))
    daily = daily.dropna(subset=["avgTa"])
    daily["month"] = daily.tm.str[:7]
    daily["hdd"], daily["cdd"] = degree_days(daily.avgTa)
    # 지점별 월합 → 지점 평균 (월 일수가 모두 채워진 달만)
    by_stn = daily.groupby(["stnId", "month"]).agg(hdd=("hdd", "sum"), cdd=("cdd", "sum"), n=("tm", "size"))
    by_stn = by_stn.reset_index()
    by_stn["days"] = by_stn.month.map(lambda m: pd.Period(m).days_in_month)
    by_stn = by_stn[by_stn.n == by_stn.days]
    monthly = by_stn.groupby("month").agg(hdd=("hdd", "mean"), cdd=("cdd", "mean"), stations=("stnId", "nunique"))
    monthly = monthly[monthly.stations == len(KMA_STATIONS)].reset_index()
    out = monthly.melt(id_vars="month", value_vars=["hdd", "cdd"], var_name="series")
    print(f"기상청 HDD·CDD: {out.month.min()}~{out.month.max()} ({len(monthly)}개월, {len(KMA_STATIONS)}개 지점 평균)")
    return out


# ---------------- KOSIS (키 필요) ----------------
def kosis_search(word):
    key = need_key("KOSIS_API_KEY")
    r = requests.get(KOSIS_SEARCH, params={"method": "getList", "apiKey": key, "searchNm": word,
                                           "format": "json", "jsonVD": "Y", "resultCount": 30}, timeout=60)
    for row in r.json():
        print(row.get("ORG_ID"), row.get("TBL_ID"), row.get("TBL_NM"), row.get("STRT_PRD_DE"), row.get("END_PRD_DE"))


def kosis_meta(org_id, tbl_id):
    """통계표의 분류·항목 코드 목록 (새 계열을 추가할 때 코드 확인용)."""
    key = need_key("KOSIS_API_KEY")
    r = requests.get(KOSIS_META, params={"method": "getMeta", "type": "ITM", "orgId": org_id,
                                         "tblId": tbl_id, "apiKey": key, "format": "json",
                                         "jsonVD": "Y"}, timeout=60)
    return pd.DataFrame(r.json())[["OBJ_ID", "OBJ_NM", "ITM_ID", "ITM_NM", "UP_ITM_ID"]]


def kosis_series(org_id, tbl_id, itm_id, obj_l1, obj_l2=None, start="200601", end=None):
    """KOSIS 통계표 한 계열을 월별로 받는다. 표·항목 코드는 kosis-search, kosis_meta로 찾는다."""
    key = need_key("KOSIS_API_KEY")
    end = end or dt.date.today().strftime("%Y%m")
    params = {"method": "getList", "apiKey": key, "orgId": org_id, "tblId": tbl_id, "itmId": itm_id,
              "objL1": obj_l1, "format": "json", "jsonVD": "Y", "prdSe": "M",
              "startPrdDe": start, "endPrdDe": end}
    if obj_l2:
        params["objL2"] = obj_l2
    js = requests.get(KOSIS_DATA, params=params, timeout=60).json()
    if isinstance(js, dict) and js.get("err"):
        raise RuntimeError(f"KOSIS 오류 {js.get('err')}: {js.get('errMsg')}")
    df = pd.DataFrame(js)
    if df.empty or df.PRD_DE.duplicated().any():
        raise RuntimeError(f"KOSIS {tbl_id}: 한 계열로 좁혀지지 않았습니다 ({len(df)}행)")
    df["month"] = df.PRD_DE.str[:4] + "-" + df.PRD_DE.str[4:6]
    df["value"] = pd.to_numeric(df.DT, errors="coerce")
    return df[["month", "value"]]


# KOSIS 계열 (코드는 kosis_meta로 확인, 2026-11-21)
KOSIS_SERIES = {
    # 품목별 소비자물가지수(2020=100): 전국(T10) × 도시가스(C01D05201)
    "cpi_city_gas": dict(org_id="101", tbl_id="DT_1J22112", itm_id="T", obj_l1="T10", obj_l2="C01D05201"),
    # 시도/산업별 광공업생산지수(2020=100): 생산지수 계절조정(T20) × 전국(00) × 총지수(0)
    "ip": dict(org_id="101", tbl_id="DT_1F02001", itm_id="T20", obj_l1="00", obj_l2="0"),
}


def fetch_kosis():
    frames = []
    for name, spec in KOSIS_SERIES.items():
        s = kosis_series(**spec).assign(series=name)
        s.to_csv(raw_dir() / f"kosis_{name}.csv", index=False, encoding="utf-8")
        print(f"KOSIS {name}: {s.month.min()}~{s.month.max()} ({len(s)}개월)")
        frames.append(s)
    return pd.concat(frames, ignore_index=True)


def save(parts):
    long = pd.concat(parts, ignore_index=True)
    long["geo"] = "KR"
    long["flag"] = ""
    long["source_updated"] = ""
    long["fetched"] = dt.date.today().strftime("%Y%m%d")
    out = INTERIM / "korea_long.csv"
    if out.exists():   # 이번에 받지 않은 계열은 기존 값을 유지
        old = pd.read_csv(out, dtype={"month": str})
        long = pd.concat([old[~old.series.isin(long.series.unique())], long], ignore_index=True)
    long = long[["series", "geo", "month", "value", "flag", "source_updated", "fetched"]]
    long.sort_values(["series", "month"]).to_csv(out, index=False, encoding="utf-8")
    print(f"저장: {out} ({len(long)}행, 계열 {sorted(long.series.unique())})")


def main():
    load_env()
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    if what == "kosis-search":
        kosis_search(sys.argv[2])
        return
    parts = []
    if what in ("kogas", "all"):
        parts.append(fetch_kogas())
    if what in ("kma", "all"):
        parts.append(fetch_kma())
    if what == "kma-local":   # API 호출 없이 저장된 일자료(data/raw/*/kma_asos_daily.csv 최신)로 다시 계산
        latest = sorted(RAW.glob("*/kma_asos_daily.csv"))[-1]
        print(f"기상청 일자료 재사용: {latest}")
        parts.append(kma_monthly(pd.read_csv(latest, dtype={"tm": str})))
    if what in ("kosis", "all"):
        parts.append(fetch_kosis())
    save(parts)


if __name__ == "__main__":
    main()
