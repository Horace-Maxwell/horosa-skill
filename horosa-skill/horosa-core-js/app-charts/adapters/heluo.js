// 河洛理数 — the app's center board (HeLuoMain.renderCenter(m), layouts/app/16-zhengchuan-heluo.less .horosa-heluo-* +
// 10-huangji-wuzhao.less .horosa-huangji-info-*) is HTML. m is the page's getModel() product; the run's result carries all of
// it — the skill's tools/heluo.js returns the same chart / dayun / judge / solarTerm the text was built from, plus a
// board_context with the two things only the board reads (年柱纳音, chartExtras) — so renderCenter runs with the app's own code
// (SSR on a bare instance, nothing re-derived here) and the markup is laid out as SVG with the stylesheet's numbers.
// The board is one long scrolling column (≈ 760 × 2400 px); on paper it is split along the app's own cards, one figure each
// (options.part): detail = toolbar + 起卦详情, xian / hou = the 先天 / 后天 卦 cards (爻画 + 纳甲六亲世应 + 元堂, name / verdict /
// 元堂 / 卦气 / gist / 互覆 / 理数 tags, then the 元堂爻辞 block), daxian = the 大限 table. Interactive bits are dropped: the
// 「经文」 expand button, the drill-down ▾ column and the heading's 「点行看爻辞、点▾看流年」 hint.
import { createElement, Fragment } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { DOMParser } from 'linkedom';
import HeLuoMain from '@horosa-app/components/shusuan/HeLuoMain.js';
import { cnxText as tx, cnxWidth, CNX } from './cnxkit.js';

// colours as the page resolves them (the page sits in .horosa-astro-redesign, which maps --horosa-text-secondary to
// --horosa-text-soft; the card tokens come from the .horosa-huangji-redesign scope returned as themeScope)
const C = {
  text: 'var(--horosa-text, #1f1f1f)',
  secondary: 'var(--horosa-text-soft, #888)',
  soft: 'var(--horosa-text-soft, #aaa)',
  accent: 'var(--horosa-accent, #c9a86a)',
  accentStrong: 'var(--horosa-accent-strong, #b07d20)',
  accentSoft: 'var(--horosa-accent-soft, rgba(201, 168, 106, 0.18))',
  surface: 'var(--horosa-surface, rgba(148, 163, 184, 0.12))',
  borderSoft: 'var(--horosa-border-soft, rgba(148, 163, 184, 0.28))',
  onAccent: 'var(--horosa-on-accent, #fff)',
};
const W = 768; // .horosa-heluo-center at a 760 px card width: padding 4 px each side
const CARD_X = 4;
const CARD_W = 760;
const X0 = CARD_X + 13; // card border 1 + padding 12
const INNER = CARD_W - 26;
const NO_LINE_START = /[。，、；：？！」』）》〉】,.;:?!)\]]/;

const cls = (el) => (el && el.getAttribute('class')) || '';
const has = (el, name) => cls(el).split(/\s+/).includes(name);
const txt = (el) => (el ? el.textContent : '');
const own = (el) => [...el.childNodes].filter((n) => n.nodeType === 3).map((n) => n.textContent).join('');

// browser line breaking for CJK text: any character may start a line except closing punctuation (it hangs instead);
// `first` is the room left on the first line (an inline pill before the text), `width` the room on the others
function wrap(text, size, width, first = width) {
  const lines = [];
  let line = '';
  let room = first;
  for (const ch of [...`${text}`]) {
    if (line && cnxWidth(line + ch, size) > room && !NO_LINE_START.test(ch)) {
      lines.push(line);
      line = '';
      room = width;
    }
    line += ch;
  }
  if (line || !lines.length) lines.push(line);
  return lines;
}

function card(out, y, h) {
  out.push(`<rect x="${CARD_X + 0.5}" y="${y + 0.5}" width="${CARD_W - 1}" height="${h - 1}" rx="7" fill="${CNX.cardBg}" stroke="${CNX.line}" stroke-width="1"/>`);
}

// .horosa-huangji-info-heading: 16 px 700 in a 23 px line box, 8 px below
function heading(out, y, text) {
  out.push(tx(X0, y + 11.5, text, 16, CNX.text, 700, 'start'));
  return 23 + 7;
}

