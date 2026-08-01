// tongshu/xuankong.js — 三元玄空大卦择日法引擎（纯前端）。
// 日课四柱 → 六十甲子配六十四卦 → 玄空五行数(1-9,无5)+卦运；五吉（生入/克入/同旺/生成/合十）；
// 日课吉凶：上上吉(年月时对日皆五吉)/上吉(月时或年时对日五吉)/吉(时对日五吉)；卦运格局(卦不出位/合十/一气清纯)。
// 天人配合：日对主事仙命(60甲子)成五吉。坐向须六十四卦天圆图（源未载 24 山→64 卦，本引擎从缺、如实标注）。
import { Solar } from 'lunar-javascript';
import { LIUSHI_JIAZI_GUA } from './xuankongData.js';

const TIANGAN = ['甲', '乙', '丙', '丁', '戊', '己', '庚', '辛', '壬', '癸'];
const DIZHI = ['子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥'];
// 玄空五行元素由数派生（河图：一六水/二七火/三八木/四九金；5 中土不入卦）。
const HETU_ELEM = { 1: '水', 6: '水', 2: '火', 7: '火', 3: '木', 8: '木', 4: '金', 9: '金' };
const SHENG = { 水: '木', 木: '火', 火: '土', 土: '金', 金: '水' };   // 生：key 生 value
const KE = { 水: '火', 火: '金', 金: '木', 木: '土', 土: '水' };      // 克：key 克 value

function elemOf(n) { return HETU_ELEM[n] || ''; }
function sameGroup(a, b) { return elemOf(a) && elemOf(a) === elemOf(b); }

// 五机全判：other 柱对 self（日）柱。进神五吉(生入/克入/同旺/生成/合十)=吉；
// 退神(生出=日气外泄 / 克出=日气受耗)=凶；仅缺数据时为平。返回 { type, jx }。
export function wujiRel(selfN, otherN) {
	if (!selfN || !otherN) { return { type: '', jx: 'neutral' }; }
	if (selfN === otherN) { return { type: '同旺', jx: 'good' }; }
	if (sameGroup(selfN, otherN)) { return { type: '生成', jx: 'good' }; }   // 河图同组（如 4-9）
	if (selfN + otherN === 10) { return { type: '合十', jx: 'good' }; }       // 归中旺气
	const se = elemOf(selfN);
	const oe = elemOf(otherN);
	if (SHENG[oe] === se) { return { type: '生入', jx: 'good' }; }            // other 生 self（进神）
	if (KE[oe] === se) { return { type: '克入', jx: 'good' }; }               // other 克 self（进神）
	if (SHENG[se] === oe) { return { type: '生出', jx: 'bad' }; }             // self 生 other（日气外泄·退神）
	if (KE[se] === oe) { return { type: '克出', jx: 'bad' }; }                // self 克 other（日气受耗·退神）
	return { type: '无关', jx: 'neutral' };
}

// 五吉判定（向后兼容）：other 柱对 self（日）柱，返回吉型名或 null（消费方按真值性判五吉）。
export function wuji(selfN, otherN) {
	const r = wujiRel(selfN, otherN);
	return r.jx === 'good' ? r.type : null;
}

function pillar(gz) {
	const g = LIUSHI_JIAZI_GUA[gz];
	if (!g) { return { gz, gua: '', wxNum: null, wxElem: '', yun: null }; }
	return { gz, gua: g.gua, wxNum: g.wxNum, wxElem: HETU_ELEM[g.wxNum] || '', yun: g.yun };
}

// 五鼠遁：日干 → 时柱干支。
function timeGanZhi(dayGan, hourZhi) {
	const dgi = TIANGAN.indexOf(dayGan);
	const hzi = DIZHI.indexOf(hourZhi);
	const tgi = ((dgi % 5) * 2 + hzi) % 10;
	return TIANGAN[tgi] + hourZhi;
}

// 卦运格局（日课四柱；以日柱为主）。
function gejuOf({ year, month, day, time }) {
	const ys = [year, month, day, time].filter((y)=> y != null);
	if (ys.length < 4) { return null; }
	if (ys.every((y)=> y === ys[0])) { return { name: '卦不出位·一气清纯', jx: 'good', note: '四柱卦运皆同，速发日课' }; }
	// 挨星合十：年月时卦运各与日卦运合十（三元不败日课）。
	if (day != null && (year + day === 10) && (month + day === 10) && (time + day === 10)) {
		return { name: '玄空挨星·卦运合十', jx: 'good', note: '年月时卦运皆与日合十，三元不败日课' };
	}
	// 大卦五行全同（一卦清纯，比和旺气）。
	return null;
}

