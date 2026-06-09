import * as AstroConst from '../../constants/AstroConst.js';

export const LRChart_Circle = 0;
export const LRChart_Square = 1;
export const LRChartType = LRChart_Circle;


export const ZiList = ['子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥'];
export const GanList = ['甲', '乙', '丙', '丁', '戊', '己', '庚', '辛', '壬', '癸'];
export const SignZiList = ['戌', '酉', '申', '未', '午', '巳', '辰', '卯', '寅', '丑', '子', '亥'];

export const WinnerZiList = ['子', '丑', '寅', '卯', '辰', '亥'];
export const SummerZiList = ['巳', '午', '未', '申', '酉', '戌'];

export const TaiSui = ['岁驾', '丧门', '官符', '死符', '岁破', '吊客', '病符'];

export const GanJiZi = {
	'甲': '寅',
	'乙': '辰',
	'丙': '巳',
	'丁': '未',
	'戊': '巳',
	'己': '未',
	'庚': '申',
	'辛': '戌',
	'壬': '亥',
	'癸': '丑'
};

export const ZiHanGan = {
	'寅': '甲',
	'辰': '乙',
	'巳': '丙戊',
	'未': '丁己',
	'申': '庚',
	'戌': '辛',
	'亥': '壬',
	'丑': '癸'
};

export const YangZi = ['子', '寅', '辰', '午', '申', '戌'];
export const YingZi = ['丑', '卯', '巳', '未', '酉', '亥'];
export const YangGan = ['甲', '丙', '戊', '庚', '壬'];
export const YingGan = ['乙', '丁', '己', '辛', '癸'];

export const LRColor = {
	tianJiangColor: '#800080',
	liuQinColor: '#948e33',
	time:{
		bg: '#CC9900',
		color: '#ffffff',
	}
};

export const TianJiang = ['贵人', '螣蛇', '朱雀', '六合', '勾陈', '青龙', '天空', '白虎', '太常', '玄武', '太阴', '天后'];

export const DayGui = {
	'甲': '未',
	'乙': '申',
	'丙': '酉',
	'丁': '亥',
	'戊': '午',
	'己': '子',
	'庚': '丑',
	'辛': '寅',
	'壬': '卯',
	'癸': '巳'
};

export const NightGui = {
	'甲': '丑',
	'乙': '子',
	'丙': '亥',
	'丁': '酉',
	'戊': '寅',
	'己': '申',
	'庚': '未',
	'辛': '午',
	'壬': '巳',
	'癸': '卯'
};

export const DayGuiLiuReng = {
	'甲': '丑',
	'乙': '子',
	'丙': '亥',
	'丁': '亥',
	'戊': '丑',
	'己': '子',
	'庚': '丑',
	'辛': '午',
	'壬': '巳',
	'癸': '巳'
};

export const NightGuiLiuReng = {
	'甲': '未',
	'乙': '申',
	'丙': '酉',
	'丁': '酉',
	'戊': '未',
	'己': '申',
	'庚': '未',
	'辛': '寅',
	'壬': '卯',
	'癸': '卯'
};

export const DayGuiDunJia = {
	'甲': '未',
	'乙': '申',
	'丙': '酉',
	'丁': '亥',
	'戊': '丑',
	'己': '子',
	'庚': '丑',
	'辛': '寅',
	'壬': '卯',
	'癸': '巳'
};

export const NightGuiDunJia = {
	'甲': '丑',
	'乙': '子',
	'丙': '亥',
	'丁': '酉',
	'戊': '未',
	'己': '申',
	'庚': '未',
	'辛': '午',
	'壬': '巳',
	'癸': '卯'
};

export const GuiRengs = [{
	day: DayGuiLiuReng,
	night: NightGuiLiuReng,
},{
	day: DayGuiDunJia,
	night: NightGuiDunJia,
},{
	day: DayGui,
	night: NightGui,
}];

export const GanZiRestrain = {
	'甲': ['戊', '己', '辰', '戌', '丑', '未'],
	'乙': ['戊', '己', '辰', '戌', '丑', '未'],
	'丙': ['庚', '辛', '申', '酉'],
	'丁': ['庚', '辛', '申', '酉'],
	'戊': ['壬', '癸', '子', '亥'],
	'己': ['壬', '癸', '子', '亥'],
	'庚': ['甲', '乙', '寅', '卯'],
	'辛': ['甲', '乙', '寅', '卯'],
	'壬': ['丙', '丁', '巳', '午'],
	'癸': ['丙', '丁', '巳', '午'],
	'子': ['丙', '丁', '巳', '午'],
	'丑': ['壬', '癸', '子', '亥'],
	'寅': ['戊', '己', '辰', '戌', '丑', '未'],
	'卯': ['戊', '己', '辰', '戌', '丑', '未'],
	'辰': ['壬', '癸', '子', '亥'],
	'巳': ['庚', '辛', '申', '酉'],
	'午': ['庚', '辛', '申', '酉'],
	'未': ['壬', '癸', '子', '亥'],
	'申': ['甲', '乙', '寅', '卯'],
	'酉': ['甲', '乙', '寅', '卯'],
	'戌': ['壬', '癸', '子', '亥'],
	'亥': ['丙', '丁', '巳', '午'],
};

