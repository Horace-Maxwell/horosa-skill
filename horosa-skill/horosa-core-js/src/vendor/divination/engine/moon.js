// divination/engine/moon.js
// 月亮专项（卜卦核心，构建清单 §2.2 + Dorotheus Ch5）。
import { norm360, angularDist } from './utils.js';
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
//   vocMode —— 'classic'(默认,后端按星座界 isVOC) | 'kenodromia'(希腊化:未来无对七曜准确入相则空) | 'exempt4'(中世纪:豁免四座不作空亡)
export function moonReport(facts, opts){
	opts = opts || {};
	const m = facts.planets.moon;
	if(!m) return { findings: [], voc: false };
	const f = [];
	const mp = facts.meta.moonPhase || {};
	const vocMode = opts.vocMode || 'classic';

	// —— 月空判定（流派可选）——
	let voc = !!m.isVOC;
	let vocNote = null;
	if(vocMode === 'kenodromia'){
		const hasApplying = applyingAspects(facts, 'moon').some((a) => CLASSICAL7.indexOf(a.other) >= 0 && PTOLEMAIC_ANG.indexOf(a.angle) >= 0);
		voc = !hasApplying; vocNote = 'kenodromia';
	}else if(vocMode === 'exempt4' && voc && VOC_EXEMPT.indexOf(m.sign) >= 0){
		voc = false; vocNote = 'exempt4';
	}

	if(voc){
		f.push({ key: 'voc', polarity: 'negative', weight: 3, text_zh: '月亮空相（VOC）：离开本座前不再成准确相位，事多无果 / 问题可能不真' + (vocNote === 'kenodromia' ? '（希腊化口径：未来无对七曜准确入相）' : '') });
	}else if(vocNote === 'exempt4'){
		f.push({ key: 'voc_exempt', polarity: 'neutral', weight: 1, text_zh: '月本为空相，但落金牛/巨蟹/射手/双鱼（中世纪豁免座）→ 仍主能成，不作空亡论' });
	}else if(vocNote === 'kenodromia' && m.isVOC){
		f.push({ key: 'voc_active', polarity: 'neutral', weight: 1, text_zh: '按星座界为空相，但未来仍有对七曜的准确入相（希腊化口径不作空亡）' });
	}
	if(isViaCombusta(m.lon)){
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
