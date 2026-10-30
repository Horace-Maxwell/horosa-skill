// 简繁检索比对 · 纯函数(不看界面当前是简体还是繁体,也不加载词典;转换器由调用方传入)。
//
// conv = 转换器对象(通常就是 scriptConvert/hantConverter 的导出),用到其中这些(缺哪个就按「原样」退化,
// 例如无头运行时的空壳转换器只有 toHant):
//   toHant(s)             简 → 繁显示写法(逐码点等长)
//   isTradFormChar(ch)    ch 是否繁体写法字(繁 → 简会改它;简体原文里不会出现;缺省退用 isTradOnlyChar)
//   hansCandidatesOf(ch)  繁体写法字 ch 的简体写法(如 鍾 → 钟 / 锺)
//   hantCandidatesOf(ch)  简体字 ch 的繁体写法(一简多繁:历 → 曆 / 歷,发 → 發 / 髮,钟 → 鐘 / 鍾,里 → 裏 / 裡)
//   toMatchKey(s)         把繁体折回简体写法(只改繁体写法字)
//   matchFormsOf(s)       buildMatchForms 的带缓存版本(可选)
//
// 比对在「显示空间」里逐位对齐做(不再整串过繁 → 简再比 —— 繁 → 简按词切分,短查询与长串切法不同,
// 子串上不稳定:单字「乾」折成「干」,却命中「天干地支」;「坐」搜不到显示为「座標」的「坐标」)。
// 被搜文字 hay 的第 k 位接受下列任一字:原文字 hay[k] · 显示字 toHant(hay)[k] ·
// (hay[k] 是繁体写法字时)它的简体写法。查询逐位落在这些字里即命中 —— 照屏幕输入、直接输入简体、
// 简繁混着输入都认,而「乾」不会命中「天干地支」(那里显示的就是「干」)。
// 被搜文字本身含繁体写法字(记录 / 史料原文存的是繁体)时,另用它整串折回的简体写法兜底一次。
// 对齐按**码点**做,不按 UTF-16 下标:转换逐码点等长,UTF-16 却不一定等长 —— 扩展 A 区有字转繁后落到辅助平面
// (㓆 → 𠗣),规范简化字里的扩展 E / F 字转繁后回到基本平面(𬣙 → 訏)。命中后经「码点下标 ↔ hay 的 UTF-16 下标」换算表落回:
// 命中下标与命中长度都是 hay 上的 UTF-16 量(长度不一定等于查询长度,高亮 / 找下一处用 spanAcrossScripts 给的长度)。
//
// relaxFold(放宽一档;只给不对着屏幕检索的调用方:AI 工具 / 无头 / 命令行):上面都不中时,两边的繁体写法字都折回简体
// (conv.toMatchKey)再比 —— 检索词来自史料 / 别处,写法未必是屏幕上的显示写法(「張三豐」要命中「张三丰」)。
// 折回只改繁体写法字,「乾」这类本身也是简体的字不折,所以「乾」仍不命中「天干地支」;反过来繁体专用字「幹」折成「干」后
// 会命中「天干」—— 这是放宽一档的设计口径(偏召回),屏幕检索不放宽。含 / 命中位置 / 整名相等三个入口同读这一档。

const HAN_RE = /[㐀-鿿豈-﫿\u{20000}-\u{3FFFF}]/u;

const toStr = (v)=>(v === undefined || v === null ? '' : `${v}`);
// 码点是否中日韩字(基本平面统一表意 / 兼容表意 / 辅助平面扩展 B–H)
const isHanCp = (c)=>{
	if(!c){ return false; }
	if(c.length === 1){ return (c >= '㐀' && c <= '鿿') || (c >= '豈' && c <= '﫿'); }
	const cp = c.codePointAt(0);
	return cp >= 0x20000 && cp <= 0x3FFFF;
};
const tradPred = (c)=>(typeof c.isTradFormChar === 'function' ? c.isTradFormChar
	: (typeof c.isTradOnlyChar === 'function' ? c.isTradOnlyChar : null));

