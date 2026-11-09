// 六爻 — the app's own GZChart (components/guazhan/GZChart.js), set up as GuaZhanMain.renderChart / GuaZhanChart.drawChart do:
//   yao      = the engine's lines (value / change, bottom → top); 六神 filled the app's way (fillYaoGods: SixGods[日干]),
//              cleared when the run's settings turn 六神 off (_liuSet.sixGods)
//   nongli   = result.nongli
//   analysis = the app's analyzeLiuyao(本卦, 动爻, 干支 ctx, settings) — getLiuyaoAnalysis, verbatim inputs
//   chartObj = an empty object: GZChart only checks it is present and passes it through
// The Python side only asks for this when the result's 变卦 agrees with 本卦 + 动爻 (or there is no 动爻) — same rule as the
// skill's own drawing: never draw a changed hexagram the text does not name.
import GZChart from '@horosa-app/components/guazhan/GZChart.js';
import { Gua64, SixGods } from '@horosa-app/components/gua/GuaConst.js';
import { analyzeLiuyao } from '@horosa-app/components/gua/liuyaoFacade.js';
import { normalizeLiuyaoSettings } from '@horosa-app/components/gua/liuyaoSchools.js';
import { mountSvg, mountTooltip, unmount } from '../dom.js';

function liuyaoContext(nongli, settings) {
  const yearGz = `${(settings.yearBoundary === 'lunar'
    ? (nongli.yearGZByLunar || nongli.yearGanZi || nongli.yearJieqi)
    : (nongli.yearJieqi || nongli.yearGanZi || nongli.yearGZByLunar)) || nongli.year || ''}`.trim();
  const monthGz = `${nongli.monthGanZi || ''}`.trim();
  const dayGz = `${nongli.dayGanZi || ''}`.trim();
  const hourGz = `${nongli.timeGanZi || nongli.hourGanZi || ''}`.trim();
  const jieqiName = `${nongli.jieqi || nongli.jieqiName || ''}`.trim();
  return {
    dayGan: dayGz.length >= 2 ? dayGz[0] : null, dayZhi: dayGz.length >= 2 ? dayGz[1] : null,
    monthGan: monthGz.length >= 2 ? monthGz[0] : null, monthZhi: monthGz.length >= 2 ? monthGz[1] : null,
    monthNum: (['寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥', '子', '丑'].indexOf(monthGz.length >= 2 ? monthGz[1] : '') + 1) || null,
    yearGan: yearGz.length >= 2 ? yearGz[0] : null, yearZhi: yearGz.length >= 2 ? yearGz[1] : null,
    hourZhi: hourGz.length >= 2 ? hourGz[1] : null,
    jieqiName: jieqiName || null,
  };
}

export function renderLiuyao(data, options = {}) {
  const lines = data && data.lines;
  const nongli = data && data.nongli;
  if (!Array.isArray(lines) || lines.length !== 6 || !nongli) {
    throw new Error('liuyao: needs six lines and nongli');
  }
  const yao = lines.map((line) => ({ value: line.value ? 1 : 0, change: !!line.change }));
  const index = Gua64.findIndex((gua) => gua.value.join('') === yao.map((y) => y.value).join(''));
  if (index < 0) throw new Error('liuyao: lines match no hexagram');
  const settings = normalizeLiuyaoSettings(data.liuyao_settings || {});
  const moving = [];
  yao.forEach((y, i) => { if (y.change) moving.push(i + 1); });
  const analysis = analyzeLiuyao(Gua64[index], moving, liuyaoContext(nongli, settings), settings);
  const gods = SixGods[`${nongli.dayGanZi || ''}`.substr(0, 1)] || [];
  const chartYao = yao.map((y, i) => ({ ...y, god: settings.sixGods ? (gods[i] || null) : null }));

  const width = Number(options.width) || 900;
  const height = Number(options.height) || 620;
  const { id, svg } = mountSvg(width, height);
  const { id: tipId, div } = mountTooltip();
  try {
    const gz = new GZChart({ id, chartObj: {}, fields: {}, tooltipId: tipId, nongli, analysis });
    gz.fields = {};
    gz.chart = {};
    gz.yao = chartYao;
    gz.nongli = nongli;
    gz.analysis = analysis;
    gz.draw();
    return { svg: svg.outerHTML, width, height };
  } finally {
    unmount(svg, div);
  }
}
