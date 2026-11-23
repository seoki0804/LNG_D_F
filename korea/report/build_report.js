// 한국 연구 최종 보고서(논문 형식, .docx). 수치는 numbers.json(python/report_numbers.py)에서 읽는다.
// 실행: korea/ 에서  node report/build_report.js   → report/한국_LNG_수요예측_보고서.docx
const fs = require("fs");
const path = require("path");
const K = require("./docx_kit");
const { P, H1, H2, BUL, NUM, EQ, FIG, TABLE, build, Paragraph, TextRun, AlignmentType } = K;

const ROOT = path.resolve(__dirname, "..");
const fig = (n) => path.join(ROOT, "outputs", "figures", n);
const N = JSON.parse(fs.readFileSync(path.join(__dirname, "numbers.json"), "utf8"));
const f0 = (x) => (x == null ? "–" : Number(x).toFixed(0));
const f1 = (x) => (x == null ? "–" : Number(x).toFixed(1));
const f2 = (x) => (x == null ? "–" : Number(x).toFixed(2));
const pv = (x) => (x < 0.001 ? "p < 0.001" : `p = ${x.toFixed(3)}`);

// ---------------- 수치 도우미 ----------------
const SER = { total: "합계", city: "도시가스용", power: "발전용" };
const NM = { "계절 naive": "Seasonal Naive", "회귀 √Y": "OLS(√Y)", SARIMAX: "SARIMAX", ETS: "ETS", Ridge: "Ridge(직접)",
  LightGBM: "LightGBM(직접)", "하이브리드 (회귀+Ridge)": "Hybrid(OLS+Ridge)", "하이브리드 (회귀+LightGBM)": "Hybrid(OLS+LightGBM)",
  "Chronos-2": "Chronos-2(단변량)", "Chronos-2 + 공변량": "Chronos-2(공변량)", "TimesFM 2.5": "TimesFM 2.5", 앙상블: "Ensemble" };
const nm = (m) => NM[m] || m;
const nat = (s, m, k = "all", i = "ex_ante", w = "eval") => (N.nat[`${s}|${m}|${i}|${w}`] || {})[k];
const MODELS = Object.keys(NM);
const ranked = (s, k = "all", i = "ex_ante", w = "eval") =>
  MODELS.map((m) => [m, nat(s, m, k, i, w)]).filter((x) => x[1] != null).sort((a, b) => a[1] - b[1]);
const best = (s, k, i, w) => ranked(s, k, i, w)[0];
const mcs = (s, h = "all", i = "ex_ante") => N.mcs[`${s}|${i}|${h}`] || [];
const inMcs = (s, m, h = "all", i = "ex_ante") => mcs(s, h, i).includes(m);
const outMcs = (s) => MODELS.filter((m) => nat(s, m) != null && !mcs(s).includes(m)).map(nm).join("·") || "없음";
const prov = (m, me, lv, k = "all") => (N.prov[`${m}|${me}|${lv}`] || {})[k];
const R = N.reg, D = N.data;
const PROV_EN = { 서울: "서울", 제주: "제주", 울산: "울산" };
const ML = ["Ridge", "LightGBM", "하이브리드 (회귀+Ridge)", "하이브리드 (회귀+LightGBM)"];
const bestML = ML.map((m) => [m, (nat("total", m) + nat("city", m) + nat("power", m)) / 3]).sort((a, b) => a[1] - b[1])[0][0];
const gap = (s, m) => nat(s, m, "all", "ex_ante") - nat(s, m, "all", "ex_post");
const share = (s, m) => 100 * gap(s, m) / nat(s, m, "all", "ex_ante");
const holdRank = (s) => ranked(s, "all", "ex_ante", "hold");

const children = [];
const add = (...xs) => xs.flat().forEach((x) => children.push(x));

// ---------------- 표지 ----------------
add(
  new Paragraph({ style: "Title", children: [new TextRun("한국 LNG 수요의 용도별·지역별 예측:")] }),
  new Paragraph({ style: "Title", children: [new TextRun("회귀분석, 기계학습, 시계열 파운데이션 모델의 비교")] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 240 }, children: [new TextRun({ text:
    "Forecasting LNG demand in Korea by use and region: regression, machine learning and time-series foundation models",
    italics: true, size: 19, color: "52514E" })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 60 }, children: [new TextRun({ text: "안형석, 양의창, 권기범", size: 21 })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 360 }, children: [new TextRun({ text: "수요예측 수업 최종 보고서 · 2026년 11월", size: 19, color: "52514E" })] }),
);

