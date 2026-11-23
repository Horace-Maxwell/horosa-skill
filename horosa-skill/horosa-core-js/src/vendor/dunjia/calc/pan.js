// 刻家起局与排盘:值符值使、地天人神四盘、飞盘、空亡驿马、门迫、九宫格
// 从 DunJiaCalc.js 按职责拆出(门面保留原导入路径与对外导出;读源码的检查读「子模块 + 门面」全集,见 scripts/source-sets.json)。
import { resolveAfter23NewDay, resolveLateZiHourUseNextDay } from '../../utils/dayBoundaryResolve.js';
import { LUOSHU_NUM } from '../DunJiaFaDoc.js';
import { prevGanZhi, getHourGanZhi, getGanzhiIndex, buildQmjuByMeta, normalizeNum, qimenJuNameChaibu, normalizeJieqi, normalizeText, resolveCalcDateTime, normalizeGanZhi, normalizeTimeAlg, getXunHead, getGanzhiGan, normalizeShiftPalace } from './basics.js';
import { GAN, ZHI, CNUMBER, ZHISHI_BY_JIEQI, GUXU, newListR, newList, zipToMap, XUN_HEADS, EIGHT_GUA, JIU_XING, JJ, CLOCKWISE_EIGHTGUA, DOOR_R, STAR_R, invertMap, POS_GUA_MAP, GUA_POS_MAP, BRANCH_TO_POS, PALACE_NAME, JI_XING_RULE, RU_MU_RULE, MEN_PO_RULE, OUTER_RING_CLOCKWISE, PALACE_GRID } from './tables.js';
import { calcYearJiaMeta, calcYueJiaMeta, calcDayJiaMeta, normalizeQijuMethod } from './juMeta.js';
import { qimenJuNameZhirun, qimenDingjuJieqi, qimenJuNameWurun, qimenJuNameMaoshan } from './yinyangdun.js';
import { jiGongOf, applyGodsPreset } from './options.js';

// 刻家十分局:一时辰(2h)分十刻(12min/刻),初局=本时辰时家局(沿当前起局法链),
//   逐刻推移:阳遁顺进一局、阴遁逆退一局(第k刻=初局±(k-1),九局循环)。
//   分遁 keJiaFenDun:zihou(默认)=子后阳午后阴(时支子~巳阳/午~亥阴,与节气无关)/jieqi=沿时家节气分遁。
//   keZiZhengHuanShi=子正换时:开=时辰界取偶数整点(子时 00:00 起),关(默认)=奇数整点(子时 23:00 起)。
function calcKeJiaMeta(opts, ganzhi, jieqi, dateParts, context){
	const zhengShift = (opts && opts.keZiZhengHuanShi) ? 0 : 1;
	const hour = dateParts && Number.isFinite(dateParts.hour) ? dateParts.hour : 0;
	const minute = dateParts && Number.isFinite(dateParts.minute) ? dateParts.minute : 0;
	// 子正换时开 → 时辰界取偶数整点的不只是刻序:初局(时家局基准)、刻柱锚、子后午后分遁 同用这一套时辰。
	//   此前三处仍取奇数整点界的 ganzhi.time / ganzhi.day → 01:30 刻序按子时、初局刻柱按丑时,两套时辰并存。
	//   规则:00:xx–01:xx 属当日子时(当日日干起子);23:xx 属当日亥时(after23NewDay 的日柱进位在此撤回)。关档逐字不变。
	let gz = ganzhi;
	if(zhengShift === 0){
		let dayGz = ganzhi.day;
		if(hour === 23 && resolveAfter23NewDay(opts && opts.after23NewDay) === 1){ dayGz = prevGanZhi(dayGz); }
		const evenHour = Math.floor(hour / 2) * 2;   // 0,2,…,22:经 getHourGanZhi 的奇数整点映射恰落 子,丑,…,亥
		const timeGz = getHourGanZhi(dayGz, evenHour) || ganzhi.time;
		gz = { ...ganzhi, day: dayGz, time: timeGz };
	}
	// 初局基准=时家局(拆掉刻家键后按当前 qijuMethod 走时家链)
	const base = resolvePaiPanMeta({ ...opts, paiPanType: 3 }, gz, jieqi, dateParts, context);
	const sinceStart = ((hour + zhengShift) % 2) * 60 + minute;      // 时辰内分钟数(0..119)
	const keIndex = Math.min(9, Math.floor(sinceStart / 12));        // 第 1..10 刻(0 基)
	let yang;
	if((opts && opts.keJiaFenDun) === 'jieqi'){
		yang = `${base.yinYangDun || ''}`.indexOf('阳') >= 0;
	}else{
		const zhi = `${gz.time || ''}`.charAt(1);
		yang = '子丑寅卯辰巳'.indexOf(zhi) >= 0;
	}
	const baseJu = base.juShu || 1;
	const ju = yang ? ((baseJu - 1 + keIndex) % 9) + 1 : (((baseJu - 1 - keIndex) % 9) + 9) % 9 + 1;
	// 刻柱干支:时柱锚法——本时辰第 1 刻即时柱本身,此后逐刻按六十甲子序进一位
	// (刻为时之细分,首刻同时柱,与「初局=时家局」同构;口径于帮助文档如实说明)。
	let keGanZhi = '';
	{
		const ti = getGanzhiIndex(gz.time || '');
		if(ti >= 0){
			const idx = ((ti + keIndex) % 60 + 60) % 60;
			keGanZhi = GAN[idx % 10] + ZHI[idx % 12];
		}
	}
	return {
		sanYuan: base.sanYuan,
		juShu: ju,
		yinYangDun: yang ? '阳遁' : '阴遁',
		qmju: buildQmjuByMeta(yang ? '阳遁' : '阴遁', ju, base.sanYuan),
		dingjuJieqi: base.dingjuJieqi,
		keIndex: keIndex + 1,
		keGanZhi,
		keTimeGanZhi: gz.time || '',   // 刻家所用时柱(子正换时开=偶数整点界;关=四柱时柱)
	};
}

