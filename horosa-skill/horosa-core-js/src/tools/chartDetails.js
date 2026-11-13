import {
  CHART_DETAIL_DEFAULTS,
  CHART_DETAIL_OPTIONS,
  CHART_DETAIL_TABLES,
  buildChartDetailsText,
  chartDetailRequestFields,
} from '../vendor/utils/chartDetails.js';

/**
 * [盘面细节]（上游 v3.14.0，占星右栏「细节」页签 30 张表的结论摘要）。
 *
 * 算全在后端 `/astroextra/chartdetails`（astrostudy/chart_details.py），请求由 Python 发；这里只做两件事，
 * 都用 vendored 上游 `utils/chartDetails.js` 的原函数：
 *   1. `chartDetailRequestFields(settings)` —— 五项口径 → 请求体键（缺省不下发）。Python 侧发请求前自己也算了一份，
 *      拿这里回传的 `request_fields` 逐键比对，不一致即报错（请求体是手抄件，值错了后端照样算出一张「合理」的表）。
 *   2. `buildChartDetailsText(result)` —— 后端结果 → 快照正文（首行 `[盘面细节]`）。
 *
 * payload: { result?: <后端结果>, settings?: { detailFaces, detailVariant, detailLunar, detailMundo, detailMidpoint }, tables?: [<表 id>…] }
 * return : { text, request_fields, settings, invalid?, error?, tables? }
 *          tables = 调用方点名的表（上游「当前表」detailTable 的无头读法）：{ id: { label, data } }，data = 后端该表原值。
 */

// 页面设置键 → CHART_DETAIL_OPTIONS / CHART_DETAIL_DEFAULTS 的组名（上游 chartDetails.js DETAIL_GEAR_KEYS，模块内未导出）。
const SETTING_GROUPS = {
  detailFaces: 'faces',
  detailVariant: 'variant',
  detailLunar: 'lunar',
  detailMundo: 'mundo',
  detailMidpoint: 'midpoint',
};

function isBlank(value) {
  return value === undefined || value === null || value === '';
}

export function chartDetailCatalog() {
  return {
    tables: CHART_DETAIL_TABLES.map((item) => ({ value: item.value, label: item.label, note: item.note, fields: item.fields || [] })),
    defaults: { ...CHART_DETAIL_DEFAULTS },
    options: Object.fromEntries(Object.keys(CHART_DETAIL_OPTIONS).map((group) => [group, CHART_DETAIL_OPTIONS[group].map((item) => ({ ...item }))])),
    setting_groups: { ...SETTING_GROUPS },
  };
}

export function runChartDetails(payload) {
  const source = payload || {};
  if (source.action === 'catalog') {
    return chartDetailCatalog();
  }
  const given = source.settings && typeof source.settings === 'object' ? source.settings : {};
  const invalid = [];
  const settings = {};
  Object.keys(SETTING_GROUPS).forEach((key) => {
    const group = SETTING_GROUPS[key];
    const allowed = CHART_DETAIL_OPTIONS[group].map((item) => item.value);
    if (isBlank(given[key])) {
      settings[key] = CHART_DETAIL_DEFAULTS[group];   // 没给 = 上游出厂缺省（headless 没有「细节页本机保存值」）
      return;
    }
    if (allowed.indexOf(given[key]) < 0) {
      invalid.push({ key, value: given[key], allowed });
      return;
    }
    settings[key] = given[key];
  });
  const tableIds = CHART_DETAIL_TABLES.map((item) => item.value);
  const wanted = Array.isArray(source.tables) ? source.tables : [];
  wanted.forEach((id) => {
    if (tableIds.indexOf(id) < 0) {
      invalid.push({ key: 'detailTable', value: id, allowed: tableIds });
    }
  });
  if (invalid.length) {
    return { text: '', error: 'invalid_setting', invalid };
  }
  const requestFields = chartDetailRequestFields(settings);
  const out = { text: '', request_fields: requestFields, settings };
  const result = source.result;
  if (result === undefined || result === null) {
    return out;   // 只要请求体键（发请求前的对拍）
  }
  const text = buildChartDetailsText(result) || '';
  if (!text) {
    // 上游 buildChartDetailsText：结果不是对象 / 没有 persian 数组 → ''（段不出）。无头侧把原因说出来。
    return { ...out, error: 'no_result' };
  }
  out.text = text;
  if (wanted.length) {
    out.tables = {};
    wanted.forEach((id) => {
      const def = CHART_DETAIL_TABLES.find((item) => item.value === id);
      out.tables[id] = { label: def.label, data: Object.prototype.hasOwnProperty.call(result, id) ? result[id] : null };
    });
  }
  return out;
}
