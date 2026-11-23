// 奇门盘附加字（暗干 / 寄干 / 天禽 / 推演标记，上游 v3.15.0 QimenCellOverlay）的 SVG 写法 —— 奇门页大盘（qimen.js：直接拿
// qimenCellLayout.layoutQimenCell 的 items）与三式合一盘（sanshi.js：读 SSR 出来的 .horosa-qimen-ov div，字框已由同一个函数算好、
// 写在行内样式里）共用这一份。落位与字号一律来自上游 qimenCellLayout；这里只按 layouts/app/17-divination-cards.less 的
// .horosa-qimen-ov* 规则画：整块竖排居中、行高 1.12、每行水平居中；前缀小字「寄」「暗」0.68em + 0.12em 右缝；推演标记小药丸
// （左右内边距各 0.2em、圆角 0.3em、相邻两枚隔 0.3em、金色描边、强调色字）。
import { LINE_HEIGHT, PRE_EM, textEm } from '@horosa-app/components/dunjia/qimenCellLayout.js';

export const OV_MINOR = 'var(--horosa-qimen-minor)';
export const OV_ACCENT = 'var(--horosa-accent-strong, var(--horosa-accent))';
const OV_PRE_MUTED = 'var(--horosa-muted)';
export const PRE_SIZE = 0.68;
const TAG_PAD = 0.2;
const TAG_GAP = 0.3;
// 行内基线对齐（.horosa-qimen-ov-line align-items: baseline）：主字按 central 落在行中，0.68em 的前缀字中线比主字低 0.38·0.32 em
export const preDrop = (font) => font * 0.38 * (1 - PRE_SIZE);

const esc = (s) => `${s == null ? '' : s}`.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
function t(x, y, value, size, color, weight, anchor = 'start') {
  return `<text x="${x}" y="${y}" font-size="${size}" font-weight="${weight}" fill="${color}" text-anchor="${anchor}" dominant-baseline="central">${esc(value)}</text>`;
}

/** it = { kind: 'minor' | 'tag', font, box: {x, y, w, h}, lines: [[{ text, pre?, em? }]] }（layoutQimenCell 的 item 同形）→ SVG。 */
export function ovItemSvg(it, ox = 0, oy = 0) {
  const parts = [];
  const lh = it.font * LINE_HEIGHT;
  const top = oy + it.box.y + (it.box.h - it.lines.length * lh) / 2; // flex column + justify-content center
  it.lines.forEach((ln, i) => {
    const cy = top + (i + 0.5) * lh;
    if (it.kind === 'tag') {
      const widths = ln.map((tok) => (textEm(tok.text) + TAG_PAD * 2) * it.font);
      const total = widths.reduce((s, w) => s + w, 0) + TAG_GAP * it.font * (ln.length - 1);
      let x = ox + it.box.x + (it.box.w - total) / 2;
      ln.forEach((tok, j) => {
        const w = widths[j];
        parts.push(`<rect x="${x + 0.5}" y="${cy - lh / 2 + 0.5}" width="${w - 1}" height="${lh - 1}" rx="${0.3 * it.font}" fill="var(--horosa-accent-soft)" stroke="var(--horosa-gold-soft)" stroke-width="1"/>`);
        parts.push(t(x + w / 2, cy, tok.text, it.font, OV_ACCENT, 700, 'middle'));
        x += w + TAG_GAP * it.font;
      });
      return;
    }
    const ems = ln.map((tok) => (tok.pre ? PRE_EM * Array.from(tok.text).length : textEm(tok.text)));
    let x = ox + it.box.x + (it.box.w - ems.reduce((s, e) => s + e, 0) * it.font) / 2;
    ln.forEach((tok, j) => {
      if (tok.pre) parts.push(t(x, cy + preDrop(it.font), tok.text, it.font * PRE_SIZE, OV_PRE_MUTED, 500));
      else parts.push(t(x, cy, tok.text, it.font, OV_MINOR, 600));
      x += ems[j] * it.font;
    });
  });
  return parts.join('');
}

const px = (v) => parseFloat(`${v || ''}`) || 0;
/** SSR 出来的一个 .horosa-qimen-ov div（行内 left / top / width / height / font-size 即 layoutQimenCell 的字框）→ item。 */
export function ovItemFromDom(el, styleOf) {
  const s = styleOf(el);
  const kind = `${el.getAttribute('class') || ''}`.includes('is-tag') ? 'tag' : 'minor';
  const lines = [...el.children].filter((ln) => `${ln.getAttribute('class') || ''}`.includes('horosa-qimen-ov-line')).map((ln) => {
    const toks = [];
    ln.childNodes.forEach((node) => {
      if (node.nodeType === 3) {
        // React 把相邻的文字片段写成 文字<!-- -->文字：并成一块（宽度可加，整行居中不变）
        const last = toks[toks.length - 1];
        if (last && !last.pre && !last.tag && last.textNode) last.text += node.textContent;
        else if (`${node.textContent}`.length) toks.push({ text: node.textContent, textNode: true });
      } else if (node.nodeType === 1) {
        const c = `${node.getAttribute('class') || ''}`;
        toks.push({ text: node.textContent, pre: c.includes('horosa-qimen-ov-pre'), tag: c.includes('horosa-qimen-ov-tag') });
      }
    });
    return toks;
  });
  return { kind, font: px(s['font-size']), box: { x: px(s.left), y: px(s.top), w: px(s.width), h: px(s.height) }, lines };
}

/** 一块容器里全部附加字（三式盘的奇门格 / 格旁空格）。 */
export function ovDomSvg(container, ox, oy, styleOf) {
  return [...container.querySelectorAll('.horosa-qimen-ov')].map((el) => ovItemSvg(ovItemFromDom(el, styleOf), ox, oy)).join('');
}
