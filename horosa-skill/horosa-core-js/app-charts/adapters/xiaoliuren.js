// 小六壬 — the app's board (XiaoLiuRenMain.renderCenter(ke)) is HTML in the shared 卜 board language (horosa-cnx-*, layouts/app/
// 19-cnx-divination.less, inside the 卜其他 page's .horosa-huangji-redesign tokens and the .horosa-xlr-page rules). The run's
// result IS the page's `ke` ({school, nums, chuan, analysis}); we render renderCenter with the app's own code (SSR on a bare
// instance) and lay the markup out as SVG with the stylesheet's numbers: board ≤ 680 px, padding 22, radius 14; header (title
// 20 px / kicker 12.5 px / 三传 badge) over a rule; the palaces as squares on the page's grid areas (gap 10, radius 10, text
// centred: 节 11 px, name 21 px + number pill, 神 12.5 px, 卦·五行·方位 11.5 px, keys 12 px, 吉 / 平 / 凶 bar 3 px at the bottom,
// 三传 cells highlighted with their 传 badges); then the 三传 flow (11 / 13 padding, radius 11, ➤ between steps).
import { createElement, Fragment } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { DOMParser } from 'linkedom';
import XiaoLiuRenMain from '@horosa-app/components/xiaoliuren/XiaoLiuRenMain.js';
import { cnxText as tx, cnxEsc as esc, cnxWidth, CNX } from './cnxkit.js';

