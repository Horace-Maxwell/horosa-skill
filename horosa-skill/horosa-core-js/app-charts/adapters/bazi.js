// 八字命盘 — the app's board is HTML: PaiBaZi (summary line) + BaZiFineChart in its default 简盘 mode (PaiBaZi state:
// chartStyle 'simple' unless 细盘 was saved), styled by layouts/app/03-bazi.less. Every value on it comes from the app's own
// code: we render BaZiFineChart with React 17's renderToStaticMarkup and read the finished board out of the markup —
// header / 主星 / 天干 / 地支 / 藏干 / 神煞 rows, the glyph colours it computed, and its 生克 connectors (left / width / top
// in percent, arrow direction) — then lay that out as SVG with the stylesheet's numbers: a 62 px label column + 4 equal
// columns, 简盘 row padding 6 px, glyphs 32 px, header 16 px muted, 主星 16 px 820, labels 14 px muted, 藏干 13 px soft,
// 神煞 11 px, connectors 2 px #c4c8cd with 7 × 9 px heads, the light-theme row tints (#fbfbfa header / 主星, #f7f7f5 地支).
// The summary line above it is PaiBaZi.render's (性别 · 农历 · 直接 / 真太阳时 · 计算基准; 节气差 · 司令 ; 调候).
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { DOMParser } from 'linkedom';
import BaZiFineChart from '@horosa-app/components/cntradition/BaZiFineChart.js';
import { BaZiMsg } from '@horosa-app/msg/bazimsg.js';
import { leapPrefix } from '@horosa-app/utils/lunarText.js';

const W = 720;
const LABEL = 62;
const COL = (W - LABEL) / 4;
const LINE = 'var(--horosa-bazi-interaction, #c4c8cd)';
const esc = (s) => `${s == null ? '' : s}`.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const t = (x, y, s, size, color, weight, anchor = 'middle') => (`${s}`.trim() ? `<text x="${x}" y="${y}" font-size="${size}" font-weight="${weight}" fill="${color}" text-anchor="${anchor}" dominant-baseline="central">${esc(s)}</text>` : '');
const pct = (style, key) => { const m = new RegExp(`${key}:\\s*([\\d.]+)%`).exec(style || ''); return m ? Number(m[1]) / 100 : null; };

function summaryLines(rec) {
  const n = rec.nongli || {};
  const lines = [];
  if (rec.nongli) {
    const clock = n.clockTime || n.birth || '';
    const solar = n.solarTime || n.birth || '';
    lines.push(`${BaZiMsg[rec.gender] || ''}  农历:${n.year || ''}年${leapPrefix(n)}${n.month || ''}${n.day || ''}  直接时间:${clock}  真太阳时:${solar}  计算基准:真太阳时`);
  }
  let extra = [n.jiedelta, n.chef].filter(Boolean).join('，');
  if (extra && n.chef) extra += '；';
  const tiaohou = Array.isArray(rec.tiaohou) && rec.tiaohou.length ? `调候：${rec.tiaohou.join('，')}` : '';
  extra = [extra, tiaohou].filter(Boolean).join(' ');
  if (extra) lines.push(extra);
  return lines;
}

