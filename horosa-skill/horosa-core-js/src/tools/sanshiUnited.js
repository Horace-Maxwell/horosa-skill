// 三式合一 headless 工具 —— 快照正文逐字交给 vendored 上游 buildSanShiUnitedSnapshotText
// （vendor/sanshi/SanShiUnitedMain.js，上游 components/sanshi/SanShiUnitedMain.js:1424），
// 入参按上游 performRecalcByNongli（:3677-3876）同链装配：六壬层由三式农历 + 奇门盘干支（buildLrNongli）
// + 星盘（chartObj）经同文件的 buildLiuRengLayout / buildKeData / buildSanChuan 起课，断卦层与参考包复用 vendored
// LiuRengMain 的同名函数，外圈按 buildOuterData。
//
// 分工（AGENTS §4「请求型 builder 归 Python，JS 层不发 HTTP」）：Python 取三式农历（上游 genParams →
// fetchPreciseNongli）、真太阳时显示值（resolveDisplaySolarTime）、星盘（props.chartObj）、奇门盘（getKinqimenDunJia，
// 经 qimen 工具）、太乙盘（getKintaiyiPan，经 taiyi 工具）与可选紫微盘，这里只做上游组件里「拿到这些之后」的纯计算。
//
// v3.11.x 同步之前 skill 在 service.py 里用三个子工具导出的段自己拼三式快照：[大六壬] 只有六壬的 [四课] 体（缺三传 /
// 递生递克 / 空禄马徽记），【】段头写成 []，段序也不同；六壬层还另起一张 /liureng/gods 盘（真太阳时农历），占时不随三式农历。
import {
  SANSHI_PAGE_SETTINGS,
  buildSanshiLiuRengCastOverride,
  buildLrNongli,
  buildLiuRengLayout,
  buildKeData,
  buildSanChuan,
  pickSanshiLiurengCastOpts,
  buildOuterData,
  buildSanShiUnitedSnapshotText,
  safe,
} from '../vendor/sanshi/SanShiUnitedMain.js';
import { buildLiuRengReferenceBundle, buildLiuRengSnapshotText } from '../vendor/liureng/LiuRengMain.js';
import { validateSettingValue } from '../vendor/utils/pageSettingsStore.js';
import * as LRConst from '../vendor/liureng/LRConst.js';
import { makeFields } from '../shared/fields.js';

// 六壬层口径键 = 上游 SANSHI_PAGE_SETTINGS 的六壬层 + 贵人（:412 / :453-460）。词表锚到 vendored schema，不手抄。
// skill 历来用 liureng_gods 的键名 guirengType 表示贵人（上游三式键名 guireng），两名都认。
const LR_LAYER_KEYS = ['yueJiangMethod', 'fenZhouYe', 'seHaiMethod', 'seHaiBoundary', 'shiRuKe',
  'yearShenShaSort', 'yinyangSystem', 'tuWangShuai'];
// zhanCategory：上游 pickSanshiLiurengCastOpts 透传给断卦层（[占断向导]），不在页面 schema 里（占类由调用处给）。
const PASS_KEYS = ['zhanCategory'];

function invalid(field, value, allowed, message) {
  return {
    ok: false,
    error: {
      code: 'invalid_option',
      field,
      value,
      allowed,
      message: message || `三式合一 ${field} 取值无效：${JSON.stringify(value)}（可选：${(allowed || []).join(' / ')}）`,
    },
  };
}

function toBool(value) {
  if (value === true || value === 1 || value === '1' || value === 'true') return true;
  if (value === false || value === 0 || value === '0' || value === 'false') return false;
  return undefined;
}

function toInt01(value, fallback) {
  if (value === undefined || value === null || value === '') return fallback;
  if (value === true || value === 1 || value === '1') return 1;
  if (value === false || value === 0 || value === '0') return 0;
  return undefined;
}

