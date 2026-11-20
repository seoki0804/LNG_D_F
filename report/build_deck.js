// 학술대회 발표 자료(.pptx) + 발표 스크립트(슬라이드 노트). 수치는 numbers.json에서 읽는다.
// 실행: cd report && node build_deck.js   → report/천연가스_수요예측_발표.pptx
const fs = require("fs");
const os = require("os");
const path = require("path");
const pptxgen = require("pptxgenjs");
// 테마 색 적용 도구(Claude pptx 스킬의 apply_theme.js)가 있으면 쓰고, 없으면 Office 기본 테마로 둔다.
// 위치: PPTX_SKILL_DIR 환경변수, 없으면 ~/.claude/skills 아래에서 찾는다.
function findThemeTool() {
  const rel = path.join("scripts", "apply_theme.js");
  if (process.env.PPTX_SKILL_DIR) return path.join(process.env.PPTX_SKILL_DIR, rel);
  const stack = [[path.join(os.homedir(), ".claude", "skills"), 0]];
  while (stack.length) {
    const [dir, depth] = stack.pop();
    if (path.basename(dir) === "pptx" && fs.existsSync(path.join(dir, rel))) return path.join(dir, rel);
    if (depth >= 4 || !fs.existsSync(dir)) continue;
    for (const e of fs.readdirSync(dir, { withFileTypes: true }))
      if (e.isDirectory()) stack.push([path.join(dir, e.name), depth + 1]);
  }
  return null;
}
const THEME_TOOL = findThemeTool();
const applyTheme = THEME_TOOL && fs.existsSync(THEME_TOOL) ? require(THEME_TOOL).applyTheme
  : async () => console.log("테마 도구 없음: Office 기본 테마 색으로 저장 (내용은 같음)");

const ROOT = path.resolve(__dirname, "..");
const FIG = (n) => path.join(ROOT, "outputs", "figures", "paper", n);
const N = JSON.parse(fs.readFileSync(path.join(__dirname, "numbers.json"), "utf8"));
const OUT = path.join(__dirname, "천연가스_수요예측_발표.pptx");

const THEME = {
  name: "Gas Demand Navy",
  headFontFace: "Malgun Gothic", bodyFontFace: "Malgun Gothic",
  colors: { dk1: "1B1B1B", lt1: "FFFFFF", dk2: "16213E", lt2: "EEF1F7", accent1: "2A78D6", accent2: "EB6834",
            accent3: "1BAF7A", accent4: "EDA100", accent5: "E87BA4", accent6: "898781", hlink: "2A78D6", folHlink: "6250D6" },
};
const HEX = THEME.colors;
const W = 13.333, H = 7.5, MX = 0.6;

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";
pres.author = "수요예측 팀";
pres.title = "2022년 에너지 위기 이후 월별 천연가스 수요예측";
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
const C = pres.SchemeColor;

// ---------------- 레이아웃 ----------------
pres.defineSlideMaster({
  title: "TITLE_DARK", background: { color: HEX.dk2 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: MX, y: 2.2, w: W - 2 * MX, h: 1.6, fontSize: 34, bold: true,
        color: C.background1, valign: "bottom", align: "left" }, text: "" } },
    { placeholder: { options: { name: "body", type: "body", x: MX, y: 3.95, w: W - 2 * MX, h: 1.0, fontSize: 18,
        color: C.background2, valign: "top", align: "left" }, text: "" } },
  ],
});
pres.defineSlideMaster({
  title: "CONTENT", background: { color: HEX.lt1 },
  margin: [0.5, 0.6, 0.6, 0.6],
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: MX, y: 0.35, w: W - 2 * MX, h: 0.85, fontSize: 28, bold: true,
        color: C.text2, valign: "middle", align: "left" }, text: "" } },
    { text: { text: "월별 천연가스 수요예측 · 수요예측 팀", options: { x: MX, y: H - 0.42, w: 6, h: 0.3, fontSize: 10,
        color: HEX.accent6 } } },
  ],
  slideNumber: { x: W - MX - 0.6, y: H - 0.42, w: 0.6, h: 0.3, fontSize: 10, color: HEX.accent6, align: "right" },
});
pres.defineSlideMaster({
  title: "CONTENT_DARK", background: { color: HEX.dk2 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: MX, y: 0.35, w: W - 2 * MX, h: 0.85, fontSize: 28, bold: true,
        color: C.background1, valign: "middle", align: "left" }, text: "" } },
  ],
  slideNumber: { x: W - MX - 0.6, y: H - 0.42, w: 0.6, h: 0.3, fontSize: 10, color: "B9C2D6", align: "right" },
});

