import * as ZWConst from '../vendor/bazi/ZWConst.js';
import * as ZiWeiHelper from '../vendor/ziwei/ZiWeiHelper.js';
import { calcZiwei, deriveSanPan, applyLifeMasterOption } from '../vendor/ziwei/ZiweiCalc.js';
import { detectPatterns } from '../vendor/ziwei/ziweiPatterns.js';
import { isYangGan } from '../vendor/ziwei/ziweiCore.js';
import {
  ZWEngineOptions,
  ziweiNeedsLocalEngine,
  collectEngineOpts,
  DAXIAN_SPAN_OPTIONS,
  TIANMA_BASIS_OPTIONS,
  STAR_SET_OPTIONS,
  SANPAN_OPTIONS,
  SHANGSHI_OPTIONS,
  LEAP_MONTH_OPTIONS,
  LATE_ZI_OPTIONS,
  YEAR_BOUNDARY_OPTIONS,
  HUOLING_OPTIONS,
  KONG_NAMING_OPTIONS,
  LIUNIAN_SIHUA_GAN_OPTIONS,
  LIU_YUE_BASIS_OPTIONS,
  KUIYUE_OPTIONS,
  KONGWANG_STYLE_OPTIONS,
  CHANGSHENG_DIRECTION_OPTIONS,
  CHANGSHENG_START_OPTIONS,
  LIFE_MASTER_BY_OPTIONS,
  BRIGHTNESS_SOURCE_OPTIONS,
} from '../vendor/ziwei/ziweiOptions.js';
import { normalizeBrightnessCustomTable, ZWBrightnessCustom } from '../vendor/ziwei/data/ziweiTables.js';
import { buildZiWeiSnapshotText } from '../vendor/ziwei/ziweiSnapshotText.js';

/**
 * 紫微 ziwei_birth：上游 buildZiweiSnapshotForParams（ZiWeiMain.js:716-822，AI 分析无头复算路径）的 headless 编排。
 *
 * 上游步骤（逐条对应，行号为上游）：
 *   ① taiSuiRelatives 文本 → [{branch}]（:720-723）；
 *   ② 四化流派 sihuaSchool 临时切 ZWSchool.school + refreshActiveSiHua + resetHuaMap（:727-736）；
 *   ③ custom 档随盘自定义四化表注入 ZWSihuaCustom.override（:739-745）；④ 随盘自定义亮度表（:747-749）；
 *   ⑤ 传本/排盘开关临时覆盖可变单例 ZWEngineOptions（:752-767）；
 *   ⑥ Java /ziwei/birth（body 去掉本地键；流派非 beipai 附 p.sihua = getActiveSiHuaGan()，:768-780）——
 *      **JS 不发 HTTP（AGENTS §4）**：本工具 action='prepare' 回 sihua 表，Python 发 Java，再 action='finalize'；
 *   ⑦ 任一传本开关非缺省（ziweiNeedsLocalEngine）→ 本地 calcZiwei(+deriveSanPan) 覆盖盘核心、同步 yearPolar、
 *      detectPatterns 重算格局（:786-804；本地异常保留 Java 盘，上游同）；否则 applyLifeMasterOption（:806）；
 *   ⑧ buildZiWeiSnapshotText(params, result)（:807）；finally 逐项还原单例（:808-822）。
 *
 * 取值锚到引擎自带词表（ziweiOptions.js 的 *_OPTIONS 与 ZWConst.SiHuaTables），认不出的键值不静默：
 * 回 `warnings`（按缺省排盘），由 Python 进 envelope.warnings。
 *
 * payload: { action: 'prepare'|'finalize', params: {date,time,zone,lon,lat,gpsLat,gpsLon,gender,timeAlg,
 *            after23NewDay,lateZiHourUseNextDay, sihuaSchool?, sihuaCustomTable?, brightnessCustomTable?,
 *            period?, <传本/流派键>…}, result?: Java /ziwei/birth 响应 }
 */

