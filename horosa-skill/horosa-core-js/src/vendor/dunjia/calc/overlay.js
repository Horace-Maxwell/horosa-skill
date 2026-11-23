// 奇门 · 盘面附加层(纯显示 / 推演,不改排盘结果):寄干与天禽落宫、翻宫链、转宫。
// 宫号一律按盘面格子编号(1 巽 · 2 离 · 3 坤 · 4 震 · 5 中 · 6 兑 · 7 艮 · 8 坎 · 9 乾,同 tables.PALACE_NAME)。
//
// 寄干:转盘中五宫不动,它的干「寄」在别宫显示 —— 地盘寄在寄宫(随中宫寄宫档),天盘随「从寄宫出发的那颗星」走
//   (缺省寄坤,即随天芮 / 天内走;天禽就是跟这颗星一起走的那颗)。反查口径:地盘寄宫 = 地盘干等于寄宫原地盘干的宫,
//   天盘寄宫 = 天盘干等于寄宫原地盘干的宫 —— 移星(整盘换局)之后照样成立。飞盘 / 天盘取飞的混合盘中宫自有星干,不寄。
// 翻宫(取象推前因后果、区分同类对象;生克成败仍以原宫为准):
//   上翻 = 往过去:用神宫天盘干 → 地盘同干之宫为上一步,再取该宫天盘干续翻;
//   下翻 = 往将来:用神宫地盘干 → 天盘同干之宫为下一步,再取该宫地盘干续翻;各最多三步。寄干参与匹配(寄宫的第二个干)。
//   用神宫天地盘同干(伏吟)时翻不出去 —— 翻宫无效,改看转宫。
// 转宫(辅助取信息,应期生克仍取原宫):空亡宫信息转到对冲宫(逢孤看虚);星门全伏吟(大伏吟)转到该卦的先天八卦位
//   (先天坎在后天兑位:坎→兑、离→震、乾→离、坤→坎、震→艮、巽→坤、艮→乾、兑→巽)。
import { PALACE_NAME, GUA_POS_MAP, OUTER_RING_CLOCKWISE } from './tables.js';

export const TUIYAN_VIEW_OPTIONS = [
	{ value: 'off', label: '常规（默认）' },
	{ value: 'fan', label: '翻宫（上翻过去·下翻将来）' },
	{ value: 'zhuan', label: '转宫（空亡转对宫·大伏吟转先天位）' },
];
// 洛书宫数(盘面格子编号 → 坎一 坤二 震三 巽四 中五 乾六 兑七 艮八 离九):下拉按洛书序排,标签带上数字才看得出次序
const LUOSHU_CN = { 8: '一', 3: '二', 4: '三', 1: '四', 5: '五', 9: '六', 6: '七', 7: '八', 2: '九' };
export const TUIYAN_GONG_OPTIONS = [
	{ value: 'shigan', label: '时干落宫（默认）' },
	{ value: 'zhifu', label: '值符落宫' },
	{ value: 'zhishi', label: '值使落宫' },
	...[8, 3, 4, 1, 9, 6, 7, 2].map((n)=>({ value: `${n}`, label: `${PALACE_NAME[n]}${LUOSHU_CN[n]}宫` })),
];

const OPPOSITE = { 1: 9, 9: 1, 2: 8, 8: 2, 3: 7, 7: 3, 4: 6, 6: 4 };
const XIANTIAN_TO = { 坎: '兑', 离: '震', 乾: '离', 坤: '坎', 震: '艮', 巽: '坤', 艮: '乾', 兑: '巽' };
const HOME_DOOR = { 坎: '休', 艮: '生', 震: '伤', 巽: '杜', 离: '景', 坤: '死', 兑: '惊', 乾: '开' };
const HOME_STAR = { 坎: '蓬', 艮: '任', 震: '冲', 巽: '辅', 离: '英', 坤: '芮禽内', 兑: '柱', 乾: '心' };
const first = (v)=>`${v || ''}`.charAt(0);

