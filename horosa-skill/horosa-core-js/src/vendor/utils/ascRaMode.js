// 赤道类盘「上升起盘」的上升取法(两档,改进为缺省)—— 宿占 / 二十八宿宿盘、节气页内嵌宿盘、七政赤仪、三式外圈赤道分宫共用。
//
// 由来:后端四轴的赤经此前不是真值 —— 上升点的 ra 实为「东点的黄经」(赤道上升点,与赤经不同系)。现在 ra 改成
// 黄道上升点的真赤经,旧值单独作为上升点对象的 eastPointLon 下发(只有上升点有)。用上升点赤经定命宫 / 画上升的盘
// 因此要表态取哪一个:
//   改进(缺省)= 上升点按自身真赤经落座,与行星、宫头同一坐标;
//   经典       = 沿用旧版取的东点黄经(两个量不同系,中纬度常差几度,命宫可能换座)。缺这个字段的老响应回落 ra。
// 只换上升点一个对象的 ra,其余对象原样;换出来的盘按 (盘, 档) 记住,同一张盘重画不另起新对象(重绘签名守卫按引用比)。
import { definePageSettings } from './pageSettingsStore.js';

export const ASC_RA_MODE_IMPROVED = 'improved';
export const ASC_RA_MODE_CLASSIC = 'classic';
export const ASC_RA_MODE_DEFAULT = ASC_RA_MODE_IMPROVED;
export const ASC_RA_MODE_OPTIONS = [
	{ value: ASC_RA_MODE_IMPROVED, label: '改进（真赤经）' },
	{ value: ASC_RA_MODE_CLASSIC, label: '经典（东点黄经）' },
];
const ASC_RA_MODE_VALUES = ASC_RA_MODE_OPTIONS.map((o)=>o.value);
const ASC_ID = 'Asc';

export function normalizeAscRaMode(v){
	return v === ASC_RA_MODE_CLASSIC ? ASC_RA_MODE_CLASSIC : ASC_RA_MODE_IMPROVED;
}

function finiteNum(v){
	if(v === undefined || v === null || v === ''){ return null; }
	const n = Number(v);
	return Number.isFinite(n) ? n : null;
}

// 上升点(或任意对象)按所选档取的赤经:经典且有 eastPointLon → 它;否则 ra。
export function ascRaOf(obj, mode){
	if(!obj){ return null; }
	if(normalizeAscRaMode(mode) === ASC_RA_MODE_CLASSIC){
		const east = finiteNum(obj.eastPointLon);
		if(east !== null){ return east; }
	}
	return finiteNum(obj.ra);
}

// 本盘的上升点经典档是否真有旧值可取(老响应没有 eastPointLon → 经典档实际回落真赤经,快照照实写)
export function chartHasEastPoint(chart){
	const objs = chart && Array.isArray(chart.objects) ? chart.objects : [];
	const asc = objs.find((o)=>o && o.id === ASC_ID);
	return !!asc && finiteNum(asc.eastPointLon) !== null;
}

const CLASSIC_MEMO = new WeakMap();
// 经典档:返回一张只把上升点 ra 换成东点黄经的浅拷贝盘(objects 换新数组,上升点换新对象,其余对象同引用);
// 改进档 / 盘上没有 eastPointLon / 两值相同 → 原样返回同一个对象。
export function withAscRaMode(chart, mode){
	if(!chart || typeof chart !== 'object' || normalizeAscRaMode(mode) !== ASC_RA_MODE_CLASSIC){ return chart; }
	if(CLASSIC_MEMO.has(chart)){ return CLASSIC_MEMO.get(chart); }
	const objs = Array.isArray(chart.objects) ? chart.objects : null;
	const idx = objs ? objs.findIndex((o)=>o && o.id === ASC_ID) : -1;
	let out = chart;
	if(idx >= 0){
		const asc = objs[idx];
		const east = finiteNum(asc.eastPointLon);
		if(east !== null && east !== finiteNum(asc.ra)){
			const nextObjs = objs.slice();
			nextObjs[idx] = { ...asc, ra: east };
			// objectMap 是部分画盘类的懒缓存(按 id 记对象,有就直接用):换了上升点就不能沿用旧表 —— 拿掉,画盘时按新 objects 重建
			const { objectMap: _staleMap, ...rest } = chart;
			out = { ...rest, objects: nextObjs };
		}
	}
	CLASSIC_MEMO.set(chart, out);
	return out;
}

