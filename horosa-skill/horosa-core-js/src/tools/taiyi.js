import { makeFields, normalizeDateTimeInput } from '../shared/fields.js';
import { unwrapNamedObject, unwrapResultEnvelope } from '../shared/unpack.js';
import { buildTaiyiSnapshotText, buildTaiyiBaziLocal, calcTaiyi, normalizeBackendPan } from '../vendor/taiyi/TaiYiCalc.js';
import { applyTaiyiSchool, DEFAULT_TAIYI_SCHOOL, TAIYI_SCHOOL_OPTIONS, normalizeTaiyiSchool } from '../vendor/taiyi/core/taiyiSchool.js';

const SCHOOL_AXES = Object.keys(DEFAULT_TAIYI_SCHOOL);

function invalid(field, value, allowed, message) {
  return {
    ok: false,
    error: {
      code: 'invalid_option',
      field,
      value,
      allowed,
      message: message || `太乙 ${field} 取值无效：${JSON.stringify(value)}（可选：${(allowed || []).join(' / ')}）`,
    },
  };
}

// 太乙流派六轴（上游 taiyiSchool.js DEFAULT_TAIYI_SCHOOL / TAIYI_SCHOOL_OPTIONS）：options.school 对象为正门；
// 兼容 options 里平铺的六轴键（旧 schema 描述的写法）与顶层 school 对象（taiyizeri 展示盘沿用扫描同一份流派）。
// 优先级 options.school > 顶层 school > 平铺键。词表锚到上游自带选项表，认不出的轴/值报错而不静默当缺省。
export function resolveTaiyiSchool(input) {
  const src = input && typeof input === 'object' ? input : {};
  const opts = src.options && typeof src.options === 'object' ? src.options : {};
  const merged = {};
  SCHOOL_AXES.forEach((axis) => {
    if (opts[axis] !== undefined && opts[axis] !== null && opts[axis] !== '') {
      merged[axis] = opts[axis];
    }
  });
  for (const [label, candidate] of [['school', src.school], ['options.school', opts.school]]) {
    if (candidate === undefined || candidate === null || candidate === '') {
      continue;
    }
    if (typeof candidate !== 'object' || Array.isArray(candidate)) {
      return invalid(label, candidate, SCHOOL_AXES, `太乙 ${label} 须为流派六轴对象 {${SCHOOL_AXES.join(', ')}}，收到 ${JSON.stringify(candidate)}。`);
    }
    Object.assign(merged, candidate);
  }
  for (const [axis, value] of Object.entries(merged)) {
    const allowed = (TAIYI_SCHOOL_OPTIONS[axis] || []).map((o) => o.value);
    if (!allowed.length) {
      return invalid(axis, value, SCHOOL_AXES, `太乙流派未知轴「${axis}」（可用：${SCHOOL_AXES.join(' / ')}）。`);
    }
    if (allowed.indexOf(value) < 0) {
      return invalid(axis, value, allowed);
    }
  }
  return { ok: true, school: normalizeTaiyiSchool(merged) };
}

export function runTaiyi(payload) {
  const normalized = normalizeDateTimeInput(payload);
  const fields = makeFields(normalized);
  const nongli = unwrapNamedObject(normalized.nongli, 'nongli') || null;
  const options = normalized.options || {};
  const resolved = resolveTaiyiSchool(normalized);
  if (!resolved.ok) {
    return { tool: 'taiyi', technique: 'taiyi', data: { ok: false, error: resolved.error }, snapshot_text: '' };
  }
  // ken (kintaiyi) is the compute authority; normalizeBackendPan reformats it into the
  // pan shape buildTaiyiSnapshotText expects (星阙 aiExport.js sections). Local calcTaiyi
  // is only a fallback when no ken response is supplied.
  const ken = unwrapResultEnvelope(payload.ken_response ?? payload.kenResponse);
  let pan;
  if (ken && typeof ken === 'object' && (ken.raw || ken.kook || ken.palace16)) {
    // 上游 fetchTaiyiPan 尾段（TaiYiCalc.js:317-323）：四柱 / 真太阳时 / 钟表时按所选时间基准由本地八字链重出
    // （直接时间 → 钟表时四柱；真太阳时 → 真太阳时四柱），不再直接套 /nongli/time 的真太阳时柱 ——
    // 此前默认「直接时间」盘在时辰边界上标着真太阳时的时柱（ken 用钟表时起局，两套时辰）。
    const baziLocal = buildTaiyiBaziLocal(fields, options);
    pan = normalizeBackendPan(ken, options, nongli, baziLocal);
    if (pan && !pan.clockTime && fields && fields.date && fields.date.value && fields.time && fields.time.value) {
      pan.clockTime = `${fields.date.value.format('YYYY-MM-DD')} ${fields.time.value.format('HH:mm:ss')}`;
    }
  } else {
    pan = calcTaiyi(fields, nongli, options);
  }
  if (!pan) {
    throw new Error('Taiyi calculation returned no result.');
  }
  // P1 流派覆盖层（上游 TaiYiMain.recalc:629 / 三式 getKintaiyiPan:2334 同链）：以 base pan 为底按所选流派六轴
  // 覆盖受影响神煞 + 几何重算主客算；全缺省 = 空操作，字节不变。此前 skill 只有择日扫描引擎调它 → 六轴在 taiyi /
  // 三式合一里是死开关（schema 描述着、结果恒缺省）。
  const ov = applyTaiyiSchool(pan, resolved.school);
  const displayPan = (ov && ov.pan) || pan;
  return {
    tool: 'taiyi',
    technique: 'taiyi',
    input_normalized: normalized,
    data: displayPan,
    school_overrides: (ov && ov.overrides) || null,
    // 星阙 v2.6.x: the kintaiyi backend returns the rich 太乙 reading `sections`
    // (太乙诸神/风游/主客定算/八门与宿曜/十二神/断法/七大兵法 + 博弈/命法/命宫行限 when applicable).
    // normalizeBackendPan drops the backend's 起盘 section (the builder already emits [起盘信息]);
    // the rest are emitted and registered as optional sections so the export contract stays clean.
    snapshot_text: buildTaiyiSnapshotText(displayPan),
  };
}
