// zeriScan — 上游 v3.10.0「择日十技法」里六个 **本地扫描** 成员的统一入口：
// 黄历择吉 / 八字择时 / 太乙择时 / 紫微择时 / 六壬择时 / 三式合一择时。
//
// 为什么一个文件而不是六个：这六个引擎的 API 是逐字同形的 —— `scanX(args)` /
// `compileXTree(tree)` / `explainXAt({geoParams, options, tree, t})` / `X_MAX_TOTAL_HITS` /
// `X_MAX_SPAN_DAYS_TOTAL` / `buildXZeriSnapshotExtra({cfg, geo, natal, tree, results, truncated})`，
// 因为它们共享同一个 `makeHourlyScanEngine`。复制六份近似代码 = 复制六份同样的坑：
// 尤其是下面那条「编译树 vs UI 树」——qimenzeri 上踩过一次，传错的后果不是报错而是
// **一个看起来合理的零命中结果**。一份实现，一处修好，六个技法同时受益。
//
// 零 HTTP：与 qimenzeri 同一条 AGENTS §4 分工 —— 展示盘仍由 Python 侧走各自后端铸，
// 只有区间**搜索**在本地跑（后端没有范围扫描端点，一个月窗口是数万次单点往返）。
import {
  scanHuangli, explainHuangliAt, HUANGLI_MAX_TOTAL_HITS, HUANGLI_MAX_SPAN_DAYS_TOTAL,
} from '../vendor/divination/zeri/huangliZeriScanEngine.js';
import { compileHuangliTree } from '../vendor/divination/zeri/huangliZeriConditionTypes.js';
import { buildHuangliZeriSnapshotExtra } from '../vendor/divination/zeri/huangliZeriSnapshot.js';

import {
  scanBazi, explainBaziAt, BAZI_MAX_TOTAL_HITS, BAZI_MAX_SPAN_DAYS_TOTAL,
} from '../vendor/divination/zeri/baziZeriScanEngine.js';
import { compileBaziTree } from '../vendor/divination/zeri/baziZeriConditionTypes.js';
import { buildBaziZeriSnapshotExtra } from '../vendor/divination/zeri/baziZeriSnapshot.js';

import {
  scanTaiyi, explainTaiyiAt, TAIYI_MAX_TOTAL_HITS, TAIYI_MAX_SPAN_DAYS_TOTAL,
} from '../vendor/divination/zeri/taiyiZeriScanEngine.js';
import { compileTaiyiTree } from '../vendor/divination/zeri/taiyiZeriConditionTypes.js';
import { buildTaiyiZeriSnapshotExtra } from '../vendor/divination/zeri/taiyiZeriSnapshot.js';

import {
  scanZiwei, explainZiweiAt, ZIWEI_MAX_TOTAL_HITS, ZIWEI_MAX_SPAN_DAYS_TOTAL,
} from '../vendor/divination/zeri/ziweiZeriScanEngine.js';
import { compileZiweiTree } from '../vendor/divination/zeri/ziweiZeriConditionTypes.js';
import { buildZiweiZeriSnapshotExtra } from '../vendor/divination/zeri/ziweiZeriSnapshot.js';

import {
  scanLiureng, explainLiurengAt, LIURENG_MAX_TOTAL_HITS, LIURENG_MAX_SPAN_DAYS_TOTAL,
} from '../vendor/divination/zeri/liurengZeriScanEngine.js';
import { compileLiurengTree } from '../vendor/divination/zeri/liurengZeriConditionTypes.js';
import { buildLiurengZeriSnapshotExtra } from '../vendor/divination/zeri/liurengZeriSnapshot.js';

import {
  scanSanshi, explainSanshiAt, SANSHI_MAX_TOTAL_HITS, SANSHI_MAX_SPAN_DAYS_TOTAL,
} from '../vendor/divination/zeri/sanshiZeriScanEngine.js';
import { compileSanshiTree } from '../vendor/divination/zeri/sanshiZeriConditionTypes.js';
import { buildSanshiZeriSnapshotExtra } from '../vendor/divination/zeri/sanshiZeriSnapshot.js';

// 七政 / 印度择时：判定与区间搜索都在 astropy 后端（swisseph 直连分钟粒度），JS 侧只剩排版。
// 所以它们只有 ConditionTypes（供 compile 校验，与后端求值器同源词表）+ Snapshot，没有 ScanEngine。
import { compileQizhengTree } from '../vendor/divination/zeri/qizhengZeriConditionTypes.js';
import { buildQizhengZeriSnapshotExtra } from '../vendor/divination/zeri/qizhengZeriSnapshot.js';
import { compileIndiaTree } from '../vendor/divination/zeri/indiaZeriConditionTypes.js';
import { buildIndiaZeriSnapshotExtra } from '../vendor/divination/zeri/indiaZeriSnapshot.js';

