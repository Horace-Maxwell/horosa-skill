import {
  buildJyotishSnapshotLines,
  buildDashaSnapshotLines,
  buildIndiaSchoolHeaderLines,
  buildIndiaSnapshotDataSections,
  indiaCalibreLine,
} from '../vendor/india/jyotishSnapshot.js';
import {
  INDIA_DASHA_SYSTEM_OPTIONS,
  INDIA_SCHOOL_OPTIONS,
  normalizeIndiaAyanamsa,
  normalizeIndiaHouseSystem,
} from '../vendor/india/indiaConst.js';
import {
  TRANSIT_DAY_OPTIONS,
  TRANSIT_DEFAULT_SELECTION,
  TRANSIT_KIND_OPTIONS,
  TRANSIT_PLANET_OPTIONS,
  TRANSIT_SNAPSHOT_MAX_ROWS,
  buildAshtakootaLines,
  buildTransitEventLines,
  maleSideOf,
} from '../vendor/utils/indiaExtraTables.js';

/**
 * 把后端 `/india/chart` 响应里的 `jyotish` 树格式化成星阙的具名段。
 *
 * Python 侧只负责取盘（`_run_india_chart_tool` 已有的 `_call_remote`），格式化交给这里逐字同源的
 * vendored builder —— 与 ken formatter 同一分工：**后端算，JS 排版**。
 *
 * payload: {
 *   chart: <整个 /india/chart 响应>,
 *   params?: { dashaSystem, indiaSchool, dashaVariants, date: 'YYYY-MM-DD', time: 'HH:mm:ss', ad, chartnum,
 *              calibreOverrides?: { indiaHsys, indiaAyanamsa } }
 * }
 * return : {
 *   sections:   { '段名': ['行', …], … },          // buildJyotishSnapshotLines
 *   dashaLines: ['行', …],                          // [大运Dasha]：buildDashaSnapshotLines(chartObj, dashaSystem, fields)
 *   dataSections:{ '段名': ['行', …], … },        // 上游 buildIndiaSnapshotDataSections：[大运Dasha] → jyotish 各段 → [未能计算]，快照同序
 *   schoolLines:['行', …],                          // [起盘信息] 起首四行：流派 / 大运流派开关 / 当前分盘 / 分盘
 *   calibreLine:'恒星黄道·…，…',                     // [起盘信息] 口径行：indiaCalibreLine(fields, overrides)（IndiaChart.js:1113-1124）
 *   calibre:    { indiaHsys, indiaAyanamsa },       // 口径行实际用的（上游 normalize* 之后的）值，供 Python 对照后端口径
 *   transitLines:['行', …],                         // [穿界时刻]（v3.14.0）：给了 params.transit 才有；= 上游 buildTransitEventLines(entry)
 * }
 *
 * params.transit（v3.14.0，上游 IndiaChart.fetchIndiaTransitLinesHeadless 的 entry 原形）:
 *   { start: 'YYYY/MM/DD', transitPlanet, transitKind, transitDays, ayanamsa, result: </astroextra/transitevents 响应> }
 *   三个所选值必须在上游选项表（TRANSIT_PLANET_OPTIONS / TRANSIT_KIND_OPTIONS / TRANSIT_DAY_OPTIONS）里，否则 invalid_setting ——
 *   后端对认不出的星 / 事件静默换成七星 / 入星座，段头却照抄原值。
 */

