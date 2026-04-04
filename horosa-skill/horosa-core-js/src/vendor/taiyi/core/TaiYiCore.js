export const TAIYI_STYLE_OPTIONS = [
	{ value: 3, label: '時計太乙' },
	{ value: 0, label: '年計太乙' },
	{ value: 1, label: '月計太乙' },
	{ value: 2, label: '日計太乙' },
	{ value: 4, label: '分計太乙' },
];

export const TAIYI_ACCUM_OPTIONS = [
	{ value: 0, label: '太乙統宗' },
	{ value: 1, label: '太乙金鏡' },
	{ value: 2, label: '太乙淘金歌' },
	{ value: 3, label: '太乙局' },
];

const DI_ZHI = '子丑寅卯辰巳午未申酉戌亥'.split('');
const GONG16_ORDER = '子丑艮寅卯辰巽巳午未坤申酉戌乾亥'.split('');
const GONG16_NUM = [8, 8, 3, 3, 4, 4, 9, 9, 2, 2, 7, 7, 6, 6, 1, 1];
const NUM_RING = [8, 3, 4, 9, 2, 7, 6, 1];
const JC = '丑寅辰巳未申戌亥'.split('');
const JC1 = '巽艮坤乾'.split('');
const TYJC = [1, 3, 7, 9];
const JIEQI_ORDER = ['小寒', '大寒', '立春', '雨水', '惊蛰', '春分', '清明', '谷雨', '立夏', '小满', '芒种', '夏至', '小暑', '大暑', '立秋', '处暑', '白露', '秋分', '寒露', '霜降', '立冬', '小雪', '大雪', '冬至'];

const TAIYI_PAI = '乾乾乾午午午艮艮艮卯卯卯酉酉酉坤坤坤子子子巽巽巽乾乾乾午午午艮艮艮卯卯卯酉酉酉坤坤坤子子子巽巽巽乾乾乾午午午艮艮艮卯卯卯酉酉酉坤坤坤子子子巽巽巽'.split('');
const SF_LIST = '坤戌亥丑寅辰巳坤酉乾丑寅辰午坤酉亥子艮辰巳未申戌亥艮卯巽未丑戌子艮卯巳午坤戌亥丑寅辰巳坤酉乾丑寅辰午坤酉亥子艮辰巳未申戌亥艮卯巽未丑戌子艮卯巳午'.split('');
const SKYEYES_YANG = '申酉戌乾乾亥子丑艮寅卯辰巽巳午未坤坤申酉戌乾乾亥子丑艮寅卯辰巽巳午未坤坤申酉戌乾乾亥子丑艮寅卯辰巽巳午未坤坤申酉戌乾乾亥子丑艮寅卯辰巽巳午未坤坤'.split('');
const SKYEYES_YIN = '寅卯辰巽巽巳午未坤申酉戌乾亥子丑艮艮寅卯辰巽巽巳午未坤申酉戌乾亥子丑艮艮寅卯辰巽巽巳午未坤申酉戌乾亥子丑艮艮寅卯辰巽巽巳午未坤申酉戌乾亥子丑艮艮'.split('');
const FOUR_GOD = '乾乾乾午午午艮艮艮卯卯卯中中中酉酉酉坤坤坤子子子巽巽巽巳巳巳申申申寅寅寅'.split('');
const SKY_YI = '酉酉酉坤坤坤子子子巽巽巽巳巳巳申申申寅寅寅乾乾乾午午午艮艮艮卯卯卯中中中'.split('');
const EARTH_YI = '巽巽巽巳巳巳申申申寅寅寅乾乾乾午午午艮艮艮卯卯卯中中中酉酉酉坤坤坤子子子'.split('');
const ZHI_FU = '中中中酉酉酉坤坤坤子子子巽巽巽巳巳巳申申申寅寅寅乾乾乾午午午艮艮艮卯卯卯'.split('');
const OFFICER_BASE = '巳巳午午午未未未申申申酉酉酉戌戌戌亥亥亥子子子丑丑丑寅寅寅卯卯卯辰辰辰巳'.split('');

