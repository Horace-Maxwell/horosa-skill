
import { SU28_MODE_LABEL } from '../guolao/guolaoData.js';







import * as AstroText from '../../constants/AstroText.js';
import * as AstroConst from '../../constants/AstroConst.js';
import * as SZConst from './SZConst.js';
import * as Su28Helper from '../su28/Su28Helper.js';
import { signDegMin, astroMsgPlainText as msg } from './suzhanAstroHelper.js';






// 最小尺寸是屏幕可读意图(物理 px),壳缩放 z 下按 1/z 折算成布局 px;z=1 恒等。

import { ASC_RA_MODE_IMPROVED, ASC_RA_MODE_CLASSIC, loadSuzhanAscRaMode, withAscRaModeRoot, ascRaModeSnapshotLine } from '../utils/ascRaMode.js';


function chartTypeName(type){
	const map = {};
	map[SZConst.SZChart_NoExternChart] = '无外盘';
	map[SZConst.SZChart_SignChart] = '星座外盘';
	map[SZConst.SZChart_FengYeChart] = '分野外盘';
	map[SZConst.SZChart_BaGuaChart] = '八卦外盘';
	map[SZConst.SZChart_DunJiaChart] = '遁甲外盘';
	map[SZConst.SZChart_TaiYiChart] = '太乙外盘';
	map[SZConst.SZChart_FangWeiChart] = '方位外盘';
	map[SZConst.SZChart_NiXiangChart] = '逆向外盘';
	return map[type] || `${type}`;
}

function chartShapeName(shape){
	return shape === SZConst.SZChart_Circle ? '圆形盘' : '方形盘';
}

function houseStartModeName(mode){
	return mode === SZConst.SZHouseStart_ASC ? 'ASC起盘' : '八字公式起盘';
}

function signFromLon(lon){
	if(lon === undefined || lon === null || Number.isNaN(Number(lon))){
		return null;
	}
	let val = Number(lon) % 360;
	if(val < 0){
		val += 360;
	}
	const idx = Math.floor(val / 30) % 12;
	return AstroConst.LIST_SIGNS[idx];
}

function resolveHouseStartMode(fields){
	if(fields && fields.houseStartMode && fields.houseStartMode.value !== undefined && fields.houseStartMode.value !== null){
		return parseInt(fields.houseStartMode.value, 10) === SZConst.SZHouseStart_ASC
			? SZConst.SZHouseStart_ASC : SZConst.SZHouseStart_Bazi;
	}
	return SZConst.SZHouseStart_Bazi;
}

// 上升取法(改进 = 真赤经 / 经典 = 东点黄经)只在「ASC 起盘」时起作用;八字公式起盘不读上升赤经定命宫 → 恒按改进。
// fields.ascRaMode(挂载齿轮写进记录、无头重算带进来)优先,否则取宿占页的保存值(节气页内嵌宿盘同此)。
export function suzhanAscRaModeOf(fields){
	if(resolveHouseStartMode(fields) !== SZConst.SZHouseStart_ASC){ return ASC_RA_MODE_IMPROVED; }
	const f = fields && fields.ascRaMode ? fields.ascRaMode.value : undefined;
	if(f === ASC_RA_MODE_IMPROVED || f === ASC_RA_MODE_CLASSIC){ return f; }
	return loadSuzhanAscRaMode();
}

function computeAscSignIndex(rootObj, chart, fields){
	const objects = chart && chart.objects ? chart.objects : [];
	const asc = objects.find((obj)=>obj.id === AstroConst.ASC);
	const sun = objects.find((obj)=>obj.id === AstroConst.SUN);
	if(!asc){
		return -1;
	}
	const ascIdx = Math.floor(Number(asc.ra) / 30);
	const mode = resolveHouseStartMode(fields);
	if(mode === SZConst.SZHouseStart_ASC){
		return ascIdx;
	}
	const bazi = (chart && chart.nongli && chart.nongli.bazi)
		|| (rootObj && rootObj.nongli && rootObj.nongli.bazi);
	if(!bazi || !sun){
		return ascIdx;
	}
	const timezi = bazi.time && bazi.time.branch ? bazi.time.branch.cell : null;
	const timesig = timezi ? SZConst.ZiSign[timezi] : null;
	const tmsigidx = timesig ? AstroConst.LIST_SIGNS.indexOf(timesig) : -1;
	if(tmsigidx < 0){
		return ascIdx;
	}
	const sunidx = Math.floor(Number(sun.ra) / 30);
	return (sunidx - tmsigidx - 5 + 24) % 12;
}

function houseFullLabel(house, idx, ascSignIndex){
	let houseName = msg(house && house.id ? house.id : null) || `第${idx + 1}宫`;
	const sign = signFromLon(house ? house.lon : null);
	if(!sign){
		return houseName;
	}
	const signIdx = AstroConst.LIST_SIGNS.indexOf(sign);
	if(signIdx >= 0 && ascSignIndex >= 0){
		const hnum = (signIdx - ascSignIndex + 12) % 12 + 1;
		houseName = `第${hnum}宫`;
	}
	const zi = SZConst.SignZi[sign] || '';
	const area = (SZConst.SZSigns[signIdx] && SZConst.SZSigns[signIdx].length >= 2)
		? `${SZConst.SZSigns[signIdx][0]}${SZConst.SZSigns[signIdx][1]}`
		: '';
	const signName = AstroText.AstroMsgCN[sign] || msg(sign);
	return `${zi}—${area}—${signName}座—${houseName}`;
}

