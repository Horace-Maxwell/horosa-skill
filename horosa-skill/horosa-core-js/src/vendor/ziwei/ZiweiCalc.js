// 紫微斗数 · 本命盘组装引擎（移植 Java ZiWeiChart.setup() 全 13 步 + 命主身主斗君）。
// 纯函数：给定 干支/月日时/性别 → 完整 chart（形状对齐 Java，供 ZWChart.js 渲染、ZiWeiHelper 运限消费）。
// 四化单一真值源 = ZWConst.getActiveSiHuaGan()（随流派切换）。农历(birth→干支月日时)由上层提供，不在此。
import {
	ZHI, GAN, z, zi, gi, isYangGan, isYangZhi, xiaoxianClockwiseFor,
	palaceGans, mingGong, shenGong, ziweiPos, tianfuPos,
	CHANGSHENG_12, CHANGSHENG_START, CHANGSHENG_START_HUO_TU, isClockwise, NORTH_MAIN_STEP, SOUTH_MAIN_STEP,
	wuxingJu as coreWuxingJu,
} from './ziweiCore.js';
import {
	STARS_YEAR_GAN, STARS_YEAR_ZI, STARS_MONTH, STARS_TIME_ZI, STARS_HUOLIN,
	STARS_BOSI, STARS_TAISUI, STARS_JIANG, LIFE_MASTER, BODY_MASTER, DOUJUN,
	HOUSES as HOUSE_NAMES, monthCnOf, XIAOXIAN_START, starLightOf,
} from './data/ziweiTables.js';
import { getActiveSiHuaGan } from '../bazi/ZWConst.js';
import { ZWEngineOptions, collectEngineOpts } from './ziweiOptions.js';
import { buildLocalBaziResult, buildLocalNongliLite } from '../bazi/baziLunarLocal.js';
import { placeShangShi, placeKuiYue } from './ziweiSchools.js';

const HUA = ['禄', '权', '科', '忌'];
// 星组 type → chart 字段（对齐 Java ZiWeiStarType / ZiWeiHouse）。
const TYPE_FIELD = { 0: 'starsMain', 1: 'starsAssist', 2: 'starsEvil', 3: 'starsOthersGood', 4: 'starsOthersBad', 5: 'starsSmall' };
const MAIN14 = ['紫微', '天机', '太阳', '武曲', '天同', '廉贞', '天府', '太阴', '贪狼', '巨门', '天相', '天梁', '七杀', '破军'];

// 单星装饰:生年四化标记(随当前流派 getActiveSiHuaGan)+ 庙旺亮度(STAR_LIGHT[正星名][宫支])。
function decorateStar(name, houseIdx, yearGan){
	const hua4 = getActiveSiHuaGan()[yearGan] || [];
	const s = { name };
	const hi = hua4.indexOf(name);
	if(hi >= 0){ s.sihua = HUA[hi]; }
	const baseName = name.charAt(0) === '副' ? name.slice(1) : name;
	// 庙旺存【基础(zi_jian)】值:memo 稳定、不随亮度源变;《全书》delta 覆盖在【显示层】(ZWCommHouse.effStarLight)
	// 按 ZWEngineOptions.brightnessSource 叠加——亮度纯显示,绝不改安星/命主(切亮度不重排盘)。
	const v = starLightOf(baseName, z(houseIdx), 'zi_jian');
	if(v){ s.starlight = v; }
	return s;
}

function ganzhiIndex(ganIdx, zhiIdx){
	for(let n = 0; n < 60; n++){ if(n % 10 === ganIdx && n % 12 === zhiIdx){ return n; } }
	return -1;
}
// 旬空：年柱 → 旬首 → 空二支（年柱口径，非年干；对齐 Java getXunEmptySet）。
function xunEmptyBranches(yearGan, yearZiIdx){
	const n = ganzhiIndex(gi(yearGan), yearZiIdx);
	const xunStartZhi = (n - (n % 10)) % 12;   // 该旬甲首之支
	return [z((xunStartZhi + 10) % 12), z((xunStartZhi + 11) % 12)];
}

function emptyHouse(){
	return { name: null, ganzi: null, phase: null, isLife: false, isBody: false,
		starsMain: [], starsAssist: [], starsEvil: [], starsOthersGood: [], starsOthersBad: [], starsSmall: [],
		direction: [0, 0], smallDirection: [] };
}

