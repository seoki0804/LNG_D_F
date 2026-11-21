// 최종 보고서(논문 형식, .docx) 생성. 수치는 numbers.json(python/report_numbers.py)에서 읽는다.
// 실행: cd report && node build_report.js   → report/천연가스_수요예측_보고서.docx
const fs = require("fs");
const path = require("path");
const K = require("./docx_kit");
const { P, H1, H2, H3, BUL, NUM, EQ, FIG, TABLE, build, Paragraph, TextRun, AlignmentType, PageBreak } = K;

const ROOT = path.resolve(__dirname, "..");
const FIGDIR = path.join(ROOT, "outputs", "figures", "paper");
const N = JSON.parse(fs.readFileSync(path.join(__dirname, "numbers.json"), "utf8"));
const GEOS = ["DE", "IT", "FR", "ES", "NL", "KR"];
const KO = { DE: "독일", IT: "이탈리아", FR: "프랑스", ES: "스페인", NL: "네덜란드", KR: "한국" };
const f1 = (x) => (x === null || x === undefined ? "–" : Number(x).toFixed(1));
const f2 = (x) => (x === null || x === undefined ? "–" : Number(x).toFixed(2));
const mean = (o) => { const v = Object.values(o).filter((x) => x !== null); return v.reduce((a, b) => a + b, 0) / v.length; };
const M = (mode, model) => mean(N.main[mode][model]);            // 본 실험 6개국 평균 MAPE
const MC = (mode, model) => N[`mcs_${mode}`].mape[model];          // 6개국 평균 손실 (MCS 표와 같은 값)
const BENCH = "회귀 √Y~HDD+가격", SAR = "SARIMAX+HDD·가격", CHR = "Chronos-2 + 공변량", ENS = "ENS";
const fig = (n) => path.join(FIGDIR, n);
const p = (x) => (x < 0.001 ? "p < 0.001" : `p = ${x.toFixed(3)}`);

const r5 = N.r5, br = N.break;
const best = (mode, g) => { const t = Object.entries(N.main[mode]).map(([m, v]) => [m, v[g]]).sort((a, b) => a[1] - b[1]); return t[0]; };
const NAME = { [BENCH]: "기준 회귀", "회귀 + 위기 변수": "회귀 + 위기 항", [SAR]: "SARIMAX", "Holt-Winters": "Holt-Winters",
  "계절 naive": "계절 naive", Ridge: "Ridge", "Ridge + 위기 변수": "Ridge + 위기 항", "Gradient Boosting": "GBM",
  LightGBM: "LightGBM", "MLP (16-8)": "MLP", "하이브리드 (회귀+GBM 잔차)": "하이브리드", "Chronos-2 단변량": "Chronos-2 (단변량)",
  [CHR]: "Chronos-2 (공변량)", "TimesFM 2.5 단변량": "TimesFM 2.5 (단변량)", [ENS]: "앙상블 (회귀·ML·Chronos)",
  "Lasso": "Lasso", "Random Forest": "Random Forest", "SVR": "SVR", "단순회귀 Y~HDD": "단순회귀",
  "통합 LightGBM (6개국)": "통합 LightGBM", "GBM + 위기 변수": "GBM + 위기 항", "TimesFM 2.5 + 공변량(XReg)": "TimesFM 2.5 (공변량)",
  "앙상블: 검증 상위 3": "검증 상위 3 앙상블", "앙상블: 회귀(위기)+ML": "회귀·ML 앙상블", "앙상블: ML 평균": "ML 평균 앙상블" };
const nm = (m) => NAME[m] || m;

const L = N.long || {}, OOS = N.oos || {}, RT = N.realtime;
// 2026년 표본 외: 6개국 평균 순위, 국가별 값, 독일 연도별 MAPE, HDD 보정 오차
const OR = N.oos_rank || [], OG = N.oos_by_geo || {}, DY = N.de_yearly || {}, HC = N.hdd_cal || {};
const orank = (m) => OR.findIndex((x) => x[0] === m) + 1;
const ensGap = OR.length ? +(OOS[ENS].MAPE_ex_post - OR[0][1]).toFixed(1) : 0;
const calMae = Object.values(HC).map((v) => v.cv_mae);
const calTxt = calMae.length ? `${Math.min(...calMae).toFixed(1)}~${Math.max(...calMae).toFixed(1)}` : "";
const ensOos = orank(ENS) === 1 ? `가장 정확했다(6개국 평균 MAPE ${f1(OOS[ENS].MAPE_ex_post)}%)`
  : `6개국 평균 MAPE ${f1(OOS[ENS].MAPE_ex_post)}%로 1위와 ${ensGap.toFixed(1)}%p 차이의 상위권이었다`;
// 그림 6 (b): 해마다 네 모델 중 가장 정확한 모델
const yrs = ["2023", "2024", "2025", "2026"];
const yBest = yrs.map((y) => Object.entries(DY).filter(([, d]) => d[y] != null).sort((a, b) => a[1][y] - b[1][y])[0]);
const ensYears = yrs.filter((y, i) => yBest[i] && yBest[i][0] === ENS);
const otherYears = yrs.map((y, i) => [y, yBest[i]]).filter(([, b]) => b && b[0] !== ENS)
  .map(([y, b]) => `${y}년에는 ${nm(b[0])}(${f1(b[1][y])}%)가 앙상블(${f1(DY[ENS][y])}%)보다 나았다`);
const fig6Txt = `앙상블은 ${ensYears.join("·")}년에 네 모델 중 가장 정확했고` + (otherYears.length ? `, ${otherYears.join(", ")}.` : ".");
const children = [];
const add = (...xs) => xs.flat().forEach((x) => children.push(x));