const YANG_CAL = [[7,13,13],[6,1,1],[1,40,32],[25,17,10],[25,14,1],[25,10,12],[8,25,9],[1,22,3],[3,15,33],[1,12,25],[4,4,13],[37,1,4],[18,19,19],[10,9,9],[9,7,6],[1,33,26],[7,27,16],[7,26,11],[8,32,14],[7,26,2],[2,17,33],[16,30,1],[16,23,32],[16,17,23],[39,40,40],[32,31,31],[31,28,31],[14,9,38],[13,39,26],[10,32,17],[33,10,34],[25,8,24],[24,3,15],[26,4,11],[25,28,1],[25,27,36],[1,7,7],[6,35,35],[35,34,26],[27,19,12],[27,16,3],[27,12,34],[8,17,1],[23,14,32],[32,7,25],[5,16,29],[4,8,17],[1,5,8],[24,25,25],[16,15,15],[15,13,6],[39,31,24],[38,25,14],[38,24,9],[16,3,22],[15,34,10],[10,25,10],[12,26,27],[12,19,28],[12,13,19],[33,34,34],[26,25,25],[25,22,18],[16,11,7],[15,1,28],[12,34,19],[25,2,26],[17,8,16],[16,32,7],[30,4,15],[29,32,5],[29,31,9]];
const YIN_CAL = [[5,29,7],[4,17,1],[1,16,30],[25,33,2],[25,30,1],[17,26,10],[2,3,3],[1,7,7],[7,33,27],[1,24,25],[6,26,19],[35,23,8],[12,37,12],[12,27,11],[11,25,4],[1,15,24],[3,9,16],[3,8,9],[14,16,16],[13,10,10],[10,1,39],[24,14,1],[24,7,40],[16,1,29],[31,16,32],[30,7,29],[29,4,26],[8,25,32],[7,15,26],[2,8,15],[27,28,28],[27,26,26],[26,18,15],[29,22,9],[25,10,1],[25,9,34],[1,25,3],[4,13,37],[37,12,26],[33,1,10],[33,38,9],[25,34,38],[2,1,1],[39,38,38],[38,31,25],[7,1,31],[6,32,25],[1,29,14],[16,1,17],[16,31,15],[15,29,4],[33,7,16],[32,1,8],[32,8,1],[16,18,18],[15,12,12],[12,3,1],[18,8,35],[18,1,34],[10,35,25],[27,22,28],[26,3,25],[25,4,12],[16,33,3],[15,23,34],[10,16,23],[25,26,26],[25,24,24],[24,16,13],[32,28,15],[31,16,7],[31,15,1]];

const BRANCH_ALIAS = { 巽: '辰', 坤: '申', 艮: '丑', 乾: '亥' };

function normalizeNum(v, def = 0){
	const n = parseInt(v, 10);
	return Number.isNaN(n) ? def : n;
}

function mod(v, m){
	const n = v % m;
	return n < 0 ? n + m : n;
}

function rotateFrom(arr, startVal){
	const idx = arr.indexOf(startVal);
	if(idx < 0){
		return arr.slice(0);
	}
	return arr.slice(idx).concat(arr.slice(0, idx));
}

function toCnNum(num){
	const d = ['零', '一', '二', '三', '四', '五', '六', '七', '八', '九'];
	if(num < 10){
		return d[num];
	}
	if(num < 20){
		return `十${d[num % 10] === '零' ? '' : d[num % 10]}`;
	}
	const ten = Math.floor(num / 10);
	const one = num % 10;
	return `${d[ten]}十${one === 0 ? '' : d[one]}`;
}

function safeFirstChar(gz){
	const text = `${gz || ''}`.trim();
	return text ? text.substring(0, 1) : '';
}

function safeSecondChar(gz){
	const text = `${gz || ''}`.trim();
	if(!text){
		return '';
	}
	return text.length >= 2 ? text.substring(1, 2) : text.substring(0, 1);
}

function parseDateTime(fields){
	if(!fields || !fields.date || !fields.time){
		return null;
	}
	const dateStr = fields.date.value.format('YYYY-MM-DD');
	const timeStr = fields.time.value.format('HH:mm:ss');
	const d = dateStr.split('-');
	const t = timeStr.split(':');
	if(d.length < 3 || t.length < 2){
		return null;
	}
	return {
		year: normalizeNum(d[0], 0),
		month: normalizeNum(d[1], 1),
		day: normalizeNum(d[2], 1),
		hour: normalizeNum(t[0], 0),
		minute: normalizeNum(t[1], 0),
		second: normalizeNum(t[2], 0),
		dateStr,
		timeStr,
	};
}

