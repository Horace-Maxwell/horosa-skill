// divination/engine/moon.js
// 月亮专项（卜卦核心，构建清单 §2.2 + Dorotheus Ch5）。
import { norm360, angularDist, chartIdOfKey } from './utils.js';
import { viaCombustaRange } from './radicality.js';
import { applyingAspects } from './aspectsEngine.js';

const PTOLEMAIC_ANG = [0, 60, 90, 120, 180];
const CLASSICAL7 = ['sun', 'mercury', 'venus', 'mars', 'jupiter', 'saturn'];
// 中世纪「月不空」豁免座：金牛/巨蟹/射手/双鱼。
const VOC_EXEMPT = ['taurus', 'cancer', 'sagittarius', 'pisces'];

// [Q-299/T-288 ②] 燃烧之路变体人话边界(与 radicality.viaCombustaRange 同四档;卜卦流派表 horarySchools 同文案)。
export function viaCombustaLabel(variant){
	if(variant === 'scorpioFull') return '天秤15°–天蝎30°';
	if(variant === 'bothFull') return '天秤0°–天蝎30°';
	if(variant === 'narrow') return '天秤28°–天蝎7°';
	return '天秤15°–天蝎15°';
}

// 燃烧之路：天秤 15° – 天蝎 15° ≈ 黄经 195°–225°
export function isViaCombusta(moonLon){
	const l = norm360(moonLon);
	return l >= 195 && l <= 225;
}

// opts（卜卦流派可选；不传 = 择日/既有调用，行为字节不变）：
//   vocMode ——
//     'classic'(默认=「无入相/正合主相位即空」1647 法,别名 'backend'。
//               2026-07 勘误:旧注「按星座界」系误录;后端 isVOC 亦已同步支持六口径(chartdynamics),
//               显示链吃全局 vocMode、判读链吃本 opts——两链语义一致,数学对齐。
//               [Q-146] 本档不再直读后端 isVOC 旗,改前端按同一定义自算,否则流派绑定值会被全局值顶掉)
//     'kenodromia'(希腊化 30° 法:未来无对目标星准确入相则空)
//     'exempt4'(中世纪:豁免四座不作空亡)
//     'by_orb'(容许度法:距下一主相位精确点 ≤12°30′ 即不空,不拘星座界)
//     'by_sign_perfect'(现代:须在本座内实际完成主相位才不空)
//     'by_sign_orb'(16c 变体:本座内逼近到容许度内即不空,不需完成)
//   vocIncludeOuter —— true 时目标星含三王星(默认 false;仅作用于前端解算的四模式)
// [Q-146/T-53] classic(1647「无入相/正合主相位即空」)分支原直读后端 isVOC,而 /chart 请求带的是
// 【全局】空亡口径 → 流派绑定 classic(或择日左栏显式选 1647)时,判读实际吃的是全局口径。
// 改为与其余五口径同源:同一张后端相位表(normalAsp)前端自算——不拘星座界、对表内全部星体
// 无入相/正合托勒密相位即空。目标集口径:normalAsp 在「虚点接纳相位」关闭(缺省)时只含十星,
// 后端 isVOC('lilly') 还把交点/朔望/阿拉伯点/四轴算作解空者 —— 1647 的月空说的是行星间的入相,
// 且盘面/右栏本来就不显示那些虚点相位,故以表内十星为准(比旧旗更贴 1647,也与所见一致)。
// 相位表缺失(纯 stub facts / 老快照)时回落后端旗,绝不因取不到表凭空判空。
// 记忆化:择日扫描/压测会对成百上千个时刻各建一份 facts 并反复问月空 —— 旧实现读一面布尔旗是 O(1),
// 自算要遍历相位表。以「该盘月亮的相位表条目对象」为键缓存(值只由它决定;换盘即换对象),
// 不缓存无表回落旗的那条路径(测试会就地改 isVOC 再问一次)。
const CLASSIC_VOC_MEMO = typeof WeakMap === 'function' ? new WeakMap() : null;
export function classicVocOf(facts){
	const m = facts && facts.planets ? facts.planets.moon : null;
	const na = facts && facts.result && facts.result.aspects && facts.result.aspects.normalAsp;
	if(!m) return false;
	const entry = na ? na[chartIdOfKey('moon')] : null;
	if(!entry) return !!m.isVOC;
	if(CLASSIC_VOC_MEMO && typeof entry === 'object' && CLASSIC_VOC_MEMO.has(entry)){
		return CLASSIC_VOC_MEMO.get(entry);
	}
	const voc = !applyingAspects(facts, 'moon').some((a) => PTOLEMAIC_ANG.indexOf(a.angle) >= 0);
	if(CLASSIC_VOC_MEMO && typeof entry === 'object'){ CLASSIC_VOC_MEMO.set(entry, voc); }
	return voc;
}

