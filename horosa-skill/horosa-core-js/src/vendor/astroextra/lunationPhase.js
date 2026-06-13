import moment from 'moment';
import * as AstroConst from '../../constants/AstroConst.js';

// 月相推运（8 相）。纯前端派生：由本命日月黄经差 + 次限推进率求推运月相。
//  次限「日为年」：月每年约进 13.18°、日约 0.986° → 日月差每年约 12.19° → 约 29.53 年走完一轮 8 相。
//  每相 45°：朔/娥眉/上弦/盈凸/望/散播/下弦/残月。
// 不依赖后端：从本命盘已有的日月黄经直接推。

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

export const PROG_ELONG_RATE = 12.1908; // °/年（次限日月差推进率）
const SYNODIC_YEARS = 360 / PROG_ELONG_RATE; // ≈ 29.53

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

function parseBirth(chartObj){
	const p = (chartObj && chartObj.params) ? chartObj.params : {};
	const birth = `${p.birth || ''}`.trim();
	if(!birth){ return null; }
	const m = moment(birth.replace(/\//g, '-'), ['YYYY-MM-DD HH:mm:ss', 'YYYY-MM-DD HH:mm', 'YYYY-MM-DD']);
	return m.isValid() ? m : null;
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
	if(sunLon == null || moonLon == null){ return { natalElong: null, natalPhase: null, timeline: [] }; }
	const natalElong = norm360(moonLon - sunLon);
	const natalPhase = computeLunationPhase(natalElong);
	const birth = parseBirth(chartObj);
	const dateAt = (age) => (birth ? moment(birth).add(Math.round(age * 365.2422), 'days').format('YYYY-MM-DD') : '');
	// 起点：出生当下的相（age 0）。然后逐个 45° 边界往后排到 maxAge。
	const timeline = [{ age: 0, date: dateAt(0), elong: natalElong, phase: natalPhase, isStart: true }];
	// 下一个 45° 边界对应的累计度数。
	let nextBoundaryDeg = (Math.floor(natalElong / 45) + 1) * 45; // 绝对累计度（>natalElong）
	while(true){
		const age = (nextBoundaryDeg - natalElong) / PROG_ELONG_RATE;
		if(age > maxAge){ break; }
		const phase = PHASES_8[(Math.floor(nextBoundaryDeg / 45)) % 8];
		timeline.push({ age, date: dateAt(age), elong: nextBoundaryDeg % 360, phase });
		nextBoundaryDeg += 45;
		if(timeline.length > 400){ break; }
	}
	return { natalElong, natalPhase, timeline, synodicYears: SYNODIC_YEARS };
}

// 给定年龄求推运相（供组件高亮当前相）。
export function phaseAtAge(chartObj, age){
	const sunLon = lonOf(chartObj, AstroConst.SUN);
	const moonLon = lonOf(chartObj, AstroConst.MOON);
	if(sunLon == null || moonLon == null || age == null){ return null; }
	const natalElong = norm360(moonLon - sunLon);
	return computeLunationPhase(natalElong + age * PROG_ELONG_RATE);
}

export function buildLunationPhaseSnapshotText(chartObj, opts){
	if(!chartObj){ return ''; }
	const r = buildLunationPhases(chartObj, opts);
	if(!r || !r.natalPhase){ return ''; }
	const lines = ['[月相推运]'];
	lines.push(`本命月相=${r.natalPhase.name}（日月差 ${r.natalElong.toFixed(1)}°）。次限推运日月差每年约 ${PROG_ELONG_RATE}°，约 ${SYNODIC_YEARS.toFixed(1)} 年走完一轮八相。`);
	lines.push('');
	lines.push('| 起始年龄 | 日期 | 月相 | 关键词 |');
	lines.push('| --- | --- | --- | --- |');
	r.timeline.forEach((t) => {
		lines.push(`| ${t.age.toFixed(1)} 岁${t.isStart ? '(本命)' : ''} | ${t.date || '-'} | ${t.phase.name} | ${t.phase.keyword} |`);
	});
	return lines.join('\n');
}

export default { buildLunationPhases, buildLunationPhaseSnapshotText, computeLunationPhase, phaseAtAge, PHASES_8, LUNATION_DEFAULT_OPTS };
