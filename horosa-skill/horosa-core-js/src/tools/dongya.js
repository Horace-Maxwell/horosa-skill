// 东亚诸术 formatter（上游 v3.14.0「命 · 其他 · 东亚」）。
//
// 一个工具七段：藏历 / 藏占（八卦 Parkha · 九宫 Mewa · 魂命煞）/ 蒙古 Zurkhai / 算命学 / 九星气学 / 洛书流年 / 易卦星盘（含推运）。
// 全部进程内计算——算法、整页数据装配、快照排版都是 vendored 上游：
//   vendor/dongya/eastAsiaArts.js      藏历（浦派时轮历）与各术的纯算术
//   vendor/dongya/eastAsiaSnapshot.js  eastAsiaParamsFromFields（字段 → 入参）· buildEastAsiaModel · eastAsiaSnapshotLines
// 本层只做三件事：把载荷包成上游的字段对象、按上游词表校验口径（认不出即结构化报错，不静默回落缺省）、原样交给上游。
//
// 「此刻」由 Python 给（payload.now_ms，服务层可冻结的时钟）：流年缺省（藏占按藏历年、洛书 / 天中杀按盘时区的公历年）与
// 易卦推运的今日环位都随它走；上游 buildEastAsiaModel 的第四个形参就是它。
// 易卦星盘读本命盘七政的黄经与宫位：payload.chart = Python 取回的整个 /chart 响应（上游页面的 props.value / 无头挂载的
// fetchChartResultForRecord）；没有就只少七政合卦那几行，上游写「没有本命盘星位,易卦星盘未出。」。
import { validateSettingValue } from '../vendor/utils/pageSettingsStore.js';
import {
  EAST_ASIA_PAGE_SETTINGS,
  EAST_ASIA_SNAPSHOT_SECTIONS,
  buildEastAsiaModel,
  eastAsiaParamsFromFields,
  eastAsiaSnapshotLines,
} from '../vendor/dongya/eastAsiaSnapshot.js';
import { parseDateParts } from '../vendor/bazi/dateStrSafe.js';

// 口径键 = 上游 buildEastAsiaModel 的 settings 键（页面设置 EAST_ASIA_PAGE_SETTINGS 的两项 + 流年）。
const SETTING_KEYS = ['fenyeVersion', 'ichingMerge'];
// 流年值域 = 上游页面流年框 / 挂载齿轮 dongyaFlowYear 的 min / max（EastAsiaMain.js InputNumber、techniqueMountSettings.js）。
export const FLOW_YEAR_RANGE = [1, 9999];

function fail(normalized, reason, message, extra) {
  return {
    tool: 'dongya',
    technique: 'dongya',
    input_normalized: normalized,
    data: { ok: false, reason, message: message || '', ...(extra || {}) },
    snapshot_text: '',
  };
}

// 上游 comp/DateTime 的两个 format 形态（eastAsiaParamsFromFields 只用这两个）：年 = 带符号整数、不补零。
function dateTimeLike(parts, timeText, zone, ad) {
  const year = parts.year > 0 && Number(ad) === -1 ? -parts.year : parts.year;
  const pad = (n) => String(n).padStart(2, '0');
  return {
    zone,
    ad: year < 0 ? -1 : 1,
    format(pattern) {
      if (pattern === 'YYYY/MM/DD') return `${year}/${pad(parts.month)}/${pad(parts.day)}`;
      if (pattern === 'HH:mm:ss') return timeText;
      throw new Error(`Unsupported format pattern: ${pattern}`);
    },
  };
}