// 月空判定单源(六口径 + 四座豁免):moonReport / 择日考量 / 规则包 / 硬旗 / 话题深化 全部走它,
// 任何一处再直读 m.isVOC 都会重演 T-53(一条链吃流派、另一条吃全局)。
export function resolveMoonVoc(facts, opts){
	opts = opts || {};
	const m = facts && facts.planets ? facts.planets.moon : null;
	if(!m) return { voc: false, note: null, classic: false };
	const vocMode = (opts.vocMode === 'backend') ? 'classic' : (opts.vocMode || 'classic');
	const targets = opts.vocIncludeOuter ? CLASSICAL7.concat(['uranus', 'neptune', 'pluto']) : CLASSICAL7;
	const moonApps = applyingAspects(facts, 'moon').filter((a) => targets.indexOf(a.other) >= 0 && PTOLEMAIC_ANG.indexOf(a.angle) >= 0);
	const classic = classicVocOf(facts);
	let voc = classic;
	let note = null;
	if(vocMode === 'kenodromia'){
		voc = !moonApps.length; note = 'kenodromia';
	}else if(vocMode === 'by_orb'){
		// 容许度法（12°30′）：距下一主相位精确点 ≤12.5° 即不空。后端相位表本身按半距和收录，
		// 月亮对七政的半距和 ≥ ~9.5°，故「在表内且 orb≤12.5」为忠实近似（跨座相位同样计入）。
		voc = !moonApps.some((a) => typeof a.orb === 'number' && a.orb <= 12.5);
		note = 'by_orb';
	}else if(vocMode === 'by_sign_perfect'){
		// 现代口径：须在本座内「完成」——入相位且精确点仍落本座（剩余弧 ≥ 当前差距）。
		const remain = 30 - (m.signlon !== undefined ? m.signlon : 0);
		voc = !moonApps.some((a) => typeof a.orb === 'number' && a.orb <= remain + 1e-9);
		note = 'by_sign_perfect';
	}else if(vocMode === 'by_sign_orb'){
		// 16c 变体：本座内「逼近到容许度内」即不空（在表内即已入容许度;若精确点在本座内更稳）。
		voc = !moonApps.length;
		note = 'by_sign_orb';
	}else if(vocMode === 'exempt4' && voc && VOC_EXEMPT.indexOf(m.sign) >= 0){
		voc = false; note = 'exempt4';
	}
	return { voc, note, classic };
}