// 组装本命盘。ctx: {yearGan, yearZi, monthInt, leap, dayInt, timeZi, male, daxianSpan?}
export function assembleNatalChart(ctx){
	const { yearGan, yearZi, monthInt, leap, dayInt, timeZi } = ctx;
	const male = !!ctx.male;
	const yearZiIdx = zi(yearZi);
	const timeIdx = zi(timeZi);
	const yearPolarYang = isYangGan(yearGan);
	const fwd = isClockwise(yearGan, male);
	const hua4 = getActiveSiHuaGan()[yearGan] || [];

	const houses = [];
	for(let i = 0; i < 12; i++){ houses.push(emptyHouse()); }

	function star(name, houseIdx){ return decorateStar(name, houseIdx, yearGan); }
	function place(idx, name, type){ const k = (idx % 12 + 12) % 12; houses[k][TYPE_FIELD[type]].push(star(name, k)); }
	const starIdx = {};   // 记录关键星落宫（生日系依赖辅弼昌曲）
	function placeRec(idx, name, type){ const k = (idx % 12 + 12) % 12; houses[k][TYPE_FIELD[type]].push(star(name, k)); starIdx[name] = k; }

	// (1) 十二宫天干
	const pg = palaceGans(yearGan);
	for(let i = 0; i < 12; i++){ houses[i].ganzi = pg[i] + ZHI[i]; }

	// (2) 命身宫 + 五行局 + 长生 + 宫名 + 大限
	// 闰月归月(古法§1.5):默认 mid_split(十五分界,16+归下月)=现 Java 口径;next=整月归下月;prev=整月归上月。
	// 命身/五行局所用月(§1.5)。月系星恒用 monthInt(下方 line~155,不受闰月归月影响=现状口径)。
	let month = monthInt;
	if(leap){
		const lm = ctx.leapMonth || 'mid_split';
		if(lm === 'next'){ month++; }
		else if(lm === 'prev'){ /* 归上月,不进 */ }
		else if(lm === 'split_star_month'){ month++; }   // 命身归下月(月系星仍上月=monthInt,§1.5⑥)
		// 前后半分割=按实际天数取中点(大月16起/小月15起归下月;缺 monthDays 回落30=旧行为优雅降级)。
		// 🔴 与 mid_split 在 29 天闰月分道 —— 旧硬编 >=16 是 mid_split 克隆(假选项,复查实锤)。
		else if(lm === 'split_days'){ if(dayInt > Math.floor((ctx.monthDays || 30) / 2)){ month++; } }
		// 按节气分界:闰月无中气必含恰一节,过节归下月(内核 resolveLeapMonth 同口径;字段缺失=未过节归本月)
		else if(lm === 'solar_term'){ if(ctx.passedNextJie){ month++; } }
		else if(dayInt >= 16){ month++; }   // mid_split 默认(十五分界)
	}
	const loc = 2 + month - 1;                      // 寅起正月
	const lifeIdx = ((loc - timeIdx) % 12 + 12) % 12;
	const bodyIdx = (loc + timeIdx) % 12;
	houses[lifeIdx].isLife = true;
	houses[bodyIdx].isBody = true;
	const lifeGanzi = houses[lifeIdx].ganzi;
	const juInfo = coreWuxingJu(lifeGanzi.charAt(0), zi(lifeGanzi.charAt(1)));
	const ju = juInfo.ju;
	// 大限跨度:默认10年;钦天派 daxianSpan='ju' → 局数年(水二2…火六6)。
	const span = ctx.daxianSpan === 'ju' ? ju : (ctx.daxianSpan || 10);
	// [P3b] 长生起法档:huo_tu=火土同宫(土五起寅);默认 shui_tu=水土同宫(现状零回归)
	const csStart = zi((ctx.changshengStart === 'huo_tu' ? CHANGSHENG_START_HUO_TU : CHANGSHENG_START)[ju]);
	// [B11] 长生顺逆档:always_forward=全顺行 —— 🔴 铁律:仅喂 phase 环,大限 direction 与
	// 博士十二神仍用 fwd(阳男阴女律),此档绝不连坐运限方向。
	const csFwd = ctx.changshengDirection === 'always_forward' ? true : fwd;
	for(let i = 0; i < 12; i++){
		const phaseIdx = csFwd ? (((i - csStart) % 12 + 12) % 12) : (((csStart - i) % 12 + 12) % 12);
		houses[i].phase = CHANGSHENG_12[phaseIdx];
		let delta = i - lifeIdx;
		let idx = Math.abs(delta);
		if(delta > 0){ idx = 12 - delta; }
		houses[i].name = HOUSE_NAMES[idx];
		if(fwd){
			houses[i].direction = idx === 0 ? [ju, ju + 9] : [10 * (12 - idx) + ju, 10 * (12 - idx) + ju + 9];
		}else {
			houses[i].direction = [10 * idx + ju, 10 * idx + ju + 9];
		}
		if(span !== 10){   // 钦天=局数年：跨度换 span，起虚岁仍 ju + span*k（k=大限序）
			const k = fwd ? (idx === 0 ? 0 : 12 - idx) : idx;
			houses[i].direction = [ju + span * k, ju + span * k + span - 1];
		}
	}

	// (3) 紫微 + 十四正曜
	const ziweiIndex = ziweiPos(dayInt, ju);
	const tf = tianfuPos(ziweiIndex);
	Object.keys(NORTH_MAIN_STEP).forEach((s)=>{ placeRec(ziweiIndex + NORTH_MAIN_STEP[s], s, 0); });
	Object.keys(SOUTH_MAIN_STEP).forEach((s)=>{ placeRec(tf + SOUTH_MAIN_STEP[s], s, 0); });

	// (4) 年干系（禄存/羊陀/魁钺/天官天福天厨/截空；截空双星+副）
	Object.keys(STARS_YEAR_GAN).forEach((name)=>{
		const def = STARS_YEAR_GAN[name];
		const type = def.type;
		const zv = def.pos[yearGan];
		if(zv && zv.length === 2){
			// 双星(如截空):正副按「与年干同极性=正支」**逐支各判**——与旬空同律(对齐 Java 已同步修)。
			// 🔴 旧实现只判第一支、第二支恒正名:截空对恒[阳支,阴支]→阳年干出两颗正截空零副截空
			//    (双端同构错,复查实锤)。修后任意年干恒一正一副。starIdx 记录沿 Java 律:恒裸名两支皆记。
			for(let b2 = 0; b2 < 2; b2++){
				const ii = zi(zv.charAt(b2));
				const isFu = isYangZhi(ii) !== yearPolarYang;
				// [B12] 单星法:只安正空支(「一般只论正空,副空不论」),副支整颗不出
				if(isFu && ctx.kongwangStyle === 'single'){ continue; }
				const k2 = (ii % 12 + 12) % 12;
				houses[k2][TYPE_FIELD[type]].push(star((isFu ? '副' : '') + name, k2));
				starIdx[name] = k2;
			}
		}else if(zv){
			// [P3a] 魁钺歌诀两版:geng_ma_hu(庚辛逢马虎)时庚干魁午/钺寅,余干与默认表全同(内核 delta)
			const kv = (name === '天魁' || name === '天钺') ? placeKuiYue(name, yearGan, ctx.kuiYue) : null;
			placeRec(zi(kv || zv), name, type);
		}
	});

	// (5) 天才(命宫起子顺数至生年支) / 天寿(身宫起子顺数至生年支) —— 与 Java setupTianCouCai 双端同改
	// 🔴 旧实现走 HOUSE_NAMES[11 - yearZiIdx] 宫名反查而恒偏一位:本文件宫名赋值是
	//    idx = (lifeIdx - i) mod 12(见上「houses[i].name = HOUSE_NAMES[idx]」一段),
	//    故 HOUSE_NAMES[k] 坐落在支位 lifeIdx-k;顺行 n 宫要的是 k=(12-n)%12 而非 11-n。
	//    实算:命宫子/年支巳 → 应落巳,旧法落午(恒 +1 宫);仅子年因 if(idx>0) 保护而正确。
	//    Java ZiWeiChart.setupTianCouCai 原为逐字同构的同源实现,已同步改正(改后须重编 jar)。
	//    今与紧邻的天寿统一为直接支位算术——两行做同一件事却写法不同,本身就是 bug 指纹。
	{
		placeRec((lifeIdx + yearZiIdx) % 12, '天才', 3);
		placeRec((bodyIdx + yearZiIdx) % 12, '天寿', 3);
	}

	// (6) 年支系
	// 「年马」与「年支起天马」逐支同位、本是同一颗星:tianmaBasis='year' 时只出天马,
	// 否则同盘会出现两颗马星(且旧月马口径下位置常不同,用户一眼判「盘不对」)。
	// 默认 month 档不受影响(此分支不触发),故既有盘与前后端字节零回归。
	const tianmaBasisEarly = ctx.tianmaBasis || 'month';
	Object.keys(STARS_YEAR_ZI).forEach((name)=>{
		if(name === '年马' && tianmaBasisEarly === 'year'){ return; }
		const def = STARS_YEAR_ZI[name];
		const zv = def.pos[yearZi];
		if(zv){ placeRec(zi(zv), name, def.type); }
	});

	// (7) 生月系（左辅右弼/天马/天刑天姚/解神天巫天月/阴煞）。天马依据可切：默认现状(月马)/年支(三合马)。
	const tianmaBasis = tianmaBasisEarly;   // 与 (6) 同源,防两处各读 ctx 而分叉
	const monthCn = monthCnOf(monthInt);
	Object.keys(STARS_MONTH).forEach((name)=>{
		if(name === '天马' && tianmaBasis === 'year'){ return; }   // 年支起马：跳过月马，下面另置
		const def = STARS_MONTH[name];
		const zv = def.pos[monthCn];
		if(zv){ placeRec(zi(zv), name, def.type); }
	});
	if(tianmaBasis === 'year'){
		const YEAR_TIANMA = { 寅: '申', 午: '申', 戌: '申', 申: '寅', 子: '寅', 辰: '寅', 巳: '亥', 酉: '亥', 丑: '亥', 亥: '巳', 卯: '巳', 未: '巳' };
		if(YEAR_TIANMA[yearZi]){ placeRec(zi(YEAR_TIANMA[yearZi]), '天马', 1); }
	}

	// (8) 生时系（文昌文曲/台辅封诰等）
	Object.keys(STARS_TIME_ZI).forEach((name)=>{
		const def = STARS_TIME_ZI[name];
		const zv = def.pos[timeZi];
		if(zv){ placeRec(zi(zv), name, def.type); }
	});

	// (9) 火铃（年支三合 → 生时；南派 nanpai 忽略生时=固定子时位，§1.6）。默认路径不变=字节零回归。
	const hlTimeZi = ctx.huoling === 'nanpai' ? '子' : timeZi;
	const hl = STARS_HUOLIN[yearZi];
	if(hl){
		['火星', '铃星'].forEach((name)=>{ if(hl[name] && hl[name][hlTimeZi]){ placeRec(zi(hl[name][hlTimeZi]), name, 2); } });
	}

	// (10) 生日系（依辅弼昌曲位）
	if(starIdx['左辅'] != null){ place(starIdx['左辅'] + dayInt - 1, '三台', 3); }
	if(starIdx['右弼'] != null){ place(starIdx['右弼'] - (dayInt - 1), '八座', 3); }
	if(starIdx['文昌'] != null){ place(starIdx['文昌'] + dayInt - 2, '恩光', 3); }
	if(starIdx['文曲'] != null){ place(starIdx['文曲'] + dayInt - 2, '天贵', 3); }

	// (11) 旬空（年柱→空二支，副按极性；[B12] 单星法只安正空支）
	xunEmptyBranches(yearGan, yearZiIdx).forEach((zk)=>{
		const i = zi(zk);
		const isFu = isYangZhi(i) !== yearPolarYang;
		if(isFu && ctx.kongwangStyle === 'single'){ return; }
		place(i, (isFu ? '副' : '') + '旬空', 4);
	});

	// (12) 博士十二神（起禄存，阳男阴女顺）
	if(starIdx['禄存'] != null){
		for(let i = 0; i < 12; i++){
			const idx = fwd ? ((starIdx['禄存'] + i) % 12) : (((starIdx['禄存'] - i) % 12 + 12) % 12);
			place(idx, STARS_BOSI[i], 5);
		}
	}
	// (13) 将前十二神（年支三合，顺）
	const jiang = STARS_JIANG[yearZi];
	if(jiang){ Object.keys(jiang).forEach((nm)=>{ place(zi(jiang[nm]), nm, 5); }); }
	// (14) 岁前十二神（太岁，顺）
	for(let i = 0; i < 12; i++){ place((yearZiIdx + i) % 12, STARS_TAISUI[i], 5); }

	// (15) 天伤/天使(古法§6)。fixed(默认):天伤@交友(命前7)、天使@疾厄(命前5),字节零回归。
	//   yinyang(中州派):仅「阴男阳女」互换;阳男阴女按常法。判据=年干阴阳×性别(据古法纠错:非阳男阴女)。
	//   走已验证内核 placeShangShi(JS==古法口径,golden 锁)。
	const ssRule = ctx.shangShi === 'yinyang' ? 'yinyang_swap' : 'fixed';
	const ss = placeShangShi(z(lifeIdx), yearGan, male ? '男' : '女', ssRule);
	place(zi(ss['天伤']), '天伤', 4);
	place(zi(ss['天使']), '天使', 4);

	// (15b) 空劫命名(古法§5):modern(默认)不动=字节零回归(时系逆行星=地空、年支独立天空已由年支表收录)。
	//   book→古本《全书》把时系逆行星称「天空」;为避免一盘两天空(古法§5.4 互斥择一),先去年支独立天空再改名。
	if(ctx.kongNaming === 'book'){
		houses.forEach((h)=>{
			// 互斥:移除年支独立天空(杂曜层,本表 type4=starsOthersBad,容错并扫 Good)
			h.starsOthersBad = h.starsOthersBad.filter((s)=>s.name !== '天空');
			h.starsOthersGood = h.starsOthersGood.filter((s)=>s.name !== '天空');
			h.starsEvil.forEach((s)=>{ if(s.name === '地空'){ s.name = '天空'; } });  // 时系逆行星→天空(古本)
		});
	}

	// (16) 小限 age 1..100。[B15b] 口径单源=ziweiCore.xiaoxianClockwiseFor(ctx.xiaoxianMode 经 FORWARD 表进来):
	// 默认'0'=男顺女逆,与 Java setupSmallDirection 字节一致(零回归);'1'=阳男阴女顺(中州)。
	const xxStart = XIAOXIAN_START[yearZi];
	if(xxStart){
		const xs = zi(xxStart);
		const xxCw = xiaoxianClockwiseFor(ctx.xiaoxianMode, male, yearPolarYang);
		for(let age = 1; age <= 100; age++){
			const k = (age - 1) % 12;
			const idx = xxCw ? ((xs + k) % 12) : (((xs - k) % 12 + 12) % 12);
			houses[idx].smallDirection.push(age);
		}
	}

	// (17) 命主 / 身主 / 斗君
	// 命主取键两法:默认按命宫地支(经典法);year_branch=按生年支(Java /ziwei/birth 同源,
	// ZiWeiChart.setup 用 StarsLifeMaster.get(yearZi))——双引擎对拍 Java 兼容档用。
	const lifeMaster = ctx.lifeMasterBy === 'year_branch'
		? (LIFE_MASTER[yearZi] || LIFE_MASTER[z(lifeIdx)])
		: (LIFE_MASTER[z(lifeIdx)] || LIFE_MASTER[yearZi]);
	const bodyMaster = BODY_MASTER[yearZi];
	const zidou = (DOUJUN[monthCn] && DOUJUN[monthCn][timeZi]) || null;
	const doujun = zidou != null ? z((zi(zidou) + yearZiIdx) % 12) : null;

	// 星集(WP-C):north18=精简18星(14主+左右昌曲),河洛派用。滤掉其余辅杂煞小(长生/大限/命身不动)。
	if(ctx.starSet === 'north18'){
		const KEEP = new Set(['紫微', '天机', '太阳', '武曲', '天同', '廉贞', '天府', '太阴', '贪狼', '巨门', '天相', '天梁', '七杀', '破军', '左辅', '右弼', '文昌', '文曲']);
		houses.forEach((h)=>{
			['starsAssist', 'starsEvil', 'starsOthersGood', 'starsOthersBad', 'starsSmall'].forEach((f)=>{
				h[f] = h[f].filter((s)=>KEEP.has(s.name.charAt(0) === '副' ? s.name.slice(1) : s.name));
			});
		});
	}

	return {
		houses, lifeHouseIndex: lifeIdx, bodyHouseIndex: bodyIdx,
		wuxingJu: ju, wuxingJuText: juInfo.juText, ziweiIndex,
		yearGan, yearZi, timeZi, lifeMaster, bodyMaster, zidou, doujun,
		birthSihua: { 禄: hua4[0], 权: hua4[1], 科: hua4[2], 忌: hua4[3] },
		dayInt, male, sanPan: 'tian',
	};
}

