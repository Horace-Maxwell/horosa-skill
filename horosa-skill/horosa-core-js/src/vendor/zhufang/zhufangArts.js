// 诸方杂术:玛雅历、十三月亮历(前端纯算)+ 人类图、灵名字母(后端 /astroextra/zhufang)。页面与无头挂载共用。
//
// 玛雅历:长历日数 = 儒略日数 − 关联常数(缺省 584283,可选 584285 / 584286)。卓尔金 260 日、哈布 365 日、
//   历轮、十三日组、九夜神都是这个日数取模:日数 0 = 4 Ajaw 8 Kumk'u,夜神 G9。
// 十三月亮历:Kin = ((34 − 1 + n) mod 260) + 1,n = 该民用日与 1987-07-26 相差的日数,2 月 29 日不计数;
//   调性 = (Kin − 1) mod 13 + 1,图腾 = (Kin − 1) mod 20 + 1。一年从 7 月 26 日起,13 个月各 28 日,7 月 25 日是「无时间日」。
import { definePageSettings } from '../utils/pageSettingsStore.js';
import { normBinaryGender } from '../utils/kinAstroFieldsSync.js';

export const ZHUFANG_TABS = [
	{ key: 'mayan', label: '玛雅历' },
	{ key: 'dreamspell', label: '十三月亮历' },
	{ key: 'hd', label: '人类图' },
	{ key: 'spirit', label: '灵名字母' },
];
export const MAYAN_CORRELATIONS = [584283, 584285, 584286];

export const ZHUFANG_PAGE_SETTINGS = definePageSettings('horosa.zhufang.settings.v1', {
	tab: { label: '当前页签', def: 'mayan', oneOf: ZHUFANG_TABS.map((t)=>t.key) },
	mayanCorrelation: { label: '玛雅历·关联常数', def: 584283, oneOf: MAYAN_CORRELATIONS },
	hdTrueNode: { label: '人类图·交点(真交点 / 平交点)', def: true },
	spiritQuadrant: { label: '灵名字母·象限(1/4/7/10 · 2/5/8/11 · 3/6/9/12)', def: 1, oneOf: [1, 2, 3] },
});

export const ZHUFANG_SNAPSHOT_SECTIONS = ['玛雅历', '十三月亮历', '人类图', '灵名字母'];

// ─────────────────────────── 玛雅历 ───────────────────────────
export const TZOLKIN_NAMES = ['Imix 鳄', 'Ik\' 风', 'Ak\'b\'al 夜', 'K\'an 种子', 'Chikchan 蛇', 'Kimi 死', 'Manik\' 鹿', 'Lamat 星', 'Muluk 水', 'Ok 犬',
	'Chuwen 猴', 'Eb\' 草', 'B\'en 芦', 'Ix 豹', 'Men 鹰', 'K\'ib\' 秃鹫', 'Kab\'an 地', 'Etz\'nab\' 燧石', 'Kawak 雨', 'Ajaw 王'];
export const HAAB_MONTHS = ['Pop', 'Wo\'', 'Sip', 'Sotz\'', 'Sek', 'Xul', 'Yaxk\'in', 'Mol', 'Ch\'en', 'Yax', 'Sak\'', 'Keh', 'Mak', 'K\'ank\'in',
	'Muwan', 'Pax', 'K\'ayab', 'Kumk\'u', 'Wayeb\''];
const mod = (a, n)=>((a % n) + n) % n;

export function gregorianToJdn(y, m, d){
	const a = Math.floor((14 - m) / 12);
	const yy = y + 4800 - a;
	const mm = m + 12 * a - 3;
	// 1582-10-15 之前按儒略历
	if(y < 1582 || (y === 1582 && (m < 10 || (m === 10 && d < 15)))){
		return d + Math.floor((153 * mm + 2) / 5) + 365 * yy + Math.floor(yy / 4) - 32083;
	}
	return d + Math.floor((153 * mm + 2) / 5) + 365 * yy + Math.floor(yy / 4) - Math.floor(yy / 100) + Math.floor(yy / 400) - 32045;
}

export function mayanDate(jdn, correlation){
	const days = jdn - (MAYAN_CORRELATIONS.indexOf(Number(correlation)) >= 0 ? Number(correlation) : 584283);
	const units = [144000, 7200, 360, 20, 1];
	let rest = days;
	const longCount = units.map((u)=>{ const q = Math.floor(rest / u); rest -= q * u; return q; });
	const tzNumber = mod(days + 3, 13) + 1;
	const tzName = mod(days + 19, 20);
	const haab = mod(days + 348, 365);
	const trecenaStart = days - (tzNumber - 1);
	return {
		days,
		longCount,
		longCountText: longCount.join('.'),
		tzolkin: { number: tzNumber, sign: tzName, name: TZOLKIN_NAMES[tzName] },
		haab: { day: haab % 20, month: Math.floor(haab / 20), name: HAAB_MONTHS[Math.floor(haab / 20)] },
		lordOfNight: mod(days + 8, 9) + 1,
		trecena: { sign: mod(trecenaStart + 19, 20), name: TZOLKIN_NAMES[mod(trecenaStart + 19, 20)], day: tzNumber },
	};
}