// ---------------- 요약 ----------------
const tb = best("total"), cb = best("city"), pb = best("power");
add(
  H2("요약"),
  P(`한국 천연가스 수요를 도시가스용과 발전용, 그리고 17개 시도로 나눠 1~12개월 앞을 예측하였다. 회귀분석으로 수요 구조를 추론한 뒤, 통계 시계열·기계학습·시계열 파운데이션 모델을 같은 롤링 평가 틀에서 비교하였다. 도시가스용 수요는 수요가중 난방도일(HDD) 하나로 변동의 ${f1(R.r2_simple * 100)}%가 설명되었지만, 발전용은 기온으로 ${f0(R.r2_power_weather * 100)}%만 설명되었다. 2023~2025년 목표월에 대한 1~12개월 앞 사전예측(평년 기온 사용)의 평균 MAPE는 도시가스용 ${f1(cb[1])}%(${nm(cb[0])}), 발전용 ${f1(pb[1])}%(${nm(pb[0])}), 합계 ${f1(tb[1])}%(${nm(tb[0])})로, 발전용이 도시가스용보다 두 배가량 어려웠다. 실제 기온을 미리 안다고 가정하면 도시가스용 오차는 ${f0(share("city", "앙상블"))}% 줄어들어, 도시가스용 오차의 상당 부분이 기온 예보로 줄일 수 있는 몫이었다. 시도별 난방 민감도는 HDD 10 증가당 판매량 ${f1(N.province_sens_range.min)}%(${N.province_sens_range.min_prov})에서 ${f1(N.province_sens_range.max)}%(${N.province_sens_range.max_prov})까지 유의하게 달랐고, 시도 예측을 합쳐 전국을 맞추는 계층 예측은 기본 모델이 약할 때만 전국 예측을 개선하였다. 같은 모델을 유럽 5개국에 적용한 결과와 비교하면 한국은 난방 민감도가 낮고 1개월 앞 예측이 가장 쉬운 나라에 속했다.`),
  P("**주제어**: 천연가스 수요예측, 다기간 예측, 난방도일, 계층 예측, 모델 신뢰집합, 시계열 파운데이션 모델"),
);

// ---------------- 1. 서론 ----------------
add(
  H1("1. 서론"),
  P(`한국은 천연가스를 거의 모두 LNG로 수입하므로, 몇 달 앞의 수요를 보고 도입 물량과 저장 계획을 정해야 한다. 월별 수요는 성격이 다른 두 부분으로 이루어진다. 도시가스용은 난방 때문에 겨울에 몰려 연중 최대월이 최소월의 약 ${f1(D.city_peak_ratio)}배에 이르고, 발전용은 전력수급과 연료 가격에 따라 움직여 계절 진폭이 ${f1(D.power_peak_ratio)}배로 작다. 2025년 공급량은 도시가스용 ${f0(D.city_2025)}만 톤, 발전용 ${f0(D.power_2025)}만 톤이었다.`),
  P("기존 연구는 주로 하루~1개월 앞 예측을 다뤘고(박진수 외, 2013; Tian et al., 2023), 수급계획에 필요한 몇 달 앞 예측에서 어떤 모델이 나은지, 그리고 그 오차 가운데 얼마가 기온 불확실성 때문인지는 잘 알려져 있지 않다. 최근에는 학습 없이 바로 쓰는 시계열 파운데이션 모델(Chronos-2, TimesFM)이 나왔지만, 작은 월별 에너지 자료에서의 성능은 검증이 부족하다. 이 연구는 다음 질문에 답한다."),
  NUM("도시가스용과 발전용 수요는 무엇으로 설명되는가? 회귀 가정은 어디서 깨지는가?"),
  NUM("시도마다 난방 민감도는 얼마나 다르고, 시간에 따라 변했는가?"),
  NUM("1~12개월 앞 예측에서 어떤 모델이 정확하며, 예측 시계가 길어지면 순위가 바뀌는가?"),
  NUM("기온을 미리 안다면 오차는 얼마나 줄어드는가?"),
  NUM("시도별로 나눠 예측해 합치면 전국 예측이 좋아지는가? 한국의 결과는 다른 나라와 비교해 어떤가?"),
);

