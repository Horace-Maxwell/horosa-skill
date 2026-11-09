// 南印方盘 — the app's default India board style (IndiaChart → IndiaSouthChart, normalizeIndiaChartStyle → 'south') is an HTML
// 4 × 4 grid styled by css/styles.less. This draws it as SVG with the app's own helpers for everything that is data
// (getObjectsBySign with the page's display set AstroConst.DEFAULT_OBJECTS and no lots, getHouseNumberForSign /
// resolveLagnaRefSignNumber, getHouseCuspDegree, getObjectLabel / getObjectDegree / getObjectColor, getSignSymbol,
// getIndiaChartOptionNote) and the stylesheet's numbers for the look (900 px board, 1.5 px strong border; per cell the house
// number 18 px gold at (10, 8) with the cusp degree 12 px under it, objects 19 px name + 12 px degree + R in the
// 38 / 12 / 30 inset area, the sign glyph 20 px ywastro at the bottom-right; the 中宫 D-tile 66 px on accent).
// The cells' CSS gradients are drawn as the flat tints they read as (the bitmap path has no gradients).
import * as AstroConst from '@horosa-app/constants/AstroConst.js';
import {
  SIGN_NAMES, getHouseNumberForSign, resolveLagnaRefSignNumber, getHouseLabel, getSignSymbol, getObjectLabel,
  getObjectDegree, getObjectColor, getHouseCuspDegree, getObjectsBySign, getIndiaChartOptionNote,
} from '@horosa-app/components/astro/IndiaSouthChart.js';

const SIZE = 900;
const CELL = SIZE / 4;
// SOUTH_INDIAN_SIGN_GRID (IndiaSouthChart): fixed signs, 双鱼 top-left, clockwise
const GRID = [[12, 1, 2, 3], [11, 0, 0, 4], [10, 0, 0, 5], [9, 8, 7, 6]];
const BORDER = 'var(--horosa-border-strong, rgba(51, 111, 201, 0.30))';
const esc = (s) => `${s == null ? '' : s}`.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const latinW = (s, size) => [...`${s}`].reduce((w, ch) => w + (/[\u0000-ÿ°′″]/.test(ch) ? size * 0.56 : size), 0);

function objectRuns(obj) {
  const glyph = null; // page default planetGlyphMode = text
  const name = glyph || getObjectLabel(obj);
  const degree = getObjectDegree(obj);
  const retro = Number(obj.lonspeed) < 0;
  const width = latinW(name, 19) + 3 + latinW(degree, 12) + (retro ? 3 + latinW('R', 12) : 0);
  return { name, degree, retro, width, color: getObjectColor(obj) };
}

function cellSvg(sign, row, col, asc, bySign, chartObj) {
  const x = col * CELL;
  const y = row * CELL;
  const house = getHouseNumberForSign(sign, asc);
  const parts = [`<g transform="translate(${x},${y})">`];
  parts.push(`<rect x="0.5" y="0.5" width="${CELL - 1}" height="${CELL - 1}" fill="var(--horosa-surface-solid, #ffffff)" stroke="${BORDER}" stroke-width="1"/>`);
  parts.push(`<rect x="1" y="1" width="${CELL - 2}" height="${(CELL - 2) * 0.42}" fill="rgba(47, 125, 241, 0.018)" stroke="none"/>`);
  if (house === 1) parts.push(`<path d="M1,1 L${CELL * 0.62},1 L1,${CELL * 0.62} Z" fill="var(--horosa-accent-soft, rgba(47, 125, 241, 0.12))" stroke="none"/>`);
  parts.push(`<text x="10" y="17" font-size="18" font-weight="700" fill="var(--horosa-gold, #b8893f)" dominant-baseline="central">${esc(getHouseLabel(house))}</text>`);
  const cusp = getHouseCuspDegree(chartObj, house, sign);
  if (cusp) parts.push(`<text x="10" y="34.5" font-size="12" font-weight="600" fill="var(--horosa-text-soft, #52627a)" dominant-baseline="central">${esc(cusp)}</text>`);
  // objects: flex-wrap rows (gap 6 × 10), centred in the inset box 38 / 12 / 30
  const runs = (bySign[sign] || []).map(objectRuns);
  const boxW = CELL - 24;
  const lines = [];
  runs.forEach((run) => {
    const line = lines[lines.length - 1];
    if (line && line.width + 10 + run.width <= boxW) { line.items.push(run); line.width += 10 + run.width; } else lines.push({ items: [run], width: run.width });
  });
  const boxTop = 38;
  const boxH = CELL - 38 - 30;
  const blockH = lines.length * 18 + Math.max(0, lines.length - 1) * 6;
  lines.forEach((line, i) => {
    let lx = 12 + (boxW - line.width) / 2;
    const cy = boxTop + (boxH - blockH) / 2 + i * 24 + 9;
    line.items.forEach((run) => {
      // separate <text> per part, the name anchored at its end and the degree / R starting after it — inline <tspan>s are
      // laid out by svglib with the placeholder font's widths and overlap once the real font is in
      const split = lx + latinW(run.name, 19);
      parts.push(`<text x="${split}" y="${cy}" font-size="19" font-weight="800" fill="${run.color}" text-anchor="end" dominant-baseline="central">${esc(run.name)}</text>`);
      parts.push(`<text x="${split + 3}" y="${cy + 2}" font-size="12" font-weight="700" fill="${run.color}" dominant-baseline="central">${esc(run.degree)}</text>`);
      if (run.retro) parts.push(`<text x="${split + 6 + latinW(run.degree, 12)}" y="${cy + 2}" font-size="12" font-weight="700" fill="var(--horosa-cinnabar, #bf3c36)" dominant-baseline="central">R</text>`);
      lx += run.width + 10;
    });
  });
  parts.push(`<text x="${CELL - 8 - 12}" y="${CELL - 8 - 12}" font-size="20" font-family="ywastro" fill="var(--horosa-accent-strong, #2167d4)" text-anchor="middle" dominant-baseline="central">${esc(getSignSymbol(sign))}</text>`);
  parts.push('</g>');
  return parts.join('');
}

