import { getLayerSihua } from '../vendor/ziwei/ZiWeiHelper.js';
import { houseName, buildDaxianItems, buildLiunianItems } from '../vendor/ziwei/zwLuckItems.js';
import * as ZWConst from '../vendor/bazi/ZWConst.js';

/**
 * 三式合一 [紫微四化] 段（生年 / 大运 / 流年 三层四化 × 落宫）。
 *
 * 上游由紫微子页签上报的 UI 状态驱动（盘 + 选中的大运/流年下标），tab 未打开过就整段不产。
 * headless 没有页签，故把同一份选择开成显式入参 `daxianIdx` / `liunianIdx`（缺省 0 = 首项，
 * 与上游「越界回退」的钳制口径一致）；紫微盘由 Python 按起课时间另取一张。
 *
 * 函数体逐字取自上游 SanShiZiWeiSihua.js。
 *
 * payload: { chart: <ziwei 盘>, daxianIdx?: number, liunianIdx?: number }
 * return : { text }
 */

function pickYearGan(chart){
	if(!chart){ return ''; }
	if(chart.yearGan){ return `${chart.yearGan}`.charAt(0); }
	if(chart.nongli && chart.nongli.yearGanZi){ return `${chart.nongli.yearGanZi}`.charAt(0); }
	return '';
}

function buildSanShiZiweiSihuaSnapshotLines(chart, daxianIdx, liunianIdx){
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

export function runSanshiZiweiSihua(payload) {
  const source = payload && typeof payload === 'object' ? payload : {};
  const chart = source.chart && typeof source.chart === 'object' ? source.chart : null;
  if (!chart) {
    return { text: '' };
  }
  try {
    const lines = buildSanShiZiweiSihuaSnapshotLines(chart, source.daxianIdx || 0, source.liunianIdx || 0) || [];
    return { text: lines.length ? ['[紫微四化]', ...lines].join('\n') : '' };
  } catch (error) {
    return { text: '' };
  }
}

export default runSanshiZiweiSihua;