function extractCurrentJieqi(nongli){
	if(!nongli){
		return '';
	}
	const delta = `${nongli.jiedelta || ''}`;
	const idx = delta.indexOf('后第');
	if(idx > 0){
		return delta.substring(0, idx);
	}
	return `${nongli.jieqi || ''}`;
}

function guessLunarYear(dateParts, nongli){
	if(!dateParts){
		return 0;
	}
	let year = dateParts.year;
	if(nongli && typeof nongli.monthInt === 'number' && dateParts.month <= 2 && nongli.monthInt >= 11){
		year -= 1;
	}
	return year;
}

function dayDiffUTC(dateParts, baseYear, baseMonth, baseDay){
	const dateUTC = Date.UTC(dateParts.year, dateParts.month - 1, dateParts.day, dateParts.hour, dateParts.minute, 0);
	const baseUTC = Date.UTC(baseYear, baseMonth - 1, baseDay, 0, 0, 0);
	return Math.floor((dateUTC - baseUTC) / (24 * 3600 * 1000));
}

function buildGanZhi(nongli){
	return {
		year: nongli ? (nongli.yearJieqi || nongli.year || '') : '',
		month: nongli ? (nongli.monthGanZi || '') : '',
		day: nongli ? (nongli.dayGanZi || '') : '',
		time: nongli ? (nongli.time || '') : '',
		minute: nongli ? (nongli.minute || '') : '',
	};
}

function divideFactor(num, division){
	if(!Number.isInteger(num) || num <= 0){
		return 0;
	}
	let n = num;
	while(n % division === 0){
		n = Math.floor(n / division);
	}
	return n;
}

function getAccNum(style, tn, dateParts, nongli){
	const lunarYear = guessLunarYear(dateParts, nongli);
	const lunarMonth = nongli && nongli.monthInt ? normalizeNum(nongli.monthInt, dateParts.month) : dateParts.month;
	const lunarDay = nongli && nongli.dayInt ? normalizeNum(nongli.dayInt, dateParts.day) : dateParts.day;
	const tndict = { 0: 10153917, 1: 1936557, 2: 10154193, 3: 10153917 };
	const tnc = tndict[tn] !== undefined ? tndict[tn] : tndict[0];
	if(style === 0){
		return tnc + lunarYear + (lunarYear < 0 ? 1 : 0);
	}
	if(style === 1){
		const accyear = tnc + lunarYear - 1 + (lunarYear < 0 ? 2 : 0);
		return accyear * 12 + 2 + lunarMonth;
	}
	if(style === 2){
		const diff = dayDiffUTC(dateParts, 1900, 6, 19);
		const configNum = 708011105 - ({ 0: 0, 1: 185, 2: 10153917, 3: 0 }[tn] || 0);
		if(tn === 3){
			return Math.round(((lunarYear - 423) * (235 / 19) * 29.5306) + lunarDay);
		}
		return configNum + diff;
	}
	if(style === 3){
		const diff = dayDiffUTC(dateParts, 1900, 12, 21);
		const configNum = 708011105 - ({ 0: 0, 1: 10153917, 2: 10153917, 3: 0 }[tn] || 0);
		const accday = configNum + diff;
		return ((accday - 1) * 12) + Math.floor((dateParts.hour + 1) / 2) + (tn !== 1 ? 1 : -11);
	}
	if(style === 4){
		const diff = dayDiffUTC(dateParts, 1900, 12, 21);
		const configNum = 708011105 - ({ 0: 0, 1: 10153917, 2: 10153917, 3: 0 }[tn] || 0);
		const accday = configNum + diff;
		return ((accday - 1) * 23) + (dateParts.hour * 10500) + (dateParts.minute + 1);
	}
	return lunarDay;
}

function normalizeJieqiName(jieqi){
	const map = { 驚蟄: '惊蛰', 穀雨: '谷雨', 處暑: '处暑' };
	return map[jieqi] || jieqi;
}

