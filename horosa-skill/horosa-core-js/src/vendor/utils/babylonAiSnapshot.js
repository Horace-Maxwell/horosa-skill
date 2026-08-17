// utils/babylonAiSnapshot.js —— 巴比伦占星 AI 快照 headless builder(轻依赖:纯逻辑 + request,
// 不 import 任何巴比伦组件,避免把组件链拖进 aiAnalysisContext 饿链)。
// 快照 = 恒星黄道(毕宿锚)盘 + 算术历日 + 七曜清单 + 分至天狼星 + 「位」三法 + 行星神性。

import * as AstroConst from '../constants/AstroConst.js';
import { buildHoroscope, PLANET_ORDER } from '../babylon/horoscope.js';
import { babylonSign, BABYLON_PLANETS } from '../divination/data/babylonianData.js';
import { julianDayIndex } from './julianDayIndex.js';

import { kalendertextD, kalendertextK, lonToSchematicDate } from '../babylon/microzodiac.js';
import { lonToSignDeg } from '../babylon/units.js';

// 出生 ±183 日窗口的实算历象(朔望/邻近食;/astroextra/ephemeris)。
// 公元 1 年前(远古纪元)不请求 —— 历日串口径不一,图式方案照常显示。
export const EPHEM_MIN_JDN = 1721426;
// 指定历日的日/月升落(供 NA/KUR 实算;单日窗口)
// 满月日 NA = 日出→月落;残月晨 KUR = 月出→日出(单位 UŠ = 4 分钟;仅当次序成立时给值)
export function usBetween(fromJd, toJd){
	if(!Number.isFinite(fromJd) || !Number.isFinite(toJd)){ return null; }
	const us = (toJd - fromJd) * 24 * 60 / 4;
	return (us > 0 && us < 90) ? Math.round(us * 10) / 10 : null;   // 时距合理域(<6h)
}
// 由 ephemeris 结果整理「Lunar Three 与邻近食」(纯函数,jest 可测)
export function digestBabylonEphemeris(ephem, birthJdn2){
	if(!ephem){ return null; }
	const phases = (ephem.lunarPhases || []).filter((p) => p.phase === 'Full Moon' || p.phase === 'New Moon');
	const byNear = (arr) => arr.slice().sort((a, b) => Math.abs(a.jd - birthJdn2) - Math.abs(b.jd - birthJdn2));
	const fullBefore = byNear(phases.filter((p) => p.phase === 'Full Moon' && p.jd <= birthJdn2))[0] || null;
	const newNear = byNear(phases.filter((p) => p.phase === 'New Moon'))[0] || null;
	const ecl = byNear(ephem.eclipses || []).slice(0, 2).map((e) => ({
		date: e.date,
		kind: e.type === 'solar_eclipse' ? '日食' : '月食',
		sub: e.eclipseType === 'total' ? '全食' : (e.eclipseType === 'annular' ? '环食' : (e.eclipseType === 'partial' ? '偏食' : (e.eclipseType || ''))),
		digit: e.digit,          // 食分(finger,月/日径 1/12)—— 与楔文口径同构
		sign: e.sign,
		before: e.jd < birthJdn2,
	}));
	return { fullBefore, newNear, eclipses: ecl };
}

// 恒星黄道(毕宿锚)排盘参数:仅覆盖 zodiacal/siderealAyanamsa,余随生辰。
export function babylonChartParams(fields){
	if(!fields || !fields.date || !fields.date.value){ return null; }
	const v = (k, d) => (fields[k] && fields[k].value !== undefined ? fields[k].value : d);
	return {
		date: fields.date.value.format('YYYY/MM/DD'),
		time: fields.time && fields.time.value ? fields.time.value.format('HH:mm:ss') : '12:00:00',
		ad: v('ad', 1),
		zone: v('zone', '+08:00'),
		lat: v('lat', ''),
		lon: v('lon', ''),
		gpsLat: v('gpsLat', ''),
		gpsLon: v('gpsLon', ''),
		hsys: v('hsys', 0),
		zodiacal: 1,
		siderealAyanamsa: 'aldebaran_15tau',
		tradition: 1,
		strongRecption: v('strongRecption', 0),
		simpleAsp: v('simpleAsp', 0),
		virtualPointReceiveAsp: v('virtualPointReceiveAsp', 0),
		predictive: 0,
		name: v('name', ''),
		pos: v('pos', ''),
	};
}

