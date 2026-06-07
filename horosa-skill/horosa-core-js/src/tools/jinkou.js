import { unwrapNamedObject, unwrapResultEnvelope } from '../shared/unpack.js';
import { buildJinKouData, normalizeKinjinkouData } from '../vendor/jinkou/JinKouCalc.js';
import { resolveJinKouDiFen } from '../vendor/jinkou/JinKouState.js';
import { buildJinKouSnapshotText } from '../vendor/jinkou/JinKouSnapshot.js';

function normalizeTimeBranch(timeValue) {
  const text = `${timeValue || ''}`;
  const match = text.match(/[子丑寅卯辰巳午未申酉戌亥]/);
  return match ? match[0] : '';
}

function buildJinkouParams(payload) {
  return {
    date: payload.date || '',
    time: payload.time || '',
    zone: payload.zone || '',
    lat: payload.lat || '',
    lon: payload.lon || '',
  };
}

export function runJinkou(payload) {
  const liureng = unwrapNamedObject(payload.liureng, 'liureng');
  if (!liureng || typeof liureng !== 'object') {
    throw new Error('Jinkou requires a liureng calculation payload.');
  }
  const options = { ...(payload.options || {}) };
  options.diFen = resolveJinKouDiFen(
    options.diFen || payload.diFen || '',
    options.diFenAuto === true,
    normalizeTimeBranch(liureng?.nongli?.time),
    false,
  );
  if (payload.guirengType !== undefined && options.guirengType === undefined) {
    options.guirengType = payload.guirengType;
  }
  if (payload.isDiurnal !== undefined && options.isDiurnal === undefined) {
    options.isDiurnal = payload.isDiurnal;
  }
  const fallback = buildJinKouData(liureng, options);
  if (!fallback || fallback.ready !== true) {
    throw new Error('Jinkou calculation returned no result.');
  }
  // ken (kinjinkou) is the compute authority; normalizeKinjinkouData overlays it onto the
  // local scaffold so the 星阙 snapshot builder emits all aiExport.js sections (含解读层).
  const ken = unwrapResultEnvelope(payload.ken_response ?? payload.kenResponse);
  const data = ken && typeof ken === 'object' && Array.isArray(ken.rows)
    ? normalizeKinjinkouData(ken, fallback)
    : fallback;
  // 星阙 buildJinKouSnapshotText(params, liureng, runyear, jinkouData, wuxing, guirengType, gender)：
  // 20 段含解读层（用神强弱/四位生克/应期/地支关系/相关神煞/分类用神·求财）。runyear=null（金口诀非行年盘）。
  const snapshot_text = buildJinKouSnapshotText(
    buildJinkouParams(payload),
    liureng,
    payload.runyear ?? null,
    data,
    data.wangElem || '',
    options.guirengType,
    payload.gender,
  );
  return {
    tool: 'jinkou',
    technique: 'jinkou',
    input_normalized: { ...payload, options },
    data,
    snapshot_text,
  };
}
