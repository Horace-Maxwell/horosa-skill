// 神数正传 · 铁板神数 —— 前端本地确定性引擎（零后端 / 零随机）。
// 数表见 data/zhengchuanTiebanTables.json（由古籍数表机读录入，随本模块静态载入）。
// 条文正文库另行按需动态载入（体积大、非算法必需），见 loadTiebanVerses()。
//
// 算法链（本命）：月命数 → 时命数 → 先天命数 → 五音 → 五音命数 → 日命数 → 时运数
//   → 考刻 → 本命数 → 十二辟卦 → 本命条文（辟卦基数 + 序数 + 项目数）
// 算法链（流年）：天四声（先天命数运限表）→ 后天命数 → 流年标记 → 流年字母 → 流年条文 → 条文校正
//
// 已对古籍三个算例逐步验证：本命链 3/3 全通过；流年链算例一 40/40 行全通过。
// 古籍自身的已知讹误（算例读串邻列、算例值不在表内、算例三流年误用他例年柱、
//   偶数岁 72-80 的第 11-20 校正数整块未印）见 golden 测试与 _meta.gaps，
//   一律以「表为准、算例为误」处置，缺格显式标缺、不外推。
import TABLES from './data/zhengchuanTiebanTables.json' with { type: 'json' };
import { nayinElement } from '../canping/canpingLocal.js';

const GAN = ['甲', '乙', '丙', '丁', '戊', '己', '庚', '辛', '壬', '癸'];
const ZHI = ['子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥'];
const MONTH_NAMES = ['正月', '二月', '三月', '四月', '五月', '六月', '七月', '八月', '九月', '十月', '十一月', '十二月'];
const ZHI_GROUPS = ['寅午戌', '申子辰', '巳酉丑', '亥卯未'];

export const TIEBAN_META = TABLES._meta || { gaps: [], ambiguous: [] };

// 字母 → 校正数（奇/偶两套字母互斥），反查表：校正数 → 字母
const PARITY = TABLES.liunianLetterParity || { odd: [], even: [] };
const ODD_SET = new Set(PARITY.odd);
const FIX_TO_LETTER = { odd: {}, even: {} };
Object.keys(TABLES.liunianVerseMain.letterToFix).forEach((ch) => {
	const p = ODD_SET.has(ch) ? 'odd' : 'even';
	FIX_TO_LETTER[p][TABLES.liunianVerseMain.letterToFix[ch]] = ch;
});

function gzIndex(gz) {
	const gi = GAN.indexOf(gz[0]);
	const zi = ZHI.indexOf(gz[1]);
	if (gi < 0 || zi < 0) return -1;
	for (let i = 0; i < 60; i += 1) {
		if (i % 10 === gi && i % 12 === zi) return i;
	}
	return -1;
}

function gzAt(i) {
	const n = ((i % 60) + 60) % 60;
	return GAN[n % 10] + ZHI[n % 12];
}

/** 逢闰月按下一个月计（古籍明定）。lunarMonth 为 1-12。 */
function effectiveMonthName(lunarMonth, isLeapMonth) {
	const m = isLeapMonth ? lunarMonth + 1 : lunarMonth;
	return MONTH_NAMES[((m - 1) % 12 + 12) % 12];
}

/**
 * 本命链。
 * @param {object} p 四柱 yearGz/dayGz/hourGz、gender('男'|'女')、
 *   lunarMonth(1-12)、lunarDay(1-30)、isLeapMonth、askGz（求测时辰干支）
 */
