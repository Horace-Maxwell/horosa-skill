import {
  buildBabylonSnapshotText,
  chartToLons,
  digestBabylonEphemeris,
} from '../vendor/utils/babylonAiSnapshot.js';
import { buildHoroscope } from '../vendor/babylon/horoscope.js';
import { BABYLON_SCHEMES } from '../vendor/babylon/babylonSchools.js';
import { julianDayIndex } from '../vendor/utils/julianDayIndex.js';

/**
 * 巴比伦占星六段（起盘信息 / 七曜按宫 / 分至天狼星 / 位三法 / 行星神性 / 微黄道）。
 *
 * 上游的编排函数 `buildBabylonSnapshotForFields` 自己发两个请求（/chart 与
 * /astroextra/ephemeris），headless 侧按 AGENTS §5 由 Python 发请求、JS 只做纯计算与排版，
 * 所以 re-vendor 时那支连同 fetch 助手一起被剥掉。这里重建同一条链，数据从 payload 进来：
 *
 *   chartToLons(chart) → buildHoroscope(lons, jdn, opts) → buildBabylonSnapshotText(bab, opts)
 *
 * 上游 `babylonBirthJdn` 走的是 moment 对象（`d.getOnlyDateNum()` / `d.year()`），headless 无
 * moment，故由 Python 传拆分后的年月日，这里用同一个 `julianDayIndex` 换算——与上游那条
 * `julianDayIndex(signedYear, month, day)` 分支逐字同算。
 *
 * payload: {
 *   chart: <后端 /chart 响应（恒星黄道 · 毕宿锚）>,
 *   year, month, day,            // 公历；year 为负表示公元前（同上游 ad<0 的 signedYear）
 *   ephemeris?: <后端 /astroextra/ephemeris 响应>,   // 缺省则 [分至天狼星] 段内两行实算自动省略
 *   scheme?, solstice?, era?, schemeCn?               // 派系口径，透传给上游 opts
 * }
 * return : { text }
 */
export function runBabylon(payload) {
  const source = payload && typeof payload === 'object' ? payload : {};
  const year = Number(source.year);
  const month = Number(source.month);
  const day = Number(source.day);
  if (!Number.isFinite(year) || !Number.isFinite(month) || !Number.isFinite(day)) {
    return { text: '' };
  }
  const jdn = julianDayIndex(year, month, day);
  if (!Number.isFinite(jdn)) {
    return { text: '' };
  }
  const lons = chartToLons(source.chart && typeof source.chart === 'object' ? source.chart : null);
  // 🔴 流派档必须**解析成参数**，不能只当标签传：judge 层的 dodecaVariant/cubitDeg 决定
  // 十二分变体（horoscope.js:43 与快照 :167）与肘度换算（units.js:80），此前一个都没传 ——
  // 于是无论选哪一档，十二分恒 B、肘度恒默认，而 [起盘信息] 行照常打出所选档名。
  // 同时 `era` 与 `scheme` 本身在整棵 vendored 树里无人消费（scheme 只用于查表，era 只是
  // 档内的元数据），所以不再原样下发。派系显示名由档派生，不再要求调用方自带 schemeCn。
  const preset = BABYLON_SCHEMES[`${source.scheme || ''}`] || null;
  const opts = {
    solstice: source.solstice || (preset && preset.backend ? preset.backend.solstice : undefined),
    schemeCn: source.schemeCn || (preset ? preset.cn : undefined),
    ...(preset && preset.judge ? preset.judge : {}),
    // 显式覆写压过档默认（与 horary/election 同一层级语义）。
    ...(source.dodecaVariant ? { dodecaVariant: source.dodecaVariant } : {}),
    ...(source.cubitDeg ? { cubitDeg: source.cubitDeg } : {}),
  };
  const bab = buildHoroscope(lons, jdn, opts);
  if (!bab) {
    return { text: '' };
  }
  // 实算历象（朔望 / 邻近食）与页面同源；取不到就整体省略那两行，图式行照常——同上游的降级口径。
  // NA/KUR 两行上游要再发一轮 rise/set 请求（computeNaKur），headless 侧不做，故不产该两行。
  const ephemDigest = source.ephemeris ? digestBabylonEphemeris(source.ephemeris, jdn) : null;
  const text = buildBabylonSnapshotText(bab, { ...opts, ephemDigest }) || '';
  return { text };
}

export default runBabylon;