// 上游 builder 读的是页面 fields（{键: {value}}，日期时间是 moment）。headless 只需 snapshotBirthDate 用到的
// format('YYYY-MM-DD') / format('HH:mm:ss') 两个形态，外加流派 / 大运流派开关两键 —— 其余键上游 builder 不读。
// skill 的公元前是 ad=-1；上游 DateTime 的公元前是 ad=0（snapshotBirthDate 见 0 即不推日期），这里对齐。
function fieldsFromParams(params) {
  const p = params && typeof params === 'object' ? params : {};
  const fields = {};
  if (p.indiaSchool) fields.indiaSchool = { value: p.indiaSchool };
  if (p.dashaVariants !== undefined && p.dashaVariants !== null && p.dashaVariants !== '') {
    fields.indiaDashaVariants = { value: p.dashaVariants };
  }
  const date = `${p.date || ''}`.replace(/\//g, '-');
  const time = `${p.time || ''}`.length === 5 ? `${p.time}:00` : `${p.time || ''}`;
  if (date && time) {
    fields.date = { value: { format: () => date } };
    fields.time = { value: { format: () => time } };
  }
  fields.ad = { value: Number(p.ad) < 0 ? 0 : 1 };
  return fields;
}

export function runIndiaJyotish(payload) {
  const chartObj = (payload && payload.chart) || null;
  if (!chartObj) {
    return { sections: {}, dashaLines: [], schoolLines: [] };
  }
  const params = (payload && payload.params) || {};
  // 值域锚定引擎词表（上游 normalize* 会把认不出的值静默归一成缺省；headless 调用方传错了要说出来）。
  const invalid = [];
  [['dashaSystem', INDIA_DASHA_SYSTEM_OPTIONS], ['indiaSchool', INDIA_SCHOOL_OPTIONS]].forEach(([key, options]) => {
    const v = params[key];
    if (v !== undefined && v !== null && v !== '' && !options.some((o) => o.value === v)) {
      invalid.push({ key, value: v, allowed: options.map((o) => o.value) });
    }
  });
  const transit = params.transit && typeof params.transit === 'object' ? params.transit : null;
  if (transit) {
    invalid.push(...invalidTransitSelection(transit));
  }
  if (invalid.length) {
    return { sections: {}, dashaLines: [], schoolLines: [], error: 'invalid_setting', invalid };
  }
  const fields = fieldsFromParams(params);
  const sections = buildJyotishSnapshotLines(chartObj) || {};
  // 上游 buildIndiaSnapshotText:1183-1187：dashaSystem 取页面/齿轮值（normalizeIndiaDashaSystem 兜 vimshottari）。
  const dashaLines = buildDashaSnapshotLines(chartObj, params.dashaSystem, fields) || [];
  // 上游 buildIndiaSnapshotText（IndiaChart.js:1300）按 buildIndiaSnapshotDataSections 出数据段（v3.12.0 起含 [未能计算]）；
  // 它从 fields.indiaDashaSystem 取体系，headless 的体系在 params.dashaSystem —— 同一值挂进 fields 再交给它。
  const dataSections = buildIndiaSnapshotDataSections(chartObj, {
    ...fields,
    ...(params.dashaSystem ? { indiaDashaSystem: { value: params.dashaSystem } } : {}),
  }) || {};
  const schoolLines = buildIndiaSchoolHeaderLines(fields, params.chartnum, null) || [];
  // [起盘信息] 口径行（上游 buildIndiaSnapshotText:1139 replaceIndiaCalibreLine(baseInfo, indiaCalibreLine(fields))）：
  // headless 的分宫制/岁差不在 fields 里而是请求体的实际口径（Python 按后端 webindiasrv 同一取值序给 overrides）；
  // indiaCalibreLine 的 overrides 分支就是上游给 props 口径留的同一入口。
  const overrides = params.calibreOverrides && typeof params.calibreOverrides === 'object' ? params.calibreOverrides : {};
  const calibreLine = indiaCalibreLine(fields, overrides);
  const calibre = {
    indiaHsys: normalizeIndiaHouseSystem(overrides.indiaHsys),
    indiaAyanamsa: normalizeIndiaAyanamsa(overrides.indiaAyanamsa),
  };
  // [穿界时刻]（上游 IndiaChart.js:1376-1396 fetchIndiaTransitLinesHeadless）：请求由 Python 发，响应连同所选三项 / 起始日 / 岁差
  // 原样交给上游 buildTransitEventLines（最多 TRANSIT_SNAPSHOT_MAX_ROWS 行，超出写「只列前 N 条」）。
  const out = { sections, dashaLines, dataSections, schoolLines, calibreLine, calibre };
  if (transit) {
    out.transitLines = buildTransitEventLines(transit) || [];
  }
  return out;
}

// 穿界表所选三项的值域 = 上游选项表（不手抄）。范围是数字，`${}` 比较与上游 optionLabel 同口径（90 与 '90' 同一档）。
const TRANSIT_SELECTION_OPTIONS = [
  ['transitPlanet', TRANSIT_PLANET_OPTIONS],
  ['transitKind', TRANSIT_KIND_OPTIONS],
  ['transitDays', TRANSIT_DAY_OPTIONS],
];

function invalidTransitSelection(selection) {
  const invalid = [];
  TRANSIT_SELECTION_OPTIONS.forEach(([key, options]) => {
    const v = selection[key];
    if (v === undefined || v === null || v === '' || !options.some((o) => `${o.value}` === `${v}`)) {
      invalid.push({ key, value: v === undefined ? null : v, allowed: options.map((o) => o.value) });
    }
  });
  return invalid;
}

/**
 * 印占四张新表里不随 `/india/chart` 回包走的两件事（v3.14.0，上游 utils/indiaExtraTables.js 逐字同源）：
 *
 *   { action: 'transit_vocab' }
 *       → { planets, kinds, days, defaults, maxRows }          // 上游选项表 / 缺省 / 快照行数上限；Python 词表与它互锚
 *   { action: 'ashtakoota_side', genderInner, genderOuter }
 *       → { maleSide: 'inner' | 'outer' }                      // 上游 maleSideOf：按记录性别定男方；都不明或同性 → 星盘 A
 *   { action: 'ashtakoota', result: </astroextra/ashtakoota 响应> }
 *       → { lines: ['行', …] }                                 // 上游 buildAshtakootaLines；回包没有 rows → []
 */
export function runIndiaTables(payload) {
  const p = payload && typeof payload === 'object' ? payload : {};
  if (p.action === 'transit_vocab') {
    return {
      planets: TRANSIT_PLANET_OPTIONS,
      kinds: TRANSIT_KIND_OPTIONS,
      days: TRANSIT_DAY_OPTIONS,
      defaults: TRANSIT_DEFAULT_SELECTION,
      maxRows: TRANSIT_SNAPSHOT_MAX_ROWS,
    };
  }
  if (p.action === 'ashtakoota_side') {
    return { maleSide: maleSideOf(p.genderInner, p.genderOuter) };
  }
  if (p.action === 'ashtakoota') {
    return { lines: buildAshtakootaLines(p.result) || [] };
  }
  return { error: 'unknown_action', action: p.action === undefined ? null : p.action, allowed: ['transit_vocab', 'ashtakoota_side', 'ashtakoota'] };
}
