// 灵棋经 — the app's 灵棋盘 (LingQiMain.renderCenter, layouts/app/21-lingqi.less light theme) is HTML. The run's counts are the
// page's state.counts; faces = the app's facesFromCounts; we render renderCenter with the app's own code (SSR on a bare
// instance) and lay its markup out as SVG with the stylesheet's light-theme numbers: board padding 18 / 22, radius 12, warm
// paper ground; header (title / kicker / counts badge); three layers (上 / 中 / 下: a centred gold label + role + 枚数 pill;
// four 72 px chips — 字面 #7a541c on #f6efdd, 覆 as a plain darker disc); the result band (卦序 13 px, 卦名 28 px gold, 象 15 px,
// attr 12.5 px).
// The 六戊日 tag is the app's isWuDay on the cast day (antd Tag can't render server-side, so that one tag is drawn here).
import { createElement, Fragment } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { DOMParser } from 'linkedom';
import LingQiMain from '@horosa-app/components/lingqi/LingQiMain.js';
import { facesFromCounts, isWuDay } from '@horosa-app/components/lingqi/core/lingqiCast.js';
import { cnxText as tx, cnxWidth, CNX } from './cnxkit.js';

const GOLD = 'var(--horosa-gold, #9a6a25)';
const MUTED = 'var(--horosa-huangji-muted, var(--horosa-text-secondary))';

