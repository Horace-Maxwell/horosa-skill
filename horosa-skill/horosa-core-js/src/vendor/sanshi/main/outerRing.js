// 三式合一页:外圈(星盘环)数据与布局、神煞表、宫位分段、四柱。
// 从 SanShiUnitedMain.js 按职责拆出(门面保留原导入路径与对外导出;读源码的检查读「子模块 + 门面」全集,见 scripts/source-sets.json)。
import { withAscRaMode, ascRaModeSnapshotLine } from '../../utils/ascRaMode.js';
import * as AstroConst from '../sanshiAstroConst.js';
import { splitDegree } from '../sanshiAstroHelper.js';
import { safe } from '../../dunjia/qimenPageShared.js';
import { appendPlanetHouseInfo } from '../../utils/planetHouseInfo.js';
import { BRANCH_ORDER, MAIN_STAR_IDS, AI_EXPORT_PLANET_INFO, SANSHI_PALACE_EXPORT_ORDER, BRANCH_ZODIAC_MAP } from './options.js';
import { resolveObjBranch, raToBranch, signToBranch, lonToBranch, parseHouseNum, normalizeLon, buildSanshiWeakSolid } from './liureng.js';
import { shortMainStarLabel, msg } from './format.js';

// ascRaMode:外圈赤道分宫时上升点的取法(经典档只把上升点 ra 换成东点黄经;黄道分宫不读上升赤经,恒原样)
export function buildOuterData(rawChartObj, coord, ascRaMode){
	const equatorial = coord === 'equatorial';
	const chartObj = equatorial ? withAscRaMode(rawChartObj, ascRaMode) : rawChartObj;
	const housesByBranch = {};
	const starsByBranch = {};
	const starsByBranchFull = {};
	const starsByBranchMeta = {};
	BRANCH_ORDER.forEach((b)=>{
		housesByBranch[b] = [];
		starsByBranch[b] = [];
		starsByBranchFull[b] = [];
		starsByBranchMeta[b] = [];
	});
	if(!chartObj){
		return { housesByBranch, starsByBranch, starsByBranchFull, starsByBranchMeta };
	}
	// 快照在第 1 宫那一支写明上升取法(只赤道分宫有这一行;黄道逐字现状)
	const ascRaLine = equatorial ? ascRaModeSnapshotLine(ascRaMode, chartObj) : '';
	const objs = chartObj.objects || [];
	let ascBranch = '';
	for(let i=0; i<objs.length; i++){
		const obj = objs[i];
		if(obj && obj.id === AstroConst.ASC){
			ascBranch = resolveObjBranch(obj, coord);
			break;
		}
	}
	const ascIdx = BRANCH_ORDER.indexOf(ascBranch);
	if(ascIdx >= 0){
		// 人事宫位：从上升1宫开始，逆时针排布
		for(let houseNo = 1; houseNo <= 12; houseNo++){
			const idx = (ascIdx - (houseNo - 1) + 12) % 12;
			housesByBranch[BRANCH_ORDER[idx]].push(`${houseNo}`);
		}
	}else{
		// 兜底：若ASC缺失则回退到按宫头经度映射
		const houses = chartObj.houses || [];
		houses.forEach((h)=>{
			const b = (coord === 'equatorial' && h && h.ra !== undefined && h.ra !== null && !Number.isNaN(parseFloat(h.ra)))
				? raToBranch(h.ra)
				: (signToBranch(h.sign) || lonToBranch(h.lon));
			if(!b){
				return;
			}
			const txt = parseHouseNum(h.id);
			if(txt && housesByBranch[b].indexOf(txt) < 0){
				housesByBranch[b].push(txt);
			}
		});
	}

	const starsByBranchRaw = {};
	BRANCH_ORDER.forEach((b)=>{ starsByBranchRaw[b] = []; });
	objs.forEach((obj)=>{
		if(!MAIN_STAR_IDS.has(obj.id)){
			return;
		}
		const b = resolveObjBranch(obj, coord);
		if(!b){
			return;
		}
		// 度数随坐标口径切换:赤道按赤经(ra)宫内度;黄道按 signlon(黄经宫内度)。
		// 否则切赤道仅地支重映射、度数/悬浮纹丝不动。
		const useEqua = coord === 'equatorial' && obj.ra !== undefined && obj.ra !== null && !Number.isNaN(parseFloat(obj.ra));
		const inSegDeg = useEqua ? (normalizeLon(obj.ra) % 30) : (obj.signlon || 0);
		const deg = splitDegree(inSegDeg);
		const retro = obj.lonspeed < 0 ? 'R' : '';
		const shortTxt = `${shortMainStarLabel(msg(obj.id))}${safe(deg[0], 0)}${retro}`;
		const starName = safe(appendPlanetHouseInfo(msg(obj.id), obj, AI_EXPORT_PLANET_INFO), '未知星曜');
		const minTxt = `${safe(deg[1], 0)}`.padStart(2, '0');
		const fullTxt = `${starName}${safe(deg[0], 0)}°${minTxt}${retro}${useEqua ? '（赤经）' : ''}`;
		starsByBranchRaw[b].push({
			shortTxt,
			fullTxt,
			deg: Number(inSegDeg) || 0,
			objId: obj.id,
		});
	});
	BRANCH_ORDER.forEach((b)=>{
		const sorted = starsByBranchRaw[b].sort((a, c)=>a.deg - c.deg);
		starsByBranch[b] = sorted.map((item)=>item.shortTxt);
		starsByBranchFull[b] = sorted.map((item)=>item.fullTxt);
		starsByBranchMeta[b] = sorted.map((item)=>({
			shortTxt: item.shortTxt,
			fullTxt: item.fullTxt,
			objId: item.objId,
		}));
	});
	return { housesByBranch, starsByBranch, starsByBranchFull, starsByBranchMeta, ...(ascRaLine ? { ascRaLine } : {}) };
}