// ---------------- 도우미 ----------------
function pngSize(file) { const b = fs.readFileSync(file); return { w: b.readUInt32BE(16), h: b.readUInt32BE(20) }; }
function figure(slide, file, box, name) {   // 상자 안에 비율을 지켜 가운데 정렬
  const { w, h } = pngSize(file);
  let iw = box.w, ih = iw * h / w;
  if (ih > box.h) { ih = box.h; iw = ih * w / h; }
  slide.addImage({ path: file, x: box.x + (box.w - iw) / 2, y: box.y + (box.h - ih) / 2, w: iw, h: ih,
                   altText: name, objectName: name });
}
function bullets(slide, items, box, size = 16) {
  slide.addText(items.map((t, i) => ({ text: t, options: { bullet: true, breakLine: i < items.length - 1 } })),
    { ...box, fontSize: size, color: C.text1, valign: "top", paraSpaceAfter: 8, isTextBox: true, objectName: "bullets" });
}
function stat(slide, value, label, x, y, w, color = HEX.accent1, dark = false) {
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h: 1.55, rectRadius: 0.08,
    fill: { color: dark ? "22305A" : HEX.lt2 }, line: { color: dark ? "22305A" : HEX.lt2 }, objectName: `card ${label}` });
  slide.addText(value, { x: x + 0.2, y: y + 0.12, w: w - 0.4, h: 0.8, fontSize: 32, bold: true, color, isTextBox: true,
    margin: 0, objectName: `value ${label}` });
  slide.addText(label, { x: x + 0.2, y: y + 0.92, w: w - 0.4, h: 0.55, fontSize: 12, color: dark ? "D6DCEA" : C.text1,
    isTextBox: true, margin: 0, valign: "top", objectName: `label ${label}` });
}
function caption(slide, text, y) {
  slide.addText(text, { x: MX, y, w: W - 2 * MX, h: 0.35, fontSize: 11, color: HEX.accent6, isTextBox: true,
    objectName: "caption" });
}
const f1 = (x) => Number(x).toFixed(1), f2 = (x) => Number(x).toFixed(2);
// 2026년 표본 외·HDD 보정·독일 연도별 수치 (report_numbers.py)
const OR = N.oos_rank || [], OG = N.oos_by_geo || {}, DY = N.de_yearly || {}, HC = N.hdd_cal || {};
const calMae = Object.values(HC).map((v) => v.cv_mae);
const calTxt = `${Math.min(...calMae).toFixed(1)}~${Math.max(...calMae).toFixed(1)}`;
const SHORT = { "회귀 √Y~HDD+가격": "기준 회귀", "SARIMAX+HDD·가격": "SARIMAX", "Chronos-2 + 공변량": "Chronos-2",
  ENS: "앙상블", "하이브리드 (회귀+GBM 잔차)": "하이브리드", "Gradient Boosting": "GBM", LightGBM: "LightGBM" };
const sn = (m) => SHORT[m] || m;
const ensRank = OR.findIndex((x) => x[0] === "ENS") + 1, sarRank = OR.findIndex((x) => x[0] === "SARIMAX+HDD·가격") + 1;
const mcsMape = (mode, m) => N[`mcs_${mode}`].mape[m];
const S = N.simple, R5 = N.r5;

// ---------------- 1. 표지 ----------------
pres.addSection({ title: "도입" });
let s = pres.addSlide({ masterName: "TITLE_DARK", sectionTitle: "도입" });
s.addText("2022년 에너지 위기 이후\n월별 천연가스 수요예측", { placeholder: "title" });
s.addText("회귀분석 · 기계학습 · 시계열 파운데이션 모델의 6개국 비교\n수요예측 팀 (팀원 1, 팀원 2, 팀원 3) · 2026년 11월", { placeholder: "body" });
s.addNotes("안녕하십니까. 저희는 2022년 에너지 위기 이후 월별 천연가스 수요를 얼마나 정확하게 예측할 수 있는지, 회귀분석과 기계학습, 그리고 최근 나온 시계열 파운데이션 모델을 6개국 자료로 비교한 결과를 발표하겠습니다.");

// ---------------- 2. 배경 ----------------
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "도입" });
s.addText("위기 이후 같은 기온에서도 수요가 줄었다", { placeholder: "title" });
figure(s, FIG("fig1_demand.png"), { x: 5.0, y: 1.35, w: 7.75, h: 5.4 }, "Fig 1 demand");
stat(s, `${f1(Math.abs(R5.DE.crisis_level_pct))}%`, "독일 기저수요 감소\n(같은 기온 기준, 2022-03 이후)", MX, 1.5, 4.0, HEX.accent2);
stat(s, "864 TWh", "독일 2025년 가스 소비\n그중 가정·상업 약 40%", MX, 3.25, 4.0);
bullets(s, ["EU 수요 감축 규정(2022/1369) 이후 유럽 수요 수준이 구조적으로 바뀜",
            "과거 관계로 학습한 예측 모델이 위기 뒤에도 쓸 만한가?"], { x: MX, y: 5.0, w: 4.2, h: 1.7 }, 14);
s.addNotes("배경입니다. 오른쪽은 6개국의 월별 가스 수요입니다. 검은 선이 12개월 평균인데, 2022년 3월 이후 독일, 이탈리아, 프랑스, 네덜란드에서 수요 수준이 눈에 띄게 낮아졌습니다. 회귀로 기온 효과를 통제해도 독일의 기저수요는 약 21% 줄었습니다. 이렇게 구조가 바뀐 상황에서 과거 자료로 학습한 예측 모델이 여전히 쓸 만한지가 이 연구의 출발점입니다.");

// ---------------- 3. 연구 질문 ----------------
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "도입" });
s.addText("연구 질문", { placeholder: "title" });
const rq = [
  ["난방 민감도", "HDD가 늘면 수요는 얼마나 늘고, 위기 뒤 바뀌었는가?"],
  ["회귀 가정", "가정은 어디서 깨지고, 어떤 변환·추론이 보정하는가?"],
  ["국가 비교", "같은 구조에서 나라별 민감도와 위기 영향은?"],
  ["모델 비교", "기계학습·파운데이션 모델이 회귀보다 유의하게 정확한가?"],
  ["견고성", "평가 기간·정보 시점·표본 외에서도 결론이 유지되는가?"],
];
rq.forEach(([h, t], i) => {
  const col = i % 3, row = Math.floor(i / 3);
  const x = MX + col * 4.1, y = 1.55 + row * 2.6;
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w: 3.85, h: 2.3, rectRadius: 0.08, fill: { color: HEX.lt2 },
    line: { color: HEX.lt2 }, objectName: `rq card ${i + 1}` });
  s.addShape(pres.shapes.OVAL, { x: x + 0.25, y: y + 0.25, w: 0.6, h: 0.6, fill: { color: HEX.dk2 },
    line: { color: HEX.dk2 }, objectName: `rq number ${i + 1}` });
  s.addText(String(i + 1), { x: x + 0.25, y: y + 0.25, w: 0.6, h: 0.6, fontSize: 18, bold: true, color: C.background1,
    align: "center", valign: "middle", margin: 0, isTextBox: true, objectName: `rq digit ${i + 1}` });
  s.addText(h, { x: x + 1.0, y: y + 0.25, w: 2.7, h: 0.6, fontSize: 18, bold: true, color: C.text2, valign: "middle",
    margin: 0, isTextBox: true, objectName: `rq head ${i + 1}` });
  s.addText(t, { x: x + 0.25, y: y + 1.05, w: 3.35, h: 1.1, fontSize: 14, color: C.text1, valign: "top", margin: 0,
    isTextBox: true, objectName: `rq text ${i + 1}` });
});
s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: MX + 2 * 4.1, y: 1.55 + 2.6, w: 3.85, h: 2.3, rectRadius: 0.08,
  fill: { color: HEX.dk2 }, line: { color: HEX.dk2 }, objectName: "scope card" });
