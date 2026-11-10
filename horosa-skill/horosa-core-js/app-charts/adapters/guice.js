// 皇极轨策 — the app's board (GuiceMain.renderCenter(p), layouts/app/18-ziwei.less .horosa-guice-*) is HTML. p comes from the
// app's own buildGuicePan with exactly the run's inputs (board_context.gua = the skill JS's qiGua result; ctx / settings /
// 世应 inputs = result.input_normalized), renderCenter runs with the app's code (SSR on a bare instance), and the markup is
// laid out as SVG with the stylesheet's desktop numbers: board padding 22 radius 14; header (title 20 px, kicker 12 px muted,
// 爻动 pill); the five 卦 cards in one row (gap 8; kicker 11 px accent, 爻画 52 × 7 px bars gap 3 — 动爻 in accent-strong,
// 互卦 as two 34 × 5 px trigrams with 体 / 用; name 15 px, sub 11 px); 四位盘 title + four cells (num 30 px accent-strong);
// then the field cards (label 11 / value 17 / sub 11) in rows of auto-fit ≥ 150 px.
import { createElement, Fragment } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { DOMParser } from 'linkedom';
import GuiceMain from '@horosa-app/components/guice/GuiceMain.js';
import { buildGuicePan } from '@horosa-app/components/guice/core/guicePan.js';
import { cnxText as tx, cnxWidth, CNX } from './cnxkit.js';

const cls = (el) => (el && el.getAttribute('class')) || '';

function glyph(out, el, cx, top, small) {
  const w = small ? 34 : 52;
  const h = small ? 5 : 7;
  const gap = small ? 5 : 7;
  const yaos = [...el.children].filter((c) => cls(c).includes('horosa-guice-yao'));
  yaos.forEach((yao, i) => {
    const y = top + i * (h + 2 + 3);
    const dong = cls(yao).includes('is-dong');
    const color = dong ? CNX.accentStrong : CNX.muted;
    if (dong) out.push(`<rect x="${cx - w / 2 - 3}" y="${y - 1}" width="${w + 6}" height="${h + 2}" rx="3" fill="${CNX.accentSoft(0.16)}" stroke="${CNX.accent}" stroke-width="0.8"/>`);
    const bar = yao.querySelector('.horosa-guice-bar');
    if (cls(bar).includes('yang')) out.push(`<rect x="${cx - w / 2}" y="${y}" width="${w}" height="${h}" rx="2" fill="${color}" stroke="none"/>`);
    else {
      const seg = (w - gap) / 2;
      out.push(`<rect x="${cx - w / 2}" y="${y}" width="${seg}" height="${h}" rx="2" fill="${color}" stroke="none"/>`);
      out.push(`<rect x="${cx + w / 2 - seg}" y="${y}" width="${seg}" height="${h}" rx="2" fill="${color}" stroke="none"/>`);
    }
  });
  return yaos.length * (h + 5) - 3;
}

// CSS overflow-wrap: break at spaces first; a single over-long token breaks anywhere
function wrap(text, size, width) {
  const lines = [];
  let line = '';
  for (const token of `${text}`.split(/(\s+)/)) {
    if (!token) continue;
    if (cnxWidth(line + token, size) <= width) { line += token; continue; }
    if (line.trim()) { lines.push(line.trimEnd()); line = ''; }
    if (/^\s+$/.test(token)) continue;
    for (const ch of [...token]) {
      if (cnxWidth(line + ch, size) > width && line) { lines.push(line); line = ch; } else line += ch;
    }
  }
  if (line.trim()) lines.push(line.trimEnd());
  return lines;
}

