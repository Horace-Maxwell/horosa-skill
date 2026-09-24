// 大六壬 headless 工具 —— 起课核（天地盘 / 四课 / 三传）与 AI 快照全部走 vendored 上游
// vendor/liureng/LiuRengMain.js（buildLiuRengCastOverride / buildLiuRengLayout / buildKeData /
// buildSanChuanData / buildLiuRengSnapshotText），与主六壬页、六壬择时扫描（liurengZeriScanEngine）
// 同一函数族：主排盘一修，这里自动跟，零第二实现。
//
// v3.11.x 同步（sanshi chunk F5）之前，本文件自带一份手写起课核（SanChuanBuilder）+ 手写快照 builder：
// 行格式停在老版（上游早已 GFM 表化）、[十二长生]/[大格]/[小局]/[参考]/[概览] 恒为占位，
// 起课法 26 法 / 换将 / 分昼夜 / 涉害取舍 / 阴阳系 / 十二长生五行 / 贵人 3·4 统统无入口；
// 断卦层 refCtx 还走另一份手抄的 liurengRefContext（三参 buildSanChuanData，不认涉害口径）——
// 同一张课两套三传。现在一律交给上游：口径参数只在这里做**词表校验**（锚到上游自带的
// LIURENG_PAGE_SETTINGS / QI_METHODS，不手抄），认不出的值报结构化错误而不静默回落缺省。
import * as LRConst from '../vendor/liureng/LRConst.js';
import {
  QI_METHODS,
  LIURENG_PAGE_SETTINGS,
  buildLiuRengCastOverride,
  computeQiXY,
  buildLiuRengLayout,
  buildKeData,
  buildSanChuanData,
  buildLiuRengSnapshotText,
  liurengBenmingXingnian,
  getSolarYearFromField,
} from '../vendor/liureng/LiuRengMain.js';
import { validateSettingValue } from '../vendor/utils/pageSettingsStore.js';

// 贵人体系显示名：与上游 buildLiuRengSnapshotText 的 [起盘信息]「贵人体系」行同序同字
// （LiuRengMain.js:4391，GuiRengs 下标 0–4）。只用于 data.layout 的回显字段，快照行由上游 builder 自产。
const GUIREN_LABELS = ['六壬法贵人', '遁甲法贵人', '星占法贵人', '甲戊兼牛羊', '干合阳阴贵'];
// 十二长生五行合法值 = vendored LRConst.WuXing 的五行（不手抄，test/handcopy.mjs 守）。
const WUXING = LRConst.WuXing.map((w) => w.elem);
// 需逐课输入的三法（上游 LiuRengMain.js:3900 QI_METHODS_NEEDING_INPUT）：缺输入时上游 computeQiXY 静默回落正时，
// headless 没有「先选法再填数」的交互，缺输入即报错。
const NEEDS_ZHI = ['xuanshi'];
const NEEDS_NUM = ['yanshu', 'baoshu'];
// 起课口径键：上游 LIURENG_PAGE_SETTINGS 的 schema 键（castMethod 另按 QI_METHODS 全 26 法校验——
// 页面设置只存不需逐课输入的 23 法，选时/演数/报数同样合法）。
const CAST_KEYS = ['castMethod', 'yueJiangMethod', 'fenZhouYe', 'seHaiMethod', 'seHaiBoundary', 'shiRuKe',
  'yearShenShaSort', 'yinyangSystem', 'tuWangShuai'];
// timeAlg 由 Python 侧校验并随 /liureng/gods 请求下发（起课时柱）；此处只放行，不参与 JS 计算。
const INPUT_KEYS = ['xuanShiZhi', 'yanShuNum', 'wuxing', 'timeAlg'];

function branchOf(value) {
  const match = `${value || ''}`.match(/[子丑寅卯辰巳午未申酉戌亥]/);
  return match ? match[0] : '';
}

function stemOf(value) {
  const match = `${value || ''}`.match(/[甲乙丙丁戊己庚辛壬癸]/);
  return match ? match[0] : '';
}

function valueText(value) {
  if (value === undefined || value === null || value === '') {
    return '';
  }
  if (typeof value === 'object') {
    return `${value.ganzi || value.cell || ''}`;
  }
  return `${value}`;
}

export function normalizeChart(payload) {
  const chart = payload.chart && payload.chart.chart ? payload.chart.chart : payload.chart;
  const liureng = payload.liureng || {};
  const chartObj = chart && typeof chart === 'object' ? { ...chart } : {};
  chartObj.nongli = {
    ...(liureng.nongli || {}),
    ...(chartObj.nongli || {}),
  };
  if (!chartObj.nongli.dayGanZi && liureng.fourColumns && liureng.fourColumns.day) {
    chartObj.nongli.dayGanZi = valueText(liureng.fourColumns.day.ganzi || liureng.fourColumns.day);
  }
  if (!chartObj.nongli.time && liureng.fourColumns && liureng.fourColumns.time) {
    chartObj.nongli.time = valueText(liureng.fourColumns.time.ganzi || liureng.fourColumns.time);
  }
  if (chartObj.isDiurnal === undefined || chartObj.isDiurnal === null) {
    chartObj.isDiurnal = payload.isDiurnal !== undefined && payload.isDiurnal !== null ? !!payload.isDiurnal : true;
  }
  return chartObj;
}