// 寄干:{ gan, diNum, tianNum } —— 不适用(飞盘 / 中宫无干 / 反查不到)返回 null。
export function resolveJiGan({ isFeipan, diPanBase, diPan, tianPan, jiGongGua }){
	if(isFeipan){ return null; }
	const gan = first(diPanBase && diPanBase[5]);
	const jiNum = GUA_POS_MAP[jiGongGua || '坤'];
	const homeGan = first(diPanBase && diPanBase[jiNum]);
	if(!gan || !homeGan){ return null; }
	const find = (map)=>OUTER_RING_CLOCKWISE.find((n)=>first(map && map[n]) === homeGan) || 0;
	const diNum = find(diPan);
	const tianNum = find(tianPan);
	if(!diNum && !tianNum){ return null; }
	return { gan, diNum, tianNum };
}

// 用神宫:'shigan' = 天盘时干所在宫(甲时取旬首遁仪;落中宫按天盘寄宫),'zhifu' / 'zhishi' = 值符 / 值使落宫,'1'..'9' = 指定宫。
// 值符 / 值使落中五宫(转盘):星门神实际排在寄宫,用神宫取寄宫(与时干那一支同口径);飞盘中宫自有星门,照实取中宫。
// 飞盘 / 天盘取飞的混合盘时干就在中五宫:照实回 5(翻宫不取,见 tuiYanRows)。
export function resolveYongShenGong(spec, { tianPan, shiGan, shiDun, ji, zhiFuPalace, zhiShiPalace }){
	const viaJi = (p)=>(p === 5 && ji && ji.diNum ? ji.diNum : (p || 0));
	if(spec === 'zhifu'){ return viaJi(zhiFuPalace); }
	if(spec === 'zhishi'){ return viaJi(zhiShiPalace); }
	const n = Number(spec);
	if(Number.isInteger(n) && n >= 1 && n <= 9 && n !== 5){ return n; }
	let target = first(shiGan);
	if(target === '甲'){ target = first(shiDun); }
	if(!target){ return 0; }
	const hit = OUTER_RING_CLOCKWISE.find((p)=>first(tianPan && tianPan[p]) === target);
	if(hit){ return hit; }
	if(ji && ji.gan === target && ji.tianNum){ return ji.tianNum; }
	if(!ji && first(tianPan && tianPan[5]) === target){ return 5; }
	return 0;
}

// 某宫天 / 地盘的干集(主干 + 寄干),供翻宫匹配
const stemsAt = (map, ji, side, n)=>{
	const out = [first(map && map[n])].filter(Boolean);
	if(ji && ji.gan && ji[side] === n){ out.push(ji.gan); }
	return out;
};

// 翻宫链:{ start, fuyin, up: [{ num, gan }], down: [{ num, gan }] }
export function qimenFanGong({ tianPan, diPan, ji, start, maxSteps = 3 }){
	const res = { start, fuyin: false, up: [], down: [] };
	if(!start || start === 5){ return res; }   // 中五宫不在翻宫的环上
	const tianAt = (n)=>stemsAt(tianPan, ji, 'tianNum', n);
	const diAt = (n)=>stemsAt(diPan, ji, 'diNum', n);
	res.fuyin = first(tianPan && tianPan[start]) !== '' && first(tianPan && tianPan[start]) === first(diPan && diPan[start]);
	const walk = (fromSide, toSide)=>{
		const steps = [];
		const seen = new Set([start]);
		let cur = start;
		for(let i = 0; i < maxSteps; i++){
			const gan = fromSide(cur)[0];
			if(!gan){ break; }
			const next = OUTER_RING_CLOCKWISE.find((p)=>toSide(p).indexOf(gan) >= 0);
			if(!next || seen.has(next)){ break; }
			steps.push({ num: next, gan });
			seen.add(next);
			cur = next;
		}
		return steps;
	};
	if(!res.fuyin){
		res.up = walk(tianAt, diAt);
		res.down = walk(diAt, tianAt);
	}
	return res;
}

// 转宫:{ start, startKong, kong: [{ from, to }], daFuyin, xianTian: [{ from, to }], startXianTian }
export function qimenZhuanGong({ star, men, kongPalaces, start }){
	const kong = (kongPalaces || []).filter((n)=>OPPOSITE[n]).map((n)=>({ from: n, to: OPPOSITE[n] }));
	const allHome = (map, home)=>OUTER_RING_CLOCKWISE.every((n)=>{
		const h = home[PALACE_NAME[n]];
		const v = `${(map && map[n]) || ''}`;
		return !!v && !!h && h.indexOf(v.charAt(0)) >= 0;
	});
	const daFuyin = allHome(star, HOME_STAR) && allHome(men, HOME_DOOR);
	const xianTian = daFuyin ? OUTER_RING_CLOCKWISE.map((n)=>({ from: n, to: GUA_POS_MAP[XIANTIAN_TO[PALACE_NAME[n]]] })) : [];
	return {
		start,
		startKong: !!(start && kong.some((k)=>k.from === start)),
		kong,
		daFuyin,
		xianTian,
		startXianTian: daFuyin && start ? GUA_POS_MAP[XIANTIAN_TO[PALACE_NAME[start]]] || 0 : 0,
	};
}