function getYinYang(style, jieqi, dayGan, timeZhi){
	if(style === 0 || style === 1 || style === 2 || style === 5){
		return '阳';
	}
	const jq = normalizeJieqiName(`${jieqi || ''}`);
	const winterPart = rotateFrom(JIEQI_ORDER, '冬至').slice(0, 12);
	const summerPart = rotateFrom(JIEQI_ORDER, '夏至').slice(0, 12);
	let season = '冬至';
	if(summerPart.indexOf(jq) >= 0){
		season = '夏至';
	}else if(winterPart.indexOf(jq) >= 0){
		season = '冬至';
	}
	if(style === 3){
		return season === '夏至' ? '阴' : '阳';
	}
	const dayIsYang = '甲丙戊庚壬'.indexOf(dayGan) >= 0;
	const inA = '申酉戌亥子丑'.indexOf(timeZhi) >= 0;
	if(season === '冬至'){
		if(dayIsYang){
			return inA ? '阳' : '阴';
		}
		return inA ? '阴' : '阳';
	}
	if(dayIsYang){
		return inA ? '阴' : '阳';
	}
	return inA ? '阳' : '阴';
}

function getKook(accNum, yinYang){
	const num = mod(accNum, 72) || 72;
	return {
		num,
		yinYang,
		text: `${yinYang === '阳' ? '阳遁' : '阴遁'}${toCnNum(num)}局`,
		year: ['理天', '理地', '理人'][(num - 1) % 3],
	};
}

function getTaiyiNum(yinYang, kookNum){
	const base = [];
	for(let i=0; i<10; i++){
		for(let j=0; j<3; j++){
			base.push(i);
		}
	}
	if(yinYang === '阳'){
		const one = base.slice(3, 15).concat(base.slice(18));
		return one.concat(one).concat(one)[kookNum - 1] || 0;
	}
	const rev = base.slice(0).reverse();
	const one = rev.slice(0, 12).concat(rev.slice(15, rev.length - 3));
	return one.concat(one).concat(one)[kookNum - 1] || 0;
}

function getTaiSui(style, gz){
	const map = { 0: gz.year, 1: gz.month, 2: gz.day, 3: gz.time, 4: gz.minute || gz.time, 5: gz.year };
	return safeSecondChar(map[style] || gz.year);
}

function getHeGod(taishui){
	return rotateFrom(DI_ZHI.slice(0).reverse(), '丑')[DI_ZHI.indexOf(taishui)] || '';
}

function getJiGod(yinYang, taishui){
	if(yinYang === '阳'){
		return rotateFrom(DI_ZHI.slice(0).reverse(), '寅')[DI_ZHI.indexOf(taishui)] || '';
	}
	return rotateFrom(DI_ZHI, '酉')[DI_ZHI.slice(0).reverse().indexOf(taishui)] || '';
}

function getWcNum(palace){
	return GONG16_NUM[rotateFrom(GONG16_ORDER, '亥').indexOf(palace)] || 0;
}

function sumToIndex(arr, val){
	const idx = arr.indexOf(val);
	if(idx < 0){
		return val;
	}
	let sum = 0;
	for(let i=0; i<idx; i++){
		sum += arr[i];
	}
	return sum;
}

function getSe(skyeyes, hegod, taishui){
	if(!skyeyes || !hegod || !taishui){
		return '';
	}
	const start = rotateFrom(GONG16_ORDER, hegod);
	const idx = start.indexOf(taishui);
	if(idx < 0){
		return '';
	}
	return rotateFrom(GONG16_ORDER, skyeyes)[idx] || '';
}

function calcHomeCal(skyeyes, taiyiNum){
	const wcNum = getWcNum(skyeyes);
	if(!wcNum){
		return taiyiNum;
	}
	return sumToIndex(rotateFrom(NUM_RING, wcNum), taiyiNum);
}

