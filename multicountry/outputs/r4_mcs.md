# R4 모델 신뢰집합 (MCS, 90%)

2023~2025 롤링 1개월 앞, 손실 APE. 'MCS 포함' = 그 나라 최고 모델과 통계적으로 구별되지 않는다 (Hansen et al. 2011, 범위 통계량, 정상 부트스트랩 5,000회).

## 사후예측: 6개국 평균 손실 MCS (월별 국가 평균 APE, 36개월)

후보 25개 중 10개: Chronos-2 + 공변량 (5.7, p=1.00), 앙상블: 회귀(위기)+ML+Chronos (5.7, p=0.98), 앙상블: 검증 상위 3 (5.7, p=0.98), SARIMAX+HDD·가격 (6.0, p=0.84), 앙상블: ML 평균 (6.0, p=0.41), GBM + 위기 변수 (6.1, p=0.57), Gradient Boosting (6.1, p=0.57), 하이브리드 (회귀+GBM 잔차) (6.1, p=0.57), Ridge + 위기 변수 (6.3, p=0.33), TimesFM 2.5 + 공변량(XReg) (6.4, p=0.57)

## 사후예측: 국가별 MCS 크기와 구성

| 국가 | 후보 수 | MCS 크기 | MCS에 남은 모델 (MAPE %) |
| --- | --- | --- | --- |
| 독일 | 25 | 12 | 앙상블: 회귀(위기)+ML (4.2), 앙상블: ML 평균 (4.3), 앙상블: 회귀(위기)+ML+Chronos (4.3), Ridge + 위기 변수 (5.0), 앙상블: 검증 상위 3 (5.1), LightGBM (5.3), 회귀 + 위기 변수 (5.4), GBM + 위기 변수 (5.5), SARIMAX+HDD·가격 (5.7), Gradient Boosting (5.8), MLP (16-8) (5.8), Random Forest (6.9) |
| 이탈리아 | 25 | 20 | TimesFM 2.5 + 공변량(XReg) (4.0), Chronos-2 + 공변량 (4.3), SARIMAX+HDD·가격 (4.3), 하이브리드 (회귀+GBM 잔차) (4.3), 앙상블: 검증 상위 3 (4.5), Holt-Winters (4.8), 앙상블: ML 평균 (4.9), Chronos-2 단변량 (4.9), 앙상블: 회귀(위기)+ML+Chronos (4.9), LightGBM (5.3), 앙상블: 회귀(위기)+ML (5.4), TimesFM 2.5 단변량 (5.4), GBM + 위기 변수 (5.5), MLP (16-8) (5.6), Ridge + 위기 변수 (5.6), Gradient Boosting (5.7), 통합 LightGBM (6개국) (5.7), SVR (5.8), Random Forest (7.0), 계절 naive (8.0) |
| 프랑스 | 25 | 18 | Chronos-2 + 공변량 (5.8), 하이브리드 (회귀+GBM 잔차) (6.5), SARIMAX+HDD·가격 (6.9), Gradient Boosting (7.0), 앙상블: 회귀(위기)+ML+Chronos (7.0), 앙상블: ML 평균 (7.1), 앙상블: 검증 상위 3 (7.1), Ridge (7.1), MLP (16-8) (7.1), GBM + 위기 변수 (7.2), TimesFM 2.5 + 공변량(XReg) (7.4), 앙상블: 회귀(위기)+ML (7.5), TimesFM 2.5 단변량 (7.7), 통합 LightGBM (6개국) (7.8), Ridge + 위기 변수 (7.8), 회귀 √Y~HDD+가격 (10.0), SVR (10.3), 회귀 + 위기 변수 (10.8) |
| 스페인 | 25 | 21 | Chronos-2 단변량 (5.5), TimesFM 2.5 단변량 (5.6), TimesFM 2.5 + 공변량(XReg) (5.6), 앙상블: 검증 상위 3 (5.7), Holt-Winters (6.0), SARIMAX+HDD·가격 (6.0), Chronos-2 + 공변량 (6.0), Gradient Boosting (6.3), GBM + 위기 변수 (6.7), 앙상블: 회귀(위기)+ML+Chronos (6.7), Random Forest (6.9), 앙상블: 회귀(위기)+ML (7.0), 앙상블: ML 평균 (7.0), MLP (16-8) (7.3), SVR (7.3), 하이브리드 (회귀+GBM 잔차) (7.5), LightGBM (7.6), Ridge + 위기 변수 (7.9), 회귀 + 위기 변수 (8.5), 회귀 √Y~HDD+가격 (9.8), 단순회귀 Y~HDD (9.9) |
| 네덜란드 | 25 | 16 | Chronos-2 + 공변량 (5.4), Holt-Winters (6.0), Chronos-2 단변량 (6.6), Ridge + 위기 변수 (6.8), TimesFM 2.5 단변량 (6.9), 앙상블: 회귀(위기)+ML+Chronos (7.0), 앙상블: 검증 상위 3 (7.1), 회귀 + 위기 변수 (7.2), GBM + 위기 변수 (7.2), Gradient Boosting (7.5), 앙상블: 회귀(위기)+ML (7.5), LightGBM (7.5), SARIMAX+HDD·가격 (7.6), 통합 LightGBM (6개국) (7.7), 하이브리드 (회귀+GBM 잔차) (7.9), SVR (8.2) |
| 한국 | 25 | 21 | 앙상블: 회귀(위기)+ML (4.1), 앙상블: 회귀(위기)+ML+Chronos (4.3), 하이브리드 (회귀+GBM 잔차) (4.3), 단순회귀 Y~HDD (4.6), Gradient Boosting (4.6), 회귀 √Y~HDD+가격 (4.7), TimesFM 2.5 + 공변량(XReg) (4.7), 앙상블: ML 평균 (4.7), GBM + 위기 변수 (4.7), Ridge + 위기 변수 (4.7), 통합 LightGBM (6개국) (4.8), 회귀 + 위기 변수 (4.9), Lasso (4.9), Ridge (5.0), 앙상블: 검증 상위 3 (5.0), SARIMAX+HDD·가격 (5.2), LightGBM (5.3), MLP (16-8) (5.6), Random Forest (5.7), Holt-Winters (6.3), TimesFM 2.5 단변량 (6.7) |