// 天地人三盘(中州派观察法·三盘起法):
//   天盘=标准命盘;地盘=身宫作命宫(身宫干支定五行局→重排十四正曜);人盘=福德宫作命宫(福德宫干支定局→重排)。
//   仅「命宫宫垣 + 十四正曜 + 十二宫名 + 五行局/命主」变,其余各星曜(辅杂煞小/长生/大限/身宫)宫位一律不变。
//   特例:命宫==身宫→天=地;身宫==福德宫→地=人(此时返回原盘)。
// [P2a] 命主取法后处理(Java 盘专用):ming_branch 时把 chart.lifeMaster 改按命宫支取。
// 🔴 只许在 ziweiNeedsLocalEngine()===false 的 Java 盘路径调用 —— 本地引擎盘已按 ctx.lifeMasterBy
//    以**天盘命宫**算好且 deriveSanPan 保留基盘命主;若在 deriveSanPan 之后按当前 lifeHouseIndex
//    重算,会拿观察盘移过的命宫=错(命主不随三盘移是不变量,金标钉守)。幂等:同选项重复调用同值。
export function applyLifeMasterOption(chart, lifeMasterBy){
	// 🔴 默认(year_branch/缺省)恒 no-op —— Java 盘原值即生年支值,默认路径零改动(V2 基线钉着);
	//    运行时「切回 year_branch」的恢复由 ZiWeiMain 交互监听显式做,不在此函数。
	if(!chart || lifeMasterBy !== 'ming_branch'){ return chart; }
	try{
		const h = chart.houses && chart.houses[chart.lifeHouseIndex];
		const zhi = h && h.ganzi ? `${h.ganzi}`.charAt(1) : '';
		if(zhi && LIFE_MASTER[zhi]){ chart.lifeMaster = LIFE_MASTER[zhi]; }
	}catch(e){ /* 派生失败保留原值 */ }
	return chart;
}

