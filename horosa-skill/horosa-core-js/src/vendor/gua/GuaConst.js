import {littleEndian, randomNum,} from './guaHelper.js';

export const LiuQi = {
	'金': {
		'金': '兄弟',
		'木': '妻财',
		'水': '子孙',
		'火': '官鬼',
		'土': '父母',
	},
	'木': {
		'金': '官鬼',
		'木': '兄弟',
		'水': '父母',
		'火': '子孙',
		'土': '妻财',
	},
	'水': {
		'金': '父母',
		'木': '子孙',
		'水': '兄弟',
		'火': '妻财',
		'土': '官鬼',
	},
	'火': {
		'金': '妻财',
		'木': '父母',
		'水': '官鬼',
		'火': '兄弟',
		'土': '子孙',
	},
	'土': {
		'金': '子孙',
		'木': '官鬼',
		'水': '妻财',
		'火': '父母',
		'土': '兄弟',
	},
};



export const Gua8 = [{
	name: '乾', abrname: '天', polar: 1, elem: '金', value: [1, 1, 1]
},{
	name: '兑', abrname: '泽', polar: 0, elem: '金', value: [1, 1, 0]
},{
	name: '离', abrname: '火', polar: 0, elem: '火', value: [1, 0, 1]
},{
	name: '震', abrname: '雷', polar: 1, elem: '木', value: [1, 0, 0]
},{
	name: '巽', abrname: '风', polar: 0, elem: '木', value: [0, 1, 1]
},{
	name: '坎', abrname: '水', polar: 1, elem: '水', value: [0, 1, 0]
},{
	name: '艮', abrname: '山', polar: 1, elem: '土', value: [0, 0, 1]
},{
	name: '坤', abrname: '地', polar: 0, elem: '土', value: [0, 0, 0]
}];

