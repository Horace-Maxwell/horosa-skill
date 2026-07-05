// divination/election/mundaneIntegration.js
// 时势合参（择日清单 §时势擇日）：择日盘命度/用事星 与「时势盘」（当年春分入宫 / 前一次新满月 / 前一次日月食）合参。
// 输入：择日 elecFacts + 时势盘 facts 集合。产出合参注记。仅在用户拉取时势盘后可用。
import { angularDist } from '../engine/utils.js';
import { PLANETS } from '../data/planets.js';

function cn(k){ return (PLANETS[k] || {}).cn || k; }

function near(d, ang, orb){ return Math.abs(angularDist0(d, ang)) <= orb; }
function angularDist0(d, ang){ const x = Math.abs(d - ang); return Math.min(x, 360 - x); }

export function mundaneIntegration(elecFacts, set){
	const notes = [];
	if(!elecFacts || !set){ return { notes, available: false }; }
	const add = (pol, text) => notes.push({ pol, text });
	const ascLon = elecFacts.meta.ascLon;
	const checks = [
		{ key: 'ingress', label: '当年春分入宫盘', facts: set.ingress },
		{ key: 'newMoon', label: '前一次新月图', facts: set.newMoon },
		{ key: 'fullMoon', label: '前一次满月图', facts: set.fullMoon },
		{ key: 'eclipse', label: '前一次日/月食图', facts: set.eclipse },
	];
	let any = false;
	checks.forEach((c) => {
		if(!c.facts || ascLon == null){ return; }
		any = true;
		// 择日命度被时势盘凶星（火/土）紧密合/刑/冲 ≤4° → 时势不利
		['mars', 'saturn'].forEach((k) => {
			const mp = c.facts.planets[k]; if(!mp || mp.lon == null) return;
			const d = angularDist(ascLon, mp.lon);
			if(d <= 4 || near(d, 90, 4) || near(d, 180, 4)){
				add('negative', `择日命度被${c.label}的${cn(k)}紧密克 → 时势不利，宜避或缓。`);
			}
		});
		// 择日命度与时势盘吉星（木/金）成三合/六合 → 时势助力
		['jupiter', 'venus'].forEach((k) => {
			const mp = c.facts.planets[k]; if(!mp || mp.lon == null) return;
			const d = angularDist(ascLon, mp.lon);
			if(near(d, 120, 4) || near(d, 60, 4)){
				add('positive', `择日命度与${c.label}的${cn(k)}成吉相 → 时势助力。`);
			}
		});
	});
	if(!any){ return { notes, available: false }; }
	if(notes.filter((n) => n.pol !== 'info').length === 0){
		add('positive', '择日命度未见时势盘凶星紧密克，时势可接受。');
	}
	return { notes, available: true };
}

export default mundaneIntegration;
