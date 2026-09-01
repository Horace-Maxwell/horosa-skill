// 灵棋经起卦引擎(纯函数,零 UI 依赖)。
// 古法口径(《靈棋經》卷首):十二棋子(上4/中4/下4)一時擲之,依所得上中下成卦,不可再擲。
// 掷法=每枚独立正/覆 → 层内正面数服从二项 B(4,½)(物理掷棋分布;不做均匀 5 档臆造)。
// 确定性:sha256(seed)→mulberry32→固定序恰 12 次消费(上4→中4→下4),同 seed 字节幂等(塔罗 shuffle 同款范式)。
// headless shim：上游只用 node-forge 取 SHA-256。改用 Node 内置 crypto —— 摘要逐字节一致，
// 却省掉一个 npm 依赖（离线 runtime 要打包，且 loadcheck 会因缺包整棵 tarot/engine 加载失败）。
// 保留 forge 的调用形状而不改上游函数体，是为了让本文件其余部分继续逐字 verbatim。
import { createHash } from 'node:crypto';
function _sha256Md(){
	const parts = [];
	return {
		update(s){ parts.push(String(s)); return this; },
		digest(){ return { toHex: () => createHash('sha256').update(parts.join(''), 'utf8').digest('hex') }; },
	};
}
const forge = { md: { sha256: { create: _sha256Md } } };

function sha256Hex(str) {
	const md = forge.md.sha256.create();
	md.update(String(str === undefined || str === null ? '' : str), 'utf8');
	return md.digest().toHex();
}

function mulberry32(a) {
	return function () {
		let t = (a += 0x6D2B79F5);
		t = Math.imul(t ^ (t >>> 15), t | 1);
		t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
		return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
	};
}

// 掷十二棋:seed → { counts:[上,中,下], faces:[[bool×4]×3] }(faces[i][j]=true 为字面朝上)。
// 恒消费 12 次 rng(层序 上→中→下、枚序 0→3),任何口径开关都不得改变消费序列(塔罗逆位铁律同款)。
export function castLingqi(seed) {
	const hex = sha256Hex(seed);
	const seedNum = parseInt(hex.substring(0, 8), 16) >>> 0;
	const rng = mulberry32(seedNum);
	const faces = [];
	const counts = [];
	for (let layer = 0; layer < 3; layer++) {
		const row = [];
		let n = 0;
		for (let k = 0; k < 4; k++) {
			const up = rng() < 0.5;
			row.push(up);
			if (up) { n += 1; }
		}
		faces.push(row);
		counts.push(n);
	}
	return { counts, faces };
}

// 读档/手动摆棋:由 counts 重建 faces(前 k 枚字面朝上,确定性;越界钳制 0..4)。
export function facesFromCounts(counts) {
	const cs = Array.isArray(counts) ? counts : [0, 0, 0];
	return [0, 1, 2].map((i) => {
		let n = Math.floor(Number(cs[i]));
		if (!Number.isFinite(n) || n < 0) { n = 0; }
		if (n > 4) { n = 4; }
		return [0, 1, 2, 3].map((k) => k < n);
	});
}

// 时间种子:占时(精确到分)拼稳定 int(geomancy computeTimeSeed 同款口径,同一分钟同种子可复现)。
export function computeTimeSeed(fields) {
	let y; let mo; let da; let h; let mi;
	const dv = fields && fields.date && fields.date.value;
	const tv = fields && fields.time && fields.time.value;
	if (dv && dv.format && tv && tv.format) {
		y = parseInt(dv.format('YYYY'), 10);
		mo = parseInt(dv.format('MM'), 10);
		da = parseInt(dv.format('DD'), 10);
		h = parseInt(tv.format('HH'), 10);
		mi = parseInt(tv.format('mm'), 10);
	} else {
		const d = new Date();
		y = d.getFullYear(); mo = d.getMonth() + 1; da = d.getDate(); h = d.getHours(); mi = d.getMinutes();
	}
	const v = ((y % 100) * 100000000) + (mo * 1000000) + (da * 10000) + (h * 100) + mi;
	return v % 2147483647;
}

