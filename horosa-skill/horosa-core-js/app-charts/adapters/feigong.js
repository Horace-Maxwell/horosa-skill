// 飞宫小奇门 — the app's own 飞宫同心盘 (components/feigong/FeiGongMain.js renderCenter: 内环八宫卦·飞干·八门 / 外环十二支·
// 原神·建除天星, 主客宫扇环). renderCenter only reads the ju it is given, so we call it on a bare instance:
//   ju = buildJu({ zhi: 起支, dayGan, dayZhi }) — the same call the page makes (doQiJu / restore), with the run's own inputs
//        (result.feigong.qiZhi / dayGan / dayZhi = what the skill's JS used for the text)
// The method returns the page's board block (an HTML header + the svg); the report has its own caption, so we keep the svg.
import { renderToStaticMarkup } from 'react-dom/server';
import FeiGongMain from '@horosa-app/components/feigong/FeiGongMain.js';
import { buildJu } from '@horosa-app/components/feigong/core/feigongJu.js';

export function renderFeigong(data) {
  const src = data && data.feigong;
  if (!src || !src.qiZhi || !src.dayGan || !src.dayZhi) throw new Error('feigong: needs feigong.qiZhi / dayGan / dayZhi');
  const ju = buildJu({ zhi: src.qiZhi, dayGan: src.dayGan, dayZhi: src.dayZhi });
  const html = renderToStaticMarkup(FeiGongMain.prototype.renderCenter.call(Object.create(FeiGongMain.prototype), ju));
  const match = html.match(/<svg[\s\S]*<\/svg>/);
  if (!match) throw new Error('feigong: board has no svg');
  const size = 560;
  let svg = match[0].replace(/^<svg/, `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}"`);
  // 飞宫页在「卜其他」的皇极式布局里（.horosa-huangji-redesign）：--horosa-huangji-* 按该页亮色令牌解析
  return { svg, width: size, height: size, themeScope: 'horosa-huangji-redesign' };
}
