import { buildSanShiZiweiSihuaSnapshotLines } from '../vendor/sanshi/SanShiZiWeiSihua.js';

/**
 * 三式合一 [紫微四化] 段（生年 / 大运 / 流年 三层四化 × 落宫）——单独取段的薄入口。
 *
 * 上游由紫微子页签上报的 UI 状态驱动（盘 + 选中的大运/流年下标），tab 未打开过就整段不产。
 * headless 没有页签，故把同一份选择开成显式入参 `daxianIdx` / `liunianIdx`（缺省 0 = 首项，
 * 与上游「越界回退」的钳制口径一致）；紫微盘由 Python 按起课时间另取一张。
 *
 * 行文由 vendored 上游 SanShiZiWeiSihua.js 的 buildSanShiZiweiSihuaSnapshotLines 产出（v3.11.x 同步前
 * 这里手抄了一份函数体）。三式合一整份快照走 sanshiunited 工具时由上游 buildSanShiUnitedSnapshotText
 * 自己调它、以【紫微四化】段头收尾——本入口只供单独取段。
 *
 * payload: { chart: <ziwei 盘>, daxianIdx?: number, liunianIdx?: number }
 * return : { text }
 */
export function runSanshiZiweiSihua(payload) {
  const source = payload && typeof payload === 'object' ? payload : {};
  const chart = source.chart && typeof source.chart === 'object' ? source.chart : null;
  if (!chart) {
    return { text: '' };
  }
  try {
    const lines = buildSanShiZiweiSihuaSnapshotLines(chart, source.daxianIdx || 0, source.liunianIdx || 0) || [];
    if (!lines.length) {
      return { text: '', error: { code: 'empty_sihua_lines', message: '紫微四化未产出行（盘可能缺 daxian/liunian 索引所指的运限）。' } };
    }
    return { text: ['[紫微四化]', ...lines].join('\n') };
  } catch (error) {
    return { text: '', error: { code: 'sihua_build_failed', message: error instanceof Error ? error.message : `${error}` } };
  }
}

export default runSanshiZiweiSihua;