export function calcTiebanBenming(p) {
	const { yearGz, dayGz, hourGz, gender, lunarMonth, lunarDay, isLeapMonth, askGz } = p;
	const steps = [];
	const monthName = effectiveMonthName(lunarMonth, isLeapMonth);
	const monthNum = TABLES.monthNum[monthName];
	const hourNum = TABLES.hourNum[hourGz[1]];
	steps.push({ key: 'monthNum', label: '月命数', input: monthName + (isLeapMonth ? '（闰月按下月计）' : ''), table: '月份配数表', output: monthNum });
	steps.push({ key: 'hourNum', label: '时命数', input: `时支 ${hourGz[1]}`, table: '时支配数表', output: hourNum });

	// 古籍只言「负则加十二」。然月命数与时命数皆 1..12 → 此式可达 0..14，而起五音表印 1..12
	// 十二行（无 0 行、无 13/14 行）→ 域即 1..12，须按十二循环归一。对古籍所载之负数例，
	// 归一与「加十二」逐值全同（−8→4、−1→11）→ 非改古法，而是补其未言之格（否则查表落空即崩）。
	const xianTianRaw = monthNum + 3 - hourNum;
	const xianTian = ((xianTianRaw - 1) % 12 + 12) % 12 + 1;
	steps.push({ key: 'xianTian', label: '先天命数', input: `${monthNum} + 3 − ${hourNum}`, table: '公式（十二循环归一）', output: xianTian });

	const yearGan = yearGz[0];
	const wuYin = TABLES.wuyinTable[String(xianTian)][yearGan];
	const wuYinNum = TABLES.wuyinNum[wuYin];
	steps.push({ key: 'wuYin', label: '五音', input: `先天命数 ${xianTian} × 年干 ${yearGan}`, table: '起五音表', output: wuYin });
	steps.push({ key: 'wuYinNum', label: '五音命数', input: wuYin, table: '五音配数表', output: wuYinNum });

	const dayNayin = nayinElement(dayGz);
	const riMing = TABLES.rimingTable[dayNayin][askGz[0]];
	steps.push({ key: 'riMing', label: '日命数', input: `日柱纳音 ${dayNayin} × 求测时干 ${askGz[0]}`, table: '起日命数表', output: riMing });

	const askNayin = nayinElement(askGz);
	const shiYun = TABLES.shiyunNum[askNayin];
	steps.push({ key: 'shiYun', label: '时运数', input: `求测时辰纳音 ${askNayin}`, table: '起时运数表', output: shiYun });

	// 考刻：阳男阴女 且 日命数+时运数>6 → 初刻；阴男阳女 则相反（≤6 各自互换）
	const yangYear = GAN.indexOf(yearGan) % 2 === 0;
	const groupA = (yangYear && gender === '男') || (!yangYear && gender === '女');
	const sum = riMing + shiYun;
	const ke = groupA ? (sum > 6 ? '初刻' : '正刻') : (sum > 6 ? '正刻' : '初刻');
	steps.push({ key: 'ke', label: '考刻', input: `${riMing}+${shiYun}=${sum}（${sum > 6 ? '>6' : '≤6'}）· ${yangYear ? '阳' : '阴'}年${gender}命`, table: '日命时运考刻表', output: ke });

	const benMingShu = (wuYinNum * 5 + riMing + shiYun - (sum <= 6 ? 1 : 6)) * 30 + lunarDay;
	steps.push({ key: 'benMingShu', label: '本命数', input: `(${wuYinNum}×5+${riMing}+${shiYun}−${sum <= 6 ? 1 : 6})×30+${lunarDay}`, table: sum <= 6 ? '公式①' : '公式②', output: benMingShu });

	const biGuaMap = ke === '初刻' ? TABLES.biguaChu : TABLES.biguaZheng;
	const biGua = biGuaMap[String(benMingShu)] || null;
	steps.push({ key: 'biGua', label: '十二辟卦', input: `${ke} · 本命数 ${benMingShu}`, table: `${ke}本命十二辟卦表`, output: biGua });

	const notes = [];
	let base = null;
	let xuShu = null;
	const items = {};
	if (!biGua) {
		notes.push(`本命数 ${benMingShu} 超出古籍所载范围（181~930），无对应辟卦。`);
	} else {
		const tbl = TABLES.benmingSecret[biGua];
		base = tbl.base;
		const key = ke === '初刻' ? 'chu' : 'zheng';
		const row = tbl.rows.find((r) => r[key] === xianTian);
		if (!row) {
			notes.push(`本命条文秘数表（${biGua}）中未见${ke}先天命数 ${xianTian} 之行。`);
		} else {
			xuShu = row.xu;
			[['xingge', '性格'], ['caineng', '才能前程'], ['caiyun', '财运'], ['xiongdi', '兄弟个数']]
				.forEach(([f, cn]) => {
					items[cn] = row[f] === null
						? { skipped: true, reason: '古籍于此项标「×」：此刻生人情况多，无条文可查。' }
						: { nums: row[f].map((v) => base + row.xu + v) };
				});
		}
	}
	return { steps, xianTian, wuYin, wuYinNum, riMing, shiYun, ke, benMingShu, biGua, base, xuShu, items, notes };
}

/** 某一岁的流年推算（不含条文正文）。 */
function liunianAt(age, seq, houTian, ke, yearZhi) {
	const tianSiSheng = seq[(age - 1) % 12];
	const zhi = ZHI[(ZHI.indexOf(yearZhi) + age - 1) % 12];
	const mark = TABLES.liunianMark[String(houTian)][zhi];
	const lkey = (ke === '初刻' ? 'chu' : 'zheng') + (age % 2 ? 'Odd' : 'Even');
	const letter = TABLES.liunianLetter[lkey][tianSiSheng][mark];
	const young = age <= 10 || age >= 81;
	const src = young ? TABLES.liunianVerseYoung : TABLES.liunianVerseMain;
	const fix = src.letterToFix[letter];
	const parity = age % 2 ? 'odd' : 'even';
	const add = young ? src.add[String(fix)] : src.addByLetter[letter];
	const val = (src.byAge[String(age)] || {})[String(fix)];
	return {
		age, gz: null, tianSiSheng, mark, letter, fix, parity, young,
		num: (val === undefined || add === undefined) ? null : add + val,
		add, val,
		missing: val === undefined,
	};
}