// ---------------- 2. 자료 ----------------
add(
  H1("2. 자료"),
  P(`분석 단위는 월이다. 전국 수요는 한국가스공사의 용도별 월 공급량(도시가스용·발전용, 천 톤)으로 ${D.start}부터 ${D.end}까지 ${D.n}개월이다. 지역 수요는 같은 기관의 시도별 도시가스 판매량(17개 시도, 백만 ㎥)을 쓴다. 자료는 2026년 11월 21일에 받았다.`),
  ...TABLE([
    ["자료", "출처", "기간", "쓰임"],
    ["용도별 월 공급량 (도시가스용·발전용)", "한국가스공사 (공공데이터포털)", "2016.01~2026.09", "전국 예측·회귀"],
    ["시도별 도시가스 판매량 (17개 시도)", "한국가스공사 (공공데이터포털)", "1989.01~2022.12", "지역 예측·회귀"],
    ["일평균기온 (시도 대표 관측소 25곳)", "기상청 ASOS", "1989.01~2026.10", "HDD·CDD·평년값"],
    ["도시가스 소비자물가, 광공업생산지수", "통계청 KOSIS", "1989~2026", "요금·산업"],
    ["월별 전력거래량", "KOSIS (전력거래소)", "2001~2025", "발전용 회귀"],
    ["아시아 LNG 가격", "FRED (PNGASJPUSDM)", "1992~2026", "발전용 회귀·예측"],
  ], [0.36, 0.26, 0.2, 0.18], "표 1. 자료", { alignLeft: [1] }),
  P(`난방도일(HDD)은 일평균기온이 15°C 이하인 날의 (18 − 기온)을, 냉방도일(CDD)은 24°C 이상인 날의 (기온 − 21)을 월별로 합한 값이다(Eurostat 방식). 넓은 도는 관측소 2~3곳을 평균했고, 전국 HDD는 2016~2018년 시도별 도시가스 판매 비중으로 가중한 수요가중 HDD다. 평년값은 직전 10년 같은 달의 평균이다.`),
  P(`자료 점검에서 세 가지를 고쳤다. 첫째, 전국 용도별 자료의 2019년 도시가스용 값은 계절 형태가 어긋나 있었다(7월 ${f0(D.fix2019.before)}천 톤, 다른 해 약 900천 톤). 같은 기관의 지역본부별 공급량 합계와 시도별 판매량은 정상 형태여서, 지역본부 합계를 '지역본부 합계 ÷ 전국'의 달별 비율로 나눠 복원하였다(7월 ${f0(D.fix2019.after)}천 톤). 둘째, 시도별 판매량은 2023년 1월부터 모든 시도가 약 25% 낮아지는데 같은 기간 전국 공급량은 그대로여서 정의 변경으로 보고 2022년까지만 썼다. 셋째, 지역본부별 발전용 공급량은 전국 값과 정의가 맞지 않아 지역 × 용도 분석에는 쓰지 않았다.`),
  ...FIG(fig("fig1_data.png"), "그림 1. (a) 용도별 월 공급량(음영: 평가 목표월 2023~2025, 표본 외 2026년 1~9월), (b) 도시가스용과 수요가중 HDD의 관계(선: √Y ~ HDD 적합)."),
);

// ---------------- 3. 방법 ----------------
add(
  H1("3. 방법"),
  H2("3.1 회귀분석"),
  P("도시가스용 수요 Y와 HDD의 관계를 단순회귀로 추정하고(Kutner et al., 2004의 1~2장), 잔차 진단(등분산·정규성·자기상관), 적합결여 검정, Box-Cox 변환을 거쳐 모형을 정한다(3장). 같은 HDD의 반복 관측이 없어 적합결여는 3차 다항식을 허용한 모형과의 F 검정으로 보았다."),
  EQ("√Yₜ = β₀ + β₁·HDDₜ + εₜ", 1),
  P("이어 냉방도일, 영업일 수, 요금, 추세를 더한 다중회귀에서 VIF와 모든 부분집합 선택으로 변수를 고르고(6~9장), 발전용은 전력거래량, 석탄발전 상한제 기간(12~3월, 2019년 12월~), LNG 가격을 더해 부분 F 검정으로 각 변수 묶음의 기여를 본다. 월별 잔차에 자기상관이 강해 계수 추론에는 Newey-West(HAC) 표준오차를 병기한다. 시도별 분석은 시도 지시변수와 HDD의 상호작용으로 기울기가 같은지 검정한다(8장). 시도 판매량은 검침 시점 기준이라 당월과 전월 HDD를 함께 넣는다."),
  EQ("log Yᵢₜ = αᵢ + δᵢ·t + βᵢ·HDDᵢₜ + γᵢ·HDDᵢ,ₜ₋₁ + θ·CDDᵢₜ + εᵢₜ", 2),
  H2("3.2 예측 모델"),
  P("예측 모델은 네 묶음이다. **통계 모형**: 1년 전 같은 달을 그대로 쓰는 계절 naive(기준), 회귀 √Y, 외생변수를 둔 SARIMAX, 지수평활(ETS). **기계학습**: 예측 시계 h를 입력으로 넣어 모든 (예측 시점, h) 쌍을 한 모델로 학습하는 직접 다기간 Ridge·LightGBM, 그리고 회귀가 기온 효과를 잡고 기계학습이 회귀의 비율 잔차를 보정하는 하이브리드(회귀+Ridge, 회귀+LightGBM). **파운데이션 모델**: Chronos-2(Amazon, 2025)와 TimesFM 2.5(Das et al., 2024)를 학습 없이 쓰며, Chronos-2는 기온·달력·요금을 공변량으로 넣는 방식도 본다. **앙상블**: 평가 전에 정한 구성(회귀 √Y, SARIMAX, LightGBM, Chronos-2 공변량)의 단순 평균이다."),
  H2("3.3 평가 설계"),
  P("예측 시점 T마다 그때까지의 자료로 모델을 다시 추정해 T+1~T+12를 예측한다. 목표월이 2023년 1월~2025년 12월인 예측만 모아, 모든 예측 시계가 같은 36개 목표월로 비교되게 했다. 하이퍼파라미터와 차수·형태(SARIMAX 차수, ETS 추세, 회귀 변수 구성 포함)는 목표월 2020~2022년의 검증 구간에서만 골라 고정하였다. 2026년 1~9월은 모든 설정을 고정한 뒤 한 번만 보는 표본 외 구간이다."),
  P("정보 조건은 두 가지다. **사전예측**은 실제 예측과 같이 미래 기온에 평년값을, 요금·가격에 예측 시점 값을 넣는다. **사후예측**은 기온만 실제값을 넣는다. 두 조건의 오차 차이가 완벽한 기온 예보가 줄일 수 있는 몫이다. 지표는 MAPE이고, 모델 간 차이는 예측 시계마다 Diebold-Mariano 검정(HLN 보정; Harvey et al., 1997)과 모델 신뢰집합(MCS, 90%; Hansen et al., 2011)으로 판단한다. 미래 입력은 수요 열 없이 만들어 넘기며, 예측 시점 이후 자료를 10배로 바꿔도 사전예측이 그대로인지 자동으로 점검하였다(부록)."),
  ...FIG(fig("fig2_design.png"), "그림 2. 평가 설계. 예측 시점 T에서 12개월 앞까지 예측하고, 목표월이 평가 구간에 드는 예측만 모은다. 설정은 검증 구간에서만 고른다."),
  H2("3.4 계층 예측"),
  P("전국 판매량은 17개 시도의 합이다. 각 시도와 전국을 같은 방법으로 따로 예측한 기본 예측을, 상향식(시도 합), 하향식(최근 3년 같은 달 시도 비중으로 전국 예측을 나눔), MinT(Wickramasuriya et al., 2019)로 조정해 합이 맞게 한다. MinT의 오차 공분산은 검증 구간(목표월 2017~2019년)의 예측 오차로 추정하고 대각 목표로 수축하였다. 시도 판매량의 평가 목표월은 2020~2022년이다."),
  EQ("ỹ = S(SᵀW⁻¹S)⁻¹SᵀW⁻¹ŷ", 3),
);