// 码点数组的 UTF-16 下标表:off[k] = 第 k 个码点在串里的 UTF-16 下标(off[n] = 串长);每个码点都只占一个 UTF-16 单元时回 null(下标恒等)
function offsetsOf(cps){
	let flat = true;
	for(let i = 0; i < cps.length; i += 1){ if(cps[i].length !== 1){ flat = false; break; } }
	if(flat){ return null; }
	const off = new Array(cps.length + 1);
	off[0] = 0;
	for(let i = 0; i < cps.length; i += 1){ off[i + 1] = off[i] + cps[i].length; }
	return off;
}
// 码点下标 → UTF-16 下标
const unitAt = (off, k)=>(off ? off[k] : k);
// UTF-16 下标 → 码点下标:第一个 UTF-16 下标 ≥ u 的码点(u 落在码点中间时取后一个码点;超出串尾 → 码点数)
function cpCeil(off, u){
	if(!off){ return u; }
	let lo = 0;
	let hi = off.length - 1;
	if(u >= off[hi]){ return hi; }
	while(lo < hi){
		const mid = (lo + hi) >> 1;
		if(off[mid] < u){ lo = mid + 1; }else{ hi = mid; }
	}
	return lo;
}
// UTF-16 下标恰在码点边界上 → 码点下标;否则 -1
function cpExact(off, u){
	const k = cpCeil(off, u);
	return unitAt(off, k) === u ? k : -1;
}

// 一段文字的比对形态(不依赖查询,可缓存):
//   text 原文 · shown 显示写法(与原文逐码点等长才逐位对齐用;否则 null)·
//   alts { 码点下标: 该位繁体写法字的简体写法(码点数组)} 或 null · key 整串折回简体(只在含繁体写法字时给)或 null ·
//   tc / sc 原文 / 显示写法的码点数组 · off / soff 两者的 UTF-16 下标表(null = 与码点下标恒等)
export function buildMatchForms(text, conv){
	const s = toStr(text);
	const c = conv || {};
	if(!s || !HAN_RE.test(s)){ return { text: s, shown: s, alts: null, key: null, tc: null, sc: null, off: null, soff: null }; }
	const tc = Array.from(s);
	let shown = typeof c.toHant === 'function' ? toStr(c.toHant(s)) : s;
	let sc = shown === s ? tc : Array.from(shown);
	if(sc.length !== tc.length){ shown = null; sc = null; }
	let alts = null;
	let hasTrad = false;
	const isTrad = tradPred(c);
	if(isTrad){
		for(let i = 0; i < tc.length; i += 1){
			const ch = tc[i];
			if(!isHanCp(ch) || !isTrad(ch)){ continue; }
			hasTrad = true;
			const hs = typeof c.hansCandidatesOf === 'function' ? (c.hansCandidatesOf(ch) || []) : [];
			const one = hs.filter((x)=>x && Array.from(x).length === 1);
			if(one.length){ (alts || (alts = {}))[i] = one; }
		}
	}
	let key = null;
	if(hasTrad && typeof c.toMatchKey === 'function'){
		key = toStr(c.toMatchKey(s));
		if(key === s){ key = null; }
	}
	const off = offsetsOf(tc);
	return { text: s, shown: shown === s ? s : shown, alts, key, tc, sc, off, soff: sc === null ? null : (sc === tc ? off : offsetsOf(sc)) };
}

function formsOf(hay, conv){
	if(conv && typeof conv.matchFormsOf === 'function'){ return conv.matchFormsOf(toStr(hay)); }
	return buildMatchForms(hay, conv);
}

// 小写形态(缓存在形态对象上;小写后码点数变了的退回原样,保证逐位对齐)
function lowerOf(f){
	if(f._lower){ return f._lower; }
	const low = (str, cps)=>{
		if(str === null){ return { str: null, cps: null, off: null }; }
		const l = str.toLowerCase();
		if(l === str){ return { str, cps, off: cps ? offsetsOf(cps) : null }; }
		const lc = Array.from(l);
		if(cps && lc.length !== cps.length){ return { str, cps, off: offsetsOf(cps) }; }
		return { str: l, cps: lc, off: offsetsOf(lc) };
	};
	const t = low(f.text, f.tc);
	const sh = f.shown === f.text ? t : low(f.shown, f.sc);
	const out = { text: t.str, tc: t.cps, toff: t.off, shown: sh.str, sc: sh.cps, soff: sh.off, key: f.key === null ? null : f.key.toLowerCase() };
	Object.defineProperty(f, '_lower', { value: out, enumerable: false, configurable: true, writable: true });
	return out;
}
// 不分大小写时与原样时同一形状(text / tc / toff / shown / sc / soff / key)
function exactOf(f){
	return { text: f.text, tc: f.tc, toff: f.off, shown: f.shown, sc: f.sc, soff: f.soff, key: f.key };
}

