// 문장 도우미: 숫자·영문 모델 이름 뒤에 붙는 조사(이/가, 은/는, 을/를, 와/과, 로/으로, 였다/이었다)와 날짜 표기.
// build_report.js, build_deck.js가 함께 쓴다.

// 끝소리: 0 = 받침 없음, 1 = 받침(ㄹ 제외), 2 = ㄹ 받침
const DIGIT = { 0: 1, 1: 2, 2: 0, 3: 1, 4: 0, 5: 0, 6: 1, 7: 2, 8: 2, 9: 0 };   // 영 일 이 삼 사 오 육 칠 팔 구
const LETTER = { l: 2, r: 2, m: 1, n: 1 };                                    // 엘 알 엠 엔, 나머지 알파벳 이름은 모음으로 끝남
function finalSound(str) {
  let t = String(str).trim();
  // 끝의 괄호 묶음은 건너뛰고 괄호 앞 말에 맞춘다: "Ensemble(5.7%)" → Ensemble
  const m = t.match(/^(.*\S)\s*\([^()]*\)$/);
  if (m) t = m[1];
  while (t && /[\]\s.,]/.test(t[t.length - 1])) t = t.slice(0, -1);
  if (!t) return 0;
  const c = t[t.length - 1];
  if (c === "%") return 0;                                            // 퍼센트
  if (/[0-9]/.test(c)) return DIGIT[c];
  const code = c.charCodeAt(0);
  if (code >= 0xac00 && code <= 0xd7a3) {
    const jong = (code - 0xac00) % 28;
    return jong === 0 ? 0 : jong === 8 ? 2 : 1;
  }
  if (/[A-Za-z]/.test(c)) {
    const word = (t.match(/[A-Za-z]+$/) || [""])[0];
    if (/ble$/i.test(word)) return 2;                                  // Ensemble(앙상블)
    if (word === word.toUpperCase() || word.length === 1) return LETTER[c.toLowerCase()] || 0;   // 약어: 알파벳 이름
    if (/l$/i.test(word)) return 2;
    if (/(m|n|ng)$/i.test(word)) return 1;
    return 0;                                                          // Naive, Ridge, Hybrid(하이브리드)처럼 모음으로 읽힘
  }
  return 0;
}
const PAIRS = { "이/가": ["가", "이"], "은/는": ["는", "은"], "을/를": ["를", "을"], "와/과": ["와", "과"],
  "였다": ["였다", "이었다"], "였고": ["였고", "이었고"], "이다": ["다", "이다"] };
function jo(str, kind) {
  const f = finalSound(str);
  if (kind === "로/으로") return `${str}${f === 1 ? "으로" : "로"}`;
  return `${str}${PAIRS[kind][f === 0 ? 0 : 1]}`;
}
// "2022-07" → "2022년 7월"
const ym = (s) => { const [y, m] = String(s).split("-"); return `${y}년 ${Number(m)}월`; };

module.exports = { jo, ym, finalSound };
