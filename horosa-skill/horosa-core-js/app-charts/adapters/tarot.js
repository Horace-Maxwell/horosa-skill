// 塔罗 — the app's spread (TarotMain.renderCenter) is HTML: the stage title, the significator slot, then the cards — absolutely
// placed on the spread's geometry (computeGeoLayout: 680 px wide, the 凯尔特 crossing card turned 90°), a grid (单张 / 三张 /
// 年度 / 36 张大阵), the row-labelled matrix (TP5 大阵) or the 开钥 piles — over the 牌阵连线 <svg>, and the attribution line.
// The run's board_context is the reading the engine drew (card ids, orientation, positions, deck, settings); the card objects are
// taken back from the app's own deck tables by id (the sid must match, otherwise nothing is drawn). We render renderCenter with
// the app's own code (SSR on a bare instance, artStyle = the page default 'image') and lay its markup out as SVG with the
// stylesheet's light-theme numbers (layouts/app/12-india-tarot-geomancy.less + the zoom rules in 22-tail-fixes.less, which load
// later and win over the geo-slot sizes: card min-height 152, symbol 30 px, name 15 px, picture ≤ 96 px):
//   card     border 1 px in the suit colour, radius 12, padding 11 / 7 (geo slot 6 / 4), items 5 px apart (geo 2), contents
//            centred; light ground = --horosa-surface-raised
//   items    position 11 px muted · face (picture or symbol, name 15 px / 640, English 10 px) — the face turns 180° for a reversed
//            card · 正位 / 逆位 pill 11 px (逆位 in --horosa-warn) · 四色阶 dots · correspondences 10 px · 尊位 pill 10 px ·
//            keywords 11 px; the geo slot hides English, correspondences, 尊位 and keywords
// Pictures: the app's cardImageUrl names the file (tarot-art/<deck>/<file>.jpg). `options.art` lists the files this install ships
// ({ href: [w, h] }, from the Python package); a card whose file is not listed falls back to the symbol face — the app's own
// <img onError> fallback. The <image> keeps the app-relative href; the Python side embeds the file. Symbols are drawn in the
// `horosa-optional-glyph` family: a symbol no report font can print is dropped there instead of printing a box.
import { createElement, Fragment } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { DOMParser } from 'linkedom';
import TarotMain from '@horosa-app/components/tarot/TarotMain.js';
import { getDeck, getDeckCards } from '@horosa-app/components/tarot/engine/deckRegistry.js';
import { makeBlankCard } from '@horosa-app/components/tarot/decks/core78.js';
import { SPREADS } from '@horosa-app/components/tarot/engine/spreads.js';
import { statePatchFromSavedSettings } from '@horosa-app/components/tarot/engine/settingsMap.js';
import TAROT_LESS from '@horosa-app/layouts/app/12-india-tarot-geomancy.less?text';
import { parseRules } from '../css.js';
import { cnxEsc as esc, cnxWidth } from './cnxkit.js';

const LH = 1.5715; // antd 4 body line-height (spans in the card inherit it)
const TEXT = 'var(--horosa-astro-text, #e8ecf3)';
const MUTED = 'var(--horosa-astro-muted, #8fa0b9)';
const GOLD = 'var(--horosa-astro-gold, #d7ad69)';
const WARN = 'var(--horosa-warn)';
const CARD_BG = 'var(--horosa-surface-raised, #f3efe6)';
export const OPTIONAL_GLYPH = 'horosa-optional-glyph';

// .horosa-tarot-page re-points the astro tokens for this page; light adds its own --horosa-astro-blue (correspondences)
const PAGE_TOKENS = (() => {
  const rules = parseRules(TAROT_LESS).filter((r) => r.selector === '.horosa-tarot-page');
  const tokens = {};
  [...rules.filter((r) => !r.light), ...rules.filter((r) => r.light)].forEach((r) => r.decls.forEach(([k, v]) => { if (k.startsWith('--')) tokens[k] = v; }));
  return tokens;
})();
const BLUE = PAGE_TOKENS['--horosa-astro-blue'] || '#3a6ea5';

