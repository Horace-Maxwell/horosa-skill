// 神数正传 · 邵子神数 —— 前端本地确定性引擎（零后端 / 零随机 / 全整数）。
//
// 条文序数 = 卦数(查 64卦数表，出百十位) + 气数(查 96气数表，出千个位)，共 6144 条(1111~12888)。
// 数表见 data/zhengchuanShaoziTables.json（由古籍机读录入）。条文正文库按需动态载入。
//
// 五基础数据：先天命卦 / 天命数 / 地命数 / 人命数 / 后天命卦
// 断本命五项：性情 · 祖业 · 财运 · 职业 · 寿命
//
// 复用（不重写）：
//   · 装卦(六亲/世应) ← components/gua/liuyaoFacade（已验：噬嗑巽宫五世 → 世在五爻己未、
//     爻1庚子父母、爻5己未妻财、爻4己酉官鬼，与古籍算例逐项吻合）
//   · 太玄配数 ← tiebanFrameworkLocal（与古籍太玄配数表逐字同）
//
// 已对古籍算例逐步验证（天数29→减25→余4→巽；地数16→取个位6→乾；阴男→天风姤；
//   天命数3522/地命数2562/人命数3534；后天火雷噬嗑三爻动→离为火）。
import TABLES from './data/zhengchuanShaoziTables.json' with { type: 'json' };
import { taixuanPeishu } from './tiebanFrameworkLocal.js';
import { guaFromLines, analyzeLiuyao } from '../gua/liuyaoFacade.js';

const GAN = ['甲', '乙', '丙', '丁', '戊', '己', '庚', '辛', '壬', '癸'];
const ZHI = ['子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥'];
const MONTH_NAMES = ['正月', '二月', '三月', '四月', '五月', '六月', '七月', '八月', '九月', '十月', '十一月', '十二月'];
const DAY_NAMES = ['初一', '初二', '初三', '初四', '初五', '初六', '初七', '初八', '初九', '初十',
	'十一', '十二', '十三', '十四', '十五', '十六', '十七', '十八', '十九', '廿十',
	'廿一', '廿二', '廿三', '廿四', '廿五', '廿六', '廿七', '廿八', '廿九', '三十'];

// 八宫纳甲（内卦前3 / 外卦后3，自下而上）。公有易学常数。
const NAJIA = {
	乾: ['甲子', '甲寅', '甲辰', '壬午', '壬申', '壬戌'],
	坤: ['乙未', '乙巳', '乙卯', '癸丑', '癸亥', '癸酉'],
	震: ['庚子', '庚寅', '庚辰', '庚午', '庚申', '庚戌'],
	巽: ['辛丑', '辛亥', '辛酉', '辛未', '辛巳', '辛卯'],
	坎: ['戊寅', '戊辰', '戊午', '戊申', '戊戌', '戊子'],
	離: ['己卯', '己丑', '己亥', '己酉', '己未', '己巳'],
	艮: ['丙辰', '丙午', '丙申', '丙戌', '丙子', '丙寅'],
	兌: ['丁巳', '丁卯', '丁丑', '丁亥', '丁酉', '丁未'],
};
const TRI_BITS = { 乾: [1, 1, 1], 兌: [1, 1, 0], 離: [1, 0, 1], 震: [1, 0, 0], 巽: [0, 1, 1], 坎: [0, 1, 0], 艮: [0, 0, 1], 坤: [0, 0, 0] };
const BITS_TRI = {};
Object.keys(TRI_BITS).forEach((t) => { BITS_TRI[TRI_BITS[t].join('')] = t; });

export const SHAOZI_META = TABLES._meta || {};

function triOf(bits3) { return BITS_TRI[bits3.join('')] || null; }

/** 重卦六爻纳甲：下卦取该八卦之内卦纳甲、上卦取其外卦纳甲。 */
export function najiaOf(lines) {
	const lo = triOf(lines.slice(0, 3));
	const up = triOf(lines.slice(3, 6));
	if (!lo || !up) return null;
	return [...NAJIA[lo].slice(0, 3), ...NAJIA[up].slice(3, 6)];
}

/** 天数余数法：<25 取个位（10→1、20→2）；=25 取5；>25 先减25 再依前法。 */
export function tianRemainder(n) {
	let v = n;
	while (v > 25) v -= 25;
	if (v === 25) return 5;
	if (v === 10) return 1;
	if (v === 20) return 2;
	return v % 10;
}