// ---------------- 표지 ----------------
add(
  new Paragraph({ style: "Title", children: [new TextRun("2022년 에너지 위기 이후 월별 천연가스 수요예측:")] }),
  new Paragraph({ style: "Title", children: [new TextRun("회귀분석, 기계학습, 시계열 파운데이션 모델의 6개국 비교")] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 240 }, children: [new TextRun({ text:
    "Monthly natural gas demand forecasting after the 2022 energy crisis: regression, machine learning and time-series foundation models in six countries",
    italics: true, size: 19, color: "52514E" })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 60 }, children: [new TextRun({ text: "수요예측 팀: 안형석, 양의창, 권기범", size: 21 })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 360 }, children: [new TextRun({ text: "수요예측 수업 최종 보고서 · 2026년 11월", size: 19, color: "52514E" })] }),
);

// ---------------- 요약 ----------------
const deHdd = r5.DE;
add(
  H2("요약"),
  P(`2022년 러시아의 우크라이나 침공 이후 유럽의 천연가스 수요는 같은 기온에서도 크게 줄었다. 이 연구는 독일을 중심으로 이탈리아·프랑스·스페인·네덜란드와 한국의 월별 천연가스 수요를 대상으로, 회귀분석으로 수요 구조의 변화를 추론하고 통계 모형, 기계학습, 시계열 파운데이션 모델의 1개월 앞 예측 정확도를 같은 평가 틀에서 비교하였다. 독일의 난방 민감도(HDD 10 증가당 수요 증가율)는 위기 전 ${f2(deHdd.hdd10_pre)}%에서 위기 후 ${f2(deHdd.hdd10_post)}%로 유의하게 커졌고(${p(deHdd.p_hdd_change)}), 같은 기온에서의 기저수요는 ${Math.abs(deHdd.crisis_level_pct).toFixed(0)}% 줄었다. 2023~2025년 롤링 평가(국가당 36회)에서 최고 단일 모델은 나라마다 달랐다. 그러나 모델 신뢰집합(MCS, 90%)으로 보면 검증 구간에서 차수를 고른 SARIMAX와, 위기 항을 넣은 회귀·기계학습 모델·Chronos-2를 단순 평균한 앙상블만이 6개국 모두에서 사후·사전예측 모두 최고 모델과 통계적으로 구별되지 않았다. 학습 없이 예측한 Chronos-2(공변량 포함)의 6개국 평균 MAPE는 ${f1(MC("ex_post", CHR))}%로, 학습한 국가별 최고 모델과 대등했다. 이 결론은 2018~2025년 장기 평가와 자료 공표 지연을 반영한 실시간 예측에서도 유지되었고, 2026년 1~9월 표본 외 검증에서 앙상블은 ${ensOos}. HDD 하나로 설명하는 기준 회귀는 수요 수준이 바뀐 나라에서 크게 틀렸지만(네덜란드 MAPE ${f1(N.main.ex_post[BENCH].NL)}%), 위기 더미와 HDD×위기 항을 더하면 오차가 절반 이하로 줄었다.`),
  P("**주제어**: 천연가스 수요예측, 난방도일(HDD), 구조변화, 모델 신뢰집합, 시계열 파운데이션 모델"),
);

// ---------------- 1. 서론 ----------------
add(
  H1("1. 서론"),
  P("천연가스는 난방과 산업 공정, 발전에 함께 쓰여 수요가 기온에 크게 좌우되고, 저장과 수입 계약은 몇 달 앞을 내다보고 결정된다. 월 단위 수요예측은 겨울철 공급 안정과 저장 계획의 기초다. 독일은 2025년 천연가스 864 TWh를 소비했고 그중 약 40%가 가정·상업 부문이다(Bundesnetzagentur, 2026)."),
  P("2022년 러시아의 우크라이나 침공 이후 유럽 도매 가스 가격이 급등했고, EU는 회원국에 15% 자발적 수요 감축을 권고하는 규정(Regulation (EU) 2022/1369)을 시행하였다. 독일의 2022년 가스 내수는 전년보다 15% 이상 줄었다(Eurostat, 2023). 과거 관계로 학습한 예측 모델이 이런 구조변화 뒤에도 쓸 만한지는 실무와 학술 모두의 질문이다."),
  P("기온과 가스 수요의 관계는 난방도일(HDD) 회귀로 오래 다뤄졌다(EIA, 2014; Fiorini & Sileo, 2011). 최근에는 기계학습 모델의 비교(Tian et al., 2023; Aidoni et al., 2023)와 여러 시계열을 한 모델로 학습하는 통합 모델(Montero-Manso & Hyndman, 2021), 학습 없이 예측하는 시계열 파운데이션 모델(Das et al., 2024; Amazon, 2025)이 제안되었다. 그러나 월 단위 자료는 표본이 작고, 위기 뒤 평가 기간은 더 짧아 모델 간 차이가 통계적으로 의미 있는지 판단하기 어렵다."),
  P("이 연구는 독일을 중심으로 유럽 4개국과 한국의 월별 천연가스 수요를 분석한다. 먼저 회귀분석(Kutner et al., 2004의 1~6장)으로 수요와 기온의 관계, 모형 가정의 위반과 보정, 위기 전후의 구조변화를 추론한다. 이어서 같은 평가 틀에서 통계 모형, 기계학습, 파운데이션 모델의 1개월 앞 예측 정확도를 비교한다. 연구 질문은 다음과 같다."),
  NUM("독일에서 HDD가 늘면 월 수요는 얼마나 늘고, 2022년 위기 뒤 이 관계는 바뀌었는가?"),
  NUM("회귀 가정은 어디서 깨지고, 어떤 변환과 추론 방법이 이를 보정하는가?"),
  NUM("같은 회귀 구조에서 나라마다 난방 민감도와 위기의 영향은 어떻게 다른가?"),
  NUM("기계학습과 파운데이션 모델은 회귀·통계 모형보다 유의하게 정확한가?"),
  NUM("이 결론은 평가 기간, 정보 시점(실시간), 표본 외 기간을 바꿔도 유지되는가?"),
  P("이 연구의 기여는 세 가지다. 첫째, 위기 전후 난방 민감도의 변화를 6개국에서 같은 구조로 추정하고 자기상관을 반영한 추론과 구조변화 검정으로 확인하였다. 둘째, 모든 모델을 같은 검증 구간에서 튜닝하고 다중비교를 보정하는 MCS로 비교했으며, 자료 공표 지연과 표본 외 기간까지 검증해 결론의 견고성을 따졌다. 셋째, 시계열 파운데이션 모델이 작은 월 단위 에너지 자료에서도 학습한 모델과 대등함을 보였다."),
);

