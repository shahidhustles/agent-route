// Free fixture: a hand-written pptxgenjs deck, built the way an agent would, to prove the sandbox and the preview.
const pptxgen = require("pptxgenjs");
const React = require("react");
const { renderToStaticMarkup } = require("react-dom/server");
const sharp = require("sharp");
const { FaTruck, FaSnowflake, FaClock } = require("react-icons/fa");

const NAVY = "12263F", ICE = "DCE9F5", AMBER = "F2A93B", INK = "1B2733", MUTE = "5B6B7A";
async function icon(Component, color) {
  const svg = renderToStaticMarkup(React.createElement(Component, { color: "#" + color, size: "256" }));
  const png = await sharp(Buffer.from(svg)).png().toBuffer();
  return "image/png;base64," + png.toString("base64");
}

(async () => {
  const pres = new pptxgen();
  pres.layout = "LAYOUT_16x9";
  pres.title = "Cold-chain pilot";
  const truck = await icon(FaTruck, AMBER), snow = await icon(FaSnowflake, AMBER), clock = await icon(FaClock, AMBER);

  let s = pres.addSlide();
  s.background = { color: NAVY };
  s.addText("Cold-chain pilot", { x: 0.6, y: 1.5, w: 8.8, h: 1.2, fontFace: "Cambria", fontSize: 48, bold: true, color: "FFFFFF", margin: 0 });
  s.addText("Proposal to move three regional routes onto monitored reefer trucks", { x: 0.6, y: 2.8, w: 7.6, h: 0.9, fontFace: "Calibri", fontSize: 20, color: ICE, margin: 0 });
  s.addText("Assumption: figures are illustrative until the fleet team supplies its logs.", { x: 0.6, y: 4.7, w: 8.8, h: 0.4, fontFace: "Calibri", fontSize: 12, italic: true, color: AMBER, margin: 0 });

  s = pres.addSlide();
  s.background = { color: "FFFFFF" };
  s.addText("Why now", { x: 0.6, y: 0.4, w: 8.8, h: 0.8, fontFace: "Cambria", fontSize: 36, bold: true, color: NAVY, margin: 0 });
  [[truck, "Three routes", "Dairy and vaccines move on the Pune, Nashik and Surat routes."],
   [snow, "Temperature holds", "Reefer units log every five minutes; a breach pages the dispatcher."],
   [clock, "Six-week pilot", "Start 4 Nov, review 16 Dec, decide by 20 Dec."]].forEach(([ic, h, t], i) => {
    const y = 1.5 + i * 1.2;
    s.addShape(pres.shapes.OVAL, { x: 0.6, y, w: 0.8, h: 0.8, fill: { color: NAVY } });
    s.addImage({ data: ic, x: 0.8, y: y + 0.2, w: 0.4, h: 0.4 });
    s.addText(h, { x: 1.7, y, w: 7.5, h: 0.4, fontFace: "Calibri", fontSize: 20, bold: true, color: INK, margin: 0 });
    s.addText(t, { x: 1.7, y: y + 0.4, w: 7.5, h: 0.5, fontFace: "Calibri", fontSize: 15, color: MUTE, margin: 0 });
  });

  s = pres.addSlide();
  s.background = { color: "FFFFFF" };
  s.addText("Spoilage by week (illustrative)", { x: 0.6, y: 0.4, w: 8.8, h: 0.8, fontFace: "Cambria", fontSize: 32, bold: true, color: NAVY, margin: 0 });
  s.addChart(pres.charts.BAR, [{ name: "Spoiled pallets", labels: ["W1", "W2", "W3", "W4", "W5", "W6"], values: [9, 8, 6, 5, 3, 2] }],
    { x: 0.6, y: 1.4, w: 5.8, h: 3.6, barDir: "col", chartColors: [AMBER], showTitle: false, showValue: true, dataLabelPosition: "outEnd",
      dataLabelColor: INK, catAxisLabelColor: MUTE, valAxisLabelColor: MUTE, valGridLine: { color: "E3E8ED", size: 0.5 }, catGridLine: { style: "none" }, showLegend: false });
  s.addText("-78%", { x: 6.9, y: 1.7, w: 2.6, h: 1.2, fontFace: "Cambria", fontSize: 66, bold: true, color: NAVY, margin: 0 });
  s.addText("spoiled pallets from week 1 to week 6 if the model holds", { x: 6.9, y: 2.9, w: 2.6, h: 1.0, fontFace: "Calibri", fontSize: 14, color: MUTE, margin: 0 });
  s.addNotes("Illustrative numbers, not measured. Replace with the fleet logs before the review.");
  await pres.writeFile({ fileName: process.argv[2] || "out/deck.pptx" });
})();
