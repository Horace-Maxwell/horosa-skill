// 东亚诸术:由出生资料(加本命盘星位)算出整页的数据,并写成 AI 快照文字。页面与无头挂载共用这一份。
import {
	eastAsiaFacts, tibetanCivilDayNumber, tibetanDateOfDayNumber, tibetanYearInfo, rabjungText, WEEKDAY_PLANETS,
	yearParkha, dayParkha, mewaSet, lunarDayMewa, calendarDayMewa, MEWA_COLOR, forcesOf, zurkhaiAspect, ZURKHAI_RELATION,
	sanmeigaku, tenchusatsuYears, nineStarKi, loshuTransit, ichingRows, ichingProgression, hexName, trigramName,
} from './eastAsiaArts.js';
import { parseGeoDegrees } from '../bazi/baziLunarLocal.js';
import { parseZoneHours } from '../utils/beijingTimeShift.js';
import { definePageSettings } from '../utils/pageSettingsStore.js';
import { normBinaryGender } from '../utils/kinAstroFieldsSync.js';
import { resolveGeoZone } from '../utils/timezone.js';
import { geoNameFieldPatch } from '../utils/geoName.js';
// headless：AstroHelper 顶层 import d3 + DOM helper，不能整份载入；这两个函数只被 geoChangeFieldsPatch（页面左栏选点的字段补丁）用到。
function convertLatToStr(){ throw new Error('eastAsiaSnapshot.geoChangeFieldsPatch 是页面专用（headless 没有 AstroHelper.convertLatToStr）'); }
function convertLonToStr(){ throw new Error('eastAsiaSnapshot.geoChangeFieldsPatch 是页面专用（headless 没有 AstroHelper.convertLonToStr）'); }

// 左栏选地点 → 字段补丁(坐标 + 按地点校正时区,钟面时刻不变;与「其他」页策天同一做法)。东亚 / 诸方两页共用:
// 藏历民用日按当地经度 5 点起算,易卦宫卦、灵名字母读本命盘上升与宫头,都随地点变。
export function geoChangeFieldsPatch(fields, rec){
	if(!rec){ return null; }
	const f = fields || {};
	const dDt = f.date && f.date.value;
	const tDt = f.time && f.time.value;
	const ds = (dDt && dDt.format) ? dDt.format('YYYY-MM-DD') : null;
	const z = resolveGeoZone(rec, ds);
	const payload = {
		lon: { value: convertLonToStr(rec.lng) },
		lat: { value: convertLatToStr(rec.lat) },
		gpsLon: { value: rec.gpsLng },
		gpsLat: { value: rec.gpsLat },
	};
	if(z){
		payload.zone = { value: z };
		if(dDt && dDt.clone){ const nd = dDt.clone(); nd.setZone(z); payload.date = { value: nd }; payload.ad = { value: nd.ad }; }
		if(tDt && tDt.clone){ const nt = tDt.clone(); nt.setZone(z); payload.time = { value: nt }; }
	}
	Object.assign(payload, geoNameFieldPatch(rec));
	return payload;
}

// 页面字段 → 本技法入参(页面与无头挂载同一份)
export function eastAsiaParamsFromFields(fields){
	const f = fields || {};
	const v = (k)=>(f[k] && f[k].value !== undefined ? f[k].value : undefined);
	const date = v('date');
	const time = v('time');
	return {
		date: date && date.format ? date.format('YYYY/MM/DD') : '',
		time: time && time.format ? time.format('HH:mm:ss') : '12:00:00',
		zone: date && date.zone ? date.zone : v('zone'),
		ad: date && date.ad !== undefined ? date.ad : 1,
		lat: v('lat'),
		lon: v('lon'),
		gender: normBinaryGender(v('gender')),
	};
}

