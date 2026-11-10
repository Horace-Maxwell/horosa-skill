// 三式合一 — the app's board (components/sanshi/SanshiUnitedBoard.js) is a hybrid: an SVG ring background plus HTML layers
// (outer houses / stars by branch, 六壬 天盘 + 天将 marks, 奇门 palace blocks, the 四课 / 三传 centre) positioned with inline
// percentages, px and calc() and styled by a CSS-module stylesheet (SanShiUnitedMain.less; the build resolves its class
// names to the plain rule names). We render the component with the app's own code (SSR) from the run's own pieces — the
// cast chart (board_context.chart, the runner's /chart), the 奇门 pan, the 六壬 layout / 课 / 三传 / 农历 and the display
// solar time — and lay the markup out as SVG: inline geometry resolved against its containing box, colours / weights /
// borders from the stylesheet rules, the board at 720 px (the page's design size), the info cards above and below it.
import { createElement, Fragment } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { DOMParser } from 'linkedom';
import SanshiUnitedBoard from '@horosa-app/components/sanshi/SanshiUnitedBoard.js';
import { cnxText as tx, cnxWidth } from './cnxkit.js';

const B = 720;
const TEXT = 'var(--horosa-text, #262626)';
const SOFT = 'var(--horosa-text-soft, #595959)';
const MUTED = 'var(--horosa-muted, #8c8c8c)';
const BORDER = 'var(--horosa-border, #e5e0d5)';
const BORDER_STRONG = 'var(--horosa-border-strong, #d9cdb4)';
const GOLD = 'var(--horosa-gold, #9a6a25)';
const FILLS = {
  fillOuterRing: 'var(--horosa-sanshi-board-outer, #f7f4ec)', fillQimenRing: 'var(--horosa-sanshi-board-qimen, #efebe2)',
  fillLiurengRing: 'var(--horosa-sanshi-board-liureng, #e3ded3)', fillCenter: 'var(--horosa-sanshi-board-center, #cfcac0)',
};
const cls = (el) => (el && el.getAttribute('class')) || '';
const styleOf = (el) => {
  const out = {};
  `${(el && el.getAttribute('style')) || ''}`.split(';').forEach((d) => { const i = d.indexOf(':'); if (i > 0) out[d.slice(0, i).trim()] = d.slice(i + 1).trim(); });
  return out;
};
// CSS length → px against a reference size: px, %, calc(a% + b px − c px …), bare numbers
function len(value, ref) {
  if (value == null || value === '') return null;
  let v = `${value}`.trim();
  const calc = v.match(/^calc\((.*)\)$/);
  if (calc) v = calc[1];
  let total = 0;
  let sign = 1;
  for (const tok of v.replace(/\s*([+-])\s*/g, ' $1 ').trim().split(/\s+/)) {
    if (tok === '+') { sign = 1; continue; }
    if (tok === '-') { sign = -1; continue; }
    const m = tok.match(/^(-?[\d.]+)(px|%)?$/);
    if (!m) continue;
    total += sign * (m[2] === '%' ? Number(m[1]) * ref / 100 : Number(m[1]));
    sign = 1;
  }
  return total;
}
function translate(transform, w, h) {
  const m = `${transform || ''}`.match(/translate(X|Y)?\((.*)\)$/);
  if (!m) return [0, 0];
  const parts = m[2].split(/,(?![^(]*\))/).map((p) => p.trim());
  if (m[1] === 'X') return [len(parts[0], w) || 0, 0];
  if (m[1] === 'Y') return [0, len(parts[0], h) || 0];
  return [len(parts[0], w) || 0, len(parts[1] || '0', h) || 0];
}
const textOf = (el) => (el ? el.textContent : '');

function svgPart(out, svg) {
  const s = B / 1000;
  for (const el of svg.children) {
    const c = cls(el);
    const fill = FILLS[c];
    const stroke = c === 'strokeMain' ? [BORDER, 3] : (c === 'strokeSub' ? [BORDER, 1.8] : null);
    const paint = fill ? `fill="${fill}" stroke="none"` : `fill="none" stroke="${stroke ? stroke[0] : BORDER}" stroke-width="${(stroke ? stroke[1] : 1) * s}"`;
    if (el.tagName === 'RECT' || el.tagName === 'rect') {
      const g = (k) => Number(el.getAttribute(k)) * s;
      out.push(`<rect x="${g('x')}" y="${g('y')}" width="${g('width')}" height="${g('height')}" ${paint}/>`);
    } else {
      const g = (k) => Number(el.getAttribute(k)) * s;
      out.push(`<line x1="${g('x1')}" y1="${g('y1')}" x2="${g('x2')}" y2="${g('y2')}" ${paint}/>`);
    }
  }
}

