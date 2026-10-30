// 六壬页 · 盘面数据:出生草稿序列化、生效出生资料、事盘性别、本命行年、缓存、四课 / 三传数据、盘面 / 三传 / 岁煞 / 长生表格行。
// 只被 components/lrzhan/LiuRengMain.js 与同目录 main/ 下的兄弟模块引用。
import * as LRConst from '../../liureng/LRConst.js';
import { ZSList, ZhangSheng } from '../../liureng/LRZhangSheng.js';
import ChuangChart from '../../liureng/ChuangChart.js';
// headless stub：DateTime 只在 UI 草稿恢复链（deserializeBirthDraft → buildBirthFields → cloneDateTimeSafe）里用，
// 该链不被任何 headless 导出调用；真被调到时构造即抛明确错误，而不是被 try/catch 吞掉的 ReferenceError。
class DateTime { constructor(){ throw new Error('headless stub: components/comp/DateTime is not vendored'); } }
import { caseGenderValue } from '../../utils/kentangCaseSave.js';
import { buildBirthFields, fmtValue, getSolarYearFromField } from './birthRunYear.js';
import { extractSingleBranch } from './ganzhiHelpers.js';

// 出生档序列化(存案 payload 用):date/time 取 'YYYY-MM-DD HH:mm:ss' 字符串,其余标量原样。
export function serializeBirthDraft(birth){
	if(!birth || !birth.date || !birth.date.value || typeof birth.date.value.format !== 'function'){ return null; }
	const v = (k)=>(birth[k] && birth[k].value !== undefined ? birth[k].value : undefined);
	const timeVal = birth.time && birth.time.value && typeof birth.time.value.format === 'function' ? birth.time.value : birth.date.value;
	return {
		date: birth.date.value.format('YYYY-MM-DD'),
		time: timeVal.format('HH:mm:ss'),
		ad: v('ad'), zone: v('zone'), lat: v('lat'), lon: v('lon'), gpsLat: v('gpsLat'), gpsLon: v('gpsLon'),
		gender: v('gender'), after23NewDay: v('after23NewDay'), lateZiHourUseNextDay: v('lateZiHourUseNextDay'),
	};
}
export function deserializeBirthDraft(raw){
	if(!raw || typeof raw !== 'object' || !raw.date){ return null; }
	try{
		const dt = new DateTime();
		dt.parse(`${raw.date} ${raw.time || '00:00:00'}`, 'YYYY-MM-DD HH:mm:ss');
		if(raw.zone){ dt.setZone(raw.zone); }
		if(raw.ad !== undefined && raw.ad !== null){ dt.ad = Number(raw.ad) === -1 ? -1 : 1; }
		const f = (val)=>({ value: val });
		return buildBirthFields({
			date: f(dt.clone()), time: f(dt.clone()),
			ad: raw.ad !== undefined ? f(raw.ad) : undefined, zone: raw.zone ? f(raw.zone) : undefined,
			lat: raw.lat ? f(raw.lat) : undefined, lon: raw.lon ? f(raw.lon) : undefined,
			gpsLat: raw.gpsLat !== undefined ? f(raw.gpsLat) : undefined, gpsLon: raw.gpsLon !== undefined ? f(raw.gpsLon) : undefined,
			gender: raw.gender !== undefined ? f(raw.gender) : undefined,
			after23NewDay: raw.after23NewDay !== undefined ? f(raw.after23NewDay) : undefined,
			lateZiHourUseNextDay: raw.lateZiHourUseNextDay !== undefined ? f(raw.lateZiHourUseNextDay) : undefined,
		}, new DateTime());
	}catch(e){ return null; }
}

export function getAppliedBirth(state){
	if(state && state.calcBirth){
		return state.calcBirth;
	}
	return state ? state.birth : null;
}

// 事盘 record.gender 单源=卜卦人性别(与盘面/行年/快照同一来源);卜卦人未填(未知/-1)才回落起课区全局值。
export function liurengCaseGender(birth, fields){
	const g = birth && birth.gender ? birth.gender.value : null;
	if(g === 0 || g === 1 || g === '0' || g === '1'){ return Number(g); }
	return caseGenderValue(fields);
}

// 六壬 本命支(命主出生年支,按公历年取年支) + 行年支 —— 第九~十二客 / 本命·行年加时 用;缺则空串(computeQiXY 退回默认)。
export function liurengBenmingXingnian(birth, runyear){
	const by = getSolarYearFromField(birth && birth.date ? birth.date : null);
	const benmingZhi = Number.isFinite(by) ? (LRConst.ZiList[(((by - 4) % 12) + 12) % 12] || '') : '';
	const xingnianZhi = extractSingleBranch(runyear && runyear.year ? runyear.year : '');
	return { benmingZhi, xingnianZhi };
}

export function clonePlain(obj){
	if(obj === undefined || obj === null){
		return obj;
	}
	try{
		return JSON.parse(JSON.stringify(obj));
	}catch(e){
		return obj;
	}
}

export function buildCacheKey(obj){
	try{
		return JSON.stringify(obj || {});
	}catch(e){
		return '';
	}
}

export function pushCache(map, key, val, max = 96){
	if(!map || !key || val === undefined || val === null){
		return;
	}
	if(map.has(key)){
		map.delete(key);
	}
	map.set(key, val);
	if(map.size > max){
		const first = map.keys().next().value;
		if(first){
			map.delete(first);
		}
	}
}