function calcAwayCal(sf, taiyiNum){
	const sfNum = getWcNum(sf);
	if(!sfNum){
		return taiyiNum;
	}
	const sfJc = JC.indexOf(sf) >= 0;
	const tyJc = TYJC.indexOf(taiyiNum) >= 0;
	const sfJc1 = JC1.indexOf(sf) >= 0;
	const order = rotateFrom(NUM_RING, sfNum);
	const key = `${sfJc ? 1 : 0}${tyJc ? 1 : 0}${sfJc1 ? 1 : 0}`;
	if(key === '100'){
		return order.slice(0, JC.indexOf(sf) + 1).reduce((s, n)=>s + n, 0) + 1;
	}
	if(key === '001'){
		if(taiyiNum === 6){
			return order.slice(taiyiNum - 2).reduce((s, n)=>s + n, 0);
		}
		if(taiyiNum < 5){
			return order.slice(0, taiyiNum + 1).reduce((s, n)=>s + n, 0);
		}
		return sumToIndex(order, taiyiNum);
	}
	if(key === '010'){
		const idx = order.indexOf(TYJC[0]);
		return idx > 0 ? order.slice(0, idx).reduce((s, n)=>s + n, 0) : 0;
	}
	if(key === '110'){
		return sumToIndex(order, taiyiNum) + 1;
	}
	if(key === '011'){
		return sumToIndex(order, taiyiNum);
	}
	if(key === '000'){
		return sfNum === taiyiNum ? taiyiNum : sumToIndex(order, taiyiNum);
	}
	return taiyiNum;
}

function calcSetCal(se, taiyiNum){
	const seNum = getWcNum(se);
	if(!seNum){
		return taiyiNum;
	}
	const seJc = JC.indexOf(se) >= 0;
	const tyJc = TYJC.indexOf(taiyiNum) >= 0;
	const seJc1 = JC1.indexOf(se) >= 0;
	const key = `${seJc ? 1 : 0}${tyJc ? 1 : 0}${seJc1 ? 1 : 0}`;
	const base = sumToIndex(rotateFrom(NUM_RING, seNum), taiyiNum);
	if(key === '100'){
		return base === 0 ? 1 : base + 1;
	}
	if(key === '110'){
		return base + 1;
	}
	if(key === '000'){
		return seNum === taiyiNum ? taiyiNum : base;
	}
	return base;
}

function findCal(yinYang, kookNum){
	return (yinYang === '阳' ? YANG_CAL : YIN_CAL)[kookNum - 1] || [0, 0, 0];
}

function num2gong(num){
	return { 1: '乾', 2: '午', 3: '艮', 4: '卯', 5: '中', 6: '酉', 7: '坤', 8: '子', 9: '巽' }[num] || '';
}

function getHomeGeneral(yinYang, kookNum){
	const c = findCal(yinYang, kookNum)[0] || 0;
	if(c < 10){ return c; }
	if(c % 10 === 0){ return 1; }
	if(c < 20){ return c - 10; }
	if(c < 30){ return c - 20; }
	if(c < 40){ return c - 30; }
	return 1;
}

function getAwayGeneral(yinYang, kookNum){
	const c = findCal(yinYang, kookNum)[1] || 0;
	if(c === 1){ return 1; }
	if(c < 10){ return c; }
	if(c % 10 === 0){ return 5; }
	if(c < 20){ return c - 10; }
	if(c < 30){ return c - 20; }
	if(c < 40){ return c - 30; }
	return 5;
}

function getSetGeneral(setCal){
	const v = mod(setCal, 10);
	return v === 0 ? 5 : v;
}

function getVGen(general){
	const v = mod(general * 3, 10);
	return v === 0 ? 5 : v;
}

function getCycleValue(arr, count){
	if(!arr || arr.length === 0){
		return '';
	}
	return arr[mod(count - 1, arr.length)] || '';
}

function getKingBase(accNum){
	let idx = Math.floor(mod(accNum + 250, 360) / 30);
	if(idx === 0){
		idx = 1;
	}
	return rotateFrom(DI_ZHI, '午')[idx - 1] || '';
}

function getFlyFu(accNum){
	return rotateFrom(DI_ZHI, '辰')[Math.floor((mod(accNum, 360) % 36) / 3) - 1] || '中';
}

function getWufu(accNum){
	const fv = mod((mod(accNum + 250, 225) % 45), 5);
	return fv === 0 ? 5 : fv;
}

function getKingFu(accNum){
	let v = mod(accNum, 20);
	if(v === 0){
		v = mod(divideFactor(accNum, 20), 20);
	}
	if(v > 16){
		v -= 16;
	}
	return rotateFrom(GONG16_ORDER, '戌')[v - 1] || '';
}

function getTaiJun(accNum){
	let v = mod(accNum, 4);
	if(v === 0){
		v = mod(divideFactor(accNum, 4), 4);
		return GONG16_ORDER[v - 1] || '';
	}
	return { 1: '子', 2: '午', 3: '卯', 4: '酉' }[v] || '';
}

