// 小六壬 — the app's board (XiaoLiuRenMain.renderCenter(ke)) is HTML in the shared 卜 board language (horosa-cnx-*, layouts/app/
// 19-cnx-divination.less, inside the 卜其他 page's .horosa-huangji-redesign tokens and the .horosa-xlr-page rules). The run's
// result IS the page's `ke` ({school, nums, chuan, analysis}); we render renderCenter with the app's own code (SSR on a bare
// instance) and lay the markup out as SVG with the stylesheet's numbers: board ≤ 680 px, padding 26, radius 14; header (title
// 20 px / kicker 12.5 px / 三传 badge) over a rule; the palaces as squares on the page's grid areas (gap 10, radius 10, text
// centred: 节 11 px, name 23 px + number pill, 神 12.5 px, 卦·五行·方位 11.5 px, keys 12 px, 吉 / 平 / 凶 bar 3 px at the bottom,
// 三传 cells highlighted with their 传 badges); then the 三传 flow (11 / 13 padding, radius 11, ➤ between steps).
import { createElement, Fragment } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { DOMParser } from 'linkedom';
import XiaoLiuRenMain from '@horosa-app/components/xiaoliuren/XiaoLiuRenMain.js';
import { cnxText as tx, cnxEsc as esc, cnxWidth, cnxSeqTone, CNX } from './cnxkit.js';

