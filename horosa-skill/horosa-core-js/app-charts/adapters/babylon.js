// 巴比伦占星 — the app's own P1 星盘 (components/babylon/BabylonHoroscope.js renderWheel: 恒星黄道宫带 + 七曜 + 距星环;
// no houses / aspects / ascendant by design). Set up as BabylonMain.render does:
//   lons = chartToLons(/chart 响应)                 — the sidereal (毕宿锚) chart the runner fetched (result.raw)
//   bab  = buildHoroscope(lons, jdn, opts)          — jdn / opts = exactly what the skill's JS used for the text
//                                                      (result.board_context, returned by tools/babylon.js)
// renderWheel() returns React elements; React 17 renderToStaticMarkup turns them into the svg markup.
import { renderToStaticMarkup } from 'react-dom/server';
import BabylonHoroscope from '@horosa-app/components/babylon/BabylonHoroscope.js';
import { buildHoroscope } from '@horosa-app/divination/babylon/horoscope.js';
import { chartToLons } from '@horosa-app/utils/babylonAiSnapshot.js';

export function renderBabylon(data) {
  const ctx = data && data.board_context;
  if (!ctx || !Number.isFinite(Number(ctx.jdn)) || !data.raw) throw new Error('babylon: needs board_context.jdn and raw');
  const opts = ctx.opts || {};
  const lons = chartToLons(data.raw);
  if (lons.sun === undefined) throw new Error('babylon: chart has no planet positions');
  const bab = buildHoroscope(lons, Number(ctx.jdn), opts);
  const view = new BabylonHoroscope({ bab, opts });
  view.props = { bab, opts };
  let svg = renderToStaticMarkup(view.renderWheel());
  // 页面里 svg 靠外层容器定尺寸（width/height 100%）；报告里给它 viewBox 的原始尺寸
  svg = svg.replace(/^<svg([^>]*?)style="[^"]*"/, '<svg$1width="600" height="600"');
  if (!/xmlns=/.test(svg.slice(0, 200))) svg = svg.replace('<svg', '<svg xmlns="http://www.w3.org/2000/svg"');
  return { svg, width: 600, height: 600 };
}