function hasHan(qc){
	for(let i = 0; i < qc.length; i += 1){ if(isHanCp(qc[i])){ return true; } }
	return false;
}

// 逐位对齐找最早命中位(码点下标,< limit);T 原文、S 显示写法(码点数组)、alts 繁体写法位的简体写法
function alignedIndex(T, S, alts, q, from, prefix, limit){
	const m = q.length;
	const last = prefix ? 0 : T.length - m;
	for(let i = from; i <= last && i < limit; i += 1){
		let ok = true;
		for(let j = 0; j < m; j += 1){
			const qc = q[j];
			const k = i + j;
			if(qc === T[k] || qc === S[k]){ continue; }
			const a = alts ? alts[k] : undefined;
			if(a && a.indexOf(qc) >= 0){ continue; }
			ok = false;
			break;
		}
		if(ok){ return i; }
	}
	return -1;
}

// 命中结果:index / length 都是 hay 上的 UTF-16 量(无命中 index = -1)
const MISS = { index: -1, length: 0 };

// 放宽一档:两边整串折回简体(只改繁体写法字)后再找。命中位置按码点落回原文:折回后与原文逐码点等长才落得回
// (UTF-16 不必等长);落不回时 index -1、hit 仍真(含 → 真,命中位置 → 不计)
function relaxedLocate(hay, q0, conv, { ci, prefix, start }){
	if(!conv || typeof conv.toMatchKey !== 'function'){ return MISS; }
	const h0 = toStr(hay);
	const hk0 = toStr(conv.toMatchKey(h0));
	const qk0 = toStr(conv.toMatchKey(q0));
	if(!qk0){ return { index: 0, length: 0, aligned: true }; }
	const hk = ci ? hk0.toLowerCase() : hk0;
	const qk = ci ? qk0.toLowerCase() : qk0;
	const hc = Array.from(h0);
	const hoff = offsetsOf(hc);
	const kc = Array.from(hk);
	const koff = offsetsOf(kc);
	const i4 = prefix ? (hk.startsWith(qk) ? 0 : -1) : hk.indexOf(qk, unitAt(koff, cpCeil(hoff, start)));
	if(i4 < 0){ return MISS; }
	const k4 = kc.length === hc.length ? cpExact(koff, i4) : -1;
	if(k4 < 0){ return { index: -1, length: 0, aligned: false, hit: true }; }
	const n = Array.from(qk).length;
	const end = Math.min(hc.length, k4 + n);
	return { index: unitAt(hoff, k4), length: unitAt(hoff, end) - unitAt(hoff, k4), aligned: true, hit: true };
}