export const Gua64 = [{
	name: '乾为天', value: [1, 1, 1, 1, 1, 1], yaoname:['子水子孙', '寅木妻财', '辰土父母应', '午火官鬼', '申金兄弟', '戌土父母世'], house: Gua8[0],
},{
	name: '天风姤', value: [0, 1, 1, 1, 1, 1], yaoname:['丑土父母世', '亥水子孙', '酉金兄弟', '午火官鬼应', '申金兄弟', '戌土父母'], house: Gua8[0],
},{
	name: '天山遁', value: [0, 0, 1, 1, 1, 1], yaoname:['辰土父母', '午火官鬼世', '申金兄弟', '午火官鬼', '申金兄弟应', '戌土父母'], house: Gua8[0],
},{
	name: '天地否', value: [0, 0, 0, 1, 1, 1], yaoname:['未土父母', '巳火官鬼', '卯木妻财世', '午火官鬼', '申金兄弟', '戌土父母应'], house: Gua8[0],
},{
	name: '风地观', value: [0, 0, 0, 0, 1, 1], yaoname:['未土父母应', '巳火官鬼', '卯木妻财', '未土父母世', '巳火官鬼', '卯木妻财'], house: Gua8[0],
},{
	name: '山地剥', value: [0, 0, 0, 0, 0, 1], yaoname:['未土父母', '巳火官鬼应', '卯木妻财', '戌土父母', '子水子孙世', '寅木妻财'], house: Gua8[0],
},{
	name: '火地晋', value: [0, 0, 0, 1, 0, 1], yaoname:['未土父母应', '巳火官鬼', '卯木妻财', '酉金兄弟世', '未土父母', '巳火官鬼'], house: Gua8[0],
},{
	name: '火天大有', value: [1, 1, 1, 1, 0, 1], yaoname:['子水子孙', '寅木妻财', '辰土父母世', '酉金兄弟', '未土父母', '巳火官鬼应'], house: Gua8[0],
},

{
	name: '坎为水', value: [0, 1, 0, 0, 1, 0], yaoname: ['寅木子孙', '辰土官鬼', '午火妻财应', '申金父母', '戌土官鬼', '子水兄弟世'], house: Gua8[5],
},{
	name: '水泽节', value: [1, 1, 0, 0, 1, 0], yaoname: ['巳火妻财世', '卯木子孙', '丑土官鬼', '申金父母应', '戌土官鬼', '子水兄弟'], house: Gua8[5],
},{
	name: '水雷屯', value: [1, 0, 0, 0, 1, 0], yaoname: ['子水兄弟', '寅木子孙世', '辰土官鬼', '申金父母', '戌土官鬼应', '子水兄弟'], house: Gua8[5],
},{
	name: '水火既济', value: [1, 0, 1, 0, 1, 0], yaoname: ['卯木子孙', '丑土官鬼', '亥水兄弟世', '申金父母', '戌土官鬼', '子水兄弟应'], house: Gua8[5],
},{
	name: '泽火革', value: [1, 0, 1, 1, 1, 0], yaoname: ['卯木子孙应', '丑土官鬼', '亥水兄弟', '亥水兄弟世', '酉金父母', '未土官鬼'], house: Gua8[5],
},{
	name: '雷火丰', value: [1, 0, 1, 1, 0, 0], yaoname: ['卯木子孙', '丑土官鬼应', '亥水兄弟', '午火妻财', '申金父母世', '戌土官鬼'], house: Gua8[5],
},{
	name: '地火明夷', value: [1, 0, 1, 0, 0, 0], yaoname: ['卯木子孙应', '丑土官鬼', '亥水兄弟', '丑土官鬼世', '亥水兄弟', '酉金父母'], house: Gua8[5],
},{
	name: '地水师', value: [0, 1, 0, 0, 0, 0], yaoname: ['寅木子孙', '辰土官鬼', '午火妻财世', '丑土官鬼', '亥水兄弟', '酉金父母应'], house: Gua8[5],
},

{
	name: '艮为山', value: [0, 0, 1, 0, 0, 1], yaoname: ['辰土兄弟', '午火父母', '申金子孙应', '戌土兄弟', '子水妻财', '寅木官鬼世'], house: Gua8[6],
},{
	name: '山火贲', value: [1, 0, 1, 0, 0, 1], yaoname: ['卯木官鬼世', '丑土兄弟', '亥水妻财', '戌土兄弟应', '子水妻财', '寅木官鬼'], house: Gua8[6],
},{
	name: '山天大畜', value: [1, 1, 1, 0, 0, 1], yaoname: ['子水妻财', '寅木官鬼世', '辰土兄弟', '戌土兄弟', '子水妻财应', '寅木官鬼'], house: Gua8[6],
},{
	name: '山泽损', value: [1, 1, 0, 0, 0, 1], yaoname: ['巳火父母', '卯木官鬼', '丑土兄弟世', '戌土兄弟', '子水妻财', '寅木官鬼应'], house: Gua8[6],
},{
	name: '火泽睽', value: [1, 1, 0, 1, 0, 1], yaoname: ['巳火父母应', '卯木官鬼', '丑土兄弟', '酉金子孙世', '未土兄弟', '巳火父母'], house: Gua8[6],
},{
	name: '天泽履', value: [1, 1, 0, 1, 1, 1], yaoname: ['巳火父母', '卯木官鬼应', '丑土兄弟', '午火父母', '申金子孙世', '戌土兄弟'], house: Gua8[6],
},{
	name: '风泽中孚', value: [1, 1, 0, 0, 1, 1], yaoname: ['巳火父母应', '卯木官鬼', '丑土兄弟', '未土兄弟世', '巳火父母', '卯木官鬼'], house: Gua8[6],
},{
	name: '风山渐', value: [0, 0, 1, 0, 1, 1], yaoname: ['辰土兄弟', '午火父母', '申金子孙世', '未土兄弟', '巳火父母', '卯木官鬼应'], house: Gua8[6],
},

{
	name: '震为雷', value: [1, 0, 0, 1, 0, 0], yaoname: ['子水父母', '寅木兄弟', '辰土妻财应', '午火子孙', '申金官鬼', '戌土妻财世'], house: Gua8[3],
},{
	name: '雷地豫', value: [0, 0, 0, 1, 0, 0], yaoname: ['未土妻财世', '巳火子孙', '卯木兄弟', '午火子孙应', '申金官鬼', '戌土妻财'], house: Gua8[3],
},{
	name: '雷水解', value: [0, 1, 0, 1, 0, 0], yaoname: ['寅木兄弟', '辰土妻财世', '午火子孙', '午火子孙', '申金官鬼应', '戌土妻财'], house: Gua8[3],
},{
	name: '雷风恒', value: [0, 1, 1, 1, 0, 0], yaoname: ['丑土妻财', '亥水父母', '酉金官鬼世', '午火子孙', '申金官鬼', '戌土妻财应'], house: Gua8[3],
},{
	name: '地风升', value: [0, 1, 1, 0, 0, 0], yaoname: ['丑土妻财应', '亥水父母', '酉金官鬼', '丑土妻财世', '亥水父母', '酉金官鬼'], house: Gua8[3],
},{
	name: '水风井', value: [0, 1, 1, 0, 1, 0], yaoname: ['丑土妻财', '亥水父母应', '酉金官鬼', '申金官鬼', '戌土妻财世', '子水父母'], house: Gua8[3],
},{
	name: '泽风大过', value: [0, 1, 1, 1, 1, 0], yaoname: ['丑土妻财应', '亥水父母', '酉金官鬼', '亥水父母世', '酉金官鬼', '未土妻财'], house: Gua8[3],
},{
	name: '泽雷随', value: [1, 0, 0, 1, 1, 0], yaoname: ['子水父母', '寅木兄弟', '辰土妻财世', '亥水父母', '酉金官鬼', '未土妻财应'], house: Gua8[3],
},

{
	name: '巽为风', value: [0, 1, 1, 0, 1, 1], yaoname: ['丑土妻财', '亥水父母', '酉金官鬼应', '未土妻财', '巳火子孙', '卯木兄弟世'], house: Gua8[4],
},{
	name: '风天小畜', value: [1, 1, 1, 0, 1, 1], yaoname: ['子水父母世', '寅木兄弟', '辰土妻财', '未土妻财应', '巳火子孙', '卯木兄弟'], house: Gua8[4],
},{
	name: '风火家人', value: [1, 0, 1, 0, 1, 1], yaoname: ['卯木兄弟', '丑土妻财世', '亥水父母', '未土妻财', '巳火子孙应', '卯木兄弟'], house: Gua8[4],
},{
	name: '风雷益', value: [1, 0, 0, 0, 1, 1], yaoname: ['子水父母', '寅木兄弟', '辰土妻财世', '未土妻财', '巳火子孙', '卯木兄弟应'], house: Gua8[4],
},{
	name: '天雷无妄', value: [1, 0, 0, 1, 1, 1], yaoname: ['子水父母应', '寅木兄弟', '辰土妻财', '午火子孙世', '申金官鬼', '戌土妻财'], house: Gua8[4],
},{
	name: '火雷噬嗑', value: [1, 0, 0, 1, 0, 1], yaoname: ['子水父母', '寅木兄弟应', '辰土妻财', '酉金官鬼', '未土妻财世', '巳火子孙'], house: Gua8[4],
},{
	name: '山雷颐', value: [1, 0, 0, 0, 0, 1], yaoname: ['子水父母应', '寅木兄弟', '辰土妻财', '戌土妻财世', '子水父母', '寅木兄弟'], house: Gua8[4],
},{
	name: '山风蛊', value: [0, 1, 1, 0, 0, 1], yaoname: ['丑土妻财', '亥水父母', '酉金官鬼世', '戌土妻财', '子水父母', '寅木兄弟应'], house: Gua8[4],
},

{
	name: '离为火', value: [1, 0, 1, 1, 0, 1], yaoname: ['卯木父母', '丑土子孙', '亥水官鬼应', '酉金妻财', '未土子孙', '巳火兄弟世'], house: Gua8[2],
},{
	name: '火山旅', value: [0, 0, 1, 1, 0, 1], yaoname: ['辰土子孙世', '午火兄弟', '申金妻财', '酉金妻财应', '未土子孙', '巳火兄弟'], house: Gua8[2],
},{
	name: '火风鼎', value: [0, 1, 1, 1, 0, 1], yaoname: ['丑土子孙', '亥水官鬼世', '酉金妻财', '酉金妻财', '未土子孙应', '巳火兄弟'], house: Gua8[2],
},{
	name: '火水未济', value: [0, 1, 0, 1, 0, 1], yaoname: ['寅木父母', '辰土子孙', '午火兄弟世', '酉金妻财', '未土子孙', '巳火兄弟应'], house: Gua8[2],
},{
	name: '山水蒙', value: [0, 1, 0, 0, 0, 1], yaoname: ['寅木父母应', '辰土子孙', '午火兄弟', '戌土子孙世', '子水官鬼', '寅木父母'], house: Gua8[2],
},{
	name: '风水涣', value: [0, 1, 0, 0, 1, 1], yaoname: ['寅木父母', '辰土子孙应', '午火兄弟', '未土子孙', '巳火兄弟世', '卯木父母'], house: Gua8[2],
},{
	name: '天水讼', value: [0, 1, 0, 1, 1, 1], yaoname: ['寅木父母应', '辰土子孙', '午火兄弟', '午火兄弟世', '申金妻财', '戌土子孙'], house: Gua8[2],
},{
	name: '天火同人', value: [1, 0, 1, 1, 1, 1], yaoname: ['卯木父母', '丑土子孙', '亥水官鬼世', '午火兄弟', '申金妻财', '戌土子孙应'], house: Gua8[2],
},

{
	name: '坤为地', value: [0, 0, 0, 0, 0, 0], yaoname: ['未土兄弟', '巳火父母', '卯木官鬼应', '丑土兄弟', '亥水妻财', '酉金子孙世'], house: Gua8[7],
},{
	name: '地雷复', value: [1, 0, 0, 0, 0, 0], yaoname: ['子水妻财世', '寅木官鬼', '辰土兄弟', '丑土兄弟应', '亥水妻财', '酉金子孙'], house: Gua8[7],
},{
	name: '地泽临', value: [1, 1, 0, 0, 0, 0], yaoname: ['巳火父母', '卯木官鬼世', '丑土兄弟', '丑土兄弟', '亥水妻财应', '酉金子孙'], house: Gua8[7],
},{
	name: '地天泰', value: [1, 1, 1, 0, 0, 0], yaoname: ['子水妻财', '寅木官鬼', '辰土兄弟世', '丑土兄弟', '亥水妻财', '酉金子孙应'], house: Gua8[7],
},{
	name: '雷天大壮', value: [1, 1, 1, 1, 0, 0], yaoname: ['子水妻财应', '寅木官鬼', '辰土兄弟', '午火父母世', '申金子孙', '戌土兄弟'], house: Gua8[7],
},{
	name: '泽天夬', value: [1, 1, 1, 1, 1, 0], yaoname: ['子水妻财', '寅木官鬼应', '辰土兄弟', '亥水妻财', '酉金子孙世', '未土兄弟'], house: Gua8[7],
},{
	name: '水天需', value: [1, 1, 1, 0, 1, 0], yaoname: ['子水妻财应', '寅木官鬼', '辰土兄弟', '申金子孙世', '戌土兄弟', '子水妻财'], house: Gua8[7],
},{
	name: '水地比', value: [0, 0, 0, 0, 1, 0], yaoname: ['未土兄弟', '巳火父母', '卯木官鬼世', '申金子孙', '戌土兄弟', '子水妻财应'], house: Gua8[7],
},

{
	name: '兑为泽', value: [1, 1, 0, 1, 1, 0], yaoname: ['巳火官鬼', '卯木妻财', '丑土父母应', '亥水子孙', '酉金兄弟', '未土父母世'], house: Gua8[1],
},{
	name: '泽水困', value: [0, 1, 0, 1, 1, 0], yaoname: ['寅木妻财世', '辰土父母', '午火官鬼', '亥水子孙应', '酉金兄弟', '未土父母'], house: Gua8[1],
},{
	name: '泽地萃', value: [0, 0, 0, 1, 1, 0], yaoname: ['未土父母', '巳火官鬼世', '卯木妻财', '亥水子孙', '酉金兄弟应', '未土父母'], house: Gua8[1],
},{
	name: '泽山咸', value: [0, 0, 1, 1, 1, 0], yaoname: ['辰土父母', '午火官鬼', '申金兄弟世', '亥水子孙', '酉金兄弟', '未土父母应'], house: Gua8[1],
},{
	name: '水山蹇', value: [0, 0, 1, 0, 1, 0], yaoname: ['辰土父母应', '午火官鬼', '申金兄弟', '申金兄弟世', '戌土父母', '子水子孙'], house: Gua8[1],
},{
	name: '地山谦', value: [0, 0, 1, 0, 0, 0], yaoname: ['辰土父母', '午火官鬼应', '申金兄弟', '丑土父母', '亥水子孙世', '酉金兄弟'], house: Gua8[1],
},{
	name: '雷山小过', value: [0, 0, 1, 1, 0, 0], yaoname: ['辰土父母应', '午火官鬼', '申金兄弟', '午火官鬼世', '申金兄弟', '戌土父母'], house: Gua8[1],
},{
	name: '雷泽归妹', value: [1, 1, 0, 1, 0, 0], yaoname: ['巳火官鬼', '卯木妻财', '丑土父母世', '午火官鬼', '申金兄弟', '戌土父母应'], house: Gua8[1],
}];

