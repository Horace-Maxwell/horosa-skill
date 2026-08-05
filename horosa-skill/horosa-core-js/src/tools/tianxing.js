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