// ---------------- 4. 결과 ----------------
const cityElast = R.price_elast;
add(
  H1("4. 결과"),
  H2("4.1 수요 구조: 도시가스용은 기온, 발전용은 기온만으로 부족하다"),
  P(`도시가스용 수요는 HDD가 1 늘면 월 ${f2(R.b1)}천 톤 늘고, 단순회귀의 R²는 ${f2(R.r2_simple)}였다. 다만 원 척도에서는 HDD가 클수록 잔차 분산이 커져 등분산이 기각되었고(BP ${pv(R.bp_y)}), Box-Cox 최적 λ는 ${f2(R.boxcox)}(${R.boxcox_ci})로 1과 다르다. √Y로 바꾸면 등분산이 기각되지 않는다(BP ${pv(R.bp_sqrt)}). 그러나 잔차 자기상관이 강해(Durbin-Watson ${f2(R.dw_sqrt)}) 교재식 표준오차는 과소추정되며, HAC 표준오차는 OLS의 ${f1(R.b1_se_hac / R.b1_se)}배였다. 3차항 F 검정은 √Y 모형에서도 곡률을 남겨(${pv(R.lof_sqrt_p)}) HDD 효과가 완전히 선형은 아니었다. 역예측으로 보면 도시가스용 월 3,000천 톤에 해당하는 HDD는 ${f0(R.inverse_hdd)}(${R.inverse})이다.`),
  P(`요금·영업일·추세를 더한 다중회귀의 R²는 ${f2(R.r2_city_multi)}이고 VIF는 모두 3 미만이었다. 모든 부분집합 선택(BIC, 수정 R², Mallows Cp)은 다섯 변수를 모두 남겼다. 요금 계수를 평균 수준의 탄력성으로 바꾸면 ${f2(cityElast)}로 작다. 구조변화 검정은 2019년 복원값을 포함하면 ${R.break_date}를 가리키지만, 복원 구간을 뺀 2020~2025년만으로는 ${R.break2_date}에 관계가 바뀌었다(${pv(R.break2_p)}). 이 시점은 2022년 도시가스 요금 인상기와 겹친다.`),
  P(`발전용은 기온만으로 R² ${f2(R.r2_power_weather)}였고, 전력거래량·석탄발전 상한제·LNG 가격·추세를 더해도 ${f2(R.r2_power)}에 그쳤다. 부분 F 검정에서 기온 묶음은 유의했지만(${pv(R.p_weather_power)}), 전력거래량(${pv(R.p_elec)})과 상한제 기간(${pv(R.p_coal)})은 유의하지 않았다. 전력거래량은 기온과 강하게 겹쳐(VIF ${f1(R.vif_elec)}) 따로 효과를 가려내기 어렵다. LNG 가격 계수는 양(+)으로 유의했는데(${pv(R.lng_coef_p)}), 겨울 수요가 현물 가격을 함께 끌어올린 결과로 보여 인과로 해석하지 않는다. 발전용 수요의 나머지 변동은 원전 정비·석탄 상한·신재생처럼 월별 공개 자료가 없는 전력 공급 측 요인에 달려 있다.`),
  H2("4.2 지역별 난방 민감도"),
  P(`2010~2019년 HDD 10 증가당 판매량 증가율은 ${N.province_sens_range.min_prov} ${f1(N.province_sens_range.min)}%에서 ${N.province_sens_range.max_prov} ${f1(N.province_sens_range.max)}%까지 달랐고, 17개 시도의 기울기가 같다는 가설은 기각되었다(F = ${f0(N.province_F)}, p < 0.001). 제주·서울·대전이 높고 울산·충남·경북이 낮아, 산업용 수요가 많은 지역일수록 기온에 덜 민감한 것으로 보인다(시도별 용도 구성 자료는 없어 해석으로만 둔다). 기간별로는 2020~2022년에 17개 시도 가운데 15곳의 민감도가 2010년대보다 커졌다.`),
  ...FIG(fig("fig3_province_sensitivity.png"), "그림 3. (a) 시도별 난방 민감도(HDD 10 증가당 도시가스 판매량 %, 2010~2019년, 당월 + 전월 HDD 효과), (b) 기간별 변화. Newey-West 표준오차로 추정."),
);

