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

const SECTIONS = [
  ['古典·派生宫转宫', (chartObj) => buildDerivedHousesSnapshotLines(chartObj)],
  ['古典·气候带', (chartObj, fields) => buildKlimataSnapshotLines(chartObj, fields)],
  ['古典·显赫计分', (chartObj) => buildEminenceSnapshotLines(chartObj)],
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
    const blocks = [];
    SECTIONS.forEach(([title, build]) => {
      let lines = [];
      try {
        lines = build(chartObj, fields) || [];
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
