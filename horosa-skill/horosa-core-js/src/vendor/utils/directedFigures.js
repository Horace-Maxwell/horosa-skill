// 推运图族四技法(演进推运 Néroman / 推运图 Bezza / 周日小限 Jay / 双黄道 Michon)的单一来源:
// 技法键、后端接口、缺省设置、选项、名称,以及「结果 → AI 快照正文」。页面、AI 挂载重算、AI 导出共用这里的出口。
// 计算全在后端 astrostudy/directed_figures.py(/astroextra/<接口>),本文件只做口径与排版,不做天文计算。
import * as AstroConst from '../../constants/AstroConst.js';
import * as AstroText from '../../constants/AstroText.js';

export const DIRECTED_FIGURE_KEYS = ['neroman', 'bezzafigure', 'jayprofection', 'michon'];

export const DIRECTED_FIGURES = {
	neroman: { label: '演进推运', author: 'Néroman', endpoint: '/astroextra/neroman' },
	bezzafigure: { label: '推运图', author: 'Bezza', endpoint: '/astroextra/bezzafigure' },
	jayprofection: { label: '周日小限', author: 'Jay', endpoint: '/astroextra/jayprofection' },
	michon: { label: '双黄道', author: 'Michon', endpoint: '/astroextra/michon' },
};

// 各技法缺省设置(= 后端缺省;页面保存键见 directionPageSettings 的 nerK / nerT0 / nerKeepDec / bezzaOrb / jayFrom / michonOrb / michonSwap / michonEqual)
export const NEROMAN_DEFAULTS = { k: 273.18, t0: 0.75, keepDec: false, orb: 1 };
export const BEZZA_DEFAULTS = { orb: 1 };
export const JAY_DEFAULTS = { from: -1 };
export const MICHON_DEFAULTS = { orb: 1, swap: false, equal: false };

export const NEROMAN_EQUATOR_OPTIONS = [
	{ value: false, label: '按黄经度数' },
	{ value: true, label: '保留本命赤纬' },
];

export const BEZZA_KIND_LABELS = { mun: '世俗相位', zod: '黄道相位', par: '子午映点', apar: '地平映点' };
export const BEZZA_MUNDANE_ASPECTS = { 0: '合', 4: '六合', 6: '刑', 8: '拱', 12: '冲' };
export const ZODIAC_ASPECT_LABELS = { 0: '合', 60: '六合', 90: '刑', 120: '拱', 180: '冲' };

// 双黄道五族(按谐波):代码与后端一致
export const MICHON_FAMILY_LABELS = {
	en: '12 谐(30° 倍数)',
	re: '18 谐(20° 倍数)',
	ta: '20 谐(18° 倍数)',
	mi: '14 谐(360°⁄14 倍数)',
	bl: '24 谐奇族(15° 奇数倍)',
	no: '无',
};

export const FIGURE_POINT_LABELS = { Tyche: '福点(世俗)', Daimon: '精神点(世俗)' };

export function pointName(id){
	if(FIGURE_POINT_LABELS[id]){ return FIGURE_POINT_LABELS[id]; }
	return (AstroText.AstroTxtMsg && AstroText.AstroTxtMsg[id]) || id || '-';
}

export function signOfLon(lon){
	const n = Number(lon);
	if(!Number.isFinite(n)){ return null; }
	return AstroConst.LIST_SIGNS[Math.floor((((n % 360) + 360) % 360) / 30) % 12];
}

export function fmtLon(lon){
	const n = Number(lon);
	if(!Number.isFinite(n)){ return '-'; }
	const x = ((n % 360) + 360) % 360;
	const sign = signOfLon(x);
	return `${(AstroText.AstroTxtMsg && AstroText.AstroTxtMsg[sign]) || sign} ${(x % 30).toFixed(2)}°`;
}

export function fmtN(v, d = 2){
	const n = Number(v);
	return Number.isFinite(n) ? n.toFixed(d) : '-';
}

function num(v, def){
	const n = Number(v);
	return Number.isFinite(n) ? n : def;
}

function bool(v){
	return v === true || v === 1 || v === '1' || v === 'true';
}