// 4.3 예측 시계별 정확도
const keyModels = ["계절 naive", "회귀 √Y", "SARIMAX", "ETS", bestML, "Chronos-2 + 공변량", "TimesFM 2.5", "앙상블"];
const row = (s, m) => [nm(m), f1(nat(s, m, "h1")), f1(nat(s, m, "h3")), f1(nat(s, m, "h6")), f1(nat(s, m, "h12")),
  f1(nat(s, m, "all")) + (inMcs(s, m) ? " ●" : "")];
const sb = (s) => ranked(s)[0];
const sameTop = ["h1", "h12"].map((k) => best("city", k)[0]);
add(
  H2("4.3 예측 시계별 정확도"),
  P(`표 2는 주요 모델의 사전예측 MAPE를 예측 시계별로 보여 준다. 1~12개월 평균으로 도시가스용은 ${nm(sb("city")[0])}(${f1(sb("city")[1])}%), 발전용은 ${nm(sb("power")[0])}(${f1(sb("power")[1])}%), 합계는 ${nm(sb("total")[0])}(${f1(sb("total")[1])}%)가 가장 정확했다. 계절 naive 대비로는 도시가스용 ${f1(nat("city", "계절 naive"))}%, 발전용 ${f1(nat("power", "계절 naive"))}%에서 줄어든 것이다. 1개월 앞 최고 모델은 도시가스용 ${nm(best("city", "h1")[0])}, 발전용 ${nm(best("power", "h1")[0])}였고, 12개월 앞에서는 도시가스용 ${nm(best("city", "h12")[0])}, 발전용 ${nm(best("power", "h12")[0])}였다.`),
  ...TABLE([["모델", "h = 1", "h = 3", "h = 6", "h = 12", "1~12 평균"],
    ["**도시가스용**", "", "", "", "", ""], ...keyModels.map((m) => row("city", m)),
    ["**발전용**", "", "", "", "", ""], ...keyModels.map((m) => row("power", m)),
    ["**합계**", "", "", "", "", ""], ...keyModels.map((m) => row("total", m))],
  [0.34, 0.12, 0.12, 0.12, 0.12, 0.18], "표 2. 1~12개월 앞 사전예측 MAPE(%), 목표월 2023~2025년(36개월). ● = 1~12개월 평균 손실 기준 90% 모델 신뢰집합(MCS) 포함. 기계학습은 세 계열 평균이 가장 낮은 변형을 표시."),
  P(`미리 정한 앙상블은 세 계열 모두에서 1~12개월 평균이 가장 낮았다. 그러나 1~12개월 평균 손실의 MCS에는 ${MODELS.length}개 모델 가운데 도시가스용 ${mcs("city").length}개, 발전용 ${mcs("power").length}개, 합계 ${mcs("total").length}개가 남아, 36개월 평가로는 상위 모델 간 차이를 통계적으로 가릴 수 없었다. MCS에서 빠진(유의하게 나쁜) 모델은 도시가스용 ${outMcs("city")}, 발전용 ${outMcs("power")}, 합계 ${outMcs("total")}였다.${mcs("power").includes("계절 naive") ? " 특히 발전용은 계절 naive까지 MCS에 남았고, 예측 시계별 DM 검정에서 계절 naive보다 유의하게 정확했던 경우도 앙상블 기준 12개 시계 가운데 " + (N.dm_beats_snaive["power|ex_ante|앙상블"] || 0) + "개뿐이었다(도시가스용은 " + (N.dm_beats_snaive["city|ex_ante|앙상블"] || 0) + "개)." : ""}`),
  ...FIG(fig("fig4_horizon.png"), "그림 4. 예측 시계별 사전예측 MAPE(목표월 2023~2025년). 점선은 계절 naive(기준)."),
);

