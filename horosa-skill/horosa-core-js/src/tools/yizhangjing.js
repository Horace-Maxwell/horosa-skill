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
  const baziParams = { date, time, zone: input.zone, lon: input.lon, gender: input.gender, timeAlg };

  // 排盘选项：定月法（农历月/节气月）、顺逆规则、命宫定法、大限一宫年数、大限起法、小限起宫、
  // 流年十二神组、早子时、重犯口诀组。神煞合参层无头导出默认开（预设全选即全量导出；关则不出该段）。
  const opts = {
    dingYue: input.dingYue === 'jieqi' ? 'jieqi' : 'lunar',
    shunniRule: input.shunniRule === 'menShunNvNi' ? 'menShunNvNi' : 'yangNanYinNv',
    mingGongMethod: input.mingGongMethod === 'shuZhiMao' ? 'shuZhiMao' : 'shiShang',
    dayunLength: input.dayunLength === 10 || input.dayunLength === '10' ? 10 : 7,
    dayunStartAge: input.dayunStartAge === 'age1' ? 'age1' : 'mi',
    xiaoxianStart: input.xiaoxianStart === 'yue' ? 'yue' : 'ri',
    flowShenSet: input.flowShenSet || 'A',
    zaoZiAdjust: !!input.zaoZiAdjust,
    chongfanKou: input.chongfanKou === 'beta' ? 'beta' : 'alpha',
    shenshaLayer: input.shenshaLayer === undefined || input.shenshaLayer === null ? true : !!input.shenshaLayer,
  };
  const normalized = {
    date,
    time,
    zone: input.zone ?? null,
    lon: input.lon ?? null,
    gender: input.gender ?? null,
    timeAlg,
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
    },
    snapshot_text: snapshotText,
  };
}
