// 五兆 — the page's default centre view is the 兆图 (WuZhaoMain centerView 'board' → <WuZhaoBoard positions classic beastView>),
// HTML styled by layouts/app/10-huangji-wuzhao.less. The run's raw is the kentang pan the page holds; wuzhaoDisplayPan(pan)
// gives positions / classic exactly as the page does; WuZhaoBoard renders with the app's own code (SSR; the only change is
// unwrapping the hover Popover its ring cells sit in — antd is a stub here) and the markup is laid out as SVG on the
// stylesheet's grid: columns 0.6fr · 1fr × 3 · 0.6fr, rows 0.5fr · 1fr × 3 · 0.5fr, gap 5; twelve branch cells round the edge
// (15 px branch, 9 px 神煞 / 行神 / 空亡 badges, dashed when 空亡), six 乡 / 支 cells inside (宫 11 px + 位名 14 px; 乡 and 支
// columns: 纳甲, 五行 17 px in the 八字 element colours, role, 六神 / 数; tags 10 px), then the 旬 / 纳甲 band.
import { createElement, Fragment } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { DOMParser } from 'linkedom';
import WuZhaoBoard from '@horosa-app/components/wuzhao/WuZhaoBoard.js';
import { wuzhaoDisplayPan } from '@horosa-app/components/wuzhao/wuzhaoDisplay.js';
import { cnxText as tx, cnxWidth, CNX } from './cnxkit.js';

class PrintWuZhaoBoard extends WuZhaoBoard {
  renderRingCell(item) {
    const el = super.renderRingCell(item);
    return el && el.props && el.props.getPopupContainer ? el.props.children : el; // drop the hover Popover wrapper
  }
}

const ELEM = { 'is-mu': 'var(--horosa-bazi-wood, #3f8f5a)', 'is-huo': 'var(--horosa-bazi-fire, #c72d22)', 'is-tu': 'var(--horosa-bazi-earth, #805526)', 'is-jin': 'var(--horosa-bazi-metal, #866a00)', 'is-shui': 'var(--horosa-bazi-water, #275fc7)' };
const BADGE_BG = { shensha: 'rgba(214, 167, 85, 0.16)', xingshen: 'rgba(110, 168, 214, 0.18)', kongwang: 'rgba(160, 160, 160, 0.18)', more: 'rgba(214, 167, 85, 0.16)' };
const TAG_BG = { 'is-ji': 'rgba(91, 171, 109, 0.2)', 'is-xiong': 'rgba(209, 104, 94, 0.2)', 'is-qi': 'rgba(214, 167, 85, 0.18)', 'is-xingshen': 'rgba(110, 168, 214, 0.18)', 'is-kong': 'rgba(160, 160, 160, 0.18)', 'is-flag': 'rgba(160, 160, 160, 0.18)' };
const SECONDARY = 'var(--horosa-text-secondary, #6b7280)';
const cls = (el) => (el && el.getAttribute('class')) || '';
const gridPos = (el) => { const s = el.getAttribute('style') || ''; return [Number((s.match(/grid-row:\s*(\d+)/) || [])[1]), Number((s.match(/grid-column:\s*(\d+)/) || [])[1])]; };

function pills(out, items, cx, y, size, maxW, center = true) {
  // flex-wrap rows of small pills; returns the height used
  const rows = [];
  items.forEach((it) => {
    const w = cnxWidth(it.text, size) + 6;
    const row = rows[rows.length - 1];
    if (row && row.w + 2 + w <= maxW) { row.items.push({ ...it, w }); row.w += 2 + w; } else rows.push({ items: [{ ...it, w }], w });
  });
  const lh = size * 1.6;
  rows.forEach((row, r) => {
    let x = center ? cx - row.w / 2 : cx;
    row.items.forEach((it) => {
      out.push(`<rect x="${x}" y="${y + r * (lh + 2)}" width="${it.w}" height="${lh}" rx="3" fill="${it.bg}" stroke="none"/>`);
      out.push(tx(x + it.w / 2, y + r * (lh + 2) + lh / 2, it.text, size, it.color || CNX.muted));
      x += it.w + 2;
    });
  });
  return rows.length ? rows.length * (lh + 2) - 2 : 0;
}

