
import * as ZWConst from '../bazi/ZWConst.js';

let DiZi = ['子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥'];
let DiZiMap = new Map();

let HuaLuMap = new Map();
let HuaQuanMap = new Map();
let HuaKeMap = new Map();
let HuaJiMap = new Map();

let HuaMaps = [HuaLuMap, HuaQuanMap, HuaKeMap, HuaJiMap];

function initHuaMap(){
	let ganhua = ZWConst.getActiveSiHuaGan();
	for(let gan in ganhua){
		let stars = ganhua[gan];
		for(let i=0; i<4; i++){
			let map = HuaMaps[i];
			let hua = map.get(stars[i]);
			if(hua === undefined || hua === null){
				hua = gan;
			}else{
				hua = hua + gan;
			}
			map.set(stars[i], hua);
		}
	}
}

// ===== P0-4 杂曜/十二神 显示开关（localStorage；四化盘主盘是否渲染 Others/Small 组） =====
export function zwShowOthers(){
	const v = localStorage.getItem('ziweiShowOthers');
	return v === null ? true : v === '1'; // 默认开（杂吉/杂凶）
}
export function zwShowSmall(){
	const v = localStorage.getItem('ziweiShowSmall');
	return v === '1'; // 默认关（将前/岁前/博士十二神，避免主盘过密）
}

// 🔴 纯显示层开关的重绘广播(2026-07-31 运行时死开关审计实证)。
//    病灶:ZiWeiInput.redrawChart() 靠「把同一份时间字段原样再传一次」来求重绘,
//    但杂曜/十二神是**纯显示层**、不进排盘请求体 —— 参数逐字节相等必被 requestDedupe 命中,
//    chart 对象不变 → ZiWeiChart 不重渲染 → localStorage 明明写了 0,盘上杂曜纹丝不动。
//    改走「写仓 + 广播」(同 divinationJudgeGlobals 范式):盘面组件监听事件自重绘,
//    与排盘请求彻底解耦,不再借道 fields 假装数据变了。
export const ZIWEI_DISPLAY_EVENT = 'horosa:ziwei-display-changed';

export function bumpZwDisplayRev(key, value){
	if(typeof window === 'undefined' || typeof window.dispatchEvent !== 'function'){ return; }
	try{
		window.dispatchEvent(new CustomEvent(ZIWEI_DISPLAY_EVENT, { detail: { key: key, value: value } }));
	}catch(e){ /* 老内核无 CustomEvent 构造器:退化为不广播,行为同改动前 */ }
}

// P1-A：切流派后必须失效四化缓存并按新表重建（getSiHua 用 size===0 懒初始化，不显式清不会重算）。
export function resetHuaMap(){
	HuaLuMap.clear();
	HuaQuanMap.clear();
	HuaKeMap.clear();
	HuaJiMap.clear();
	initHuaMap();
}

export function getHouseZiIndex(zi){
	if(ZWConst.HouseZiMap.size === 0){
		for(let i=0; i<ZWConst.HouseZi.length; i++){
			ZWConst.HouseZiMap.set(ZWConst.HouseZi[i], i);
		}
	}
	return ZWConst.HouseZiMap.get(zi);
}

export function getSiHua(star, gan){
	if(HuaLuMap.size === 0){
		initHuaMap();
	}

	let lu = HuaLuMap.get(star);
	let quan = HuaQuanMap.get(star);
	let ke = HuaKeMap.get(star);
	let ji = HuaJiMap.get(star);
	if(lu !== undefined && lu !== null && lu.indexOf(gan) >= 0){
		return ZWConst.SiHua.hua[0];
	}
	if(quan !== undefined && quan !== null && quan.indexOf(gan) >= 0){
		return ZWConst.SiHua.hua[1];
	}
	if(ke !== undefined && ke !== null && ke.indexOf(gan) >= 0){
		return ZWConst.SiHua.hua[2];
	}
	if(ji !== undefined && ji !== null && ji.indexOf(gan) >= 0){
		return ZWConst.SiHua.hua[3];
	}
	return null;
}

export function isDirCloseWise(chartobj){
	let gender = chartobj.gender;
	let polar = chartobj.yearPolar;
	if((gender === 'Male' && polar === 'Positive') 
		|| (gender === 'Female' && polar === 'Negative') ){
		return true;
	}
	return false;
}

export function getDouJun(zidou, yearzi){
	if(DiZiMap.size === 0){
		for(let i=0; i<DiZi.length; i++){
			DiZiMap.set(DiZi[i], i);
		}
	}
	let ziidx = DiZiMap.get(zidou);
	let yearziIdx = DiZiMap.get(yearzi);

	let idx = (ziidx + yearziIdx) % 12;
	return DiZi[idx];
}

