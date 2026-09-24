// astroextra: compute 星阙 v2.4.0 本命增补 sections (12分度 / 主宰星链 / 寿命格局) from a chart object.
// The skill passes the Python `/chart` response (wrapper with .chart.objects/.houses) as payload.chart;
// this returns structured data that the Python layer formats into the astrochart export sections.
import { buildNatalExtras } from '../vendor/astroextra/natalExtras.js';

export function runAstroExtra(payload) {
  const input = payload && typeof payload === 'object' ? payload : {};
  // Accept either the full chart wrapper directly or under .chart.
  const chartObj = input.chart && input.chart.chart ? input.chart : input.chart && input.chart.objects ? { chart: input.chart } : input;
  // options.lifespanMethod：[寿命格局] 取主法（ptolemy/alcabitius/dorotheus；值域校验在 Python 侧）。
  const options = input.options && typeof input.options === 'object' ? input.options : {};
  const data = buildNatalExtras(chartObj && chartObj.chart ? chartObj : { chart: (chartObj || {}).chart }, options);
  return {
    tool: 'astroextra',
    technique: 'astroextra',
    data,
  };
}
