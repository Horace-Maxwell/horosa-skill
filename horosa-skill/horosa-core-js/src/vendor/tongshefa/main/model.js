// 通摄法卦模型:取卦 / 互卦 / 错卦 / 爻信息 / 主关系 / 大格局 / 升降 / 爻变(纯函数,无界面)
// 从 TongSheFaMain.js 按职责拆出(门面保留原导入路径与对外导出;读源码的检查读「子模块 + 门面」全集,见 scripts/source-sets.json)。
import { littleEndian } from '../../gua/littleEndian.js';
import { getGua64, Gua64 } from '../../gua/GuaConst.js';
import { DEFAULT_SELECTION, BAGUA_MAP, BAGUA_LIST, ZHI_ELEM_MAP, SHENG_MAP, KE_MAP, KIN_TO_REL, HOUSE_CHANGE_CN, LIUCHUAN_SET, LIUHE_SET, MAIN_RELATION_LABEL } from './data.js';

function arrEq(a, b){
	if(!(a instanceof Array) || !(b instanceof Array) || a.length !== b.length){
		return false;
	}
	for(let i=0; i<a.length; i++){
		if(a[i] !== b[i]){
			return false;
		}
	}
	return true;
}

export function safeText(txt, def = '—'){
	const v = `${txt === undefined || txt === null ? '' : txt}`.trim();
	return v === '' ? def : v;
}

export function normalizeSelection(raw){
	const base = { ...DEFAULT_SELECTION };
	if(!raw || typeof raw !== 'object'){
		return base;
	}
	Object.keys(base).forEach((key)=>{
		const val = raw[key];
		if(val && BAGUA_MAP.has(val)){
			base[key] = val;
		}
	});
	return base;
}

export function getBagua(key){
	if(key && BAGUA_MAP.has(key)){
		return BAGUA_MAP.get(key);
	}
	return BAGUA_MAP.get(DEFAULT_SELECTION.taiyin);
}

function getBaguaByLines(lines){
	for(let i=0; i<BAGUA_LIST.length; i++){
		const item = BAGUA_LIST[i];
		if(arrEq(item.value, lines)){
			return item;
		}
	}
	return null;
}

export function shortGuaName(name){
	const txt = `${name || ''}`.trim();
	for(let i=0; i<BAGUA_LIST.length; i++){
		const item = BAGUA_LIST[i];
		if(txt === `${item.name}为${item.cname}`){
			return item.name;
		}
	}
	if(txt.length <= 2){
		return txt || '—';
	}
	return txt.substring(2);
}

function linePattern(val){
	return val === 1 ? '—' : '--';
}

export function linePolarity(val){
	return val === 1 ? '阳' : '阴';
}

export function lineAdmit(val){
	return val === 1 ? '否' : '认';
}

export function lineVerb(val){
	return val === 1 ? '蔑视' : '看重';
}

function buildHexByLines(lines, upperHint, lowerHint){
	const bits = lines.slice(0);
	const key = littleEndian(bits);
	const gua = getGua64(key);
	const lowerLines = bits.slice(0, 3);
	const upperLines = bits.slice(3, 6);
	const lower = lowerHint || getBaguaByLines(lowerLines) || BAGUA_LIST[0];
	const upper = upperHint || getBaguaByLines(upperLines) || BAGUA_LIST[0];
	return {
		key,
		lines: bits,
		gua,
		upper,
		lower,
	};
}

function buildHex(upper, lower){
	return buildHexByLines([
		lower.value[0], lower.value[1], lower.value[2],
		upper.value[0], upper.value[1], upper.value[2],
	], upper, lower);
}

function buildMutualHex(hex){
	const bits = hex.lines;
	return buildHexByLines([
		bits[1], bits[2], bits[3],
		bits[2], bits[3], bits[4],
	]);
}

function buildOppositeHex(hex){
	const bits = hex.lines.map((item)=>item === 1 ? 0 : 1);
	return buildHexByLines(bits);
}

