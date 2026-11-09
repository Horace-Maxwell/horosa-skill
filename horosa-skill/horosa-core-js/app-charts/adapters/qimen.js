// 奇门遁甲 — the app's 遁甲盘 (components/dunjia/DunJiaBoard.js) is HTML (absolutely positioned divs with inline styles), so
// a report cannot run it as is. This draws the same board as SVG from the same pan (result.pan = the app's calcDunJia output)
// with DunJiaBoard's own numbers: 214 px cells in a 3 × 3 grid with 10 px gaps, glyphs 34 px at insets 52 / 40, palace
// labels 15 px against the 中宫 side (palacePosMap), the 中宫 天盘干 + 五合; and the summary card above it (date / 时间,
// 局 tag, colored 四柱, 局 / 值符 / 值使, 空亡 / 旬首 lines) and the 六害 legend below. Colors come from the app's own tables
// (QIMEN_HARM_COLOR + tint, BaZiColor / ZhiColor) and the light-theme tokens.
// Deviations, all forced by print: no hover popovers; 驿马 is printed as 「马」 (the page's 🐎 has no glyph in any report font);
// the 金函 day-chart layout (pan.isJinhan) is not drawn here — the skill's own drawing is used for it.
import { BaZiColor, ZhiColor } from '@horosa-app/msg/bazimsg.js';
import sealedImage from '@horosa-app/assets/sealed.png';
import { QIMEN_WU_HE } from '@horosa-app/components/dunjia/DunJiaCalc.js';
import { getBoardTimeInfo } from '@horosa-app/components/dunjia/DunJiaBoard.js';
import { QIMEN_HARM_COLOR, tint } from '@horosa-app/components/dunjia/qimenHarmColors.js';

const CELL = 214;
const GAP = 10;
const BOARD_W = CELL * 3 + GAP * 2;
const GLYPH = 34;
const INSET_X = 52;
const INSET_Y = 40;
const TEXT = 'var(--horosa-text, #262626)';
const SOFT = 'var(--horosa-text-soft, #595959)';
const MUTED = 'var(--horosa-muted, #8c8c8c)';
const GAN_COLOR = {
  甲: BaZiColor.PositiveWood, 乙: BaZiColor.NegativeWood, 丙: BaZiColor.PositiveFire, 丁: BaZiColor.NegativeFire,
  戊: BaZiColor.PositiveEarth, 己: BaZiColor.NegativeEarth, 庚: BaZiColor.PositiveMetal, 辛: BaZiColor.NegativeMetal,
  壬: BaZiColor.PositiveWater, 癸: BaZiColor.NegativeWater,
};
const LEGEND = [
  { label: '击刑', color: QIMEN_HARM_COLOR.击刑, bg: tint(QIMEN_HARM_COLOR.击刑, 10) },
  { label: '入墓', color: QIMEN_HARM_COLOR.入墓, bg: tint(QIMEN_HARM_COLOR.入墓, 12) },
  { label: '击刑+入墓', color: QIMEN_HARM_COLOR.击刑入墓, bg: tint(QIMEN_HARM_COLOR.击刑入墓, 10) },
  { label: '门迫', color: QIMEN_HARM_COLOR.门迫, bg: tint(QIMEN_HARM_COLOR.门迫, 12) },
  { label: '空亡', color: QIMEN_HARM_COLOR.空亡, bg: tint(QIMEN_HARM_COLOR.空亡, 10) },
  { label: '马 驿马', color: TEXT, bg: 'rgba(140, 140, 140, 0.10)' },
];
// DunJiaBoard palacePosMap: the palace name sits on the side facing 中宫 → [x, y, anchor] inside the cell
const PALACE_POS = {
  1: [CELL - 12, CELL - 8 - 7.5, 'end'], 2: [CELL / 2, CELL - 8 - 7.5, 'middle'], 3: [12, CELL - 8 - 7.5, 'start'],
  4: [CELL - 12, CELL / 2, 'end'], 6: [12, CELL / 2, 'start'],
  7: [CELL - 12, 8 + 7.5, 'end'], 8: [CELL / 2, 8 + 7.5, 'middle'], 9: [12, 8 + 7.5, 'start'],
};

