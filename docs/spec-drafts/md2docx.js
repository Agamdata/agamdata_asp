// Focused markdown-to-docx converter for ASP governance specs.
// Handles: headings 1-4, paragraphs, pipe tables, fenced code blocks,
// bullet/numbered lists, inline bold/italic/code, horizontal rules.
// Not a general-purpose md parser.

const fs = require('fs');
const path = require('path');
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  HeadingLevel, AlignmentType, BorderStyle, WidthType, ShadingType,
  LevelFormat, PageOrientation, PageBreak,
} = require('docx');

const [, , inputPath, outputPath] = process.argv;
if (!inputPath || !outputPath) {
  console.error('Usage: node md2docx.js <input.md> <output.docx>');
  process.exit(1);
}

const md = fs.readFileSync(inputPath, 'utf8');
const lines = md.split(/\r?\n/);

const CONTENT_WIDTH = 9360; // US Letter, 1" margins

// ---- inline parser: **bold**, *italic*, `code` ------------------------------
function parseInline(text, baseOpts = {}) {
  const runs = [];
  let i = 0;
  let buf = '';
  const flush = (opts = {}) => {
    if (buf) {
      runs.push(new TextRun({ ...baseOpts, ...opts, text: buf }));
      buf = '';
    }
  };
  while (i < text.length) {
    // Bold **text**
    if (text.startsWith('**', i)) {
      const end = text.indexOf('**', i + 2);
      if (end !== -1) {
        flush();
        runs.push(new TextRun({ ...baseOpts, bold: true, text: text.slice(i + 2, end) }));
        i = end + 2;
        continue;
      }
    }
    // Inline code `code`
    if (text[i] === '`') {
      const end = text.indexOf('`', i + 1);
      if (end !== -1) {
        flush();
        runs.push(new TextRun({
          ...baseOpts,
          font: 'Consolas',
          text: text.slice(i + 1, end),
          shading: { type: ShadingType.CLEAR, fill: 'F2F2F2' },
        }));
        i = end + 1;
        continue;
      }
    }
    // Italic *text* (not in middle of word)
    if (text[i] === '*' && text[i + 1] !== '*') {
      const end = text.indexOf('*', i + 1);
      if (end !== -1 && end > i + 1) {
        flush();
        runs.push(new TextRun({ ...baseOpts, italics: true, text: text.slice(i + 1, end) }));
        i = end + 1;
        continue;
      }
    }
    buf += text[i];
    i++;
  }
  flush();
  return runs.length ? runs : [new TextRun({ ...baseOpts, text })];
}

// ---- block parser ----------------------------------------------------------
const children = [];
const numbering = {
  config: [
    { reference: 'bullets', levels: [{
      level: 0, format: LevelFormat.BULLET, text: '\u2022',
      alignment: AlignmentType.LEFT,
      style: { paragraph: { indent: { left: 720, hanging: 360 } } },
    }]},
  ],
};

const border = { style: BorderStyle.SINGLE, size: 4, color: 'BFBFBF' };
const allBorders = { top: border, bottom: border, left: border, right: border };

function hr() {
  return new Paragraph({
    border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: '808080', space: 1 } },
    spacing: { before: 120, after: 120 },
    children: [new TextRun('')],
  });
}

function makeTable(rows) {
  const nCols = rows[0].length;
  const colWidth = Math.floor(CONTENT_WIDTH / nCols);
  const columnWidths = new Array(nCols).fill(colWidth);
  columnWidths[nCols - 1] = CONTENT_WIDTH - colWidth * (nCols - 1);

  const tRows = rows.map((cells, rowIdx) => new TableRow({
    tableHeader: rowIdx === 0,
    children: cells.map((cell, colIdx) => new TableCell({
      borders: allBorders,
      width: { size: columnWidths[colIdx], type: WidthType.DXA },
      shading: rowIdx === 0
        ? { type: ShadingType.CLEAR, fill: 'D9E2F3' }
        : undefined,
      margins: { top: 80, bottom: 80, left: 120, right: 120 },
      children: [new Paragraph({
        children: parseInline(cell, rowIdx === 0 ? { bold: true } : {}),
      })],
    })),
  }));

  return new Table({
    width: { size: CONTENT_WIDTH, type: WidthType.DXA },
    columnWidths,
    rows: tRows,
  });
}