function parseYaoName(raw){
	const text = `${raw || ''}`;
	const branch = text.substring(0, 1);
	const elem = text.substring(1, 2) || ZHI_ELEM_MAP[branch] || '';
	let tail = text.substring(2);
	let shiYing = '';
	if(tail.endsWith('世') || tail.endsWith('应')){
		shiYing = tail.substring(tail.length - 1);
		tail = tail.substring(0, tail.length - 1);
	}
	let kin = '';
	if(tail.indexOf('兄弟') >= 0){
		kin = '兄弟';
	}else if(tail.indexOf('父母') >= 0){
		kin = '父母';
	}else if(tail.indexOf('官鬼') >= 0){
		kin = '官鬼';
	}else if(tail.indexOf('子孙') >= 0){
		kin = '子孙';
	}else if(tail.indexOf('妻财') >= 0){
		kin = '妻财';
	}else if(tail.indexOf('妻才') >= 0){
		kin = '妻才';
	}
	return {
		branch,
		elem,
		kin,
		shiYing,
	};
}

export function relationByElem(mainElem, otherElem){
	const main = `${mainElem || ''}`;
	const other = `${otherElem || ''}`;
	if(main === '' || other === ''){
		return '';
	}
	if(main === other){
		return '同';
	}
	if(SHENG_MAP[other] === main){
		return '义';
	}
	if(KE_MAP[other] === main){
		return '鬼';
	}
	if(SHENG_MAP[main] === other){
		return '爱';
	}
	if(KE_MAP[main] === other){
		return '制';
	}
	return '';
}

function buildLineInfos(hex){
	const elem = hex && hex.gua && hex.gua.house ? hex.gua.house.elem : '';
	const infos = [];
	for(let i=0; i<6; i++){
		const bits = hex.lines[i];
		const raw = hex && hex.gua && hex.gua.yaoname ? hex.gua.yaoname[i] : '';
		const parsed = parseYaoName(raw);
		const lineElem = parsed.elem || ZHI_ELEM_MAP[parsed.branch] || '';
		const ownRel = parsed.kin ? (KIN_TO_REL[parsed.kin] || '') : relationByElem(elem, lineElem);
		infos.push({
			line: i + 1,
			value: bits,
			pattern: linePattern(bits),
			branch: parsed.branch || '',
			elem: lineElem,
			kin: parsed.kin,
			ownRel,
			shiYing: parsed.shiYing || '',
		});
	}
	return infos;
}

function getHexElem(hex){
	if(hex && hex.gua && hex.gua.house && hex.gua.house.elem){
		return hex.gua.house.elem;
	}
	return hex && hex.upper ? hex.upper.elem : '';
}

function getHouseChangeLabel(hex){
	if(!(hex && hex.gua && hex.gua.house && hex.gua.house.name)){
		return '—';
	}
	const houseName = hex.gua.house.name;
	let order = 0;
	for(let i=0; i<Gua64.length; i++){
		const item = Gua64[i];
		if(!(item && item.house && item.house.name === houseName)){
			continue;
		}
		if(item.name === hex.gua.name && arrEq(item.value, hex.gua.value)){
			return `${houseName}${HOUSE_CHANGE_CN[order] || order}`;
		}
		order++;
	}
	return `${houseName}—`;
}

function getMainRelationCode(leftElem, rightElem){
	if(leftElem === '' || rightElem === ''){
		return '思同实';
	}
	if(leftElem === rightElem){
		return '思同实';
	}
	if(SHENG_MAP[leftElem] === rightElem){
		return '思生实';
	}
	if(KE_MAP[leftElem] === rightElem){
		return '思克实';
	}
	if(SHENG_MAP[rightElem] === leftElem){
		return '实生思';
	}
	if(KE_MAP[rightElem] === leftElem){
		return '实克思';
	}
	return '思同实';
}

