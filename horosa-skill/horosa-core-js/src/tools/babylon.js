import {
  buildBabylonSnapshotText,
  chartToLons,
  digestBabylonEphemeris,
} from '../vendor/utils/babylonAiSnapshot.js';
import { buildHoroscope } from '../vendor/babylon/horoscope.js';
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
  const opts = {
    scheme: source.scheme,
    solstice: source.solstice,
    era: source.era,
    schemeCn: source.schemeCn,
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
