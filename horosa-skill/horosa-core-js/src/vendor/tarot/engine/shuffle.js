// 通用确定性洗牌(可复现 + size 感知)。SHA-256(seed)→mulberry32→Fisher–Yates(size)→逐张定逆位。
// 兼容铁律:size=78、usesReversals、pReversed=0.5 时与旧 tarotShuffle 字节一致(order 与 reversed 全等)。
// 逆位谓词 rng()>=(1-p)(p=0.5 即旧 >=0.5)。逆位关=同 order、reversed 全 false(只改朝向不改抽到的牌)。
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

function sha256Hex(str){
	const md = forge.md.sha256.create();
	md.update(String(str === undefined || str === null ? '' : str), 'utf8');
	return md.digest().toHex();
}

function mulberry32(a){
	return function(){
		let t = (a += 0x6D2B79F5);
		t = Math.imul(t ^ (t >>> 15), t | 1);
		t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
		return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
	};
}

// 主洗牌:返回 { order:[size 索引排列], reversed:[size bool] }。
//   opts.size(默认 78) · opts.usesReversals(默认 true) · opts.pReversed(默认 0.5)
export function shuffle(seed, opts){
	const o = opts || {};
	const size = Number.isFinite(o.size) && o.size > 0 ? Math.floor(o.size) : 78;
	const usesReversals = o.usesReversals === undefined ? true : !!o.usesReversals;
	const p = Number.isFinite(o.pReversed) ? o.pReversed : 0.5;
	const hex = sha256Hex(seed);
	const seedNum = parseInt(hex.substring(0, 8), 16) >>> 0;
	const rng = mulberry32(seedNum);
	const order = Array.from({ length: size }, (_, i) => i);
	for(let i = order.length - 1; i > 0; i--){
		const j = Math.floor(rng() * (i + 1));
		const tmp = order[i];
		order[i] = order[j];
		order[j] = tmp;
	}
	// 逆位:逐张抽 rng(消费序列与旧版一致),再据 usesReversals 决定是否生效;关时同 order 仅朝向全正。
	const threshold = 1 - p;
	const reversed = order.map(() => {
		const v = rng() >= threshold;
		return usesReversals ? v : false;
	});
	return { order, reversed };
}

// 旧门面:tarotShuffle(seed) == shuffle(seed,{size:78,usesReversals:true,pReversed:0.5})
export function tarotShuffle(seed){
	return shuffle(seed, { size: 78, usesReversals: true, pReversed: 0.5 });
}

export default shuffle;
