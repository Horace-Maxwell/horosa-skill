// Shared pieces for the 卜 boards drawn in the app's horosa-cnx / huangji board language (19-cnx-divination.less): the colour
// tokens they use (resolved through the page root's scopes `.horosa-astro-redesign.horosa-huangji-redesign` — adapters return
// both as themeScope; the astro one re-points --horosa-text-secondary), the
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
  // v3.14.0: the filled 一传 pill (.horosa-cnx-seq.is-1) = the page's call-to-action ground with its ink
  ctaBg: 'var(--horosa-huangji-cta-bg, #7d5419)',
  inkOnAccent: 'var(--horosa-huangji-ink-on-accent, #fffaf0)',
  accentSoft: (alpha) => `rgba(var(--horosa-huangji-accent-rgb, 154, 106, 37), ${alpha})`,
  tone: {
    ji: 'rgba(var(--horosa-jade-rgb, 63, 156, 91), 0.72)',
    ping: 'rgba(var(--horosa-huangji-accent-rgb, 154, 106, 37), 0.62)',
    xiong: 'rgba(var(--horosa-danger-rgb, 207, 19, 34), 0.62)',
  },
};

/** Fill of a 传序 pill by its class (.horosa-cnx-seq base 16 %, .is-2 30 %, .is-3 12 %; .is-1 is the filled one). */
export function cnxSeqTone(cls) {
  const first = /(^|\s)is-1(\s|$)/.test(cls || '');
  if (first) return { fill: CNX.ctaBg, stroke: CNX.ctaBg, ink: CNX.inkOnAccent };
  const alpha = /(^|\s)is-2(\s|$)/.test(cls || '') ? 0.3 : (/(^|\s)is-3(\s|$)/.test(cls || '') ? 0.12 : 0.16);
  return { fill: CNX.accentSoft(alpha), stroke: CNX.lineStrong, ink: CNX.accentStrong };
}

export const cnxEsc = (s) => `${s == null ? '' : s}`.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

export function cnxText(x, y, s, size, color, weight = 400, anchor = 'middle', extra = '') {
  if (s == null || `${s}`.trim() === '') return '';
  return `<text x="${x}" y="${y}" font-size="${size}" font-weight="${weight}" fill="${color}" text-anchor="${anchor}" dominant-baseline="central"${extra}>${cnxEsc(s)}</text>`;
}

/** Rough advance width: CJK / full-width = 1 em, Latin / digits / punctuation ≈ 0.56 em. */
export function cnxWidth(s, size) {
  return [...`${s == null ? '' : s}`].reduce((w, ch) => w + (/[\u0000-ɏ -⁯]/.test(ch) ? size * 0.56 : size), 0);
}