// inline pill (b) of the 爻辞 blocks: 12 px 600, line box 20.4, padding 0 8, radius 4, margin-right 8
function pill(out, x, cy, text) {
  const w = cnxWidth(text, 12) + 16;
  out.push(`<rect x="${x}" y="${cy - 10.2}" width="${w}" height="20.4" rx="4" fill="${C.accentSoft}" stroke="none"/>`);
  out.push(tx(x + w / 2, cy, text, 12, C.accentStrong, 600));
  return w + 8;
}

// .horosa-heluo-verdict: 12 px 600, padding 1 7, radius 10, surface background
function verdict(out, x, cy, text) {
  if (!text) return 0;
  const w = cnxWidth(text, 12) + 14;
  out.push(`<rect x="${x}" y="${cy - 8}" width="${w}" height="16" rx="8" fill="${C.surface}" stroke="none"/>`);
  out.push(tx(x + w / 2, cy, text, 12, C.accentStrong, 600));
  return w;
}

function partDetail(doc, out) {
  // toolbar: part 16 px 700 accent-strong and sub 12 px on one baseline (flex align-items: baseline), gap 14
  const part = txt(doc.querySelector('.horosa-heluo-part'));
  const sub = txt(doc.querySelector('.horosa-heluo-sub'));
  const base = 4 + 6 + 17; // padding-top 6, baseline of a 16 px line in its 23 px box
  out.push(tx(CARD_X, base - 0.35 * 16, part, 16, C.accentStrong, 700, 'start'));
  out.push(tx(CARD_X + cnxWidth(part, 16) + 14, base - 0.35 * 12, sub, 12, C.secondary, 400, 'start'));
  const top = 4 + 39;
  const el = doc.querySelector('.horosa-huangji-info-card');
  const inner = [];
  let y = top + 13 + heading(inner, top + 13, txt(el.querySelector('.horosa-huangji-info-heading')));
  // rows: grid 32% | 1fr, gap 8; label 12 px muted (line 17.4), value 13 px 700 (line 18.85, pre-line), padding 5 0
  const labelW = INNER * 0.32;
  for (const row of el.querySelectorAll('.horosa-huangji-info-row')) {
    const value = txt(row.querySelector('strong'));
    const lines = value.split('\n').flatMap((l) => wrap(l, 13, INNER - labelW - 8));
    inner.push(tx(X0, y + 5 + 8.7, txt(row.querySelector('span')), 12, CNX.muted, 400, 'start'));
    lines.forEach((l, i) => inner.push(tx(X0 + labelW + 8, y + 5 + 9.4 + i * 18.85, l, 13, CNX.text, 700, 'start')));
    y += 10 + Math.max(17.4, lines.length * 18.85);
  }
  const h = y - top + 12;
  card(out, top, h);
  out.push(...inner);
  return top + h;
}

function yaoRows(out, guaEl, top) {
  // .horosa-heluo-gua: 6 rows (20.5 px, gap 3), each padding 2 5: 纳甲 56 px right-aligned 12 px | 60 × 8 bar | 爻位 11 px
  [...guaEl.querySelectorAll('.horosa-heluo-yaorow')].forEach((row, i) => {
    const y = top + i * 23.5;
    if (cls(row).includes('is-yuan')) {
      out.push(`<rect x="${X0}" y="${y}" width="198" height="20.5" rx="4" fill="${C.accentSoft}" stroke="${C.accent}" stroke-width="1"/>`);
    }
    const najia = row.querySelector('.horosa-heluo-najia');
    const sy = najia.querySelector('.horosa-heluo-shiying');
    const right = X0 + 5 + 56;
    if (sy) {
      const mark = sy.textContent.trim();
      out.push(tx(right, y + 10.25, mark, 12, C.accentStrong, 700, 'end'));
      out.push(tx(right - cnxWidth(` ${mark}`, 12), y + 10.25, own(najia), 12, C.secondary, 400, 'end'));
    } else out.push(tx(right, y + 10.25, own(najia), 12, C.secondary, 400, 'end'));
    const bx = X0 + 5 + 56 + 8;
    const bar = row.querySelector('.horosa-heluo-bar');
    if (cls(bar).includes('yang')) out.push(`<rect x="${bx}" y="${y + 6.25}" width="60" height="8" rx="2" fill="${C.text}" stroke="none"/>`);
    else {
      out.push(`<rect x="${bx}" y="${y + 6.25}" width="26" height="8" rx="2" fill="${C.text}" stroke="none"/>`);
      out.push(`<rect x="${bx + 34}" y="${y + 6.25}" width="26" height="8" rx="2" fill="${C.text}" stroke="none"/>`);
    }
    out.push(tx(bx + 60 + 8, y + 10.25, txt(row.querySelector('.horosa-heluo-yaolabel')), 11, C.soft, 400, 'start'));
  });
  return 6 * 20.5 + 5 * 3;
}

