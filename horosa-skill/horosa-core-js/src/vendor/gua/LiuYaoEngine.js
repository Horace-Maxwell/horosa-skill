// 六爻纳甲断卦引擎(WP-B 装卦结构 / WP-C 旺衰 / WP-D 月破空墓)。纯函数、确定性。
// 只产「结构真值」(世应/卦序类型/卦身/飞伏/旺相休囚死/日辰生克冲合/月破/旬空/十二长生),
// 吉凶断语交 AI。分歧点(土长生水土/火土、月破当月/出月)以入参开关切换,不自裁。
import { littleEndian } from './guaHelper.js';
import { getGua64 } from './GuaConst.js';
import {
	ZHI_WUXING, WUXING_SHENG, WUXING_KE, LIUCHONG, LIUHE, HAI, PO, isXing, SANHE, SANHUI,
	PALACE_TYPES, CHANGSHENG_STAGES, CHANGSHENG_START, CHANGSHENG_START_ALT,
	shengKe,
} from './LiuYaoConst.js';

// ── 解析 yaoname:'子水子孙'/'辰土父母应' → {zhi,wuxing,liuqin,shiYing} ──
export function parseYaoName(name){
	if(!name || name.length < 4){ return { zhi: '', wuxing: '', liuqin: '', shiYing: '' }; }
	return {
		zhi: name.substr(0, 1),
		wuxing: name.substr(1, 1),
		liuqin: name.substr(2, 2),
		shiYing: name.length > 4 ? name.substr(4, 1) : '',
	};
}

// ── WP-B 本宫首卦(八纯卦):value = [...house.value, ...house.value] ──
export function pureGuaOf(gua){
	if(!gua || !gua.house){ return null; }
	const v = [...gua.house.value, ...gua.house.value];
	return getGua64(littleEndian(v));
}

// ── WP-B 卦序类型/世位/应位:本卦 value 对本宫首卦 XOR,变爻集匹配 PALACE_TYPES ──
export function palaceTypeOf(gua){
	if(!gua || !gua.house || !gua.value){ return null; }
	const base = [...gua.house.value, ...gua.house.value];
	const moving = [];
	for(let i = 0; i < 6; i++){
		if(gua.value[i] !== base[i]){ moving.push(i + 1); }
	}
	const key = moving.join(',');
	const hit = PALACE_TYPES.find((p) => p.moving.join(',') === key);
	if(!hit){ return null; }
	return { type: hit.type, shi: hit.shi, ying: hit.ying, palace: gua.house.name };
}

// ── WP-B 卦身(月卦身):阳世从子起、阴世从午起,数至世爻;返回卦身支+持身爻位(1-6)+是否上卦 ──
export function guaShenOf(gua){
	const pt = palaceTypeOf(gua);
	if(!pt || !gua.value){ return null; }
	const shi = pt.shi;
	const shiYaoYang = gua.value[shi - 1] === 1;
	const base = shiYaoYang ? ['子', '丑', '寅', '卯', '辰', '巳'] : ['午', '未', '申', '酉', '戌', '亥'];
	const body = base[shi - 1];
	const holders = [];
	for(let i = 0; i < 6; i++){
		const yn = (gua.yaoname && gua.yaoname[i]) || '';
		if(parseYaoName(yn).zhi === body){ holders.push(i + 1); }
	}
	return { body, holders, onChart: holders.length > 0 };
}

// ── WP-B 飞伏神:本宫首卦同位爻(地支/五行/六亲);某位本卦缺某六亲时该位伏神才「现」 ──
export function fushenForGua(gua){
	const pure = pureGuaOf(gua);
	if(!pure){ return null; }
	// 本卦各位六亲(用于判断哪些六亲缺、对应位伏神当现)
	const benLiuqin = new Set();
	for(let i = 0; i < 6; i++){
		const p = parseYaoName((gua.yaoname && gua.yaoname[i]) || '');
		if(p.liuqin){ benLiuqin.add(p.liuqin); }
	}
	const res = [];
	for(let i = 0; i < 6; i++){
		const fp = parseYaoName(pure.yaoname[i] || '');
		res.push({
			pos: i + 1,
			zhi: fp.zhi,
			wuxing: fp.wuxing,
			liuqin: fp.liuqin,
			// 伏神当现:其六亲在本卦六爻中缺失(传统「用神不上卦,looks伏神」口径)
			show: !benLiuqin.has(fp.liuqin),
		});
	}
	return res;
}

