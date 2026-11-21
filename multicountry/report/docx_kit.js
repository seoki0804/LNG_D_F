// 보고서(.docx) 공통 부품: 스타일, 문단, 그림, 표, 수식. build_report.js가 사용한다.
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType, ImageRun, Table, TableRow, TableCell,
  WidthType, BorderStyle, ShadingType, LevelFormat, PageNumber, Footer, Header, TableOfContents, PageBreak,
  VerticalAlign,
} = require("docx");

const FONT = "Malgun Gothic";       // 한글 본문 (Windows 기본)
const FONT_EN = "Arial";
const INK = "0B0B0B", INK2 = "52514E", RULE = "C3C2B7", HEAD_FILL = "F0EFEC";
const PAGE_W = 11906, MARGIN = 1304;  // A4, 2.3 cm 여백
const TEXT_W = PAGE_W - 2 * MARGIN;   // 본문 폭 (DXA)

const styles = {
  default: { document: { run: { font: { ascii: FONT_EN, eastAsia: FONT, hAnsi: FONT_EN }, size: 21 },
                         paragraph: { spacing: { line: 300, after: 120 } } } },
  paragraphStyles: [
    { id: "Title", name: "Title", basedOn: "Normal", run: { font: FONT, size: 34, bold: true, color: INK },
      paragraph: { alignment: AlignmentType.CENTER, spacing: { before: 0, after: 160 }, keepNext: true } },
    { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
      run: { font: FONT, size: 26, bold: true, color: INK },
      paragraph: { spacing: { before: 360, after: 140 }, keepNext: true, outlineLevel: 0 } },
    { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
      run: { font: FONT, size: 23, bold: true, color: INK },
      paragraph: { spacing: { before: 240, after: 100 }, keepNext: true, outlineLevel: 1 } },
    { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
      run: { font: FONT, size: 21, bold: true, color: INK2 },
      paragraph: { spacing: { before: 180, after: 80 }, keepNext: true, outlineLevel: 2 } },
    { id: "Caption", name: "Caption", basedOn: "Normal", run: { font: FONT, size: 18, color: INK2 },
      paragraph: { spacing: { before: 60, after: 220 }, alignment: AlignmentType.LEFT } },
  ],
};

const numbering = {
  config: [
    { reference: "bullets", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
      style: { paragraph: { indent: { left: 440, hanging: 260 } } } }] },
    { reference: "numbers", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
      style: { paragraph: { indent: { left: 440, hanging: 300 } } } }] },
  ],
};

// **굵게**와 *기울임*을 지원하는 간단한 인라인 표기
function runs(text, base = {}) {
  const out = [];
  const re = /(\*\*[^*]+\*\*|\*[^*]+\*)/g;
  let last = 0, m;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) out.push(new TextRun({ text: text.slice(last, m.index), ...base }));
    const t = m[0];
    if (t.startsWith("**")) out.push(new TextRun({ text: t.slice(2, -2), bold: true, ...base }));
    else out.push(new TextRun({ text: t.slice(1, -1), italics: true, ...base }));
    last = m.index + t.length;
  }
  if (last < text.length) out.push(new TextRun({ text: text.slice(last), ...base }));
  return out;
}

const P = (text, opts = {}) => new Paragraph({ children: runs(text), alignment: AlignmentType.JUSTIFIED, ...opts });
const H1 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun(t)] });
const H2 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun(t)] });
const H3 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_3, children: [new TextRun(t)] });
const BUL = (t) => new Paragraph({ numbering: { reference: "bullets", level: 0 }, children: runs(t),
                                   spacing: { after: 60 } });
const NUM = (t, ref = "numbers") => new Paragraph({ numbering: { reference: ref, level: 0 }, children: runs(t),
                                                    spacing: { after: 60 } });