// label 是右栏页签上的短名(六个页签在 1440 宽窗口的右栏也要一排放下,不收进「…」);full 是全名(悬停提示)
export const EAST_ASIA_TABS = [
	{ key: 'tibetan', label: '藏历藏占', full: '藏历藏占' },
	{ key: 'zurkhai', label: '蒙古', full: '蒙古 Zurkhai' },
	{ key: 'sanmei', label: '算命学', full: '算命学' },
	{ key: 'ninestar', label: '九星', full: '九星气学' },
	{ key: 'loshu', label: '洛书', full: '洛书流年' },
	{ key: 'iching', label: '易卦', full: '易卦星盘' },
];

// 藏历日期文字(页面与快照同一份):「2026 年 9 月 29 日」
export function tibetanDateText(d, withMarks){
	if(!d){ return '—'; }
	const marks = withMarks ? `${d.extra ? '(重日)' : ''}${d.skippedDay ? `(本日跳过 ${d.skippedDay} 日)` : ''}` : '';
	return `${d.year} 年 ${d.leap ? '闰' : ''}${d.month} 月 ${d.day} 日${marks}`;
}

// 页面设置:当前页签(视图态,随页记住)、算命学藏干表、易卦合卦规则
export const EAST_ASIA_PAGE_SETTINGS = definePageSettings('horosa.dongya.settings.v1', {
	tab: { label: '当前页签', def: 'tibetan', oneOf: EAST_ASIA_TABS.map((t)=>t.key) },
	fenyeVersion: { label: '算命学·藏干表(通行版 / 法诀版)', def: 'common', oneOf: ['common', 'fajue'] },
	ichingMerge: { label: '易卦星盘·星卦合入(地平上下 / 恒合上卦 / 恒合下卦)', def: 'horizon', oneOf: ['horizon', 'upper', 'lower'] },
});

const SECTION_TITLES = ['藏历', '藏占', '蒙古 Zurkhai', '算命学', '九星气学', '洛书流年', '易卦星盘'];
export const EAST_ASIA_SNAPSHOT_SECTIONS = SECTION_TITLES;

function planetCn(id){
	return { Sun: '太阳', Moon: '月亮', Mercury: '水星', Venus: '金星', Mars: '火星', Jupiter: '木星', Saturn: '土星' }[id] || id;
}

function chartPlanets(chartObj){
	const chart = chartObj && (chartObj.chart || chartObj);
	const objects = chart && Array.isArray(chart.objects) ? chart.objects : [];
	return objects.map((o)=>{
		const m = `${o.house || ''}`.match(/(\d+)/);
		return { id: o.id, lon: Number(o.lon), house: m ? Number(m[1]) : null };
	});
}

function todayDayNumber(lonEast, nowMs){
	const jd = (Number(nowMs) || Date.now()) / 86400000 + 2440587.5;
	return tibetanCivilDayNumber(jd, lonEast);
}

/**
 * params:{ date:'YYYY/MM/DD', time, zone, lat, lon, gender(1 男 / 0 女) };chartObj 可空(易卦星盘就不出)。
 * settings:{ fenyeVersion, ichingMerge, flowYear(藏历年,缺省今年) };nowMs 供测试固定「今天」。
 */
