// 年家 / 月家 / 日家起局(局数与阴阳遁;时家的局数在排盘里按起局法另算)
// 从 DunJiaCalc.js 按职责拆出(门面保留原导入路径与对外导出;读源码的检查读「子模块 + 门面」全集,见 scripts/source-sets.json)。
import { dateKeyOf, parseDateKey } from '../../bazi/dateStrSafe.js';
import { normalizeNum, juNumberToCn, getGanzhiIndex, isYangDunJieqi, findYuan } from './basics.js';
import { ZHI } from './tables.js';
import { keyToUtcDay } from './yinyangdun.js';

// 年家定局两档:sanyuan(默认)=六十年一元恒一局(上1/中4/下7,皆阴遁,历史行为);
//   yinian=逐年换局——三元甲子起元首局逐年逆退九局循环,与通行年游九星完全同构
//   (公域可核验锚:1984甲子=7、2025乙巳=2、2026丙午=1)。元名仍按六十年块显示。
export const YEARJIA_JU_OPTIONS = [
	{ value: 'sanyuan', label: '六十年一局（默认）' },
	{ value: 'yinian', label: '一年一局（逐年逆退）' },
];

export function calcYearJiaMeta(year, yearJiaJu){
	if(year >= 0 && year <= 3){
		return { sanYuan: '中元', juShu: 4, yinYangDun: '阴遁' };
	}
	const cycle = ((Math.floor((year - 4) / 60) % 3) + 3) % 3;
	const FIRST = [7, 1, 4][cycle];
	const YUAN = ['下元', '上元', '中元'][cycle];
	if(yearJiaJu === 'yinian'){
		const n = (((year - 4) % 60) + 60) % 60;
		const ju = (((FIRST - 1 - n) % 9) + 9) % 9 + 1;
		return { sanYuan: YUAN, juShu: ju, yinYangDun: '阴遁' };
	}
	return { sanYuan: YUAN, juShu: FIRST, yinYangDun: '阴遁' };
}

// 月家奇门(经典「附月奇门·年干支定局法」/又法,五年一元):局由年柱「符头」(最近甲/己年)定,整个 5 年元块同一局,皆阴遁。
//   符头支 子午卯酉=上元阴七 / 寅申巳亥=中元阴一 / 辰戌丑未=下元阴四 ≡ 局=[7,1,4][符头60序÷5 mod3]。
//   月柱仅作值符值使锚点(值符随月干、值使随月支、寻月柱旬首,见 calcDunJia panGanzhi),不参与定局。
// 真值核验(用户 4 参考盘 + 课本非典型例):2026丙午/2025乙巳→符头甲辰(辰)→下元阴四 ✓✓;2048戊辰→符头甲子(子)→上元阴七 ✓;
//   2053癸酉→符头己巳(巳)→中元阴一 ✓;2003癸未→符头己卯(卯)→上元阴七 ✓(课本) = 5/5。
//   〔对比〕又一传本「逐10月递减(上7→6→…→2)」对 2026 给阴二,不符 → 弃用;故取年符头定局法。
// yueJiaQiJuType:0=年柱符头(正传,默认) / 1=年支直取(变体,不取符头,供对比)。
const MONTH_ZHI_JU = { 子: 7, 午: 7, 卯: 7, 酉: 7, 寅: 1, 申: 1, 巳: 1, 亥: 1, 辰: 4, 戌: 4, 丑: 4, 未: 4 };

const MONTH_JU_YUAN = { 7: '上元', 1: '中元', 4: '下元' };

// 逐月换局(一月一局):正月入中局按年支组(仲年子午卯酉=8/孟年寅申巳亥=2/季年辰戌丑未=5),
//   逐月逆退九局循环——月家文献自载「孟年正月二黑、仲年八白、季年五黄,星顺月逆而布」,
//   与通行月游九星同构(公域可核验)。月序按月柱地支(寅=正月…丑=十二月),皆阴遁。
const MONTH_START_JU_MONTHLY = { 子: 8, 午: 8, 卯: 8, 酉: 8, 寅: 2, 申: 2, 巳: 2, 亥: 2, 辰: 5, 戌: 5, 丑: 5, 未: 5 };

