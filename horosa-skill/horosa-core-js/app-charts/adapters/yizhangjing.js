// 一掌经 — the app's 十二宫盘 (YiZhangJingMain.renderBoard(m), components/yizhangjing/yizhangjing.less) is HTML. m is the app's
// buildYizhangjingModel output; the skill's tools/yizhangjing.js computes exactly that model for the text and hands the slice
// renderBoard reads to the report as board_context. renderBoard runs with the app's own code (SSR on a bare instance) and its
// markup is laid out as SVG with the stylesheet's numbers: 4 × 4 grid, gap 8 — twelve palace cards on the 紫微-style fixed
// branch seats (branch + 生肖 10.5 px muted top-left, 命 / 年月日时 pills top-right, star 30 px gold 800, 人事宫 pill, 道 · 品
// 9.5 px at the foot; 上品 gold tint, 下品 red tint, 命宫 gold ring) round the hub (brand 11 px, 命宫主星 46 px, meta, tags).
import { createElement, Fragment } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { DOMParser } from 'linkedom';
import YiZhangJingMain from '@horosa-app/components/yizhangjing/YiZhangJingMain.js';
import { cnxText as tx, cnxWidth } from './cnxkit.js';

const GOLD = 'var(--horosa-gold, #9a6a25)';
const MUTED = 'var(--horosa-muted, #8894a6)';
const SOFT = 'var(--horosa-text-soft, #5c6a80)';
const goldSoft = (a) => `rgba(var(--horosa-gold-rgb, 154, 106, 37), ${a})`;
const cls = (el) => (el && el.getAttribute('class')) || '';

export function renderYizhangjing(data) {
  const m = data && data.yizhangjing && data.yizhangjing.board_context;
  if (!m || !m.chart || !m.chart.fourIdx) throw new Error('yizhangjing: needs board_context (renderBoard slice of the model)');
  const view = Object.create(YiZhangJingMain.prototype);
  view.state = {};
  view.props = {};
  const html = renderToStaticMarkup(createElement(Fragment, null, view.renderBoard(m)));
  const doc = new DOMParser().parseFromString(`<!doctype html><html><body>${html}</body></html>`, 'text/html');
  const q = (sel, root = doc) => root.querySelector(sel);
  const W = 720;
  const GAP = 8;
  const cw = (W - GAP * 3) / 4;
  const ch = 112;
  const out = [];
  for (const cell of doc.querySelectorAll('.horosa-yizhangjing-cell')) {
    const style = cell.getAttribute('style') || '';
    const col = Number((style.match(/grid-column:\s*(\d+)/) || [])[1]) || 1;
    const row = Number((style.match(/grid-row:\s*(\d+)/) || [])[1]) || 1;
    const x = (col - 1) * (cw + GAP);
    const y = (row - 1) * (ch + GAP);
    const c = cls(cell);
    const ming = c.includes('is-ming');
    const fill = ming ? 'var(--horosa-surface, #fdfbf6)' : (c.includes('is-up') ? goldSoft(0.09) : (c.includes('is-down') ? 'rgba(176, 72, 60, 0.07)' : 'var(--horosa-surface, #fdfbf6)'));
    const stroke = ming ? GOLD : (c.includes('is-up') ? goldSoft(0.34) : (c.includes('is-down') ? 'rgba(176, 72, 60, 0.28)' : 'var(--horosa-border, rgba(120, 120, 120, 0.24))'));
    out.push(`<rect x="${x + 0.5}" y="${y + 0.5}" width="${cw - 1}" height="${ch - 1}" rx="10" fill="${fill}" stroke="${stroke}" stroke-width="${ming ? 2.5 : 1}"/>`);
    out.push(tx(x + 8, y + 6 + 7, q('.cell-br', cell).textContent, 10.5, MUTED, 400, 'start'));
    let tagX = x + cw - 8;
    [...cell.querySelectorAll('.cell-tags > span')].reverse().forEach((tag) => {
      const isMing = cls(tag).includes('cell-ming');
      const w = Math.max(15, cnxWidth(tag.textContent, 10) + 12);
      tagX -= w;
      out.push(`<rect x="${tagX}" y="${y + 6}" width="${w}" height="15" rx="7.5" fill="${isMing ? GOLD : goldSoft(0.16)}" stroke="none"/>`);
      out.push(tx(tagX + w / 2, y + 13.5, tag.textContent, 10, isMing ? 'var(--horosa-on-accent, #fff)' : GOLD, isMing ? 800 : 700));
      tagX -= 4;
    });
    out.push(tx(x + cw / 2, y + ch * 0.44, q('.cell-star', cell).textContent, 30, GOLD, 800, 'middle', ' letter-spacing="0.6"'));
    const pal = q('.cell-palace', cell);
    if (pal && pal.textContent) {
      const pw = cnxWidth(pal.textContent, 10) + 14;
      out.push(`<rect x="${x + cw / 2 - pw / 2}" y="${y + ch * 0.44 + 20}" width="${pw}" height="14" rx="7" fill="${goldSoft(0.14)}" stroke="none"/>`);
      out.push(tx(x + cw / 2, y + ch * 0.44 + 27, pal.textContent, 10, GOLD, 700));
    }
    out.push(tx(x + cw / 2, y + ch - 6 - 6, q('.cell-foot', cell).textContent, 9.5, SOFT));
  }
  const hub = q('.horosa-yizhangjing-hub');
  if (hub) {
    const x = cw + GAP;
    const y = ch + GAP;
    const w = cw * 2 + GAP;
    const h = ch * 2 + GAP;
    out.push(`<rect x="${x + 0.5}" y="${y + 0.5}" width="${w - 1}" height="${h - 1}" rx="14" fill="var(--horosa-panel-soft, rgba(154, 106, 37, 0.05))" stroke="var(--horosa-border, rgba(120, 120, 120, 0.24))" stroke-width="1"/>`);
    const get = (sel) => { const el = q(sel, hub); return el ? el.textContent : ''; };
    const tags = [...hub.querySelectorAll('.hub-tags span')].map((s) => s.textContent);
    const blockH = 15 + 6 + 15 + 2 + 51 + 2 + 16 + (tags.length ? 8 + 20 : 0);
    let yy = y + (h - blockH) / 2;
    out.push(tx(x + w / 2, yy + 7.5, get('.hub-brand'), 11, MUTED, 400, 'middle', ' letter-spacing="0.6"')); yy += 15 + 6;
    out.push(tx(x + w / 2, yy + 7.5, get('.hub-title'), 11.5, SOFT)); yy += 15 + 2;
    out.push(tx(x + w / 2, yy + 25, get('.hub-star'), 46, GOLD, 800)); yy += 51 + 2;
    out.push(tx(x + w / 2, yy + 8, get('.hub-meta'), 12, SOFT)); yy += 16;
    if (tags.length) {
      const widths = tags.map((t) => cnxWidth(t, 11) + 20);
      let tx0 = x + w / 2 - (widths.reduce((a, b) => a + b, 0) + 6 * (tags.length - 1)) / 2;
      tags.forEach((t, i) => {
        out.push(`<rect x="${tx0}" y="${yy + 8}" width="${widths[i]}" height="19" rx="9.5" fill="${goldSoft(0.14)}" stroke="none"/>`);
        out.push(tx(tx0 + widths[i] / 2, yy + 17.5, t, 11, GOLD));
        tx0 += widths[i] + 6;
      });
    }
  }
  const H = ch * 4 + GAP * 3;
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">${out.join('')}</svg>`;
  return { svg, width: W, height: H };
}
