// 赤纬推运 — the app's own declination ladder (components/astro/AstroDeclinationLadder.js), as ProgMethodPanel shows it in
// mode="declination": natalDeclinations = the result's natalDeclinations, progressedDeclinations / parallels = the selected
// method's (page default `secondary`). The component is a card: HTML captions and glyph labels absolutely positioned over an
// <svg> of axes, spines, true-value dots and parallel lines. We SSR it and keep its <svg> as is; the HTML parts (title,
// legend, column heads, the de-collided glyph + degree labels whose positions the app computes in private helpers) are read
// from the rendered DOM and redrawn as svg text at the same boxes (HTML-class pattern, see cnxkit.js). Nothing is computed
// here: every position, colour and label comes from the app's render.
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { DOMParser } from 'linkedom';
import AstroDeclinationLadder from '@horosa-app/components/astro/AstroDeclinationLadder.js';
import { cnxEsc, cnxWidth } from './cnxkit.js';

// The app measures the card (clientWidth / height prop); on paper we give it the report's square figure size, the same
// way the page gives it its left column.
const SIZE = 760;
// antd body line-height: an HTML line box of font-size f is f × 1.5715 tall; captions sit at its middle
const LINE = 1.5715;
// Advance widths (em) of the planet glyphs in the app's symbol font (data/fonts/ywastro.ttf, measured with reportlab's
// TTFont.stringWidth). The flex row lays the degree label next to the glyph box, so its x needs the glyph's advance.
const GLYPH_ADVANCE = { A: 0.798, B: 0.759, C: 0.407, D: 0.48, E: 0.866, F: 0.54, G: 0.558, H: 0.49, I: 0.644, J: 0.517 };

class MeasuredLadder extends AstroDeclinationLadder {
  constructor(props) {
    super(props);
    this.state = { ...this.state, width: SIZE }; // what measure() sets once the card is laid out in its column
  }
}

function css(el) {
  const out = {};
  `${(el && el.getAttribute && el.getAttribute('style')) || ''}`.split(';').forEach((decl) => {
    const i = decl.indexOf(':');
    if (i > 0) out[decl.slice(0, i).trim().toLowerCase()] = decl.slice(i + 1).trim();
  });
  return out;
}
const px = (v, d = 0) => (Number.isFinite(parseFloat(v)) ? parseFloat(v) : d);

function text(x, y, s, size, attrs) {
  return `<text x="${x.toFixed(2)}" y="${y.toFixed(2)}" font-size="${size}" dominant-baseline="central"${attrs}>${cnxEsc(s)}</text>`;
}

// a caption div: absolute box at `top`; `left: 0; right: 0; text-align: center` spans the card (title, legend), a lone
// `left` + translateX(-50%) centers on that x (the column heads)
function caption(div, width) {
  const st = css(div);
  const size = px(st['font-size'], 14);
  const y = px(st.top) + (size * LINE) / 2;
  const weight = st['font-weight'] ? ` font-weight="${st['font-weight']}"` : '';
  const opacity = st.opacity ? ` opacity="${st.opacity}"` : '';
  const base = st.color ? ` fill="${st.color}"` : ' fill="var(--horosa-text)"';
  const runs = [];
  for (const node of div.childNodes) {
    if (node.nodeType === 3) runs.push({ s: node.textContent, fill: base });
    else runs.push({ s: node.textContent, fill: css(node).color ? ` fill="${css(node).color}"` : base });
  }
  const total = runs.reduce((w, r) => w + cnxWidth(r.s, size), 0);
  const spansCard = st['text-align'] === 'center' || st.right !== undefined || st.left === undefined;
  let x = (spansCard ? width / 2 : px(st.left)) - total / 2;
  // svg drops leading / trailing blanks of a <text> (the legend's full-width spaces between runs): advance over them instead
  return runs.map((r) => {
    const lead = r.s.match(/^\s*/)[0];
    const body = r.s.trim();
    const out = body ? text(x + cnxWidth(lead, size), y, body, size, ` text-anchor="start"${weight}${opacity}${r.fill}`) : '';
    x += cnxWidth(r.s, size);
    return out;
  }).join('');
}

