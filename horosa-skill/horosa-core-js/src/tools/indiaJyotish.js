import { buildJyotishSnapshotLines } from '../vendor/india/jyotishSnapshot.js';

/**
 * 把后端 `/india/chart` 响应里的 `jyotish` 树格式化成星阙的具名段。
 *
 * Python 侧只负责取盘（`_run_india_chart_tool` 已有的 `_call_remote`），格式化交给这里逐字同源的
 * vendored builder —— 与 ken formatter 同一分工：**后端算，JS 排版**。
 *
 * payload: { chart: <整个 /india/chart 响应> }
 * return : { sections: { '段名': ['行', …], … } }
 */
export function runIndiaJyotish(payload) {
  const chartObj = (payload && payload.chart) || null;
  if (!chartObj) {
    return { sections: {} };
  }
  const sections = buildJyotishSnapshotLines(chartObj) || {};
  return { sections };
}