// 盘根对象(含 chart 子对象)的同款换法:{ ...root, chart: withAscRaMode(root.chart) },按 (根, 档) 记住。
const ROOT_MEMO = new WeakMap();
export function withAscRaModeRoot(root, mode){
	if(!root || typeof root !== 'object' || !root.chart || normalizeAscRaMode(mode) !== ASC_RA_MODE_CLASSIC){ return root; }
	if(ROOT_MEMO.has(root)){ return ROOT_MEMO.get(root); }
	const chart = withAscRaMode(root.chart, mode);
	const out = chart === root.chart ? root : { ...root, chart };
	ROOT_MEMO.set(root, out);
	return out;
}

// 快照 / 导出里写明用的哪一档(经典档但本盘没有旧值时照实写「回落」)
export function ascRaModeSnapshotLine(mode, chart){
	const m = normalizeAscRaMode(mode);
	if(m === ASC_RA_MODE_CLASSIC){
		const fallback = chart && !chartHasEastPoint(chart);
		return `上升取法：经典(东点黄经,旧版口径)${fallback ? ';本盘未带东点黄经,实际按真赤经' : ''}`;
	}
	return '上升取法：改进(上升点真赤经,与行星、宫头同一坐标)';
}

const ASC_RA_MODE_SPEC = { label: '上升取法', def: ASC_RA_MODE_DEFAULT, oneOf: ASC_RA_MODE_VALUES };

// 宿占(含二十八宿宿盘、节气页内嵌宿盘):只在「人事十二宫 = ASC 起盘」时起作用、才显示。
// 读在宿占左栏构造时与画盘 / 快照时,写在左栏下拉的亲手改动里;节气页内嵌的只读宿盘跟随这份设置、不写。
export const SUZHAN_ASC_SETTINGS = definePageSettings('horosa.suzhan.settings.v1', {
	ascRaMode: ASC_RA_MODE_SPEC,
});
export function loadSuzhanAscRaMode(){
	return normalizeAscRaMode(SUZHAN_ASC_SETTINGS.load().ascRaMode);
}

// 七政:只在赤仪(按赤经置宿的宿度制)时起作用、才显示 —— 黄仪各环取黄经,不读上升赤经。
// 读在七政左栏构造时与画盘 / 快照时,写在左栏下拉的亲手改动里(择日宿主内嵌的七政页只改本页、不写)。
export const GUOLAO_ASC_SETTINGS = definePageSettings('horosa.guolao.settings.v1', {
	ascRaMode: ASC_RA_MODE_SPEC,
});
export function loadGuolaoAscRaMode(){
	return normalizeAscRaMode(GUOLAO_ASC_SETTINGS.load().ascRaMode);
}
// 七政盘是否按赤仪显示(各环画赤经):单一真值 = chart.displayCoord(后端按宿度制宣告);
// 旧响应没有该字段时与七政盘面同一回退判据(只有恒星制郑式按黄经)。
export function guolaoEquatorialDisplay(chart){
	const coord = chart && chart.displayCoord;
	if(coord === 'equatorial'){ return true; }
	if(coord === 'ecliptic'){ return false; }
	const params = chart && chart.params ? chart.params : {};
	return !(Number(params.doubingSu28) === 4 || Number(params.guolaoZhengSidereal) === 1);
}
// 七政实际生效的上升取法:黄仪恒按改进(不读上升赤经);赤仪 = fields.ascRaMode(无头重算带进来时)优先,否则七政页保存值
export function guolaoAscRaModeOf(chart, fields){
	if(!guolaoEquatorialDisplay(chart)){ return ASC_RA_MODE_IMPROVED; }
	const f = fields && fields.ascRaMode ? fields.ascRaMode.value : undefined;
	if(f === ASC_RA_MODE_IMPROVED || f === ASC_RA_MODE_CLASSIC){ return f; }
	return loadGuolaoAscRaMode();
}
