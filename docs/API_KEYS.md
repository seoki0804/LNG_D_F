# API 키 발급과 설정

한국 자료 중 두 가지만 키가 필요하다. KOGAS 공급량, Eurostat, FRED는 키 없이 받는다.

| 자료 | 발급처 | 승인 | 쓰는 곳 |
| --- | --- | --- | --- |
| 기상청 ASOS 일평균기온 → 한국 HDD·CDD | 공공데이터포털 (data.go.kr) | 자동승인, 즉시 | `KMA_SERVICE_KEY` |
| 도시가스 소비자물가, 광공업생산지수 | KOSIS 공유서비스 (kosis.kr/openapi) | 즉시 발급 | `KOSIS_API_KEY` |

팀에서 한 사람만 받으면 된다. 키는 개인 계정에 묶이므로 저장소에 올리지 말고 각자 `.env`에 둔다.

## 1. 기상청 ASOS 일자료 (공공데이터포털)

1. [공공데이터포털](https://www.data.go.kr)에 회원가입하고 로그인한다.
2. [기상청_지상(종관, ASOS) 일자료 조회서비스](https://www.data.go.kr/data/15059093/openapi.do) 페이지에서 **활용신청**을 누른다.
3. 활용목적(예: 학습/연구, "대학 수업 수요예측 프로젝트")을 적고, 라이선스에 동의한 뒤 신청한다. 자동승인이라 바로 승인된다.
4. **마이페이지 → 데이터 활용 → Open API → 활용신청 현황**에서 이 서비스를 누르고 **일반 인증키 (Decoding)** 값을 복사한다.
   - Encoding/Decoding 두 개가 보이면 **Decoding** 키를 쓴다. 코드(requests)가 알아서 인코딩한다.
5. 승인 직후 1~2시간은 `SERVICE_KEY_IS_NOT_REGISTERED_ERROR`가 날 수 있다. 시간이 지나면 해결된다.

개발계정 한도는 하루 10,000건이다. 이 프로젝트는 7개 지점 × 21년 = 약 150건이면 충분하다.

## 2. KOSIS 공유서비스 (통계청·국가데이터처)

1. [KOSIS 공유서비스](https://kosis.kr/openapi/)에 접속해 로그인한다 (KOSIS 회원가입 필요).
2. 상단 **활용신청**에서 약관에 동의하고 활용 목적을 적어 신청한다. 인증키가 바로 발급된다.
3. **마이페이지 → 활용신청현황**에서 인증키를 복사한다.

## 3. 키 넣기

저장소 루트(README.md가 있는 폴더)에 `.env` 파일을 만들고 다음처럼 적는다. `.env.example`을 복사해 써도 된다.

```
KMA_SERVICE_KEY=여기에_공공데이터포털_Decoding_키
KOSIS_API_KEY=여기에_KOSIS_키
```

`.env`는 `.gitignore`에 들어 있어 커밋되지 않는다. 키를 채팅이나 저장소에 붙여넣지 말 것.

## 4. 받기

```bash
cd python
python fetch_korea.py all                    # KOGAS + 기상청 HDD·CDD + KOSIS 전부
python fetch_korea.py kma-local              # 기상청을 다시 호출하지 않고 저장된 일자료로 HDD만 재계산
python fetch_korea.py kosis-search 도시가스   # 새 KOSIS 통계표를 찾을 때
python build_dataset.py                      # data/processed/KR.csv 생성
```

KOSIS 계열 코드는 `fetch_korea.py`의 `KOSIS_SERIES`에 있다 (도시가스 CPI `DT_1J22112`, 광공업생산지수 `DT_1F02001`). 새 계열을 추가할 때는 `kosis_meta(org_id, tbl_id)`로 분류·항목 코드를 확인한다.
