// 古典衍化四段（上游 v3.9.2）：派生宫转宫 / 气候带 / 显赫计分 / 世界范式盘。
// 计算单源 = vendored utils/astroClassicalDerived.js（与上游四组件同引）。
// 上游是 opt-in（仅本命 astro 快照路径传 classicalDerived；germany/mundane/indiachart 等嵌套消费方
// 缺省 falsy = 零输出）——skill 侧同口径：只有 astrochart 流传 chart 进来才产段，条件段双登记。
// 喂 {chart, lat?}：chart = /chart 响应整体（builder 读 chart.chart.objects / params.lat），
// lat 是 fields 兜底（readLatDeg 先 params.lat 再 fields.lat）。任一段空数组 = 不产该段（上游同形）。
import {
  buildDerivedHousesSnapshotLines,
  buildKlimataSnapshotLines,
  buildEminenceSnapshotLines,
  buildThemaMundiSnapshotLines,
} from '../vendor/utils/astroClassicalDerived.js';
import { specByKey } from '../vendor/utils/classicalParamSpec.js';

// [古典·显赫计分] predOpts（上游 astroAiSnapshot.js:1716-1726）：busyPlaces 逗号串 → 整数数组；其余键原样。
// 四个全局键的值域锚定 classicalParamSpec（认不出的回执 invalid，不静默当缺省用）。
const EMINENCE_GLOBAL_KEYS = ['busyPlaces', 'dynamicalDivisions', 'domicileMasterMethod', 'rayWeighting'];
function eminenceOpts(raw, chartObj) {
  const src = raw && typeof raw === 'object' ? raw : {};
  const invalid = [];
  EMINENCE_GLOBAL_KEYS.forEach((k) => {
    const v = src[k];
    if (v === undefined || v === null || v === '') return;
    const spec = specByKey(k);
    let norm = v;
    if (spec && spec.valueType === 'int') norm = (v === true ? 1 : (v === false ? 0 : parseInt(`${v}`, 10)));
    const allowed = spec && spec.options ? spec.options.map((o) => o.value) : (spec && spec.valueType === 'int' ? [0, 1] : null);
    if (allowed && allowed.indexOf(norm) < 0) invalid.push({ key: k, value: v, allowed });
  });
  const pick = (k) => (src[k] !== undefined && src[k] !== null && src[k] !== '' ? src[k] : undefined);
  const busy = pick('busyPlaces');
  const opts = {
    busyPlaces: busy === undefined ? undefined : `${busy}`.split(',').map((x) => parseInt(x, 10)).filter((n) => Number.isFinite(n)),
    dynamicalDivisions: pick('dynamicalDivisions') === undefined ? undefined : (src.dynamicalDivisions === true ? 1 : Number(src.dynamicalDivisions)),
    domicileMasterMethod: pick('domicileMasterMethod'),
    termsVariant: pick('termsVariant'),
    geminiBoundEmended: pick('geminiBoundEmended'),
    customTermsDay: pick('customTermsDay') || (chartObj && chartObj.params ? chartObj.params.customTermsDay : undefined),
    customTermsNight: pick('customTermsNight') || (chartObj && chartObj.params ? chartObj.params.customTermsNight : undefined),
    rayWeighting: pick('rayWeighting'),
  };
  return { opts, invalid };
}

const SECTIONS = [
  ['古典·派生宫转宫', (chartObj) => buildDerivedHousesSnapshotLines(chartObj)],
  ['古典·气候带', (chartObj, fields) => buildKlimataSnapshotLines(chartObj, fields)],
  ['古典·显赫计分', (chartObj, fields, predOpts) => buildEminenceSnapshotLines(chartObj, predOpts)],
  ['古典·世界范式盘', () => buildThemaMundiSnapshotLines()],
];

export function runClassicalDerived(payload) {
  try {
    const p = payload && typeof payload === 'object' ? payload : {};
    const chartObj = p.chart && typeof p.chart === 'object' ? p.chart : null;
    if (!chartObj) {
      return { snapshot_text: '' };
    }
    const fields = p.lat !== undefined && p.lat !== null ? { lat: { value: p.lat } } : null;
    const { opts: predOpts, invalid } = eminenceOpts(p.eminence, chartObj);
    if (invalid.length) {
      return { snapshot_text: '', error: 'invalid_setting', invalid };
    }
    const blocks = [];
    SECTIONS.forEach(([title, build]) => {
      let lines = [];
      try {
        lines = build(chartObj, fields, predOpts) || [];
      } catch (e) {
        lines = []; // 上游同款：单段失败不阻断其余段
      }
      if (Array.isArray(lines) && lines.length) {
        blocks.push(`[${title}]\n${lines.join('\n')}`);
      }
    });
    return { snapshot_text: blocks.join('\n\n') };
  } catch (e) {
    return { snapshot_text: '' };
  }
}
