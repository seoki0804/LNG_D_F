// 한국 연구 학술대회 발표 자료(.pptx) + 발표 스크립트(슬라이드 노트). 수치는 numbers.json에서 읽는다.
// 실행: korea/ 에서  node report/build_deck.js   → report/한국_LNG_수요예측_발표.pptx
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
const FIG = (n) => path.join(ROOT, "outputs", "figures", n);
const N = JSON.parse(fs.readFileSync(path.join(__dirname, "numbers.json"), "utf8"));
const OUT = path.join(__dirname, "한국_LNG_수요예측_발표.pptx");

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
pres.author = "안형석, 양의창, 권기범";
pres.title = "한국 LNG 수요의 용도별·지역별 예측";
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
    { text: { text: "한국 LNG 수요예측 · 안형석, 양의창, 권기범", options: { x: MX, y: H - 0.42, w: 6, h: 0.3, fontSize: 10,
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
// ---------------- 수치 도우미 (report_numbers.py → numbers.json) ----------------
const f0 = (x) => Number(x).toFixed(0), f1 = (x) => Number(x).toFixed(1), f2 = (x) => Number(x).toFixed(2);
const pv = (x) => (x < 0.001 ? "p < 0.001" : `p = ${x.toFixed(3)}`);
const NM = { "계절 naive": "Seasonal Naive", "회귀 √Y": "OLS(√Y)", SARIMAX: "SARIMAX", ETS: "ETS", Ridge: "Ridge",
  LightGBM: "LightGBM", "하이브리드 (회귀+Ridge)": "Hybrid(Ridge)", "하이브리드 (회귀+LightGBM)": "Hybrid(LGBM)",
  "Chronos-2": "Chronos-2", "Chronos-2 + 공변량": "Chronos-2(공변량)", "TimesFM 2.5": "TimesFM 2.5", 앙상블: "Ensemble" };
const nm = (m) => NM[m] || m;
const nat = (s, m, k = "all", i = "ex_ante", w = "eval") => (N.nat[`${s}|${m}|${i}|${w}`] || {})[k];
const ranked = (s, k = "all", i = "ex_ante", w = "eval") =>
  Object.keys(NM).map((m) => [m, nat(s, m, k, i, w)]).filter((x) => x[1] != null).sort((a, b) => a[1] - b[1]);
const best = (s, k = "all", i = "ex_ante", w = "eval") => ranked(s, k, i, w)[0];
const mcs = (s, h = "all", i = "ex_ante") => N.mcs[`${s}|${i}|${h}`] || [];
const prov = (m, me, lv) => (N.prov[`${m}|${me}|${lv}`] || {}).all;
const share = (s, m) => N.weather_share[`${s}|${m}`];   // 반올림 전 MAPE로 계산한 값 (그림 5와 같음)
const R = N.reg, D = N.data, PS = N.province_sens_range, SIX = N.six || {};
const cb = best("city"), pb = best("power"), tb = best("total");
const met = (s, m, k) => ((N.metrics || {})[`${s}|${m}|ex_ante|eval`] || {})[k];
const itv = (s, m, me) => (N.intervals || {})[`${s}|${m}|${me}`] || {};
const fr = (s) => (N.friedman || {})[`${s}|ex_ante`] || {};
const shp = (s, f) => (N.shap || {})[`${s}|${f}`];
const nearEns = (k) => Object.keys(NM).filter((m) => m !== "앙상블" && met(k, m, "rank") - met(k, "앙상블", "rank") < fr(k).CD).map(nm).join(", ") || "없음";

// ---------------- 1. 표지 ----------------
pres.addSection({ title: "도입" });
let s = pres.addSlide({ masterName: "TITLE_DARK", sectionTitle: "도입" });
s.addText("한국 LNG 수요의\n용도별·지역별 예측", { placeholder: "title" });
s.addText("회귀분석 · 기계학습 · 시계열 파운데이션 모델의 비교\n안형석, 양의창, 권기범 · 2026년 11월", { placeholder: "body" });
s.addNotes("안녕하십니까. 저희는 한국의 천연가스 수요를 도시가스용과 발전용, 그리고 17개 시도로 나눠 1개월부터 12개월 앞까지 예측하고, 회귀분석과 기계학습, 시계열 파운데이션 모델을 같은 조건에서 비교한 결과를 발표하겠습니다.");

// ---------------- 2. 배경 ----------------
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "도입" });
s.addText("같은 가스, 다른 수요: 도시가스용과 발전용", { placeholder: "title" });
figure(s, FIG("fig1_data.png"), { x: 4.75, y: 1.4, w: 8.0, h: 4.3 }, "Fig 1 data");
stat(s, `${f1(D.city_peak_ratio)}배`, "도시가스용 최대월/최소월\n(겨울 난방이 좌우)", MX, 1.5, 3.9, HEX.accent1);
stat(s, `${f1(D.power_peak_ratio)}배`, "발전용 최대월/최소월\n(전력수급이 좌우)", MX, 3.25, 3.9, HEX.accent2);
bullets(s, ["한국은 천연가스를 거의 모두 LNG로 수입 → 도입·저장 계획은 몇 달 앞을 보고 결정",
            "필요한 것은 1개월이 아니라 1~12개월 앞 예측"], { x: MX, y: 5.0, w: 4.0, h: 1.8 }, 14);
s.addNotes(`배경입니다. 한국은 천연가스를 거의 모두 LNG로 들여오기 때문에 몇 달 앞을 보고 도입 물량과 저장을 계획해야 합니다. 수요는 성격이 다른 두 부분으로 나뉩니다. 검은 선의 도시가스용은 겨울 난방 때문에 최대월이 최소월의 ${f1(D.city_peak_ratio)}배에 이르고, 파란 선의 발전용은 전력수급에 따라 움직여 계절 진폭이 ${f1(D.power_peak_ratio)}배로 작습니다. 그래서 저희는 용도를 나누고, 1개월이 아니라 1년 앞까지의 예측을 다뤘습니다.`);

// ---------------- 3. 연구 질문 ----------------
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "도입" });
s.addText("연구 질문", { placeholder: "title" });
const rq = [
  ["수요 구조", "도시가스용·발전용은 무엇으로 설명되고, 회귀 가정은 어디서 깨지는가?"],
  ["지역 차이", "시도마다 난방 민감도는 얼마나 다르고, 변했는가?"],
  ["다기간 예측", "1~12개월 앞에서 어떤 모델이 정확한가? 시계가 길면 순위가 바뀌는가?"],
  ["기온의 가치", "기온을 미리 알면 오차가 얼마나 줄어드는가?"],
  ["계층·비교", "시도 예측을 합치면 전국 예측이 좋아지는가? 다른 나라와는?"],
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
           { text: "한국 월별 수요: 용도 2(도시가스용·발전용) × 지역 17개 시도, 1~12개월 앞 예측" }],
  { x: MX + 2 * 4.1 + 0.25, y: 1.55 + 2.6 + 0.25, w: 3.35, h: 1.8, fontSize: 14, color: C.background1, valign: "top",
    margin: 0, isTextBox: true, objectName: "scope text" });
