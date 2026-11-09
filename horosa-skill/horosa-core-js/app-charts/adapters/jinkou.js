// 金口诀 — the app's own JinKouPanChart (components/jinkou/JinKouPanChart.js), set up as JinKouChart.drawChart does:
//   chart / nongli = the cast-moment chart (result.board_context.chart) with the 六壬 农历 merged over it — JinKouMain.jkChartFor
//                    does exactly that under the page's default time basis ('direct')
//   liureng        = the /liureng/gods prerequisite the runner used (result.prerequisites.liureng)
//   jinkou         = result.jinkou — the same normalizeKinjinkouData output the page builds (assembleJinKouData)
//   guireng / gender = the run's own inputs (board_context; 金口诀页贵人缺省 0); runyear none; zhangshengElem the page
//                    default (it is stored, never drawn)
import JinKouPanChart, { JK_DESIGN_MIN_H, JK_DESIGN_MIN_W } from '@horosa-app/components/jinkou/JinKouPanChart.js';
import { mountSvg, mountTooltip, unmount } from '../dom.js';

export function renderJinkou(data, options = {}) {
  const ctx = data && data.board_context;
  if (!ctx || !ctx.chart || !Array.isArray(ctx.chart.objects) || !data.liureng || !data.jinkou) {
    throw new Error('jinkou: needs board_context.chart, liureng and jinkou');
  }
  const chart = JSON.parse(JSON.stringify(ctx.chart));
  if (data.liureng.nongli) chart.nongli = { ...(chart.nongli || {}), ...data.liureng.nongli };
  // 盘的设计尺寸不是正方形（JK_DESIGN_MIN_W × _H）：按它的比例放大一点画，版面与 app 一致
  const width = Math.round(JK_DESIGN_MIN_W * 1.2);
  const height = Math.round(JK_DESIGN_MIN_H * 1.2);
  void options;
  const { id, svg } = mountSvg(width, height);
  const { id: tipId, div } = mountTooltip();
  try {
    const pan = new JinKouPanChart({
      id, fields: {}, tooltipId: tipId, chartObj: null, nongli: chart.nongli, liureng: data.liureng, runyear: null,
      gender: ctx.gender, zhangshengElem: '土', guireng: ctx.guireng, jinkouData: data.jinkou,
    });
    pan.fields = {};
    pan.chart = chart;
    pan.nongli = chart.nongli;
    pan.liureng = data.liureng;
    pan.runyear = null;
    pan.zhangshengElem = '土';
    pan.guireng = ctx.guireng;
    pan.jinkou = data.jinkou;
    pan.gender = ctx.gender;
    pan.draw();
    return { svg: svg.outerHTML, width, height };
  } finally {
    unmount(svg, div);
  }
}