// ─────────────────────────── 十三月亮历 ───────────────────────────
export const DREAMSPELL_SEALS = ['红龙', '白风', '蓝夜', '黄种子', '红蛇', '白世界桥', '蓝手', '黄星星', '红月', '白狗',
	'蓝猴', '黄人', '红天行者', '白巫师', '蓝鹰', '黄战士', '红地球', '白镜', '蓝风暴', '黄太阳'];
export const DREAMSPELL_TONES = ['磁性', '月亮', '电力', '自我存在', '超频', '韵律', '共振', '银河', '太阳', '行星', '光谱', '水晶', '宇宙'];
// 与 gregorianToJdn 同一历法:1582 年以前按儒略历(逢 4 即闰)
const isLeap = (y)=>(y < 1582 ? mod(y, 4) === 0 : (y % 4 === 0 && (y % 100 !== 0 || y % 400 === 0)));

function leapDaysBetween(lo, hi, excludeLo){
	// lo 到 hi 之间落着的 2 月 29 日个数(含 hi;excludeLo 时不含 lo 本身)
	let count = 0;
	for(let y = lo.y; y <= hi.y; y += 1){
		if(!isLeap(y)){ continue; }
		const j = gregorianToJdn(y, 2, 29);
		if((excludeLo ? j > lo.jdn : j >= lo.jdn) && j <= hi.jdn){ count += 1; }
	}
	return count;
}

export function dreamspell(y, m, d){
	const base = { y: 1987, jdn: gregorianToJdn(1987, 7, 26) };
	const t = { y, jdn: gregorianToJdn(y, m, d) };
	let n = t.jdn - base.jdn;
	// 往前数时当天若是 2 月 29 日不算进去,它才和 2 月 28 日同号(往后数时含当天,同理)
	if(n >= 0){ n -= leapDaysBetween(base, t, false); }else{ n += leapDaysBetween(t, base, true); }
	const kin = mod(33 + n, 260) + 1;
	const tone = mod(kin - 1, 13) + 1;
	const seal = mod(kin - 1, 20) + 1;
	const wave = kin - (tone - 1);
	// 十三月亮历日期:年起 7 月 26 日
	const startYear = (m > 7 || (m === 7 && d >= 26)) ? y : y - 1;
	const start = { y: startYear, jdn: gregorianToJdn(startYear, 7, 26) };
	let dayOfYear = t.jdn - start.jdn;
	const feb29 = isLeap(startYear + 1) && t.jdn >= gregorianToJdn(startYear + 1, 2, 29);
	const isFeb29 = m === 2 && d === 29;
	if(feb29 && !isFeb29){ dayOfYear -= 1; }
	let moonDate;
	if(isFeb29){ moonDate = { special: '闰日(不计数)' }; }
	else if(dayOfYear >= 364){ moonDate = { special: '无时间日' }; }
	else{ moonDate = { moon: Math.floor(dayOfYear / 28) + 1, day: dayOfYear % 28 + 1 }; }
	return {
		kin, tone, seal,
		toneName: DREAMSPELL_TONES[tone - 1], sealName: DREAMSPELL_SEALS[seal - 1],
		wavespell: { kin: wave, sealName: DREAMSPELL_SEALS[mod(wave - 1, 20)] },
		year: startYear, moonDate,
	};
}

// ─────────────────────────── 人类图 / 灵名 文字 ───────────────────────────
export const HD_CENTER_CN = { head: '头顶', ajna: '脑', throat: '喉', g: '自我(G)', heart: '意志(心)', sacral: '荐骨', solar: '情绪', spleen: '直觉(脾)', root: '根部' };
export const HD_TYPE_CN = { manifestor: '显示者', generator: '生产者', manifestingGenerator: '显示生产者', projector: '投射者', reflector: '反映者' };
export const HD_AUTHORITY_CN = { emotional: '情绪', sacral: '荐骨', splenic: '直觉(脾)', ego: '意志(心)', self: '自我投射(G)', mental: '无内在权威(环境 / 心智)', lunar: '月亮周期' };
export const HD_PROFILE_CN = { 1: '研究者', 2: '隐士', 3: '烈士', 4: '机会主义者', 5: '异端者', 6: '角色模范' };
export const HD_DEFINITION_CN = { 0: '无定义', 1: '一分人', 2: '二分人', 3: '三分人', 4: '四分人' };
export const HD_POINT_CN = { Sun: '太阳', Earth: '地球', 'North Node': '北交', 'South Node': '南交', Moon: '月亮', Mercury: '水星', Venus: '金星', Mars: '火星',
	Jupiter: '木星', Saturn: '土星', Uranus: '天王星', Neptune: '海王星', Pluto: '冥王星' };
