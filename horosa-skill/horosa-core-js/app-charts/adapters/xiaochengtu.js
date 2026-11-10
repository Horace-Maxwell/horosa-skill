// 小成图 — the app's 洛书九宫 board (XiaoChengTuMain.renderCenter(pan) in the 卜 board language, .horosa-xct-page rules) is
// HTML. The run's result carries the page's qi (board_context: the 本卦 / 之卦 hexagram objects the text was built from — returned
// by the skill's own tools/xiaochengtu.js), so: qi → the app's buildPan → renderCenter with the app's own code (SSR on a bare
// instance; state = { settings.yongGong, qi } is all it reads), then the markup is laid out as SVG with the stylesheet's
// numbers — header (本卦 / 之卦 glyph pair 24 × 3 px bars, title 20 px, kicker, 用宫 badge), the 3 × 3 palaces (trigram glyph
// 30 × 4 px bars, name 36 px 800, 地盘 · 宫 13.5 px; 中宫 dashed; 用宫 / 推N badges), and the 推导 box under it.
import { createElement, Fragment } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { DOMParser } from 'linkedom';
import XiaoChengTuMain from '@horosa-app/components/xiaochengtu/XiaoChengTuMain.js';
import { buildPan } from '@horosa-app/components/xiaochengtu/core/xiaochengtuPan.js';
import { cnxText as tx, cnxWidth, CNX } from './cnxkit.js';

const SECONDARY = 'var(--horosa-text-secondary, #6b7280)';

function bars(out, x, y, lines, { w, h, gap, yinGap, color, opacity }) {
  lines.forEach((yang, i) => {
    const top = y + i * (h + gap);
    if (yang) out.push(`<rect x="${x - w / 2}" y="${top}" width="${w}" height="${h}" rx="1" fill="${color}" fill-opacity="${opacity}" stroke="none"/>`);
    else {
      const seg = (w - yinGap) / 2;
      out.push(`<rect x="${x - w / 2}" y="${top}" width="${seg}" height="${h}" fill="${color}" fill-opacity="${opacity}" stroke="none"/>`);
      out.push(`<rect x="${x + w / 2 - seg}" y="${top}" width="${seg}" height="${h}" fill="${color}" fill-opacity="${opacity}" stroke="none"/>`);
    }
  });
}
const linesOf = (el) => [...el.querySelectorAll('i')].map((i) => (i.getAttribute('class') || '').includes('is-yang'));