const OBJ_KEYS = {
	[AstroConst.MOON]: 'moon', [AstroConst.SUN]: 'sun', [AstroConst.JUPITER]: 'jupiter',
	[AstroConst.VENUS]: 'venus', [AstroConst.MERCURY]: 'mercury', [AstroConst.SATURN]: 'saturn', [AstroConst.MARS]: 'mars',
};
export function chartToLons(chartObj){
	const inner = chartObj && chartObj.chart ? chartObj.chart : (chartObj || {});
	const out = {};
	(inner.objects || []).forEach((o) => {
		const k = OBJ_KEYS[o.id];
		if(k && Number.isFinite(Number(o.lon))){ out[k] = Number(o.lon); }
	});
	return out;
}

// 出生 JDN:DateTime 实例走权威 getOnlyDateNum;moment 形态回退 julianDayIndex 同轴。
export function babylonBirthJdn(fields){
	if(!fields || !fields.date || !fields.date.value){ return null; }
	const d = fields.date.value;
	if(typeof d.getOnlyDateNum === 'function'){ return d.getOnlyDateNum(); }
	if(typeof d.year === 'function'){
		const adv = Number(fields.ad && fields.ad.value);
		const signedYear = adv < 0 ? -Math.abs(d.year()) : Math.abs(d.year());
		return julianDayIndex(signedYear, d.month() + 1, d.date());
	}
	return null;
}

function degMin(deg){
	const d = Math.floor(deg);
	const m = Math.round((deg - d) * 60);
	return m >= 60 ? `${d + 1}°0′` : `${d}°${m}′`;
}
const EN_SIGN_CN = { Aries: '白羊', Taurus: '金牛', Gemini: '双子', Cancer: '巨蟹', Leo: '狮子', Virgo: '处女', Libra: '天秤', Scorpio: '天蝎', Sagittarius: '射手', Capricorn: '摩羯', Aquarius: '水瓶', Pisces: '双鱼' };
function zhSign(en){ return EN_SIGN_CN[en] || en || ''; }

