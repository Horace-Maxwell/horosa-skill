// divination/engine/perfection.js
// 完成与破坏（判断「能否成事」核心）。Sahl §1.4 三完成法为主骨架 + Sibly 4 完成 / 7 破坏
// + 完成度三分（Sahl §1.8 / 补充 B.1）+ 难易/主动方（B.2）。
import { PLANETS } from '../data/planets.js';
import { aspectBetween, applyingAspects, separatingAspects, antiscionBetween } from './aspectsEngine.js';
import { receives, mutualReceptionBetween } from './reception.js';
import { signedDelta } from './utils.js';

const SPEED_ORDER = ['moon', 'mercury', 'venus', 'sun', 'mars', 'jupiter', 'saturn', 'uranus', 'neptune', 'pluto'];
function speedIdx(k){ const i = SPEED_ORDER.indexOf(k); return i < 0 ? 99 : i; }
function lighter(a, b){ return speedIdx(a) < speedIdx(b); }   // a 比 b 轻/快
function cn(k){ return (PLANETS[k] || {}).cn || k; }
const EASY = [0, 60, 120];

const PTOL = [0, 60, 90, 120, 180];

function hasReception(facts, a, b){
	return receives(facts, a, b) || receives(facts, b, a) || mutualReceptionBetween(facts, a, b);
}

// 阻碍 / 挫败 / 切断识别（两征象星入相位成相前，光线被第三星截断或事项另有所属）。
// 时序判据两口径（opts.interferenceTiming）：
//   'degree'(默认,零回归)＝以「入相位所差度数」近似「谁先成相」；
//   'speed'＝按带符号速度折算到达时间 t=Δ/|相对速度| 比较（04§4.3 文档口径）。
// 术语调和公式（04§4.4）：阻止/挫败命名第三星抢先的「行为」；切断 abscission 命名
// 「较快第三星抢先与 mover 完成相位、把 mover 的光线截走」这一结果情形。
function arriveMetric(facts, x, fromKey, toKey, mode){
	if(typeof x.orb !== 'number') return null;
	if(mode !== 'speed') return x.orb;
	const pa = facts.planets[fromKey]; const pb = facts.planets[toKey];
	const rel = Math.abs(((pa && pa.speed) || 0) - ((pb && pb.speed) || 0));
	return rel > 1e-6 ? x.orb / rel : x.orb * 1e6;
}
function detectInterference(facts, sigA, sigB, mover, target, dAB, opts){
	if(typeof dAB !== 'number') return null;
	const mode = (opts && opts.interferenceTiming) || 'degree';
	const dABm = mode === 'speed' ? arriveMetric(facts, { orb: dAB }, mover, target, mode) : dAB;
	const cands = Object.keys(facts.planets).filter((k) => k !== sigA && k !== sigB);
	// 阻碍 prohibition：第三星 T 抢先入相 target（比 mover 更快成相）→ 第三方/意外插入截断。
	for(let i = 0; i < cands.length; i++){
		const T = cands[i];
		const app = applyingAspects(facts, T).find((x) => x.other === target && PTOL.indexOf(x.angle) >= 0);
		if(app && typeof app.orb === 'number' && arriveMetric(facts, app, T, target, mode) < dABm - 0.01){
			return { kind: 'prohibition', planet: T, text: `阻碍（prohibition）：${cn(T)} 抢先与 ${cn(target)} 成相（还差 ${app.orb.toFixed(1)}°，早于两征象星的 ${dAB.toFixed(1)}°）→ 光线被第三方截断，事遭插入 / 阻挠。` };
		}
	}
	// 切断 abscission（opts.detectAbscission 才启用——默认关，保持既有默认输出零回归）：
	// 较快第三星 T 抢先与 mover 完成相位 → mover 的光线在到达 target 前被截走。
	if(opts && opts.detectAbscission){
		for(let i = 0; i < cands.length; i++){
			const T = cands[i];
			const app = applyingAspects(facts, T).find((x) => x.other === mover && PTOL.indexOf(x.angle) >= 0);
			if(app && typeof app.orb === 'number' && arriveMetric(facts, app, T, mover, mode) < dABm - 0.01){
				return { kind: 'abscission', planet: T, text: `光线切断（abscission）：${cn(T)} 抢先与 ${cn(mover)} 完成相位（还差 ${app.orb.toFixed(1)}°，早于两征象星的 ${dAB.toFixed(1)}°）→ ${cn(mover)} 的光线在抵达 ${cn(target)} 前被截断。` };
			}
		}
	}
	// 挫败 frustration：target 先与另一（非 mover）星成相 → 事项另有所属，被抢先。
	const targetApps = applyingAspects(facts, target)
		.filter((x) => x.other !== mover && x.other !== target && PTOL.indexOf(x.angle) >= 0)
		.sort((a, b) => (arriveMetric(facts, a, target, a.other, mode) - arriveMetric(facts, b, target, b.other, mode)));
	if(targetApps.length && typeof targetApps[0].orb === 'number' && arriveMetric(facts, targetApps[0], target, targetApps[0].other, mode) < dABm - 0.01){
		const T = targetApps[0].other;
		return { kind: 'frustration', planet: T, text: `挫败（frustration）：${cn(target)} 先与 ${cn(T)} 成相（还差 ${targetApps[0].orb.toFixed(1)}°，早于与 ${cn(mover)} 的 ${dAB.toFixed(1)}°）→ 事项另有所属，被抢先一步。` };
	}
	return null;
}