export function buildHouseObjectLines(chart){
	const lines = [];
	const houses = chart.houses || [];
	const objects = chart.objects || [];
	if(houses.length === 0){
		return lines;
	}
	lines.push('| 宫位 | 星体 | 度 | 座 | 分 | 宿 |');
	lines.push('| --- | --- | --- | --- | --- | --- |');
	houses.forEach((house)=>{
		const inHouse = objects.filter((obj)=>obj.house === house.id);
		if(inHouse.length === 0){
			lines.push(`| ${msg(house.id)} | 无 | — | — | — | — |`);
			return;
		}
		inHouse.forEach((obj, k)=>{
			const sd = signDegMin(obj.signlon);
			lines.push(`| ${k === 0 ? msg(house.id) : '—'} | ${msg(obj.id)} | ${sd[0]} | ${msg(obj.sign)} | ${sd[1]} | ${obj.su28 || '—'} |`);
		});
	});
	return lines;
}

function buildSu28ObjectLines(chart, planetDisplay){
	const lines = [];
	const suHouses = chart && chart.fixedStarSu28 ? chart.fixedStarSu28 : [];
	const objects = chart && chart.objects ? chart.objects : [];
	const suMap = new Map();
	suHouses.forEach((su)=>{
		suMap.set(su.name, su);
	});

	let visibleSet = null;
	if(planetDisplay && planetDisplay.length){
		visibleSet = new Set(planetDisplay);
	}

	suHouses.forEach((su)=>{
		lines.push(`${su.name}`);
		let inSu = objects.filter((obj)=>{
			if(obj.su28 !== su.name){
				return false;
			}
			if(visibleSet){
				return visibleSet.has(obj.id);
			}
			return AstroConst.isTraditionPlanet(obj.id);
		});
		inSu = inSu.sort((a, b)=>{
			// 环形序须对称全序(同文件 buildHouseSuLines 同款):跨 0°RA 两向都判,
			// 旧版只判一侧 → 非对称比较器,Array.sort 行为未定义,宿内列序随实现漂移。
			if(a.ra > 300 && b.ra < 30){
				return -1;
			}
			if(b.ra > 300 && a.ra < 30){
				return 1;
			}
			return a.ra - b.ra;
		});
		if(inSu.length === 0){
			lines.push('星体：无');
			lines.push('');
			return;
		}
		inSu.forEach((obj)=>{
			let radeg = Number(obj.ra) - Number(su.ra);
			if(Number.isNaN(radeg)){
				radeg = Number(obj.signlon);
			}
			if(radeg < 0){
				radeg += 360;
			}
			const sd = signDegMin(radeg);
			lines.push(`星体：${msg(obj.id)} ${sd[0]}˚${obj.su28}${sd[1]}分`);
		});
		lines.push('');
	});

	return lines;
}

function buildHouseSuLines(rootObj, chart, planetDisplay, fields){
	const lines = [];
	const houses = chart && chart.houses ? chart.houses : [];
	const objects = chart && chart.objects ? chart.objects : [];
	const ascSignIndex = computeAscSignIndex(rootObj, chart, fields);
	let visibleSet = null;
	if(planetDisplay && planetDisplay.length){
		visibleSet = new Set(planetDisplay);
	}

	houses.forEach((house, idx)=>{
		lines.push(`宫位：${houseFullLabel(house, idx, ascSignIndex)}`);
		let inHouse = objects.filter((obj)=>{
			if(obj.house !== house.id){
				return false;
			}
			if(visibleSet){
				return visibleSet.has(obj.id);
			}
			return AstroConst.isTraditionPlanet(obj.id);
		});
		inHouse = inHouse.sort((a, b)=>{
			// 环形序须对称全序:跨 0°RA 的宫,300°+ 侧在前、30°- 侧在后,两向都要判;
			// 旧版只判一侧(非对称比较器,Array.sort 行为未定义 → 宫内列序随实现漂移)。
			if(a.ra > 300 && b.ra < 30){ return -1; }
			if(b.ra > 300 && a.ra < 30){ return 1; }
			return a.ra - b.ra;
		});
		if(inHouse.length === 0){
			lines.push('二十八宿：无');
			lines.push('星曜：无');
			lines.push('');
			return;
		}

		const suMap = new Map();
		inHouse.forEach((obj)=>{
			const su = obj.su28 || '未知宿';
			if(!suMap.has(su)){
				suMap.set(su, []);
			}
			suMap.get(su).push(obj);
		});

		const suKeys = Array.from(suMap.keys()).sort((a, b)=>{
			const ia = Su28Helper.Su28.indexOf(a);
			const ib = Su28Helper.Su28.indexOf(b);
			if(ia < 0 && ib < 0){
				return `${a}`.localeCompare(`${b}`);
			}
			if(ia < 0){
				return 1;
			}
			if(ib < 0){
				return -1;
			}
			return ia - ib;
		});

		suKeys.forEach((su)=>{
			const list = suMap.get(su) || [];
			lines.push(`二十八宿：${su}`);
			list.forEach((obj)=>{
				let radeg = Number(obj.ra);
				if(!Number.isNaN(radeg)){
					const suRef = (chart.fixedStarSu28 || []).find((it)=>it.name === su);
					if(suRef && suRef.ra !== undefined && suRef.ra !== null){
						radeg = Number(obj.ra) - Number(suRef.ra);
						if(radeg < 0){
							radeg += 360;
						}
					}else{
						radeg = Number(obj.signlon);
					}
				}else{
					radeg = Number(obj.signlon);
				}
				const sd = signDegMin(radeg);
				lines.push(`星曜：${msg(obj.id)} ${sd[0]}˚${su}${sd[1]}分`);
			});
		});
		lines.push('');
	});

	return lines;
}

