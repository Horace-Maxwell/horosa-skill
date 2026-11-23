// 用爻与五行旺衰
// 从 JinKouCalc.js 按职责拆出(门面保留原导入路径与对外导出;读源码的检查读「子模块 + 门面」全集,见 scripts/source-sets.json)。
import { JinKouWuXingKe, JinKouWuXingOrder, JinKouWuXingSheng } from './tables.js';

export function resolveYongYao(lineSigns){
	const lines = lineSigns instanceof Array ? lineSigns : [];
	let yangCount = 0;
	let yinCount = 0;
	let yangLine = null;
	let yinLine = null;
	for(let i=0; i<lines.length; i++){
		const one = lines[i];
		if(one.sign === '+'){
			yangCount += 1;
			yangLine = one;
		}else if(one.sign === '-'){
			yinCount += 1;
			yinLine = one;
		}
	}

	if(yangCount === 1 && yinCount === 3){
		return {
			label: yangLine ? yangLine.label : '',
			sign: '+',
			reason: '三阴一阳，以阳为用',
			theme: '男子',
		};
	}
	if(yangCount === 3 && yinCount === 1){
		return {
			label: yinLine ? yinLine.label : '',
			sign: '-',
			reason: '三阳一阴，以阴为用',
			theme: '女子',
		};
	}
	if(yangCount === 2 && yinCount === 2){
		const jiang = lines.find((item)=>item.label === '将神');
		return {
			label: jiang ? jiang.label : '将神',
			sign: jiang ? jiang.sign : '',
			reason: '二阴二阳，以将为用',
			theme: jiang && jiang.sign === '+' ? '男子' : '女子',
		};
	}
	if(yangCount === 0 && yinCount === 4){
		return {
			label: '人元',
			sign: '+',
			reason: '纯阴反阳，以阳为用',
			theme: '男子',
		};
	}
	if(yangCount === 4 && yinCount === 0){
		return {
			label: '贵神',
			sign: '-',
			reason: '纯阳反阴，以星为用',
			theme: '女子',
		};
	}
	const fallback = lines.find((item)=>item.label === '将神');
	return {
		label: fallback ? fallback.label : '',
		sign: fallback ? fallback.sign : '',
		reason: '按将神为用',
		theme: '',
	};
}

export function getSeason(liureng, elem){
	if(!liureng || !liureng.season || !elem){
		return '';
	}
	const map = liureng.season;
	if(map[elem]){
		return map[elem];
	}
	const keys = Object.keys(map);
	for(let i=0; i<keys.length; i++){
		const key = keys[i];
		if(key.indexOf(elem) >= 0){
			return map[key];
		}
	}
	return '';
}

export function buildPowerText(elem, sign, season){
	// 旺衰文本仅「五行+旺衰」(如 金相/土旺)；阴阳(+/-)另列单独显示，避免与旺衰连写「金-相」误解。
	let txt = elem ? elem : '—';
	if(season){
		txt += season;
	}
	return txt;
}

function normalizeElements(elements){
	const vals = elements instanceof Array ? elements : [];
	const out = [];
	for(let i=0; i<vals.length; i++){
		const elem = `${vals[i] || ''}`;
		if(JinKouWuXingKe[elem]){
			out.push(elem);
		}
	}
	return out;
}

function countElements(elements){
	const map = {};
	for(let i=0; i<elements.length; i++){
		const elem = elements[i];
		map[elem] = map[elem] ? map[elem] + 1 : 1;
	}
	return map;
}

function rankElements(keys, counts, scores){
	const ary = keys.slice(0);
	ary.sort((a, b)=>{
		const scoreA = scores && scores[a] !== undefined ? scores[a] : 0;
		const scoreB = scores && scores[b] !== undefined ? scores[b] : 0;
		if(scoreA !== scoreB){
			return scoreB - scoreA;
		}
		const cntA = counts && counts[a] !== undefined ? counts[a] : 0;
		const cntB = counts && counts[b] !== undefined ? counts[b] : 0;
		if(cntA !== cntB){
			return cntB - cntA;
		}
		return JinKouWuXingOrder.indexOf(a) - JinKouWuXingOrder.indexOf(b);
	});
	return ary;
}

export function calcJinKouWangElem(elements){
	const vals = normalizeElements(elements);
	if(vals.length === 0){
		return '';
	}
	const counts = countElements(vals);
	const keys = Object.keys(counts);
	if(keys.length === 1){
		return keys[0];
	}

	let maxCount = 0;
	for(let i=0; i<keys.length; i++){
		const cnt = counts[keys[i]];
		if(cnt > maxCount){
			maxCount = cnt;
		}
	}
	if(maxCount >= 3){
		return rankElements(keys, counts)[0];
	}

	if(keys.length === 4){
		let missing = '';
		for(let i=0; i<JinKouWuXingOrder.length; i++){
			const elem = JinKouWuXingOrder[i];
			if(!counts[elem]){
				missing = elem;
				break;
			}
		}
		if(missing && JinKouWuXingKe[missing]){
			return JinKouWuXingKe[missing];
		}
		return rankElements(keys, counts)[0];
	}

	if(keys.length === 2){
		const a = keys[0];
		const b = keys[1];
		if(counts[a] !== counts[b]){
			return counts[a] > counts[b] ? a : b;
		}
		if(JinKouWuXingKe[a] === b){
			return a;
		}
		if(JinKouWuXingKe[b] === a){
			return b;
		}
		if(JinKouWuXingSheng[a] === b){
			return b;
		}
		if(JinKouWuXingSheng[b] === a){
			return a;
		}
		return rankElements(keys, counts)[0];
	}

	let pairElem = '';
	const singles = [];
	for(let i=0; i<keys.length; i++){
		const elem = keys[i];
		if(counts[elem] >= 2){
			pairElem = elem;
		}else{
			singles.push(elem);
		}
	}
	if(pairElem){
		for(let i=0; i<keys.length; i++){
			const target = keys[i];
			if(target !== pairElem && JinKouWuXingKe[pairElem] === target){
				return pairElem;
			}
		}
		for(let i=0; i<singles.length; i++){
			if(JinKouWuXingKe[singles[i]] === pairElem){
				return singles[i];
			}
		}
		for(let i=0; i<singles.length; i++){
			for(let j=0; j<singles.length; j++){
				if(i !== j && JinKouWuXingKe[singles[i]] === singles[j]){
					return singles[i];
				}
			}
		}
	}

	const score = {};
	for(let i=0; i<keys.length; i++){
		const one = keys[i];
		score[one] = 0;
		for(let j=0; j<keys.length; j++){
			const target = keys[j];
			if(one !== target && JinKouWuXingKe[one] === target){
				score[one] += counts[target];
			}
		}
	}
	return rankElements(keys, counts, score)[0];
}

export function buildJinKouWangShuaiMap(wangElem){
	const map = {};
	if(!wangElem || !JinKouWuXingKe[wangElem]){
		return map;
	}
	map[wangElem] = '旺';
	map[JinKouWuXingSheng[wangElem]] = '相';
	map[JinKouWuXingKe[wangElem]] = '死';
	const keys = Object.keys(JinKouWuXingSheng);
	for(let i=0; i<keys.length; i++){
		const elem = keys[i];
		if(JinKouWuXingSheng[elem] === wangElem){
			map[elem] = '休';
			break;
		}
	}
	const ctrlKeys = Object.keys(JinKouWuXingKe);
	for(let i=0; i<ctrlKeys.length; i++){
		const elem = ctrlKeys[i];
		if(JinKouWuXingKe[elem] === wangElem){
			map[elem] = '囚';
			break;
		}
	}
	return map;
}
