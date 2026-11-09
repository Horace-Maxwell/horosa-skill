// 大六壬 — the app's own RengChart (components/lrzhan/RengChart.js), set up exactly as LiuRengChart.drawChart does:
//   chart / nongli   = the cast-moment chart (result.board_context.chart: objects, nongli, isDiurnal — the runner keeps it)
//   liureng          = the /liureng/gods result (result.liureng)
//   runyear          = result.runyear (行年; null for 起课)
//   zhangshengElem / panStyleName = what the headless engine used (result.headless_liureng), so the board matches the text
//   guireng / gender = the run's own inputs (board_context)
//   castOverride     = null when the headless engine reports none (app: buildLiuRengCastOverride → no override)
//   chartType        = the app default (square board, readLiurengChartType without a saved view); timeAlg 0 (default)
import RengChart from '@horosa-app/components/lrzhan/RengChart.js';
import { LRChart_Square } from '@horosa-app/components/liureng/LRConst.js';
import { mountSvg, mountTooltip, unmount } from '../dom.js';

export function renderLiureng(data, options = {}) {
  const ctx = data && data.board_context;
  if (!ctx || !ctx.chart || !Array.isArray(ctx.chart.objects) || !data.liureng) {
    throw new Error('liureng: needs board_context.chart and liureng');
  }
  const headless = data.headless_liureng || {};
  const castOverride = headless.castOverride && Object.keys(headless.castOverride).length ? headless.castOverride : null;
  const size = Number(options.size) || 760;
  const chart = JSON.parse(JSON.stringify(ctx.chart));
  // LiuRengMain.lrChartFor：/liureng/gods 的农历覆盖盘的农历（时间算法缺省 = 真太阳时时两者同一时刻）。runner 取盘时没要 nongli，
  // 于是盘上为空，取 gods 的那份——与 app 合并后的结果一致。
  if (data.liureng.nongli) chart.nongli = { ...(chart.nongli || {}), ...data.liureng.nongli };
  const { id, svg } = mountSvg(size, size);
  const { id: tipId, div } = mountTooltip();
  try {
    const renger = new RengChart({
      id, fields: {}, tooltipId: tipId, chartObj: null, nongli: chart.nongli, liureng: data.liureng, runyear: data.runyear || null,
      gender: ctx.gender, zhangshengElem: headless.zhangshengElem, guireng: ctx.guireng, castOverride,
      panStyleName: headless.panStyleName || '', onMetaInfoClick: () => {}, chartType: LRChart_Square, compactPreview: false, timeAlg: 0,
    });
    renger.fields = {};
    renger.chart = chart;
    renger.nongli = chart.nongli;
    renger.liureng = data.liureng;
    renger.runyear = data.runyear || null;
    renger.gender = ctx.gender;
    renger.zhangshengElem = headless.zhangshengElem;
    renger.guireng = ctx.guireng;
    renger.castOverride = castOverride;
    renger.panStyleName = headless.panStyleName || '';
    renger.chartType = LRChart_Square;
    renger.compactPreview = false;
    renger.timeAlg = 0;
    renger.draw();
    // 「圆形盘」是切换盘式的按钮（悬停预览），纸面上没有意义
    for (const node of svg.querySelectorAll('.liureng-circle-preview-button')) node.remove();
    return { svg: svg.outerHTML, width: size, height: size };
  } finally {
    unmount(svg, div);
  }
}
