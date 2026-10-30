import moment from 'moment';
import { Body, MakeTime, PairLongitude } from 'astronomy-engine';
import { birthMomentOfChart, civilDateAfterDays } from '../utils/civilMoment.js';
import { parseDateTimeParts } from '../utils/dateTimeParse.js';
import { civilJdnOfYmd } from '../utils/civilCalendar.js';
import { zoneOffsetMinutesOf } from '../utils/zoneOffset.js';
import * as AstroConst from '../../constants/AstroConst.js';
// [YB] 三段补厚共享 helper(起盘信息/当前时点/方法说明;astroAiSnapshot 不回引本文件,无环)。
// namespace import + typeof 守卫:测试环境可能部分 mock astroAiSnapshot(只留 buildAstroSnapshotContent 等),
// 缺函数时回 [] 保底 → 输出与补厚前逐字节一致,不炸挂载。
// headless stub：上游 [YB] 三段补厚用它产 [起盘信息]/[当前时点]/[方法说明]，但 skill 的 Python 层
// 已经产这三段（_predictive_setup_section_text / _predictive_common_sections_text），再让 JS 产一遍会重段。
// 上游每个调用点都写了 typeof …==='function' 守卫：未定义的 helper 回退 []（不产段）。唯一例外是
// buildCurrentMomentLines——它收下 builder 自算的 [当前时点] 定位行（extraLines，如「当前主限」），交给
// tools/progextra.js 回传 Python 追加进 [当前时点]（= 上游 buildCurrentMomentLines(chartObj, extraLines)），自身仍返 []。
const astroAiSnapshot = {
	buildCurrentMomentLines: (chartObj, extraLines) => {
		globalThis.__horosaProgMomentLines = Array.isArray(extraLines) ? extraLines.filter(Boolean).map((l) => `${l}`) : [];
		return [];
	},
};

const birthHeaderLines = (c) => (typeof astroAiSnapshot.buildPredictiveBirthHeaderLines === 'function' ? astroAiSnapshot.buildPredictiveBirthHeaderLines(c) : []);
const currentMomentLines = (c, x) => (typeof astroAiSnapshot.buildCurrentMomentLines === 'function' ? astroAiSnapshot.buildCurrentMomentLines(c, x) : []);
const methodNoteLines = (k) => (typeof astroAiSnapshot.buildMethodNoteLines === 'function' ? astroAiSnapshot.buildMethodNoteLines(k) : []);

// 月相推运（8 相,次限「一日为一年」）:N 岁的推运日月差 = 出生后第 N 天(按回归年折算)真实的月 − 日黄经差。
//  推运日月差逐日按星历精算(astronomy-engine 的 Moon − Sun 地心黄经差),以本命盘自己的日月差为起点只取变化量
//  (两套星历的常差在差分里相消);月亮真实日行 11.8°–15.4°、太阳 0.95°–1.02°,所以各相起点不是平均速率能推的。
//  每相 45°：朔/娥眉/上弦/盈凸/望/散播/下弦/残月;各相起始岁数对每个 45° 边界二分求解。
//  出生时刻读不出(无日期 / 时区)时退回平均速率(每年 12.1908°)并在快照里注明。
export const PHASES_8 = [
	{ key: 'new', name: '朔 · 新月', en: 'New', lo: 0, hi: 45, keyword: '萌发 · 新启 · 直觉行动' },
	{ key: 'crescent', name: '娥眉月', en: 'Crescent', lo: 45, hi: 90, keyword: '挣扎立足 · 突破惯性' },
	{ key: 'first', name: '上弦月', en: 'First Quarter', lo: 90, hi: 135, keyword: '行动建构 · 危机决断' },
	{ key: 'gibbous', name: '盈凸月', en: 'Gibbous', lo: 135, hi: 180, keyword: '修炼完善 · 趋向目标' },
	{ key: 'full', name: '望 · 满月', en: 'Full', lo: 180, hi: 225, keyword: '圆满显化 · 觉察对照' },
	{ key: 'disseminating', name: '散播月', en: 'Disseminating', lo: 225, hi: 270, keyword: '传播分享 · 成果输出' },
	{ key: 'last', name: '下弦月', en: 'Last Quarter', lo: 270, hi: 315, keyword: '反省转向 · 旧序重整' },
	{ key: 'balsamic', name: '残月', en: 'Balsamic', lo: 315, hi: 360, keyword: '消融释放 · 蓄势待新' },
];