export function renderBazi(data) {
  const rec = data && data.bazi;
  if (!rec || !rec.fourColumns) throw new Error('bazi: needs bazi.fourColumns');
  const html = renderToStaticMarkup(createElement(BaZiFineChart, {
    value: rec, fields: {}, mode: 'simple', showRelations: true, cangVersion: 'common', onlyZiGanShen: true, // BaZi.js baziOpt default: 副星 hidden
    school: 'zonghe', showSchoolMarks: true, showShenSha: true,
  }));
  const doc = new DOMParser().parseFromString(`<!doctype html><html><body>${html}</body></html>`, 'text/html');
  const chart = doc.querySelector('.horosa-bazi-fine-chart');
  if (!chart) throw new Error('bazi: the app rendered no board');
  const out = [];
  let y = 0;
  const summary = summaryLines(rec);
  summary.forEach((line, i) => out.push(t(0, 11 + i * 22, line, i === 0 ? 14 : 13, i === 0 ? 'var(--horosa-text, #222)' : 'var(--horosa-text-soft, #595959)', i === 0 ? 600 : 400, 'start')));
  y = summary.length ? summary.length * 22 + 10 : 0;
  const boardTop = y;
  const body = [];
  const cellsOf = (row) => [...row.children].filter((el) => (el.getAttribute('class') || '').includes('horosa-bazi-fine-cell'));
  const colX = (i) => LABEL + COL * i + COL / 2;
  for (const node of [...chart.children]) {
    const cls = node.getAttribute('class') || '';
    if (cls.includes('horosa-bazi-fine-relation-row')) continue; // 简盘: display none
    if (cls.includes('horosa-bazi-fine-row-wrap')) {
      const row = node.querySelector('.horosa-bazi-fine-row');
      const h = 44;
      const branch = (row.getAttribute('class') || '').includes('branch-row');
      body.push(`<rect x="0" y="${y}" width="${W}" height="${h}" fill="${branch ? '#f7f7f5' : 'none'}" stroke="none"/>`);
      body.push(`<line x1="0" y1="${y + 0.5}" x2="${W}" y2="${y + 0.5}" stroke="rgba(142, 148, 158, 0.10)" stroke-width="1"/>`);
      const label = row.querySelector('.horosa-bazi-fine-label');
      body.push(t(LABEL / 2, y + h / 2, label ? label.textContent : '', 14, 'var(--horosa-muted, #8c8c8c)', 760));
      cellsOf(row).forEach((cell, i) => {
        const glyph = cell.querySelector('.horosa-bazi-fine-glyph');
        if (!glyph) return;
        const color = ((glyph.getAttribute('style') || '').match(/color:\s*([^;]+)/) || [])[1] || 'var(--horosa-text, #222)';
        body.push(t(colX(i), y + h / 2, glyph.textContent, 32, color, 860));
      });
      for (const conn of node.querySelectorAll('.horosa-bazi-fine-conn-h')) {
        const style = conn.getAttribute('style') || '';
        const x1 = LABEL + (W - LABEL) * (pct(style, 'left') || 0);
        const x2 = x1 + (W - LABEL) * (pct(style, 'width') || 0);
        const cy = y + h * (pct(style, 'top') ?? 0.5);
        body.push(`<line x1="${x1}" y1="${cy}" x2="${x2}" y2="${cy}" stroke="${LINE}" stroke-width="2"/>`);
        if (conn.querySelector('.horosa-bazi-fine-conn-arrow-right')) body.push(`<path d="M${x2 + 2},${cy} L${x2 - 5},${cy - 4.5} L${x2 - 5},${cy + 4.5} Z" fill="${LINE}" stroke="none"/>`);
        if (conn.querySelector('.horosa-bazi-fine-conn-arrow-left')) body.push(`<path d="M${x1 - 2},${cy} L${x1 + 5},${cy - 4.5} L${x1 + 5},${cy + 4.5} Z" fill="${LINE}" stroke="none"/>`);
      }
      y += h;
      continue;
    }
    if (cls.includes('horosa-bazi-fine-vconn-row')) {
      const h = 22;
      cellsOf(node).forEach((cell, i) => {
        if (!cell.querySelector('.horosa-bazi-fine-conn-vline')) return;
        const x = colX(i);
        body.push(`<line x1="${x}" y1="${y + 3}" x2="${x}" y2="${y + h - 3}" stroke="${LINE}" stroke-width="2"/>`);
        if (cell.querySelector('.horosa-bazi-fine-conn-arrow-down')) body.push(`<path d="M${x},${y + h + 1} L${x - 4.5},${y + h - 6} L${x + 4.5},${y + h - 6} Z" fill="${LINE}" stroke="none"/>`);
        if (cell.querySelector('.horosa-bazi-fine-conn-arrow-up')) body.push(`<path d="M${x},${y - 1} L${x - 4.5},${y + 6} L${x + 4.5},${y + 6} Z" fill="${LINE}" stroke="none"/>`);
      });
      y += h;
      continue;
    }
    if (!cls.includes('horosa-bazi-fine-row')) continue;
    const label = node.querySelector('.horosa-bazi-fine-label');
    const cells = cellsOf(node);
    const stacked = cls.includes('hidden-row') || cls.includes('shensha-row');
    if (stacked) {
      const hidden = cls.includes('hidden-row');
      const size = hidden ? 13 : 11;
      const lh = hidden ? Math.max(14, 13 * 1.12) : 11 * 1.14;
      const pad = hidden ? 5 : 6;
      const lists = cells.map((cell) => [...cell.querySelectorAll('span')].map((s) => s.textContent).filter((s) => s.trim()));
      const maxN = Math.max(1, ...lists.map((l) => l.length));
      const h = Math.max(hidden ? 50 : 64, pad * 2 + maxN * lh + (maxN - 1));
      body.push(`<line x1="0" y1="${y + 0.5}" x2="${W}" y2="${y + 0.5}" stroke="${hidden ? 'var(--horosa-border, #ececec)' : 'rgba(142, 148, 158, 0.10)'}" stroke-width="1"/>`);
      body.push(t(LABEL / 2, y + (hidden ? 5 + 9 : h / 2), label ? label.textContent : '', 14, 'var(--horosa-muted, #8c8c8c)', 760));
      lists.forEach((list, i) => {
        const block = list.length * lh + Math.max(0, list.length - 1);
        const top = y + (h - block) / 2;
        list.forEach((item, j) => body.push(t(colX(i), top + j * (lh + 1) + lh / 2, item, size, hidden ? 'var(--horosa-text-soft, #595959)' : 'var(--horosa-text, #262626)', 720)));
      });
      y += h;
      continue;
    }
    const header = cls.includes('horosa-bazi-fine-header');
    const main = cls.includes('main-star-row');
    const h = 6 + 16 * 1.28 + 6;
    if ((header || main) && y === boardTop) body.push(`<path d="M0,${y + h} L0,${y + 16} Q0,${y} 16,${y} L${W - 16},${y} Q${W},${y} ${W},${y + 16} L${W},${y + h} Z" fill="#fbfbfa" stroke="none"/>`); // first row under the 16 px corners
    else if (header || main) body.push(`<rect x="0" y="${y}" width="${W}" height="${h}" fill="#fbfbfa" stroke="none"/>`);
    else body.push(`<line x1="0" y1="${y + 0.5}" x2="${W}" y2="${y + 0.5}" stroke="rgba(142, 148, 158, 0.10)" stroke-width="1"/>`);
    body.push(t(LABEL / 2, y + h / 2, label ? label.textContent : '', 14, 'var(--horosa-muted, #8c8c8c)', 760));
    cells.forEach((cell, i) => {
      const strong = cell.querySelector('strong');
      const text = (strong || cell).textContent;
      if (header) body.push(t(colX(i), y + h / 2, text, 16, 'var(--horosa-muted, #8c8c8c)', 780));
      else if (main) body.push(t(colX(i), y + h / 2, text, 16, 'var(--horosa-text, #262626)', 820));
      else body.push(t(colX(i), y + h / 2, text, 13, 'var(--horosa-text, #262626)', 720));
    });
    y += h;
  }
  const boardH = y - boardTop;
  out.push(`<rect x="0.5" y="${boardTop + 0.5}" width="${W - 1}" height="${boardH - 1}" rx="16" fill="var(--horosa-surface-solid, #fdfbf6)" stroke="var(--horosa-border, #ececec)" stroke-width="1"/>`);
  out.push(...body);
  const height = Math.ceil(y + 2);
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${height}" viewBox="0 0 ${W} ${height}">${out.join('')}</svg>`;
  return { svg, width: W, height };
}
