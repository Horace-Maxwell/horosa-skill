// 紫微斗数 · 七大流派分歧点权威内核(纯决策内核,逐函数对齐古法口径)。
// 七点:① 火铃起宫 ② 闰月取月 ③ 晚子时 ④ 定年界线 ⑤ 空劫命名 ⑥ 天伤天使 ⑦ 宫干+四化。
// 纯决策函数、无副作用、可单测;配套 golden 见 __tests__/ziweiSchools.test.js。
// 关键纠错:火铃「全书=全集」同表(真分歧是南派忽略生时);
// 天伤天使「阴男阳女」才互换(非阳男阴女);四化七干各派一致、仅戊庚壬分歧、庚干四派两两不同(北派天相忌独有)。

export const STEMS = ['甲', '乙', '丙', '丁', '戊', '己', '庚', '辛', '壬', '癸'];
export const BRANCHES = ['子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥'];
export const TRIADS = ['寅午戌', '申子辰', '巳酉丑', '亥卯未'];
export const TRIAD_OF = (function(){ const m = {}; TRIADS.forEach((g)=>{ for(let i = 0; i < g.length; i++){ m[g.charAt(i)] = g; } }); return m; })();

const bi = (b)=>BRANCHES.indexOf(b);
const si = (s)=>STEMS.indexOf(s);
const mod12 = (n)=>((n % 12) + 12) % 12;
export function isYangStem(stem){ return si(stem) % 2 === 0; }   // 阳干 甲丙戊庚壬

// ① 火星/铃星(年支三合定子时起宫,顺数到生时;南派 nanpai 忽略生时=固定子)。全书=全集=同表。
export const HUO_START = { 寅午戌: '丑', 申子辰: '寅', 巳酉丑: '卯', 亥卯未: '酉' };
export const LING_START = { 寅午戌: '卯', 申子辰: '戌', 巳酉丑: '戌', 亥卯未: '戌' };
export function placeHuoLing(yearBranch, hourBranch, huoling){
	const triad = TRIAD_OF[yearBranch];
	const huo0 = bi(HUO_START[triad]);
	const ling0 = bi(LING_START[triad]);
	const h = huoling === 'nanpai' ? 0 : bi(hourBranch);   // 南派固定子(h=0)
	return { 火星: BRANCHES[mod12(huo0 + h)], 铃星: BRANCHES[mod12(ling0 + h)] };
}

// ② 闰月取月。返回 {palaceMonth(命身/月系所用月), starMonth}。仅 split_star_month 二者不同。
export function resolveLeapMonth(month, day, isLeap, leapMonth, monthDays, passedNextTerm){
	if(!isLeap){ return { palaceMonth: month, starMonth: month }; }
	const nxt = (month % 12) + 1;   // 下月(闰十二→正月)
	const r = leapMonth;
	if(r === 'current'){ return { palaceMonth: month, starMonth: month }; }
	if(r === 'next'){ return { palaceMonth: nxt, starMonth: nxt }; }
	if(r === 'split15'){ const m = day <= 15 ? month : nxt; return { palaceMonth: m, starMonth: m }; }
	// 🔴 split_days=「按实际天数取中点」:大月(30)半点=15、小月(29)半点=14 —— 与 split15 在
	//    29 天闰月分道。旧实现 floor((d+1)/2) 对 29/30 都得 15=split15 克隆(假选项,复查实锤)。
	if(r === 'split_days'){ const half = Math.floor((monthDays || 30) / 2); const m = day <= half ? month : nxt; return { palaceMonth: m, starMonth: m }; }
	if(r === 'solar_term'){ if(passedNextTerm == null){ throw new Error('solar_term 需 passedNextTerm'); } const m = passedNextTerm ? nxt : month; return { palaceMonth: m, starMonth: m }; }
	if(r === 'split_star_month'){ return { palaceMonth: nxt, starMonth: month }; }
	throw new Error('leapMonth ' + r);
}
export function flowMonthSplit(day){ return day <= 15 ? 0 : 1; }   // 推流月:≤15归上月、≥16归下月

// ③ 晚子时(23:00–24:00)。返回 1 盘(day_unchanged/day_advance)或 2 盘(dual_chart)。
export function isLateZi(clockHour){ return clockHour === 23; }
export function resolveLateZi(lunarDay, dayGzIndex, nextDayGzIndex, lateZi){
	const zi = '子';
	if(lateZi === 'day_unchanged'){ return [{ lunarDay, dayGz: dayGzIndex, hourBranch: zi, label: '夜子时·日不换(当日)' }]; }
	if(lateZi === 'day_advance'){ return [{ lunarDay: lunarDay + 1, dayGz: nextDayGzIndex, hourBranch: zi, label: '子初换日(次日)' }]; }
	if(lateZi === 'dual_chart'){ return [
		{ lunarDay, dayGz: dayGzIndex, hourBranch: zi, label: '夜子时盘(当日)' },
		{ lunarDay: lunarDay + 1, dayGz: nextDayGzIndex, hourBranch: zi, label: '早子时盘(次日)' },
	]; }
	throw new Error('lateZi ' + lateZi);
}

