// Load-check every vendored module: `import()` each src/vendor/**/*.js and fail on any that throws.
//
// Why this exists: the vendored tree is copied from 星阙 with a mechanical headless transform
// (scripts/revendor_core_js.py) that rewrites import specifiers onto a *different* directory layout.
// A specifier that lands on nothing is invisible until some caller happens to reach that module —
// `vendor/taiyi/core/taiyiSchool.js` shipped a dead `../../../utils/dateStrSafe.js` import for
// several releases purely because nothing imported it. selfcheck.mjs only loads what its ~12 entry
// points reach; this walks all of them.
//
// It catches: unresolved specifiers, `ReferenceError` from a pruned aggregate export, and a missing
// `with { type: 'json' }` attribute. AGENTS §5 is explicit that this is necessary but NOT sufficient —
// "load 过 ≠ 真盘不崩" — so selfcheck.mjs still has to run real data through the engines.

import { readdirSync, statSync } from 'node:fs';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { dirname, join, relative } from 'node:path';

const HERE = dirname(fileURLToPath(import.meta.url));
const VENDOR = join(HERE, '..', 'src', 'vendor');

function walk(dir) {
	const out = [];
	for (const entry of readdirSync(dir)) {
		const full = join(dir, entry);
		if (statSync(full).isDirectory()) out.push(...walk(full));
		else if (entry.endsWith('.js')) out.push(full);
	}
	return out;
}

// skill 自己写的 tools/ 与 shared/ 也要加载：它们按名从 vendor 导入，上游删 / 改名一个导出（v3.12.0 删了
// DunJiaCalc.buildJieqiYearSeed）时 vendor 树自己照样能加载，坏的是 tools/qimen.js ——而 cli.mjs 一启动就经
// tools/index.js 加载全部工具，于是**所有** JS 技法一起挂。只查 vendor 时这条整个漏掉（selfcheck 不走 tools/index）。
const SRC = join(HERE, '..', 'src');
const files = [...walk(VENDOR), ...walk(join(SRC, 'tools')), ...walk(join(SRC, 'shared'))].sort();
const failures = [];

for (const file of files) {
	try {
		await import(pathToFileURL(file).href);
	} catch (err) {
		failures.push(`${relative(SRC, file)}: ${err && err.message ? err.message : err}`);
	}
}

if (failures.length) {
	console.error(`loadcheck: FAIL — ${failures.length}/${files.length} modules (vendor + tools + shared) do not load:`);
	for (const line of failures) console.error(`  - ${line}`);
	console.error('\nA module that cannot load is un-callable in production. Fix the import (usually a');
	console.error('specifier the re-vendor transform pointed at the wrong subdir) or add a shim.');
	process.exit(1);
}

console.log(`loadcheck: ok (${files.length} modules — vendor + tools + shared — load cleanly)`);