function outerCell(out, cell, ox, oy) {
  const st = styleOf(cell);
  const cx = ox + len(st.left, B);
  const cy = oy + len(st.top, B);
  const cw = len(st.width, B);
  const chh = len(st.height, B);
  for (const child of cell.children) {
    const c = cls(child);
    const s = styleOf(child);
    if (c.includes('outerLabel')) {
      const fs = parseFloat(s['font-size']) || 18;
      const lh = parseFloat(s['line-height']) || fs;
      const house = c.includes('outerHouse');
      const y = s.top != null ? cy + len(s.top, chh) + lh / 2 : cy + chh - len(s.bottom, chh) - lh / 2;
      if (s.left != null) out.push(tx(cx + len(s.left, cw), y, textOf(child), fs, house ? TEXT : MUTED, house ? 700 : 500, 'start'));
      else out.push(tx(cx + cw - len(s.right, cw), y, textOf(child), fs, house ? TEXT : MUTED, house ? 700 : 500, 'end'));
    } else if (c.includes('outerWeakSolid')) {
      const dot = child.querySelector('.outerWeakSolidDot');
      const ds = styleOf(dot);
      const d = parseFloat(ds.width) || 5;
      const x = s.left != null ? cx + len(s.left, cw) + d / 2 : cx + cw - len(s.right, cw) - d / 2;
      const y = s.top != null ? cy + len(s.top, chh) + d / 2 : cy + chh - len(s.bottom, chh) - d / 2;
      out.push(`<circle cx="${x}" cy="${y}" r="${d / 2}" fill="${ds.background || '#008000'}" stroke="rgba(255, 255, 255, 0.55)" stroke-width="1"/>`);
    } else if (c.includes('outerStars')) {
      const fs = parseFloat(s['font-size']) || 18;
      const lh = parseFloat(s['line-height']) || fs;
      const rows = [...child.querySelectorAll('.outerStarsRow')].map((row) => {
        const items = [...row.querySelectorAll('.outerStarItem')].map((it) => ({ text: textOf(it), hidden: cls(it).includes('outerStarPlaceholder'), w: Math.max(1.8 * fs, cnxWidth(textOf(it), fs)) }));
        const w = items.reduce((a, it) => a + it.w, 0) + Math.max(0, items.length - 1) * 5;
        return { items, w, justify: styleOf(row)['justify-content'] || 'center' };
      });
      const W = Math.max(0, ...rows.map((r) => r.w));
      const H = rows.length * lh;
      const [dx, dy] = translate(s.transform, W, H);
      let x0 = s.left != null ? cx + len(s.left, cw) : cx + cw - len(s.right, cw) - W;
      let y0 = s.top != null ? cy + len(s.top, chh) : cy + chh - len(s.bottom, chh) - H;
      x0 += dx; y0 += dy;
      rows.forEach((row, r) => {
        let x = row.justify === 'flex-end' ? x0 + W - row.w : (row.justify === 'flex-start' ? x0 : x0 + (W - row.w) / 2);
        row.items.forEach((it) => {
          if (!it.hidden) out.push(tx(x + it.w / 2, y0 + r * lh + lh / 2, it.text, fs, MUTED, 400));
          x += it.w + 5;
        });
      });
    }
  }
}

function lrMark(out, el, ox, oy) {
  const s = styleOf(el);
  const fs = parseFloat(s['font-size']) || 22;
  const w = cnxWidth(textOf(el), fs);
  const [dx, dy] = translate(s.transform || 'translate(-50%, -50%)', w, fs);
  const x = ox + len(s.left, B) + dx + w / 2;
  const y = oy + len(s.top, B) + dy + fs / 2;
  out.push(tx(x, y, textOf(el), fs, SOFT, 700));
}

