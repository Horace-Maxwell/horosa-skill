// 地占 — the page's default centre view is the 护盾方盘 (GeomancyMain state centerView 'square' → renderShield), an HTML
// board. We render renderShield with the app's own code (React 17 SSR on a bare instance whose state holds the reading, the
// only thing it reads) and lay its markup out as SVG with the stylesheet's numbers (layouts/app/12-india-tarot-geomancy.less
// + GeomancyMain.less): title 14 px gold, four 族 rows (母 / 女 / 甥 / 证判) 8 px apart with an 18 px vertical group label and
// a dashed rule, four cells per row 8 px apart (radius 12, padding 8 6 7, good / bad 3 px top bar and border tint), slot
// 11 px muted with the 过去 / 现在 / 未来 tag, the 得地 mark 11 px top-right, the figure's four rows of 9 px dots (gap 9 ×
// 7), name 13 px + 10 px muted. Everything printed comes out of the app's markup.
import { createElement, Fragment } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { DOMParser } from 'linkedom';
import GeomancyMain from '@horosa-app/components/geomancy/GeomancyMain.js';

const W = 720;
const esc = (s) => `${s == null ? '' : s}`.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const t = (x, y, s, size, color, weight = 400, anchor = 'middle', extra = '') => (`${s}`.trim() ? `<text x="${x}" y="${y}" font-size="${size}" font-weight="${weight}" fill="${color}" text-anchor="${anchor}" dominant-baseline="central"${extra}>${esc(s)}</text>` : '');
const GOLD = 'var(--horosa-astro-gold, #d7ad69)';
const MUTED = 'var(--horosa-astro-muted, #8fa0b9)';
const TEN_COLOR = { full: GOLD, assist: 'var(--horosa-jx-he, #3f8f5a)', stall: 'var(--horosa-jx-other, #8c8c8c)', weak: '#b5788a' };
const cls = (el) => el.getAttribute('class') || '';