export function renderWuzhao(data) {
  const pan = wuzhaoDisplayPan(data && data.raw);
  if (!pan || !Array.isArray(pan.positions) || !pan.positions.length) throw new Error('wuzhao: needs raw.positions');
  const html = renderToStaticMarkup(createElement(Fragment, null, createElement(PrintWuZhaoBoard, { positions: pan.positions, classic: pan.classic || null, beastView: 'both' })));
  const doc = new DOMParser().parseFromString(`<!doctype html><html><body>${html}</body></html>`, 'text/html');
  const q = (sel, root = doc) => root.querySelector(sel);
  const W = 720;
  const GAP = 5;
  const fr = (W - GAP * 4) / 4.2;
  const colW = [0.6 * fr, fr, fr, fr, 0.6 * fr];
  const rowFr = 152;
  const rowH = [0.5 * rowFr, rowFr, rowFr, rowFr, 0.5 * rowFr];
  const colX = (c) => colW.slice(0, c).reduce((a, b) => a + b + GAP, 0);
  const rowY = (r) => rowH.slice(0, r).reduce((a, b) => a + b + GAP, 0);
  const out = [];
  for (const cell of doc.querySelectorAll('.horosa-wuzhao-ring-cell')) {
    const [r, c] = gridPos(cell);
    const x = colX(c - 1);
    const y = rowY(r - 1);
    const w = colW[c - 1];
    const h = rowH[r - 1];
    const kong = cls(cell).includes('is-kongwang');
    out.push(`<rect x="${x + 0.5}" y="${y + 0.5}" width="${w - 1}" height="${h - 1}" rx="6" fill="rgba(120, 96, 56, 0.05)" stroke="${CNX.line}" stroke-width="1"${kong ? ' stroke-dasharray="4,3"' : ''}/>`);
    const badges = [...cell.querySelectorAll('.horosa-wuzhao-ring-badges em')].map((em) => {
      const kind = (cls(em).match(/is-(\w+)/) || [])[1] || 'shensha';
      return { text: em.textContent, bg: BADGE_BG[kind] || BADGE_BG.shensha, color: kong ? SECONDARY : CNX.muted };
    });
    const bh = badges.length ? Math.ceil(badges.length / Math.max(1, Math.floor((w - 6) / 34))) * 16 : 0;
    const top = y + (h - (17 + (bh ? 2 + bh : 0))) / 2;
    out.push(tx(x + w / 2, top + 8.5, q('strong', cell).textContent, 15, kong ? SECONDARY : CNX.text, 700));
    if (badges.length) pills(out, badges, x + w / 2, top + 19, 9, w - 6);
  }
  for (const cell of doc.querySelectorAll('.horosa-wuzhao-cell')) {
    const [r, c] = gridPos(cell);
    const x = colX(c - 1);
    const y = rowY(r - 1);
    const w = colW[c - 1];
    const h = rowH[r - 1];
    const zhao = cls(cell).includes('is-zhao');
    out.push(`<rect x="${x + 0.5}" y="${y + 0.5}" width="${w - 1}" height="${h - 1}" rx="6" fill="rgba(255, 255, 255, 0.86)" stroke="${zhao ? 'rgba(214, 167, 85, 0.62)' : CNX.line}" stroke-width="${zhao ? 2 : 1}"/>`);
    const head = q('.horosa-wuzhao-cell-head', cell);
    out.push(tx(x + 9, y + 8 + 8, q('span', head).textContent, 11, CNX.muted, 400, 'start'));
    out.push(tx(x + w - 9, y + 8 + 8, q('b', head).textContent, 14, CNX.text, 600, 'end'));
    const cols = [q('.horosa-wuzhao-cell-xiang', cell), q('.horosa-wuzhao-cell-zhi', cell)].filter(Boolean);
    const colWd = (w - 18 - (cols.length - 1) * 8) / cols.length;
    let contentBottom = y + 30;
    cols.forEach((col, k) => {
      const cx0 = x + 9 + k * (colWd + 8);
      if (k > 0) out.push(`<line x1="${cx0 - 4.5}" y1="${y + 30}" x2="${cx0 - 4.5}" y2="${y + 30 + 62}" stroke="${CNX.line}" stroke-width="1" stroke-dasharray="3,2"/>`);
      let yy = y + 30;
      const najia = q('.horosa-wuzhao-najia', col);
      if (najia) { out.push(tx(cx0 + (k > 0 ? 4 : 0), yy + 7, najia.textContent, 10, CNX.muted, 400, 'start')); yy += 14; }
      const strong = q('strong', col);
      const elem = Object.keys(ELEM).find((key) => cls(strong).includes(key));
      out.push(tx(cx0 + (k > 0 ? 4 : 0), yy + 10, strong.textContent, 17, elem ? ELEM[elem] : CNX.text, 700, 'start'));
      yy += 21;
      const role = q('span', col);
      if (role && role.textContent) { out.push(tx(cx0 + (k > 0 ? 4 : 0), yy + 7.5, role.textContent, 11, CNX.muted, 400, 'start')); yy += 15; }
      const extra = q('i', col);
      if (extra) { out.push(tx(cx0 + (k > 0 ? 4 : 0), yy + 7, extra.textContent, 10, cls(extra).includes('beast') ? CNX.text : CNX.muted, 400, 'start', cls(extra).includes('beast') ? ' opacity="0.82"' : '')); yy += 14; }
      contentBottom = Math.max(contentBottom, yy);
    });
    const tags = [...cell.querySelectorAll('.horosa-wuzhao-cell-foot em')].map((em) => ({ text: em.textContent, bg: TAG_BG[Object.keys(TAG_BG).find((k) => cls(em).includes(k))] || 'rgba(120, 96, 56, 0.09)' }));
    if (tags.length) pills(out, tags, x + 9, contentBottom + 5, 10, w - 18, false); // foot: flows under the body (gap 5)
  }
  let y = rowY(5);
  const band = q('.horosa-wuzhao-najia-band');
  if (band) {
    // the page scrolls this band sideways; on paper it wraps (items keep their order)
    const title = q('.horosa-wuzhao-najia-title', band).textContent;
    const left = 9 + cnxWidth(title, 12) + 8;
    const items = [...band.querySelectorAll('.horosa-wuzhao-najia-item')].map((item) => {
      const s0 = q('strong', item).textContent;
      const em0 = q('em', item);
      return { item, w: Math.max(cnxWidth(s0, 11), em0 ? cnxWidth(em0.textContent, 9) : 0) + 10 };
    });
    let lines = 1;
    { let lx = left; items.forEach((it) => { if (lx + it.w > W - 9 && lx > left) { lines += 1; lx = left; } lx += it.w + 4; }); }
    const bh = 7 + lines * 30 + (lines - 1) * 4 + 7;
    out.push(`<rect x="0.5" y="${y + 6 + 0.5}" width="${W - 1}" height="${bh - 1}" rx="6" fill="none" stroke="${CNX.line}" stroke-width="1"/>`);
    out.push(tx(9, y + 6 + 7 + 15, title, 12, CNX.text, 600, 'start'));
    let x = left;
    let line = 0;
    for (const { item, w: iw0 } of items) {
      if (x + iw0 > W - 9 && x > left) { line += 1; x = left; }
      const yOff = line * 34;
      const s = q('strong', item).textContent;
      const em = q('em', item);
      const iw = iw0;
      const used = cls(item).includes('is-used');
      const kong = cls(item).includes('is-kongwang');
      if (used || kong) out.push(`<rect x="${x}" y="${y + 6 + 7 + yOff}" width="${iw}" height="30" rx="4" fill="${used ? 'rgba(214, 167, 85, 0.12)' : 'none'}" stroke="${used ? 'rgba(214, 167, 85, 0.5)' : CNX.line}" stroke-width="1"${kong ? ' stroke-dasharray="3,2"' : ''}/>`);
      out.push(tx(x + iw / 2, y + 6 + 7 + yOff + (em ? 9 : 15), s, 11, used ? CNX.text : (kong ? SECONDARY : CNX.muted)));
      if (em) out.push(tx(x + iw / 2, y + 6 + 7 + yOff + 22, em.textContent, 9, kong ? SECONDARY : CNX.muted));
      x += iw + 4;
    }
    y += 6 + bh;
  }
  const H = Math.ceil(y + 2);
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">${out.join('')}</svg>`;
  return { svg, width: W, height: H, themeScope: 'horosa-huangji-redesign' };
}
