// 建除十二神(十二值神)单一来源:名表、吉凶归类、按「建」位顺数求值神。
// 黄历 / 风水择日 / 三式合一右栏 / 奇门与三式盘面外环共用同一份;演禽另有自家吉凶归类(yanqinConst.JIANCHU_GOOD),属流派差异,不并。
// 口径(正统古法):日值神 = 月建(节气月的月支)位起「建」,顺数到日支,**逢节重复** —— 交节那一天整天按新月建起建
// (于是交节日与前一天同一个值神;与本软件黄历 fengshui/zeri.dayCourse、lunar-javascript getZhiXing 同一口径,
// 不按交节时刻切:盘上的月柱按交节时刻换,交节当天交节前的几个小时会差一位);时值神 = 以日支为建,顺数到时支。
import { Solar } from 'lunar-javascript';
import { parseDateParts } from '../bazi/dateStrSafe.js';
import { isLunarJsYearReliable } from '../bazi/lunarDomainGuard.js';

export const JIANCHU_12 = ['建', '除', '满', '平', '定', '执', '破', '危', '成', '收', '开', '闭'];
export const JIANCHU_JX = {
	建: 'neutral', 除: 'good', 满: 'neutral', 平: 'neutral', 定: 'good', 执: 'good',
	破: 'bad', 危: 'neutral', 成: 'good', 收: 'neutral', 开: 'good', 闭: 'bad',
};
const ZHI12 = '子丑寅卯辰巳午未申酉戌亥';
const zhiOf = (v)=>`${v === undefined || v === null ? '' : v}`.slice(-1);   // 干支取支;单支原样

// jianZhi = 起「建」之支(月建支 / 日支,可传干支),zhi = 要查的支。认不出返回 null。
export function jianChuOf(jianZhi, zhi){
	const za = zhiOf(jianZhi);
	const zb = zhiOf(zhi);
	const a = za ? ZHI12.indexOf(za) : -1;   // 空串 indexOf 恒为 0,会被当成「子」→ 先挡掉
	const b = zb ? ZHI12.indexOf(zb) : -1;
	if(a < 0 || b < 0){ return null; }
	const idx = ((b - a) % 12 + 12) % 12;
	const name = JIANCHU_12[idx];
	return { name, idx, jx: JIANCHU_JX[name] };
}

const JX_TEXT = { good: '吉', bad: '凶', neutral: '平' };
export const jianChuText = (r)=>(r ? `${r.name}（${JX_TEXT[r.jx] || '平'}）` : '—');

const nextZhi = (z)=>{ const i = ZHI12.indexOf(z); return i < 0 ? '' : ZHI12[(i + 1) % 12]; };

// 日值所用的月建支(逢节重复):先认这一盘的日柱落在哪个民用日 —— 在钟面日期前后一天里找日柱干支相同的那天
// (23 点换日、真太阳时跨零点都对得上;六十甲子三天内不会重名),取那一天的节令月支(交节当天即新月;
// 「哪一天交节」按历法库的东八区民用日,与本软件黄历页同)。
// 两道闸,过不了就退回盘上的月柱(= 按交节时刻切,只在交节当天交节前差一位):
//   ① 历法库只在公元 1–9999 年可信,域外不报错但节气错位(公元前的三月会给出亥月)—— 域外的日子一律不采;
//   ② 节令月支只可能等于盘上月支(平日 / 交节之后),或是它的下一支(交节当天交节之前);对不上 = 两边历法不同源
//      (时区使交节日差一天、真太阳时跨日等),信盘 —— 外环的「建」不会落到与盘上月柱无关的支上。
// 没给日期 / 日期认不出 / 三天里都对不上日柱时同样退回。
export function jianChuMonthZhi(ganzhi, dateStr){
	const gz = ganzhi || {};
	const fallback = zhiOf(gz.month);
	const dp = parseDateParts(dateStr);
	if(!dp || !gz.day || !isLunarJsYearReliable(dp.year)){ return fallback; }
	try{
		const base = Solar.fromYmd(dp.year, dp.month, dp.day);
		for(const off of [0, 1, -1]){
			const solar = off ? base.next(off) : base;
			if(!isLunarJsYearReliable(solar.getYear())){ continue; }
			const lunar = solar.getLunar();
			if(lunar.getDayInGanZhi() !== `${gz.day}`){ continue; }
			const z = lunar.getMonthZhi();
			return (!fallback || z === fallback || z === nextZhi(fallback)) ? z : fallback;
		}
	}catch(_e){ /* 历表认不出的日期(如 1582 年 10 月改历空档):退回盘上的月柱 */ }
	return fallback;
}

// 一盘的日值 / 时值(ganzhi = { month, day, time } 干支,dateStr = 这一盘的钟面日期):外环、右栏卡、快照都从这里取
export function jianChuOfChart(ganzhi, dateStr){
	const gz = ganzhi || {};
	const monthZhi = jianChuMonthZhi(gz, dateStr);
	return { monthZhi, day: jianChuOf(monthZhi, gz.day), hour: jianChuOf(gz.day, gz.time) };
}

// 盘面外环一圈:每支按(逢节重复的)月建起建所值的建星;日支那一格就是今日日值。
// 时值以日支为建、另起一圈,不在这一圈上(右栏卡片与快照各有一行)。认不出月建返回 null。
export function jianChuRing(ganzhi, dateStr){
	const gz = ganzhi || {};
	const { monthZhi, day, hour } = jianChuOfChart(gz, dateStr);
	if(!jianChuOf(monthZhi, '子')){ return null; }
	const dayZhi = zhiOf(gz.day);
	const byZhi = {};
	ZHI12.split('').forEach((z)=>{
		const r = jianChuOf(monthZhi, z);
		byZhi[z] = { ...r, isDay: z === dayZhi, title: `${z} 值${r.name}（${JX_TEXT[r.jx] || '平'}）${z === dayZhi ? ' · 今日日值' : ''}` };
	});
	return { monthZhi, dayZhi, byZhi, day, hour };
}

// 快照 / 导出一行:日值以月建起建(逢节重复)、时值以日支为建
export function jianChuLines(ganzhi, dateStr){
	const { day, hour } = jianChuOfChart(ganzhi, dateStr);
	if(!day && !hour){ return []; }
	return [`十二建星：日值${jianChuText(day)}、时值${jianChuText(hour)}（日值以节气月建起建顺数日支，交节当日按新月建；时值以日支为建顺数时支）`];
}
