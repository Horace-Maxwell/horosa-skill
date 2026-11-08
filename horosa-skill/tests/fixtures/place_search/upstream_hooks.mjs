// 让 node 直接跑上游星阙的 bundler 写法源码（只读，不拷贝、不改写）：
//   - 相对 import 无扩展名 → 补 `.js` / `/index.js`；
//   - `.js` 没有 "type": "module" → 按 ESM 加载；
//   - JSON 无 import 属性 → 解析时补 `type: 'json'`；
//   - 裸包 `tz-lookup` → horosa-core-js/node_modules 里那份（与上游 package-lock 同版本同 integrity）。
import { existsSync, statSync } from 'node:fs';
import { fileURLToPath, pathToFileURL } from 'node:url';

let tzLookupUrl = null;
let upstreamRoot = null;

export async function initialize(data) {
	tzLookupUrl = data.tzLookupUrl;
	upstreamRoot = data.upstreamRoot;
}

export async function resolve(specifier, context, nextResolve) {
	if (specifier === 'tz-lookup') {
		return { url: tzLookupUrl, shortCircuit: true, format: 'commonjs' };
	}
	const parent = `${context.parentURL || ''}`;
	if ((specifier.startsWith('./') || specifier.startsWith('../')) && parent.startsWith(upstreamRoot)) {
		const target = new URL(specifier, parent);
		const path = fileURLToPath(target);
		if (path.endsWith('.json')) {
			return { url: target.href, shortCircuit: true, format: 'json', importAttributes: { type: 'json' } };
		}
		if (!existsSync(path) || statSync(path).isDirectory()) {
			for (const candidate of [`${path}.js`, `${path}/index.js`]) {
				if (existsSync(candidate)) {
					return { url: pathToFileURL(candidate).href, shortCircuit: true, format: 'module' };
				}
			}
		}
		return { url: target.href, shortCircuit: true, format: 'module' };
	}
	return nextResolve(specifier, context);
}

export async function load(url, context, nextLoad) {
	if (url.startsWith(upstreamRoot) && url.endsWith('.js')) {
		return nextLoad(url, { ...context, format: 'module' });
	}
	return nextLoad(url, context);
}