// ---------------- 2. 자료 ----------------
add(
  H1("2. 자료"),
  P("분석 대상은 독일·이탈리아·프랑스·스페인·네덜란드와 한국의 월별 천연가스 수요다. 유럽은 Eurostat 월별 가스 수급 통계(nrg_cb_gasm)의 내수 소비(총발열량 기준, PJ), 한국은 한국가스공사의 용도별 월 공급량(도시가스용 + 발전용, 천 톤)을 쓴다. 표본은 유럽 2008년 1월~2026년 10월, 한국 2016년 1월~2026년 9월이다. 설명변수는 표 1과 같다(자료는 2026년 11월 21일 호출)."),
  ...TABLE([
    ["변수", "유럽 5개국", "한국"],
    ["수요", "Eurostat nrg_cb_gasm 내수 소비 (PJ)", "KOGAS 용도별 공급량 (천 톤)"],
    ["HDD·CDD", "Eurostat nrg_chdd_m", "기상청 ASOS 7개 도시 일평균기온으로 계산"],
    ["소비자 요금", "HICP 가스 지수 (CP0452)", "소비자물가 도시가스 지수"],
    ["도매가격 (전월)", "FRED EU 천연가스 (USD/MMBtu)", "FRED 아시아 LNG (USD/MMBtu)"],
    ["산업생산", "Eurostat 산업생산지수 B–D (계절조정)", "광공업생산지수 (계절조정)"],
    ["달력", "국가별 공휴일 반영 영업일 수", "설·추석 포함 영업일 수"],
    ["부문 (보조)", "독일 THE 일별 SLP·RLM 소비 (2021-10~)", "도시가스용·발전용 공급량"],
  ], [0.18, 0.42, 0.40], "표 1. 자료와 변수", { alignLeft: [1, 2] }),
  P(`난방도일은 Eurostat 방식에 따라 일평균기온이 15°C 이하인 날의 (18 − 기온)을 월별로 합한 값이고, 냉방도일은 24°C 이상인 날의 (기온 − 21)을 합한 값이다. 한국은 서울·부산·대구·인천·광주·대전·울산 관측소의 일평균기온으로 같은 방식에 따라 계산하였다(인구가중 평균과 설명력 차이가 없어 단순평균을 썼다). 2026년 표본 외 검증에 필요한 유럽의 2026년 HDD는 아직 공표되지 않아, 독일은 기상청(DWD) 12개 도시 관측소, 나머지 4개국은 ERA5 재분석 자료(Open-Meteo)의 도시 기온으로 계산한 뒤 2014~2025년 Eurostat 값에 맞춰 보정하였다. Eurostat 값은 산간을 포함한 국토 전체 기준이라 도시 기온과의 관계가 달마다 달라서, 월별 절편과 기온 오프셋(0~2°C, 연도별 교차검증으로 선택)을 둔 보정식을 썼다. 한 해씩 빼고 맞혀 본 오차는 월 ${calTxt} HDD다.`),
  ...FIG(fig("fig1_demand.png"), "그림 1. 6개국 월별 천연가스 수요. 검은 선은 12개월 중심이동평균, 세로선은 2022년 3월, 음영은 평가 구간(2023~2025)과 표본 외 구간(2026년 1~9월)이다. 독일·이탈리아·프랑스·네덜란드는 2022년 이후 수요 수준이 뚜렷이 낮아졌다."),
  P("2008~2025년 유럽 자료와 2016~2025년 한국 자료에는 결측이 없다. 한국가스공사 전국 용도별 자료의 2019년 도시가스용 값은 계절 형태가 어긋나 있어(7월이 다른 해의 약 2배), 같은 기관의 지역본부별 공급량 합계로 복원했다. 최근 일부 값은 잠정치이며(프랑스 3개월, 네덜란드 12개월), 스페인 2026년 8월 값(0)은 명백한 오류여서 분석에서 뺐다."),
);