let i = 0;
while (i < lines.length) {
  const line = lines[i];

  // Fenced code block
  if (/^```/.test(line)) {
    const lang = line.replace(/^```/, '').trim();
    i++;
    const codeLines = [];
    while (i < lines.length && !/^```/.test(lines[i])) {
      codeLines.push(lines[i]);
      i++;
    }
    i++; // skip closing ```
    for (const cl of codeLines) {
      children.push(new Paragraph({
        spacing: { before: 0, after: 0 },
        shading: { type: ShadingType.CLEAR, fill: 'F2F2F2' },
        children: [new TextRun({ text: cl || ' ', font: 'Consolas', size: 18 })],
      }));
    }
    children.push(new Paragraph({ spacing: { before: 60, after: 60 }, children: [new TextRun('')] }));
    continue;
  }

  // Horizontal rule
  if (/^---+\s*$/.test(line)) {
    children.push(hr());
    i++;
    continue;
  }

  // Table
  if (/^\|.*\|\s*$/.test(line) && i + 1 < lines.length && /^\|[\s:|-]+\|\s*$/.test(lines[i + 1])) {
    const rows = [];
    // Header
    rows.push(line.slice(1, -1).split('|').map(c => c.trim()));
    i += 2; // skip header + separator
    while (i < lines.length && /^\|.*\|\s*$/.test(lines[i])) {
      rows.push(lines[i].slice(1, -1).split('|').map(c => c.trim()));
      i++;
    }
    children.push(makeTable(rows));
    children.push(new Paragraph({ spacing: { before: 60, after: 60 }, children: [new TextRun('')] }));
    continue;
  }

  // Headings
  const h = /^(#{1,4})\s+(.*)$/.exec(line);
  if (h) {
    const level = h[1].length;
    const text = h[2];
    const heading = [HeadingLevel.HEADING_1, HeadingLevel.HEADING_2, HeadingLevel.HEADING_3, HeadingLevel.HEADING_4][level - 1];
    children.push(new Paragraph({
      heading,
      spacing: { before: 240, after: 120 },
      children: parseInline(text),
    }));
    i++;
    continue;
  }

  // Bullet list
  if (/^\s*[-*]\s+/.test(line)) {
    while (i < lines.length && /^\s*[-*]\s+/.test(lines[i])) {
      const text = lines[i].replace(/^\s*[-*]\s+/, '');
      children.push(new Paragraph({
        numbering: { reference: 'bullets', level: 0 },
        spacing: { before: 40, after: 40 },
        children: parseInline(text),
      }));
      i++;
    }
    continue;
  }

  // Numbered list (simple — each becomes a paragraph with its number)
  if (/^\s*\d+\.\s+/.test(line)) {
    while (i < lines.length && /^\s*\d+\.\s+/.test(lines[i])) {
      children.push(new Paragraph({
        spacing: { before: 40, after: 40 },
        indent: { left: 360 },
        children: parseInline(lines[i].replace(/^\s*/, '')),
      }));
      i++;
    }
    continue;
  }

  // Blank line
  if (/^\s*$/.test(line)) {
    children.push(new Paragraph({ spacing: { before: 40, after: 40 }, children: [new TextRun('')] }));
    i++;
    continue;
  }

  // Paragraph (gather consecutive non-empty non-special lines)
  const paraLines = [];
  while (i < lines.length && !/^\s*$/.test(lines[i]) && !/^#{1,4}\s/.test(lines[i])
         && !/^```/.test(lines[i]) && !/^\|.*\|\s*$/.test(lines[i])
         && !/^---+\s*$/.test(lines[i]) && !/^\s*[-*]\s/.test(lines[i])
         && !/^\s*\d+\.\s/.test(lines[i])) {
    paraLines.push(lines[i]);
    i++;
  }
  if (paraLines.length) {
    children.push(new Paragraph({
      spacing: { before: 80, after: 80 },
      children: parseInline(paraLines.join(' ')),
    }));
  }
}

// ---- document --------------------------------------------------------------
const doc = new Document({
  creator: 'ASP Development Team',
  title: 'ASP-FEAT-ASP-00 v1.0 — Gateway Service Detailed Spec',
  styles: {
    default: { document: { run: { font: 'Calibri', size: 22 } } },
    paragraphStyles: [
      { id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: 32, bold: true, font: 'Calibri' },
        paragraph: { spacing: { before: 360, after: 180 }, outlineLevel: 0 } },
      { id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: 26, bold: true, font: 'Calibri' },
        paragraph: { spacing: { before: 240, after: 120 }, outlineLevel: 1 } },
      { id: 'Heading3', name: 'Heading 3', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: 24, bold: true, font: 'Calibri' },
        paragraph: { spacing: { before: 180, after: 100 }, outlineLevel: 2 } },
      { id: 'Heading4', name: 'Heading 4', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: 22, bold: true, italics: true, font: 'Calibri' },
        paragraph: { spacing: { before: 120, after: 80 }, outlineLevel: 3 } },
    ],
  },
  numbering,
  sections: [{
    properties: {
      page: {
        size: { width: 12240, height: 15840 },
        margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 },
      },
    },
    children,
  }],
});

Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync(outputPath, buf);
  console.log(`Wrote ${outputPath} (${buf.length} bytes, ${children.length} block elements)`);
}).catch(e => {
  console.error('Packer error:', e);
  process.exit(2);
});
