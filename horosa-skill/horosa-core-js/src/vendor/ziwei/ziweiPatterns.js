// 紫微格局自动识别(JS 移植自 Java ZiWeiPattern.detect,条件原语一一对应)。
// 用途:本地引擎(calcZiwei)产出的盘,格局须随本地盘重算(否则用 Java 默认盘的 patterns 会与切开关后的盘不符)。
// 输出与 Java 同形:[{name,category,duanyi,source_ref,broken,logic,conditions,breakers}]。
// 三方四正(命)={命,财帛(命-4),官禄(命+4),迁移(命+6)};四化取 getActiveSiHuaGan()[生年干](随流派)。
import GE_PATTERNS from './data/tables/ziweige.json' with { type: 'json' };
import { STAR_LIGHT } from './data/ziweiTables.js';
import { getActiveSiHuaGan } from '../bazi/ZWConst.js';

const HUA_IDX = { 禄: 0, 权: 1, 科: 2, 忌: 3 };
const STAR_FIELDS = ['starsMain', 'starsAssist', 'starsEvil', 'starsOthersGood', 'starsOthersBad', 'starsSmall'];

function buildCtx(chart){
	const life = chart.lifeHouseIndex;
	const yearGan = chart.yearGan;
	// star → houseIdx(去「副」前缀;同名多处取最后,对齐 Java map 覆盖语义)
	const starIdx = {};
	for(let i = 0; i < 12; i++){
		STAR_FIELDS.forEach((f)=>{
			(chart.houses[i][f] || []).forEach((s)=>{
				const nm = s.name && s.name.charAt(0) === '副' ? s.name.slice(1) : s.name;
				if(nm){ starIdx[nm] = i; }
			});
		});
	}
	const trine = new Set([life, (life - 4 + 12) % 12, (life + 4) % 12, (life + 6) % 12]);
	const idx = (star)=>(starIdx[star] == null ? -1 : starIdx[star]);
	const zhiOf = (houseIdx)=>{ const gz = chart.houses[houseIdx].ganzi; return gz ? gz.charAt(1) : null; };
	const sandwich = (center, a, b)=>{
		const left = (center + 11) % 12, right = (center + 1) % 12;
		const ia = idx(a), ib = idx(b);
		return (ia === left && ib === right) || (ia === right && ib === left);
	};
	const hua4 = (getActiveSiHuaGan()[yearGan]) || [];
	const huaHouse = (hua)=>{ const hi = HUA_IDX[hua]; if(hi == null || !hua4[hi]){ return -1; } return idx(hua4[hi]); };
	return { chart, life, trine, idx, zhiOf, sandwich, huaHouse };
}

function evalCond(cond, ctx){
	if(!cond){ return false; }
	const op = String(cond.op);
	const list = (k)=>(Array.isArray(cond[k]) ? cond[k].map(String) : []);
	switch(op){
		case 'and': return (cond.conditions || []).every((c)=>evalCond(c, ctx));
		case 'or': return (cond.conditions || []).some((c)=>evalCond(c, ctx));
		case 'inMing': return ctx.idx(String(cond.star)) === ctx.life;
		case 'inTrine': return ctx.trine.has(ctx.idx(String(cond.star)));
		case 'inTrineAny': {
			const need = cond.atLeast != null ? Number(cond.atLeast) : 1;
			let n = 0; list('stars').forEach((s)=>{ if(ctx.trine.has(ctx.idx(s))){ n++; } });
			return n >= need;
		}
		case 'same': {
			let first = -2;
			const stars = list('stars');
			for(let i = 0; i < stars.length; i++){
				const v = ctx.idx(stars[i]);
				if(v < 0){ return false; }
				if(first === -2){ first = v; }
				else if(v !== first){ return false; }
			}
			return first >= 0;
		}
		case 'sameAnyOf': {
			const base = ctx.idx(String(cond.star));
			if(base < 0){ return false; }
			return list('others').some((s)=>ctx.idx(s) === base);
		}
		case 'mingZhi': return list('branches').indexOf(ctx.zhiOf(ctx.life)) >= 0;
		case 'inZhi': {
			const i = ctx.idx(String(cond.star));
			return i >= 0 && list('branches').indexOf(ctx.zhiOf(i)) >= 0;
		}
		case 'sandwichMing': {
			const ss = list('stars');
			return ss.length === 2 && ctx.sandwich(ctx.life, ss[0], ss[1]);
		}
		case 'sandwichStarMix': {
			const t = ctx.idx(String(cond.target));
			if(t < 0){ return false; }
			const left = (t + 11) % 12, right = (t + 1) % 12;
			const si = ctx.idx(String(cond.star));
			const hi = ctx.huaHouse(String(cond.hua));
			return (si === left && hi === right) || (si === right && hi === left);
		}
		case 'bright': {
			const i = ctx.idx(String(cond.star));
			if(i < 0){ return false; }
			const lt = STAR_LIGHT[String(cond.star)] && STAR_LIGHT[String(cond.star)][ctx.zhiOf(i)];
			return lt != null && list('levels').indexOf(lt) >= 0;
		}
		case 'mingNoMainStar': return (ctx.chart.houses[ctx.life].starsMain || []).length === 0;
		case 'huaMing': return ctx.huaHouse(String(cond.hua)) === ctx.life;
		case 'huaTrineAll': return list('huas').every((h)=>ctx.trine.has(ctx.huaHouse(h)));
		case 'huaWithStar': {
			const i = ctx.idx(String(cond.star));
			return i >= 0 && i === ctx.huaHouse(String(cond.hua));
		}
		case 'breakBy': {
			const qian = (ctx.life + 6) % 12;
			return list('stars').some((s)=>{ const i = ctx.idx(s); return i === ctx.life || i === qian; });
		}
		case 'inOpp': {
			const opp = (ctx.life + 6) % 12;
			return list('stars').some((s)=>ctx.idx(s) === opp);
		}
		case 'sandwichHua': {
			const l = (ctx.life + 11) % 12, r = (ctx.life + 1) % 12;
			const hi = ctx.huaHouse(String(cond.hua));
			return hi === l || hi === r;
		}
		// WP-G 新增 op：noneInTrine(stars 全不在三方四正,负判「无辅拱」)、notInMing(某星不在命宫)。
		case 'noneInTrine': return !list('stars').some((s)=>ctx.trine.has(ctx.idx(s)));
		case 'notInMing': return ctx.idx(String(cond.star)) !== ctx.life;
		default: return false;
	}
}

// 对本地盘检测命中格局。返回与 Java detect() 同形数组。
export function detectPatterns(chart){
	const res = [];
	if(!chart || chart.lifeHouseIndex == null || chart.lifeHouseIndex < 0){ return res; }
	const ctx = buildCtx(chart);
	Object.keys(GE_PATTERNS).forEach((name)=>{
		const rule = GE_PATTERNS[name];
		const conds = rule.conditions || [];
		const logic = rule.logic || 'AND';
		const hit = String(logic).toUpperCase() === 'OR'
			? conds.some((c)=>evalCond(c, ctx))
			: conds.every((c)=>evalCond(c, ctx));
		if(!hit){ return; }
		let broken = false;
		if(Array.isArray(rule.breakers)){ broken = rule.breakers.some((b)=>evalCond(b, ctx)); }
		res.push({
			name, category: rule.category, duanyi: rule.duanyi, source_ref: rule.source_ref,
			broken, logic, conditions: rule.conditions, breakers: rule.breakers,
		});
	});
	return res;
}
