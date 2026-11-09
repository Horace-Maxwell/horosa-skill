// 太乙 — the app's own TaiyiBoardSvg (components/taiyi/TaiyiBoardSvg.js), a pure React function of `pan`, rendered to
// static markup (no DOM, no effects). Props as TaiYiMain passes them with the default options: showBoardMark = false
// (盘面标注 default off), nothing selected.
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import TaiyiBoardSvg from '@horosa-app/components/taiyi/TaiyiBoardSvg.js';

export function renderTaiyi(data, options = {}) {
  const pan = data && data.pan;
  if (!pan || typeof pan !== 'object') {
    throw new Error('taiyi: engine result has no `pan`');
  }
  const html = renderToStaticMarkup(React.createElement(TaiyiBoardSvg, { pan, showBoardMark: false, selectedPalace: null }));
  const start = html.indexOf('<svg');
  const end = html.lastIndexOf('</svg>');
  if (start < 0 || end < 0) {
    throw new Error('taiyi: TaiyiBoardSvg rendered no <svg>');
  }
  let svg = html.slice(start, end + 6);
  if (!/\swidth="/.test(svg.slice(0, svg.indexOf('>')))) {
    const box = (svg.match(/viewBox="([\d.\s-]+)"/) || [])[1];
    const [, , w, h] = (box || '0 0 760 760').trim().split(/\s+/).map(Number);
    svg = svg.replace('<svg', `<svg width="${w}" height="${h}"`);
  }
  const width = Number((svg.match(/\swidth="([\d.]+)"/) || [])[1]) || 760;
  const height = Number((svg.match(/\sheight="([\d.]+)"/) || [])[1]) || 760;
  void options;
  return { svg, width, height };
}
