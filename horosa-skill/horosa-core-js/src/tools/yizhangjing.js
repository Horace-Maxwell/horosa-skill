// 一掌经 formatter.
//
// 原生·非 kentang 技法，全程进程内计算：四柱/农历来自 vendored bazi 链（baziLunarLocal.js →
// lunar-javascript），一掌经引擎（yizhangjingLocal 纯分支算术 + yizhangjingReport 断语装配）排
// 四柱四宫/命宫/人事十二宫/格局/重犯/交互格/大限/小限流年十二神，并可叠神煞合参层（生年支/
// 日干/月支/日柱旬定位落宫）。快照由引擎自带 buildYizhangjingSnapshotText 产出——其段头为
// 全角【段名】（源过滤器格式），本层转为 skill 导出契约的 [段名]，正文逐字不动。
import { buildLocalBaziResult } from '../vendor/bazi/baziLunarLocal.js';
import {
  buildYizhangjingModel,
  buildYizhangjingSnapshotText,
} from '../vendor/yizhangjing/yizhangjingReport.js';
import { BRANCHES, mod12, xiaoxianStarAtDir, xunShenAt } from '../vendor/yizhangjing/yizhangjingLocal.js';

// 小限（一宫一年，1–120 岁逐年落宫）与流年十二神（流年支 × 宫支 12×12 全表）：
// 此前两者只进快照文本，网页拿不到结构化值——小限起宫/十二神传本等口径轴改了盘面零反馈。
function buildXiaoxianRows(c, model) {
  const dir = model.xiaoDir === 'always' ? 1 : c.dir;
  const rows = [];
  for (let age = 1; age <= 120; age++) {
    const idx = mod12(c.xiaoStartIdx + dir * (age - 1));
    rows.push({ age, branch: BRANCHES[idx], star: xiaoxianStarAtDir(c.xiaoStartIdx, c.dir, age, model.xiaoDir) });
  }
  return { start: c.xiaoStartLabel || '日柱宫', dir: model.xiaoDir === 'always' ? '一律顺行' : (c.dir === 1 ? '随盘顺行' : '随盘逆行'), rows };
}
function buildFlowShenTable(c) {
  const set = (c.opts && c.opts.flowSet) || 'A';
  return {
    set,
    natalYearBranch: (c.input && c.input.yearBranch) || null,
    table: BRANCHES.map((yearBranch, fi) => ({ yearBranch, shen: BRANCHES.map((_, ti) => xunShenAt(fi, ti, set)) })),
  };
}

function insufficient(normalized, reason, message) {
  return {
    tool: 'yizhangjing',
    technique: 'yizhangjing',
    input_normalized: normalized,
    data: { ok: false, reason, message: message || '' },
    snapshot_text: '',
  };
}