// 4.4 기온 정보의 가치
add(
  H2("4.4 기온 정보의 가치"),
  P(`실제 기온을 넣은 사후예측과 평년 기온을 넣은 사전예측의 차이를 보면, 앙상블 기준 1~12개월 평균 MAPE는 도시가스용 ${f1(nat("city", "앙상블", "all", "ex_ante"))}% → ${f1(nat("city", "앙상블", "all", "ex_post"))}%, 발전용 ${f1(nat("power", "앙상블", "all", "ex_ante"))}% → ${f1(nat("power", "앙상블", "all", "ex_post"))}%였다. 도시가스용 오차의 약 ${f0(share("city", "앙상블"))}%는 기온 불확실성에서 왔지만, 발전용은 ${f0(share("power", "앙상블"))}%에 그쳤다. 도시가스용은 장기 기온 전망을 개선하는 것이, 발전용은 전력 공급 측 정보를 확보하는 것이 오차를 줄이는 길이다.`),
  ...FIG(fig("fig5_weather_value.png"), "그림 5. 앙상블의 사전예측(평년 기온)과 사후예측(실제 기온) MAPE. 음영은 완벽한 기온 예보가 줄일 수 있는 오차."),
);

// 4.5 계층 예측
const pm = ["계절 naive", "ETS", "회귀 √Y", "Chronos-2 + 공변량"];
add(
  H2("4.5 지역별 계층 예측"),
  P(`시도별 판매량의 1~12개월 앞 예측에서 전국 MAPE는 기본(전국 직접) 예측 기준 ${pm.map((m) => `${nm(m)} ${f1(prov(m, "기본", "전국"))}%`).join(", ")}였다. 상향식과 MinT 조정은 ETS(${f1(prov("ETS", "기본", "전국"))}% → MinT ${f1(prov("ETS", "MinT", "전국"))}%)와 Chronos-2(${f1(prov("Chronos-2 + 공변량", "기본", "전국"))}% → ${f1(prov("Chronos-2 + 공변량", "MinT", "전국"))}%)의 전국 예측을 개선했지만, 전월 기온까지 넣은 회귀는 전국 직접 예측이 가장 정확했고(${f1(prov("회귀 √Y", "기본", "전국"))}%) 조정하면 오히려 나빠졌다(MinT ${f1(prov("회귀 √Y", "MinT", "전국"))}%). 시도 평균 MAPE는 ${f1(prov("Chronos-2 + 공변량", "MinT", "시도 평균"))}~${f1(prov("회귀 √Y", "기본", "시도 평균"))}%로 전국보다 높고, 하향식은 시도 예측을 크게 나쁘게 했다. 계층 조정은 전국 모델이 약할 때 시도 정보를 더해 주는 보완책이며, 잘 설계한 전국 모델을 대신하지는 못한다.`),
  ...FIG(fig("fig6_hierarchy.png"), "그림 6. 시도별 도시가스 판매량의 계층 예측(목표월 2020~2022년, 1~12개월 평균 MAPE). (a) 전국, (b) 17개 시도 평균."),
);

// 4.6 표본 외
const hr = (s) => holdRank(s).slice(0, 3).map(([m, v]) => `${nm(m)} ${f1(v)}%`).join(", ");
add(
  H2("4.6 2026년 표본 외 검증"),
  P(`2025년까지의 자료로 고정한 모델을 2026년 1~9월에 적용하였다. 1~12개월 앞 사전예측의 평균 MAPE 상위 세 모델은 도시가스용 ${hr("city")}, 발전용 ${hr("power")}, 합계 ${hr("total")}였다. 2026년 7~8월 발전용 수요가 각 약 192만 톤으로 2022~2025년 같은 달(132만~164만 톤)보다 크게 늘어 발전용 오차가 컸다. 평가 구간에서 가장 정확했던 앙상블은 2026년에 합계 ${holdRank("total").findIndex((x) => x[0] === "앙상블") + 1}위, 도시가스용 ${holdRank("city").findIndex((x) => x[0] === "앙상블") + 1}위, 발전용 ${holdRank("power").findIndex((x) => x[0] === "앙상블") + 1}위(${holdRank("total").length}개 모델 중)로, 해마다 최고 모델이 바뀐다는 점이 다시 확인되었다.`),
  ...FIG(fig("fig7_holdout_2026.png"), "그림 7. 2025년 12월 시점에서 본 2026년 1~9월 예측(사전예측). 노란 음영은 Chronos-2의 80% 예측구간."),
);

