// 法奇门（荀爽体系）分析引擎 —— 纯函数叠加层。
// 仅消费 DunJiaCalc 产出的 pan 对象的派生字段，不改排盘引擎、不发请求、不触 DOM，
// 便于单测与 AI 快照复用。下列「洛书/后天八卦」常量为不变事实，镜像 DunJiaCalc.js 的私有常量。

import {
	POS_TO_BRANCHES,
	LUOSHU_NUM,
	ZHI_CHONG,
	JI_XING_JIE,
	MU_KU,
	MEN_PO_JIE,
	ZHI_LIUHE,
	ZHI_ZODIAC,
	PALACE_META,
	ganObjText,
	zhiObjText,
} from './DunJiaFaDoc.js';

// 宫号 → 后天八卦（宫名）
export const POS_GUA = { 1: '巽', 2: '离', 3: '坤', 4: '震', 5: '中', 6: '兑', 7: '艮', 8: '坎', 9: '乾' };
// 宫号 → 现实方位
export const POS_DIRECTION = { 1: '东南', 2: '正南', 3: '西南', 4: '正东', 5: '中宫', 6: '正西', 7: '东北', 8: '正北', 9: '西北' };
// 对宫（仅外八宫；中5无对宫）
export const OPPOSITE_PALACE = { 1: 6, 2: 8, 3: 9, 4: 7, 6: 1, 7: 4, 8: 2, 9: 3 };
const OUTER_PALACES = [1, 2, 3, 4, 6, 7, 8, 9];

// 危害程度（递减）：击刑 > 入墓 > 庚 > 白虎 > 门迫 > 空亡；天干 > 一切，先解击刑天干。
export const DANGER_SEVERITY = { 击刑: 6, 入墓: 5, 庚: 4, 白虎: 3, 门迫: 2, 空亡: 1 };
const DANGER_NOTE = {
	击刑: '争执损耗（最烈，先解）',
	入墓: '沉溺迷失',
	庚: '凶祸阻隔',
	白虎: '快速危险',
	门迫: '压力胁迫',
	空亡: '虚假不实',
};

// 天干五合：甲己 乙庚 丙辛 丁壬 戊癸
export const WU_HE_PAIRS = [['甲', '己'], ['乙', '庚'], ['丙', '辛'], ['丁', '壬'], ['戊', '癸']];
export const WU_HE_MAP = { 甲: '己', 己: '甲', 乙: '庚', 庚: '乙', 丙: '辛', 辛: '丙', 丁: '壬', 壬: '丁', 戊: '癸', 癸: '戊' };

function dirOf(p){
	return POS_DIRECTION[p] || '';
}
function nameOf(p){
	return POS_GUA[p] || (p ? `${p}` : '');
}

// 把 pan.cells 规整成查表索引；天干/神/门/星索引优先取「非中宫」占位，避免中宫寄宫歧义。
export function readCells(pan){
	const cells = pan && Array.isArray(pan.cells) ? pan.cells : [];
	const byPalace = {};
	const byTianGan = {};
	const byDiGan = {};
	const byGod = {};
	const byDoor = {};
	const byStar = {};
	const assign = (map, key, val)=>{
		if(key && map[key] === undefined){
			map[key] = val;
		}
	};
	// 第一遍只收外八宫（优先级高），第二遍补中宫，使索引指向外宫占位。
	cells.forEach((c)=>{
		byPalace[c.palaceNum] = c;
	});
	[false, true].forEach((centerPass)=>{
		cells.forEach((c)=>{
			const isCenter = c.palaceNum === 5 || !!c.isCenter;
			if(isCenter !== centerPass){
				return;
			}
			assign(byTianGan, c.tianGan, c.palaceNum);
			assign(byDiGan, c.diGan, c.palaceNum);
			assign(byGod, normalizeGod(c.god), c.palaceNum);
			assign(byDoor, c.door, c.palaceNum);
			assign(byStar, c.tianXing, c.palaceNum);
		});
	});
	return { cells, byPalace, byTianGan, byDiGan, byGod, byDoor, byStar };
}