// 页面 / 挂载设置 → 请求体专属字段(缺省值照发:后端缺省与此同值,发与不发结果相同)
export function directedFigureRequestFields(key, opts){
	const o = opts && typeof opts === 'object' ? opts : {};
	if(key === 'neroman'){
		return { nerK: num(o.k, NEROMAN_DEFAULTS.k), nerT0: num(o.t0, NEROMAN_DEFAULTS.t0), nerKeepDec: bool(o.keepDec) ? 1 : 0, orb: num(o.orb, NEROMAN_DEFAULTS.orb) };
	}
	if(key === 'bezzafigure'){
		return { orb: num(o.orb, BEZZA_DEFAULTS.orb) };
	}
	if(key === 'jayprofection'){
		return { jayFrom: Math.round(num(o.from, JAY_DEFAULTS.from)) };
	}
	if(key === 'michon'){
		return { orb: num(o.orb, MICHON_DEFAULTS.orb), mzSwap: bool(o.swap) ? 1 : 0, mzEqual: bool(o.equal) ? 1 : 0 };
	}
	return {};
}

function table(lines, head, rows){
	lines.push(`| ${head.join(' | ')} |`);
	lines.push(`| ${head.map(()=>'---').join(' | ')} |`);
	rows.forEach((r)=>lines.push(`| ${r.join(' | ')} |`));
}

function headLines(r){
	return [`目标时刻：${r.target || '-'}`, `年龄：${fmtN(r.age, 4)} 岁(回归年)`];
}

