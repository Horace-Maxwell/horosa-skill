// 通用洗牌(可复现 + size 感知)。
// 随机抽牌 = 真随机:种子是一段「真随机记录」(系统随机源取的原始字节,见 utils/trueRandom.js)时,洗牌的每一步、每张牌的正逆
// 都直接读记录里的随机位(Fisher–Yates,拒绝采样),不经伪随机数发生器;重开卦例是回放这条记录。
// 生辰种子 / 手动种子是确定性起法:SHA-256(seed)→mulberry32→Fisher–Yates(size)→逐张定逆位。
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
import { isEntropySeed, newEntropySeed } from '../../utils/trueRandom.js';
import { entropyReader } from '../../utils/entropyTape.js';

// 一条真随机记录里各条随机流各占的一段:[起始字节, 长度]。互不重叠,一条流读多读少不影响别的流。
// 长度按「最大的牌组 + 拒绝采样的余量」留足:主洗牌 97 张连正逆平均约 110 字节;三指定牌只定前三张、切牌只定一张;
// 计时法洗 52–56 张小牌平均约 45 字节;开钥五操作各自整副重洗。划定后不能再改(改了旧卦例重开就不是原来那副牌)。
const LANE_MAIN = [0, 192];
const ENTROPY_LANES = {
	fof: [192, 32],
	cut: [224, 32],
	timing: [256, 128],
	ook1: [384, 192],
	ook2: [576, 192],
	ook3: [768, 192],
	ook4: [960, 192],
	ook5: [1152, 192],
};
export const BASE_ENTROPY_BYTES = 384;   // 主洗牌 + 三指定牌 + 切牌 + 计时(短记录的长度)
const FULL_ENTROPY_BYTES = 1344;   // 再加开钥五操作
const SUB_SEED_RE = /^(tr1-(?:[0-9a-f]{2})+)\|([A-Za-z0-9_]+)$/i;

// 随机抽一副牌要取的真随机记录:一律取满(含开钥五操作那五段)。
// 页面一打开就按当前牌阵抽一次,用户再换到开钥牌阵是常见走法:换牌阵只拿原记录重算,记录若只有前四段(BASE_ENTROPY_BYTES),
// 开钥五次整副重洗就全部落在续接上,没有一位来自系统随机源。取满以后换到哪个牌阵都读得到记录原文;前四段的位置不变。
// 短记录照样能重开(读法相同;换到开钥时走续接)。
export function newTarotRandomSeed(){
	return newEntropySeed(FULL_ENTROPY_BYTES);
}

// seed(或「记录|子流名」)若指向真随机记录 → 该流的读取器;否则 null(走确定性种子)。
function entropyStream(seed){
	if(isEntropySeed(seed)){
		return entropyReader(seed, { offset: LANE_MAIN[0], length: LANE_MAIN[1], domain: '' });
	}
	const m = typeof seed === 'string' ? SUB_SEED_RE.exec(seed) : null;
	if(!m){ return null; }
	const lane = ENTROPY_LANES[m[2]];
	// 没划过段的子流名:整条流由「记录 + 流名」确定性续出(仍只由这条记录决定)
	return entropyReader(m[1], lane ? { offset: lane[0], length: lane[1], domain: m[2] } : { offset: 0, length: 0, domain: m[2] });
}

// 读记录洗牌:正向 Fisher–Yates(第 i 位从剩下的牌里等概率挑一张),前 k 位只由前 k 次读取决定;
// take 给出时只定前 take 位(调用方只用这几位),其余位不读。
function shuffleFromRecord(reader, size, usesReversals, p, take){
	const order = Array.from({ length: size }, (_, i) => i);
	const settle = take === undefined ? size - 1 : Math.min(size - 1, Math.max(0, Math.floor(take)));
	for(let i = 0; i < settle; i++){
		const j = i + reader.int(size - i);
		const tmp = order[i];
		order[i] = order[j];
		order[j] = tmp;
	}
	const facing = take === undefined ? size : Math.min(size, Math.max(0, Math.floor(take)));
	const reversed = order.map((_, i) => {
		if(!usesReversals || i >= facing || !(p > 0)){ return false; }
		return p >= 1 ? true : reader.chance(p);
	});
	// entropy:这次读了记录多少位、有没有读到头续接(0 = 全部读自记录原文);只供自检,不参与排盘。
	return { order, reversed, entropy: { bitsUsed: reader.bitsUsed(), extended: reader.extended() } };
}

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
//   opts.take(可选):调用方只用前几位时给出;只对真随机记录生效(确定性种子照旧整副洗完,字节不变)。
export function shuffle(seed, opts){
	const o = opts || {};
	const size = Number.isFinite(o.size) && o.size > 0 ? Math.floor(o.size) : 78;
	const usesReversals = o.usesReversals === undefined ? true : !!o.usesReversals;
	const p = Number.isFinite(o.pReversed) ? o.pReversed : 0.5;
	const stream = entropyStream(seed);
	if(stream){ return shuffleFromRecord(stream, size, usesReversals, p, o.take); }
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