export function renderGuice(data) {
  const gua = data && data.guice && data.guice.board_context && data.guice.board_context.gua;
  const norm = (data && data.input_normalized) || {};
  if (!gua) throw new Error('guice: needs guice.board_context.gua');
  const p = buildGuicePan({ gua, ctx: norm.ctx || {}, settings: norm.settings, shiyingInputs: norm.shiyingInputs || {} });
  const view = Object.create(GuiceMain.prototype);
  view.state = { settings: norm.settings || {} };
  view.props = {};
  const html = renderToStaticMarkup(createElement(Fragment, null, view.renderCenter(p)));
  const doc = new DOMParser().parseFromString(`<!doctype html><html><body>${html}</body></html>`, 'text/html');
  const q = (sel, root = doc) => root.querySelector(sel);
  const W = 720;
  const PAD = 22;
  const inner = W - PAD * 2;
  const out = [];
  out.push(tx(PAD, PAD + 13, q('.horosa-guice-board-title').textContent, 20, CNX.text, 700, 'start', ' letter-spacing="0.8"'));
  out.push(tx(PAD, PAD + 26 + 3 + 8, q('.horosa-guice-board-kicker').textContent, 12, CNX.muted, 400, 'start'));
  const time = q('.horosa-guice-board-time');
  if (time) {
    const bw = cnxWidth(time.textContent, 12) + 20;
    out.push(`<rect x="${W - PAD - bw}" y="${PAD + 2}" width="${bw}" height="20" rx="10" fill="${CNX.accentSoft(0.14)}" stroke="${CNX.lineStrong}" stroke-width="1"/>`);
    out.push(tx(W - PAD - bw / 2, PAD + 12, time.textContent, 12, CNX.accentStrong, 700));
  }
  const headH = 26 + 3 + 16 + 12;
  out.push(`<line x1="${PAD}" y1="${PAD + headH + 0.5}" x2="${W - PAD}" y2="${PAD + headH + 0.5}" stroke="${CNX.line}" stroke-width="1"/>`);
  let y = PAD + headH + 14;
  // five 卦 cards
  const cards = [...doc.querySelectorAll('.horosa-guice-gua-card')];
  const cw = (inner - 8 * (cards.length - 1)) / cards.length;
  const ch = 152;
  cards.forEach((card, i) => {
    const x = PAD + i * (cw + 8);
    const ben = cls(card).includes('is-ben');
    out.push(`<rect x="${x + 0.5}" y="${y + 0.5}" width="${cw - 1}" height="${ch - 1}" rx="10" fill="${CNX.accentSoft(ben ? 0.06 : 0.02)}" stroke="${ben ? CNX.lineStrong : CNX.line}" stroke-width="1"/>`);
    out.push(tx(x + cw / 2, y + 12 + 7, q('.horosa-guice-gua-card-kicker', card).textContent, 11, CNX.accent, 700, 'middle', ' letter-spacing="0.9"'));
    const pair = q('.horosa-guice-tri-pair', card);
    const top = y + 12 + 14 + 8;
    if (pair) {
      const tris = [...pair.querySelectorAll('.horosa-guice-tri')];
      tris.forEach((tri, k) => {
        const cx = x + cw / 2 + (k - (tris.length - 1) / 2) * (34 + 12);
        const gh = glyph(out, q('.horosa-guice-gua-glyph', tri), cx, top + 12, true);
        const em = q('em', tri);
        out.push(tx(cx, top + 12 + gh + 4 + 6, em ? em.textContent : '', 10, CNX.accent, 700));
      });
    } else {
      glyph(out, q('.horosa-guice-gua-glyph', card), x + cw / 2, top, false);
    }
    const strong = q('strong', card);
    out.push(tx(x + cw / 2, y + ch - 12 - 15 - 10, strong ? strong.textContent : '', 15, CNX.text, 700));
    const sub = [...card.children].filter((c) => c.tagName === 'SPAN' && !cls(c)).pop();
    out.push(tx(x + cw / 2, y + ch - 12 - 7, sub ? sub.textContent : '', 11, CNX.muted, 400));
  });
  y += ch + 14;
  // 四位盘
  const st = q('.horosa-guice-section-title');
  if (st) {
    const title = [...st.childNodes].filter((n) => n.nodeType === 3).map((n) => n.textContent).join('').trim();
    out.push(tx(PAD, y + 9, title, 13, CNX.text, 700, 'start'));
    const em = q('em', st);
    if (em) out.push(tx(PAD + cnxWidth(title, 13) + 10, y + 9.5, em.textContent, 11, CNX.muted, 500, 'start'));
    y += 18 + 14;
  }
  const siwei = [...doc.querySelectorAll('.horosa-guice-siwei')];
  if (siwei.length) {
    const sw = (inner - 8 * (siwei.length - 1)) / siwei.length;
    const sh = 104;
    siwei.forEach((cell, i) => {
      const x = PAD + i * (sw + 8);
      const empty = cls(cell).includes('is-empty');
      out.push(`<rect x="${x + 0.5}" y="${y + 0.5}" width="${sw - 1}" height="${sh - 1}" rx="10" fill="${CNX.cardBg}" stroke="${CNX.line}" stroke-width="1"${empty ? ' stroke-dasharray="4,3" opacity="0.72"' : ''}/>`);
      const get = (c) => { const el = q(c, cell); return el ? el.textContent : ''; };
      out.push(tx(x + sw / 2, y + 12 + 7, get('.horosa-guice-siwei-wei'), 11, CNX.muted));
      out.push(tx(x + sw / 2, y + 12 + 14 + 3 + 16.5, get('.horosa-guice-siwei-num'), 30, CNX.accentStrong, 700));
      out.push(tx(x + sw / 2, y + 12 + 14 + 3 + 33 + 3 + 10, get('.horosa-guice-siwei-gua'), 14, CNX.text, 600));
      out.push(tx(x + sw / 2, y + 12 + 14 + 3 + 33 + 3 + 20 + 3 + 7, get('.horosa-guice-siwei-wx'), 11, CNX.muted));
    });
    y += sh + 14;
  }
  // field cards: auto-fit ≥ 150 px per row group
  for (const grid of doc.querySelectorAll('.horosa-guice-meta-grid')) {
    const fields = [...grid.querySelectorAll('.horosa-guice-field')];
    const perRow = Math.max(1, Math.min(fields.length, Math.floor((inner + 8) / (150 + 8))));
    const fw = (inner - 8 * (perRow - 1)) / perRow;
    for (let r = 0; r < fields.length; r += perRow) {
      const row = fields.slice(r, r + perRow).map((f) => ({
        label: (q('.horosa-guice-field-label', f) || { textContent: '' }).textContent,
        value: (q('.horosa-guice-field-value', f) || { textContent: '' }).textContent,
        sub: wrap((q('.horosa-guice-field-sub', f) || { textContent: '' }).textContent, 11, fw - 24),
      }));
      const rh = 10 + 15 + 2 + 22 + 2 + Math.max(1, ...row.map((f) => f.sub.length)) * 16 + 10;
      row.forEach((f, k) => {
        const x = PAD + k * (fw + 8);
        out.push(`<rect x="${x + 0.5}" y="${y + 0.5}" width="${fw - 1}" height="${rh - 1}" rx="10" fill="${CNX.cardBg}" stroke="${CNX.line}" stroke-width="1"/>`);
        out.push(tx(x + 12, y + 10 + 7.5, f.label, 11, CNX.muted, 400, 'start'));
        out.push(tx(x + 12, y + 10 + 15 + 2 + 11, f.value, 17, CNX.text, 700, 'start'));
        f.sub.forEach((line, j) => out.push(tx(x + 12, y + 10 + 15 + 2 + 22 + 2 + 8 + j * 16, line, 11, CNX.muted, 400, 'start')));
      });
      y += rh + 8;
    }
    y += 6;
  }
  const H = Math.ceil(y - 14 + PAD);
  const board = `<rect x="0.5" y="0.5" width="${W - 1}" height="${H - 1}" rx="14" fill="${CNX.cardBg}" stroke="${CNX.lineStrong}" stroke-width="1"/>`;
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">${board}${out.join('')}</svg>`;
  return { svg, width: W, height: H, themeScope: 'horosa-huangji-redesign' };
}