/** 地数余数法：<30 取个位（10→1、20→2）；=30 取3；>30 先减30 再依前法。 */
export function diRemainder(n) {
	let v = n;
	while (v > 30) v -= 30;
	if (v === 30) return 3;
	if (v === 10) return 1;
	if (v === 20) return 2;
	return v % 10;
}

/** 余数为 5 时河洛配卦表无对应，另按元运×性别定。 */
function guaOfRemainder(r, { yuan, gender, yangYear }) {
	if (r !== 5) return TABLES.heluoGua[String(r)] || null;
	if (yuan === 'shang') return gender === '男' ? '艮' : '坤';
	if (yuan === 'xia') return gender === '男' ? '離' : '兌';
	const groupA = (yangYear && gender === '男') || (!yangYear && gender === '女');   // 阳男阴女
	return groupA ? '艮' : '坤';
}

/**
 * 先天命卦：四柱配数 → 奇数和＝天数、偶数和＝地数 → 各取余数配卦
 * → 阳男阴女 天上地下；阴男阳女 天下地上。
 */
export function xianTianMingGua({ pillars, gender, yuan = 'zhong' }) {
	// 入参守卫：四柱须齐且各为真干支。只查「二字」不够 —— 'XX' 之类会混过，致天地数皆 0、
	// 配卦得 null，而后于 [...TRI_BITS[lo]] 处抛「not iterable」。
	if (!Array.isArray(pillars) || pillars.length < 4
		|| pillars.some((x) => !x || GAN.indexOf(`${x}`[0]) < 0 || ZHI.indexOf(`${x}`[1]) < 0)) return null;
	const odd = [];
	const even = [];
	pillars.forEach((gz) => {
		const g = TABLES.ganNum[gz[0]];
		if (g != null) (g % 2 ? odd : even).push({ src: gz[0], n: g });
		const zs = TABLES.zhiNum[gz[1]] || [];
		zs.forEach((n) => (n % 2 ? odd : even).push({ src: gz[1], n }));
	});
	const tian = odd.reduce((a, b) => a + b.n, 0);
	const di = even.reduce((a, b) => a + b.n, 0);
	const yangYear = GAN.indexOf(pillars[0][0]) % 2 === 0;
	const tr = tianRemainder(tian);
	const dr = diRemainder(di);
	const tianGua = guaOfRemainder(tr, { yuan, gender, yangYear });
	const diGua = guaOfRemainder(dr, { yuan, gender, yangYear });
	const groupA = (yangYear && gender === '男') || (!yangYear && gender === '女');
	const up = groupA ? tianGua : diGua;
	const lo = groupA ? diGua : tianGua;
	if (!TRI_BITS[lo] || !TRI_BITS[up]) return null;   // 天/地数配卦不得 → 显式返 null，不带 undefined 往下展开
	const lines = [...TRI_BITS[lo], ...TRI_BITS[up]];
	return {
		odd, even, tian, di, tianRem: tr, diRem: dr, tianGua, diGua,
		yangYear, groupA, up, lo, lines, gua: guaFromLines(lines),
	};
}

/** 天命数＝父岁余×1000＋父岁商×10＋502；整除时＝(商−1)×10＋12502 */
export function tianMingShu(fatherAge) {
	const q = Math.floor(fatherAge / 12);
	const r = fatherAge % 12;
	return r === 0
		? { q, r, num: (q - 1) * 10 + 12502, special: true }
		: { q, r, num: r * 1000 + q * 10 + 502, special: false };
}

/** 地命数＝母岁余×1000＋(母岁商+4)×10＋502；整除时＝(商+3)×10＋12502 */
export function diMingShu(motherAge) {
	const q = Math.floor(motherAge / 12);
	const r = motherAge % 12;
	return r === 0
		? { q, r, num: (q + 3) * 10 + 12502, special: true }
		: { q, r, num: r * 1000 + (q + 4) * 10 + 502, special: false };
}