s.addNotes("연구 질문은 다섯 가지입니다. 첫째, 두 용도의 수요는 무엇으로 설명되는가. 둘째, 지역마다 기온에 대한 반응이 얼마나 다른가. 셋째, 1개월부터 12개월 앞까지 어떤 모델이 정확한가. 넷째, 기온을 미리 안다면 오차가 얼마나 줄어드는가. 다섯째, 시도별 예측을 합치면 전국 예측이 좋아지는가, 그리고 다른 나라와 비교하면 어떤가입니다.");

// ---------------- 4. 자료 ----------------
pres.addSection({ title: "자료와 방법" });
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "자료와 방법" });
s.addText("자료: 공개 통계만으로, 점검하고 고쳐서", { placeholder: "title" });
const head = { bold: true, color: C.text2, fill: { color: HEX.lt2 } };
s.addTable([
  [{ text: "자료", options: head }, { text: "출처", options: head }, { text: "기간", options: head }],
  ["용도별 월 공급량 (도시가스용·발전용)", "한국가스공사", "2016.01~2026.09"],
  ["시도별 도시가스 판매량 (17개 시도)", "한국가스공사", "1989.01~2022.12"],
  ["일평균기온 (시도 관측소 25곳) → 수요가중 HDD", "기상청 ASOS", "1989~2026"],
  ["요금·산업생산·전력거래량·LNG 가격", "KOSIS · FRED", "2001~2026"],
], { x: MX, y: 1.5, w: 7.4, colW: [3.9, 1.7, 1.8], fontSize: 13, color: HEX.dk1, rowH: 0.55, valign: "middle",
     border: { type: "solid", pt: 0.75, color: "D0D4DE" }, objectName: "data table" });
const fixes = [["2019년 도시가스용 오류", `7월 ${f0(D.fix2019.before)}천 톤 → 지역본부 자료로 복원 ${f0(D.fix2019.after)}천 톤`],
               ["시도 판매량 정의 변경", "2023년 1월 모든 시도 약 −25% → 2022년까지만 사용"],
               ["지역본부 발전용 불일치", "전국 값과 정의가 달라 지역 × 용도 분석에서 제외"]];