const esc = (s) => `${s == null ? '' : s}`.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
// HTML line boxes are centred on their line-height → dominant-baseline central at the box's middle
function text(x, y, value, { size, color = TEXT, weight = 700, anchor = 'start' } = {}) {
  if (value == null || `${value}`.trim() === '') return '';
  return `<text x="${x}" y="${y}" font-size="${size}" font-weight="${weight}" fill="${color}" text-anchor="${anchor}" dominant-baseline="central">${esc(value)}</text>`;
}
const textWidth = (s, size) => [...`${s}`].reduce((w, ch) => w + (/[\u0000-ÿ]/.test(ch) ? size * 0.56 : size), 0);

function cellSvg(cell, x0, y0) {
  const parts = [`<g transform="translate(${x0},${y0})">`,
    `<rect x="0.5" y="0.5" width="${CELL - 1}" height="${CELL - 1}" rx="14" fill="var(--horosa-panel-soft, #f6f6f6)" stroke="var(--horosa-border, #ececec)" stroke-width="1"/>`];
  const mid = GLYPH / 2;
  if (cell.isCenter && !cell.isFeipan) {
    const gan = cell.tianGan || cell.diGan || '';
    const items = [gan, gan && QIMEN_WU_HE[gan] ? `五合${QIMEN_WU_HE[gan]}` : ''].filter(Boolean);
    const top = CELL / 2 - (items.length * 32 + (items.length - 1) * 4) / 2;
    items.forEach((item, i) => parts.push(text(CELL / 2, top + i * 36 + 16, item, { size: 32, color: MUTED, anchor: 'middle' })));
    parts.push('</g>');
    return parts.join('');
  }
  let ganColor = TEXT;
  if (cell.hasJiXing && cell.hasRuMu) ganColor = QIMEN_HARM_COLOR.击刑入墓;
  else if (cell.hasJiXing) ganColor = QIMEN_HARM_COLOR.击刑;
  else if (cell.hasRuMu) ganColor = QIMEN_HARM_COLOR.入墓;
  if (cell.isYiMa) {
    const gen = cell.palaceNum === 7 || cell.palaceName === '艮';
    parts.push(text(gen ? 10 : CELL - 10, gen ? CELL - 8 - 10 : 8 + 10, '马', { size: 20, anchor: gen ? 'start' : 'end', weight: 400 }));
  }
  parts.push(text(INSET_X, INSET_Y + mid, cell.tianGan, { size: GLYPH, color: ganColor }));
  if (cell.anGan) parts.push(text(INSET_X + GLYPH + 6, INSET_Y + 6 + 8, `${cell.anGan}${cell.anZhi || ''}`, { size: 16, color: MUTED, weight: 600 }));
  parts.push(text(INSET_X, CELL - INSET_Y - mid, cell.diGan, { size: GLYPH }));
  parts.push(text(CELL - INSET_X, INSET_Y + mid, cell.god, { size: GLYPH, anchor: 'end' }));
  parts.push(text(CELL - INSET_X, CELL - INSET_Y - mid, cell.tianXing, { size: GLYPH, anchor: 'end' }));
  parts.push(text(CELL / 2, CELL / 2, cell.door, { size: GLYPH, color: cell.hasMenPo ? QIMEN_HARM_COLOR.门迫 : TEXT, anchor: 'middle' }));
  const pos = PALACE_POS[cell.palaceNum];
  if (pos) {
    const titleColor = cell.hasKongWang ? QIMEN_HARM_COLOR.空亡 : (cell.isCenter ? 'var(--horosa-muted, #c7c7c7)' : 'var(--horosa-text-soft, #5f5f5f)');
    parts.push(text(pos[0], pos[1], cell.palaceName, { size: 15, color: titleColor, anchor: pos[2] }));
  }
  parts.push('</g>');
  return parts.join('');
}