// ── 无-orb 序列完成（orbMode='sequence' 门控;04§4.0 序列口径）：不问当下是否入容许度,
// 只问「按当前速度线性外推,两星能否在双方各自离开本座之前把某个托勒密相位走到精确」。
// 逆行以带符号速度自然参与（背向 → 无正解 → 正确地不完成）。返回最早可成的 {angle, tDays, orbNow}。
export function sequenceFuturePerfect(facts, a, b){
	const pa = facts.planets[a]; const pb = facts.planets[b];
	if(!pa || !pb || pa.lon === undefined || pb.lon === undefined) return null;
	const va = pa.speed || 0; const vb = pb.speed || 0;
	const rel = va - vb;
	if(Math.abs(rel) < 1e-6) return null;
	const d0 = signedDelta(pb.lon, pa.lon);   // a−b ∈ (−180,180]
	const remainIn = (p, v, t) => {
		if(p.signlon === undefined) return true;
		const end = p.signlon + v * t;
		return end >= 0 && end < 30;
	};
	let best = null;
	[0, 60, 90, 120, 180].forEach((A) => {
		const targets = (A === 0 || A === 180) ? [A === 0 ? 0 : 180, A === 0 ? 0 : -180] : [A, -A];
		targets.forEach((T) => {
			for(let k = -1; k <= 1; k++){
				const t = (T - d0 + 360 * k) / rel;
				if(t > 1e-6 && remainIn(pa, va, t) && remainIn(pb, vb, t)){
					if(!best || t < best.tDays){ best = { angle: A, tDays: t, orbNow: Math.min(Math.abs(T - d0), 360 - Math.abs(T - d0)) }; }
				}
			}
		});
	});
	return best;
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
	// 1) 入相位 Application（先查阻碍/挫败：光线在成相前被截 → 阻断完成）
	const asp = aspectBetween(facts, sigA, sigB);
	result.aspect = asp;
	if(asp && asp.applying){
		const mover = (asp.from === sigA) ? sigA : sigB;
		const target = (asp.from === sigA) ? sigB : sigA;
		// 现代心理档（lenient）淡化机械截断，仅取主完成法；其余档按古典识别阻碍/挫败(/切断,门控)。
		const inter = (opts.perfectionStrict === 'lenient') ? null : detectInterference(facts, sigA, sigB, mover, target, asp.orb, opts);
		if(inter){
			result.destroyed = true; result.destruction = inter.kind; result.interferer = inter.planet;
			detail.push(inter.text);
		}
	}
	if(asp && asp.applying && !result.destroyed){
		const mover = (asp.from === sigA) ? sigA : sigB;
		const rec = hasReception(facts, sigA, sigB);
		// 撤回 refranation 独立破坏态（opts.refranationAsDestruction 门控;默认仍为风险注记=零回归）。
		// 变体：refranationIncludeSignChange —— mover 在精确前先出本座（顺行且剩余弧 < 所差度数）亦作撤回。
		let refranationHit = null;
		const pm = facts.planets[mover];
		if(opts.refranationAsDestruction && pm){
			if(pm.retro){ refranationHit = `撤回（refranation）：入相方 ${cn(mover)} 逆行、精确前自我反向 → 相位永不完成。`; }
			else if(opts.refranationIncludeSignChange && pm.signlon !== undefined && typeof asp.orb === 'number' && (30 - pm.signlon) < asp.orb){
				refranationHit = `撤回（变体）：入相方 ${cn(mover)} 将在精确前先换星座（剩余 ${(30 - pm.signlon).toFixed(1)}° < 所差 ${asp.orb.toFixed(1)}°）→ 相位不在本座完成。`;
			}
		}
		if(refranationHit){
			result.destroyed = true; result.destruction = 'refranation';
			detail.push(refranationHit);
		}else if((asp.angle === 90 || asp.angle === 180) && rec && opts.perfectionStrict === 'strict'){
			// 严格档独有差异:硬相位即使有接纳也只减损不豁免——完成但带「得而复失/成而后悔」。
			// (standard 档接纳即化解=零回归;strict 只在「硬相位+有接纳」的边缘局面显形。)
			result.perfects = true; result.method = 'application'; result.ease = 'hard'; result.regret = true;
			detail.push(`两征象星以${asp.angle}°硬相位入相、虽有接纳——严格档:接纳仅减损不免破,事可成但常伴反复/后悔。`);
		}else if((asp.angle === 90 || asp.angle === 180) && !rec){
			// 冲相三态（opts.oppositionVerdict='yes_but' 时 180° 无接纳 → YES-but 得而复失;默认破坏=零回归）。
			if(asp.angle === 180 && opts.oppositionVerdict === 'yes_but'){
				result.perfects = true; result.method = 'application'; result.ease = 'hard'; result.regret = true;
				detail.push(`两征象星对分入相位且无接纳 → 事可成但常「得而复失/成而后悔」（冲相三态口径）。`);
			}else{
				result.destroyed = true;
				result.destruction = 'no_reception_hard';
				detail.push(`${cn(sigA)} 与 ${cn(sigB)} 以${asp.angle}°（${asp.angle === 90 ? '四分' : '对分'}）入相位且无接纳 → 破坏。`);
			}
		}else{
			result.perfects = true; result.method = 'application';
			result.ease = EASY.indexOf(asp.angle) >= 0 ? 'easy' : 'hard';
			detail.push(`两征象星入相位（${asp.angle}°）→ 直接完成${result.ease === 'easy' ? '（三/六合，轻松达成）' : '（四/对分，艰难拖延后达成）'}${rec ? '，且有接纳化解' : ''}。`);
			// 主动方（B.2）：谁入相谁
			if(asp.from === sigA) { result.byWhom = 'querent_effort'; detail.push('问卜者入相位对方 → 靠问卜者努力促成。'); }
			else { result.byWhom = 'other_initiates'; detail.push('对方入相位问卜者 → 由对方主动/自愿促成。'); }
			// 折返 refranation：入相方逆行 → 临成又退，恐反复/告吹。
			if(pm && pm.retro){ result.refranationRisk = true; detail.push(`注意：入相方 ${cn(mover)} 逆行 → 恐折返（refranation），临成又退、事有反复。`); }
		}
	}

	// 1b) 无-orb 序列完成（orbMode='sequence' 门控）：后端容许度表未见入相位时,按线性外推判
	//     「本座内最终精确」。硬相位无接纳仍按破坏/三态口径。
	if(!result.perfects && !result.destroyed && opts.orbMode === 'sequence' && !(asp && asp.applying)){
		const seq = sequenceFuturePerfect(facts, sigA, sigB);
		if(seq){
			const rec = hasReception(facts, sigA, sigB);
			if((seq.angle === 90 || seq.angle === 180) && !rec && !(seq.angle === 180 && opts.oppositionVerdict === 'yes_but')){
				result.destroyed = true; result.destruction = 'no_reception_hard';
				detail.push(`序列外推：两征象星将以 ${seq.angle}° 精确但无接纳 → 破坏（无-orb 序列口径）。`);
			}else{
				result.perfects = true; result.method = 'application'; result.sequence = true;
				result.ease = EASY.indexOf(seq.angle) >= 0 ? 'easy' : 'hard';
				if(seq.angle === 180 && !rec && opts.oppositionVerdict === 'yes_but'){ result.regret = true; }
				result.aspect = result.aspect || { angle: seq.angle, orb: seq.orbNow, from: sigA, to: sigB, sequence: true };
				detail.push(`序列完成（无-orb）：线性外推约 ${Math.round(seq.tDays * 10) / 10} 天后 ${cn(sigA)} 与 ${cn(sigB)} 以 ${seq.angle}° 精确（双方均未出本座）→ 事终能成。`);
			}
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
	//    严格派条件（opts.collectionRequireReception 门控）：汇集星须同时被双方容纳
	//    （CA p.111「they both receive him in some of their essential dignities」——C 落 A 与 B 的尊贵中）。
	if(!result.perfects && !result.destroyed){
		const cands = Object.keys(facts.planets).filter((k) => k !== sigA && k !== sigB);
		for(let i = 0; i < cands.length; i++){
			const C = cands[i];
			const aToC = applyingAspects(facts, sigA).some((x) => x.other === C);
			const bToC = applyingAspects(facts, sigB).some((x) => x.other === C);
			if(aToC && bToC && !lighter(C, sigA) && !lighter(C, sigB)){
				if(opts.collectionRequireReception){
					const bothReceive = receives(facts, sigA, C) && receives(facts, sigB, C);
					if(!bothReceive){
						detail.push(`汇集候选 ${cn(C)} 未被双方容纳（严格派要求 C 落两征象星尊贵中）→ 不作汇集完成。`);
						continue;
					}
				}
				result.perfects = true; result.method = 'collection'; result.collector = C;
				detail.push(`光线汇集：${cn(sigA)} 与 ${cn(sigB)} 同时入相位较重的 ${cn(C)} → 两方的光线汇集到 ${cn(C)}，经「法官/居中求助对象＝${cn(C)}」促成${opts.collectionRequireReception ? '（且满足双方容纳的严格条件）' : ''}。`);
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
	// 燃烧豁免（opts.combustExemptConjAnswer 门控）：当「与太阳合相」本身即所求之「是」
	// （事项征象星=太阳且完成法为合相入相位）时，燃烧不作破坏——否则日永无法与任何星合。
	const conjIsAnswer = !!(opts.combustExemptConjAnswer && result.perfects && result.method === 'application'
		&& result.aspect && result.aspect.angle === 0 && (sigA === 'sun' || sigB === 'sun'));
	if(pA.combustion === 'combust' || pB.combustion === 'combust'){
		if(conjIsAnswer){ detail.push('征象星虽入燃烧范围，但「与太阳合相」正是所问之答案 → 燃烧豁免，不作破坏。'); }
		else if(result.perfects){ detail.push(`注意：${pA.combustion === 'combust' ? cn(sigA) : cn(sigB)} 燃烧，完成受严重削弱。`); }
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