// ── WP-C 旺相休囚死(按月令):当令旺、令生相、生令休、克令囚、令克死 ──
export function wangShuaiByMonth(yaoWx, monthZhi){
	const monthWx = ZHI_WUXING[monthZhi];
	if(!yaoWx || !monthWx){ return ''; }
	if(yaoWx === monthWx){ return '旺'; }
	if(WUXING_SHENG[monthWx] === yaoWx){ return '相'; } // 令生者相
	if(WUXING_SHENG[yaoWx] === monthWx){ return '休'; } // 生令者休
	if(WUXING_KE[yaoWx] === monthWx){ return '囚'; }     // 克令者囚
	if(WUXING_KE[monthWx] === yaoWx){ return '死'; }     // 令克者死
	return '';
}

// ── WP-C 日辰对爻的作用:生/克/冲/合/比及方向 ──
export function dayRelationOf(yaoZhi, dayZhi){
	if(!ZHI_WUXING[yaoZhi] || !ZHI_WUXING[dayZhi]){ return null; }
	const yWx = ZHI_WUXING[yaoZhi], dWx = ZHI_WUXING[dayZhi];
	const r = {
		chong: LIUCHONG[dayZhi] === yaoZhi, he: LIUHE[dayZhi] === yaoZhi,
		xing: isXing(dayZhi, yaoZhi), hai: HAI[dayZhi] === yaoZhi, po: PO[dayZhi] === yaoZhi,
		sheng: false, ke: false, same: false, note: '',
	};
	const sk = shengKe(dWx, yWx); // 日 对 爻
	if(sk === '同'){ r.same = true; r.note = '日辰比和(帮扶)'; }
	else if(sk === '生'){ r.sheng = true; r.note = '日辰生爻'; }
	else if(sk === '克'){ r.ke = true; r.note = '日辰克爻'; }
	else if(sk === '泄'){ r.note = '爻生日辰(泄气)'; }
	else if(sk === '耗'){ r.note = '爻克日辰(耗气)'; }
	if(r.chong){ r.note = (r.note ? r.note + '·' : '') + '日辰冲爻(旺则暗动、衰则日破)'; }
	if(r.he){ r.note = (r.note ? r.note + '·' : '') + '日辰合爻'; }
	if(r.xing){ r.note = (r.note ? r.note + '·' : '') + '日辰刑爻'; }
	if(r.hai){ r.note = (r.note ? r.note + '·' : '') + '日辰害爻'; }
	if(r.po){ r.note = (r.note ? r.note + '·' : '') + '日辰破爻'; }
	return r;
}

// ── WP-D 月破:月支冲爻支(yuepoMode='inMonth' 当月有效 / 'always' 不论;出月填实由解读层) ──
export function isYuePo(yaoZhi, monthZhi){
	return !!yaoZhi && !!monthZhi && LIUCHONG[monthZhi] === yaoZhi;
}

// ── WP-D 旬空:kongPair 为旬空两支(由 getXunEmpty 得,如 '戌亥') ──
export function isXunKong(yaoZhi, kongPair){
	return !!yaoZhi && !!kongPair && kongPair.indexOf(yaoZhi) >= 0;
}

// ── WP-C/D 十二长生:某五行在某支的阶段(tuMode:'water'水土同宫/'fire'火土同宫/'off'关) ──
export function changshengOf(yaoWx, atZhi, tuMode){
	if(!yaoWx || !atZhi || tuMode === 'off'){ return ''; }
	const startMap = (tuMode === 'fire') ? CHANGSHENG_START_ALT : CHANGSHENG_START;
	const start = startMap[yaoWx];
	if(!start){ return ''; }
	const order = ['子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥'];
	const s = order.indexOf(start), z = order.indexOf(atZhi);
	if(s < 0 || z < 0){ return ''; }
	return CHANGSHENG_STAGES[((z - s) % 12 + 12) % 12];
}
// 入墓 = 长生十二宫之「墓」
export function isRuMu(yaoWx, atZhi, tuMode){
	return changshengOf(yaoWx, atZhi, tuMode) === '墓';
}

// ── 六冲卦/六合卦(§5.7):内外卦三对爻(初↔四/二↔五/三↔上)地支全冲=六冲卦、全合=六合卦 ──
export function guaChongHe(gua){
	if(!gua || !gua.yaoname){ return ''; }
	let chong = 0, he = 0;
	for(let i = 0; i < 3; i++){
		const a = parseYaoName(gua.yaoname[i] || '').zhi;
		const b = parseYaoName(gua.yaoname[i + 3] || '').zhi;
		if(a && LIUCHONG[a] === b){ chong++; }
		if(a && LIUHE[a] === b){ he++; }
	}
	if(chong === 3){ return '六冲卦'; }
	if(he === 3){ return '六合卦'; }
	return '';
}