export function resolvePaiPanMeta(opts, ganzhi, jieqi, dateParts, context){
	const paiPanType = normalizeNum(opts && opts.paiPanType, 3);
	if(paiPanType === 0){
		return calcYearJiaMeta(dateParts.year, opts && opts.yearJiaJu);
	}
	if(paiPanType === 1){
		return calcYueJiaMeta(ganzhi, opts && opts.yueJiaQiJuType);
	}
	if(paiPanType === 2){
		return calcDayJiaMeta(dateParts, ganzhi.day, jieqi, context, opts && opts.dayJiaJu);
	}
	if(paiPanType === 4){
		return calcKeJiaMeta(opts, ganzhi, jieqi, dateParts, context);
	}
	const seeds = context && context.jieqiYearSeeds ? context.jieqiYearSeeds : {};
	const m = normalizeQijuMethod(opts && opts.qijuMethod);
	let qmju;
	// 定局节气:拆补/茅山/阴盘=曆法节气;置闰/无闰=超神接气链上的节气(超神时可≠曆法,口径同
	// Python 侧 config.dingju_jieqi)。展示/快照用它,免「局对节气错」自相矛盾(2026-08-02 缺陷②修)。
	let dingjuJieqi = jieqi;
	if(m === 'zhirun'){
		qmju = qimenJuNameZhirun(dateParts, ganzhi.day, seeds, jieqi, opts && opts.after23NewDay, false, opts && opts.zhirunLeapDays);
		dingjuJieqi = qimenDingjuJieqi(dateParts, seeds, opts && opts.after23NewDay, false, opts && opts.zhirunLeapDays) || jieqi;
	}else if(m === 'wurun'){
		qmju = qimenJuNameWurun(dateParts, ganzhi.day, seeds, jieqi, opts && opts.after23NewDay, opts && opts.zhirunLeapDays);
		dingjuJieqi = qimenDingjuJieqi(dateParts, seeds, opts && opts.after23NewDay, true, opts && opts.zhirunLeapDays) || jieqi;
	}else if(m === 'maoshan'){
		qmju = qimenJuNameMaoshan(dateParts, jieqi, seeds, ganzhi.day);
	}else{
		qmju = qimenJuNameChaibu(jieqi, ganzhi.day);
	}
	const parsed = parseQmju(qmju);
	return {
		sanYuan: parsed.yuan,
		juShu: CNUMBER.indexOf(parsed.kook) + 1,
		yinYangDun: parsed.yy === '阴' ? '阴遁' : '阳遁',
		qmju,
		dingjuJieqi,
	};
}

function resolveSpecialZhiShi(zhiShiType, yinYangDun, jieqi){
	const type = normalizeNum(zhiShiType, 0);
	if(type === 1){
		return yinYangDun === '阳遁' ? '生' : '死';
	}
	if(type === 3){
		return yinYangDun === '阳遁' ? '死' : '生';   // 阳遁寄坤借死门、阴遁寄艮借生门
	}
	if(type === 2){
		const jq = normalizeJieqi(jieqi);
		for(let i=0; i<ZHISHI_BY_JIEQI.length; i++){
			if(ZHISHI_BY_JIEQI[i].list.indexOf(jq) >= 0){
				return ZHISHI_BY_JIEQI[i].door;
			}
		}
	}
	return '死';
}

export function parseQmju(qmju){
	const text = normalizeText(qmju);
	const yy = text.includes('阴遁') ? '阴' : '阳';
	const kook = (text.match(/[一二三四五六七八九]/) || ['一'])[0];
	const yuan = text.includes('上元') ? '上元' : (text.includes('中元') ? '中元' : '下元');
	return { text, yy, kook, yuan };
}