// 结果 → 快照正文(段头登记在 aiExport preset;第一段名 = 技法名)
export function buildDirectedFigureText(key, r){
	if(!r || typeof r !== 'object' || r.err){ return ''; }
	const lines = [];
	if(key === 'neroman'){
		if(!Array.isArray(r.evolved) || !r.evolved.length){ return ''; }
		lines.push('[演进推运]');
		lines.push(...headLines(r));
		lines.push(`演进弧：${fmtN(r.arc, 4)}°(弧 = ${fmtN(r.k, 2)} × ln(1 + 年龄 ⁄ ${fmtN(r.t0, 2)}),各点赤经逆行减弧)`);
		lines.push(`换到赤道：${r.keepDeclination ? '保留本命赤纬' : '按黄经度数'}`);
		lines.push('');
		lines.push('[演进位置]');
		table(lines, ['点', '本命', '演进'], r.evolved.map((p)=>[pointName(p.id), fmtLon(p.natalLon), fmtLon(p.lon)]));
		lines.push('');
		lines.push('[演进对本命相位]');
		const cs = (r.contacts || []).slice(0, 60);
		if(cs.length){ table(lines, ['演进点', '相位', '本命点', '误差'], cs.map((c)=>[pointName(c.evolved), ZODIAC_ASPECT_LABELS[c.asp] || `${c.asp}°`, pointName(c.natal), fmtN(c.orb, 2)])); } else { lines.push(`容许度 ${fmtN(r.orb, 1)}° 内无相位`); }
		lines.push('');
		lines.push('[天顶与上升过本命点]');
		const near = (r.events || []).filter((e)=>Math.abs(e.age - r.age) <= 10).slice(0, 60);
		table(lines, ['年龄', '日期', '演进点', '相位', '本命点'], near.map((e)=>[fmtN(e.age, 2), e.date || '-', pointName(e.mover), ZODIAC_ASPECT_LABELS[e.asp] || `${e.asp}°`, pointName(e.target)]));
	}else if(key === 'bezzafigure'){
		if(!Array.isArray(r.points) || !r.points.length){ return ''; }
		lines.push('[推运图]');
		lines.push(...headLines(r));
		lines.push(`推运弧：${fmtN(r.arc, 4)}°(真太阳弧,赤经;各点随自身半弧周日运动推进)`);
		lines.push('');
		lines.push('[推运图位置]');
		table(lines, ['点', '本命黄经', '本命时位', '推运时位', '推运黄经'], r.points.map((p)=>[pointName(p.id), fmtLon(p.lon), fmtN(p.hp0, 3), fmtN(p.hp1, 3), fmtLon(p.dp)]));
		lines.push('');
		lines.push('[推运图接触]');
		const cs = r.contacts || [];
		if(cs.length){
			table(lines, ['类别', '动点', '本命点', '相位', '弧', '与当前差', '年龄', '日期'], cs.map((c)=>[
				BEZZA_KIND_LABELS[c.kind] || c.kind, pointName(c.pid), pointName(c.prm),
				c.kind === 'mun' ? (BEZZA_MUNDANE_ASPECTS[c.asp] || `${c.asp} 时`) : (c.kind === 'zod' ? (ZODIAC_ASPECT_LABELS[c.asp] || `${c.asp}°`) : '-'),
				fmtN(c.arc, 3), fmtN(c.d, 3), fmtN(c.age, 2), c.date || '-',
			]));
		}else{ lines.push(`当前弧 ±${fmtN(r.orb, 1)}° 内无接触`); }
	}else if(key === 'jayprofection'){
		if(!Array.isArray(r.rows) || !r.rows.length){ return ''; }
		const cols = ['Asc', 'MC', ...['Sun', 'Moon', 'Mercury', 'Venus', 'Mars', 'Jupiter', 'Saturn'], 'Tyche'];
		lines.push('[周日小限]');
		lines.push(...headLines(r));
		lines.push('赤经中天每年 +30°(一年一宫,十二年一周);诸星保持本命 Placidus 世俗位置随天球转动。');
		lines.push('');
		lines.push('[当前小限]');
		const c = r.current || {};
		lines.push(`小限上升落本命第 ${c.house || '-'} 宫;${cols.map((k)=>`${pointName(k)} ${fmtLon(c[k])}`).join(';')}`);
		lines.push('');
		lines.push('[逐年小限]');
		table(lines, ['年龄', '日期', '落宫', ...cols.map(pointName)], r.rows.map((row)=>[fmtN(row.age, 0), row.date || '-', `${row.house || '-'}`, ...cols.map((k)=>fmtLon(row[k]))]));
	}else if(key === 'michon'){
		if(!Array.isArray(r.superpositions) || !r.superpositions.length){ return ''; }
		const sign = (i)=>{ const s = AstroConst.LIST_SIGNS[i]; return (AstroText.AstroTxtMsg && AstroText.AstroTxtMsg[s]) || s; };
		lines.push('[双黄道]');
		lines.push(`恒星黄道岁差：${fmtN(r.ayanamsa, 4)}°(J2000.0 时 26°37′18″,随标准岁差)`);
		lines.push(`守护：${r.swapMercuryVenus ? '水金互换' : '现代守护'};宫位：${r.equalHouses ? '等宫(上升居第一宫正中)' : '本盘宫制'};容许度 ${fmtN(r.orb, 1)}°`);
		lines.push('');
		lines.push('[叠合]');
		table(lines, ['序', '回归座', '恒星座', '守护', '距角', '族', '偏差', '宫'], r.superpositions.map((s)=>[
			`${s.n}`, sign(s.tropicalSign), sign(s.siderealSign), `${pointName(s.p1)}—${pointName(s.p2)}`, fmtN(s.sep, 2),
			MICHON_FAMILY_LABELS[s.family] || s.family, s.dev === null || s.dev === undefined ? '-' : fmtN(s.dev, 2), `${s.house0}/${s.house1}`,
		]));
		lines.push('');
		lines.push('[互动]');
		const hit = (r.interactions || []).filter((i)=>i.tropicalFamily !== 'no' || i.siderealFamily !== 'no');
		table(lines, ['叠合对', '回归守护', '回归族', '恒星守护', '恒星族'], hit.map((i)=>[
			`${i.a}·${i.b}`, `${pointName(i.tropical[0])}—${pointName(i.tropical[1])} ${fmtN(i.tropicalSep, 1)}°`, MICHON_FAMILY_LABELS[i.tropicalFamily] || i.tropicalFamily,
			`${pointName(i.sidereal[0])}—${pointName(i.sidereal[1])} ${fmtN(i.siderealSep, 1)}°`, MICHON_FAMILY_LABELS[i.siderealFamily] || i.siderealFamily,
		]));
		lines.push(`(66 组互动中两侧皆无族的 ${66 - hit.length} 组从略)`);
	}else{
		return '';
	}
	return lines.join('\n');
}
