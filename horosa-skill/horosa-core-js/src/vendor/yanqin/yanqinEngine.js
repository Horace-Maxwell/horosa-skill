// 演禽 · 起禽核心引擎(纯函数,无副作用,无星历依赖=纯历法引擎)。
// 复现两份权威复原文档「已程序验证」的起禽四法 + 翻禽倒将活曜 + 投胎度数。
// 所有结论由 yanqinEngine.golden.test.js 锁死(文档锚点 = 法律)。
import {
	MANSIONS, mansionByIdx, MANSION_HEAD_TO_IDX, MANSION_NAME_TO_IDX,
	YAO_CYCLE, YAO_TO_WEEKDAY, YAO_TO_WUXING, YAO_ORDER, WEEKDAY_TO_YAO,
	TIANGAN, DIZHI, DIZHI_TO_IDX,
	R_RING, MONTHQIN_START_BY_YAO, MONTHQIN_START_BY_YAO_B,
	HUOYAO_START_BY_YAO, FANHUOYAO_START_BY_YAO,
	HESU_OF, TOUTAI_BIRDS, WUXING_KE,
	HUANGDAO_12SHEN, HUANGDAO_JI, JIANCHU_12, JIANCHU_GOOD,
	QIYUAN_JIAZI_START, SIJI_WANG, WANGFU_WUXING,
} from './yanqinConst.js';

const ANCHOR_MANSION_IDX = 11; // 虚日鼠
const ANCHOR_GANZHI = 0;       // 甲子

function mod(n, m) { return ((n % m) + m) % m; }

// 🔴 连续日序 = 儒略/格里 JDN(含 1582-10-15 切换),而非 JS Date.UTC(proleptic Gregorian)。
// 后者对 1582 前(尤其 BC)与真实儒略历日序偏差(实测 BC12026 日禽/日干支偏约 28 位,全错);
// year=带符号显示年(BC 负、无 0 年)→ 天文年(BC1=0)。现代域(1582 后)走格里分支,与旧 Date.UTC
// 差常数、diff 不变=零回归(golden 用现代日期不受影响);BC/1582 前走儒略分支,日序修正。
export function dayNumber(year, month, day) {
	const ay = year < 0 ? year + 1 : year;
	const a = Math.floor((14 - month) / 12);
	const y = ay + 4800 - a;
	const m = month + 12 * a - 3;
	const isGreg = year > 1582 || (year === 1582 && (month > 10 || (month === 10 && day >= 15)));
	if (isGreg) {
		return day + Math.floor((153 * m + 2) / 5) + 365 * y + Math.floor(y / 4) - Math.floor(y / 100) + Math.floor(y / 400) - 32045;
	}
	return day + Math.floor((153 * m + 2) / 5) + 365 * y + Math.floor(y / 4) - 32083;
}

// 锚点:1996-01-28 = 甲子日 = 虚日鼠(序11) = 一元一将(七元甲子最干净起点)。以同一 JDN 函数
// 求锚,现代域 diff = dayNumber - ANCHOR 与旧 Date.UTC 口径逐日一致(零回归);古籍 实测坐实。
const ANCHOR_DAY_NUMBER = dayNumber(1996, 1, 28);

// —— 日禽:周历机制(一日一换,28日一轮)✅ ——
// 序号 = ((日序 − 锚点日序 + 锚点宿序 − 1) mod 28) + 1
export function mansionIdxOfDay(year, month, day) {
	const diff = dayNumber(year, month, day) - ANCHOR_DAY_NUMBER;
	return mod(diff + ANCHOR_MANSION_IDX - 1, 28) + 1;
}
export function mansionOfDay(year, month, day) { return mansionByIdx(mansionIdxOfDay(year, month, day)); }

// —— 干支(日)✅:锚 1996-01-28=甲子 ——
export function ganzhiIdxOfDay(year, month, day) {
	const diff = dayNumber(year, month, day) - ANCHOR_DAY_NUMBER;
	return mod(diff + ANCHOR_GANZHI, 60);
}
export function ganzhiOfDay(year, month, day) {
	const g = ganzhiIdxOfDay(year, month, day);
	return TIANGAN[g % 10] + DIZHI[g % 12];
}

// —— 七元 / 四将 ✅:一元=60日、七元=420日;元=⌊(diff mod420)/60⌋+1、将=⌊(diff mod60)/15⌋+1 ——
export function yuanJiangOfDay(year, month, day) {
	const diff = dayNumber(year, month, day) - ANCHOR_DAY_NUMBER;
	const yuan = Math.floor(mod(diff, 420) / 60) + 1; // 1..7
	const jiang = Math.floor(mod(diff, 60) / 15) + 1; // 1..4
	return { yuan, jiang };
}