// ── 三合局/三会方(§1.5):卦中三支齐现成局(有动则成局力强);返回 [{type,zhis,wuxing,positions,hasMoving}] ──
export function guaSanHeHui(gua, movingSet){
	if(!gua || !gua.yaoname){ return []; }
	const moving = movingSet || new Set();
	const posByZhi = {};
	for(let i = 0; i < 6; i++){
		const z = parseYaoName(gua.yaoname[i] || '').zhi;
		if(z){ (posByZhi[z] = posByZhi[z] || []).push(i + 1); }
	}
	const out = [];
	const scan = (table, type) => {
		Object.keys(table).forEach((key) => {
			const chars = key.split('');
			if(chars.every((z) => posByZhi[z])){
				const positions = chars.map((z) => posByZhi[z][0]);
				out.push({ type, zhis: key, wuxing: table[key], positions, hasMoving: positions.some((p) => moving.has(p)) });
			}
		});
	};
	scan(SANHE, '三合局');
	scan(SANHUI, '三会方');
	return out;
}

// ── WP-D 真空/假空(§5.6):旬空 + (休囚死/月破=无气) + 不动 + 不被日生扶 + 不临日月 → 真空(到底空);
// 否则(旺相/发动/逢生/临日月可填实) → 假空(出空即用)。非旬空返 ''。 ──
export function voidKindOf(y, ctx){
	if(!y || !y.xunKong){ return ''; }
	const c = ctx || {};
	const weak = (y.wangShuai === '休' || y.wangShuai === '囚' || y.wangShuai === '死');
	const shengFu = y.dayRel && (y.dayRel.sheng || y.dayRel.same); // 日辰生/比扶
	const linRiYue = (c.dayZhi && y.zhi === c.dayZhi) || (c.monthZhi && y.zhi === c.monthZhi); // 临日月可填实
	if((weak || y.yuePo) && !y.moving && !shengFu && !linRiYue){ return '真空'; }
	return '假空';
}

// ── 汇总:对一卦六爻产出结构断盘(供中右栏 + AI 快照单一真值源) ──
// ctx: { dayGan, dayZhi, monthZhi, kongPair, tuMode='water', yuepoMode='inMonth' }
export function analyzeGua(gua, ctx){
	if(!gua){ return null; }
	const c = ctx || {};
	const tuMode = c.tuMode || 'water';
	const pt = palaceTypeOf(gua);
	const shen = guaShenOf(gua);
	const fu = fushenForGua(gua);
	const movingSet = new Set(c.movingPositions || []);
	const yaos = [];
	for(let i = 0; i < 6; i++){
		const p = parseYaoName((gua.yaoname && gua.yaoname[i]) || '');
		const fuHere = fu && fu[i] && fu[i].show ? fu[i] : null;
		const y = {
			pos: i + 1,
			yin: gua.value[i] === 0,
			moving: movingSet.has(i + 1),
			zhi: p.zhi,
			wuxing: p.wuxing,
			liuqin: p.liuqin,
			shiYing: p.shiYing || (pt ? (pt.shi === i + 1 ? '世' : (pt.ying === i + 1 ? '应' : '')) : ''),
			wangShuai: wangShuaiByMonth(p.wuxing, c.monthZhi),
			dayRel: dayRelationOf(p.zhi, c.dayZhi),
			yuePo: c.monthZhi ? isYuePo(p.zhi, c.monthZhi) : false,
			xunKong: c.kongPair ? isXunKong(p.zhi, c.kongPair) : false,
			changsheng: c.dayZhi ? changshengOf(p.wuxing, c.dayZhi, tuMode) : '',
			ruMu: c.dayZhi ? isRuMu(p.wuxing, c.dayZhi, tuMode) : false,
			isShen: shen ? shen.holders.indexOf(i + 1) >= 0 : false,
			fushen: fuHere ? { zhi: fuHere.zhi, wuxing: fuHere.wuxing, liuqin: fuHere.liuqin } : null,
		};
		y.voidKind = voidKindOf(y, c); // 真空/假空(依赖 xunKong/wangShuai/yuePo/moving/dayRel)
		yaos.push(y);
	}
	return { palaceType: pt, guaShen: shen, yaos };
}
