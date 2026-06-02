// divination/election/natalIntegration.js
// 与本命盘结合（择日清单 §7）：择日盘 = 对本命的一次「永久过运」。
// 输入两个 facts（本命 natalFacts + 择日 elecFacts），产出合参注记。
import { norm360, angularDist } from '../engine/utils.js';
import { PLANETS } from '../data/planets.js';

function cn(k){ return (PLANETS[k] || {}).cn || k; }

const ASPECTS = [
	{ a: 0, n: '合', orb: 6 }, { a: 60, n: '六合', orb: 4 }, { a: 90, n: '四分', orb: 5 },
	{ a: 120, n: '三合', orb: 5 }, { a: 180, n: '对分', orb: 6 },
];
function crossAspect(lon1, lon2){
	if(lon1 === null || lon2 === null || lon1 === undefined || lon2 === undefined) return null;
	const d = angularDist(lon1, lon2);
	for(let i = 0; i < ASPECTS.length; i++){
		if(Math.abs(d - ASPECTS[i].a) <= ASPECTS[i].orb) return ASPECTS[i];
	}
	return null;
}
function isHard(asp){ return asp && (asp.a === 90 || asp.a === 180); }
function isSoft(asp){ return asp && (asp.a === 60 || asp.a === 120); }

export function natalIntegration(natalFacts, elecFacts){
	const notes = [];
	if(!natalFacts || !elecFacts){ return { notes, available: false }; }
	const add = (pol, text) => notes.push({ pol, text });

	// 昼夜宗派强调
	if(natalFacts.meta.isDiurnal) add('info', '本命为昼盘：择日宜强调木星过运、避火星紧密过运。');
	else add('info', '本命为夜盘：择日宜强调金星过运、避土星紧密过运。');

	// 本命敏感点
	const targets = {
		命度: natalFacts.meta.ascLon,
		太阳: natalFacts.planets.sun ? natalFacts.planets.sun.lon : null,
		月亮: natalFacts.planets.moon ? natalFacts.planets.moon.lon : null,
		中天: natalFacts.meta.mcLon,
	};
	// 择日盘行星 → 本命敏感点 的过运相位
	['saturn', 'mars', 'jupiter', 'venus'].forEach((k) => {
		const ep = elecFacts.planets[k];
		if(!ep) return;
		Object.keys(targets).forEach((label) => {
			const asp = crossAspect(ep.lon, targets[label]);
			if(!asp) return;
			if((k === 'jupiter' || k === 'venus') && isSoft(asp)){
				add('positive', `择日 ${cn(k)} 过运吉相本命${label}（${asp.n}）→ 助力。`);
			}else if((k === 'saturn' || k === 'mars') && isHard(asp)){
				add('negative', `择日 ${cn(k)} 过运刑冲本命${label}（${asp.n}）→ 长期压力，宜避或缓。`);
			}
		});
	});

	// 本命月亮（夜）/太阳（昼）不应被择日盘刑剋
	const lightKey = natalFacts.meta.isDiurnal ? 'sun' : 'moon';
	const lightLon = natalFacts.planets[lightKey] ? natalFacts.planets[lightKey].lon : null;
	['mars', 'saturn'].forEach((k) => {
		const ep = elecFacts.planets[k];
		if(ep && isHard(crossAspect(ep.lon, lightLon))){
			add('negative', `择日 ${cn(k)} 刑冲本命${lightKey === 'sun' ? '太阳' : '月亮'}（昼夜光体）→ 务必留意。`);
		}
	});

	if(notes.filter((n) => n.pol !== 'info').length === 0){
		add('positive', '择日盘未见对本命敏感点的明显凶性过运，可接受。');
	}
	return { notes, available: true };
}

export default natalIntegration;