// ===== 运限流曜（前端本地计算，与后端 ZiWeiLuck 同源；避免每次点击都打后端） =====
// 年干系：流禄存/流擎羊(禄前一)/流陀罗(禄后一)/流天魁/流天钺  （取自 ziweiyeargan.json）
const FlowLuStorePos = { '甲':'寅','乙':'卯','丙':'巳','丁':'午','戊':'巳','己':'午','庚':'申','辛':'酉','壬':'亥','癸':'子' };
const FlowKuiPos = { '甲':'丑','乙':'子','丙':'亥','丁':'亥','戊':'丑','己':'子','庚':'丑','辛':'午','壬':'卯','癸':'卯' };
const FlowYuePos = { '甲':'未','乙':'申','丙':'酉','丁':'酉','戊':'未','己':'申','庚':'未','辛':'寅','壬':'巳','癸':'巳' };
// 流昌/流曲：干系（与 ziweiliuchangqu.json 一致）
const FlowChangPos = { '甲':'巳','乙':'午','丙':'申','丁':'酉','戊':'申','己':'酉','庚':'亥','辛':'子','壬':'寅','癸':'卯' };
const FlowQuPos = { '甲':'酉','乙':'申','丙':'午','丁':'巳','戊':'午','己':'巳','庚':'寅','辛':'丑','壬':'戌','癸':'亥' };
// 流马：年支三合（申子辰马在寅、寅午戌马在申、巳酉丑马在亥、亥卯未马在巳）
const FlowMaPos = { '子':'寅','丑':'亥','寅':'申','卯':'巳','辰':'寅','巳':'亥','午':'申','未':'巳','申':'寅','酉':'亥','戌':'申','亥':'巳' };

// 返回某天干/地支的全套流曜 [{name, zhi}]
export function getFlowStars(gan, zhi){
	const out = [];
	const lu = FlowLuStorePos[gan];
	if(lu){
		out.push({ name: '流禄', zhi: lu });
		const li = getHouseZiIndex(lu);
		if(li !== undefined && li !== null){
			out.push({ name: '流羊', zhi: DiZi[(li + 1) % 12] });
			out.push({ name: '流陀', zhi: DiZi[(li + 11) % 12] });
		}
	}
	if(FlowKuiPos[gan]) out.push({ name: '流魁', zhi: FlowKuiPos[gan] });
	if(FlowYuePos[gan]) out.push({ name: '流钺', zhi: FlowYuePos[gan] });
	if(FlowChangPos[gan]) out.push({ name: '流昌', zhi: FlowChangPos[gan] });
	if(FlowQuPos[gan]) out.push({ name: '流曲', zhi: FlowQuPos[gan] });
	if(zhi && FlowMaPos[zhi]) out.push({ name: '流马', zhi: FlowMaPos[zhi] });
	return out;
}

// 干支地支 → 本命宫 index（houses[i] 地支 = DiZi[i]）
export function ziToHouseIndex(zhi){
	return getHouseZiIndex(zhi);
}

// P1-C 流年「将前十二神 / 岁前十二神」（按流年支起，纯地支表；仅流年层用）。
// 将前：将星按年支三合定位（申子辰→子、寅午戌→午、巳酉丑→酉、亥卯未→卯），其后顺行 12 神。
// 岁前：岁建=流年支本位（太岁位），顺行 12 神。
const FLOW_JIANG_ORDER = ['将星', '攀鞍', '岁驿', '息神', '华盖', '劫煞', '灾煞', '天煞', '指背', '咸池', '月煞', '亡神'];
const FLOW_SUI_ORDER = ['岁建', '晦气', '丧门', '贯索', '官符', '小耗', '岁破', '龙德', '白虎', '天德', '吊客', '病符'];
const FLOW_JIANG_START = {
	'申': '子', '子': '子', '辰': '子',
	'寅': '午', '午': '午', '戌': '午',
	'巳': '酉', '酉': '酉', '丑': '酉',
	'亥': '卯', '卯': '卯', '未': '卯',
};
export function getFlowJiangSui(zhi){
	const out = [];
	if(!zhi){
		return out;
	}
	const jStart = DiZi.indexOf(FLOW_JIANG_START[zhi]);
	if(jStart >= 0){
		for(let i=0; i<12; i++){
			out.push({ name: '流' + FLOW_JIANG_ORDER[i], zhi: DiZi[(jStart + i) % 12], group: 'jiang' });
		}
	}
	const ziIdx = DiZi.indexOf(zhi);
	if(ziIdx >= 0){
		for(let i=0; i<12; i++){
			out.push({ name: '流' + FLOW_SUI_ORDER[i], zhi: DiZi[(ziIdx + i) % 12], group: 'sui' });
		}
	}
	return out;
}