// 单个时辰的玄空日课（年月日固定 + 该时柱），可选主事仙命。
export function xuankongForHour({ y, m, d, hourZhi }, mingYear) {
	const solar = Solar.fromYmd(y, m, d);
	const lunar = solar.getLunar();
	const yearGZ = lunar.getYearInGanZhiByLiChun ? lunar.getYearInGanZhiByLiChun() : lunar.getYearInGanZhi();
	const monthGZ = lunar.getMonthInGanZhi();
	const dayGZ = lunar.getDayInGanZhi();
	const timeGZ = timeGanZhi(dayGZ[0], hourZhi);

	const P = { year: pillar(yearGZ), month: pillar(monthGZ), day: pillar(dayGZ), time: pillar(timeGZ) };
	const dN = P.day.wxNum;
	const relTime = wujiRel(dN, P.time.wxNum);
	const relMonth = wujiRel(dN, P.month.wxNum);
	const relYear = wujiRel(dN, P.year.wxNum);
	const wj = {
		// 兼容旧字段：五吉名或 null（生出/克出/无关 皆 null）。
		timeVsDay: relTime.jx === 'good' ? relTime.type : null,
		monthVsDay: relMonth.jx === 'good' ? relMonth.type : null,
		yearVsDay: relYear.jx === 'good' ? relYear.type : null,
		// 退神明细（生出/克出）供显示标凶。
		timeRel: relTime.type, monthRel: relMonth.type, yearRel: relYear.type,
	};
	// 日课吉凶等级（以时对日为主）。时对日退神(生出/克出=泄耗)→凶；五吉再按年月叠档。
	const t = relTime.jx === 'good', mo = relMonth.jx === 'good', yr = relYear.jx === 'good';
	let level;
	if (relTime.jx === 'bad') { level = { name: '凶', jx: 'bad' }; }   // 时泄/耗日气，退神不宜
	else if (t && mo && yr) { level = { name: '上上吉', jx: 'good' }; }
	else if (t && (mo || yr)) { level = { name: '上吉', jx: 'good' }; }
	else if (t) { level = { name: '吉', jx: 'good' }; }
	else { level = { name: '平/不合', jx: 'neutral' }; }

	const geju = gejuOf({ year: P.year.yun, month: P.month.yun, day: P.day.yun, time: P.time.yun });

	// 天人：日对仙命。
	let ming = null;
	let dayVsMing = null;
	let dayVsMingRel = '';
	if (mingYear && LIUSHI_JIAZI_GUA[mingYear]) {
		ming = pillar(mingYear);
		const relMing = wujiRel(ming.wxNum, P.day.wxNum);   // 日(other)对仙命(self)
		dayVsMing = relMing.jx === 'good' ? relMing.type : null;   // 兼容旧字段（五吉名或 null）
		dayVsMingRel = relMing.type;                               // 完整五机名（含退神）
	}

	return { y, m, d, hourZhi, pillars: P, wuji: wj, level, geju, ming, dayVsMing, dayVsMingRel };
}

// 一日 12 时辰玄空日课概览（年月日固定，时柱变）。
export function xuankongDay({ y, m, d }, mingYear) {
	const rows = DIZHI.map((hz)=>{
		const r = xuankongForHour({ y, m, d, hourZhi: hz }, mingYear);
		return {
			hourZhi: hz, timeGZ: r.pillars.time.gz, timeGua: r.pillars.time.gua,
			level: r.level, timeVsDay: r.wuji.timeVsDay,
		};
	});
	const base = xuankongForHour({ y, m, d, hourZhi: '子' }, mingYear);
	return {
		y, m, d,
		year: base.pillars.year, month: base.pillars.month, day: base.pillars.day,
		ming: base.ming,
		rows,
		bestHours: rows.filter((x)=> x.level.name === '上上吉' || x.level.name === '上吉').map((x)=> `${x.hourZhi}时(${x.level.name})`),
	};
}

export default xuankongDay;
