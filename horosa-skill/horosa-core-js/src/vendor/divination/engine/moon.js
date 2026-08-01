// divination/engine/moon.js
// 月亮专项（卜卦核心，构建清单 §2.2 + Dorotheus Ch5）。
import { norm360, angularDist } from './utils.js';
import { viaCombustaRange } from './radicality.js';
import { applyingAspects } from './aspectsEngine.js';

const PTOLEMAIC_ANG = [0, 60, 90, 120, 180];
const CLASSICAL7 = ['sun', 'mercury', 'venus', 'mars', 'jupiter', 'saturn'];
// 中世纪「月不空」豁免座：金牛/巨蟹/射手/双鱼。
const VOC_EXEMPT = ['taurus', 'cancer', 'sagittarius', 'pisces'];

// 燃烧之路：天秤 15° – 天蝎 15° ≈ 黄经 195°–225°
export function isViaCombusta(moonLon){
	const l = norm360(moonLon);
	return l >= 195 && l <= 225;
}

// opts（卜卦流派可选；不传 = 择日/既有调用，行为字节不变）：
//   vocMode ——
//     'classic'(默认,读后端 isVOC;后端口径=「无入相/正合主相位即空」1647 法,别名 'backend'。
//               2026-07 勘误:旧注「按星座界」系误录;后端 isVOC 亦已同步支持六口径(chartdynamics),
//               显示链吃全局 vocMode、判读链吃本 opts——两链语义一致,数学对齐)
//     'kenodromia'(希腊化 30° 法:未来无对目标星准确入相则空)
//     'exempt4'(中世纪:豁免四座不作空亡)
//     'by_orb'(容许度法:距下一主相位精确点 ≤12°30′ 即不空,不拘星座界)
//     'by_sign_perfect'(现代:须在本座内实际完成主相位才不空)
//     'by_sign_orb'(16c 变体:本座内逼近到容许度内即不空,不需完成)
//   vocIncludeOuter —— true 时目标星含三王星(默认 false;仅作用于前端解算的四模式)
export function moonReport(facts, opts){
	opts = opts || {};
	const m = facts.planets.moon;
	if(!m) return { findings: [], voc: false };
	const f = [];
	const mp = facts.meta.moonPhase || {};
	const vocMode = (opts.vocMode === 'backend') ? 'classic' : (opts.vocMode || 'classic');
	const targets = opts.vocIncludeOuter ? CLASSICAL7.concat(['uranus', 'neptune', 'pluto']) : CLASSICAL7;
	const moonApps = applyingAspects(facts, 'moon').filter((a) => targets.indexOf(a.other) >= 0 && PTOLEMAIC_ANG.indexOf(a.angle) >= 0);

	// —— 月空判定（流派可选）——
	let voc = !!m.isVOC;
	let vocNote = null;
	if(vocMode === 'kenodromia'){
		voc = !moonApps.length; vocNote = 'kenodromia';
	}else if(vocMode === 'by_orb'){
		// 容许度法（12°30′）：距下一主相位精确点 ≤12.5° 即不空。后端相位表本身按半距和收录，
		// 月亮对七政的半距和 ≥ ~9.5°，故「在表内且 orb≤12.5」为忠实近似（跨座相位同样计入）。
		voc = !moonApps.some((a) => typeof a.orb === 'number' && a.orb <= 12.5);
		vocNote = 'by_orb';
	}else if(vocMode === 'by_sign_perfect'){
		// 现代口径：须在本座内「完成」——入相位且精确点仍落本座（剩余弧 ≥ 当前差距）。
		const remain = 30 - (m.signlon !== undefined ? m.signlon : 0);
		voc = !moonApps.some((a) => typeof a.orb === 'number' && a.orb <= remain + 1e-9);
		vocNote = 'by_sign_perfect';
	}else if(vocMode === 'by_sign_orb'){
		// 16c 变体：本座内「逼近到容许度内」即不空（在表内即已入容许度;若精确点在本座内更稳）。
		voc = !moonApps.length;
		vocNote = 'by_sign_orb';
	}else if(vocMode === 'exempt4' && voc && VOC_EXEMPT.indexOf(m.sign) >= 0){
		voc = false; vocNote = 'exempt4';
	}

	if(voc){
		f.push({ key: 'voc', polarity: 'negative', weight: 3, text_zh: '月亮空相（VOC）：离开本座前不再成准确相位，事多无果 / 问题可能不真' + (vocNote === 'kenodromia' ? '（希腊化口径：未来无对七曜准确入相）' : '') });
		// [WP-F] 四座减凶注记(vocMitigateSigns):非 exempt4 口径下月落豁免四座 → 出中性注记
		// (判空布尔不变,只提示传统认为凶性减轻)。exempt4 口径已直接豁免,不重复出注。
		if(opts.vocMitigateSigns && vocMode !== 'exempt4' && VOC_EXEMPT.indexOf(m.sign) >= 0){
			f.push({ key: 'voc_mitigated_sign', polarity: 'neutral', weight: 1, text_zh: '月虽空相，但落金牛/巨蟹/射手/双鱼（传统豁免座）→ 凶性减轻，可酌情从宽（注记，不改判定）' });
		}
	}else if(vocNote === 'exempt4'){
		f.push({ key: 'voc_exempt', polarity: 'neutral', weight: 1, text_zh: '月本为空相，但落金牛/巨蟹/射手/双鱼（中世纪豁免座）→ 仍主能成，不作空亡论' });
	}else if(vocNote === 'kenodromia' && m.isVOC){
		f.push({ key: 'voc_active', polarity: 'neutral', weight: 1, text_zh: '按星座界为空相，但未来仍有对七曜的准确入相（希腊化口径不作空亡）' });
	}
	const vcr = viaCombustaRange(opts.viaCombustaVariant);
	if(norm360(m.lon) >= vcr[0] && norm360(m.lon) <= vcr[1]){
		f.push({ key: 'via_combusta', polarity: 'negative', weight: 2, text_zh: '月亮在燃烧之路（天秤15°–天蝎15°）：最糟阻碍之一；尤忌婚姻/女性事务/买卖/出国（保密类除外）' });
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