s.addText([{ text: "대상", options: { bold: true, breakLine: true } },
           { text: "독일·이탈리아·프랑스·스페인·네덜란드·한국, 월별 수요, 1개월 앞 예측" }],
  { x: MX + 2 * 4.1 + 0.25, y: 1.55 + 2.6 + 0.25, w: 3.35, h: 1.8, fontSize: 14, color: C.background1, valign: "top",
    margin: 0, isTextBox: true, objectName: "scope text" });
s.addNotes("연구 질문은 다섯 가지입니다. 첫째, HDD 즉 난방도일이 늘면 수요가 얼마나 늘고 위기 뒤 이 관계가 바뀌었는지. 둘째, 회귀 가정이 어디서 깨지고 어떻게 보정하는지. 셋째, 나라마다 민감도와 위기 영향이 어떻게 다른지. 넷째, 기계학습과 파운데이션 모델이 회귀보다 유의하게 정확한지. 다섯째, 이 결론이 평가 방식을 바꿔도 유지되는지입니다.");

// ---------------- 4. 자료 ----------------
pres.addSection({ title: "자료와 방법" });
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "자료와 방법" });
s.addText("자료: 6개국 월별 수요와 기상·가격·산업 변수", { placeholder: "title" });
const head = { bold: true, color: HEX.dk2, fill: { color: HEX.lt2 } };
const rows = [
  [{ text: "변수", options: head }, { text: "유럽 5개국", options: head }, { text: "한국", options: head }],
  ["수요", "Eurostat 내수 소비 (PJ), 2008~", "KOGAS 용도별 공급량 (천 톤), 2016~"],
  ["HDD·CDD", "Eurostat (18°C 기준, 15°C 이하인 날)", "기상청 7개 도시 일평균기온 → 같은 방식"],
  ["가격", "HICP 가스 요금 · EU 도매가 (전월)", "도시가스 CPI · 아시아 LNG (전월)"],
  ["산업·달력", "산업생산지수 · 영업일 수", "광공업생산지수 · 영업일 수"],
  ["2026년 HDD", `DWD(독일) · ERA5(4개국) 월별 보정, 오차 ${calTxt} HDD`, "기상청 관측"],
];
s.addTable(rows, { x: MX, y: 1.55, w: W - 2 * MX, colW: [2.0, 5.1, 5.033], fontSize: 14, color: HEX.dk1,
  border: { type: "solid", pt: 0.75, color: "D0D4DE" }, rowH: 0.62, valign: "middle", objectName: "data table" });
caption(s, "평가 구간 2023~2025년 결측 없음 · 2026-11-21 호출 · 스페인 2026-08 값(0)은 자료 오류로 제외", 5.6);
s.addNotes("자료입니다. 유럽 5개국은 Eurostat의 월별 가스 내수 소비를, 한국은 가스공사의 용도별 공급량을 씁니다. 설명변수는 난방도일과 냉방도일, 소비자 요금과 전월 도매가격, 산업생산, 영업일 수입니다. 한국의 난방도일은 기상청 7개 도시 기온으로 Eurostat과 같은 방식으로 계산했습니다. 2026년 검증에 필요한 유럽의 난방도일은 아직 공표 전이라 관측소와 재분석 자료로 계산해 Eurostat 값에 맞췄습니다. Eurostat 값은 산간을 포함한 국토 전체 기준이라 달마다 보정식을 따로 두었고, 한 해씩 빼고 맞혀 본 오차는 월 " + calTxt + " HDD입니다.");

// ---------------- 5. 방법: 모델 ----------------
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "자료와 방법" });
s.addText("비교한 모델: 네 묶음, 25개", { placeholder: "title" });
const fams = [
  ["통계 모형", HEX.accent1, "기준 회귀 √Y ~ HDD + 가격\n+ 위기 더미·HDD×위기\nSARIMAX · Holt-Winters\n계절 naive"],
  ["기계학습", HEX.accent3, "Ridge · Lasso · RF\nGBM · LightGBM · SVR · MLP\n회귀+GBM 하이브리드\n6개국 통합 LightGBM"],
  ["파운데이션 모델", HEX.accent4, "Chronos-2 · TimesFM 2.5\n학습 없이(zero-shot)\n단변량 / 공변량 포함"],
  ["앙상블", HEX.accent5, "미리 정한 구성의 단순 평균\n(회귀·ML·Chronos)\n검증 상위 3개 평균"],
];
fams.forEach(([h, col, t], i) => {
  const x = MX + i * 3.08, y = 1.6;
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w: 2.88, h: 4.4, rectRadius: 0.08, fill: { color: HEX.lt2 },
    line: { color: HEX.lt2 }, objectName: `family card ${i + 1}` });
  s.addShape(pres.shapes.OVAL, { x: x + 0.25, y: y + 0.3, w: 0.42, h: 0.42, fill: { color: col }, line: { color: col },
    objectName: `family dot ${i + 1}` });
  s.addText(h, { x: x + 0.8, y: y + 0.25, w: 2.0, h: 0.52, fontSize: 18, bold: true, color: C.text2, valign: "middle",
    margin: 0, isTextBox: true, objectName: `family head ${i + 1}` });
  s.addText(t, { x: x + 0.25, y: y + 1.0, w: 2.45, h: 3.2, fontSize: 14, color: C.text1, valign: "top", margin: 0,
    paraSpaceAfter: 6, isTextBox: true, objectName: `family text ${i + 1}` });
});
caption(s, "입력 9개: HDD, CDD, 소비자 요금, 전월 도매가, 산업생산, 월(sin·cos), 전월·12개월 전 수요 · 색은 이후 모든 그림의 모델군 색", 6.2);
s.addNotes("비교한 모델은 네 묶음, 모두 25개입니다. 통계 모형은 HDD와 가격으로 설명하는 기준 회귀, 여기에 위기 더미를 더한 회귀, SARIMAX와 Holt-Winters입니다. 기계학습은 선형 정규화부터 부스팅, 신경망, 그리고 6개국을 함께 학습하는 통합 모델까지 포함했습니다. 파운데이션 모델은 아마존의 Chronos-2와 구글의 TimesFM 2.5를 학습 없이 그대로 썼습니다. 마지막으로 평가 전에 구성을 정해 둔 앙상블입니다. 카드의 색은 이후 그림에서 같은 모델군을 뜻합니다.");

