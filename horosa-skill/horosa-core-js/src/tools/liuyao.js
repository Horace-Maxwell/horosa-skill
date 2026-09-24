// 六爻 headless 层：镜像上游 AI 挂载无头路径（Horosa-Public utils/aiAnalysisContext.js
// regenerateSixyaoSnapshot :1739-1760；已存卦分支 :1509-1516）。起卦与**整份**快照都出自 vendored 上游函数，
// 本文件只做入参装配、不自写一行快照：
//   ① 未手动摇卦（lines 空）→ buildTimeGua(nongli)（GuaZhanMain.js:74-98 以时起卦：年支序 + 农历月数
//      monthInt + 农历日数 dayInt + 时柱支序，时柱随 timeAlg）；
//   ② 扁平齿轮 liuyaoSettings → mergeLiuyaoGearSettings（aiAnalysisContext.js:1684-1729），仅在给了键时注入；
//   ③ 进 builder 前先 await 断语库（ensureLiuyaoDoctrineLoaded :1735-1737，[Q-391/T-373]：不载则 [占类断语]
//      的《断易天机》摘要行整段静默缺失）；
//   ④ 快照 = buildGuaSnapshotText(buildCaseSnapshotFields(record), st)（GuaZhanMain.js:201-391，
//      regenerateSixyaoSnapshot:1756 同一调用）：[起盘信息]（含 旬空 行与起卦时间「X时」后缀）/ [卦象]（本/互/之/
//      错/综卦）/ [六爻与动爻]（本卦逐爻 + 之/互/伏神/综/错卦逐爻装卦）/ [断卦结构] / [卦辞与断语] /
//      [判语库·参考诀表] / [断诀命中] / [占类断语]，段序、行式逐字节即上游。
//   无头卦不带 guaDesc（buildTimeGua 只回 {yao,currentGua,nongli}）→ [卦辞与断语] 只有段头（上游同形，
//   GuaZhanMain.js:62-63 注明挂载路径无 guaDesc）；卦辞原文仍由 Python 侧 /gua/desc 回在 data.descriptions。
//   无头卦亦不带 god（页面 fillYaoGods 渲染期才写，GuaZhanMain.js:1482-1493）→ 逐爻行无「六神:」后缀，
//   六神在 [断卦结构] 表内（同上游无头路径）。
import { buildTimeGua, buildGuaSnapshotText } from '../vendor/guazhan/GuaZhanMain.js';
import { loadDoctrine } from '../vendor/gua/data/liuyaoDoctrineCache.js';
import { getGua64, Gua64 } from '../vendor/gua/GuaConst.js';
import { littleEndian } from '../vendor/gua/littleEndian.js';
import { normalizeLiuyaoSettings, applyPreset, LIUYAO_PRESETS } from '../vendor/gua/liuyaoSchools.js';
import { YONGSHEN_CATEGORIES } from '../vendor/gua/liuyaoYongShen.js';
import { buildLocalBaziResult } from '../vendor/bazi/baziLunarLocal.js';

// ── 六爻判读口径（liuyaoSettings）────────────────────────────────────────────────────
// 键表 = 上游 AI 挂载齿轮 SIXYAO_FIELDS 的 24 个 name 与控件类型（techniqueMountSettings.js:614-676，
// 上游 HEAD 9b74714b），逐键移植。上游 mergeLiuyaoGearSettings 就是按这张 schema 机械求白名单的；
// skill 不 vendor 那份 2798 行的 schema 文件（它 import 了半棵 UI 常量树），故只移植「键名 + 是否开关」——
// 值域与缺省仍由 vendored liuyaoSchools / 各判读引擎自己的词表决定。键表漂移由
// tests/test_sync311_divination.py 在有上游 checkout 时对拍上游源看守。
export const LIUYAO_GEAR_FIELDS = Object.freeze({
  school: 'select', askType: 'select', yongOverride: 'select', benming: 'select',
  tuChangsheng: 'select', bianyaoScope: 'select', fushen: 'select', yuepoMode: 'select',
  shishen: 'select', jinTuiTu: 'select', tianshiSchool: 'select', yearBoundary: 'select',
  guashen: 'switch', sixGods: 'switch', yuqi: 'switch', yingqi: 'switch', doctrine: 'switch',
  gufa: 'switch', yueLiushen: 'switch', guirenFa: 'select',
  shenshaOn: 'switch', shenshaBase: 'select', shenshaSet: 'multiselect', shenshaExOn: 'switch',
});
const LY_STRUCTURAL = ['shenshaOn', 'shenshaBase', 'shenshaSet', 'shenshaExOn'];
const lyBool = (v) => v === true || v === 1 || v === '1';