// 수식 한 줄 (가운데, 기울임, 오른쪽 번호)
const EQ = (t, n) => new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 80, after: 120 },
  children: [new TextRun({ text: t, italics: true, font: "Cambria Math" }),
             ...(n ? [new TextRun({ text: `\t(${n})`, font: FONT_EN })] : [])] });

// 그림: PNG 크기 비율을 읽어 본문 폭에 맞춘다
function pngSize(file) {
  const b = fs.readFileSync(file);
  return { w: b.readUInt32BE(16), h: b.readUInt32BE(20) };
}
function FIG(file, caption, widthCm = 16) {
  const { w, h } = pngSize(file);
  const wpx = Math.round(widthCm / 2.54 * 96), hpx = Math.round(wpx * h / w);
  return [
    new Paragraph({ alignment: AlignmentType.CENTER, keepNext: true, spacing: { before: 120, after: 40 },
      children: [new ImageRun({ type: "png", data: fs.readFileSync(file), transformation: { width: wpx, height: hpx },
                                altText: { title: path.basename(file), description: caption, name: path.basename(file) } })] }),
    new Paragraph({ style: "Caption", children: runs(caption) }),
  ];
}

// 표: rows[0]은 머리행. widths는 열 비율(합 1)
function TABLE(rows, widths, caption, opts = {}) {
  const colW = widths.map((x) => Math.round(x * TEXT_W));
  colW[colW.length - 1] = TEXT_W - colW.slice(0, -1).reduce((a, b) => a + b, 0);
  const border = { style: BorderStyle.SINGLE, size: 4, color: RULE };
  const none = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };
  const size = opts.size || 17;
  const tr = rows.map((r, i) => new TableRow({
    tableHeader: i === 0,
    children: r.map((c, j) => new TableCell({
      width: { size: colW[j], type: WidthType.DXA },
      verticalAlign: VerticalAlign.CENTER,
      margins: { top: 50, bottom: 50, left: 90, right: 90 },
      shading: i === 0 ? { fill: HEAD_FILL, type: ShadingType.CLEAR, color: "auto" } : undefined,
      borders: { top: i === 0 ? border : none, bottom: (i === 0 || i === rows.length - 1) ? border : none,
                 left: none, right: none },
      children: [new Paragraph({ spacing: { after: 0, line: 260 },
        alignment: j === 0 ? AlignmentType.LEFT : (opts.alignLeft && opts.alignLeft.includes(j) ? AlignmentType.LEFT
                                                                                                  : AlignmentType.CENTER),
        children: runs(String(c), { size, bold: i === 0 ? true : undefined }) })],
    })),
  }));
  return [
    new Paragraph({ style: "Caption", keepNext: true, spacing: { before: 200, after: 60 }, children: runs(caption) }),
    new Table({ width: { size: TEXT_W, type: WidthType.DXA }, columnWidths: colW, rows: tr }),
    new Paragraph({ spacing: { after: 120 }, children: [] }),
  ];
}

function build(children, outFile, meta) {
  const doc = new Document({
    creator: meta.creator, title: meta.title, description: meta.description, styles, numbering,
    sections: [{
      properties: { page: { size: { width: PAGE_W, height: 16838 },
                            margin: { top: 1304, bottom: 1304, left: MARGIN, right: MARGIN } } },
      headers: { default: new Header({ children: [new Paragraph({ alignment: AlignmentType.RIGHT,
        children: [new TextRun({ text: meta.runningHead, size: 16, color: INK2 })] })] }) },
      footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER,
        children: [new TextRun({ children: [PageNumber.CURRENT], size: 18, color: INK2 })] })] }) },
      children,
    }],
  });
  return Packer.toBuffer(doc).then((buf) => fs.writeFileSync(outFile, buf));
}

module.exports = { P, H1, H2, H3, BUL, NUM, EQ, FIG, TABLE, build, runs, Paragraph, TextRun, AlignmentType,
                   PageBreak, TableOfContents, HeadingLevel, TEXT_W };
