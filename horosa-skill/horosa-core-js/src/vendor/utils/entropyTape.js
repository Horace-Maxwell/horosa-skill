// 「真随机记录」的读法:按顺序直接从记录的字节里读出每一个随机决定(一枚棋的正反、洗牌时下一张换到哪)。
// 这里没有伪随机数发生器 —— 结果的每一位都是记录里的系统随机位;同一条记录再读一遍结果必然相同(所以卦例能原样重开)。
//
// 读法(固定下来就不能再改,改了旧卦例重开就不是原来那一卦):
//   · 位序:逐字节、每个字节从最高位到最低位;
//   · int(n):读 ⌈log2 n⌉ 位,读到的数不小于 n 就丢掉重读(拒绝采样,[0, n) 严格等概率;n = 1 不读);
//   · chance(p):p = 0.5 读 1 位;其它读 32 位与 p 比。
// 记录读完了怎么办:正常起的卦取的字节数留足了余量,读不完。只有手改过记录、或起卦后又换了更费随机位的设置(比如换一副张数
// 更多的牌),才会读到头 —— 这时用「记录全文 + 序号」的 SHA-256 接着往下读:仍然只由这条记录决定、同样可以原样重开。
// 一条记录要供几条互不相干的随机流时(塔罗:主洗牌 / 三指定牌 / 切牌 / 计时 / 开钥各操作),每条流在记录里各划一段字节
// (lane.offset / lane.length);lane.domain 是这条流的名字,只在续接时掺进哈希,保证各流续出来的内容互不相同。
// headless shim：上游只用 node-forge 的 SHA-256 与 encodeUtf8。改用 Node 内置 crypto，语义逐字对齐 forge：
// update(s, 'raw') 每个字符取低 8 位为一字节（forge 缺省编码就是 raw）、'utf8' 先编 UTF-8；digest().getBytes() 回「一字符一字节」串；
// util.encodeUtf8 把字符串编成 UTF-8 后同样写成一字符一字节串。tests/test_entropy_tape_shim.py 对真 node-forge 逐字节对拍。
import { createHash } from 'node:crypto';
const _rawBuf = (s) => { const str = String(s); const b = Buffer.alloc(str.length); for(let i = 0; i < str.length; i++){ b[i] = str.charCodeAt(i) & 255; } return b; };
function _sha256Md(){
	const parts = [];
	return {
		update(s, enc){ parts.push(enc === 'utf8' ? Buffer.from(String(s), 'utf8') : _rawBuf(s)); return this; },
		digest(){ const d = createHash('sha256').update(Buffer.concat(parts)).digest(); return { getBytes: () => d.toString('latin1'), toHex: () => d.toString('hex') }; },
	};
}
const forge = { md: { sha256: { create: _sha256Md } }, util: { encodeUtf8: (s) => Buffer.from(String(s), 'utf8').toString('latin1') } };
import { entropySeedBytes } from './trueRandom.js';

function sha256Block(tape, domain, counter){
	const md = forge.md.sha256.create();
	let bin = '';
	for(let i = 0; i < tape.length; i++){ bin += String.fromCharCode(tape[i]); }
	if(domain){ bin += forge.util.encodeUtf8(`|${domain}`); }
	bin += String.fromCharCode((counter >>> 24) & 255, (counter >>> 16) & 255, (counter >>> 8) & 255, counter & 255);
	md.update(bin, 'raw');
	const raw = md.digest().getBytes();
	const out = new Uint8Array(raw.length);
	for(let i = 0; i < raw.length; i++){ out[i] = raw.charCodeAt(i); }
	return out;
}

const MAX_REJECTS = 100000;

// seed 不是真随机记录 → 抛 TypeError(调用方先用 isEntropySeed 分流)。lane 缺省 = 整条记录一条流。
export function entropyReader(seed, lane){
	const tape = entropySeedBytes(seed);
	if(!tape){ throw new TypeError('entropyReader: 不是真随机记录'); }
	const domain = lane && lane.domain ? `${lane.domain}` : '';
	const from = lane ? Math.max(0, Math.floor(Number(lane.offset) || 0)) : 0;
	const to = lane && lane.length !== undefined ? from + Math.max(0, Math.floor(Number(lane.length) || 0)) : tape.length;
	let chunk = tape.subarray(Math.min(from, tape.length), Math.min(to, tape.length));
	let byteIdx = 0;
	let bitIdx = 0;   // 当前字节里已读掉的位数
	let extended = 0;   // 续接过几块(0 = 全部读自记录原文)
	let used = 0;
	const nextBit = ()=>{
		if(byteIdx >= chunk.length){
			chunk = sha256Block(tape, domain, extended);
			extended += 1;
			byteIdx = 0;
			bitIdx = 0;
		}
		const bit = (chunk[byteIdx] >> (7 - bitIdx)) & 1;
		bitIdx += 1;
		if(bitIdx === 8){ bitIdx = 0; byteIdx += 1; }
		used += 1;
		return bit;
	};
	const bits = (k)=>{
		const n = Math.floor(Number(k));
		if(!(n >= 1) || n > 32){ throw new RangeError('entropyReader.bits: 位数须在 1 到 32 之间'); }
		let v = 0;
		for(let i = 0; i < n; i++){ v = v * 2 + nextBit(); }
		return v;
	};
	const int = (n)=>{
		const m = Math.floor(Number(n));
		if(!(m >= 1) || m > 4294967296){ throw new RangeError('entropyReader.int: 上限须在 1 到 2^32 之间'); }
		if(m === 1){ return 0; }
		let k = 0;
		for(let span = m - 1; span > 0; span = Math.floor(span / 2)){ k += 1; }
		let v = 0;
		for(let tries = 0; tries < MAX_REJECTS; tries++){
			v = bits(k);
			if(v < m){ return v; }
		}
		return v % m;   // 只为保证必然返回;走到这里的概率不大于 2^-100000
	};
	return {
		bits,
		int,
		bool: ()=>nextBit() === 1,
		chance: (p)=>{
			const q = Number(p);
			if(q === 0.5){ return nextBit() === 1; }
			return bits(32) < q * 4294967296;
		},
		bitsUsed: ()=>used,
		extended: ()=>extended,
	};
}
