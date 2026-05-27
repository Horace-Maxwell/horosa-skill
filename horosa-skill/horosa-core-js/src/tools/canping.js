// 邵子参评数（金锁银匙）formatter.
//
// canping is a "原生·非 kentang" technique: unlike qimen/taiyi/jinkou (which are computed by the ken
// backend and only formatted here), canping is computed entirely in-process. The four pillars come
// from the vendored bazi chain (baziLunarLocal.js → lunar-javascript), and canpingLocal.js does the
// 金锁银匙 起数 + 条文 lookup. This mirrors 星阙's CanPingMain.js, which calls buildLocalBaziResult
// then canpingCalculate/liunianSeries/buildSnapshotText — none of which touch the backend.
//
// snapshot_text is emitted byte-identical to 星阙's canpingLocal.buildSnapshotText (sections
// [起盘]/[本命]/[大运·歲運]/[流年·歲運]). The skill's export layer legacy-maps 大运·歲運→大运 and
// 流年·歲運→流年 so the parsed sections match 星阙's declared aiExport contract ['起盘','本命','大运','流年'].
import { buildLocalBaziResult } from '../vendor/bazi/baziLunarLocal.js';
import { calculate as canpingCalculate, liunianSeries, buildSnapshotText } from '../vendor/canping/canpingLocal.js';

const METHODS = new Set(['ming', 'gu']);

function normalizeMethod(value) {
  const text = `${value ?? ''}`.trim().toLowerCase();
  return METHODS.has(text) ? text : 'ming';
}

function pillarGanzhi(pillar) {
  return (pillar && (pillar.ganzi || pillar.ganZhi)) || '';
}

function insufficient(normalized, reason, message) {
  return {
    tool: 'canping',
    technique: 'canping',
    input_normalized: normalized,
    data: { ok: false, reason, message: message || '' },
    snapshot_text: '',
  };
}

export function runCanping(payload) {
  const input = payload && typeof payload === 'object' ? payload : {};
  // parseDateTime (baziLunarLocal) splits the date on '-' only; coerce '/' so YYYY/MM/DD also works.
  const date = `${input.date ?? ''}`.trim().replace(/\//g, '-');
  const time = `${input.time ?? ''}`.trim() || '00:00:00';
  const method = normalizeMethod(input.method);
  // timeAlg: 0 → 真太阳时 (longitude + equation-of-time correction); any other value → clock time.
  // Default 1 (clock time) mirrors 星阙 CanPingMain.js's `fieldVal(f, 'timeAlg', 1)`.
  const timeAlg = input.timeAlg === undefined || input.timeAlg === null ? 1 : input.timeAlg;
  const baziParams = {
    date,
    time,
    zone: input.zone,
    lon: input.lon,
    gender: input.gender,
    timeAlg,
  };
  const normalized = {
    date,
    time,
    zone: input.zone ?? null,
    lon: input.lon ?? null,
    gender: input.gender ?? null,
    timeAlg,
    method,
  };

  if (!date) {
    return insufficient(normalized, 'missing_date', 'canping requires a birth date.');
  }

  let bazi;
  try {
    bazi = buildLocalBaziResult(baziParams).bazi;
  } catch (error) {
    return insufficient(normalized, 'invalid_bazi_input', error instanceof Error ? error.message : `${error}`);
  }

  const fc = (bazi && bazi.fourColumns) || {};
  const yearGz = pillarGanzhi(fc.year);
  const monthBranch = pillarGanzhi(fc.month).charAt(1);
  const dayBranch = pillarGanzhi(fc.day).charAt(1);
  const hourBranch = pillarGanzhi(fc.time).charAt(1);
  if (!yearGz || !monthBranch || !dayBranch || !hourBranch) {
    return insufficient(normalized, 'incomplete_pillars', 'Could not derive four pillars from the birth input.');
  }

  const gender = bazi.gender === 'Female' ? '女' : '男';
  const birthYear = parseInt(`${date}`.slice(0, 4), 10) || 0;
  const base = { yearGz, monthBranch, dayBranch, hourBranch, gender, method, qiyunAge: 1 };
  const result = canpingCalculate(base);

  let series = null;
  try {
    series = liunianSeries({ ...base, birthYear, startAge: 1, endAge: 120 });
  } catch (error) {
    series = null;
  }

  return {
    tool: 'canping',
    technique: 'canping',
    input_normalized: {
      ...normalized,
      gender,
      birthYear,
      fourPillars: { yearGz, monthBranch, dayBranch, hourBranch },
    },
    data: { ...result, series },
    snapshot_text: buildSnapshotText(result),
  };
}
