// 奇门遁甲排盘引擎门面(对外导入路径与导出不变):主入口 calcDunJia 在这里,其余按职责拆在 calc/ 下,依赖只朝前一层:
//   tables(常量表)→ basics(入参 / 干支 / 节气等底层工具)→ options(选项与流派口径)→ yinyangdun(阴阳遁局表与置闰)
//   → juMeta(年 / 月 / 日家起局)→ pan(刻家与排盘)→ kinqimen / shensha(后端取盘 / 神煞与金函日家)→ snapshot(AI 快照)。
// 读源码的检查读「子模块 + 门面」全集(scripts/source-sets.json)。
import { leapPrefix } from '../utils/lunarText.js';
import { jianChuRing } from '../utils/jianChu.js';
import { LUOSHU_NUM } from './DunJiaFaDoc.js';

import { resolveAfter23NewDay, resolveLateZiHourUseNextDay } from '../utils/dayBoundaryResolve.js';
import { SEX_OPTIONS, DATE_TYPE_OPTIONS, LEAP_MONTH_OPTIONS, XUSHI_OPTIONS, JIEQI_OPTIONS, PAIPAN_OPTIONS, KEJIA_FENDUN_OPTIONS, DAYJIA_JU_OPTIONS, ZHISHI_OPTIONS, YUEJIA_QIJU_OPTIONS, YEAR_GZ_OPTIONS, MONTH_GZ_OPTIONS, DAY_GZ_OPTIONS, DAY_SWITCH_OPTIONS, QIJU_METHOD_OPTIONS, ANGAN_MODE_OPTIONS, panAnGan, anZhiOf, GODS_PRESET_OPTIONS, applyGodsPreset, JIGONG_MODE_OPTIONS, resolveJiGong, SCHOOL_OPTIONS, normalizeSchool, KONG_MODE_OPTIONS, MA_MODE_OPTIONS, YIXING_OPTIONS } from './calc/options.js';
import { CNUMBER, JIU_XING, JJ, GUA_POS_MAP, JIU_XING_NAME, BA_MEN_NAME, computeShuziYongShenGong, GUXU, PALACE_NAME } from './calc/tables.js';
import { normalizeNum, normalizeShiftPalace, normalizeTimeAlg, getTimeAlgLabel, getOptionLabel, parseDateTime, getXunHead, latestSeedTermAt, resolveCurrentJieqi, resolveFuTouByBacktrack, juNumberToCn, buildQmjuByMeta, isYangDunJieqi } from './calc/basics.js';
import { YEARJIA_JU_OPTIONS, normalizeQijuMethod } from './calc/juMeta.js';
import { resolvePaiPanMeta, parseQmju, buildGanzhiForQimen, daykongShikong, zhifuNZhishi, leadStarOf, panEarth, panGod, panDoor, panStar, panSky, panFeipan, convertGuaMapToPos, getKongByMode, resolveKongWangPalaces, resolveYiMa, resolveSpecials, resolveMenPo, mapListByPos, rotateOuterMapByShift, rotateOuterPalaceNum, buildCells } from './calc/pan.js';
import { buildQimenShenSha, buildJinhanRiJiaPan } from './calc/shensha.js';
import { resolveJiGan, resolveYongShenGong, qimenFanGong, qimenZhuanGong, TUIYAN_VIEW_OPTIONS, TUIYAN_GONG_OPTIONS } from './calc/overlay.js';
export { SEX_OPTIONS, DATE_TYPE_OPTIONS, LEAP_MONTH_OPTIONS, XUSHI_OPTIONS, JIEQI_OPTIONS, PAIPAN_OPTIONS, JINHAN_MENPAI_OPTIONS, KEJIA_FENDUN_OPTIONS, DAYJIA_JU_OPTIONS, ZHISHI_OPTIONS, YUEJIA_QIJU_OPTIONS, YEAR_GZ_OPTIONS, MONTH_GZ_OPTIONS, DAY_GZ_OPTIONS, DAY_SWITCH_OPTIONS, QIJU_METHOD_OPTIONS, QIJU_METHOD_NONSHI_OPTIONS, qijuMethodUsesJieqiFa, qijuMethodOptionsFor, FEI_MEN_ZHONG_CAN_LABELS, MIX_LAYER_LABELS, mixLayerDefaultLabel, migrateLegacyQimenSchool, qijuMethodSelectValue, ZHIRUN_LEAP_OPTIONS, ANGAN_MODE_OPTIONS, panAnGan, anZhiOf, GODS_PRESET_OPTIONS, applyGodsPreset, JIGONG_MODE_OPTIONS, SHIFT_ZHIFU_OPTIONS, resolveJiGong, SCHOOL_OPTIONS, KONG_MODE_OPTIONS, MA_MODE_OPTIONS, TIME_ALG_OPTIONS, YIXING_OPTIONS, CHART_CATEGORY_OPTIONS } from './calc/options.js';
export { birthToYearGan, qimenGlyphScriptAttrs, buildQimenWangShuai, computeShuziYongShenGong, GUXU, QIMEN_WU_HE } from './calc/tables.js';
export { getXunHead } from './calc/basics.js';
export { YEARJIA_JU_OPTIONS } from './calc/juMeta.js';
export { isKinqimenMode, qimenLocalOnlyOverrides, isQimenLocalRoute, needJieqiYearSeed, jieqiSeedYears, jieqiSeedSignature, normalizeKinqimenData } from './calc/kinqimen.js';
export { panFeipan } from './calc/pan.js';
export { buildJinhanRiJiaPan } from './calc/shensha.js';
export { buildDunJiaSnapshotText } from './calc/snapshot.js';
export { TUIYAN_VIEW_OPTIONS, TUIYAN_GONG_OPTIONS, tuiYanRows, tuiYanLines, jiGanRows, jiGanLines, resolveJiGan, qimenFanGong, qimenZhuanGong } from './calc/overlay.js';