const gongName = (n)=>`${PALACE_NAME[n] || n}宫`;

// 推演(翻宫 / 转宫)结构化行:{ title, rows: [[标签, 内容]], note } —— 奇门页 / 三式概览卡片与 AI 快照共用这一份
export function tuiYanRows(t){
	if(!t || (t.view !== 'fan' && t.view !== 'zhuan')){ return null; }
	const gl = `${t.gongLabel || ''}`.replace(/[（(]默认[)）]$/, '');   // 「时干落宫（默认）」进括号里不再套括号
	const rows = [['用神宫', t.start ? `${gongName(t.start)}（${gl}）` : `未找到（${gl}）`]];
	if(t.view === 'fan'){
		const f = t.fan || {};
		if(!t.start){ return { title: '推演 · 翻宫', rows, note: '' }; }
		if(t.start === 5){ return { title: '推演 · 翻宫', rows: rows.concat([['翻宫', '用神宫在中五宫，翻宫只在外八宫之间取，此局不取']]), note: '' }; }
		if(f.fuyin){ return { title: '推演 · 翻宫', rows: rows.concat([['翻宫', '用神宫天地盘同干（伏吟），翻宫无效，宜改看转宫']]), note: '' }; }
		// 一步内用不换行空格连住(卡片窄时只在箭头处折行,不把「上3 兑宫（己）」拆成两行);快照文字里换回普通空格
		const chain = (arr, tag)=>(arr && arr.length ? arr.map((st, i)=>`${tag}${i + 1}\u00a0${gongName(st.num)}（${st.gan}）`).join(' → ') : '无');
		rows.push(['上翻（往过去）', chain(f.up, '上')]);
		rows.push(['下翻（往将来）', chain(f.down, '下')]);
		return { title: '推演 · 翻宫', rows, note: '天盘为现在、地盘为过去；翻宫只取象推前因后果、区分同类，生克成败仍以原宫为准。' };
	}
	const z = t.zhuan || {};
	const startKong = z.startKong ? z.kong.find((k)=>k.from === t.start) : null;
	rows.push(['空亡转宫', startKong ? `用神宫空亡，信息转看对冲${gongName(startKong.to)}` : '用神宫不空亡']);
	if(z.kong && z.kong.length){ rows.push(['全盘空亡', z.kong.map((k)=>`${gongName(k.from)}→${gongName(k.to)}`).join('、')]); }
	rows.push(['大伏吟', z.daFuyin ? `星门全伏吟，用神宫转看先天位${gongName(z.startXianTian)}` : '非大伏吟']);
	return { title: '推演 · 转宫', rows, note: '空亡转对冲（逢孤看虚）、大伏吟转先天八卦位，只作辅助取信息；应期与生克仍取原宫。' };
}

// 推演快照文字
export function tuiYanLines(t){
	const r = tuiYanRows(t);
	if(!r){ return []; }
	return [`${r.title}：${r.rows.map(([k, v])=>`${k} ${v}`).join('；').replace(/\u00a0/g, ' ')}`].concat(r.note ? [`推演说明：${r.note}`] : []);
}

// 寄干 / 天禽结构化行与快照文字(pan.jiGan 开关开才有)
export function jiGanRows(j){
	if(!j || !j.gan){ return []; }
	const rows = [];
	if(j.show){ rows.push(['寄干', `中五宫${j.gan}：地盘寄${j.diNum ? gongName(j.diNum) : '—'}，天盘随星寄${j.tianNum ? gongName(j.tianNum) : '—'}`]); }
	if(j.tianQin && j.tianNum){ rows.push(['天禽', `随寄宫之星落${gongName(j.tianNum)}`]); }
	return rows;
}
export function jiGanLines(j){
	return jiGanRows(j).map(([k, v])=>`${k}：${v}`);
}