// 每个技法把它自己的四件套（编译 / 扫描 / 单点判读 / 快照）报到这里。`hourly` 标记区分
// 黄历（日粒度，`scanHuangli({cfg, tree, …})`，不吃 geo/options）与其余五个（时辰粒度，
// 共享 `makeHourlyScanEngine`，吃 `{cfg, geoParams, options, tree, limits}`）。
export const ZERI_TECHNIQUES = {
  huanglizeri: {
    label: '黄历择吉',
    hourly: false,
    compile: compileHuangliTree,
    scan: scanHuangli,
    explainAt: explainHuangliAt,
    snapshot: buildHuangliZeriSnapshotExtra,
    limits: { max_hits: HUANGLI_MAX_TOTAL_HITS, max_span_days: HUANGLI_MAX_SPAN_DAYS_TOTAL },
  },
  bazizeri: {
    label: '八字择时',
    hourly: true,
    compile: compileBaziTree,
    scan: scanBazi,
    explainAt: explainBaziAt,
    snapshot: buildBaziZeriSnapshotExtra,
    limits: { max_hits: BAZI_MAX_TOTAL_HITS, max_span_days: BAZI_MAX_SPAN_DAYS_TOTAL },
  },
  taiyizeri: {
    label: '太乙择时',
    hourly: true,
    compile: compileTaiyiTree,
    scan: scanTaiyi,
    explainAt: explainTaiyiAt,
    snapshot: buildTaiyiZeriSnapshotExtra,
    limits: { max_hits: TAIYI_MAX_TOTAL_HITS, max_span_days: TAIYI_MAX_SPAN_DAYS_TOTAL },
  },
  ziweizeri: {
    label: '紫微择时',
    hourly: true,
    compile: compileZiweiTree,
    scan: scanZiwei,
    explainAt: explainZiweiAt,
    snapshot: buildZiweiZeriSnapshotExtra,
    limits: { max_hits: ZIWEI_MAX_TOTAL_HITS, max_span_days: ZIWEI_MAX_SPAN_DAYS_TOTAL },
  },
  liurengzeri: {
    label: '六壬择时',
    hourly: true,
    compile: compileLiurengTree,
    scan: scanLiureng,
    explainAt: explainLiurengAt,
    snapshot: buildLiurengZeriSnapshotExtra,
    limits: { max_hits: LIURENG_MAX_TOTAL_HITS, max_span_days: LIURENG_MAX_SPAN_DAYS_TOTAL },
  },
  sanshizeri: {
    label: '三式合一择时',
    hourly: true,
    compile: compileSanshiTree,
    scan: scanSanshi,
    explainAt: explainSanshiAt,
    snapshot: buildSanshiZeriSnapshotExtra,
    limits: { max_hits: SANSHI_MAX_TOTAL_HITS, max_span_days: SANSHI_MAX_SPAN_DAYS_TOTAL },
  },
};

// 后端扫描的两个成员：只暴露 compile（本地先校验，错在 skill 侧就报掉，不浪费一次远端往返）
// 与 snapshot（排版）。scan 由 Python 直接打 /qizhengelectionscan|/indiaelectionscan。
export const ZERI_REMOTE_TECHNIQUES = {
  qizhengzeri: { label: '七政择时', compile: compileQizhengTree, snapshot: buildQizhengZeriSnapshotExtra },
  indiazeri: { label: '印度择时（Muhurta）', compile: compileIndiaTree, snapshot: buildIndiaZeriSnapshotExtra },
};

export async function runZeriScanRemote(payload) {
  const input = payload && typeof payload === 'object' ? payload : {};
  const technique = `${input.technique || ''}`;
  const spec = ZERI_REMOTE_TECHNIQUES[technique];
  if (!spec) {
    return fail(technique, `${input.action || 'snapshot'}`, 'unknown_technique',
      `未知后端择日技法 ${technique || '(空)'}；可用：${Object.keys(ZERI_REMOTE_TECHNIQUES).join(' / ')}。`);
  }
  const action = `${input.action || 'snapshot'}`;
  const tree = input.tree && typeof input.tree === 'object' ? input.tree : null;
  if (action === 'compile') {
    if (!tree) { return fail(technique, action, 'missing_conditions', '未提供择时条件树（conditions）。'); }
    try {
      return { tool: 'zeri_scan_remote', technique, action, data: { ok: true, compiled: spec.compile(tree) }, snapshot_text: '' };
    } catch (error) {
      return fail(technique, action, 'invalid_conditions', `${(error && error.message) || error}`);
    }
  }
  const snapshot_text = spec.snapshot({
    cfg: input.cfg && typeof input.cfg === 'object' ? input.cfg : {},
    geo: input.geo && typeof input.geo === 'object' ? input.geo : {},
    tree,
    results: input.results || null,
    truncated: !!input.truncated,
  }) || '';
  return { tool: 'zeri_scan_remote', technique, action, data: { ok: !!snapshot_text }, snapshot_text };
}