/** 人命数＝卦数(生辰卦位→64卦数表) + 气数(生辰声音→96气数表) */
export function renMingShu({ lunarMonth, lunarDay, isLeapMonth }) {
	const mName = MONTH_NAMES[lunarMonth - 1];
	const key = Object.keys(TABLES.birthMonthGua).find((k) => {
		const leap = k.indexOf('閏') >= 0 || k.indexOf('闰') >= 0;
		return leap === !!isLeapMonth && k.replace(/[閏闰]/g, '').indexOf(mName) >= 0;
	});
	const gua = key ? TABLES.birthMonthGua[key] : null;
	const guaNum = gua ? TABLES.gua64Num[gua] : null;
	const parity = lunarMonth % 2 ? 'odd' : 'even';
	const dName = DAY_NAMES[lunarDay - 1];
	const sound = (TABLES.birthDaySound[parity] || {})[dName] || null;
	const qiNum = sound ? TABLES.qi96Num[sound] : null;
	return {
		monthKey: key, gua, guaNum, parity, dayName: dName, sound, qiNum,
		num: (guaNum != null && qiNum != null) ? guaNum + qiNum : null,
	};
}

const digitsSum = (n) => String(n).split('').reduce((a, c) => a + Number(c), 0);

/**
 * 后天命卦：天命数四位和＋天数 ÷9 配连山卦（阳男阴女作上卦、阴男阳女作下卦）；
 * 地命数四位和＋地数 ÷9 同理反之；人命数四位和 ÷6 ＝动爻。
 * 连山九槽：后天命卦除九取余需 9 槽，而连山仅八卦，故古籍此表必有一卦重出；余 0 按第 9 槽。
 */
export function houTianMingGua({ tianMing, diMing, renMing, tian, di, groupA }) {
	// 🔴 入参守卫 —— 与 xianTianMingGua 同则(此前独它没有,遂于下方 [...TRI_BITS[lo]] 处抛
	//    「not iterable」:父母年龄为 0/负/非数时，三命数算不出 → 连山配卦得 undefined)。
	if (!Number.isFinite(tianMing) || !Number.isFinite(diMing) || !Number.isFinite(renMing)
		|| !Number.isFinite(tian) || !Number.isFinite(di)) return null;
	const a = digitsSum(tianMing) + tian;
	const b = digitsSum(diMing) + di;
	const ra = a % 9;
	const rb = b % 9;
	const ga = TABLES.lianshanGua[String(ra === 0 ? 9 : ra)];
	const gb = TABLES.lianshanGua[String(rb === 0 ? 9 : rb)];
	const up = groupA ? ga : gb;
	const lo = groupA ? gb : ga;
	if (!TRI_BITS[lo] || !TRI_BITS[up]) return null;   // 连山表取不着 → 不臆造一个卦
	const lines = [...TRI_BITS[lo], ...TRI_BITS[up]];
	const dsum = digitsSum(renMing);
	const dr = dsum % 6;
	const dongYao = dr === 0 ? 6 : dr;
	const bianLines = lines.slice();
	bianLines[dongYao - 1] = bianLines[dongYao - 1] ? 0 : 1;
	return {
		tianCalc: { digits: digitsSum(tianMing), plus: tian, sum: a, rem: ra, gua: ga },
		diCalc: { digits: digitsSum(diMing), plus: di, sum: b, rem: rb, gua: gb },
		up, lo, lines, gua: guaFromLines(lines),
		dongCalc: { digits: dsum, rem: dr }, dongYao,
		bianLines, bianGua: guaFromLines(bianLines),
	};
}

/** 装卦：逐爻 纳甲干支 + 六亲 + 世应（六亲/世应复用仓内六爻引擎） */
export function dressGua(lines, dongYao) {
	const gua = guaFromLines(lines);
	if (!gua) return null;
	const an = analyzeLiuyao(gua, dongYao ? [dongYao] : [], {}, {});
	const nj = najiaOf(lines);
	const yaos = (an.yaos || []).map((y, i) => ({ ...y, gz: nj[i] }));
	return { gua, yaos, palaceType: an.palaceType, palace: gua.house && gua.house.name };
}

const findYao = (yaos, pred) => yaos.find(pred) || null;

