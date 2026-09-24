import { buildLocalBaziResult } from '../vendor/bazi/baziLunarLocal.js';
import { buildBaziSnapshotText, normalizeBaziResult } from '../vendor/bazi/baziSnapshot.js';

/**
 * 八字（bazi_birth / bazi_direct）本地优先起盘 + 上游整份快照。
 *
 * 上游页面主路径 = BaZi.js:716-755 fetchBaziCached（bazi_direct 同形 fetchBaziDirectCached :757-795）：
 * `buildLocalBaziResult(params)` 成功即用；**抛错**（lunar-javascript 不可靠域：公元前 / 万年后 / 不可解析日期）才回退
 * Java /bazi/birth（/bazi/direct）。两条路都经 normalizeBaziResult → buildBaziSnapshotText（BaZi.js:1000-1046）。
 * JS 层不发 HTTP（AGENTS §4），所以回退由 Python 做：本地抛错时本工具回
 * `data: {ok:false, reason:'local_engine_unavailable'}`，Python 调 Java 后把响应作 `java_result` 再交回本工具出快照。
 *
 * payload: {
 *   params:   genParams 形状（BaZi.js:961-985；缺省值由 Python 按上游补齐），
 *   snapshot: { school?, ageStyle?, zodiacBoundary?, period? }  —— 只进快照（BaZi.js:1029 snapshotParams / 挂载 period），
 *   java_result?: Java /bazi/* 响应（回退路径）
 * }
 * return : { data: { ok, local, bazi?, gender?, reason?, message? }, snapshot_text }
 */
export function runBaziLocal(payload) {
  const source = payload && typeof payload === 'object' ? payload : {};
  const params = source.params && typeof source.params === 'object' ? source.params : {};
  const extra = source.snapshot && typeof source.snapshot === 'object' ? source.snapshot : {};
  let raw = source.java_result && typeof source.java_result === 'object' ? source.java_result : null;
  const fromJava = !!raw;
  if (!raw) {
    try {
      raw = buildLocalBaziResult(params);
    } catch (error) {
      return {
        snapshot_text: '',
        data: { ok: false, reason: 'local_engine_unavailable', message: `${(error && error.message) || error}` },
      };
    }
  }
  const result = normalizeBaziResult(raw, params);
  if (!result || !result.bazi) {
    return { snapshot_text: '', data: { ok: false, reason: 'empty_result', message: '八字结果为空' } };
  }
  // BaZi.js:1029 snapshotParams = { ...params, school, shenshaGroups, ageStyle, zodiacBoundary }（+ 挂载 period）
  const snapshotParams = { ...params };
  ['school', 'ageStyle', 'zodiacBoundary', 'period'].forEach((key) => {
    if (extra[key] !== undefined && extra[key] !== null && extra[key] !== '') {
      snapshotParams[key] = extra[key];
    }
  });
  const text = buildBaziSnapshotText(snapshotParams, result) || '';
  return {
    snapshot_text: text,
    data: { ok: true, local: !fromJava && !!result.local, bazi: result.bazi, gender: result.gender || result.bazi.gender },
  };
}

export default runBaziLocal;
