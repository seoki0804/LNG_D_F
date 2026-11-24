// 한국 연구 학술대회 발표 자료(.pptx) + 발표 스크립트(슬라이드 노트). 수치는 numbers.json에서 읽는다.
// 그림은 python/slide_figures.py가 만든 발표용 그림(outputs/figures/slides)을 쓴다.
// 실행: korea/ 에서  node report/build_deck.js   → report/한국_LNG_수요예측_발표.pptx
const fs = require("fs");
const os = require("os");
const path = require("path");
const pptxgen = require("pptxgenjs");
const { jo, ym } = require("./text_kit");

// 테마 색 적용 도구(pptx 스킬의 apply_theme.js)가 있으면 쓰고, 없으면 Office 기본 테마로 둔다.
function findThemeTool() {
  const rel = path.join("scripts", "apply_theme.js");
  if (process.env.PPTX_SKILL_DIR) return path.join(process.env.PPTX_SKILL_DIR, rel);
  const roots = [path.join(os.homedir(), ".claude", "skills"), path.join(os.homedir(), ".claude", "plugins")];
  const stack = roots.map((r) => [r, 0]);
  while (stack.length) {
    const [dir, depth] = stack.pop();
    if (path.basename(dir) === "pptx" && fs.existsSync(path.join(dir, rel))) return path.join(dir, rel);
    if (depth >= 7 || !fs.existsSync(dir)) continue;
    for (const e of fs.readdirSync(dir, { withFileTypes: true }))
      if (e.isDirectory()) stack.push([path.join(dir, e.name), depth + 1]);
  }
  return null;
}
// 도구가 이 폴더의 pptxgenjs·jszip을 찾을 수 있게 NODE_PATH에 report/node_modules를 더한다.
process.env.NODE_PATH = [path.join(__dirname, "node_modules"), process.env.NODE_PATH].filter(Boolean).join(path.delimiter);
require("module").Module._initPaths();
const THEME_TOOL = findThemeTool();
const applyTheme = THEME_TOOL && fs.existsSync(THEME_TOOL) ? require(THEME_TOOL).applyTheme
  : async () => console.log("테마 도구 없음: Office 기본 테마 색으로 저장 (내용은 같음)");

const ROOT = path.resolve(__dirname, "..");
const SF = (n) => path.join(ROOT, "outputs", "figures", "slides", n);
const FIG = (n) => path.join(ROOT, "outputs", "figures", n);
const N = JSON.parse(fs.readFileSync(path.join(__dirname, "numbers.json"), "utf8"));
const OUT = path.join(__dirname, "한국_LNG_수요예측_발표.pptx");

// ---------------- 디자인 체계 ----------------
// 남색(구조·Ensemble) + 파랑(도시가스용) + 주황(발전용) + 초록(파운데이션 모델). 그림과 같은 색 규칙.
const THEME = {
  name: "LNG Demand",
  headFontFace: "Malgun Gothic", bodyFontFace: "Malgun Gothic",
  colors: { dk1: "1B1B1B", lt1: "FFFFFF", dk2: "16213E", lt2: "F1F3F7", accent1: "2A78D6", accent2: "EB6834",
            accent3: "1BAF7A", accent4: "EDA100", accent5: "8A8F9C", accent6: "C0392B", hlink: "2A78D6", folHlink: "6250D6" },
};
const HEX = { ...THEME.colors, ink2: "4A4F5C", muted: "8A8F9C", rule: "D5D9E2", card: "F1F3F7", navy2: "23305A",
              soft: "C9D3E8", red: "C0392B" };
const W = 13.333, H = 7.5, MX = 0.6, CW = W - 2 * MX;
const SECTIONS = ["연구 배경", "자료와 방법", "결과", "논의와 결론"];

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";
pres.author = "안형석, 양의창, 권기범";
pres.title = "한국 LNG 수요의 용도별·지역별 예측";
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
const C = pres.SchemeColor;

pres.defineSlideMaster({
  title: "TITLE_DARK", background: { color: HEX.dk2 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: MX, y: 2.0, w: 7.6, h: 1.9, fontSize: 40, bold: true,
        color: C.background1, valign: "bottom", align: "left", lineSpacingMultiple: 1.05 }, text: "" } },
    { placeholder: { options: { name: "body", type: "body", x: MX, y: 4.1, w: 7.4, h: 0.9, fontSize: 17,
        color: "C9D3E8", valign: "top", align: "left" }, text: "" } },
  ],
});
pres.defineSlideMaster({
  title: "CONTENT", background: { color: HEX.lt1 },
  margin: [0.5, 0.6, 0.6, 0.6],
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: MX, y: 0.62, w: CW, h: 0.78, fontSize: 24, bold: true,
        color: C.text2, valign: "middle", align: "left" }, text: "" } },
    { text: { text: "한국 LNG 수요의 용도별·지역별 예측", options: { x: MX, y: H - 0.42, w: 6, h: 0.28, fontSize: 10,
        color: HEX.muted, margin: 0 } } },
  ],
  slideNumber: { x: W - MX - 0.6, y: H - 0.42, w: 0.6, h: 0.28, fontSize: 10, color: HEX.muted, align: "right" },
});
pres.defineSlideMaster({
  title: "CONTENT_DARK", background: { color: HEX.dk2 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: MX, y: 0.62, w: CW, h: 0.78, fontSize: 24, bold: true,
        color: C.background1, valign: "middle", align: "left" }, text: "" } },
  ],
  slideNumber: { x: W - MX - 0.6, y: H - 0.42, w: 0.6, h: 0.28, fontSize: 10, color: "9AA6C4", align: "right" },
});

// ---------------- 도우미 ----------------
let s;
function slide(section, title, dark = false) {
  const sec = section === "부록" ? "부록" : section;
  s = pres.addSlide({ masterName: dark ? "CONTENT_DARK" : "CONTENT", sectionTitle: sec });
  const items = section === "부록" ? ["부록"] : SECTIONS;
  const runs = [];
  items.forEach((t, i) => {
    const on = t === section;
    runs.push({ text: t, options: { bold: on, color: on ? (dark ? "FFFFFF" : HEX.dk2) : (dark ? "6F7C9C" : "A3A9B5") } });
    if (i < items.length - 1) runs.push({ text: "   ›   ", options: { color: dark ? "4B587A" : "C5CAD3" } });
  });
  s.addText(runs, { x: MX, y: 0.28, w: CW, h: 0.3, fontSize: 11, margin: 0, isTextBox: true, objectName: "section tracker" });
  s.addText(title, { placeholder: "title" });
  return s;
}
function pngSize(file) { const b = fs.readFileSync(file); return { w: b.readUInt32BE(16), h: b.readUInt32BE(20) }; }
function figure(file, box, name, align = "center") {
  const { w, h } = pngSize(file);
  let iw = box.w, ih = iw * h / w;
  if (ih > box.h) { ih = box.h; iw = ih * w / h; }
  const x = align === "left" ? box.x : box.x + (box.w - iw) / 2;
  s.addImage({ path: file, x, y: box.y + (box.h - ih) / 2, w: iw, h: ih, altText: name, objectName: name });
}
function text(t, box, o = {}) {
  s.addText(t, { ...box, fontSize: 15, color: C.text1, valign: "top", margin: 0, isTextBox: true, ...o });
}
function bullets(items, box, size = 15, color = null) {
  s.addText(items.map((t, i) => ({ text: t, options: { bullet: { indent: 16 }, breakLine: i < items.length - 1 } })),
    { ...box, fontSize: size, color: color || C.text1, valign: "top", paraSpaceAfter: 7, margin: 0, isTextBox: true,
      objectName: "bullets" });
}
function card(x, y, w, h, fill = HEX.card, name = "card") {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.07, fill: { color: fill },
    line: { color: fill, width: 0.5 }, objectName: name });
}
// 큰 수치 카드: value(큰 글씨) + label(굵게) + desc(설명)
function stat(value, label, x, y, w, h, color, desc = "", o = {}) {
  card(x, y, w, h, o.fill || HEX.card, `stat ${label}`);
  const dark = !!o.fill && o.fill !== HEX.card;
  s.addText(value, { x: x + 0.22, y: y + 0.14, w: w - 0.44, h: 0.62, fontSize: o.vsize || 28, bold: true, color,
    margin: 0, valign: "middle", isTextBox: true, objectName: `value ${label}` });
  s.addText(label, { x: x + 0.22, y: y + 0.8, w: w - 0.44, h: 0.5, fontSize: 13, bold: true,
    color: dark ? "FFFFFF" : HEX.dk2, margin: 0, valign: "top", isTextBox: true, objectName: `label ${label}` });
  if (desc) s.addText(desc, { x: x + 0.22, y: y + 1.28, w: w - 0.44, h: h - 1.38, fontSize: o.dsize || 12, color: dark ? "D6DCEA" : HEX.ink2,
    margin: 0, valign: "top", isTextBox: true, objectName: `desc ${label}` });
}
function badge(n, x, y, color = HEX.dk2, d = 0.46, fs_ = 15) {
  s.addShape(pres.shapes.OVAL, { x, y, w: d, h: d, fill: { color }, line: { color, width: 0.5 }, objectName: `badge ${n}` });
  s.addText(String(n), { x, y, w: d, h: d, fontSize: fs_, bold: true, color: "FFFFFF", align: "center", valign: "middle",
    margin: 0, isTextBox: true, objectName: `badge text ${n}` });
}
function note(t, y = 6.68) {
  s.addText(t, { x: MX, y, w: CW, h: 0.3, fontSize: 10.5, color: HEX.muted, margin: 0, valign: "top", isTextBox: true,
    objectName: "source note" });
}
const TH = (t, o = {}) => ({ text: t, options: { bold: true, color: HEX.dk2, fill: { color: HEX.card }, valign: "middle", ...o } });
function table(rows, box, colW, o = {}) {
  const body = rows.map((r, i) => i === 0 ? r.map((c) => (typeof c === "string" ? TH(c, { align: o.headAlign || "left" }) : c))
    : r.map((c, j) => (typeof c === "string" ? { text: c, options: { align: (o.center || []).includes(j) ? "center" : "left",
        valign: "middle", bold: j === 0 && o.firstBold } } : c)));
  s.addTable(body, { ...box, colW, fontSize: o.size || 13, color: HEX.dk1, rowH: o.rowH, margin: o.margin || [3, 6, 3, 6],
    border: { type: "solid", pt: 0.75, color: HEX.rule }, autoPage: false, objectName: o.name || "table" });
}

