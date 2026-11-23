// 后端排盘结果归一与取盘(kinqimen 模式判定、字段归一、请求)
// 从 DunJiaCalc.js 按职责拆出(门面保留原导入路径与对外导出;读源码的检查读「子模块 + 门面」全集,见 scripts/source-sets.json)。
import { LUOSHU_NUM } from '../DunJiaFaDoc.js';
import { leapPrefix } from '../../utils/lunarText.js';
import { jianChuRing } from '../../utils/jianChu.js';


import { normalizeNum, normalizeShiftPalace, normalizeText, getOptionLabel, parseDateTime, resolveCalcDateTime } from './basics.js';
import { normalizeQijuMethod } from './juMeta.js';
import { convertGuaMapToPos, rotateOuterMapByShift, rotateOuterPalaceNum, getKongByMode, resolveKongWangPalaces, resolveYiMa, resolveSpecials, resolveMenPo, buildCells, mapListByPos } from './pan.js';
import { GUA_POS_MAP, BRANCH_TO_POS, PALACE_NAME, JIU_XING_NAME, BA_MEN_NAME } from './tables.js';
import { PAIPAN_OPTIONS, normalizeSchool } from './options.js';

export function isKinqimenMode(paiPanType){
	const type = normalizeNum(paiPanType, 3);
	// 年(0)/月(1)/日(2)/刻(4)家走本地全盘(各家局法 + 各柱锚点;刻家=十分局本地引擎);时(3)/综合(5)走后端(时家保后端=转盘字节护栏)。
	return type === 3 || type === 5;
}

// 后端 /qimen/pan 只收 排盘家/起局法/盘式(及日界两开关);下列七组口径只在本地 calcDunJia 生效,合并阶段
//   (normalizeKinqimenData 重建 cells)也不再施加 → 任一非缺省时转盘若仍走后端:页面恒按缺省出盘、快照[盘型]却标所选、
//   AI 无头重算又按所选全算(三套口径),后端离线又翻回本地按所选。判据单源:非缺省 → 路由切本地(与飞盘/混合/报数同一旁路);
//   全缺省 → 历来后端路由,字节不变。返回非缺省键名列表(空=可走后端)。缺省值与 DunJiaMain/三式 QIMEN_OPTIONS 同值。
// 格子上的盘面附加层键(本地 calcDunJia 开关开才写;合并路径按宫抄回)
export const OVERLAY_CELL_KEYS = ['jiTianGan', 'jiDiGan', 'tianQin', 'tuiYanTags'];
export function qimenLocalOnlyOverrides(options){
	const o = options || {};
	const out = [];
	if(normalizeNum(o.zhiShiType, 0) !== 0){ out.push('zhiShiType'); }                                           // 值使取法(后端固定 天禽值符-死门)
	if(normalizeQijuMethod(o.qijuMethod) === 'zhirun' && normalizeNum(o.zhirunLeapDays, 9) !== 9){ out.push('zhirunLeapDays'); }   // 置闰天数
	if(o.godsPreset && o.godsPreset !== 'baihu_xuanwu'){ out.push('godsPreset'); }                               // 八神取神
	if(o.jiGongMode && o.jiGongMode !== 'kun'){ out.push('jiGongMode'); }                                        // 中宫寄宫
	if(o.anGanMode && o.anGanMode !== 'off'){ out.push('anGanMode'); }                                           // 暗干(暗支随暗干)
	if(o.kongMarkBoth){ out.push('kongMarkBoth'); }                                                              // 空亡并标(宫位高亮两组)
	if(normalizeShiftPalace(o.shiftPalace) && o.shiftZhiFuMode === 'recalc'){ out.push('shiftZhiFuMode'); }      // 移星值符重定
	return out;
}

// 奇门盘路由单源(独立页 getResolvedPan / 三式 getKinqimenDunJia / 择日弹窗 / 步进预取 同判据):
//   true=本地 calcDunJia:年/月/日/刻/金函家、飞盘/混合、阴盘报数、或上述本地口径任一非缺省;
//   false=后端 fetchQimenPan+normalizeKinqimenData(时家/综合·转盘·全缺省口径=转盘字节护栏)。
export function isQimenLocalRoute(options){
	const o = options || {};
	if(!isKinqimenMode(o.paiPanType)){ return true; }
	if(o.school === '飞盘' || o.school === '混合' || o.qijuMethod === 'shuzi'){ return true; }
	return qimenLocalOnlyOverrides(o).length > 0;
}

