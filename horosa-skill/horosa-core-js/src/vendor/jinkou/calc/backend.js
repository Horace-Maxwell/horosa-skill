// 后端排盘结果归一与取盘
// 从 JinKouCalc.js 按职责拆出(门面保留原导入路径与对外导出;读源码的检查读「子模块 + 门面」全集,见 scripts/source-sets.json)。
import { parseDateTimeText, parseFieldsDateTime } from '../../utils/fieldsDateTime.js';


import { getYinYangSign, rowZhi } from './basics.js';
import { JinKouElementColor, JinKouYueJiangName } from './tables.js';
import { buildJinKouRelations, buildJinKouBihe, buildJinKouXiangyi, buildJinKouDong } from './readings.js';
import { buildJinKouBranchRelations, buildJinKouGeju, buildJinKouTaixuan, buildJinKouYongStrength, buildJinKouYingQi } from './layers.js';

function safeText(value){
	return value === undefined || value === null ? '' : `${value}`;
}

function resolveCalculationDateTime(fields, nongli, options){
	if(options && options.timeBasis === 'trueSolar'){
		return parseDateTimeText(nongli && nongli.birth) || parseFieldsDateTime(fields);
	}
	return parseFieldsDateTime(fields);
}

function cleanDisplay(value, def = '—'){
	const text = safeText(value).trim();
	if(!text || text === 'None'){
		return def;
	}
	return text;
}

function normalizeBackendRow(row, fallbackRow){
	const elem = cleanDisplay(row && row.element, '');
	const content = cleanDisplay(row && row.content, '—');
	// 阴阳列：后端有给则用后端，否则由四位定位干支(人元=天干、贵神/将神/地分=地支)现算，
	// 保证中间盘四位旁 +/- 列四行齐全(零回归：后端给值时不动)。
	const sign = cleanDisplay(row && row.sign, '') || getYinYangSign(content) || (fallbackRow ? cleanDisplay(fallbackRow.sign, '') : '');
	const season = cleanDisplay(row && row.season, '');
	const label = cleanDisplay(row && row.label, fallbackRow ? fallbackRow.label : '');
	return {
		...(fallbackRow || {}),
		label: label,
		gan: cleanDisplay(row && row.gan, '-'),
		content: content,
		shenjiang: cleanDisplay(row && row.shenjiang, '-'),
		// 力量列去掉阴阳符号(+/-)，阴阳改由中间盘四位旁的独立 +/- 列承担，避免「金-相」误读为减号
		power: cleanDisplay(row && row.power, elem || sign || season ? `${elem}${sign}${season}` : '—').replace(/[+\-−]/g, ''),
		// 先认后端本行的空亡，再回落本地 fallback —— 原先只认 fallback，
		// 无 liureng（只有后端盘）时四位空亡列恒「—」，后端算了也白算。
		kong: cleanDisplay(row && row.kong, '') || (fallbackRow && fallbackRow.kong ? fallbackRow.kong : '—'),
		elem: elem,
		sign: sign,
		season: season,
		nayin: cleanDisplay(row && row.nayin, ''),
		ganZhi: cleanDisplay(row && row.ganZhi, ''),
		branch: cleanDisplay(row && row.branch, ''),
		isYong: !!(row && row.isYong),
		contentColor: JinKouElementColor[elem] ? JinKouElementColor[elem] : '#262626',
		ganColor: JinKouElementColor[elem] ? JinKouElementColor[elem] : (fallbackRow ? fallbackRow.ganColor : '#262626'),
		powerColor: JinKouElementColor[elem] ? JinKouElementColor[elem] : '#262626',
	};
}

export function normalizeKinjinkouData(backendPan, fallbackData){
	if(!backendPan || !backendPan.rows){
		return fallbackData;
	}
	const fallback = fallbackData || {};
	const fallbackRows = fallback.rows || [];
	const rows = backendPan.rows.map((row, idx)=>normalizeBackendRow(row, fallbackRows[idx]));
	const yongRow = rows.find((row)=>row.isYong);
	// 解读层随「显示行(后端)」重算，避免与本地 fallback 行（月将/将神可能不同）不一致
	const reYongLabel = (yongRow && yongRow.label) || (backendPan.yongYao && backendPan.yongYao.label) || (fallback.yongYao && fallback.yongYao.label) || '';
	const reYongRow = reYongLabel ? rows.find((row)=>row.label === reYongLabel) : null;
	const reGuiRow = rows.find((row)=>row.label === '贵神');
	const reJiangRow = rows.find((row)=>row.label === '将神');
	const reJiangZhi = reJiangRow ? rowZhi(reJiangRow) : '';
	return {
		...fallback,
		ready: true,
		source: 'kinjinkou',
		backend: backendPan,
		diFen: cleanDisplay(backendPan.difen, fallback.diFen || '子'),
		timeZi: cleanDisplay(backendPan.zhanshi, fallback.timeZi || ''),
		yuejiang: cleanDisplay(backendPan.yuejiang, fallback.yuejiang || ''),
		xunKongBranches: fallback.xunKongBranches || [],
		siDaKong: cleanDisplay(backendPan.siDaKong, fallback.siDaKong || '无'),
		yongYao: {
			...(fallback.yongYao || {}),
			...(backendPan.yongYao || {}),
			label: yongRow ? yongRow.label : (backendPan.yongYao ? backendPan.yongYao.label : ''),
			sign: yongRow ? yongRow.sign : (backendPan.yongYao ? backendPan.yongYao.sign : ''),
		},
		rows: rows,
		relations: buildJinKouRelations(rows),
		bihe: buildJinKouBihe(rows),
		xiangyi: buildJinKouXiangyi(reGuiRow ? reGuiRow.shenjiang : '', JinKouYueJiangName[reJiangZhi] || ''),
		branchRelations: buildJinKouBranchRelations(rows, fallback.dayZi),
		dong: buildJinKouDong(rows, fallback.xunKongBranches, reYongLabel),
		geju: buildJinKouGeju(rows),
		taixuan: buildJinKouTaixuan(rows),
		yongStrength: reYongRow ? buildJinKouYongStrength({ label: reYongRow.label }, rows, fallback.wangShuai) : fallback.yongStrength,
		yingQi: buildJinKouYingQi({ yongRow: reYongRow, rows: rows, dayGan: fallback.dayGan, dayZi: fallback.dayZi, timeZi: fallback.timeZi, yearZi: fallback.yearZi, guiGan: reGuiRow ? reGuiRow.gan : fallback.guiGan, guiZi: reGuiRow ? rowZhi(reGuiRow) : fallback.guiZi, wangShuaiMap: fallback.wangShuai, xunKongBranches: fallback.xunKongBranches }),
		plates: backendPan.plates || [],
		sections: backendPan.sections || [],
		shenshaRows: fallback.shenshaRows || [],
		topInfo: {
			...(fallback.topInfo || {}),
			diFen: cleanDisplay(backendPan.difen, fallback.topInfo ? fallback.topInfo.diFen : '子'),
			xunKong: cleanDisplay(backendPan.xunKong, fallback.topInfo ? fallback.topInfo.xunKong : '无'),
			siDaKong: cleanDisplay(backendPan.siDaKong, fallback.topInfo ? fallback.topInfo.siDaKong : '无'),
			yuejiang: cleanDisplay(backendPan.yuejiang, ''),
			zhanshi: cleanDisplay(backendPan.zhanshi, ''),
		},
	};
}