// ---------------- 3. 방법 ----------------
add(
  H1("3. 방법"),
  H2("3.1 회귀분석"),
  P("독일 자료(2008~2025년, n = 216)로 단순회귀부터 시작한다."),
  EQ("Yₜ = β₀ + β₁·HDDₜ + εₜ", 1),
  P("β₁의 추론과 신뢰·예측구간, 분산분석(1~2장) 뒤에 잔차 진단 6종(잔차 대 X, |잔차| 대 X, 잔차 대 적합값·시간, 상자그림, 정규확률그림), 등분산 검정(Breusch-Pagan, Brown-Forsythe), 정규성(Shapiro-Wilk), 자기상관(Durbin-Watson), 적합결여 검정을 하고 Box-Cox 변환을 고른다(3장). 이어 β₀·β₁의 Bonferroni 동시 신뢰구간, 평균 반응의 Working-Hotelling 신뢰대, 겨울 3개월의 동시 예측구간, 역예측과 행렬 계산(4~5장)을 수행한다. 잔차 자기상관이 강하므로 Newey-West(1987) 표준오차를 함께 보고한다."),
  P("다중회귀(6장~)는 √Y를 반응변수로 하여 CDD, 소비자 요금, 전월 도매가격, 산업생산, 화학 생산, 영업일, 원자력·풍력 발전량, 위기 더미 Dₜ(2022년 3월 이후 = 1)와 HDD×D를 후보로 둔다. 다중공선성은 VIF로, 변수선택은 모든 부분집합의 수정 R², AIC, BIC, Mallows Cp, PRESS로 판단한다."),
  P("국가 간 비교는 단위와 규모가 달라도 비교되도록 로그 모형을 쓴다."),
  EQ("log Yₜ = α + β·HDDₜ + γ·CDDₜ + δ·log Pₜ + θ·Dₜ + φ·HDDₜ·Dₜ + εₜ", 2),
  P("HDD 10 증가당 수요 변화율은 위기 전 100·(e¹⁰ᵝ − 1), 위기 후 100·(e¹⁰⁽ᵝ⁺ᵠ⁾ − 1)%이다. 위기 시점을 미리 정한 것이 타당한지는 2022년 3월 Chow 검정, 시점을 모를 때의 sup-F 검정(Andrews, 1993), 다중 구조변화 검정(Bai & Perron, 2003)으로 확인한다."),
  H2("3.2 예측 모델"),
  P("모델은 네 묶음이다. **통계 모형**: 기준 회귀 √Yₜ = β₀ + β₁·HDDₜ + β₂·Pₜ, 여기에 위기 항을 더한 회귀, 외생변수를 둔 SARIMAX, Holt-Winters, 계절 naive(12개월 전 값). **기계학습**: Ridge, Lasso, Random Forest, Gradient Boosting(GBM), LightGBM, SVR, MLP(16-8), 회귀 잔차를 GBM이 학습하는 하이브리드, 6개국을 쌓아 학습하는 통합(global) LightGBM. 입력은 HDD, CDD, 소비자 요금, 전월 도매가격, 산업생산, 월(sin·cos), 전월·12개월 전 수요의 9개다. **파운데이션 모델**: Chronos-2(Amazon, 2025)와 TimesFM 2.5(Das et al., 2024)를 미세조정 없이(zero-shot) 쓰며, 수요 이력만 넣는 단변량과 위 공변량을 함께 넣는 방식을 모두 본다. **앙상블**: 평가 구간을 보기 전에 정한 구성(위기 항 회귀, Ridge, GBM, LightGBM, MLP, Chronos-2)의 단순 평균과, 검증 구간 MAPE가 가장 낮은 세 모델의 평균이다."),
  H2("3.3 평가 설계"),
  P("모든 모델은 같은 평가 코드로 평가한다(그림 2). 평가 구간의 매달 t마다 t − 1월까지의 자료로 모델을 다시 추정해 t월을 예측한다(확장창, 학습 시작 2015년 1월). 하이퍼파라미터는 ML뿐 아니라 SARIMAX 차수와 Holt-Winters 형태까지 2020~2022년 검증 구간의 MAPE로 고른 뒤 고정한다. 랜덤성이 있는 모델은 시드 5개의 예측을 평균한다."),
  ...FIG(fig("fig2_design.png"), "그림 2. 평가 설계. 본 평가(2023~2025), 장기 평가(유럽 2018~2025, 한국 2020~2025), 2026년 표본 외 검증은 각각 앞선 검증 구간에서만 하이퍼파라미터를 고른다."),
  P("정보 시점은 세 가지로 나눈다. **사후예측**은 예측 달의 실제 기온·가격을 넣고, **사전예측**은 HDD·CDD에 평년값(직전 10년 같은 달 평균)을, 같은 달 가격·산업 변수에 직전 달 값을 넣는다. **실시간 예측**은 여기에 자료 공표 지연까지 반영해, 수요는 2개월(독일·이탈리아·스페인·네덜란드) 또는 3개월(프랑스·한국) 전, 산업생산은 3개월 전까지만 쓴다."),
  P("정확도는 MAPE를 중심으로 RMSE와 MASE(Hyndman & Koehler, 2006)를 함께 본다. 두 모델의 차이는 소표본 보정을 한 Diebold-Mariano 검정(Diebold & Mariano, 1995; Harvey et al., 1997)으로, 여러 모델의 동시 비교는 모델 신뢰집합(MCS; Hansen et al., 2011, 범위 통계량, 정상 부트스트랩 5,000회, 90%)으로 판단한다. 6개국 평균 손실에 대한 MCS도 계산해 검정력을 높였다. 미래 자료를 고의로 훼손해도 예측이 바뀌지 않는지 확인하는 누수 점검을 모든 모델에 적용했고 " + `${N.leakage}건 모두 통과하였다.`),
);