// 上游 mergeLiuyaoGearSettings（aiAnalysisContext.js:1684-1731）逐行同构。saved = 存档卦的
// liuyaoSettings；skill 每次现起卦、无存档层，恒传 {}。
export function mergeLiuyaoGearSettings(saved, flat) {
  const f = flat && typeof flat === 'object' ? flat : {};
  let base = saved && typeof saved === 'object' ? { ...saved } : {};
  // [Q-206/T-151] 选中的预设与存档流派不同 → 以 applyPreset(该派) 为底，其余齿轮键再叠上。
  if (f.school && f.school !== base.school && LIUYAO_PRESETS[f.school]) {
    base = applyPreset(f.school, base);
  }
  Object.keys(LIUYAO_GEAR_FIELDS).forEach((k) => {
    if (LY_STRUCTURAL.indexOf(k) >= 0 || f[k] === undefined) {
      return;
    }
    base[k] = LIUYAO_GEAR_FIELDS[k] === 'switch' ? lyBool(f[k]) : f[k];
  });
  if (f.shenshaOn !== undefined || f.shenshaBase !== undefined || f.shenshaSet !== undefined) {
    const prev = (saved && saved.shensha && typeof saved.shensha === 'object') ? saved.shensha : {};
    base.shensha = {
      ...prev,
      ...(f.shenshaOn !== undefined ? { on: lyBool(f.shenshaOn) } : {}),
      ...(f.shenshaBase !== undefined ? { base: f.shenshaBase } : {}),
      ...(f.shenshaSet !== undefined && Array.isArray(f.shenshaSet) ? { set: f.shenshaSet.slice() } : {}),
    };
  }
  if (f.shenshaExOn !== undefined) {
    base.shenshaEx = {
      ...((saved && saved.shenshaEx && typeof saved.shenshaEx === 'object') ? saved.shenshaEx : { set: null }),
      on: lyBool(f.shenshaExOn),
    };
  }
  return base;
}

// 回执：认不出的键 / 值不在 vendored 词表里的键，两类各自如实列出。
// （旧版另有第三类「只改 skill 尚不产之段」—— shishen/tianshiSchool/yuqi/gufa/yueLiushen/shenshaExOn 六键
//   只影响 [断诀命中]/[占类断语]；两段现由 vendored liuyaoSnapshotEx 产出，六键全部生效，该类作废。）
function liuyaoSettingsReport(flat) {
  const f = flat && typeof flat === 'object' ? flat : {};
  const ignored = Object.keys(f).filter((k) => !Object.prototype.hasOwnProperty.call(LIUYAO_GEAR_FIELDS, k)).sort();
  const invalid = [];
  if (f.school !== undefined && !LIUYAO_PRESETS[f.school] && f.school !== 'custom') {
    invalid.push(`school=${f.school}`);
  }
  if (f.askType !== undefined && !YONGSHEN_CATEGORIES.some((c) => c.key === f.askType)) {
    invalid.push(`askType=${f.askType}`);
  }
  return { ignored, invalid };
}

