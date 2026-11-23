"""한국 연구 자료 수집. 원자료는 data/raw/<호출일>/에 그대로 저장한다.

    python fetch.py kogas   # 한국가스공사 3종 (키 불필요): 전국 용도별, 지역본부별 용도별, 시도별 도시가스 판매량
    python fetch.py kma     # 기상청 ASOS 일평균기온, 시도 대표 관측소 (KMA_SERVICE_KEY). 지점별로 저장해 끊겨도 이어 받는다
    python fetch.py kosis   # KOSIS: 도시가스 소비자물가, 광공업생산지수, 월별 전력거래량 (KOSIS_API_KEY)
    python fetch.py fred    # FRED 아시아 LNG 가격 (키 불필요)
    python fetch.py all

API 키는 저장소 루트의 .env에 둔다 (발급 절차: docs/API_KEYS.md).
"""
import datetime as dt
import io
import json
import os
import re
import sys
import time

import pandas as pd
import requests

from config import KMA_START_YEAR, PROVINCE_STATIONS, RAW, REPO

TODAY = dt.date.today().strftime("%Y%m%d")

# 공공데이터포털 파일데이터 (한국가스공사)
DATAGO = {
    "kogas_national": "15129906",   # 용도별 월 공급량 (전국, 도시가스·발전, 톤), 2016~
    "kogas_region": "15049902",     # 지역본부별 용도별 천연가스 공급량 (9개 지역본부, 톤), 2019~
    "kogas_province": "15040819",   # 월별 시도별 도시가스 판매현황 (17개 시도, 천㎥), 1989~
}
KMA_URL = "https://apis.data.go.kr/1360000/AsosDalyInfoService/getWthrDataList"
KOSIS_DATA = "https://kosis.kr/openapi/Param/statisticsParameterData.do"
FRED = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}"


def load_env():
    path = REPO / ".env"
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def need_key(name):
    key = os.environ.get(name)
    if not key:
        sys.exit(f"{name}가 없습니다. 저장소 루트의 .env에 {name}=키 를 적어 주세요 (docs/API_KEYS.md).")
    return key


def raw_dir(*sub):
    d = RAW.joinpath(TODAY, *sub)
    d.mkdir(parents=True, exist_ok=True)
    return d


# ---------------- 한국가스공사 (공공데이터포털 파일, 키 불필요) ----------------
def datago_file(pk):
    """파일데이터 상세 페이지에서 파일 식별자를 찾아 CSV를 받는다. 반환: (본문, 파일 수정일)."""
    html = requests.get(f"https://www.data.go.kr/data/{pk}/fileData.do", timeout=60).text
    uddi = re.search(r"uddi:[0-9a-f\-]{36}", html)
    if not uddi:
        raise RuntimeError(f"공공데이터포털 {pk}: 파일 식별자를 찾지 못했습니다")
    meta = requests.post("https://www.data.go.kr/tcs/dss/selectFileDataDownload.do",
                         data={"publicDataPk": pk, "publicDataDetailPk": uddi.group(0), "atchFileId": "",
                               "fileDetailSn": "1", "publicDataTyCode": "PR0051"}, timeout=60).json()
    raw = requests.get("https://www.data.go.kr/cmm/cmm/fileDownload.do",
                       params={"atchFileId": meta["atchFileId"], "fileDetailSn": "1"}, timeout=120).content
    text = raw.decode("utf-8-sig") if raw.startswith(b"\xef\xbb\xbf") else raw.decode("cp949")
    return text, meta.get("dataSetFileDetailInfo", {}).get("updtDt", "")


def fetch_kogas():
    for name, pk in DATAGO.items():
        text, updated = datago_file(pk)
        (raw_dir() / f"{name}.csv").write_text(text, encoding="utf-8")
        df = pd.read_csv(io.StringIO(text))
        print(f"한국가스공사 {name} ({pk}): {len(df)}행, 열 {list(df.columns)[:6]}, 파일 수정일 {updated}")


# ---------------- 기상청 ASOS 일자료 (KMA_SERVICE_KEY) ----------------
def kma_range(key, stn, start, end):
    """start~end(최대 999일) 일자료 한 번 호출."""
    params = {"serviceKey": key, "pageNo": 1, "numOfRows": 999, "dataType": "JSON", "dataCd": "ASOS",
              "dateCd": "DAY", "startDt": start.strftime("%Y%m%d"), "endDt": end.strftime("%Y%m%d"), "stnIds": stn}
    for i in range(6):
        try:
            js = requests.get(KMA_URL, params=params, timeout=90).json()
            break
        except (requests.RequestException, json.JSONDecodeError):
            if i == 5:
                raise RuntimeError(f"기상청 응답 오류 (지점 {stn}, {start}~{end})")
            time.sleep(3 * (i + 1))
    head = js["response"]["header"]
    if head["resultCode"] == "03":      # 자료 없음 (관측 시작 전)
        return pd.DataFrame(columns=["tm", "stnId", "avgTa"])
    if head["resultCode"] != "00":
        raise RuntimeError(f"기상청 오류 {head['resultCode']}: {head['resultMsg']}")
    return pd.DataFrame(js["response"]["body"]["items"]["item"])[["tm", "stnId", "avgTa"]]