/**
 * 取某六亲之爻：一卦可有同一六亲两爻（如噬嗑有妻财两爻），须择一。
 * 规则＝**取最近世爻者**。三例反解 3/3 全中：
 *   · 算例D 妻财：世在五爻，候选 爻3/爻5 → 取爻5 己未（距0）
 *   · 通例 父母：世在三爻，候选 爻3/爻6 → 取爻3 丁丑（距0）
 *   · 通例 官鬼：世在三爻，候选 爻1/爻4 → 取爻4 庚午（距1，另一距2）
 * 与另一传本所载「推算父母要以最近世爻的父母爻为准」同规，两源互证。
 */
function pickByLiuqin(yaos, names) {
	const cands = yaos.filter((y) => names.indexOf(y.liuqin) >= 0);
	if (!cands.length) return null;
	if (cands.length === 1) return cands[0];
	const shi = yaos.find((y) => y.shiYing === '世');
	if (!shi) return cands[cands.length - 1];
	return cands.slice().sort((a, b) => Math.abs(a.pos - shi.pos) - Math.abs(b.pos - shi.pos))[0];
}

/** 性情：世爻五行本数 + 人命数 → ÷12 取余 → 配动爻位 → 性情声音卦位表 */
export function xingQing(dress, renMing, dongYao) {
	const shi = findYao(dress.yaos, (y) => y.shiYing === '世');
	if (!shi) return null;
	const ben = TABLES.wuxingBen[shi.wuxing];
	const sum = ben + renMing;
	const rem = sum % 12 || 12;   // 表键 1..12 无 0 行 → 余 0 作 12(否则键 12 成死码、余 0 静默失值)
	const yaoName = ['初爻', '二爻', '三爻', '四爻', '五爻', '六爻'][dongYao - 1];
	const sound = (TABLES.xingqingSound[String(rem)] || {})[yaoName] || null;
	const gua = (TABLES.xingqingSound['所屬卦位'] || {})[yaoName] || null;
	const guaNum = gua ? TABLES.gua64Num[gua] : null;
	const qiNum = sound ? TABLES.qi96Num[sound] : null;
	return {
		shiYao: shi, ben, sum, rem, yaoName, sound, gua, guaNum, qiNum,
		num: (guaNum != null && qiNum != null) ? guaNum + qiNum : null,
	};
}

/** 祖业：父母爻五行生数 + 人命数 → ÷12 取余 → 配父母爻五行 → 祖业卦位 → 配月支 → 祖业声音 */
export function zuYe(dress, renMing, monthZhi) {
	const fu = pickByLiuqin(dress.yaos, ['父母']);
	if (!fu) return null;
	const sheng = TABLES.wuxingSheng[fu.wuxing];
	const sum = sheng + renMing;
	const rem = sum % 12 || 12;   // 同上:表键 1..12 无 0 行
	const gua = (TABLES.zuyeGua[String(rem)] || {})[fu.wuxing] || null;
	const sound = gua ? (TABLES.zuyeSound[gua] || {})[monthZhi] : null;
	const guaNum = gua ? TABLES.gua64Num[gua] : null;
	const qiNum = sound ? TABLES.qi96Num[sound] : null;
	return {
		fuYao: fu, sheng, sum, rem, gua, sound, guaNum, qiNum,
		num: (guaNum != null && qiNum != null) ? guaNum + qiNum : null,
	};
}

/** 太玄玉景：爻干支太玄配数 + 人命数 → ÷81 取商余 → 余数定太玄首 → 商÷9 定爻 → 归藏卦数 */
export function taiXuanPath(gz, renMing) {
	const t = taixuanPeishu(gz[0]) + taixuanPeishu(gz[1]);
	const sum = t + renMing;
	const q = Math.floor(sum / 81);
	const r = sum % 81 || 81;     // 玉景八十一首,表键 1..81 无 0 行 → 余 0 作 81
	const shou = TABLES.taixuanYuJing[String(r)] || null;
	const yr = q % 9;
	const yaoIdx = yr === 0 ? 9 : yr;
	const guizang = shou ? shou.yao[yaoIdx - 1] : null;
	return { peishu: t, sum, quotient: q, rem: r, shou, yaoIdx, guizang };
}