// 上游 fetchPreciseNongli 的 ensureYearGZByLunar（preciseCalcBridge.js:361-377）：后端 /nongli/time 不产
// yearGZByLunar，缺键时按同一份本地历法（buildLocalNongliFallback → buildLocalBaziResult(...).bazi.nongli，
// :220-224）补上，其余字段一字不动 —— 不补则六爻「定年界线=正月初一」（yearBoundary='lunar'）恒回落立春。
// 入参 = skill 发给 /nongli/time 的同一份请求；日界两开关缺席时取上游挂载路径实发值 1/1
// （buildCaseSnapshotParams:819-820 恒带 defaultAfter23NewDay()/defaultLateZiHourUseNextDay() = 出厂 1/1，
// 与后端缺省同值）。
function withYearGzByLunar(nongli, params, warnings) {
  if (!nongli || typeof nongli !== 'object' || nongli.yearGZByLunar || !params || typeof params !== 'object') {
    return nongli;
  }
  const bit = (v, def) => (v === undefined || v === null || v === '' ? def : (Number(v) === 1 ? 1 : 0));
  try {
    const local = buildLocalBaziResult({
      date: params.date, time: params.time, zone: params.zone, lon: params.lon,
      timeAlg: bit(params.timeAlg, 0),
      after23NewDay: bit(params.after23NewDay, 1),
      lateZiHourUseNextDay: bit(params.lateZiHourUseNextDay, 1),
    });
    const lunarYear = local && local.bazi && local.bazi.nongli ? local.bazi.nongli.yearGZByLunar : null;
    if (lunarYear) {
      return { ...nongli, yearGZByLunar: lunarYear };
    }
    warnings.push('正月初一口径年干支（yearGZByLunar）本地历法补不出：定年界线=正月初一 将回落立春年干支。');
  } catch (e) {
    warnings.push(`正月初一口径年干支（yearGZByLunar）本地补算失败（${e instanceof Error ? e.message : e}）：定年界线=正月初一 将回落立春年干支。`);
  }
  return nongli;
}

function manualLines(lines) {
  return Array.isArray(lines) && lines.length === 6 && lines.every((y) => y && (y.value === 0 || y.value === 1));
}