function analyzeBigPattern(lines){
	const pairs = [
		{ from: 1, to: 4 },
		{ from: 2, to: 5 },
		{ from: 3, to: 6 },
	];
	const details = pairs.map((item)=>{
		const a = lines[item.from - 1] ? lines[item.from - 1].branch : '';
		const b = lines[item.to - 1] ? lines[item.to - 1].branch : '';
		const key = `${a}${b}`;
		let status = '无';
		if(LIUCHUAN_SET.has(key)){
			status = '穿';
		}else if(LIUHE_SET.has(key)){
			status = '合';
		}
		return {
			...item,
			branchPair: `${a}${b}`,
			status,
		};
	});
	const allChuan = details.every((item)=>item.status === '穿');
	const allHe = details.every((item)=>item.status === '合');
	return {
		type: allChuan ? '六穿' : (allHe ? '六合' : '无'),
		details,
	};
}

function analyzeRise(lines){
	const attacks = [];
	for(let i=0; i<6; i++){
		if(lines[i] !== 1 || i === 5){
			continue;
		}
		let j = i + 1;
		while(j < 6 && lines[j] !== 1){
			j++;
		}
		const end = j < 6 ? j - 1 : 5;
		if(end < i + 1){
			continue;
		}
		const targets = [];
		for(let k=i + 1; k<=end; k++){
			targets.push(k + 1);
		}
		attacks.push({
			from: i + 1,
			targets,
		});
	}
	return attacks;
}

function analyzeYaoChanges(leftLines, rightLines){
	const list = [];
	for(let i=5; i>=0; i--){
		const lineNum = i + 1;
		list.push({
			line: lineNum,
			changed: leftLines[i] !== rightLines[i],
		});
	}
	return list;
}

function uniqBagua(list){
	const seen = new Set();
	const out = [];
	list.forEach((item)=>{
		if(!item || seen.has(item.key)){
			return;
		}
		seen.add(item.key);
		out.push(item);
	});
	return out;
}

export function buildTongSheFaModel(selection){
	const selected = normalizeSelection(selection);
	const taiyin = getBagua(selected.taiyin);
	const taiyang = getBagua(selected.taiyang);
	const shaoyang = getBagua(selected.shaoyang);
	const shaoyin = getBagua(selected.shaoyin);

	const baseLeft = buildHex(taiyin, shaoyang);
	const baseRight = buildHex(taiyang, shaoyin);
	const mutualLeft = buildMutualHex(baseLeft);
	const mutualRight = buildMutualHex(baseRight);
	const oppositeLeft = buildOppositeHex(baseLeft);
	const oppositeRight = buildOppositeHex(baseRight);

	const leftElem = getHexElem(baseLeft);
	const rightElem = getHexElem(baseRight);
	const leftLines = buildLineInfos(baseLeft);
	const rightLines = buildLineInfos(baseRight);

	const mainRelation = getMainRelationCode(leftElem, rightElem);

	return {
		selected,
		taiyin,
		taiyang,
		shaoyang,
		shaoyin,
		baseLeft,
		baseRight,
		mutualLeft,
		mutualRight,
		oppositeLeft,
		oppositeRight,
		leftElem,
		rightElem,
		leftLines,
		rightLines,
		leftHouseLabel: getHouseChangeLabel(baseLeft),
		rightHouseLabel: getHouseChangeLabel(baseRight),
		mainRelation,
		mainRelationLabel: MAIN_RELATION_LABEL[mainRelation] || '',
		leftBigPattern: analyzeBigPattern(leftLines),
		rightBigPattern: analyzeBigPattern(rightLines),
		leftRise: analyzeRise(baseLeft.lines),
		rightRise: analyzeRise(baseRight.lines),
		yaoChanges: analyzeYaoChanges(baseLeft.lines, baseRight.lines),
		baguaPicked: uniqBagua([taiyin, taiyang, shaoyang, shaoyin]),
	};
}