// 上游 buildZiweiSnapshotForParams 的 ZW_ENGINE_SWITCH_KEYS（ZiWeiMain.js:752-754），键名与顺序逐字。
const ZW_ENGINE_SWITCH_KEYS = ['daxianSpan', 'tianmaBasis', 'starSet', 'sanPan', 'shangShi', 'leapMonth', 'lateZi', 'yearBoundary', 'huoling', 'kongNaming',
  'brightnessSource', 'lifeMasterBy', 'liuYueBasis', 'liunianSihuaGan', 'changshengStart', 'changshengDirection', 'kuiYue', 'kongwangStyle', 'flowLuanXi', 'flowHuoLing', 'flowShenshaOnChart', 'childLimit', 'zhongxian', 'huoPan', 'qishuWei', 'borrowPalace', 'taiSuiRuGua', 'taiSuiRelatives', 'xiaoxianMode'];

// 选择型键 → 引擎自带选项表（取值唯一真值；不手抄）。
const SELECT_VOCAB = {
  daxianSpan: DAXIAN_SPAN_OPTIONS,
  tianmaBasis: TIANMA_BASIS_OPTIONS,
  starSet: STAR_SET_OPTIONS,
  sanPan: SANPAN_OPTIONS,
  shangShi: SHANGSHI_OPTIONS,
  leapMonth: LEAP_MONTH_OPTIONS,
  lateZi: LATE_ZI_OPTIONS,
  yearBoundary: YEAR_BOUNDARY_OPTIONS,
  huoling: HUOLING_OPTIONS,
  kongNaming: KONG_NAMING_OPTIONS,
  liunianSihuaGan: LIUNIAN_SIHUA_GAN_OPTIONS,
  liuYueBasis: LIU_YUE_BASIS_OPTIONS,
  kuiYue: KUIYUE_OPTIONS,
  kongwangStyle: KONGWANG_STYLE_OPTIONS,
  changshengDirection: CHANGSHENG_DIRECTION_OPTIONS,
  changshengStart: CHANGSHENG_START_OPTIONS,
  lifeMasterBy: LIFE_MASTER_BY_OPTIONS,
  brightnessSource: BRIGHTNESS_SOURCE_OPTIONS,
  // 小限顺逆：挂载键 ziweiXiaoxianYinyang → 单例键 xiaoxianMode（aiAnalysisContext.js:1903-1906；取值 '0'/'1'）
  xiaoxianMode: [{ value: '0' }, { value: '1' }],
};
const SWITCH_KEYS = ['flowLuanXi', 'flowHuoLing', 'flowShenshaOnChart', 'childLimit', 'zhongxian', 'huoPan', 'qishuWei', 'borrowPalace', 'taiSuiRuGua'];
const BRANCHES = '子丑寅卯辰巳午未申酉戌亥';

function present(v) {
  return v !== undefined && v !== null && !(typeof v === 'string' && v.trim() === '');
}

// 紫云关系人：数组 [{branch,role,sex}] / 文本「午:母:female 子」两态（aiAnalysisContext.js:1923-1938 同式）。
function normalizeRelatives(raw) {
  if (Array.isArray(raw)) {
    return raw.map((it) => {
      if (it && typeof it === 'object') {
        const b = `${it.branch || ''}`;
        return (BRANCHES.indexOf(b) >= 0 && b) ? { branch: b, role: it.role || '', sex: it.sex || '' } : null;
      }
      const seg = `${it}`.split(/[:：]/);
      return (BRANCHES.indexOf(seg[0]) >= 0 && seg[0]) ? { branch: seg[0], role: seg[1] || '', sex: seg[2] || '' } : null;
    }).filter(Boolean);
  }
  return `${raw}`.split(/[\s,，、]+/).map((tok) => {
    const seg = `${tok}`.split(/[:：]/);
    return (BRANCHES.indexOf(seg[0]) >= 0 && seg[0]) ? { branch: seg[0], role: seg[1] || '', sex: seg[2] || '' } : null;
  }).filter(Boolean);
}