export const ZiList = ['子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥'];
export const GanList = ['甲', '乙', '丙', '丁', '戊', '己', '庚', '辛', '壬', '癸'];
export const HourZi = [
	'子',
	'丑', '丑',
	'寅', '寅', 
	'卯', '卯', 
	'辰', '辰', 
	'巳', '巳', 
	'午', '午', 
	'未', '未', 
	'申', '申', 
	'酉', '酉', 
	'戌', '戌', 
	'亥', '亥',
	'子'
];

export const SixGods = {
	'甲': ['青龙', '朱雀', '勾陈', '螣蛇', '白虎', '玄武'],
	'乙': ['青龙', '朱雀', '勾陈', '螣蛇', '白虎', '玄武'],
	'丙': ['朱雀', '勾陈', '螣蛇', '白虎', '玄武', '青龙'],
	'丁': ['朱雀', '勾陈', '螣蛇', '白虎', '玄武', '青龙'],
	'戊': ['勾陈', '螣蛇', '白虎', '玄武', '青龙', '朱雀'],
	'己': ['螣蛇', '白虎', '玄武', '青龙', '朱雀', '勾陈'],
	'庚': ['白虎', '玄武', '青龙', '朱雀', '勾陈', '螣蛇'],
	'辛': ['白虎', '玄武', '青龙', '朱雀', '勾陈', '螣蛇'],
	'壬': ['玄武', '青龙', '朱雀', '勾陈', '螣蛇', '白虎'],
	'癸': ['玄武', '青龙', '朱雀', '勾陈', '螣蛇', '白虎'],
};