function width(s, size, spacing = 0) {
  return cnxWidth(s, size) + [...`${s == null ? '' : s}`].length * spacing;
}

/** Greedy line breaking the way a narrow flex item wraps: anywhere between CJK characters, at spaces in Latin runs. */
function wrap(s, size, max) {
  const text = `${s == null ? '' : s}`.trim();
  if (!text) return [];
  if (max <= 0 || width(text, size) <= max) return [text];
  const tokens = text.match(/[A-Za-z0-9.'’()\-]+ ?|\s+|./gu) || [];
  const lines = [];
  let line = '';
  for (const token of tokens) {
    if (line && width(line + token, size) > max) {
      lines.push(line.trimEnd());
      line = token.trimStart();
    } else {
      line += token;
    }
  }
  if (line.trim()) lines.push(line.trimEnd());
  return lines;
}

function tx(x, y, s, size, color, weight = 400, anchor = 'middle', extra = '') {
  if (s == null || `${s}`.trim() === '') return '';
  return `<text x="${x.toFixed(2)}" y="${y.toFixed(2)}" font-size="${size}" font-weight="${weight}" fill="${color}" text-anchor="${anchor}" dominant-baseline="central"${extra}>${esc(s)}</text>`;
}

function styleOf(el) {
  const out = {};
  `${(el && el.getAttribute('style')) || ''}`.split(';').forEach((decl) => {
    const i = decl.indexOf(':');
    if (i > 0) out[decl.slice(0, i).trim()] = decl.slice(i + 1).trim();
  });
  return out;
}

const has = (el, cls) => !!el && ` ${el.getAttribute('class') || ''} `.includes(` ${cls} `);
const kids = (el) => [...(el ? el.children : [])];

// ─────────────────────────────── one card ───────────────────────────────

/** Measure a .horosa-tarot-card: a list of items (in DOM order, hidden ones dropped) with their heights, at outer width w. */
function measureCard(card, w, geo, art) {
  const padX = geo ? 4 : 7;
  const padY = geo ? 6 : 11;
  const inner = w - 2 - padX * 2;
  const style = styleOf(card);
  const items = [];
  for (const el of kids(card)) {
    if (has(el, 'horosa-tarot-card-pos')) {
      items.push({ type: 'lines', lines: wrap(el.textContent, 11, inner), size: 11, lh: 11 * LH, color: MUTED });
    } else if (has(el, 'horosa-tarot-card-face')) {
      const fs = styleOf(el);
      const parts = [];
      const img = el.querySelector('.horosa-tarot-card-img');
      const src = img && img.getAttribute('src');
      const symbol = el.querySelector('.horosa-tarot-card-symbol');
      if (src && art[src]) {
        const [iw, ih] = art[src];
        const pw = Math.min(inner, 96); // max-width 96 (22-tail-fixes); the geo slot's 100% is narrower anyway
        parts.push({ type: 'image', src, w: pw, h: pw * ih / iw, alt: img.getAttribute('alt') || '' });
      } else if (symbol) {
        // no picture for this deck / card (or not shipped) → the symbol face, as the app's <img onError> does
        parts.push({ type: 'symbol', text: symbol.textContent, size: 30, h: 30, color: fs.color || GOLD });
      }
      const name = el.querySelector('.horosa-tarot-card-name');
      if (name) {
        const lines = wrap(name.textContent, 15, inner);
        parts.push({ type: 'lines', lines, size: 15, lh: 15 * LH, color: TEXT, weight: 640 });
      }
      const en = el.querySelector('.horosa-tarot-card-en');
      if (en && !geo) parts.push({ type: 'lines', lines: wrap(en.textContent, 10, inner), size: 10, lh: 12, color: MUTED });
      parts.forEach((p) => { if (p.type === 'lines') p.h = p.lines.length * p.lh; });
      const h = parts.reduce((t, p) => t + p.h, 0) + Math.max(0, parts.length - 1) * 3;
      items.push({ type: 'face', parts, h, reversed: /rotate\(180deg\)/.test(fs.transform || '') });
    } else if (has(el, 'horosa-tarot-card-orient')) {
      const reversed = has(el, 'is-reversed');
      items.push({ type: 'pill', text: el.textContent, size: 11, padX: 8, h: 11 * LH + 4, radius: 9, color: reversed ? WARN : MUTED });
    } else if (has(el, 'horosa-tarot-scales')) {
      if (geo) continue;
      const dots = [...el.querySelectorAll('.horosa-tarot-scale-dot span')].map((d) => styleOf(d).background).filter(Boolean);
      const label = el.querySelector('.horosa-tarot-scale-lbl');
      items.push({ type: 'scales', dots, label: label ? label.textContent : '', h: 10 * 1.35 });
    } else if (has(el, 'horosa-tarot-corr')) {
      if (geo) continue;
      const lines = wrap(el.textContent, 10, inner);
      items.push({ type: 'lines', lines, size: 10, lh: 13.5, color: BLUE });
    } else if (has(el, 'horosa-tarot-dignity')) {
      if (geo) continue;
      const tone = has(el, 'is-strong') ? GOLD : has(el, 'is-weak') ? WARN : MUTED;
      items.push({ type: 'pill', text: el.textContent, size: 10, padX: 6, h: 15 + 2, radius: 8, color: tone });
    } else if (has(el, 'horosa-tarot-card-kw')) {
      if (geo) continue;
      const lines = wrap(el.textContent, 11, inner);
      items.push({ type: 'lines', lines, size: 11, lh: 11 * 1.4, color: MUTED });
    }
  }
  items.forEach((it) => { if (it.type === 'lines') it.h = it.lines.length * it.lh; });
  const content = items.reduce((t, it) => t + it.h, 0) + Math.max(0, items.length - 1) * (geo ? 2 : 5);
  return { items, padY, gap: geo ? 2 : 5, h: Math.max(152, content + padY * 2 + 2), content, border: style['border-color'] || GOLD, dashed: /dashed/.test(style['border-style'] || '') };
}

function drawLines(out, item, cx, top) {
  item.lines.forEach((line, i) => out.push(tx(cx, top + item.lh * (i + 0.5), line, item.size, item.color, item.weight || 400)));
}

function drawCard(m, x, y, w, h) {
  const out = [];
  out.push(`<rect x="${(x + 0.5).toFixed(2)}" y="${(y + 0.5).toFixed(2)}" width="${(w - 1).toFixed(2)}" height="${(h - 1).toFixed(2)}" rx="12" fill="${CARD_BG}" stroke="${m.border}" stroke-width="1"${m.dashed ? ' stroke-dasharray="4 3"' : ''}/>`);
  const cx = x + w / 2;
  let top = y + (h - m.content) / 2; // justify-content: center
  for (const it of m.items) {
    if (it.type === 'lines') {
      drawLines(out, it, cx, top);
    } else if (it.type === 'pill') {
      const pw = width(it.text, it.size) + it.padX * 2 + 2;
      out.push(`<rect x="${(cx - pw / 2).toFixed(2)}" y="${(top + 0.5).toFixed(2)}" width="${pw.toFixed(2)}" height="${(it.h - 1).toFixed(2)}" rx="${it.radius}" fill="none" stroke="${it.color}" stroke-width="1"/>`);
      out.push(tx(cx, top + it.h / 2, it.text, it.size, it.color));
    } else if (it.type === 'scales') {
      const lw = it.label ? width(it.label, 9) + 3 : 0;
      const total = it.dots.length * 9 + Math.max(0, it.dots.length - 1) * 2 + (it.dots.length ? 2 : 0) + lw;
      let sx = cx - total / 2;
      it.dots.forEach((color) => {
        out.push(`<rect x="${sx.toFixed(2)}" y="${(top + (it.h - 9) / 2).toFixed(2)}" width="9" height="9" rx="2" fill="${color}" stroke="none"/>`);
        sx += 11;
      });
      if (it.label) out.push(tx(sx + 3, top + it.h / 2, it.label, 9, BLUE, 400, 'start', ' opacity="0.7"'));
    } else if (it.type === 'face') {
      const face = [];
      let fy = top;
      for (const p of it.parts) {
        if (p.type === 'image') {
          face.push(`<image href="${esc(p.src)}" x="${(cx - p.w / 2).toFixed(2)}" y="${fy.toFixed(2)}" width="${p.w.toFixed(2)}" height="${p.h.toFixed(2)}" preserveAspectRatio="none"/>`);
        } else if (p.type === 'symbol') {
          face.push(tx(cx, fy + p.h / 2, p.text, p.size, p.color, 400, 'middle', ` font-family="${OPTIONAL_GLYPH}"`));
        } else {
          drawLines(face, p, cx, fy);
        }
        fy += p.h + 3;
      }
      const mid = top + it.h / 2;
      // transform: rotate(180deg) on .horosa-tarot-card-face (about its own centre) — the picture and the names turn together
      out.push(it.reversed ? `<g transform="translate(${cx.toFixed(2)} ${mid.toFixed(2)}) rotate(180) translate(${(-cx).toFixed(2)} ${(-mid).toFixed(2)})">${face.join('')}</g>` : face.join(''));
    }
    top += it.h + m.gap;
  }
  return out.join('');
}

// ─────────────────────────────── the stage ───────────────────────────────

function sigSlot(el) {
  const ribbon = el.querySelector('.horosa-tarot-sig-ribbon');
  const symbol = el.querySelector('.horosa-tarot-card-symbol');
  const name = el.querySelector('.horosa-tarot-card-name');
  const face = el.querySelector('.horosa-tarot-card-face');
  const color = styleOf(face).color || GOLD;
  const rows = [
    ribbon && { text: ribbon.textContent, size: 10, h: 10 * LH + 2, color: GOLD, extra: ' letter-spacing="1"', gapAfter: 0 },
    symbol && { text: symbol.textContent, size: 30, h: 30, color, glyph: true, gapAfter: 3 },
    name && { text: name.textContent, size: 15, h: 15 * LH, color: TEXT, weight: 640, gapAfter: 0 },
  ].filter(Boolean);
  const w = Math.max(...rows.map((r) => width(r.text, r.size))) + 28 + 2.8;
  const h = rows.reduce((t, r) => t + r.h + r.gapAfter, 0) + 12 + 2.8;
  return { w, h, rows, border: styleOf(el)['border-color'] || GOLD };
}

function drawSig(s, cx, y) {
  const out = [`<rect x="${(cx - s.w / 2 + 0.7).toFixed(2)}" y="${(y + 0.7).toFixed(2)}" width="${(s.w - 1.4).toFixed(2)}" height="${(s.h - 1.4).toFixed(2)}" rx="10" fill="${CARD_BG}" stroke="${s.border}" stroke-width="1.4" stroke-dasharray="5 3"/>`];
  let top = y + 6 + 1.4;
  for (const r of s.rows) {
    out.push(tx(cx, top + r.h / 2, r.text, r.size, r.color, r.weight || 400, 'middle', `${r.extra || ''}${r.glyph ? ` font-family="${OPTIONAL_GLYPH}"` : ''}`));
    top += r.h + r.gapAfter;
  }
  return out.join('');
}

function layoutGeo(geoEl, x0, y0, art) {
  const gs = styleOf(geoEl);
  const W = parseFloat(gs.width) || 680;
  const H = parseFloat(gs.height) || 340;
  const out = [];
  const lines = geoEl.querySelector('.horosa-tarot-lines');
  if (lines) out.push(`<g transform="translate(${x0} ${y0})">${kids(lines).map((l) => l.outerHTML).join('')}</g>`);
  for (const slot of kids(geoEl).filter((el) => has(el, 'horosa-tarot-geo-slot'))) {
    const ss = styleOf(slot);
    const card = slot.querySelector('.horosa-tarot-card');
    if (!card) continue;
    const w = parseFloat(ss.width);
    const cx = x0 + (parseFloat(ss.left) / 100) * W;
    const cy = y0 + (parseFloat(ss.top) / 100) * H;
    const m = measureCard(card, w, true, art);
    const body = drawCard(m, cx - w / 2, cy - m.h / 2, w, m.h);
    const turned = /rotate\(90deg\)/.test(ss.transform || '');
    const opacity = ss.opacity ? ` opacity="${ss.opacity}"` : '';
    out.push(turned || opacity
      ? `<g${opacity}${turned ? ` transform="translate(${cx.toFixed(2)} ${cy.toFixed(2)}) rotate(90) translate(${(-cx).toFixed(2)} ${(-cy).toFixed(2)})"` : ''}>${body}</g>`
      : body);
  }
  return { svg: out.join(''), h: H, w: W };
}

function layoutGrid(gridEl, x0, y0, W, art) {
  const cols = Number((styleOf(gridEl)['grid-template-columns'] || '').match(/repeat\((\d+)/)?.[1]) || 1;
  const gap = 10;
  const cw = (W - gap * (cols - 1)) / cols;
  const cards = kids(gridEl).filter((el) => has(el, 'horosa-tarot-card'));
  const out = [];
  let y = y0;
  for (let r = 0; r * cols < cards.length; r += 1) {
    const row = cards.slice(r * cols, r * cols + cols).map((el) => measureCard(el, cw, false, art));
    const rh = Math.max(...row.map((m) => m.h)); // grid rows stretch their items
    row.forEach((m, c) => out.push(drawCard(m, x0 + c * (cw + gap), y, cw, rh)));
    y += rh + gap;
  }
  return { svg: out.join(''), h: Math.max(0, y - y0 - gap) };
}

function layoutMatrix(matEl, x0, y0, W, art) {
  const cols = Number((styleOf(matEl)['grid-template-columns'] || '').match(/repeat\((\d+)/)?.[1]) || 1;
  const gap = 6;
  const labelW = 72;
  const cw = (W - labelW - gap * cols) / cols;
  const cells = kids(matEl);
  const per = cols + 1;
  const out = [];
  let y = y0;
  const labelLines = (el, w) => wrap(el.textContent, 11.5, w - 4);
  for (let r = 0; r * per < cells.length; r += 1) {
    const row = cells.slice(r * per, r * per + per);
    const header = !row[0].textContent && !row[0].children.length; // the empty corner opens the column-label row
    const measured = row.map((el, i) => {
      if (i === 0 || header) return { label: labelLines(el, i === 0 ? labelW : cw), h: labelLines(el, i === 0 ? labelW : cw).length * 11.5 * 1.4 };
      const card = el.querySelector('.horosa-tarot-card');
      return card ? { card: measureCard(card, cw, false, art) } : { dot: true, h: 18 * LH };
    });
    const rh = Math.max(header ? 20 : 96, ...measured.map((m) => (m.card ? m.card.h : m.h)));
    measured.forEach((m, i) => {
      const x = i === 0 ? x0 : x0 + labelW + gap + (i - 1) * (cw + gap);
      const w = i === 0 ? labelW : cw;
      if (m.card) {
        out.push(drawCard(m.card, x, y, w, rh));
      } else if (m.dot) {
        out.push(tx(x + w / 2, y + rh / 2, '·', 18, 'var(--horosa-text-secondary)'));
      } else {
        m.label.forEach((line, k) => out.push(tx(x + w / 2, y + (rh - m.h) / 2 + 11.5 * 1.4 * (k + 0.5), line, 11.5, GOLD)));
      }
    });
    y += rh + gap;
  }
  return { svg: out.join(''), h: Math.max(0, y - y0 - gap) };
}

// 开钥: the significator line (12 px, margin 2 / 6), then .horosa-tarot-ook-zones (padding 2, zones 9 apart): each zone border 1 +
// padding 8 / 10, radius 8; head (badge 11 px / 640 on gold, op name 12.5 px / 600, pile 11 px muted; 7 apart, margin-bottom 7);
// the counting chain wraps (gap 3): mini cards min 44 / max 62 wide, padding 4 / 3, symbol 18 px (line 1.1, turned for 逆位),
// name 9.5 px (line 1.15, margin-top 1), › arrows 13 px; op 5 is a summary line 11.5 px (line 1.7).
function layoutOok(stage, x0, y0, W) {
  const out = [];
  let y = y0;
  const sig = stage.querySelector('.horosa-tarot-ook-sig');
  if (sig) {
    const b = sig.querySelector('b');
    const spans = [...sig.querySelectorAll('span')];
    const head = [...sig.childNodes].filter((n) => n.nodeType === 3).map((n) => n.textContent).join('').trim();
    const runs = [{ t: head, c: TEXT }, b && { t: b.textContent, c: GOLD, w: 700 }, ...spans.map((sp) => ({ t: sp.textContent, c: styleOf(sp).color || GOLD, glyph: true }))].filter((r) => r && r.t);
    const total = runs.reduce((t, r) => t + width(r.t, 12) + 4, -4);
    let x = x0 + W / 2 - total / 2;
    runs.forEach((r) => {
      out.push(tx(x, y + 2 + 12 * LH / 2, r.t, 12, r.c, r.w || 400, 'start', r.glyph ? ` font-family="${OPTIONAL_GLYPH}"` : ''));
      x += width(r.t, 12) + 4;
    });
    y += 2 + 12 * LH + 6 + 12;
  }
  y += 2; // .horosa-tarot-ook-zones padding
  const zx = x0 + 2;
  const zw = W - 4;
  const left = zx + 11;
  const innerW = zw - 22;
  const zones = [...stage.querySelectorAll('.horosa-tarot-ook-zone')];
  zones.forEach((zone) => {
    const zo = [];
    let zy = y + 9;
    const head = zone.querySelector('.horosa-tarot-ook-zone-head');
    let hx = left;
    const headH = 12.5 * LH;
    for (const el of kids(head)) {
      if (has(el, 'horosa-tarot-ook-badge')) {
        const bw = width(el.textContent, 11) + 14;
        zo.push(`<rect x="${hx.toFixed(2)}" y="${(zy + (headH - 11 * LH - 2) / 2).toFixed(2)}" width="${bw.toFixed(2)}" height="${(11 * LH + 2).toFixed(2)}" rx="4" fill="${GOLD}" stroke="none"/>`);
        zo.push(tx(hx + bw / 2, zy + headH / 2, el.textContent, 11, '#1b1206', 640));
        hx += bw + 7;
      } else {
        const pile = has(el, 'horosa-tarot-ook-pile');
        const size = pile ? 11 : 12.5;
        zo.push(tx(hx, zy + headH / 2, el.textContent, size, pile ? MUTED : TEXT, has(el, 'horosa-tarot-ook-opname') ? 600 : 400, 'start'));
        hx += width(el.textContent, size) + 7;
      }
    }
    zy += headH + 7;
    const chain = zone.querySelector('.horosa-tarot-ook-chain');
    const line = zone.querySelector('.horosa-tarot-ook-line');
    if (chain) {
      // measure the flex items, wrap them into rows, centre each item on its row (align-items: center)
      const items = kids(chain).map((el) => {
        if (has(el, 'horosa-tarot-ook-mini')) {
          const sym = el.querySelector('.horosa-tarot-ook-mini-sym');
          const name = el.querySelector('.horosa-tarot-ook-mini-name');
          const lines = wrap(name ? name.textContent : '', 9.5, 62 - 8);
          const w = Math.min(62, Math.max(44, Math.max(18, ...lines.map((l) => width(l, 9.5))) + 8));
          return { el, kind: 'mini', sym, lines, w, h: 10 + 18 * 1.1 + 1 + lines.length * 9.5 * 1.15 };
        }
        if (has(el, 'horosa-tarot-ook-arrow')) return { el, kind: 'arrow', w: width(el.textContent, 13), h: 13 * LH };
        return { el, kind: 'text', w: width(el.textContent, 13), h: 13 * LH };
      });
      const rows = [[]];
      let used = 0;
      items.forEach((it) => {
        const need = (rows[rows.length - 1].length ? 3 : 0) + it.w;
        if (rows[rows.length - 1].length && used + need > innerW) { rows.push([]); used = 0; }
        used += (rows[rows.length - 1].length ? 3 : 0) + it.w;
        rows[rows.length - 1].push(it);
      });
      rows.forEach((row, r) => {
        const rh = Math.max(...row.map((it) => it.h));
        let cx = left;
        row.forEach((it) => {
          const top = zy + (rh - it.h) / 2;
          if (it.kind === 'mini') {
            const border = styleOf(it.el)['border-color'] || GOLD;
            zo.push(`<rect x="${(cx + 0.5).toFixed(2)}" y="${(top + 0.5).toFixed(2)}" width="${(it.w - 1).toFixed(2)}" height="${(it.h - 1).toFixed(2)}" rx="6" fill="rgba(0, 0, 0, 0.04)" stroke="${border}" stroke-width="1"/>`);
            if (has(it.el, 'is-sig')) zo.push(`<rect x="${(cx - 1).toFixed(2)}" y="${(top - 1).toFixed(2)}" width="${(it.w + 2).toFixed(2)}" height="${(it.h + 2).toFixed(2)}" rx="7" fill="none" stroke="${GOLD}" stroke-width="2"/>`);
            const ss = styleOf(it.sym);
            const mid = cx + it.w / 2;
            const symY = top + 5 + 18 * 1.1 / 2;
            const symText = tx(mid, symY, it.sym ? it.sym.textContent : '', 18, ss.color || GOLD, 400, 'middle', ` font-family="${OPTIONAL_GLYPH}"`);
            zo.push(/rotate\(180deg\)/.test(ss.transform || '') ? `<g transform="translate(${mid.toFixed(2)} ${symY.toFixed(2)}) rotate(180) translate(${(-mid).toFixed(2)} ${(-symY).toFixed(2)})">${symText}</g>` : symText);
            it.lines.forEach((l, k) => zo.push(tx(mid, top + 5 + 18 * 1.1 + 1 + 9.5 * 1.15 * (k + 0.5), l, 9.5, TEXT)));
          } else {
            zo.push(tx(cx + it.w / 2, top + it.h / 2, it.el.textContent, 13, it.kind === 'arrow' ? MUTED : 'var(--horosa-text-secondary)'));
          }
          cx += it.w + 3;
        });
        zy += rh + (r < rows.length - 1 ? 3 : 0);
      });
    } else if (line) {
      const lines = wrap(line.textContent, 11.5, innerW);
      lines.forEach((l, k) => zo.push(tx(left, zy + 11.5 * 1.7 * (k + 0.5), l, 11.5, MUTED, 400, 'start')));
      zy += lines.length * 11.5 * 1.7;
    }
    const zh = zy + 9 - y;
    const op5 = has(zone, 'is-op5');
    out.push(`<rect x="${(zx + 0.5).toFixed(2)}" y="${(y + 0.5).toFixed(2)}" width="${(zw - 1).toFixed(2)}" height="${(zh - 1).toFixed(2)}" rx="8" fill="rgba(215, 173, 105, ${op5 ? 0.08 : 0.06})" stroke="rgba(215, 173, 105, ${op5 ? 0.4 : 0.22})" stroke-width="1"/>`);
    out.push(zo.join(''));
    y += zh + 9;
  });
  if (zones.length) y -= 9;
  y += 2;
  return { svg: out.join(''), h: Math.max(0, y - y0) };
}

// ─────────────────────────────── entry ───────────────────────────────

function resolver(deck) {
  const byId = new Map(getDeckCards(deck.id).map((c) => [c.id, c]));
  return (ref) => {
    if (!ref) return null;
    let card = byId.get(ref.cardId);
    if (!card && ref.sid === 'blank' && ref.cardId === deck.size) card = makeBlankCard(deck.size); // TP4 空白牌 (78 + 1)
    if (!card || card.sid !== ref.sid) throw new Error(`tarot: card ${ref.cardId} / ${ref.sid} is not in the app's ${deck.id} deck`);
    return card;
  };
}

export function renderTarot(data, options = {}) {
  const bc = data && data.board_context;
  if (!bc || !Array.isArray(bc.draws)) throw new Error('tarot: needs board_context.draws (the engine reading)');
  const deck = getDeck(bc.deckId);
  if (!deck || deck.id !== bc.deckId) throw new Error(`tarot: unknown deck ${bc.deckId}`);
  if (!SPREADS[bc.spreadType]) throw new Error(`tarot: unknown spread ${bc.spreadType}`);
  const resolve = resolver(deck);
  const sig = bc.significator ? resolve(bc.significator) : null;
  const ook = bc.ook && Array.isArray(bc.ook.operations)
    ? { ...bc.ook, operations: bc.ook.operations.map((op) => ({ ...op, chain: op.chain.map((it) => ({ card: resolve(it), isReversed: !!it.isReversed })) })) }
    : bc.ook;
  const reading = {
    deckId: deck.id, deckTitle: deck.title, deckCaps: deck.caps, spreadType: bc.spreadType, spreadTitle: SPREADS[bc.spreadType].label,
    settings: bc.settings || {},
    significator: sig ? { sid: sig.sid, cardId: sig.id, card: sig } : null,
    draws: bc.draws.map((d) => ({ ...d, card: resolve(d), ...(d.overlay ? { overlay: { ...d.overlay, card: resolve(d.overlay) } } : {}) })),
    firstReversal: bc.firstReversal || null,
    ook,
  };
  const view = Object.create(TarotMain.prototype);
  view.state = { ...statePatchFromSavedSettings(reading.settings, {}), deckId: deck.id, spreadType: bc.spreadType, artStyle: 'image', reading };
  view.props = {};
  const html = renderToStaticMarkup(createElement(Fragment, null, view.renderCenter()));
  const doc = new DOMParser().parseFromString(`<!doctype html><html><body>${html}</body></html>`, 'text/html');
  const stage = doc.querySelector('.horosa-tarot-stage');
  if (!stage) throw new Error(`tarot: no spread to draw (${(doc.body.textContent || '').trim().slice(0, 80)})`);
  const art = options.art && typeof options.art === 'object' ? options.art : {};
  const PAD = 8;
  const IW = 680;
  const W = IW + PAD * 2;
  const out = [];
  let y = PAD;
  const title = stage.querySelector('.horosa-tarot-stage-title');
  out.push(tx(W / 2, y + 15 * LH / 2, title.textContent, 15, GOLD, 640, 'middle', ' letter-spacing="1.8"'));
  y += 15 * LH + 12;
  const sigEl = stage.querySelector('.horosa-tarot-sig-card');
  if (sigEl) {
    const s = sigSlot(sigEl);
    out.push(drawSig(s, W / 2, y));
    y += s.h + 8 + 12;
  }
  const geo = stage.querySelector('.horosa-tarot-geo');
  const grid = stage.querySelector('.horosa-tarot-grid');
  const matrix = stage.querySelector('.horosa-tarot-matrix');
  let body;
  if (geo) body = layoutGeo(geo, PAD + (IW - (parseFloat(styleOf(geo).width) || IW)) / 2, y, art);
  else if (grid) body = layoutGrid(grid, PAD, y, IW, art);
  else if (matrix) body = layoutMatrix(matrix, PAD, y, IW, art);
  else if (stage.querySelector('.horosa-tarot-ook-zones')) body = layoutOok(stage, PAD, y, IW);
  else throw new Error('tarot: unknown stage layout');
  out.push(body.svg);
  y += body.h + 12;
  const attr = stage.querySelector('.horosa-tarot-attr');
  if (attr) {
    const lines = wrap(attr.textContent, 10, IW);
    lines.forEach((l, k) => out.push(tx(W / 2, y + 10 * LH * (k + 0.5), l, 10, MUTED, 400, 'middle', ' opacity="0.7"')));
    y += lines.length * 10 * LH;
  }
  const H = Math.ceil(y + PAD);
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">${out.join('')}</svg>`;
  return { svg, width: W, height: H };
}
