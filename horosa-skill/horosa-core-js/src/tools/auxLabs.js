import * as AstroText from '../constants/AstroText.js';
import {
  TRANSFORM_KINDS,
  TRANSFORM_PAGE_SETTINGS,
  ZODIAC_PAGE_SETTINGS,
  transformKindDef,
  transformSnapshotChart,
  transformSnapshotLines,
  zodiacSnapshotLines,
  zodiacVersionLabel,
} from '../vendor/utils/transformCharts.js';
import { DERIVED_LAB_HEADLESS_KEYS, transformRequestOptions } from '../vendor/utils/aiAnalysisContext/derivedLabsHeadless.js';
import { validateSettingValue } from '../vendor/utils/pageSettingsStore.js';

/**
 * 辅盘「变换盘」「黄道制」（上游 v3.14.0）：后端结果 → 快照专属段。
 *
 * 上游自己就有无头路径 utils/aiAnalysisContext/derivedLabsHeadless.js：取本命盘 → 按辅盘页保存的设置请求
 * /astroextra/transformchart 或 /astroextra/zodiacsystems → 正文 = derivedAstroSnapshotText(变换后的整盘 | null, fields,
 * () => transformSnapshotLines(res, settings, planetName) | zodiacSnapshotLines(res, planetName))。headless 分工：
 * Python 发请求、出整盘通用段（engine/astro_snapshot.py，与本命盘同一份）；这里只跑上游那几个纯函数——
 *   · transformSnapshotLines / zodiacSnapshotLines：专属段的行（首行是 `[变换盘]` / `[黄道制]` 段头）；
 *   · transformSnapshotChart：北交宫盘给 AI 的宫头用真宫头（盘面画的是段头），其余变换原样返回；
 *   · transformRequestOptions：变换盘只发这种变换真正用到的选项——按同一份设置重算回传，runner 与自己发出的逐键比对。
 * 设置的值域取上游页面设置表（TRANSFORM_PAGE_SETTINGS / ZODIAC_PAGE_SETTINGS 的 schema），不在这里另抄一份。
 *
 * payload: { technique: 'transformchart' | 'zodiacsystems', result: <后端响应>,
 *            settings: 变换盘 { kind, planet, shift, house, variant }（页面键，缺省已由调用方补齐）| 黄道制 { version } }
 * return : { title, lines, ... }；设置值不在上游候选里 → { invalid: [{ key, value, allowed }] }（不落缺省）。
 */

const planetName = (id) => (AstroText.AstroMsgCN && AstroText.AstroMsgCN[id]) || id;

const TRANSFORM_KEYS = ['kind', 'planet', 'shift', 'house', 'variant'];

function invalidSettings(store, keys, settings) {
  const invalid = [];
  keys.forEach((key) => {
    const spec = store.schema[key];
    const value = settings[key];
    if (!validateSettingValue(spec, value).ok) {
      invalid.push({ key, value: value === undefined ? null : value, allowed: Array.isArray(spec.oneOf) ? spec.oneOf.slice() : [true, false] });
    }
  });
  return invalid;
}

// 上游的行数组首行是段头 `[名]`：拆成 { title, lines }，Python 侧按段装配（与龙盘 / 调波盘 / 重置盘的专属段同形）。
function splitSection(lines) {
  if (!Array.isArray(lines) || !lines.length) {
    return { title: '', lines: [] };
  }
  const head = /^\[(.+)\]$/.exec(`${lines[0]}`);
  if (!head) {
    throw new Error(`horosa-core-js: aux lab snapshot does not start with a section header: ${lines[0]}`);
  }
  return { title: head[1], lines: lines.slice(1) };
}

function runTransform(source) {
  const settings = source.settings && typeof source.settings === 'object' ? source.settings : {};
  const invalid = invalidSettings(TRANSFORM_PAGE_SETTINGS, TRANSFORM_KEYS, settings);
  if (invalid.length) {
    return { invalid };
  }
  const def = transformKindDef(settings.kind);
  const result = source.result && typeof source.result === 'object' ? source.result : null;
  const section = splitSection(transformSnapshotLines(result, settings, planetName));
  const chart = result ? transformSnapshotChart(result) : null;
  const moved = chart && result && chart !== result.chart && chart.chart && Array.isArray(chart.chart.houses);
  return {
    title: section.title,
    lines: section.lines,
    // 只在上游换了宫头（北交宫盘）时回传；其余变换 null = 照后端回的宫头出正文。
    snapshot_houses: moved ? chart.chart.houses : null,
    request_fields: transformRequestOptions(settings, def),
    kind: { value: def.value, label: def.label, desc: def.desc, options: (def.options || []).slice() },
  };
}

function runZodiac(source) {
  const settings = source.settings && typeof source.settings === 'object' ? source.settings : {};
  const invalid = invalidSettings(ZODIAC_PAGE_SETTINGS, ['version'], settings);
  if (invalid.length) {
    return { invalid };
  }
  const result = source.result && typeof source.result === 'object' ? source.result : null;
  const section = splitSection(zodiacSnapshotLines(result, planetName));
  return {
    title: section.title,
    lines: section.lines,
    version: { value: settings.version, label: zodiacVersionLabel(settings.version) },
  };
}

export function runAuxLabs(payload) {
  const source = payload && typeof payload === 'object' ? payload : {};
  const technique = `${source.technique || ''}`;
  if (DERIVED_LAB_HEADLESS_KEYS.indexOf(technique) < 0) {
    throw new Error(`horosa-core-js: aux_labs does not know technique "${technique}" (expected one of ${DERIVED_LAB_HEADLESS_KEYS.join(' / ')})`);
  }
  return technique === 'transformchart' ? runTransform(source) : runZodiac(source);
}

// 上游表原样导出：测试把 Python 侧的词表（auxlab_vocab.py）逐项锚到这里。
export { TRANSFORM_KINDS };

export default runAuxLabs;
