// utils/dispositorChain.js
// 主宰星链（dispositor chains）：七政各落星座的本垣主，顺链至「落自家星座」的终极主宰，或互容成环。
// 纯函数、无 React，供 AstroDispositor（古典 tab）与 astroPatternOverview（格局速览/格局 tab）复用，避免重复实现。
import { SIGNS, SIGN_ORDER } from '../divination/data/signs.js';
import { chartIdOfKey, keyOfChartId } from '../divination/engine/utils.js';

function norm360(x){ return ((x % 360) + 360) % 360; }
function signOf(lon){ return SIGN_ORDER[Math.floor(norm360(lon) / 30)]; }
function houseNum(id){ const m = /House\s*(\d+)/.exec(String(id || '')); return m ? parseInt(m[1], 10) : null; }
const TRAD = ['sun', 'moon', 'mercury', 'venus', 'mars', 'jupiter', 'saturn'];

// 入参 objects = chartObj.chart.objects；返回 { pos, step, chains, finals(Set), loops(去重数组), traditional }。
// pos: key->{sign,house}；step: key->其落座庙主 key；chains: key->链路数组；finals: 终极主宰 key 集；loops: 互容环（key 数组的数组）。
export function computeDispositors(objects){
	const pos = {};
	(objects || []).forEach((o) => {
		if(!o || !o.id) return;
		const k = keyOfChartId(o.id);
		const sign = o.sign ? String(o.sign).toLowerCase() : (o.lon != null ? signOf(o.lon) : null);
		pos[k] = { sign, house: houseNum(o.house) };
	});
	const step = {};
	TRAD.forEach((k) => { const p = pos[k]; if(p && p.sign) step[k] = (SIGNS[p.sign] || {}).domicile || null; });
	const chains = {}; const finals = new Set(); const loops = [];
	TRAD.forEach((start) => {
		if(step[start] === undefined) return;
		const path = []; const seen = new Set(); let cur = start;
		while(cur && step[cur] !== undefined){
			if(seen.has(cur)){ loops.push(path.slice(path.indexOf(cur))); path.push(cur); break; }
			seen.add(cur); path.push(cur);
			const nxt = step[cur];
			if(nxt === cur){ finals.add(cur); break; }
			cur = nxt;
		}
		chains[start] = path;
	});
	const seenLoop = new Set(); const uniqLoops = [];
	loops.forEach((c) => { const key = [...c].sort().join('>'); if(!seenLoop.has(key)){ seenLoop.add(key); uniqLoops.push(c); } });
	return { pos, step, chains, finals, loops: uniqLoops, traditional: TRAD };
}

export { TRAD, signOf, houseNum, chartIdOfKey, keyOfChartId };