// 4.7 다른 나라와 비교
const six = N.six || {};
add(
  H2("4.7 다른 나라와의 비교"),
  P(`같은 모델과 평가 절차를 독일·이탈리아·프랑스·스페인·네덜란드에 적용한 비교 연구(1개월 앞, 2023~2025년)에서 한국의 난방 민감도는 HDD 10당 약 ${f1(six.r5 ? six.r5.KR.hdd10_post : null)}%로 프랑스(${f1(six.r5 ? six.r5.FR.hdd10_post : null)}%)·독일(${f1(six.r5 ? six.r5.DE.hdd10_post : null)}%)보다 낮았다. 유럽은 2022년 에너지 위기로 독일·네덜란드·이탈리아의 기저수요가 12~23% 줄어 위기 변수 없는 회귀가 크게 틀렸지만(네덜란드 ${f1(six.main_ex_post ? six.main_ex_post["회귀 √Y~HDD+가격"].NL : null)}%), 한국은 공급 충격이 없어 기준 회귀(${f1(six.main_ex_post ? six.main_ex_post["회귀 √Y~HDD+가격"].KR : null)}%)도 여섯 나라 가운데 가장 정확했다. 어느 나라에서나 튜닝한 SARIMAX와 미리 정한 앙상블이 최고 모델과 통계적으로 구별되지 않았다는 점은 한국 다기간 결과와 같은 방향이다.`),
  ...FIG(fig("fig8_six_countries.png"), "그림 8. 같은 모델로 본 6개국 비교. (a) 난방 민감도(2022년 3월 전후), (b) 1개월 앞 MAPE(기준 회귀와 국가별 최고 모델)."),
);

// ---------------- 5. 논의 ----------------
add(
  H1("5. 논의"),
  P("**용도별로 다른 전략이 필요하다.** 도시가스용은 기온으로 대부분 설명되고 오차의 상당 부분이 기온 불확실성이어서, 좋은 기온 시나리오와 √Y 회귀·SARIMAX 같은 단순한 모형으로 충분히 정확하다. 발전용은 기온으로 절반 남짓만 설명되고 기온을 알아도 오차가 크게 줄지 않는다. 발전용 예측을 개선하려면 원전 정비 일정, 석탄 상한제, 전력수요 전망처럼 전력 공급 측 정보를 모형에 넣어야 한다."),
  P("**단일 최고 모델보다 모델군과 앙상블.** 미리 정한 앙상블은 평가 구간에서 세 계열 모두 가장 정확했지만, 상위 모델들은 MCS로 구분되지 않았고 2026년에는 순위가 바뀌었다. 어떤 모델이 다음 해에 최고일지 미리 알 수 없으므로, 서로 다른 원리의 모델을 함께 운용하고 평균하는 것이 가장 안전하다."),
  P("**파운데이션 모델은 강한 기준선이다.** Chronos-2와 TimesFM은 학습 없이도 학습한 모델과 비슷한 정확도를 냈고 예측구간도 함께 준다. 다만 사전학습 자료에 공개 통계가 섞였을 가능성이 있어 2026년 표본 외 결과를 함께 보아야 한다."),
  P("**지역 정보는 보완재다.** 시도별 난방 민감도는 뚜렷이 달랐지만, 시도 예측을 합치는 것이 전국 예측을 늘 개선하지는 않았다. 판매량의 검침 지연(전월 기온)처럼 지역 자료의 특성을 모형에 반영하는 것이 더 중요했다."),
  H2("한계"),
  BUL("전국 용도별 자료는 2016년부터라 평가 구간이 36개월이고, 2019년 값은 복원값이다."),
  BUL("시도별 판매량은 2023년 정의 변경으로 2022년까지만 썼고, 용도를 더 나눈 자료(주택·업무·산업)는 월별로 공개되지 않는다."),
  BUL("발전용의 핵심 요인인 원전·석탄 발전량의 월별 공개 자료를 확보하지 못했다."),
  BUL("기온 시나리오는 평년값 하나만 썼다. 기상청 장기예보를 쓰면 사전예측이 더 좋아질 수 있다."),
);

// ---------------- 6. 결론 ----------------
add(
  H1("6. 결론"),
  P(`한국 천연가스 수요를 용도별·지역별로 나눠 1~12개월 앞을 예측하였다. 도시가스용은 수요가중 HDD로 대부분 설명되어 사전예측 MAPE가 ${f1(cb[1])}% 수준이었고, 오차의 상당 부분은 기온 불확실성이었다. 발전용은 기온만으로 설명되지 않아 오차가 ${f1(pb[1])}%로 두 배가량 컸다. 시도별 난방 민감도는 세 배 가까이 달랐지만 계층 조정의 이득은 기본 모델에 따라 달랐다. 수급계획 관점에서는 용도별로 다른 정보(도시가스용은 기온 전망, 발전용은 전력 공급 계획)를 모형에 넣고, 서로 다른 원리의 모델을 앙상블로 함께 운용하는 것이 가장 안정적이다.`),
  P("모든 자료와 코드, 결과는 공개 저장소(github.com/seoki0804/LNG_D_F, korea/ 폴더)에 있으며 python/run_all.py 한 번으로 재현할 수 있다."),
);