// ---------------- 수치 도우미 ----------------
const f0 = (x) => Number(x).toFixed(0), f1 = (x) => Number(x).toFixed(1), f2 = (x) => Number(x).toFixed(2);
const comma = (x) => Math.round(x).toLocaleString("en-US");
const pv = (x) => (x < 0.001 ? "p < 0.001" : `p = ${x.toFixed(3)}`);
const NM = { "계절 naive": "Seasonal Naive", "회귀 √Y": "OLS(√Y)", SARIMAX: "SARIMAX", ETS: "ETS", Ridge: "Ridge",
  LightGBM: "LightGBM", "하이브리드 (회귀+Ridge)": "Hybrid(OLS+Ridge)", "하이브리드 (회귀+LightGBM)": "Hybrid(OLS+LightGBM)",
  "Chronos-2": "Chronos-2", "Chronos-2 + 공변량": "Chronos-2(공변량)", "TimesFM 2.5": "TimesFM 2.5", 앙상블: "Ensemble" };
const MODELS = Object.keys(NM);
const nm = (m) => NM[m] || m;
const nat = (sr, m, k = "all", i = "ex_ante", w = "eval") => (N.nat[`${sr}|${m}|${i}|${w}`] || {})[k];
const ranked = (sr, k = "all", i = "ex_ante", w = "eval") =>
  MODELS.map((m) => [m, nat(sr, m, k, i, w)]).filter((x) => x[1] != null).sort((a, b) => a[1] - b[1]);
const best = (sr, k = "all", i = "ex_ante", w = "eval") => ranked(sr, k, i, w)[0];
const mcs = (sr, h = "all", i = "ex_ante") => N.mcs[`${sr}|${i}|${h}`] || [];
const prov = (m, me, lv) => (N.prov[`${m}|${me}|${lv}`] || {}).all;
const share = (sr, m) => N.weather_share[`${sr}|${m}`];
const met = (sr, m, k, w = "eval") => ((N.metrics || {})[`${sr}|${m}|ex_ante|${w}`] || {})[k];
const itv = (sr, m, me) => (N.intervals || {})[`${sr}|${m}|${me}`] || {};
const fr = (sr) => (N.friedman || {})[`${sr}|ex_ante`] || {};
const shp = (sr, f) => (N.shap || {})[`${sr}|${f}`];
const em = (sr, i, w, c, k = "bias", m = "앙상블") => ((N.err_month || {})[`${sr}|${m}|${i}|${w}|${c}`] || {})[k];
const su = (y, c, k) => ((N.summer || {})[`${y}|${c}`] || {})[k];
const abl = (v, sr, w = "eval") => (N.ablation || {})[`${v}|${sr}|ex_ante|${w}`];
const nearEns = (k) => MODELS.filter((m) => m !== "앙상블" && met(k, m, "rank") - met(k, "앙상블", "rank") < fr(k).CD);
const R = N.reg, D = N.data, PS = N.province_sens_range, SIX = N.six || {};
const ensC = nat("city", "앙상블"), ensP = nat("power", "앙상블"), ensT = nat("total", "앙상블");
const nModels = MODELS.filter((m) => nat("city", m) != null).length;
const holdRank = (k) => ranked(k, "all", "ex_ante", "hold");
const summerBias = (em("power", "ex_ante", "hold", 7) + em("power", "ex_ante", "hold", 8)) / 2;
const yoy = (c) => (su(2026, c, "power") / su(2025, c, "power") - 1) * 100;

// ================= 1. 표지 =================
pres.addSection({ title: "연구 배경" });
s = pres.addSlide({ masterName: "TITLE_DARK", sectionTitle: "연구 배경" });
s.addImage({ path: SF("s_title.png"), x: 6.1, y: 2.9, w: 7.0, h: 3.6, transparency: 35, altText: "decorative demand lines",
  objectName: "title lines" });
s.addText("수요예측 수업 최종 발표", { x: MX, y: 1.45, w: 6, h: 0.4, fontSize: 14, color: "9EC5F4", bold: true, margin: 0,
  isTextBox: true, objectName: "kicker" });
s.addText("한국 LNG 수요의\n용도별·지역별 예측", { placeholder: "title" });
s.addText("회귀분석, 기계학습, 시계열 파운데이션 모델의\n1~12개월 앞 예측 비교", { placeholder: "body" });
s.addText([{ text: "안형석 · 양의창 · 권기범", options: { bold: true, breakLine: true } }, { text: "2026년 11월" }],
  { x: MX, y: 5.55, w: 6, h: 0.8, fontSize: 15, color: "FFFFFF", margin: 0, isTextBox: true, objectName: "authors" });
s.addNotes("안녕하십니까. 한국의 천연가스 수요를 도시가스용과 발전용으로 나누고, 17개 시도까지 내려가 1개월에서 12개월 앞을 예측한 연구를 발표하겠습니다. 회귀분석, 기계학습, 그리고 최근 나온 시계열 파운데이션 모델을 같은 조건에서 비교했습니다.");

// ================= 2. 연구 요약 =================
slide("연구 배경", "연구 요약: 용도마다 예측 오차의 원인이 다르다");
const sumCards = [
  [`${f1(ensC)}% · ${f1(ensP)}%`, "1~12개월 앞 평균 오차 (MAPE)", `도시가스용 · 발전용, Ensemble 기준. 발전용 오차가 약 2배다.`, HEX.dk2],
  [`${f0(share("city", "앙상블"))}% · ${f0(share("power", "앙상블"))}%`, "실제 기온을 알 때 줄어드는 오차",
    "도시가스용 오차의 상당 부분은 기온 불확실성에서 오지만, 발전용은 그렇지 않다.", HEX.accent1],
  [`${mcs("city").length} · ${mcs("power").length} / ${nModels}`, "최고 모델과 통계적으로 구별되지 않는 모델 수",
    "Ensemble이 평균 1위지만, 36개월 평가로는 상위 모델 간 차이를 가릴 수 없다 (MCS 90%).", HEX.ink2],
  [`${f0(summerBias)}%`, "2026년 7~8월 발전용 예측 오차", "실제 수요가 전년보다 38~46% 늘었지만 기온으로는 설명되지 않아, 모든 모델이 낮게 예측했다.", HEX.red],
];
sumCards.forEach(([v, l, d, c], i) => {
  const x = MX + (i % 2) * (CW / 2 + 0.1), y = 1.6 + Math.floor(i / 2) * 2.5;
  stat(v, l, x, y, CW / 2 - 0.1, 2.3, c, d, { vsize: 34, dsize: 14.5 });
});
s.addNotes(`먼저 결과를 요약하겠습니다. 미리 정한 Ensemble 기준으로 1~12개월 앞 평균 오차율은 도시가스용 ${f1(ensC)}%, 발전용 ${f1(ensP)}%로, 발전용이 약 두 배 어렵습니다. 실제 기온을 미리 안다고 가정하면 도시가스용 오차는 ${f0(share("city", "앙상블"))}% 줄지만 발전용은 ${f0(share("power", "앙상블"))}%만 줄어, 두 용도의 오차 원인이 다릅니다. 모델 비교에서는 Ensemble이 평균 1위였지만 상위 모델 사이의 차이는 통계적으로 유의하지 않았습니다. 그리고 2026년 표본 외 검증에서 발전용 7~8월 수요가 크게 늘었는데, 기온으로 설명되지 않아 모든 모델이 약 30% 낮게 예측했습니다.`);

// ================= 3. 배경 =================
slide("연구 배경", "도시가스용은 겨울에 몰리고, 발전용은 계절 진폭이 작다");
figure(SF("s_demand.png"), { x: MX, y: 1.5, w: 8.1, h: 4.95 }, "monthly demand by use", "left");
stat(`${comma(D.city_2025 * 100)}만 톤`, `2025년 도시가스용 (전체의 ${f0(D.city_share_2025)}%)`, 9.0, 1.6, 3.73, 1.32, HEX.accent1);
stat(`${comma(D.power_2025 * 100)}만 톤`, "2025년 발전용", 9.0, 3.08, 3.73, 1.32, HEX.accent2);
bullets(["천연가스를 거의 전량 LNG로 수입", "도입 계약·수송 일정은 몇 달 앞에 정해짐", "그래서 1~12개월 앞의 월별 예측이 필요"],
  { x: 9.0, y: 4.65, w: 3.73, h: 1.8 }, 14);
note(`최대월/최소월 비율(연평균): 도시가스용 ${f1(D.city_peak_ratio)}배, 발전용 ${f1(D.power_peak_ratio)}배 · 자료: 한국가스공사 용도별 월 공급량, 2016.01~2026.09`);
s.addNotes(`한국은 천연가스를 거의 모두 LNG로 수입하기 때문에, 도입 계약과 수송 일정을 몇 달 앞을 보고 정해야 합니다. 그림은 용도별 월 공급량입니다. 파란 선의 도시가스용은 겨울 난방 때문에 최대월이 최소월의 ${f1(D.city_peak_ratio)}배에 이르고, 주황 선의 발전용은 여름과 겨울 두 번 오르지만 진폭은 ${f1(D.power_peak_ratio)}배로 작습니다. 2025년 공급량은 도시가스용이 약 ${comma(D.city_2025 * 100)}만 톤, 발전용이 약 ${comma(D.power_2025 * 100)}만 톤이었습니다. 음영은 뒤에서 설명할 평가 구간과 표본 외 구간입니다.`);

// ================= 4. 선행연구 =================
slide("연구 배경", "선행연구와 이 연구의 범위");
table([
  ["주제", "선행연구", "이 연구"],
  ["기온과 가스 수요", "난방도일(HDD) 회귀가 표준 방법 (Sarak & Satman, 2003; Soldo, 2012)", "용도별·시도별 민감도 추정, 회귀 가정(이분산·자기상관) 진단"],
  ["국내 도시가스 예측", "일별 단기 예측 (이근철·한정희, 2015; 최용옥·박혜성, 2020), 수도권·지방 지역 모형 (이성로, 2017)", "발전용까지 포함한 1~12개월 앞 월별 예측, 17개 시도 계층 예측"],
  ["통계·기계학습 비교", "적합한 모형은 예측 기간과 자료에 따라 다름 (Liu et al., 2021; Tian et al., 2023)", "12개 모델을 같은 롤링 평가와 유의성 검정(DM·MCS)으로 비교"],
  ["시계열 파운데이션 모델", "대규모 사전학습으로 추가 학습 없이 예측 (Ansari et al., 2024; Das et al., 2024)", "작은 월별 에너지 자료에서 정확도와 예측구간을 검증"],
  ["예측 결합·계층 조정", "단순 평균 결합의 안정성 (Bates & Granger, 1969; Wang et al., 2023), MinT (Wickramasuriya et al., 2019)", "미리 정한 Ensemble, 시도 → 전국 조정을 한국 자료에 적용"],
], { x: MX, y: 1.6, w: CW }, [2.45, 5.35, 4.33], { size: 13.5, rowH: [0.46, 0.86, 0.86, 0.86, 0.86, 0.86], firstBold: true });
s.addNotes("선행연구와 이 연구의 위치입니다. 가스 수요와 기온의 관계는 난방도일 회귀가 표준적인 방법입니다. 국내 연구는 주로 일별 단기 예측이었고, 이성로(2017)는 수도권과 지방을 나눈 지역 모형이 전국 예측을 개선한다고 보고했습니다. 기계학습 비교 연구들은 적합한 모형이 예측 기간과 자료에 따라 달라진다고 정리합니다. 최근에는 대규모 시계열로 사전학습해 추가 학습 없이 예측하는 파운데이션 모델이 나왔는데, 작은 월별 에너지 자료에서의 검증은 아직 드뭅니다. 이 연구는 발전용까지 포함해 1~12개월 앞을 예측하고, 이 모델들을 같은 평가 틀에서 비교했습니다.");