export const PROG_ELONG_RATE = 360 / 29.530588853; // °/年:平均朔望月 → 次限日月差平均推进率(≈ 12.1908);只用于数圈数与读不出出生时刻时的退路
const SYNODIC_YEARS = 360 / PROG_ELONG_RATE; // ≈ 29.53
const PROG_DAYS_PER_YEAR = 1;   // 次限:一日 = 一回归年
const JD_J2000 = 2451545.0;
const SAMPLE_YEARS = 0.5;       // 取样步长(推运日月差每步约 6°,不会跳过 45° 边界)

export const LUNATION_DEFAULT_OPTS = { maxAge: 90 };

function norm360(v){ let n = Number(v) % 360; if(n < 0){ n += 360; } return n; }

function findObj(chartObj, id){
	const objs = (chartObj && chartObj.chart && chartObj.chart.objects) || [];
	return objs.find((x) => x.id === id) || null;
}

function lonOf(chartObj, id){
	const o = findObj(chartObj, id);
	if(o && o.lon !== undefined && o.lon !== null){ return Number(o.lon); }
	if(o){
		const idx = AstroConst.LIST_SIGNS.indexOf(o.sign);
		if(idx >= 0 && o.signlon !== undefined && o.signlon !== null){ return idx * 30 + Number(o.signlon); }
	}
	return null;
}

// 出生时刻单源(全年份域:公元前 / 公元 1–99 年 / 五位年不误读;见 utils/civilMoment)
function parseBirth(chartObj){
	return birthMomentOfChart(chartObj);
}

// 出生时刻的世界时儒略日(params.birth / date+time 民用历 + params.zone);读不出 → null
export function birthJdUtOfChart(chartObj){
	const p = (chartObj && chartObj.params) ? chartObj.params : {};
	const birth = `${p.birth || ''}`.trim() || `${`${p.date || ''}`.trim()} ${`${p.time || ''}`.trim()}`.trim();
	const t = birth ? parseDateTimeParts(birth) : null;
	if(!t || t.year === 0){ return null; }
	const zoneMin = zoneOffsetMinutesOf(p.zone === undefined || p.zone === null || `${p.zone}`.trim() === '' ? '+00:00' : p.zone);
	if(zoneMin === null){ return null; }
	const jdn = civilJdnOfYmd(t.year, t.month, t.day);
	if(!Number.isFinite(jdn)){ return null; }
	return jdn - 0.5 + (Number(t.hour || 0) + Number(t.minute || 0) / 60 + Number(t.second || 0) / 3600) / 24 - zoneMin / 1440;
}

function pairElongAt(jdUt){
	return PairLongitude(Body.Moon, Body.Sun, MakeTime(jdUt - JD_J2000));
}

// 推运日月差(展开,不回绕):起点 = 本命盘日月差,加上星历上出生后 age 天的真实变化量。
// 圈数按平均速率定:真实与平均之差恒在十几度以内(月亮中心差 + 出差 + 太阳中心差),远小于半圈,不会数错。
function makeProgressedElong(chartObj, natalElong){
	const t0 = birthJdUtOfChart(chartObj);
	if(t0 === null){ return null; }
	let e0;
	try{ e0 = pairElongAt(t0); }catch(e){ return null; }
	return (age) => {
		const d = norm360(pairElongAt(t0 + age * PROG_DAYS_PER_YEAR) - e0);
		const k = Math.round((age * PROG_ELONG_RATE - d) / 360);
		return natalElong + d + 360 * k;
	};
}

export function computeLunationPhase(elong){
	const e = norm360(elong);
	const idx = Math.min(7, Math.floor(e / 45));
	return PHASES_8[idx];
}