export function buildGanzhiForQimen(nongli, dateParts, opts, context){
	const bazi = nongli && nongli.bazi && nongli.bazi.fourColumns ? nongli.bazi.fourColumns : null;
	const calcDateTime = resolveCalcDateTime(dateParts, nongli, opts, context);
	let day = normalizeGanZhi(
		(bazi && bazi.day && bazi.day.ganzi)
		|| (nongli ? nongli.dayGanZi : '甲子')
	);
	// 日柱换日已由 nongli 来源(后端 /nongli/time 或本地 buildLocalBaziResult)按 after23NewDay 完成,此处不可再次进位。
	// 用户语义(拍板,字面直觉版):
	//   after23NewDay=1「23点算第二天」→ hour==23 时 day 已上移到次日(壬寅);
	//   after23NewDay=0「24点算第二天」→ hour==23 时 day 守今(辛丑)。
	// v2.2.1 第二全局开关 lateZiHourUseNextDay:
	//   lateZi=1(默认):时柱永远按"次日日干"起子时(同 lunar.js Exact)
	//   lateZi=0:时柱按钟面当天(今日)的日干起子时(与日柱开关独立;after23=1 时日柱已次日、时干仍按今日 —— 口径 B)
	// 仅 hour==23 时影响时柱;其它 22 小时一律 NO-OP。
	const preciseTime = normalizeGanZhi(
		(bazi && bazi.time && bazi.time.ganzi)
		|| (nongli ? nongli.time : '')
	);
	const computedTime = getHourGanZhi(day, calcDateTime.hour);
	const isLateZi = calcDateTime.hour === 23;
	const dayShiftedByLateZi = isLateZi && resolveAfter23NewDay(opts && opts.after23NewDay) === 1; // after23NewDay=1 → 进位(经单源归一:缺键取全局现值,'0' 不当真)
	const lateZiUseNextDay = resolveLateZiHourUseNextDay(opts && opts.lateZiHourUseNextDay);
	const timeAlgIsTrueSolar = normalizeTimeAlg(opts && opts.timeAlg) === 0;
	let time;
	if(dayShiftedByLateZi){
		// after23=1 + hour==23: day 已 shift 到次日(壬寅)。
		// lateZi=1: 时柱用次日日干起子时 → getHourGanZhi(壬寅, 23) = 庚子
		// lateZi=0: 时柱用今日(=prevDay)日干起子时 → getHourGanZhi(辛丑, 23) = 戊子
		if(lateZiUseNextDay){
			time = computedTime || preciseTime;
		} else {
			const todayDay = prevGanZhi(day);
			time = getHourGanZhi(todayDay, calcDateTime.hour) || computedTime || preciseTime;
		}
	} else if(isLateZi){
		// after23=0 + hour==23: day 守今(辛丑)
		if(lateZiUseNextDay){
			// lateZi=1 默认:时柱按次日干起 → preciseTime = lunar.js Exact 现行结果(庚子)
			time = preciseTime || computedTime;
		} else {
			// lateZi=0:时柱跟日柱一致 → computedTime = getHourGanZhi(today_day, 23) = 戊子(核心新 case)
			time = computedTime || preciseTime;
		}
	} else if(timeAlgIsTrueSolar){
		time = computedTime || preciseTime;
	} else {
		time = preciseTime || computedTime;
	}
	return {
		year: normalizeGanZhi(
			(bazi && bazi.year && bazi.year.ganzi)
			|| (nongli ? (nongli.yearJieqi || nongli.year) : '')
		),
		month: normalizeGanZhi(
			(bazi && bazi.month && bazi.month.ganzi)
			|| (nongli ? nongli.monthGanZi : '')
		),
		day,
		time,
	};
}

export function daykongShikong(dayGanZhi, hourGanZhi){
	const dk = getXunHead(dayGanZhi);
	const sk = getXunHead(hourGanZhi);
	return {
		日空: GUXU[dk] || '戌亥',
		时空: GUXU[sk] || '戌亥',
	};
}

function zhifuPai(qmju){
	const meta = parseQmju(qmju);
	const table = {
		阳: {
			一: '九八七一二三四五六',
			二: '一九八二三四五六七',
			三: '二一九三四五六七八',
			四: '三二一四五六七八九',
			五: '四三二五六七八九一',
			六: '五四三六七八九一二',
			七: '六五四七八九一二三',
			八: '七六五八九一二三四',
			九: '八七六九一二三四五',
		},
		阴: {
			九: '一二三九八七六五四',
			八: '九一二八七六五四三',
			七: '八九一七六五四三二',
			六: '七八九六五四三二一',
			五: '六七八五四三二一九',
			四: '五六七四三二一九八',
			三: '四五六三二一九八七',
			二: '三四五二一九八七六',
			一: '二三四一九八七六五',
		},
	};
	const pai = table[meta.yy][meta.kook];
	const yinlist = newListR(CNUMBER, meta.kook).slice(0, 6).map((x)=>x + pai);
	const yanglist = newList(CNUMBER, meta.kook).slice(0, 6).map((x)=>x + pai);
	return meta.yy === '阴' ? zipToMap(XUN_HEADS, yinlist) : zipToMap(XUN_HEADS, yanglist);
}