// ================= 5. 연구 질문과 기여 =================
slide("연구 배경", "연구 질문과 기여");
const rqs = ["도시가스용·발전용 수요는 무엇으로 설명되는가?", "시도마다 난방 민감도는 얼마나 다르고, 변했는가?",
  "1~12개월 앞에서 어떤 모델이 정확한가?", "기온을 미리 알면 오차가 얼마나 줄어드는가?", "시도 예측을 합치면 전국 예측이 나아지는가?"];
rqs.forEach((t, i) => {
  const y = 1.7 + i * 0.95;
  badge(i + 1, MX, y, HEX.dk2, 0.5, 16);
  text(t, { x: MX + 0.7, y: y - 0.02, w: 6.4, h: 0.55 }, { fontSize: 17, valign: "middle", objectName: `rq ${i + 1}` });
});
card(8.0, 1.6, W - MX - 8.0, 4.85, HEX.dk2, "contribution card");
s.addText("기여", { x: 8.3, y: 1.8, w: 4.1, h: 0.45, fontSize: 18, bold: true, color: "FFFFFF", margin: 0, isTextBox: true,
  objectName: "contrib head" });
["공개 통계만으로 용도·지역별 1~12개월 앞 예측 체계를 구성하고, 원자료의 오류를 찾아 보정했다.",
 "통계·기계학습·파운데이션 모델 12개를 같은 롤링 평가와 유의성 검정으로 비교했다.",
 "사전·사후예측을 비교해 예측 오차 가운데 기온 불확실성의 몫을 분리했다."].forEach((t, i) => {
  const y = 2.45 + i * 1.3;
  badge(i + 1, 8.3, y + 0.02, HEX.accent1, 0.4, 13);
  s.addText(t, { x: 8.85, y, w: 3.65, h: 1.15, fontSize: 14, color: "E6EAF2", margin: 0, valign: "top", isTextBox: true,
    objectName: `contrib ${i + 1}` });
});
s.addNotes("연구 질문은 다섯 가지입니다. 두 용도의 수요는 무엇으로 설명되는지, 시도마다 기온에 대한 반응이 얼마나 다른지, 1~12개월 앞에서 어떤 모델이 정확한지, 기온을 미리 알면 오차가 얼마나 줄어드는지, 그리고 시도 예측을 합치면 전국 예측이 나아지는지입니다. 기여는 세 가지로 정리했습니다. 공개 자료만으로 예측 체계를 만들면서 원자료 오류를 찾아 고쳤고, 성격이 다른 12개 모델을 같은 절차로 비교했으며, 오차 가운데 기온 때문에 생기는 부분을 따로 측정했습니다.");

// ================= 6. 자료 =================
pres.addSection({ title: "자료와 방법" });
slide("자료와 방법", "자료: 공개 통계로 구성한 월별 자료");
table([
  ["자료", "출처", "기간", "쓰임"],
  ["용도별 월 공급량 (도시가스용·발전용)", "한국가스공사", "2016.01~2026.09", "전국 예측·회귀"],
  ["시도별 도시가스 판매량 (17개 시도)", "한국가스공사", "1989.01~2022.12", "지역 예측·회귀"],
  ["일평균기온 (시도 대표 관측소 25곳)", "기상청 ASOS", "1989.01~2026.10", "HDD·CDD·평년값"],
  ["도시가스 소비자물가, 광공업생산지수", "통계청 KOSIS", "1989~2026", "요금·산업"],
  ["월별 전력거래량", "KOSIS (전력거래소)", "2001~2025", "발전용 회귀"],
  ["아시아 LNG 가격", "FRED", "1992~2026", "발전용 회귀"],
], { x: MX, y: 1.6, w: 7.75 }, [3.35, 1.6, 1.55, 1.25], { size: 12.5, rowH: 0.52 });
card(8.65, 1.6, W - MX - 8.65, 4.85, HEX.card, "weather index card");
s.addText("기온 지표", { x: 8.9, y: 1.78, w: 3.6, h: 0.4, fontSize: 16, bold: true, color: HEX.dk2, margin: 0, isTextBox: true,
  objectName: "weather head" });
const defs = [["난방도일 (HDD)", "일평균기온 15°C 이하인 날의 (18 − 기온)을 월별로 합함"],
  ["냉방도일 (CDD)", "24°C 이상인 날의 (기온 − 21)을 합함"],
  ["수요가중 전국 HDD", "시도 HDD를 2016~2018년 시도 판매 비중으로 가중"],
  ["평년값", "직전 10년 같은 달 평균. 사전예측의 미래 기온으로 사용"]];
defs.forEach(([h_, t], i) => {
  const y = 2.32 + i * 1.02;
  s.addText([{ text: h_, options: { bold: true, color: HEX.dk2, breakLine: true } }, { text: t, options: { color: HEX.ink2 } }],
    { x: 8.9, y, w: 3.65, h: 0.95, fontSize: 13, margin: 0, valign: "top", isTextBox: true, objectName: `def ${i + 1}` });
});
note("자료 수집일 2026년 11월 21일 · 공공데이터포털(한국가스공사), 기상청 ASOS 일자료, 통계청 KOSIS, FRED");
s.addNotes("자료는 모두 공개 통계입니다. 전국 수요는 가스공사의 용도별 월 공급량으로 2016년부터 2026년 9월까지이고, 지역 수요는 시도별 도시가스 판매량입니다. 기온은 기상청 관측소 25곳의 일평균기온으로 난방도일과 냉방도일을 만들었습니다. 난방도일은 기온이 낮을수록 커지는 지표라 난방 수요와 같은 방향으로 움직입니다. 전국 값은 시도별 판매 비중으로 가중했고, 실제 예측에서는 미래 기온을 모르므로 직전 10년 같은 달의 평균, 즉 평년값을 넣었습니다.");

// ================= 7. 자료 점검 =================
slide("자료와 방법", "자료 점검: 오류 1건을 복원하고, 정의가 다른 자료 2건은 제외했다");
figure(SF("s_fix2019.png"), { x: MX, y: 1.6, w: 5.8, h: 3.45 }, "2019 city gas fix", "left");
text(`2019년 도시가스용 월 공급량. 원자료는 7월이 ${comma(D.fix2019.before)}천 톤으로 다른 해의 약 2배여서, 같은 기관의 지역본부 공급량으로 복원했다(${comma(D.fix2019.after)}천 톤).`,
  { x: MX, y: 5.15, w: 5.8, h: 1.2 }, { fontSize: 12.5, color: HEX.ink2 });
const fixes = [["1", "2019년 도시가스용 값 오류 → 복원", "계절 형태가 다른 해와 어긋남. 지역본부 공급량 합계를 '지역본부 합계 ÷ 전국' 비율로 나눠 복원"],
  ["2", "시도 판매량 정의 변경 → 2022년까지만 사용", "2023년 1월부터 모든 시도가 약 25% 낮아졌으나 전국 공급량은 그대로였음"],
  ["3", "지역본부 발전용 공급량 → 사용하지 않음", "전국 값과 정의가 맞지 않아 지역 × 용도 분석에서 제외"]];
fixes.forEach(([n, h_, t], i) => {
  const y = 1.6 + i * 1.62;
  card(6.75, y, W - MX - 6.75, 1.45, HEX.card, `fix ${n}`);
  badge(n, 6.98, y + 0.22, i === 0 ? HEX.accent1 : HEX.muted, 0.42, 13);
  s.addText(h_, { x: 7.6, y: y + 0.18, w: 5.0, h: 0.45, fontSize: 15, bold: true, color: HEX.dk2, margin: 0, valign: "middle",
    isTextBox: true, objectName: `fix head ${n}` });
  s.addText(t, { x: 7.6, y: y + 0.66, w: 5.0, h: 0.72, fontSize: 12.5, color: HEX.ink2, margin: 0, valign: "top",
    isTextBox: true, objectName: `fix text ${n}` });
});
s.addNotes(`자료를 점검하다 세 가지 문제를 찾았습니다. 첫째, 전국 자료의 2019년 도시가스용 값은 7월이 ${comma(D.fix2019.before)}천 톤으로 다른 해의 두 배였고 계절 형태도 어긋나 있었습니다. 같은 기관의 지역본부별 공급량은 정상이어서 이를 이용해 복원했고, 그림의 파란 선이 복원값입니다. 둘째, 시도별 판매량은 2023년 1월부터 모든 시도가 함께 약 25% 낮아지는데 전국 공급량은 그대로여서 정의가 바뀐 것으로 보고 2022년까지만 썼습니다. 셋째, 지역본부별 발전용은 전국 값과 정의가 맞지 않아 쓰지 않았습니다.`);