/** 入参 → 规范化的单例覆盖表 + warnings（认不出的值不进覆盖，按缺省排盘并回报）。 */
export function canonicalZiweiSettings(params) {
  const src = params && typeof params === 'object' ? params : {};
  const engine = {};
  const warnings = [];
  ZW_ENGINE_SWITCH_KEYS.forEach((key) => {
    const raw = key === 'xiaoxianMode' && !present(src.xiaoxianMode) ? src.ziweiXiaoxianYinyang : src[key];
    if (!present(raw)) { return; }
    if (key === 'taiSuiRelatives') {
      engine[key] = normalizeRelatives(raw);
      return;
    }
    if (SWITCH_KEYS.indexOf(key) >= 0) {
      const text = `${raw}`.trim().toLowerCase();
      if (['1', 'true', 'on', 'yes'].indexOf(text) >= 0) { engine[key] = true; return; }
      if (['0', 'false', 'off', 'no'].indexOf(text) >= 0) { engine[key] = false; return; }
      warnings.push({ key, value: raw, valid: ['0', '1'] });
      return;
    }
    const vocab = SELECT_VOCAB[key] || [];
    const hit = vocab.find((opt) => `${opt.value}` === `${raw}`.trim());
    if (hit) {
      engine[key] = hit.value;   // 取引擎表里的规范值（daxianSpan 的 10 是 number，'ju' 是 string）
    } else {
      warnings.push({ key, value: raw, valid: vocab.map((opt) => `${opt.value}`) });
    }
  });
  let school = null;
  if (present(src.sihuaSchool)) {
    const s = `${src.sihuaSchool}`.trim();
    if (ZWConst.SiHuaTables[s] || s === 'custom') {
      school = s;
    } else {
      warnings.push({ key: 'sihuaSchool', value: src.sihuaSchool, valid: [...Object.keys(ZWConst.SiHuaTables), 'custom'] });
    }
  }
  const customSihua = present(src.sihuaCustomTable) ? ZWConst.normalizeSihuaCustomTable(src.sihuaCustomTable) : null;
  if (present(src.sihuaCustomTable) && !customSihua) {
    warnings.push({ key: 'sihuaCustomTable', value: '(invalid)', valid: ['{"干":["禄星","权星","科星","忌星"],…}'] });
  }
  if (school === 'custom' && !customSihua) {
    warnings.push({ key: 'sihuaSchool', value: 'custom', valid: ['custom 需配合法 sihuaCustomTable；缺表按通用表'] });
  }
  const customBrightness = present(src.brightnessCustomTable) ? normalizeBrightnessCustomTable(src.brightnessCustomTable) : null;
  if (present(src.brightnessCustomTable) && !customBrightness) {
    warnings.push({ key: 'brightnessCustomTable', value: '(invalid)', valid: ['{"星":{"支":"庙|旺|得|地|利|平|闲|不|陷"}}'] });
  }
  return { engine, school, customSihua, customBrightness, warnings };
}

// ②③④⑤：临时切单例；返回还原函数（调用方 finally 调）。
function applyOverrides(settings) {
  const prevSchool = ZWConst.ZWSchool.school;
  const overrideSchool = settings.school && settings.school !== prevSchool ? settings.school : null;
  if (overrideSchool) {
    ZWConst.ZWSchool.school = overrideSchool;
    ZWConst.refreshActiveSiHua();
    ZiWeiHelper.resetHuaMap();
  }
  const useCustomSihua = ZWConst.ZWSchool.school === 'custom' && settings.customSihua;
  if (useCustomSihua) {
    ZWConst.ZWSihuaCustom.override = settings.customSihua;
    ZWConst.refreshActiveSiHua();
    ZiWeiHelper.resetHuaMap();
  }
  if (settings.customBrightness) { ZWBrightnessCustom.override = settings.customBrightness; }
  const prevEngine = {};
  Object.keys(settings.engine).forEach((key) => {
    prevEngine[key] = ZWEngineOptions[key];
    ZWEngineOptions[key] = settings.engine[key];
  });
  return () => {
    if (settings.customBrightness) { ZWBrightnessCustom.override = null; }
    if (useCustomSihua) {
      ZWConst.ZWSihuaCustom.override = null;
      ZWConst.refreshActiveSiHua();
      ZiWeiHelper.resetHuaMap();
    }
    if (overrideSchool) {
      ZWConst.ZWSchool.school = prevSchool;
      ZWConst.refreshActiveSiHua();
      ZiWeiHelper.resetHuaMap();
    }
    Object.keys(prevEngine).forEach((key) => { ZWEngineOptions[key] = prevEngine[key]; });
  };
}