export function buildShenShaMap(dunjia){
	const map = {};
	if(!dunjia || !dunjia.shenSha || !dunjia.shenSha.allItems){
		return map;
	}
	dunjia.shenSha.allItems.forEach((item)=>{
		map[item.name] = item.value;
	});
	// 兼容不同命名写法，避免取值缺失。
	if(!map.幕贵 && map.墓贵){
		map.幕贵 = map.墓贵;
	}
	if(!map.墓贵 && map.幕贵){
		map.墓贵 = map.幕贵;
	}
	return map;
}

export function appendSection(lines, title, bodyLines){
	lines.push(`【${title}】`);
	(bodyLines || []).forEach((line)=>{
		lines.push(`${line}`);
	});
	lines.push('');
}

function buildLiuRengBranchMap(lrLayout){
	const map = {};
	if(!lrLayout || !Array.isArray(lrLayout.downZi)){
		return map;
	}
	lrLayout.downZi.forEach((branch, idx)=>{
		map[branch] = {
			up: safe(lrLayout.upZi && lrLayout.upZi[idx], '—'),
			god: safe(lrLayout.houseTianJiang && lrLayout.houseTianJiang[idx], '—'),
		};
	});
	return map;
}

// 单一真值源:把独立技法 builder 产出的整篇快照(段头形如 [X])解析成「段名 → 正文行数组」的 Map,
// 供三式合一按需挑段并以 appendSection(【X】)重发。这样段内容 100% 来自独立 builder(零平行实现),
// 三式合一只做「选段 + 改前缀」。段头识别与 parseSectionTitleLine 同口径:整行 [X] 才算段头。
// 把独立 builder 整篇里的指定段,以「前缀 + 段名」重发到三式合一快照(单一真值源:正文照搬)。
// 仅在该段存在且有正文时输出(条件段天然豁免;空段不污染导出与导出设置勾选面)。
export function appendPickedSections(lines, sectionMap, titles, prefix){
	(titles || []).forEach((title)=>{
		const body = sectionMap[title];
		if(!body || !body.length){
			return;
		}
		appendSection(lines, `${prefix || ''}${title}`, body);
	});
}