export function buildKeData(layout, chartObj){
	const result = {
		raw: [],
		lines: [],
	};
	if(!layout || !chartObj || !chartObj.nongli || !chartObj.nongli.dayGanZi){
		return result;
	}
	const dayGanZi = chartObj.nongli.dayGanZi;
	const daygan = dayGanZi.substr(0, 1);
	const dayzi = dayGanZi.substr(1, 1);

	const idx1 = layout.downZi.indexOf(LRConst.GanJiZi[daygan]);
	if(idx1 < 0){
		return result;
	}
	const ke1zi = layout.upZi[idx1];
	const ke1 = [layout.houseTianJiang[idx1], ke1zi, daygan];

	const idx2 = layout.downZi.indexOf(ke1zi);
	const ke2zi = idx2 >= 0 ? layout.upZi[idx2] : '';
	const ke2 = [idx2 >= 0 ? layout.houseTianJiang[idx2] : '', ke2zi, ke1zi];

	const idx3 = layout.downZi.indexOf(dayzi);
	const ke3zi = idx3 >= 0 ? layout.upZi[idx3] : '';
	const ke3 = [idx3 >= 0 ? layout.houseTianJiang[idx3] : '', ke3zi, dayzi];

	const idx4 = layout.downZi.indexOf(ke3zi);
	const ke4zi = idx4 >= 0 ? layout.upZi[idx4] : '';
	const ke4 = [idx4 >= 0 ? layout.houseTianJiang[idx4] : '', ke4zi, ke3zi];

	const all = [ke1, ke2, ke3, ke4];
	const names = ['一课', '二课', '三课', '四课'];
	all.forEach((item, idx)=>{
		result.lines.push(`${names[idx]}：地盘=${item[2]}，天盘=${item[1]}，贵神=${item[0]}`);
	});
	result.raw = all;
	return result;
}

export function buildSanChuanData(layout, keRaw, chartObj, castOverride){
	if(!layout || !keRaw || keRaw.length !== 4 || !chartObj || !chartObj.nongli){
		return null;
	}
	try{
		const helper = new ChuangChart({
			owner: null,
			chartObj: chartObj,
			nongli: chartObj.nongli,
			ke: keRaw,
			seHaiOpts: castOverride ? castOverride.seHaiOpts : null,
			liuRengChart: {
				upZi: layout.upZi,
				downZi: layout.downZi,
				houseTianJiang: layout.houseTianJiang,
			},
			x: 0,
			y: 0,
			width: 0,
			height: 0,
		});
		helper.genCuangs();
		return helper.cuangs || null;
	}catch(e){
		return null;
	}
}

// ---- AI 快照·段内容行 builder(纯函数,导出供证明测试)：段头 [X] 仍由 buildLiuRengSnapshotText 内联推入 ----
// GFM 表化(段内排版,值零变化):事实 token 与旧「行式」逐字同,仅列结构化,fact-multiset 证明见
// liurengSnapshotTables.test.js。空值 cell 统一 '—'(旧式无空值路径的沿用原字面,如 '无')。
// [十二地盘/十二天盘/十二贵神对应] 内容行 → | 序 | 地盘 | 天盘 | 贵神 |。
export function buildLiuRengPanRows(layout){
	const rows = [];
	rows.push('| 序 | 地盘 | 天盘 | 贵神 |');
	rows.push('| --- | --- | --- | --- |');
	for(let i=0; i<12; i++){
		rows.push(`| ${i + 1} | ${layout.downZi[i] || '—'} | ${layout.upZi[i] || '—'} | ${layout.houseTianJiang[i] || '—'} |`);
	}
	return rows;
}

// [三传] 三行内容(课式行不在此,仍内联)→ | 传 | 干支 | 六亲 | 贵神 |;缺项沿用旧字面 '无'。
export function buildLiuRengSanChuanRows(sanChuan){
	const rows = [];
	rows.push('| 传 | 干支 | 六亲 | 贵神 |');
	rows.push('| --- | --- | --- | --- |');
	const names = ['初传', '中传', '末传'];
	for(let i=0; i<3; i++){
		const gz = sanChuan.cuang && sanChuan.cuang[i] ? sanChuan.cuang[i] : '无';
		const lq = sanChuan.liuQin && sanChuan.liuQin[i] ? sanChuan.liuQin[i] : '无';
		const gs = sanChuan.tianJiang && sanChuan.tianJiang[i] ? sanChuan.tianJiang[i] : '无';
		rows.push(`| ${names[i]} | ${gz} | ${lq} | ${gs} |`);
	}
	return rows;
}

// [岁煞] 内容行(LRConst.TaiSui 七煞序)→ | 神煞 | 值 |;缺值 fmtValue 已产 '无'。
export function buildLiuRengSuiShaRows(yearGods){
	const rows = [];
	rows.push('| 神煞 | 值 |');
	rows.push('| --- | --- |');
	LRConst.TaiSui.forEach((name)=>{
		rows.push(`| ${name} | ${fmtValue(yearGods[name])} |`);
	});
	return rows;
}

// [十二长生] 内容行(所选五行 × 十二位)→ | 长生位 | 地支 |。
export function buildLiuRengZhangShengRows(zhangshengElem){
	const rows = [];
	rows.push('| 长生位 | 地支 |');
	rows.push('| --- | --- |');
	ZSList.forEach((item)=>{
		const key = `${zhangshengElem}_${item}`;
		rows.push(`| ${item} | ${fmtValue(ZhangSheng.wxphase[key])} |`);
	});
	return rows;
}