/** 条文校正：1-10 及 81-108 岁 校正数 +2（>6 减 6）；其余 +3（>20 减 20）。可反复施用。 */
export function correctTiebanVerse(row, times = 1) {
	const out = [];
	let fix = row.fix;
	for (let t = 0; t < times; t += 1) {
		const step = row.young ? 2 : 3;
		const mod = row.young ? 6 : 20;
		fix += step;
		if (fix > mod) fix -= mod;
		const src = row.young ? TABLES.liunianVerseYoung : TABLES.liunianVerseMain;
		const letter = row.young ? null : FIX_TO_LETTER[row.parity][fix];
		const add = row.young ? src.add[String(fix)] : src.addByLetter[letter];
		const val = (src.byAge[String(row.age)] || {})[String(fix)];
		out.push({
			round: t + 1, fix, letter,
			num: (val === undefined || add === undefined) ? null : add + val,
			missing: val === undefined,
		});
	}
	return out;
}

/** 流年链。fromAge/toAge 虚岁，古籍所载数表覆盖 1-108。 */
export function calcTiebanLiunian(benming, { yearGz, gender, fromAge = 1, toAge = 108 } = {}) {
	const { xianTian, benMingShu, ke } = benming;
	const yearZhi = yearGz[1];
	const grp = ZHI_GROUPS.find((g) => g.indexOf(yearZhi) >= 0);
	const yx = TABLES.yunxian[String(xianTian)];
	const order = yx.order[grp][gender];
	const col = yx.tian4[yearGz[0]];
	// 按「起流年天四声顺序」栏的序号 1..12 去读年干栏，得一组 12 个天四声，逐 12 年循环
	const seq = [];
	for (let i = 1; i <= 12; i += 1) seq.push(col[order.indexOf(i)]);

	// 后天命数 = (先天命数+本命数) ÷8 之余。古籍未载整除之例(诸算例之余皆非 0),
	// 然流年标记表印 1..8 八行、无 0 行 → 域即 1..8,余 0 须作 8(数表自证;否则查表落空即崩)。
	const houTian = (xianTian + benMingShu) % 8 || 8;
	const base = gzIndex(yearGz);
	const rows = [];
	for (let age = fromAge; age <= toAge; age += 1) {
		const r = liunianAt(age, seq, houTian, ke, yearZhi);
		r.gz = gzAt(base + age - 1);
		rows.push(r);
	}
	return { seq, houTian, rows, zhiGroup: grp };
}

/** 条文正文库按需载入（体积大，独立 chunk；条文号同步可得，正文到达后再填）。 */
let versesPromise = null;
export function loadTiebanVerses() {
	if (!versesPromise) {
		versesPromise = import('./data/zhengchuanTiebanVerses.json', { with: { type: 'json' } })
			.then((m) => m.default || m);
	}
	return versesPromise;
}

/** 干支之真伪：须恰二字、上干下支皆在其谱（只查长度不够——'XX' 之类会混过去） */
function isGz(x) {
	const t = `${x == null ? '' : x}`.trim();
	return t.length === 2 && GAN.indexOf(t[0]) >= 0 && ZHI.indexOf(t[1]) >= 0;
}

/**
 * 🔴 入口守卫 —— 本支之「求测时辰」是【自由文本】，用户什么都打得进来：
 *    此前坏字既不拦也不报，一路算到本命数成 NaN(出个错盘)；四柱若坏则更直接抛 TypeError。
 *    今于入口即验：四柱须齐且皆真干支；求测时辰坏则回落本人时柱(古籍本以时柱为默认)。
 */
export function calcTieban(input, opts = {}) {
	const i = input || {};
	const four = [i.yearGz, i.monthGz, i.dayGz, i.hourGz];
	if (four.some((x) => !isGz(x))) return null;
	const askGz = isGz(i.askGz) ? i.askGz : i.hourGz;   // 坏/空 → 回落本人时柱，不出错盘
	input = { ...i, askGz };
	const benming = calcTiebanBenming(input);
	if (!benming || !Number.isFinite(benming.benMingShu)) return null;
	const liunian = benming.biGua
		? calcTiebanLiunian(benming, { yearGz: input.yearGz, gender: input.gender, fromAge: opts.fromAge || 1, toAge: opts.toAge || 108 })
		: null;
	return { school: 'tieban', input, benming, liunian, meta: TIEBAN_META };
}

export default calcTieban;