// ---------------- 참고문헌 ----------------
add(
  H1("참고문헌"),
  ...[
    "박진수, 김윤배, 정철우 (2013). 도시가스 일일수요의 단기예측. 대한산업공학회지, 39(4), 247-252.",
    "Amazon (2025). Chronos-2: From univariate to universal forecasting. arXiv:2510.15821.",
    "Das, A., Kong, W., Sen, R. & Zhou, Y. (2024). A decoder-only foundation model for time-series forecasting. ICML 2024.",
    "Diebold, F. X. & Mariano, R. S. (1995). Comparing predictive accuracy. Journal of Business & Economic Statistics, 13(3), 253-263.",
    "Hansen, P. R., Lunde, A. & Nason, J. M. (2011). The model confidence set. Econometrica, 79(2), 453-497.",
    "Harvey, D., Leybourne, S. & Newbold, P. (1997). Testing the equality of prediction mean squared errors. International Journal of Forecasting, 13(2), 281-291.",
    "Kutner, M. H., Nachtsheim, C. J., Neter, J. & Li, W. (2004). Applied Linear Statistical Models (5th ed.). McGraw-Hill.",
    "Newey, W. K. & West, K. D. (1987). A simple, positive semi-definite, heteroskedasticity and autocorrelation consistent covariance matrix. Econometrica, 55(3), 703-708.",
    "Tian, N. et al. (2023). Application of forecasting strategies and techniques to natural gas consumption: A comprehensive review and comparative study. Engineering Applications of Artificial Intelligence.",
    "Wickramasuriya, S. L., Athanasopoulos, G. & Hyndman, R. J. (2019). Optimal forecast reconciliation for hierarchical and grouped time series through trace minimization. Journal of the American Statistical Association, 114(526), 804-819.",
    "자료: 한국가스공사 용도별 월 공급량·지역본부별 공급량·시도별 도시가스 판매현황(공공데이터포털), 기상청 ASOS 일자료, 통계청 KOSIS, FRED. 2026년 11월 21일 호출.",
  ].map((t) => new Paragraph({ spacing: { after: 80 }, indent: { left: 360, hanging: 360 }, children: [new TextRun({ text: t, size: 19 })] })),
);

// ---------------- 부록 ----------------
const lk = N.leakage, VR = N.vars;
add(
  H1("부록"),
  ...(VR ? [P(`**추가 변수 점검.** 석탄 가격(FRED), LNG/석탄 가격비, 계통한계가격(SMP), 전력거래량, 산업생산을 튜닝한 OLS(√Y)·Hybrid(OLS+Ridge)·SARIMAX 설정에 하나씩 더하고, 검증 구간(목표월 2020~2022년)에서 MAPE가 0.1%p 넘게 줄면 채택하는 규칙을 적용하였다. 이 규칙으로 고른 ${VR.n_adopted}개 조합은 평가 구간(2023~2025년)에서 평균 ${f2(-VR.avg_eval_gain)}%p 나빠졌고, 좋아진 ${VR.n_eval_better}개 가운데 DM 검정으로 유의한 개선은 ${VR.n_sig_better_adopted}개, 유의하게 나빠진 것은 ${VR.n_sig_worse_adopted}개였다. 검증 구간이 2022년 에너지 가격 급등기와 겹쳐 가격 변수가 우연히 좋아 보였고, 실제 예측에서는 미래 가격을 모르므로 예측 시점 값으로 둘 수밖에 없기 때문으로 보인다. 그래서 본문 결과는 기본 설정을 유지하였다. 발전용 예측에 가장 필요한 월별 원전·석탄 발전량은 공개 월별 통계가 없어 시험하지 못했다.`)] : []),
  P(`**누수 점검.** 세 예측 시점(2022년 6월, 2023년 11월, 2025년 3월)에서 예측 시점 이후의 수요·기온·가격을 10배로 바꿔도 사전예측이 바뀌지 않는지 모든 학습 모델에 대해 확인하였다${lk ? `(${lk.n}건 중 ${lk.ok}건 통과)` : ""}. 실제 기온을 쓰도록 설계한 사후예측은 값이 바뀌어, 점검이 변화를 잡아낼 수 있음도 확인하였다.`),
  ...FIG(fig("figA1_diagnostics.png"), "그림 A1. 도시가스용 √Y ~ HDD 회귀의 잔차 진단. (a) 잔차 대 적합값, (b) 정규 Q–Q, (c) 시간에 따른 잔차(자기상관)."),
);

build(children, path.join(__dirname, "한국_LNG_수요예측_보고서.docx"), {
  creator: "안형석, 양의창, 권기범", title: "한국 LNG 수요의 용도별·지역별 예측",
  description: "수요예측 수업 최종 보고서", runningHead: "한국 LNG 수요예측 · 안형석, 양의창, 권기범",
}).then(() => console.log("저장: report/한국_LNG_수요예측_보고서.docx"));
