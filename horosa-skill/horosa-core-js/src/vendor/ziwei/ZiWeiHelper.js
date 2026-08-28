
import * as ZWConst from '../bazi/ZWConst.js';
import * as TB from './data/ziweiTables.js';
import { xiaoxianClockwiseFor, xiaoxianAgesForHouse, isYangGan as coreIsYangGan } from './ziweiCore.js';
import { placeKuiYue } from './ziweiSchools.js';
import { placeHuoLing } from './ziweiSchools.js';
import * as __req0 from './ziweiOptions.js';

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
export function zwShowStarLight(){
	const v = localStorage.getItem('ziweiShowStarLight');
	return v === null ? true : v === '1'; // 默认开（=现状零回归；三合盘星名下庙旺标注）
}

// ===== [D1] 盘面显示开关族A(纯显示层:localStorage+bump 广播;默认值=现状零回归) =====
function lsFlag(key, dflt){
	let v = null;
	try{ v = localStorage.getItem(key); }catch(e){ /* SSR/隐私模式回落默认 */ }
	return v === null ? dflt : v === '1';
}
export function zwShowLaiyin(){ return lsFlag('ziweiShowLaiyin', true); }          // 来因标记,默认开
export function zwShowBodyPalace(){ return lsFlag('ziweiShowBodyPalace', true); }  // 身宫标记,默认开(两盘统一)
export function zwSixEvilBlack(){ return lsFlag('ziweiSixEvilBlack', false); }     // 六煞黑字,默认关
export function zwShowShaHuagai(){ return lsFlag('ziweiShowShaHuagai', true); }    // 华盖/劫煞/咸池,默认开
export function zwShowShaSande(){ return lsFlag('ziweiShowShaSande', true); }      // 天德/月德,默认开
export function zwShowShaTaizuo(){ return lsFlag('ziweiShowShaTaizuo', true); }    // 三台/八座/恩光/天贵,默认开
export function zwZihuaAlways(){ return lsFlag('ziweiZihuaAlways', false); }       // 自化常显,默认关
// [D2] 宫格增量信息族(默认全关=现状)
export function zwShowMingSihua(){ return lsFlag('ziweiShowMingSihua', false); }       // 命宫干四化徽
export function zwShowDaySihua(){ return lsFlag('ziweiShowDaySihua', false); }         // 日干四化徽
export function zwShowYearAges(){ return lsFlag('ziweiShowYearAges', false); }         // 流年岁数条
export function zwShowXiaoxianAges(){ return lsFlag('ziweiShowXiaoxianAges', false); } // 小限岁数条
export function zwShowXiaoxianLayer(){ return lsFlag('ziweiShowXiaoxianLayer', false); } // [D3] 小限叠宫层(盘上「限X」标签),默认关
export function zwShowSfszLine(){ return lsFlag('ziweiShowSfszLine', true); }      // [D4] 对宫指示线(点宫后中宫画被点宫↔对宫虚线),默认开(静态盘零变化)
export function zwCenterContent(){                                                  // [D4] 中宫内容:clean(默认现状)/bazi(四柱+主星要素)/full(全量)
	let v = null;
	try{ v = localStorage.getItem('ziweiCenterContent'); }catch(e){ /* noop */ }
	return v === 'bazi' || v === 'full' ? v : 'clean';
}