// ---------------- 6. 평가 설계 ----------------
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "자료와 방법" });
s.addText("평가 설계: 공정한 튜닝, 세 가지 정보 시점, 다중비교 보정", { placeholder: "title" });
figure(s, FIG("fig2_design.png"), { x: MX, y: 1.3, w: W - 2 * MX, h: 3.55 }, "Fig 2 design");
bullets(s, [
  "매달 다시 추정해 다음 달을 예측 (롤링 1개월 앞)",
  "하이퍼파라미터는 ML·SARIMAX·Holt-Winters 모두 검증 구간에서만 선택",
  "사후(실제 기온) · 사전(평년 HDD) · 실시간(공표 지연 반영)",
], { x: MX, y: 5.05, w: 6.0, h: 1.9 }, 15);
bullets(s, [
  "Diebold-Mariano(HLN) + 모델 신뢰집합 MCS(90%)",
  `누수 점검: 미래 자료를 훼손해도 예측 불변 ${N.leakage}/${N.leakage}건`,
  "랜덤 모델은 시드 5개 예측 평균",
], { x: 6.85, y: 5.05, w: 5.9, h: 1.9 }, 15);
s.addNotes("평가 설계입니다. 모든 모델은 매달 다시 추정해서 다음 달을 예측합니다. 중요한 점은 공정성입니다. 처음에는 기계학습만 튜닝하고 SARIMAX는 차수를 고정했는데, 같은 검증 절차를 모든 모델에 적용하자 결론이 바뀌었습니다. 정보 시점도 세 가지로 나눴습니다. 실제 기온을 아는 사후예측, 평년 기온을 쓰는 사전예측, 그리고 자료가 공표되는 데 걸리는 시간까지 반영한 실시간 예측입니다. 여러 모델을 동시에 비교하기 때문에 다중비교를 보정하는 모델 신뢰집합을 썼습니다.");

// ---------------- 7. 회귀분석 결과 ----------------
pres.addSection({ title: "결과" });
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "결과" });
s.addText("독일 회귀분석: HDD가 수요의 90%를 설명하지만 가정 위반이 있다", { placeholder: "title" });
stat(s, f2(S.r2), "단순회귀 R²\n(2008~2025, n = 216)", MX, 1.55, 2.9);
stat(s, `${f2(S.b1)} PJ`, `HDD 1당 월 수요 증가\n95% CI ${f2(S.b1_lo)}~${f2(S.b1_hi)}`, MX + 3.08, 1.55, 2.9);
stat(s, `λ = ${f2(S.boxcox)}`, "Box-Cox → √Y 변환\n이분산·비선형 해소", MX + 6.16, 1.55, 2.9, HEX.accent3);
stat(s, `DW ${f2(S.dw_y)}`, `잔차 자기상관 → HAC\n표준오차 ${f2(N.ch45.hac_ratio_b1)}배`, MX + 9.24, 1.55, 2.9, HEX.accent2);
bullets(s, [
  `이분산(BP p = ${f2(S.bp_y)})·적합결여(p = ${f2(S.lof_y)}) → √Y 변환 뒤 사라짐 (p = ${f2(S.bp_sqrt)}, ${f2(S.lof_sqrt)})`,
  `Working-Hotelling(W = ${f2(N.ch45.W)}) < Bonferroni(B = ${f2(N.ch45.B)}), 행렬 계산은 lm()과 일치`,
  `다중회귀(BIC): √Y ~ HDD + 풍력 + 위기 + HDD×위기, R² ${f2(N.multiple.r2)}`,
  `HDD 1당 효과 ${f2(N.multiple.hdd_pre)} → ${f2(N.multiple.hdd_post)} PJ (위기 전 → 후)`,
  `영업일은 유의하지 않음 (t = ${f2(N.multiple.workdays_t)})`,
], { x: MX, y: 3.4, w: 5.6, h: 3.5 }, 14);
figure(s, FIG("figA1_diagnostics.png"), { x: 6.3, y: 3.3, w: 6.45, h: 3.65 }, "Fig A1 diagnostics");
s.addNotes("독일 회귀분석 결과입니다. 난방도일 하나로 수요 변동의 90%를 설명하고, 난방도일이 1 늘면 월 수요가 약 0.55 PJ 늘어납니다. 다만 이분산과 비선형성이 있었고, Box-Cox 결과에 따라 제곱근 변환을 하자 두 문제가 모두 사라졌습니다. 그러나 잔차의 자기상관은 남았습니다. 그래서 Newey-West 표준오차를 함께 썼고, 기울기의 표준오차는 교재식 계산보다 1.6배 큽니다. 다중회귀에서는 위기 더미와 상호작용이 선택되었고, 위기 후 난방 효과가 0.50에서 0.61 PJ로 커졌습니다.");