function tags(out, el, x, top, width) {
  // flex-wrap, gap 5; tag 11 px, padding 1 7, border 1, radius 9, 19 px tall
  const none = el.querySelector('.horosa-heluo-tag-none');
  if (none) {
    out.push(tx(x, top + 8.5, none.textContent, 12, C.soft, 400, 'start'));
    return 17;
  }
  let cx = x;
  let row = 0;
  for (const tag of el.querySelectorAll('.horosa-heluo-tag')) {
    const c = cls(tag);
    const text = tag.textContent;
    const w = cnxWidth(text, 11) + 16;
    if (cx > x && cx + w > x + width) { cx = x; row += 1; }
    const y = top + row * 24;
    const rel = c.includes('is-rel');
    const fan = c.includes('is-fan');
    const fill = rel ? C.accent : (fan ? 'none' : C.accentSoft);
    const stroke = rel ? 'none' : C.accent;
    out.push(`<g${fan ? ' opacity="0.82"' : ''}><rect x="${cx + 0.5}" y="${y + 0.5}" width="${w - 1}" height="18" rx="9" fill="${fill}" stroke="${stroke}" stroke-width="1"${fan ? ' stroke-dasharray="3,2"' : ''}/>`
      + `${tx(cx + w / 2, y + 9.5, text, 11, rel ? C.onAccent : C.accentStrong, rel ? 600 : 400)}</g>`);
    cx += w + 5;
  }
  return (row + 1) * 19 + row * 5;
}

function yaoci(out, el, top) {
  if (!el) return 0;
  if (!has(el, 'horosa-heluo-yaoci')) {
    // （空爻·无条文）: a lone .horosa-heluo-yaoci-detail line
    out.push(tx(X0, top + 13.65, el.textContent, 14, C.text, 400, 'start'));
    return 27.3;
  }
  let y = top;
  const head = el.querySelector('.horosa-heluo-yaoci-head');
  // head: 14 px 700 accent-strong (20 px line) — 卦 · 爻, verdict pill (margin-left 8), relation in 12 px 600
  const name = own(head).trim();
  let hx = X0;
  out.push(tx(hx, y + 10, name, 14, C.accentStrong, 700, 'start'));
  hx += cnxWidth(name, 14) + 8;
  const v = head.querySelector('.horosa-heluo-verdict');
  hx += verdict(out, hx, y + 10, v ? v.textContent : '');
  const rel = head.querySelector('.horosa-heluo-yaoci-rel');
  if (rel) out.push(tx(hx, y + 10, rel.textContent, 12, C.accentStrong, 600, 'start'));
  y += 20;
  for (const block of [...el.children].slice(1)) {
    const b = block.querySelector('b');
    const label = b ? b.textContent : '';
    const body = own(block);
    y += 10;
    if (has(block, 'horosa-heluo-yaoci-yaoci')) {
      // boxed: padding 8 12, surface, 3 px accent-soft left rule, radius 6
      const lines = wrap(body, 14, INNER - 27, INNER - 27 - (cnxWidth(label, 12) + 24));
      const h = 16 + lines.length * 27.3;
      out.push(`<rect x="${X0}" y="${y}" width="${INNER}" height="${h}" rx="6" fill="${C.surface}" stroke="none"/>`);
      out.push(`<rect x="${X0}" y="${y}" width="3" height="${h}" fill="${C.accentSoft}" stroke="none"/>`);
      const lx = X0 + 15;
      const off = pill(out, lx, y + 8 + 13.65, label);
      lines.forEach((l, i) => out.push(tx(i ? lx : lx + off, y + 8 + 13.65 + i * 27.3, l, 14, C.text, 400, 'start')));
      y += h;
      continue;
    }
    // 摘要 / 诗歌 (white-space: pre-line) / 易经爻辞推命 (secondary colour): 14 px, line-height 27.3, pill inline first
    const color = has(block, 'horosa-heluo-yaoci-simple') ? C.secondary : C.text;
    const off = cnxWidth(label, 12) + 24;
    const lines = [];
    body.split('\n').forEach((part, i) => {
      const room = i === 0 ? INNER - off : INNER;
      wrap(part, 14, INNER, room).forEach((l, j) => lines.push({ text: l, x: i === 0 && j === 0 ? X0 + off : X0 }));
    });
    pill(out, X0, y + 13.65, label);
    lines.forEach((l, i) => out.push(tx(l.x, y + 13.65 + i * 27.3, l.text, 14, color, 400, 'start')));
    y += lines.length * 27.3;
  }
  return y - top;
}