export function renderLingqi(data) {
  const counts = data && data.counts;
  if (!Array.isArray(counts) || counts.length !== 3) throw new Error('lingqi: needs counts [上, 中, 下]');
  const view = Object.create(LingQiMain.prototype);
  view.state = { counts, faces: facesFromCounts(counts), display: 'simp', category: data.category || 'general', guaOrigin: null };
  view.props = {};
  view.nongli = () => null; // see header: the 六戊日 tag is drawn below from the cast day
  const html = renderToStaticMarkup(createElement(Fragment, null, view.renderCenter()));
  const doc = new DOMParser().parseFromString(`<!doctype html><html><body>${html}</body></html>`, 'text/html');
  const q = (sel, root = doc) => root.querySelector(sel);
  const W = 680;
  const PX = 22;
  const out = [];
  let y = 18;
  out.push(tx(PX, y + 13, q('.horosa-cnx-board-title').textContent, 20, CNX.text, 700, 'start', ' letter-spacing="0.8"'));
  out.push(tx(PX, y + 26 + 5 + 9, q('.horosa-cnx-board-kicker').textContent, 12.5, CNX.text, 400, 'start', ' opacity="0.78"'));
  const badge = q('.horosa-cnx-board-badge').textContent;
  const bw = cnxWidth(badge, 12) + 20;
  out.push(`<rect x="${W - PX - bw}" y="${y + 2}" width="${bw}" height="20" rx="10" fill="${CNX.accentSoft(0.14)}" stroke="${CNX.lineStrong}" stroke-width="1"/>`);
  out.push(tx(W - PX - bw / 2, y + 12, badge, 12, CNX.accentStrong, 700));
  y += 26 + 5 + 18 + 12;
  out.push(`<line x1="${PX}" y1="${y + 0.5}" x2="${W - PX}" y2="${y + 0.5}" stroke="${CNX.line}" stroke-width="1"/>`);
  y += 18;
  // Layers as the app lays them out on a 680 px board (measured in Chrome with the app's stylesheet, v3.14.0): rows of
  // 16 + 72 + 16 (+ border) 18 px apart; the label is a centred 66 px column — 层 24 px / 700 in gold on a 1.15 line, 位 11 px,
  // the 枚数 pill 11 px on a 17 px line (3 px between them) — then 20 px and the chips area, where the four 72 px chips sit
  // centred, 20 px apart (字面 2 px rim rgba(154,106,37,.55); 覆 2 px rim rgba(110,100,82,.5)).
  const CHIP = 72;
  const LABEL_W = 66;
  for (const layer of doc.querySelectorAll('.horosa-lingqi-layer')) {
    const h = 2 + 16 * 2 + CHIP;
    out.push(`<rect x="${PX + 0.5}" y="${y + 0.5}" width="${W - PX * 2 - 1}" height="${h - 1}" rx="12" fill="rgba(255, 255, 255, 0.35)" stroke="rgba(154, 106, 37, 0.16)" stroke-width="1"/>`);
    const label = q('.horosa-lingqi-layer-label', layer);
    const lcx = PX + 1 + 22 + LABEL_W / 2;
    const top = y + (h - (27.6 + 3 + 17.3 + 3 + 19)) / 2;
    out.push(tx(lcx, top + 13.8, q('b', label).textContent, 24, GOLD, 700));
    out.push(tx(lcx, top + 27.6 + 3 + 8.65, q('em', label).textContent, 11, MUTED, 400));
    const count = q('span', label).textContent;
    const pw = cnxWidth(count, 11) + 18;
    const py = top + 27.6 + 3 + 17.3 + 3;
    out.push(`<rect x="${lcx - pw / 2 + 0.5}" y="${py + 0.5}" width="${pw - 1}" height="18" rx="8" fill="none" stroke="rgba(154, 106, 37, 0.28)" stroke-width="1"/>`);
    out.push(tx(lcx, py + 9.5, count, 11, 'rgba(74, 63, 48, 0.8)'));
    const chips = [...layer.querySelectorAll('.horosa-lingqi-chip')];
    const span = chips.length * CHIP + (chips.length - 1) * 20;
    const areaLeft = PX + 1 + 22 + LABEL_W + 20;
    const left = areaLeft + ((W - PX - 1 - 22) - areaLeft - span) / 2;
    chips.forEach((chip, i) => {
      const cx = left + i * (CHIP + 20) + CHIP / 2;
      const cy = y + h / 2;
      const front = q('.horosa-lingqi-chip-face.is-front', chip);
      if (front) {
        out.push(`<circle cx="${cx}" cy="${cy}" r="${CHIP / 2 - 1}" fill="#f6efdd" stroke="rgba(154, 106, 37, 0.55)" stroke-width="2"/>`);
        out.push(`<circle cx="${cx - CHIP * 0.1}" cy="${cy - CHIP * 0.12}" r="${CHIP * 0.2}" fill="#ffffff" fill-opacity="0.45" stroke="none"/>`);
        out.push(tx(cx, cy, front.textContent, 29, '#7a541c', 700));
      } else {
        out.push(`<circle cx="${cx}" cy="${cy}" r="${CHIP / 2 - 1}" fill="#d8ccb2" stroke="rgba(110, 100, 82, 0.5)" stroke-width="2"/>`);
        out.push(`<circle cx="${cx}" cy="${cy}" r="${CHIP / 2 - 8}" fill="none" stroke="rgba(122, 84, 28, 0.18)" stroke-width="1"/>`);
      }
    });
    y += h + 18;
  }
  const band = q('.horosa-lingqi-result-band');
  if (band) {
    const sub = q('.horosa-lingqi-result-sub', band);
    const wu = isWuDay(data.day_ganzhi ? { dayGanZi: data.day_ganzhi } : null);
    const bh = 2 + 16 + 44 + 7 + 19.6 + 13; // border + padding 16 / 13, the 卦名 line (28 px × 1.5715), 7, the attribute line
    out.push(`<rect x="${PX + 0.5}" y="${y + 0.5}" width="${W - PX * 2 - 1}" height="${bh - 1}" rx="12" fill="rgba(154, 106, 37, 0.045)" stroke="rgba(154, 106, 37, 0.3)" stroke-width="1"/>`);
    const ord = q('.horosa-lingqi-result-ordinal', band).textContent;
    const name = q('.horosa-lingqi-result-name', band).textContent;
    const xiang = q('.horosa-lingqi-result-xiang', band).textContent;
    const total = cnxWidth(ord, 13) + 2 * ord.length + 12 + cnxWidth(name, 28) + 4 * name.length + 12 + cnxWidth(xiang, 15) + xiang.length;
    let x = W / 2 - total / 2;
    const base = y + 1 + 16 + 22; // middle of the 卦名 line; 卦序 / 象 share its baseline (their line middles sit ≈ 5 px lower)
    out.push(tx(x, base + 5.2, ord, 13, MUTED, 400, 'start', ' letter-spacing="2"')); x += cnxWidth(ord, 13) + 2 * ord.length + 12;
    out.push(tx(x, base, name, 28, GOLD, 700, 'start', ' letter-spacing="4"')); x += cnxWidth(name, 28) + 4 * name.length + 12;
    out.push(tx(x, base + 4.8, xiang, 15, 'rgba(42, 47, 58, 0.85)', 400, 'start', ' letter-spacing="1"'));
    const attr = sub ? [...sub.children].filter((c) => c.tagName === 'SPAN').map((c) => c.textContent).join(' ') : '';
    const tag = wu ? '六戊日 · 古法不宜占卜' : '';
    const tagW = tag ? cnxWidth(tag, 11) + 14 : 0;
    const subW = cnxWidth(attr, 12.5) + attr.length + (tag ? 8 + tagW : 0);
    const sx = W / 2 - subW / 2;
    const subMid = y + 1 + 16 + 44 + 7 + 9.8;
    out.push(tx(sx, subMid, attr, 12.5, MUTED, 400, 'start', ' letter-spacing="1"'));
    if (tag) {
      const tx0 = sx + subW - tagW;
      out.push(`<rect x="${tx0}" y="${subMid - 8.5}" width="${tagW}" height="17" rx="3" fill="rgba(191, 60, 54, 0.07)" stroke="rgba(191, 60, 54, 0.35)" stroke-width="1"/>`);
      out.push(tx(tx0 + tagW / 2, subMid, tag, 11, '#b5493a'));
    }
    y += bh + 18;
  }
  const H = Math.ceil(y);
  const board = `<rect x="0.5" y="0.5" width="${W - 1}" height="${H - 1}" rx="12" fill="#f3ece0" stroke="rgba(154, 106, 37, 0.3)" stroke-width="1"/>`;
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">${board}${out.join('')}</svg>`;
  return { svg, width: W, height: H, themeScope: 'horosa-astro-redesign horosa-huangji-redesign' };
}