let Gua64Map = new Map();
function initGua64(){
	for(let i=0; i<Gua64.length; i++){
		Gua64[i].index = i;
		let gua = Gua64[i].value;
		let key = littleEndian(gua);
		Gua64Map.set(key, Gua64[i]);
	}
}

export function getGua64(key){
	if(Gua64Map.size === 0){
		initGua64();
	}
	if(key < 0){
		return null;
	}
	return Gua64Map.get(key);
}

let Gua8Map = new Map();
function initGua8(){
	Gua8.map((item, idx)=>{
		Gua8Map.set(item.name, item);
		Gua8Map.set(item.abrname, item);
	});
}

export function getGua8(key){
	if(Gua8Map.size === 0){
		initGua8();
	}
	if(key < 0){
		return null;
	}
	return Gua8Map.get(key);
}

export function setupYao(yaos, orghouse){
	let bits = [];
	for(let i=0; i<yaos.length; i++){
		bits[i] = yaos[i].value;
	}
	let key = littleEndian(bits);
	let gua = getGua64(key);
	if(gua){
		for(let i=0; i<yaos.length; i++){
			yaos[i].name = gua.yaoname[i];
		}
	}
	if(orghouse){
		let helem = orghouse.elem;
		for(let i=0; i<yaos.length; i++){
			let str = yaos[i].name;
			let zi = str.substr(0, 2);
			let elem = zi.substr(1, 1);
			let liu = LiuQi[helem][elem];
			let txt = zi + liu;
			if(str.length > 4){
				txt = txt + str.substr(4);
			}
			yaos[i].name = txt;
		}
	}
}