def kma_station(key, stn, out):
    f = out / f"{stn}.csv"
    if f.exists():                      # 이미 받은 지점은 건너뛴다 (중단 후 이어 받기)
        return
    last = dt.date.today() - dt.timedelta(days=2)
    d, parts = dt.date(KMA_START_YEAR, 1, 1), []
    while d <= last:
        e = min(d + dt.timedelta(days=998), last)
        parts.append(kma_range(key, stn, d, e))
        d = e + dt.timedelta(days=1)
    df = pd.concat(parts, ignore_index=True)
    df.to_csv(f, index=False, encoding="utf-8")
    print(f"  기상청 지점 {stn}: {df.tm.min()}~{df.tm.max()} ({len(df)}일)", flush=True)


def fetch_kma():
    from concurrent.futures import ThreadPoolExecutor
    key = need_key("KMA_SERVICE_KEY")
    stations = sorted({s for v in PROVINCE_STATIONS.values() for s in v})
    out = raw_dir("kma")
    with ThreadPoolExecutor(max_workers=4) as ex:     # 지점 4곳씩 동시에
        list(ex.map(lambda s: kma_station(key, s, out), stations))
    print(f"기상청: {len(list(out.glob('*.csv')))}/{len(stations)}개 지점 → {out}")


# ---------------- KOSIS (KOSIS_API_KEY) ----------------
def kosis(params):
    params = {"method": "getList", "apiKey": need_key("KOSIS_API_KEY"), "format": "json", "jsonVD": "Y", **params}
    js = requests.get(KOSIS_DATA, params=params, timeout=60).json()
    if isinstance(js, dict) and js.get("err"):
        raise RuntimeError(f"KOSIS 오류 {js.get('err')}: {js.get('errMsg')}")
    return pd.DataFrame(js)


def fetch_kosis():
    end = dt.date.today().strftime("%Y%m")
    # 품목별 소비자물가지수(2020=100): 전국 × 도시가스 / 광공업생산지수 계절조정 총지수
    monthly = {"cpi_city_gas": dict(orgId="101", tblId="DT_1J22112", itmId="T", objL1="T10", objL2="C01D05201"),
               "ip": dict(orgId="101", tblId="DT_1F02001", itmId="T20", objL1="00", objL2="0")}
    for name, p in monthly.items():
        df = kosis({**p, "prdSe": "M", "startPrdDe": "198901", "endPrdDe": end})
        df.to_csv(raw_dir() / f"kosis_{name}.csv", index=False, encoding="utf-8")
        print(f"KOSIS {name}: {df.PRD_DE.min()}~{df.PRD_DE.max()} ({len(df)}개월)")
    # 연도별 월별 전력거래량 (전력거래소, MWh): 연 단위 표에 '월' 분류가 들어 있다
    df = kosis(dict(orgId="388", tblId="TX_38804_A006", itmId="16388AAW3", objL1="ALL", prdSe="Y",
                    startPrdDe="2001", endPrdDe=str(dt.date.today().year)))
    df.to_csv(raw_dir() / "kosis_elec_traded.csv", index=False, encoding="utf-8")
    print(f"KOSIS 전력거래량: {df.PRD_DE.min()}~{df.PRD_DE.max()}년, {len(df)}행")
    # 연도별 월별 평균 계통한계가격 SMP (전력거래소, 원/kWh): 같은 형식
    df = kosis(dict(orgId="388", tblId="TX_38804_A012", itmId="16388AAX0", objL1="ALL", prdSe="Y",
                    startPrdDe="2001", endPrdDe=str(dt.date.today().year)))
    df.to_csv(raw_dir() / "kosis_smp.csv", index=False, encoding="utf-8")
    print(f"KOSIS SMP: {df.PRD_DE.min()}~{df.PRD_DE.max()}년, {len(df)}행")


def fetch_fred():
    for sid in ("PNGASJPUSDM", "PCOALAUUSDM"):   # 아시아 LNG 가격 (USD/MMBtu), 호주 석탄 가격 (USD/t)
        text = requests.get(FRED.format(sid=sid), timeout=60).text
        (raw_dir() / f"fred_{sid}.csv").write_text(text, encoding="utf-8")
        print(f"FRED {sid}: {len(text.splitlines()) - 1}개월")


def main():
    load_env()
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    steps = {"kogas": fetch_kogas, "kosis": fetch_kosis, "fred": fetch_fred, "kma": fetch_kma}
    for name, fn in steps.items():
        if what in (name, "all"):
            fn()


if __name__ == "__main__":
    main()