fixes.forEach(([h, t], i) => {
  const y = 1.5 + i * 1.65;
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 8.35, y, w: 4.4, h: 1.45, rectRadius: 0.08, fill: { color: HEX.lt2 },
    line: { color: HEX.lt2 }, objectName: `fix card ${i + 1}` });
  s.addText(h, { x: 8.6, y: y + 0.15, w: 4.0, h: 0.4, fontSize: 15, bold: true, color: HEX.accent2, margin: 0,
    isTextBox: true, objectName: `fix head ${i + 1}` });
  s.addText(t, { x: 8.6, y: y + 0.6, w: 4.0, h: 0.75, fontSize: 12.5, color: C.text1, margin: 0, valign: "top",
    isTextBox: true, objectName: `fix text ${i + 1}` });
});
caption(s, "HDD = Σ(18 − 기온), 일평균 15°C 이하인 날 · 전국 HDD는 2016~2018년 시도 판매 비중으로 가중 · 평년 = 직전 10년 같은 달 평균", 6.6);
s.addNotes(`자료는 모두 공개 통계입니다. 가스공사의 용도별 공급량과 시도별 판매량, 기상청 관측소 25곳의 기온, 그리고 요금과 산업·전력 지표를 썼습니다. 자료를 점검하다 세 가지 문제를 찾았습니다. 전국 자료의 2019년 도시가스용 값은 7월이 ${f0(D.fix2019.before)}천 톤으로 다른 해의 두 배여서 같은 기관의 지역본부 자료로 복원했습니다. 시도별 판매량은 2023년에 모든 시도가 함께 25% 낮아지는 정의 변경이 있어 2022년까지만 썼고, 지역본부별 발전용은 정의가 맞지 않아 쓰지 않았습니다.`);

// ---------------- 5. 평가 설계 ----------------
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "자료와 방법" });
s.addText("평가 설계: 같은 목표월, 같은 절차, 미래는 보지 않는다", { placeholder: "title" });
figure(s, FIG("fig2_design.png"), { x: MX, y: 1.3, w: 7.9, h: 4.2 }, "Fig 2 design");
bullets(s, ["예측 시점마다 다시 추정해 1~12개월 앞을 한 번에 예측",
            "모든 시계를 같은 36개 목표월(2023~2025)로 비교",
            "설정·차수는 2020~2022 검증 구간에서만 선택",
            "사전예측 = 평년 기온 · 사후예측 = 실제 기온",
            "DM 검정·MCS·평균 순위 검정, 80% 예측구간, 누수 자동 점검"], { x: 8.75, y: 1.45, w: 4.0, h: 4.6 }, 14);
caption(s, "모델: Seasonal Naive · OLS(√Y) · SARIMAX · ETS · Ridge/LightGBM(직접 다기간) · Hybrid(OLS+ML) · Chronos-2 · TimesFM 2.5 · Ensemble", 6.2);
s.addNotes("평가 방법입니다. 예측 시점마다 그때까지의 자료로 모델을 다시 추정해서 다음 12개월을 한 번에 예측합니다. 목표월이 2023년부터 2025년인 예측만 모아서, 1개월 앞이든 12개월 앞이든 같은 36개월로 비교했습니다. 모든 모델의 설정은 그 이전 검증 구간에서만 골랐습니다. 실제 예측처럼 미래 기온 자리에 평년값을 넣는 사전예측을 기본으로 하고, 실제 기온을 넣는 사후예측과 비교해 기온 정보의 가치를 따로 봤습니다.");