function qmBlock(out, el, ox, oy) {
  const s = styleOf(el);
  const corner = cls(el).includes('qmBlockCorner');
  const size = (corner ? 11.2 : 11) * B / 100;
  const x = ox + len(s.left, B) - size / 2;
  const y = oy + len(s.top, B) - size / 2;
  const inset = corner ? -1 : 0;
  out.push(`<rect x="${x + inset}" y="${y + inset}" width="${size - inset * 2}" height="${size - inset * 2}" fill="${FILLS.fillLiurengRing}" stroke="${FILLS.fillLiurengRing}" stroke-width="1.6"/>`);
  const glyph = (sel, anchor, top, color) => {
    const g = el.querySelector(sel);
    if (!g) return;
    const fs = parseFloat(styleOf(g)['font-size']) || 22;
    const gx = anchor === 'start' ? x + 1 : x + size - 1;
    const gy = top ? y + 1 + fs / 2 : y + size - 1 - fs / 2;
    out.push(tx(gx, gy, textOf(g), fs, color, 700, anchor));
  };
  glyph('.qmTianGan', 'start', true, TEXT);
  glyph('.qmGod', 'end', true, TEXT);
  glyph('.qmDiGan', 'start', false, MUTED);
  glyph('.qmStar', 'end', false, TEXT);
  const box = el.querySelector('.qmDoorBox');
  if (box) {
    const bs = styleOf(box);
    const bw = parseFloat(bs.width) || 26;
    const bh = parseFloat(bs.height) || 26;
    out.push(`<rect x="${x + size / 2 - bw / 2}" y="${y + size / 2 - bh / 2}" width="${bw}" height="${bh}" fill="${SOFT}" stroke="${SOFT}" stroke-width="${parseFloat(bs['border-width']) || 1.6}"/>`);
    const door = box.querySelector('.qmDoor');
    const fs = parseFloat(styleOf(door)['font-size']) || 18;
    out.push(tx(x + size / 2, y + size / 2, textOf(door), fs, 'var(--horosa-surface-solid, #fff)', 700));
  }
}

function centerBlock(out, el, ox, oy) {
  const s = styleOf(el);
  const size = 33.4 * B / 100;
  const x = ox + len(s.left, B) - size / 2;
  const y = oy + len(s.top, B) - size / 2;
  const ke = el.querySelector('.centerKe');
  if (ke) {
    const ks = styleOf(ke);
    const fs = parseFloat(ks['font-size']) || 22;
    const lh = parseFloat(ks['line-height']) || fs * 1.05;
    let colX = x + 2;
    for (const col of ke.querySelectorAll('.centerKeCol')) {
      const cw = Math.max(1.02 * fs, fs);
      [...col.children].forEach((cell, r) => out.push(tx(colX + cw / 2, y + 2 + r * lh + lh / 2, textOf(cell), fs, cls(cell).includes('Gray') ? MUTED : TEXT, 700)));
      colX += cw + 1;
    }
  }
  const chuan = el.querySelector('.centerChuan');
  if (chuan) {
    const cs = styleOf(chuan);
    const fs = parseFloat(cs['font-size']) || 22;
    const lh = parseFloat(cs['line-height']) || fs * 1.05;
    const rows = [...chuan.querySelectorAll('.centerChuanRow')];
    const cw = 1.02 * fs;
    rows.forEach((row, r) => {
      const top = y + size - 2 - (rows.length - r) * lh;
      [...row.children].forEach((cell, k) => {
        out.push(tx(x + size - 2 - (3 - k) * cw + cw / 2, top + lh / 2, textOf(cell), fs, cls(cell).includes('Gray') ? MUTED : TEXT, 700));
      });
    });
  }
}

