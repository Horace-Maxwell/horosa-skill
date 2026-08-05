// qimenzeri 奇门择日「找局」: scan a time window for 时辰 matching a 奇门 condition tree, then emit the
// three extra AI-export sections that get appended after the 17-section 奇门 snapshot.
//
// Zero HTTP by design — the vendored qimenScanEngine排盘s locally via `calcDunJia`. See AGENTS §4 on the
// compute split: the *displayed* pan is still cast by the ken backend (`/qimen/pan` + `_require_ken_pan`
// on the Python side), only the interval **search** runs locally. ken exposes no range-scan endpoint, and
// a one-month window is ~44k single-moment round-trips; upstream anchors the local排盘 against the backend
// on a 42,731-point 0-diff parity grid (qimenScanEngine.js header), and this repo's own qimen tool already
// computes `calcDunJia` on every call before overlaying ken onto it.
import { scanQimen, QIMEN_MAX_TOTAL_HITS, QIMEN_MAX_SPAN_DAYS_TOTAL } from '../vendor/divination/zeri/qimenScanEngine.js';
import { compileQimenTree } from '../vendor/divination/zeri/qimenConditionTypes.js';
import { buildQimenZeriSnapshotExtra } from '../vendor/divination/zeri/qimenZeriSnapshot.js';

export async function runQimenZeri(payload) {
  const input = payload && typeof payload === 'object' ? payload : {};
  const action = `${input.action || 'scan'}`;
  const cfg = input.cfg && typeof input.cfg === 'object' ? input.cfg : {};
  const geo = input.geo && typeof input.geo === 'object' ? input.geo : {};
  const options = input.options && typeof input.options === 'object' ? input.options : {};
  const tree = input.tree && typeof input.tree === 'object' ? input.tree : null;

  if (action === 'snapshot') {
    // Verbatim upstream builder — the three 段头 are 🔒 four-sync-locked against aiExport.js.
    const snapshot_text = buildQimenZeriSnapshotExtra({
      cfg,
      geo,
      options,
      tree,
      results: input.results || null,
      truncated: !!input.truncated,
    }) || '';
    return { tool: 'qimenzeri', action, data: { ok: !!snapshot_text }, snapshot_text };
  }

  // --- scan ---
  if (!tree) {
    return {
      tool: 'qimenzeri',
      action: 'scan',
      data: { ok: false, error: { code: 'missing_conditions', message: '未提供择日条件树（conditions）。' } },
      snapshot_text: '',
    };
  }
  let compiled = null;
  try {
    // Each leaf's own `validate` runs here and throws a localized 「<label>」条件：<msg>. Letting the
    // vendored table validate keeps the skill from re-encoding 30+ condition schemas that go stale.
    compiled = compileQimenTree(tree);
  } catch (error) {
    return {
      tool: 'qimenzeri',
      action: 'scan',
      data: { ok: false, error: { code: 'invalid_conditions', message: `${(error && error.message) || error}` } },
      snapshot_text: '',
    };
  }

  try {
    const limits = input.limits && typeof input.limits === 'object' ? input.limits : undefined;
    // ⚠ Two tree shapes, and they are not interchangeable:
    //   UI tree       {kind:'group', joiner:'all', children:[…]}  → what the snapshot builder renders
    //   compiled tree {type:'all',   conditions:[…]}              → what evaluateQimenTree walks
    // scanQimen hands `tree` straight to evaluateQimenTree, so it must get the COMPILED one. Passing
    // the UI tree "works" — it silently matches nothing and reports a plausible zero-hit search.
    const result = await scanQimen({ cfg, geoParams: geo, options, tree: compiled, limits });
    const intervals = (result && result.intervals) || [];
    return {
      tool: 'qimenzeri',
      action: 'scan',
      data: {
        ok: true,
        intervals,
        truncated: !!(result && result.truncated),
        stats: (result && result.stats) || null,
        hit_count: intervals.length,
        compiled_tree: compiled,
        limits: { max_hits: QIMEN_MAX_TOTAL_HITS, max_span_days: QIMEN_MAX_SPAN_DAYS_TOTAL },
      },
      snapshot_text: '',
    };
  } catch (error) {
    // Never degrade a range/validation failure into "zero hits" — that reads as a valid empty result.
    return {
      tool: 'qimenzeri',
      action: 'scan',
      data: {
        ok: false,
        error: { code: `${(error && error.code) || 'scan_failed'}`, message: `${(error && error.message) || error}` },
      },
      snapshot_text: '',
    };
  }
}
