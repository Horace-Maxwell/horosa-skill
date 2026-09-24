import {
  buildJyotishSnapshotLines,
  buildDashaSnapshotLines,
  buildIndiaSchoolHeaderLines,
  indiaCalibreLine,
} from '../vendor/india/jyotishSnapshot.js';
import {
  INDIA_DASHA_SYSTEM_OPTIONS,
  INDIA_SCHOOL_OPTIONS,
  normalizeIndiaAyanamsa,
  normalizeIndiaHouseSystem,
} from '../vendor/india/indiaConst.js';

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
 *   schoolLines:['行', …],                          // [起盘信息] 起首四行：流派 / 大运流派开关 / 当前分盘 / 分盘
 *   calibreLine:'恒星黄道·…，…',                     // [起盘信息] 口径行：indiaCalibreLine(fields, overrides)（IndiaChart.js:1113-1124）
 *   calibre:    { indiaHsys, indiaAyanamsa },       // 口径行实际用的（上游 normalize* 之后的）值，供 Python 对照后端口径
 * }
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
  if (invalid.length) {
    return { sections: {}, dashaLines: [], schoolLines: [], error: 'invalid_setting', invalid };
  }
  const fields = fieldsFromParams(params);
  const sections = buildJyotishSnapshotLines(chartObj) || {};
  // 上游 buildIndiaSnapshotText:1183-1187：dashaSystem 取页面/齿轮值（normalizeIndiaDashaSystem 兜 vimshottari）。
  const dashaLines = buildDashaSnapshotLines(chartObj, params.dashaSystem, fields) || [];
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
  return { sections, dashaLines, schoolLines, calibreLine, calibre };
}