export function renderIndiaSouth(data) {
  const chartObj = data && data.chartObj;
  if (!chartObj || !chartObj.chart || !Array.isArray(chartObj.chart.objects)) throw new Error('india: needs chartObj.chart.objects');
  const chartnum = Number(data.chartnum) || 1;
  const label = chartnum === 1 ? '命盘' : `${chartnum}分盘`;
  const asc = resolveLagnaRefSignNumber(chartObj, data.lagnaRef);
  if (!asc || !SIGN_NAMES[asc]) throw new Error('india: no lagna sign');
  const bySign = getObjectsBySign(chartObj, AstroConst.DEFAULT_OBJECTS, []);
  const out = [];
  GRID.forEach((row, r) => row.forEach((sign, c) => { if (sign) out.push(cellSvg(sign, r, c, asc, bySign, chartObj)); }));
  // 中宫 (grid 2–3 × 2–3): panel-soft + a soft accent glow, the D tile, label and option note (gap 6)
  const cx = SIZE / 2;
  out.push(`<rect x="${CELL + 0.5}" y="${CELL + 0.5}" width="${CELL * 2 - 1}" height="${CELL * 2 - 1}" fill="var(--horosa-panel-soft, rgba(242, 247, 254, 0.78))" stroke="${BORDER}" stroke-width="1"/>`);
  out.push(`<circle cx="${cx}" cy="${SIZE * 0.45 + CELL * 0.1}" r="${CELL * 0.52}" fill="var(--horosa-accent-soft, rgba(47, 125, 241, 0.12))" fill-opacity="0.4" stroke="none"/>`);
  const note = getIndiaChartOptionNote(chartObj);
  const blockH = 66 + 6 + 20 + 6 + 16;
  const top = cx - blockH / 2;
  const dText = `D${chartnum}`;
  const dW = Math.max(66, latinW(dText, 24) + 24);
  out.push(`<rect x="${cx - dW / 2}" y="${top}" width="${dW}" height="66" rx="8" fill="var(--horosa-accent, #2f7df1)" stroke="none"/>`);
  out.push(`<text x="${cx}" y="${top + 33}" font-size="24" font-weight="800" fill="var(--horosa-on-accent, #ffffff)" text-anchor="middle" dominant-baseline="central">${esc(dText)}</text>`);
  out.push(`<text x="${cx}" y="${top + 66 + 6 + 10}" font-size="15" font-weight="700" fill="var(--horosa-text, #162033)" text-anchor="middle" dominant-baseline="central">${esc(label)}</text>`);
  out.push(`<text x="${cx}" y="${top + 66 + 6 + 20 + 6 + 8}" font-size="12" fill="var(--horosa-muted, #8794a8)" text-anchor="middle" dominant-baseline="central">${esc(note)}</text>`);
  out.push(`<rect x="0.75" y="0.75" width="${SIZE - 1.5}" height="${SIZE - 1.5}" fill="none" stroke="${BORDER}" stroke-width="1.5"/>`);
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${SIZE}" height="${SIZE}" viewBox="0 0 ${SIZE} ${SIZE}"><rect width="${SIZE}" height="${SIZE}" fill="var(--horosa-surface-solid, #ffffff)"/>${out.join('')}</svg>`;
  return { svg, width: SIZE, height: SIZE };
}
