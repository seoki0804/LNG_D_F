"""프로젝트 공통 설정: 경로, 국가, 기간."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
INTERIM = ROOT / "data" / "interim"
PROCESSED = ROOT / "data" / "processed"
OUTPUTS = ROOT / "outputs"

for p in (RAW, INTERIM, PROCESSED, OUTPUTS):
    p.mkdir(parents=True, exist_ok=True)

# 유럽 5개국 (Eurostat geo 코드)
EU_GEOS = ["DE", "IT", "FR", "ES", "NL"]
GEO_NAMES = {"DE": "독일", "IT": "이탈리아", "FR": "프랑스", "ES": "스페인", "NL": "네덜란드", "KR": "한국"}

START = "2008-01"          # 유럽 분석 시작
END = "2025-12"            # 평가 마지막 달
EVAL_START = "2023-01"     # 롤링 평가 시작 (36회)
EVAL_END = "2025-12"
