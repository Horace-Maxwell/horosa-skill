// 宿占快照 builder —— 自上游 components/suzhan/SuZhanMain.js **逐字**抽出（bespoke，derived_from 由
// contracts/vendor_manifest.json 的 derived_sha256 看守：上游 SuZhanMain.js 一动即红，复核本文件后 --restamp）。
// 上游这些纯函数与 React 组件同在一个文件里（整份 vendor 会把 antd/JSX 带进来），故只抽快照闭包：
//   · SIMPLE_TOKEN_MAP / splitDegree / isEncodedToken / msg / chartTypeName / chartShapeName / houseStartModeName /
//     signFromLon / resolveHouseStartMode / computeAscSignIndex / houseFullLabel（SuZhanMain.js:27-192）
//   · buildHouseSuLines / foldHouseSuLinesToTable / buildSuzhanSnapshotText（SuZhanMain.js:275-428）
// 人事十二宫「八字公式起盘」（缺省档）读 chart.nongli.bazi 的时支 —— 只有 Java /chart（ChartController 附农历四柱）
// 带它；headless 调用方须给 Java /chart 的整份响应（上游页面同源），缺 nongli 时 computeAscSignIndex 回落 ASC 起盘。
// 函数体逐字未改；只有下方 import 按 vendor 树改了路径（上游是 ../../constants/xxx 等）。
import { SU28_MODE_LABEL } from '../guolao/guolaoData.js';
import * as AstroText from '../../constants/AstroText.js';
import * as AstroConst from '../../constants/AstroConst.js';
import * as SZConst from './SZConst.js';
import * as Su28Helper from '../su28/Su28Helper.js';

const SIMPLE_TOKEN_MAP = {
	A: '日',
	B: '月',
	C: '水',
	D: '金',
	E: '火',
	F: '木',
	G: '土',
	H: '天王',
	I: '海王',
	J: '冥王',
	K: '北交',
	L: '南交',
	p: '福点',
	v: '暗月',
	w: '紫气',
	y: '凯龙',
	z: '月亮朔望点',
	Y: '月亮平均远地点',
	$: '月亮平均近地点',
	a: '白羊',
	b: '金牛',
	c: '双子',
	d: '巨蟹',
	e: '狮子',
	f: '处女',
	g: '天秤',
	h: '天蝎',
	i: '射手',
	j: '摩羯',
	k: '水瓶',
	l: '双鱼',
	0: '上升',
	1: '天顶',
	2: '天底',
	3: '下降',
	4: '谷神星',
	5: '智神星',
	6: '婚神星',
	7: '灶神星',
	8: '人龙星',
};

function splitDegree(degree){
	let d = Number(degree);
	if(Number.isNaN(d)){
		return [0, 0];
	}
	if(d < 0){
		d += 360;
	}
	const deg = Math.floor(d % 30);
	const min = Math.floor(((d % 30) - deg) * 60);
	return [deg, min];
}

function isEncodedToken(text){
	return /^[A-Za-z0-9${}]$/.test((text || '').trim());
}

function msg(id){
	if(id === undefined || id === null){
		return '';
	}
	if(AstroText.AstroTxtMsg[id]){
		return AstroText.AstroTxtMsg[id];
	}
	if(AstroText.AstroMsg[id]){
		const val = AstroText.AstroMsg[id];
		if(!isEncodedToken(val)){
			return `${val}`;
		}
	}
	const one = `${id}`.trim();
	if(one.length === 1 && SIMPLE_TOKEN_MAP[one]){
		return SIMPLE_TOKEN_MAP[one];
	}
	return `${id}`;
}

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
			// [X1·P2-12] 环形序须对称全序:跨 0°RA 的宫,300°+ 侧在前、30°- 侧在后,两向都要判;
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
				const sd = splitDegree(radeg);
				lines.push(`星曜：${msg(obj.id)} ${sd[0]}˚${su}${sd[1]}分`);
			});
		});
		lines.push('');
	});

	return lines;
}

// [v2 排版] 宫宿三行组(宫位：/二十八宿：/星曜：×12 宫)折叠成 GFM 表行(经归一器直通、docx/PDF 渲染真表)。
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

export function buildSuzhanSnapshotText(chartObj, fields, planetDisplay){
	const lines = [];
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
		lines.push(`宿法：${SU28_MODE_LABEL[fields.doubingSu28.value] || (fields.doubingSu28.value === 1 ? '斗柄定房法' : '荀爽距星(19年测)')}`);   // [Q-203] 九档同源取名
	}
	if(fields && fields.houseStartMode){
		lines.push(`人事十二宫起盘：${houseStartModeName(fields.houseStartMode.value)}`);
	}

	lines.push('');
	lines.push('[宿盘宫位与二十八宿星曜]');
	lines.push(...foldHouseSuLinesToTable(buildHouseSuLines(chartObj, chart, planetDisplay, fields)));

	return lines.join('\n');
}

export { msg, splitDegree, computeAscSignIndex, houseFullLabel, buildHouseSuLines, foldHouseSuLinesToTable };