// 八神归一：引擎在阳遁回「勾/雀」但前端 DunJiaCalc:1209 已 replace 勾→虎、雀→玄；
// 此处再兜底一次，保证白虎检测（'虎'/'白虎'）在阴阳遁通用。
function normalizeGod(god){
	const g = `${god || ''}`;
	if(g === '勾'){ return '虎'; }
	if(g === '雀'){ return '玄'; }
	return g;
}
function isBaiHu(god){
	const g = normalizeGod(god);
	return g === '虎' || g === '白虎';
}

// 完整六害 + 危害排序。复用 pan 已算好的宫号数组；庚/白虎为本引擎新增检测。
export function computeDangers(pan){
	if(!pan){
		return [];
	}
	const idx = readCells(pan);
	const out = [];
	const push = (type, palaceNum, symbol)=>{
		const p = Number(palaceNum) || 0;
		if(!p){
			return;
		}
		out.push({
			type,
			oneChar: DANGER_ONECHAR[type] || type.charAt(0),
			palaceNum: p,
			palaceName: nameOf(p),
			direction: dirOf(p),
			symbol: symbol || '',
			severity: DANGER_SEVERITY[type] || 0,
			note: DANGER_NOTE[type] || '',
		});
	};
	// 击刑（六仪击刑）—— 取该宫天盘干
	(pan.jiXingPalaces || []).forEach((p)=>push('击刑', p, (idx.byPalace[p] || {}).tianGan));
	// 入墓（奇仪入墓）
	(pan.ruMuPalaces || []).forEach((p)=>push('入墓', p, (idx.byPalace[p] || {}).tianGan));
	// 庚：天盘干为庚（凶祸阻隔；只看天盘干）
	idx.cells.forEach((c)=>{
		if(c.tianGan === '庚'){
			push('庚', c.palaceNum, '庚');
		}
	});
	// 白虎：八神为虎/白虎
	idx.cells.forEach((c)=>{
		if(isBaiHu(c.god)){
			push('白虎', c.palaceNum, '白虎');
		}
	});
	// 门迫
	((pan.menPo && pan.menPo.palaces) || []).forEach((p)=>push('门迫', p, (idx.byPalace[p] || {}).door));
	// 空亡（宫空）
	(pan.kongWangPalaces || []).forEach((p)=>push('空亡', p, '空亡'));
	// 危害递减；同级按宫序，稳定可复现。
	out.sort((a, b)=>(b.severity - a.severity) || (a.palaceNum - b.palaceNum));
	return out;
}

// 天干五合：①各对天盘定位（甲为隐干，取值符宫）；②天地盘五合宫（天盘干+地盘干成五合＝合住）。
export function computeWuHe(pan){
	if(!pan){
		return { pairs: [], tianDiHe: [] };
	}
	const idx = readCells(pan);
	const zhiFuPalace = Number(pan.zhiFuPalace) || 0;
	const locate = (gan)=>(gan === '甲' ? zhiFuPalace : (idx.byTianGan[gan] || 0));
	const pairs = WU_HE_PAIRS.map(([a, b])=>{
		const pa = locate(a);
		const pb = locate(b);
		return {
			ganA: a,
			ganB: b,
			palaceA: pa,
			palaceB: pb,
			nameA: nameOf(pa),
			nameB: nameOf(pb),
			directionA: dirOf(pa),
			directionB: dirOf(pb),
			hiddenJia: a === '甲',
			sameP: !!(pa && pb && pa === pb),
		};
	});
	const tianDiHe = [];
	idx.cells.forEach((c)=>{
		if(c.tianGan && WU_HE_MAP[c.tianGan] && WU_HE_MAP[c.tianGan] === c.diGan){
			tianDiHe.push({
				palaceNum: c.palaceNum,
				palaceName: nameOf(c.palaceNum),
				direction: dirOf(c.palaceNum),
				tianGan: c.tianGan,
				diGan: c.diGan,
			});
		}
	});
	return { pairs, tianDiHe };
}