// ④ 定年界线:lunar_new_year 正月初一(紫微正统) / lichun 立春(八字法)。
export function resolveYearGanzhi(solarMs, lunarNewYearMs, lichunMs, prevYearGz, curYearGz, yearBoundary){
	const boundary = yearBoundary === 'lunar_new_year' ? lunarNewYearMs : lichunMs;
	return solarMs >= boundary ? curYearGz : prevYearGz;
}

// ⑤ 空劫:地劫=亥起子顺、地空(逆行星)=亥起子逆。book 命名:逆行星叫「天空」。
export function placeKongJie(hourBranch, kongNaming){
	const h = bi(hourBranch); const hai = bi('亥');
	const jie = BRANCHES[mod12(hai + h)];
	const kong = BRANCHES[mod12(hai - h)];
	return kongNaming === 'book' ? { 地劫: jie, 天空: kong } : { 地劫: jie, 地空: kong };
}
export function placeTiankongYear(yearBranch){ return BRANCHES[mod12(bi(yearBranch) + 1)]; }   // 独立天空=太岁前一位
export function placeJieluKong(yearStem){   // 截路空亡(年干系):空两支
	const table = { 甲: '申', 己: '申', 乙: '午', 庚: '午', 丙: '辰', 辛: '辰', 丁: '寅', 壬: '寅', 戊: '子', 癸: '子' };
	const start = bi(table[yearStem]);
	return [BRANCHES[start], BRANCHES[mod12(start + 1)]];
}

// ⑥ 天伤天使:常法 天伤@仆役(命-7)/天使@疾厄(命-5),夹迁移(命-6)。
//   阴阳互换(中州派):仅「阴男阳女」互换;阳男阴女按常法。判据=年干阴阳×性别。
export function yinyangGroup(yearStem, gender){
	const male = ['m', '男', 'male', 'man', 'boy'].indexOf(String(gender).toLowerCase()) >= 0;
	const yang = isYangStem(yearStem);
	return ((yang && male) || (!yang && !male)) ? '阳男阴女' : '阴男阳女';
}
export function placeShangShi(mingBranch, yearStem, gender, shangShi){
	const mi = bi(mingBranch);
	const puyi = BRANCHES[mod12(mi - 7)];    // 仆役(交友)第8宫
	const jieE = BRANCHES[mod12(mi - 5)];    // 疾厄 第6宫
	const swap = shangShi === 'yinyang_swap' && yinyangGroup(yearStem, gender) === '阴男阳女';
	return swap ? { 天伤: jieE, 天使: puyi } : { 天伤: puyi, 天使: jieE };
}