// ================= 8. 예측 모델 =================
slide("자료와 방법", "예측 모델: 네 계열 12개 모델을 같은 조건에서 비교");
const fams = [
  ["통계 모형", HEX.muted, "기온·달력 변수와 과거 수요의 관계를 식으로 추정", ["Seasonal Naive (기준)", "OLS(√Y)", "SARIMAX", "ETS"],
    "Seasonal Naive = 작년 같은 달 값"],
  ["기계학습", HEX.muted, "예측 시계 h를 입력에 넣어 1~12개월 앞을 한 모델로 학습", ["Ridge", "LightGBM", "Hybrid(OLS+Ridge)", "Hybrid(OLS+LightGBM)"],
    "Hybrid = 회귀 예측의 오차를 기계학습이 보정"],
  ["파운데이션 모델", HEX.accent3, "대규모 시계열로 사전학습한 모델을 추가 학습 없이 사용", ["Chronos-2 (단변량)", "Chronos-2 (공변량)", "TimesFM 2.5"],
    "공변량 = 기온·달력·요금을 함께 입력"],
  ["Ensemble", HEX.dk2, "평가 전에 정한 4개 모델의 단순 평균", ["OLS(√Y)", "SARIMAX", "LightGBM", "Chronos-2 (공변량)"],
    "구성은 평가 결과를 보고 바꾸지 않음"],
];
const fw = (CW - 3 * 0.2) / 4;
fams.forEach(([h_, col, t, list, foot], i) => {
  const x = MX + i * (fw + 0.2), y = 1.6, hh = 3.9;
  card(x, y, fw, hh, HEX.card, `family ${i + 1}`);
  badge(i + 1, x + 0.22, y + 0.24, col, 0.46, 15);
  s.addText(h_, { x: x + 0.8, y: y + 0.24, w: fw - 0.95, h: 0.46, fontSize: 17, bold: true, color: HEX.dk2, margin: 0,
    valign: "middle", isTextBox: true, objectName: `family head ${i + 1}` });
  s.addText(t, { x: x + 0.22, y: y + 0.88, w: fw - 0.44, h: 0.95, fontSize: 13, color: HEX.ink2, margin: 0, valign: "top",
    isTextBox: true, objectName: `family text ${i + 1}` });
  s.addText(list.map((m, k) => ({ text: m, options: { bullet: { indent: 14 }, breakLine: k < list.length - 1 } })),
    { x: x + 0.22, y: y + 1.85, w: fw - 0.44, h: 1.3, fontSize: 14, bold: true, color: HEX.dk1, margin: 0, valign: "top",
      paraSpaceAfter: 6, isTextBox: true, objectName: `family list ${i + 1}` });
  s.addText(foot, { x: x + 0.22, y: y + 3.2, w: fw - 0.44, h: 0.6, fontSize: 11.5, color: HEX.muted, margin: 0, valign: "top",
    isTextBox: true, objectName: `family foot ${i + 1}` });
});
card(MX, 5.7, CW, 0.82, HEX.dk2, "input band");
s.addText([{ text: "공통 입력   ", options: { bold: true, color: "9EC5F4" } },
  { text: "과거 수요 · 목표월 HDD·CDD (사전예측은 평년값, 사후예측은 실제값) · 영업일·명절 · 도시가스 요금 지수 · 석탄 상한제 기간", options: { color: "FFFFFF" } }],
  { x: MX + 0.3, y: 5.7, w: CW - 0.6, h: 0.82, fontSize: 14, margin: 0, valign: "middle", isTextBox: true, objectName: "input text" });
note("하이퍼파라미터·차수·변수 구성은 검증 구간(목표월 2020~2022년)에서만 선택 · 결과 그림의 색: Ensemble 남색, 파운데이션 모델 초록, 나머지 회색");
s.addNotes("비교한 모델은 네 계열 12개입니다. 통계 모형은 작년 같은 달 값을 그대로 쓰는 Seasonal Naive를 기준으로, 제곱근 변환 회귀, SARIMAX, 지수평활을 썼습니다. 기계학습은 예측 시계를 입력으로 넣어 1~12개월 앞을 한 모델로 학습했고, 회귀 예측의 오차를 기계학습이 보정하는 Hybrid도 넣었습니다. 파운데이션 모델은 대규모 시계열로 미리 학습된 Chronos-2와 TimesFM을 추가 학습 없이 썼습니다. 마지막으로 서로 다른 원리의 네 모델을 평가 전에 골라 단순 평균한 것이 Ensemble입니다.");

// ================= 9. 평가 설계 =================
slide("자료와 방법", "평가 설계: 매달 다시 학습해 1~12개월 앞을 예측한다");
{
  const x0 = MX + 0.3, x1 = W - MX - 0.3, yr = (t) => x0 + (t - 2016) / 11 * (x1 - x0);
  const by = 2.75, bh = 0.55;
  const segs = [[2016, 2020, "초기 학습", "E3E6ED", HEX.dk2], [2020, 2023, "검증 (설정 선택)", "CDE2FB", HEX.dk2],
    [2023, 2026, "평가 (목표월 36개월)", HEX.accent1, "FFFFFF"], [2026, 2026.75, "표본 외", HEX.dk2, "FFFFFF"]];
  segs.forEach(([a, b, lab, fill, tc], i) => {
    s.addShape(pres.shapes.RECTANGLE, { x: yr(a), y: by, w: yr(b) - yr(a) - 0.03, h: bh, fill: { color: fill },
      line: { color: fill, width: 0.5 }, objectName: `seg ${i}` });
    s.addText(lab, { x: yr(a), y: by, w: yr(b) - yr(a) - 0.03, h: bh, fontSize: i === 3 ? 11 : 13, bold: true, color: tc,
      align: "center", valign: "middle", margin: 0, isTextBox: true, objectName: `seg label ${i}` });
  });
  for (let t = 2016; t <= 2027; t++)
    s.addText(String(t), { x: yr(t) - 0.35, y: by + bh + 0.05, w: 0.7, h: 0.3, fontSize: 11, color: HEX.muted, align: "center",
      margin: 0, isTextBox: true, objectName: `year ${t}` });
  // 예측 시점 예시 (롤링)
  [[2022.0, 1.65], [2022.5, 2.05], [2024.2, 1.65]].forEach(([t, y], i) => {
    s.addShape(pres.shapes.OVAL, { x: yr(t) - 0.07, y: y - 0.07, w: 0.14, h: 0.14, fill: { color: HEX.dk2 },
      line: { color: HEX.dk2 }, objectName: `origin ${i}` });
    s.addShape(pres.shapes.LINE, { x: yr(t) + 0.08, y, w: yr(t + 1) - yr(t) - 0.08, h: 0, line: { color: HEX.dk2, width: 1.5,
      endArrowType: "triangle" }, objectName: `arrow ${i}` });
  });
  s.addText("예측 시점 T → T+1 … T+12", { x: yr(2022.0) - 3.15, y: 1.5, w: 3.0, h: 0.3, fontSize: 12, color: HEX.dk2,
    align: "right", margin: 0, isTextBox: true, objectName: "origin label" });
}
const evs = [["롤링 원점 예측", `예측 시점마다 그때까지의 자료로 다시 추정한다. 목표월이 2023~2025년인 예측만 모아, 1개월 앞과 12개월 앞을 같은 36개월로 비교한다.`],
  ["사전예측 vs 사후예측", "사전예측은 미래 기온에 평년값을 넣는다(실제 운영과 같음). 사후예측은 실제 기온을 넣는다. 둘의 차이가 기온 정보의 가치다."],
  ["누수 점검", `예측 시점 이후의 수요·기온·가격을 10배로 바꿔도 사전예측이 그대로인지 자동으로 확인했다 (${N.leakage ? `${N.leakage.n}건 모두 통과` : ""}).`]];
evs.forEach(([h_, t], i) => {
  const x = MX + i * (CW / 3 + 0.05), w = CW / 3 - 0.1, y = 4.0;
  card(x, y, w, 2.3, HEX.card, `eval card ${i + 1}`);
  s.addText(h_, { x: x + 0.22, y: y + 0.18, w: w - 0.44, h: 0.42, fontSize: 15, bold: true, color: HEX.dk2, margin: 0,
    valign: "middle", isTextBox: true, objectName: `eval head ${i + 1}` });
  s.addText(t, { x: x + 0.22, y: y + 0.7, w: w - 0.44, h: 1.5, fontSize: 14, color: HEX.ink2, margin: 0, valign: "top",
    isTextBox: true, objectName: `eval text ${i + 1}` });
});
s.addNotes("평가 방법입니다. 위의 시간축처럼 2016~2019년으로 처음 학습하고, 2020~2022년 검증 구간에서 모든 설정을 고른 뒤, 2023~2025년을 평가 구간으로 썼습니다. 예측 시점을 한 달씩 옮기면서 그때까지의 자료로 모델을 다시 추정하고 다음 12개월을 예측합니다. 목표월이 평가 구간에 드는 예측만 모아서, 1개월 앞이든 12개월 앞이든 같은 36개월로 비교했습니다. 실제 운영처럼 미래 기온 자리에 평년값을 넣는 사전예측이 기본이고, 실제 기온을 넣는 사후예측과 비교해 기온 정보의 가치를 측정했습니다. 미래 정보가 새어 들어가지 않았는지는 자동 점검으로 확인했습니다.");

// ================= 10. 평가 지표 =================
slide("자료와 방법", "평가 지표와 검정: 정확도, 유의성, 불확실성을 함께 본다");
table([
  ["구분", "지표·검정", "무엇을 보는가"],
  ["점예측 정확도", "MAPE (주 지표), MAE, RMSE, sMAPE", "예측 오차의 크기. MAPE에는 목표월 블록 부트스트랩 95% 신뢰구간"],
  ["척도 없는 비교", "MASE, Seasonal Naive 대비 상대 MAE", "작년 같은 달을 쓰는 예측보다 얼마나 나은가 (1 미만이면 더 정확)"],
  ["통계적 유의성", "Diebold-Mariano 검정, 모델 신뢰집합 (MCS 90%)", "최고 모델과 유의하게 다른가, 구별되지 않는 모델은 몇 개인가"],
  ["순위 비교", "평균 순위, Friedman 검정과 Nemenyi 임계차", "432개 (목표월, 시계) 조합마다 매긴 오차 순위의 평균"],
  ["불확실성", "80% 예측구간의 적중률과 구간 점수", "구간이 실제값을 명목 수준(80%)만큼 포함하는가"],
  ["강건성·해석", "연도별 순위 일치도 (Kendall W), Ensemble 구성 변경, SHAP", "결과가 해마다 유지되는가, 모델이 무엇을 근거로 예측했는가"],
], { x: MX, y: 1.6, w: CW }, [2.4, 4.6, 5.13], { size: 13.5, rowH: [0.46, 0.7, 0.7, 0.7, 0.7, 0.7, 0.7], firstBold: true });
s.addNotes("평가 지표입니다. 주 지표는 실제값 대비 오차율인 MAPE이고, 다른 연구와 비교할 수 있도록 MAE, RMSE, MASE 같은 지표도 함께 계산했습니다. 순위가 우연인지 보기 위해 Diebold-Mariano 검정과 모델 신뢰집합, 평균 순위 검정을 썼습니다. 수급계획에는 예측값과 함께 불확실성의 범위가 필요하므로 80% 예측구간이 실제로 80%를 맞추는지도 보았고, 결과가 해마다 유지되는지와 모델이 무엇을 근거로 예측했는지도 확인했습니다.");

// ================= 11. 기온과 수요 =================
pres.addSection({ title: "결과" });
slide("결과", `도시가스용은 HDD로 ${f1(R.r2_simple * 100)}%가 설명되지만, 발전용은 ${f0(R.r2_power_weather * 100)}%에 그친다`);
figure(SF("s_weather_scatter.png"), { x: MX, y: 1.5, w: CW, h: 4.95 }, "demand vs weather");
note("도시가스용: √Y ~ HDD 단순회귀 (2016~2025년 월별) · 발전용: HDD·CDD 회귀 · 빈 원(2026년 7~8월)은 추정에 쓰지 않은 표본 외 자료");
s.addNotes(`왼쪽은 도시가스용 수요와 수요가중 난방도일의 관계입니다. 점들이 거의 한 곡선 위에 있어 난방도일 하나로 변동의 ${f1(R.r2_simple * 100)}%가 설명됩니다. 오른쪽은 발전용 수요와 월평균 기온인데, 겨울과 여름에 모두 높은 U자 모양이지만 흩어짐이 큽니다. 난방도일과 냉방도일을 함께 넣어도 설명력은 ${f0(R.r2_power_weather * 100)}%입니다. 빈 원으로 표시한 2026년 7~8월은 기온이 평소 여름과 비슷한데도 수요가 훨씬 높았는데, 이 점은 뒤의 표본 외 검증에서 다시 보겠습니다.`);