// 伏吟 / 反吟局（荀爽定义，移星不变量）：
// 伏吟 = 每宫天盘干 ≡ 地盘干；反吟 = 每宫天盘干 ≡ 对宫地盘干。
export function computePanType(pan){
	if(!pan){
		return { type: null, text: '' };
	}
	const tian = pan.tianPan || {};
	const di = pan.diPan || {};
	const allMatch = (diPicker)=>OUTER_PALACES.every((p)=>{
		const t = tian[p] || '';
		const d = diPicker(p);
		return t && d && t === d;
	});
	if(allMatch((p)=>di[p] || '')){
		return { type: '伏吟', text: '天地伏吟局：天地盘干重叠，凝滞不动、进退两难、应事较慢；可借马宫带动能量。' };
	}
	if(allMatch((p)=>di[OPPOSITE_PALACE[p]] || '')){
		return { type: '反吟', text: '反吟局：天地盘对冲颠倒，事多反复折腾、重来不定。' };
	}
	return { type: null, text: '' };
}

// —— 化解方案生成（消费六害，套 DunJiaFaDoc 解神/形象表）——
function hazardsAt(palaceNum, pan, idx){
	const out = [];
	if((pan.jiXingPalaces || []).indexOf(palaceNum) >= 0){ out.push('击刑'); }
	if((pan.ruMuPalaces || []).indexOf(palaceNum) >= 0){ out.push('入墓'); }
	const c = idx.byPalace[palaceNum] || {};
	if(c.tianGan === '庚'){ out.push('庚'); }
	if(isBaiHu(c.god)){ out.push('白虎'); }
	if(((pan.menPo && pan.menPo.palaces) || []).indexOf(palaceNum) >= 0){ out.push('门迫'); }
	if((pan.kongWangPalaces || []).indexOf(palaceNum) >= 0){ out.push('空亡'); }
	return out;
}

const DANGER_ONECHAR = { 击刑: '刑', 入墓: '墓', 庚: '庚', 白虎: '虎', 门迫: '迫', 空亡: '空' };

