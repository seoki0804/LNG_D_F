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
  fetch_korea.py       한국: KOGAS 공급량(키 불필요), 기상청 HDD·CDD·KOSIS(키 필요)
  fetch_the.py         독일 부문별: THE 일별 SLP·RLM → 월 PJ (키 불필요, 2021-10~)
  build_dataset.py     국가별 월 데이터셋 병합 (영업일 수 포함)
  rolling_eval.py      공통 롤링 평가 코드 (사후·사전예측, MAPE·RMSE·MASE)
  models.py            모델 정의 (회귀·Ridge·Lasso·RF·GBM·LightGBM·SVR·MLP·SARIMAX·Holt-Winters·하이브리드)
  dm_test.py           Diebold-Mariano 검정 (HLN 보정)
  run_experiment.py    본 실험: 튜닝 → 고정 → 6개국 평가 → DM 검정
  r1_variables_de.py   R1 변수 설계: 독일 외부 변수를 같은 튜닝 절차로 평가
  r7_sector.py         R7 부문별 예측: 부문 합산 vs 총량 직접 (독일·한국), 부문별 민감도
  pre_experiment_de.py 계획서의 독일 사전 실험(기본 설정) 재현
  sensitivity_de.py    독일 ML 모델 설정 민감도
R/
  01_de_simple_regression.R   독일 단순회귀 추론(Ch1~2), 진단 plot 6종·검정·Box-Cox(Ch3)
  02_de_multiple_regression.R 독일 다중회귀(Ch6~): 부분 F·VIF·모든 부분집합 선택·HAC 표준오차·추가변수 plot
docs/
  API_KEYS.md          기상청·KOSIS API 키 발급 절차
outputs/
  experiment/          본 실험 결과 (report.md, summary.csv, predictions.csv, dm_tests.csv, tuning.csv)
  figures/             그림
```

## 실행 순서

```bash
pip install -r requirements.txt
cd python
python fetch_europe.py        # 유럽·FRED 데이터 (data/raw/<오늘 날짜>/ 에 원자료 저장)
python fetch_korea.py all     # 한국: KOGAS·기상청·KOSIS (키는 docs/API_KEYS.md, 키 없으면 kogas만 가능)
python fetch_the.py           # 독일 부문별 THE SLP·RLM
python build_dataset.py       # data/processed/ 생성
python run_experiment.py      # 본 실험 6개국 (12코어 약 7분) → outputs/experiment/report.md
python r1_variables_de.py     # R1 (약 4분) → outputs/r1_de_variables.md
python r7_sector.py           # R7 (약 1분, run_experiment 결과 필요) → outputs/r7_sector.md
cd ..
Rscript R/01_de_simple_regression.R     # → outputs/de_simple_regression.txt, outputs/figures/
Rscript R/02_de_multiple_regression.R   # → outputs/de_multiple_regression.txt, outputs/figures/
```

보조 스크립트: `pre_experiment_de.py`(계획서 기본 설정 재현), `sensitivity_de.py`(설정 민감도).
특정 Eurostat 계열만 새로 받기: `python fetch_europe.py wind_gwh` (다른 계열은 수정치로 바뀌지 않는다).

R 패키지: `install.packages(c("lmtest", "car", "sandwich"))` (MASS는 기본 포함)

## 새 모델을 평가하는 법

모든 모델은 `rolling_eval.py`의 같은 평가 코드를 쓴다. 모델은 `fit_predict(train, test, features, target)` 함수 하나로 만든다.

```python
from rolling_eval import load_country, rolling_forecast, metrics, BASE_FEATURES

def my_model(train, test, features, target):
    ...  # train으로만 적합 (표준화도 train으로만)
    return 예측값_배열   # test 행 수만큼