export function moonReport(facts, opts){
	opts = opts || {};
	const m = facts.planets.moon;
	if(!m) return { findings: [], voc: false };
	const f = [];
	const mp = facts.meta.moonPhase || {};
	const vocMode = (opts.vocMode === 'backend') ? 'classic' : (opts.vocMode || 'classic');

	// —— 月空判定（流派可选，单源 resolveMoonVoc）——
	const vocRes = resolveMoonVoc(facts, opts);
	const voc = vocRes.voc;
	const vocNote = vocRes.note;

	if(voc){
		f.push({ key: 'voc', polarity: 'negative', weight: 3, text_zh: '月亮空相（VOC）：离开本座前不再成准确相位，事多无果 / 问题可能不真' + (vocNote === 'kenodromia' ? '（希腊化口径：未来无对七曜准确入相）' : '') });
		// [WP-F] 四座减凶注记(vocMitigateSigns):非 exempt4 口径下月落豁免四座 → 出中性注记
		// (判空布尔不变,只提示传统认为凶性减轻)。exempt4 口径已直接豁免,不重复出注。
		if(opts.vocMitigateSigns && vocMode !== 'exempt4' && VOC_EXEMPT.indexOf(m.sign) >= 0){
			f.push({ key: 'voc_mitigated_sign', polarity: 'neutral', weight: 1, text_zh: '月虽空相，但落金牛/巨蟹/射手/双鱼（传统豁免座）→ 凶性减轻，可酌情从宽（注记，不改判定）' });
		}
	}else if(vocNote === 'exempt4'){
		f.push({ key: 'voc_exempt', polarity: 'neutral', weight: 1, text_zh: '月本为空相，但落金牛/巨蟹/射手/双鱼（中世纪豁免座）→ 仍主能成，不作空亡论' });
	}else if(vocNote === 'kenodromia' && vocRes.classic){
		f.push({ key: 'voc_active', polarity: 'neutral', weight: 1, text_zh: '按现行（1647「无入相即空」）口径为空相，但未来仍有对七曜的准确入相（希腊化口径不作空亡）' });
	}
	const vcr = viaCombustaRange(opts.viaCombustaVariant);
	if(norm360(m.lon) >= vcr[0] && norm360(m.lon) <= vcr[1]){
		// [Q-299/T-288 ②] 注记边界随变体(此前恒写「天秤15°–天蝎15°」,窄口径/全宫变体下与判定不符)。
		f.push({ key: 'via_combusta', polarity: 'negative', weight: 2, text_zh: `月亮在燃烧之路（${viaCombustaLabel(opts.viaCombustaVariant)}）：最糟阻碍之一；尤忌婚姻/女性事务/买卖/出国（保密类除外）` });
	}
	if(mp.nearNew){
		f.push({ key: 'near_new', polarity: 'negative', weight: 1, text_zh: '临近新月（日月相距 <12°）：重要用事/手术宜避开前后数日' });
	}
	if(mp.nearFull){
		f.push({ key: 'near_full', polarity: 'negative', weight: 1, text_zh: '临近满月：手术/重要用事宜避开前后数日' });
	}
	if(mp.phase === 'waxing'){
		f.push({ key: 'waxing', polarity: 'neutral', weight: 1, text_zh: '月盈（增光）：宜建造/求取/创业；行度上偏慢（找回类难抓）' });
	}else if(mp.phase === 'waning'){
		f.push({ key: 'waning', polarity: 'neutral', weight: 1, text_zh: '月亏（减光）：宜遗嘱/手术/释放/戒断；行度上偏快（找回类易抓）' });
	}

	// 在交点 12° 内
	const nn = facts.planets.north_node;
	const sn = facts.planets.south_node;
	const nodeLon = nn ? nn.lon : (sn ? norm360(sn.lon + 180) : null);
	if(nodeLon !== null && angularDist(m.lon, nodeLon) <= 12){
		f.push({ key: 'on_nodes', polarity: 'negative', weight: 1, text_zh: '月亮在交点 12° 内，受限' });
	}

	// 落陷（天蝎）
	if(m.sign === 'scorpio'){
		f.push({ key: 'moon_fall', polarity: 'negative', weight: 2, text_zh: '月亮落陷于天蝎，带秘密/占有（婚姻盘尤忌）' });
	}
	// 末度数
	if(m.signlon !== undefined && m.signlon >= 28){
		f.push({ key: 'late_degree', polarity: 'negative', weight: 1, text_zh: '月亮在星座后段（≥28°），变动气质已现' });
	}

	const score = f.reduce((s, x) => s + (x.polarity === 'positive' ? x.weight : (x.polarity === 'negative' ? -x.weight : 0)), 0);
	return { findings: f, voc: voc, viaCombusta: isViaCombusta(m.lon), phase: mp.phase, score };
}

export default moonReport;
