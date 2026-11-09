// 宿占 / 宿盘 — the app's own SZChart (components/suzhan/SZChart.js), fed as SuZhanMain.render prepares it:
// value = result.chart + { aspects, lots }; display flags / planets = the app defaults; form fields (time zone / place / name,
// printed in the center) = this run's params, the same values the app's form would hold.
import SZChart from '@horosa-app/components/suzhan/SZChart.js';
import * as AstroConst from '@horosa-app/constants/AstroConst.js';
import { mountSvg, mountTooltip, unmount } from '../dom.js';

export function renderSuzhan(data, options = {}) {
  const chart = data && data.chart;
  if (!chart || !chart.fixedStarSu28) {
    throw new Error('suzhan: engine result has no chart.fixedStarSu28');
  }
  const size = Number(options.size) || 760;
  AstroConst.setColorTheme(AstroConst.DefaultColorTheme);
  const params = data.params || {};
  const field = (value) => ({ value: value === undefined ? null : value });
  const fields = { zone: field(params.zone), lon: field(params.lon), lat: field(params.lat), name: field(params.name || null),
    gender: field(params.gender), doubingSu28: field(params.doubingSu28) };
  const value = { ...JSON.parse(JSON.stringify(chart)), aspects: data.aspects || {}, lots: data.lots || [] };
  // app 的盘来自 Java /chart、恒带 chart.nongli（中宫四柱）；本盘走 chart 服务时由 runner 另取同一时刻四柱放在 board_context
  if (!value.nongli && data.board_context && data.board_context.nongli) value.nongli = data.board_context.nongli;
  if (!value.nongli) throw new Error('suzhan: no nongli for the center panel');
  const { id, svg } = mountSvg(size, size);
  const { id: tipId, div } = mountTooltip();
  try {
    const sz = new SZChart(id, null, fields, tipId);
    sz.chartDisp = AstroConst.CHART_DEFAULTOPTS.reduce((sum, flag) => sum + Number(flag || 0), 0);
    sz.planetDisp = new Set(AstroConst.DEFAULT_OBJECTS);
    sz.fields = fields;
    sz.chart = value;
    sz.draw();
    return { svg: svg.outerHTML, width: size, height: size };
  } finally {
    unmount(svg, div);
  }
}