function invalid(field, value, allowed, message) {
  return {
    ok: false,
    error: {
      code: 'invalid_option',
      field,
      value,
      allowed,
      message: message || `大六壬 ${field} 取值无效：${JSON.stringify(value)}（可选：${(allowed || []).join(' / ')}）`,
    },
  };
}

function toBool(value) {
  if (value === true || value === 1 || value === '1' || value === 'true') return true;
  if (value === false || value === 0 || value === '0' || value === 'false') return false;
  return undefined;
}

// 起课口径：payload.options（MCP 声明入口）与顶层同名键（三式合一子盘 / 历史调用）双读，options 优先。
// 返回 {ok, castOpts, guirengType, wuxing}；认不出的值 → {ok:false, error}（Python 侧转 ToolValidationError）。
export function resolveLiurengOptions(payload) {
  const src = payload && typeof payload === 'object' ? payload : {};
  const opts = src.options && typeof src.options === 'object' ? src.options : {};
  const pick = (key) => (opts[key] !== undefined && opts[key] !== null && opts[key] !== '' ? opts[key]
    : (src[key] !== undefined && src[key] !== null && src[key] !== '' ? src[key] : undefined));
  const schema = LIURENG_PAGE_SETTINGS.schema;
  const castOpts = {};
  for (const key of CAST_KEYS) {
    let value = pick(key);
    if (value === undefined) continue;
    if (key === 'castMethod') {
      const allowed = QI_METHODS.map((m) => m.key);
      if (allowed.indexOf(value) < 0) return invalid(key, value, allowed);
    } else if (key === 'shiRuKe') {
      const b = toBool(value);
      if (b === undefined) return invalid(key, value, ['true', 'false']);
      value = b;
    } else if (!validateSettingValue(schema[key], value).ok) {
      return invalid(key, value, schema[key].oneOf);
    }
    castOpts[key] = value;
  }
  const method = castOpts.castMethod || 'zheng';
  if (NEEDS_ZHI.indexOf(method) >= 0) {
    const zhi = pick('xuanShiZhi');
    if (LRConst.ZiList.indexOf(zhi) < 0) {
      return invalid('xuanShiZhi', zhi, LRConst.ZiList, '起课法「选时·事发之时」需要 xuanShiZhi（事发之时地支，子…亥）。');
    }
    castOpts.xuanShiZhi = zhi;
  }
  if (NEEDS_NUM.indexOf(method) >= 0) {
    const num = pick('yanShuNum');
    if (!/^-?\d+$/.test(`${num === undefined ? '' : num}`.trim())) {
      return invalid('yanShuNum', num, ['整数'], `起课法「${method === 'baoshu' ? '报数/端法' : '演数'}」需要 yanShuNum（整数）。`);
    }
    castOpts.yanShuNum = `${num}`.trim();
  }
  const guirengRaw = pick('guirengType');
  const guirengType = guirengRaw === undefined ? schema.guireng.def : Number(guirengRaw);
  if (!validateSettingValue(schema.guireng, guirengType).ok) {
    return invalid('guirengType', guirengRaw, schema.guireng.oneOf);
  }
  const wuxing = pick('wuxing');
  if (wuxing !== undefined && WUXING.indexOf(wuxing) < 0) {
    return invalid('wuxing', wuxing, WUXING);
  }
  for (const key of Object.keys(opts)) {
    if (CAST_KEYS.indexOf(key) < 0 && INPUT_KEYS.indexOf(key) < 0 && key !== 'guirengType' && key !== 'zhanCategory') {
      return invalid(key, opts[key], [...CAST_KEYS, ...INPUT_KEYS, 'guirengType', 'zhanCategory'], `大六壬 options 含未知键「${key}」（可用键：${[...CAST_KEYS, ...INPUT_KEYS, 'guirengType', 'zhanCategory'].join(' / ')}）。`);
    }
  }
  return { ok: true, castOpts, guirengType, wuxing };
}

function parseYearAd(dateText, adValue) {
  const m = `${dateText || ''}`.trim().match(/^(-?\d{1,6})-\d{1,2}-\d{1,2}/);
  if (!m) return null;
  const raw = parseInt(m[1], 10);
  const ad = Number(adValue) === -1 || raw < 0 ? -1 : 1;
  return { year: Math.abs(raw), ad };
}

function genderValue(value) {
  if (value === true || value === 1 || value === '1' || value === '男') return 1;
  if (value === false || value === 0 || value === '0' || value === '女') return 0;
  return undefined;
}

