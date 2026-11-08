// 十进制 → 罗盘串对拍（tests/test_coordinate_text.py）：直接跑上游源本身的 convertLatToStr / convertLonToStr（只读加载，
// 与 harness.mjs 同一套 upstream_hooks.mjs），值全部出自上游函数，这里不算任何东西。
// argv[2] = 配置 JSON：{ hooks, hookData, astroHelper, geoCompass, cases: [[label, "数字的字面量"]], sets: {name: [number…]} }。
// cases 用字面量字符串传（Number(...) 还原），这样 -0 / NaN / Infinity / 1e21 也能原样进上游函数。
import { readFileSync } from 'node:fs';
import { register } from 'node:module';

const cfg = JSON.parse(readFileSync(process.argv[2], 'utf8'));
register(cfg.hooks, { data: cfg.hookData });
const helper = await import(cfg.astroHelper);
const compass = await import(cfg.geoCompass);

const both = (v) => [helper.convertLatToStr(v), helper.convertLonToStr(v)];
let compassMismatches = 0;
const check = (v, pair) => {
	if (compass.convertLatToStr(v) !== pair[0] || compass.convertLonToStr(v) !== pair[1]) {
		compassMismatches += 1;
	}
	return pair;
};
const out = { cases: [], sets: {}, compassMismatches: 0 };
for (const [label, literal] of cfg.cases) {
	const v = Number(literal);
	out.cases.push([label, literal, ...check(v, both(v))]);
}
for (const [name, values] of Object.entries(cfg.sets)) {
	out.sets[name] = values.map((v) => check(v, both(v)));
}
out.compassMismatches = compassMismatches;
process.stdout.write(JSON.stringify(out));
