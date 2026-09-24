import { buildYanqinYanfaSnapshot } from '../vendor/yanqin/yanqinSnapshot.js';
import { YANQIN_PRESETS, YANQIN_OPTION_META } from '../vendor/yanqin/yanqinSchools.js';
import { getYanqinSettings, setYanqinSchool, setYanqinSwitch } from '../vendor/yanqin/yanqinStore.js';

/**
 * 演禽「演法」五段（流派 / 起禽 / 择日 / 占卜 / 投胎）。
 *
 * 后端 `/xianqin/pan` 不产这些段——它们是上游前端 `yanqin/yanqinSnapshot.js` 按出生四数
 * （年月日时）本地推演出来的，与 kinastro 盘面互补。故走 JS 层，Python 只传拆分后的时间。
 *
 * payload: { year, month, day, hour, lunarMonth?, school?, woBi?, xunOffset?, monthVerse?,
 *            huoYaoVariant?, sansuo?, qinWuxing? }（hour 为 0-23 整点小时）
 * return : { text: '<[演法·流派] … 多段拼接文本>', data: { ok, settings } }
 *
 * 流派/开关：上游经 yanqinStore 模块级单例（localStorage 持久）读「当前流派」；headless 没有持久化，
 * 此前恒为池本理默认、六开关不可设（sync311 F7）。这里每次调用先按 school 套预设（applyPreset 覆盖全部
 * 开关——同一进程多次调用也不串味），再逐开关 setOption（偏离预设 → school 标 custom，上游同律）。
 * 取值一律锚到引擎自带词表（YANQIN_PRESETS / YANQIN_OPTION_META），不在词表里的值结构化报错、不回落。
 */
function applyYanqinSettings(payload) {
  const rawSchool = payload.school;
  const school = rawSchool === undefined || rawSchool === null || rawSchool === '' ? 'chibenli' : `${rawSchool}`;
  if (!YANQIN_PRESETS[school]) {
    return { error: { code: 'invalid_setting', message: `演法流派 ${school} 不存在`, details: { key: 'school', value: school, allowed: Object.keys(YANQIN_PRESETS) } } };
  }
  setYanqinSchool(school);
  for (const meta of YANQIN_OPTION_META) {
    let value = payload[meta.key];
    if (value === undefined || value === null || value === '') { continue; }
    const allowed = meta.options.map((o) => o.value);
    if (typeof allowed[0] === 'boolean') {
      if (value === 1 || value === '1' || value === 'true') { value = true; }
      if (value === 0 || value === '0' || value === 'false') { value = false; }
    }
    if (!allowed.includes(value)) {
      return { error: { code: 'invalid_setting', message: `演法开关 ${meta.key}=${value} 不在词表内`, details: { key: meta.key, value, allowed } } };
    }
    setYanqinSwitch(meta.key, value);
  }
  return { settings: { ...getYanqinSettings() } };
}

export function runYanqinYanfa(payload) {
  const input = payload && typeof payload === 'object' ? payload : {};
  const year = Number(input.year);
  const month = Number(input.month);
  const day = Number(input.day);
  const hour = Number(input.hour);
  if (!Number.isFinite(year) || !Number.isFinite(month) || !Number.isFinite(day)) {
    return { text: '', data: { ok: false, error: { code: 'invalid_datetime', message: 'yanqin_yanfa 需要可解析的 year/month/day。' } } };
  }
  const applied = applyYanqinSettings(input);
  if (applied.error) {
    return { text: '', data: { ok: false, error: applied.error } };
  }
  // 🔴 lunarMonth 必须透传：月禽与投胎都按**农历月**起（yanqinEngine monthQin/toutaiDu），
  // 引擎在域外（公元前 / 万年后，lunar-js 静默算错）只认调用方注入的 payload.lunarMonth，
  // 否则退公历月兜底 —— 而快照照常自信打出月禽与投胎度，不作任何标注。
  const lunarMonth = Number(input.lunarMonth);
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
  return { text, data: { ok: true, settings: applied.settings } };
}