// 八宫逐宫合成段(正北坎宫 … 西北乾宫):遁甲天 / 地盘干、八神、九星,逐支人事宫位、虚实、六壬天盘 / 神将、外圈星盘;
// 赤道分宫时第 1 宫那一支写上升取法。页面快照与无头 / 挂载重算共用这一个函数(同一盘逐字节相同)。
// 入参:dunjia(含 cells / ganzhi)、lrLayout(六壬天地盘)、outerData(buildOuterData 的结果,可空)。返回 [{ title, body }]。
export function buildSanshiPalaceSections({ dunjia, lrLayout, outerData }){
	const out = [];
	if(!dunjia){ return out; }
	const qimenMap = {};
	if(Array.isArray(dunjia.cells)){
		dunjia.cells.forEach((cell)=>{
			qimenMap[cell.palaceNum] = cell;
		});
	}
	const lrBranchMap = buildLiuRengBranchMap(lrLayout);
	// 与盘面同源:外圈虚实点按 buildSanshiWeakSolid(四柱地支定实 / 四柱旬空推虚)
	const weakSolidMap = (()=>{ try{ return buildSanshiWeakSolid(dunjia); }catch(e){ return null; } })();
	const starsByBranch = outerData && outerData.starsByBranchFull ? outerData.starsByBranchFull
		: (outerData && outerData.starsByBranch ? outerData.starsByBranch : {});
	SANSHI_PALACE_EXPORT_ORDER.forEach((palace)=>{
		const qimenCell = qimenMap[palace.palaceNum] || {};
		const body = [
			`遁甲：天盘干：${safe(qimenCell.tianGan, '—')}；八神：${safe(qimenCell.god, '—')}；九星：${safe(qimenCell.tianXing, '—')}；地盘干：${safe(qimenCell.diGan, '—')}`,
			'',
		];
		palace.branches.forEach((branch, idx)=>{
			const lr = lrBranchMap[branch] || {};
			const stars = Array.isArray(starsByBranch[branch]) ? starsByBranch[branch] : [];
			body.push(`「${branch}-${safe(BRANCH_ZODIAC_MAP[branch], '未知星座')}」`);
			// 盘面外圈画了「人事宫位号」与「虚实红绿点」(四柱地支定实 / 旬空推虚),快照此前两样都没有 →
			//   AI 看不到盘上最显眼的两层标注。此处逐支补齐(无数据不产行,缺省字节零变化)。
			const houseNos = outerData && outerData.housesByBranch && Array.isArray(outerData.housesByBranch[branch]) ? outerData.housesByBranch[branch] : [];
			if(houseNos.length){ body.push(`人事宫位：第 ${houseNos.join('、')} 宫`); }
			if(houseNos.indexOf('1') >= 0 && outerData && outerData.ascRaLine){ body.push(outerData.ascRaLine); }
			const ws = weakSolidMap ? weakSolidMap[branch] : null;
			if(ws && (ws.solid || ws.weak)){
				const parts = [];
				if(ws.solid){ parts.push(`实（${(ws.solidPillars || []).join('') || '四柱'}柱地支）`); }
				if(ws.weak){ parts.push(`虚（${(ws.weakPillars || []).join('') || '旬空'}旬空）`); }
				body.push(`虚实：${parts.join('；')}`);
			}
			body.push(`六壬：天盘：${safe(lr.up, '—')}；神将：${safe(lr.god, '—')}`);
			body.push(`星盘：${stars.length ? stars.join('；') : '无'}`);
			if(idx < palace.branches.length - 1){
				body.push('');
			}
		});
		out.push({ title: palace.title, body });
	});
	return out;
}