function topBox(out, top, y0) {
  // .topBox: 1px border, radius 10, padding 4 / 6, grid 1fr 164px gap 6
  const rightW = 164;
  const leftW = B - 12 - 6 - rightW;
  const x0 = 6;
  let y = y0 + 4;
  // date panel: two 31 px rows, label column 54
  const rows = [...top.querySelectorAll('.dateRow')];
  out.push(`<rect x="${x0 + 0.5}" y="${y + 0.5}" width="${leftW - 1}" height="${rows.length * 31 - 1}" rx="8" fill="none" stroke="${BORDER}" stroke-width="1"/>`);
  rows.forEach((row, i) => {
    const ry = y + i * 31;
    if (i) out.push(`<line x1="${x0}" y1="${ry + 0.5}" x2="${x0 + leftW}" y2="${ry + 0.5}" stroke="${BORDER}" stroke-width="1"/>`);
    out.push(`<line x1="${x0 + 54.5}" y1="${ry}" x2="${x0 + 54.5}" y2="${ry + 31}" stroke="${BORDER}" stroke-width="1"/>`);
    out.push(tx(x0 + 27, ry + 15.5, textOf(row.querySelector('.dateLabel')), 13, SOFT));
    out.push(tx(x0 + 54 + 9, ry + 15.5, textOf(row.querySelector('.dateMainText')), 15, TEXT, 600, 'start'));
    const meta = `${textOf(row.querySelector('.dateMetaLabel'))} ${textOf(row.querySelector('.dateMetaValue'))}`;
    out.push(tx(x0 + leftW - 9, ry + 15.5, meta, 12, MUTED, 500, 'end'));
  });
  y += rows.length * 31 + 6;
  // pillar area: grid 1fr 118 gap 6 — four pillar boxes (66) + tag dots (24), then the 月将 / 年命 pairs
  const metaW = 118;
  const pillarsW = leftW - 6 - metaW;
  const pw = (pillarsW - 15) / 4;
  [...top.querySelectorAll('.pillarBox')].forEach((box, i) => {
    const px = x0 + i * (pw + 5);
    out.push(`<rect x="${px + 0.5}" y="${y + 0.5}" width="${pw - 1}" height="65" rx="8" fill="rgba(0, 0, 0, 0.02)" stroke="${BORDER}" stroke-width="1"/>`);
    out.push(tx(px + pw / 2, y + 33 - 10, textOf(box.querySelector('.pillarGan')), 18, TEXT, 700));
    out.push(tx(px + pw / 2, y + 33 + 10, textOf(box.querySelector('.pillarZhi')), 18, SOFT, 700));
  });
  [...top.querySelectorAll('.pillarTagDot')].forEach((dot, i) => {
    const cx = x0 + i * (pw + 5) + pw / 2;
    out.push(`<circle cx="${cx}" cy="${y + 66 + 4 + 12}" r="11.5" fill="var(--horosa-panel-soft, #f3efe6)" stroke="${BORDER}" stroke-width="1"/>`);
    out.push(tx(cx, y + 66 + 4 + 12, textOf(dot), 13, GOLD, 600));
  });
  const pairs = [...top.querySelectorAll('.metaPair')];
  const mw = (metaW - 5) / 2;
  pairs.forEach((pair, i) => {
    const mx = x0 + pillarsW + 6 + i * (mw + 5);
    out.push(`<rect x="${mx + 0.5}" y="${y + 0.5}" width="${mw - 1}" height="${45 - 1}" rx="8" fill="var(--horosa-panel-soft, #f3efe6)" stroke="${BORDER}" stroke-width="1"/>`);
    out.push(tx(mx + mw / 2, y + 22.5, textOf(pair.querySelector('.metaTitle')), 13, SOFT));
    out.push(`<rect x="${mx + 0.5}" y="${y + 48 + 0.5}" width="${mw - 1}" height="${45 - 1}" rx="8" fill="rgba(0, 0, 0, 0.02)" stroke="${BORDER}" stroke-width="1"/>`);
    out.push(tx(mx + mw / 2, y + 48 + 22.5, textOf(pair.querySelector('.metaValue')), 13, TEXT, 600));
  });
  const leftBottom = y + 94;
  // 神煞 box (right): two columns × six 28 px rows
  const items = [...top.querySelectorAll('.ssItem')];
  const values = [...top.querySelectorAll('.ssValue')];
  const sx = x0 + leftW + 6;
  const sy = y0 + 4;
  out.push(`<rect x="${sx + 0.5}" y="${sy + 0.5}" width="${rightW - 1}" height="${items.length * 28 - 1}" rx="8" fill="none" stroke="${BORDER_STRONG}" stroke-width="1"/>`);
  out.push(`<line x1="${sx + rightW / 2}" y1="${sy}" x2="${sx + rightW / 2}" y2="${sy + items.length * 28}" stroke="${BORDER}" stroke-width="1"/>`);
  items.forEach((it, i) => {
    if (i) out.push(`<line x1="${sx}" y1="${sy + i * 28 + 0.5}" x2="${sx + rightW}" y2="${sy + i * 28 + 0.5}" stroke="${BORDER}" stroke-width="1"/>`);
    out.push(tx(sx + rightW / 4, sy + i * 28 + 14, textOf(it), 12, SOFT));
    out.push(tx(sx + rightW * 3 / 4, sy + i * 28 + 14, textOf(values[i]), 12, TEXT, 600));
  });
  const bottom = Math.max(leftBottom, sy + items.length * 28) + 4;
  out.unshift(`<rect x="0.5" y="${y0 + 0.5}" width="${B - 1}" height="${bottom - y0 - 1}" rx="10" fill="none" stroke="${BORDER}" stroke-width="1"/>`);
  return bottom;
}