function zhishiPai(qmju){
	const meta = parseQmju(qmju);
	const newKook = newList(CNUMBER, meta.kook);
	const newRKook = newListR(CNUMBER, meta.kook);
	const yanglist = `${newKook.join('')}${newKook.join('')}${newKook.join('')}`;
	const yinlist = `${newRKook.join('')}${newRKook.join('')}${newRKook.join('')}`;
	const yinlist1 = newRKook.slice(0, 6).map((i)=>`${i}${yinlist.slice(yinlist.indexOf(i) + 1, yinlist.indexOf(i) + 12)}`);
	const yanglist1 = newKook.slice(0, 6).map((i)=>`${i}${yanglist.slice(yanglist.indexOf(i) + 1, yanglist.indexOf(i) + 12)}`);
	return meta.yy === '阴' ? zipToMap(XUN_HEADS, yinlist1) : zipToMap(XUN_HEADS, yanglist1);
}

export function zhifuNZhishi(ganzhi, qmju, ext){
	const gongsCode = zipToMap(CNUMBER, EIGHT_GUA);
	const hgan = GAN.indexOf(ganzhi.time.substring(0, 1));
	const chour = getXunHead(ganzhi.time);
	const eg = '休死伤杜中开惊生景'.split('');
	const zspai = zhishiPai(qmju);
	const zfpai = zhifuPai(qmju);
	const zspaiKeys = Object.keys(zspai);
	const zspaiValues = Object.values(zspai);
	const zfKeys = Object.keys(zfpai);
	const zfValues = Object.values(zfpai);

	const a = zspaiValues.map((i)=>zipToMap(CNUMBER, eg)[i.substring(0, 1)]);
	const b = zfValues.map((i)=>zipToMap(CNUMBER, JIU_XING)[i.substring(0, 1)]);
	const c = zfValues.map((i)=>gongsCode[i.substring(hgan, hgan + 1)]);
	const d = zspaiValues.map((i)=>gongsCode[i.substring(hgan, hgan + 1)]);

	const star = zipToMap(zfKeys, b)[chour];
	const starGong = zipToMap(zfKeys, c)[chour];
	let door = zipToMap(zspaiKeys, a)[chour];
	// 仅“值符星=禽”时按天禽值符规则处理；值符落中宫并不等于天禽值符。
	const isTianQinAsZhiFu = star === '禽';
	if(isTianQinAsZhiFu){
		door = resolveSpecialZhiShi(ext && ext.zhiShiType, ext && ext.yinYangDun, ext && ext.jieqi);
	}else if(door === '中'){
		door = '死';
	}
	return {
		值符天干: [chour, JJ[chour]],
		值符星宫: [star, starGong],
		值使门宫: [door, zipToMap(zspaiKeys, d)[chour]],
	};
}

export function panEarth(qmju){
	const meta = parseQmju(qmju);
	const palaces = newList(CNUMBER, meta.kook).map((x)=>zipToMap(CNUMBER, EIGHT_GUA)[x]);
	const vals = meta.yy === '阳' ? '戊己庚辛壬癸丁丙乙'.split('') : '戊乙丙丁癸壬辛庚己'.split('');
	return zipToMap(palaces, vals);
}

export function panGod(ganzhi, qmju, ext){
	const zfzs = zhifuNZhishi(ganzhi, qmju, ext);
	const meta = parseQmju(qmju);
	const startingGong = zfzs.值符星宫[1];
	const rotate = meta.yy === '阳' ? CLOCKWISE_EIGHTGUA : [...CLOCKWISE_EIGHTGUA].reverse();
	const gongReorder = startingGong === '中' ? newList(rotate, jiGongOf(ext, meta.yy)) : newList(rotate, startingGong);
	const vals = (meta.yy === '阳' ? '符蛇阴合勾雀地天' : '符蛇阴合虎玄地天').split('');
	const out = zipToMap(gongReorder, vals);
	// 八神名按预设分派(ext.godsPreset;缺省=历史默认恒虎玄)
	Object.keys(out).forEach((k)=>{
		out[k] = applyGodsPreset(out[k], ext && ext.godsPreset);
	});
	return out;
}

export function panDoor(ganzhi, qmju, ext){
	const zfzs = zhifuNZhishi(ganzhi, qmju, ext);
	const meta = parseQmju(qmju);
	const startingDoor = zfzs.值使门宫[0];
	const startingGong = zfzs.值使门宫[1];
	const rotate = meta.yy === '阳' ? CLOCKWISE_EIGHTGUA : [...CLOCKWISE_EIGHTGUA].reverse();
	const gongReorder = startingGong === '中' ? newList(rotate, jiGongOf(ext, meta.yy)) : newList(rotate, startingGong);
	const yydoor = meta.yy === '阳' ? newList(DOOR_R, startingDoor) : newList([...DOOR_R].reverse(), startingDoor);
	return zipToMap(gongReorder, yydoor);
}