// [D2] 命宫干:命宫宫干首字(两盘 houses 结构同源;缺盘/缺宫返 null 不画=best-effort)。
export function mingGanOf(chartObj){
	try{
		const i = chartObj && chartObj.lifeHouseIndex;
		const gz = chartObj && chartObj.houses && chartObj.houses[i] && chartObj.houses[i].ganzi;
		return gz ? `${gz}`.charAt(0) : null;
	}catch(e){ return null; }
}
// [D2] 日干:本地盘 fourColumns 口径优先(晚子时进位正确),Java 盘 bazi 两路回落;全缺不画。
export function dayGanOf(chartObj){
	if(!chartObj){ return null; }
	try{
		const fc = chartObj.fourColumns && chartObj.fourColumns.day && (chartObj.fourColumns.day.ganzi || chartObj.fourColumns.day.ganZhi);
		if(fc){ return `${fc}`.charAt(0); }
	}catch(e){ /* fallthrough */ }
	try{
		if(chartObj.bazi && chartObj.bazi.dayGanZi){ return `${chartObj.bazi.dayGanZi}`.charAt(0); }
	}catch(e){ /* fallthrough */ }
	try{
		const gz = chartObj.bazi && chartObj.bazi.bazi && chartObj.bazi.bazi.day && chartObj.bazi.bazi.day.ganzi;
		if(gz){ return `${gz}`.charAt(0); }
	}catch(e){ /* fallthrough */ }
	return null;
}
// [D2] 流年岁列:宫支相对生年支的首轮虚岁,而后每 12 年一轮。count 默认 8(~百岁内)。
export function yearAgesOf(houseZhi, yearZi, count = 8){
	const hi = getHouseZiIndex(houseZhi);
	const yi = getHouseZiIndex(yearZi);
	if(hi === undefined || hi === null || yi === undefined || yi === null || hi < 0 || yi < 0){ return []; }
	const first = ((hi - yi) % 12 + 12) % 12 + 1;
	const out = [];
	for(let k = 0; k < count; k++){ out.push(first + k * 12); }
	return out;
}
// [B15b] 小限顺逆(chart 版包装,单一真值源=ziweiCore 纯函数):读 ZWEngineOptions.xiaoxianMode
// (挂载/导出期由 builder SWITCH_KEYS 临时覆盖,消费期现算天然跟随)。惰性 require 照 kuiYue 先例防加载序。
// 性别:Java 顶层 gender 三形态优先,裸本地引擎盘(assembleNatalChart 原始形状,仅 male bool)回退;
// 年干阴阳:yearGan 判定优先(两种盘原生都有;chart.yearPolar 仅 Java 顶层字段,裸本地盘缺)。
function chartMale(chart){
	if(chart && chart.gender !== undefined && chart.gender !== null){
		return chart.gender === 'Male' || chart.gender === 1 || chart.gender === '1';
	}
	return !!(chart && chart.male === true);
}
function chartYearYang(chart){
	if(chart && chart.yearGan){ return coreIsYangGan(chart.yearGan); }
	return !!(chart && chart.yearPolar === 'Positive');
}
function xiaoxianModeNow(){
	try{ return `${__req0.ZWEngineOptions.xiaoxianMode || '0'}`; }catch(e){ return '0'; }
}
export function xiaoxianClockwise(chart){
	if(!chart){ return true; }
	return xiaoxianClockwiseFor(xiaoxianModeNow(), chartMale(chart), chartYearYang(chart));
}
// [B15b] 某宫小限岁列(渲染期现算,随「小限顺逆」档跟随)。现算条件不足(缺盘/缺年支/缺宫支)返 null,
// 由消费端回退排盘期 smallDirection(排盘数据恒默认口径,仅作保底)。
export function xiaoxianAgesOf(chart, houseZhi, maxAge = 100){
	if(!chart || !chart.yearZi || !houseZhi){ return null; }
	const startZhi = TB.XIAOXIAN_START[chart.yearZi];
	if(!startZhi){ return null; }
	const ages = xiaoxianAgesForHouse(xiaoxianModeNow(), chartMale(chart), chartYearYang(chart), startZhi, houseZhi, maxAge);
	return ages.length ? ages : null;
}
// [D2] 岁数条排版:数列→空格串,超出截断加省略号(纯函数,金标锁)。
export function formatAgeStrip(ages, maxCount = 8){
	const arr = Array.isArray(ages) ? ages : [];
	if(!arr.length){ return ''; }
	const shown = arr.slice(0, maxCount);
	return shown.join(' ') + (arr.length > maxCount ? '…' : '');
}

// [D1] 六煞黑字:集合={擎羊陀罗火铃空劫};'天空'为空劫古名档(kongNaming=book)的地空显示名兜底。
// 仅煞曜组消费本函数——杂曜组的年支系天空走 Others 色不经此,天刑/天姚/咸池等保持煞曜红。
export const SIX_EVIL_NAMES = ['擎羊', '陀罗', '火星', '铃星', '地空', '地劫', '天空'];
export function colorForEvilStar(name){
	if(zwSixEvilBlack() && SIX_EVIL_NAMES.indexOf(name) >= 0){
		return ZWConst.ZWColor.StarSixEvilStroke;
	}
	return ZWConst.ZWColor.StarEvilStroke;
}