// ================= 12. 회귀 진단 =================
slide("결과", "회귀 가정 점검: 이분산과 자기상관을 보정해 추론했다");
const rc = [[`λ = ${f2(R.boxcox)}`, "Box-Cox 최적 변환", `원 척도의 이분산(BP ${pv(R.bp_y)}) → √Y로 해소 (BP ${pv(R.bp_sqrt)})`, HEX.accent1],
  [`DW ${f2(R.dw_sqrt)}`, "잔차 자기상관", `Newey-West(HAC) 표준오차가 OLS의 ${f1(R.b1_se_hac / R.b1_se)}배 → 추론은 HAC로`, HEX.accent1],
  [R.break2_date.replace("-", "."), "관계 변화 시점 (sup-F)", "2020~2025년 자료 기준. 2022년 도시가스 요금 인상기와 겹침", HEX.accent1],
  [`${f2(R.price_elast)}`, "요금 탄력성 (평균 수준)", `다중회귀 R² ${f2(R.r2_city_multi)}, VIF 모두 3 미만`, HEX.accent1]];
rc.forEach(([v, l, d], i) => stat(v, l, MX + i * (CW / 4 + 0.03), 1.6, CW / 4 - 0.09, 2.15, HEX.accent1, d));
card(MX, 4.0, CW / 2 - 0.1, 2.45, HEX.card, "city box");
card(MX + CW / 2 + 0.1, 4.0, CW / 2 - 0.1, 2.45, HEX.card, "power box");
s.addText("도시가스용", { x: MX + 0.25, y: 4.15, w: 5, h: 0.4, fontSize: 15, bold: true, color: HEX.accent1, margin: 0, isTextBox: true, objectName: "city head" });
bullets([`HDD 1 증가 → 월 ${f2(R.b1)}천 톤 증가 (단순회귀)`, "3차항 F 검정: 곡률이 일부 남아 HDD 효과가 완전한 선형은 아님",
  "요금·영업일·추세를 더해도 기온이 대부분을 설명"], { x: MX + 0.25, y: 4.62, w: CW / 2 - 0.6, h: 1.75 }, 13);
s.addText("발전용", { x: MX + CW / 2 + 0.35, y: 4.15, w: 5, h: 0.4, fontSize: 15, bold: true, color: HEX.accent2, margin: 0, isTextBox: true, objectName: "power head" });
bullets([`기온만 R² ${f2(R.r2_power_weather)} → 전력·정책·가격 추가 ${f2(R.r2_power)}`,
  `전력거래량(${pv(R.p_elec)})·석탄 상한제(${pv(R.p_coal)})는 유의하지 않음`,
  "원전 정비·석탄 발전처럼 월별 공개 자료가 없는 공급 측 요인이 남음"], { x: MX + CW / 2 + 0.35, y: 4.62, w: CW / 2 - 0.6, h: 1.75 }, 13);
s.addNotes(`회귀 가정을 점검했습니다. 원 척도에서는 수요가 클수록 오차가 커지는 이분산이 있어 Box-Cox 결과에 따라 제곱근 변환을 했고, 그러면 등분산 검정이 기각되지 않습니다. 월별 자료라 잔차 자기상관이 강해서 계수 추론에는 Newey-West 표준오차를 썼는데, OLS 표준오차의 ${f1(R.b1_se_hac / R.b1_se)}배였습니다. 2020년 이후만 보면 ${ym(R.break2_date)} 전후로 관계가 바뀌는데, 요금 인상기와 겹칩니다. 발전용은 전력거래량이나 석탄 상한제 기간을 넣어도 설명력이 ${f2(R.r2_power)}에 그쳐, 공개 자료로는 잡히지 않는 공급 측 요인이 남아 있습니다.`);

// ================= 13. 시도별 민감도 =================
slide("결과", `시도별 난방 민감도는 ${f1(PS.min)}%~${f1(PS.max)}%로 약 세 배 차이 난다`);
figure(SF("s_province.png"), { x: MX, y: 1.5, w: CW, h: 4.95 }, "province sensitivity");
note(`HDD 10 증가당 도시가스 판매량 증가율, 당월+전월 HDD (검침 시점 반영), Newey-West 표준오차 · 시도 기울기 동일성 F = ${f0(N.province_F)}, p < 0.001`);
s.addNotes(`시도별로 보면 기온이 같은 만큼 내려갈 때 늘어나는 판매량이 ${PS.min_prov} ${f1(PS.min)}%에서 ${PS.max_prov} ${f1(PS.max)}%까지 약 세 배 차이 납니다. 17개 시도의 기울기가 같다는 가설은 강하게 기각됩니다. 산업 도시인 울산, 충남, 경북이 낮고 서울, 제주, 대전이 높아, 산업용 수요가 많은 지역일수록 기온에 덜 민감한 것으로 보입니다. 오른쪽은 기간별 변화로, 2020년대에 17곳 중 15곳에서 민감도가 커졌습니다. 시도 판매량은 검침 시점 기준이라 전월 기온까지 넣었는데, 이 점이 뒤의 계층 예측에서도 중요했습니다.`);

// ================= 14. 예측 시계 =================
slide("결과", "발전용 오차는 도시가스용의 약 2배이고, 시계에 따른 차이는 작다");
figure(SF("s_horizon.png"), { x: MX, y: 1.5, w: CW, h: 4.95 }, "error by horizon");
note(`사전예측, 목표월 2023~2025년(36개월) · Ensemble 1~12개월 평균 MAPE: 도시가스용 ${f1(ensC)}%, 발전용 ${f1(ensP)}%, 합계 ${f1(ensT)}%`);
s.addNotes(`예측 시계별 오차입니다. 가로축이 몇 개월 앞인지, 세로축이 오차율이고, 두 그림의 세로축 범위를 같게 맞췄습니다. 남색 굵은 선이 Ensemble, 점선이 작년 같은 달 값을 쓰는 Seasonal Naive입니다. 도시가스용은 Ensemble이 평균 ${f1(ensC)}%로 Seasonal Naive의 ${f1(nat("city", "계절 naive"))}%보다 크게 낮습니다. 발전용은 ${f1(ensP)}%로 두 배가량 높고, Seasonal Naive와의 차이도 상대적으로 작습니다. 평년 기온을 쓰는 한 12개월 앞 오차도 1개월 앞과 크게 다르지 않았습니다.`);

// ================= 15. 모델별 정확도 =================
slide("결과", "Ensemble의 평균 오차가 가장 낮지만, 신뢰구간은 상위 모델과 겹친다");
figure(SF("s_models.png"), { x: MX, y: 1.5, w: CW, h: 4.95 }, "model accuracy with CI");
note("1~12개월 앞 사전예측, 목표월 2023~2025년 · 속이 빈 점 = 90% 모델 신뢰집합(MCS) 밖 · 신뢰구간: 목표월 블록 부트스트랩 2,000회");
s.addNotes(`12개 모델의 평균 오차와 95% 신뢰구간입니다. 두 용도 모두 Ensemble이 가장 위에 있습니다. 하지만 막대로 표시한 신뢰구간은 상위 모델끼리 크게 겹칩니다. 최고 모델과 통계적으로 구별되지 않는 모델 집합, 즉 MCS에는 도시가스용 ${mcs("city").length}개, 발전용 ${mcs("power").length}개가 남았고, 속이 빈 점으로 표시한 모델만 유의하게 나빴습니다.${mcs("power").includes("계절 naive") ? " 발전용에서는 Seasonal Naive조차 집합에서 빠지지 않았습니다." : ""} 36개월 평가로는 상위 모델 간의 작은 차이를 가릴 수 없다는 뜻입니다. 파운데이션 모델은 추가 학습 없이도 중상위권에 들었습니다.`);

// ================= 16. 평균 순위 =================
slide("결과", "평균 순위로 보아도 Ensemble이 1위이며, 상위 모델과의 차이는 작다");
figure(SF("s_rank.png"), { x: MX, y: 1.5, w: CW, h: 4.95 }, "average rank");
note(`432개 (목표월, 시계) 조합마다 매긴 절대오차 순위의 평균 · Friedman 검정 모두 p < 0.001, Nemenyi 임계차 CD = ${f2(fr("total").CD)} · 같은 목표월을 여러 시계에서 예측하므로 참고용 검정`);
s.addNotes(`지표를 바꿔도 결론이 같은지 확인했습니다. 목표월과 시계의 조합마다 12개 모델의 순위를 매겨 평균한 결과, 세 계열 모두 Ensemble이 1위였고 MAE와 MASE에서도 1위였습니다. 파란 띠는 Ensemble의 순위에 임계차를 더한 범위로, 이 안에 든 모델은 Ensemble과 구별되지 않습니다. 도시가스용 ${nearEns("city").length}개, 발전용 ${nearEns("power").length}개, 합계 ${nearEns("total").length}개 모델이 이 범위에 들었습니다. 같은 목표월을 여러 시계에서 예측해 관측이 독립이 아니므로 이 검정은 참고용으로 보고, 통계적 판단은 앞의 모델 신뢰집합을 따랐습니다.`);

// ================= 17. 오차 패턴 =================
slide("결과", "도시가스용은 환절기, 발전용은 11~12월 과대예측에서 오차가 컸다");
figure(SF("s_error_month.png"), { x: MX, y: 1.5, w: CW, h: 4.95 }, "error by calendar month");
note("Ensemble 사전예측, 목표월 2023~2025년, 1~12개월 앞 전체 · 평균 오차 = (예측 − 실제) / 실제 × 100");
s.addNotes(`오차가 어느 달에 생기는지 보았습니다. 도시가스용은 난방이 시작되거나 끝나는 2~3월과 10~11월에 오차가 컸습니다. 이때는 기온이 하루하루 크게 바뀌고 난방을 켜는 시점이 해마다 달라 평년 기온과 실제가 많이 어긋납니다. 발전용은 12월 오차가 ${f0(em("power", "ex_ante", "eval", 12, "MAPE"))}%로 가장 컸는데, 오른쪽 그림처럼 거의 전부가 과대예측이었습니다. 2023~2025년 12월의 발전용 수요가 그 전 해들보다 낮아졌는데, 모델이 과거 겨울 수준을 따라간 결과입니다.`);

