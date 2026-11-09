// 米雄回归 / 恒星双黄道 — the app's own MichonDualRing (components/astro/MichonDualRing.js: 外圈回归黄道 + 内圈恒星黄道,
// 叠位着色, 宫位). AstroMichon.renderWheel passes the /astroextra/michon result as is; so do we (result.raw = that response,
// the same one the skill's text is formatted from). A function component with hooks → React 17 renderToStaticMarkup
// (the appearance-watch effect never runs on the server). Colors are the app's light chart palette (setColorTheme default).
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import MichonDualRing from '@horosa-app/components/astro/MichonDualRing.js';
import * as AstroConst from '@horosa-app/constants/AstroConst.js';

export function renderMichon(data, options = {}) {
  const result = data && data.raw;
  if (!result || !Array.isArray(result.superpositions) || !Array.isArray(result.planets)) {
    throw new Error('michon: needs raw.superpositions and raw.planets');
  }
  AstroConst.setColorTheme(AstroConst.DefaultColorTheme);
  const size = Number(options.size) || 680;
  let svg = renderToStaticMarkup(createElement(MichonDualRing, { result, size, height: size }));
  if (!/xmlns=/.test(svg.slice(0, 200))) svg = svg.replace('<svg', '<svg xmlns="http://www.w3.org/2000/svg"');
  return { svg, width: size, height: size };
}
