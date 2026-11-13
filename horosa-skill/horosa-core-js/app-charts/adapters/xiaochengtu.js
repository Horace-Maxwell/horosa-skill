// 小成图 — the app's 洛书九宫 board (XiaoChengTuMain.renderCenter(pan) in the 卜 board language, .horosa-xct-page rules) is
// HTML. The run's result carries the page's qi (board_context: the 本卦 / 之卦 hexagram objects the text was built from — returned
// by the skill's own tools/xiaochengtu.js), so: qi → the app's buildPan → renderCenter with the app's own code (SSR on a bare
// instance; state = { settings.yongGong, qi } is all it reads), then the markup is laid out as SVG with the stylesheet's
// numbers — header (本卦 / 之卦 glyph pair 24 × 3 px bars, title 20 px, kicker, 用宫 badge), the 3 × 3 palaces (trigram glyph
// 30 × 4 px bars, name 44 px 800, 地盘 · 宫 13.5 px; 中宫 dashed; 用宫 / 推N badges), and the 推导 box under it.
// v3.14.0 palace cell (.horosa-xct-page .horosa-cnx-cell.horosa-xct-cell): padding 19 / 12 / 9 with the items 8 px apart (was
// 14 / 12 and 9) — the extra room at the top is for the badge row: 用宫 at the left, the 推N step pushed to the right.
import { createElement, Fragment } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { DOMParser } from 'linkedom';
import XiaoChengTuMain from '@horosa-app/components/xiaochengtu/XiaoChengTuMain.js';
import { buildPan } from '@horosa-app/components/xiaochengtu/core/xiaochengtuPan.js';
import { cnxText as tx, cnxWidth, cnxSeqTone, CNX } from './cnxkit.js';

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
  // Numbers below are the app's own layout on a 680 px board at a desktop window (measured in Chrome with the v3.14.0
  // stylesheet; the clamp()s — board padding, trigram-name size — sit at their upper bound from ≈ 1400 px up).
  const W = 680;
  const PAD = 27; // 1 px border + padding clamp(18px, 2.2vw, 26px)
  const LH = 1.5715; // antd body line-height
  const inner = W - PAD * 2;
  const out = [];
  // header: the 本卦 / 之卦 glyph pair (6 × 3 px bars 2 px apart, 24 px wide, 12 px between the two) sits on the title's
  // baseline, so the title block is 50 px tall with the text line at its top; 5 px; kicker; badge at the right
  const titleEl = q('.horosa-cnx-board-title');
  let gx = PAD + 12;
  const glyphs = [...titleEl.querySelectorAll('.horosa-xct-hexglyph')];
  glyphs.forEach((g) => {
    bars(out, gx, PAD + 22, linesOf(g), { w: 24, h: 3, gap: 2, yinGap: 4, color: CNX.text, opacity: 0.72 });
    gx += 24 + 12;
  });
  const title = [...titleEl.childNodes].filter((n) => n.nodeType === 3).map((n) => n.textContent).join('').trim();
  const titleH = glyphs.length ? 50 : 20 * LH;
  out.push(tx(PAD + (glyphs.length ? glyphs.length * 36 - 12 + 10 : 0), PAD + 15.5, title, 20, CNX.text, 700, 'start', ' letter-spacing="0.8"'));
  out.push(tx(PAD, PAD + titleH + 5 + 12.5 * LH / 2, q('.horosa-cnx-board-kicker').textContent, 12.5, CNX.text, 400, 'start', ' opacity="0.78"'));
  const badge = q('.horosa-cnx-board-badge').textContent;
  const bw = cnxWidth(badge, 12) + 22;
  const bh = 12 * LH + 8;
  out.push(`<rect x="${W - PAD - bw + 0.5}" y="${PAD + 0.5}" width="${bw - 1}" height="${bh - 1}" rx="12" fill="${CNX.accentSoft(0.14)}" stroke="${CNX.lineStrong}" stroke-width="1"/>`);
  out.push(tx(W - PAD - bw / 2, PAD + bh / 2, badge, 12, CNX.accentStrong, 700));
  const headH = titleH + 5 + 12.5 * LH + 12 + 1;
  out.push(`<line x1="${PAD}" y1="${PAD + headH - 0.5}" x2="${W - PAD}" y2="${PAD + headH - 0.5}" stroke="${CNX.line}" stroke-width="1"/>`);
  // 九宫
  const cw = (inner - 20) / 3;
  const NAME = 44; // clamp(30px, 3.2vw, 44px), line-height 1
  const CENTER_NAME = 27; // clamp(20px, 2vw, 27px)
  const metaLh = 13.5 * LH;
  const ch = 2 + 19 + 9 + (18 + 8 + NAME + 8 + metaLh); // border + padding 19 / 9 + glyph / name / meta, 8 px apart
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
    const nameSize = center ? CENTER_NAME : NAME;
    const block = (glyph ? 18 + 8 : 0) + nameSize + 8 + metaLh;
    let cy = y + 1 + 19 + (ch - 2 - 19 - 9 - block) / 2; // justify-content: center inside the padding box
    const ink = center ? SECONDARY : (active ? CNX.accentStrong : CNX.text);
    if (glyph) { bars(out, x + cw / 2, cy, linesOf(glyph), { w: 30, h: 4, gap: 3, yinGap: 6, color: active ? CNX.accentStrong : CNX.text, opacity: 0.78 }); cy += 18 + 8; }
    out.push(tx(x + cw / 2, cy + nameSize / 2, name ? name.textContent : '', nameSize, ink, 800, 'middle', ` letter-spacing="${(nameSize * 0.08).toFixed(2)}"`));
    cy += nameSize + 8;
    out.push(tx(x + cw / 2, cy + metaLh / 2, meta ? meta.textContent : '', 13.5, center ? SECONDARY : CNX.muted, 600, 'middle', ' letter-spacing="0.8"'));
    // 传序角标 (.horosa-xct-cell .horosa-cnx-cell-seqs): one row across the top — top 3, left / right 6 inside the 1 px border,
    // 4 px apart; the 推N step carries margin-left: auto (right edge). Pill = 13 px line + border, padding 0 5, 10 px / 800, .02em.
    let sx = x + 1 + 6;
    [...cell.querySelectorAll('.horosa-cnx-seq')].forEach((el) => {
      const s = el.textContent;
      const seqCls = el.getAttribute('class') || '';
      const tone = cnxSeqTone(seqCls);
      const sw = cnxWidth(s, 10) + [...s].length * 0.2 + 12;
      const step = /(^|\s)is-step(\s|$)/.test(seqCls);
      const left = step ? x + cw - 1 - 6 - sw : sx;
      out.push(`<rect x="${left + 0.5}" y="${y + 4.5}" width="${sw - 1}" height="14" rx="7" fill="${tone.fill}" stroke="${tone.stroke}" stroke-width="1"/>`);
      out.push(tx(left + sw / 2, y + 4 + 7.5, s, 10, tone.ink, 800));
      if (!step) sx += sw + 4;
    });
  });
  // 推导 box(es): padding 11 / 13, label line 11 px, 6 px, text line 13 px; width = text + padding (min 200)
  let y = gridTop + ch * 3 + 20 + 14;
  const stepH = 2 + 22 + 11 * LH + 6 + 13 * LH;
  for (const step of doc.querySelectorAll('.horosa-cnx-flow-step')) {
    const em = q('em', step);
    const span = q('span', step);
    const text = span ? span.textContent : '';
    const sw = Math.min(inner, Math.max(200, cnxWidth(text, 13) + 28));
    out.push(`<rect x="${PAD + 0.5}" y="${y + 0.5}" width="${sw - 1}" height="${stepH - 1}" rx="11" fill="${CNX.accentSoft(0.06)}" stroke="${CNX.lineStrong}" stroke-width="1"/>`);
    out.push(tx(PAD + 14, y + 12 + 11 * LH / 2, em ? em.textContent : '', 11, CNX.accent, 800, 'start', ' letter-spacing="0.9"'));
    out.push(tx(PAD + 14, y + 12 + 11 * LH + 6 + 13 * LH / 2, text, 13, CNX.text, 400, 'start'));
    y += stepH + 8;
  }
  const H = Math.ceil(y - 8 + PAD);
  const board = `<rect x="0.5" y="0.5" width="${W - 1}" height="${H - 1}" rx="14" fill="${CNX.cardBg}" stroke="${CNX.lineStrong}" stroke-width="1"/>`;
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">${board}${out.join('')}</svg>`;
  return { svg, width: W, height: H, themeScope: 'horosa-astro-redesign horosa-huangji-redesign' };
}