// ---------------- 8. 구조변화·국가별 민감도 ----------------
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "결과" });
s.addText("위기 후 난방 민감도가 커진 나라는 독일뿐이다", { placeholder: "title" });
figure(s, FIG("fig3_hdd_sensitivity.png"), { x: MX, y: 1.35, w: 6.6, h: 5.4 }, "Fig 3 sensitivity");
const br = N.break;
bullets(s, [
  `HDD 10당 수요: 프랑스 ${f1(R5.FR.hdd10_pre)}% > 이탈리아 > 독일 > 네덜란드 > 한국 > 스페인 ${f1(R5.ES.hdd10_pre)}%`,
  `독일 ${f1(R5.DE.hdd10_pre)}% → ${f1(R5.DE.hdd10_post)}% (p < 0.001), 기저수요 ${f1(R5.DE.crisis_level_pct)}%`,
  `2022-03 Chow 검정: 이탈리아(p = ${f2(br.IT.chow_p)})를 뺀 5개국에서 유의`,
  `시점을 모를 때 sup-F: 독일 ${br.DE.supF_hac_date}, 네덜란드 ${br.NL.supF_hac_date} — EU 감축 규정 시행 무렵`,
], { x: 7.45, y: 1.55, w: 5.3, h: 5.0 }, 15);
s.addNotes("같은 로그 회귀 구조를 6개국에 추정한 결과입니다. 난방 민감도는 프랑스가 가장 크고 스페인이 가장 작습니다. 스페인은 가스가 발전에 많이 쓰여 기온의 설명력이 낮습니다. 위기 뒤 민감도가 유의하게 커진 나라는 독일뿐이었고, 독일은 기온과 무관한 기저 수요가 21% 줄었습니다. 구조변화 검정으로도 이탈리아를 뺀 다섯 나라에서 2022년 변화가 확인되었고, 시점을 모를 때 찾은 변화 시점은 EU 수요 감축 규정이 시행된 2022년 여름 무렵이었습니다.");

// ---------------- 9. 정확도 (네이티브 차트) ----------------
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "결과" });
s.addText("2023~2025년 정확도: 최고 단일 모델은 나라마다 다르다", { placeholder: "title" });
const keys = [["회귀 √Y~HDD+가격", "기준 회귀"], ["회귀 + 위기 변수", "회귀+위기"], ["SARIMAX+HDD·가격", "SARIMAX"],
  ["Gradient Boosting", "GBM"], ["LightGBM", "LightGBM"], ["MLP (16-8)", "MLP"], ["Chronos-2 + 공변량", "Chronos-2"],
  ["ENS", "앙상블"]];
s.addChart(pres.charts.BAR, [
  { name: "사후예측 (실제 기온)", labels: keys.map((k) => k[1]), values: keys.map((k) => +f1(mcsMape("ex_post", k[0]))) },
  { name: "사전예측 (평년 HDD)", labels: keys.map((k) => k[1]), values: keys.map((k) => +f1(mcsMape("ex_ante", k[0]))) },
], { x: MX, y: 1.35, w: 7.9, h: 5.4, barDir: "col", barGrouping: "clustered", chartColors: [HEX.dk2, "9EC5F4"],
  showValue: true, dataLabelPosition: "outEnd", dataLabelFontSize: 10, dataLabelColor: HEX.dk1, dataLabelFormatCode: "0.0",
  catAxisLabelFontSize: 11, valAxisLabelFontSize: 10, catAxisLabelColor: "52514E", valAxisLabelColor: "52514E",
  valAxisTitle: "6개국 평균 MAPE (%)", showValAxisTitle: true, valAxisTitleFontSize: 11, valAxisTitleColor: "52514E",
  valGridLine: { color: "E1E0D9", size: 0.5 }, catGridLine: { style: "none" }, showLegend: true, legendPos: "t",
  legendFontSize: 11, catAxisLabelFontFace: "+mn-lt", valAxisLabelFontFace: "+mn-lt", legendFontFace: "+mn-lt",
  dataLabelFontFace: "+mn-lt", valAxisTitleFontFace: "+mn-lt", valAxisMinVal: 0, objectName: "accuracy chart" });
bullets(s, [
  `기준 회귀는 구조가 바뀐 나라에서 크게 틀림: 네덜란드 ${f1(N.main.ex_post["회귀 √Y~HDD+가격"].NL)}%`,
  `위기 항 2개로 네덜란드 ${f1(N.main.ex_post["회귀 √Y~HDD+가격"].NL)} → 7.2%`,
  `튜닝한 SARIMAX가 학습형 단일 모델 평균 1위 (${f1(mcsMape("ex_post", "SARIMAX+HDD·가격"))}%)`,
  `Chronos-2는 학습 없이 ${f1(mcsMape("ex_post", "Chronos-2 + 공변량"))}%, 사전예측 1위 (${f1(mcsMape("ex_ante", "Chronos-2 + 공변량"))}%)`,
  "트리 모델은 평년 HDD를 넣으면 크게 나빠짐",
], { x: 8.75, y: 1.5, w: 4.0, h: 5.2 }, 14);
s.addNotes("2023년부터 2025년까지 36개월 동안 매달 예측한 결과의 6개국 평균 오차입니다. 짙은 막대는 실제 기온을 아는 사후예측, 옅은 막대는 평년 기온을 쓰는 사전예측입니다. 기준 회귀는 수요 수준이 바뀐 나라에서 크게 틀렸고, 네덜란드에서는 17%였습니다. 위기 항 두 개만 더해도 7%대로 줄었습니다. 같은 절차로 튜닝한 SARIMAX가 학습형 단일 모델 중 가장 정확했고, 학습을 전혀 하지 않은 Chronos-2도 이와 대등했으며 사전예측에서는 가장 좋았습니다.");