// ---------------- 6. 회귀 ----------------
pres.addSection({ title: "결과" });
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "결과" });
s.addText(`도시가스용은 기온이 ${f1(R.r2_simple * 100)}%를 설명, 발전용은 ${f0(R.r2_power_weather * 100)}%`, { placeholder: "title" });
stat(s, Number(R.r2_simple).toFixed(3), "도시가스용 R²\nY ~ HDD (2016~2025)", MX, 1.5, 3.0, HEX.accent1);
stat(s, `${f2(R.r2_power_weather)} → ${f2(R.r2_power)}`, "발전용 R²\n기온만 → 전력·정책·가격 추가", MX + 3.15, 1.5, 3.6, HEX.accent2);
stat(s, `${f1(R.b1_se_hac / R.b1_se)}배`, "HAC 표준오차 / OLS\n(잔차 자기상관)", MX + 6.9, 1.5, 2.7, HEX.accent3);
stat(s, R.break2_date, "도시가스용 관계 변화 시점\n(2020~2025 sup-F)", MX + 9.75, 1.5, 2.6, HEX.accent5);
bullets(s, [
  `원 척도는 이분산(BP ${pv(R.bp_y)}) → Box-Cox λ ${f2(R.boxcox)}, √Y로 해소(BP ${pv(R.bp_sqrt)})`,
  `잔차 자기상관이 강해(DW ${f2(R.dw_sqrt)}) 추론은 Newey-West 표준오차로`,
  `다중회귀 R² ${f2(R.r2_city_multi)}, 요금 탄력성 ${f2(R.price_elast)}로 작음 · 2022년 요금 인상기에 관계 변화`,
  `발전용: 전력거래량(${pv(R.p_elec)})·석탄 상한제(${pv(R.p_coal)})는 유의하지 않음 → 공급 측 정보가 빠져 있음`,
], { x: MX, y: 3.4, w: W - 2 * MX, h: 3.2 }, 16);
s.addNotes(`회귀분석 결과입니다. 도시가스용은 난방도일 하나로 변동의 ${f1(R.r2_simple * 100)}%가 설명됩니다. 다만 수요가 클수록 오차가 커지는 이분산이 있어 Box-Cox 결과에 따라 제곱근 변환을 했고, 월별 자료라 잔차 자기상관이 강해 HAC 표준오차로 추론했습니다. 2020년 이후만 보면 ${R.break2_date} 전후로 관계가 바뀌는데, 요금 인상기와 겹칩니다. 반면 발전용은 기온으로 ${f0(R.r2_power_weather * 100)}%만 설명되고, 전력거래량이나 석탄 상한제 기간을 넣어도 크게 늘지 않습니다. 원전 정비나 석탄 발전량 같은 공급 측 정보가 빠져 있다는 뜻입니다.`);

// ---------------- 7. 지역 ----------------
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "결과" });
s.addText(`난방 민감도는 시도마다 ${f1(PS.min)}%~${f1(PS.max)}%로 다르다`, { placeholder: "title" });
figure(s, FIG("fig3_province_sensitivity.png"), { x: MX, y: 1.3, w: W - 2 * MX, h: 5.0 }, "Fig 3 provinces");
caption(s, `HDD 10 증가당 도시가스 판매량 % (당월 + 전월, 검침 지연 반영) · 기울기 동일성 F = ${f0(N.province_F)}, p < 0.001 · 2020년대에 17곳 중 15곳 상승`, 6.45);
s.addNotes(`지역별로 보면, 기온이 같은 만큼 내려갈 때 늘어나는 판매량이 ${PS.min_prov} ${f1(PS.min)}%에서 ${PS.max_prov} ${f1(PS.max)}%까지 세 배 가까이 차이 납니다. 17개 시도의 기울기가 같다는 가설은 강하게 기각됩니다. 산업용 수요가 많은 울산, 충남, 경북이 낮고 제주, 서울, 대전이 높습니다. 판매량은 검침 시점 기준이라 전월 기온까지 넣었는데, 이 점이 뒤의 예측에서도 중요했습니다.`);

// ---------------- 8. 예측 시계 ----------------
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "결과" });
s.addText("1~12개월 앞: 발전용이 도시가스용보다 두 배 어렵다", { placeholder: "title" });
figure(s, FIG("fig4_horizon.png"), { x: MX, y: 1.3, w: W - 2 * MX, h: 4.75 }, "Fig 4 horizon");
caption(s, `1~12개월 평균 사전예측 MAPE 최저: 도시가스용 ${nm(cb[0])} ${f1(cb[1])}% · 발전용 ${nm(pb[0])} ${f1(pb[1])}% · 합계 ${nm(tb[0])} ${f1(tb[1])}% (Seasonal Naive ${f1(nat("city", "계절 naive"))} / ${f1(nat("power", "계절 naive"))} / ${f1(nat("total", "계절 naive"))}%)`, 6.25);
s.addNotes(`예측 시계별 오차입니다. 가로축이 몇 개월 앞인지, 세로축이 오차율입니다. 도시가스용은 가장 좋은 모델이 평균 ${f1(cb[1])}%, 발전용은 ${f1(pb[1])}%로 발전용이 두 배가량 어렵습니다. 점선인 Seasonal Naive, 즉 작년 같은 달 값과 비교하면 도시가스용에서는 대부분의 모델이 크게 낫지만, 발전용에서는 개선 폭이 작습니다. 시계가 길어지면 오차가 조금씩 커지지만, 평년 기온을 쓰는 한 12개월 앞도 1개월 앞과 크게 다르지 않습니다.`);

