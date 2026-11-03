// Free fixture: a hand-written docx-js document with a title block, headings, a table, bullets, header and page numbers.
const fs = require("fs");
const { Document, Packer, Paragraph, TextRun, HeadingLevel, Table, TableRow, TableCell, WidthType, ShadingType, AlignmentType,
  LevelFormat, Header, Footer, PageNumber, BorderStyle } = require("docx");

const GREEN = "1F5C4A", GREY = "5B6B7A", LIGHT = "E6F0EC";
const border = { style: BorderStyle.SINGLE, size: 4, color: "C9D6D0" };
const borders = { top: border, bottom: border, left: border, right: border };
const cell = (text, w, head) => new TableCell({ width: { size: w, type: WidthType.DXA }, borders, margins: { top: 80, bottom: 80, left: 120, right: 120 },
  shading: head ? { fill: GREEN, type: ShadingType.CLEAR, color: "auto" } : undefined,
  children: [new Paragraph({ children: [new TextRun({ text, bold: head, color: head ? "FFFFFF" : "1B2733", font: "Calibri", size: 22 })] })] });
const row = (a, b, c, head) => new TableRow({ children: [cell(a, 3600, head), cell(b, 2880, head), cell(c, 2880, head)] });
const p = (text, opts = {}) => new Paragraph({ spacing: { after: 140, line: 300 }, children: [new TextRun({ text, font: "Calibri", size: 23, ...opts })] });

const doc = new Document({
  styles: { default: { document: { run: { font: "Calibri", size: 23 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true, run: { size: 34, bold: true, font: "Cambria", color: GREEN }, paragraph: { spacing: { before: 320, after: 140 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true, run: { size: 26, bold: true, font: "Cambria", color: "1B2733" }, paragraph: { spacing: { before: 220, after: 100 }, outlineLevel: 1 } }] },
  numbering: { config: [{ reference: "bullets", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] }] },
  sections: [{
    properties: { page: { size: { width: 12240, height: 15840 }, margin: { top: 1440, right: 1440, bottom: 1300, left: 1440 } } },
    headers: { default: new Header({ children: [new Paragraph({ alignment: AlignmentType.RIGHT, children: [new TextRun({ text: "Harbour Mill  |  Pilot proposal", color: GREY, size: 18, font: "Calibri" })] })] }) },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "Page ", color: GREY, size: 18 }), new TextRun({ children: [PageNumber.CURRENT], color: GREY, size: 18 })] })] }) },
    children: [
      new Paragraph({ spacing: { before: 600, after: 80 }, children: [new TextRun({ text: "Weekend delivery pilot", font: "Cambria", size: 56, bold: true, color: GREEN })] }),
      new Paragraph({ spacing: { after: 360 }, border: { bottom: { style: BorderStyle.SINGLE, size: 8, color: GREEN, space: 8 } }, children: [new TextRun({ text: "A proposal for Harbour Mill bakery, prepared for the owners", color: GREY, size: 24 })] }),
      new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun("Summary")] }),
      p("Harbour Mill proposes a ten-week Saturday and Sunday delivery pilot to cafes within 8 km of the bakery. The request names the cafes and the weekday volumes; nothing below goes beyond them."),
      new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun("What the pilot costs")] }),
      new Table({ width: { size: 9360, type: WidthType.DXA }, columnWidths: [3600, 2880, 2880], rows: [
        row("Item", "Weekly", "Ten weeks", true), row("Van hire", "$240", "$2,400"), row("Driver, 2 shifts", "$320", "$3,200"), row("Packaging", "$60", "$600"), row("Total", "$620", "$6,200")] }),
      p("Assumption: van and driver rates are placeholders until quotes arrive.", { italics: true, color: GREY }),
      new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun("Risks to watch")] }),
      ...["Weekend demand is untested, so week three is a go or no-go review.", "A single van means one breakdown stops every delivery.", "Fresh bread cut-off times move earlier on Sundays."].map(t =>
        new Paragraph({ numbering: { reference: "bullets", level: 0 }, spacing: { after: 100 }, children: [new TextRun({ text: t, font: "Calibri", size: 23 })] })),
    ] }] });
Packer.toBuffer(doc).then(b => fs.writeFileSync(process.argv[2] || "out/document.docx", b));