export function getOuterLabelLayout(branch, houseFont){
	// 外圈标签逐宫定位：四正宫按矩形角，八斜宫贴到对应三角区角落。
	const px = 1;
	const py = 1;
	const rowGap = Math.max(10, Math.round(houseFont * 0.92));
	const colGap = Math.max(11, Math.round(houseFont * 0.98));
	// 角宫位移：控制在 2~3 格之间，避免过度偏移。
	const shiftStep = Math.max(6, Math.round(houseFont * 0.34));
	const shiftRows = Math.round(shiftStep * 2.4);
	const shiftCols = Math.round(shiftStep * 2.4);
	// [角宫地支对角对称](horosa_sanshi_corner_label_mirror_v1)**只移地支、宫位数字原地不动**
	// (用户两点定版:「辰申往下、寅戌往上,做成隔壁字沿对角线镜像翻转的位置」+「宫位数字的
	// 位置别变,否则仍会挤在一起」)。辰/申/戌/寅 四个纵向角标原各比其横向邻居(巳/未/亥/丑)
	// 多减一格 oneGridShift ⇒ 过分贴角、与邻居不成镜像;现只把 **branch** 那一格去掉,
	// house 保留 —— 数字位置逐像素不变,地支沿边下移/上移,两者间距因此拉开(不再挤)。
	const oneGridShift = shiftStep;
	// 原注(保留以明来历)：辰/申/戌/寅 四个**纵向**角标
	// 原各比其横向邻居(巳/未/亥/丑)多减一格 oneGridShift ⇒ 四者过分贴角、与邻居不成镜像
	// (用户实圈:「辰申往下、寅戌往上,做成隔壁字沿对角线镜像翻转的位置」)。去掉那一格后,
	// 纵向标签距角的距离与横向邻居一致 —— 主对角线两侧自然对称。house 与 branch 同去,
	// 两者相对间距(rowGap)逐字不变,只是整体沿边平移。
	const oneAndHalfGridShift = shiftStep * 1.5;
	const fourGridShift = shiftStep * 4;
	const cornerOffset = '-16%';
	const wideNumGap = colGap + Math.max(8, Math.round(houseFont * 0.5));
	const topLeft = { left: px, top: py };
	const topRight = { right: px, top: py };
	const bottomLeft = { left: px, bottom: py };
	const bottomRight = { right: px, bottom: py };

	switch(branch){
	case '卯': // 左矩形：地支左下，数字左上
		return { house: topLeft, branch: bottomLeft };
	case '酉': // 右矩形：地支右下，数字右上
		return { house: topRight, branch: bottomRight };
	case '子': // 下矩形：地支右下，数字左下
		return { house: bottomLeft, branch: bottomRight };
	case '午': // 上矩形：地支右上，数字左上
		return { house: topLeft, branch: topRight };
	case '巳': // 上偏左梯形：落入左上角三角，数字左上，地支在其右
		return {
			house: { left: `calc(${cornerOffset} + ${shiftCols}px - ${fourGridShift}px - ${oneAndHalfGridShift}px)`, top: py },
			branch: { left: `calc(${cornerOffset} + ${colGap + shiftCols}px - ${fourGridShift}px)`, top: py },
		};
	case '辰': // 左偏上梯形：落入左上角三角，数字左上，地支在其下
		return {
			house: { left: px, top: `calc(${cornerOffset} + ${shiftRows}px - ${fourGridShift}px - ${oneGridShift}px)` },
			branch: { left: px, top: `calc(${cornerOffset} + ${rowGap + shiftRows}px - ${fourGridShift}px)` },
		};
	case '未': // 上偏右梯形：落入右上角三角，数字右上，地支在其左
		return {
			house: { right: `calc(${cornerOffset} + ${shiftCols}px - ${fourGridShift}px - ${oneAndHalfGridShift}px)`, top: py },
			branch: { right: `calc(${cornerOffset} + ${wideNumGap + shiftCols}px - ${fourGridShift}px - ${oneAndHalfGridShift}px)`, top: py },
		};
	case '申': // 右偏上梯形：落入右上角三角，数字右上，地支在其下
		return {
			house: { right: px, top: `calc(${cornerOffset} + ${shiftRows}px - ${fourGridShift}px - ${oneGridShift}px)` },
			branch: { right: px, top: `calc(${cornerOffset} + ${rowGap + shiftRows}px - ${fourGridShift}px)` },
		};
	case '戌': // 右偏下梯形：落入右下角三角，数字右下，地支在其上
		return {
			house: { right: px, bottom: `calc(${cornerOffset} + ${shiftRows}px - ${fourGridShift}px - ${oneGridShift}px)` },
			branch: { right: px, bottom: `calc(${cornerOffset} + ${rowGap + shiftRows}px - ${fourGridShift}px)` },
		};
	case '亥': // 下偏右梯形：落入右下角三角，数字右下，地支在其左
		return {
			house: { right: `calc(${cornerOffset} + ${shiftCols}px - ${fourGridShift}px - ${oneAndHalfGridShift}px)`, bottom: py },
			branch: { right: `calc(${cornerOffset} + ${wideNumGap + shiftCols}px - ${fourGridShift}px - ${oneAndHalfGridShift}px)`, bottom: py },
		};
	case '丑': // 下偏左梯形：落入左下角三角，数字左下，地支在其右
		return {
			house: { left: `calc(${cornerOffset} + ${shiftCols}px - ${fourGridShift}px - ${oneAndHalfGridShift}px)`, bottom: py },
			branch: { left: `calc(${cornerOffset} + ${colGap + shiftCols}px - ${fourGridShift}px)`, bottom: py },
		};
	case '寅': // 左偏下梯形：落入左下角三角，数字左下，地支在其上
		return {
			house: { left: px, bottom: `calc(${cornerOffset} + ${shiftRows}px - ${fourGridShift}px - ${oneGridShift}px)` },
			branch: { left: px, bottom: `calc(${cornerOffset} + ${rowGap + shiftRows}px - ${fourGridShift}px)` },
		};
	default:
		return { house: topLeft, branch: topRight };
	}
}