// ---------------- 9. MCS 표 ----------------
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "결과" });
s.addText("Ensemble이 평균 1위, 그러나 통계적으로 최고 모델은 하나가 아니다", { placeholder: "title" });
const SER = [["city", "도시가스용"], ["power", "발전용"], ["total", "합계"]];
const th = [{ text: "", options: head }, ...SER.map(([, n]) => ({ text: n, options: { ...head, align: "center" } }))];
const cell = (t) => ({ text: t, options: { fontSize: 13, align: "center", valign: "middle" } });
const outM = (k) => Object.keys(NM).filter((m) => nat(k, m) != null && !mcs(k).includes(m)).map(nm).join(", ") || "없음";
const rows = [th,
  [{ text: "1~12 평균 최저", options: { bold: true, fontSize: 13 } }, ...SER.map(([k]) => cell(`${nm(best(k)[0])} ${f1(best(k)[1])}%`))],
  [{ text: "h = 1 최저", options: { bold: true, fontSize: 13 } }, ...SER.map(([k]) => cell(`${nm(best(k, "h1")[0])} ${f1(best(k, "h1")[1])}%`))],
  [{ text: "h = 12 최저", options: { bold: true, fontSize: 13 } }, ...SER.map(([k]) => cell(`${nm(best(k, "h12")[0])} ${f1(best(k, "h12")[1])}%`))],
  [{ text: "MCS(90%)에 남은 모델", options: { bold: true, fontSize: 13 } }, ...SER.map(([k]) => cell(`${mcs(k).length}개 / ${Object.keys(NM).filter((m) => nat(k, m) != null).length}개`))],
  [{ text: "MCS 밖 (유의하게 나쁨)", options: { bold: true, fontSize: 13 } }, ...SER.map(([k]) => cell(outM(k)))],
];
s.addTable(rows, { x: MX, y: 1.45, w: W - 2 * MX, colW: [2.6, 3.17, 3.17, 3.19], rowH: [0.5, 0.6, 0.6, 0.6, 0.6, 1.4],
  border: { type: "solid", pt: 0.75, color: "D0D4DE" }, color: HEX.dk1, objectName: "mcs table" });
caption(s, "MCS = 최고 모델과 통계적으로 구별되지 않는 모델 집합 (범위 통계량, 정상 부트스트랩 5,000회, 손실 APE)", 6.45);
s.addNotes(`통계적으로 보면 결론은 조심스럽습니다. 평균으로는 미리 정한 Ensemble이 세 계열 모두 가장 정확했지만, 1개월 앞과 12개월 앞의 최고 모델은 용도마다 다릅니다. 최고 모델과 통계적으로 구별되지 않는 모델 집합에는 12개 중 ${mcs("city").length}개, ${mcs("power").length}개, ${mcs("total").length}개가 남습니다.${mcs("power").includes("계절 naive") ? " 특히 발전용은 작년 같은 달 값을 그대로 쓰는 Seasonal Naive조차 빠지지 않습니다." : ""} 36개월로는 상위 모델끼리의 작은 차이를 가릴 수 없다는 뜻이고, 그래서 한 모델을 고르기보다 서로 다른 원리의 모델을 함께 쓰는 쪽을 권합니다.`);


// ---------------- 9-2. 여러 지표와 평균 순위 ----------------
if (N.metrics) {
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "결과" });
  s.addText("지표를 바꿔도 같은 결론: Ensemble이 1위, 상위권 차이는 작다", { placeholder: "title" });
  figure(s, FIG("fig9_critical_difference.png"), { x: MX, y: 1.2, w: W - 2 * MX, h: 5.05 }, "Fig 9 critical difference");
  caption(s, `MAE·MASE·평균 순위 모두 Ensemble 1위 (MASE ${f2(met("city", "앙상블", "MASE"))} / ${f2(met("power", "앙상블", "MASE"))} / ${f2(met("total", "앙상블", "MASE"))}) · MAPE 95% 신뢰구간은 상위 모델끼리 겹침 · Friedman p < 0.001, Nemenyi CD = ${f2(fr("total").CD)} · 막대로 이어진 모델은 구별되지 않음`, 6.4);
  s.addNotes(`MAPE 하나만 보면 지표에 따라 결론이 달라질 수 있어서, 머신러닝 논문에서 쓰는 지표들로 다시 확인했습니다. MAE, MASE, 그리고 목표월과 시계마다 매긴 순위의 평균에서 세 계열 모두 Ensemble이 1위였습니다. 다만 MAPE의 신뢰구간은 상위 모델끼리 겹치고, 그림처럼 평균 순위 차이가 임계차보다 작은 모델들이 굵은 막대로 묶입니다. 합계에서는 ${nearEns("total")}까지 Ensemble과 구별되지 않습니다. 같은 목표월을 여러 시계에서 예측하기 때문에 이 검정은 참고용이고, 결론은 앞의 모델 신뢰집합과 같습니다.`);
}