// 宿名第二字(七曜)
export function elementOf(mansionName) {
	const name = typeof mansionName === 'object' ? mansionName.name : mansionName;
	return name && name.length >= 2 ? name[1] : null;
}

// —— 年禽 ✅:(year+15) mod 28,0→28 ——
// 此式本身即「三元甲子承袭」:1864上元甲子=氐、1924中元甲子=箕、1984下元甲子=虚,三锚全中;
// 2002=角木蛟、2008=箕水豹(主流)。坊间另称 B 系「值日宿承袭·2002=箕」经核系单源内部矛盾,不采纳(详 yanqinSchools 注)。
export function yearQin(year) {
	const idx = mod(year + 15, 28) || 28;
	return mansionByIdx(idx);
}

// —— 月禽 ✅:年禽曜→正月起宿,顺数填月。verse 'A'(主流,默认)| 'B'(异系) ——
export function monthQin(year, lunarMonth, verse) {
	const yq = yearQin(year);
	const tbl = verse === 'B' ? MONTHQIN_START_BY_YAO_B : MONTHQIN_START_BY_YAO;
	const startIdx = MANSION_NAME_TO_IDX[tbl[yq.yao]];
	return mansionByIdx(mod(startIdx - 1 + (lunarMonth - 1), 28) + 1);
}

// —— 禽星五行:按七政(宿曜第二字·默认);qinWuxing='wangfu' 时汪绂重配已坐实者 override(WP-17)——
export function wuxingOfMansion(mansion, qinWuxing) {
	if (!mansion) { return null; }
	if (qinWuxing === 'wangfu') {
		const w = WANGFU_WUXING[mansion.name && mansion.name[0]];
		if (w) { return w; }   // 已坐实(亢火/牛木);余宿待校→回退七政
	}
	return YAO_TO_WUXING[mansion.yao];
}

// —— 时禽(元元相轮 + 旬头位移)⚠️ 古籍 ——
// 子时正禽 = R[(曜序 + 元-1 + 旬头位移) mod 7];旬头位移 = 日干支序 mod 10(甲日=0)。
// 「七元甲子时禽表」= 基准(useXun=false 即无位移,等价甲子日)。
// ⚠️ 文档冲突:一处判旬头位移强制(T1 庚午卯=井木犴 需位移);另有时禽 T2、翻禽 F1 两算例"无位移"。
// 三锚不能同时满足。useXun 做成开关交流派/用户定;默认依主流古籍口径 = true。
// 基准子时起宿(无位移)idx:R[(曜序+元-1) mod 7]
export function hourZiBaseIdx(dayYao, yuan) {
	const rIdx = mod(YAO_ORDER[dayYao] + (yuan - 1), 7);
	return MANSION_HEAD_TO_IDX[R_RING[rIdx]];
}
export function hourZiStartIdx(year, month, day, useXun) {
	const dayM = mansionOfDay(year, month, day);
	const { yuan } = yuanJiangOfDay(year, month, day);
	const baseR = mod(YAO_ORDER[dayM.yao] + (yuan - 1), 7);
	const xun = (useXun === false) ? 0 : (ganzhiIdxOfDay(year, month, day) % 10);
	return MANSION_HEAD_TO_IDX[R_RING[mod(baseR + xun, 7)]];
}
// hourBranch: 0=子 … 11=亥
export function hourQin(year, month, day, hourBranch, useXun) {
	const ziIdx = hourZiStartIdx(year, month, day, useXun);
	return mansionByIdx(mod(ziIdx - 1 + hourBranch, 28) + 1);
}

// —— 翻禽(他禽)✅ 古籍 ——
// 当日盘 = 子时正禽置子、顺地支排28宿;从时禽地支顺数(地支+宿同进)至日禽宿,记落地支,
// 在当日盘读该地支之禽 = 翻禽。
export function fanQin(year, month, day, hourBranch, useXun) {
	const ziIdx = hourZiStartIdx(year, month, day, useXun);   // 子时正禽 Z
	const hourMansionIdx = mod(ziIdx - 1 + hourBranch, 28) + 1; // 时禽 T
	const dayIdx = mansionIdxOfDay(year, month, day);          // 日禽 D
	const k = mod(dayIdx - hourMansionIdx, 28);                // 顺数步数 T→D
	const landBranch = mod(hourBranch + k, 12);               // 落地支
	const idx = mod(ziIdx - 1 + landBranch, 28) + 1;          // 当日盘读落点
	return { fan: mansionByIdx(idx), hourMansion: mansionByIdx(hourMansionIdx), landBranch };
}

