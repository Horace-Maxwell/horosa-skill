// 皇极轨策 formatter —— 十二法起卦·演数四位·卦变断法·三要十应·元会运世·大定起数，纯函数进程内，零后端。
// 卦为【冻结值】：起卦一经起出即不重起，改流派/十开关只重排断法。占时四柱由 service.py 前置
// /nongli/time 拼 ctx（立春界年柱 + 农历月日 + 时支）后传入，JS 层不发 HTTP（AGENTS §4）。
import { qiGua } from '../vendor/guice/core/guiceQiGua.js';
import { buildGuicePan } from '../vendor/guice/core/guicePan.js';
import { buildGuiceSnapshotText } from '../vendor/guice/guiceSnapshot.js';
import { normalizeGuiceSettings, DEFAULT_GUICE_SETTINGS } from '../vendor/guice/guiceSchools.js';

const SETTING_KEYS = ['school', 'qiguaFa', 'yanshuFa', 'jiGongMode', 'qiguaShu', 'shenSha', 'shiFang', 'shuXi', 'dadingTable', 'shiyingSet'];
const CAST_KEYS = ['nums', 'wuShu', 'shengShu', 'text', 'shu', 'shu2', 'tones', 'zhang', 'chi', 'cun', 'qu', 'wuGuaNum', 'fangGuaNum', 'kind'];

function insufficient(normalized, reason, message) {
  return {
    tool: 'guice',
    technique: 'guice',
    input_normalized: normalized,
    data: { ok: false, reason, message: message || '' },
    snapshot_text: '',
  };
}

export function runGuice(payload) {
  const input = payload && typeof payload === 'object' ? payload : {};
  const rawSettings = {};
  SETTING_KEYS.forEach((k) => { if (input[k] !== undefined && input[k] !== null) { rawSettings[k] = input[k]; } });
  const settings = normalizeGuiceSettings(rawSettings);
  const fa = settings.qiguaFa || DEFAULT_GUICE_SETTINGS.qiguaFa;
  // 起卦输入：法专属字段 + 占时四要（年支/农历月日/时支，time 法与多数报数法之下卦即时数）。
  const castInput = { hourZhi: input.hourZhi, yearZhi: input.yearZhi, lunarMonth: input.lunarMonth, lunarDay: input.lunarDay };
  CAST_KEYS.forEach((k) => { if (input[k] !== undefined && input[k] !== null) { castInput[k] = input[k]; } });
  const ctx = {
    yearZhi: input.yearZhi,
    monthZhi: input.monthZhi,
    lunarMonth: input.lunarMonth,
    lunarDay: input.lunarDay,
    hourZhi: input.hourZhi,
    year: input.year,
    dayGan: input.dayGan,
    pillars: Array.isArray(input.pillars) ? input.pillars : [],
    fangKey: input.fangKey,
    askEvent: `${input.askEvent ?? ''}`.trim(),
  };
  const shiyingInputs = input.shiyingInputs && typeof input.shiyingInputs === 'object' ? input.shiyingInputs : {};
  const timeLines = Array.isArray(input.timeLines) ? input.timeLines : [];
  const normalized = { qiguaFa: fa, settings, ctx, shiyingInputs };
  const gua = qiGua(fa, castInput);
  if (!gua) {
    return insufficient(normalized, 'qigua_failed', `guice ${fa} 法起卦失败：所需之输入未足（见 QIGUA_FA_INPUTS）。`);
  }
  let pan;
  try {
    pan = buildGuicePan({ gua, ctx, settings, shiyingInputs });
  } catch (error) {
    return insufficient(normalized, 'buildpan_failed', error instanceof Error ? error.message : `${error}`);
  }
  if (!pan) {
    return insufficient(normalized, 'buildpan_null', 'guice could not build the 盘 from the cast/context.');
  }
  const snapshot_text = buildGuiceSnapshotText(pan, { timeLines });
  return {
    tool: 'guice',
    technique: 'guice',
    input_normalized: normalized,
    data: {
      qiguaFa: fa,
      // 本卦名在 pan.gua.name（buildGuicePan 叠加），变卦名在 pan.bianName；raw gua 只有 up/lo/dongYao。
      gua: { ben: (pan.gua && pan.gua.name) || null, bian: pan.bianName || null, dongYao: gua.dongYao },
      settings,
    },
    snapshot_text,
  };
}