export function calcYueJiaMeta(ganzhi, yueJiaQiJuType){
	const t = normalizeNum(yueJiaQiJuType, 0);
	if(t === 2){
		const yearZhi = `${ganzhi.year || '甲子'}`.charAt(1);
		const monthZhi = `${ganzhi.month || '丙寅'}`.charAt(1);
		const first = MONTH_START_JU_MONTHLY[yearZhi] || 8;
		const zi = ZHI.indexOf(monthZhi);
		const m = zi >= 0 ? ((zi - 2 + 12) % 12) : 0;
		const ju = (((first - 1 - m) % 9) + 9) % 9 + 1;
		// qmju 显式给出(无元名尾)——否则 calcDunJia 兜底 buildQmjuByMeta 会拼上「上元」假元名进 juText
		return { sanYuan: '', juShu: ju, yinYangDun: '阴遁', qmju: `阴遁${juNumberToCn(ju)}局` };
	}
	const yearIdx = ((getGanzhiIndex(ganzhi.year || '甲子') % 60) + 60) % 60;
	// 符头 = 最近的甲/己年(60 序向下取到 5 的倍数);变体则直接用年支。
	const baseIdx = (t === 1) ? yearIdx : (yearIdx - (yearIdx % 5));
	const zhi = ZHI[baseIdx % 12];
	const juShu = MONTH_ZHI_JU[zhi] || 4;
	return { sanYuan: MONTH_JU_YUAN[juShu] || '下元', juShu, yinYangDun: '阴遁' };
}

// 日家奇门(经典「又法日奇门起例」/节气三元·六十日一局):冬至后第1/2/3甲子(各60日)=阳遁 1/7/4 局;
//   夏至后第1/2/3甲子(各60日)=阴遁 9/3/6 局。皆以其日旬首所值星为值符、门为值使;超接置闰如时奇(符头超30日即置闰)。
//   实现:阴阳遁由节气半年定;局由「距本半年起始『至甲子』的 60 日块数 mod3」定(至甲子=离冬/夏至最近之甲子日;超30日置闰取后一甲子)。
// 真值核验(用户 5 参考盘):2026乙丑=阳一(上块)/2053丁未=阳七(中块)/2025丁酉=阴六(下块)/2048壬寅=阴六(下块)/1964癸亥=阴三(中块) = 5/5。
//   ⚠️ 阴遁序列取 9·3·6(§10 节气三元),非又法原文「9·2·6」——1964癸亥落中块,真值阴三(9·2·6 会给阴二,证伪;传本有别,从真软件)。
//   〔对比弃用〕传本「日支定局(子午2·丑未6·寅申1·卯酉8·辰戌4·巳亥9)」对乙丑给阳六不符;「findYuan符头元(无置闰漂移)」对丁酉给阴九不符。
const DAY_BLOCK_JU = { 阳: [1, 7, 4], 阴: [9, 3, 6] };

const DAY_BLOCK_YUAN = ['上元', '中元', '下元'];

export function dayJiaHalfYear(seeds, dateParts){
	// 以「至」定半年(非节令!):夏至≤date<本年末冬至 → 阴遁(至=夏至);本年末冬至后或本年夏至前 → 阳遁(至=最近冬至)。
	// 节令(nongli.jieqi)在至界会滞后(如06-22已过夏至仍报芒种)→ 必须用至日期判,否则阴阳遁错半年。
	if(!seeds){ return null; }
	const y = dateParts.year;
	const dU = keyToUtcDay(dateKeyOf(y, dateParts.month, dateParts.day));
	if(!Number.isFinite(dU)){ return null; }
	// ⚠️ 种子约定有两种:后端「年内至 seeds[y].冬至=Dec(y)」vs 本地 buildLocalJieqiYearSeed「上年至 seeds[y].冬至=Dec(y-1)」。
	//   故不按种子索引年取(会因约定不同错半年,曾致 12-22 退阴九),改按「至日实际年份」跨 y-1/y/y+1 三年定位——
	//   两种约定都能取到 Dec(y-1)/Dec(y)/Jun(y),彻底兼容。
	const pick = (term, yr)=>{
		let found = null;
		[y - 1, y, y + 1].forEach((yy)=>{
			const s = seeds[yy] && seeds[yy][term];
			if(s && s.dateKey && (parseDateKey(s.dateKey) || {}).year === yr){ found = s; }
		});
		return found;
	};
	const xz = pick('夏至', y);            // 本年夏至(约 Jun y)
	const dzStart = pick('冬至', y - 1);    // 本年初冬至(约 Dec y-1),启动本年阳半年
	const dzEnd = pick('冬至', y);          // 本年末冬至(约 Dec y),阴→阳界
	if(!xz || !xz.dateKey){ return null; }
	const xzU = keyToUtcDay(xz.dateKey);
	if(dzEnd && dzEnd.dateKey && dU >= keyToUtcDay(dzEnd.dateKey)){ return { yang: true, zhiSeed: dzEnd }; }  // 本年末冬至后 → 阳遁
	if(dU >= xzU){ return { yang: false, zhiSeed: xz }; }                                                      // 本年夏至后 → 阴遁
	return { yang: true, zhiSeed: dzStart || null };                                                           // 夏至前 → 阳遁(至=上年冬至)
}

