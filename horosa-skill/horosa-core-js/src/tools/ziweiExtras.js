import { ZWEngineOptions } from '../vendor/ziwei/ziweiOptions.js';
import {
  buildZiweiPeriodOverviewLines,
  buildZiweiPeriodLines,
  buildZiweiOverlayLines,
} from '../vendor/ziwei/ziweiSnapshotLayers.js';

/**
 * 紫微三段：[运限概览]（无条件）、[运限]（指定时段）与 [流派叠层]（流派开关叠加层）。
 *
 * 三个 builder 全部来自 vendored `vendor/ziwei/ziweiSnapshotLayers.js`（自上游 ZiWeiMain.js 逐字抽出、
 * manifest `derived_sha256` 看守 —— 此前这里是无人看守的手抄件，上游 v3.11.0 给 [运限] 加的
 * 沈氏三限行与新增的 [运限概览] 段就这么漏了一版）。段序同上游 buildZiWeiSnapshotText：
 * 运限概览 → 运限 → 流派叠层。
 *
 * [运限概览] 上游是无条件段（ZiWeiMain.js:597-599）：有大限就出。[运限] 与 [流派叠层] 上游由界面状态驱动
 * —— 前者是用户勾选的大限/流年/流月/流日/流时组合（`body.length === 0` 就整段不产），后者读可变单例
 * `ZWEngineOptions` 的一组流派开关。headless 没有界面，故把同一份选择开成显式入参：
 *   period  = { daxian:[…], liunian:[…], liuyue:[…], liuri:[…], liushi:[…] }
 *   schools = { childLimit, zhongxian, huoPan, qishuWei, borrowPalace, taiSuiRuGua, taiSuiRelatives:[…] }
 *
 * `ZWEngineOptions` 是**可变单例**，且 [运限] 与 [流派叠层] **都**读它（沈氏三限 zhongxian 在 [运限] 的
 * 大限段里出行）—— 所以流派开关必须在三段求值**之前**覆盖、之后还原（此前只包住了 [流派叠层]，
 * 于是 schools.zhongxian 对 [运限] 永远不生效）。
 *
 * payload: { chart: <ziwei/birth 响应的 chart>, period?: {…}, schools?: {…} }
 * return : { text, errors: [{ section, message }] } —— 单段失败不带崩其余段，但失败必须回报（不静默）。
 */
const _OVERLAY_KEYS = ['childLimit', 'zhongxian', 'huoPan', 'qishuWei', 'borrowPalace', 'taiSuiRuGua', 'taiSuiRelatives'];

export function runZiweiExtras(payload) {
  const source = payload && typeof payload === 'object' ? payload : {};
  const chart = source.chart && typeof source.chart === 'object' ? source.chart : null;
  if (!chart) {
    return { text: '', errors: [] };
  }
  const blocks = [];
  const errors = [];
  const run = (section, build) => {
    try {
      const lines = build() || [];
      const body = lines.filter((l) => l !== '');
      if (body.length) {
        blocks.push(body.join('\n'));
      }
    } catch (error) {
      errors.push({ section, message: `${(error && error.message) || error}` });
    }
  };

  const schools = source.schools && typeof source.schools === 'object' ? source.schools : null;
  const saved = {};
  _OVERLAY_KEYS.forEach((k) => { saved[k] = ZWEngineOptions[k]; });
  try {
    if (schools) {
      _OVERLAY_KEYS.forEach((k) => {
        if (schools[k] !== undefined) { ZWEngineOptions[k] = schools[k]; }
      });
    }
    run('运限概览', () => buildZiweiPeriodOverviewLines(chart));
    if (source.period && typeof source.period === 'object') {
      run('运限', () => buildZiweiPeriodLines(chart, source.period));
    }
    // 上游无条件调用（开关全关时返回 []）；headless 缺省开关全关 → 与上游同为零输出。
    run('流派叠层', () => buildZiweiOverlayLines(chart));
  } finally {
    // 可变单例 —— 逐次覆盖后**必须还原**，否则同进程内下一次调用会串味。
    _OVERLAY_KEYS.forEach((k) => { ZWEngineOptions[k] = saved[k]; });
  }

  return { text: blocks.join('\n\n'), errors };
}

export default runZiweiExtras;