// 节气种子取数判据(独立页/三式/择日共用单源;此前两页各写一份:三式只认「时家+置闰」,独立页刻家落到恒 false):
//   置闰/无闰=超神接气、茅山=按交节时刻足60时辰 → 本地链须精确交节种子;日家(2)=节气三元60日块、金函(6)=至日定阴阳 →
//   任何起局法都要至日种子(含 y+1 供腊月过冬至);刻家(4)初局=本时辰时家局(沿置闰/无闰/茅山链)→ 与时家本地路由同需;
//   年家/月家不吃种子;后端路由由后端自处理节气,本地种子无关。
export function needJieqiYearSeed(options){
	const opt = options || {};
	const type = normalizeNum(opt.paiPanType, 3);
	const usesShenJie = opt.qijuMethod === 'zhirun' || opt.qijuMethod === 'wurun' || opt.qijuMethod === 'maoshan';
	if(type === 2 || type === 6){ return true; }
	if(type === 0 || type === 1){ return false; }
	if(type === 4){ return usesShenJie; }
	return isQimenLocalRoute(opt) && usesShenJie;
}

// 种子年份集(与 needJieqiYearSeed 同源):日家/金函 腊月过冬至需次年至日 → y-1,y,y+1;其余 y-1,y。
export function jieqiSeedYears(options, year){
	const y = Number(year);
	if(!y || !Number.isFinite(y)){ return []; }   // 与各页 `if(!year || Number.isNaN(year))` 同口径(null/''/0 皆无种子年)
	const type = normalizeNum((options || {}).paiPanType, 3);
	return (type === 2 || type === 6) ? [y - 1, y, y + 1] : [y - 1, y];
}

// 缓存键/重算签名用的种子签名:已到达种子年份升序拼接;种子异步到达后签名变 → 不再命中缺种子时算出的退化盘。
export function jieqiSeedSignature(seeds){
	const s = seeds || {};
	return 'seed:' + Object.keys(s).filter((y)=>!!s[y]).sort().join(',');
}

function getKinqimenMode(paiPanType){
	const type = normalizeNum(paiPanType, 3);
	if(type === 0){
		return 'year';
	}
	if(type === 4){
		return 'minute';
	}
	if(type === 2){
		return 'golden';
	}
	if(type === 5){
		return 'overall';
	}
	return 'hour';
}

function getRawValue(obj, keys, def = ''){
	for(let i=0; i<keys.length; i++){
		if(obj && obj[keys[i]] !== undefined && obj[keys[i]] !== null){
			return obj[keys[i]];
		}
	}
	return def;
}

function normalizeGuaName(gua){
	return normalizeText(gua)
		.replace(/離/g, '离')
		.replace(/兌/g, '兑')
		.replace(/乾/g, '乾');
}

function normalizeGuaMap(mapObj){
	const out = {};
	Object.keys(mapObj || {}).forEach((key)=>{
		const gua = normalizeGuaName(key);
		out[gua] = normalizeText(mapObj[key]);
	});
	return out;
}

function parseKinqimenGanzhi(rawText, fallbackGanzhi){
	const text = normalizeText(rawText || '');
	const match = text.match(/([甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥])年([甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥])月([甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥])日([甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥])时(?:([甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥])分)?/);
	if(!match){
		return fallbackGanzhi || {};
	}
	return {
		...(fallbackGanzhi || {}),
		year: match[1] || '',
		month: match[2] || '',
		day: match[3] || '',
		time: match[4] || '',
		minute: match[5] || '',
	};
}

