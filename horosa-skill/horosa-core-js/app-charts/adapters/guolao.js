// 七政四余 — the app's own GLChart (components/guolao/GLChart.js), fed the way GuoLaoChartMain.render prepares it:
// value = result.chart + { aspects, lots } (GuoLaoChartMain.render at the pinned upstream).
// Board shape / display flags = the app's defaults (no saved preference → square board, CHART_DEFAULTOPTS, DEFAULT_OBJECTS).
import GLChart from '@horosa-app/components/guolao/GLChart.js';
import * as AstroConst from '@horosa-app/constants/AstroConst.js';
import { mountSvg, mountTooltip, unmount } from '../dom.js';

export function renderGuolao(data, options = {}) {
  const chart = data && data.chart;
  if (!chart || !chart.fixedStarSu28) {
    throw new Error('guolao: engine result has no chart.fixedStarSu28');
  }
  const size = Number(options.size) || 760;
  AstroConst.setColorTheme(AstroConst.DefaultColorTheme);
  // 中宫抬头印的是表单字段（时区 / 经纬度 / 姓名，星阙记法串）：取自这次起盘的 params，与 app 起同一盘时表单里的值相同。
  const params = data.params || {};
  const field = (value) => ({ value: value === undefined ? null : value });
  const fields = { zone: field(params.zone), lon: field(params.lon), lat: field(params.lat), name: field(params.name || null),
    gender: field(params.gender), doubingSu28: field(params.doubingSu28) };
  const value = { ...JSON.parse(JSON.stringify(chart)), aspects: data.aspects || {}, lots: data.lots || [] };
  const { id, svg } = mountSvg(size, size);
  const { id: tipId, div } = mountTooltip();
  try {
    const gl = new GLChart(id, null, fields, tipId, () => {});
    gl.chartDisp = AstroConst.CHART_DEFAULTOPTS.reduce((sum, flag) => sum + Number(flag || 0), 0);
    gl.planetDisp = new Set(AstroConst.DEFAULT_OBJECTS);
    gl.fields = fields;
    gl.chart = value;
    gl.draw();
    return { svg: svg.outerHTML, width: size, height: size };
  } finally {
    unmount(svg, div);
  }
}
