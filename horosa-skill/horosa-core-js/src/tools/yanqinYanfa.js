import { buildYanqinYanfaSnapshot } from '../vendor/yanqin/yanqinSnapshot.js';

/**
 * 演禽「演法」五段（流派 / 起禽 / 择日 / 占卜 / 投胎）。
 *
 * 后端 `/xianqin/pan` 不产这些段——它们是上游前端 `yanqin/yanqinSnapshot.js` 按出生四数
 * （年月日时）本地推演出来的，与 kinastro 盘面互补。故走 JS 层，Python 只传拆分后的时间。
 *
 * payload: { year, month, day, hour }（hour 为 0-23 整点小时）
 * return : { text: '<[演法·流派] … 多段拼接文本>' }
 */
export function runYanqinYanfa(payload) {
  const year = Number(payload && payload.year);
  const month = Number(payload && payload.month);
  const day = Number(payload && payload.day);
  const hour = Number(payload && payload.hour);
  if (!Number.isFinite(year) || !Number.isFinite(month) || !Number.isFinite(day)) {
    return { text: '', error: { code: 'invalid_datetime', message: 'yanqin_yanfa 需要可解析的 year/month/day。' } };
  }
  // 🔴 lunarMonth 必须透传：月禽与投胎都按**农历月**起（yanqinEngine monthQin/toutaiDu），
  // 引擎在域外（公元前 / 万年后，lunar-js 静默算错）只认调用方注入的 payload.lunarMonth，
  // 否则退公历月兜底 —— 而快照照常自信打出月禽与投胎度，不作任何标注。
  const lunarMonth = Number(payload && payload.lunarMonth);
  const raw = buildYanqinYanfaSnapshot({
    year,
    month,
    day,
    hour: Number.isFinite(hour) ? hour : 0,
    ...(Number.isFinite(lunarMonth) && lunarMonth > 0 ? { lunarMonth } : {}),
  }) || '';
  // 上游这支写成行内 `[段名] 正文`（面板里一行一条），而 skill 的导出解析器要求段头**独占一行**
  // ——同行写法会被整体误解析成一个空标题段，段虽在文本里却全部报 missing。这里只在段头后断行，
  // 正文逐字不动，快照仍与上游同源。
  const text = raw.replace(/^(\[[^\]]+\])[ \t]+/gm, '$1\n');
  return { text };
}