function fail(technique, action, code, message) {
  return {
    tool: 'zeri_scan',
    technique,
    action,
    data: { ok: false, error: { code, message } },
    snapshot_text: '',
  };
}

export async function runZeriScan(payload) {
  const input = payload && typeof payload === 'object' ? payload : {};
  const technique = `${input.technique || ''}`;
  const spec = ZERI_TECHNIQUES[technique];
  if (!spec) {
    return fail(technique, `${input.action || 'scan'}`, 'unknown_technique',
      `未知择日技法 ${technique || '(空)'}；可用：${Object.keys(ZERI_TECHNIQUES).join(' / ')}。`);
  }
  const action = `${input.action || 'scan'}`;
  const cfg = input.cfg && typeof input.cfg === 'object' ? input.cfg : {};
  const geo = input.geo && typeof input.geo === 'object' ? input.geo : {};
  const options = input.options && typeof input.options === 'object' ? input.options : {};
  const natal = input.natal && typeof input.natal === 'object' ? input.natal : null;
  const tree = input.tree && typeof input.tree === 'object' ? input.tree : null;

  if (action === 'snapshot') {
    // 逐字上游 builder —— 段头与 aiExport.js 四方同锁，skill 侧不重排版。
    const snapshot_text = spec.snapshot({
      cfg, geo, natal, tree,
      results: input.results || null,
      truncated: !!input.truncated,
    }) || '';
    return {
      tool: 'zeri_scan', technique, action,
      data: { ok: !!snapshot_text },
      snapshot_text,
    };
  }

  if (!tree) {
    return fail(technique, action, 'missing_conditions', '未提供择日条件树（conditions）。');
  }
  let compiled = null;
  try {
    // 让 vendored 条件表跑它自己的 `validate`，抛出本地化的「<label>」条件：<msg>。
    // skill 侧不重编三百余个条件类的 schema —— 那样上游一加条件就烂。
    compiled = spec.compile(tree);
  } catch (error) {
    return fail(technique, action, 'invalid_conditions', `${(error && error.message) || error}`);
  }

  // ⚠ 两种树形状不可互换（qimenzeri 上踩过）：
  //   UI 树       {kind:'group', joiner:'all', children:[…]}  → 快照 builder 渲染的那份
  //   编译树      {type:'all',   conditions:[…]}              → evaluateXTree 走的那份
  // scan 把 tree 直接交给 evaluateXTree，所以必须给**编译树**。传 UI 树不会报错，
  // 它会静默地什么都匹配不上，报出一个看起来合理的零命中结果。
  try {
    const limits = input.limits && typeof input.limits === 'object' ? input.limits : undefined;
    const args = spec.hourly
      ? { cfg, geoParams: geo, options: natal ? { ...options, _natal: natal } : options, tree: compiled, limits }
      : { cfg, tree: compiled, limits };
    const result = await spec.scan(args);
    const intervals = (result && result.intervals) || [];
    return {
      tool: 'zeri_scan', technique, action: 'scan',
      data: {
        ok: true,
        intervals,
        truncated: !!(result && result.truncated),
        stats: (result && result.stats) || null,
        hit_count: intervals.length,
        compiled_tree: compiled,
        limits: spec.limits,
      },
      snapshot_text: '',
    };
  } catch (error) {
    // 绝不把范围/校验失败降级成「零命中」—— 那读起来是一个有效的空结果。
    return fail(technique, 'scan', `${(error && error.code) || 'scan_failed'}`,
      `${(error && error.message) || error}`);
  }
}

export async function runZeriExplain(payload) {
  const input = payload && typeof payload === 'object' ? payload : {};
  const technique = `${input.technique || ''}`;
  const spec = ZERI_TECHNIQUES[technique];
  if (!spec) {
    return fail(technique, 'explain', 'unknown_technique', `未知择日技法 ${technique || '(空)'}。`);
  }
  const tree = input.tree && typeof input.tree === 'object' ? input.tree : null;
  if (!tree) {
    return fail(technique, 'explain', 'missing_conditions', '未提供择日条件树（conditions）。');
  }
  let compiled = null;
  try {
    compiled = spec.compile(tree);
  } catch (error) {
    return fail(technique, 'explain', 'invalid_conditions', `${(error && error.message) || error}`);
  }
  try {
    const t = input.t;
    if (!Number.isFinite(Number(t))) {
      return fail(technique, 'explain', 'missing_moment', 'explain 需要毫秒时刻 t。');
    }
    const args = spec.hourly
      ? { geoParams: input.geo || {}, options: input.options || {}, tree: compiled, t: Number(t) }
      : { tree: compiled, t: Number(t) };
    const explain = spec.explainAt(args);
    return {
      tool: 'zeri_scan', technique, action: 'explain',
      data: { ok: !!explain, explain: explain || null },
      snapshot_text: '',
    };
  } catch (error) {
    return fail(technique, 'explain', `${(error && error.code) || 'explain_failed'}`,
      `${(error && error.message) || error}`);
  }
}

export default runZeriScan;