### 사후예측: 모델별로 MCS에 포함된 나라 수 (6개국 중)

| 모델 | 포함 국가 수 | 6개국 평균 MAPE |
| --- | --- | --- |
| 앙상블: 회귀(위기)+ML+Chronos | 6 | 5.7 |
| 앙상블: 검증 상위 3 | 6 | 5.7 |
| 앙상블: 회귀(위기)+ML | 6 | 6.0 |
| SARIMAX+HDD·가격 | 6 | 6.0 |
| GBM + 위기 변수 | 6 | 6.1 |
| Gradient Boosting | 6 | 6.1 |
| Ridge + 위기 변수 | 6 | 6.3 |
| 앙상블: ML 평균 | 5 | 6.0 |
| 하이브리드 (회귀+GBM 잔차) | 5 | 6.1 |
| TimesFM 2.5 단변량 | 5 | 6.7 |
| MLP (16-8) | 5 | 6.7 |
| LightGBM | 5 | 6.8 |
| 회귀 + 위기 변수 | 5 | 7.6 |
| Chronos-2 + 공변량 | 4 | 5.7 |
| TimesFM 2.5 + 공변량(XReg) | 4 | 6.4 |
| 통합 LightGBM (6개국) | 4 | 6.7 |
| Holt-Winters | 4 | 7.5 |
| Random Forest | 4 | 8.0 |
| SVR | 4 | 8.0 |
| Chronos-2 단변량 | 3 | 6.6 |
| 회귀 √Y~HDD+가격 | 3 | 9.5 |
| Ridge | 2 | 7.2 |
| 단순회귀 Y~HDD | 2 | 14.0 |
| Lasso | 1 | 7.6 |
| 계절 naive | 1 | 9.1 |

## 사전예측: 6개국 평균 손실 MCS (월별 국가 평균 APE, 36개월)

후보 25개 중 4개: Chronos-2 + 공변량 (6.4, p=1.00), Chronos-2 단변량 (6.6, p=0.46), TimesFM 2.5 단변량 (6.7, p=0.46), SARIMAX+HDD·가격 (7.2, p=0.23)

## 사전예측: 국가별 MCS 크기와 구성