export function deriveSanPan(tianChart, anchor){
	if(!tianChart || anchor === 'tian' || !anchor){ return tianChart; }
	const houses = tianChart.houses;
	// 新命宫所在物理宫:地盘=身宫宫位;人盘=福德宫宫位。
	let newMingIdx;
	if(anchor === 'di'){ newMingIdx = tianChart.bodyHouseIndex; }
	else if(anchor === 'ren'){ newMingIdx = houses.findIndex((h)=>h.name === '福德宫' || h.name === '福德'); }
	else { return tianChart; }
	if(newMingIdx == null || newMingIdx < 0){ return tianChart; }
	// 新局/新紫微/新十四正曜
	const mg = houses[newMingIdx].ganzi;
	const juInfo = coreWuxingJu(mg.charAt(0), zi(mg.charAt(1)));
	const newJu = juInfo.ju;
	const newZiwei = ziweiPos(tianChart.dayInt, newJu);
	const tf = tianfuPos(newZiwei);
	const newMain = {};   // idx → [星名]
	Object.keys(NORTH_MAIN_STEP).forEach((s)=>{ const k = ((newZiwei + NORTH_MAIN_STEP[s]) % 12 + 12) % 12; (newMain[k] = newMain[k] || []).push(s); });
	Object.keys(SOUTH_MAIN_STEP).forEach((s)=>{ const k = ((tf + SOUTH_MAIN_STEP[s]) % 12 + 12) % 12; (newMain[k] = newMain[k] || []).push(s); });
	// 克隆:清空主星层、按新位重排;其余星组/相位/long生 照搬天盘;宫名随新命宫旋转。
	const out = houses.map((h, i)=>{
		let delta = i - newMingIdx; let idx = Math.abs(delta); if(delta > 0){ idx = 12 - delta; }
		return {
			...h,
			name: HOUSE_NAMES[idx],
			isLife: i === newMingIdx,
			starsMain: (newMain[i] || []).map((nm)=>decorateStar(nm, i, tianChart.yearGan)),
		};
	});
	return {
		...tianChart, houses: out,
		lifeHouseIndex: newMingIdx,
		wuxingJu: newJu, wuxingJuText: juInfo.juText, ziweiIndex: newZiwei,
		// 命主保留基盘值(生年支口径,与 bodyMaster 一致):三盘只重排宫名/局/主星,命主是【生年属性】不随太极点移动;
		// 若按新命宫支重算会致「切地盘/人盘→命主跳」(与亮度/切开关同类的误改坑)。
		lifeMaster: tianChart.lifeMaster,
		sanPan: anchor,
	};
}