// ================= 18. 기온 정보의 가치 =================
slide("결과", `실제 기온을 알면 도시가스용 오차는 ${f0(share("city", "앙상블"))}% 줄지만, 발전용은 ${f0(share("power", "앙상블"))}%만 준다`);
figure(SF("s_weather_value.png"), { x: MX, y: 1.5, w: 8.1, h: 4.95 }, "value of weather information", "left");
stat(`${f0(share("city", "앙상블"))}%`, "도시가스용 오차 중 기온 불확실성의 몫", 9.0, 1.6, 3.73, 1.5, HEX.accent1);
stat(`${f0(share("power", "앙상블"))}%`, "발전용 오차 중 기온 불확실성의 몫", 9.0, 3.25, 3.73, 1.5, HEX.accent2);
text("도시가스용은 장기 기온 전망이 좋아질수록 예측도 좋아진다. 발전용은 기온보다 전력 공급 측 정보가 필요하다.",
  { x: 9.0, y: 4.95, w: 3.73, h: 1.4 }, { fontSize: 13.5, color: HEX.ink2 });
note("Ensemble, 1~12개월 평균 MAPE · 몫 = (사전예측 − 사후예측) / 사전예측");
s.addNotes(`실제 기온을 미리 안다고 가정한 사후예측과 비교했습니다. 도시가스용 오차는 ${f1(nat("city", "앙상블"))}%에서 ${f1(nat("city", "앙상블", "all", "ex_post"))}%로 ${f0(share("city", "앙상블"))}% 줄었습니다. 도시가스용 오차의 상당 부분이 기온을 몰라서 생긴다는 뜻이고, 기상청 장기 전망을 잘 활용하면 그만큼 줄일 여지가 있습니다. 반면 발전용은 ${f0(share("power", "앙상블"))}%만 줄어, 기온보다 원전 가동이나 석탄 발전 같은 전력 공급 측 정보가 필요합니다. 용도마다 다른 정보가 필요하다는 것이 이 연구의 중심 결과입니다.`);

// ================= 19. 예측구간 =================
slide("결과", "80% 예측구간: Chronos-2 자체 구간은 좁고, 검증 오차로 만든 구간은 넓다");
figure(SF("s_intervals.png"), { x: MX, y: 1.5, w: 8.1, h: 4.95 }, "interval coverage", "left");
stat(`${f0(itv("total", "Chronos-2 + 공변량", "native").cov)}%`, "Chronos-2 자체 80% 구간의 적중률", 9.0, 1.6, 3.73, 1.5, "B7791F");
stat(`${f0(itv("total", "앙상블", "conformal").cov)}%`, "Ensemble 보정 구간의 적중률", 9.0, 3.25, 3.73, 1.5, HEX.accent1);
text("검증 구간(2020~2022)에 코로나19와 2022년 가격 급등기가 들어 있어 보정 구간이 넓어졌다. 실무에서는 최근 오차로 보정을 갱신해야 한다.",
  { x: 9.0, y: 4.95, w: 3.73, h: 1.5 }, { fontSize: 13, color: HEX.ink2 });
note("합계, 사전예측, 목표월 2023~2025년 · 보정 구간(conformal) = 검증 구간의 예측 오차로 시계마다 만든 80% 구간");
s.addNotes(`수급계획에는 예측값과 함께 불확실성의 범위가 필요해서, 80% 예측구간이 실제로 얼마나 맞았는지 보았습니다. Chronos-2가 스스로 낸 80% 구간은 실제값을 ${f0(itv("total", "Chronos-2 + 공변량", "native").cov)}%만 포함해 불확실성을 작게 잡았습니다. 반대로 검증 구간의 오차로 만든 보정 구간은 ${f0(itv("total", "앙상블", "conformal").cov)}%를 포함해 필요 이상으로 넓었습니다. 검증 구간에 코로나19와 2022년 가격 급등기가 들어 있어 오차가 컸기 때문입니다. 파운데이션 모델의 구간을 그대로 쓰기보다, 최근 오차로 보정을 계속 갱신하는 것이 필요합니다.`);

// ================= 20. SHAP =================
slide("결과", `LightGBM 특성 기여도: 도시가스용은 HDD가 ${f0(shp("city", "hdd"))}%, 발전용은 여러 요인에 나뉜다`);
figure(SF("s_shap.png"), { x: MX, y: 1.5, w: CW, h: 4.4 }, "SHAP");
text("도시가스용은 회귀분석과 같은 결론이다. 발전용에는 결정적인 변수가 없고, 요금 지수는 꾸준히 오른 변수라 추세 역할을 한 것으로 보인다.",
  { x: MX, y: 6.0, w: CW, h: 0.6 }, { fontSize: 14, color: HEX.ink2 });
note("TreeSHAP, 2025년 11월 예측 시점의 학습 자료, 시드 3개 평균 · 상위 6개 특성");
s.addNotes(`기계학습 모델이 무엇을 근거로 예측했는지 SHAP으로 확인했습니다. 도시가스용은 목표월 난방도일이 기여의 ${f0(shp("city", "hdd"))}%를 차지해 회귀분석과 같은 결론입니다. 발전용은 난방도일 ${f0(shp("power", "hdd"))}%, 냉방도일 ${f0(shp("power", "cdd"))}%, 작년 같은 달 수요와 요금 지수가 각각 ${f0(shp("power", "lag12"))}%, ${f0(shp("power", "log_cpi"))}%로 기여가 흩어져 있습니다. 발전용을 설명하는 결정적인 변수가 지금의 입력에는 없다는 뜻입니다.`);

// ================= 21. 계층 예측 =================
slide("결과", "시도 예측을 합치는 조정은 ETS·Chronos-2에서만 전국 오차를 줄였다");
figure(SF("s_hier.png"), { x: MX, y: 1.5, w: CW, h: 4.2 }, "hierarchical forecasting");
bullets([`ETS ${f1(prov("ETS", "기본", "전국"))}% → MinT ${f1(prov("ETS", "MinT", "전국"))}%, Chronos-2(공변량) ${f1(prov("Chronos-2 + 공변량", "기본", "전국"))}% → ${f1(prov("Chronos-2 + 공변량", "MinT", "전국"))}%: 시도 정보가 약한 전국 모델을 보완`,
  `전월 기온을 넣은 OLS(√Y)는 전국 직접 예측이 ${f1(prov("회귀 √Y", "기본", "전국"))}%로 가장 정확하고, 조정하면 오히려 나빠짐 (MinT ${f1(prov("회귀 √Y", "MinT", "전국"))}%)`],
  { x: MX, y: 5.8, w: CW, h: 0.85 }, 13.5);
s.addNotes(`17개 시도를 따로 예측해 합이 전국과 맞도록 조정하는 계층 예측입니다. 흰 원이 전국을 직접 예측한 것이고, 검은 원이 시도 합, 파란 마름모가 MinT 조정입니다. 지수평활이나 Chronos-2처럼 전국 모델이 상대적으로 약할 때는 시도 정보를 합치는 조정이 전국 예측을 개선했습니다. 하지만 전월 기온까지 넣은 회귀는 전국 직접 예측이 ${f1(prov("회귀 √Y", "기본", "전국"))}%로 가장 정확했고, 조정하면 나빠졌습니다. 계층 조정은 잘 만든 전국 모델을 대신하지 못하는 보완책입니다.`);

// ================= 22. 2026 표본 외 =================
slide("결과", `2026년 표본 외: 발전용 7~8월 수요 급증을 모든 모델이 약 30% 낮게 예측했다`);
figure(SF("s_hold.png"), { x: MX, y: 1.45, w: CW, h: 3.9 }, "2026 holdout");
const hc = [[`+${f0(yoy(7))}% · +${f0(yoy(8))}%`, "7·8월 발전용 수요, 전년 대비", HEX.accent2],
  [`${f0(su(2026, 7, "cdd"))} vs ${f0(su(2025, 7, "cdd"))}`, "7월 냉방도일: 2026년 vs 2025년", HEX.dk2],
  [`${f0(em("power", "ex_post", "hold", 7))}% · ${f0(em("power", "ex_post", "hold", 8))}%`, "실제 기온을 넣은 사후예측 오차 (7·8월)", HEX.red]];
hc.forEach(([v, l, c], i) => stat(v, l, MX + i * (CW / 3 + 0.05), 5.4, CW / 3 - 0.1, 1.2, c, "", { vsize: 22 }));
s.addNotes(`모든 설정을 고정한 뒤 2026년 1~9월에 적용했습니다. 그림은 2025년 12월 시점에서 본 예측입니다. 도시가스용은 실제 수요를 잘 따라갔습니다. 발전용은 7월과 8월 수요가 전년보다 각각 ${f0(yoy(7))}%, ${f0(yoy(8))}% 늘었는데, 12개 모델 모두 26~32% 낮게 예측했습니다. 그런데 7월 냉방도일은 ${f0(su(2026, 7, "cdd"))}로 2025년의 ${f0(su(2025, 7, "cdd"))}보다 오히려 낮았고, 실제 기온을 넣은 사후예측도 ${f0(em("power", "ex_post", "hold", 7)).replace("-", "−")}%와 ${f0(em("power", "ex_post", "hold", 8)).replace("-", "−")}%로 거의 같은 오차를 냈습니다. 즉 이 오차는 기온이 아니라 전력 공급 측 변화에서 왔다고 볼 수 있습니다. 원전 정비 일정이나 석탄 발전 같은 월별 자료가 있어야 설명할 수 있는 부분이고, 회귀분석에서 본 발전용의 한계와 같은 결과입니다.`);

// ================= 23. 6개국 =================
slide("결과", "같은 모델로 본 6개국: 한국은 난방 민감도가 낮고 1개월 앞 오차가 가장 작다");
figure(SF("s_six.png"), { x: MX, y: 1.5, w: CW, h: 4.3 }, "six countries");
bullets(["독일·이탈리아·프랑스·스페인·네덜란드에 같은 모델과 같은 평가 절차(1개월 앞, 2023~2025년)를 적용",
  "유럽은 2022년 에너지 위기로 수요 수준이 바뀌어 기준 회귀가 크게 틀렸고, 한국은 그런 공급 충격이 없어 기준 회귀도 정확"],
  { x: MX, y: 5.9, w: CW, h: 0.8 }, 13.5);
s.addNotes(`같은 모델과 평가 절차를 유럽 5개국에도 적용했습니다. 한국의 난방 민감도는 HDD 10당 ${SIX.r5 ? f1(SIX.r5.KR.hdd10_post) : "–"}%로 프랑스나 독일보다 낮습니다. 유럽은 2022년 에너지 위기로 수요 수준 자체가 바뀌어 위기를 반영하지 않은 회귀가 크게 틀렸지만, 한국은 그런 공급 충격이 없어 단순한 회귀도 여섯 나라 중 가장 정확했습니다. 어느 나라에서나 SARIMAX와 Ensemble이 최고 모델과 구별되지 않았다는 점은 한국 결과와 같습니다.`);

