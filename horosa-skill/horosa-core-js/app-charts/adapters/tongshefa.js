// 统摄法 — the app's board (TongSheFaMain.render: three renderMatrixStylePanel cards 本卦 / 错亲 / 互潜 in two columns) is HTML
// with inline styles inside antd Cards. The model is the app's own exported buildTongSheFaModel(selected) on the run's four
// chosen trigrams; each panel is rendered with the app's method (the Card wrapper — a stub here — unwrapped) and laid out as
// SVG with the inline numbers: card title 14 px 600, subtitle 12 px soft, the 卦名 pair, then the 4-column table (12 % side
// label · 38 % · 38 % · 12 %, 1 px #e8e8e8 grid — the page shows it by default) with 太阴 / 太阳 · trigram stacks (58 px wide,
// 6 px bars, 6 px apart, top line first) · 本体 / 方法 · 少阳 / 少阴 · stacks · 认识 / 宇宙.
import { createElement, Fragment } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { DOMParser } from 'linkedom';
import TongSheFaMain, { buildTongSheFaModel } from '@horosa-app/components/tongshefa/TongSheFaMain.js';
import { cnxText as tx } from './cnxkit.js';

const TEXT = 'var(--horosa-text, #333)';
const SOFT = 'var(--horosa-text-soft, #666)';
const GRID = 'var(--horosa-border, #e8e8e8)';

function stack(out, cx, top, values) {
  const lines = (values || []).slice().reverse(); // renderYaoStack: last line drawn first (top)
  lines.forEach((v, i) => {
    const y = top + i * 12;
    if (v === 1) out.push(`<rect x="${cx - 29}" y="${y}" width="58" height="6" rx="3" fill="${TEXT}" stroke="none"/>`);
    else {
      out.push(`<rect x="${cx - 29}" y="${y}" width="${58 * 0.44}" height="6" rx="3" fill="${TEXT}" stroke="none"/>`);
      out.push(`<rect x="${cx + 29 - 58 * 0.44}" y="${y}" width="${58 * 0.44}" height="6" rx="3" fill="${TEXT}" stroke="none"/>`);
    }
  });
  return lines.length * 12 - 6;
}

function panel(out, view, title, L, R, x0, y0, w) {
  const card = view.renderMatrixStylePanel(title, L, R);
  const html = renderToStaticMarkup(createElement(Fragment, null, card.props.children));
  const doc = new DOMParser().parseFromString(`<!doctype html><html><body>${html}</body></html>`, 'text/html');
  const divs = [...doc.body.children].filter((el) => el.tagName === 'DIV');
  const head = divs.map((d) => d.textContent);
  const rows = [...doc.querySelectorAll('tr')].map((tr) => [...tr.querySelectorAll('td')].map((td) => td.textContent));
  const pad = 12;
  let y = y0 + pad;
  out.push(tx(x0 + w / 2, y + 10, head[0] || title, 14, TEXT, 600)); y += 22 + 6;
  if (head.length > 2) { out.push(tx(x0 + w / 2, y + 7, head[1], 12, SOFT)); y += 17 + 5; }
  out.push(tx(x0 + w / 2, y + 10, head[head.length - 1], 14, TEXT)); y += 22 + 8;
  const tw = w - pad * 2;
  const cols = [0.12, 0.38, 0.38, 0.12].map((f) => f * tw);
  const cx = (i) => x0 + pad + cols.slice(0, i).reduce((a, b) => a + b, 0) + cols[i] / 2;
  const heights = [32, 60, 32, 32, 60, 32];
  const trigram = [null, [L.upper, R.upper], null, null, [L.lower, R.lower], null];
  rows.forEach((cells, r) => {
    const h = heights[r];
    let cxStart = x0 + pad;
    cols.forEach((cw) => { out.push(`<rect x="${cxStart}" y="${y}" width="${cw}" height="${h}" fill="none" stroke="${GRID}" stroke-width="1"/>`); cxStart += cw; });
    cells.forEach((text, c) => {
      if (trigram[r] && (c === 1 || c === 2)) {
        const bagua = trigram[r][c - 1];
        if (bagua) stack(out, cx(c), y + 6 + (h - 6 - 30) / 2, bagua.value);
        else out.push(tx(cx(c), y + h / 2, '—', 14, TEXT));
      } else if (text) {
        const small = r === 0 || r === 3;
        out.push(tx(cx(c), y + h / 2, text, small ? 13 : 14, small ? SOFT : TEXT, small ? 500 : 400));
      }
    });
    y += h;
  });
  const h = y - y0 + pad;
  out.unshift(`<rect x="${x0 + 0.5}" y="${y0 + 0.5}" width="${w - 1}" height="${h - 1}" rx="8" fill="var(--horosa-surface-solid, #fff)" stroke="var(--horosa-border, #f0f0f0)" stroke-width="1"/>`);
  return h;
}

export function renderTongshefa(data) {
  const selected = data && data.tongshefa && data.tongshefa.selected;
  if (!selected) throw new Error('tongshefa: needs tongshefa.selected');
  const model = buildTongSheFaModel(selected);
  const view = Object.create(TongSheFaMain.prototype);
  view.state = { selected, showMatrixBorder: true };
  view.props = {};
  const W = 720;
  const GAP = 8;
  const pw = (W - GAP) / 2;
  const out = [];
  const h1 = Math.max(panel(out, view, '本卦', model.baseLeft, model.baseRight, 0, 0, pw), panel(out, view, '错亲', model.oppositeLeft, model.oppositeRight, pw + GAP, 0, pw));
  const h2 = panel(out, view, '互潜', model.mutualLeft, model.mutualRight, 0, h1 + GAP, pw);
  const H = Math.ceil(h1 + GAP + h2 + 1);
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">${out.join('')}</svg>`;
  return { svg, width: W, height: H };
}