// 晚子时方案(古法§1.3)→ (after23NewDay, lateZiHourUseNextDay)。仅紫微自用,不动共享默认。
//   A 子初换日(默认):过23点换日、时柱用次日干 → (1,1)。B 夜子折中:日柱不换、时柱用次日干 → (0,1)。C 子正换日:都不换 → (0,0)。
function lateZiParams(lateZi){
	if(lateZi === 'midnight_split'){ return { after23NewDay: 0, lateZiHourUseNextDay: 1 }; }
	if(lateZi === 'zi_zheng'){ return { after23NewDay: 0, lateZiHourUseNextDay: 0 }; }
	return { after23NewDay: 1, lateZiHourUseNextDay: 1 };   // zi_chu(A) 默认
}

// 农历入口:birth + options(timeAlg/晚子时 lateZi/闰月 leapMonth/定年界线 yearBoundary/大限跨度/天马/星集/天伤天使) → 完整本命盘。
// 农历经 buildLocalBaziResult(lunar.js,共享层零改动);所有传本调整在本紫微引擎内完成,不影响其他技术。
export function calcZiwei(birth, options = {}){
	// 晚子时双盘(§1.3,令东来「排两盘取与命主经历相似者」):当日盘(日不换)+次日盘(过23换日)。
	// 仅 23 时生辰两盘真不同;非 23 时两盘相同→不挂 dualAlt(退化为单盘)。当日盘为 primary。
	if(options.lateZi === 'dual'){
		const dayChart = calcZiwei(birth, { ...options, lateZi: 'zi_zheng' });    // 当日盘:日柱不换
		const nextChart = calcZiwei(birth, { ...options, lateZi: 'zi_chu' });      // 次日盘:过23点换日
		const differ = dayChart.ziweiIndex !== nextChart.ziweiIndex || dayChart.lifeHouseIndex !== nextChart.lifeHouseIndex;
		if(differ){
			dayChart.dualAlt = nextChart;
			dayChart.dualLabels = ['当日盘', '次日盘'];
			nextChart.dualLabels = ['当日盘', '次日盘'];
		}
		return dayChart;
	}
	// 晚子时:若给了具体方案则映射;'global'(默认档)/缺省=沿用显式 after23NewDay/lateZiHourUseNextDay(即全局设置)。
	const lz = (options.lateZi && options.lateZi !== 'global') ? lateZiParams(options.lateZi) : { after23NewDay: options.after23NewDay, lateZiHourUseNextDay: options.lateZiHourUseNextDay };
	const params = {
		date: birth.date, time: birth.time, zone: birth.zone, lon: birth.lon, lat: birth.lat,
		gpsLon: birth.gpsLon, gpsLat: birth.gpsLat, ad: birth.ad != null ? birth.ad : 1,
		gender: birth.gender,
		timeAlg: options.timeAlg != null ? options.timeAlg : 0,
		after23NewDay: lz.after23NewDay,
		lateZiHourUseNextDay: lz.lateZiHourUseNextDay,
	};
	const r = buildLocalBaziResult(params);
	return buildChartFromBazi(r, birth, options);
}

