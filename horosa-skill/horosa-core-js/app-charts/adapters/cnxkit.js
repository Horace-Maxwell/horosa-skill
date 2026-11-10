// Shared pieces for the 卜 boards drawn in the app's horosa-cnx / huangji board language (19-cnx-divination.less): the colour
// tokens they use (resolved through the .horosa-huangji-redesign page scope — adapters return themeScope for it), the
// translucent-accent fills the stylesheet writes as color-mix(accent N%, transparent) / rgba(accent-rgb, N), a text helper
// (HTML line boxes → dominant-baseline central at the box middle) and a width estimate for laying out pills and inline runs.
export const CNX = {
  text: 'var(--horosa-huangji-text, #262626)',
  muted: 'var(--horosa-huangji-muted, #8c8c8c)',
  accent: 'var(--horosa-huangji-accent, #9a6a25)',
  accentStrong: 'var(--horosa-huangji-accent-strong, #9b6a2d)',
  line: 'var(--horosa-huangji-line, rgba(184, 137, 63, 0.18))',
  lineStrong: 'var(--horosa-huangji-line-strong, rgba(145, 110, 62, 0.40))',
  cardBg: 'var(--horosa-huangji-card-bg, rgba(255, 255, 255, 0.9))',
  accentSoft: (alpha) => `rgba(var(--horosa-huangji-accent-rgb, 154, 106, 37), ${alpha})`,
  tone: {
    ji: 'rgba(var(--horosa-jade-rgb, 63, 156, 91), 0.72)',
    ping: 'rgba(var(--horosa-huangji-accent-rgb, 154, 106, 37), 0.62)',
    xiong: 'rgba(var(--horosa-danger-rgb, 207, 19, 34), 0.62)',
  },
};

export const cnxEsc = (s) => `${s == null ? '' : s}`.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

export function cnxText(x, y, s, size, color, weight = 400, anchor = 'middle', extra = '') {
  if (s == null || `${s}`.trim() === '') return '';
  return `<text x="${x}" y="${y}" font-size="${size}" font-weight="${weight}" fill="${color}" text-anchor="${anchor}" dominant-baseline="central"${extra}>${cnxEsc(s)}</text>`;
}

/** Rough advance width: CJK / full-width = 1 em, Latin / digits / punctuation ≈ 0.56 em. */
export function cnxWidth(s, size) {
  return [...`${s == null ? '' : s}`].reduce((w, ch) => w + (/[\u0000-ɏ -⁯]/.test(ch) ? size * 0.56 : size), 0);
}