// 值符是天禽(旬首遁仪就在中五宫)时,天禽自己没有宫可出发,由「本宫是寄宫的那颗星」代它领盘:
// 寄坤天芮 / 寄艮天任 / 寄巽天辅 / 寄乾天心,按八节寄宫时另有震冲、离英、兑柱、坎蓬。
// 九星圈上坤宫那一位记作「禽」(盘上显「内」);值符不是天禽时原样(芮就是坤宫那一位)。
// 天盘干(panSky)一直按这颗星的本宫起排,九星层与值符名必须跟它是同一颗 —— 否则「天盘干 = 该宫之星本宫的地盘干」不成立。
const LEAD_STAR_OF_GONG = { 坎: '蓬', 艮: '任', 震: '冲', 巽: '辅', 离: '英', 坤: '禽', 兑: '柱', 乾: '心' };
export function leadStarOf(zfStar, ext, yy){
	if(zfStar === '禽'){ return LEAD_STAR_OF_GONG[jiGongOf(ext, yy)] || '禽'; }
	return String(zfStar || '').replace(/芮/g, '禽');
}

export function panStar(ganzhi, qmju, ext){
	const zfzs = zhifuNZhishi(ganzhi, qmju, ext);
	const meta = parseQmju(qmju);
	const startingStar = leadStarOf(zfzs.值符星宫[0], ext, meta.yy);
	const startingGong = zfzs.值符星宫[1];
	const rotate = meta.yy === '阳' ? CLOCKWISE_EIGHTGUA : [...CLOCKWISE_EIGHTGUA].reverse();
	const stars = meta.yy === '阳' ? newList(STAR_R, startingStar) : newList([...STAR_R].reverse(), startingStar);
	const gongReorder = startingGong === '中' ? newList(rotate, jiGongOf(ext, meta.yy)) : newList(rotate, startingGong);
	const out = zipToMap(gongReorder, stars);
	Object.keys(out).forEach((k)=>{
		out[k] = out[k].replace(/[芮禽]+/g, '内');   // 转盘(8星)天禽随中显「内」(天内);飞盘9星含中宫照显「禽」(用户:内对芮讹)
	});
	return out;
}

export function panSky(ganzhi, qmju, ext){
	const meta = parseQmju(qmju);
	const rotate = meta.yy === '阳' ? CLOCKWISE_EIGHTGUA : [...CLOCKWISE_EIGHTGUA].reverse();
	const earth = panEarth(qmju);
	const earthR = invertMap(earth);
	const zfzs = zhifuNZhishi(ganzhi, qmju, ext);
	const fuHead = JJ[getXunHead(ganzhi.time)] || '戊';
	const ganHead = zfzs.值符天干[1];
	const starGong = zfzs.值符星宫[1];
	const earthOnRing = rotate.map((g)=>earth[g]);
	const jiGong = jiGongOf(ext, meta.yy);
	if(starGong === '中'){
		// 时干就是中五宫的干:值符随时干入中、寄到寄宫。天盘干由九星带着各自本宫的地盘干走,所以寄宫得到的是值符星本宫的干(旬首遁仪):
		//   · 值符星本宫不在寄宫 → 旬首遁仪落寄宫,其余依圈顺排;
		//   · 值符星本宫就是寄宫(值符天芮、寄坤)→ 星没有动,天盘干与地盘干逐宫相同(伏吟);
		//   · 旬首遁仪就在中五宫(值符天禽,随寄宫之星)→ 同样是寄宫之星不动,伏吟。
		// 上游参考实现在第二种情形另写了一支「从圈上最后一个干排起」,结果是九星 / 八门 / 八神都伏吟而天盘干转了两三宫,
		// 与它自己排出的星盘矛盾(全年约 1.1% 的时辰);这里按「干随星走」统一处理。
		const gongReorder = newList(rotate, jiGong);
		let ganReorder;
		if(panGod(ganzhi, qmju, ext)[jiGong] !== '符'){
			ganReorder = newList(earthOnRing, earth[jiGong]);
		}else{
			try{
				ganReorder = newList(earthOnRing, ganHead);
			}catch(e){
				ganReorder = newList(earthOnRing, earth[jiGong]);
			}
		}
		const out = zipToMap(gongReorder, ganReorder);
		out.中 = earth.中;
		return out;
	}
	const timeGan = getGanzhiGan(ganzhi.time);
	const normalizeTianpanGong = (gong)=>gong === '中' ? jiGong : gong;
	const sourceGong = normalizeTianpanGong(earthR[fuHead]);
	const targetGong = normalizeTianpanGong(earthR[timeGan]);
	const safeSourceGong = rotate.indexOf(sourceGong) >= 0 ? sourceGong : rotate[0];
	const safeTargetGong = rotate.indexOf(targetGong) >= 0 ? targetGong : safeSourceGong;
	const ganReorder = newList(rotate, safeSourceGong).map((g)=>earth[g]);
	const gongReorder = newList(rotate, safeTargetGong);
	const out = zipToMap(gongReorder, ganReorder);
	out.中 = earth.中;
	return out;
}