export function randYao(){
	let res = {
		value: 0,
		change: false,
	};

	let y1 = randomNum() % 2;
	let y2 = randomNum() % 2;
	let y3 = randomNum() % 2;

	let yangCnt = 0;
	let yinCnt = 0;
	if(y1 === 1){
		yangCnt = yangCnt + 1;
	}else{
		yinCnt = yinCnt + 1;
	}
	if(y2 === 1){
		yangCnt = yangCnt + 1;
	}else{
		yinCnt = yinCnt + 1;
	}
	if(y3 === 1){
		yangCnt = yangCnt + 1;
	}else{
		yinCnt = yinCnt + 1;
	}

	if(yangCnt === 3){
		res.value = 1;
		res.change = true;
	}else if(yinCnt === 3){
		res.value = 0;
		res.change = true;
	}else{
		if(yangCnt === 1){
			res.value = 1;
		}else if(yinCnt === 1){
			res.value = 0;
		}
		res.change = false;
	}
	return res;
}

export function getXun(gan, zi){
	let ganIdx = GanList.indexOf(gan);
	let ziIdx = ZiList.indexOf(zi);
	let firstZiIdx = (ziIdx - ganIdx + 12) % 12;
	let lastZiIdx = (ziIdx + 9 - ganIdx) % 12;
	let xun = [];
	if(firstZiIdx === 0){
		xun = ZiList.slice(0, 10);
	}else{
		let delta = 12 - firstZiIdx;
		if(delta >= 10){
			xun = ZiList.slice(firstZiIdx, lastZiIdx + 1);
		}else{
			xun = ZiList.slice(firstZiIdx, 12);
			for(let i=0; i<=lastZiIdx; i++){
				xun.push(ZiList[i]);
			}
		}
	}
	return xun;
}

export function getXunEmpty(gan, zi){
	let ganIdx = GanList.indexOf(gan);
	let ziIdx = ZiList.indexOf(zi);
	let firstZiIdx = (ziIdx - ganIdx + 12) % 12;
	let lastZiIdx = (ziIdx + 9 - ganIdx) % 12;
	let idx0 = (lastZiIdx + 1) % 12;
	let idx1 = (lastZiIdx + 2) % 12;
	return ZiList[idx0] + ZiList[idx1];
}