// 某天干在该命盘上的四化落宫：返回 [{star,hua,houseIndex}]
export function getLayerSihua(chartObj, gan){
	const res = [];
	if(!chartObj || !gan){
		return res;
	}
	const ganhua = ZWConst.getActiveSiHuaGan()[gan];
	if(!ganhua){
		return res;
	}
	const huaNames = ZWConst.SiHua.hua; // [禄,权,科,忌]
	const houses = chartObj.houses || [];
	for(let h=0; h<4; h++){
		const starName = ganhua[h];
		let houseIndex = -1;
		for(let i=0; i<houses.length; i++){
			const groups = ['starsMain','starsAssist','starsEvil','starsOthersGood','starsOthersBad','starsSmall','stars'];
			let found = false;
			for(const key of groups){
				const arr = houses[i] && houses[i][key] ? houses[i][key] : [];
				if(arr.some((s)=> (typeof s === 'string' ? s : (s && s.name)) === starName)){
					found = true;
					break;
				}
			}
			if(found){ houseIndex = i; break; }
		}
		res.push({ star: starName, hua: huaNames[h], houseIndex });
	}
	return res;
}

// 运限三方四正: 给定运命宫索引, 返回三合两宫索引 [运财帛宫, 运官禄宫]
// 🔴 方向铁律:紫微十二宫自命宫沿地支**逆行**排布(命→兄→夫→子→财→疾→迁→友→官→田→福→父),
//   chart.houses 数组按地支固定序(子=0..亥=11)⇒ 传统宫序 = 数组 index **递减**方向。
//   因此 财帛 = 命−4 ≡ (命+8)%12、迁移 = 命±6、官禄 = 命−8 ≡ (命+4)%12。
//   与 ZWChart 主盘「运X」角标(delta = dirIndex − i)/ luckRoleChar / ZWCenterHouse.drawSangheLine
//   (caiIdx=fromIdx−4 / guanIdx=fromIdx+4)三处正确参照同口径。
//   历史 bug:曾误当 index 递增 = 传统序写成 财=+4/官=+8,恰好整体对调(右栏「运限三合」与
//   AI 挂载的运财帛/运官禄互换)——jest 一致性测试 + 发布自检哨兵 双守卫,勿再反向。
// 本宫和对宫已在 head 行("命宫【X】·对宫【Y】"),三方四正块只补两个三合宫即可,不重复。
export function getSanheIndices(mingIdx){
	if(typeof mingIdx !== 'number' || mingIdx < 0) return [];
	const idx = ((mingIdx % 12) + 12) % 12;
	const caibo = (idx + 8) % 12;    // 运财帛宫(= 命−4,地支逆行 4 宫)
	const guanlu = (idx + 4) % 12;   // 运官禄宫(= 命−8,地支逆行 8 宫)
	return [caibo, guanlu];
}

// 收集某宫位的所有星曜(主/辅/煞/桃花/杂等),返回数组
export function collectAllStars(house){
	if(!house) return [];
	const groups = ['starsMain','starsAssist','starsEvil','starsOthersGood','starsOthersBad','starsSmall','stars'];
	const collected = [];
	groups.forEach((key)=>{
		const arr = house[key] || [];
		arr.forEach((s)=>{
			const name = typeof s === 'string' ? s : (s && s.name);
			if(name && !collected.includes(name)) collected.push(name);
		});
	});
	return collected;
}

// 运限三合两宫 (运财帛宫 + 运官禄宫): 返回 [{runName, palaceName, ganZhi, stars}, ...]
// runName 是该宫在当前运限下的身份(运财帛/运官禄), palaceName 是它在原命盘上的本名(如疾厄宫/兄弟宫)
// 用于运限快照写入 + UI 渲染 + AI 报告 prompt
export function collectSanhePalaces(chart, mingIdx){
	if(!chart || !chart.houses || typeof mingIdx !== 'number') return [];
	const [caiboIdx, guanluIdx] = getSanheIndices(mingIdx);
	const buildOne = (runName, i)=>{
		const h = chart.houses[i] || {};
		return {
			runName,
			palaceName: h.name || h.houseName || '',
			ganZhi: h.ganzi || h.ganZhi || h.gan_zhi || '',
			houseIndex: i,
			stars: collectAllStars(h),
		};
	};
	return [
		buildOne('运财帛宫', caiboIdx),
		buildOne('运官禄宫', guanluIdx),
	];
}