// WP-A 飞盘排盘(资料 Step6-8 / 参考引擎 paipanCore 飞盘分支,已对 golden 逐宫核对)。
// 一次算齐 天/门/星/神 四盘(共用 Hv/P/Pu 锚点),输出洛书宫→卦名 map,下游 convertGuaMapToPos 零改。
// 中宫照常飞、九神含中宫、不做 禽→芮 / 勾→虎 / 雀→玄 替换(那些是转盘专有)。
// 九门归宫(含中5「中门」):飞盘八门其实是九门整体飞九宫——值符落中5(天禽值符)时,值使门即「中门」从中5起数,
//   非中宫值符时中门作为第9门随飞填满某宫(对齐参考实现:6-22中门@震3、02-04中门@坎1、时乙酉中门@艮8)。
const FEI_GATE_HOME = { 1: '休', 8: '生', 3: '伤', 4: '杜', 5: '中', 9: '景', 2: '死', 7: '惊', 6: '开' };

// 九神飞布:阳遁 值符螣蛇太阴六合勾陈太常朱雀九地九天;阴遁 值符螣蛇太阴六合白虎太常玄武九地九天(5白虎/7玄武)。
const FEI_GODS_YANG = '符蛇阴合勾常雀地天'.split('');

const FEI_GODS_YIN = '符蛇阴合虎常玄地天'.split('');

const lpFei = (n)=>((n - 1) % 9 + 9) % 9 + 1;

// fopts 飞盘细项(全缺省=历史行为零回归):
//   feiXingShun/feiMenShun/feiShenShun=该层阴阳遁皆顺飞(只改飞布方向,值符/值使定位不动);
//   feiMenZhongCan=false 时门层按「八门跳中5」传派布(中宫永不布门,数飞跳中);
//   feiMenZhongShow=true 且中门不参与时,中宫标「中」字样(纯显示)。
export function panFeipan(ganzhi, qmju, fopts){
	const fo = fopts || {};
	const meta = parseQmju(qmju);
	const isY = meta.yy === '阳';
	const earthGua = panEarth(qmju);                                  // 卦→干
	const earthGong = {};
	for(let g = 1; g <= 9; g++){ earthGong[g] = earthGua[EIGHT_GUA[g - 1]]; }   // 洛书宫→干
	const xunHead = getXunHead(ganzhi.time);
	const dunYi = JJ[xunHead] || '戊';
	let Hv = 5;
	for(let g = 1; g <= 9; g++){ if(earthGong[g] === dunYi){ Hv = g; break; } } // 值符宫=旬首遁仪所在宫
	const timeGan = `${ganzhi.time || ''}`.substring(0, 1);
	let P = Hv;                                                       // 时干宫(甲→值符原地)
	if(timeGan !== '甲'){ for(let g = 1; g <= 9; g++){ if(earthGong[g] === timeGan){ P = g; break; } } }
	// 时干序(=时柱在旬内位次+1,旬首恒甲)。🔴 空时柱时 indexOf('')=-1 → xord=0,
	// 值使门整盘静默偏一宫;非法输入按旬首(xord=1)兜底,不再产出错位盘。
	const xord = Math.max(1, GAN.indexOf(timeGan) + 1);
	const step = isY ? 1 : -1;
	const stepXing = (isY || fo.feiXingShun) ? 1 : -1;
	const stepMen = (isY || fo.feiMenShun) ? 1 : -1;
	const stepShen = (isY || fo.feiShenShun) ? 1 : -1;
	// 值使门落宫:从值符宫(旬首遁仪宫,含中5)顺(阳)/逆(阴)数至时柱(参考实现门入中宫,Pu 可为中5)。
	const Pu = lpFei(Hv + step * (xord - 1));                         // 中宫值符(Hv=5)时值使=中门,亦从中5起数(6-22→震3、02-04→坎1 已对参考实现)
	const starG = {}, skyG = {}, gateG = {}, godG = {};
	// 九星:值符星(JIU_XING[Hv-1])落时干宫P,蓬芮冲辅禽心柱任英按号顺(阳)/逆(阴)飞九宫(含中5)。
	for(let n = 1; n <= 9; n++){ starG[lpFei(P + stepXing * (n - Hv))] = JIU_XING[n - 1]; }
	// 天盘(六仪三奇):地盘整体随值符平移(值符遁仪→时干宫,平移量 P-Hv),非随星逆飞——
	//   阴遁星逆飞但天盘是整体平移,故各宫天盘干须单独按平移算(对齐参考实现:坎1=庚/巽4=乙…)。
	const dPan = ((P - Hv) % 9 + 9) % 9;
	for(let q = 1; q <= 9; q++){ skyG[lpFei(q + dPan)] = earthGong[q]; }
	// 九门:值使门(FEI_GATE_HOME[Hv],中宫值符时=中门)落Pu,休死伤杜中开惊生景九门按九宫顺(阳)/逆(阴)整体飞——
	//   对齐参考实现(门入中宫:中门是第9门随飞,落中5者中宫得门),非书本「八门跳中5」传本(以本引擎为准)。
	if(fo.feiMenZhongCan === false){
		// 跳中传派:八门(无中门)全程 8 宫环(洛书序跳中5),值使定位数宫亦跳中;值符宫=中5 时值使取死门、自死门本位起数。
		const RING8 = [1, 2, 3, 4, 6, 7, 8, 9];
		const DOORS8 = ['休', '死', '伤', '杜', '开', '惊', '生', '景'];   // 洛书本位序(1休2死3伤4杜6开7惊8生9景)
		let vDoor = FEI_GATE_HOME[`${Hv}`] || '死';
		if(vDoor === '中'){ vDoor = '死'; }
		const vHome = RING8[DOORS8.indexOf(vDoor)];
		const hv8 = Hv === 5 ? vHome : Hv;
		const pos8 = (g)=>RING8.indexOf(g);
		const pu8 = RING8[(((pos8(hv8) + step * (xord - 1)) % 8) + 8) % 8];
		const di = DOORS8.indexOf(vDoor);
		for(let k = 0; k < 8; k++){ gateG[RING8[(((pos8(pu8) + stepMen * k) % 8) + 8) % 8]] = DOORS8[(di + k) % 8]; }
		if(fo.feiMenZhongShow){ gateG[5] = '中'; }
	}else{
		Object.keys(FEI_GATE_HOME).forEach((hk)=>{ const h = Number(hk); const np = lpFei(Pu + stepMen * (h - Hv)); gateG[np] = FEI_GATE_HOME[hk]; });
	}
	// 九神:值符落时干宫P(同值符星),阳遁勾常雀顺、阴遁白玄逆,飞九宫(含中5)。
	(isY ? FEI_GODS_YANG : FEI_GODS_YIN).forEach((god, i)=>{ const np = lpFei(P + i * stepShen); godG[np] = god; });
	const toGua = (gongMap)=>{ const out = {}; for(let g = 1; g <= 9; g++){ out[EIGHT_GUA[g - 1]] = gongMap[g] || ''; } return out; };
	return {
		tianpanGua: toGua(skyG),
		menGua: toGua(gateG),
		starGua: toGua(starG),
		shenGua: toGua(godG),
		zfzs: {
			值符天干: [xunHead, dunYi],
			值符星宫: [JIU_XING[Hv - 1], EIGHT_GUA[lpFei(P) - 1]],
			值使门宫: (function(){
				if(fo.feiMenZhongCan === false){
					let vd = FEI_GATE_HOME[`${Hv}`] || '死';
					if(vd === '中'){ vd = '死'; }
					const gong = Object.keys(gateG).find((g)=>gateG[g] === vd);
					return [vd, EIGHT_GUA[(Number(gong) || 2) - 1]];
				}
				return [FEI_GATE_HOME[`${Hv}`] || '死', EIGHT_GUA[lpFei(Pu) - 1]];
			})(),
		},
	};
}

