// zeriConditions — 择日十技法的条件词表与「条件按此理解」回显（skill 自有，不是上游模块）。
//
// 为什么要有：深审 F5 —— 黄历择吉的 `chong_shengxiao` 自带判法（mode 缺省 without = 不冲所选肖），客户端再加 `negate: true`
// 想表达「避开冲马」，结果拿到的恰恰是冲马的日子；schema 与 guidance 都没说条件的极性，结果里也没有把它读懂成什么。
// 这里只读上游注册表（label / category / defaults / fields / summary），不改判定：
//   catalog → 每个技法每类条件一条（标签、门类、缺省设定读作什么、自带判法的选项），由 Python 生成双语的一行说明；
//   echo    → 把这次的条件树按引擎的读法写成人话（每叶的 summary + 取反 + 连接词，与 compileRows 同样从上到下左结合）。
import { CONDITION_TYPES } from '../vendor/divination/zeri/conditionTypes.js';
import { conditionSummaryText } from '../vendor/divination/zeri/conditionGlyph.js';
import { HUANGLI_CONDITION_TYPES } from '../vendor/divination/zeri/huangliZeriConditionTypes.js';
import { BAZI_CONDITION_TYPES } from '../vendor/divination/zeri/baziZeriConditionTypes.js';
import { TAIYI_CONDITION_TYPES } from '../vendor/divination/zeri/taiyiZeriConditionTypes.js';
import { ZIWEI_CONDITION_TYPES } from '../vendor/divination/zeri/ziweiZeriConditionTypes.js';
import { LIURENG_CONDITION_TYPES } from '../vendor/divination/zeri/liurengZeriConditionTypes.js';
import { SANSHI_CONDITION_TYPES } from '../vendor/divination/zeri/sanshiZeriConditionTypes.js';
import { QIZHENG_CONDITION_TYPES } from '../vendor/divination/zeri/qizhengZeriConditionTypes.js';
import { INDIA_CONDITION_TYPES } from '../vendor/divination/zeri/indiaZeriConditionTypes.js';
import { QIMEN_CONDITION_TYPES } from '../vendor/divination/zeri/qimenConditionTypes.js';

export const ZERI_REGISTRIES = {
  tianxing: CONDITION_TYPES,
  huanglizeri: HUANGLI_CONDITION_TYPES,
  qimenzeri: QIMEN_CONDITION_TYPES,
  bazizeri: BAZI_CONDITION_TYPES,
  taiyizeri: TAIYI_CONDITION_TYPES,
  ziweizeri: ZIWEI_CONDITION_TYPES,
  liurengzeri: LIURENG_CONDITION_TYPES,
  sanshizeri: SANSHI_CONDITION_TYPES,
  qizhengzeri: QIZHENG_CONDITION_TYPES,
  indiazeri: INDIA_CONDITION_TYPES,
};

const JOINER_ZH = { all: '且', any: '或', xor: '异或' };
const JOINER_EN = { all: 'AND', any: 'OR', xor: 'XOR' };

function summaryOf(technique, type, params) {
  const spec = ZERI_REGISTRIES[technique][type];
  if (!spec) { return ''; }
  try {
    if (typeof spec.summary === 'function') { return `${spec.summary(params || {}) || ''}`; }
    // 天星的注册表没有 summary：上游工作台与快照用 conditionGlyph 出文字（glyph 回退 title）。
    return conditionSummaryText({ type, params: params || {} });
  } catch (error) {
    return '';
  }
}

// 自带判法的选择字段（判法 / 模式 / 极性）：值不止一种、且选项是互斥的读法 → 原样列出，Python 写进一行说明。
function choiceFields(spec) {
  return (spec.fields || [])
    .filter((field) => field && field.kind === 'select' && Array.isArray(field.options) && field.options.length > 1)
    .map((field) => ({
      key: field.key,
      label: field.label || field.key,
      default: spec.defaults ? spec.defaults[field.key] : undefined,
      options: field.options.map((o) => ({ value: o.value, label: `${o.label}` })),
    }));
}

function catalog() {
  const out = {};
  Object.keys(ZERI_REGISTRIES).forEach((technique) => {
    const registry = ZERI_REGISTRIES[technique];
    out[technique] = Object.keys(registry).map((type) => {
      const spec = registry[type];
      return {
        type,
        label: `${spec.label || type}`,
        category: `${spec.category || ''}`,
        default_reads: summaryOf(technique, type, spec.defaults || {}),
        choices: choiceFields(spec),
      };
    });
  });
  return out;
}

function isGroup(node) {
  return !!node && (node.kind === 'group' || Array.isArray(node.children));
}

function echoNode(technique, node, depth, joiner, lines, unknown) {
  const pad = '  '.repeat(depth);
  const zhJoin = joiner ? `${JOINER_ZH[joiner] || '且'} ` : '';
  const enJoin = joiner ? `${JOINER_EN[joiner] || 'AND'} ` : '';
  if (isGroup(node)) {
    lines.push({
      depth,
      zh: `${pad}${zhJoin}${node.negate ? '以下整组不成立（取反）：' : '（一组）'}`,
      en: `${pad}${enJoin}${node.negate ? 'NOT (the whole group below):' : '(group)'}`,
    });
    (node.children || []).forEach((child, index) => {
      echoNode(technique, child, depth + 1, index === 0 ? null : (child.joiner || 'all'), lines, unknown);
    });
    return;
  }
  const spec = ZERI_REGISTRIES[technique][node.type];
  if (!spec) { unknown.push(`${node.type}`); }
  const label = spec ? `${spec.label}` : `${node.type}`;
  const body = summaryOf(technique, node.type, node.params || {});
  const reads = body ? `${label}：${body}` : label;
  lines.push({
    depth,
    zh: node.negate ? `${pad}${zhJoin}不满足〔${reads}〕（negate 取反：这一项不成立才算命中）` : `${pad}${zhJoin}${reads}`,
    en: node.negate ? `${pad}${enJoin}NOT [${node.type}: ${reads}] (negate: matches only where this leaf fails)` : `${pad}${enJoin}${node.type}: ${reads}`,
  });
}

function echo(technique, tree) {
  const lines = [];
  const unknown = [];
  if (isGroup(tree) && !tree.negate) {
    // 根组：不另起一行，子项按从上到下、左结合（与 compileRows 同）。
    (tree.children || []).forEach((child, index) => {
      echoNode(technique, child, 0, index === 0 ? null : (child.joiner || 'all'), lines, unknown);
    });
  } else if (tree) {
    echoNode(technique, tree, 0, null, lines, unknown);
  }
  return { lines, unknown };
}

export function runZeriConditions(payload) {
  const input = payload && typeof payload === 'object' ? payload : {};
  const action = `${input.action || 'catalog'}`;
  if (action === 'catalog') {
    return { tool: 'zeri_conditions', action, data: { ok: true, catalog: catalog() } };
  }
  if (action === 'echo') {
    const technique = `${input.technique || ''}`;
    if (!ZERI_REGISTRIES[technique]) {
      return { tool: 'zeri_conditions', action, data: { ok: false, error: { code: 'unknown_technique', message: `不认识的择日技法：${technique}` } } };
    }
    return { tool: 'zeri_conditions', action, data: { ok: true, ...echo(technique, input.tree) } };
  }
  return { tool: 'zeri_conditions', action, data: { ok: false, error: { code: 'unknown_action', message: `unknown action ${action}` } } };
}
