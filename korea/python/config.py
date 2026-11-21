"""한국 천연가스 수요예측 연구의 경로·지역·기간 설정."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]          # korea/
REPO = ROOT.parent                                   # 저장소 루트 (.env, .venv-fm)
RAW = ROOT / "data" / "raw"
INTERIM = ROOT / "data" / "interim"
PROCESSED = ROOT / "data" / "processed"
OUTPUTS = ROOT / "outputs"
FIGURES = OUTPUTS / "figures"
for p in (RAW, INTERIM, PROCESSED, OUTPUTS, FIGURES):
    p.mkdir(parents=True, exist_ok=True)

# 시도별 대표 기상관측소(ASOS). 넓은 도는 2~3개 지점 평균.
PROVINCE_STATIONS = {
    "서울": [108], "부산": [159], "대구": [143], "인천": [112], "광주": [156], "대전": [133], "울산": [152],
    "세종": [133, 131],          # 세종 관측소는 2019년 이후라 인접한 대전·청주 평균으로 대신한다
    "경기": [119, 203],          # 수원, 이천
    "강원": [101, 105, 114],     # 춘천, 강릉, 원주
    "충북": [131, 127],          # 청주, 충주
    "충남": [232, 129],          # 천안, 서산
    "전북": [146, 140],          # 전주, 군산
    "전남": [165, 168],          # 목포, 여수
    "경북": [136, 138],          # 안동, 포항
    "경남": [155, 192],          # 창원, 진주
    "제주": [184],
}
PROVINCES = list(PROVINCE_STATIONS)

# 한국가스공사 지역본부 → 관할 시도 (지역본부별 용도별 공급량 자료의 9개 지역)
REGIONS = {
    "서울": ["서울"], "인천": ["인천"], "경기": ["경기"], "강원": ["강원"],
    "대전.충청": ["대전", "세종", "충북", "충남"], "전북": ["전북"], "광주.전남": ["광주", "전남"],
    "대구.경북": ["대구", "경북"], "부산.경남": ["부산", "울산", "경남"],
}
USES = {"city": "도시가스용", "power": "발전용"}

KMA_START_YEAR = 1989        # 시도별 판매량 자료(1989~)와 같은 시작