df = load_country("DE")
res = rolling_forecast(df, my_model, BASE_FEATURES, modes=("ex_post", "ex_ante"))  # 2023-01~2025-12, 36회
print(metrics(res[res["mode"] == "ex_post"], df))     # MAPE, RMSE, MASE
```

본 실험에 넣으려면 `run_experiment.py`의 `SPECS`에 `Spec(이름, 특성, build=..., grid=...)` 한 줄을 추가한다. 하이퍼파라미터는 2020~2022 검증 구간에서만 고르고, 2023~2025 평가 구간은 튜닝에 쓰지 않는다.

## 데이터

| 변수 | 유럽 5개국 | 한국 |
| --- | --- | --- |
| 변수 (공통 열 이름) | 유럽 5개국 | 한국 |
| --- | --- | --- |
| 수요 `y` | Eurostat `nrg_cb_gasm` 내수 소비 (PJ, GCV), 2008-01~ | KOGAS 용도별 월 공급량 도시가스용+발전용 (천 톤), 2016-01~ |
| `hdd`, `cdd` | Eurostat `nrg_chdd_m` | 기상청 ASOS 7개 도시(서울·부산·대구·인천·광주·대전·울산) 일평균기온으로 Eurostat 방식 계산, 지점 평균 |
| `price_retail` | Eurostat `prc_hicp_midx` CP0452 (2015=100) | KOSIS 소비자물가 도시가스 `DT_1J22112` (2020=100) |
| `price_wholesale` | FRED `PNGASEUUSDM` (USD/MMBtu) | FRED `PNGASJPUSDM` 아시아 LNG (USD/MMBtu) |
| `ip` | Eurostat `sts_inpr_m` B-D 계절조정 (2021=100) | KOSIS 광공업생산지수 계절조정 총지수 `DT_1F02001` (2020=100) |
| `ip_chem` | Eurostat `sts_inpr_m` C20 | — |
| `nuclear_gwh` | Eurostat `nrg_cb_pem` N9000 (GWh) | — |
| `workdays` | python-holidays 국가 공휴일 | 같음 (설·추석·대체공휴일 포함) |

- 한국 HDD: HDD = Σ(18 − Tm) (Tm ≤ 15°C인 날), CDD = Σ(Tm − 21) (Tm ≥ 24°C인 날)을 지점별로 월합한 뒤 7개 지점을 단순평균한다. 일평균기온 결측 2일(2011-10-16 인천, 2013-09-30 대구)은 앞뒤 날로 보간했다.
- Eurostat `prc_hicp_midx`는 2025년 12월에서 끝난다(COICOP 개편). 2026년 추가 검증에는 대체 출처가 필요하다.
- 한국 소비자 도시가스 요금은 규제 요금이라 몇 달에 한 번만 바뀐다.

## 진행 상황

- [x] 유럽 5개국 + FRED 데이터 수집 (2026-11-21 호출, 2008-01~2025-12 결측 없음)
- [x] 한국 데이터: KOGAS 공급량, 기상청 7개 도시 HDD·CDD, KOSIS 도시가스 CPI·광공업생산지수 (2016-01~2025-12 결측 없음)
- [x] 국가별 데이터셋 병합 (2025년 소비량·최대월/최소월 비 계획서와 일치)
- [x] 공통 롤링 평가 코드 (사후·사전예측)
- [x] 독일 단순회귀 추론·진단·Box-Cox (R)
- [x] 본 실험: 6개국 × 13개 모델, 검증 구간 튜닝, 시드 평균, DM 검정 (R4·R5 일부)
- [x] 독일 부문별 자료 THE SLP·RLM (2021-10~, Eurostat 총량과 상관 0.995), 부문별 예측 (R7)
- [x] 독일 다중회귀·VIF·변수선택·HAC (Ch6~), 외부 변수 평가 (R1)
- [ ] 국가별 회귀계수·HDD 민감도 비교 (R5), 구조변화 대응 (R2)
- [ ] 6개국 통합 모델 (R6), SHAP (R3), 파운데이션 모델 (R8)

## 본 실험 결과 (6개국) — `outputs/experiment/report.md`

2023~2025년 롤링 1개월 앞 사후예측 MAPE(%). 하이퍼파라미터는 2020~2022년 검증 구간에서만 골랐다.

| 모델 | 독일 | 이탈리아 | 프랑스 | 스페인 | 네덜란드 | 한국 |
| --- | --- | --- | --- | --- | --- | --- |
| 기준: 회귀 √Y~HDD+가격 | 6.5 | 9.1 | 10.0 | 9.8 | 17.1 | 4.6 |
| SARIMAX+HDD·가격 | 7.0 | 6.0 | 9.1 | 6.9 | 10.2 | **4.5** |
| Holt-Winters | 7.6 | 6.7 | 13.6 | **5.7** | 9.3 | 6.1 |
| Ridge | 5.6 | 5.6 | 7.1 | 9.2 | 10.5 | 6.6 |
| Gradient Boosting | 5.8 | 5.7 | 7.0 | 6.3 | **7.5** | 5.1 |
| LightGBM | **5.3** | 5.3 | 10.2 | 7.6 | 7.5 | 6.1 |
| MLP (16-8) | 5.8 | 5.6 | 7.1 | 7.3 | 8.8 | 5.3 |
| 하이브리드 (회귀+GBM 잔차) | 6.3 | **4.3** | **6.5** | 7.5 | 7.9 | 4.6 |

- **최고 모델이 국가마다 다르다.** 독일은 LightGBM, 이탈리아·프랑스는 하이브리드, 스페인은 Holt-Winters, 네덜란드는 GBM, 한국은 SARIMAX다.
- **기준 회귀는 수요 수준이 구조적으로 바뀐 나라에서 크게 틀린다.** 네덜란드는 17.1%, 프랑스는 10.0%다. 전월 수요를 쓰는 모델은 이 변화를 따라간다.
- **한국은 HDD 하나로 충분하다.** 단순회귀 4.6%보다 유의하게 정확한 모델이 없고, Ridge·LightGBM·SVR은 유의하게 부정확하다(DM p < 0.05).
- **독일에서 기준 회귀보다 유의하게 정확한 모델은 Lasso 하나뿐이다**(p = 0.034). LightGBM(5.3%)도 p = 0.29로 유의하지 않다. 36개월 평가로는 1%p 차이를 가르기 어렵다.
- **사전예측(평년 HDD)에서는 트리 모델이 크게 나빠진다**(독일 GBM 5.8% → 9.2%). 하이브리드·MLP·Ridge가 더 안정적이다. MLP는 시드에 따라 MAPE가 ±0.4~1.3%p 흔들린다.

## R1 외부 변수 (독일) — `outputs/r1_de_variables.md`

변수 조합마다 검증 구간에서 다시 튜닝해 고정한 사후예측 MAPE(%). 기존 변수는 회귀 6.5 / Ridge 5.6 / Lasso 5.6 / GBM 5.8 / LightGBM 5.3이다.

- 외부 변수(영업일·화학 생산·원자력·풍력·석탄 가격 등)는 모델에 따라 −0.6~+1.7%p로 엇갈리고, 같은 모델의 기존 변수 대비 DM 검정에서 유의하게 좋아진 경우는 Lasso + 화학 생산지수 하나뿐이다.
- 화학 + 영업일 + 원자력 조합: Ridge 5.5, GBM 5.3 (계획서의 5.3, 5.0은 튜닝 없이 나온 값). 유의한 개선은 없다.
- 사전예측에서는 외부 변수가 대부분 오차를 키운다. 같은 달 값을 미리 알 수 없기 때문이다.
- 결론: 본 실험은 기본 9개 변수를 유지한다.

## 독일 다중회귀 (Ch6~) — `outputs/de_multiple_regression.txt`

√Y ~ HDD, CDD, 소비자요금, 전월 도매가, 산업생산, 화학 생산, 영업일, 원자력, 풍력, 2022년 위기(2022-03~) 더미와 HDD×위기, 2008-02~2025-12 (n = 215).

- **VIF:** 소비자요금 21, 위기 더미 19. 2022년에 요금 급등과 수요 감축이 함께 일어나 두 효과를 따로 추정하기 어렵다.
- **변수선택:** BIC 최적은 √Y ~ HDD + 풍력 + 위기 + HDD×위기 (R² 0.927). 수정 R²·AIC·PRESS 최적은 여기에 영업일·원자력을 더한 7개 계수 모형이다.
- **위기 후 변화:** 기저수요는 줄고 난방 민감도는 커졌다. 평균 수준에서 HDD 1당 0.50 PJ → 0.61 PJ (HDD×위기 HAC p < 0.001).
- **영업일 t값:** 1.8 (HAC 1.9)로 유의하지 않다. 계획서의 t = 3.3은 재현되지 않는다.
- **풍력 계수:** 양(+)으로, 예상(풍력↑ → 가스 발전↓)과 반대다. 풍력이 겨울에 많아 계절성과 섞인 것으로 보이며, 인과 해석은 하지 않는다.
- **잔차:** 다중회귀 후에도 자기상관이 남는다(DW 1.12). OLS 표준오차 대신 Newey-West 표준오차로 추론했다.

## R7 부문별 예측 — `outputs/r7_sector.md`

같은 모델로 부문별 예측을 합산한 값과 총량을 바로 예측한 값의 사후예측 MAPE(%). 하이퍼파라미터는 본 실험의 설정을 쓴다.

| 모델 | 독일 직접 | 독일 합산 | 한국 직접 | 한국 합산 |
| --- | --- | --- | --- | --- |
| 회귀 √Y~HDD+가격 | 3.9 | 3.7 | 4.6 | 4.6 |
| SARIMAX+HDD·가격 | 4.7 | 4.6 | 4.5 | 4.4 |
| Gradient Boosting | 5.6 | 5.1 | 5.1 | 5.7 |
| 하이브리드 | 4.4 | 3.7 | 4.6 | 4.7 |

- 독일(THE 총량, 평가 2024~2025년 24회)은 합산이 대체로 조금 더 정확하지만 유의하지 않다(DM p ≥ 0.13). 한국은 차이가 없다.
- **부문별 HDD 민감도:** 독일 SLP는 HDD 10당 수요 +4.7%로 RLM(+1.1%)의 4배다. 한국은 도시가스용 +1.9%, 발전용 +0.7%다.
- **요금 탄력성:** 독일 RLM(산업·발전)만 유의하다(−0.29). 한국은 규제 요금이라 유의하지 않다.
- THE 자료는 2021-10부터라 독일 부문 모델의 학습 표본이 15~27개월로 짧다. 그래서 독일 직접 예측 MAPE(3.9%)는 본 실험(Eurostat 총량, 2023~2025)과 바로 비교하지 않는다.

## 독일 상세 결과

**단순회귀 Y ~ HDD (2008~2025, n = 216)** — `outputs/de_simple_regression.txt`

- R² 0.905. HDD가 1 늘면 월 수요 0.549 PJ 증가 (95% CI 0.525~0.573).
- 기간별 기울기 0.48 → 0.57 → 0.63 PJ, 절편 156 → 147 → 110 PJ (계획서와 일치).
- 등분산: BP(Koenker) p = 0.028 → √Y 변환 후 p = 0.32. Box-Cox 최적 λ = 0.56 (95% CI 0.36~0.76). 계획서의 BP p = 0.004는 재현되지 않았지만 결론(이분산 → √Y로 해소)은 같다.
- **잔차 자기상관이 강하다: Durbin-Watson 0.96 (p < 10⁻¹⁴), √Y 후에도 0.89.** 계획서에 없는 위반으로, 추론(표준오차·구간)을 해석할 때 주의가 필요하다. 시차 변수나 HAC 표준오차를 검토해야 한다.

**계획서 사전 실험 재현 (기본 설정, 튜닝 없음)** — `outputs/de_pre_experiment.md`

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
- ML 모델은 원 분석의 설정을 알 수 없어 차이가 난다. 설정만 바꿔도 GBM은 5.7~7.5%, Ridge는 5.6~7.7% 범위에서 움직인다(`outputs/de_sensitivity.csv`). 그래서 본 실험은 검증 구간 튜닝으로 설정을 고정했다. **보고서·발표에는 본 실험 수치를 쓴다** (계획서의 GBM 5.6%, Ridge 6.4% 대신 GBM 5.8%, Ridge 5.6%, LightGBM 5.3%).
- RMSE·MASE 기준으로는 GBM(19.9 PJ, 0.40)이 회귀(25.9 PJ, 0.47)보다 낫다. MAPE는 수요가 낮은 여름 달의 오차를 크게 반영한다.
