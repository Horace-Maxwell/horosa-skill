// 诸方杂术 formatter（上游 v3.14.0「命 · 其他 · 诸方」）。
//
// 一个工具四段：玛雅历 / 十三月亮历（进程内纯算）+ 人类图 / 灵名字母（后端 /astroextra/zhufang 算，Python 发请求，
// JS 层不发 HTTP）。算法与排版都是 vendored 上游 vendor/zhufang/zhufangArts.js：
//   zhufangParamsFromFields（字段 → 入参）· ZHUFANG_PAGE_SETTINGS（口径词表与出厂值）· localZhufangModel · zhufangSnapshotLines
// 请求体映射取自 vendor/zhufang/zhufangRequest.js（上游网络件 zhufangRemote.js 的纯映射抽出件）。
//
// 后端结果缺席（payload.remote 为空 / 两块都没算出）时照上游页面与无头挂载：玛雅历 / 十三月亮历照出，人类图 / 灵名字母
// 两段写「未算出」——是否缺、缺哪块由 data.remote_status 如实回给 Python（进 warnings），不静默。
import { validateSettingValue } from '../vendor/utils/pageSettingsStore.js';
import {
  MAYAN_CORRELATIONS,
  ZHUFANG_PAGE_SETTINGS,
  ZHUFANG_SNAPSHOT_SECTIONS,
  localZhufangModel,
  zhufangParamsFromFields,
  zhufangSnapshotLines,
} from '../vendor/zhufang/zhufangArts.js';
import { zhufangRemoteAccepted, zhufangRequestBody } from '../vendor/zhufang/zhufangRequest.js';
import { parseDateParts } from '../vendor/bazi/dateStrSafe.js';

function fail(normalized, reason, message, extra) {
  return {
    tool: 'zhufang',
    technique: 'zhufang',
    input_normalized: normalized,
    data: { ok: false, reason, message: message || '', ...(extra || {}) },
    snapshot_text: '',
  };
}

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

function toBool(value) {
  if (value === true || value === 1 || value === '1' || value === 'true') return true;
  if (value === false || value === 0 || value === '0' || value === 'false' || value === 'mean') return false;
  return undefined;
}

// 口径解析：只认上游词表（ZHUFANG_PAGE_SETTINGS / MAYAN_CORRELATIONS）里的值。
//   mayanCorrelation 584283（缺省）/ 584285 / 584286；hdTrueNode true 真交点（缺省）/ false 平交点（挂载齿轮写 'true' / 'mean'）；
//   spiritQuadrant 1（缺省，1·4·7·10 宫）/ 2 / 3。
export function resolveZhufangSettings(input) {
  const src = input && typeof input === 'object' ? input : {};
  const schema = ZHUFANG_PAGE_SETTINGS.schema;
  const given = (key) => src[key] !== undefined && src[key] !== null && src[key] !== '';
  const settings = {
    mayanCorrelation: schema.mayanCorrelation.def,
    hdTrueNode: schema.hdTrueNode.def,
    spiritQuadrant: schema.spiritQuadrant.def,
  };
  if (given('mayanCorrelation')) {
    const n = Number(src.mayanCorrelation);
    if (!validateSettingValue(schema.mayanCorrelation, n).ok) {
      return { ok: false, error: { field: 'mayanCorrelation', value: src.mayanCorrelation, allowed: MAYAN_CORRELATIONS.slice() } };
    }
    settings.mayanCorrelation = n;
  }
  if (given('hdTrueNode')) {
    const b = toBool(src.hdTrueNode);
    if (b === undefined) {
      return { ok: false, error: { field: 'hdTrueNode', value: src.hdTrueNode, allowed: [true, false] } };
    }
    settings.hdTrueNode = b;
  }
  if (given('spiritQuadrant')) {
    const n = Number(src.spiritQuadrant);
    if (!validateSettingValue(schema.spiritQuadrant, n).ok) {
      return { ok: false, error: { field: 'spiritQuadrant', value: src.spiritQuadrant, allowed: schema.spiritQuadrant.oneOf.slice() } };
    }
    settings.spiritQuadrant = n;
  }
  return { ok: true, settings };
}

export function runZhufang(payload) {
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
    hsys: input.hsys ?? null,
  };
  const parts = parseDateParts(dateText.replace(/\//g, '-'));
  if (!parts) {
    return fail(normalized, 'missing_date', `诸方杂术需要出生日期（YYYY-MM-DD）：${JSON.stringify(dateText)}`);
  }
  if (!/^\d{2}:\d{2}:\d{2}$/.test(timeText)) {
    return fail(normalized, 'missing_time', `诸方杂术需要出生时刻（HH:mm:ss）：${JSON.stringify(rawTime)}`);
  }
  const resolved = resolveZhufangSettings(input);
  if (!resolved.ok) {
    const e = resolved.error;
    return fail(normalized, 'invalid_option',
      `诸方杂术 ${e.field} 取值无效：${JSON.stringify(e.value)}（可选：${(e.allowed || []).join(' / ')}）`, { error: e });
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
    hsys: { value: input.hsys },
    gender: { value: input.gender },
  };
  const params = zhufangParamsFromFields(fields);
  // 上游 zhufangRequestBody 只读 hdTrueNode / spiritQuadrant（玛雅关联常数只给下面的 localZhufangModel）：只交它读的两键，
  // 边界守卫（verify_js_boundary_contracts）才看得出哪个键真的到了后端。请求体与整包传入逐字相同。
  const request = zhufangRequestBody(params, { hdTrueNode: settings.hdTrueNode, spiritQuadrant: settings.spiritQuadrant });
  if (input.request_only) {
    // Python 发请求前先取上游口径的请求体（同一份设置、同一个映射）；不排版。
    return { tool: 'zhufang', technique: 'zhufang', input_normalized: normalized, data: { ok: true, request_only: true, params, settings }, request, snapshot_text: '' };
  }

  // 后端回包：上游 fetchZhufangRemote 的同一判据——两块都没有就当没取到（null）。
  const raw = input.remote && typeof input.remote === 'object' ? input.remote : null;
  const remote = zhufangRemoteAccepted(raw);
  const remoteStatus = {
    fetched: !!raw,
    humanDesign: !!(remote && remote.humanDesign),
    spiritNames: !!(remote && remote.spiritNames),
  };

  let local;
  let lines;
  try {
    local = localZhufangModel(params, settings);
    lines = zhufangSnapshotLines(local, remote, settings);
  } catch (error) {
    return fail(normalized, 'zhufang_calc_failed', error instanceof Error ? error.message : `${error}`);
  }
  if (!local) {
    return fail(normalized, 'missing_date', `诸方杂术读不了出生日期：${JSON.stringify(params.date)}`);
  }
  return {
    tool: 'zhufang',
    technique: 'zhufang',
    input_normalized: normalized,
    data: {
      ok: true,
      params,
      settings,
      sections: ZHUFANG_SNAPSHOT_SECTIONS.slice(),
      local,
      remote_status: remoteStatus,
      // 公元前：上游两种历都不排（localZhufangModel 的 ad<0 分支），快照写「公元前日期不排…」。
      bc: Number(params.ad) < 0,
    },
    request,
    snapshot_text: lines.join('\n'),
  };
}
