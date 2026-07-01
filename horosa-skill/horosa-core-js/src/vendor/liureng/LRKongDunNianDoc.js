// 大六壬 §7 收尾断法层(纯函数·解读层·零回归——仅右栏「概览/占断」消费,不入排盘):
//   E2 旬空落点(六处全标 + 陷空,§7.1/§22)·E3 三传遁干特殊(§7.2)·E4 年命上神断(§7.3)。
// 断语取公版古籍纲要重述,不录第三方专有文本;不写软件/书名。

import * as LRConst from './LRConst.js';

const z1 = (z) => `${z || ''}`.trim().substring(0, 1);
const SHENG = { '木': '火', '火': '土', '土': '金', '金': '水', '水': '木' };
const KE = { '木': '土', '土': '水', '水': '火', '火': '金', '金': '木' };
const wx = (gz) => LRConst.GanZiWuXing[z1(gz)] || '';

// 六亲(以日干为我):同=兄弟 / 我生=子孙 / 生我=父母 / 我克=妻财 / 克我=官鬼。
export function liuQinOf(meElem, otherElem){
	if(!meElem || !otherElem){ return ''; }
	if(meElem === otherElem){ return '兄弟'; }
	if(SHENG[meElem] === otherElem){ return '子孙'; }
	if(SHENG[otherElem] === meElem){ return '父母'; }
	if(KE[meElem] === otherElem){ return '妻财'; }
	if(KE[otherElem] === meElem){ return '官鬼'; }
	return '';
}

// E2 旬空落点(六处:干上神/支上神/初中末传/年命上神)逐位断 + 陷空(地盘空位上的天盘上神)。
// ctx 需:xunKongBranches、ke1Up(干上神)、ke3Up(支上神)、sanChuanBranches、branchUpMap、runYearBranch、(benMingBranch 可选)。
const KONG_POS_NOTE = {
	'干上神': '事虚不实、求而难得',
	'支上神': '对方／宅根基虚',
	'初传': '斩首——事起即空、起手落空',
	'中传': '折腰——将成而止、中途生变',
	'末传': '勿用——终无结果',
	'行年上神': '一年无成',
	'本命上神': '一生无成',
};
export function analyzeKongLocations(ctx){
	if(!ctx){ return { hits: [], xianKong: [], allSanChuanKong: false }; }
	const kong = (ctx.xunKongBranches || []).map(z1).filter(Boolean);
	if(!kong.length){ return { hits: [], xianKong: [], allSanChuanKong: false }; }
	const sc = (ctx.sanChuanBranches || []).map(z1);
	const runYear = z1(ctx.runYearBranch);
	const benMing = z1(ctx.benMingBranch);
	const up = ctx.branchUpMap || {};
	const positions = [
		{ pos: '干上神', branch: z1(ctx.ke1Up) },
		{ pos: '支上神', branch: z1(ctx.ke3Up) },
		{ pos: '初传', branch: sc[0] || '' },
		{ pos: '中传', branch: sc[1] || '' },
		{ pos: '末传', branch: sc[2] || '' },
		{ pos: '行年上神', branch: runYear ? z1(up[runYear]) : '' },
		{ pos: '本命上神', branch: benMing ? z1(up[benMing]) : '' },
	];
	const hits = positions
		.filter((p) => p.branch && kong.indexOf(p.branch) >= 0)
		.map((p) => ({ pos: p.pos, branch: p.branch, note: KONG_POS_NOTE[p.pos] || '空亡、虚不成' }));
	// 陷空:地盘旬空二支之上的天盘上神(落于空位之神)。
	const xianKong = kong
		.map((kb) => ({ seat: kb, god: z1(up[kb]) }))
		.filter((x) => x.god)
		.map((x) => ({ seat: x.seat, god: x.god }));
	const scKong = sc.filter((z) => z && kong.indexOf(z) >= 0);
	const allSanChuanKong = sc.length === 3 && scKong.length === 3;
	return { hits, xianKong, allSanChuanKong, kong };
}

// E3 三传遁干特殊(遁鬼/遁甲/遁癸/遁丁;旬空二支无遁干)。
// ctx 需:sanChuanBranches、xunGanMap、dayGan、xunKongBranches。
const DUN_FLAG = {
	'遁鬼': '暗鬼——藏于支下之官鬼,防暗中之险、隐忧',
	'遁甲': '旬头——遁出旬首甲,主端绪、领袖、栋梁之象',
	'遁癸': '闭口——遁出旬尾癸,主闭塞、缄默、收束',
	'遁丁': '丁马——遁出丁,主动、信息、奔走',
};
export function analyzeDunGan(ctx){
	if(!ctx){ return []; }
	const sc = (ctx.sanChuanBranches || []).map(z1).filter(Boolean);
	const map = ctx.xunGanMap || {};
	const kong = (ctx.xunKongBranches || []).map(z1);
	const meWX = wx(ctx.dayGan);
	const out = [];
	const POS = ['初传', '中传', '末传'];
	sc.forEach((zhi, i) => {
		if(kong.indexOf(zhi) >= 0){
			out.push({ pos: POS[i] || '', branch: zhi, gan: '', liuqin: '', flags: [], note: '旬空之支无遁干（空不遁）' });
			return;
		}
		const gan = z1(map[zhi]);
		if(!gan){ return; }
		const liuqin = liuQinOf(meWX, wx(gan));
		const flags = [];
		if(liuqin === '官鬼'){ flags.push('遁鬼'); }
		if(gan === '甲'){ flags.push('遁甲'); }
		if(gan === '癸'){ flags.push('遁癸'); }
		if(gan === '丁'){ flags.push('遁丁'); }
		if(flags.length){
			out.push({ pos: POS[i] || '', branch: zhi, gan, liuqin, flags, note: flags.map((f) => DUN_FLAG[f]).join('；') });
		}
	});
	return out;
}

// E4 年命上神断(行年/本命上神空亡;年命入课传重参)。
// ctx 需:runYearBranch(行年)、(benMingBranch 可选·本命)、branchUpMap、xunKongBranches、sanChuanBranches、courseBranches。
export function analyzeNianMing(ctx){
	if(!ctx){ return []; }
	const up = ctx.branchUpMap || {};
	const kong = (ctx.xunKongBranches || []).map(z1);
	const inChuan = (ctx.sanChuanBranches || []).map(z1);
	const inCourse = (ctx.courseBranches || []).map(z1);
	const out = [];
	const mk = (label, branch, emptyNote) => {
		const b = z1(branch);
		if(!b){ return; }
		const god = z1(up[b]);
		const entered = inChuan.indexOf(b) >= 0 || inCourse.indexOf(b) >= 0;
		const isKong = god && kong.indexOf(god) >= 0;
		const parts = [];
		parts.push(entered ? `${b}已入课传——以身应之、重参` : `${b}不入课传——专看其上神`);
		if(god){ parts.push(`上神${god}${isKong ? '（旬空）' : ''}`); }
		if(isKong){ parts.push(emptyNote); }
		out.push({ label, branch: b, god, entered, isKong, note: parts.join('，') });
	};
	mk('行年', ctx.runYearBranch, '行年上神空亡——一年无成');
	mk('本命', ctx.benMingBranch, '命上神空亡——一生无成');
	return out;
}