// 种子来源归一(塔罗 resolveSeed 同款三态;time_seed 档取占时种子)。
export function resolveLingqiSeed(seedMode, manualSeed, fields) {
	if (seedMode === 'manual') { return `${manualSeed === undefined || manualSeed === null ? 0 : manualSeed}`; }
	if (seedMode === 'time_seed') { return `t-${computeTimeSeed(fields)}`; }
	const r = (typeof window !== 'undefined' && window.crypto && window.crypto.getRandomValues)
		? window.crypto.getRandomValues(new Uint32Array(1))[0] : Math.floor(Math.random() * 4294967296);
	return `rnd-${r}`;
}

// ── 三才数性结构(刘基后序明文,不推衍) ──
// 「四以一為少陽三為太陽二為少隂四為老隂」;0=十二棋皆覆之位,无爻。
export const SHU_XING = { 0: '覆', 1: '少陽', 2: '少隂', 3: '太陽', 4: '老隂' };
export const SANCAI_ROLES = [
	{ key: 'up', label: '上', role: '君', realm: '天' },
	{ key: 'mid', label: '中', role: '臣', realm: '人' },
	{ key: 'down', label: '下', role: '民', realm: '地' },
];

// 层际关系:仅标后序明文两对——「少陽與少隂為耦(得耦而悦)」「太陽與老隂為敵(得敵而争)」;
// 其余组合原文无明文,一律不标(不臆造)。
export function pairRelation(a, b) {
	const s = new Set([a, b]);
	if (s.size === 2 && s.has(1) && s.has(2)) { return { kind: 'ou', label: '耦', gloss: '得耦而悦' }; }
	if (s.size === 2 && s.has(3) && s.has(4)) { return { kind: 'di', label: '敵', gloss: '得敵而争' }; }
	return null;
}

// 结构总览:逐层数性 + 三组层际关系(上中/中下/上下)+ 阴阳多寡(陽=1,3;隂=2,4;覆不计)。
// 「陽多者道同而助,隂盛者志異而乖」(后序)——只在一侧严格居多时给原文语,均势不判。
export function sanCaiOf(counts) {
	const cs = Array.isArray(counts) ? counts : [0, 0, 0];
	const layers = cs.map((v, i) => ({
		...SANCAI_ROLES[i],
		value: v,
		xing: SHU_XING[v] || '',
	}));
	const rel = [
		{ between: '上中', ...(pairRelation(cs[0], cs[1]) || { kind: null, label: '', gloss: '' }) },
		{ between: '中下', ...(pairRelation(cs[1], cs[2]) || { kind: null, label: '', gloss: '' }) },
		{ between: '上下', ...(pairRelation(cs[0], cs[2]) || { kind: null, label: '', gloss: '' }) },
	];
	let yang = 0; let yin = 0;
	cs.forEach((v) => {
		if (v === 1 || v === 3) { yang += 1; }
		if (v === 2 || v === 4) { yin += 1; }
	});
	let tendency = '';
	if (yang > yin) { tendency = '陽多者道同而助'; }
	else if (yin > yang) { tendency = '隂盛者志異而乖'; }
	return { layers, relations: rel, yang, yin, tendency };
}

// 六戊日检测(卷首「六戊日不宜占卜」):占时日干=戊 → true(提示不阻断)。
// nongli 取 deriveNongliUniversalSync 产物({bazi:{day:{stem:{cell}}}})或后端 nongli(dayGanZi 串)。
export function isWuDay(nongli) {
	if (!nongli) { return false; }
	const b = nongli.bazi || {};
	const stem = (b.day && b.day.stem && b.day.stem.cell) || '';
	if (stem) { return stem === '戊'; }
	const gz = `${nongli.dayGanZi || ''}`.trim();
	return gz.length >= 1 && gz.charAt(0) === '戊';
}

// 诗句排版:按行界/全角空切段;某段恰为基准句长 2 倍时对半重切(源文本行界丢失所致的连排,
// 如「大降洪恩布九垓萬物一時沾聖化」14 字 = 7+7)。仅整倍且其余段等长时才切,不齐言者保持原样。
export function splitVerse(shi) {
	if (!shi) { return []; }
	const raw = `${shi}`.split(/[\n　]+/).map((s) => s.trim()).filter(Boolean);
	if (!raw.length) { return []; }
	const lens = raw.map((s) => s.length);
	const base = Math.min(...lens);
	if (base >= 4 && raw.every((s) => s.length === base || s.length === base * 2)) {
		const out = [];
		raw.forEach((s) => {
			if (s.length === base * 2) { out.push(s.slice(0, base), s.slice(base)); }
			else { out.push(s); }
		});
		return out;
	}
	return raw;
}