// 上游组件 state.options 的出厂值（构造器 :2037-2082）：页面 schema 的缺省 + 构造器独有键（模式 / 性别 / 日界两键）。
// 日界两键 = 全局出厂 23 点换日 / 晚子时用次日（dayBoundary.js defaultAfter23NewDay / defaultLateZiHourUseNextDay）。
function upstreamDefaultOptions() {
  const defs = SANSHI_PAGE_SETTINGS.defaults();
  delete defs.outerCoord;   // 外圈两项是组件 state，不在 options 里（构造器 :2014 摘出）
  delete defs.showWeakSolid;
  return {
    mode: 'shi',
    sex: 1,
    zodiacal: 0,
    siderealAyanamsa: '',
    hsys: 0,
    after23NewDay: 1,
    lateZiHourUseNextDay: 1,
    shiftPalace: 0,
    shuziReportNumber: '',
    fengJu: false,
    ...defs,
  };
}

// 三式 options（上游 mergedOptions）：出厂值 ⊕ 共享时间键 / 性别 ⊕ 六壬层口径。奇门 / 太乙层的口径已由各自工具算进盘里，
// buildSanShiUnitedSnapshotText 只读 options.timeAlg / after23NewDay / sex 与六壬层键。认不出的键 / 值 → 结构化报错。
export function resolveSanshiOptions(input) {
  const src = input && typeof input === 'object' ? input : {};
  const schema = SANSHI_PAGE_SETTINGS.schema;
  const options = upstreamDefaultOptions();
  const timeAlg = toInt01(src.timeAlg, 0);
  if (timeAlg === undefined) return invalid('timeAlg', src.timeAlg, [0, 1]);
  options.timeAlg = timeAlg;
  for (const key of ['after23NewDay', 'lateZiHourUseNextDay']) {
    const v = toInt01(src[key], options[key]);
    if (v === undefined) return invalid(key, src[key], [0, 1]);
    options[key] = v;
  }
  const sex = toInt01(src.sex, 1);
  if (sex === undefined) return invalid('sex', src.sex, [0, 1]);
  options.sex = sex;
  const lr = src.liureng && typeof src.liureng === 'object' ? src.liureng : {};
  const allowedLrKeys = ['guirengType', 'guireng', 'castMethod', ...LR_LAYER_KEYS, ...PASS_KEYS];
  for (const key of Object.keys(lr)) {
    if (allowedLrKeys.indexOf(key) < 0) {
      return invalid(`liureng_options.${key}`, lr[key], allowedLrKeys,
        `三式合一六壬层 liureng_options 含未知键「${key}」（上游 SANSHI_PAGE_SETTINGS 六壬层可用：${allowedLrKeys.join(' / ')}）。`);
    }
  }
  if (lr.castMethod !== undefined && lr.castMethod !== null && lr.castMethod !== '' && lr.castMethod !== 'zheng') {
    return invalid('liureng_options.castMethod', lr.castMethod, ['zheng'],
      '三式合一只支持正时正将起课法（上游 pickSanshiLiurengCastOpts 锁 castMethod:zheng）。');
  }
  const guiRaw = lr.guirengType !== undefined && lr.guirengType !== null && lr.guirengType !== '' ? lr.guirengType : lr.guireng;
  if (guiRaw !== undefined && guiRaw !== null && guiRaw !== '') {
    const gui = Number(guiRaw);
    if (!validateSettingValue(schema.guireng, gui).ok) return invalid('liureng_options.guirengType', guiRaw, schema.guireng.oneOf);
    options.guireng = gui;
  }
  for (const key of LR_LAYER_KEYS) {
    let value = lr[key];
    if (value === undefined || value === null || value === '') continue;
    if (key === 'shiRuKe') {
      value = toBool(value);
      if (value === undefined) return invalid(`liureng_options.${key}`, lr[key], ['true', 'false']);
    } else if (!validateSettingValue(schema[key], value).ok) {
      return invalid(`liureng_options.${key}`, value, schema[key].oneOf);
    }
    options[key] = value;
  }
  if (lr.zhanCategory !== undefined && lr.zhanCategory !== null && lr.zhanCategory !== '') {
    options.zhanCategory = `${lr.zhanCategory}`;
  }
  return { ok: true, options };
}

function branchOf(value) {
  const match = `${value || ''}`.match(/[子丑寅卯辰巳午未申酉戌亥]/);
  return match ? match[0] : '';
}