// a glyph row: flex, gap 5, centered on `top`; natal rows end at `left` (translate -100%), progressed rows start there
function glyphRow(div) {
  const st = css(div);
  const y = px(st.top);
  const left = px(st.left);
  const natal = /translate\(\s*-100%/.test(st.transform || '');
  const gap = px(st.gap, 5);
  const spans = [...div.children];
  const parts = spans.map((span) => {
    const inner = span.querySelector('span');
    const s = css(span);
    if (inner && /ywastro/.test(css(inner)['font-family'] || '')) {
      const size = px(s['font-size'], 22) * 1.1; // astroSymbolStyle: fontSize 1.1em
      const ch = inner.textContent;
      return { glyph: true, s: ch, size, width: (GLYPH_ADVANCE[ch] || 0.7) * size,
        fill: s.color && s.color !== 'inherit' ? s.color : 'var(--horosa-text)', weight: s['font-weight'] || '400' };
    }
    const size = px(s['font-size'], 11);
    return { glyph: false, s: span.textContent, size, width: cnxWidth(span.textContent, size), fill: s.color || 'var(--horosa-text)' };
  });
  const total = parts.reduce((w, p) => w + p.width, 0) + gap * Math.max(0, parts.length - 1);
  let x = natal ? left - total : left;
  return parts.map((p) => {
    const attrs = p.glyph
      ? ` text-anchor="start" font-family="ywastro" font-weight="${p.weight}" fill="${p.fill}"`
      : ` text-anchor="start" fill="${p.fill}"`;
    const out = text(x, y, p.s, Number(p.size.toFixed(2)), attrs);
    x += p.width + gap;
    return out;
  }).join('');
}

export function renderDeclinationLadder(data) {
  const method = data && data.method;
  if (!data || !Array.isArray(data.natalDeclinations) || !method || !Array.isArray(method.declinations)) {
    throw new Error('declination ladder: needs natalDeclinations and the method\'s declinations');
  }
  const html = renderToStaticMarkup(createElement(MeasuredLadder, {
    natalDeclinations: data.natalDeclinations,
    progressedDeclinations: method.declinations,
    parallels: method.parallels || [],
    height: SIZE,
  }));
  const doc = new DOMParser().parseFromString(`<!doctype html><html><body>${html}</body></html>`, 'text/html');
  const card = doc.body.firstElementChild;
  const svgEl = card.querySelector('svg');
  if (!svgEl) throw new Error('declination ladder: the component rendered no svg');
  const W = px(svgEl.getAttribute('width'), SIZE);
  const cardStyle = css(card);
  // the card's height style is the content box (+ padding top and bottom); the svg is drawn from the padding box's top
  const H = px(cardStyle.height, SIZE) + 2 * px(cardStyle.padding, 0);
  // cardStyle: 1px border, radius 6, surface background; absolute children sit on the padding box (inside the border)
  const border = (cardStyle.border || '1px solid var(--horosa-border)').replace(/^\S+\s+\S+\s+/, '');
  const parts = [`<rect x="0.5" y="0.5" width="${W + 1}" height="${H + 1}" rx="${px(cardStyle['border-radius'], 6)}" fill="${cardStyle.background || 'var(--horosa-surface-solid)'}" stroke="${border}" stroke-width="1"/>`];
  parts.push(`<g transform="translate(1,1)">${svgEl.innerHTML}`);
  for (const div of card.children) {
    if (div === svgEl || div.tagName.toLowerCase() !== 'div') continue;
    const st = css(div);
    parts.push(st.display === 'flex' ? glyphRow(div) : caption(div, W));
  }
  parts.push('</g>');
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${W + 2}" height="${H + 2}" viewBox="0 0 ${W + 2} ${H + 2}" color="var(--horosa-text)">${parts.join('')}</svg>`;
  return { svg, width: W + 2, height: H + 2 };
}