/** 财运：妻财爻走太玄玉景 → 归藏数配财运卦位 → 配财爻五行查财运声音 */
export function caiYun(dress, renMing) {
	const cai = pickByLiuqin(dress.yaos, ['妻財', '妻财']);
	if (!cai) return null;
	const p = taiXuanPath(cai.gz, renMing);
	const gua = p.guizang != null ? TABLES.caiyunGua[String(p.guizang)] : null;
	const gzName = p.guizang != null ? ({ 1: '坤', 2: '巽', 3: '離', 4: '兌', 5: '中宮', 6: '艮', 7: '坎', 8: '震', 9: '乾' })[p.guizang] : null;
	const sound = (gua && gzName) ? ((TABLES.caiyunSound[gua] || {})[gzName] || {})[cai.wuxing] : null;
	const guaNum = gua ? TABLES.gua64Num[gua] : null;
	const qiNum = sound ? TABLES.qi96Num[sound] : null;
	return {
		caiYao: cai, ...p, gua, guizangGua: gzName, sound, guaNum, qiNum,
		num: (guaNum != null && qiNum != null) ? guaNum + qiNum : null,
	};
}

/** 职业：官鬼爻走太玄玉景 → 归藏数配职业卦位 → 按官鬼爻所在卦爻位查职业声音 */
export function zhiYe(dress, renMing) {
	const guan = pickByLiuqin(dress.yaos, ['官鬼']);
	if (!guan) return null;
	const p = taiXuanPath(guan.gz, renMing);
	const gua = p.guizang != null ? TABLES.zhiyeGua[String(p.guizang)] : null;
	const posName = guan.pos <= 2 ? '下爻' : (guan.pos <= 4 ? '中爻' : '上爻');
	const sound = (TABLES.zhiyeSound[posName] || {})[guan.zhi] || null;
	const guaNum = gua ? TABLES.gua64Num[gua] : null;
	const qiNum = sound ? TABLES.qi96Num[sound] : null;
	return {
		guanYao: guan, ...p, gua, posName, sound, guaNum, qiNum,
		num: (guaNum != null && qiNum != null) ? guaNum + qiNum : null,
	};
}

/** 条文正文库按需动态载入（体积大、非算法必需；条文号同步可得，正文到达后填）。 */
let versesPromise = null;
export function loadShaoziVerses() {
	if (!versesPromise) {
		versesPromise = import('./data/zhengchuanShaoziVerses.json', { with: { type: 'json' } })
			.then((m) => m.default || m);
	}
	return versesPromise;
}

/** 全链：五基础数据 + 断本命四项（寿命另计） */
export function calcShaozi(input) {
	const { pillars, gender, fatherAge, motherAge, lunarMonth, lunarDay, isLeapMonth, yuan } = input || {};
	const xt = xianTianMingGua({ pillars, gender, yuan });
	if (!xt) return null;   // 四柱不全/坏值 → 显式返 null，不半途而废地往下算
	const tm = tianMingShu(fatherAge);
	const dm = diMingShu(motherAge);
	const rm = renMingShu({ lunarMonth, lunarDay, isLeapMonth });
	if (rm.num == null) return { school: 'shaozi', input, xianTian: xt, tianMing: tm, diMing: dm, renMing: rm, notes: ['人命数不可得（生辰查表未命中）'] };
	const ht = houTianMingGua({
		tianMing: tm.num, diMing: dm.num, renMing: rm.num,
		tian: xt.tian, di: xt.di, groupA: xt.groupA,
	});
	// 🔴 后天命卦不可得（父母年龄为 0/负/非数 → 三命数算不出）→ 照上方「人命数不可得」之同款，
	//    出半盘并明说其由，不再直取 ht.lines（此前如此，遂抛「reading 'lines' of null」）。
	if (!ht) {
		return {
			school: 'shaozi', input, xianTian: xt, tianMing: tm, diMing: dm, renMing: rm,
			notes: ['后天命卦不可得（三命数未全，多因父母年龄未录或非正数）'],
		};
	}
	const dress = dressGua(ht.lines, ht.dongYao);
	return {
		school: 'shaozi', input,
		xianTian: xt, tianMing: tm, diMing: dm, renMing: rm, houTian: ht, dress,
		benming: {
			性情: xingQing(dress, rm.num, ht.dongYao),
			祖业: zuYe(dress, rm.num, pillars[1][1]),
			财运: caiYun(dress, rm.num),
			职业: zhiYe(dress, rm.num),
		},
		notes: [],
	};
}

export default calcShaozi;
