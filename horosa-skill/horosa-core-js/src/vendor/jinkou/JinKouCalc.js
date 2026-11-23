// 金口诀排盘引擎门面(对外导入路径与导出不变):主入口 buildJinKouData 在这里,其余按职责拆在 calc/ 下,依赖只朝前一层:
//   tables(常量表)→ basics(取干支 / 节气 / 地分与四位的底层工具)→ wangShuai(用爻与旺衰)→ shensha(神煞逐行起例)
//   → readings / layers(断法层上 / 下)→ backend(后端排盘结果归一与取盘)。读源码的检查读「子模块 + 门面」全集(scripts/source-sets.json)。
import * as LRConst from '../liureng/LRConst.js';
import { JINKOU_CATEGORY_RULES } from './JinKouDoc.js';

import { containsVal, getDayGan, getDayZi, getDayGanZi, getYearGanZi, getMonthZi, getYearZi, getTimeZi, normalizeDiFen, getStemByWuZiDun, getGuiShenAtDiFen, buildJinKouPlates, getYueJiang, getJiangZiAtDiFen, parseBranches, calcSiDaKongWang, getElem, getMonthIndexByZi, getSeasonByMonthZi, getYinYangSign, rowZhi } from './calc/basics.js';
import { resolveYongYao, getSeason, calcJinKouWangElem, buildJinKouWangShuaiMap } from './calc/wangShuai.js';
import { calcJinKouShenShaRows, buildRow } from './calc/shensha.js';
import { buildJinKouRelations, buildJinKouBihe, buildJinKouXiangyi, buildJinKouNianYueRi, buildJinKouJishi, buildJinKouDong, buildJinKouErDun, buildJinKouCiKe, buildJinKouYiXing, buildJinKouShiJian, buildJinKouTopic, buildJinKouTopicJue } from './calc/readings.js';
import { buildJinKouXingNian, jinKouPhaseTable, buildJinKouYinPan, buildJinKouNeiWai, buildJinKouHezhan, buildJinKouFangWei, buildJinKouSixiangShu, buildJinKouSixiangWuxing, buildJinKouGeju, buildJinKouSiQiu, buildJinKouBranchRelations, buildJinKouTaixuan, buildJinKouYongStrength, buildJinKouYingQi, buildJinKouShenshaDoc } from './calc/layers.js';
export { JinKouElementColor, JinKouYueJiangName, JinKouShenShaOrder } from './calc/tables.js';
export { calcJinKouWangElem, buildJinKouWangShuaiMap } from './calc/wangShuai.js';
export { buildJinKouBihe, jinKouZiByNumber, jinKouZiByColor, jinKouZiByShengXiao, resolveDiFenBySource, buildJinKouErDun, buildJinKouCiKe, buildJinKouYiXing, buildJinKouShiJian, buildJinKouTopic, JINKOU_TOPIC_KEYS, buildJinKouTopicJue } from './calc/readings.js';
export { buildJinKouXingNian, JINKOU_SOIL_PHASE_START, jinKouSoilStart, jinKouPhaseTable, JINKOU_HEZHAN_FOCUS, JINKOU_HEZHAN_TIME } from './calc/layers.js';
export { normalizeKinjinkouData } from './calc/backend.js';

