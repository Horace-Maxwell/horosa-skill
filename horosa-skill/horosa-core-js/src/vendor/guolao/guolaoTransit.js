// 七政四余 行运(洞微大限 / 小限 / 月限 / 童限)纯前端 compute —— 据古籍 §10 确切口径,从命宫地支 + 太阳躔度 + 岁数派生。
// 零后端、零 Java、additive 零回归(作为现「古度限度法」之外的可选行运法)。中性词。
import { DONGWEI_PALACE_YEARS } from './guolaoData.js';

const ZHI = '子丑寅卯辰巳午未申酉戌亥'.split('');
// 十二宫逆布名序(§7.2):命宫起逆布 —— 小限 age 序(出生当年命宫、二岁财帛、三岁兄弟…)即此序(§10.2)。
const PALACE_NAMES_REVERSE = ['命宫', '财帛', '兄弟', '田宅', '男女', '奴仆', '妻妾', '疾厄', '迁移', '官禄', '福德', '相貌'];

function ziIndex(zi){ const s = String(zi || ''); for(let i = 0; i < s.length; i++){ const k = ZHI.indexOf(s[i]); if(k >= 0){ return k; } } return -1; }

// 洞微大限(§10.1):命宫顺行,各宫年数不等;命宫起限岁 = floor(太阳在本宫躔度/3)+10(三度一年+十年)。
// 洞微大限(PDF ch.3-4 捷法):出限虚岁 = 10 + 太阳宫内度/3 + 月份/12(节气月 寅=1…丑=12);
// WP-E:不 floor(保吊度精确)+ 含月份项 + 逐宫飞星吊度(每年 30/宫年数,entryDeg 链式)。
// birthMonthSeq 可选(缺省 0 即不含月份项)。worked-example:computeDongwei(19.5,8).startAge≈17.17(17岁2月)。
export function computeDongwei(sunLonInSign, birthMonthSeq){
	const inSign = Number.isFinite(Number(sunLonInSign)) ? ((Number(sunLonInSign) % 30) + 30) % 30 : 0;
	const monthSeq = Number.isFinite(Number(birthMonthSeq)) ? Number(birthMonthSeq) : 0;
	const startAge = 10 + inSign / 3 + monthSeq / 12;   // 虚岁(含月份项,不 floor)
	const r2 = (x)=> Math.round(x * 100) / 100;
	let acc = startAge;
	let entryDeg = inSign;   // 命宫飞星起度 = 太阳宫内度
	const rows = [];
	DONGWEI_PALACE_YEARS.forEach(([palace, years], i)=>{
		const perYearDeg = 30 / years;   // 每年吊度
		const diaodu = [];
		for(let y = 0; y < Math.ceil(years); y++){
			diaodu.push({ age: r2(acc + y), deg: r2(((entryDeg + perYearDeg * y) % 30 + 30) % 30) });
		}
		rows.push({ index: i + 1, palace, years, fromAge: r2(acc), toAge: r2(acc + years),
			perYearDeg: Math.round(perYearDeg * 1000) / 1000, entryDeg: r2(entryDeg), diaodu });
		entryDeg = ((entryDeg + perYearDeg * years) % 30 + 30) % 30;   // 链式:下一宫入度
		acc += years;
	});
	return { startAge: r2(startAge), rows, totalSpan: r2(acc - startAge) };
}

// 小限(§10.2):生年支加命宫逆数;age1=命宫宫支,逐年逆行一宫(12年一轮)。宫名按逆布序。
export function computeXiaoxian(mingZhi, age){
	const mi = ziIndex(mingZhi);
	const a = Math.max(1, Number(age) || 1);
	if(mi < 0){ return null; }
	const k = (a - 1) % 12;
	return { age: a, palaceZi: ZHI[((mi - k) % 12 + 12) % 12], palaceName: PALACE_NAMES_REVERSE[k] };
}

// 月限(§10.2):由当年小限宫起生月,按月逆寻。lunarMonth 1-12。宫名=相对命宫逆布偏移。
export function computeYuexian(mingZhi, age, lunarMonth){
	const x = computeXiaoxian(mingZhi, age);
	if(!x){ return null; }
	const mi = ziIndex(mingZhi);
	const xi = ziIndex(x.palaceZi);
	const m = Math.max(1, Number(lunarMonth) || 1);
	const yi = ((xi - (m - 1)) % 12 + 12) % 12;        // 月限地支 index
	const k = ((mi - yi) % 12 + 12) % 12;              // 相对命宫的逆布偏移 → 宫名
	return { lunarMonth: m, palaceZi: ZHI[yi], palaceName: PALACE_NAMES_REVERSE[k] };
}

// 童限(§10.2):一命二财三疾四妻五福 顺排;出童限年 ≈ 逆数至太阳交中气(三日一年)+ 基数。
// 太阳交中气:中气为黄经 15° 整数倍;逆数 = 太阳黄经距上一中气度数 ≈ 天数(太阳约 1°/日)。
// 基数分歧(古籍 ch.4 作者三页论辩,坊间排盘软件即出 9 岁/10 岁两版;PDF 主张「虚十上本生度起行、早不过十一晚不过二十」):
//   tong10=通行十年(默认·现状零回归) / gu9=古九岁 / xu11=虚十一(PDF 早不过11晚不过20,加界钳)。基准之争(命宫躔度 vs 太阳中气)留作后续,此处先把「基数」分歧做成可选。
const TONGXIAN_PALACES = ['命宫', '财帛', '疾厄', '妻妾', '福德'];
export const TONGXIAN_BASE_DEFAULT = 'tong10';
export function computeTongxian(sunLon, baseVariant){
	const lon = Number(sunLon);
	const backDeg = Number.isFinite(lon) ? (((lon % 15) + 15) % 15) : 0;   // 距上一中气(15°)度数≈天数
	const v = (baseVariant === 'gu9' || baseVariant === 'xu11') ? baseVariant : 'tong10';
	const base = v === 'gu9' ? 9 : (v === 'xu11' ? 11 : 10);   // 三日一年 + 基数(派别分歧)
	let exitAge = backDeg / 3 + base;
	if(v === 'xu11'){ exitAge = Math.min(20, Math.max(11, exitAge)); }   // PDF「早不过十一、晚不过二十」界钳
	return { palaces: TONGXIAN_PALACES.slice(), exitAge: Math.round(exitAge * 10) / 10, backDays: Math.round(backDeg * 10) / 10, baseVariant: v };
}