// 化解方案（按「宫」合并：一宫可多害，化解须合起来做）。
// 庚击刑→乙巳、庚单独→只乙、庚入墓→对宫冲，皆由「逐宫合并 + 去重」自然得出。
export function buildJieHua(pan){
	if(!pan){
		return [];
	}
	const idx = readCells(pan);
	const dangers = computeDangers(pan);
	const byPalace = {};
	dangers.forEach((d)=>{
		(byPalace[d.palaceNum] = byPalace[d.palaceNum] || []).push(d);
	});
	const out = Object.keys(byPalace).map((pnStr)=>{
		const pn = Number(pnStr);
		const ds = byPalace[pn].slice().sort((a, b)=>b.severity - a.severity);
		const cell = idx.byPalace[pn] || {};
		const symbol = cell.tianGan || '';
		const door = cell.door || '';
		const meta = PALACE_META[nameOf(pn)] || {};
		const oppNum = OPPOSITE_PALACE[pn];
		const benZhi = (POS_TO_BRANCHES[pn] || []).join('·');
		const duiZhi = (POS_TO_BRANCHES[oppNum] || []).join('·');
		const types = ds.map((d)=>d.type);
		const has = (t)=>types.indexOf(t) >= 0;
		const mie = [];
		if(has('击刑') || has('入墓') || has('庚')){
			const moveRule = has('入墓') ? '只可移、不可扔送（入墓乃机遇/三奇，不可丢）' : '可移、可扔、可送';
			mie.push(`找出天盘干「${symbol}」的现实物（${ganObjText(symbol)}），移出本方位（${moveRule}）。`);
		}
		if(has('门迫')){
			mie.push(`拆走与「${door}门」对应的现实物。`);
		}
		if(has('白虎')){
			mie.push('移走凶硬、尖锐、金属之物。');
		}
		const place = [];
		const seen = {};
		const pushP = (key, where, text)=>{
			if(text && !seen[key]){
				seen[key] = 1;
				place.push({ where, text });
			}
		};
		if(has('庚')){
			pushP('gao乙', '高处放·天干', `「乙」（${ganObjText('乙')}）`);
		}
		if(has('白虎')){
			pushP('gao乙', '高处放·天干', `「乙」（${ganObjText('乙')}）`);
		}
		if(has('击刑')){
			const j = JI_XING_JIE[symbol] || {};
			pushP('gao' + j.wuHe, '高处放·天干', j.wuHe ? `「${j.wuHe}」（${ganObjText(j.wuHe)}）` : '');
			pushP('di' + j.liuHe, '低处放·地支', j.liuHe ? `「${j.liuHe}」（${zhiObjText(j.liuHe)}）` : '');
		}
		if(has('入墓')){
			const ku = MU_KU[symbol] || '';
			const chong = ZHI_CHONG[ku] || '';
			pushP('chong' + chong, `本宫（或对宫 ${nameOf(oppNum)}·${dirOf(oppNum)}）`, chong ? `放「${chong}」（${zhiObjText(chong)}）` : '');
		}
		if(has('门迫')){
			const js = MEN_PO_JIE[door] || '';
			pushP('di' + js, '低处放·地支', js ? `「${js}」（${zhiObjText(js)}）` : '');
		}
		if(has('空亡')){
			pushP('fill', '填实·本宫（或对宫）', `补「${symbol}」（${ganObjText(symbol)}）的现实物，缺啥补啥`);
		}
		const notes = [];
		if(has('击刑')){ notes.push('击刑危害最烈，须第一个解。'); }
		if(has('庚')){ notes.push('乾·西北「乙」入墓，故西北只灭象、不放乙；从事高风险/武力行业者庚为用武之地，勿灭。'); }
		if(has('入墓')){ notes.push('入墓只可移、不可扔送；若用对宫，该宫须无四害。'); }
		if(has('空亡')){ notes.push('空亡若本宫另有六害，先灭象、再于对宫放空亡之形象。'); }
		const ZHI_SUB = { 辰: '水盆代龙（辰）', 巳: '红烛代蛇（巳）', 寅: '猫科代虎（寅）' };
		const subUsed = [];
		['辰', '巳', '寅'].forEach((z)=>{ if(place.some((pp)=>pp.text.indexOf('「' + z + '」') >= 0)){ subUsed.push(ZHI_SUB[z]); } });
		if(subUsed.length){ notes.push('龙/蛇/虎之象普通人把握不住，可用替代物：' + subUsed.join('、') + '。'); }
		return {
			palaceNum: pn,
			palaceName: nameOf(pn),
			direction: dirOf(pn),
			deg: meta.deg || '',
			ben: meta.ben || '',
			dui: meta.dui || '',
			benZhi,
			duiZhi,
			tianGan: symbol,
			dangers: ds.map((d)=>({ type: d.type, oneChar: d.oneChar })),
			worstSeverity: ds.length ? ds[0].severity : 0,
			mie,
			placements: place,
			notes,
		};
	});
	out.sort((a, b)=>(b.worstSeverity - a.worstSeverity) || (a.palaceNum - b.palaceNum));
	return out;
}

// 布阵保护单行。
function protectRowAt(label, gan, palace, pan, idx){
	const p = Number(palace) || 0;
	const hz = p ? hazardsAt(p, pan, idx) : [];
	return {
		label,
		gan: gan || '',
		palaceNum: p,
		palaceName: p ? nameOf(p) : '—',
		direction: p ? dirOf(p) : '',
		hazards: hz,
		ok: p > 0 && hz.length === 0,
		advice: !p ? '局中未现，留意补位。' : (hz.length ? `落「${hz.join('/')}」之宫，宜移出该宫或就地化解。` : '宫位平稳，护其不受克即可。'),
	};
}