// 宫宿三行组(宫位：/二十八宿：/星曜：×12 宫)折叠成 GFM 表行(经归一器直通、docx/PDF 渲染真表)。
// 单一真值仍是 buildHouseSuLines(UI「宫宿」tab 与本表同源共用,故不动原函数,只做排版折叠):
// 单元格值=原行全角冒号后文本逐字搬运(一宫多宿/多曜以「、」并列;空宫沿用原「无」),数值零变更。
function foldHouseSuLinesToTable(suLines){
	const rows = [];
	let cur = null;
	(suLines || []).forEach((line)=>{
		const t = `${line || ''}`;
		if(t.indexOf('宫位：') === 0){
			cur = { house: t.slice('宫位：'.length), su: [], stars: [] };
			rows.push(cur);
			return;
		}
		if(!cur){
			return;
		}
		if(t.indexOf('二十八宿：') === 0){
			cur.su.push(t.slice('二十八宿：'.length));
			return;
		}
		if(t.indexOf('星曜：') === 0){
			cur.stars.push(t.slice('星曜：'.length));
		}
	});
	if(!rows.length){
		return [];
	}
	const out = ['| 宫位 | 二十八宿 | 星曜 |', '| --- | --- | --- |'];
	rows.forEach((r)=>{
		out.push(`| ${r.house} | ${r.su.join('、') || '无'} | ${r.stars.join('、') || '无'} |`);
	});
	return out;
}

export function buildSuzhanSnapshotText(rawChartObj, fields, planetDisplay){
	const lines = [];
	// 上升取法换在盘数据这一层(只换上升点的 ra):宫位起宫、宫宿表与盘面同一份
	const ascRaMode = suzhanAscRaModeOf(fields);
	const chartObj = withAscRaModeRoot(rawChartObj, ascRaMode);
	const chart = chartObj && chartObj.chart ? chartObj.chart : {};

	lines.push('[起盘信息]');
	if(fields && fields.date && fields.time){
		lines.push(`日期：${fields.date.value.format('YYYY-MM-DD')} ${fields.time.value.format('HH:mm:ss')}`);
	}
	if(fields && fields.zone){
		lines.push(`时区：${fields.zone.value}`);
	}
	if(fields && fields.lon && fields.lat){
		lines.push(`经纬度：${fields.lon.value} ${fields.lat.value}`);
	}
	if(fields && fields.szchart){
		lines.push(`外盘：${chartTypeName(fields.szchart.value)}`);
	}
	if(fields && fields.szshape){
		lines.push(`盘型：${chartShapeName(fields.szshape.value)}`);
	}
	if(fields && fields.doubingSu28){
		lines.push(`宿法：${SU28_MODE_LABEL[fields.doubingSu28.value] || (fields.doubingSu28.value === 1 ? '斗柄定房法' : '荀爽距星(19年测)')}`);   // 九档同源取名
	}
	if(fields && fields.houseStartMode){
		lines.push(`人事十二宫起盘：${houseStartModeName(fields.houseStartMode.value)}`);
	}
	if(resolveHouseStartMode(fields) === SZConst.SZHouseStart_ASC){
		lines.push(ascRaModeSnapshotLine(ascRaMode, chart));
	}

	lines.push('');
	lines.push('[宿盘宫位与二十八宿星曜]');
	lines.push(...foldHouseSuLinesToTable(buildHouseSuLines(chartObj, chart, planetDisplay, fields)));

	return lines.join('\n');
}

// [MU parity] 宿盘遁甲外盘曾把薄快照(仅 [起盘信息]+[九宫与宫内星体])写进共享奇门模块槽,
// latest-wins 覆盖真奇门(DunJia)快照 → 奇门导出吐错内容+丢真奇门 17 段;且 [九宫与宫内星体] 是奇门
// 旧段名(真奇门现产 [九宫方盘]/[旺相休囚死·月令能量]),不在奇门 preset。已删该跨模块写入与其专用 builder。
// 遁甲外盘型已在 buildSuzhanSnapshotText 的 [起盘信息] 以「外盘：遁甲外盘」标注,足够 AI 识别。