// ---------------- 4. 결과 ----------------
const S = N.simple, MU = N.multiple;
add(
  H1("4. 결과"),
  H2("4.1 독일 수요의 회귀분석"),
  P(`단순회귀 (1)의 R²는 ${f2(S.r2)}이고, HDD가 1 늘면 월 수요는 ${f2(S.b1)} PJ(95% 신뢰구간 ${f2(S.b1_lo)}~${f2(S.b1_hi)}) 늘었다. 잔차에는 이분산(Breusch-Pagan ${p(S.bp_y)})과 선형성 위반(적합결여 ${p(S.lof_y)})이 있었다. Box-Cox 최적 λ는 ${f2(S.boxcox)}(95% 구간 ${f2(S.boxcox_lo)}~${f2(S.boxcox_hi)})로 √Y 변환을 지지했고, 변환 뒤 두 위반은 모두 사라졌다(각각 ${p(S.bp_sqrt)}, ${p(S.lof_sqrt)}). 그러나 Durbin-Watson 통계량은 ${f2(S.dw_y)}(변환 뒤 ${f2(S.dw_sqrt)})로 강한 양의 자기상관이 남았다. Newey-West 표준오차는 OLS보다 β₁에서 ${f2(N.ch45.hac_ratio_b1)}배 커서, 독립 오차를 가정한 교재의 구간은 실제 불확실성보다 좁다(부록 그림 A1).`),
  P(`동시추론에서는 평균 반응의 Working-Hotelling 배수(W = ${f2(N.ch45.W)})가 네 점의 Bonferroni 배수(B = ${f2(N.ch45.B)})보다 작아 더 좁은 신뢰대를 주었고, 행렬 계산으로 구한 b, s²{b}, 모자 행렬은 최소제곱 결과와 10⁻¹³ 이내로 일치했다. 다중회귀에서는 소비자 요금과 위기 더미의 VIF가 각각 21, 19로 높아 두 효과를 따로 추정하기 어려웠다. BIC가 고른 모형은 √Y ~ HDD + 풍력 + D + HDD×D(R² ${f2(MU.r2)})이며, 평균 수준에서 HDD 1당 수요 효과는 위기 전 ${f2(MU.hdd_pre)} PJ에서 위기 후 ${f2(MU.hdd_post)} PJ로 커졌다. 계획 단계에서 유의하다고 본 영업일 수는 t = ${f2(MU.workdays_t)}로 유의하지 않았다.`),
  H2("4.2 구조변화와 국가별 난방 민감도"),
  P(`2022년 3월의 Chow 검정은 독일(${p(br.DE.chow_p)}), 프랑스, 스페인, 네덜란드, 한국에서 유의했고 이탈리아에서는 유의하지 않았다(${p(br.IT.chow_p)}). 시점을 모를 때의 HAC sup-F 검정이 찾은 시점은 독일 ${br.DE.supF_hac_date}, 네덜란드 ${br.NL.supF_hac_date}로, EU 수요 감축 규정이 시행된 2022년 여름과 가깝다. 위기 시점을 2022년 9월로 바꿔도 예측 결론은 같아(4.4절), 사전에 정한 2022년 3월을 유지하였다.`),
  ...FIG(fig("fig3_hdd_sensitivity.png"), "그림 3. 모형 (2)로 추정한 국가별 난방 민감도(HDD 10 증가당 월 수요 증가율)의 위기 전후 비교. 막대는 Newey-West 95% 신뢰구간이다.", 9.5),
  P(`난방 민감도는 프랑스(${f2(r5.FR.hdd10_pre)}%)가 가장 크고 스페인(${f2(r5.ES.hdd10_pre)}%)이 가장 작았다(그림 3). 스페인은 발전용 비중이 커서 기온의 설명력이 낮다(R² ${f2(r5.ES.R2)}). 위기 뒤 민감도가 유의하게 커진 나라는 독일뿐이었고, 기저수요는 독일(${f1(r5.DE.crisis_level_pct)}%)·네덜란드(${f1(r5.NL.crisis_level_pct)}%)·이탈리아(${f1(r5.IT.crisis_level_pct)}%)에서 유의하게 줄었다. 독일의 수요 감축은 기온과 무관한 기저 부분(산업·발전)에 집중되었고, 그 결과 남은 수요에서 난방의 비중이 커진 것으로 해석된다.`),
);

// 4.3 예측 정확도
const m6 = (m) => f1(MC("ex_post", m)), a6 = (m) => f1(MC("ex_ante", m));
const inPost = N.mcs_ex_post.in.map(nm), inAnte = N.mcs_ex_ante.in.map(nm);
add(
  H2("4.3 예측 정확도 비교 (2023~2025년)"),
  ...FIG(fig("fig4_accuracy_heatmap.png"), "그림 4. 2023~2025년 롤링 1개월 앞 예측의 MAPE(%). (a) 사후예측, (b) 사전예측. 굵은 숫자는 열의 최솟값, 'Mean' 열의 점은 6개국 평균 손실 기준 90% 모델 신뢰집합에 포함된 모델이다."),
  P(`그림 4는 25개 모델의 국가별 MAPE다. 최고 단일 모델은 나라마다 달랐다. 6개국 평균 손실의 MCS(사후예측)에는 25개 중 ${N.mcs_ex_post.in.length}개 모델이 남았고, 국가별 MCS에도 ${Math.min(...Object.values(N.mcs_size_ex_post))}~${Math.max(...Object.values(N.mcs_size_ex_post))}개가 남았다. 36개월 평가로는 상위 모델들 사이의 1%p 안팎 차이를 통계적으로 구분할 수 없다는 뜻이다. 반면 사전예측에서는 6개국 평균 MCS에 ${N.mcs_ex_ante.in.length}개만 남았다: ${inAnte.join(", ")}.`),
  P(`기준 회귀(6개국 평균 ${m6(BENCH)}%)는 수요 수준이 바뀐 나라에서 크게 틀렸다(네덜란드 ${f1(N.main.ex_post[BENCH].NL)}%, 프랑스 ${f1(N.main.ex_post[BENCH].FR)}%). 전월 수요나 계절 차분을 쓰는 모델은 이 변화를 따라갔다. 검증 구간에서 계절 차분 차수를 고른 SARIMAX는 학습형 단일 모델 중 평균이 가장 낮았다(${m6(SAR)}%, 사전 ${a6(SAR)}%). 처음 실험에서 SARIMAX 차수를 고정했을 때(평균 7.4%)는 기계학습보다 못해 보였는데, 같은 튜닝 절차를 적용하자 순위가 바뀌었다. 모델 비교에서 튜닝의 공정성이 결론을 좌우할 수 있음을 보여 준다.`),
  P(`학습 없이 예측한 Chronos-2(공변량)의 평균 MAPE는 ${m6(CHR)}%로, 평가 구간에서 사후에 고른 국가별 최고 모델의 평균(약 5.4%)에 가까웠고 사전예측에서는 가장 낮았다(${a6(CHR)}%). 미리 정한 앙상블은 ${m6(ENS)}%(사전 ${a6(ENS)}%)로, 사후·사전예측 모두 6개국 모든 나라의 MCS에 포함되었다. 기계학습 모델은 사후예측에서 강했지만 평년 HDD를 넣는 사전예측에서는 트리 모델의 오차가 크게 늘었다(독일 GBM ${f1(N.main.ex_post["Gradient Boosting"].DE)}% → ${f1(N.main.ex_ante["Gradient Boosting"].DE)}%).`),
);

