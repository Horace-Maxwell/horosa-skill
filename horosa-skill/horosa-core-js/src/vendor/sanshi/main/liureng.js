// 三式合一页:六壬家起课与布局(起课参数、课 / 三传、天地盘布局、宫位地支换算、旺衰虚实、旬)。
// 从 SanShiUnitedMain.js 按职责拆出(门面保留原导入路径与对外导出;读源码的检查读「子模块 + 门面」全集,见 scripts/source-sets.json)。
import { liurengSeHaiOptsOf, getYueJiangByMethod } from '../../liureng/LiuRengMain.js';
import * as LRConst from '../../liureng/LRConst.js';
import ChuangChart from '../../liureng/ChuangChart.js';
import { getXunHead, GUXU } from '../../dunjia/DunJiaCalc.js';
import { safe } from '../../dunjia/qimenPageShared.js';
import { XUN_SHOU_TO_LIUYI } from '../../dunjia/DunJiaBaGongRules.js';
import { computeSanshiFenZhouYe, getChartYue } from './format.js';
import { BRANCH_ORDER, STEM_ORDER } from './options.js';

// 汇总 大六壬流派(换将/分昼夜/涉害取舍/昼夜阳阴归属)→ castOverride;全默认返回 null(零回归)。
// 与独立 lrzhan/buildLiuRengCastOverride 同款语义(三式合一只支持「正时正将」起课法,不含 25 起课变体)。
// 三式合一 → 六壬断卦层的 castOpts 形态(与 buildLiuRengSnapshotText 第 8 参同键;三式锁正时正将)。
export function pickSanshiLiurengCastOpts(opts, nongli){
	const o = opts && typeof opts === 'object' ? opts : {};
	const solarYear = Number(o.solarYear) || (nongli && Number(nongli.solarYear)) || undefined;
	return {
		castMethod: 'zheng',
		yueJiangMethod: o.yueJiangMethod,
		fenZhouYe: o.fenZhouYe,
		seHaiMethod: o.seHaiMethod,
		seHaiBoundary: o.seHaiBoundary,
		shiRuKe: o.shiRuKe,
		yinyangSystem: o.yinyangSystem,
		yearShenShaSort: o.yearShenShaSort,
		tuWangShuai: o.tuWangShuai,
		zhanCategory: o.zhanCategory,
		...(solarYear ? { solarYear } : {}),
	};
}

export const SANSHI_TRUE_SOLAR_FALLBACK_NOTE = '(历法服务暂不可用,本次农历按真太阳时)';

export function buildSanshiLiuRengCastOverride(chartObj, opts){
	opts = opts || {};
	if(!chartObj || !chartObj.nongli){
		return null;
	}
	const yueJiangMethod = opts.yueJiangMethod || 'zhongqi';
	const fenZhouYe = opts.fenZhouYe || 'chenhun';
	const isDiurnal = computeSanshiFenZhouYe(fenZhouYe, chartObj);
	const seHaiOpts = liurengSeHaiOptsOf(opts);
	const seHaiDefault = seHaiOpts.method === 'app' && seHaiOpts.boundary === 'app' && !seHaiOpts.shiRuKe;
	const yinyangSystem = opts.yinyangSystem === 'yinyang' ? 'yinyang' : 'danmu';
	const yearShenShaSort = opts.yearShenShaSort || 'sanyuan'; // 年神排序(默认四利三元序);三式合一原 override 漏传→六壬子盘 AI 快照年神恒默认
	const tuWangShuai = opts.tuWangShuai || 'siji'; // 三传旺衰(默认四季月土旺)
	const allDefault = yueJiangMethod !== 'jieqi' && yueJiangMethod !== 'richan'
		&& isDiurnal === undefined && seHaiDefault && yinyangSystem === 'danmu'
		&& yearShenShaSort === 'sanyuan' && tuWangShuai === 'siji';
	if(allDefault){
		return null;
	}
	const solarYear = Number(opts.solarYear) || (chartObj.nongli && Number(chartObj.nongli.solarYear)) || undefined;
	const yueEff = getYueJiangByMethod(chartObj, yueJiangMethod, solarYear);
	return { yue: yueEff, isDiurnal, seHaiOpts, yinyangSystem, yearShenShaSort, tuWangShuai };
}

