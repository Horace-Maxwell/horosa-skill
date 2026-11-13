#!/usr/bin/env node
// 农历月表（1900–2100）：每个农历年正月初一的公历日期 + 各月（负数 = 闰月）天数。来源 = horosa-core-js 已锁版本的 lunar-javascript
// （与八字 / 黄历 / 万年历同一个历法引擎），Python 侧 `horosa_skill.lunar_calendar` 只查这张表，不手写任何历法规则。
//
//   node scripts/gen_lunar_table.mjs            # 重写 src/horosa_skill/data/lunar_months.json
//   node scripts/gen_lunar_table.mjs --check    # 与磁盘上的一致才退出 0
// 守卫：tests/test_fix314_lunar_input.py 逐日往返（1900–2100 每一天：公历 → 农历 → 公历）与 --check。
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const PKG = path.resolve(HERE, '..');
const require = createRequire(path.join(PKG, 'horosa-core-js', 'package.json'));
const { LunarYear, Solar } = require('lunar-javascript');
const version = require('lunar-javascript/package.json').version;
const OUT = path.join(PKG, 'src', 'horosa_skill', 'data', 'lunar_months.json');

const years = {};
for (let y = 1900; y <= 2100; y += 1) {
  const months = LunarYear.fromYear(y).getMonthsInYear();
  years[y] = {
    start: Solar.fromJulianDay(months[0].getFirstJulianDay()).toYmd(),
    months: months.map((m) => [m.getMonth(), m.getDayCount()]),
  };
}
const text = `${JSON.stringify({
  _comment: '农历月表：start = 该农历年正月初一的公历日期；months = [月, 天数]，负数 = 闰月。由 scripts/gen_lunar_table.mjs 从 lunar-javascript 生成，勿手改。',
  source: `lunar-javascript ${version}`,
  range: [1900, 2100],
  years,
})}\n`;
if (process.argv.includes('--check')) {
  const current = fs.existsSync(OUT) ? fs.readFileSync(OUT, 'utf8') : '';
  if (current !== text) {
    console.error('lunar_months.json is stale: run node scripts/gen_lunar_table.mjs');
    process.exit(1);
  }
  console.log(`lunar-table: up to date (${Object.keys(years).length} years, ${version})`);
} else {
  fs.writeFileSync(OUT, text);
  console.log(`wrote ${path.relative(PKG, OUT)} (${Object.keys(years).length} years, ${(text.length / 1024).toFixed(1)} KB, ${version})`);
}