// ================= 24. 선행연구와 비교 =================
pres.addSection({ title: "논의와 결론" });
slide("논의와 결론", "선행연구와 비교한 결과");
table([
  ["주제", "선행연구", "이 연구의 결과"],
  ["기온 정보", "기상청 기온 예측을 반영하면 일별 도시가스 수요 오차가 크게 줄어듦 (최용옥·박혜성, 2020)",
    `월별 1~12개월 앞에서도 도시가스용 오차의 ${f0(share("city", "앙상블"))}%가 기온 불확실성. 발전용은 ${f0(share("power", "앙상블"))}%`],
  ["지역 모형", "수도권·지방 모형의 합산이 전국 예측을 개선 (이성로, 2017)",
    "개선은 전국 모델이 약할 때만. 전월 기온을 넣은 회귀는 전국 직접 예측이 최선"],
  ["예측 결합", "단순 평균 결합이 대체로 안정적 (Bates & Granger, 1969; Wang et al., 2023)",
    `미리 정한 4개 평균이 세 계열 모두 평균 1위. 2026년에는 합계 ${holdRank("total").findIndex((x) => x[0] === "앙상블") + 1}위로 순위 하락`],
  ["파운데이션 모델", "추가 학습 없이 경쟁력 있는 정확도 (Ansari et al., 2024; Das et al., 2024)",
    `정확도는 학습한 모델과 비슷. 자체 80% 구간은 ${f0(itv("total", "Chronos-2 + 공변량", "native").cov)}%만 적중해 보정이 필요`],
], { x: MX, y: 1.6, w: CW }, [2.2, 5.0, 4.93], { size: 13.5, rowH: [0.46, 1.0, 1.0, 1.0, 1.0], firstBold: true });
s.addNotes(`결과를 선행연구와 비교하겠습니다. 최용옥·박혜성(2020)은 일별 예측에서 기상청 기온 예측을 쓰면 오차가 크게 줄어든다고 보고했는데, 월별 1~12개월 앞에서도 도시가스용 오차의 ${f0(share("city", "앙상블"))}%가 기온 불확실성이어서 같은 방향입니다. 이성로(2017)는 지역 모형의 합산이 전국 예측을 개선한다고 했지만, 저희 결과에서는 전국 모델이 약할 때만 그랬습니다. 단순 평균 결합이 안정적이라는 결합 예측 연구의 결론은 평가 구간에서 확인됐지만, 2026년에는 순위가 내려갔습니다. 파운데이션 모델은 추가 학습 없이도 학습한 모델과 비슷한 정확도를 냈지만, 자체 예측구간은 보정이 필요했습니다.`);

// ================= 25. 결론 =================
slide("논의와 결론", "결론", true);
const take = [
  ["도시가스용: 기온이 핵심", `수요 변동의 ${f1(R.r2_simple * 100)}%가 HDD로 설명되고, 예측 오차의 ${f0(share("city", "앙상블"))}%가 기온 불확실성이다. 장기 기온 전망을 개선하면 예측이 좋아진다.`, HEX.accent1],
  ["발전용: 공급 측 정보가 필요", `기온으로 ${f0(R.r2_power_weather * 100)}%만 설명되고 2026년 여름처럼 기온 밖 요인으로 오차가 커진다. 원전·석탄 발전 계획 같은 정보를 모형에 넣어야 한다.`, HEX.accent2],
  ["모델 운용: 하나보다 여러 개", "상위 모델 간 차이는 유의하지 않고 해마다 순위가 바뀐다. 서로 다른 원리의 모델을 함께 운용하고 평균하는 것이 안정적이다.", "9EC5F4"],
];
take.forEach(([h_, t, c], i) => {
  const y = 1.65 + i * 1.6;
  badge(i + 1, MX, y + 0.05, c, 0.62, 20);
  s.addText(h_, { x: MX + 0.95, y, w: 11, h: 0.5, fontSize: 20, bold: true, color: "FFFFFF", margin: 0, valign: "middle",
    isTextBox: true, objectName: `takeaway head ${i + 1}` });
  s.addText(t, { x: MX + 0.95, y: y + 0.55, w: 11.1, h: 0.85, fontSize: 15, color: "D6DCEA", margin: 0, valign: "top",
    isTextBox: true, objectName: `takeaway text ${i + 1}` });
});
s.addNotes(`결론은 세 가지입니다. 첫째, 도시가스용 수요는 기온으로 대부분 설명되고 예측 오차의 약 ${f0(share("city", "앙상블"))}%가 기온 불확실성이므로, 장기 기온 전망을 개선하면 예측이 좋아집니다. 둘째, 발전용은 기온만으로 절반 남짓 설명되고, 2026년 여름처럼 기온과 무관한 요인으로 오차가 커집니다. 원전과 석탄 발전 계획 같은 공급 측 정보를 모형에 넣어야 합니다. 셋째, 상위 모델 간 차이는 통계적으로 유의하지 않고 해마다 순위가 바뀌므로, 서로 다른 원리의 모델을 함께 운용하고 평균하는 것이 안정적입니다.`);

// ================= 26. 한계 =================
slide("논의와 결론", "한계와 향후 과제");
const lim = [
  ["평가 기간", "전국 용도별 자료가 2016년부터라 평가 목표월이 36개월이고, 2019년은 복원값이다.", "자료가 쌓이는 대로 평가 기간을 늘려 순위의 안정성을 다시 확인"],
  ["지역 자료", "시도 판매량은 2023년 정의 변경으로 2022년까지만 썼고, 주택·산업 용도 구분은 월별로 공개되지 않는다.", "새 정의의 시도 자료로 계층 모형을 갱신"],
  ["발전용 요인", "원전·석탄 발전량의 월별 공개 자료를 확보하지 못했다. SMP·석탄 가격은 평가 구간 개선이 없었다.", "전력거래소 발전원별 자료를 연계해 발전용 모형을 보강"],
  ["기온 시나리오", "미래 기온으로 평년값 하나만 썼다.", "기상청 장기예보와 여러 기온 시나리오를 넣어 확률 예측으로 확장"],
];
lim.forEach(([h_, t, f], i) => {
  const x = MX + (i % 2) * (CW / 2 + 0.1), y = 1.6 + Math.floor(i / 2) * 2.5, w = CW / 2 - 0.1;
  card(x, y, w, 2.3, HEX.card, `limit ${i + 1}`);
  s.addText(h_, { x: x + 0.25, y: y + 0.18, w: w - 0.5, h: 0.42, fontSize: 16, bold: true, color: HEX.dk2, margin: 0,
    valign: "middle", isTextBox: true, objectName: `limit head ${i + 1}` });
  s.addText(t, { x: x + 0.25, y: y + 0.66, w: w - 0.5, h: 0.85, fontSize: 13, color: HEX.ink2, margin: 0, valign: "top",
    isTextBox: true, objectName: `limit text ${i + 1}` });
  s.addText([{ text: "향후  ", options: { bold: true, color: HEX.accent1 } }, { text: f, options: { color: HEX.dk1 } }],
    { x: x + 0.25, y: y + 1.6, w: w - 0.5, h: 0.6, fontSize: 13, margin: 0, valign: "top", isTextBox: true,
      objectName: `limit future ${i + 1}` });
});
s.addNotes("한계와 향후 과제입니다. 전국 용도별 자료가 2016년부터라 평가 기간이 36개월로 짧고, 2019년은 복원값입니다. 시도별 판매량은 정의 변경 때문에 2022년까지만 썼습니다. 발전용의 핵심 요인인 원전과 석탄 발전량의 월별 자료를 확보하지 못했고, 미래 기온으로는 평년값 하나만 썼습니다. 각각 평가 기간 확대, 새 시도 자료 반영, 전력거래소 발전원별 자료 연계, 기상청 장기예보를 이용한 확률 예측으로 이어갈 수 있습니다.");

// ================= 27. 참고문헌 =================
slide("논의와 결론", "참고문헌");
const refs = [
  "박진수, 김윤배, 정철우 (2013). 도시가스 일일수요의 단기예측. 대한산업공학회지, 39(4), 247-252.",
  "이근철, 한정희 (2015). 선별적 샘플링을 이용한 국내 도시가스 일별 수요예측 절차 개발. 한국산학기술학회논문지, 16(10), 6860-6868.",
  "이성로 (2017). 수도권과 지방권 수요예측모형을 통한 전국 도시가스수요전망의 예측력 향상. 자원·환경경제연구, 26(4), 519-547.",
  "최용옥, 박혜성 (2020). 함수 주성분 분석을 이용한 일별 도시가스 수요 예측. 자원·환경경제연구, 29(4), 419-442.",
  "Ansari, A. F. et al. (2024). Chronos: Learning the language of time series. Transactions on Machine Learning Research.",
  "Bates, J. M. & Granger, C. W. J. (1969). The combination of forecasts. Operational Research Quarterly, 20(4), 451-468.",
  "Das, A., Kong, W., Sen, R. & Zhou, Y. (2024). A decoder-only foundation model for time-series forecasting. ICML 2024.",
  "Demšar, J. (2006). Statistical comparisons of classifiers over multiple data sets. JMLR, 7, 1-30.",
  "Diebold, F. X. & Mariano, R. S. (1995). Comparing predictive accuracy. JBES, 13(3), 253-263.",
  "Hansen, P. R., Lunde, A. & Nason, J. M. (2011). The model confidence set. Econometrica, 79(2), 453-497.",
  "Liu, J. et al. (2021). Natural gas consumption forecasting: A discussion on forecasting history and future challenges. J. Natural Gas Sci. Eng., 90, 103930.",
  "Sarak, H. & Satman, A. (2003). The degree-day method to estimate the residential heating natural gas consumption in Turkey. Energy, 28(9), 929-939.",
  "Soldo, B. (2012). Forecasting natural gas consumption. Applied Energy, 92, 26-37.",
  "Tian, N. et al. (2023). Application of forecasting strategies and techniques to natural gas consumption. Eng. Appl. of AI.",
  "Wang, X., Hyndman, R. J., Li, F. & Kang, Y. (2023). Forecast combinations: An over 50-year review. IJF, 39(4), 1518-1547.",
  "Wickramasuriya, S. L., Athanasopoulos, G. & Hyndman, R. J. (2019). Optimal forecast reconciliation through trace minimization. JASA, 114(526), 804-819.",
];
const half = Math.ceil(refs.length / 2);
[refs.slice(0, half), refs.slice(half)].forEach((col, k) => {
  s.addText(col.map((t, i) => ({ text: t, options: { breakLine: i < col.length - 1 } })),
    { x: MX + k * (CW / 2 + 0.15), y: 1.55, w: CW / 2 - 0.15, h: 5.0, fontSize: 10.5, color: HEX.ink2, valign: "top",
      paraSpaceAfter: 6, margin: 0, isTextBox: true, objectName: `refs ${k + 1}` });
});
s.addNotes("참고문헌입니다.");