export function calcDayJiaMeta(dateParts, dayGanZhi, jieqi, context, dayJiaJu){
	const seeds = context && context.jieqiYearSeeds ? context.jieqiYearSeeds : null;
	const half = dayJiaHalfYear(seeds, dateParts);
	const yang = half ? half.yang : isYangDunJieqi(jieqi);   // 有种子=至定半年(准);无种子退化用节气(可能滞后)
	const yy = yang ? '阳' : '阴';
	// 十日一局:逐旬按符头换元(甲子甲午旬=上元/甲戌甲辰=中元/甲申甲寅=下元),局取该元经典局。
	if(dayJiaJu === 'shitian'){
		const block = ({ 上元: 0, 中元: 1, 下元: 2 })[findYuan(dayGanZhi)] || 0;
		return { sanYuan: DAY_BLOCK_YUAN[block], juShu: DAY_BLOCK_JU[yy][block], yinYangDun: yang ? '阳遁' : '阴遁' };
	}
	let block = null;
	let sinceJiazi = null;
	const zhiSeed = half ? half.zhiSeed : null;
	if(zhiSeed && zhiSeed.dateKey && zhiSeed.dayGanzhi){
		const dayUtc = keyToUtcDay(dateKeyOf(dateParts.year, dateParts.month, dateParts.day));
		const zhiUtc = keyToUtcDay(zhiSeed.dateKey);
		const z = ((getGanzhiIndex(zhiSeed.dayGanzhi) % 60) + 60) % 60;     // 至日柱 60 序
		const jiaziUtc = zhiUtc - z + (z > 30 ? 60 : 0);                     // 至甲子=最近甲子(超30日置闰取后一甲子)
		if(Number.isFinite(dayUtc) && Number.isFinite(jiaziUtc) && dayUtc >= jiaziUtc){
			block = Math.floor((dayUtc - jiaziUtc) / 60) % 3;
			sinceJiazi = dayUtc - jiaziUtc;
		}
	}
	if(block === null){
		// 无种子退化:符头元(findYuan)近似定块,占位不崩(非精确,传本有别)。
		block = { 上元: 0, 中元: 1, 下元: 2 }[findYuan(dayGanZhi)] || 0;
	}
	block = ((block % 3) + 3) % 3;
	// 一日一局:自「至甲子」起逐日推局(阳:上元首局起顺进;阴:逆退);元仍按六十日块显示。
	//   无种子时退化用日柱 60 序近似(60≢0 mod 9,跨甲子有断点,如实近似不掩盖)。
	if(dayJiaJu === 'yitian'){
		const d = sinceJiazi !== null ? sinceJiazi : ((getGanzhiIndex(dayGanZhi) % 60) + 60) % 60;
		const startJu = DAY_BLOCK_JU[yy][0];
		const ju = yang ? ((startJu - 1 + d) % 9) + 1 : (((startJu - 1 - d) % 9) + 9) % 9 + 1;
		return { sanYuan: DAY_BLOCK_YUAN[block], juShu: ju, yinYangDun: yang ? '阳遁' : '阴遁' };
	}
	return { sanYuan: DAY_BLOCK_YUAN[block], juShu: DAY_BLOCK_JU[yy][block], yinYangDun: yang ? '阳遁' : '阴遁' };
}

export function normalizeQijuMethod(method){
	return ['zhirun', 'chaibu', 'maoshan', 'wurun', 'shuzi'].indexOf(method) >= 0 ? method : 'chaibu';
}
