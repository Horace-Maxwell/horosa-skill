// divination/engine/perfection.js
// 完成与破坏（判断「能否成事」核心）。Sahl §1.4 三完成法为主骨架 + Sibly 4 完成 / 7 破坏
// + 完成度三分（Sahl §1.8 / 补充 B.1）+ 难易/主动方（B.2）。
import { PLANETS } from '../data/planets.js';
import { aspectBetween, applyingAspects, separatingAspects, antiscionBetween } from './aspectsEngine.js';
import { receives, mutualReceptionBetween } from './reception.js';

const SPEED_ORDER = ['moon', 'mercury', 'venus', 'sun', 'mars', 'jupiter', 'saturn', 'uranus', 'neptune', 'pluto'];
function speedIdx(k){ const i = SPEED_ORDER.indexOf(k); return i < 0 ? 99 : i; }
function lighter(a, b){ return speedIdx(a) < speedIdx(b); }   // a 比 b 轻/快
function cn(k){ return (PLANETS[k] || {}).cn || k; }
const EASY = [0, 60, 120];

function hasReception(facts, a, b){
	return receives(facts, a, b) || receives(facts, b, a) || mutualReceptionBetween(facts, a, b);
}

// 完成度三分（3 大征象：上升星/月亮/事件守护星，免受 凶/逆/燃/陷 的数量）
export function completionThirds(facts, sigKeys){
	const safe = [];
	const unsafe = [];
	sigKeys.filter(Boolean).forEach((k) => {
		const p = facts.planets[k];
		if(!p) return;
		const ok = !p.retro && p.combustion !== 'combust' && p.dignityScore > -4;
		(ok ? safe : unsafe).push(k);
	});
	const n = safe.length;
	const total = safe.length + unsafe.length;
	let fraction = 'none';
	if(total > 0){
		if(n === total && total >= 3) fraction = 'all';
		else if(n >= 2) fraction = '2/3';
		else if(n === 1) fraction = '1/3';
	}
	return { safe, unsafe, count: n, total, fraction };
}