// ================= 28. 질의응답 =================
s = pres.addSlide({ masterName: "TITLE_DARK", sectionTitle: "논의와 결론" });
s.addImage({ path: SF("s_title.png"), x: 6.1, y: 2.9, w: 7.0, h: 3.6, transparency: 35, altText: "decorative demand lines",
  objectName: "closing lines" });
s.addText("감사합니다", { placeholder: "title" });
s.addText("질의응답", { placeholder: "body" });
s.addText("안형석 · 양의창 · 권기범", { x: MX, y: 5.55, w: 6, h: 0.4, fontSize: 15, bold: true, color: "FFFFFF", margin: 0,
  isTextBox: true, objectName: "authors" });
s.addNotes("들어 주셔서 감사합니다. 질문 받겠습니다. 세부 지표, 하이퍼파라미터, Ensemble 구성 변경 결과는 부록 슬라이드에 정리해 두었습니다.");

// ================= 부록 =================
pres.addSection({ title: "부록" });
// A. 전체 지표
slide("부록", "부록 A. 12개 모델의 점예측 지표 (사전예측, 목표월 2023~2025년)");
{
  const cols = [["city", "MAPE"], ["city", "MASE"], ["power", "MAPE"], ["power", "MASE"], ["total", "MAPE"], ["total", "MASE"], ["total", "rank"]];
  const bestv = cols.map(([sr, k]) => Math.min(...MODELS.map((m) => met(sr, m, k)).filter((v) => v != null)));
  const rows = [["모델", "도시가스 MAPE", "도시가스 MASE", "발전 MAPE", "발전 MASE", "합계 MAPE", "합계 MASE", "합계 평균 순위"]];
  MODELS.forEach((m) => rows.push([nm(m), ...cols.map(([sr, k], j) => {
    const v = met(sr, m, k);
    return { text: k === "MAPE" ? f2(v) : f2(v), options: { align: "center", valign: "middle", bold: v === bestv[j],
      color: v === bestv[j] ? HEX.dk2 : HEX.dk1 } };
  })]));
  table(rows, { x: MX, y: 1.55, w: CW }, [2.95, 1.31, 1.31, 1.31, 1.31, 1.31, 1.31, 1.32], { size: 12, rowH: 0.37, headAlign: "center" });
  note("굵게 = 열마다 최고 · MASE 척도 = 2016~2022년 계절 차분의 평균 절대오차 · 평균 순위는 (목표월, 시계) 432개 조합 기준 · MAE·RMSE·sMAPE는 보고서 표 3");
  s.addNotes("부록입니다. 12개 모델의 지표를 모두 정리했습니다.");
}
// B. Ensemble ablation
slide("부록", "부록 B. Ensemble 구성을 바꾸면: 해마다 이득이 엇갈린다");
{
  const VARS = [["Ensemble (4)", "Ensemble (미리 정한 4개 평균)"], ["Ensemble (4, 중앙값)", "같은 4개의 중앙값"], ["− 회귀 √Y", "− OLS(√Y)"],
    ["− SARIMAX", "− SARIMAX"], ["− LightGBM", "− LightGBM"], ["− Chronos-2 + 공변량", "− Chronos-2(공변량)"],
    ["통계 (OLS+SARIMAX)", "통계만 (OLS + SARIMAX)"], ["AI (LightGBM+Chronos-2)", "AI만 (LightGBM + Chronos-2)"], ["전 모델 평균 (11)", "전 모델 평균 (11개)"]];
  const rows = [["변형", "합계 2023~25", "도시가스 2023~25", "발전 2023~25", "합계 2026", "도시가스 2026", "발전 2026"]];
  VARS.forEach(([v, lab]) => rows.push([lab, ...["eval", "hold"].flatMap((w) => ["total", "city", "power"].map((sr) => ({
    text: f2(abl(v, sr, w)), options: { align: "center", valign: "middle" } })))]));
  table(rows, { x: MX, y: 1.55, w: CW }, [3.6, 1.42, 1.42, 1.42, 1.42, 1.42, 1.43], { size: 12.5, rowH: 0.44, headAlign: "center" });
  note("1~12개월 앞 사전예측 MAPE(%) · 2026 = 표본 외 1~9월 · 구성원별 기여가 해마다 엇갈려, 사후에 구성을 바꾸지 않고 미리 정한 단순 평균을 유지");
  s.addNotes(`Ensemble 구성원을 하나씩 빼거나 묶음을 바꿔 본 결과입니다. 평가 구간에서는 OLS를 빼면 합계 오차가 ${f2(abl("Ensemble (4)", "total"))}%에서 ${f2(abl("− 회귀 √Y", "total"))}%로 나빠지지만, 2026년에는 반대로 ${f2(abl("Ensemble (4)", "total", "hold"))}%에서 ${f2(abl("− 회귀 √Y", "total", "hold"))}%로 좋아집니다. 이렇게 해마다 이득이 엇갈려 미리 정한 구성을 유지했습니다.`);
}
// C. 연도별
slide("부록", "부록 C. 연도별 MAPE: 해마다 최고 모델이 바뀐다");
{
  const YM = ["계절 naive", "회귀 √Y", "SARIMAX", "ETS", "LightGBM", "하이브리드 (회귀+Ridge)", "Chronos-2 + 공변량", "TimesFM 2.5", "앙상블"];
  const yr = (sr, m, y) => (N.by_year || {})[`${sr}|${m}|${y}`];
  const rows = [["모델", "도시 ’23", "도시 ’24", "도시 ’25", "발전 ’23", "발전 ’24", "발전 ’25", "합계 ’23", "합계 ’24", "합계 ’25"]];
  YM.forEach((m) => rows.push([nm(m), ...["city", "power", "total"].flatMap((sr) => ["2023", "2024", "2025"].map((y) => {
    const v = yr(sr, m, y), b = Math.min(...YM.map((x) => yr(sr, x, y)));
    return { text: f1(v), options: { align: "center", valign: "middle", bold: v === b, color: v === b ? HEX.dk2 : HEX.dk1 } };
  }))]));
  table(rows, { x: MX, y: 1.55, w: CW }, [2.8, ...Array(9).fill((CW - 2.8) / 9)], { size: 12.5, rowH: 0.44, headAlign: "center" });
  const KW = N.kendall_W || {};
  note(`굵게 = 그해 최저 · 연도는 목표월 기준 · 연도 간 순위 일치도 Kendall W: 도시가스용 ${f2(KW.city)}, 발전용 ${f2(KW.power)}, 합계 ${f2(KW.total)}`);
  s.addNotes("연도별로 나누어 보면 그해 최고 모델이 매년 바뀌고, 2024년 발전용과 합계에서는 Seasonal Naive가 가장 정확했습니다. 순위 일치도는 중간 정도입니다.");
}
// D. 하이퍼파라미터·계산 비용
slide("부록", "부록 D. 선택한 설정과 계산 비용");
{
  const FEAT = { hdd: "HDD", cdd: "CDD", workdays: "영업일", log_cpi: "요금", trend: "추세", coal_cap: "상한제", log_lng: "LNG 가격" };
  const fmtHP = (m, js) => {
    const p = JSON.parse(js);
    const f = p.feats ? p.feats.map((x) => FEAT[x] || x).join("·") : "";
    if (m === "SARIMAX") return `(${p.order.join(",")})(${p.seasonal.join(",")})₁₂, ${p.exog.map((x) => FEAT[x] || x).join("·")}`;
    if (m === "ETS") return p.trend ? (p.damped ? "감쇠 추세" : "가법 추세") : "추세 없음";
    if (m === "Ridge") return `α = ${p.alpha}`;
    if (m === "LightGBM") return `잎 ${p.num_leaves}, 트리 ${p.n_estimators}, 최소 ${p.min_child_samples}`;
    if (m === "하이브리드 (회귀+Ridge)") return `${f}, α = ${p.alpha}`;
    if (m === "하이브리드 (회귀+LightGBM)") return `${f}, 잎 ${p.num_leaves}`;
    return f || "–";
  };
  const HM = ["회귀 √Y", "SARIMAX", "ETS", "Ridge", "LightGBM", "하이브리드 (회귀+Ridge)", "하이브리드 (회귀+LightGBM)"];
  const hp = (sr, m) => (N.hyper || {})[`${sr}|${m}`];
  const rows = [["모델", "후보 수", "선택 (합계)", "예측 시점당 시간"]];
  HM.forEach((m) => rows.push([nm(m), { text: String(hp("total", m).n), options: { align: "center", valign: "middle" } },
    fmtHP(m, hp("total", m).params), { text: N.compute[m].sec < 0.01 ? "< 0.01초" : `${f2(N.compute[m].sec)}초`, options: { align: "center", valign: "middle" } }]));
  ["Chronos-2", "Chronos-2 + 공변량", "TimesFM 2.5"].forEach((m) => rows.push([nm(m), { text: "–", options: { align: "center" } },
    `추가 학습 없음, 매개변수 ${N.compute[m].params}개`, { text: `${f2(N.compute[m].sec)}초`, options: { align: "center", valign: "middle" } }]));
  table(rows, { x: MX, y: 1.55, w: CW }, [2.9, 1.2, 6.03, 2.0], { size: 12.5, rowH: 0.42, headAlign: "center" });
  note("설정은 검증 구간(목표월 2020~2022년) MAPE로 선택 · 시간: 도시가스용, CPU, 평가 구간 예측 시점 6개의 중앙값 (LightGBM 계열은 시드 3개 합계)");
  s.addNotes("검증 구간에서 고른 설정과 계산 시간입니다. 모든 모델이 예측 시점 한 번에 1초 안팎으로 끝났습니다.");
}
// E. 시계별 개선율
slide("부록", "부록 E. 예측 시계별로 본 Seasonal Naive 대비 개선율");
figure(FIG("fig10_skill_heatmap.png"), { x: MX, y: 1.5, w: CW, h: 4.95 }, "skill heatmap");
note("파랑 = Seasonal Naive보다 오차가 작음, 주황 = 큼 · 사전예측, 목표월 2023~2025년 · 보고서 그림 A2");
s.addNotes("모든 모델의 예측 시계별 개선율입니다. 도시가스용은 모든 모델이 모든 시계에서 Seasonal Naive보다 나았고, 발전용 ETS는 4~7개월 앞에서 오히려 나빴습니다.");

pres.writeFile({ fileName: OUT })
  .then(() => applyTheme(OUT, THEME))
  .then(() => console.log("저장: report/한국_LNG_수요예측_발표.pptx"));
