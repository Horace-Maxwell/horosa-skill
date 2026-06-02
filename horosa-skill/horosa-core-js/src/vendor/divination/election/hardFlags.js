// divination/election/hardFlags.js
// 红线/警告系统（择日清单 §4）。布尔检查，命中进 hard_flags[]，按 severity 影响评分/分级。
// 带 * 的规则参照当前 topic.must_avoid 决定触发/升降级。
import { aspectsOf } from '../engine/aspectsEngine.js';
import { isViaCombusta } from '../engine/moon.js';
import { PLANETS } from '../data/planets.js';
import { SIGNS } from '../data/signs.js';

function lord1Of(facts){
	const s = facts.meta.ascSign;
	return s && SIGNS[s] ? SIGNS[s].domicile : null;
}

function cn(k){ return (PLANETS[k] || {}).cn || k; }

export function evalHardFlags(facts, topic){
	const flags = [];
	const mustAvoid = (topic && topic.must_avoid) || [];
	const inAvoid = (id) => mustAvoid.indexOf(id) >= 0;
	const add = (id, severity, message, factor) => flags.push({ id, severity, message, factor });

	const moon = facts.planets.moon;
	if(moon){
		if(moon.isVOC) add('moon_void_of_course', 'critical', '月亮空亡：此刻起的行动通常无效应', 'moon');
		const ma = aspectsOf(facts, 'moon');
		if(ma.some((a) => a.angle === 90)) add('moon_square', 'high', '月亮逢刑（90°）：不安定、缺生产力 → 应避', 'moon');
		if(ma.some((a) => a.angle === 180)) add('moon_opposition', 'medium', '月亮逢冲（180°）：尤不利合作', 'moon');
		if(moon.combustion) add('moon_combust', 'medium', '月亮在日光束下，力量受限', 'moon');
		if(isViaCombusta(moon.lon)) add('moon_via_combusta', 'high', '月在燃烧之路（天秤15°–天蝎15°）：最糟阻碍之一', 'moon');
		const mp = facts.meta.moonPhase;
		if(mp && (mp.nearNew || mp.nearFull)) add('near_new_or_full_moon', 'medium', '临近新/满月：手术/重要用事宜避前后数日', 'moon');
		if(moon.sign === 'scorpio') add('moon_in_fall', 'medium', '月落陷天蝎，带秘密/占有（婚姻盘尤忌）', 'moon');
		if(moon.signlon >= 28) add('moon_late_degrees', 'low', '月在星座后段（≥28°）、变动气质', 'moon');
		if(moon.speed !== undefined && Math.abs(moon.speed) < 13) add('moon_slow', 'low', '月行度缓慢（<13°/日）、力弱', 'moon');
	}

	// 逆行（带 *：纯入宅等不触发，由 topic.must_avoid 控制升降级）
	['mercury', 'venus', 'mars', 'jupiter'].forEach((k) => {
		const p = facts.planets[k];
		if(p && p.retro){
			let sev = k === 'jupiter' ? 'medium' : 'high';
			if(!inAvoid(k + '_retro') && !inAvoid('mercury_retro_for_contract')) sev = k === 'jupiter' ? 'low' : 'medium';
			add(k + '_retro', sev, `${cn(k)} 逆行（按用事性质决定是否必避）`, k);
		}
	});

	// 命主/用事宫主逆行
	const lord1 = lord1Of(facts);
	if(lord1 && facts.planets[lord1] && facts.planets[lord1].retro){
		add('sig_ruler_retro', 'high', `命主（${cn(lord1)}）逆行：主管命宫的星逆行始终标红`, lord1);
	}

	// 凶星临角宫且无力
	['mars', 'saturn', 'uranus', 'neptune'].forEach((k) => {
		const p = facts.planets[k];
		if(p && p.angularity === 'angular' && (p.dignityScore <= 0 || p.combustion === 'combust' || p.retro)){
			add('malefic_on_angle', 'high', `${cn(k)} 凶星临角宫且无援`, k);
		}
	});
	const sat = facts.planets.saturn;
	if(sat && sat.angularity === 'angular' && !inAvoid('saturn_building_ok')){
		add('saturn_on_angle', inAvoid('saturn_on_angle_1_7') ? 'high' : 'medium', '土星入始宫：阻碍/延迟（建筑/管理/土地用事除外，但仍需吉相）', 'saturn');
	}
	const ura = facts.planets.uranus;
	if(ura && (ura.house === 1 || ura.house === 7)){
		add('uranus_on_angle_1_7', 'high', '天王星在 1 或 7 宫：分离/决裂（婚姻盘尤忌）', 'uranus');
	}

	// 南交点会合 Asc/日/月（近似：南交点在 1 宫且近上升）
	const sn = facts.planets.south_node;
	if(sn && (sn.house === 1)){
		add('south_node_on_point', 'medium', '南交点近上升：不喜南交点会合关键点', 'south_node');
	}

	// 用事星游走
	(topic && topic.natural_significators || []).forEach((k) => {
		const p = facts.planets[k];
		if(p && p.peregrine) add('peregrine_significator', 'low', `用事星 ${cn(k)} 游走（无尊贵），缺乏力量`, k);
	});

	return flags;
}

export default evalHardFlags;