export function convertGuaMapToPos(mapObj){
	const out = {};
	Object.keys(POS_GUA_MAP).forEach((k)=>{
		out[k] = '';
	});
	Object.keys(mapObj || {}).forEach((gua)=>{
		const pos = GUA_POS_MAP[gua];
		if(pos){
			out[pos] = mapObj[gua] || '';
		}
	});
	return out;
}

export function getKongByMode(mode, dayShiKong){
	return mode === 'time' ? (dayShiKong.时空 || '') : (dayShiKong.日空 || '');
}

export function resolveKongWangPalaces(kongWang){
	const list = [];
	const palaces = [];
	// 逐字遍历(两字串=历史行为字节同;kongMarkBoth 并集串为四字,全标)
	String(kongWang || '').split('').forEach((zhi)=>{
		const pos = BRANCH_TO_POS[zhi];
		if(pos && palaces.indexOf(pos) < 0){
			palaces.push(pos);
			list.push(`${PALACE_NAME[pos]}${LUOSHU_NUM[PALACE_NAME[pos]]}宫空亡`);
		}
	});
	return { list, palaces };
}

function getYiMaZhi(sourceZhi){
	if('申子辰'.indexOf(sourceZhi) >= 0){
		return '寅';
	}
	if('寅午戌'.indexOf(sourceZhi) >= 0){
		return '申';
	}
	if('巳酉丑'.indexOf(sourceZhi) >= 0){
		return '亥';
	}
	if('亥卯未'.indexOf(sourceZhi) >= 0){
		return '巳';
	}
	return '';
}

export function resolveYiMa(mode, ganzhi){
	const source = mode === 'time' ? (ganzhi.time || '') : (ganzhi.day || '');
	const sourceZhi = source.substring(1, 2);
	const yimaZhi = getYiMaZhi(sourceZhi);
	const palace = BRANCH_TO_POS[yimaZhi] || 0;
	return {
		mode,
		source,
		sourceZhi,
		yimaZhi,
		palace,
		text: palace ? `${mode === 'time' ? '时马' : '日马'}：${yimaZhi}（${PALACE_NAME[palace]}${LUOSHU_NUM[PALACE_NAME[palace]]}宫）` : `${mode === 'time' ? '时马' : '日马'}：无`,
	};
}