export const GanZiBrother = {
	'甲': ['乙', '寅', '卯'],
	'乙': ['甲', '寅', '卯'],
	'丙': ['丁', '巳', '午'],
	'丁': ['丙', '巳', '午'],
	'戊': ['己', '辰', '戌', '丑', '未'],
	'己': ['戊', '辰', '戌', '丑', '未'],
	'庚': ['辛', '申', '酉'],
	'辛': ['庚', '申', '酉'],
	'壬': ['癸', '子', '亥'],
	'癸': ['壬', '子', '亥'],
	'子': ['壬', '癸', '亥'],
	'丑': ['戊', '己', '辰', '戌', '未'],
	'寅': ['甲', '乙', '卯'],
	'卯': ['甲', '乙', '寅'],
	'辰': ['戊', '己', '丑', '戌', '未'],
	'巳': ['丙', '丁', '午'],
	'午': ['丙', '丁', '巳'],
	'未': ['戊', '己', '丑', '戌', '辰'],
	'申': ['庚', '辛', '酉'],
	'酉': ['庚', '辛', '申'],
	'戌': ['戊', '己', '丑', '辰', '未'],
	'亥': ['壬', '癸', '子'],
};

export const GanZiAccrue = {
	'甲': ['丙', '丁', '巳', '午'],
	'乙': ['丙', '丁', '巳', '午'],
	'丙': ['戊', '己', '辰', '戌', '丑', '未'],
	'丁': ['戊', '己', '辰', '戌', '丑', '未'],
	'戊': ['庚', '辛', '申', '酉'],
	'己': ['庚', '辛', '申', '酉'],
	'庚': ['壬', '癸', '子', '亥'],
	'辛': ['壬', '癸', '子', '亥'],
	'壬': ['甲', '乙', '寅', '卯'],
	'癸': ['甲', '乙', '寅', '卯'],
	'子': ['甲', '乙', '寅', '卯'],
	'丑': ['庚', '辛', '申', '酉'],
	'寅': ['丙', '丁', '巳', '午'],
	'卯': ['丙', '丁', '巳', '午'],
	'辰': ['庚', '辛', '申', '酉'],
	'巳': ['戊', '己', '辰', '戌', '丑', '未'],
	'午': ['戊', '己', '辰', '戌', '丑', '未'],
	'未': ['庚', '辛', '申', '酉'],
	'申': ['壬', '癸', '子', '亥'],
	'酉': ['壬', '癸', '子', '亥'],
	'戌': ['庚', '辛', '申', '酉'],
	'亥': ['甲', '乙', '寅', '卯'],
};

export const ZiMeng = ['寅', '申', '巳', '亥'];
export const ZiZong = ['子', '午', '卯', '酉'];
export const ZiJi = ['辰', '戌', '丑', '未'];
export const ZiXing = {
	'子': '卯',
	'丑': '戌',
	'寅': '巳',
	'卯': '子',
	'辰': '辰',
	'巳': '申',
	'午': '午',
	'未': '丑',
	'申': '寅',
	'酉': '酉',
	'戌': '未',
	'亥': '亥',
};

export const ZiCong = {
	'子': '午',
	'丑': '未',
	'寅': '申',
	'卯': '酉',
	'辰': '戌',
	'巳': '亥',
	'午': '子',
	'未': '丑',
	'申': '寅',
	'酉': '卯',
	'戌': '辰',
	'亥': '巳'
};

export const ZiYiMa = {
	'子': '寅',
	'丑': '亥',
	'寅': '申',
	'卯': '巳',
	'辰': '寅',
	'巳': '亥',
	'午': '申',
	'未': '巳',
	'申': '寅',
	'酉': '亥',
	'戌': '申',
	'亥': '巳'
};

export const ZiHe = {
	'子': '丑',
	'丑': '子',
	'寅': '亥',
	'卯': '戌',
	'辰': '酉',
	'巳': '申',
	'午': '未',
	'未': '午',
	'申': '巳',
	'酉': '辰',
	'戌': '卯',
	'亥': '寅'
};