export function buildLiuRengLayout(chartObj, guirengType, castOverride){
	if(!chartObj || !chartObj.nongli || !chartObj.nongli.time){
		return null;
	}
	const yue = (castOverride && castOverride.yue) || getChartYue(chartObj);
	if(!yue){
		return null;
	}
	const downZi = LRConst.ZiList.slice(0);
	const upZi = LRConst.ZiList.slice(0);
	const yueIndexs = [];
	// 临位(地盘临位)与六壬页同口径:可被 castOverride.timeZhi 覆盖;缺省=正时。
	const timezi = (castOverride && castOverride.timeZhi) || chartObj.nongli.time.substr(1);
	const yueIdx = LRConst.ZiList.indexOf(yue);
	const tmIdx = LRConst.ZiList.indexOf(timezi);
	if(yueIdx < 0 || tmIdx < 0){
		return null;
	}
	const delta = yueIdx - tmIdx;
	for(let i=0; i<12; i++){
		const idx = (i + delta + 12) % 12;
		yueIndexs[i] = idx;
		upZi[i] = LRConst.ZiList[idx];
	}

	const houseTianJiang = LRConst.TianJiang.slice(0);
	const guizi = LRConst.getGuiZi(
		chartObj,
		guirengType === undefined ? 2 : guirengType,
		castOverride ? castOverride.isDiurnal : undefined,
		castOverride ? castOverride.yinyangSystem : undefined
	);
	// 贵人未命中即判失败(与六壬页 buildLiuRengLayout 同口径):不再静默落子位、让十二天将整环偏移;
	// 宁可不出盘也不出错盘,调用方按 null 走不出盘分支。
	let houseidx = -1;
	for(let i=0; i<12; i++){
		const zi = LRConst.ZiList[yueIndexs[i]];
		if(zi === guizi){
			houseidx = i;
			break;
		}
	}
	if(houseidx < 0){
		return null;
	}
	const housezi = LRConst.ZiList[houseidx];
	if(LRConst.SummerZiList.indexOf(housezi) >= 0){
		for(let i=0; i<12; i++){
			const idx = (houseidx - i + 12) % 12;
			houseTianJiang[i] = LRConst.TianJiang[idx];
		}
	}else{
		for(let i=0; i<12; i++){
			const idx = (i - houseidx + 12) % 12;
			houseTianJiang[i] = LRConst.TianJiang[idx];
		}
	}
	return { yue, timezi, guizi, downZi, upZi, houseTianJiang };
}

export function buildLrNongli(nongli, dunjia){
	const dayGanZi = dunjia && dunjia.ganzhi ? (dunjia.ganzhi.day || '') : '';
	const timeGanZi = dunjia && dunjia.ganzhi ? (dunjia.ganzhi.time || '') : '';
	return {
		...(nongli || {}),
		dayGanZi: dayGanZi || (nongli && nongli.dayGanZi ? nongli.dayGanZi : ''),
		time: timeGanZi || (nongli && nongli.time ? nongli.time : ''),
	};
}

export function buildKeData(layout, chartObj){
	const result = { raw: [], lines: [] };
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

	result.raw = [ke1, ke2, ke3, ke4];
	// 标签与 raw 同序(ke1=一课 日干上神 … ke4=四课);此前 四→一 反标(无消费方,顺手对齐防再被引用)。
	result.lines = [
		`一课 ${ke1[2]}${ke1[1]}${ke1[0]}`,
		`二课 ${ke2[2]}${ke2[1]}${ke2[0]}`,
		`三课 ${ke3[2]}${ke3[1]}${ke3[0]}`,
		`四课 ${ke4[2]}${ke4[1]}${ke4[0]}`,
	];
	return result;
}