export function buildEastAsiaModel(params, chartObj, settings, nowMs){
	const p = params || {};
	const opts = settings || {};
	const facts = eastAsiaFacts(p);
	if(!facts){ return null; }
	const male = Number(p.gender) !== 0;
	const zone = parseZoneHours(p.zone);
	const lonEast = parseGeoDegrees(p.lon, 180);
	const lon = Number.isFinite(lonEast) ? lonEast : 0;
	const jdUt = facts.julianDay - (Number.isFinite(zone) ? zone : 0) / 24;
	const birthDay = tibetanCivilDayNumber(jdUt, lon);
	const tib = tibetanDateOfDayNumber(birthDay);
	const birthYear = tibetanYearInfo(tib.year);
	const today = tibetanDateOfDayNumber(todayDayNumber(lon, nowMs));
	const userYear = Number.isFinite(Number(opts.flowYear)) && Number(opts.flowYear) > 0 ? Number(opts.flowYear) : null;
	const flowYear = userYear || today.year;                                   // 藏占:藏历年
	// 「今年」按盘的时区取(东八区元旦凌晨取 UTC 年会差一年)
	const civilNow = new Date((Number(nowMs) || Date.now()) + (Number.isFinite(zone) ? zone : 0) * 3600000).getUTCFullYear();
	const civilFlowYear = userYear || civilNow;                                 // 洛书 / 天中杀:公历年
	const age = flowYear - tib.year + 1;
	const mewa = mewaSet(tib.year, flowYear);
	const sm = sanmeigaku(facts, opts.fenyeVersion);
	const zurkhai = zurkhaiAspect(facts.year.zhi, facts.month.zhi);
	const planets = chartPlanets(chartObj);
	const iching = planets.length ? ichingRows(planets, opts.ichingMerge) : [];
	const todayJd = (Number(nowMs) || Date.now()) / 86400000 + 2440587.5;
	return {
		facts,
		male,
		flowYear,
		tibetan: {
			date: tib, year: birthYear, weekday: WEEKDAY_PLANETS[((birthDay + 1) % 7 + 7) % 7], dayNumber: birthDay,
			today,
		},
		parkha: {
			age,
			year: yearParkha(age, male),
			day: dayParkha(tib.month, tib.day),
			years: Array.from({ length: 9 }, (_, i)=>({ year: flowYear + i, age: age + i, parkha: yearParkha(age + i, male) })),
		},
		mewa: { ...mewa, lunarDay: lunarDayMewa(tib.month, tib.day), calendarDay: calendarDayMewa(birthDay) },
		forces: forcesOf(birthYear.animalIndex),
		zurkhai: { yearZhi: facts.year.zhi, monthZhi: facts.month.zhi, yearGz: facts.year.gz, monthGz: facts.month.gz, aspect: zurkhai, relation: ZURKHAI_RELATION[zurkhai] || '' },
		sanmei: sm ? { ...sm, years: tenchusatsuYears(sm.tenchusatsu, civilFlowYear, 4) } : null,
		ninestar: nineStarKi(facts),
		loshu: Array.from({ length: 9 }, (_, i)=>loshuTransit(facts.civil.year, civilFlowYear + i)),
		iching: { rows: iching, merge: opts.ichingMerge || 'horizon', progression: ichingProgression(todayJd - jdUt) },
	};
}

const mewaText = (v)=>`${v}${MEWA_COLOR[v] || ''}`;
const parkhaText = (pk)=>(pk ? `${pk.gua}(${pk.tib},${pk.dir},${pk.element})` : '—');
const MERGE_CN = { horizon: '地平上合上卦、地平下合下卦', upper: '恒合上卦', lower: '恒合下卦' };

