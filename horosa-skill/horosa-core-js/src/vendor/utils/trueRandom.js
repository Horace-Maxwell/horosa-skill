// 真随机源:全站随机起卦 / 抽牌 / 掷骰 / 掷钱的唯一随机入口。
//
// 来源 = 操作系统的随机源(crypto.getRandomValues;macOS 上由内核熵池供给,熵池由芯片的硬件随机数发生器持续注入)。
// 这里不留任何退路:环境没有系统随机源就直接报错,绝不悄悄换成 Math.random 这类按公式推出来的伪随机数。
//
// 两种用法:
//   · 当场定结果(六爻掷钱、骰子这类把结果本身存下来的):randomInt / randomBit,每个随机决定各取一次系统随机数;
//   · 结果要能原样重开(塔罗、灵棋、地占、五兆、荆诀、太玄这类按「种子」重排的):newEntropySeed 取一段系统随机字节,
//     以「真随机记录」(tr1- 加十六进制)存进卦例。引擎按顺序直接读这段字节来定每一个随机决定(见 entropyTape.js 与
//     Python 侧 astrostudy/truerandom.py),重开卦例是回放这段记录,中间不经过伪随机数发生器。
// 手动种子、时间起卦、生辰种子本来就是「同样的输入必出同样的结果」的确定性起法,不归这里管,照旧。

export const ENTROPY_SEED_PREFIX = 'tr1-';
const ENTROPY_SEED_RE = /^tr1-(?:[0-9a-f]{2})+$/i;
const UINT32_SPAN = 4294967296;
const CHUNK = 65536;   // getRandomValues 单次上限

function systemRandom(){
	const g = typeof globalThis !== 'undefined' ? globalThis : (typeof window !== 'undefined' ? window : null);
	const c = g && g.crypto;
	if(c && typeof c.getRandomValues === 'function'){ return c; }
	throw new Error('本机环境没有系统随机源,无法随机起卦');
}

// n 个系统随机字节
export function randomBytes(n){
	const len = Math.floor(Number(n));
	if(!(len >= 1)){ throw new RangeError('randomBytes: 字节数须为正整数'); }
	const c = systemRandom();
	const out = new Uint8Array(len);
	for(let off = 0; off < len; off += CHUNK){
		c.getRandomValues(out.subarray(off, Math.min(len, off + CHUNK)));
	}
	return out;
}

export function randomUint32(){
	const a = new Uint32Array(1);
	systemRandom().getRandomValues(a);
	return a[0];
}

// [0, n) 上严格等概率的整数(拒绝采样:落在「不是 n 的整数倍」那截尾巴里的随机数丢掉重取,不用取模凑,免得小数字多出现一点)。
export function randomInt(n){
	const m = Math.floor(Number(n));
	if(!(m >= 1) || m > UINT32_SPAN){ throw new RangeError('randomInt: 上限须在 1 到 2^32 之间'); }
	if(m === 1){ return 0; }
	const limit = UINT32_SPAN - (UINT32_SPAN % m);
	for(;;){
		const v = randomUint32();
		if(v < limit){ return v % m; }
	}
}

// 一枚钱 / 一枚棋:0 或 1 各半
export function randomBit(){
	return randomUint32() & 1;
}

function toHex(bytes){
	let s = '';
	for(let i = 0; i < bytes.length; i++){ s += (bytes[i] < 16 ? '0' : '') + bytes[i].toString(16); }
	return s;
}

// 取 nBytes 个系统随机字节,写成「真随机记录」
export function newEntropySeed(nBytes){
	return ENTROPY_SEED_PREFIX + toHex(randomBytes(nBytes));
}

export function isEntropySeed(seed){
	return typeof seed === 'string' && ENTROPY_SEED_RE.test(seed);
}

// 记录里的原始字节(不是真随机记录 → null)
export function entropySeedBytes(seed){
	if(!isEntropySeed(seed)){ return null; }
	const hex = seed.slice(ENTROPY_SEED_PREFIX.length);
	const out = new Uint8Array(hex.length / 2);
	for(let i = 0; i < out.length; i++){ out[i] = parseInt(hex.substr(i * 2, 2), 16); }
	return out;
}

// 能拿来原样重开一卦的种子:真随机记录,或整数种子(手动种子 / 旧卦例)。
export function isReplayableSeed(seed){
	if(isEntropySeed(seed)){ return true; }
	if(seed === undefined || seed === null || seed === '' || typeof seed === 'boolean'){ return false; }
	return Number.isFinite(Number(seed));
}

// 手填种子框里的字:粘进来的是真随机记录就原样留着;否则只取数字,夹到 [0, max]。
export function parseManualSeedInput(text, max){
	const raw = `${text === undefined || text === null ? '' : text}`.trim();
	if(isEntropySeed(raw)){ return raw.toLowerCase(); }
	const digits = raw.replace(/\D/g, '');
	if(!digits){ return 0; }
	const n = Number(digits);
	const cap = Number.isFinite(max) ? max : 2147483647;
	return Number.isFinite(n) ? Math.min(cap, n) : cap;
}

// 界面 / 导出里写种子用:真随机记录很长,只写开头 8 位作短指纹(窄卡片里不折行;全文另放悬停提示或种子框);其它种子原样。
export function seedDisplayText(seed){
	if(seed === undefined || seed === null){ return ''; }
	if(!isEntropySeed(seed)){ return `${seed}`; }
	const hex = seed.slice(ENTROPY_SEED_PREFIX.length).toLowerCase();
	return hex.length <= 16 ? `真随机 ${hex}` : `真随机 ${hex.slice(0, 8)}…`;
}