export function renderXiaochengtu(data) {
  const x0 = data && data.xiaochengtu;
  const ctx = x0 && x0.board_context;
  if (!ctx || !ctx.ben || !ctx.zhi) throw new Error('xiaochengtu: needs board_context.ben / zhi (hexagram objects)');
  const qi = { mode: x0.mode, ben: ctx.ben, zhi: ctx.zhi, dongYaos: x0.dongYaos || [] };
  const pan = buildPan(qi);
  if (!pan) throw new Error('xiaochengtu: the app built no pan');
  const view = Object.create(XiaoChengTuMain.prototype);
  view.state = { settings: { yongGong: x0.yongGong }, qi };
  view.props = {};
  const html = renderToStaticMarkup(createElement(Fragment, null, view.renderCenter(pan)));
  const doc = new DOMParser().parseFromString(`<!doctype html><html><body>${html}</body></html>`, 'text/html');
  const q = (sel, root = doc) => root.querySelector(sel);
  const W = 680;
  const PAD = 22;
  const inner = W - PAD * 2;
  const out = [];
  // header: glyph pair + title, kicker, badge
  const titleEl = q('.horosa-cnx-board-title');
  let gx = PAD + 12;
  [...titleEl.querySelectorAll('.horosa-xct-hexglyph')].forEach((g) => {
    bars(out, gx, PAD + 2, linesOf(g), { w: 24, h: 3, gap: 2, yinGap: 4, color: CNX.text, opacity: 0.72 });
    gx += 24 + 12;
  });
  const title = [...titleEl.childNodes].filter((n) => n.nodeType === 3).map((n) => n.textContent).join('').trim();
  out.push(tx(gx - 2, PAD + 13, title, 20, CNX.text, 700, 'start', ' letter-spacing="0.8"'));
  out.push(tx(PAD, PAD + 34 + 9, q('.horosa-cnx-board-kicker').textContent, 12.5, CNX.text, 400, 'start', ' opacity="0.78"'));
  const badge = q('.horosa-cnx-board-badge').textContent;
  const bw = cnxWidth(badge, 12) + 20;
  out.push(`<rect x="${W - PAD - bw}" y="${PAD + 2}" width="${bw}" height="20" rx="10" fill="${CNX.accentSoft(0.14)}" stroke="${CNX.lineStrong}" stroke-width="1"/>`);
  out.push(tx(W - PAD - bw / 2, PAD + 12, badge, 12, CNX.accentStrong, 700));
  const headH = 34 + 18 + 12;
  out.push(`<line x1="${PAD}" y1="${PAD + headH + 0.5}" x2="${W - PAD}" y2="${PAD + headH + 0.5}" stroke="${CNX.line}" stroke-width="1"/>`);
  // 九宫
  const cw = (inner - 20) / 3;
  const ch = 124;
  const gridTop = PAD + headH + 14;
  [...doc.querySelectorAll('.horosa-cnx-cell')].forEach((cell, i) => {
    const x = PAD + (i % 3) * (cw + 10);
    const y = gridTop + Math.floor(i / 3) * (ch + 10);
    const cls = cell.getAttribute('class') || '';
    const active = cls.includes('is-active');
    const center = cls.includes('is-center');
    out.push(`<rect x="${x + 0.5}" y="${y + 0.5}" width="${cw - 1}" height="${ch - 1}" rx="10" fill="${CNX.accentSoft(active ? 0.12 : 0.03)}" stroke="${active ? CNX.accent : CNX.line}" stroke-width="${active ? 2 : 1}"${center ? ' stroke-dasharray="4,3"' : ''}/>`);
    const glyph = q('.horosa-xct-glyph', cell);
    const name = q('.horosa-xct-cell-name', cell);
    const meta = q('.horosa-xct-cell-meta', cell);
    const nameSize = center ? 24 : 36;
    const parts = (glyph ? 18 : 0) + (glyph ? 9 : 0) + nameSize + 9 + 17;
    let cy = y + (ch - parts) / 2;
    const ink = center ? SECONDARY : (active ? CNX.accentStrong : CNX.text);
    if (glyph) { bars(out, x + cw / 2, cy, linesOf(glyph), { w: 30, h: 4, gap: 3, yinGap: 6, color: active ? CNX.accentStrong : CNX.text, opacity: 0.78 }); cy += 18 + 9; }
    out.push(tx(x + cw / 2, cy + nameSize / 2, name ? name.textContent : '', nameSize, ink, 800, 'middle', ' letter-spacing="2"'));
    cy += nameSize + 9;
    out.push(tx(x + cw / 2, cy + 8.5, meta ? meta.textContent : '', 13.5, center ? SECONDARY : CNX.muted, 600, 'middle', ' letter-spacing="0.8"'));
    const seqs = [...cell.querySelectorAll('.horosa-cnx-seq')].map((s) => s.textContent);
    let sx = x + cw - 7;
    seqs.slice().reverse().forEach((s) => {
      const sw = cnxWidth(s, 10) + 10;
      sx -= sw;
      out.push(`<rect x="${sx}" y="${y + 7}" width="${sw}" height="15" rx="7.5" fill="${CNX.accentSoft(0.16)}" stroke="${CNX.lineStrong}" stroke-width="1"/>`);
      out.push(tx(sx + sw / 2, y + 14.5, s, 10, CNX.accentStrong, 800));
      sx -= 3;
    });
  });
  // 推导 box(es)
  let y = gridTop + ch * 3 + 20 + 14;
  for (const step of doc.querySelectorAll('.horosa-cnx-flow-step')) {
    const em = q('em', step);
    const span = q('span', step);
    const text = span ? span.textContent : '';
    const sw = Math.min(inner, Math.max(200, cnxWidth(text, 13) + 26));
    out.push(`<rect x="${PAD + 0.5}" y="${y + 0.5}" width="${sw - 1}" height="${55 - 1}" rx="11" fill="${CNX.accentSoft(0.06)}" stroke="${CNX.lineStrong}" stroke-width="1"/>`);
    out.push(tx(PAD + 13, y + 11 + 8, em ? em.textContent : '', 11, CNX.accent, 800, 'start', ' letter-spacing="0.9"'));
    out.push(tx(PAD + 13, y + 11 + 16 + 6 + 9, text, 13, CNX.text, 400, 'start'));
    y += 55 + 8;
  }
  const H = Math.ceil(y - 8 + PAD);
  const board = `<rect x="0.5" y="0.5" width="${W - 1}" height="${H - 1}" rx="14" fill="${CNX.cardBg}" stroke="${CNX.lineStrong}" stroke-width="1"/>`;
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">${board}${out.join('')}</svg>`;
  return { svg, width: W, height: H, themeScope: 'horosa-huangji-redesign' };
}
