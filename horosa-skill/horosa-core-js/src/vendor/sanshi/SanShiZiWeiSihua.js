



import { defaultAfter23NewDay, defaultLateZiHourUseNextDay } from '../bazi/dayBoundary.js';
import { getLayerSihua } from '../ziwei/ZiWeiHelper.js';
import { buildDaxianItems, buildLiunianItems, houseName } from '../ziwei/zwLuckItems.js';
import * as ZWConst from '../bazi/ZWConst.js';


// 紫微四化做进「三式合一」右栏:为三式起课时间取一张紫微盘,展示 生年 + 大运/流年 四化×落宫。
// 纯展示——复用紫微既有算法(getLayerSihua / ZWLuckPanel builders / ZWColor),不改紫微页、不触 AI 注册表。

function fv(fields, key, fb){
	return (fields && fields[key] && fields[key].value !== undefined && fields[key].value !== null) ? fields[key].value : fb;
}

function buildZiweiParams(fields){
	if(!fields || !fields.date || !fields.date.value || !fields.time || !fields.time.value){
		return null;
	}
	const timeAlg = fv(fields, 'timeAlg', 0);
	return {
		date: fields.date.value.format('YYYY-MM-DD'),
		time: fields.time.value.format('HH:mm:ss'),
		zone: fv(fields, 'zone', ''),
		lon: fv(fields, 'lon', ''),
		lat: fv(fields, 'lat', ''),
		gpsLat: fv(fields, 'gpsLat', ''),
		gpsLon: fv(fields, 'gpsLon', ''),
		gender: fv(fields, 'gender', 1),
		timeAlg: timeAlg === 1 ? 1 : 0,
		after23NewDay: defaultAfter23NewDay(),
		lateZiHourUseNextDay: defaultLateZiHourUseNextDay(),
	};
}

// 生年天干:盘 yearGan 优先,否则取年柱干支首字(天干无繁简问题)。
function pickYearGan(chart){
	if(!chart){ return ''; }
	if(chart.yearGan){ return `${chart.yearGan}`.charAt(0); }
	if(chart.nongli && chart.nongli.yearGanZi){ return `${chart.nongli.yearGanZi}`.charAt(0); }
	return '';
}

// [YA v42] AI 快照取数(供三式合一 buildSanShiUnitedSnapshotText 复用):与本 tab 完全同一套计算
// (pickYearGan/getLayerSihua/buildDaxianItems/buildLiunianItems/houseName),给定盘与当前大运/流年
// 选中下标,产出 生年/大运/流年 四化文本行;无盘或无四化返 [](调用方不产段,零回归)。纯函数,组件行为不变。
export function buildSanShiZiweiSihuaSnapshotLines(chart, daxianIdx, liunianIdx){
	if(!chart){
		return [];
	}
	// 单层四化行文案:与 renderHuaChips 芯片同构(化名+星名+·落宫短名)。
	const fmtRows = (gan)=>{
		const rows = gan ? (getLayerSihua(chart, gan) || []) : [];
		if(!rows.length){
			return '';
		}
		return rows.map((r)=>{
			const palace = r.houseIndex >= 0 ? houseName(chart, r.houseIndex, true) : '—';
			return `${r.hua}${r.star}·${palace}`;
		}).join('；');
	};
	const lines = [];
	const yearGan = pickYearGan(chart);
	const birthText = fmtRows(yearGan);
	if(birthText){
		lines.push(`◆ 生年四化（${yearGan}）：${birthText}`);
	}
	const daxianItems = buildDaxianItems(chart) || [];
	// 下标钳制与 render 同口径(选中项越界回退末项)。
	const dxIdx = Math.min(Math.max(0, daxianIdx || 0), Math.max(0, daxianItems.length - 1));
	const dx = daxianItems.length ? daxianItems[dxIdx] : null;
	if(dx){
		const dxText = fmtRows(dx.gan);
		if(dxText){
			lines.push(`◆ 大运四化（${dx.top}　${dx.ganzi}限）：${dxText}`);
		}
		const liunianItems = buildLiunianItems(chart, dx) || [];
		const lnIdx = Math.min(Math.max(0, liunianIdx || 0), Math.max(0, liunianItems.length - 1));
		const ln = liunianItems.length ? liunianItems[lnIdx] : null;
		if(ln){
			const lnText = fmtRows(ln.gan);
			if(lnText){
				lines.push(`◆ 流年四化（${ln.top}　${ln.ganzi}）：${lnText}`);
			}
		}
	}
	if(lines.length){
		lines.push(`四化随当前紫微流派（${ZWConst.ZWSchool ? ZWConst.ZWSchool.school : 'beipai'}）取表；按起课时间排盘。`);
	}
	return lines;
}