function partGua(doc, out, index) {
  const el = doc.querySelectorAll('.horosa-heluo-guacard')[index];
  const top = 4;
  const inner = [];
  let y = top + 13 + heading(inner, top + 13, txt(el.querySelector('.horosa-huangji-info-heading')));
  const headTop = y;
  const guaH = yaoRows(inner, el.querySelector('.horosa-heluo-gua'), headTop);
  // meta column: 198 px gua + 20 px gap → x + 218, 516 px wide
  const mx = X0 + 218;
  const mw = INNER - 218;
  const meta = el.querySelector('.horosa-heluo-guameta');
  const nameEl = meta.querySelector('.horosa-heluo-guaname');
  const name = own(nameEl);
  inner.push(tx(mx, headTop + 12, name, 17, C.text, 700, 'start'));
  const v = nameEl.querySelector('.horosa-heluo-verdict');
  verdict(inner, mx + cnxWidth(name, 17) + 8, headTop + 14, v ? v.textContent : '');
  let my = headTop + 24;
  const line = (sel, size, color, weight, mt, lh) => {
    const node = meta.querySelector(sel);
    if (!node) return;
    my += mt;
    wrap(node.textContent, size, mw).forEach((l) => { inner.push(tx(mx, my + lh / 2, l, size, color, weight, 'start')); my += lh; });
  };
  line('.horosa-heluo-yuanyao', 13, C.secondary, 400, 3, 19);
  line('.horosa-heluo-wangshuai', 12, C.accentStrong, 600, 3, 17);
  line('.horosa-heluo-gist', 13, C.soft, 400, 4, 19);
  line('.horosa-heluo-dui', 12, C.secondary, 400, 5, 17);
  my += 6;
  my += tags(inner, meta.querySelector('.horosa-heluo-tags'), mx, my, mw);
  y = Math.max(headTop + guaH, my);
  const yc = [...el.children].find((c) => has(c, 'horosa-heluo-yaoci') || has(c, 'horosa-heluo-yaoci-detail'));
  if (yc) y += 12 + yaoci(inner, yc, y + 12);
  const h = y - top + 12;
  card(out, top, h);
  out.push(...inner);
  return top + h;
}