// 求测事项 → 八门化气大阵「意象」天干（识破人心无意象）。
const TOPIC_YIXIANG = { wealth: { gan: '戊', label: '财富' }, career: { gan: '甲', label: '事业' }, romance: { gan: '癸', label: '婚恋' } };

// 八门化气大阵·布阵保护清单：日干 / 时干 / 生年干 / 意象干 / 符使。
export function computeProtect(pan, ctx){
	if(!pan){
		return [];
	}
	const idx = readCells(pan);
	const gz = pan.ganzhi || {};
	const topic = ctx && ctx.topic;
	const out = [];
	const locate = (gan)=>(gan === '甲' ? (Number(pan.zhiFuPalace) || 0) : (idx.byTianGan[gan] || 0));
	const addGan = (label, gan)=>{
		if(!gan){
			return;
		}
		out.push(protectRowAt(label, gan, locate(gan), pan, idx));
	};
	addGan('日干·内心/实质', (gz.day || '').charAt(0));
	addGan('时干·外在/表象', (gz.time || '').charAt(0));
	// 生年干·局中各人：从左栏「相关人员」选入者的生年干（捕获快照，逐人一行）；未选则不显示该类。
	// pan.faRelatedPeople 为显式数组(含空[])时以它为准(储存/重开/已保存记录)；缺省(undefined)时兜底读全局当前选择
	// (覆盖 AI 挂载里「重算 pan 不带 stamp」的路径，保证四同步无遗漏)。
	const relatedPeople = Array.isArray(pan.faRelatedPeople)
		? pan.faRelatedPeople
		: ((typeof window !== 'undefined' && Array.isArray(window.__horosa_qimen_related_people)) ? window.__horosa_qimen_related_people : []);
	relatedPeople.forEach((person)=>{
		if(person && person.yearGan){
			addGan(`生年干·${person.name || '相关人员'}`, person.yearGan);
		}
	});
	const yx = TOPIC_YIXIANG[topic];
	if(yx){
		addGan(`意象·${yx.label}`, yx.gan);
	}
	const zfCell = idx.byPalace[pan.zhiFuPalace] || {};
	const zsCell = idx.byPalace[pan.zhiShiPalace] || {};
	out.push(protectRowAt('值符（话语权）', zfCell.tianGan || '', pan.zhiFuPalace, pan, idx));
	out.push(protectRowAt('值使（用武之地）', zsCell.tianGan || '', pan.zhiShiPalace, pan, idx));
	return out;
}

// —— 用神 / 分论（荀爽分论篇：识破人心 / 财富七要 / 事业七要 / 恋爱姻缘 / 解孤辰寡宿）——
const GAN_YINYANG = { 甲: '阳', 丙: '阳', 戊: '阳', 庚: '阳', 壬: '阳', 乙: '阴', 丁: '阴', 己: '阴', 辛: '阴', 癸: '阴' };
const GAN_WUXING = { 甲: '木', 乙: '木', 丙: '火', 丁: '火', 戊: '土', 己: '土', 庚: '金', 辛: '金', 壬: '水', 癸: '水' };
const GAN_KE = { 甲: ['戊', '己'], 乙: ['戊', '己'], 丙: ['庚', '辛'], 丁: ['庚', '辛'], 戊: ['壬', '癸'], 己: ['壬', '癸'], 庚: ['甲', '乙'], 辛: ['甲', '乙'], 壬: ['丙', '丁'], 癸: ['丙', '丁'] };
const ZHI_WUXING = { 寅: '木', 卯: '木', 巳: '火', 午: '火', 辰: '土', 戌: '土', 丑: '土', 未: '土', 申: '金', 酉: '金', 子: '水', 亥: '水' };
const WX_SHENG = { 木: '火', 火: '土', 土: '金', 金: '水', 水: '木' };
const WX_KE = { 木: '土', 土: '水', 水: '火', 火: '金', 金: '木' };
const MUYU_ZHI = { 甲: '子', 乙: '巳', 丙: '卯', 丁: '申', 戊: '卯', 己: '申', 庚: '午', 辛: '亥', 壬: '酉', 癸: '寅' };
const BRANCH_POS = { 辰: 1, 巳: 1, 午: 2, 未: 3, 申: 3, 卯: 4, 酉: 6, 寅: 7, 丑: 7, 子: 8, 亥: 9, 戌: 9 };