function getFlyBird(accNum){
	const v = mod(accNum, 8);
	if(v === 0){
		return '坤';
	}
	return num2gong({ 1: 1, 2: 8, 3: 3, 4: 4, 5: 9, 6: 2, 7: 7, 8: 6 }[v]);
}

function getThreeWind(accNum){
	const v = mod(accNum, 9);
	if(v === 0){
		return mod(divideFactor(accNum, 9), 9) || 9;
	}
	return [7, 2, 6, 1, 3, 9, 4, 8][v - 1] || 1;
}

function getFiveWind(accNum){
	const v = mod(accNum, 29);
	if(v === 0){
		return mod(divideFactor(accNum, 29), 9) || 9;
	}
	const idx = v % 9 === 0 ? Math.floor(v / 9) : mod(v, 9);
	return [1, 3, 5, 7, 9, 2, 4, 6, 8][idx - 1] || 1;
}

function getEightWind(accNum){
	const v = mod(accNum, 9);
	if(v === 0){
		return mod(divideFactor(accNum, 9), 9) || 9;
	}
	const idx = v % 9 === 0 ? Math.floor(v / 9) : mod(v, 9);
	return [2, 3, 4, 6, 7, 8, 9, 1][idx - 1] || 1;
}

function getBigYo(accNum){
	let big = mod(accNum + 34, 288);
	if(big > 36){
		big = Math.floor(big / 36);
	}
	if(big < 6){
		big = 6;
	}
	return { 7: 1, 8: 2, 9: 3, 1: 4, 2: 5, 3: 6, 4: 7, 6: 8 }[big] || 1;
}

function getSmallYo(accNum){
	const small = mod(accNum, 360);
	if(small < 24){
		return (small % 3) || 1;
	}
	let sm = mod(small, 24);
	if(small > 10){
		sm = small - 9;
	}
	if(sm % 3 !== 0){
		return { 1: 1, 2: 2 }[sm % 3] || 1;
	}
	return { 1: 1, 2: 2, 3: 3, 4: 4, 6: 5, 7: 6, 8: 7, 9: 8 }[Math.floor(sm / 3)] || 1;
}

function normOptionSex(sex){
	return (sex === 0 || sex === '女') ? '女' : '男';
}

function normalizePalace(palace){
	return BRANCH_ALIAS[palace] || palace;
}

function calcJiyuan(style, accNum){
	if(style !== 0 && style !== 1 && style !== 2){
		return '';
	}
	let jiNum = accNum % 360 === 1 ? 1 : Math.floor((mod(accNum, 360) / 60) + 1);
	let yuanNum = Math.floor(mod(mod(mod(accNum, 360), 72), 24) / 3) || 1;
	if(jiNum > 6){ jiNum -= 6; }
	if(yuanNum > 6){ yuanNum -= 6; }
	const cnum = '一二三四五六';
	return `第${cnum[jiNum - 1] || '一'}纪第${cnum[yuanNum - 1] || '一'}元`;
}

function buildPalaceMarks(pan){
	const marks = [
		{ label: '太乙', palace: pan.taiyiPalace },
		{ label: '文昌', palace: pan.skyeyes },
		{ label: '太岁', palace: pan.taishui },
		{ label: '合神', palace: pan.hegod },
		{ label: '计神', palace: pan.jigod },
		{ label: '始击', palace: pan.sf },
		{ label: '定目', palace: pan.se },
		{ label: '君基', palace: pan.kingbase },
		{ label: '臣基', palace: pan.officerbase },
		{ label: '民基', palace: pan.pplbase },
		{ label: '四神', palace: pan.fgd },
		{ label: '天乙', palace: pan.skyyi },
		{ label: '地乙', palace: pan.earthyi },
		{ label: '直符', palace: pan.zhifu },
		{ label: '飞符', palace: pan.flyfu },
		{ label: '主大', palace: pan.homeGeneralPalace },
		{ label: '主参', palace: pan.homeVGenPalace },
		{ label: '客大', palace: pan.awayGeneralPalace },
		{ label: '客参', palace: pan.awayVGenPalace },
		{ label: '五福', palace: pan.wufuPalace },
		{ label: '帝符', palace: pan.kingfu },
		{ label: '太尊', palace: pan.taijun },
		{ label: '飞鸟', palace: pan.flybird },
		{ label: '三风', palace: pan.threewindPalace },
		{ label: '五风', palace: pan.fivewindPalace },
		{ label: '八风', palace: pan.eightwindPalace },
		{ label: '大游', palace: pan.bigyoPalace },
		{ label: '小游', palace: pan.smyoPalace },
	];
	const map16 = {};
	[...GONG16_ORDER, '中'].forEach((palace)=>{ map16[palace] = []; });
	const map12 = {};
	DI_ZHI.forEach((branch)=>{ map12[branch] = []; });
	marks.forEach((item)=>{
		if(!item.palace){
			return;
		}
		if(map16[item.palace]){
			map16[item.palace].push(item.label);
		}
		const branch = normalizePalace(item.palace);
		if(map12[branch]){
			map12[branch].push(item.label);
		}
	});
	return {
		marks,
		palace16: [...GONG16_ORDER, '中'].map((palace)=>({ palace, items: map16[palace] })),
		branch12: DI_ZHI.map((branch)=>({ branch, items: map12[branch] })),
	};
}