// ---------------- 10. 기온의 가치 ----------------
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "결과" });
s.addText("기온을 알면 도시가스용 오차는 크게 준다, 발전용은 아니다", { placeholder: "title" });
figure(s, FIG("fig5_weather_value.png"), { x: MX, y: 1.3, w: 8.6, h: 4.9 }, "Fig 5 weather");
stat(s, `${f0(share("city", "앙상블"))}%`, "도시가스용 오차 중\n기온 불확실성 몫", 9.5, 1.6, 3.25, HEX.accent1);
stat(s, `${f0(share("power", "앙상블"))}%`, "발전용 오차 중\n기온 불확실성 몫", 9.5, 3.35, 3.25, HEX.accent2);
caption(s, "Ensemble 기준, 사전예측(평년 기온) − 사후예측(실제 기온) MAPE의 비중, 1~12개월 평균", 6.45);
s.addNotes(`실제 기온을 미리 안다고 가정한 사후예측과 비교해 보았습니다. 도시가스용은 오차의 약 ${f0(share("city", "앙상블"))}%가 기온을 몰라서 생긴 것으로, 기온 전망을 개선하면 그만큼 줄일 수 있습니다. 반면 발전용은 ${f0(share("power", "앙상블"))}%에 그쳐, 기온보다 전력 공급 측 정보가 필요합니다. 용도마다 다른 정보에 투자해야 한다는 실무적 시사점입니다.`);


// ---------------- 10-2. 예측구간 ----------------
if (N.intervals) {
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "결과" });
  s.addText("불확실성: AI 모델의 자체 구간은 너무 좁고, 보정 구간은 넓다", { placeholder: "title" });
  figure(s, FIG("fig11_intervals.png"), { x: MX, y: 1.3, w: 8.6, h: 4.98 }, "Fig 11 intervals");
  stat(s, `${f0(itv("total", "Chronos-2 + 공변량", "native").cov)}%`, "Chronos-2 자체 80% 구간의\n실제 적중률 (합계)", 9.5, 1.5, 3.25, HEX.accent2);
  stat(s, `${f0(itv("total", "앙상블", "conformal").cov)}%`, "Ensemble 보정(conformal)\n80% 구간의 적중률 (합계)", 9.5, 3.3, 3.25, HEX.accent1);
  caption(s, "conformal = 검증 구간(2020~2022) 오차로 시계마다 만든 80% 구간 · 자체 = 모델이 낸 10%·90% 분위수 · 평가 목표월 2023~2025", 6.45);
  s.addNotes(`수급계획에는 예측값과 함께 불확실성의 범위가 필요합니다. 80% 예측구간이 실제로 얼마나 맞았는지 보았습니다. Chronos-2가 스스로 낸 구간은 합계에서 ${f0(itv("total", "Chronos-2 + 공변량", "native").cov)}%만 맞아 불확실성을 과소평가했습니다. 반대로 검증 구간의 오차로 만든 보정 구간은 ${f0(itv("total", "앙상블", "conformal").cov)}%를 맞춰 너무 넓었는데, 검증 구간에 코로나19와 2022년 가격 급등기가 들어 있었기 때문입니다. 파운데이션 모델의 분위수를 그대로 믿지 말고, 최근 오차로 보정을 갱신해야 한다는 시사점입니다.`);

  // ---------------- 10-3. 특성 기여도 ----------------
  s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "결과" });
  s.addText("LightGBM이 본 것: 도시가스용은 기온, 발전용은 여러 요인", { placeholder: "title" });
  figure(s, FIG("fig12_shap.png"), { x: MX, y: 1.4, w: W - 2 * MX, h: 4.3 }, "Fig 12 SHAP");
  bullets(s, [
    `도시가스용: 목표월 HDD ${f0(shp("city", "hdd"))}% · 1년 전 수요 ${f0(shp("city", "lag12"))}% → 회귀분석 결과와 같음`,
    `발전용: HDD ${f0(shp("power", "hdd"))}% · CDD ${f0(shp("power", "cdd"))}% · 1년 전 수요 ${f0(shp("power", "lag12"))}% · 요금 지수 ${f0(shp("power", "log_cpi"))}%(추세 대용) · 석탄 상한제 ${f0(shp("power", "coal_cap"))}%`,
  ], { x: MX, y: 5.75, w: W - 2 * MX, h: 1.1 }, 14);
  s.addNotes(`기계학습 모델이 무엇을 보고 예측했는지 SHAP으로 확인했습니다. 도시가스용은 목표월 난방도일이 기여의 ${f0(shp("city", "hdd"))}%를 차지해 회귀분석과 같은 이야기를 합니다. 발전용은 난방도일, 냉방도일, 작년 같은 달 수요, 추세 역할을 하는 요금 지수, 석탄 상한제 기간으로 기여가 흩어져 있습니다. 발전용을 설명할 결정적인 변수가 없다는 뜻이고, 앞에서 본 공급 측 정보의 필요성과 맞닿아 있습니다.`);
}