export function buildJinKouData(liureng, options){
	const opt = options ? options : {};
	if(!liureng || !liureng.nongli){
		return {
			ready: false,
			diFen: '子',
			timeZi: '',
			rows: [],
			shenshaRows: [],
			xunKongBranches: [],
			siDaKong: '',
		};
	}

	const dayGan = getDayGan(liureng);
	const monthZi = getMonthZi(liureng);
	// 占时（zhanShi）：默认取八字时支；AI 挂载/主页面可指定具体地支（非 'auto' 且为合法支时覆盖）。
	const autoTimeZi = getTimeZi(liureng);
	const timeZi = (opt.zhanShi && opt.zhanShi !== 'auto' && containsVal(LRConst.ZiList, opt.zhanShi)) ? opt.zhanShi : autoTimeZi;
	const diFen = normalizeDiFen(opt.diFen, timeZi);
	const renYuanGan = getStemByWuZiDun(dayGan, diFen);
	// 排盘流派(P0-1)：月将换将(中气/交节)、贵人昼夜表(实务/古法)、起贵神盘(地盘/天盘)、盘式(阳/阴占位)。
	const schoolYueJiang = opt.schoolYueJiang === 'jiaojie' ? 'jiaojie' : 'zhongqi';
	const schoolGuiTable = opt.schoolGuiTable === 'liuren' ? 'liuren' : 'shiwu';
	const schoolGuiPan = opt.schoolGuiPan === 'tian' ? 'tian' : 'di';
	const panShi = opt.panShi === 'yin' ? 'yin' : 'yang';
	// 土之十二长生：默认「水土同宫」(申)，少数派「火土同宫」(寅)；默认值即现状，零回归。
	const soilChangSheng = opt.soilChangSheng === 'yin' ? 'yin' : 'shen';
	// 月将（yueJiang）先算(天盘起贵神依赖月将)：默认按节气取；可手动覆盖。
	const autoYueJiang = getYueJiang(liureng, monthZi, schoolYueJiang);
	const yuejiang = (opt.yueJiang && opt.yueJiang !== 'auto' && containsVal(LRConst.ZiList, opt.yueJiang)) ? opt.yueJiang : autoYueJiang;
	const guiShen = getGuiShenAtDiFen(dayGan, timeZi, diFen, opt.guirengType, opt.isDiurnal, { guiTable: schoolGuiTable, guiPan: schoolGuiPan, yuejiang: yuejiang });
	const guiZi = guiShen.zi;
	const guiGan = getStemByWuZiDun(dayGan, guiZi);
	const jiang = getJiangZiAtDiFen(yuejiang, timeZi, diFen);
	const jiangZi = jiang.zi;
	const jiangGan = getStemByWuZiDun(dayGan, jiangZi);

	const xunKongBranches = parseBranches(liureng.xun ? liureng.xun['旬空'] : '');
	const siDaKong = calcSiDaKongWang(liureng.xun ? liureng.xun['旬首'] : '');

	const renElem = getElem(renYuanGan);
	const guiElem = getElem(guiZi);
	const jiangElem = getElem(jiangZi);
	const diElem = getElem(diFen);

	const renSign = getYinYangSign(renYuanGan);
	const guiSign = getYinYangSign(guiZi);
	const jiangSign = getYinYangSign(jiangZi);
	const diSign = getYinYangSign(diFen);
	const lineSigns = [{
		label: '人元',
		sign: renSign,
	}, {
		label: '贵神',
		sign: guiSign,
	}, {
		label: '将神',
		sign: jiangSign,
	}, {
		label: '地分',
		sign: diSign,
	}];
	const yongYao = resolveYongYao(lineSigns);

	const wangElem = calcJinKouWangElem([renElem, guiElem, jiangElem, diElem]);
	const wangShuaiMap = buildJinKouWangShuaiMap(wangElem);
	const getJinKouSeason = (elem)=>{
		if(elem && wangShuaiMap[elem]){
			return wangShuaiMap[elem];
		}
		return getSeason(liureng, elem);
	};

	const rows = [
		buildRow({
			label: '人元',
			gan: '-',
			content: renYuanGan,
			shenjiang: '-',
			elem: renElem,
			ganElem: renElem,
			sign: renSign,
			season: getJinKouSeason(renElem),
			branch: '',
			emptyBranches: xunKongBranches,
			siDaKong: siDaKong,
		}),
		buildRow({
			label: '贵神',
			gan: guiGan,
			content: guiZi,
			shenjiang: guiShen.name,
			elem: guiElem,
			ganElem: getElem(guiGan),
			sign: guiSign,
			season: getJinKouSeason(guiElem),
			branch: guiZi,
			emptyBranches: xunKongBranches,
			siDaKong: siDaKong,
		}),
		buildRow({
			label: '将神',
			gan: jiangGan,
			content: jiangZi,
			shenjiang: jiang.name,
			elem: jiangElem,
			ganElem: getElem(jiangGan),
			sign: jiangSign,
			season: getJinKouSeason(jiangElem),
			branch: jiangZi,
			emptyBranches: xunKongBranches,
			siDaKong: siDaKong,
		}),
		buildRow({
			label: '地分',
			gan: '-',
			content: diFen,
			shenjiang: '-',
			elem: diElem,
			ganElem: diElem,
			sign: diSign,
			season: getJinKouSeason(diElem),
			branch: diFen,
			emptyBranches: xunKongBranches,
			siDaKong: siDaKong,
		}),
	];

	const shenshaRows = calcJinKouShenShaRows(liureng, rows, {
		renYuanGan: renYuanGan,
		guiZi: guiZi,
		jiangElem: jiangElem,
	});

	// 解读层派生字段（全部确定性纯计算：生克关系/五动三动/格局/应期/神煞判语/四象取象/合占直断）
	const dayZi = getDayZi(liureng);
	const yearZi = getYearZi(liureng);
	const yongRow = yongYao && yongYao.label ? rows.find((r)=>r.label === yongYao.label) : null;
	const shenshaDoc = buildJinKouShenshaDoc(shenshaRows, yongYao ? yongYao.label : '');
	const jkRelations = buildJinKouRelations(rows);
	const jkBihe = buildJinKouBihe(rows);
	const jkBranchRelations = buildJinKouBranchRelations(rows, dayZi);
	const jkTaixuan = buildJinKouTaixuan(rows);
	const jkYongStrength = buildJinKouYongStrength(yongYao, rows, wangShuaiMap);
	const jkYingQi = buildJinKouYingQi({ yongRow: yongRow, rows: rows, dayGan: dayGan, dayZi: dayZi, timeZi: timeZi, yearZi: yearZi, guiGan: guiGan, guiZi: guiZi, wangShuaiMap: wangShuaiMap, xunKongBranches: xunKongBranches });
	const jkDong = buildJinKouDong(rows, xunKongBranches, yongYao ? yongYao.label : '');
	const jkGeju = buildJinKouGeju(rows);
	// 四丘按季支另判（需月令季节，与四位结构类格局分开算后并入同一列表）。
	const jkSiQiu = buildJinKouSiQiu(rows, getSeasonByMonthZi(monthZi));
	if(jkSiQiu){ jkGeju.push(jkSiQiu); }
	const jkFourBranches = rows.map((r)=>rowZhi(r)).filter(Boolean);
	// 四位带干之柱(贵神=神干+本家支、将神=将干+将神支)——真太岁比对整柱用。
	const jkFourGanZi = [`${guiGan}${guiZi}`, `${jiangGan}${jiangZi}`].filter((s)=>s && s.length === 2);
	const jkNianYueRi = buildJinKouNianYueRi(yearZi, monthZi, getMonthIndexByZi(monthZi), dayZi, jkFourBranches, {
		yearGanZi: getYearGanZi(liureng),
		dayGanZi: getDayGanZi(liureng),
		fourGanZi: jkFourGanZi,
		jiangZi: jiangZi,
	});
	const jkJishi = buildJinKouJishi(monthZi, dayGan, timeZi);
	const jkSixiangShu = buildJinKouSixiangShu(rows);
	const jkSixiangWuxing = buildJinKouSixiangWuxing(rows, wangElem);
	const jkFangWei = buildJinKouFangWei(dayGan);
	// 专题起式（定局法）：二遁人元恒算（细象常用）；次客/移星换将为参考式；
	// 测年月日与七专题按 opt.topicKey / opt.benMing 产出，未选则为 null（零额外开销）。
	const jkErDun = buildJinKouErDun(renYuanGan, diFen);
	const jkCiKe = buildJinKouCiKe({
		yuejiang: yuejiang, timeZi: timeZi, diFen: diFen, dayGan: dayGan, dayZi: dayZi,
		guiName: guiShen.name,
		yongZhi: yongRow ? rowZhi(yongRow) : '',
		yongGan: yongRow && yongRow.gan && yongRow.gan !== '-' ? yongRow.gan : (yongYao && yongYao.label === '人元' ? renYuanGan : ''),
	});
	const jkYiXing = buildJinKouYiXing(dayGan);
	const topicCtx = {
		yuejiang: yuejiang, timeZi: timeZi, diFen: diFen, yearZi: yearZi,
		benMing: opt.benMing || '', renYuanGan: renYuanGan, dayGan: dayGan,
	};
	const jkTopic = opt.topicKey ? buildJinKouTopic(opt.topicKey, topicCtx) : null;
	const jkTopicJue = opt.topicKey ? buildJinKouTopicJue(opt.topicKey, {
		diFen: diFen, jiangZi: jiangZi, guiName: guiShen.name,
		erDunGan: jkErDun ? jkErDun.gan : '', rows: rows,
	}) : null;
	// 金口诀行年（旬法）：与既有干支流年并存，不替换 runyear。
	const jkXingNian = (opt.birthGanZi && opt.age) ? buildJinKouXingNian(opt.birthGanZi, opt.gender, opt.age) : null;
	const jkShiJian = opt.shiJianKind ? buildJinKouShiJian(opt.shiJianKind, {
		yuejiang: yuejiang, yearZi: yearZi, monthZi: monthZi, dayZi: dayZi, benMing: opt.benMing || '',
	}) : null;
	// 阴盘三层仅在盘式=阴盘时产出（阳盘恒 null → 断法主线与既有输出零回归）。
	const jkYinPan = panShi === 'yin' ? buildJinKouYinPan(rows, dayGan, liureng.season, soilChangSheng) : null;
	const jkNeiWai = buildJinKouNeiWai(rows, yongYao ? yongYao.label : '');
	const jkHezhan = buildJinKouHezhan({
		rows: rows,
		yongLabel: yongYao ? yongYao.label : '',
		askKey: opt.askKey || '',
		timeScope: opt.timeScope || 'default',
		dong: jkDong,
		relevantShensha: shenshaDoc.relevant,
		neiwai: jkNeiWai,
	});

	return {
		ready: true,
		diFen: diFen,
		timeZi: timeZi,
		monthZi: monthZi,
		dayGan: dayGan,
		renYuanGan: renYuanGan,
		guiName: guiShen.name,
		guiZi: guiZi,
		guiGan: guiGan,
		guiStartZi: guiShen.startZi,
		isDay: guiShen.isDay,
		dayBasis: guiShen.dayBasis || 'branch',
		dayBasisText: guiShen.dayBasisText || '时支粗判·卯至申为昼',
		jiangZi: jiangZi,
		jiangName: jiang.name,
		jiangGan: jiangGan,
		yuejiang: jiang.yuejiang,
		xunKongBranches: xunKongBranches,
		siDaKong: siDaKong,
		wangElem: wangElem,
		wangShuai: wangShuaiMap,
		lineSigns: lineSigns,
		yongYao: yongYao,
		rows: rows,
		shenshaRows: shenshaRows,
		dayZi: dayZi,
		yearZi: yearZi,
		yongStrength: jkYongStrength,
		relations: jkRelations,
		bihe: jkBihe,
		xiangyi: buildJinKouXiangyi(guiShen.name, jiang.name),
		nianYueRi: jkNianYueRi,
		jishi: jkJishi,
		branchRelations: jkBranchRelations,
		taixuan: jkTaixuan,
		yingQi: jkYingQi,
		shenshaDocRows: shenshaDoc.rows,
		relevantShensha: shenshaDoc.relevant,
		categoryRules: JINKOU_CATEGORY_RULES,
		schools: { yueJiang: schoolYueJiang, guiTable: schoolGuiTable, guiPan: schoolGuiPan, panShi: panShi, soilChangSheng: soilChangSheng },
		// 三盘环按当前流派现算（G21）：默认流派下与后端环一致，偏离时不再退化成「待续」占位。
		plates: buildJinKouPlates(yuejiang, timeZi, guiShen.circle),
		// 十二长生落支表（土随流派，其余四行恒定）：右栏长生卡与快照据此，勿再各自查表。
		phaseTable: jinKouPhaseTable(opt.wuxing || '土', soilChangSheng),
		dong: jkDong,
		geju: jkGeju,
		sixiangShu: jkSixiangShu,
		sixiangWuxing: jkSixiangWuxing,
		fangWeiShensha: jkFangWei,
		neiwai: jkNeiWai,
		hezhan: jkHezhan,
		yinPan: jkYinPan,
		erDun: jkErDun,
		cike: jkCiKe,
		yiXing: jkYiXing,
		topic: jkTopic,
		topicJue: jkTopicJue,
		shiJian: jkShiJian,
		xingNian: jkXingNian,
		topInfo: {
			diFen: diFen,
			xunKong: xunKongBranches.length ? xunKongBranches.join('') : '无',
			siDaKong: siDaKong ? siDaKong : '无',
			// 月将/占时补齐:此前本地(非默认流派)路径中栏顶行画「—」、课情行显「无」。
			yuejiang: jiangZi ? `${jiangZi}${jiang && jiang.name ? `·${jiang.name}` : ''}` : '',
			zhanshi: timeZi || '',
		},
	};
}