export function calcTaiyiPanFromKintaiyi(fields, nongli, options){
	const dateParts = parseDateTime(fields);
	if(!dateParts){
		return null;
	}
	const opt = options || {};
	const style = opt.style !== undefined ? opt.style : 3;
	const tn = opt.tn !== undefined ? opt.tn : 0;
	const styleForPan = style === 5 ? 3 : style;
	const tnForPan = style === 5 ? 0 : tn;
	const sex = normOptionSex(opt.sex);

	const gz = buildGanZhi(nongli || {});
	const currentJie = extractCurrentJieqi(nongli);
	const yinYang = getYinYang(styleForPan, currentJie, safeFirstChar(gz.day), safeSecondChar(gz.time));
	const accNum = getAccNum(styleForPan, tnForPan, dateParts, nongli || {});
	const kook = getKook(accNum, yinYang);

	const taishui = getTaiSui(styleForPan, gz);
	const hegod = getHeGod(taishui);
	const jigod = getJiGod(yinYang, taishui);
	const sf = SF_LIST[kook.num - 1] || '';
	const skyeyes = (yinYang === '阳' ? SKYEYES_YANG : SKYEYES_YIN)[kook.num - 1] || '';
	const taiyiNum = getTaiyiNum(yinYang, kook.num);
	const taiyiPalace = TAIYI_PAI[kook.num - 1] || '';
	const se = getSe(skyeyes, hegod, taishui);

	const homeCal = calcHomeCal(skyeyes, taiyiNum);
	const awayCal = calcAwayCal(sf, taiyiNum);
	const setCal = calcSetCal(se, taiyiNum);
	const homeGeneral = getHomeGeneral(yinYang, kook.num);
	const awayGeneral = getAwayGeneral(yinYang, kook.num);
	const setGeneral = getSetGeneral(setCal);
	const homeVGen = getVGen(homeGeneral);
	const awayVGen = getVGen(awayGeneral);
	const setVGen = getVGen(setGeneral);

	const kingbase = getKingBase(accNum);
	const officerbase = getCycleValue(OFFICER_BASE, kook.num);
	const pplbase = getCycleValue(rotateFrom(DI_ZHI, '申'), kook.num);
	const fgd = getCycleValue(FOUR_GOD, kook.num);
	const skyyi = getCycleValue(SKY_YI, kook.num);
	const earthyi = getCycleValue(EARTH_YI, kook.num);
	const zhifu = getCycleValue(ZHI_FU, kook.num);
	const flyfu = getFlyFu(accNum);

	const wufuNum = getWufu(accNum);
	const threewindNum = getThreeWind(accNum);
	const fivewindNum = getFiveWind(accNum);
	const eightwindNum = getEightWind(accNum);
	const bigyoNum = getBigYo(accNum);
	const smyoNum = getSmallYo(accNum);

	const pan = {
		style,
		styleForPan,
		tn,
		tnForPan,
		sex,
		zhao: sex === '女' ? '坤造' : '乾造',
		dateStr: dateParts.dateStr,
		timeStr: dateParts.timeStr,
		realSunTime: nongli ? (nongli.birth || '') : '',
		lunarText: nongli ? `${nongli.year || ''}年${nongli.leap ? '闰' : ''}${nongli.month || ''}${nongli.day || ''}` : '',
		jiedelta: nongli ? (nongli.jiedelta || '') : '',
		jieqi: currentJie,
		ganzhi: gz,
		accNum,
		jiyuan: calcJiyuan(styleForPan, accNum),
		kook,
		taishui,
		hegod,
		jigod,
		sf,
		skyeyes,
		se,
		taiyiNum,
		taiyiPalace,
		homeCal,
		awayCal,
		setCal,
		homeGeneral,
		homeVGen,
		awayGeneral,
		awayVGen,
		setGeneral,
		setVGen,
		kingbase,
		officerbase,
		pplbase,
		fgd,
		skyyi,
		earthyi,
		zhifu,
		flyfu,
		wufuNum,
		wufuPalace: num2gong(wufuNum),
		kingfu: getKingFu(accNum),
		taijun: getTaiJun(accNum),
		flybird: getFlyBird(accNum),
		threewindNum,
		threewindPalace: num2gong(threewindNum),
		fivewindNum,
		fivewindPalace: num2gong(fivewindNum),
		eightwindNum,
		eightwindPalace: num2gong(eightwindNum),
		bigyoNum,
		bigyoPalace: num2gong(bigyoNum),
		smyoNum,
		smyoPalace: num2gong(smyoNum),
		homeGeneralPalace: num2gong(homeGeneral),
		homeVGenPalace: num2gong(homeVGen),
		awayGeneralPalace: num2gong(awayGeneral),
		awayVGenPalace: num2gong(awayVGen),
		setGeneralPalace: num2gong(setGeneral),
		setVGenPalace: num2gong(setVGen),
		options: {
			styleLabel: getTaiyiStyleLabel(style),
			accumLabel: getTaiyiAccumLabel(tnForPan),
			sexLabel: sex,
		},
	};

	const marks = buildPalaceMarks(pan);
	pan.palaceMarks = marks.marks;
	pan.palace16 = marks.palace16;
	pan.branch12 = marks.branch12;
	return pan;
}