// ⑦ 宫干(五虎遁)+ 十干四化(各派)。
export const WUHU_YIN = { 甲: '丙', 己: '丙', 乙: '戊', 庚: '戊', 丙: '庚', 辛: '庚', 丁: '壬', 壬: '壬', 戊: '甲', 癸: '甲' };
export function palaceStems(yearStem){
	const start = si(WUHU_YIN[yearStem]);
	const out = {};
	for(let off = 0; off < 12; off++){ const b = mod12(2 + off); out[BRANCHES[b]] = STEMS[(start + off) % 10]; }
	return out;   // 子宫干==寅宫干、丑宫干==卯宫干(循环必然)
}
// 基表=通行/全集(顺序 禄权科忌)。各派仅戊/庚/壬有别。
export const SIHUA_BASE = {
	甲: ['廉贞', '破军', '武曲', '太阳'], 乙: ['天机', '天梁', '紫微', '太阴'],
	丙: ['天同', '天机', '文昌', '廉贞'], 丁: ['太阴', '天同', '天机', '巨门'],
	戊: ['贪狼', '太阴', '右弼', '天机'], 己: ['武曲', '贪狼', '天梁', '文曲'],
	庚: ['太阳', '武曲', '太阴', '天同'], 辛: ['巨门', '太阳', '文曲', '文昌'],
	壬: ['天梁', '紫微', '左辅', '武曲'], 癸: ['破军', '巨门', '太阴', '贪狼'],
};
// ⚠️ 命名坑(与 constants/ZWConst.js 交叉核对,勿混):
//   · 本文件 `beipai` ＝ 真·北派「天相忌」口径(天同科·天相忌);规范键名＝ `beixiang_tianxiang`,`beipai` 仅历史别名(值同)。
//   · ZWConst.SiHuaTables.beipai ＝【通用/飞星】口径(＝本文件 SIHUA_BASE),真·北派在 ZWConst 侧叫 `beixiang`。
//   同名异义:ZWConst 由 sihuaTable('beixiang_tianxiang') 派生其 beixiang 表。
const BEIXIANG_TIANXIANG = { 庚: ['太阳', '武曲', '天同', '天相'] };   // 北派:天同科·天相忌(天相忌独有)
export const SIHUA_OVERRIDES = {
	tongxing: {}, feixing: {}, toupai: {},
	quanshu: { 庚: ['太阳', '武曲', '天同', '太阴'], 壬: ['天梁', '紫微', '天府', '武曲'] },
	zhongzhou: { 戊: ['贪狼', '太阴', '太阳', '天机'], 庚: ['太阳', '武曲', '天府', '天同'], 壬: ['天梁', '紫微', '天府', '武曲'] },
	beixiang_tianxiang: BEIXIANG_TIANXIANG,   // 真·北派(规范键名)
	beipai: BEIXIANG_TIANXIANG,               // 历史别名(=beixiang_tianxiang);⚠️勿与 ZWConst.beipai(通用)混淆
};
export function sihuaTable(school){ return Object.assign({}, SIHUA_BASE, SIHUA_OVERRIDES[school] || {}); }
export function sihuaOf(yearStem, school){ const t = sihuaTable(school)[yearStem]; return { 禄: t[0], 权: t[1], 科: t[2], 忌: t[3] }; }
export function flySihua(palaceStem, school){ return sihuaOf(palaceStem, school); }
// 🔴 来因宫判据单源:宫干==生年干,且宫支不取子丑 —— 五虎遁十干恰布寅至亥,子丑必借寅卯
//    之干,借干宫不作来因。盘面 ZWHouse.drawLaiYing 一直如此;快照/报告曾不排子丑,辛壬年
//    生人会被列出两个来因宫(画的与 AI 读的不是同一批宫,复查实锤)。四消费点全走此谓词。
export function isLaiyinPalace(ganzi, yearStem){
	if(!ganzi || !yearStem) return false;
	const s = `${ganzi}`;
	return s.charAt(0) === yearStem && s.charAt(1) !== '子' && s.charAt(1) !== '丑';
}
export function laiyinPalaces(yearStem){ const ps = palaceStems(yearStem); return Object.keys(ps).filter((b)=>ps[b] === yearStem && b !== '子' && b !== '丑'); }

export const SIHUA_SCHOOLS = ['tongxing', 'quanshu', 'zhongzhou', 'beipai', 'feixing', 'toupai'];

// ── ⑧ 天魁天钺歌诀两版(2026-08-07 双源考据) ─────────────────────────────
// 古版「甲戊庚牛羊…六辛逢马虎」(=现表 ziweiyeargan.json:庚→魁丑/钺未);
// 新版「甲戊兼牛羊…庚辛逢马虎」:仅庚干改魁午/钺寅(辛两版同为午寅;乙己/丙丁/壬癸全同)。
// 两版并存源于《全集》木刻版天魁天钺诀上方小注「一本作甲戊兼牛羊,庚辛逢马虎」。
// delta 仅 2 格,代码常量承载(不建第二张 JSON;基表与 Java 孪生零动)。
// 四版=庚干归属(守牛羊丑未 vs 随辛)×魁钺马虎序(对仗恒魁前钺后:马虎=魁午钺寅/虎马=魁寅钺午);
// 其余八干四版全同。delta 常量承载,基表与 Java 孪生零动;未知档/默认档返 null 沿基表=安全降级。
export const KUIYUE_VARIANTS = {
	geng_ma_hu:     { 天魁: { 庚: '午' }, 天钺: { 庚: '寅' } },                     // 庚辛逢马虎(庚随辛午寅)
	liu_xin_hu_ma:  { 天魁: { 辛: '寅' }, 天钺: { 辛: '午' } },                     // 六辛逢虎马(辛对调,庚守丑未)
	geng_xin_hu_ma: { 天魁: { 庚: '寅', 辛: '寅' }, 天钺: { 庚: '午', 辛: '午' } }, // 庚辛逢虎马(庚辛同魁寅钺午)
};
export function placeKuiYue(starName, yearStem, variant){
	const v = KUIYUE_VARIANTS[variant];
	if(v){
		const d = v[starName];
		if(d && d[yearStem]){ return d[yearStem]; }
	}
	return null;
}