// —— 倒将(主将/次将)✅ 古籍 ——
// 次将 = 气将本宫→顺数→时将之宫所得宿;主将 = 时将之宫→倒回(逆数)→气将之位所得宿。
// 气将 = 当日值日宿(28将=28宿,落本日地支);时将 = 时禽。此处给程序化次/主将。
export function daoJiang(year, month, day, hourBranch, useXun) {
	const dayIdx = mansionIdxOfDay(year, month, day);
	const dayBranch = ganzhiIdxOfDay(year, month, day) % 12; // 气将本宫(日支)
	const { hourMansion } = fanQin(year, month, day, hourBranch, useXun);
	const hourMansionIdx = hourMansion.idx;
	const step = mod(hourBranch - dayBranch, 12);            // 气将宫→时将宫 宫数
	const ciJiang = mansionByIdx(mod(dayIdx - 1 + step, 28) + 1);   // 次将:顺数
	const zhuJiang = mansionByIdx(mod(hourMansionIdx - 1 - step, 28) + 1); // 主将:倒回
	return { ciJiang, zhuJiang };
}

// —— 活曜(番禽活曜头诀,自寅起)✅ 古籍 ——
// variant: 'fanqin'(番禽系,土→翼)| 'fanqin2'(翻禽系异本,土→箕)
export function huoYao(year, month, day, hourBranch, variant) {
	const dayM = mansionOfDay(year, month, day);
	const tbl = variant === 'fanqin2' ? FANHUOYAO_START_BY_YAO : HUOYAO_START_BY_YAO;
	const startHead = tbl[dayM.yao];
	const startIdx = MANSION_HEAD_TO_IDX[startHead];
	// 自寅位(寅=2)起轮:寅时即起宿,顺数到所求时支
	const steps = mod(hourBranch - 2, 12);
	return mansionByIdx(mod(startIdx - 1 + steps, 28) + 1);
}

// —— 投胎度数→十二禽兽(体系A 禄命)✅ 古籍 ——
// 寅时(2)正月(1)固定起凤凰(环序0);月进一→度退一(环-1),时进一→环+1。
export function toutaiDu(lunarMonth, hourBranch) {
	// TOUTAI_BIRDS 已按"度反序"排环。月进一→度退一=环 index+1;时进一→度进一=环 index-1。
	// 寅时正月起凤凰(index0)。ringPos = (月-正月) − (时支-寅)。
	const ringPos = mod((lunarMonth - 1) - (hourBranch - 2), 12);
	return TOUTAI_BIRDS[ringPos];
}

// —— 命星→身星(合宿歌法,体系C 禄命)✅ 古籍 ——
// ① 命星之宿取合宿;② 合宿置子,沿28宿顺地支前行;③ 数到生年地支落点之禽=身星。
export function shenStarFromMingStar(mingStarHead, birthYearBranchIdx) {
	const heHead = HESU_OF[mingStarHead];
	if (!heHead) { return null; }
	const startIdx = MANSION_HEAD_TO_IDX[heHead];
	return mansionByIdx(mod(startIdx - 1 + birthYearBranchIdx, 28) + 1);
}

// —— 禽课吉凶基元:我禽 vs 彼禽 五行胜负 ✅ ——
// 直接吃五行:'meWin'我克彼|'theyWin'彼克我|'meSheng'我生彼|'theySheng'彼生我|'peace'比和
export function qinKeByWuxing(a, b) {
	if (!a || !b) { return 'peace'; }
	if (a === b) { return 'peace'; }
	if (WUXING_KE[a] === b) { return 'meWin'; }
	if (WUXING_KE[b] === a) { return 'theyWin'; }
	const sheng = { 木: '火', 火: '土', 土: '金', 金: '水', 水: '木' };
	if (sheng[a] === b) { return 'meSheng'; }
	if (sheng[b] === a) { return 'theySheng'; }
	return 'peace';
}
// 吃宿名第二字(七曜)的便捷版(默认七政五行)
export function qinKeJudge(meYao, theyYao) {
	return qinKeByWuxing(YAO_TO_WUXING[meYao], YAO_TO_WUXING[theyYao]);
}