export function renderXiaoliuren(data) {
  const ke = data && data.xiaoliuren;
  if (!ke || !Array.isArray(ke.chuan) || ke.chuan.length !== 3) throw new Error('xiaoliuren: needs xiaoliuren.chuan (三传)');
  const view = Object.create(XiaoLiuRenMain.prototype);
  view.state = { settings: {} };
  view.props = {};
  const html = renderToStaticMarkup(createElement(Fragment, null, view.renderCenter(ke)));
  const doc = new DOMParser().parseFromString(`<!doctype html><html><body>${html}</body></html>`, 'text/html');
  const q = (sel, root = doc) => root.querySelector(sel);
  // Numbers below are the app's own layout on a 680 px board at a desktop window (measured in Chrome with the v3.14.0
  // stylesheet; the clamp()s — board padding, palace-name size — sit at their upper bound from ≈ 1280 px up).
  const W = 680;
  const PAD = 27; // 1 px border + padding clamp(18px, 2.2vw, 26px)
  const LH = 1.5715; // antd body line-height
  const inner = W - PAD * 2;
  const out = [];
  // header: title line 20 px, 5 px, kicker line 12.5 px; 12 px + rule under it
  out.push(tx(PAD, PAD + 20 * LH / 2, q('.horosa-cnx-board-title').textContent, 20, CNX.text, 700, 'start', ' letter-spacing="0.8"'));
  out.push(tx(PAD, PAD + 20 * LH + 5 + 12.5 * LH / 2, q('.horosa-cnx-board-kicker').textContent, 12.5, CNX.text, 400, 'start', ' opacity="0.78"'));
  const badge = q('.horosa-cnx-board-badge').textContent;
  const bw = cnxWidth(badge, 12) + 22;
  const bh = 12 * LH + 8;
  out.push(`<rect x="${W - PAD - bw + 0.5}" y="${PAD + 0.5}" width="${bw - 1}" height="${bh - 1}" rx="12" fill="${CNX.accentSoft(0.14)}" stroke="${CNX.lineStrong}" stroke-width="1"/>`);
  out.push(tx(W - PAD - bw / 2, PAD + bh / 2, badge, 12, CNX.accentStrong, 700));
  const headH = 20 * LH + 5 + 12.5 * LH + 12 + 1;
  out.push(`<line x1="${PAD}" y1="${PAD + headH - 0.5}" x2="${W - PAD}" y2="${PAD + headH - 0.5}" stroke="${CNX.line}" stroke-width="1"/>`);
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
    parts.push({ text: name, size: 23, color: CNX.text, weight: 800, num: num ? num.textContent : null }); // clamp(19px, 2vw, 23px)
    const deity = q('.horosa-cnx-cell-deity', cell);
    if (deity) parts.push({ text: deity.textContent, size: 12.5, color: CNX.accentStrong, weight: 600 });
    const gua = q('.horosa-cnx-cell-gua', cell);
    if (gua) parts.push({ text: gua.textContent, size: 11.5, color: CNX.muted, weight: 400 });
    const keys = q('.horosa-cnx-cell-keys', cell);
    if (keys) parts.push({ text: keys.textContent, size: 12, color: CNX.text, weight: 400, opacity: 0.9, lh: 18 }); // .horosa-cnx-cell-keys { line-height: 1.5; opacity: .9 }
    const lh = (p) => p.lh || p.size * LH;
    const block = parts.reduce((h, p) => h + lh(p), 0) + (parts.length - 1) * 4;
    let cy = y + (size - block) / 2;
    parts.forEach((p) => {
      const mid = cy + lh(p) / 2;
      if (p.num) {
        const nw = Math.max(17, cnxWidth(p.num, 11) + 8);
        const tw = cnxWidth(p.text, p.size) + [...p.text].length * p.size * 0.12; // letter-spacing .12em
        const total = tw + 5 + nw;
        const left = x + size / 2 - total / 2;
        out.push(tx(left, mid, p.text, p.size, p.color, p.weight, 'start', ` letter-spacing="${(p.size * 0.12).toFixed(2)}"`));
        out.push(`<rect x="${left + total - nw}" y="${mid - 6.7}" width="${nw}" height="17" rx="8.5" fill="${CNX.accentSoft(0.16)}" stroke="none"/>`);
        out.push(tx(left + total - nw / 2, mid + 1.8, p.num, 11, CNX.accentStrong, 700));
      } else {
        out.push(tx(x + size / 2, mid, p.text, p.size, p.color, p.weight, 'middle', p.opacity ? ` opacity="${p.opacity}"` : ''));
      }
      cy += lh(p) + 4;
    });
    // 传序角标 (v3.14.0 .horosa-xlr-page .horosa-cnx-cell-sq .horosa-cnx-cell-seqs): top 5 / right 5 inside the cell's 1 px border,
    // stacked in a column (right-aligned, 2 px apart) so two 传 on one palace no longer run into the 节 name; each pill is a
    // 14 px line + border, padding 0 4, 10 px / 800 with .04em tracking; 一传 is the filled one (cnxSeqTone)
    let sy = y + 6;
    [...cell.querySelectorAll('.horosa-cnx-seq')].forEach((el) => {
      const s = el.textContent;
      const seqTone = cnxSeqTone(el.getAttribute('class'));
      const sw = cnxWidth(s, 10) + [...s].length * 0.4 + 10;
      const sx = x + size - 6 - sw;
      out.push(`<rect x="${sx + 0.5}" y="${sy + 0.5}" width="${sw - 1}" height="15" rx="7.5" fill="${seqTone.fill}" stroke="${seqTone.stroke}" stroke-width="1"/>`);
      out.push(tx(sx + sw / 2, sy + 8, s, 10, seqTone.ink, 800));
      sy += 16 + 2;
    });
  });
  // 三传 flow: steps (padding 11 / 13, items 6 px apart: 传 label line 11 px, 课名 line 17 px + meta, key pills) with ➤ between, 8 px either side
  const flowTop = gridTop + rows * size + (rows - 1) * 10 + 14;
  const steps = [...doc.querySelectorAll('.horosa-cnx-flow-step')];
  const arrowW = 12.2;
  const stepW = (inner - (steps.length - 1) * (arrowW + 16)) / steps.length;
  const emLh = 11 * LH;
  const headLh = 17 * LH;
  const pillH = 11.5 * LH + 4;
  const stepH = 2 + 22 + emLh + 6 + headLh + 6 + pillH;
  steps.forEach((step, i) => {
    const x = PAD + i * (stepW + arrowW + 16);
    const first = (step.getAttribute('class') || '').includes('is-1'); // .horosa-cnx-flow-step.is-1: accent border, 12 % ground
    out.push(`<rect x="${x + 0.5}" y="${flowTop + 0.5}" width="${stepW - 1}" height="${stepH - 1}" rx="11" fill="${CNX.accentSoft(first ? 0.12 : 0.06)}" stroke="${first ? CNX.accent : CNX.lineStrong}" stroke-width="1"/>`);
    const em = q('em', step);
    const top = flowTop + 1 + 11;
    out.push(tx(x + 14, top + emLh / 2, em ? em.textContent : '', 11, CNX.accent, 800, 'start', ' letter-spacing="0.9"'));
    const b = q('b', step);
    const meta = q('.horosa-cnx-flow-meta', step);
    const headMid = top + emLh + 6 + headLh / 2;
    out.push(tx(x + 14, headMid, b ? b.textContent : '', 17, CNX.text, 800, 'start', ' letter-spacing="1"'));
    if (meta) out.push(tx(x + 14 + cnxWidth(b ? b.textContent : '', 17) + [...(b ? b.textContent : '')].length * 1.02 + 8, headMid + 1.7, meta.textContent, 11.5, CNX.muted, 400, 'start'));
    let kx = x + 14;
    const pillTop = top + emLh + 6 + headLh + 6;
    [...step.querySelectorAll('.horosa-cnx-flow-keys span')].forEach((k) => {
      const kw = cnxWidth(k.textContent, 11.5) + 18;
      out.push(`<rect x="${kx + 0.5}" y="${pillTop + 0.5}" width="${kw - 1}" height="${pillH - 1}" rx="10" fill="${CNX.accentSoft(0.1)}" stroke="${CNX.accentSoft(0.22)}" stroke-width="1"/>`);
      out.push(tx(kx + kw / 2, pillTop + pillH / 2, k.textContent, 11.5, CNX.accentStrong, 600));
      kx += kw + 4;
    });
    if (i > 0) out.push(tx(x - 8 - arrowW / 2, flowTop + stepH / 2, '➤', 15, CNX.accent, 700, 'middle', ' opacity="0.9"')); // .horosa-cnx-flow-arrow { font-size: 15px }
  });
  const H = Math.ceil(flowTop + stepH + PAD);
  const board = `<rect x="0.5" y="0.5" width="${W - 1}" height="${H - 1}" rx="14" fill="${CNX.cardBg}" stroke="${CNX.lineStrong}" stroke-width="1"/>`;
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">${board}${out.join('')}</svg>`;
  return { svg, width: W, height: H, themeScope: 'horosa-astro-redesign horosa-huangji-redesign' };
}