// ---------------- 10. MCS ----------------
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "결과" });
s.addText("통계적으로 구별되지 않는 모델군: MCS가 고른 것", { placeholder: "title" });
const designs = [["본 평가 사후", N.mcs_ex_post.in], ["본 평가 사전", N.mcs_ex_ante.in],
  ["장기 평가 사후", (N.long_mcs || {}).ex_post || []], ["장기 평가 사전", (N.long_mcs || {}).ex_ante || []]];
const mrows = [["SARIMAX+HDD·가격", "SARIMAX (튜닝)"], ["ENS", "앙상블 (회귀·ML·Chronos)"], ["Chronos-2 + 공변량", "Chronos-2 (공변량)"],
  ["Chronos-2 단변량", "Chronos-2 (단변량)"], ["Gradient Boosting", "GBM"], ["LightGBM", "LightGBM"],
  ["회귀 + 위기 변수", "회귀 + 위기 항"], ["회귀 √Y~HDD+가격", "기준 회귀"]];
const hdr = [{ text: "모델", options: head }, ...designs.map(([d]) => ({ text: d, options: { ...head, align: "center" } }))];
const body = mrows.map(([k, lab]) => [lab, ...designs.map(([, inc]) => ({ text: inc.includes(k) ? "●" : "–",
  options: { align: "center", color: inc.includes(k) ? HEX.accent1 : "B5B3AC", bold: inc.includes(k) } }))]);
s.addTable([hdr, ...body], { x: MX, y: 1.5, w: 8.2, colW: [3.0, 1.3, 1.3, 1.3, 1.3], fontSize: 14, color: HEX.dk1,
  border: { type: "solid", pt: 0.75, color: "D0D4DE" }, rowH: 0.5, valign: "middle", objectName: "mcs table" });
bullets(s, [
  "6개국 평균 손실 기준 90% 모델 신뢰집합",
  `본 평가(36개월)는 국가별 MCS에 25개 중 ${Math.min(...Object.values(N.mcs_size_ex_post))}~${Math.max(...Object.values(N.mcs_size_ex_post))}개가 남아 상위 모델을 가르기 어려움`,
  "장기 평가(72~96개월)에서 검정력이 오르자 SARIMAX·앙상블·Chronos-2만 남음",
  "권고: 단일 '최고 모델'보다 이 모델군",
], { x: 9.1, y: 1.5, w: 3.65, h: 5.2 }, 14);
caption(s, "● = MCS 포함 · 본 평가 2023~2025, 장기 평가 유럽 2018~2025·한국 2020~2025", 6.2);
s.addNotes("여러 모델을 동시에 비교하면 우연히 유의해 보이는 결과가 섞입니다. 그래서 모델 신뢰집합으로 '최고 모델과 통계적으로 구별되지 않는 모델들'을 골랐습니다. 36개월 평가에서는 나라마다 25개 중 14개 이상이 남아 상위 모델을 가를 수 없었습니다. 평가 기간을 72개월에서 96개월로 늘리자 검정력이 높아졌고, 튜닝한 SARIMAX, 앙상블, Chronos-2만 남았습니다. 그래서 저희는 단일 최고 모델보다 이 모델군을 권고합니다.");

// ---------------- 11. 견고성 ----------------
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "결과" });
s.addText("결론은 기간·정보 시점·표본 외에서도 유지된다", { placeholder: "title" });
// 그림 5와 같은 수치를 편집 가능한 표로: 칸 색 = MAPE 크기(파랑 명도), 굵게 = 열 최소, ● = 통합 MCS 포함
const D = N.design;
const ramp = ["CDE2FB", "9EC5F4", "6DA7EC", "3987E5", "256ABF", "184F95", "0D366B"];
const shade = (v) => ramp[Math.max(0, Math.min(ramp.length - 1, Math.floor((v - 4) / 9 * ramp.length)))];
const colLab = ["본 평가\n사후", "본 평가\n사전", "실시간", "장기\n사후", "장기\n사전", "2026\n사후", "2026\n사전"];
const rowLab = { "회귀 √Y~HDD+가격": "기준 회귀", "회귀 + 위기 변수": "회귀 + 위기 항", "SARIMAX+HDD·가격": "SARIMAX (튜닝)",
  "Holt-Winters": "Holt-Winters (튜닝)", "Ridge + 위기 변수": "Ridge + 위기 항", "Gradient Boosting": "GBM", LightGBM: "LightGBM",
  "MLP (16-8)": "MLP", "하이브리드 (회귀+GBM 잔차)": "하이브리드", "Chronos-2 단변량": "Chronos-2 (단변량)",
  "Chronos-2 + 공변량": "Chronos-2 (공변량)", ENS: "앙상블 (회귀·ML·Chronos)" };
const colMin = D.columns.map((_, j) => Math.min(...D.values.map((r) => (r[j] === null ? 99 : r[j]))));
const thead = [{ text: "6개국 평균 MAPE (%)", options: { ...head, fontSize: 12 } },
  ...colLab.map((c) => ({ text: c, options: { ...head, align: "center", fontSize: 12 } }))];
const tbody = D.models.map((m, i) => [{ text: rowLab[m] || m, options: { fontSize: 13 } },
  ...D.values[i].map((v, j) => v === null ? { text: "–", options: { align: "center", color: "9A988F", fontSize: 13 } } : {
    text: `${v.toFixed(1)}${D.mcs[i][j] ? " ●" : ""}`,
    options: { align: "center", fontSize: 13, bold: v === colMin[j], fill: { color: shade(v) },
               color: (v - 4) / 9 > 0.5 ? "FFFFFF" : HEX.dk1 } })]);
s.addTable([thead, ...tbody], { x: MX, y: 1.3, w: 8.75, colW: [2.45, 0.9, 0.9, 0.9, 0.9, 0.9, 0.9, 0.9], rowH: 0.385,
  border: { type: "solid", pt: 1, color: "FFFFFF" }, valign: "middle", objectName: "robustness table" });