export function buildSanChuan(layout, keRaw, chartObj, castOverride){
	if(!layout || !keRaw || keRaw.length !== 4 || !chartObj || !chartObj.nongli){
		return null;
	}
	try{
		const helper = new ChuangChart({
			owner: null,
			chartObj: chartObj,
			nongli: chartObj.nongli,
			ke: keRaw,
			// 涉害取舍流派(默认 null=仅下贼上,已固定,零回归);非默认时携 seHaiOpts 影响涉害课取用。
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

export function normalizeLon(v){
	let lon = parseFloat(v);
	if(Number.isNaN(lon)){
		return null;
	}
	lon = ((lon % 360) + 360) % 360;
	return lon;
}

export function lonToBranch(lon){
	const nlon = normalizeLon(lon);
	if(nlon === null){
		return '';
	}
	// 星座-地支固定映射：
	// 水瓶-子、摩羯-丑、射手-寅、天蝎-卯、天秤-辰、处女-巳、
	// 狮子-午、巨蟹-未、双子-申、金牛-酉、白羊-戌、双鱼-亥
	const signIdx = Math.floor(nlon / 30) % 12; // 白羊=0 ... 双鱼=11
	const branchIdx = (10 - signIdx + 12) % 12;
	return BRANCH_ORDER[branchIdx];
}

// 赤经(RA)→地支:与 lonToBranch 同口径(RA 0°=白羊点,对齐黄经 0°),供「外圈赤道分宫」复用 obj.ra。
export function raToBranch(ra){
	const nra = normalizeLon(ra);
	if(nra === null){
		return '';
	}
	const signIdx = Math.floor(nra / 30) % 12;
	const branchIdx = (10 - signIdx + 12) % 12;
	return BRANCH_ORDER[branchIdx];
}

export function signToBranch(sign){
	if(!sign){
		return '';
	}
	try{
		return LRConst.getSignZi(sign) || '';
	}catch(e){
		return '';
	}
}

export function resolveObjBranch(obj, coord){
	if(!obj){
		return '';
	}
	// 赤道模式:按赤经(obj.ra)分入地支;缺赤经则回退黄道避免空。默认(ecliptic/未传)逐字现状。
	if(coord === 'equatorial'){
		const ra = obj.ra;
		if(ra !== undefined && ra !== null && !Number.isNaN(parseFloat(ra))){
			return raToBranch(ra);
		}
	}
	const bySign = signToBranch(obj.sign);
	if(bySign){
		return bySign;
	}
	return lonToBranch(obj.lon);
}

export function parseHouseNum(houseId){
	if(!houseId){
		return '';
	}
	const m = `${houseId}`.match(/\d+/);
	return m ? m[0] : '';
}

// 单柱「虚支」:与后端七政四余 Moira(MoiraPropRuleEngine.computeWeakHouse)逐字一致——
// 旬空二支按 60 甲子位次奇偶仅取其一(偶位取前支/奇位取后支),非整对旬空。
// i = 干序 g + 10*旬序;index = 10 - 2*旬序,i 奇(即 g 奇)则 +1,取 BRANCH_ORDER[index]。
function computeMoiraWeakZhi(ganzhi){
	if(!ganzhi || ganzhi.length < 2){ return ''; }
	const g = STEM_ORDER.indexOf(ganzhi.charAt(0));
	const z = BRANCH_ORDER.indexOf(ganzhi.charAt(1));
	if(g < 0 || z < 0){ return ''; }
	const xun = ((((g - z) % 12) + 12) % 12) / 2; // 旬序 0..5(= 60甲子位次 i 的 i/10)
	let index = 10 - 2 * xun;
	if(g % 2 === 1){ index++; } // i 奇 ⇔ g 奇(i = g + 10*旬序)
	return BRANCH_ORDER[(((index % 12) + 12) % 12)] || '';
}

// 三式外圈「虚实」红绿点 八字源,与七政四余 Moira 红绿点逐宫一致:
//  实宫=年月日时【四柱地支】各自定实;虚宫=四柱各自 computeMoiraWeakZhi(每柱仅一支)推虚。
// pan.ganzhi = 起课四柱(年/月/日/时干支)。返回 { 地支: {solid,weak,solidPillars,weakPillars} }。
export function buildSanshiWeakSolid(pan){
	const map = {};
	BRANCH_ORDER.forEach((b)=>{ map[b] = { solid: false, weak: false, solidPillars: [], weakPillars: [] }; });
	const gz = (pan && pan.ganzhi) || {};
	const pillars = [
		{ label: '年', gz: gz.year || '' },
		{ label: '月', gz: gz.month || '' },
		{ label: '日', gz: gz.day || '' },
		{ label: '时', gz: gz.time || '' },
	];
	// 实宫:四柱地支各自定实。
	pillars.forEach((p)=>{
		const zhi = (p.gz || '').charAt(1);
		if(zhi && map[zhi]){
			map[zhi].solid = true;
			if(map[zhi].solidPillars.indexOf(p.label) < 0){
				map[zhi].solidPillars.push(p.label);
			}
		}
	});
	// 虚宫:四柱各自取 Moira 虚支(每柱一支)推虚。
	pillars.forEach((p)=>{
		const wz = computeMoiraWeakZhi(p.gz);
		if(wz && map[wz]){
			map[wz].weak = true;
			if(map[wz].weakPillars.indexOf(p.label) < 0){
				map[wz].weakPillars.push(p.label);
			}
		}
	});
	return map;
}

// 三式「旬」统一口径(时家奇门;概览/盘底/快照单一来源,杜绝与后端 xunShou/fuTou(=六仪)及繁简键漂移):
//  旬首=时柱所在旬之甲(该时辰旬首,如癸巳→甲申);旬仪=旬首所遁六仪(甲申→庚,显示甲申庚);
//  本旬=日柱所在旬之甲(本日之旬);旬空=日柱旬空(日空);时空=时柱旬空。
// 旬首(甲X)展开为「甲X丁Y癸Z」:旬首(第一日甲)+旬丁(第四日丁=丁马)+旬尾(第十日癸);
// 丁在旬首后第 3 位、癸在第 9 位(地支同步推移)。例:甲子→甲子丁卯癸酉;甲辰→甲辰丁未癸丑。
function expandXunPillars(head){
	if(!head || head.length < 2){ return head || ''; }
	const z = BRANCH_ORDER.indexOf(head.charAt(1));
	if(z < 0){ return head; }
	const ding = `丁${BRANCH_ORDER[(z + 3) % 12]}`; // 第四日(丁) + 地支
	const gui = `癸${BRANCH_ORDER[(z + 9) % 12]}`; // 第十日(癸) + 地支
	return `${head}${ding}${gui}`;
}

export function computeSanshiXun(pan){
	const gz = (pan && pan.ganzhi) || {};
	const dayHead = gz.day ? getXunHead(gz.day) : '';
	const timeHead = gz.time ? getXunHead(gz.time) : '';
	const xunShou = timeHead || safe(pan && pan.xunShou, '—');
	const xunYi = timeHead ? `${timeHead}${XUN_SHOU_TO_LIUYI[timeHead] || ''}` : safe(pan && pan.fuTou, '—');
	// 本旬=日柱所在旬,展开旬首/旬丁/旬尾(甲X丁Y癸Z),与参考样张一致。
	const benXun = dayHead ? expandXunPillars(dayHead) : safe(pan && pan.xunShou, '—');
	const riKong = (dayHead && GUXU[dayHead]) || safe(pan && pan.xunkong && pan.xunkong.日空, '—');
	const shiKong = (timeHead && GUXU[timeHead]) || safe(pan && pan.xunkong && (pan.xunkong.时空 || pan.xunkong.時空), '—');
	return { xunShou, xunYi, benXun, riKong, shiKong };
}