export function eastAsiaSnapshotLines(model){
	if(!model){ return []; }
	const out = [];
	const t = model.tibetan;
	const d = t.date;
	out.push('[藏历]');
	out.push(`出生藏历:${tibetanDateText(d, true)},${t.weekday}曜日`);
	out.push(`年:${t.year.element}${t.year.male ? '阳' : '阴'}${t.year.animal}年,${rabjungText(t.year)};真太阳 ${d.trueSun.toFixed(2)}°`);
	out.push('[藏占]');
	out.push(model.parkha.age < 1
		? `${model.flowYear} 年早于出生(藏历生年 ${d.year} 年):没有流年八卦;出生日八卦 ${parkhaText(model.parkha.day)}`
		: `${model.flowYear} 年 ${model.parkha.age} 岁(${model.male ? '男' : '女'}命):流年八卦 ${parkhaText(model.parkha.year)};出生日八卦 ${parkhaText(model.parkha.day)}`);
	out.push(`九宫:本命 ${mewaText(model.mewa.birth)} · 当年 ${mewaText(model.mewa.year)} · 生命力 ${mewaText(model.mewa.vitality)} · 个人力 ${mewaText(model.mewa.power)} · 下降 ${mewaText(model.mewa.descending)} · 太阴日 ${mewaText(model.mewa.lunarDay)} · 历日 ${mewaText(model.mewa.calendarDay)}`);
	out.push(`魂命煞(${t.year.animal}年):${model.forces.map((f)=>`${f.label} ${f.value}`).join(';')}`);
	out.push('[蒙古 Zurkhai]');
	const z = model.zurkhai;
	out.push(`年支 ${z.yearZhi} · 月支 ${z.monthZhi} · 相位 ${z.aspect}${z.relation ? `(${z.relation})` : ''}`);
	out.push('[算命学]');
	const sm = model.sanmei;
	if(sm){
		out.push(`三柱:${sm.pillars.map((p)=>`${p.label}柱 ${p.gz}`).join(' · ')};节入 ${sm.prevJie || ''} 后 ${sm.daysAfterJie} 日`);
		out.push(`藏干(按节入日数):${sm.hidden.map((h)=>`${h.label}支 ${h.zhi} → ${h.ruler || '—'}(${h.rulerPos || ''})`).join(';')}`);
		out.push(`天中杀:${sm.tenchusatsu.join('')}${sm.years.length ? `;近年 ${sm.years.map((y)=>`${y.year}(${y.zhi})`).join('、')}` : ''}`);
		if(sm.relations.length){ out.push(`三支关系:${sm.relations.map((r)=>`${r.a}${r.b} ${r.kind} ${r.text}`).join(';')}`); }
	}
	out.push('[九星气学]');
	const k = model.ninestar;
	if(k){ out.push(`本命星 ${k.honmeiName} · 月命星 ${k.getsumeiName}${k.nichimeiName ? ` · 日命星 ${k.nichimeiName}${k.nichimeiDun ? `(${k.nichimeiDun})` : ''}` : ''}(立春年 ${k.year})`); }
	out.push('[洛书流年]');
	const ls = model.loshu[0];
	if(ls && ls.beforeBirth){
		out.push(`${ls.year} 年早于出生(公历生年 ${model.facts.civil.year} 年),不排洛书流年。`);
		const later = model.loshu.filter((r)=>!r.beforeBirth);
		if(later.length){ out.push(`出生后当年数:${later.map((r)=>`${r.year} ${r.active}`).join('、')}`); }
	}else if(ls){
		out.push(`${ls.year} 年(${ls.age} 岁):中宫 ${ls.center},当年数 ${ls.active};${ls.cells.map((c)=>`${c.label} ${c.value}${c.active ? '★' : ''}`).join(' ')}`);
		out.push(`其后八年当年数:${model.loshu.slice(1).map((r)=>`${r.year} ${r.active}`).join('、')}`);
	}
	out.push('[易卦星盘]');
	const ic = model.iching;
	if(ic.rows.length){
		out.push(`合卦规则:${MERGE_CN[ic.merge] || ic.merge}`);
		ic.rows.forEach((r)=>{
			out.push(`${planetCn(r.id)}(${trigramName(r.trigram)}):度卦 ${hexName(r.degree)} → ${hexName(r.degreeMerged)};座卦 ${hexName(r.sign_)} → ${hexName(r.signMerged)}${r.house_ ? `;宫卦 ${hexName(r.house_)} → ${hexName(r.houseMerged)}` : ''}`);
		});
	}else{
		out.push('没有本命盘星位,易卦星盘未出。');
	}
	out.push(`易卦推运:今日环位 ${ic.progression.position},${hexName(ic.progression.hexagram)}`);
	return out;
}

export function buildEastAsiaSnapshotText(params, chartObj, settings, nowMs){
	return eastAsiaSnapshotLines(buildEastAsiaModel(params, chartObj, settings, nowMs)).join('\n');
}
