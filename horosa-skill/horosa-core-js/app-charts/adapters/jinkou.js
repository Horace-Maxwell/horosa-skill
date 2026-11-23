// 金口诀 — the app's own JinKouPanChart (components/jinkou/JinKouPanChart.js), set up as JinKouChart.drawChart does:
//   chart / nongli = the cast-moment chart (result.board_context.chart) with the 六壬 农历 merged over it — JinKouMain.jkChartFor
//                    does exactly that under the page's default time basis ('direct')
//   liureng        = the /liureng/gods prerequisite the runner used (result.prerequisites.liureng)
//   jinkou         = result.jinkou — the same normalizeKinjinkouData output the page builds (assembleJinKouData)
//   guireng / gender = the run's own inputs (board_context; 金口诀页贵人缺省 0); runyear none; zhangshengElem the page
//                    default (it is stored, never drawn)
// 没有行年（结果的 [行年] 是「无」：起课没带出生年）时，app 在右下格只印一句界面提示「起盘后显示行年/旬日/旺衰/神煞」——
// 那是给页面上「还没起盘」的人看的，印在纸上是错话（v0.50.0，评审 R-11）。按「纸面无意义的交互件剔除」去掉这句，
// 格子留空，并回一条说明（报告印在图下）。不替 app 画那几张小表，也不造行年。
import JinKouPanChart, { JK_DESIGN_MIN_H, JK_DESIGN_MIN_W } from '@horosa-app/components/jinkou/JinKouPanChart.js';
import { JinKouElementColor } from '@horosa-app/components/jinkou/JinKouCalc.js';
import { mountSvg, mountTooltip, plainTextBoard, unmount } from '../dom.js';

// result.jinkou 的每一行带着 JinKouCalc 算盘时落下的颜色（contentColor / ganColor / powerColor = 它当时的五行色板）。页面重开一个
// 事盘时会用今天的色板重算；存档里的结果不会。v3.14.0 把五行色全站统一（土 #805526 → #7a4f2a、金 #866a00 → #ab5500），升级前存下的
// 金口诀盘于是半张旧色半张新色（地支走 app 现行令牌、这几格走存档里的旧值）。按「旧色板的值 → 五行 → app 现行色板」逐格换回，
// 取色仍是 app 自己的 JinKouElementColor；别的值（非五行色、未来的新色）原样不动。
const LEGACY_ELEMENT_OF_COLOR = { '#805526': '土', '#866a00': '金' };

function withCurrentPalette(value) {
  if (Array.isArray(value)) return value.map(withCurrentPalette);
  if (!value || typeof value !== 'object') return value;
  const out = {};
  for (const [key, item] of Object.entries(value)) {
    const element = typeof item === 'string' && /Color$/.test(key) ? LEGACY_ELEMENT_OF_COLOR[item.toLowerCase()] : undefined;
    out[key] = element && JinKouElementColor[element] ? JinKouElementColor[element] : withCurrentPalette(item);
  }
  return out;
}

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
  const jinkou = withCurrentPalette(data.jinkou);
  const { id, svg } = mountSvg(width, height);
  const { id: tipId, div } = mountTooltip();
  try {
    const pan = new JinKouPanChart({
      id, fields: {}, tooltipId: tipId, chartObj: null, nongli: chart.nongli, liureng: data.liureng, runyear: null,
      gender: ctx.gender, zhangshengElem: '土', guireng: ctx.guireng, jinkouData: jinkou,
    });
    pan.fields = {};
    pan.chart = chart;
    pan.nongli = chart.nongli;
    pan.liureng = data.liureng;
    pan.runyear = null;
    pan.zhangshengElem = '土';
    pan.guireng = ctx.guireng;
    pan.jinkou = jinkou;
    pan.gender = ctx.gender;
    pan.draw();
    plainTextBoard(svg); // JinKouChart 的 <svg className="horosa-plain-text-board">（上游 v3.15.0 起）
    const note = dropRunYearPlaceholder(svg);
    return { svg: svg.outerHTML, width, height, ...(note ? { note } : {}) };
  } finally {
    unmount(svg, div);
  }
}

const RUNYEAR_PLACEHOLDER = '起盘后显示行年/旬日/旺衰/神煞';

function dropRunYearPlaceholder(svg) {
  const hits = [...svg.querySelectorAll('text')].filter((node) => (node.textContent || '').trim() === RUNYEAR_PLACEHOLDER);
  for (const node of hits) node.remove();
  return hits.length
    ? '右下格（行年 / 旬日 / 旺衰 / 神煞）留空：这次结果没有行年（起课没带出生年），app 在那里只显示一句页面上的占位提示；旬日、旺衰、神煞见正文。'
    : '';
}
