// divination/engine/radicality.js
// 卜卦根本性门禁（构建清单 §2.6）+ Hephaistion 一般禁忌（2/8 宫）+ 痣验证（可选）。
// 警告不阻断，交用户决定。
import { SIGNS } from '../data/signs.js';
import { PLANETS } from '../data/planets.js';
import { bodyPartsOf, degreePosition, moleSide, moleFrontBack } from '../data/bodyParts.js';
import { aspectBetween } from './aspectsEngine.js';

function cn(k){ return (PLANETS[k] || {}).cn || k; }

export function ascRulerKey(facts){
	const s = facts.meta.ascSign;
	return s && SIGNS[s] ? SIGNS[s].domicile : null;
}

export function radicality(facts){
	const warnings = [];
	const ok = [];
	const meta = facts.meta;
	const ascRuler = ascRulerKey(facts);
	const lord1 = ascRuler;

	// 适合判断
	if(meta.hourRuler && lord1){
		const hr = PLANETS[meta.hourRuler]; const l1 = PLANETS[lord1];
		if(hr && l1 && (meta.hourRuler === lord1 || hr.sect === l1.sect)){
			ok.push('上升定位星与时主星同性质/同宗派 → 适合判断。');
		}
	}

	// 警告（§2.6）
	const ad = meta.ascDegree;
	if(ad !== null && ad !== undefined){
		if(ad < 3) warnings.push({ key: 'asc_early', text: `上升落星座极早（${ad.toFixed(1)}°<3°）：恐为时过早/无赖捏造，慎判。` });
		else if(ad > 27) warnings.push({ key: 'asc_late', text: `上升落星座极晚（${ad.toFixed(1)}°>27°）：事已成定局/问者已知答案，慎判。` });
	}
	const moon = facts.planets.moon;
	if(moon){
		if(moon.isVOC) warnings.push({ key: 'moon_voc', text: '月亮空相：问题可能不真或无果。' });
		if(moon.combustion === 'combust') warnings.push({ key: 'moon_combust', text: '月亮燃烧：受克严重，慎判。' });
		// 月与七宫主刑冲
		const l7 = facts.houses[7] && facts.houses[7].ruler;
		if(l7){
			const a = aspectBetween(facts, 'moon', l7);
			if(a && (a.angle === 90 || a.angle === 180)) warnings.push({ key: 'moon_l7_hard', text: `月亮与七宫主（${cn(l7)}）${a.angle === 90 ? '四分' : '对分'}：传统视为不宜判断。` });
		}
	}
	const sat = facts.planets.saturn;
	if(sat && sat.house === 1 && (sat.retro || sat.combustion === 'combust' || sat.dignityScore <= -4)){
		warnings.push({ key: 'saturn_asc', text: '土星落上升且受克：占星师/判断本身受阻。' });
	}
	if(lord1 && facts.planets[lord1]){
		const lp = facts.planets[lord1];
		if(lp.combustion === 'combust') warnings.push({ key: 'l1_combust', text: `上升定位星（${cn(lord1)}）燃烧：问卜者状态受灼。` });
		if(lp.retro) warnings.push({ key: 'l1_retro', text: `上升定位星（${cn(lord1)}）逆行：事态反复。` });
		// Hephaistion 2/8 禁忌
		if(lp.house === 2 || lp.house === 8) warnings.push({ key: 'l1_in_2_8', text: `上升主落 ${lp.house} 宫（Hephaistion 忌 2/8 宫）。` });
	}

	const suitable = warnings.length === 0;
	return { suitable, warnings, ok, ascRuler, moleHints: moleHints(facts) };
}

// 痣验证（可选增强）：列出对应身体部位 + 颜色 + 左右 + 前后 + 上中下
export function moleHints(facts){
	const hints = [];
	const add = (label, key) => {
		const p = facts.planets[key];
		const sign = p ? p.sign : null;
		if(!sign) return;
		const sgn = SIGNS[sign];
		const parts = bodyPartsOf(sign);
		hints.push({
			source: label,
			sign,
			parts,
			side: sgn ? moleSide(sgn.gender) : null,
			frontBack: p ? moleFrontBack(p.aboveHorizon) : null,
			updown: p && p.signlon !== undefined ? degreePosition(p.signlon) : null,
		});
	};
	const ascRuler = ascRulerKey(facts);
	const ascSign = facts.meta.ascSign;
	if(ascSign){ const parts = bodyPartsOf(ascSign); hints.push({ source: '上升座', sign: ascSign, parts }); }
	if(ascRuler) add('上升定位星所落座', ascRuler);
	const l6 = facts.houses[6] && facts.houses[6].ruler;
	if(facts.houses[6]) hints.push({ source: '六宫头座', sign: facts.houses[6].sign, parts: bodyPartsOf(facts.houses[6].sign) });
	if(l6) add('六宫主所落座', l6);
	add('月亮所落座', 'moon');
	return hints;
}

export default radicality;