export const ZiSangHe = {
	'子': ['申', '辰'],
	'丑': ['酉', '巳'],
	'寅': ['戌', '午'],
	'卯': ['亥', '未'],
	'辰': ['子', '申'],
	'巳': ['丑', '酉'],
	'午': ['寅', '戌'],
	'未': ['卯', '亥'],
	'申': ['辰', '子'],
	'酉': ['巳', '丑'],
	'戌': ['午', '寅'],
	'亥': ['未', '卯']
};

// 金口诀解读层：地支六害/六破 + 太玄数/五行数（公版常识，供 jinkou 关系图/数理复用；六冲复用上方 ZiCong、刑复用上方 ZiXing）
export const ZiHai = { '子': '未', '未': '子', '丑': '午', '午': '丑', '寅': '巳', '巳': '寅', '卯': '辰', '辰': '卯', '申': '亥', '亥': '申', '酉': '戌', '戌': '酉' };
export const ZiPo = { '子': '酉', '酉': '子', '丑': '辰', '辰': '丑', '寅': '亥', '亥': '寅', '卯': '午', '午': '卯', '巳': '申', '申': '巳', '戌': '未', '未': '戌' };
export const TaiXuanNum = { '甲': 9, '己': 9, '乙': 8, '庚': 8, '丙': 7, '辛': 7, '丁': 6, '壬': 6, '戊': 5, '癸': 5, '子': 9, '午': 9, '丑': 8, '未': 8, '寅': 7, '申': 7, '卯': 6, '酉': 6, '辰': 5, '戌': 5, '巳': 4, '亥': 4 };
export const WuXingNum = { '金': [3, 6, 9], '木': [3, 6, 9], '水': [1, 5, 7], '土': [1, 5, 7], '火': [2, 4, 8] };

export const GanHe = {
	'甲': '己',
	'乙': '庚',
	'丙': '辛',
	'丁': '壬',
	'戊': '癸',
	'己': '甲',
	'庚': '乙',
	'辛': '丙',
	'壬': '丁',
	'癸': '戊',
};

export const ZiLiuQin = {
	'子': {
		'甲': '父母',
		'乙': '父母',
		'丙': '官鬼',
		'丁': '官鬼',
		'戊': '妻财',
		'己': '妻财',
		'庚': '子孙',
		'辛': '子孙',
		'壬': '兄弟',
		'癸': '兄弟',
	},
	'丑': {
		'甲': '妻财',
		'乙': '妻财',
		'丙': '子孙',
		'丁': '子孙',
		'戊': '兄弟',
		'己': '兄弟',
		'庚': '父母',
		'辛': '父母',
		'壬': '官鬼',
		'癸': '官鬼',
	},
	'寅': {
		'甲': '兄弟',
		'乙': '兄弟',
		'丙': '父母',
		'丁': '父母',
		'戊': '官鬼',
		'己': '官鬼',
		'庚': '妻财',
		'辛': '妻财',
		'壬': '子孙',
		'癸': '子孙',
	},
	'卯': {
		'甲': '兄弟',
		'乙': '兄弟',
		'丙': '父母',
		'丁': '父母',
		'戊': '官鬼',
		'己': '官鬼',
		'庚': '妻财',
		'辛': '妻财',
		'壬': '子孙',
		'癸': '子孙',
	},
	'辰': {
		'甲': '妻财',
		'乙': '妻财',
		'丙': '子孙',
		'丁': '子孙',
		'戊': '兄弟',
		'己': '兄弟',
		'庚': '父母',
		'辛': '父母',
		'壬': '官鬼',
		'癸': '官鬼',
	},
	'巳': {
		'甲': '子孙',
		'乙': '父母',
		'丙': '兄弟',
		'丁': '兄弟',
		'戊': '父母',
		'己': '父母',
		'庚': '官鬼',
		'辛': '官鬼',
		'壬': '妻财',
		'癸': '妻财',
	},
	'午': {
		'甲': '子孙',
		'乙': '父母',
		'丙': '兄弟',
		'丁': '兄弟',
		'戊': '父母',
		'己': '父母',
		'庚': '官鬼',
		'辛': '官鬼',
		'壬': '妻财',
		'癸': '妻财',
	},
	'未': {
		'甲': '妻财',
		'乙': '妻财',
		'丙': '子孙',
		'丁': '子孙',
		'戊': '兄弟',
		'己': '兄弟',
		'庚': '父母',
		'辛': '父母',
		'壬': '官鬼',
		'癸': '官鬼',
	},
	'申': {
		'甲': '官鬼',
		'乙': '官鬼',
		'丙': '妻财',
		'丁': '妻财',
		'戊': '子孙',
		'己': '子孙',
		'庚': '兄弟',
		'辛': '兄弟',
		'壬': '父母',
		'癸': '父母',
	},
	'酉': {
		'甲': '官鬼',
		'乙': '官鬼',
		'丙': '妻财',
		'丁': '妻财',
		'戊': '子孙',
		'己': '子孙',
		'庚': '兄弟',
		'辛': '兄弟',
		'壬': '父母',
		'癸': '父母',
	},
	'戌': {
		'甲': '妻财',
		'乙': '妻财',
		'丙': '子孙',
		'丁': '子孙',
		'戊': '兄弟',
		'己': '兄弟',
		'庚': '父母',
		'辛': '父母',
		'壬': '官鬼',
		'癸': '官鬼',
	},
	'亥': {
		'甲': '父母',
		'乙': '父母',
		'丙': '官鬼',
		'丁': '官鬼',
		'戊': '妻财',
		'己': '妻财',
		'庚': '子孙',
		'辛': '子孙',
		'壬': '兄弟',
		'癸': '兄弟',
	},
}