// [Z4·择日] 轻量入口:农历核走 buildLocalNongliLite(无百年大运推演;calcZiwei 全量核 91ms/盘
// 实测,重头在 buildLocalBaziResult 的 yun/daYunList——本命盘 13 步安星本身纯查表 <1ms)。
// 组装体与 calcZiwei 同一 buildChartFromBazi(判定同源单源,主安星逻辑修正两口自动跟);
// 差异仅农历供数层,产出 chart 无 r.yun 大运依赖(assembleNatalChart 不读)。
// 🔴 不支持 lateZi='dual'(双盘人工比对是本命场景;择日候选时刻用单方案,调用方 validate)。
export function calcZiweiFromLite(birth, options = {}){
	const lz = (options.lateZi && options.lateZi !== 'global' && options.lateZi !== 'dual') ? lateZiParams(options.lateZi) : { after23NewDay: options.after23NewDay, lateZiHourUseNextDay: options.lateZiHourUseNextDay };
	const params = {
		date: birth.date, time: birth.time, zone: birth.zone, lon: birth.lon, lat: birth.lat,
		gpsLon: birth.gpsLon, gpsLat: birth.gpsLat, ad: birth.ad != null ? birth.ad : 1,
		gender: birth.gender,
		timeAlg: options.timeAlg != null ? options.timeAlg : 0,
		after23NewDay: lz.after23NewDay,
		lateZiHourUseNextDay: lz.lateZiHourUseNextDay,
	};
	const r = buildLocalNongliLite(params);
	return buildChartFromBazi(r, birth, options);
}

