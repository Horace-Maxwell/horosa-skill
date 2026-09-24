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
import { ganzhiYearBase } from '../vendor/utils/ganzhiYearBase.js';

// 四立 — 土用 window markers, mirrored from HeLuoMain.js.
const LI_TERMS = ['立春', '立夏', '立秋', '立冬'];

// Ported verbatim from 星阙 HeLuoMain.solarTerm: real 节气(化工/象限+土用) + 三候(节气内 5 日一候).
// quHuaGong 取化工法（上游 HeLuoMain.js:156 / aiAnalysisContext.heluoSolarTermForDate）：
// 'tuWangKunGen' 土王寄坤艮（缺省，土用期补坤艮/反乾兑）| 'siFangBoOnly' 直取四方伯（土用期不补）。
function solarTerm(dateStr, quHuaGong) {
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
    return { ...solarTermHuagong(prevName, tuyong, { quHuaGong: quHuaGong || 'tuWangKunGen' }), term: prevName, hou, houLabel };
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
  // timeAlg: 0 → 真太阳时; any other value → clock time.
  // 缺省 0（sync311 wave 3b，此前误为 1）：上游 AI 挂载无头路径 buildHeluoSnapshotForRecord → buildChartShusuanBazi →
  // buildChartBaziParams 取 buildFieldObject 的 timeAlg = record.timeAlg ?? 0（aiAnalysisContext.js:603,1793）；挂载齿轮
  // 缺省亦 0（techniqueMountSettings.js:147,1882）。页面 HeLuoMain.getModel 的 `fieldVal(f, 'timeAlg', 1)`（:188）读全局
  // fields.timeAlg —— 该字段恒在、出厂种子 0（models/astro.js:375-377 + newChartSeeds.js:43），回退值 1 从不生效。
  const timeAlg = input.timeAlg === undefined || input.timeAlg === null ? 0 : input.timeAlg;
  // 日界 / 晚子时：上游两路缺省同为全局出厂 1/1 —— 无头 buildFieldObject after23NewDay = record ?? defaultAfter23NewDay()
  // （aiAnalysisContext.js:606）、页面 fieldVal(f,'after23NewDay',defaultAfter23NewDay())（HeLuoMain.js:191-192）。
  // 此前不传 → vendored baziLunarLocal 把 undefined 当「24 点换日」（baziLunarLocal.js:1107），23 点档生人日柱与上游不同。
  const after23NewDay = input.after23NewDay === undefined || input.after23NewDay === null ? 1 : input.after23NewDay;
  const lateZiHourUseNextDay = input.lateZiHourUseNextDay === undefined || input.lateZiHourUseNextDay === null
    ? 1 : input.lateZiHourUseNextDay;
  const baziParams = {
    date,
    time,
    zone: input.zone,
    lon: input.lon,
    gender: input.gender,
    timeAlg,
    after23NewDay,
    lateZiHourUseNextDay,
  };
  const normalized = {
    date,
    time,
    zone: input.zone ?? null,
    lon: input.lon ?? null,
    gender: input.gender ?? null,
    timeAlg,
    after23NewDay,
    lateZiHourUseNextDay,
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
  // 2026-09-04：第 N 岁流年以干支年为基准（桌面 HeLuoMain/ganzhiYearBase 同修；立春前生者此前错一位）
  const birthYear = ganzhiYearBase(parseInt(`${date}`.slice(0, 4), 10) || 0, fourPillars.year);
  const gender = bazi.gender === 'Female' ? '女' : '男';

  // 取法四轴 + 阳令手定（缺省与 vendor calculate() 内建默认逐字相同 → 不给即字节不变）
  const hlOpts = {
    ziShuMode: input.ziShuMode === 'single' ? 'single' : 'pair',
    jiGongMode: input.jiGongMode === 'legacy' ? 'legacy' : 'manualSanYuan',
    zhiZunEnabled: !(input.zhiZunEnabled === false || input.zhiZunEnabled === 0 || input.zhiZunEnabled === 'false' || input.zhiZunEnabled === '0'),
    pureGanKunVariant: input.pureGanKunVariant === 'alt' ? 'alt' : 'current',
    // 键名必须是 liunianStep2：buildSnapshotText 读 snapOpts.liunianStep2 再转成 liuNian 的 step2；
    // 此前发 step2 → 引擎永远走默认应爻法（同模块另一函数恰有 step2 参数，子串式边界契约看不见这条死键）。
    liunianStep2: input.liunianStep2 === 'sequential' ? 'sequential' : 'ying',
    // 纪年基准（黄帝纪元差）：[断验]「纪年：黄帝N年」行 = 干支年 + huangdiOffset（heluoLocal.jiNian）。
    // 缺省 2697；与上游 KinAstroMain.buildHeluoOpts 同式 parseInt、0 可达（[Q-265/SO-18]）。
    huangdiOffset: Number.isFinite(parseInt(input.huangdiOffset, 10)) ? parseInt(input.huangdiOffset, 10) : 2697,
  };
  // 取化工法（上游挂载 schema heluo.quHuaGong，techniqueMountSettings.js:1883-1886）：只认两档，余者回缺省。
  const quHuaGong = input.quHuaGong === 'siFangBoOnly' ? 'siFangBoOnly' : 'tuWangKunGen';
  const monthYangLing = (input.monthYangLing === undefined || input.monthYangLing === null || input.monthYangLing === '')
    ? undefined
    : (input.monthYangLing === true || input.monthYangLing === 1 || input.monthYangLing === 'yang' || input.monthYangLing === '1' || input.monthYangLing === 'true');
  let chart;
  try {
    chart = calc({ fourPillars, gender, hourZhi, birthYear, monthZhi, monthYangLing, opts: hlOpts });
  } catch (error) {
    return insufficient(normalized, 'heluo_calc_failed', error instanceof Error ? error.message : `${error}`);
  }
  if (!chart || !chart.xian || !chart.hou || !chart.xian.name || !chart.hou.name) {
    return insufficient(normalized, 'heluo_no_chart', 'heluo could not derive the 先天/后天 gua.');
  }

  const dy = daYun(chart.xian, chart.hou, birthYear);
  const st = solarTerm(date, quHuaGong);
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
      ...hlOpts,
      quHuaGong,
      ...(monthYangLing === undefined ? {} : { monthYangLing }),
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
    // extra 带 opts/monthZhi：流年分歧口径随取法走，且 [断验] 的时令/先后天卦气三行由 monthZhi→SEASON 救活
    snapshot_text: buildSnapshotText(chart, jg, dy, { opts: hlOpts, monthZhi, birthYear }),
  };
}