export const SPIRIT_POINT_CN = { Sun: '太阳', Moon: '月亮', Asc: '上升', Fortune: '福点', Syzygy: '产前朔望之月' };

export function zhufangParamsFromFields(fields){
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
		hsys: v('hsys'),
		gender: normBinaryGender(v('gender')),
	};
}

export function localZhufangModel(params, settings){
	const p = params || {};
	const m = `${p.date || ''}`.match(/^(-?\d+)[/-](\d+)[/-](\d+)/);
	if(!m){ return null; }
	const y = Number(m[1]); const mo = Number(m[2]); const d = Number(m[3]);
	if(Number(p.ad) < 0){ return { y, mo, d, mayan: null, dreamspell: null }; }
	const s = settings || {};
	return { y, mo, d, mayan: mayanDate(gregorianToJdn(y, mo, d), s.mayanCorrelation), dreamspell: dreamspell(y, mo, d) };
}

const fmtLon = (lon)=>{
	if(!Number.isFinite(Number(lon))){ return '—'; }
	const v = ((Number(lon) % 360) + 360) % 360;
	const signs = ['白羊', '金牛', '双子', '巨蟹', '狮子', '处女', '天秤', '天蝎', '射手', '摩羯', '水瓶', '双鱼'];
	return `${signs[Math.floor(v / 30)]} ${(v % 30).toFixed(2)}°`;
};
const PLANET_CN = { Sun: '太阳', Moon: '月亮', Mercury: '水星', Venus: '金星', Mars: '火星', Jupiter: '木星', Saturn: '土星' };

export function zhufangSnapshotLines(local, remote, settings){
	const out = [];
	const s = settings || {};
	out.push('[玛雅历]');
	if(local && local.mayan){
		const mm = local.mayan;
		out.push(`长历 ${mm.longCountText}(关联常数 ${s.mayanCorrelation || 584283});卓尔金 ${mm.tzolkin.number} ${mm.tzolkin.name};哈布 ${mm.haab.day} ${mm.haab.name};九夜神 G${mm.lordOfNight};十三日组 ${mm.trecena.name} 第 ${mm.trecena.day} 日`);
	}else{ out.push('公元前日期不排玛雅历。'); }
	out.push('[十三月亮历]');
	if(local && local.dreamspell){
		const ds = local.dreamspell;
		out.push(`Kin ${ds.kin}:${ds.toneName}调性 ${ds.tone} · ${ds.sealName};波符 ${ds.wavespell.sealName};${ds.moonDate.special || `${ds.year} 年第 ${ds.moonDate.moon} 月第 ${ds.moonDate.day} 日`}`);
	}else{ out.push('公元前日期不排十三月亮历。'); }
	out.push('[人类图]');
	const hd = remote && remote.humanDesign;
	if(hd){
		out.push(`类型 ${HD_TYPE_CN[hd.type] || hd.type} · 内在权威 ${HD_AUTHORITY_CN[hd.authority] || hd.authority} · 人生角色 ${hd.profile.join('/')}(${hd.profile.map((x)=>HD_PROFILE_CN[x]).join(' / ')}) · ${HD_DEFINITION_CN[hd.definition] || ''}`);
		out.push(`轮回交叉 ${hd.cross[0]}/${hd.cross[1]} | ${hd.cross[2]}/${hd.cross[3]};交点 ${hd.trueNode ? '真交点' : '平交点'}`);
		out.push(`有定义中心:${hd.defined.map((c)=>HD_CENTER_CN[c] || c).join('、') || '无'}`);
		out.push(`通道:${hd.channels.map((c)=>c.gates.join('-')).join('、') || '无'}`);
		out.push(`个人(出生):${hd.personality.map((r)=>`${HD_POINT_CN[r.id] || r.id} ${r.gate}.${r.line}`).join(' · ')}`);
		out.push(`设计(太阳前移 88°):${hd.design.map((r)=>`${HD_POINT_CN[r.id] || r.id} ${r.gate}.${r.line}`).join(' · ')}`);
	}else{ out.push('人类图未算出。'); }
	out.push('[灵名字母]');
	const sn = remote && remote.spiritNames;
	if(sn){
		out.push(`五要点:${sn.ibnEzra.map((r)=>`${SPIRIT_POINT_CN[r.id] || r.id} ${r.letter ? `${r.letter.glyph} ${r.letter.name}(${r.letter.index})` : '—'}`).join(';')}`);
		out.push(`十一宫度数主星 ${PLANET_CN[sn.eleventh.almuten] || sn.eleventh.almuten}(${fmtLon(sn.eleventh.lon)})→ ${sn.eleventh.letter.glyph} ${sn.eleventh.letter.name}`);
		out.push(`象限 ${sn.quadrant}:${sn.quadrantRows.map((r)=>`${r.house} 宫 ${PLANET_CN[r.almuten] || r.almuten}(${r.score} 分)→ ${r.letter.glyph} ${r.letter.name}`).join(';')}`);
	}else{ out.push('灵名字母未算出。'); }
	return out;
}