function palaceInfo(pan, idx, palace){
	const p = Number(palace) || 0;
	const hz = p ? hazardsAt(p, pan, idx) : [];
	return { palaceNum: p, palaceName: p ? nameOf(p) : '—', direction: p ? dirOf(p) : '', hazards: hz, ok: p > 0 && hz.length === 0 };
}
function locateStem(pan, idx, gan){
	const p = gan === '甲' ? (Number(pan.zhiFuPalace) || 0) : (idx.byTianGan[gan] || 0);
	return { symbol: gan || '', ...palaceInfo(pan, idx, p) };
}
function locateGod(pan, idx, god){
	return { symbol: god || '', ...palaceInfo(pan, idx, idx.byGod[god] || 0) };
}
function locateDoor(pan, idx, door){
	return { symbol: door || '', ...palaceInfo(pan, idx, idx.byDoor[door] || 0) };
}

// 用神定位（荀爽：日干为求测者/内心、时干为平台/外在；干合/符使/六亲）。
export function computeYongShen(pan, ctx){
	if(!pan){ return null; }
	const idx = readCells(pan);
	const gz = pan.ganzhi || {};
	const dayGan = (gz.day || '').charAt(0);
	const timeGan = (gz.time || '').charAt(0);
	const monthGan = (gz.month || '').charAt(0);
	const yearGan = (gz.year || '').charAt(0);
	const heGan = WU_HE_MAP[dayGan] || '';
	const out = {
		dayGan: locateStem(pan, idx, dayGan),
		timeGan: locateStem(pan, idx, timeGan),
		ganHe: heGan ? { heOf: dayGan, ...locateStem(pan, idx, heGan) } : null,
		zhiFu: palaceInfo(pan, idx, pan.zhiFuPalace),
		zhiShi: palaceInfo(pan, idx, pan.zhiShiPalace),
		liuQin: [
			{ rel: '年干·父母长辈', ...locateStem(pan, idx, yearGan) },
			{ rel: '月干·兄弟同辈', ...locateStem(pan, idx, monthGan) },
			{ rel: '日干·自己', ...locateStem(pan, idx, dayGan) },
			{ rel: '时干·子女晚辈', ...locateStem(pan, idx, timeGan) },
		],
	};
	out.yongShenText = `用神＝日干「${dayGan}」（${GAN_YINYANG[dayGan] || ''}），落 ${out.dayGan.palaceName}${out.dayGan.palaceNum ? out.dayGan.palaceNum + '宫' : ''}；时干为平台（事之表象 / 人之外在）。`;
	return out;
}