export const WuXing = [{
	'elem': '土',
	'ganzi': '戊己辰戌丑未',
},{
	'elem': '金',
	'ganzi': '庚辛申酉',
},{
	'elem': '水',
	'ganzi': '壬癸亥子',
},{
	'elem': '木',
	'ganzi': '甲乙寅卯',
},{
	'elem': '火',
	'ganzi': '丙丁巳午',
}];

export const GanZiWuXing = {
	'戊': '土',
	'己': '土',
	'辰': '土',
	'戌': '土',
	'丑': '土',
	'未': '土',
	'庚': '金',
	'辛': '金',
	'申': '金',
	'酉': '金',
	'壬': '水',
	'癸': '水',
	'亥': '水',
	'子': '水',
	'甲': '木',
	'乙': '木',
	'寅': '木',
	'卯': '木',
	'丙': '火',
	'丁': '火',
	'午': '火',
	'巳': '火',
};


export function getHouseColor(i){
	let sig = AstroConst.LIST_SIGNS[i];
	return AstroConst.AstroColor.SignFill[sig];
}

export function getSigColor(i){
	let sig = AstroConst.LIST_SIGNS[i];
	return AstroConst.AstroColor[sig];
}

export function getSignZi(sign){
	let idx = AstroConst.LIST_SIGNS.indexOf(sign);
	return SignZiList[idx];
}

export function getGuiZi(chartObj, guirengType, isDiurnalOverride){
	let guirengobj = GuiRengs[guirengType];
	let dayGui = guirengobj.day;
	let nightGui = guirengobj.night;

	let gan = chartObj.nongli.dayGanZi.substr(0, 1);
	// 昼夜默认取星历 isDiurnal；六壬「换日/分昼夜法」可显式覆盖（缺省=现状，零回归）。
	let diurnal = (typeof isDiurnalOverride === 'boolean') ? isDiurnalOverride : chartObj.isDiurnal;
	let guizi = null;
	if(diurnal){
		guizi = dayGui[gan];
	}else{
		guizi = nightGui[gan];
	}
	return guizi;
}

export function isRestrain(gz1, gz2){
	return GanZiRestrain[gz1].indexOf(gz2) >= 0;
}

export function isBrother(gz1, gz2){
	return GanZiBrother[gz1].indexOf(gz2) >= 0;
}

export function isAccrue(gz1, gz2){
	return GanZiAccrue[gz1].indexOf(gz2) >= 0;
}

export function sameYingYang(gan, ziAry){
	let cnt = 0;
	let cuang0 = null;
	let stack = [];
	if(YangGan.indexOf(gan) >= 0){
		for(let i=0; i<ziAry.length; i++){
			if(YangZi.indexOf(ziAry[i]) >= 0){
				cuang0 = ziAry[i];
				cnt = cnt + 1;
				stack.push(ziAry[i]);
			}
		}
		if(cnt === 1){
			return {
				cnt: 1,
				data: [cuang0],
			};
		}else if(cnt > 1){
			return {
				cnt: cnt,
				data: stack,
			}
		}else{
			return {
				cnt: 0,
				data: ziAry,
			}
		}
	}else{
		for(let i=0; i<ziAry.length; i++){
			if(YingZi.indexOf(ziAry[i]) >= 0){
				cuang0 = ziAry[i];
				cnt = cnt + 1;
				stack.push(ziAry[i]);
			}
		}
		if(cnt === 1){
			return {
				cnt: 1,
				data: [cuang0],
			};
		}else if(cnt > 1){
			return {
				cnt: cnt,
				data: stack,
			}
		}else{
			return {
				cnt: 0,
				data: ziAry,
			}
		}
	}
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