// 上游 buildCaseSnapshotFields(record)（aiAnalysisContext.js:780-797）的同形薄适配：buildGuaSnapshotText 只读
// date/time（.value.format）、zone、lon/lat（两者皆为对象即出「经纬度」行）、gender 五项。缺省逐项照上游：
// zone 缺省 '+08:00'、lon/lat 缺省 ''、gender = record.gender ?? 1（:791；起课时间合成源 timepointDraft.gender
// 亦缺省 1，AIAnalysisMain.js:996；页面全局 fields.gender 出厂 1，models/astro.js:410）→ 缺省即「求测人性别：男」。
// record 缺 date/time（直调 JS、无占时）→ 不建 date/time 字段，builder 即不出「日期」行（fieldTime 为空）。
// date/time 是同一 DateTime 的两种格式化（:784-785）：这里直接回 Python 已归一的 'YYYY-MM-DD' / 'HH:mm:ss' 串，
// 不做二次校验（公元前等非常规日期照印，不因格式化炸掉整份快照）。
function caseSnapshotFields(record) {
  if (!record || typeof record !== 'object') {
    return null;
  }
  const fields = {};
  if (record.date && record.time) {
    const date = `${record.date}`.replace(/\//g, '-');
    const time = /^\d{1,2}:\d{2}$/.test(`${record.time}`) ? `${record.time}:00` : `${record.time}`;
    const dt = { format: (pattern) => (pattern === 'YYYY-MM-DD' ? date : time) };
    fields.date = { value: dt };
    fields.time = { value: dt };
  }
  fields.zone = { value: record.zone ? record.zone : '+08:00' };
  fields.lon = { value: record.lon ? record.lon : '' };
  fields.lat = { value: record.lat ? record.lat : '' };
  fields.gender = { value: record.gender !== undefined && record.gender !== null ? record.gender : 1 };
  return fields;
}

// 手动摇卦 = 页面一次性成卦后的 state（GuaZhanMain.getCurrentGua + setupYao，:1106-1138）：currentGua = Gua64 序，
// 爻名缺省取该卦 yaoname（setupYao 就地写 name）；调用方自带的 name/god 原样保留（旧接口字段，逐爻行照印）。
function manualGua(lines, nongli) {
  const g = getGua64(littleEndian(lines.map((y) => y.value)));
  if (!g) {
    return null;
  }
  const names = Gua64[g.index].yaoname;
  return {
    yao: lines.map((y, i) => ({ ...y, change: !!y.change, name: y.name || names[i] })),
    currentGua: g.index,
    nongli,
  };
}

export async function runLiuyao(payload) {
  const input = payload && typeof payload === 'object' ? payload : {};
  const warnings = [];
  const gear = input.liuyaoSettings && typeof input.liuyaoSettings === 'object' ? input.liuyaoSettings : null;
  const report = liuyaoSettingsReport(gear);
  const nongli = withYearGzByLunar(input.nongli && typeof input.nongli === 'object' ? input.nongli : {}, input.nongliParams, warnings);

  // 卦：手动摇卦（lines 六爻俱全）按页面 state 同形（currentGua = Gua64 序、yao 自下而上、爻名取卦 yaoname）；
  // 否则以时起卦 = 上游无头路径 buildTimeGua(nongli)。
  const hasLines = Array.isArray(input.lines) && input.lines.length > 0;
  let gua = null;
  if (hasLines) {
    if (manualLines(input.lines)) {
      gua = manualGua(input.lines, nongli);
    }
  } else {
    gua = buildTimeGua(nongli);
  }
  const lines = gua ? gua.yao.map((y) => ({ value: y.value, change: !!y.change, god: y.god ?? null, name: y.name ?? null })) : [];
  const castInfo = {
    lines,
    time_cast: !hasLines,
    current_gua: gua && Gua64[gua.currentGua] ? { index: gua.currentGua, name: Gua64[gua.currentGua].name } : null,
  };
  if (!gua) {
    return {
      ...castInfo,
      snapshot_text: '',
      data: { settings_ignored: report.ignored, settings_invalid: report.invalid, warnings,
        time_cast_failed: !hasLines, lines_invalid: hasLines },
    };
  }

  // 齿轮判读设置注入：与上游同 —— 只在给了键时才叠 liuyaoSettings（regenerateSixyaoSnapshot:1753-1755）。
  const st = gear && Object.keys(gear).length ? { ...gua, liuyaoSettings: mergeLiuyaoGearSettings({}, gear) } : gua;
  const doctrine = await loadDoctrine();   // ensureLiuyaoDoctrineLoaded（:1735-1737）
  if (!doctrine) {
    warnings.push('六爻《断易天机》断语库未能载入：[占类断语] 缺「断语·占类门」摘要行（上游同样不阻断快照）。');
  }
  const settings = normalizeLiuyaoSettings(st.liuyaoSettings);
  return {
    ...castInfo,
    // 整份快照 = 上游 buildGuaSnapshotText(fields, st)（regenerateSixyaoSnapshot:1756），不再拼接、不裁段。
    snapshot_text: buildGuaSnapshotText(caseSnapshotFields(input.record), st),
    data: {
      // 实际生效的判读口径（归一后），供 Python 如实回执。
      settings: {
        school: settings.school, askType: settings.askType, yongOverride: settings.yongOverride,
        benming: settings.benming, tuChangsheng: settings.tuChangsheng, bianyaoScope: settings.bianyaoScope,
        fushen: settings.fushen, yuepoMode: settings.yuepoMode, shishen: settings.shishen, jinTuiTu: settings.jinTuiTu,
        tianshiSchool: settings.tianshiSchool, yearBoundary: settings.yearBoundary, guashen: settings.guashen,
        sixGods: settings.sixGods, yuqi: settings.yuqi, yingqi: settings.yingqi, doctrine: settings.doctrine,
        gufa: settings.gufa, yueLiushen: settings.yueLiushen, guirenFa: settings.guirenFa,
        shensha: settings.shensha, shenshaEx: settings.shenshaEx,
      },
      doctrine_loaded: !!doctrine,
      settings_ignored: report.ignored,
      settings_invalid: report.invalid,
      warnings,
    },
  };
}