// 4.4 견고성
const L1 = (mode, m) => f1((L[mode] || {})[m]);
const O1 = (m, k = "MAPE_ex_post") => f1((OOS[m] || {})[k]);
const RT1 = (m) => f1((RT[m] || {}).MAPE_realtime);
add(
  H2("4.4 견고성: 장기 평가, 실시간 예측, 2026년 표본 외 검증"),
  ...FIG(fig("fig5_robustness.png"), "그림 5. 평가 설계별 6개국 평균 MAPE(%). 굵은 숫자는 열의 최솟값, 점은 6개국 평균 손실 기준 90% MCS 포함(본 평가와 장기 평가)이다. 실시간 열의 '–'는 해당 설계에서 평가하지 않은 모델이다."),
  P(`평가 기간을 늘리면 결론이 바뀌는지 보기 위해 유럽은 2018~2025년(96개월), 한국은 2020~2025년(72개월)을 별도의 검증 구간(유럽 2015~2017, 한국 2019)으로 튜닝해 다시 평가했다. 이 기간은 위기 전·위기·위기 후를 모두 포함한다. 장기 평가의 6개국 평균 MAPE는 SARIMAX ${L1("ex_post", SAR)}%, Chronos-2(공변량) ${L1("ex_post", CHR)}%, 앙상블 ${L1("ex_post", ENS)}%, 기준 회귀 ${L1("ex_post", BENCH)}%였다(그림 5). 6개국 평균 손실 MCS에는 ${(N.long_mcs || {}).ex_post ? N.long_mcs.ex_post.map(nm).join(", ") : "–"}가 남았다.`),
  P(`실시간 예측에서는 오차가 평균 0.5~1%p 커졌지만 순위는 유지되었다. Chronos-2(공변량)가 ${RT1(CHR)}%로 가장 낮았고, 앙상블 ${RT1(ENS)}%, 위기 항 Ridge ${RT1("Ridge + 위기 변수")}%가 뒤를 이었으며 기준 회귀는 ${RT1(BENCH)}%였다. 전월 수요에 크게 의존하는 트리 모델은 공표 지연의 손해가 컸다.`),
  P(`2026년 1~9월 표본 외 검증(국가당 9회, 스페인은 2026년 8월 자료 오류로 7회)은 2023~2025년으로 고정한 모델과 설정을 그대로 적용한 것이다. 6개국 평균 MAPE는 ${OR.slice(0, 4).map(([m, v]) => `${nm(m)} ${f1(v)}%`).join(", ")}로 상위 모델이 ${f1(OR[3][1] - OR[0][1])}%p 안에 모였고, 기준 회귀는 ${O1(BENCH)}%였다. 모델 순위는 2023~2025년과 비슷했다(순위상관 ${f2(N.oos_rho)}). 다만 SARIMAX는 프랑스에서 ${f1(OG[SAR].FR)}%로 크게 틀려 평균 ${O1(SAR)}%(${OR.length}개 중 ${orank(SAR)}위)에 그쳤다. 위기 시점을 2022년 9월로 바꾼 견고성 확인에서도 독일의 2026년 MAPE는 거의 같았다.`),
  ...FIG(fig("fig6_forecasts_DE.png"), `그림 6. 독일의 1개월 앞 사후예측(2023년 1월~2026년 9월). (a) 실제 수요와 예측(노란 음영은 Chronos-2의 80% 예측구간, 회색 구간은 2026년 표본 외 검증), (b) 연도별 MAPE. ${fig6Txt}`),
);

// 4.5 불확실성
const iv = (meth, lv) => N.intervals.find((x) => x.method === meth && Math.abs(x.level - lv) < 1e-6) || {};
add(
  H2("4.5 예측구간"),
  ...FIG(fig("fig7_interval_calibration.png"), "그림 7. 예측구간의 실제 포함률과 평균 폭. 큰 표식은 6개국 평균, 작은 표식은 개별 국가, 가로선은 명목 수준이다."),
  P(`명목 80% 구간에서 Chronos-2의 분위수 구간은 실제 포함률 ${f1(iv("Chronos-2 + 공변량 분위수", 0.8).cover)}%로 명목 수준에 가장 가까웠고 폭도 가장 좁았다(실제값의 ${f1(iv("Chronos-2 + 공변량 분위수", 0.8).width)}%). 회귀 예측구간과 conformal 구간은 ${f1(iv("회귀 PI (위기 변수)", 0.8).cover)}%, ${f1(iv("Conformal (LightGBM)", 0.8).cover)}%로 보수적이었다. 분위수 GBM은 ${f1(iv("분위수 GBM", 0.8).cover)}%로 크게 모자랐는데, 학습 표본이 100여 개월이라 꼬리 분위수를 직접 학습하기 어렵기 때문이다. 명목 95%에서는 LightGBM 주변의 conformal 구간이 포함률 ${f1(iv("Conformal (LightGBM)", 0.95).cover)}%, 폭 ${f1(iv("Conformal (LightGBM)", 0.95).width)}%로 가장 균형이 좋았다.`),
);