caption(s, "굵게 = 열 최소 · ● = 6개국 평균 손실 기준 90% MCS 포함(본·장기 평가) · 장기: 유럽 2018~2025, 한국 2020~2025", 6.5);
const O = N.oos || {}, RT = N.realtime;
stat(s, `${f1(O.ENS.MAPE_ex_post)}%`, "2026년 1~9월 표본 외\n앙상블 6개국 평균 MAPE", 9.5, 1.45, 3.25, HEX.accent5);
stat(s, `${f1(RT["Chronos-2 + 공변량"].MAPE_realtime)}%`, "실시간 예측 1위\nChronos-2 (공변량)", 9.5, 3.15, 3.25, HEX.accent4);
stat(s, f2(N.oos_rho), "2023~2025 대비 2026년\n모델 순위 상관", 9.5, 4.85, 3.25, HEX.accent1);
s.addNotes(`결론이 평가 방식에 따라 바뀌는지 확인했습니다. 표의 각 열이 서로 다른 평가 설계입니다. 장기 평가와 공표 지연을 반영한 실시간 예측에서는 앙상블과 SARIMAX, Chronos-2가 꾸준히 상위에 있습니다. 2023~2025년으로 고정한 모델을 그대로 2026년에 적용한 표본 외 검증에서는 ${OR.slice(0, 4).map(([m, v]) => `${sn(m)} ${f1(v)}%`).join(", ")}로 상위 모델이 거의 붙어 있었고, 앙상블은 ${ensRank}위였습니다. SARIMAX는 프랑스에서 ${f1(OG["SARIMAX+HDD·가격"].FR)}%로 크게 틀려 ${sarRank}위로 내려갔습니다. 전체 모델 순위는 2023~2025년과 ${f2(N.oos_rho)}의 상관을 보였습니다.`);

// ---------------- 12. 사례 ----------------
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "결과" });
s.addText("독일 사례: 앙상블은 겨울 정점을 가장 잘 따라간다", { placeholder: "title" });
figure(s, FIG("fig6_forecasts_DE.png"), { x: MX, y: 1.35, w: W - 2 * MX, h: 4.9 }, "Fig 6 Germany");
caption(s, "앙상블 연도별 MAPE: " + ["2023", "2024", "2025", "2026"].map((y) => `${y}년 ${f1(DY.ENS[y])}%` + (DY["SARIMAX+HDD·가격"][y] < DY.ENS[y] ? `(SARIMAX ${f1(DY["SARIMAX+HDD·가격"][y])}%)` : "")).join(" · "), 6.4);
s.addNotes("독일의 실제 수요와 예측을 겹쳐 본 그림입니다. 기준 회귀는 위기 직후 겨울 정점을 낮게 예측했고, 앙상블이 정점을 가장 잘 따라갔습니다. 오른쪽 연도별 오차를 보면 앙상블은 2023년, 2024년, 그리고 표본 외인 2026년에 가장 정확했습니다. 다만 2025년에는 SARIMAX가 더 나았는데, 이처럼 해마다 최고 모델이 바뀐다는 점이 모델군을 권고하는 이유입니다.");

// ---------------- 13. 예측구간 ----------------
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "결과" });
s.addText("불확실성: Chronos-2의 예측구간이 가장 잘 보정되어 있다", { placeholder: "title" });
figure(s, FIG("fig7_interval_calibration.png"), { x: MX, y: 1.35, w: W - 2 * MX, h: 4.7 }, "Fig 7 intervals");
const iv = (m, l) => N.intervals.find((x) => x.method === m && Math.abs(x.level - l) < 1e-6);
caption(s, `80% 구간 포함률: Chronos-2 ${f1(iv("Chronos-2 + 공변량 분위수", 0.8).cover)}% (폭 ${f1(iv("Chronos-2 + 공변량 분위수", 0.8).width)}%) · 회귀 PI ${f1(iv("회귀 PI (위기 변수)", 0.8).cover)}% · 분위수 GBM ${f1(iv("분위수 GBM", 0.8).cover)}%`, 6.25);
s.addNotes("수요 계획에는 점예측뿐 아니라 불확실성도 중요합니다. 80% 예측구간의 실제 포함률을 보면 Chronos-2가 81%로 명목 수준에 가장 가까웠고 폭도 가장 좁았습니다. 회귀 예측구간과 conformal 구간은 넓게 잡는 보수적인 구간이었고, 분위수 GBM은 56%로 크게 모자랐습니다. 표본이 100여 개월이라 꼬리 분위수를 직접 학습하기 어렵기 때문입니다.");

// ---------------- 14. 확장 분석 ----------------
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "결과" });
s.addText("확장 분석: 부문, 통합 학습, 기후 시나리오", { placeholder: "title" });
figure(s, FIG("figA3_sector_climate.png"), { x: MX, y: 1.25, w: W - 2 * MX, h: 3.75 }, "Fig A3 sector climate");
const SEC = N.sector, CL = N.climate, GL = N.global.LightGBM;
stat(s, `${f1(SEC["DE|SLP (가정·소규모)"])}% vs ${f1(SEC["DE|RLM (산업·발전)"])}%`, "독일 HDD 10당 수요\n가정·소규모 vs 산업·발전", MX, 5.15, 3.9);
stat(s, `${f1(CL["DE|겨울(12~2월) HDD −10%"])}%`, "겨울 HDD 10% 감소 시\n독일 연간 수요", MX + 4.1, 5.15, 3.9, HEX.accent3);
stat(s, `${f1(GL.global_ex_ante)}%`, `6개국 통합 LightGBM 사전예측\n(국가별 ${f1(GL.local_ex_ante)}%)`, MX + 8.2, 5.15, 3.9, HEX.accent1);
s.addNotes("확장 분석 세 가지입니다. 독일의 가정·소규모 수요는 난방도일 10당 4.7% 늘어 산업·발전보다 네 배 이상 기온에 민감했습니다. 겨울 난방도일이 10% 줄면 독일의 연간 수요는 4.3% 줄어드는 것으로 추정됩니다. 그리고 6개국 자료를 함께 학습한 통합 LightGBM은 국가별 모델보다 사전예측 오차가 작았습니다. 반대로 선형 모델은 통합하면 나빠졌는데, 나라마다 난방 민감도가 달라 한 식으로 묶이지 않기 때문입니다.");