function partDaxian(doc, out) {
  const cards = [...doc.querySelectorAll('.horosa-huangji-info-card')].filter((c) => !has(c, 'horosa-heluo-guacard'));
  const el = cards[cards.length - 1];
  const top = 4;
  const inner = [];
  const title = txt(el.querySelector('.horosa-huangji-info-heading')).replace(/\s*·\s*点行.*$/, '');
  let y = top + 13 + heading(inner, top + 13, title);
  // table: border-collapse, 1 px border-soft; th surface / secondary / 500, td text; 13 px, padding 6 10, rows 31.5 px.
  // The browser's auto layout gave 年龄 160 / 卦 195 / 动爻 125.5 / 阴阳·吉凶 205.6 (+ 47 for the ▾ column, dropped);
  // the four columns keep those proportions across the card.
  const table = el.querySelector('table');
  const head = [...table.querySelectorAll('thead th')].map(txt).filter((t) => t.trim());
  const rows = [...table.querySelectorAll('tbody tr')].map((tr) => [...tr.querySelectorAll('td')].filter((td) => !cls(td).includes('arrowcell')).map(txt));
  const prop = [160.1, 194.9, 125.5, 205.6];
  const total = prop.reduce((a, b) => a + b, 0);
  const widths = head.map((_h, i) => (prop[i] || prop[prop.length - 1]) * INNER / total);
  const rowH = 31.5;
  const xs = widths.reduce((acc, w) => [...acc, acc[acc.length - 1] + w], [X0]);
  [head, ...rows].forEach((cells, r) => {
    const ry = y + r * rowH;
    if (r === 0) inner.push(`<rect x="${X0}" y="${ry}" width="${INNER}" height="${rowH}" fill="${C.surface}" stroke="none"/>`);
    cells.forEach((cell, i) => inner.push(tx(xs[i] + 10, ry + rowH / 2, cell, 13, r === 0 ? C.secondary : C.text, r === 0 ? 500 : 400, 'start')));
  });
  const th = (rows.length + 1) * rowH;
  for (let r = 0; r <= rows.length + 1; r += 1) inner.push(`<line x1="${X0}" y1="${y + r * rowH}" x2="${X0 + INNER}" y2="${y + r * rowH}" stroke="${C.borderSoft}" stroke-width="1"/>`);
  xs.forEach((x) => inner.push(`<line x1="${x}" y1="${y}" x2="${x}" y2="${y + th}" stroke="${C.borderSoft}" stroke-width="1"/>`));
  y += th;
  const h = y - top + 12;
  card(out, top, h);
  out.push(...inner);
  return top + h;
}

export function renderHeluo(data, options = {}) {
  const h = data && data.heluo;
  const ctx = h && h.board_context;
  if (!h || !h.chart || !h.dayun || !h.judge || !ctx || !ctx.extras) {
    throw new Error('heluo: needs heluo.chart / dayun / judge and board_context (nayin, extras) from the engine result');
  }
  const norm = (data && data.input_normalized) || {};
  // HeLuoMain.getModel()'s m, every member taken from the run
  const opts = {};
  for (const key of ['ziShuMode', 'jiGongMode', 'zhiZunEnabled', 'pureGanKunVariant', 'liunianStep2', 'huangdiOffset']) {
    if (norm[key] !== undefined) opts[key] = norm[key];
  }
  const m = {
    fourPillars: h.fourPillars, monthZhi: h.monthZhi, hourZhi: h.hourZhi, birthYear: h.birthYear, gender: h.gender,
    chart: h.chart, dy: h.dayun, jg: h.judge, st: h.solarTerm, nayin: ctx.nayin, extras: ctx.extras, opts,
  };
  const view = Object.create(HeLuoMain.prototype);
  view.state = { daxianKey: '', openYao: '', liunianKey: '', liuyueKey: '', yearForMonth: null, monthForDay: null, openJing: '' };
  view.props = { slot: 'center', quHuaGong: norm.quHuaGong, opts };
  const html = renderToStaticMarkup(createElement(Fragment, null, view.renderCenter(m)));
  const doc = new DOMParser().parseFromString(`<!doctype html><html><body>${html}</body></html>`, 'text/html');
  const out = [];
  const part = options.part || 'detail';
  let bottom;
  if (part === 'detail') bottom = partDetail(doc, out);
  else if (part === 'xian') bottom = partGua(doc, out, 0);
  else if (part === 'hou') bottom = partGua(doc, out, 1);
  else if (part === 'daxian') bottom = partDaxian(doc, out);
  else throw new Error(`heluo: unknown part ${part}`);
  const H = Math.ceil(bottom + 4);
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">${out.join('')}</svg>`;
  return { svg, width: W, height: H, themeScope: 'horosa-huangji-redesign' };
}