// [D1] 神煞三组显示过滤(纯显示层,列宽计算前调用;绝不动 chart 数据层)。
// 三开关默认全开→返回原引用=零开销零变化。同名双份(如年支系/月系重复)不去重,各自受同一开关辖。
const SHENSHA_G_HUAGAI = ['华盖', '劫煞', '咸池'];
const SHENSHA_G_SANDE = ['天德', '月德'];
const SHENSHA_G_TAIZUO = ['三台', '八座', '恩光', '天贵'];
export function filterShenshaForDisplay(arr){
	const dropHuagai = !zwShowShaHuagai();
	const dropSande = !zwShowShaSande();
	const dropTaizuo = !zwShowShaTaizuo();
	if(!dropHuagai && !dropSande && !dropTaizuo){ return arr; }
	return (arr || []).filter((s)=>{
		const n = s && s.name;
		if(!n){ return true; }
		if(dropHuagai && SHENSHA_G_HUAGAI.indexOf(n) >= 0){ return false; }
		if(dropSande && SHENSHA_G_SANDE.indexOf(n) >= 0){ return false; }
		if(dropTaizuo && SHENSHA_G_TAIZUO.indexOf(n) >= 0){ return false; }
		return true;
	});
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
// 🔴 [A5] 位置表单一真值:全部改读 data 表(禄存/魁钺=ziweiyeargan、昌曲=ziweiliuchangqu、
//    马=ziweiyearzi 年马行)——旧六份硬编副本已逐字节核对与表相等后消除;禁字面量表回潮。
//    流魁流钺过 placeKuiYue 随本命魁钺歌诀档同移(否则庚辛年切档后本命移了流魁没移=口径分叉)。
const flowGanPos = (star, gan) => {
	const def = TB.STARS_YEAR_GAN[star];
	return def && def.pos ? def.pos[gan] : undefined;
};
const flowMaPos = (zhi) => {
	const def = TB.STARS_YEAR_ZI['年马'];
	return def && def.pos ? def.pos[zhi] : undefined;
};
// [P3d] 流鸾/流喜:支系,公式与本命红鸾天喜同源(ziweiyearzi.json:红鸾=卯起子逆→支序(3−n+12)%12;天喜=对宫)。
const FlowLuanPos = (zhi)=>{ const n = DiZi.indexOf(zhi); return n < 0 ? null : DiZi[((3 - n) % 12 + 12) % 12]; };

// 返回某天干/地支的全套流曜 [{name, zhi}]。
// [P3d] flowLuanXi 开关(默认关):加流鸾/流喜两颗 —— 默认关的理由:getFlowStars 同时喂快照
// [运限] 流曜行,恒开会动 ziweiV2Baseline withPeriod 事实多重集(基线字节稳);开=显式选择。
// [B13] 盘上时辰支 best-effort:本地盘 chart.timeZi → Java 盘 bazi.bazi.time 支 → null(缺则流火铃不出)
export function hourZhiOf(chartObj){
	if(!chartObj){ return null; }
	if(chartObj.timeZi){ return chartObj.timeZi; }
	try{
		const gz = chartObj.bazi && chartObj.bazi.bazi && chartObj.bazi.bazi.time && chartObj.bazi.bazi.time.ganzi;
		if(gz && `${gz}`.length >= 2){ return `${gz}`.charAt(1); }
	}catch(e){ /* fallthrough */ }
	return null;
}
export function getFlowStars(gan, zhi, hourZhi){
	const out = [];
	const lu = flowGanPos('禄存', gan);
	if(lu){
		out.push({ name: '流禄', zhi: lu });
		const li = getHouseZiIndex(lu);
		if(li !== undefined && li !== null){
			out.push({ name: '流羊', zhi: DiZi[(li + 1) % 12] });
			out.push({ name: '流陀', zhi: DiZi[(li + 11) % 12] });
		}
	}
	// 流魁流钺随魁钺歌诀档(placeKuiYue delta;默认档返 null 落表)
	const kuiV = __req0.ZWEngineOptions.kuiYue;
	const kui = placeKuiYue('天魁', gan, kuiV) || flowGanPos('天魁', gan);
	const yue = placeKuiYue('天钺', gan, kuiV) || flowGanPos('天钺', gan);
	if(kui) out.push({ name: '流魁', zhi: kui });
	if(yue) out.push({ name: '流钺', zhi: yue });
	const chang = TB.STARS_LIU_CHANGQU['流昌'][gan];
	const qu = TB.STARS_LIU_CHANGQU['流曲'][gan];
	if(chang) out.push({ name: '流昌', zhi: chang });
	if(qu) out.push({ name: '流曲', zhi: qu });
	const ma = zhi ? flowMaPos(zhi) : undefined;
	if(ma) out.push({ name: '流马', zhi: ma });
	// [B13] 流年火铃:开关默认关;起法=本命火铃内核 placeHuoLing(流年支代年支+生时,nanpai 档语义自动继承)。
	// hourZhi 缺省不出两星=旧调用零回归。
	if(zhi && hourZhi && zwFlowHuoLingEnabled()){
		try{
			const hl = placeHuoLing(zhi, hourZhi, __req0.ZWEngineOptions.huoling);
			if(hl && hl['火星']){ out.push({ name: '流火', zhi: hl['火星'] }); }
			if(hl && hl['铃星']){ out.push({ name: '流铃', zhi: hl['铃星'] }); }
		}catch(e){ /* 内核缺位不阻断其余流曜 */ }
	}
	if(zhi && zwFlowLuanXiEnabled()){
		const luan = FlowLuanPos(zhi);
		if(luan){
			out.push({ name: '流鸾', zhi: luan });
			out.push({ name: '流喜', zhi: DiZi[(DiZi.indexOf(luan) + 6) % 12] });
		}
	}
	return out;
}
// [P3d] 开关读取(经 ZWEngineOptions 单例;require 防循环 import——ziweiOptions 零依赖纯常量,实际无环,双保险)
function zwFlowLuanXiEnabled(){
	try{ return !!__req0.ZWEngineOptions.flowLuanXi; }catch(e){ return false; }
}
function zwFlowHuoLingEnabled(){
	try{ return !!__req0.ZWEngineOptions.flowHuoLing; }catch(e){ return false; }
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

// [D3] 流年神煞上盘(BUG-H 方案:绘制期替换,零触 chart 数据层)。
// smalls 序恒 [博士系,将前系,岁前系] 三条(Java/本地引擎同序;P0-1 排法依据)——
// 开关开+有流年支时:博士保留,将前/岁前两条换成流年版(「流」前缀,getFlowJiangSui 落于本宫支者),
// 并携 natal 字段(被替换的本命神煞名)供 tooltip 对照。任何形状不符(≠3条)诚实降级返原引用。
export function resolveSmallStarsForDisplay(smalls, houseZhi, flowZhi){
	let on = false;
	try{ on = !!__req0.ZWEngineOptions.flowShenshaOnChart; }catch(e){ on = false; }
	if(!on || !flowZhi || !houseZhi || !Array.isArray(smalls) || smalls.length !== 3){
		return smalls;
	}
	const flow = getFlowJiangSui(flowZhi);
	const fj = flow.find((x)=>x.group === 'jiang' && x.zhi === houseZhi);
	const fs2 = flow.find((x)=>x.group === 'sui' && x.zhi === houseZhi);
	if(!fj || !fs2){
		return smalls;
	}
	return [
		smalls[0],
		{ name: fj.name, flow: true, natal: smalls[1] && smalls[1].name },
		{ name: fs2.name, flow: true, natal: smalls[2] && smalls[2].name },
	];
}

// [B10-fix] 运限层四化取干(消费期现算单源):流年层且档=ming_gong_gan → 流年命宫宫干;
// 其余层恒 layer.gan。此前把 sihuaGan 烙死在选择时的 item 快照上——切档后已选流年不追新、
// 切回默认还残留宫干(双向死开关体验)。三消费点(面板卡/快照行/盘面滑窗源头)统一走本函数。
export function effLayerSihuaGan(chartObj, layer){
	if(!layer){ return null; }
	const isLiunian = layer.level === 'liunian' || layer.key === 'liunian';
	if(isLiunian){
		let mode = 'year_gan';
		try{ mode = __req0.ZWEngineOptions.liunianSihuaGan || 'year_gan'; }catch(e){ /* 默认档 */ }
		if(mode === 'ming_gong_gan'){
			try{
				const i = layer.mingIndex;
				const gz = chartObj && chartObj.houses && chartObj.houses[i] && chartObj.houses[i].ganzi;
				if(gz){ return `${gz}`.charAt(0); }
			}catch(e){ /* 回落 */ }
		}
		return layer.gan;   // year_gan 档:显式忽略残留的 item.sihuaGan(切回默认必须立刻还原)
	}
	return layer.sihuaGan || layer.gan;
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
	if(sel.liunian) layers.push({ key: 'liunian', gan: sel.liunian.gan, sihuaGan: sel.liunian.sihuaGan, mingIndex: sel.liunian.mingIndex, prefix: ZWConst.ZWPeriodPrefix.liunian });
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
export function luckLabelLayers(sel, includeXiaoxian = false){
	const out = [];
	if(!sel){
		return out;
	}
	if(sel.liunian) out.push({ key: 'liunian', prefix: ZWConst.ZWPeriodPrefix.liunian, mingIndex: sel.liunian.mingIndex });
	// [D3] 小限叠宫层:仅 UI 显式开启才插(默认参 false=快照/挂载/既有调用零回归);金框语义不动(仍流年命宫)。
	if(includeXiaoxian && sel.xiaoxian) out.push({ key: 'xiaoxian', prefix: ZWConst.ZWPeriodPrefix.xiaoxian, mingIndex: sel.xiaoxian.mingIndex });
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