export function getTaiyiStyleLabel(value){
	const one = TAIYI_STYLE_OPTIONS.find((item)=>item.value === value);
	return one ? one.label : `${value}`;
}

export function getTaiyiAccumLabel(value){
	const one = TAIYI_ACCUM_OPTIONS.find((item)=>item.value === value);
	return one ? one.label : `${value}`;
}

export function buildTaiyiSnapshotLines(pan){
	if(!pan){
		return [];
	}
	const lines = [];
	lines.push(`盘式：${pan.options ? pan.options.styleLabel : ''}`);
	lines.push(`积年法：${pan.options ? pan.options.accumLabel : ''}`);
	if(pan.jiyuan){
		lines.push(`纪元：${pan.jiyuan}`);
	}
	lines.push(`局式：${pan.kook ? pan.kook.text : ''}（${pan.kook ? pan.kook.year : ''}）`);
	lines.push(`积数：${pan.accNum}`);
	lines.push(`太乙：${pan.taiyiPalace}宫（太乙数${pan.taiyiNum}）`);
	lines.push(`文昌：${pan.skyeyes} 始击：${pan.sf} 定目：${pan.se || '—'}`);
	lines.push(`太岁：${pan.taishui} 合神：${pan.hegod} 计神：${pan.jigod}`);
	lines.push(`主算：${pan.homeCal} 客算：${pan.awayCal} 定算：${pan.setCal}`);
	lines.push(`主大/主参：${pan.homeGeneralPalace}/${pan.homeVGenPalace} 客大/客参：${pan.awayGeneralPalace}/${pan.awayVGenPalace}`);
	lines.push(`君臣民基：${pan.kingbase}/${pan.officerbase}/${pan.pplbase}`);
	lines.push(`四神/天乙/地乙/直符/飞符：${pan.fgd}/${pan.skyyi}/${pan.earthyi}/${pan.zhifu}/${pan.flyfu}`);
	lines.push(`五福/帝符/太尊/飞鸟：${pan.wufuPalace}/${pan.kingfu}/${pan.taijun}/${pan.flybird}`);
	lines.push(`三风/五风/八风：${pan.threewindPalace}/${pan.fivewindPalace}/${pan.eightwindPalace}`);
	lines.push(`大游/小游：${pan.bigyoPalace}/${pan.smyoPalace}`);
	return lines;
}