// 共同组装体:buildLocal(Bazi|NongliLite) 产物 → 完整 chart(nongli 键谱两路同构=buildNongli 同函数)。
function buildChartFromBazi(r, birth, options){
	const nl = r.bazi.nongli;
	const fc = r.bazi.fourColumns;
	// 定年界线(古法§1.6):默认 lichun(立春,= fourColumns.year,现状口径);lunar_1_1=正月初一(yearGZByLunar)。
	const ygLichun = (fc.year && (fc.year.ganzi || fc.year.ganZhi)) || '甲子';
	const yg = (options.yearBoundary === 'lunar_1_1' && nl.yearGZByLunar) ? nl.yearGZByLunar : ygLichun;
	const tg = (fc.time && (fc.time.ganzi || fc.time.ganZhi)) || '甲子';
	// 晚子时·紫微所用农历(月/日/闰):after23NewDay=1 且本命落 23 点子时段时,日柱已进位次日,
	// 紫微落宫/命宫/农历日须随之进位——否则 zi_chu/midnight_split/zi_zheng 三方案紫微全同(死)。
	// ziweiMonthNum/ziweiDayNum/ziweiLeap 由 baziLunarLocal 按日柱口径派生,默认==monthNum/dayNum/leap(零回归)。
	// ziweiLunarBasis='calendar':安命/安紫微改用【日历口径】农历日(23:30 不进日)——Java 同源
	// (ZiWeiChart 的 nongli.day 即日历日,八字四柱仍进日,属「柱进盘不进」混合口径);对拍 Java 兼容档用。
	const calBasis = options.ziweiLunarBasis === 'calendar';
	const zwMonth = (!calBasis && nl.ziweiMonthNum != null) ? nl.ziweiMonthNum : nl.monthNum;
	const zwDay = (!calBasis && nl.ziweiDayNum != null) ? nl.ziweiDayNum : nl.dayNum;
	const zwLeap = (!calBasis && nl.ziweiLeap != null) ? nl.ziweiLeap : nl.leap;
	const chart = assembleNatalChart({
		yearGan: yg.charAt(0), yearZi: yg.charAt(1),
		monthInt: zwMonth, leap: zwLeap, dayInt: zwDay, timeZi: tg.charAt(1),
		male: Number(birth.gender) !== 0,                  // 0=女、其余=男(对齐 BaZiGender)
		// 🔴 引擎键经单一真值表转发(手抄清单曾漏 changshengStart/kuiYue=真机死开关,复查实锤)
		...collectEngineOpts(options),
		// 闰月两口径派生(baziLunarLocal 仅 leap 时给值;split_days 真半点 / solar_term 过节归下月)
		monthDays: nl.ziweiMonthDays, passedNextJie: nl.ziweiPassedNextJie,
	});
	chart.nongli = nl;
	chart.fourColumns = fc;
	// [Z4] 安星实际锚(择日 plateKey 消费):calendar/ziwei 两基准下安星真正用的月/闰/日——
	// plateKey 若绕过此锚直读 nl.ziweiDayNum,在 calendar 基准+晚子时进位窗(23 点段)与
	// 判定面(日历日)不同构 → 23 点段被折进次日行(行内同盘探针实抓)。
	chart.anchorMD = { m: zwMonth, leap: !!zwLeap, d: zwDay, yg: yg };
	return chart;
}