// 财富七要。
export function computeWealth(pan){
	if(!pan){ return null; }
	const idx = readCells(pan);
	const gz = pan.ganzhi || {};
	const dayGan = (gz.day || '').charAt(0);
	const yearGan = (gz.year || '').charAt(0);
	const timeGan = (gz.time || '').charAt(0);
	const monthZhi = (gz.month || '').charAt(1);
	const yueWx = ZHI_WUXING[monthZhi] || '';
	const yongWx = GAN_WUXING[dayGan] || '';
	let yueRel = '';
	if(yueWx && yongWx){
		if(WX_SHENG[yueWx] === yongWx){ yueRel = '月令生用神：扩张＋量大'; }
		else if(yueWx === yongWx){ yueRel = '月令同用神：稳健＋量大'; }
		else if(WX_KE[yongWx] === yueWx){ yueRel = '用神克月令：努力＋量小'; }
		else if(WX_SHENG[yongWx] === yueWx){ yueRel = '用神生月令：损耗＋量小'; }
		else if(WX_KE[yueWx] === yongWx){ yueRel = '月令克用神：大亏＋量小'; }
	}
	const ganCai = []
		.concat((GAN_KE[dayGan] || []).map((g)=>({ src: '日干财', ...locateStem(pan, idx, g) })))
		.concat((GAN_KE[yearGan] || []).map((g)=>({ src: '生年财', ...locateStem(pan, idx, g) })));
	return {
		items: [
			{ name: '戊·本钱', note: '存款/工资/不动产/本金', ...locateStem(pan, idx, '戊') },
			{ name: '生门·利润', note: '利息/利润/回报/市场', ...locateDoor(pan, idx, '生') },
			{ name: '六合·合作', note: '合伙/融资/上下游/大钱', ...locateGod(pan, idx, '合') },
			{ name: '时干·机会', note: '客户/市场/平台/员工', ...locateStem(pan, idx, timeGan) },
		],
		month: { zhi: monthZhi, wuxing: yueWx, relation: yueRel },
		ganCai,
		industryHint: '行业取象：经商＝生门、合伙＝六合、演艺＝景门/天英/丙、武职＝庚/白虎/天冲、技术＝杜门、西医＝天心、内科＝天内、中医＝乙。',
	};
}

// 事业七要。
export function computeCareer(pan){
	if(!pan){ return null; }
	const idx = readCells(pan);
	const gz = pan.ganzhi || {};
	const gengP = idx.byTianGan['庚'] || 0;
	const huP = idx.byGod['虎'] || 0;
	const same = gengP && huP && gengP === huP;
	return {
		items: [
			{ name: '开门·单位', note: '工作环境/团体', ...locateDoor(pan, idx, '开') },
			{ name: '景门·业绩', note: '成果/形象/被看见', ...locateDoor(pan, idx, '景') },
			{ name: '玄武·小人', note: '暗中算计/陷阱', ...locateGod(pan, idx, '玄') },
			{ name: '庚虎·压力', note: same ? '庚＋白虎同宫，强敌压力' : '庚与白虎（压力/敌人）', ...palaceInfo(pan, idx, same ? gengP : (gengP || huP)) },
		],
		fuShi: [
			{ rel: '值符·一把手', ...palaceInfo(pan, idx, pan.zhiFuPalace) },
			{ rel: '值使·二把手', ...palaceInfo(pan, idx, pan.zhiShiPalace) },
		],
		zhuGan: [
			{ rel: '年干·大老板', ...locateStem(pan, idx, (gz.year || '').charAt(0)) },
			{ rel: '月干·同事', ...locateStem(pan, idx, (gz.month || '').charAt(0)) },
			{ rel: '时干·下属', ...locateStem(pan, idx, (gz.time || '').charAt(0)) },
		],
		industryHint: '行业取象：经商＝生门、合伙＝六合、演艺＝景门/天英/丙、武职＝庚/白虎/天冲、技术码农＝杜门、西医＝天心、内科＝天内、中医＝乙、文教＝天辅、口才法律＝天柱/惊门、丧葬养老＝死门、公职＝休/值符。',
	};
}