export function calcDunJia(fields, nongli, options, context){
	// 日家·古籍金函系=独立体系(查表盘,无局法/三盘),早返专用构建器。日界两键与主路径同样先经单源归一
	// (此前早返不归一:缺键按「不进位」算、'0' 字符串当成开,晚子时与主路径、请求体的全局口径不同)
	if(normalizeNum(options && options.paiPanType, 3) === 6){
		return buildJinhanRiJiaPan(fields, nongli, {
			...(options || {}),
			after23NewDay: resolveAfter23NewDay(options && options.after23NewDay),
			lateZiHourUseNextDay: resolveLateZiHourUseNextDay(options && options.lateZiHourUseNextDay),
		}, context);
	}
	const dateParts = parseDateTime(fields);
	if(!dateParts){
		return null;
	}
	const opts = {
		qijuMethod: 'zhirun',
		school: '转盘',
		kongMode: 'day',
		yimaMode: 'day',
		timeAlg: 0,
		shiftPalace: 0,
		fengJu: false,
		zhirunLeapDays: 9,
		...(options || {}),
	};
	// 日界两键缺键取全局现值(此前内部缺省 after23NewDay 写死 0,与请求体 / 扫描 / 页面的全局口径不同)
	opts.after23NewDay = resolveAfter23NewDay(opts.after23NewDay);
	opts.lateZiHourUseNextDay = resolveLateZiHourUseNextDay(opts.lateZiHourUseNextDay);
	// 旧数据迁移:阴盘曾为盘式(school='阴盘'),现为起局法(qijuMethod='shuzi')。须在 normalizeSchool(阴盘→转盘) 前判 raw school,
	// 保旧存盘(命盘/事盘/AI 快照)载入仍走报数定局。normalizeKenQimenOptions 已在 UI 层同迁,此为引擎兜底(覆盖任意直接调用方)。
	if(opts.school === '阴盘'){ opts.qijuMethod = 'shuzi'; }
	opts.qijuMethod = normalizeQijuMethod(opts.qijuMethod);
	opts.school = normalizeSchool(opts.school);
	opts.timeAlg = normalizeTimeAlg(opts.timeAlg);
	const shiftPalace = normalizeShiftPalace(opts.shiftPalace);

	const ganzhi = buildGanzhiForQimen(nongli || {}, dateParts, opts, context || {});
	// 节气含中气、时刻感知(种子优先;此前只取节令 → 每个节的后半整段错局)。
	const jieqi = resolveCurrentJieqi(nongli || {}, dateParts, context || {}, fields && fields.zone ? fields.zone.value : undefined);
	const paiPanMeta = resolvePaiPanMeta(opts, ganzhi, jieqi, dateParts, context || {});
	let qmju = paiPanMeta.qmju || buildQmjuByMeta(paiPanMeta.yinYangDun, paiPanMeta.juShu, paiPanMeta.sanYuan);
	// 数字起盘(起局=数字·报数,§5.5 通则):报数各位求和除9(余0作9)定局数;阴阳遁仍按节气;元沿用节气符头元。
	// 与盘式(转/飞/混)正交——任意盘式选数字起局皆生效。报数空 → 退节气拆补(占位不崩)。报数→用神宫供右栏/快照。传本有别。
	let shuziInfo = null;
	if(normalizeQijuMethod(opts.qijuMethod) === 'shuzi'){
		const shuziDigits = String(opts.shuziReportNumber || '').replace(/[^0-9]/g, '');
		if(shuziDigits){
			shuziInfo = computeShuziYongShenGong(shuziDigits);
			const shuziSum = shuziDigits.split('').reduce((acc, ch)=>acc + Number(ch), 0);
			const shuziJu = (shuziSum % 9) === 0 ? 9 : (shuziSum % 9);
			qmju = buildQmjuByMeta(isYangDunJieqi(jieqi) ? '阳遁' : '阴遁', shuziJu, paiPanMeta.sanYuan);
		}
	}
	// WP-A 盘式分流:飞盘走 panFeipan(洛书飞,一次算齐天/门/星/神+值符值使);转盘走原五函数(字节零回归)。
	// 月家(§9):排盘锚点用月柱(值符随月干、值使随月支、寻月柱旬首)→ 给排盘函数传 time=月柱 的 panGanzhi;
	// 时家/刻家等 panGanzhi===ganzhi(字节零回归)。
	// 各家排盘锚点:年家用年柱、月家用月柱、日家用日柱(值符随该柱天干、值使随该柱地支、寻该柱旬首);
	// 时家/刻家/综合 panGanzhi===ganzhi(字节零回归)。
	let panGanzhi = ganzhi;
	if(ganzhi){
		if(opts.paiPanType === 0 && ganzhi.year){ panGanzhi = { ...ganzhi, time: ganzhi.year }; }
		else if(opts.paiPanType === 1 && ganzhi.month){ panGanzhi = { ...ganzhi, time: ganzhi.month }; }
		else if(opts.paiPanType === 2 && ganzhi.day){ panGanzhi = { ...ganzhi, time: ganzhi.day }; }
	}
	const isFeipan = opts.school === '飞盘';
	const isHuohe = opts.school === '混合';                          // 飞转混合:星转·门飞·九神(专题§4.2)
	const fei = (isFeipan || isHuohe) ? panFeipan(panGanzhi, qmju, {
		feiXingShun: !!opts.feiXingShun, feiMenShun: !!opts.feiMenShun, feiShenShun: !!opts.feiShenShun,
		// 中门参与:页面传布尔 false,挂载 schema(select)传 0/'0' → 曾只认 false ⇒ 挂载「不参与(跳中)」恒死(中宫门位显示随之恒死)。
		feiMenZhongCan: !(opts.feiMenZhongCan === false || opts.feiMenZhongCan === 0 || opts.feiMenZhongCan === '0'),
		feiMenZhongShow: (opts.feiMenZhongShow === true || opts.feiMenZhongShow === 1 || opts.feiMenZhongShow === '1'),
	}) : null;
	// 转盘/混合 都需转盘值符值使(混合的值符星宫走转盘);飞盘走飞盘 zfzs。
	// 🔴 值符值使解算上下文:此前只有这一处传了 ext,而下面排八门的 panDoor 没传 →
	//    「值符星=禽」时 resolveSpecialZhiShi(undefined,…) 恒取 0 档,八门实际起排永远从死门起,
	//    与标题显示的值使门名自相矛盾(用户切「阴阳遁/节气」两档看不到盘面变化)。四处同源。
	const zfzsExt = {
		zhiShiType: opts.zhiShiType,
		yinYangDun: paiPanMeta.yinYangDun,
		jieqi,
		godsPreset: opts.godsPreset,   // 八神预设透传(panGod 消费)
		jiGongMode: opts.jiGongMode,   // 中宫寄宫档透传(panGod/panDoor/panStar/panSky 消费)
	};
	const zfzsZhuan = isFeipan ? null : zhifuNZhishi(panGanzhi, qmju, zfzsExt);
	// 混合:值符星宫=转盘(星轮转),值使门宫=飞盘(门飞泊);故取转盘 zfzs 但门宫换飞盘的。
	// 混合盘四层自由装配(mixTian/mixXing/mixMen/mixShen ∈ ''|'zhuan'|'fei';全缺省=历史组合:天转·星转·门飞·神飞)。
	const mixOf = (key, dft)=>{ const v = opts[key]; return (v === 'fei' || v === 'zhuan') ? v : dft; };
	const mixTian = mixOf('mixTian', 'zhuan');
	const mixXing = mixOf('mixXing', 'zhuan');
	const mixMen = mixOf('mixMen', 'fei');
	const mixShen = mixOf('mixShen', 'fei');
	const zfzs = isFeipan ? fei.zfzs : (isHuohe ? {
		...zfzsZhuan,
		// 值符星宫随星层来源、值使门宫随门层来源(层取转则用转盘解算,取飞则用飞盘解算)
		值符星宫: (mixXing === 'fei' && fei && fei.zfzs) ? fei.zfzs.值符星宫 : zfzsZhuan.值符星宫,
		值使门宫: (mixMen === 'fei' && fei && fei.zfzs) ? fei.zfzs.值使门宫 : zfzsZhuan.值使门宫,
	} : zfzsZhuan);
	const dipanGua = panEarth(qmju);
	const tianpanGua = isFeipan ? fei.tianpanGua : (isHuohe && mixTian === 'fei' ? fei.tianpanGua : panSky(panGanzhi, qmju, zfzsExt));
	const menGua = isFeipan ? fei.menGua : (isHuohe ? (mixMen === 'fei' ? fei.menGua : panDoor(panGanzhi, qmju, zfzsExt)) : panDoor(panGanzhi, qmju, zfzsExt));
	const starGua = isFeipan ? fei.starGua : (isHuohe && mixXing === 'fei' ? fei.starGua : panStar(panGanzhi, qmju, zfzsExt));
	const shenGua = isFeipan ? fei.shenGua : (isHuohe ? (mixShen === 'fei' ? fei.shenGua : panGod(panGanzhi, qmju, zfzsExt)) : panGod(panGanzhi, qmju, zfzsExt));
	const xunkong = daykongShikong(ganzhi.day, ganzhi.time);

	const diPanBase = convertGuaMapToPos(dipanGua);
	const tianPanBase = convertGuaMapToPos(tianpanGua);
	const menBase = convertGuaMapToPos(menGua);
	const starBase = convertGuaMapToPos(starGua);
	const shenBase = convertGuaMapToPos(shenGua);
	const diPan = rotateOuterMapByShift(diPanBase, shiftPalace);
	const tianPan = rotateOuterMapByShift(tianPanBase, shiftPalace);
	const men = rotateOuterMapByShift(menBase, shiftPalace);
	const star = rotateOuterMapByShift(starBase, shiftPalace);
	const shen = rotateOuterMapByShift(shenBase, shiftPalace);
	// 转盘八神名按预设分派(默认=历史恒虎玄);飞盘/混合九神保真(含勾陈/太常/朱雀),不替换。
	if(!isFeipan && !isHuohe){
		Object.keys(shen).forEach((k)=>{ shen[k] = applyGodsPreset(String(shen[k] || ''), opts.godsPreset); });
	}

	// 暗干层(默认 off=null 零回归):模式产每宫暗干;showAnZhi 开再配旬内暗支。
	// 🔴 ctx 必须传「卦名键」盘面(panAnGan 输出以卦名为键,cells 装配经 GUA_TO_NUM 反查):
	//   直接传 rotate 后的 men/diPan(宫号键)会产出数字键 → cells 全滤空(真机实抓的死链);
	//   故此处以 PALACE_NAME 把移星后的门/地盘归一回卦名键(暗干基于最终盘面,含移星)。
	const menByGua = {};
	const diByGua = {};
	const tianByGua = {};
	for(let g = 1; g <= 9; g++){
		const guaName = PALACE_NAME[g];
		if(!guaName){ continue; }
		menByGua[guaName] = men[g] || '';
		diByGua[guaName] = diPan[g] || '';
		tianByGua[guaName] = tianPan[g] || '';
	}
	// 寄干(中五干寄宫):地盘寄在寄宫,天盘随「从寄宫出发的那颗星」落宫;飞盘 / 天盘取飞的混合盘中宫自有星干,不寄(见 calc/overlay)
	const jiGongGua = resolveJiGong(opts.jiGongMode, paiPanMeta.yinYangDun, jieqi);
	const ji = resolveJiGan({ isFeipan: isFeipan || (isHuohe && mixTian === 'fei'), diPanBase, diPan, tianPan, jiGongGua });
	const shiDun = JJ[getXunHead(panGanzhi.time)] || '';
	const anGanMap = panAnGan(opts.anGanMode, {
		menGua: menByGua, dipanGua: diByGua, yy: paiPanMeta.yinYangDun,
		shiGan: (panGanzhi.time || '').charAt(0),
		zhishiGong: zfzs && zfzs.值使门宫 ? zfzs.值使门宫[1] : '',
		jiGong: jiGongGua,
		tianpanGua: tianByGua,   // 天盘干序转用(其余五法不读)
		jiTian: ji && ji.tianNum ? { gua: PALACE_NAME[ji.tianNum], gan: ji.gan } : null,
		shiDun,
	});
	const anZhiMap = (anGanMap && opts.showAnZhi)
		? Object.keys(anGanMap).reduce((acc, g)=>{ acc[g] = anZhiOf(anGanMap[g], panGanzhi.time); return acc; }, {})
		: null;

	const specials = resolveSpecials(tianPan);
	const menPo = resolveMenPo(men);
	// kongMarkBoth=同时标日空+时空(并集);默认关=单模式(现状字节稳)
	const kongWang = opts.kongMarkBoth ? `${xunkong.日空 || ''}${xunkong.时空 || ''}` : getKongByMode(opts.kongMode, xunkong);
	const kongWangMeta = resolveKongWangPalaces(kongWang);
	// showAllKong=四柱空亡全览(纯附加信息,默认关=null 零回归)
	const allKong = opts.showAllKong ? {
		年空: GUXU[getXunHead(ganzhi.year)] || '',
		月空: GUXU[getXunHead(ganzhi.month)] || '',
		日空: xunkong.日空 || '',
		时空: xunkong.时空 || '',
	} : null;
	const yiMaMeta = resolveYiMa(opts.yimaMode, ganzhi);
	const isDiurnal = context && context.isDiurnal !== undefined && context.isDiurnal !== null
		? !!context.isDiurnal
		: (nongli && nongli.isDiurnal !== undefined && nongli.isDiurnal !== null ? !!nongli.isDiurnal : null);

	let zhiFuPalace = rotateOuterPalaceNum(GUA_POS_MAP[zfzs.值符星宫[1]] || 5, shiftPalace);
	let zhiShiPalace = rotateOuterPalaceNum(GUA_POS_MAP[zfzs.值使门宫[1]] || 5, shiftPalace);
	let zfStarRaw = (zfzs.值符星宫[0] || '');
	// 值符是天禽时,代它领盘的是寄宫之星(寄坤 = 天芮,显「天内」;其它寄宫档 = 寄宫那一宫的星):值符名与九星层取同一颗。
	// 星层取飞盘(九星含中宫,天禽自有本位)时不代。
	const leadOfQin = (isFeipan || (isHuohe && mixXing === 'fei')) ? '禽' : leadStarOf('禽', zfzsExt, paiPanMeta.yinYangDun);
	if(zfStarRaw === '禽'){ zfStarRaw = leadOfQin; }
	let zsDoorRaw = (zfzs.值使门宫[0] || '');
	// 移星值符两档:follow(默认)=标记随几何平移;recalc=移后盘视为新局按标准定义重解——
	//   新值符星/值使门 = 移后地盘旬首遁仪所在宫的本位星/本位门(门为「中」依转盘传统取死门),
	//   标记宫 = 新星名/门名在移后星层/门层的实际落宫。仅移星≠0 时生效(=0 两档恒同,默认零回归)。
	if(opts.shiftZhiFuMode === 'recalc' && normalizeShiftPalace(shiftPalace) !== 0){
		const dunYi = JJ[getXunHead(panGanzhi.time)] || '戊';
		let dg = 0;
		for(let i = 1; i <= 9; i++){ if(String(diPan[i] || '') === dunYi){ dg = i; break; } }
		if(dg){
			const luoshu = LUOSHU_NUM[PALACE_NAME[dg]] || 5;
			let newStar = JIU_XING[luoshu - 1] || '';
			if(newStar === '禽'){ newStar = leadOfQin; }   // 遁仪在中五:新值符 = 代天禽领盘的那颗星
			let newDoor = '休死伤杜中开惊生景'.charAt(luoshu - 1) || '';
			if(newDoor === '中' && !isFeipan){ newDoor = '死'; }
			const starMatch = (cellStar)=>{
				const cs = String(cellStar || '');
				if(!newStar){ return false; }
				if(cs.indexOf(newStar) >= 0){ return true; }
				return ('芮禽'.indexOf(newStar) >= 0) && cs.indexOf('内') >= 0;   // 转盘芮/禽归一显「内」
			};
			for(let i = 1; i <= 9; i++){ if(starMatch(star[i])){ zhiFuPalace = i; break; } }
			for(let i = 1; i <= 9; i++){ if(String(men[i] || '').charAt(0) === newDoor){ zhiShiPalace = i; break; } }
			zfStarRaw = newStar || zfStarRaw;
			zsDoorRaw = newDoor || zsDoorRaw;
		}
	}
	const zfStarDisp = isFeipan ? zfStarRaw : zfStarRaw.replace(/[芮禽]+/g, '内');   // 转盘值符=天禽(中宫禽/芮)时显「内」(天内),飞盘保「禽」
	const zhiFu = JIU_XING_NAME[zfStarDisp] || `${zfStarDisp}`;
	const zhiShi = BA_MEN_NAME[zsDoorRaw] || `${zsDoorRaw}门`;

	// 暗干卦名键→宫号键(cells 以 palaceNum 索引)
	const GUA_TO_NUM = Object.keys(PALACE_NAME).reduce((acc, n)=>{ acc[PALACE_NAME[n]] = Number(n); return acc; }, {});
	const anGanByNum = anGanMap ? Object.keys(anGanMap).reduce((acc, gua)=>{ if(GUA_TO_NUM[gua]){ acc[GUA_TO_NUM[gua]] = anGanMap[gua]; } return acc; }, {}) : null;
	const anZhiByNum = anZhiMap ? Object.keys(anZhiMap).reduce((acc, gua)=>{ if(GUA_TO_NUM[gua]){ acc[GUA_TO_NUM[gua]] = anZhiMap[gua]; } return acc; }, {}) : null;
	const cells = buildCells(diPan, tianPan, men, shen, star, zhiFuPalace, zhiShiPalace, {
		jiXingPalaces: specials.jiXingPalaces,
		ruMuPalaces: specials.ruMuPalaces,
		menPoPalaces: menPo.palaces,
		kongWangPalaces: kongWangMeta.palaces,
		yimaPalace: yiMaMeta.palace,
		godsPreset: opts.godsPreset,
		anGanByNum,
		anZhiByNum,
		school: opts.school,
	});
	// 寄干 / 天禽显示(默认关:格子不加键,盘面逐字节同旧)
	const showJiGan = !!opts.showJiGan && !!ji;
	// 星层取飞的混合盘:禽在星层有自己的落宫,「随寄宫之星落某宫」的附注与它不同宫 —— 不出
	const showTianQin = !!opts.showTianQin && !!(ji && ji.tianNum) && !(isHuohe && mixXing === 'fei');
	if(showJiGan || showTianQin){
		cells.forEach((cell)=>{
			if(showJiGan && cell.palaceNum === ji.tianNum){ cell.jiTianGan = ji.gan; }
			if(showJiGan && cell.palaceNum === ji.diNum){ cell.jiDiGan = ji.gan; }
			if(showTianQin && cell.palaceNum === ji.tianNum){ cell.tianQin = true; }
		});
	}
	// 推演显示(翻宫 / 转宫;默认常规=不出键):只在盘面上标路径、右栏与快照写推演,不改任何排盘结果
	const tuiYanView = (opts.tuiYanView === 'fan' || opts.tuiYanView === 'zhuan') ? opts.tuiYanView : '';
	let tuiYan = null;
	if(tuiYanView){
		const gongSpec = opts.tuiYanGong || 'shigan';
		const start = resolveYongShenGong(gongSpec, { tianPan, shiGan: (panGanzhi.time || '').charAt(0), shiDun, ji, zhiFuPalace, zhiShiPalace });
		tuiYan = {
			view: tuiYanView,
			gong: gongSpec,
			gongLabel: getOptionLabel(TUIYAN_GONG_OPTIONS, gongSpec),
			start,
			fan: tuiYanView === 'fan' ? qimenFanGong({ tianPan, diPan, ji, start }) : null,
			zhuan: tuiYanView === 'zhuan' ? qimenZhuanGong({ star, men, kongPalaces: kongWangMeta.palaces, start }) : null,
		};
		const tags = {};
		const add = (n, t)=>{ if(n){ (tags[n] = tags[n] || []).push(t); } };
		add(start, '用');
		if(tuiYan.fan){
			tuiYan.fan.up.forEach((st, i)=>add(st.num, `上${i + 1}`));
			tuiYan.fan.down.forEach((st, i)=>add(st.num, `下${i + 1}`));
		}
		if(tuiYan.zhuan){
			tuiYan.zhuan.kong.forEach((k)=>add(k.from, `空转${PALACE_NAME[k.to]}`));
			if(tuiYan.zhuan.startXianTian){ add(tuiYan.zhuan.startXianTian, '先天位'); }
		}
		cells.forEach((cell)=>{ if(tags[cell.palaceNum]){ cell.tuiYanTags = tags[cell.palaceNum]; } });
	}

	const qmjuMeta = parseQmju(qmju);

	return {
		anGan: anGanMap,   // 每宫暗干(off=null);盘面/快照消费
		...(showJiGan || showTianQin ? { jiGan: { ...ji, show: showJiGan, tianQin: showTianQin } } : {}),   // 寄干 / 天禽(开关开才出键)
		...(tuiYan ? { tuiYan } : {}),   // 推演(翻宫 / 转宫;开才出键)
		...(opts.showJianChu ? { jianChu: jianChuRing(ganzhi, dateParts.dateStr) } : {}),   // 十二建星外环(开才出键;盘面外环 / 右栏卡 / 快照同一份)
		anZhi: anZhiMap,   // 每宫暗支(showAnZhi 开时;随暗干)
		allKong,           // 四柱空亡全览(showAllKong 开;默认 null)
		xunKong: xunkong,  // {日空,时空}恒暴露(kongMarkBoth 显示层拆分消费)
		keIndex: paiPanMeta.keIndex || null,   // 刻家第几刻(1..10;非刻家=null)
		keGanZhi: paiPanMeta.keGanZhi || '',   // 刻柱干支(时柱锚法:首刻=时柱逐刻进一;非刻家='')
		keTimeGanZhi: paiPanMeta.keTimeGanZhi || '',   // 刻家所用时柱(子正换时开时可≠四柱时柱)
		dateStr: dateParts.dateStr,
		timeStr: dateParts.timeStr,
		realSunTime: (context && context.displaySolarTime) || (nongli ? (nongli.birth || '') : ''),
		lunarText: nongli ? `${nongli.year || ''}年${leapPrefix(nongli)}${nongli.month || ''}${nongli.day || ''}` : '',
		jiedelta: nongli ? (nongli.jiedelta || '') : '',
		ganzhi,
		fuTou: resolveFuTouByBacktrack(ganzhi.day),
		// 节气 chip/快照用「定局节气」——置闰超神时≠曆法节气,旧拼法(曆法节气+定局元)会出
		// 「阳遁七局中元+大雪中元」矛盾串(2026-08-02 缺陷②修);曆法节气另存 lifaJieqi 供参照。
		jieqiText: `${paiPanMeta.dingjuJieqi || jieqi || '未知节气'}${paiPanMeta.sanYuan !== undefined ? paiPanMeta.sanYuan : (qmjuMeta.yuan || '')}`,
		dingjuJieqi: paiPanMeta.dingjuJieqi || jieqi || '',
		lifaJieqi: jieqi || '',
		yinYangDun: paiPanMeta.yinYangDun || (qmjuMeta.yy === '阴' ? '阴遁' : '阳遁'),
		sanYuan: paiPanMeta.sanYuan !== undefined ? paiPanMeta.sanYuan : (qmjuMeta.yuan || ''),
		juShu: juNumberToCn(paiPanMeta.juShu || (CNUMBER.indexOf(qmjuMeta.kook) + 1)),
		juText: qmju,
		xunShou: getXunHead(ganzhi.day),
		kongWang,
		zhiFu,
		zhiShi,
		zhiFuPalace,
		zhiShiPalace,
		shiftPalace,
		fengJu: !!opts.fengJu,
		school: opts.school,
		shuziInfo,
		diPan,
		tianPan,
		renPan: men,
		shenPan: shen,
		tianGan: tianPan,
		diPanList: mapListByPos(diPan),
		tianPanList: mapListByPos(tianPan),
		renPanList: mapListByPos(men),
		shenPanList: mapListByPos(shen),
		jiXingPalaces: specials.jiXingPalaces,
		ruMuPalaces: specials.ruMuPalaces,
		liuYiJiXing: specials.liuYi,
		qiYiRuMu: specials.ruMu,
		menPo,
		kongWangDesc: kongWangMeta.list,
		kongWangPalaces: kongWangMeta.palaces,
		yiMa: yiMaMeta,
		shenSha: buildQimenShenSha(ganzhi, isDiurnal),
		isDiurnal,	// 择日 plateKey diurnal 掩位供数(shenSha 昼夜口径同源;纯附加键)
		cells,
		xunkong,
		options: {
			sexLabel: getOptionLabel(SEX_OPTIONS, opts.sex),
			// 盘类(命局/事局)随 opts 进 pan.options:页面 calc 后手写同键(DunJiaMain),无头/三式重算路径此前缺此
			// ⇒ 挂载「盘类=命局」齿轮恒死(全局速览段恒按事局)。未传则不写键(向后兼容:缺 chartCategory=事局)。
			...(opts.chartCategory !== undefined && opts.chartCategory !== null && opts.chartCategory !== '' ? { chartCategory: opts.chartCategory } : {}),
			dateTypeLabel: getOptionLabel(DATE_TYPE_OPTIONS, opts.dateType),
			leapLabel: getOptionLabel(LEAP_MONTH_OPTIONS, opts.leapMonthType),
			xuShiLabel: getOptionLabel(XUSHI_OPTIONS, opts.xuShiSuiType),
			jieQiLabel: getOptionLabel(JIEQI_OPTIONS, opts.jieQiType),
			paiPanLabel: getOptionLabel(PAIPAN_OPTIONS, opts.paiPanType),
			// 飞盘/混合档值使由飞宫定序直出,取法开关不参与 → 回显如实标注(勿谎报所选取法生效)
			zhiShiLabel: (isFeipan || isHuohe) ? '飞宫定序(取法不适用)' : getOptionLabel(ZHISHI_OPTIONS, opts.zhiShiType),
			zhiShiType: (isFeipan || isHuohe) ? 0 : (Number(opts.zhiShiType) || 0),   // 非缺省档快照「盘型」出注记(与中宫寄宫同例)
			yueJiaLabel: getOptionLabel(YUEJIA_QIJU_OPTIONS, opts.yueJiaQiJuType),
			yearLabel: getOptionLabel(YEAR_GZ_OPTIONS, opts.yearGanZhiType),
			monthLabel: getOptionLabel(MONTH_GZ_OPTIONS, opts.monthGanZhiType),
			dayLabel: getOptionLabel(DAY_GZ_OPTIONS, opts.dayGanZhiType),
			daySwitchLabel: getOptionLabel(DAY_SWITCH_OPTIONS, opts.after23NewDay),
			qijuMethodLabel: getOptionLabel(QIJU_METHOD_OPTIONS, opts.qijuMethod),
			schoolLabel: getOptionLabel(SCHOOL_OPTIONS, opts.school),
			godsPreset: opts.godsPreset || 'baihu_xuanwu',
			godsPresetLabel: getOptionLabel(GODS_PRESET_OPTIONS, opts.godsPreset || 'baihu_xuanwu'),
			jiGongMode: opts.jiGongMode || 'kun',
			jiGongModeLabel: getOptionLabel(JIGONG_MODE_OPTIONS, opts.jiGongMode || 'kun'),
			feiXingShun: !!opts.feiXingShun,
			feiMenShun: !!opts.feiMenShun,
			feiShenShun: !!opts.feiShenShun,
			feiMenZhongCan: !(opts.feiMenZhongCan === false || opts.feiMenZhongCan === 0 || opts.feiMenZhongCan === '0'),
			feiMenZhongShow: !!opts.feiMenZhongShow,
			mixTian: (opts.mixTian === 'fei' || opts.mixTian === 'zhuan') ? opts.mixTian : '',
			mixXing: (opts.mixXing === 'fei' || opts.mixXing === 'zhuan') ? opts.mixXing : '',
			mixMen: (opts.mixMen === 'fei' || opts.mixMen === 'zhuan') ? opts.mixMen : '',
			mixShen: (opts.mixShen === 'fei' || opts.mixShen === 'zhuan') ? opts.mixShen : '',
			kongMarkBoth: !!opts.kongMarkBoth,
			showAllKong: !!opts.showAllKong,
			shiftZhiFuMode: opts.shiftZhiFuMode === 'recalc' ? 'recalc' : 'follow',
			dayJiaJu: opts.dayJiaJu || 'yiyuan',
			dayJiaJuLabel: getOptionLabel(DAYJIA_JU_OPTIONS, opts.dayJiaJu || 'yiyuan'),
			keJiaFenDun: opts.keJiaFenDun || 'zihou',
			keJiaFenDunLabel: getOptionLabel(KEJIA_FENDUN_OPTIONS, opts.keJiaFenDun || 'zihou'),
			keZiZhengHuanShi: !!opts.keZiZhengHuanShi,
			yearJiaJu: opts.yearJiaJu === 'yinian' ? 'yinian' : 'sanyuan',
			yearJiaJuLabel: getOptionLabel(YEARJIA_JU_OPTIONS, opts.yearJiaJu === 'yinian' ? 'yinian' : 'sanyuan'),
			anGanModeLabel: getOptionLabel(ANGAN_MODE_OPTIONS, opts.anGanMode || 'off'),
			...(opts.showJiGan ? { showJiGan: true } : {}),
			...(opts.showTianQin ? { showTianQin: true } : {}),
			...(opts.showJianChu ? { showJianChu: true } : {}),
			...(tuiYanView ? { tuiYanView, tuiYanViewLabel: getOptionLabel(TUIYAN_VIEW_OPTIONS, tuiYanView), tuiYanGong: opts.tuiYanGong || 'shigan' } : {}),
			fullNameTips: !!opts.fullNameTips,
			// 当前实际所用定局法:数字盘=报数定局;各家自有定局(年/月/日/刻);时家/综合用拆补/置闰/茅山/无闰选择。
			dingFaLabel: (opts.qijuMethod === 'shuzi' && shuziInfo) ? '阴盘·报数定局'
				: opts.paiPanType === 0 ? (opts.yearJiaJu === 'yinian' ? '逐年换局·皆阴遁' : '三元起宫·皆阴遁')
					: opts.paiPanType === 1 ? (normalizeNum(opts.yueJiaQiJuType, 0) === 2 ? '逐月换局·皆阴遁' : (normalizeNum(opts.yueJiaQiJuType, 0) === 1 ? '年支直取·皆阴遁' : '年符头定局·皆阴遁'))
						: opts.paiPanType === 2 ? '节气三元·六十日一局'
							: opts.paiPanType === 4 ? (opts.keJiaFenDun === 'jieqi' ? '十分局·节气分遁' : '十分局·子后阳午后阴')
								: getOptionLabel(QIJU_METHOD_OPTIONS, opts.qijuMethod),
			// 中间盘角标:X家（X盘）=排盘体例（定局法/盘式短名）。
			boardTag: (function(){
				const fam = String(getOptionLabel(PAIPAN_OPTIONS, opts.paiPanType) || '时家奇门').replace('奇门', '').replace('排盘', '');
				let method;
				if(opts.qijuMethod === 'shuzi' && shuziInfo){ method = '阴盘'; }
				else if(opts.paiPanType === 0){ method = (opts.yearJiaJu === 'yinian' ? '逐年' : '三元'); }
				else if(opts.paiPanType === 1){ method = (normalizeNum(opts.yueJiaQiJuType, 0) === 2 ? '逐月' : (normalizeNum(opts.yueJiaQiJuType, 0) === 1 ? '年支' : '符头')); }
				else if(opts.paiPanType === 2){ method = '节气'; }
				else if(opts.paiPanType === 4){ method = '十分局'; }
				else { method = getOptionLabel(QIJU_METHOD_OPTIONS, opts.qijuMethod); }
				const panShi = (opts.school === '飞盘') ? '飞盘' : (opts.school === '混合' ? '飞转' : '转盘');
				return fam + '·' + panShi + '（' + method + '）';
			})(),
			kongModeLabel: getOptionLabel(KONG_MODE_OPTIONS, opts.kongMode),
			yimaModeLabel: getOptionLabel(MA_MODE_OPTIONS, opts.yimaMode),
			timeAlgLabel: getTimeAlgLabel(opts.timeAlg),
			shiftLabel: getOptionLabel(YIXING_OPTIONS, shiftPalace),
			fengJuLabel: opts.fengJu ? '已封局' : '未封局',
		},
	};
}

// 仅供单测:当前节气解析(种子 → 本地种子 → nongli 兜底),不改任何行为。
export const __testing__ = { resolveCurrentJieqi, latestSeedTermAt };