// —— 择日叠加:黄黑道十二值神 ✅ 古籍 ——
// 青龙起位随月支(寅月龙在子),十二神顺数日支。monthZhiIdx/dayZhiIdx = 地支序(子0…亥11)。
export function huangHeiDao(monthZhiIdx, dayZhiIdx) {
	const qinglong = mod(2 * (monthZhiIdx - 2), 12); // 青龙位地支:寅月(2)→子(0)
	const idx = mod(dayZhiIdx - qinglong, 12);
	return { shen: HUANGDAO_12SHEN[idx], huang: HUANGDAO_JI.has(idx), idx };
}
// —— 择日叠加:建除十二神 ✅ 古籍 ——:月建(月支)位起「建」,顺数日支。
export function jianChu(monthZhiIdx, dayZhiIdx) {
	const idx = mod(dayZhiIdx - monthZhiIdx, 12);
	const shen = JIANCHU_12[idx];
	return { shen, good: JIANCHU_GOOD.has(shen), idx };
}
// 便捷:给公历日期(日支内算)+ 农历月支序,出黄黑道/建除。monthZhiIdx 须由调用方(农历)提供。
export function huangHeiDaoOfDay(year, month, day, monthZhiIdx) {
	const dayZhiIdx = ganzhiIdxOfDay(year, month, day) % 12;
	return huangHeiDao(monthZhiIdx, dayZhiIdx);
}
export function jianChuOfDay(year, month, day, monthZhiIdx) {
	const dayZhiIdx = ganzhiIdxOfDay(year, month, day) % 12;
	return jianChu(monthZhiIdx, dayZhiIdx);
}

// —— 定局表生成(查表化身,零新算法;由已验证起禽式循环生成)✅ ——
// 日禽 60×7:干支序(0..59) × 元(1..7) → 值日宿。甲子日某元起宿 = QIYUAN_JIAZI_START[元-1],干支顺进一宿。
export function dingjuRiqin() {
	const out = [];
	for (let gz = 0; gz < 60; gz += 1) {
		const cells = [];
		for (let yuan = 1; yuan <= 7; yuan += 1) {
			const startIdx = MANSION_HEAD_TO_IDX[QIYUAN_JIAZI_START[yuan - 1]];
			cells.push(mansionByIdx(mod(startIdx - 1 + gz, 28) + 1).name);
		}
		out.push({ ganzhi: TIANGAN[gz % 10] + DIZHI[gz % 12], cells });
	}
	return out;
}
// 月禽 7×12:年禽曜 × 农历月(1..12) → 月禽。verse 'A'(默认)|'B'。
export function dingjuYueqin(verse) {
	const tbl = verse === 'B' ? MONTHQIN_START_BY_YAO_B : MONTHQIN_START_BY_YAO;
	return YAO_CYCLE.map((yao) => {
		const startIdx = MANSION_NAME_TO_IDX[tbl[yao]];
		return { yao, cells: Array.from({ length: 12 }, (_, m) => mansionByIdx(mod(startIdx - 1 + m, 28) + 1).name) };
	});
}
// 年禽三元定局:[startYear, endYear] 逐年 → 年禽(A系公式)。
export function dingjuNianqin(startYear, endYear) {
	const out = [];
	for (let y = startYear; y <= endYear; y += 1) { out.push({ year: y, name: yearQin(y).name }); }
	return out;
}
// 四季旺:某宿(单字首字)所旺之季(春夏秋冬),无则 null。用于四季歌高亮。
export function seasonOfMansionHead(head) {
	const found = Object.keys(SIJI_WANG).find((s) => SIJI_WANG[s].includes(head));
	return found || null;
}

// 一站式:给公历日期+时支,出该时刻四禽 + 翻禽倒将活曜(择日/占卜共用)。
export function castQinChart(year, month, day, hourBranch, opts) {
	const o = opts || {};
	const useXun = o.useXun;
	const dayMansion = mansionOfDay(year, month, day);
	const { yuan, jiang } = yuanJiangOfDay(year, month, day);
	const ganzhi = ganzhiOfDay(year, month, day);
	const hour = (hourBranch !== undefined && hourBranch !== null)
		? hourQin(year, month, day, hourBranch, useXun) : null;
	const fan = (hourBranch !== undefined && hourBranch !== null)
		? fanQin(year, month, day, hourBranch, useXun) : null;
	const dao = (hourBranch !== undefined && hourBranch !== null)
		? daoJiang(year, month, day, hourBranch, useXun) : null;
	// 活曜:huoYaoVariant='off'(如池本理不载活曜)→ 不出;番禽系/翻禽系土曜起宿不同。
	const huo = (hourBranch !== undefined && hourBranch !== null && o.huoYaoVariant !== 'off')
		? huoYao(year, month, day, hourBranch, o.huoYaoVariant) : null;
	const ziStart = (hourBranch !== undefined && hourBranch !== null)
		? mansionByIdx(hourZiStartIdx(year, month, day, useXun)) : null;
	return {
		ganzhi, yuan, jiang, ziStart,
		weekday: WEEKDAY_TO_YAO[ (function(){ const d = new Date(Date.UTC(year, month - 1, day)); return d.getUTCDay(); })() ],
		yearQin: yearQin(year),
		dayQin: dayMansion,
		hourQin: hour,
		fanQin: fan ? fan.fan : null,
		daoJiang: dao,
		huoYao: huo,
		hourBranch: (hourBranch !== undefined && hourBranch !== null) ? hourBranch : null,
	};
}