export function runZiweiBirth(payload) {
  const source = payload && typeof payload === 'object' ? payload : {};
  const params = source.params && typeof source.params === 'object' ? source.params : {};
  const settings = canonicalZiweiSettings(params);
  const restore = applyOverrides(settings);
  try {
    const school = ZWConst.ZWSchool.school;
    // ⑥ 非 beipai 流派附四化表（上游 :776-779「非默认流派才附 sihua」零回归约定）。
    const sihua = school && school !== 'beipai' ? ZWConst.getActiveSiHuaGan() : null;
    const localEngine = ziweiNeedsLocalEngine();
    if (source.action === 'prepare') {
      return { data: { ok: true, sihua, school, localEngine }, warnings: settings.warnings };
    }
    const javaResult = source.result && typeof source.result === 'object' ? source.result : null;
    if (!javaResult || !javaResult.chart) {
      return { data: { ok: false, reason: 'missing_java_result' }, text: '', warnings: settings.warnings };
    }
    const result = { ...javaResult, chart: { ...javaResult.chart } };
    let localApplied = false;
    let localError = null;
    if (localEngine) {
      // ⑦ 上游 :786-804 逐句：birth.ad 恒 1（上游同）；opts 的日界/晚子时用已解析缺省（本地引擎缺键 = 不进位）。
      try {
        const birth = { date: params.date, time: params.time, zone: params.zone, lon: params.lon, lat: params.lat, gpsLon: params.gpsLon, gpsLat: params.gpsLat, ad: 1, gender: params.gender };
        const opts = { timeAlg: params.timeAlg, after23NewDay: params.after23NewDay, lateZiHourUseNextDay: params.lateZiHourUseNextDay, lateZi: ZWEngineOptions.lateZi, yearBoundary: ZWEngineOptions.yearBoundary, ...collectEngineOpts(ZWEngineOptions), lifeMasterBy: ZWEngineOptions.lifeMasterBy || 'year_branch' };
        let localChart = calcZiwei(birth, opts);
        if (ZWEngineOptions.sanPan && ZWEngineOptions.sanPan !== 'tian') { localChart = deriveSanPan(localChart, ZWEngineOptions.sanPan); }
        if (localChart && Array.isArray(localChart.houses) && localChart.houses.length === 12) {
          result.chart = { ...result.chart, ...localChart };
          if (localChart.yearGan) { result.chart.yearPolar = isYangGan(localChart.yearGan) ? 'Positive' : 'Negative'; }
          try { const lp = detectPatterns(result.chart); if (Array.isArray(lp)) { result.patterns = lp; } } catch (e3) { /* 保留 Java patterns（上游同） */ }
          localApplied = true;
        }
      } catch (e4) {
        // 本地异常 → 保留 Java 盘（上游 :804 同）；但不静默：回报给 Python 进 warnings。
        localError = `${(e4 && e4.message) || e4}`;
      }
    }
    // ⑧' [P2a] 命主取法后处理：仅 Java 盘路径（上游 :806）
    if (!localEngine) { applyLifeMasterOption(result.chart, ZWEngineOptions.lifeMasterBy); }
    const text = buildZiWeiSnapshotText(params, result) || '';
    return {
      data: { ok: true, chart: result.chart, patterns: result.patterns || [], school, localEngine, localApplied, localError },
      text,
      warnings: settings.warnings,
    };
  } finally {
    restore();
  }
}

export default runZiweiBirth;
