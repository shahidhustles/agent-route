// Tested helpers for pptxgenjs decks. Use: const H = require('/usr/local/lib/ar/pptx_helpers.js');
//   await H.icon('FaCoffee', '#1F6F6B')  -> "image/png;base64,..." for slide.addImage({ data, x, y, w, h })
//   H.SHAPE.rect / .round / .oval / .line  -> pass to slide.addShape(H.SHAPE.round, {...})
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');
const sharp = require('sharp');
const pack = { Fa: 'fa', Fa6: 'fa6', Md: 'md', Io: 'io5', Bs: 'bs', Hi: 'hi', Ri: 'ri', Tb: 'tb', Lu: 'lu' };

async function icon(name, color = '#000000', px = 256) {
  const prefix = Object.keys(pack).sort((a, b) => b.length - a.length).find((p) => name.startsWith(p));
  if (!prefix) throw new Error(`unknown icon set for ${name}; use Fa*, Md*, Bs*, Hi*, Ri*, Tb* or Lu*`);
  const mod = require(`react-icons/${pack[prefix]}`);
  if (!mod[name]) throw new Error(`no icon ${name} in react-icons/${pack[prefix]}`);
  const svg = renderToStaticMarkup(React.createElement(mod[name], { color, size: String(px) }));
  const png = await sharp(Buffer.from(svg)).resize(px, px, { fit: 'contain', background: { r: 0, g: 0, b: 0, alpha: 0 } }).png().toBuffer();
  return 'image/png;base64,' + png.toString('base64');
}

const SHAPE = { rect: 'rect', round: 'roundRect', oval: 'ellipse', line: 'line', triangle: 'triangle', chevron: 'chevron' };
module.exports = { icon, SHAPE };