export function getOuterStarsLayout(branch, starFont){
	const sidePad = 2;
	const rightPad = sidePad + 2;
	const topPad = Math.max(8, Math.round(starFont * 1.35));
	const bottomPad = Math.max(8, Math.round(starFont * 1.35));
	const onePerRowBranches = new Set(['寅', '卯', '辰', '申', '酉', '戌']);
	const perRow = onePerRowBranches.has(branch) ? 1 : 3;
	let style = {};
	let rowJustify = 'center';

	switch(branch){
	case '卯':
		style = { left: sidePad, top: '50%', transform: 'translateY(-50%)', textAlign: 'left' };
		rowJustify = 'flex-start';
		break;
	case '酉':
		style = { right: sidePad, top: '50%', transform: 'translateY(-50%)', textAlign: 'right' };
		rowJustify = 'flex-end';
		break;
	case '午':
		style = { left: '50%', top: topPad, transform: 'translateX(-50%)', textAlign: 'center' };
		rowJustify = 'center';
		break;
	case '子':
		style = { left: '50%', bottom: bottomPad, transform: 'translateX(-50%)', textAlign: 'center' };
		rowJustify = 'center';
		break;
	case '巳':
	case '丑':
		style = { right: rightPad, top: '50%', transform: 'translateY(-50%)', textAlign: 'right' };
		rowJustify = 'flex-end';
		break;
	case '亥':
	case '未':
		style = { left: sidePad, top: '50%', transform: 'translateY(-50%)', textAlign: 'left' };
		rowJustify = 'flex-start';
		break;
	case '辰':
		style = { left: sidePad, top: topPad, textAlign: 'left' };
		rowJustify = 'flex-start';
		break;
	case '申':
		style = { right: sidePad, top: topPad, textAlign: 'right' };
		rowJustify = 'flex-end';
		break;
	case '寅':
		style = { left: sidePad, bottom: bottomPad, textAlign: 'left' };
		rowJustify = 'flex-start';
		break;
	case '戌':
		style = { right: sidePad, bottom: bottomPad, textAlign: 'right' };
		rowJustify = 'flex-end';
		break;
	default:
		style = { left: '50%', top: '50%', transform: 'translate(-50%, -50%)', textAlign: 'center' };
		rowJustify = 'center';
		break;
	}

	return {
		perRow,
		rowJustify,
		style,
	};
}

export function padOuterStarsRow(row, perRow, rowJustify){
	const padded = row.slice();
	while(padded.length < perRow){
		if(rowJustify === 'flex-end'){
			padded.unshift('');
			continue;
		}
		if(rowJustify === 'center' && perRow === 3 && padded.length === 1){
			padded.unshift('');
			padded.push('');
			continue;
		}
		padded.push('');
	}
	return padded;
}

export function buildPillarFromPan(pan, key){
	if(!pan || !pan.ganzhi){
		return '';
	}
	return pan.ganzhi[key] || '';
}