export function renderGeomancy(data) {
  const reading = data && data.reading;
  if (!reading || !Array.isArray(reading.figures16) || reading.figures16.length < 15) throw new Error('geomancy: needs reading.figures16');
  const view = Object.create(GeomancyMain.prototype);
  view.state = { result: { reading } };
  view.props = {};
  const html = renderToStaticMarkup(createElement(Fragment, null, view.renderShield(reading)));
  const doc = new DOMParser().parseFromString(`<!doctype html><html><body>${html}</body></html>`, 'text/html');
  const shield = doc.querySelector('.horosa-geomancy-shield');
  if (!shield) throw new Error('geomancy: the app rendered no shield');
  const out = [];
  const title = shield.querySelector('.horosa-geomancy-shield-title');
  out.push(t(W / 2, 10, title ? title.textContent : '', 14, GOLD, 600, 'middle', ' letter-spacing="1.4"'));
  const CELL_H = 128;
  const cellW = (W - 18 - 6 - 8 * 3) / 4;
  let y = 30;
  for (const group of shield.querySelectorAll('.horosa-geomancy-shield-rowgroup')) {
    const lab = group.querySelector('.horosa-geomancy-shield-grouplab');
    const chars = [...(lab ? lab.textContent : '')];
    chars.forEach((ch, i) => out.push(t(9, y + CELL_H / 2 + (i - (chars.length - 1) / 2) * 13, ch, 11, 'var(--horosa-text-secondary, #6b7280)')));
    out.push(`<line x1="19.5" y1="${y}" x2="19.5" y2="${y + CELL_H}" stroke="rgba(148, 163, 184, 0.35)" stroke-width="1" stroke-dasharray="3,3"/>`);
    [...group.querySelectorAll('.horosa-geomancy-shield-cell')].forEach((cell, c) => {
      const x = 24 + c * (cellW + 8);
      const tone = cls(cell).includes('is-good') ? 'good' : (cls(cell).includes('is-bad') ? 'bad' : '');
      const border = tone === 'good' ? 'rgba(89, 168, 105, 0.5)' : (tone === 'bad' ? 'rgba(191, 60, 54, 0.5)' : 'var(--horosa-border, rgba(215, 173, 105, 0.22))');
      out.push(`<rect x="${x + 0.5}" y="${y + 0.5}" width="${cellW - 1}" height="${CELL_H - 1}" rx="12" fill="var(--horosa-surface, rgba(127, 127, 127, 0.05))" stroke="${border}" stroke-width="1"/>`);
      if (tone) out.push(`<path d="M${x + 12},${y + 1} L${x + cellW - 12},${y + 1} L${x + cellW - 12},${y + 3.5} L${x + 12},${y + 3.5} Z" fill="${tone === 'good' ? '#59a869' : '#bf3c36'}" stroke="none"/>`);
      const slot = cell.querySelector('.horosa-geomancy-shield-slot');
      const when = slot && slot.querySelector('.horosa-geomancy-shield-time');
      const slotText = slot ? [...slot.childNodes].filter((n) => n.nodeType === 3).map((n) => n.textContent).join('').trim() : '';
      if (when) {
        const sw = slotText.length * 11 + 4;
        const tw = when.textContent.length * 10 + 6;
        const left = x + cellW / 2 - (sw + tw) / 2;
        out.push(t(left, y + 15, slotText, 11, MUTED, 400, 'start'));
        out.push(`<rect x="${left + sw}" y="${y + 9}" width="${tw}" height="13" rx="3" fill="var(--horosa-accent-soft, rgba(215, 173, 105, 0.14))" stroke="none"/>`);
        out.push(t(left + sw + tw / 2, y + 15.5, when.textContent, 10, GOLD));
      } else {
        out.push(t(x + cellW / 2, y + 15, slotText, 11, MUTED));
      }
      const ten = cell.querySelector('.horosa-geomancy-shield-tenancy');
      if (ten) {
        const grade = (cls(ten).match(/is-(full|assist|stall|weak)/) || [])[1];
        out.push(t(x + cellW - 4, y + 3 + 5.5, ten.textContent, 11, TEN_COLOR[grade] || GOLD, 400, 'end'));
      }
      const rows = [...cell.querySelectorAll('.horosa-geomancy-fig-dotrow')];
      const dotsTop = y + 8 + 14 + 4 + 8;
      rows.forEach((row, i) => {
        const marks = row.children.length;
        const cy = dotsTop + i * (9 + 7) + 4.5;
        const lines = cls(row.children[0] || row).includes('fig-line');
        if (lines) {
          const lw = marks === 1 ? 30 : 13;
          for (let k = 0; k < marks; k += 1) out.push(`<rect x="${x + cellW / 2 - (marks * lw + (marks - 1) * 4) / 2 + k * (lw + 4)}" y="${cy - 2}" width="${lw}" height="4" rx="2" fill="${GOLD}" stroke="none"/>`);
        } else {
          for (let k = 0; k < marks; k += 1) out.push(`<circle cx="${x + cellW / 2 + (k - (marks - 1) / 2) * 18}" cy="${cy}" r="4.5" fill="${GOLD}" stroke="none"/>`);
        }
      });
      const name = cell.querySelector('.horosa-geomancy-shield-name');
      const strong = name && name.querySelector('strong');
      const em = name && name.querySelector('em');
      out.push(t(x + cellW / 2, y + CELL_H - 7 - 12.5 - 8.1, strong ? strong.textContent : '', 13, 'var(--horosa-astro-text, #262626)', 700));
      out.push(t(x + cellW / 2, y + CELL_H - 7 - 6.25, em ? em.textContent : '', 10, MUTED));
    });
    y += CELL_H + 8;
  }
  const height = Math.ceil(y);
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${height}" viewBox="0 0 ${W} ${height}">${out.join('')}</svg>`;
  return { svg, width: W, height };
}
