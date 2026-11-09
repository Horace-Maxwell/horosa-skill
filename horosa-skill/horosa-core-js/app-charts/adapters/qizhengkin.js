// 坚七政（七政 kentang 档）— the app's own 圆形星盘 GuoLaoQizhengWheel (components/guolao/GuoLaoQizhengWheel.js: 大限环 /
// 神煞环 / 二十八宿环 / 十二宫环 / 七政与相位 / 四柱). GuoLaoChartMain.renderQizhengKinBoard passes the kentang pan as is;
// the skill's result.raw is that same pan. Its colors are custom properties and class rules in GuoLaoQizhengWheel.less
// (dark by default, `:root[data-horosa-appearance='light'] .horosa-qizheng-kin-wheel` for light) → css.js inlines them.
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import GuoLaoQizhengWheel from '@horosa-app/components/guolao/GuoLaoQizhengWheel.js';
import WHEEL_CSS from '@horosa-app/components/guolao/GuoLaoQizhengWheel.less';
import { applyComponentCss } from '../css.js';

export function renderQizhengKin(data) {
  const pan = data && data.raw;
  if (!pan || !pan.qizheng || !pan.qizheng.chart) throw new Error('qizhengkin: needs raw.qizheng');
  const html = renderToStaticMarkup(createElement(GuoLaoQizhengWheel, { pan }));
  const match = html.match(/<svg[\s\S]*<\/svg>/);
  if (!match) throw new Error('qizhengkin: wheel has no svg');
  const box = (match[0].match(/viewBox="0 0 ([\d.]+) ([\d.]+)"/) || []).slice(1).map(Number);
  const size = box[0] || 960;
  let svg = match[0].replace(/^<svg/, `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${box[1] || size}"`);
  svg = applyComponentCss(svg, WHEEL_CSS, 'horosa-qizheng-kin-wheel');
  return { svg, width: size, height: box[1] || size };
}