// 旧 API 保留兼容(若有外部调用), 但弃用 - 新代码用 collectSanhePalaces
export function collectFourPalaceStars(chart, mingIdx){
	return collectSanhePalaces(chart, mingIdx);
}
export function getTripleIndices(mingIdx){
	return getSanheIndices(mingIdx);
}

// ===== 运限渲染纯函数（需求3/5；与大限「运X」同口径，可测） =====
// 某宫(houseIndex)在某运限层(命宫=layerMingIndex)下的角色字：与 ZWChart 大限 dirname 同算法
// (delta=层命宫-本宫; 角色=ZWHouses[(delta%12+12)%12])，取宫名首字（命/兄/夫/子/财/疾/迁/友/官/田/福/父）。
export function luckRoleChar(layerMingIndex, houseIndex){
	if(layerMingIndex === undefined || layerMingIndex === null || houseIndex === undefined || houseIndex === null){
		return '';
	}
	const idx = (((layerMingIndex - houseIndex) % 12) + 12) % 12;
	const name = ZWConst.ZWHouses[idx] || '';
	let ch = name.charAt(0);
	if(ch === '交'){ ch = '友'; } // 交友宫简写「友」(与大限运X同口径，避免与「子/财」等单字混淆)
	return ch;
}

// 有序活跃运限层（浅→深）：本命恒在；大限/流年小限/流月/流日/流时 选中才在。
// 每层 {key, gan, mingIndex, prefix}（本命 prefix=null/mingIndex=null）。供四化滑窗 + 标签 + 快照同源。
export function buildLuckLayers(sel, yearGan){
	const layers = [{ key: 'benming', gan: yearGan || '', mingIndex: null, prefix: null }];
	if(!sel){
		return layers;
	}
	if(sel.daxian) layers.push({ key: 'daxian', gan: sel.daxian.gan, mingIndex: sel.daxian.mingIndex, prefix: ZWConst.ZWPeriodPrefix.daxian });
	if(sel.liunian) layers.push({ key: 'liunian', gan: sel.liunian.gan, mingIndex: sel.liunian.mingIndex, prefix: ZWConst.ZWPeriodPrefix.liunian });
	if(sel.liuyue) layers.push({ key: 'liuyue', gan: sel.liuyue.gan, mingIndex: sel.liuyue.mingIndex, prefix: ZWConst.ZWPeriodPrefix.liuyue });
	if(sel.liuri) layers.push({ key: 'liuri', gan: sel.liuri.gan, mingIndex: sel.liuri.mingIndex, prefix: ZWConst.ZWPeriodPrefix.liuri });
	if(sel.liushi) layers.push({ key: 'liushi', gan: sel.liushi.gan, mingIndex: sel.liushi.mingIndex, prefix: ZWConst.ZWPeriodPrefix.liushi });
	return layers;
}

// 四化滑窗：取活跃层末 3 层；仅当只剩本命(=未选任何运限)时显示自化（腾位给运限层）。
// 无→[本命]+自化; 大限→[本命,大限]; 流年→[本命,大限,流年]; 流月→[大限,流年,流月]; 流日→[流年,流月,流日]; 流时→[流月,流日,流时]。
export function luckSihuaWindow(sel, yearGan){
	const layers = buildLuckLayers(sel, yearGan);
	return { layers: layers.slice(-3), showZihua: layers.length === 1 };
}

// 长生左侧运限标签层：仅 流年小限/流月/流日/流时（大限「运X」已在宫顶，本命不画）。
export function luckLabelLayers(sel){
	const out = [];
	if(!sel){
		return out;
	}
	if(sel.liunian) out.push({ key: 'liunian', prefix: ZWConst.ZWPeriodPrefix.liunian, mingIndex: sel.liunian.mingIndex });
	if(sel.liuyue) out.push({ key: 'liuyue', prefix: ZWConst.ZWPeriodPrefix.liuyue, mingIndex: sel.liuyue.mingIndex });
	if(sel.liuri) out.push({ key: 'liuri', prefix: ZWConst.ZWPeriodPrefix.liuri, mingIndex: sel.liuri.mingIndex });
	if(sel.liushi) out.push({ key: 'liushi', prefix: ZWConst.ZWPeriodPrefix.liushi, mingIndex: sel.liushi.mingIndex });
	return out;
}

// 最深选中层的命宫 index（驱动盘面金框高亮）；无选中 → null。
export function luckDeepestMingIndex(sel){
	if(!sel){
		return null;
	}
	const d = sel.liushi || sel.liuri || sel.liuyue || sel.liunian || sel.daxian || null;
	return d && (d.mingIndex !== undefined && d.mingIndex !== null) ? d.mingIndex : null;
}