// ---------------- 11. 계층 ----------------
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "결과" });
s.addText("시도 예측을 합치면? 기본 모델이 약할 때만 도움", { placeholder: "title" });
figure(s, FIG("fig6_hierarchy.png"), { x: MX, y: 1.3, w: W - 2 * MX, h: 4.2 }, "Fig 6 hierarchy");
bullets(s, [
  `ETS ${f1(prov("ETS", "기본", "전국"))}% → MinT ${f1(prov("ETS", "MinT", "전국"))}%, Chronos-2 ${f1(prov("Chronos-2 + 공변량", "기본", "전국"))}% → ${f1(prov("Chronos-2 + 공변량", "MinT", "전국"))}%: 조정이 전국 예측을 개선`,
  `전월 기온을 넣은 회귀는 전국 직접 ${f1(prov("회귀 √Y", "기본", "전국"))}%가 최선, 조정하면 나빠짐(MinT ${f1(prov("회귀 √Y", "MinT", "전국"))}%)`,
], { x: MX, y: 5.55, w: W - 2 * MX, h: 1.3 }, 14);
s.addNotes(`17개 시도를 따로 예측해 합치는 계층 예측입니다. 지수평활이나 Chronos-2처럼 기본 모델이 상대적으로 약할 때는 시도 정보를 합치는 상향식이나 MinT 조정이 전국 예측을 개선했습니다. 하지만 전월 기온까지 넣은 회귀는 전국을 직접 예측한 것이 ${f1(prov("회귀 √Y", "기본", "전국"))}%로 가장 정확했고, 조정하면 오히려 나빠졌습니다. 계층 조정은 좋은 전국 모델을 대신하지 못하는 보완책이라는 결론입니다.`);

// ---------------- 12. 2026 ----------------
const hold = (k) => ranked(k, "all", "ex_ante", "hold");
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "결과" });
s.addText("2026년 표본 외: 도시가스용은 맞고, 발전용은 여름에 빗나갔다", { placeholder: "title" });
figure(s, FIG("fig7_holdout_2026.png"), { x: MX, y: 1.3, w: W - 2 * MX, h: 4.75 }, "Fig 7 holdout");
caption(s, `2026년 1~9월, 1~12개월 평균 MAPE 최저: 도시가스용 ${nm(hold("city")[0][0])} ${f1(hold("city")[0][1])}% · 발전용 ${nm(hold("power")[0][0])} ${f1(hold("power")[0][1])}% · 합계 ${nm(hold("total")[0][0])} ${f1(hold("total")[0][1])}%`, 6.25);
s.addNotes(`모든 설정을 고정한 뒤 2026년 1월부터 9월까지에 적용했습니다. 그림은 2025년 12월 시점에서 본 예측입니다. 도시가스용은 실제 수요를 잘 따라갔지만, 발전용은 2026년 7~8월 수요가 예년보다 크게 늘어 모든 모델이 낮게 예측했습니다. 기온만으로는 알 수 없는 전력 공급 측 변화가 있었던 것으로 보이며, 앞의 회귀 결과와 같은 이야기입니다.`);

// ---------------- 13. 다른 나라 ----------------
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "결과" });
s.addText("같은 모델로 본 6개국: 한국은 덜 민감하고, 더 예측하기 쉽다", { placeholder: "title" });
figure(s, FIG("fig8_six_countries.png"), { x: MX, y: 1.3, w: W - 2 * MX, h: 4.4 }, "Fig 8 six countries");
bullets(s, [
  "독일·이탈리아·프랑스·스페인·네덜란드에 같은 모델·같은 평가 절차(1개월 앞, 2023~2025)를 적용",
  "유럽은 2022년 위기로 수요 수준이 바뀌어 기준 회귀가 크게 틀림 · 한국은 공급 충격이 없어 회귀도 정확",
], { x: MX, y: 5.75, w: W - 2 * MX, h: 1.1 }, 14);
s.addNotes(`같은 모델과 같은 평가 절차를 유럽 5개국에도 적용했습니다. 한국의 난방 민감도는 HDD 10당 ${SIX.r5 ? f1(SIX.r5.KR.hdd10_post) : "–"}%로 프랑스나 독일보다 낮습니다. 유럽은 2022년 에너지 위기로 수요 수준 자체가 바뀌어 위기를 반영하지 않은 회귀가 크게 틀렸지만, 한국은 그런 공급 충격이 없어 단순한 회귀도 여섯 나라 중 가장 정확했습니다. 어느 나라에서든 튜닝한 SARIMAX와 Ensemble이 최고 모델과 구별되지 않았다는 점은 한국 결과와 같습니다.`);

