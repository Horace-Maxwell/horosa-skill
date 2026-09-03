// 八字 [大运/流年明细] 本地补算：birth 路径的后端响应不含 direction，
// 此处用 vendored 本地引擎按出生资料补算 direction/mainDirection/smallDirection
// 合并回响应（Java runtime 只作外部盘面，三推运由本地 buildBaziCore 无条件产出）。
// 任一步失败回空（不连累既有 bazi 段），与 baziGeju.js 降级策略一致。
import { buildLocalBaziResult } from '../vendor/bazi/baziLunarLocal.js';

export function runBaziLocal(payload) {
  const core = buildLocalBaziResult(payload || {});
  const b = core && core.bazi ? core.bazi : {};
  return {
    direction: Array.isArray(b.direction) ? b.direction.slice() : [],
    mainDirection: Array.isArray(b.mainDirection) ? b.mainDirection.slice() : [],
    smallDirection: Array.isArray(b.smallDirection) ? b.smallDirection.slice() : [],
    directTime: b.directTime ?? null,
    directInfo: b.directInfo ?? null,
    gender: b.gender ?? null,
    source: core.local ? 'lunar-local' : null,
  };
}