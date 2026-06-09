// 七政四余 政余格局（Moira DSL）headless wrapper。
// 输入 payload.chart = /chart 七政四余响应；payload.fields/params 可选（headless 缺省走默认 lifeMode/昼夜/季节）。
// 输出 snapshot_text = 与 星阙 buildGuolaoPatternSection 同源同格式的「喜格/忌格/察看」三行。
import { buildLocalMoiraPatterns, buildGodRowsFromChart } from '../vendor/guolao/guolaoMoira.js';

export function runGuolaoMoira(payload) {
  const result = payload && payload.chart ? payload.chart : payload;
  const fields = (payload && payload.fields) || {};
  const params = (payload && payload.params) || {};
  try {
    const godRows = buildGodRowsFromChart(result, fields);
    const patterns = buildLocalMoiraPatterns(result, fields, params, godRows) || [];
    if (!patterns.length) {
      return { snapshot_text: '无', data: { patterns: [] } };
    }
    const fmt = (list) => list.map((it) => `${it.name}（${it.detail || it.dsl || ''}）`).join('；');
    const good = patterns.filter((it) => it.level === 'good');
    const bad = patterns.filter((it) => it.level === 'bad');
    const other = patterns.filter((it) => it.level !== 'good' && it.level !== 'bad');
    const out = [];
    out.push(`喜格：${good.length ? fmt(good) : '（无）'}`);
    out.push(`忌格：${bad.length ? fmt(bad) : '（无）'}`);
    if (other.length) {
      out.push(`察看：${fmt(other)}`);
    }
    return { snapshot_text: out.join('\n'), data: { patterns } };
  } catch (e) {
    // 降级「无」，不影响既有 guolao 段（与 星阙 buildGuolaoPatternSection 的 try/catch 一致）。
    return { snapshot_text: '无', data: { patterns: [], error: String(e) } };
  }
}