export function renderXiaoliuren(data) {
  const ke = data && data.xiaoliuren;
  if (!ke || !Array.isArray(ke.chuan) || ke.chuan.length !== 3) throw new Error('xiaoliuren: needs xiaoliuren.chuan (三传)');
  const view = Object.create(XiaoLiuRenMain.prototype);
  view.state = { settings: {} };
  view.props = {};
  const html = renderToStaticMarkup(createElement(Fragment, null, view.renderCenter(ke)));
  const doc = new DOMParser().parseFromString(`<!doctype html><html><body>${html}</body></html>`, 'text/html');
  const q = (sel, root = doc) => root.querySelector(sel);
  const W = 680;
  const PAD = 22;
  const inner = W - PAD * 2;
  const out = [];
  // header
  out.push(tx(PAD, PAD + 13, q('.horosa-cnx-board-title').textContent, 20, CNX.text, 700, 'start', ' letter-spacing="0.8"'));
  out.push(tx(PAD, PAD + 26 + 5 + 9, q('.horosa-cnx-board-kicker').textContent, 12.5, CNX.text, 400, 'start', ' opacity="0.78"'));
  const badge = q('.horosa-cnx-board-badge').textContent;
  const bw = cnxWidth(badge, 12) + 20;
  out.push(`<rect x="${W - PAD - bw}" y="${PAD + 2}" width="${bw}" height="20" rx="10" fill="${CNX.accentSoft(0.14)}" stroke="${CNX.lineStrong}" stroke-width="1"/>`);
  out.push(tx(W - PAD - bw / 2, PAD + 12, badge, 12, CNX.accentStrong, 700));
  const headH = 26 + 5 + 18 + 12;
  out.push(`<line x1="${PAD}" y1="${PAD + headH + 0.5}" x2="${W - PAD}" y2="${PAD + headH + 0.5}" stroke="${CNX.line}" stroke-width="1"/>`);
  // palaces
  const cells = [...doc.querySelectorAll('.horosa-cnx-cell')];
  const areas = cells.map((cell) => {
    const style = cell.getAttribute('style') || '';
    return [Number((style.match(/grid-row:\s*(\d+)/) || [])[1]) || 1, Number((style.match(/grid-column:\s*(\d+)/) || [])[1]) || 1];
  });
  const rows = Math.max(...areas.map((a) => a[0]));
  const size = (inner - 20) / 3;
  const gridTop = PAD + headH + 14;
  cells.forEach((cell, i) => {
    const [r, c] = areas[i];
    const x = PAD + (c - 1) * (size + 10);
    const y = gridTop + (r - 1) * (size + 10);
    const cls = cell.getAttribute('class') || '';
    const active = cls.includes('is-active');
    out.push(`<rect x="${x + 0.5}" y="${y + 0.5}" width="${size - 1}" height="${size - 1}" rx="10" fill="${CNX.accentSoft(active ? 0.12 : 0.03)}" stroke="${active ? CNX.accent : CNX.line}" stroke-width="${active ? 2 : 1}"/>`);
    const tone = (cls.match(/is-(ji|ping|xiong)/) || [])[1];
    if (tone) out.push(`<rect x="${x + size * 0.22}" y="${y + size - 11}" width="${size * 0.56}" height="3" rx="1.5" fill="${CNX.tone[tone]}" stroke="none"/>`);
    const parts = [];
    const jie = q('.horosa-cnx-cell-jie', cell);
    if (jie) parts.push({ text: jie.textContent, size: 11, color: CNX.muted, weight: 400 });
    const nameEl = q('.horosa-cnx-cell-name', cell);
    const num = nameEl && q('.horosa-cnx-cell-num', nameEl);
    const name = nameEl ? [...nameEl.childNodes].filter((n) => n.nodeType === 3).map((n) => n.textContent).join('') : '';
    parts.push({ text: name, size: 21, color: CNX.text, weight: 700, num: num ? num.textContent : null });
    const deity = q('.horosa-cnx-cell-deity', cell);
    if (deity) parts.push({ text: deity.textContent, size: 12.5, color: CNX.accentStrong, weight: 600 });
    const gua = q('.horosa-cnx-cell-gua', cell);
    if (gua) parts.push({ text: gua.textContent, size: 11.5, color: CNX.muted, weight: 400 });
    const keys = q('.horosa-cnx-cell-keys', cell);
    if (keys) parts.push({ text: keys.textContent, size: 12, color: CNX.text, weight: 400 });
    const lh = (p) => p.size * 1.45;
    const block = parts.reduce((h, p) => h + lh(p), 0) + (parts.length - 1) * 4;
    let cy = y + (size - block) / 2;
    parts.forEach((p) => {
      const mid = cy + lh(p) / 2;
      if (p.num) {
        const nw = Math.max(17, cnxWidth(p.num, 11) + 8);
        const total = cnxWidth(p.text, p.size) + 5 + nw;
        const left = x + size / 2 - total / 2;
        out.push(tx(left, mid, p.text, p.size, p.color, p.weight, 'start', ' letter-spacing="1"'));
        out.push(`<rect x="${left + total - nw}" y="${mid - 8.5}" width="${nw}" height="17" rx="8.5" fill="${CNX.accentSoft(0.16)}" stroke="none"/>`);
        out.push(tx(left + total - nw / 2, mid, p.num, 11, CNX.accentStrong, 700));
      } else {
        out.push(tx(x + size / 2, mid, p.text, p.size, p.color, p.weight));
      }
      cy += lh(p) + 4;
    });
    const seqs = [...cell.querySelectorAll('.horosa-cnx-seq')].map((s) => s.textContent);
    let sx = x + size - 7;
    seqs.slice().reverse().forEach((s) => {
      const sw = cnxWidth(s, 10) + 10;
      sx -= sw;
      out.push(`<rect x="${sx}" y="${y + 7}" width="${sw}" height="15" rx="7.5" fill="${CNX.accentSoft(0.16)}" stroke="${CNX.lineStrong}" stroke-width="1"/>`);
      out.push(tx(sx + sw / 2, y + 14.5, s, 10, CNX.accentStrong, 800));
      sx -= 3;
    });
  });
  // 三传 flow
  const flowTop = gridTop + rows * size + (rows - 1) * 10 + 14;
  const steps = [...doc.querySelectorAll('.horosa-cnx-flow-step')];
  const arrowW = 18;
  const stepW = (inner - (steps.length - 1) * (arrowW + 16)) / steps.length;
  const stepH = 92;
  steps.forEach((step, i) => {
    const x = PAD + i * (stepW + arrowW + 16);
    out.push(`<rect x="${x + 0.5}" y="${flowTop + 0.5}" width="${stepW - 1}" height="${stepH - 1}" rx="11" fill="${CNX.accentSoft(0.06)}" stroke="${CNX.lineStrong}" stroke-width="1"/>`);
    const em = q('em', step);
    out.push(tx(x + 13, flowTop + 11 + 8, em ? em.textContent : '', 11, CNX.accent, 800, 'start', ' letter-spacing="0.9"'));
    const b = q('b', step);
    const meta = q('.horosa-cnx-flow-meta', step);
    out.push(tx(x + 13, flowTop + 11 + 16 + 6 + 12, b ? b.textContent : '', 17, CNX.text, 800, 'start', ' letter-spacing="1"'));
    if (meta) out.push(tx(x + 13 + cnxWidth(b ? b.textContent : '', 17) + 10, flowTop + 11 + 16 + 6 + 13, meta.textContent, 11.5, CNX.muted, 400, 'start'));
    let kx = x + 13;
    [...step.querySelectorAll('.horosa-cnx-flow-keys span')].forEach((k) => {
      const kw = cnxWidth(k.textContent, 11.5) + 16;
      out.push(`<rect x="${kx}" y="${flowTop + 11 + 16 + 6 + 24 + 6}" width="${kw}" height="19" rx="9.5" fill="${CNX.accentSoft(0.1)}" stroke="${CNX.accentSoft(0.22)}" stroke-width="1"/>`);
      out.push(tx(kx + kw / 2, flowTop + 11 + 16 + 6 + 24 + 6 + 9.5, k.textContent, 11.5, CNX.accentStrong, 600));
      kx += kw + 4;
    });
    if (i > 0) out.push(tx(x - 8 - arrowW / 2, flowTop + stepH / 2, '➤', 13, CNX.accent, 700, 'middle', ' opacity="0.9"'));
  });
  const H = Math.ceil(flowTop + stepH + PAD);
  const board = `<rect x="0.5" y="0.5" width="${W - 1}" height="${H - 1}" rx="14" fill="${CNX.cardBg}" stroke="${CNX.lineStrong}" stroke-width="1"/>`;
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">${board}${out.join('')}</svg>`;
  return { svg, width: W, height: H, themeScope: 'horosa-huangji-redesign' };
}