function locate(hay, query, conv, { ci = true, prefix = false, from = 0, relaxFold = false } = {}){
	const q0 = toStr(query);
	if(!q0){ return { index: 0, length: 0, aligned: true }; }
	const q = ci ? q0.toLowerCase() : q0;
	const f0 = formsOf(hay, conv);
	const T = ci ? lowerOf(f0) : exactOf(f0);
	const start = prefix ? 0 : Math.max(0, from | 0);
	if(prefix && start > 0){ return MISS; }
	// ① 原文直接含(简体模式等价口径;最快):字面命中,UTF-16 长度就是查询长度
	const i0 = prefix ? (T.text.startsWith(q) ? 0 : -1) : T.text.indexOf(q, start);
	if(!f0.tc){
		if(i0 >= 0){ return { index: i0, length: q.length, aligned: true }; }   // 不含中日韩字的串只有字面比
		return relaxFold ? relaxedLocate(hay, q0, conv, { ci, prefix, start }) : MISS;
	}
	// 字面命中换算到 hay 的码点下标(小写后 UTF-16 量变了的,经小写串自己的下标表)
	const lit = i0 >= 0 ? cpExact(T.toff, i0) : -1;
	const qc = Array.from(q);
	const span = (k)=>({ index: unitAt(f0.off, k), length: unitAt(f0.off, k + qc.length) - unitAt(f0.off, k), aligned: true });
	const startCp = cpCeil(f0.off, start);
	if(lit >= 0 && (lit === startCp || !hasHan(qc))){ return span(lit); }
	if(lit < 0 && i0 >= 0 && !hasHan(qc)){ return { index: i0, length: q.length, aligned: true }; }
	if(i0 < 0 && !hasHan(qc)){ return MISS; }
	// ② 显示空间逐位对齐(照屏幕输入 / 输入简体 / 混着输入)
	let best = lit;
	if(T.sc !== null){
		const s1 = prefix ? (T.shown.startsWith(q) ? 0 : -1) : T.shown.indexOf(q, unitAt(T.soff, startCp));
		const i1 = s1 >= 0 ? cpExact(T.soff, s1) : -1;
		if(i1 >= 0 && (best < 0 || i1 < best)){ best = i1; }
		if(best !== startCp){
			const i2 = alignedIndex(T.tc, T.sc, f0.alts, qc, startCp, prefix, best < 0 ? T.tc.length + 1 : best);
			if(i2 >= 0){ best = i2; }
		}
	}
	if(best >= 0){ return span(best); }
	// ③ 原文存的是繁体:整串折回简体后再找一次(折回后与原文逐码点不等长时下标不可用)
	const K = T.key;
	if(K !== null){
		const i3 = prefix ? (K.startsWith(q) ? 0 : -1) : K.indexOf(q, start);
		if(i3 >= 0){
			const kc = Array.from(f0.key);
			if(kc.length !== f0.tc.length){ return { index: -1, length: 0, aligned: false, hit: true }; }
			const k3 = cpExact(offsetsOf(Array.from(K)), i3);
			return k3 >= 0 ? { ...span(k3), hit: true } : { index: -1, length: 0, aligned: false, hit: true };
		}
	}
	// ④ 放宽一档(relaxFold):查询里的繁体写法字也折回
	if(relaxFold){ return relaxedLocate(hay, q0, conv, { ci, prefix, start }); }
	return MISS;
}

// hay 里是否含 query(ci:不分大小写,缺省是;prefix:只认开头;relaxFold:放宽一档,见文件头)
export function matchAcrossScripts(hay, query, conv, opts){
	const r = locate(hay, query, conv, opts);
	return r.index >= 0 || !!r.hit;
}

// 命中位置(hay 的 UTF-16 下标);无命中或命中位置无法落回原文时回 -1。from:从 hay 的第几个 UTF-16 下标起找。
// 命中在 hay 上占的 UTF-16 长度不一定等于查询长度(扩展区字),要长度用 spanAcrossScripts
export function indexAcrossScripts(hay, query, conv, opts){
	const q = toStr(query);
	if(!q){ return 0; }
	return locate(hay, q, conv, opts).index;
}

// 命中位置与长度:{ index, length }(都是 hay 上的 UTF-16 量;无命中 index = -1、length = 0)。高亮 / 找下一处用它
export function spanAcrossScripts(hay, query, conv, opts){
	const q = toStr(query);
	if(!q){ return { index: 0, length: 0 }; }
	const r = locate(hay, q, conv, opts);
	return r.index >= 0 ? { index: r.index, length: r.length } : { index: -1, length: 0 };
}

// 两段逐码点等长的文字之间换算 UTF-16 下标(一段的下标 → 另一段同一码点的下标):
// 原文下标落回已转换的页面文字用(转换逐码点等长、UTF-16 不一定等长)。码点数对不上时按原下标截到 to 的长度
export function mapUnitIndexBetween(from, to, u){
	const a = toStr(from);
	const b = toStr(to);
	const n = Math.max(0, u | 0);
	if(a === b || (a.length === b.length && !/[\uD800-\uDFFF]/.test(a) && !/[\uD800-\uDFFF]/.test(b))){ return Math.min(n, b.length); }
	const ac = Array.from(a);
	const bc = Array.from(b);
	if(ac.length !== bc.length){ return Math.min(n, b.length); }
	return unitAt(offsetsOf(bc), cpCeil(offsetsOf(ac), n));
}