| 국가 | 후보 수 | MCS 크기 | MCS에 남은 모델 (MAPE %) |
| --- | --- | --- | --- |
| 독일 | 25 | 21 | Ridge + 위기 변수 (6.2), 앙상블: 검증 상위 3 (6.4), 하이브리드 (회귀+GBM 잔차) (6.4), MLP (16-8) (6.7), Ridge (6.7), Lasso (6.8), Chronos-2 단변량 (6.8), 앙상블: 회귀(위기)+ML+Chronos (6.9), 앙상블: ML 평균 (6.9), SARIMAX+HDD·가격 (7.0), 앙상블: 회귀(위기)+ML (7.0), 통합 LightGBM (6개국) (7.0), Chronos-2 + 공변량 (7.4), LightGBM (7.4), 회귀 + 위기 변수 (7.7), TimesFM 2.5 단변량 (7.9), TimesFM 2.5 + 공변량(XReg) (8.0), 계절 naive (8.3), Gradient Boosting (9.2), Holt-Winters (9.2), Random Forest (9.5) |
| 이탈리아 | 25 | 22 | Holt-Winters (4.8), Chronos-2 단변량 (4.9), Chronos-2 + 공변량 (5.2), TimesFM 2.5 단변량 (5.4), SVR (5.8), 앙상블: ML 평균 (5.9), 앙상블: 회귀(위기)+ML+Chronos (6.0), Ridge + 위기 변수 (6.1), 통합 LightGBM (6개국) (6.2), 앙상블: 검증 상위 3 (6.3), MLP (16-8) (6.3), 하이브리드 (회귀+GBM 잔차) (6.3), 앙상블: 회귀(위기)+ML (6.4), LightGBM (6.4), GBM + 위기 변수 (6.5), SARIMAX+HDD·가격 (6.6), Ridge (6.8), Gradient Boosting (6.8), TimesFM 2.5 + 공변량(XReg) (6.9), Lasso (6.9), Random Forest (7.9), 계절 naive (8.0) |
| 프랑스 | 25 | 14 | Chronos-2 + 공변량 (7.4), TimesFM 2.5 단변량 (7.7), MLP (16-8) (7.9), SARIMAX+HDD·가격 (8.2), 통합 LightGBM (6개국) (8.7), Chronos-2 단변량 (8.8), Ridge (8.9), TimesFM 2.5 + 공변량(XReg) (9.0), SVR (9.5), 하이브리드 (회귀+GBM 잔차) (9.5), Ridge + 위기 변수 (9.5), 앙상블: 회귀(위기)+ML+Chronos (9.6), 앙상블: ML 평균 (9.7), 계절 naive (10.7) |
| 스페인 | 25 | 15 | Chronos-2 단변량 (5.5), TimesFM 2.5 단변량 (5.6), Holt-Winters (6.0), Chronos-2 + 공변량 (6.1), TimesFM 2.5 + 공변량(XReg) (6.2), 앙상블: 검증 상위 3 (6.3), SARIMAX+HDD·가격 (6.6), 앙상블: 회귀(위기)+ML+Chronos (7.1), Gradient Boosting (7.1), SVR (7.1), 앙상블: 회귀(위기)+ML (7.5), 하이브리드 (회귀+GBM 잔차) (7.9), Ridge + 위기 변수 (7.9), Random Forest (8.1), 회귀 + 위기 변수 (8.8) |
| 네덜란드 | 25 | 14 | Holt-Winters (6.0), Chronos-2 단변량 (6.6), Chronos-2 + 공변량 (6.7), TimesFM 2.5 단변량 (6.9), 계절 naive (7.8), SARIMAX+HDD·가격 (8.1), Ridge + 위기 변수 (8.3), GBM + 위기 변수 (8.6), 앙상블: 회귀(위기)+ML+Chronos (8.7), LightGBM (8.8), 회귀 + 위기 변수 (9.1), Gradient Boosting (9.2), 통합 LightGBM (6개국) (9.2), SVR (9.6) |
| 한국 | 25 | 24 | MLP (16-8) (5.1), 앙상블: 회귀(위기)+ML+Chronos (5.3), 앙상블: 회귀(위기)+ML (5.3), 앙상블: ML 평균 (5.4), Gradient Boosting (5.5), 통합 LightGBM (6개국) (5.5), GBM + 위기 변수 (5.5), Chronos-2 + 공변량 (5.6), TimesFM 2.5 + 공변량(XReg) (5.6), 앙상블: 검증 상위 3 (5.7), 하이브리드 (회귀+GBM 잔차) (6.1), Lasso (6.2), 회귀 √Y~HDD+가격 (6.2), Random Forest (6.2), LightGBM (6.2), Holt-Winters (6.3), Ridge (6.3), 단순회귀 Y~HDD (6.4), 회귀 + 위기 변수 (6.4), Ridge + 위기 변수 (6.4), TimesFM 2.5 단변량 (6.7), SARIMAX+HDD·가격 (6.8), Chronos-2 단변량 (6.9), SVR (7.4) |

### 사전예측: 모델별로 MCS에 포함된 나라 수 (6개국 중)

| 모델 | 포함 국가 수 | 6개국 평균 MAPE |
| --- | --- | --- |
| Chronos-2 + 공변량 | 6 | 6.4 |
| Chronos-2 단변량 | 6 | 6.6 |
| TimesFM 2.5 단변량 | 6 | 6.7 |
| SARIMAX+HDD·가격 | 6 | 7.2 |
| 앙상블: 회귀(위기)+ML+Chronos | 6 | 7.3 |
| Ridge + 위기 변수 | 6 | 7.4 |
| 통합 LightGBM (6개국) | 5 | 7.5 |
| Holt-Winters | 5 | 7.5 |
| TimesFM 2.5 + 공변량(XReg) | 5 | 7.6 |
| 하이브리드 (회귀+GBM 잔차) | 5 | 7.9 |
| Gradient Boosting | 5 | 8.2 |
| SVR | 5 | 8.4 |
| MLP (16-8) | 4 | 7.4 |
| 앙상블: 검증 상위 3 | 4 | 7.5 |
| 앙상블: ML 평균 | 4 | 7.5 |
| 앙상블: 회귀(위기)+ML | 4 | 7.6 |
| LightGBM | 4 | 8.3 |
| Ridge | 4 | 8.4 |
| 계절 naive | 4 | 9.1 |
| 회귀 + 위기 변수 | 4 | 9.3 |
| Random Forest | 4 | 9.5 |
| GBM + 위기 변수 | 3 | 8.2 |
| Lasso | 3 | 9.3 |
| 회귀 √Y~HDD+가격 | 1 | 11.8 |
| 단순회귀 Y~HDD | 1 | 17.0 |