// 恋爱姻缘（正缘 / 桃花 / 情感不顺）。
export function computeRomance(pan){
	if(!pan){ return null; }
	const idx = readCells(pan);
	const gz = pan.ganzhi || {};
	const dayGan = (gz.day || '').charAt(0);
	const heGan = WU_HE_MAP[dayGan] || '';
	const pt = computePanType(pan);
	const muYu = MUYU_ZHI[dayGan] || '';
	const muYuP = muYu ? (BRANCH_POS[muYu] || 0) : 0;
	const trouble = [];
	if(pt.type === '伏吟'){ trouble.push('伏吟局：孤独执着、舔狗纯爱，难逢变通。'); }
	if(pt.type === '反吟'){ trouble.push('反吟局：反复折腾、朝三暮四，难长久。'); }
	const dayP = (dayGan === '甲') ? (Number(pan.zhiFuPalace) || 0) : (idx.byTianGan[dayGan] || 0);
	const heP = heGan ? ((heGan === '甲') ? (Number(pan.zhiFuPalace) || 0) : (idx.byTianGan[heGan] || 0)) : 0;
	const heP6 = idx.byGod['合'] || 0;
	const kp = pan.kongWangPalaces || [];
	if(dayP && kp.indexOf(dayP) >= 0){ trouble.push('日干空亡：自身不现实、错失机会。'); }
	if(heP && kp.indexOf(heP) >= 0){ trouble.push('干合空亡：意中人一直不出现。'); }
	if(heP6 && kp.indexOf(heP6) >= 0){ trouble.push('六合空亡：互有意却无交往机会。'); }
	const gen = hazardsAt(7, pan, idx);
	const kun = hazardsAt(3, pan, idx);
	if(gen.indexOf('击刑') >= 0 || gen.indexOf('门迫') >= 0 || kun.indexOf('击刑') >= 0 || kun.indexOf('门迫') >= 0){
		trouble.push('艮坤刑迫：家庭/情感多变故、伤害大。');
	}
	return {
		zhengYuan: [
			{ name: '干合·正缘（配偶/理想型）', symbol: heGan, ...palaceInfo(pan, idx, heP) },
			{ name: '六合·人缘（月老）', symbol: '合', ...palaceInfo(pan, idx, heP6) },
		],
		taoHua: {
			sanQi: ['乙', '丙', '丁'].map((g)=>({ gan: g, ...locateStem(pan, idx, g) })),
			muYu: { zhi: muYu, palaceNum: muYuP, palaceName: muYuP ? nameOf(muYuP) : '—', direction: muYuP ? dirOf(muYuP) : '' },
		},
		zhanTaoHua: '斩桃花（守正缘）：保护干合·六合；把「三奇乙丙丁 / 沐浴位 / 太阴 / 玄武 / 壬癸」之象移入入墓宫或空亡宫镇压，断出轨桃花。',
		trouble,
	};
}

// 解孤辰寡宿（读神煞 + 六合解法）。
export function computeGuGua(pan){
	if(!pan){ return []; }
	const items = (pan.shenSha && pan.shenSha.allItems) || [];
	const out = [];
	['孤辰', '寡宿'].forEach((name)=>{
		const hit = items.find((x)=>x.name === name);
		if(hit && hit.value){
			const z = `${hit.value}`.charAt(0);
			const he = ZHI_LIUHE[z] || '';
			const p = BRANCH_POS[z] || 0;
			out.push({ name, zhi: hit.value, jie: he ? `于 ${p ? nameOf(p) + '·' + dirOf(p) : ''} 用「${he}（${ZHI_ZODIAC[he] || ''}）」六合住` : '' });
		}
	});
	return out;
}

// 总入口。P1 dangers/wuHe/panType；P2 jieHua/protect；P3 yongShen/wealth/career/romance/guGua。
export function buildFaQimenAnalysis(pan, ctx){
	if(!pan){
		return null;
	}
	return {
		dangers: computeDangers(pan),
		wuHe: computeWuHe(pan),
		panType: computePanType(pan),
		jieHua: buildJieHua(pan),
		protect: computeProtect(pan, ctx),
		yongShen: computeYongShen(pan, ctx),
		wealth: computeWealth(pan),
		career: computeCareer(pan),
		romance: computeRomance(pan),
		guGua: computeGuGua(pan),
		ctx: ctx || null,
	};
}