export function runYizhangjing(payload) {
  const input = payload && typeof payload === 'object' ? payload : {};
  const date = `${input.date ?? ''}`.trim().replace(/\//g, '-');
  const time = `${input.time ?? ''}`.trim() || '00:00:00';
  // timeAlg 缺省 1（钟表时），与 canping/heluo 一致。
  const timeAlg = input.timeAlg === undefined || input.timeAlg === null ? 1 : input.timeAlg;
  // 日界 / 晚子时：上游 YiZhangJingMain.getModel 读盘面 fields，缺席回退全局出厂默认
  // defaultAfter23NewDay()=1 / defaultLateZiHourUseNextDay()=1（YiZhangJingMain.js:124-128）。
  // 此前两键都不传 → vendored baziLunarLocal 把 undefined 当「24 点换日」（after23=0），23 点档生人
  // 日柱与农历日（lunarByDayBoundary 进位）都与桌面不同。晚子时只动时干，一掌经只用时支，上游挂载
  // 已撤下该齿轮（techniqueMountSettings.js:1909），这里仍原样透传以与页面同形。
  const after23NewDay = input.after23NewDay === undefined || input.after23NewDay === null ? 1 : input.after23NewDay;
  const lateZiHourUseNextDay = input.lateZiHourUseNextDay === undefined || input.lateZiHourUseNextDay === null
    ? 1 : input.lateZiHourUseNextDay;
  const baziParams = {
    date, time, zone: input.zone, lon: input.lon, gender: input.gender, timeAlg, after23NewDay, lateZiHourUseNextDay,
  };
  const off = (v) => v === false || v === 0 || v === '0' || v === 'false';

  // 排盘选项 = 上游 KinAstroMain.buildYizhangjingOpts 同键（KinAstroMain.js:3357-3380），缺省 = 上游
  // KINASTRO_PAGE_SETTINGS 出厂档（KinAstroMain.js:1039-1056，即「秘传口诀」预设）：定月法、顺逆规则、
  // 命宫定法、大限一宫年数、大限起法、小限起宫/顺逆、逐年法、流年十二神组、早子时、重犯口诀组、
  // 星名系统、六道术语、童限显示、神煞合参层（出厂关）。
  const opts = {
    dingYue: input.dingYue === 'jieqi' ? 'jieqi' : 'lunar',
    shunniRule: input.shunniRule === 'menShunNvNi' ? 'menShunNvNi' : 'yangNanYinNv',
    mingGongMethod: input.mingGongMethod === 'shuZhiMao' ? 'shuZhiMao' : 'shiShang',
    dayunLength: input.dayunLength === 10 || input.dayunLength === '10' ? 10 : 7,
    dayunStartAge: input.dayunStartAge === 'age1' ? 'age1' : 'mi',
    xiaoxianStart: input.xiaoxianStart === 'yue' ? 'yue' : 'ri',
    xiaoxianDir: input.xiaoxianDir === 'always' ? 'always' : 'chart',
    // 逐年法：页面出厂 'xiaoxian'（B10 明训：小限/流年只用一套）；引擎见 '' 才两套并列。
    annualMethod: input.annualMethod === 'liunian' ? 'liunian' : 'xiaoxian',
    flowShenSet: input.flowShenSet || 'A',
    zaoZiAdjust: !!input.zaoZiAdjust,
    chongfanKou: input.chongfanKou === 'beta' ? 'beta' : 'alpha',
    starNaming: input.starNaming === 'B' || input.starNaming === 'C' ? input.starNaming : 'A',
    daoTerm: input.daoTerm === 'edao' ? 'edao' : 'gui',
    tongxianShow: !off(input.tongxianShow),
    // 神煞合参层：上游出厂关（yizhangjingShensha def false；挂载 schema default 0）。
    shenshaLayer: input.shenshaLayer === undefined || input.shenshaLayer === null ? false : !off(input.shenshaLayer) && !!input.shenshaLayer,
    // 折半法（十五折半/夜半折半）与品级变体：只在显式给出时进 opts（缺省字节不变）
    ...(input.leapRule === 'midnight' ? { leapRule: 'midnight' } : {}),
    ...(input.gradeSet === 'variant' ? { gradeSet: 'variant' } : {}),
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
    ...opts,
  };

  if (!date) {
    return insufficient(normalized, 'missing_date', 'yizhangjing requires a birth date.');
  }

  let bazi;
  try {
    bazi = buildLocalBaziResult(baziParams).bazi;
  } catch (error) {
    return insufficient(normalized, 'invalid_bazi_input', error instanceof Error ? error.message : `${error}`);
  }

  let model;
  try {
    model = buildYizhangjingModel(bazi, opts);
  } catch (error) {
    return insufficient(normalized, 'yizhangjing_calc_failed', error instanceof Error ? error.message : `${error}`);
  }
  if (!model || !model.chart) {
    return insufficient(normalized, 'yizhangjing_no_chart', 'yizhangjing could not derive the palm chart from the birth input.');
  }

  // 段头【段名】→ [段名]；正文（含行内全角括号）不动。
  const snapshotText = buildYizhangjingSnapshotText(model).replace(/^【([^】\n]+)】$/gm, '[$1]');

  const c = model.chart;
  return {
    tool: 'yizhangjing',
    technique: 'yizhangjing',
    input_normalized: normalized,
    data: {
      input: model.input,
      opts: c.opts,
      pillars: model.pillars,
      mingGong: { branch: c.mingBranch, star: c.mingStar },
      renshi: model.renshi,
      pattern: {
        fourPalaceRank: c.fourPalaceRank,
        mingGe: c.mingGe,
        nineGrade: c.nineGrade,
        gradeCount: c.gradeCount,
      },
      repeats: model.repeats,
      rishi: model.rishi,
      zhiye: model.zhiye,
      dayun: model.dayun,
      liunianZong: model.liunianZong,
      shenshaHits: model.shenshaHits,
      shenshaLayer: model.shenshaLayer,
      xiaoxian: buildXiaoxianRows(c, model),
      flowShen: buildFlowShenTable(c),
    },
    snapshot_text: snapshotText,
  };
}