export function buildLunationPhases(chartObj, opts){
	const o = { ...LUNATION_DEFAULT_OPTS, ...(opts || {}) };
	const maxAge = Number(o.maxAge) > 0 ? Number(o.maxAge) : 90;
	const sunLon = lonOf(chartObj, AstroConst.SUN);
	const moonLon = lonOf(chartObj, AstroConst.MOON);
	if(sunLon == null || moonLon == null){ return { natalElong: null, natalPhase: null, timeline: [], exact: false }; }
	const natalElong = norm360(moonLon - sunLon);
	const natalPhase = computeLunationPhase(natalElong);
	const birth = parseBirth(chartObj);
	const dateAt = (age) => (birth ? civilDateAfterDays(birth, age * 365.2422) : '');   // 民用历日期标签(1582 以前儒略历)
	const prog = makeProgressedElong(chartObj, natalElong);
	const elongAt = prog || ((age) => natalElong + age * PROG_ELONG_RATE);
	// 起点：出生当下的相（age 0）。然后逐个 45° 边界往后排到 maxAge。
	const timeline = [{ age: 0, date: dateAt(0), elong: natalElong, phase: natalPhase, isStart: true }];
	let nextBoundaryDeg = (Math.floor(natalElong / 45) + 1) * 45; // 绝对累计度(>natalElong)
	let lo = 0;
	while(lo < maxAge && timeline.length <= 400){
		const hi = Math.min(maxAge, lo + SAMPLE_YEARS);
		const gHi = elongAt(hi);
		while(gHi >= nextBoundaryDeg && timeline.length <= 400){
			// 推运日月差单调递增(月亮恒快于太阳):区间内二分求恰到边界的岁数
			let a = lo; let b = hi;
			for(let i = 0; i < 48; i++){
				const m = (a + b) / 2;
				if(elongAt(m) < nextBoundaryDeg){ a = m; }else{ b = m; }
			}
			const age = (a + b) / 2;
			timeline.push({ age, date: dateAt(age), elong: nextBoundaryDeg % 360, phase: PHASES_8[(Math.floor(nextBoundaryDeg / 45)) % 8] });
			nextBoundaryDeg += 45;
		}
		lo = hi;
		if(hi >= maxAge){ break; }
	}
	return { natalElong, natalPhase, timeline, synodicYears: SYNODIC_YEARS, exact: !!prog };
}

// 推运日月差(展开值;读不出出生时刻时按平均速率)
export function progressedElongAtAge(chartObj, age){
	const sunLon = lonOf(chartObj, AstroConst.SUN);
	const moonLon = lonOf(chartObj, AstroConst.MOON);
	if(sunLon == null || moonLon == null || age == null || !Number.isFinite(Number(age))){ return null; }
	const natalElong = norm360(moonLon - sunLon);
	const prog = makeProgressedElong(chartObj, natalElong);
	return prog ? prog(Number(age)) : natalElong + Number(age) * PROG_ELONG_RATE;
}

// 给定年龄求推运相（供组件高亮当前相）。
export function phaseAtAge(chartObj, age){
	const e = progressedElongAtAge(chartObj, age);
	return e === null ? null : computeLunationPhase(e);
}

export function buildLunationPhaseSnapshotText(chartObj, opts){
	if(!chartObj){ return ''; }
	const r = buildLunationPhases(chartObj, opts);
	if(!r || !r.natalPhase){ return ''; }
	const lines = [];
	// [YB] 头部盘主生辰([起盘信息];无数据 helper 自返 [],不产空段头)。
	lines.push(...birthHeaderLines(chartObj));
	lines.push('[月相推运]');
	lines.push(r.exact
		? `本命月相=${r.natalPhase.name}（日月差 ${r.natalElong.toFixed(1)}°）。次限推运:N 岁的日月差 = 出生后第 N 天真实的月日黄经差(按星历逐日精算),一轮约 ${SYNODIC_YEARS.toFixed(1)} 年;下列起始岁数是推运日月差恰到各相边界的时刻。`
		: `本命月相=${r.natalPhase.name}（日月差 ${r.natalElong.toFixed(1)}°）。出生时刻读不出,按平均速率每年 ${PROG_ELONG_RATE.toFixed(4)}° 推(约 ${SYNODIC_YEARS.toFixed(1)} 年一轮)。`);
	lines.push('');
	lines.push('| 起始年龄 | 日期 | 月相 | 关键词 |');
	lines.push('| --- | --- | --- | --- |');
	r.timeline.forEach((t) => {
		lines.push(`| ${t.age.toFixed(2)} 岁${t.isStart ? '(本命)' : ''} | ${t.date || '-'} | ${t.phase.name} | ${t.phase.keyword} |`);
	});
	// [YB] 尾部 [当前时点]+[方法说明];定位行=当前年龄的推运月相(与组件高亮同源 phaseAtAge)。
	const extraLines = [];
	const birth = parseBirth(chartObj);
	if(birth){
		const curAge = moment().diff(birth, 'days', true) / 365.2422;
		const curElong = progressedElongAtAge(chartObj, curAge);
		const curPhase = curElong === null ? null : computeLunationPhase(curElong);
		if(curPhase){
			extraLines.push(`当前推运月相：${curPhase.name}（${curPhase.keyword};推运日月差 ${norm360(curElong).toFixed(1)}°）`);
		}
	}
	const tail = [...currentMomentLines(chartObj, extraLines), ...methodNoteLines('lunationphase')];
	if(tail.length){
		lines.push('');
		lines.push(...tail);
	}
	return lines.join('\n');
}

export default { buildLunationPhases, buildLunationPhaseSnapshotText, computeLunationPhase, phaseAtAge, progressedElongAtAge, birthJdUtOfChart, PHASES_8, LUNATION_DEFAULT_OPTS };