// 4.6 확장 분석
const SEC = N.sector, CL = N.climate;
add(
  H2("4.6 확장 분석"),
  P(`**외부 변수.** 독일에서 영업일, 화학 생산지수, 원자력·풍력 발전량, 석탄 가격 등을 하나씩 더해 변수 조합마다 다시 튜닝한 결과, 50개 비교 중 같은 모델 대비 유의하게 좋아진 경우는 2개로 우연 기대치(2.5개) 수준이었다. 기본 9개 입력을 유지하였다.`),
  P(`**통합 모델.** 6개국을 쌓아 학습한 LightGBM은 국가별 모델보다 평균 MAPE가 낮았다(사후 ${f1(N.global.LightGBM.global_ex_post)}% 대 ${f1(N.global.LightGBM.local_ex_post)}%, 사전 ${f1(N.global.LightGBM.global_ex_ante)}% 대 ${f1(N.global.LightGBM.local_ex_ante)}%). 반면 선형 모델과 MLP는 통합하면 나빠졌는데, 나라마다 HDD 기울기가 달라(그림 3) 한 식으로 묶이지 않기 때문이다.`),
  P(`**해석가능성.** 순열 SHAP으로 본 변수 기여도는 Ridge와 LightGBM 모두 6개국에서 HDD가 가장 컸다(독일 ${f1(N.shap_hdd.DE[0])}%·${f1(N.shap_hdd.DE[1])}%). 두 모델의 변수 순위 상관은 유럽 ${f2(Math.min(...["DE", "IT", "FR", "ES", "NL"].map((g) => N.shap_rho[g])))}~${f2(Math.max(...["DE", "IT", "FR", "ES", "NL"].map((g) => N.shap_rho[g])))}, 한국 ${f2(N.shap_rho.KR)}이었다(부록 그림 A2).`),
  P(`**부문별 수요와 기후 시나리오.** 독일 가정·소규모(SLP) 수요는 HDD 10당 ${f1(SEC["DE|SLP (가정·소규모)"])}% 늘어 산업·발전(RLM, ${f1(SEC["DE|RLM (산업·발전)"])}%)보다 네 배 이상 민감했다. 부문별 예측을 합산하는 방식은 총량 직접 예측보다 조금 나았지만 유의하지 않았다. 겨울(12~2월) HDD가 10% 줄면 연간 수요는 프랑스 ${f1(CL["FR|겨울(12~2월) HDD −10%"])}%, 독일 ${f1(CL["DE|겨울(12~2월) HDD −10%"])}%, 스페인 ${f1(CL["ES|겨울(12~2월) HDD −10%"])}% 변한다(부록 그림 A3).`),
);

// ---------------- 5. 논의 ----------------
add(
  H1("5. 논의"),
  P("**구조변화를 모형에 넣는 방법이 모형 종류보다 중요했다.** HDD 회귀는 기온과 수요의 관계를 잘 설명하지만(R² 0.9 이상), 2022년 이후 기저수요가 줄어든 나라에서는 예측이 체계적으로 높게 나왔다. 위기 더미와 HDD×위기 항 두 개만 더해도 네덜란드의 오차가 절반 이하로 줄었고, 전월 수요나 계절 차분을 쓰는 모델은 별도 설정 없이 이 변화를 따라갔다. 긴 학습 자료(2009년~)는 오히려 정확도를 떨어뜨렸다. 구조변화가 있는 에너지 수요에서는 변화를 명시적으로 표현하거나 최근 수준에 적응하는 구조가 필요하다."),
  P("**단일 최고 모델보다 모델군을 권고한다.** 36개월 평가에서는 상위 모델들 사이의 차이가 MCS로 구분되지 않았고, 최고 모델도 나라와 정보 시점에 따라 바뀌었다. 반면 튜닝한 SARIMAX와 미리 정한 앙상블은 6개국 사후·사전예측 모두에서 MCS에 남았다. 그중 앙상블은 장기 평가·실시간·2026년 표본 외 검증에서도 상위를 지켰지만, SARIMAX는 2026년 프랑스에서 크게 틀렸다. 실무에서는 어떤 모델이 최고일지 미리 알 수 없으므로 서로 다른 원리의 모델을 평균하는 앙상블이 가장 안전하다."),
  P("**파운데이션 모델은 작은 월 단위 자료에서 유용한 기준선이다.** Chronos-2는 학습 없이도 학습한 모델과 대등했고, 기온 전망이 필요 없는 단변량으로도 사전예측 정확도가 높았으며, 예측구간의 보정도 가장 좋았다. 다만 사전학습 자료에 평가 기간의 공개 통계가 포함되었을 가능성을 배제할 수 없어, 2026년 표본 외 결과를 함께 보는 것이 필요하다."),
  P("**회귀분석의 역할.** 정확도 경쟁과 별개로, 회귀분석은 난방 민감도의 크기와 위기 전후 변화, 가정 위반과 그 보정을 정량적으로 보여 주었다. 예측 모델의 해석(SHAP)도 회귀와 같은 결론(HDD 지배)을 냈다. 다만 잔차 자기상관 때문에 교재식 구간은 좁게 나오므로 HAC 표준오차를 함께 써야 한다."),
  H2("한계"),
  BUL("평가 기간이 국가당 36개월로 짧다. 장기 평가와 6개국 통합 MCS로 보완했지만, 상위 모델 간 작은 차이는 여전히 구분하기 어렵다."),
  BUL("1개월 앞 예측만 다뤘다. 저장 계획에 필요한 몇 달 앞 예측에서는 순위가 달라질 수 있다."),
  BUL(`Eurostat 최근 값 일부는 잠정치이고, 2026년 HDD는 공표 전이라 도시 기온으로 계산한 보정값을 썼다(교차검증 오차 월 ${calTxt} HDD).`),
  BUL("한국 수요는 소비가 아닌 공급량이고, 소비자 요금이 규제 요금이라 가격 효과를 위기 효과와 구분하기 어렵다."),
);