function normalizeZhiFuZhiShi(zfzs){
	const zhiFuStar = getRawValue(zfzs, ['值符星宮', '值符星宫'], []);
	const zhiShiDoor = getRawValue(zfzs, ['值使門宮', '值使门宫'], []);
	const zhiFuGan = getRawValue(zfzs, ['值符天干'], '');
	return {
		zhiFuGan,
		zhiFuStar: Array.isArray(zhiFuStar) ? zhiFuStar.map((item)=>normalizeText(item)) : [],
		zhiShiDoor: Array.isArray(zhiShiDoor) ? zhiShiDoor.map((item)=>normalizeText(item)) : [],
	};
}

function normalizeBackendSections(sections){
	if(!Array.isArray(sections)){
		return [];
	}
	return sections.map((section)=>({
		title: normalizeText(section && section.title ? section.title : ''),
		rows: Array.isArray(section && section.rows) ? section.rows.map((row)=>({
			label: normalizeText(row && row.label ? row.label : ''),
			value: normalizeText(row && row.value ? row.value : '—') || '—',
		})) : [],
	})).filter((section)=>section.title || section.rows.length);
}

function mergeKinqimenMaps(raw, fallbackPan, opts){
	const shiftPalace = normalizeShiftPalace(opts && opts.shiftPalace);
	const tianpanRaw = normalizeGuaMap(getRawValue(raw, ['天盤', '天盘'], {}));
	const dipanRaw = normalizeGuaMap(getRawValue(raw, ['地盤', '地盘'], {}));
	const menRaw = normalizeGuaMap(getRawValue(raw, ['門', '门'], {}));
	const starRaw = normalizeGuaMap(getRawValue(raw, ['星'], {}));
	const shenRaw = normalizeGuaMap(getRawValue(raw, ['神'], {}));
	const diPanBase = Object.keys(dipanRaw).length ? convertGuaMapToPos(dipanRaw) : (fallbackPan.diPan || {});
	const tianPanBase = Object.keys(tianpanRaw).length ? convertGuaMapToPos(tianpanRaw) : (fallbackPan.tianPan || {});
	const menBase = Object.keys(menRaw).length ? convertGuaMapToPos(menRaw) : (fallbackPan.renPan || {});
	const starBase = Object.keys(starRaw).length ? convertGuaMapToPos(starRaw) : {};
	const shenBase = Object.keys(shenRaw).length ? convertGuaMapToPos(shenRaw) : (fallbackPan.shenPan || {});
	const diPan = rotateOuterMapByShift(diPanBase, shiftPalace);
	const tianPan = rotateOuterMapByShift(tianPanBase, shiftPalace);
	const renPan = rotateOuterMapByShift(menBase, shiftPalace);
	let tianXing = rotateOuterMapByShift(Object.keys(starBase).length ? starBase : (fallbackPan.tianXing || {}), shiftPalace);
	// 后端盘星名归一:转盘(8星)天禽寄芮、禽/芮/禽芮合一,统一显「内」(天内);飞盘(9星)含中宫禽,保「禽」不动(用户:内对芮讹)。
	if((opts && opts.school) !== '飞盘'){
		const convStar = {};
		Object.keys(tianXing).forEach((k)=>{ convStar[k] = String(tianXing[k] == null ? '' : tianXing[k]).replace(/[芮禽]+/g, '内'); });
		tianXing = convStar;
	}
	const shenPan = rotateOuterMapByShift(shenBase, shiftPalace);
	return { diPan, tianPan, renPan, tianXing, shenPan };
}