export function renderQimen(data) {
  const pan = data && data.pan;
  if (!pan || !Array.isArray(pan.cells) || pan.cells.length !== 9 || !pan.ganzhi) throw new Error('qimen: needs pan.cells (9) and pan.ganzhi');
  if (pan.isJinhan) throw new Error('qimen: 金函 day-chart layout is not drawn by the report');
  const options = pan.options || {};
  const info = getBoardTimeInfo(pan);
  const out = [];
  // ── summary card (padding 12, radius 14) ──
  const pad = 12;
  let y = pad;
  const rows = [];
  // one run (no inline <tspan>: svglib lays those out with the placeholder font's widths); the page's 1.2em gap ≈ one 全角空格
  rows.push(text(pad, y + 11, `${info.dateText}\u3000${`直接时间：${info.clockHm}\u3000真太阳时：${info.solarHm}`}`, { size: 18 }));
  rows.push(text(BOARD_W - pad, y + 11, options.boardTag || '', { size: 17, color: 'var(--horosa-astro-gold, #b8860b)', weight: 800, anchor: 'end' }));
  if (pan.shiftPalace > 0) rows.push(text(BOARD_W - pad, y + 22 + 2 + 9, `（顺转${pan.shiftPalace}宫）`, { size: 14, color: SOFT, anchor: 'end' }));
  y += 22 + (pan.shiftPalace > 0 ? 20 : 0) + 6;
  const pillars = [['年', pan.ganzhi.year], ['月', pan.ganzhi.month], ['日', pan.ganzhi.day], ['时', pan.ganzhi.time]];
  if (pan.keGanZhi) pillars.push(['刻', pan.keGanZhi]);
  let px = pad;
  pillars.forEach(([label, gz]) => {
    const gan = `${gz || ''}`.substr(0, 1);
    const zhi = `${gz || ''}`.substr(1, 1);
    rows.push(text(px + 16, y + 16, gan, { size: 32, color: GAN_COLOR[gan] || TEXT, anchor: 'middle' }));
    rows.push(text(px + 16, y + 32 + 4 + 16, zhi, { size: 32, color: ZhiColor[zhi] || TEXT, anchor: 'middle' }));
    rows.push(text(px + 32 + 6, y + 34, label, { size: 24, color: MUTED }));
    px += 32 + 6 + 24 + 14;
  });
  y += 68 + 6;
  rows.push(text(pad, y + 10, `${pan.juText || ''} 值符:${pan.zhiFu || ''} 值使:${pan.zhiShi || ''}`, { size: 16 }));
  y += 20 + 4;
  const kong = options.kongMarkBoth && pan.xunKong
    ? `日空-${pan.xunKong.日空 || ''}·时空-${pan.xunKong.时空 || ''}`
    : `${options.kongModeLabel || '空亡'}-${pan.kongWang || ''}`;
  rows.push(text(pad, y + 9, `${kong} 旬首-${pan.xunShou || ''}`, { size: 14, color: SOFT, weight: 400 }));
  y += 18;
  if (pan.allKong) {
    y += 2;
    rows.push(text(pad, y + 8.5, `年空-${pan.allKong.年空} 月空-${pan.allKong.月空} 日空-${pan.allKong.日空} 时空-${pan.allKong.时空}`, { size: 13, color: SOFT, weight: 400 }));
    y += 17;
  }
  const cardH = y + pad;
  out.push(`<rect x="0.5" y="0.5" width="${BOARD_W - 1}" height="${cardH - 1}" rx="14" fill="var(--horosa-surface-solid, #fbfbfb)" stroke="var(--horosa-border, #efefef)" stroke-width="1"/>`);
  out.push(...rows);
  // ── 3 × 3 grid ──
  const gridTop = cardH + 8;
  pan.cells.forEach((cell, i) => out.push(cellSvg(cell, (i % 3) * (CELL + GAP), gridTop + Math.floor(i / 3) * (CELL + GAP))));
  const gridH = CELL * 3 + GAP * 2;
  if (pan.fengJu) {
    const w = Math.min(BOARD_W * 0.62, 430);
    out.push(`<image x="${(BOARD_W - w) / 2}" y="${gridTop + (gridH - w) / 2}" width="${w}" height="${w}" opacity="0.22" href="${sealedImage}"/>`);
  }
  // ── legend tags (13 px, padding 0 8, radius 6, gap 6) ──
  let lx = 0;
  const ly = gridTop + gridH + 12;
  LEGEND.forEach((item) => {
    const w = textWidth(item.label, 13) + 16;
    out.push(`<rect x="${lx + 0.5}" y="${ly + 0.5}" width="${w - 1}" height="21" rx="6" fill="${item.bg}" stroke="${item.color}" stroke-width="1"/>`);
    out.push(text(lx + w / 2, ly + 11, item.label, { size: 13, color: item.color, anchor: 'middle' }));
    lx += w + 6;
  });
  const height = Math.ceil(ly + 22 + 2);
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="${BOARD_W}" height="${height}" viewBox="0 0 ${BOARD_W} ${height}">${out.join('')}</svg>`;
  return { svg, width: BOARD_W, height };
}
