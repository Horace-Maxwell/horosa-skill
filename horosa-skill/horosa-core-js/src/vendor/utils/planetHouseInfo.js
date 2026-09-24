
function parseHouseNum(houseId){
	if(houseId === undefined || houseId === null){
		return null;
	}
	const matched = `${houseId}`.match(/\d+/);
	if(!matched){
		return null;
	}
	const num = parseInt(matched[0], 10);
	if(Number.isNaN(num) || num <= 0){
		return null;
	}
	return num;
}

function uniqSorted(nums){
	const set = new Set();
	const out = [];
	for(let i=0; i<nums.length; i++){
		const n = nums[i];
		if(!Number.isFinite(n) || n <= 0){
			continue;
		}
		if(set.has(n)){
			continue;
		}
		set.add(n);
		out.push(n);
	}
	out.sort((a, b)=>a - b);
	return out;
}

function normalizeEnabled(enabled){
	if(enabled && typeof enabled === 'object'){
		return {
			showHouse: enabled.showHouse === 1 || enabled.showHouse === true,
			showRuler: enabled.showRuler === 1 || enabled.showRuler === true,
		};
	}
	const on = enabled === true || enabled === 1;
	return {
		showHouse: on,
		showRuler: on,
	};
}

function normalizeLabel(label){
	if(label === undefined || label === null){
		return '';
	}
	return `${label}`;
}

export function findChartObject(chartWrap, objId){
	if(!chartWrap || !objId){
		return null;
	}
	const chart = chartWrap.chart ? chartWrap.chart : chartWrap;
	const objects = chart && chart.objects ? chart.objects : [];
	for(let i=0; i<objects.length; i++){
		if(objects[i] && objects[i].id === objId){
			return objects[i];
		}
	}
	const lots = chartWrap && chartWrap.lots ? chartWrap.lots : (chart && chart.lots ? chart.lots : []);
	for(let j=0; j<lots.length; j++){
		if(lots[j] && lots[j].id === objId){
			return lots[j];
		}
	}
	return null;
}

export function getPlanetHouseInfo(obj){
	const houseNum = parseHouseNum(obj && obj.house);
	const rawRules = obj && obj.ruleHouses ? obj.ruleHouses : [];
	const ruleNums = uniqSorted(rawRules.map((id)=>parseHouseNum(id)));
	return {
		houseNum,
		ruleNums,
	};
}

export function formatPlanetHouseInfo(obj, enabled){
	const info = getPlanetHouseInfo(obj);
	const mode = normalizeEnabled(enabled);
	const parts = [];
	if(mode.showHouse){
		parts.push(info.houseNum ? `${info.houseNum}th` : '-');
	}
	if(mode.showRuler){
		parts.push(info.ruleNums.length ? info.ruleNums.map((n)=>`${n}R`).join('') : '-');
	}
	if(parts.length === 0){
		return '';
	}
	return parts.join('; ');
}

export function appendPlanetHouseInfo(label, obj, enabled){
	const mode = normalizeEnabled(enabled);
	const enabledAny = mode.showHouse || mode.showRuler;
	const normalizedLabel = normalizeLabel(label);
	if(!enabledAny){
		return normalizedLabel;
	}
	const infoText = formatPlanetHouseInfo(obj, mode);
	if(!infoText){
		return normalizedLabel;
	}
	return `${normalizedLabel} (${infoText})`;
}

export function appendPlanetHouseInfoById(label, chartWrap, objId, enabled){
	const obj = findChartObject(chartWrap, objId);
	if(!obj){
		return normalizeLabel(label);
	}
	return appendPlanetHouseInfo(label, obj, enabled);
}

export function isPlanetHouseInfoEnabled(enabled){
	const mode = normalizeEnabled(enabled);
	return mode.showHouse || mode.showRuler;
}

export function splitPlanetHouseInfoText(text){
	const raw = `${text || ''}`;
	const matched = raw.match(/^(.*?)(?:\s*\(([^()]*)\))$/);
	if(!matched){
		return {
			label: raw,
			info: '',
		};
	}
	return {
		label: `${matched[1] || ''}`.trim(),
		info: `${matched[2] || ''}`.trim(),
	};
}