export function normalizeKinqimenData(backendPan, fallbackPan, options, nongli){
	if(!backendPan || !fallbackPan){
		return fallbackPan;
	}
	const raw = backendPan.selected || backendPan.raw || {};
	const opts = options || {};
	const maps = mergeKinqimenMaps(raw, fallbackPan, opts);
	const zfzs = normalizeZhiFuZhiShi(getRawValue(raw, ['值符值使'], {}));
	const zhiFuPalaceRaw = zfzs.zhiFuStar[1] || '';
	const zhiShiPalaceRaw = zfzs.zhiShiDoor[1] || '';
	const shiftPalace = normalizeShiftPalace(opts.shiftPalace);
	const zhiFuPalace = zhiFuPalaceRaw ? rotateOuterPalaceNum(GUA_POS_MAP[zhiFuPalaceRaw] || 5, shiftPalace) : fallbackPan.zhiFuPalace;
	const zhiShiPalace = zhiShiPalaceRaw ? rotateOuterPalaceNum(GUA_POS_MAP[zhiShiPalaceRaw] || 5, shiftPalace) : fallbackPan.zhiShiPalace;
	// 飞盘天禽有本位(中宫),值符星=禽 时不替芮;转盘禽寄芮照旧。
	const zhiFuShort = (opts.school === '飞盘') ? (zfzs.zhiFuStar[0] || '') : (zfzs.zhiFuStar[0] || '').replace(/[芮禽]+/g, '内');
	const zhiShiShort = zfzs.zhiShiDoor[0] || '';
	const xunkong = getRawValue(raw, ['旬空'], fallbackPan.xunkong || {});
	const kongWang = getKongByMode(opts.kongMode, {
		日空: normalizeText(xunkong && xunkong.日空 ? xunkong.日空 : ''),
		时空: normalizeText((xunkong && (xunkong.時空 || xunkong.时空)) || ''),
	}) || fallbackPan.kongWang;
	const kongWangMeta = resolveKongWangPalaces(kongWang);
	const horse = getRawValue(raw, ['馬星', '马星'], {});
	// 驿马按 yimaMode(日马=日支三合 / 时马=时支三合)自算,与本地 calcDunJia 同源(resolveYiMa);
	//   后端 馬星.驛馬 是单一值、不随 yimaMode 变,时家须自算,左栏「日马/时马」切换才会改盘+右栏(用户报障)。
	const yiMaMeta = resolveYiMa(opts.yimaMode, fallbackPan.ganzhi || {});
	const yiMaZhi = yiMaMeta.yimaZhi || normalizeText((horse && (horse.驛馬 || horse.驿马)) || '');
	const yiMaPalace = yiMaMeta.palace || BRANCH_TO_POS[yiMaZhi] || (fallbackPan.yiMa ? fallbackPan.yiMa.palace : 0);
	const yiMa = {
		...(fallbackPan.yiMa || {}),
		mode: opts.yimaMode,
		yimaZhi: yiMaZhi || (fallbackPan.yiMa ? fallbackPan.yiMa.yimaZhi : ''),
		palace: yiMaPalace,
		text: yiMaMeta.text || (yiMaPalace ? `驿马：${yiMaZhi}（${PALACE_NAME[yiMaPalace]}${LUOSHU_NUM[PALACE_NAME[yiMaPalace]]}宫）` : (fallbackPan.yiMa ? fallbackPan.yiMa.text : '驿马：无')),
		raw: horse,
	};
	const specials = resolveSpecials(maps.tianPan);
	const menPo = resolveMenPo(maps.renPan);
	const cells = buildCells(maps.diPan, maps.tianPan, maps.renPan, maps.shenPan, maps.tianXing, zhiFuPalace, zhiShiPalace, {
		jiXingPalaces: specials.jiXingPalaces,
		ruMuPalaces: specials.ruMuPalaces,
		menPoPalaces: menPo.palaces,
		kongWangPalaces: kongWangMeta.palaces,
		yimaPalace: yiMaPalace,
		school: opts.school,
	});
	// 盘面附加层(寄干 / 天禽 / 推演路径)只有本地排盘会往格子上写:这里重建了格子,按宫抄回 ——
	//   否则出厂口径(走这条合并路径)下开了这几项,右栏卡片与快照有内容,九宫格上一个标注都没有
	(fallbackPan.cells || []).forEach((fc)=>{
		const c = fc ? cells.find((x)=>x.palaceNum === fc.palaceNum) : null;
		if(c){ OVERLAY_CELL_KEYS.forEach((k)=>{ if(fc[k] !== undefined){ c[k] = fc[k]; } }); }
	});
	const qimenModeLabel = normalizeText(backendPan.modeLabel || '');
	const juText = normalizeText(getRawValue(raw, ['排局', '局'], fallbackPan.juText));
	let ganzhi = parseKinqimenGanzhi(getRawValue(raw, ['干支'], ''), fallbackPan.ganzhi);
	// v2.2.1: 本地 buildGanzhiForQimen 是 lateZi 语义的唯一可信来源(覆盖 4 case 矩阵)。
	// 后端 kinqimen(kinwangji jieqi)已对齐同一口径:(after23=1 + lateZi=0 + hour==23) 亦返回 戊子,
	// 页头与九宫 / 值符 / 旬空不再两套时辰;这里保留「以本地时柱为准」只作兜底(两边现应逐字相同)。
	if(fallbackPan && fallbackPan.ganzhi && fallbackPan.ganzhi.time && ganzhi.time !== fallbackPan.ganzhi.time){
		ganzhi = { ...ganzhi, time: fallbackPan.ganzhi.time };
	}
	return {
		...fallbackPan,
		source: 'kinqimen',
		backend: backendPan,
		raw,
		allRaw: backendPan.allRaw || {},
		sections: normalizeBackendSections(backendPan.sections),
		qimenMode: backendPan.mode || getKinqimenMode(opts.paiPanType),
		qimenModeLabel,
		qimenCapabilities: backendPan.capabilities || null,
		juText: juText || fallbackPan.juText,
		jieqiText: normalizeText(getRawValue(raw, ['節氣', '节气'], fallbackPan.jieqiText)) || fallbackPan.jieqiText,
		yinYangDun: juText.indexOf('阴遁') >= 0 ? '阴遁' : (juText.indexOf('阳遁') >= 0 ? '阳遁' : fallbackPan.yinYangDun),
		sanYuan: juText.indexOf('上元') >= 0 || juText.endsWith('上') ? '上元' : (juText.indexOf('中元') >= 0 || juText.endsWith('中') ? '中元' : (juText.indexOf('下元') >= 0 || juText.endsWith('下') ? '下元' : fallbackPan.sanYuan)),
		juShu: (juText.match(/[一二三四五六七八九]/) || [fallbackPan.juShu || ''])[0],
		ganzhi,
		// 十二建星外环随合并后的四柱重算(外环 / 右栏 / 快照同一份四柱)
		...(fallbackPan.jianChu ? { jianChu: jianChuRing(ganzhi, fallbackPan.dateStr) } : {}),
		xunShou: normalizeText(getRawValue(raw, ['旬首'], fallbackPan.xunShou)),
		fuTou: normalizeText(getRawValue(raw, ['旬首'], fallbackPan.fuTou)),
		xunkong,
		kongWang,
		zhiFu: zhiFuShort ? (JIU_XING_NAME[zhiFuShort] || zhiFuShort) : fallbackPan.zhiFu,
		zhiShi: zhiShiShort ? (BA_MEN_NAME[zhiShiShort] || `${zhiShiShort}门`) : fallbackPan.zhiShi,
		zhiFuPalace,
		zhiShiPalace,
		diPan: maps.diPan,
		tianPan: maps.tianPan,
		renPan: maps.renPan,
		shenPan: maps.shenPan,
		tianGan: maps.tianPan,
		tianXing: maps.tianXing,
		diPanList: mapListByPos(maps.diPan),
		tianPanList: mapListByPos(maps.tianPan),
		renPanList: mapListByPos(maps.renPan),
		shenPanList: mapListByPos(maps.shenPan),
		jiXingPalaces: specials.jiXingPalaces,
		ruMuPalaces: specials.ruMuPalaces,
		liuYiJiXing: specials.liuYi,
		qiYiRuMu: specials.ruMu,
		menPo,
		kongWangDesc: kongWangMeta.list,
		kongWangPalaces: kongWangMeta.palaces,
		yiMa,
		cells,
		options: {
			...(fallbackPan.options || {}),
			qimenEngineLabel: '',
			qimenModeLabel,
			paiPanLabel: getOptionLabel(PAIPAN_OPTIONS, opts.paiPanType),
			qijuMethodLabel: normalizeText(backendPan.qijuMethod) === 'zhirun' ? '置闰' : (normalizeText(getRawValue(raw, ['排盤方式', '排盘方式'], '')) || (fallbackPan.options ? fallbackPan.options.qijuMethodLabel : '')),
		},
		lunarText: fallbackPan.lunarText || (nongli ? `${nongli.year || ''}年${leapPrefix(nongli)}${nongli.month || ''}${nongli.day || ''}` : ''),
	};
}