// ---------------- 6. 결론 ----------------
add(
  H1("6. 결론"),
  P(`6개국의 월별 천연가스 수요를 회귀분석과 세 계열의 예측 모델로 분석하였다. 독일의 난방 민감도는 2022년 위기 뒤 유의하게 커졌고 기저수요는 줄었으며, 이런 구조변화는 이탈리아를 뺀 5개국에서 통계적으로 확인되었다. 예측에서는 최고 단일 모델이 나라마다 달랐지만, 같은 절차로 튜닝한 SARIMAX와 회귀·기계학습·파운데이션 모델의 앙상블이 모든 나라와 정보 시점에서 최고 모델과 구별되지 않았고, 학습 없이 쓰는 Chronos-2도 이와 대등했다. 앙상블은 장기 평가, 실시간 정보, 2026년 표본 외 자료에서도 상위를 지켰다. 위기처럼 수요 구조가 바뀌는 시기에는 단일 모델의 작은 정확도 차이보다 구조변화의 반영과 모델 다양성이 더 중요하다.`),
  P("모든 자료와 코드, 결과는 공개 저장소(github.com/seoki0804/LNG_D_F)에 있으며 python/run_all.py 한 번으로 재현할 수 있다."),
);

// ---------------- 참고문헌 ----------------
const refs = [
  "Aidoni, A. et al. (2023). Deep learning models for natural gas demand forecasting: a comparative study of MLP, CNN and LSTM. Romanian Journal of Petroleum & Gas Technology.",
  "Amazon (2025). Chronos-2: From univariate to universal forecasting. arXiv:2510.15821.",
  "Andrews, D. W. K. (1993). Tests for parameter instability and structural change with unknown change point. Econometrica, 61(4), 821–856.",
  "Bai, J., & Perron, P. (2003). Computation and analysis of multiple structural change models. Journal of Applied Econometrics, 18(1), 1–22.",
  "Box, G. E. P., & Cox, D. R. (1964). An analysis of transformations. Journal of the Royal Statistical Society: Series B, 26(2), 211–252.",
  "Bundesnetzagentur (2026). Gas supply figures for 2025. Press release, 12 January 2026.",
  "Das, A., Kong, W., Sen, R., & Zhou, Y. (2024). A decoder-only foundation model for time-series forecasting. Proceedings of ICML 2024.",
  "Diebold, F. X., & Mariano, R. S. (1995). Comparing predictive accuracy. Journal of Business & Economic Statistics, 13(3), 253–263.",
  "EIA (2014). Short-Term Energy Outlook supplement: winter heating demand. U.S. Energy Information Administration.",
  "Eurostat (2023). EU natural gas consumption in 2022. Eurostat news, 4 May 2023.",
  "Fiorini, A., & Sileo, A. (2011). A note on asymmetries in heating degree-days and natural gas consumption dependence structure. Working Paper n. 42, Bocconi University.",
  "Hansen, P. R., Lunde, A., & Nason, J. M. (2011). The model confidence set. Econometrica, 79(2), 453–497.",
  "Harvey, D., Leybourne, S., & Newbold, P. (1997). Testing the equality of prediction mean squared errors. International Journal of Forecasting, 13(2), 281–291.",
  "Hyndman, R. J., & Koehler, A. B. (2006). Another look at measures of forecast accuracy. International Journal of Forecasting, 22(4), 679–688.",
  "Kutner, M. H., Nachtsheim, C. J., & Neter, J. (2004). Applied Linear Regression Models (4th ed.). McGraw-Hill/Irwin.",
  "Montero-Manso, P., & Hyndman, R. J. (2021). Principles and algorithms for forecasting groups of time series: Locality and globality. International Journal of Forecasting, 37(4), 1632–1653.",
  "Newey, W. K., & West, K. D. (1987). A simple, positive semi-definite, heteroskedasticity and autocorrelation consistent covariance matrix. Econometrica, 55(3), 703–708.",
  "Tian, N. et al. (2023). Application of forecasting strategies and techniques to natural gas consumption: A comprehensive review and comparative study. Engineering Applications of Artificial Intelligence.",
];
add(H1("참고문헌"), ...refs.map((t) => new Paragraph({ children: [new TextRun({ text: t, size: 18 })], spacing: { after: 80 },
  indent: { left: 360, hanging: 360 } })));

// ---------------- 부록 ----------------
add(
  new Paragraph({ children: [new PageBreak()] }),
  H1("부록"),
  ...FIG(fig("figA1_diagnostics.png"), "그림 A1. 독일 단순회귀의 잔차 진단. (a)~(c) Y ~ HDD, (d)~(f) √Y ~ HDD. 변환 뒤 이분산과 비선형성은 사라지지만 시간에 따른 잔차의 자기상관(b, e)은 남는다."),
  ...FIG(fig("figA2_shap.png"), "그림 A2. Ridge와 LightGBM의 변수 기여도(순열 SHAP, 평균 |SHAP| 비중). ρ는 두 모델의 변수 순위 상관이다."),
  ...FIG(fig("figA3_sector_climate.png"), "그림 A3. (a) 부문별 난방 민감도(독일 2021년 10월~, 한국 2016년~), (b) 겨울·난방철 HDD 10% 감소 시 연간 수요 변화와 95% 구간."),
);

build(children, path.join(__dirname, "천연가스_수요예측_보고서.docx"), {
  creator: "수요예측 팀", title: "2022년 에너지 위기 이후 월별 천연가스 수요예측",
  description: "회귀분석, 기계학습, 시계열 파운데이션 모델의 6개국 비교", runningHead: "월별 천연가스 수요예측 · 수요예측 팀",
}).then(() => console.log("저장: report/천연가스_수요예측_보고서.docx"));
