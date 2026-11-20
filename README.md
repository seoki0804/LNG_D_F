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
  models.py            사전 실험 모델 (회귀·Ridge·Lasso·RF·GBM·SVR·MLP·SARIMAX·Holt-Winters·하이브리드)
  pre_experiment_de.py 독일 사전 실험 재현
  sensitivity_de.py    독일 ML 모델 설정 민감도
R/
  01_de_simple_regression.R   독일 단순회귀 추론(Ch1~2), 진단 plot 6종·검정·Box-Cox(Ch3)
outputs/               결과표(.csv, .md, .txt)와 그림(figures/)
```

## 실행 순서

```bash
pip install -r requirements.txt
cd python
python fetch_europe.py        # 데이터 다시 받기 (data/raw/<오늘 날짜>/ 에 저장)
python build_dataset.py       # data/processed/ 생성
python pre_experiment_de.py   # 독일 사전 실험 재현 → outputs/de_pre_experiment.md
python sensitivity_de.py      # ML 설정 민감도 → outputs/de_sensitivity.csv
cd ..
Rscript R/01_de_simple_regression.R   # → outputs/de_simple_regression.txt, outputs/figures/
```

R 패키지: `install.packages(c("lmtest", "car"))` (MASS는 기본 포함)

## 새 모델을 평가하는 법

모든 모델은 `rolling_eval.py`의 같은 평가 코드를 쓴다. 모델은 `fit_predict(train, test, features, target)` 함수 하나로 만든다.

```python
from rolling_eval import load_country, rolling_forecast, metrics, BASE_FEATURES

def my_model(train, test, features, target):
    ...  # train으로만 적합 (표준화도 train으로만)
    return 예측값_배열

df = load_country("DE")
res = rolling_forecast(df, my_model, BASE_FEATURES)   # 2023-01~2025-12, 36회
print(metrics(res, df))                               # MAPE, RMSE, MASE
```

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

- [x] 유럽 5개국 + FRED 데이터 수집 (2026-11-21 호출, 2008-01~2025-12 결측 없음)
- [x] 국가별 데이터셋 병합 (2025년 소비량·최대월/최소월 비 계획서와 일치)
- [x] 공통 롤링 평가 코드
- [x] 독일 단순회귀 추론·진단·Box-Cox (R)
- [x] 독일 사전 실험 재현 — 통계 모델은 일치, ML 모델은 차이 (아래)
- [ ] 한국 데이터 (KOGAS·기상청·KOSIS) — 기상청·KOSIS API 키 필요
- [ ] 독일 부문별 자료 (THE SLP·RLM)
- [ ] 다중회귀·VIF (Ch6~), 국가별 회귀, DM 검정

## 지금까지의 결과 (독일)

**단순회귀 Y ~ HDD (2008~2025, n = 216)** — `outputs/de_simple_regression.txt`

- R² 0.905. HDD가 1 늘면 월 수요 0.549 PJ 증가 (95% CI 0.525~0.573).
- 기간별 기울기 0.48 → 0.57 → 0.63 PJ, 절편 156 → 147 → 110 PJ (계획서와 일치).
- 등분산: BP(Koenker) p = 0.028 → √Y 변환 후 p = 0.32. Box-Cox 최적 λ = 0.56 (95% CI 0.36~0.76). 계획서의 BP p = 0.004는 재현되지 않았지만 결론(이분산 → √Y로 해소)은 같다.
- **잔차 자기상관이 강하다: Durbin-Watson 0.96 (p < 10⁻¹⁴), √Y 후에도 0.89.** 계획서에 없는 위반으로, 추론(표준오차·구간)을 해석할 때 주의가 필요하다. 시차 변수나 HAC 표준오차를 검토해야 한다.

**롤링 MAPE 재현 (2023~2025, 36회, 추정 시작 2015-01)** — `outputs/de_pre_experiment.md`

| 모델 | 재현 | 계획서 |
| --- | --- | --- |
| 회귀 √Y ~ HDD + 소비자가격 | 6.5% | 6.5% |
| SARIMAX + HDD·소비자가격 | 7.0% | 7.0% |
| 계절 naive | 8.3% | 8.3% |
| 단순회귀 Y ~ HDD | 11.8% | 11.8% |
| Gradient Boosting | 6.6% | 5.6% |
| Ridge (변수 9개) | 6.8% | 6.4% |
| 하이브리드 (회귀 + GBM 잔차) | 6.2% | 6.8% |

- 통계 모델과 외부 변수 표의 OLS 열 9개는 모두 정확히 재현된다. 따라서 데이터와 평가 코드는 원 분석과 같다.
- ML 모델은 원 분석의 설정을 알 수 없어 차이가 난다. 설정만 바꿔도 GBM은 5.7~7.5%, Ridge는 5.6~7.7% 범위에서 움직인다(`outputs/de_sensitivity.csv`). 모델 간 차이 1%p 안팎은 설정 변동 폭보다 작으므로, 모델 순위는 튜닝을 고정한 뒤 DM 검정(R4)으로 판단해야 한다.
- RMSE·MASE 기준으로는 GBM(19.9 PJ, 0.40)이 회귀(25.9 PJ, 0.47)보다 낫다. MAPE는 수요가 낮은 여름 달의 오차를 크게 반영한다.
