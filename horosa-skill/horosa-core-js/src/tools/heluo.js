// 河洛理数 formatter.
//
// Like canping, heluo is a "原生·非 kentang" technique computed entirely in-process: the four pillars
// come from the vendored bazi chain (baziLunarLocal.js → lunar-javascript), and heluoLocal.js does the
// 起命（天地数→卦→元堂→后天）, 起运（大限/流年）, 命运篇 judge, and 爻辞 lookup. This mirrors 星阙's
// HeLuoMain.js, which calls buildLocalBaziResult → calc → daYun → judge → buildSnapshotText.
//
// The 命运篇 section depends on the real 节气 (solar term) at birth, so we port HeLuoMain.solarTerm:
// it uses lunar-javascript's JieQi table + solarTermHuagong to derive the 化工/三候 context that judge()
// consumes. snapshot_text is byte-identical to 星阙's heluoLocal.buildSnapshotText; the 先天·…/后天·…
// /大限·岁运 dynamic labels are legacy-mapped to the declared aiExport sections 先天卦/后天卦/大限 in
// the skill's export layer.
import { Solar } from 'lunar-javascript';
import { buildLocalBaziResult } from '../vendor/bazi/baziLunarLocal.js';
import calc, { daYun, judge, buildSnapshotText, solarTermHuagong } from '../vendor/heluo/heluoLocal.js';

// 四立 — 土用 window markers, mirrored from HeLuoMain.js.
const LI_TERMS = ['立春', '立夏', '立秋', '立冬'];

// Ported verbatim from 星阙 HeLuoMain.solarTerm: real 节气(化工/象限+土用) + 三候(节气内 5 日一候).
function solarTerm(dateStr) {
  try {
    const [y, m, d] = `${dateStr}`.split('-').map((x) => parseInt(x, 10));
    const solar = Solar.fromYmd(y, m, d);
    const lunar = solar.getLunar();
    const prev = lunar.getPrevJieQi(true);
    const prevName = prev.getName();
    const jd = solar.getJulianDay();
    const tbl = lunar.getJieQiTable();
    const tuyong = LI_TERMS.some((n) => {
      const t = tbl[n];
      if (!t) return false;
      const diff = t.getJulianDay() - jd;
      return diff >= 0 && diff <= 18;
    });
    const daysIn = Math.max(0, Math.floor(jd - prev.getSolar().getJulianDay()));
    const hou = Math.min(3, Math.floor(daysIn / 5) + 1);
    const houLabel = `${prevName}${['初候', '二候', '三候'][hou - 1]}·${prevName}後`;
    return { ...solarTermHuagong(prevName, tuyong), term: prevName, hou, houLabel };
  } catch (error) {
    return null;
  }
}

function pillarGanzhi(pillar) {
  return (pillar && (pillar.ganzi || pillar.ganZhi)) || '';
}

function insufficient(normalized, reason, message) {
  return {
    tool: 'heluo',
    technique: 'heluo',
    input_normalized: normalized,
    data: { ok: false, reason, message: message || '' },
    snapshot_text: '',
  };
}

export function runHeluo(payload) {
  const input = payload && typeof payload === 'object' ? payload : {};
  // parseDateTime (baziLunarLocal) splits the date on '-' only; coerce '/' so YYYY/MM/DD also works.
  const date = `${input.date ?? ''}`.trim().replace(/\//g, '-');
  const time = `${input.time ?? ''}`.trim() || '00:00:00';
  // timeAlg: 0 → 真太阳时; any other value → clock time. Default 1 mirrors 星阙 HeLuoMain.js's
  // `fieldVal(f, 'timeAlg', 1)`.
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
  };

  if (!date) {
    return insufficient(normalized, 'missing_date', 'heluo requires a birth date.');
  }

  let bazi;
  try {
    bazi = buildLocalBaziResult(baziParams).bazi;
  } catch (error) {
    return insufficient(normalized, 'invalid_bazi_input', error instanceof Error ? error.message : `${error}`);
  }

  const fc = (bazi && bazi.fourColumns) || {};
  const fourPillars = {
    year: pillarGanzhi(fc.year),
    month: pillarGanzhi(fc.month),
    day: pillarGanzhi(fc.day),
    hour: pillarGanzhi(fc.time),
  };
  if (!fourPillars.year || !fourPillars.month || !fourPillars.day || !fourPillars.hour) {
    return insufficient(normalized, 'incomplete_pillars', 'Could not derive four pillars from the birth input.');
  }

  const monthZhi = fourPillars.month.charAt(1);
  const hourZhi = fourPillars.hour.charAt(1);
  const birthYear = parseInt(`${date}`.slice(0, 4), 10) || 0;
  const gender = bazi.gender === 'Female' ? '女' : '男';

  let chart;
  try {
    chart = calc({ fourPillars, gender, hourZhi, birthYear, monthZhi });
  } catch (error) {
    return insufficient(normalized, 'heluo_calc_failed', error instanceof Error ? error.message : `${error}`);
  }
  if (!chart || !chart.xian || !chart.hou || !chart.xian.name || !chart.hou.name) {
    return insufficient(normalized, 'heluo_no_chart', 'heluo could not derive the 先天/后天 gua.');
  }

  const dy = daYun(chart.xian, chart.hou, birthYear);
  const st = solarTerm(date);
  const jg = judge(chart, fourPillars, monthZhi, st);

  return {
    tool: 'heluo',
    technique: 'heluo',
    input_normalized: {
      ...normalized,
      gender,
      birthYear,
      fourPillars,
      monthZhi,
      hourZhi,
    },
    data: {
      gender,
      fourPillars,
      monthZhi,
      hourZhi,
      birthYear,
      chart,
      dayun: dy,
      judge: jg,
      solarTerm: st,
    },
    snapshot_text: buildSnapshotText(chart, jg, dy),
  };
}