// ---------------- 14. 결론 ----------------
pres.addSection({ title: "결론" });
s = pres.addSlide({ masterName: "CONTENT_DARK", sectionTitle: "결론" });
s.addText("결론과 시사점", { placeholder: "title" });
const take = [
  ["용도별로 다른 정보에 투자하라", "도시가스용은 기온 전망, 발전용은 원전·석탄·전력수요 같은 공급 측 정보."],
  ["단일 최고 모델보다 모델군", "시계·용도마다 최고 모델이 바뀌고 상위 모델은 통계적으로 구별되지 않는다."],
  ["지역 정보는 보완재", "시도 민감도는 세 배 차이지만, 계층 조정은 약한 모델만 개선한다."],
];
take.forEach(([h, t], i) => {
  const y = 1.55 + i * 1.75;
  s.addShape(pres.shapes.OVAL, { x: MX, y: y + 0.1, w: 0.75, h: 0.75, fill: { color: [HEX.accent1, HEX.accent5, HEX.accent3][i] },
    line: { color: [HEX.accent1, HEX.accent5, HEX.accent3][i] }, objectName: `takeaway dot ${i + 1}` });
  s.addText(String(i + 1), { x: MX, y: y + 0.1, w: 0.75, h: 0.75, fontSize: 22, bold: true, color: HEX.dk2, align: "center",
    valign: "middle", margin: 0, isTextBox: true, objectName: `takeaway digit ${i + 1}` });
  s.addText(h, { x: MX + 1.1, y, w: 10.8, h: 0.6, fontSize: 22, bold: true, color: C.background1, margin: 0, valign: "middle",
    isTextBox: true, objectName: `takeaway head ${i + 1}` });
  s.addText(t, { x: MX + 1.1, y: y + 0.62, w: 10.8, h: 0.75, fontSize: 16, color: "D6DCEA", margin: 0, valign: "top",
    isTextBox: true, objectName: `takeaway text ${i + 1}` });
});
s.addNotes("결론은 세 가지입니다. 첫째, 도시가스용과 발전용은 오차의 원인이 달라서, 도시가스용은 기온 전망을, 발전용은 전력 공급 측 정보를 확보하는 것이 정확도를 높이는 길입니다. 둘째, 예측 시계와 용도마다 최고 모델이 바뀌고 상위 모델들이 통계적으로 구별되지 않으므로, 서로 다른 모델을 함께 운용하는 것이 안전합니다. 셋째, 지역별 민감도 차이는 크지만, 시도 예측을 합치는 계층 조정은 좋은 전국 모델을 대신하지 못하는 보완책입니다.");

// ---------------- 15. 한계 ----------------
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "결론" });
s.addText("한계와 향후 과제", { placeholder: "title" });
const lim = [
  ["평가 기간", "전국 용도별 자료는 2016년부터, 평가 36개월. 2019년은 복원값"],
  ["지역 자료", "시도 판매량은 2023년 정의 변경으로 2022년까지, 주택·산업 용도 구분은 월별 비공개"],
  ["발전용 요인", "SMP·석탄 가격·산업생산·전력거래량은 평가 구간 개선 없음. 월별 원전·석탄 발전량 자료 확보가 관건"],
  ["기온 시나리오", "평년값 하나만 사용 → 기상청 장기예보·앙상블 시나리오로 확장"],
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
s.addNotes("한계도 말씀드리겠습니다. 전국 용도별 자료가 2016년부터라 평가 기간이 36개월이고 2019년은 복원값입니다. 시도별 판매량은 정의 변경 때문에 2022년까지만 썼고, 주택용이나 산업용 같은 세부 용도는 월별로 공개되지 않습니다. 발전용의 핵심 요인인 원전과 석탄 발전량의 월별 자료를 확보하지 못했고, 기온 시나리오는 평년값 하나만 썼습니다. 이 부분들이 향후 과제입니다.");

// ---------------- 16. 질의응답 ----------------
s = pres.addSlide({ masterName: "TITLE_DARK", sectionTitle: "결론" });
s.addText("감사합니다", { placeholder: "title" });
s.addText("질의응답\n자료·코드·결과: github.com/seoki0804/LNG_D_F (korea/, python/run_all.py 한 번으로 재현)", { placeholder: "body" });
s.addNotes("들어 주셔서 감사합니다. 모든 자료와 코드는 공개 저장소에 있고 한 번의 실행으로 재현할 수 있습니다. 질문 받겠습니다.");

pres.writeFile({ fileName: OUT })
  .then(() => applyTheme(OUT, THEME))
  .then(() => console.log("저장: report/한국_LNG_수요예측_발표.pptx"));
