# 천연가스 월 수요예측

수요예측 팀: 안형석, 양의창, 권기범

| 폴더 | 내용 | 상태 |
| --- | --- | --- |
| [`korea/`](korea/) | 본 연구. 한국 천연가스 수요의 용도별(도시가스용·발전용)·지역별 1~12개월 앞 예측 | 진행 중 |
| [`multicountry/`](multicountry/) | 6개국(독일·이탈리아·프랑스·스페인·네덜란드·한국) 비교 연구. 같은 모델·같은 평가 절차로 나라별 정확도와 난방 민감도를 비교 | 완료 (태그 `v1-multicountry`) |

공통 준비:

- Python 패키지: `pip install -r requirements.txt`
- API 키(기상청·KOSIS): 저장소 루트의 `.env`에 둔다. 발급 절차는 [`docs/API_KEYS.md`](docs/API_KEYS.md).
- 파운데이션 모델(Chronos-2·TimesFM 2.5)용 가상환경 `.venv-fm`도 저장소 루트에 둔다. 만드는 법은 [`multicountry/README.md`](multicountry/README.md).
