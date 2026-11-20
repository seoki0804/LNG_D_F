# 천연가스 월 수요예측: 독일 중심 6개국, 회귀분석과 AI 모델 비교

독일 월별 천연가스 수요를 회귀분석(강의 Ch1~6)과 AI 모델로 예측하고, 같은 모델 구조를 이탈리아·프랑스·스페인·네덜란드·한국에 적용해 국가별 정확도와 난방 민감도를 비교한다.

- 평가: 2023년 1월~2025년 12월, 매달 재추정 후 1개월 앞 예측(36회), MAPE·RMSE·MASE, Diebold-Mariano 검정
- 도구: 회귀 R, AI Python

## 폴더 구조

```
data/
  raw/<호출일>/        원자료 그대로 (Eurostat JSON-stat, FRED CSV)
  interim/             long 형식 정리본 (europe_long.csv)
  processed/           국가별 분석 데이터셋 (DE.csv … panel.csv)
python/
  config.py            경로·국가·기간 설정
  fetch_europe.py      유럽 5개국 + FRED 수집
  build_dataset.py     국가별 월 데이터셋 병합 (영업일 수 포함)
  rolling_eval.py      공통 롤링 평가 코드 (모든 모델이 이 코드로 평가)
R/                     회귀분석 (Ch1~6)
outputs/               그림·결과표
```

## 실행 순서

```bash
pip install -r requirements.txt
cd python
python fetch_europe.py      # 데이터 다시 받기 (data/raw/<오늘 날짜>/ 에 저장)
python build_dataset.py     # data/processed/ 생성
```

R 스크립트는 저장소 루트에서 `Rscript R/<파일명>.R` 로 실행한다.

## 데이터

| 변수 | 유럽 5개국 | 한국 |
| --- | --- | --- |
| 수요 Y | Eurostat `nrg_cb_gasm` 내수 소비 (TJ, GCV) | KOGAS 용도별 월 공급량 (톤) — 수동 다운로드 필요 |
| HDD·CDD | Eurostat `nrg_chdd_m` | 기상청 ASOS 일자료로 계산 — API 키 필요 |
| 가스 요금 | Eurostat `prc_hicp_midx` CP0452 (2015=100) | KOSIS 도시가스 물가 — API 키 필요 |
| 도매가격 | FRED `PNGASEUUSDM` | FRED `PNGASJPUSDM` |
| 산업생산 | Eurostat `sts_inpr_m` B-D (2021=100) | KOSIS 광공업생산지수 |
| 화학 생산 | Eurostat `sts_inpr_m` C20 | — |
| 원자력 발전 | Eurostat `nrg_cb_pem` N9000 (GWh) | — |
| 영업일 수 | python-holidays 국가 공휴일 | 같음 |

주의: Eurostat `prc_hicp_midx`는 2025년 12월에서 끝난다(COICOP 개편). 2026년 추가 검증에는 대체 출처가 필요하다.

## 진행 상황

- [x] 유럽 5개국 + FRED 데이터 수집
- [ ] 국가별 데이터셋 병합
- [ ] 공통 롤링 평가 코드
- [ ] 독일 사전 실험 재현 (R² 0.91, GBM 5.6%)
- [ ] 한국 데이터 (KOGAS·기상청·KOSIS)
- [ ] 독일 부문별 자료 (THE SLP·RLM)