// bab(buildHoroscope 结果)→ 快照文本(段名与 AI 导出 preset 对齐)
export function buildBabylonSnapshotText(bab, opts){
	if(!bab){ return ''; }
	const o = opts || {};
	const lines = [];
	lines.push('[起盘信息]');
	// [V6-W2] 兜底串锚:'现代实位·A 规范' 必须与 babylonSchools swissA10(默认档).cn 逐字一致
	// (挂载有齿轮时上游已传 schemeCn=真实档名;无齿轮=默认档,此兜底即默认档名的事实标注)。
	lines.push(`技法:巴比伦占星(美索不达米亚天象体系);坐标:恒星黄道 · 毕宿锚(Aldebaran=金牛15°);派系:${o.schemeCn || '现代实位·A 规范'};分至规范:${o.solstice === 'B8' ? '春分白羊 8°' : '春分白羊 10°'}。`);
	lines.push(`出生历日(算术历):${bab.babylonianDateText};19 年周期第 ${bab.babylonianDate.cycleYear} 年;该月${bab.monthLen === 30 ? '满(30 日)' : '缺(29 日)'}。算术历与逐月观测实历可差 ±1–2 日。`);
	lines.push('本体系无十二宫位、无相位、无上升点——星盘为数据清单,解读装置为「位」(三分+日段)与行星神性吉凶。');
	lines.push('');
	lines.push('[七曜按宫]');
	lines.push('固定序 月-日-木-金-水-土-火(吉→中→凶编排序,非空间序):');
	bab.rows.forEach((r) => {
		if(r.missing){ return; }
		const si = r.signInfo || {};
		const marks = [];
		if(r.combust){ marks.push('已没 ŠÚ(与日同,不可见)'); }
		if(r.inExalt){ marks.push('在其秘密之屋(旺宫)'); }
		if(r.inOwnTrip){ marks.push('在其本三分之宫'); }
		lines.push(`${r.cn}:${si.cn || ''} ${degMin(r.deg)}(${si.cune || ''});${r.nature}${marks.length ? ';' + marks.join(';') : ''}`);
	});
	lines.push('');
	lines.push('[分至天狼星]');
	const u = bab.uruk && bab.uruk.text ? bab.uruk.text : {};
	lines.push(`该年图式方案(19 年周期):春分 ${u.ve || '—'};夏至 ${u.ss || '—'};秋分 ${u.ae || '—'};冬至 ${u.ws || '—'}。`);
	lines.push(`天狼星:偕日升 ${u.siriusRise || '—'};偕日没 ${u.siriusSet || '—'}(图式推得,非实测)。`);
	// 实算历象(可得时并入本段:手册模板 (c)(e) 项——Lunar Three 与邻近食;不新增段名,零段表迁移)
	const dg = o.ephemDigest;
	if(dg){
		if(dg.fullBefore){ lines.push(`出生前最近满月:${dg.fullBefore.date}(月在${zhSign(dg.fullBefore.sign)})${dg.na ? `,该日 NA(日出→月落)≈ ${dg.na} UŠ` : ''};最近新月:${dg.newNear ? dg.newNear.date : '—'}${dg.kur ? `,残月晨 KUR(月出→日出)≈ ${dg.kur} UŠ` : ''}。`); }
		if(dg.eclipses && dg.eclipses.length){
			lines.push(`出生邻近之食:${dg.eclipses.map((e) => `${e.date} ${e.kind}${e.sub ? '·' + e.sub : ''}${e.digit ? `(食分 ${e.digit} 指)` : ''}${e.before ? '(生前)' : '(生后)'}`).join(';')}。`);
		}
	}
	lines.push('');
	lines.push('[位三法]');
	const bn = bab.bitNisirti || {};
	lines.push(`① 近生分至月三分主:${bn.bySolsticeMonth ? `${bn.bySolsticeMonth.lordCn}(组 ${bn.bySolsticeMonth.cn})` : '—'}。`);
	const ownTrip = bab.rows.filter((r) => !r.missing && r.inOwnTrip).map((r) => r.cn);
	lines.push(`② 行星实宫三分:${ownTrip.length ? ownTrip.join('、') + '——兴旺、平安之位' : '本盘无行星落其本三分'}。`);
	lines.push(`③ 生日日段主:第 ${bab.babylonianDate.day} 日 → ${bn.byDaySegment ? bn.byDaySegment.cn + '星段' : '—'}。`);
	lines.push('「位」为三分+日段方案,非希腊宫位;楔文旺位只给宫,度数属希腊叠加。');
	lines.push('');
	lines.push('[行星神性]');
	bab.rows.forEach((r) => {
		if(r.missing){ return; }
		const p = BABYLON_PLANETS.find((x) => x.key === r.key) || {};
		lines.push(`${r.cn}:${r.god}${r.number ? `(圣数 ${r.number})` : ''} · ${r.nature} · ${p.note || ''}`);
	});
	if(bab.land){
		lines.push(`出生月所主之国(月食地理):${bab.land.land}(${bab.land.dir}方)。`);
	}
	// [微黄道] 月/日两点的 144 微段定位(×12/×13/×277 三联),与微黄道页同一套纯函数;
	// 无点位(缺盘)则整段不产,零空段。
	const mzRows = ['moon', 'sun']
		.map((k) => bab.rows.find((r) => r.key === k))
		.filter((r) => r && !r.missing && r.lon !== undefined && r.lon !== null);
	if(mzRows.length){
		lines.push('');
		lines.push('[微黄道]');
		lines.push(`十二分变体:${o.dodecaVariant === 'A' ? 'A(加于宫起点)' : 'B(加于点本身/楔文)'};微段 = 2;30°,全周 144 段。`);
		mzRows.forEach((r) => {
			const dd = r.dodeca || {};
			const micro = babylonSign(dd.microSign) || {};
			const d13 = lonToSignDeg(kalendertextD(r.lon));
			const s13 = babylonSign(d13.sign) || {};
			const dt = lonToSchematicDate(kalendertextK(r.lon));
			lines.push(`${r.cn}:${(r.signInfo || {}).cn || ''} ${degMin(r.deg)} → ×12 微宫 ${micro.cn || dd.microSign || '—'};×13 图式月位 ${s13.cn || ''} ${degMin(d13.deg)};×277 历日 第${dt.M}月第${Math.round(dt.d)}日。`);
		});
	}
	return lines.join('\n');
}

// 命盘挂载 headless 复算入口(record→fields 已由调用侧 buildFieldObject 完成)