function bottomBox(out, box, y0) {
  // .bottomBox: grid 1fr 94px gap 8 — 2 × 2 cells (min-height 40) + 阳遁 / 局 column
  const rightW = 94;
  const gw = B - 8 - rightW;
  const cells = [...box.querySelectorAll('.bottomCell')];
  const ch = 40;
  out.push(`<rect x="0.5" y="${y0 + 0.5}" width="${gw - 1}" height="${ch * 2 - 1}" rx="8" fill="none" stroke="${BORDER_STRONG}" stroke-width="1"/>`);
  out.push(`<line x1="${gw / 2}" y1="${y0}" x2="${gw / 2}" y2="${y0 + ch * 2}" stroke="${BORDER}" stroke-width="1"/>`);
  out.push(`<line x1="0" y1="${y0 + ch + 0.5}" x2="${gw}" y2="${y0 + ch + 0.5}" stroke="${BORDER}" stroke-width="1"/>`);
  cells.forEach((cell, i) => {
    const cx = (i % 2) * (gw / 2);
    const cy = y0 + Math.floor(i / 2) * ch + ch / 2;
    out.push(tx(cx + 10, cy, textOf(cell.querySelector('span')), 16, SOFT, 400, 'start'));
    out.push(tx(cx + gw / 2 - 10, cy, textOf(cell.querySelector('b')), 16, TEXT, 700, 'end'));
  });
  const parts = [...box.querySelectorAll('.bottomRight > div')];
  const rx = gw + 8;
  out.push(`<rect x="${rx + 0.5}" y="${y0 + 0.5}" width="${rightW - 1}" height="${ch * 2 - 1}" rx="8" fill="none" stroke="${BORDER}" stroke-width="1"/>`);
  parts.forEach((p, i) => {
    if (i) out.push(`<line x1="${rx}" y1="${y0 + ch + 0.5}" x2="${rx + rightW}" y2="${y0 + ch + 0.5}" stroke="${BORDER}" stroke-width="1"/>`);
    out.push(tx(rx + rightW / 2, y0 + i * ch + ch / 2, textOf(p), 20, TEXT, 600));
  });
  return y0 + ch * 2;
}

export function renderSanshi(data) {
  const ctx = data && data.board_context;
  if (!ctx || !ctx.chart || !Array.isArray(ctx.chart.objects) || !data.qimen || !data.liureng || !data.liureng.layout) {
    throw new Error('sanshi: needs board_context.chart, qimen and liureng.layout');
  }
  const fields = ctx.date && ctx.time ? {
    date: { value: { format: () => `${ctx.date}`.replace(/\//g, '-') } },
    time: { value: { format: (f) => `${ctx.time}`.slice(0, f === 'HH:mm' ? 5 : 8) } },
  } : null;
  const html = renderToStaticMarkup(createElement(Fragment, null, createElement(SanshiUnitedBoard, {
    chartWrap: { chart: ctx.chart }, dunjia: data.qimen, lrLayout: data.liureng.layout, keData: { raw: data.liureng.ke || [] },
    sanChuan: data.liureng.sanChuan, nongli: data.liureng.nongli, liureng: data.liureng, fields,
    displaySolarTime: data.displaySolarTime, boardSize: B,
  })));
  const doc = new DOMParser().parseFromString(`<!doctype html><html><body>${html}</body></html>`, 'text/html');
  const out = [];
  let y = 0;
  const top = doc.querySelector('.topBox');
  if (top) y = topBox(out, top, 0) + 8;
  const boardTop = y;
  const svg = doc.querySelector('.boardSvg');
  const board = [];
  if (svg) svgPart(board, svg);
  const layer = doc.querySelector('.boardLayer');
  if (layer) {
    for (const el of layer.children) {
      const c = cls(el);
      if (c.includes('outerCell')) outerCell(board, el, 0, 0);
      else if (c.includes('lrMark')) lrMark(board, el, 0, 0);
      else if (c.includes('qmBlock') && el.querySelector('.centerKe, .centerChuan')) centerBlock(board, el, 0, 0);
      else if (c.includes('qmBlock')) qmBlock(board, el, 0, 0);
    }
  }
  out.push(`<g transform="translate(0,${boardTop})">${board.join('')}<rect x="0.5" y="0.5" width="${B - 1}" height="${B - 1}" fill="none" stroke="${BORDER}" stroke-width="1"/></g>`);
  y = boardTop + B + 8;
  const bottom = doc.querySelector('.bottomBox');
  if (bottom) y = bottomBox(out, bottom, y);
  const H = Math.ceil(y + 2);
  const svgOut = `<svg xmlns="http://www.w3.org/2000/svg" width="${B}" height="${H}" viewBox="0 0 ${B} ${H}">${out.join('')}</svg>`;
  return { svg: svgOut, width: B, height: H };
}
