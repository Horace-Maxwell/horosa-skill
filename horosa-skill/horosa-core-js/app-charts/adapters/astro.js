// Western wheel — the app's own AstroChartCircle (components/astro/AstroChartCircle.js), fed the chart-service
// response exactly as the app's AstroChart feeds it (`value` = { params, chart, aspects, lots, ... }).
import * as d3 from 'd3';
import AstroChartCircle from '@horosa-app/components/astro/AstroChartCircle.js';
import * as AstroConst from '@horosa-app/constants/AstroConst.js';
import { mountSvg, mountTooltip, unmount } from '../dom.js';

const RSTEP = 30; // AstroChart's state.rStep

export function renderNatalWheel(value, options = {}) {
  if (!value || !value.chart) {
    throw new Error('natal wheel: engine result has no `chart`');
  }
  const size = Number(options.size) || 760;
  AstroConst.setColorTheme(AstroConst.DefaultColorTheme);
  const { id, svg } = mountSvg(size, size);
  const { id: tipId, div } = mountTooltip();
  try {
    const circle = new AstroChartCircle({ divTooltip: d3.select(`#${tipId}`), onTipClick: () => {} });
    const planetDisp = new Set([...AstroConst.DEFAULT_OBJECTS, ...AstroConst.DEFAULT_LOTS]);
    circle.drawChart(id, value, RSTEP, AstroConst.CHART_DEFAULTOPTS, planetDisp, null, AstroConst.CHART_STYLE_CURRENT);
    return { svg: svg.outerHTML, width: size, height: size };
  } finally {
    unmount(svg, div);
  }
}