export function runSanshiUnited(payload) {
  const input = payload && typeof payload === 'object' ? payload : {};
  const resolved = resolveSanshiOptions(input.options);
  if (!resolved.ok) {
    return { tool: 'sanshiunited', data: { ok: false, error: resolved.error }, snapshot_text: '' };
  }
  const options = resolved.options;
  const nongli = input.nongli && typeof input.nongli === 'object' ? input.nongli : null;
  const dunjia = input.dunjia && typeof input.dunjia === 'object' ? input.dunjia : null;
  const taiyi = input.taiyi && typeof input.taiyi === 'object' ? input.taiyi : null;
  const chartWrap = input.chart && typeof input.chart === 'object'
    ? (input.chart.chart ? input.chart : { chart: input.chart })
    : null;
  const astroChart = chartWrap && chartWrap.chart && typeof chartWrap.chart === 'object' ? chartWrap.chart : null;
  const missing = [['nongli', nongli], ['dunjia', dunjia], ['chart', astroChart]].filter(([, v]) => !v).map(([k]) => k);
  if (missing.length) {
    return {
      tool: 'sanshiunited',
      data: { ok: false, error: { code: 'missing_inputs', field: missing.join(','), message: `三式合一缺少起盘输入：${missing.join(' / ')}。` } },
      snapshot_text: '',
    };
  }
  const fields = makeFields(input);
  const warnings = [];
  // skill 扩展（上游无此入口）：liureng_isDiurnal 显式指定六壬层昼夜（贵人昼夜取法读 chartObj.isDiurnal），缺省 = 星盘自带。
  const lrChartBase = input.liurengIsDiurnal === true || input.liurengIsDiurnal === false
    ? { ...astroChart, isDiurnal: input.liurengIsDiurnal }
    : astroChart;
  const guirengType = options.guireng;
  // :3695-3698 大六壬流派覆盖（换将 / 分昼夜 / 涉害 / 阴阳系…）；全缺省 → null（=固定月将，与上游零回归口径一致）。
  let lrCastOverride = buildSanshiLiuRengCastOverride({ ...lrChartBase, nongli }, options);
  // skill 扩展（上游无此入口）：liureng_yue 显式月将。三式锁正时正将，月将即天盘加临之将；其余覆盖口径沿用上面算出的。
  const explicitYue = branchOf(input.liurengYue);
  if (explicitYue) {
    lrCastOverride = {
      isDiurnal: undefined,
      seHaiOpts: { method: options.seHaiMethod || 'app', boundary: options.seHaiBoundary || 'app', shiRuKe: !!options.shiRuKe },
      yinyangSystem: options.yinyangSystem === 'yinyang' ? 'yinyang' : 'danmu',
      yearShenShaSort: options.yearShenShaSort || 'sanyuan',
      tuWangShuai: options.tuWangShuai || 'siji',
      ...(lrCastOverride || {}),
      yue: explicitYue,
    };
  }
  // :3772-3818 六壬层：占日 / 占时取奇门盘干支（buildLrNongli），不另起盘 —— 占时随三式农历（跟 timeAlg）。
  const lrNongli = buildLrNongli(nongli, dunjia);
  const nianMing = safe(lrNongli && lrNongli.runyear, '')
    || ((dunjia && dunjia.ganzhi && dunjia.ganzhi.year) ? dunjia.ganzhi.year.substring(1, 2) : '');
  const chartForLr = { ...lrChartBase, nongli: lrNongli };
  const lrLayout = buildLiuRengLayout(chartForLr, guirengType, lrCastOverride);
  const keData = buildKeData(lrLayout, chartForLr);
  const sanChuan = buildSanChuan(lrLayout, keData.raw, chartForLr, lrCastOverride);
  if (!lrLayout || !sanChuan) {
    // 上游 buildSanChuan 吞掉异常回 null、快照随之整份为空（!sanChuan → ''）。headless 不许静默：点名失败的一环。
    return {
      tool: 'sanshiunited',
      data: {
        ok: false,
        error: {
          code: lrLayout ? 'sanchuan_failed' : 'liureng_layout_failed',
          message: lrLayout
            ? '三式合一六壬层三传起不出（上游 buildSanChuan 吞错回 null）——检查四课与涉害口径。'
            : `三式合一六壬层天地盘起不出（月将「${getChartYueText(chartForLr, lrCastOverride)}」/占时「${safe(lrNongli && lrNongli.time, '')}」）。`,
        },
      },
      snapshot_text: '',
    };
  }
  const liureng = {
    nongli: lrNongli,
    nianMing,
    yue: lrLayout.yue,
    timezi: lrLayout.timezi,
    guizi: lrLayout.guizi,
    fourColumns: {
      year: dunjia.ganzhi ? (dunjia.ganzhi.year || '') : '',
      month: dunjia.ganzhi ? (dunjia.ganzhi.month || '') : '',
      day: dunjia.ganzhi ? (dunjia.ganzhi.day || '') : '',
      time: dunjia.ganzhi ? (dunjia.ganzhi.time || '') : '',
    },
  };
  const runYearRef = lrNongli && lrNongli.runyear ? { year: lrNongli.runyear } : null;
  let liurengRefBundle = null;
  try {
    liurengRefBundle = buildLiuRengReferenceBundle(liureng, chartForLr, guirengType, runYearRef, lrCastOverride);
  } catch (error) {
    // 上游同链吞错置 null（快照照出、[六壬大格]等四段落「无」）；headless 把它报出来。
    liurengRefBundle = null;
    warnings.push(`三式合一六壬参考包构建失败（[六壬大格]/[六壬小局]/[六壬参考]/[六壬概览] 以「无」输出）：${error && error.message ? error.message : error}`);
  }
  const lrCastOpts = pickSanshiLiurengCastOpts(options, lrNongli);
  // 断卦层由 builder 内部调 buildLiuRengSnapshotText 且 try/catch 吞错（失败 = 十三段静默缺席）；先按同参探一次，失败即告警。
  try {
    buildLiuRengSnapshotText(null, liureng, runYearRef, chartForLr, guirengType, '', options.sex,
      { ...(lrCastOpts || {}), castOverride: lrCastOverride || undefined });
  } catch (error) {
    warnings.push(`三式合一六壬断卦层构建失败（十二盘式…七政 等断卦段缺席）：${error && error.message ? error.message : error}`);
  }
  // :3830-3837 外圈：出厂黄道分宫（SANSHI_PAGE_SETTINGS.outerCoord def 'ecliptic'）。
  const outerData = buildOuterData(astroChart, 'ecliptic');
  const ziweiSihua = input.ziweiSihua && typeof input.ziweiSihua === 'object' && input.ziweiSihua.chart
    ? {
      chart: input.ziweiSihua.chart,
      daxianIdx: Number(input.ziweiSihua.daxianIdx) || 0,
      liunianIdx: Number(input.ziweiSihua.liunianIdx) || 0,
    }
    : null;
  // :3838-3857 snapshotPayload 同形。
  const snapshot_text = buildSanShiUnitedSnapshotText({
    fields,
    options,
    nongli,
    displaySolarTime: `${input.displaySolarTime || ''}`,
    liureng,
    dunjia,
    taiyi,
    liurengRefBundle,
    keData,
    sanChuan,
    lrLayout,
    outerData,
    guirengType,
    liurengChartForLr: chartForLr,
    lrCastOverride,
    lrCastOpts,
    liurengRunYear: runYearRef,
    ziweiSihua,
  });
  if (!snapshot_text) {
    return {
      tool: 'sanshiunited',
      data: { ok: false, error: { code: 'empty_snapshot', message: '三式合一快照为空（上游 builder 在缺奇门盘 / 课 / 三传时回空串）。' } },
      snapshot_text: '',
    };
  }
  return {
    tool: 'sanshiunited',
    technique: 'sanshiunited',
    data: {
      ok: true,
      options,
      liureng: {
        ...liureng,
        layout: { ...lrLayout, guirengType },
        ke: keData.raw,
        keText: keData.lines,
        sanChuan,
        panStyle: `${lrLayout.yue}将加${lrLayout.timezi}时`,
        castOverride: lrCastOverride || null,
        castOptions: lrCastOpts,
      },
      warnings,
    },
    snapshot_text,
  };
}

function getChartYueText(chartObj, castOverride) {
  if (castOverride && castOverride.yue) return castOverride.yue;
  const objs = (chartObj && chartObj.objects) || [];
  const sun = objs.find((o) => o && o.id === 'Sun');
  return sun ? (LRConst.getSignZi(sun.sign) || '') : '';
}