// 整串相等(看到的字 / 原文 / 简繁混写都算同一个名字;relaxFold:两边都折回简体后相等也算,与含 / 命中位置同一档)
export function equalsAcrossScripts(hay, query, conv, { ci = true, relaxFold = false } = {}){
	const h = toStr(hay);
	const q = toStr(query);
	if(h === q){ return true; }
	if(ci && h.toLowerCase() === q.toLowerCase()){ return true; }
	const f0 = formsOf(h, conv);
	if(f0.tc && Array.from(q).length === f0.tc.length){
		const r = locate(h, q, conv, { ci, prefix: true });
		if(r.index === 0 && r.length === h.length){ return true; }
	}
	if(f0.key !== null && (ci ? f0.key.toLowerCase() === q.toLowerCase() : f0.key === q)){ return true; }
	if(relaxFold && conv && typeof conv.toMatchKey === 'function'){
		const hk = toStr(conv.toMatchKey(h));
		const qk = toStr(conv.toMatchKey(q));
		return ci ? hk.toLowerCase() === qk.toLowerCase() : hk === qk;
	}
	return false;
}

// 远端检索(库里简繁混存,没法在这边两边归一)要一并发出的其它写法:
//   简体写法(查询里有繁体写法字时,逐位换成其简体写法)+ 显示写法 + 一简多繁逐位展开的各繁体写法;
//   不含原词本身,不发「整串繁 → 简」(那会把「乾」变成「干」、把「著」变成「着」,远端结果凭空扩张)。
//   组合数上限 limit(缺省 8),显示写法总在最前。
export const QUERY_VARIANT_LIMIT = 8;

function product(options, cap){
	let acc = [''];
	for(let i = 0; i < options.length; i += 1){
		const next = [];
		for(let a = 0; a < acc.length && next.length < cap; a += 1){
			const opts = options[i];
			for(let b = 0; b < opts.length && next.length < cap; b += 1){ next.push(acc[a] + opts[b]); }
		}
		acc = next;
	}
	return acc;
}

export function queryVariantsAcrossScripts(query, conv, { limit = QUERY_VARIANT_LIMIT } = {}){
	const raw = toStr(query).trim();
	const c = conv || {};
	if(!raw || !HAN_RE.test(raw) || typeof c.toHant !== 'function'){ return []; }
	const chars = Array.from(raw);
	const shownStr = toStr(c.toHant(raw));
	const shown = Array.from(shownStr);
	const out = [];
	const push = (v)=>{
		const s = toStr(v).trim();
		if(s && s !== raw && out.indexOf(s) < 0 && out.length < limit){ out.push(s); }
	};
	push(shownStr);
	if(shown.length !== chars.length){ return out; }
	const isTrad = tradPred(c);
	const tradOnly = (ch)=>!!isTrad && !!isTrad(ch);
	const hansOf = (ch)=>(typeof c.hansCandidatesOf === 'function' ? (c.hansCandidatesOf(ch) || []) : []);
	const hantOf = (ch)=>(typeof c.hantCandidatesOf === 'function' ? (c.hantCandidatesOf(ch) || []) : []);
	const uniq = (arr)=>arr.filter((x, i)=>x && arr.indexOf(x) === i);
	// 简体写法:繁体写法字逐位换成简体(优先整串折回时的那个字,即带语境的选择)
	if(chars.some(tradOnly)){
		const key = typeof c.toMatchKey === 'function' ? Array.from(toStr(c.toMatchKey(raw))) : chars;
		const opts = chars.map((ch, i)=>{
			if(!tradOnly(ch)){ return [ch]; }
			const hs = hansOf(ch);
			const first = key.length === chars.length ? key[i] : null;
			const list = uniq([first].concat(hs).filter((x)=>x && x !== ch));
			return list.length ? list : [ch];
		});
		product(opts, limit).forEach(push);
	}
	// 繁体写法:显示字在前,其后是该简体字的其它繁体写法(原文里的繁体写法字照原样)
	const opts = chars.map((ch, i)=>(tradOnly(ch) ? [ch] : uniq([shown[i]].concat(hantOf(ch)))));
	product(opts, limit).forEach(push);
	return out;
}
