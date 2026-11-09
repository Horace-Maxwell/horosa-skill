// 紫微斗数 — the app's own ZWChart (components/ziwei/ZWChart.js), fed `chart` exactly as ZiWeiChart does.
// The rule library only feeds hover tooltips, so a static render gets empty tables.
import ZWChart, { ZW_DESIGN_MIN } from '@horosa-app/components/ziwei/ZWChart.js';
import { mountSvg, mountTooltip, unmount } from '../dom.js';

// 引擎给的经纬度是「121e28」「31n13」（度 + 方位字母 + 分）。app 中宫用 Number() 判数值：「121e28」恰是合法的科学计数法
// （1.21e30），于是被当成数字转成 1°7′4″E —— 上游 bug（notes-local/upstream-reports/2026-11-09-ziwei-center-lon-sci-notation.md），
// app 自己遇到同样的串也会这样。这里只做无损的记法换算（度 + 分/60 → 十进制度），交给 app 自己的 formatLonDms 排版。
function compassToDecimal(value, positive, negative) {
  const m = typeof value === 'string' && value.trim().toLowerCase().match(/^(\d{1,3})([a-z])(\d{1,2})(?:\.(\d+))?$/);
  if (!m || (m[2] !== positive && m[2] !== negative)) return value;
  const degrees = Number(m[1]) + Number(`${m[3]}${m[4] ? `.${m[4]}` : ''}`) / 60;
  return m[2] === negative ? -degrees : degrees;
}

export function renderZiwei(data, options = {}) {
  const chart = data && (data.chart || data);
  if (!chart || !Array.isArray(chart.houses) || chart.houses.length !== 12) {
    throw new Error('ziwei: engine result has no 12-house `chart`');
  }
  const size = Math.max(Number(options.size) || ZW_DESIGN_MIN, ZW_DESIGN_MIN);
  const { id, svg } = mountSvg(size, size);
  const { id: tipId, div } = mountTooltip();
  try {
    // 中宫档位是 app 的用户偏好（ZiWeiHelper.zwCenterContent 读 localStorage）：报告要把中宫信息直接印出来 = full。
    localStorage.setItem('ziweiCenterContent', options.center || 'full');
    const zw = new ZWChart(id, null, {}, tipId, () => {}, () => {});
    zw.fields = {};
    zw.rules = { ZWRules: { RuleHouses: {}, RuleStars: {}, RuleSihua: {} } };
    const value = JSON.parse(JSON.stringify(chart));
    value.lon = compassToDecimal(value.lon, 'e', 'w');
    value.lat = compassToDecimal(value.lat, 'n', 's');
    zw.chart = value;
    zw.draw();
    // 「命盘信息」是点开详情的按钮，纸面上没有意义（详情已由 full 档画进中宫）。
    for (const node of svg.querySelectorAll('.horosa-ziwei-center-info-button')) node.remove();
    return { svg: svg.outerHTML, width: size, height: size };
  } finally {
    unmount(svg, div);
  }
}
