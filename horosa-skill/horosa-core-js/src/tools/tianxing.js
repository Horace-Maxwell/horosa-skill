// tianxing 天星择日·征象搜索: compile the condition tree and format the AI snapshot.
//
// The *search* itself is NOT here — it is `POST /electionscan/scan` on the Python chart service, and per
// AGENTS §5 ("请求型 builder 一律归 Python") the month-splitting orchestration lives in service.py. This
// module is the branch-3 half: a verbatim-vendored pure formatter whose 段头 must stay byte-identical to
// 星阙, plus the vendored condition-tree compiler so validation messages come from the same table the
// backend uses instead of a re-encoded copy that goes stale.
import { compileTree } from '../vendor/divination/zeri/conditionTypes.js';
import { buildTianxingSnapshot } from '../vendor/divination/zeri/tianxingSnapshot.js';
import { splitByMonth, stitchIntervals } from '../vendor/divination/zeri/intervalOps.js';
import { conditionSummaryText } from '../vendor/divination/zeri/conditionGlyph.js';

// ── [单时判读]（/electionscan/explain 的文本化）────────────────────────────────
// 语汇与配对规则逐字取自上游 ConditionBuilderModal.js:139-181（renderExplainNode）：
//   组行 = GATE_CN2[op] + ✓/✗；叶 = 「设定 <conditionSummary>」+「实际 <actual> ✓/✗」；
//   设定文本按 UI 树叶 DFS 序与 explain 树（编译形）先序配对 —— compile 不增删叶，先序一致。
// 差异仅在呈现介质：文本导出用 conditionSummaryText（glyph 回退 title），缩进代替嵌套边框。
const GATE_CN2 = { all: '且(全部满足)', any: '或(任一满足)', xor: '异或(奇数满足)', not: '非(取反)' };

function collectUiLeaves(node, out) {
  if (!node) { return out; }
  // 上游 modal 树的叶带 kind:'leaf'；skill schema 的叶是裸 {type, params}（无 kind）。两形都收：
  // 组的判据 = kind:'group' 或带 children —— 与 compileTree 对组的判定同宽。
  const isGroup = node.kind === 'group' || Array.isArray(node.children);
  if (!isGroup) { out.push(node); return out; }
  (node.children || []).forEach((c) => collectUiLeaves(c, out));
  return out;
}

function explainNodeLines(node, uiLeaves, counter, depth, lines) {
  if (!node || typeof node !== 'object') { return; }
  const pad = '  '.repeat(depth);
  const mark = node.pass ? '✓' : '✗';
  if (node.kind === 'group') {
    lines.push(`${pad}${GATE_CN2[node.op] || node.op} ${mark}`);
    (node.children || []).forEach((c) => explainNodeLines(c, uiLeaves, counter, depth + 1, lines));
    return;
  }
  const ui = uiLeaves[counter.i];
  counter.i += 1;
  let setting = '';
  try {
    setting = ui ? conditionSummaryText(ui) : '';
  } catch (error) {
    setting = '';
  }
  if (!setting) { setting = `${node.type || '条件'}`; }
  const negate = ui && ui.negate ? '(取反)' : '';
  lines.push(`${pad}设定 ${setting}${negate}`);
  lines.push(`${pad}实际 ${node.actual === undefined || node.actual === null ? '—' : node.actual} ${mark}`);
}

export function runTianxing(payload) {
  const input = payload && typeof payload === 'object' ? payload : {};
  const action = `${input.action || 'snapshot'}`;

  if (action === 'compile') {
    try {
      return { tool: 'tianxing', action, data: { ok: true, compiled: compileTree(input.tree || null) }, snapshot_text: '' };
    } catch (error) {
      return {
        tool: 'tianxing',
        action,
        data: { ok: false, error: { code: 'invalid_conditions', message: `${(error && error.message) || error}` } },
        snapshot_text: '',
      };
    }
  }

  if (action === 'split') {
    // Exposed so Python drives the same month-splitting the UI uses (the backend caps one request at
    // 93 days). Returned as plain segments; Python owns the HTTP loop.
    const cfg = input.cfg && typeof input.cfg === 'object' ? input.cfg : {};
    return {
      tool: 'tianxing',
      action,
      data: { ok: true, segments: splitByMonth(cfg.startDate, cfg.startTime, cfg.endDate, cfg.endTime) },
      snapshot_text: '',
    };
  }

  if (action === 'stitch') {
    return {
      tool: 'tianxing',
      action,
      data: { ok: true, intervals: stitchIntervals(Array.isArray(input.lists) ? input.lists : []) },
      snapshot_text: '',
    };
  }

  if (action === 'explain_section') {
    // input: { t, tree(UI 树), explain(/electionscan/explain 返回的判读树) } → [单时判读] 段文本。
    const explain = input.explain && typeof input.explain === 'object' ? input.explain : null;
    if (!explain) {
      return {
        tool: 'tianxing',
        action,
        data: { ok: false, error: { code: 'missing_explain_tree', message: '缺少判读树（explain）。' } },
        snapshot_text: '',
      };
    }
    const lines = [`判读时刻：${input.t || ''}`];
    explainNodeLines(explain, collectUiLeaves(input.tree || null, []), { i: 0 }, 0, lines);
    return { tool: 'tianxing', action, data: { ok: true }, snapshot_text: `[单时判读]\n${lines.join('\n')}` };
  }

  // --- snapshot ---
  const ctx = input.ctx && typeof input.ctx === 'object' ? input.ctx : {};
  let snapshot_text = '';
  try {
    snapshot_text = buildTianxingSnapshot(input.chart || null, input.fields || null, input.extra || null, ctx) || '';
  } catch (error) {
    return {
      tool: 'tianxing',
      action: 'snapshot',
      data: { ok: false, error: { code: 'snapshot_failed', message: `${(error && error.message) || error}` } },
      snapshot_text: '',
    };
  }
  return { tool: 'tianxing', action: 'snapshot', data: { ok: !!snapshot_text }, snapshot_text };
}