// 口径解析：只认上游词表里的值。返回 {ok, settings} 或 {ok:false, error}。
export function resolveDongyaSettings(input) {
  const src = input && typeof input === 'object' ? input : {};
  const schema = EAST_ASIA_PAGE_SETTINGS.schema;
  const settings = {};
  for (const key of SETTING_KEYS) {
    const value = src[key];
    if (value === undefined || value === null || value === '') {
      settings[key] = schema[key].def;
      continue;
    }
    if (!validateSettingValue(schema[key], value).ok) {
      return { ok: false, error: { field: key, value, allowed: schema[key].oneOf } };
    }
    settings[key] = value;
  }
  const flow = src.flowYear;
  if (flow === undefined || flow === null || flow === '') {
    settings.flowYear = null;
  } else {
    const n = Number(flow);
    if (!Number.isInteger(n) || n < FLOW_YEAR_RANGE[0] || n > FLOW_YEAR_RANGE[1]) {
      return { ok: false, error: { field: 'flowYear', value: flow, allowed: FLOW_YEAR_RANGE } };
    }
    settings.flowYear = n;
  }
  return { ok: true, settings };
}

export function runDongya(payload) {
  const input = payload && typeof payload === 'object' ? payload : {};
  const dateText = `${input.date ?? ''}`.trim();
  const rawTime = `${input.time ?? ''}`.trim();
  const timeText = /^\d{1,2}:\d{2}$/.test(rawTime) ? `${rawTime}:00` : rawTime;
  const normalized = {
    date: dateText,
    time: timeText,
    zone: input.zone ?? null,
    lat: input.lat ?? null,
    lon: input.lon ?? null,
    ad: input.ad ?? 1,
    gender: input.gender ?? null,
  };
  const parts = parseDateParts(dateText.replace(/\//g, '-'));
  if (!parts) {
    return fail(normalized, 'missing_date', `东亚诸术需要出生日期（YYYY-MM-DD）：${JSON.stringify(dateText)}`);
  }
  if (!/^\d{2}:\d{2}:\d{2}$/.test(timeText)) {
    return fail(normalized, 'missing_time', `东亚诸术需要出生时刻（HH:mm:ss）：${JSON.stringify(rawTime)}`);
  }
  const resolved = resolveDongyaSettings(input);
  if (!resolved.ok) {
    const e = resolved.error;
    return fail(normalized, 'invalid_option',
      `东亚诸术 ${e.field} 取值无效：${JSON.stringify(e.value)}（可选：${(e.allowed || []).join(' / ')}）`, { error: e });
  }
  const settings = resolved.settings;
  Object.assign(normalized, settings);

  const moment = dateTimeLike(parts, timeText, input.zone, input.ad);
  const fields = {
    date: { value: moment },
    time: { value: moment },
    zone: { value: input.zone },
    lat: { value: input.lat },
    lon: { value: input.lon },
    gender: { value: input.gender },
  };
  const params = eastAsiaParamsFromFields(fields);
  const nowMs = Number(input.now_ms);
  const chartObj = input.chart && typeof input.chart === 'object' ? input.chart : null;

  let model;
  try {
    model = buildEastAsiaModel(params, chartObj, settings, Number.isFinite(nowMs) && nowMs > 0 ? nowMs : undefined);
  } catch (error) {
    return fail(normalized, 'dongya_calc_failed', error instanceof Error ? error.message : `${error}`);
  }
  if (!model) {
    // 上游 EastAsiaMain.emptyReason 的两句（页面右栏与中栏同一句）。
    return Number(params.ad) < 0
      ? fail(normalized, 'bc_unsupported', '公元前出生暂不排东亚诸术:干支历只覆盖公元 1 年以后。')
      : fail(normalized, 'out_of_range', '这份出生资料排不出东亚诸术(日期超出干支历范围)。');
  }
  const lines = eastAsiaSnapshotLines(model);
  return {
    tool: 'dongya',
    technique: 'dongya',
    input_normalized: normalized,
    data: {
      ok: true,
      params,
      settings: { ...settings, flowYear: model.flowYear, flowYearGiven: settings.flowYear !== null },
      sections: EAST_ASIA_SNAPSHOT_SECTIONS.slice(),
      hasChart: model.iching.rows.length > 0,
      model,
    },
    snapshot_text: lines.join('\n'),
  };
}