// 主分析：sigA=问卜者征象星, sigB=事项征象星
export function analyzePerfection(facts, sigA, sigB, opts){
	opts = opts || {};
	const detail = [];
	const result = { perfects: false, method: null, translator: null, collector: null, ease: null, byWhom: null, destroyed: false, destruction: null, detail, aspect: null };
	if(!sigA || !sigB || !facts.planets[sigA] || !facts.planets[sigB]){
		detail.push('征象星不全，无法判断完成法。');
		return result;
	}
	const pA = facts.planets[sigA];
	const pB = facts.planets[sigB];

	// —— 完成法 ——
	// 1) 入相位 Application
	const asp = aspectBetween(facts, sigA, sigB);
	result.aspect = asp;
	if(asp && asp.applying){
		const rec = hasReception(facts, sigA, sigB);
		if((asp.angle === 90 || asp.angle === 180) && !rec){
			result.destroyed = true;
			result.destruction = 'no_reception_hard';
			detail.push(`${cn(sigA)} 与 ${cn(sigB)} 以${asp.angle}°（${asp.angle === 90 ? '四分' : '对分'}）入相位且无接纳 → 破坏。`);
		}else{
			result.perfects = true; result.method = 'application';
			result.ease = EASY.indexOf(asp.angle) >= 0 ? 'easy' : 'hard';
			detail.push(`两征象星入相位（${asp.angle}°）→ 直接完成${result.ease === 'easy' ? '（三/六合，轻松达成）' : '（四/对分，艰难拖延后达成）'}${rec ? '，且有接纳化解' : ''}。`);
			// 主动方（B.2）：谁入相谁
			if(asp.from === sigA) { result.byWhom = 'querent_effort'; detail.push('问卜者入相位对方 → 靠问卜者努力促成。'); }
			else { result.byWhom = 'other_initiates'; detail.push('对方入相位问卜者 → 由对方主动/自愿促成。'); }
		}
	}

	// 2) 光线传递 Translation（较轻星先出相一方、再入相另一方）—— 明确指出谁在哪两者之间传递
	if(!result.perfects && !result.destroyed){
		const cands = Object.keys(facts.planets).filter((k) => k !== sigA && k !== sigB);
		for(let i = 0; i < cands.length; i++){
			const T = cands[i];
			const sepA = separatingAspects(facts, T).some((x) => x.other === sigA);
			const appB = applyingAspects(facts, T).some((x) => x.other === sigB);
			const sepB = separatingAspects(facts, T).some((x) => x.other === sigB);
			const appA = applyingAspects(facts, T).some((x) => x.other === sigA);
			if(sepA && appB){
				result.perfects = true; result.method = 'translation'; result.translator = T; result.translatorFrom = sigA; result.translatorTo = sigB;
				detail.push(`光线传递：${cn(T)} 刚从 ${cn(sigA)} 出相位、正入相位 ${cn(sigB)} → 由 ${cn(T)} 把 ${cn(sigA)} 的光线带给 ${cn(sigB)}（中间人/信使＝${cn(T)}）促成。`);
				break;
			}
			if(sepB && appA){
				result.perfects = true; result.method = 'translation'; result.translator = T; result.translatorFrom = sigB; result.translatorTo = sigA;
				detail.push(`光线传递：${cn(T)} 刚从 ${cn(sigB)} 出相位、正入相位 ${cn(sigA)} → 由 ${cn(T)} 把 ${cn(sigB)} 的光线带给 ${cn(sigA)}（中间人/信使＝${cn(T)}）促成。`);
				break;
			}
		}
	}

	// 3) 集中/汇集 Collection（两征象星各入相同一较重星）—— 明确指出汇集于谁
	if(!result.perfects && !result.destroyed){
		const cands = Object.keys(facts.planets).filter((k) => k !== sigA && k !== sigB);
		for(let i = 0; i < cands.length; i++){
			const C = cands[i];
			const aToC = applyingAspects(facts, sigA).some((x) => x.other === C);
			const bToC = applyingAspects(facts, sigB).some((x) => x.other === C);
			if(aToC && bToC && !lighter(C, sigA) && !lighter(C, sigB)){
				result.perfects = true; result.method = 'collection'; result.collector = C;
				detail.push(`光线汇集：${cn(sigA)} 与 ${cn(sigB)} 同时入相位较重的 ${cn(C)} → 两方的光线汇集到 ${cn(C)}，经「法官/居中求助对象＝${cn(C)}」促成。`);
				break;
			}
		}
	}

	// 4) 落位 Position（征象星互落对方/事项宫位）
	if(!result.perfects && !result.destroyed){
		const qh = opts.quesitedHouse;
		if(qh && (pA.house === qh || pB.house === 1 || pB.house === qh)){
			result.perfects = true; result.method = 'position';
			detail.push('落位：征象星落对方/事项宫位 → 完成。');
		}
		// 映点也可促成（力≈六合/三合）
		const ant = antiscionBetween(facts, sigA, sigB);
		if(!result.perfects && ant){
			result.perfects = true; result.method = 'antiscion';
			detail.push('两征象星成映点（力量≈六合/三合）→ 完成。');
		}
	}

	// —— 破坏识别（补强）——
	if(pA.combustion === 'combust' || pB.combustion === 'combust'){
		if(result.perfects){ detail.push(`注意：${pA.combustion === 'combust' ? cn(sigA) : cn(sigB)} 燃烧，完成受严重削弱。`); }
		else { result.destroyed = true; result.destruction = 'combustion'; detail.push('征象星燃烧 → 最严重破坏。'); }
	}
	// 刚出相 = 事败（无任何完成法且两征象星正出相）
	if(!result.perfects && !result.destroyed){
		const sep = separatingAspects(facts, sigA).find((x) => x.other === sigB);
		if(sep){ result.destroyed = true; result.destruction = 'separation'; detail.push('两征象星刚出相位 → 事已过/绝对失败。'); }
	}
	if(!result.perfects && !result.destroyed){
		detail.push('未见明确完成法（入相/传递/汇集/落位），亦未见硬破坏 → 多半不成，宜结合其他证词。');
	}
	return result;
}

export default analyzePerfection;