// skill 扩展（上游无此入口：LiuRengMain.js 里 `params.yue = yue` 早已注释掉）：显式 yue = 月将，替代星历月将；
// 起课法照常作用于它（X/Y 同 computeQiXY），其余覆盖口径（分昼夜 / 涉害 / 阴阳系）沿用 castOverride。
function applyExplicitYue(chartObj, castOpts, castOverride, explicitYue) {
  const castMethod = castOpts.castMethod || 'zheng';
  const xy = computeQiXY(castMethod, chartObj, explicitYue, castOpts);
  const tFallback = chartObj.nongli && chartObj.nongli.time ? chartObj.nongli.time.substr(1) : '';
  const base = castOverride || {};
  return {
    yue: LRConst.ZiList.indexOf(xy.X) >= 0 ? xy.X : explicitYue,
    timeZhi: LRConst.ZiList.indexOf(xy.Y) >= 0 ? xy.Y : tFallback,
    isDiurnal: base.isDiurnal,
    actualYue: explicitYue,
    seHaiOpts: base.seHaiOpts || {
      method: castOpts.seHaiMethod || 'app',
      boundary: castOpts.seHaiBoundary || 'app',
      shiRuKe: !!castOpts.shiRuKe,
    },
    yinyangSystem: base.yinyangSystem || (castOpts.yinyangSystem === 'yinyang' ? 'yinyang' : 'danmu'),
  };
}

export function runLiureng(payload) {
  const resolved = resolveLiurengOptions(payload);
  if (!resolved.ok) {
    return { data: { ok: false, error: resolved.error }, snapshot_text: '' };
  }
  const { castOpts, guirengType } = resolved;
  const liureng = payload.liureng || {};
  const runyear = payload.runyear || null;
  const chartObj = normalizeChart(payload);
  // 起课时刻（行年盘 = guaDate/guaTime；正盘 = date/time）：月将换将的岁差年与快照 [起盘信息] 的「日期」行都按它取。
  const keDate = payload.guaDate || payload.date || '';
  const keTime = `${payload.guaTime || payload.time || ''}`.slice(0, 5);
  const keYear = parseYearAd(keDate, payload.guaAd ?? payload.ad);
  const solarYear = keYear ? getSolarYearFromField({ value: keYear }) : NaN;
  // 本命支 / 行年支（第九~十二客、本命 / 行年加时）：上游 liurengBenmingXingnian 按问测人出生公历年 + 行年干支取。
  // 正盘无单独出生档时同上游缺省「问测人 = 起课档」取起课年（buildBirthFields(this.props.fields)）。
  const birthYear = parseYearAd(payload.date, payload.ad);
  const bx = liurengBenmingXingnian(birthYear ? { date: { value: birthYear } } : null, runyear);
  const fullCastOpts = {
    ...castOpts,
    ...(Number.isFinite(solarYear) ? { solarYear } : {}),
    benmingZhi: bx.benmingZhi,
    xingnianZhi: bx.xingnianZhi,
    zhanCategory: payload.zhanCategory || (payload.options && payload.options.zhanCategory) || undefined,
  };
  // 调用方已算好的 castOverride（三式合一六壬层同款 P0 入口，上游 buildLiuRengSnapshotText 第 8 参）直接用。
  let castOverride = payload.castOverride && typeof payload.castOverride === 'object'
    ? payload.castOverride
    : buildLiuRengCastOverride(chartObj, fullCastOpts);
  const explicitYue = branchOf(payload.yue);
  if (explicitYue && chartObj.nongli) {
    castOverride = applyExplicitYue(chartObj, fullCastOpts, castOverride, explicitYue);
  }
  const layout = buildLiuRengLayout(chartObj, guirengType, castOverride);
  const ke = buildKeData(layout, chartObj);
  const sanChuan = buildSanChuanData(layout, ke.raw, chartObj, castOverride);
  // 十二长生五行：上游缺省 = 日干五行（LiuRengMain 起课回包按日干重置，wuxingUserSet 才保留手选）。
  const dayGan = stemOf(chartObj.nongli && chartObj.nongli.dayGanZi);
  const wuxing = resolved.wuxing || LRConst.GanZiWuXing[dayGan] || '';
  const params = {
    date: keDate,
    time: keTime,
    zone: payload.guaZone || payload.zone || '',
    lon: payload.guaLon || payload.lon || '',
    lat: payload.guaLat || payload.lat || '',
  };
  const snapshot_text = buildLiuRengSnapshotText(
    params,
    liureng,
    runyear,
    chartObj,
    guirengType,
    wuxing,
    genderValue(payload.gender),
    { ...fullCastOpts, castOverride: castOverride || undefined },
  );
  const data = {
    layout: layout ? { ...layout, guirengType, guirengLabel: GUIREN_LABELS[guirengType] || '' } : null,
    ke,
    sanChuan,
    panStyleName: layout ? `${layout.yue}将加${layout.timezi}时` : '',
    castOptions: fullCastOpts,
    castOverride: castOverride || null,
    zhangshengElem: wuxing,
    runtime_note: 'local_headless_liureng',
  };
  return { data, snapshot_text };
}
