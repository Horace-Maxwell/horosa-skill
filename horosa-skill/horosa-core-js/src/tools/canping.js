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
import { ganzhiYearBase } from '../vendor/utils/ganzhiYearBase.js';

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
  // 缺省 0（sync311 wave 3b，此前误为 1）：上游 AI 挂载无头路径 buildCanpingSnapshotForRecord →
  // buildChartShusuanBazi → buildChartBaziParams 取 buildFieldObject 的 timeAlg = record.timeAlg ?? 0
  // （aiAnalysisContext.js:603,1793）；挂载齿轮缺省亦 0（techniqueMountSettings.js:147,1866）。页面
  // CanPingMain.getModel 的 `fieldVal(f, 'timeAlg', 1)`（:138）读的是全局 fields.timeAlg —— 该字段恒在、出厂种子 0
  // （models/astro.js:375-377 + newChartSeeds.js:43），回退值 1 从不生效。页面与无头同为 0。
  const timeAlg = input.timeAlg === undefined || input.timeAlg === null ? 0 : input.timeAlg;
  // 日界 / 晚子时：上游两路缺省同为全局出厂 1/1 —— 无头 buildFieldObject after23NewDay = record ?? defaultAfter23NewDay()
  // （aiAnalysisContext.js:606）、页面 fieldVal(f,'after23NewDay',defaultAfter23NewDay())（CanPingMain.js:141-142）。
  // 此前不传 → vendored baziLunarLocal 把 undefined 当「24 点换日」（after23=0，baziLunarLocal.js:1107），23 点档生人
  // 日柱/日支与上游不同（与一掌经此前同病，tools/yizhangjing.js 已修）。
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
  // 2026-09-04：第 N 岁流年以干支年为基准（桌面 HeLuoMain/ganzhiYearBase 同修；立春前生者此前错一位）
  const birthYear = ganzhiYearBase(parseInt(`${date}`.slice(0, 4), 10) || 0, yearGz);
  // 🔴 lunarMonth/lunarDay/baziYun 必须转发：引擎默认 dayunRule='mingGongQiyun' → 走
  // qiyunFromLunarDate(lunarMonth, lunarDay)，两者缺省为 0 时守卫判非法 → 起运岁回落 1
  // （canpingLocal.js:113/185）。于是九个大运区间整体平移，liunianSeries 又按
  // floor((age-qiyun)/10) 分段 → 120 行流年全部归错大运。数据本来就在 bazi 里，只是没传。
  const nl = (bazi && bazi.nongli) || {};
  const dayunRule = ['mingGongQiyun', 'mingGongOne', 'baziStyle'].indexOf(input.dayunRule) >= 0
    ? input.dayunRule
    : 'mingGongQiyun';
  // baziStyle 档要的是**扁平化**的运列（`{branch, ganzi, ageStart, ageEnd, startYear, endYear}`），
  // 不是 bazi.direction 原样 —— 引擎 `filter((d) => d && d.branch)`（canpingLocal.js:138）对
  // 原样数组会全滤空、静默回落旧排序法。映射逐字照上游 aiAnalysisContext.js:1909。
  let baziYun = null;
  if (dayunRule === 'baziStyle' && Array.isArray(bazi && bazi.direction) && bazi.direction.length) {
    try {
      baziYun = bazi.direction.map((d) => {
        const gzd = (d.mainDirect && (d.mainDirect.ganzi || d.mainDirect.ganZhi)) || '';
        return { branch: gzd.charAt(1) || '', ganzi: gzd, ageStart: d.age, ageEnd: d.age + 9, startYear: d.startYear, endYear: d.endYear };
      }).filter((d) => d.branch);
      if (!baziYun.length) { baziYun = null; }
    } catch (error) { baziYun = null; }
  }
  const base = {
    yearGz, monthBranch, dayBranch, hourBranch, gender, method, dayunRule, baziYun,
    lunarMonth: Number(nl.monthNum) || 0,
    lunarDay: Number(nl.dayNum) || 0,
    qiyunAge: 1,
  };
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
    // 全生涯流年表喂给快照（逐岁太岁/大运/顺逆数），[流年·歲運] 段随之产出。
    snapshot_text: buildSnapshotText(result, { liunianRows: series && Array.isArray(series.rows) ? series.rows : null }),
  };
}