export function resolveSpecials(tianPan){
	const liuYi = [];
	const ruMu = [];
	const jiXingSet = new Set();
	const ruMuSet = new Set();
	for(let i=1; i<=9; i++){
		const gan = tianPan[i] || '';
		const jiRule = JI_XING_RULE[i] || '';
		const ruRule = RU_MU_RULE[i] || '';
		if(gan && jiRule && jiRule.indexOf(gan) >= 0){
			jiXingSet.add(i);
			liuYi.push(`${gan}击刑（${PALACE_NAME[i]}${LUOSHU_NUM[PALACE_NAME[i]]}宫）`);
		}
		if(gan && ruRule && ruRule.indexOf(gan) >= 0){
			ruMuSet.add(i);
			ruMu.push(`${gan}入墓（${PALACE_NAME[i]}${LUOSHU_NUM[PALACE_NAME[i]]}宫）`);
		}
	}
	return {
		liuYi,
		ruMu,
		jiXingPalaces: [...jiXingSet],
		ruMuPalaces: [...ruMuSet],
	};
}

export function resolveMenPo(men){
	const list = [];
	const palaces = [];
	Object.keys(MEN_PO_RULE).forEach((k)=>{
		const i = parseInt(k, 10);
		const door = men[i] || '';
		const head = door.substring(0, 1);
		if(head && MEN_PO_RULE[i].indexOf(head) >= 0){
			palaces.push(i);
			list.push(`${head}门迫（${PALACE_NAME[i]}${LUOSHU_NUM[PALACE_NAME[i]]}宫）`);
		}
	});
	return { list, palaces };
}

export function mapListByPos(mapObj){
	const out = [];
	for(let i=1; i<=9; i++){
		out.push(mapObj[i] || '');
	}
	return out;
}

export function rotateOuterMapByShift(mapObj, shiftPalace){
	const step = normalizeShiftPalace(shiftPalace);
	const out = {};
	for(let i=1; i<=9; i++){
		out[i] = mapObj && mapObj[i] ? mapObj[i] : '';
	}
	if(step === 0){
		return out;
	}
	for(let i=0; i<OUTER_RING_CLOCKWISE.length; i++){
		const srcPalace = OUTER_RING_CLOCKWISE[i];
		const destPalace = OUTER_RING_CLOCKWISE[(i + step) % OUTER_RING_CLOCKWISE.length];
		out[destPalace] = mapObj && mapObj[srcPalace] ? mapObj[srcPalace] : '';
	}
	out[5] = mapObj && mapObj[5] ? mapObj[5] : '';
	return out;
}

export function rotateOuterPalaceNum(palaceNum, shiftPalace){
	const step = normalizeShiftPalace(shiftPalace);
	if(step === 0 || palaceNum === 5){
		return palaceNum;
	}
	const idx = OUTER_RING_CLOCKWISE.indexOf(palaceNum);
	if(idx < 0){
		return palaceNum;
	}
	return OUTER_RING_CLOCKWISE[(idx + step) % OUTER_RING_CLOCKWISE.length];
}

export function buildCells(diPan, tianPan, men, shen, star, zhiFuPalace, zhiShiPalace, status){
	const jiXingSet = new Set(status && status.jiXingPalaces ? status.jiXingPalaces : []);
	const ruMuSet = new Set(status && status.ruMuPalaces ? status.ruMuPalaces : []);
	const menPoSet = new Set(status && status.menPoPalaces ? status.menPoPalaces : []);
	const kongSet = new Set(status && status.kongWangPalaces ? status.kongWangPalaces : []);
	const yimaPalace = status && status.yimaPalace ? status.yimaPalace : 0;

	return PALACE_GRID.map((palaceNum)=>({
		palaceNum,
		palaceName: PALACE_NAME[palaceNum] || `${palaceNum}`,
		diGan: diPan[palaceNum] || '',
		tianXing: star[palaceNum] || '',
		door: men[palaceNum] || '',
		god: (status && (status.school === '飞盘' || status.school === '混合')) ? String(shen[palaceNum] || '') : applyGodsPreset(String(shen[palaceNum] || ''), status && status.godsPreset),
		tianGan: tianPan[palaceNum] || '',
		isCenter: palaceNum === 5,
		isFeipan: !!(status && (status.school === '飞盘' || status.school === '混合')),   // 混合:门神飞泊可入中5,中宫按飞盘渲染(星仍转盘寄坤2)
		isZhiFu: palaceNum === zhiFuPalace,
		isZhiShi: palaceNum === zhiShiPalace,
		hasJiXing: jiXingSet.has(palaceNum),
		hasRuMu: ruMuSet.has(palaceNum),
		hasMenPo: menPoSet.has(palaceNum),
		hasKongWang: kongSet.has(palaceNum),
		isYiMa: palaceNum === yimaPalace,
		anGan: (status && status.anGanByNum && status.anGanByNum[palaceNum]) || '',   // 暗干(off=空)
		anZhi: (status && status.anZhiByNum && status.anZhiByNum[palaceNum]) || '',   // 暗支(随开关)
	}));
}