// ---------------- 15. 결론 ----------------
pres.addSection({ title: "결론" });
s = pres.addSlide({ masterName: "CONTENT_DARK", sectionTitle: "결론" });
s.addText("결론과 시사점", { placeholder: "title" });
const take = [
  ["구조변화를 모형에 넣어라", "위기 항 두 개로 기준 회귀 오차가 절반 이하로. 긴 과거 자료는 오히려 해롭다."],
  ["단일 최고 모델보다 모델군", "튜닝한 SARIMAX·앙상블·Chronos-2는 본·장기 평가의 통합 MCS에 모두 남는다."],
  ["파운데이션 모델은 강한 기준선", "학습 없이 학습한 모델과 대등, 예측구간 보정도 가장 좋다."],
];
take.forEach(([h, t], i) => {
  const y = 1.55 + i * 1.75;
  s.addShape(pres.shapes.OVAL, { x: MX, y: y + 0.1, w: 0.75, h: 0.75, fill: { color: [HEX.accent2, HEX.accent5, HEX.accent4][i] },
    line: { color: [HEX.accent2, HEX.accent5, HEX.accent4][i] }, objectName: `takeaway dot ${i + 1}` });
  s.addText(String(i + 1), { x: MX, y: y + 0.1, w: 0.75, h: 0.75, fontSize: 22, bold: true, color: HEX.dk2, align: "center",
    valign: "middle", margin: 0, isTextBox: true, objectName: `takeaway digit ${i + 1}` });
  s.addText(h, { x: MX + 1.1, y, w: 10.8, h: 0.6, fontSize: 22, bold: true, color: C.background1, margin: 0, valign: "middle",
    isTextBox: true, objectName: `takeaway head ${i + 1}` });
  s.addText(t, { x: MX + 1.1, y: y + 0.62, w: 10.8, h: 0.75, fontSize: 16, color: "D6DCEA", margin: 0, valign: "top",
    isTextBox: true, objectName: `takeaway text ${i + 1}` });
});
s.addNotes("결론은 세 가지입니다. 첫째, 위기처럼 구조가 바뀌는 시기에는 그 변화를 모형에 직접 넣는 것이 모델 종류를 바꾸는 것보다 효과가 큽니다. 둘째, 최고 단일 모델은 나라와 해마다 바뀌므로, 본 평가와 장기 평가의 통계 검정에서 꾸준히 살아남은 SARIMAX, 앙상블, Chronos-2 같은 모델군을 쓰는 것이 안전합니다. 셋째, 파운데이션 모델은 학습 없이도 강한 기준선이 되며, 특히 불확실성 표현이 좋았습니다.");

// ---------------- 16. 한계 ----------------
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "결론" });
s.addText("한계와 향후 과제", { placeholder: "title" });
const lim = [
  ["평가 기간", "본 평가는 국가당 36개월. 장기 평가·통합 MCS로 보완했지만 작은 차이는 구분 어려움"],
  ["예측 시계", "1개월 앞만 다룸 → 저장 계획에 필요한 3~6개월 앞 예측으로 확장"],
  ["자료", "최근 Eurostat 일부 잠정치, 2026년 HDD는 보정값, 한국은 공급량·규제 요금"],
  ["파운데이션 모델", "사전학습 자료에 평가 기간 통계가 섞였을 가능성 → 2026년 표본 외로 확인"],
];
lim.forEach(([h, t], i) => {
  const x = MX + (i % 2) * 6.1, y = 1.55 + Math.floor(i / 2) * 2.45;
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w: 5.85, h: 2.2, rectRadius: 0.08, fill: { color: HEX.lt2 },
    line: { color: HEX.lt2 }, objectName: `limit card ${i + 1}` });
  s.addText(h, { x: x + 0.3, y: y + 0.25, w: 5.25, h: 0.5, fontSize: 18, bold: true, color: C.text2, margin: 0,
    isTextBox: true, objectName: `limit head ${i + 1}` });
  s.addText(t, { x: x + 0.3, y: y + 0.85, w: 5.25, h: 1.2, fontSize: 14, color: C.text1, margin: 0, valign: "top",
    isTextBox: true, objectName: `limit text ${i + 1}` });
});
s.addNotes("한계도 분명히 말씀드리겠습니다. 본 평가 기간이 36개월로 짧아 장기 평가와 통합 검정으로 보완했습니다. 1개월 앞 예측만 다뤘기 때문에 저장 계획에 필요한 몇 달 앞 예측은 향후 과제입니다. 최근 자료 일부는 잠정치이고, 파운데이션 모델은 사전학습 자료에 평가 기간이 섞였을 가능성이 있어 2026년 표본 외 결과를 함께 확인했습니다.");

// ---------------- 17. 질의응답 ----------------
s = pres.addSlide({ masterName: "TITLE_DARK", sectionTitle: "결론" });
s.addText("감사합니다", { placeholder: "title" });
s.addText("질의응답\n자료·코드·결과: github.com/seoki0804/LNG_D_F (python/run_all.py 한 번으로 재현)", { placeholder: "body" });
s.addNotes("들어 주셔서 감사합니다. 모든 자료와 코드는 공개 저장소에 있고 한 번의 실행으로 재현할 수 있습니다. 질문 받겠습니다.");

pres.writeFile({ fileName: OUT })
  .then(() => applyTheme(OUT, THEME))
  .then(() => console.log("저장: report/천연가스_수요예측_발표.pptx"));
