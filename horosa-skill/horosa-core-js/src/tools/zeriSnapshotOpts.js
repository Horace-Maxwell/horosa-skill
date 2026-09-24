// 择日十宿主 + 天星 AI 快照「命中清单」的共用小件（上游 [Q-452 裁决 A / Q-453 裁决 2026-09-18]）。
//
// ① 两旋钮归一：清单上限 maxRows（缺省 60，10–500）、前 N 行附判读树 explainRows（缺省 3，0–20，0=不附），
//    一律用 vendored 上游 utils/zeriSnapshotPrefs.js 的 normalize*。显式归一后再交 builder —— builder 见
//    undefined 会去读 globalSetup(localStorage)，Node 下那是实验性全局；读不到只是回缺省，但「缺省从哪来」
//    不该取决于运行时有没有 localStorage。
// ② UI 树叶补 kind：上游工作台 UI 树的叶恒带 kind:'leaf'；skill schema 容许裸叶 {type, params}（compile 与
//    各段渲染都按「非组即叶」处理，照样工作）。唯独 zeriExplainText.collectZeriUiLeaves 只认
//    kind==='leaf' —— 裸叶会让判读行的「设定」退化成条件类键名。补 kind 只影响这一处配对。
// ③ 后端扫描家族（天星/七政/印度）的判读是服务端的：Python 按上游 prefetchSnapshotExplains 预取前 N 行，
//    按行序交来；这里装成 builder 要的 explainAt(row, i)。
import { normalizeZeriSnapshotMaxRows, normalizeZeriSnapshotExplainRows } from '../vendor/utils/zeriSnapshotPrefs.js';

export function zeriRowOpts(input) {
  const o = input && typeof input === 'object' ? input : {};
  return {
    maxRows: normalizeZeriSnapshotMaxRows(o.maxRows),
    explainRows: normalizeZeriSnapshotExplainRows(o.explainRows),
  };
}

export function withLeafKind(node) {
  if (!node || typeof node !== 'object') {
    return node;
  }
  if (node.kind === 'group' || Array.isArray(node.children)) {
    return { ...node, children: (node.children || []).map(withLeafKind) };
  }
  return node.kind ? node : { ...node, kind: 'leaf' };
}

export function explainAtFromList(list) {
  if (!Array.isArray(list)) {
    return undefined;
  }
  return (row, i) => (list[i] && typeof list[i] === 'object' ? list[i] : null);
}
