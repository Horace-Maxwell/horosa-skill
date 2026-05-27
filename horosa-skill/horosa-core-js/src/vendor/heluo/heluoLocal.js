// 河洛理数 —— 前端本地计算（不走任何后端 / kentang）。
// 四柱来自 baziLunarLocal（星阙自己的八字）；本模块做起命(天地数→卦→元堂→后天)、起运(大限/流年)、命运篇判断、爻辞查找。
// 算法依《河洛理数》(陈抟·邵康节) 主篇逐字实现；已对算例验证：
//   甲子丁卯庚申庚辰(阳男·辰时)→先天天风姤·元堂上九；丁巳丙午壬寅辛丑(阴男)→水风井；壬子年命例 澤地萃(元堂4)→地水師(元堂1)。
import TIAOWEN from './data/heluoTiaowen.json' with { type: 'json' };

// ── 八卦（自下而上三爻 bit：1阳 0阴）──
const TRIGRAM_BITS = {
	乾: [1, 1, 1], 兌: [1, 1, 0], 離: [1, 0, 1], 震: [1, 0, 0],
	巽: [0, 1, 1], 坎: [0, 1, 0], 艮: [0, 0, 1], 坤: [0, 0, 0],
};
// 洛书数 → 八卦（5 寄中宫，另行处理）
const LUOSHU_TRIGRAM = { 1: '坎', 2: '坤', 3: '震', 4: '巽', 6: '乾', 7: '兌', 8: '艮', 9: '離' };
// 天干 → 洛书纳甲数
const GAN_NUM = { 甲: 6, 乙: 2, 丙: 8, 丁: 7, 戊: 1, 己: 9, 庚: 3, 辛: 4, 壬: 6, 癸: 2 };
// 地支 → 河图数对 [奇, 偶]
const ZHI_PAIR = {
	子: [1, 6], 亥: [1, 6], 寅: [3, 8], 卯: [3, 8], 巳: [7, 2], 午: [7, 2],
	申: [9, 4], 酉: [9, 4], 辰: [5, 10], 戌: [5, 10], 丑: [5, 10], 未: [5, 10],
};
const GAN = ['甲', '乙', '丙', '丁', '戊', '己', '庚', '辛', '壬', '癸'];
const ZHI = ['子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥'];
const YANG_ZHI = new Set(['子', '寅', '辰', '午', '申', '戌']);   // 阳支(年支定阳命)
const YANG_HOURS = ['子', '丑', '寅', '卯', '辰', '巳'];           // 上六时·阳时
const YIN_HOURS = ['午', '未', '申', '酉', '戌', '亥'];            // 下六时·阴时
// 自然象 → 八卦（复合卦名取上下两象）
const NATURAL = { 天: '乾', 地: '坤', 水: '坎', 火: '離', 雷: '震', 山: '艮', 風: '巽', 澤: '兌' };

// ── 由条文 64 卦名解析 (上卦,下卦) ↔ 卦名 ──
const NAME_TO_TRI = {};   // 卦名 → {up, low}
const TRI_TO_NAME = {};   // `${up}|${low}` → 卦名
const NAME_INDEX = {};    // 卦名 → 王弗序 1-64
(function buildGuaTables() {
	Object.keys(TIAOWEN).forEach((name) => {
		let up;
		let low;
		if (name[1] === '為') { up = name[0]; low = name[0]; }            // 纯卦 乾為天
		else { up = NATURAL[name[0]]; low = NATURAL[name[1]]; }           // 复合 上象+下象
		if (TRIGRAM_BITS[up] && TRIGRAM_BITS[low]) {
			NAME_TO_TRI[name] = { up, low };
			TRI_TO_NAME[`${up}|${low}`] = name;
			NAME_INDEX[name] = TIAOWEN[name].index;
		}
	});
}());

function guaName(up, low) { return TRI_TO_NAME[`${up}|${low}`] || ''; }
// 六爻 bit（自下而上 1-6）= 下卦三爻 + 上卦三爻
function guaLines(up, low) { return [...TRIGRAM_BITS[low], ...TRIGRAM_BITS[up]]; }
function linesToGua(lines) {
	const low = Object.keys(TRIGRAM_BITS).find((t) => TRIGRAM_BITS[t].every((b, i) => b === lines[i]));
	const up = Object.keys(TRIGRAM_BITS).find((t) => TRIGRAM_BITS[t].every((b, i) => b === lines[i + 3]));
	return { up, low, name: guaName(up, low) };
}

// ── 天数(去25)/地数(去30) 归卦数 1-9（5 表示寄中宫）──
function reduceTian(t) {
	let v = t;
	while (v > 25) v -= 25;       // 50→25
	if (v === 25) return 5;
	if (v >= 10) { const u = v % 10; return u === 0 ? v / 10 : u; }
	return v;
}
function reduceDi(d) {
	let v = d;
	while (v > 30) v -= 30;
	if (v === 30) return 3;
	if (v >= 10) { const u = v % 10; return u === 0 ? v / 10 : u; }
	return v;
}

// 5 寄中宫：按三元(民國年) + 阴阳(年干奇偶) + 男女
function wuJiGong(minguoYear, yangGan, isMale) {
	if (minguoYear <= 12) return isMale ? '艮' : '坤';        // 上元
	if (minguoYear <= 72) {                                   // 中元
		const ay = (yangGan && isMale) || (!yangGan && !isMale); // 阳男 or 阴女
		return ay ? '艮' : '坤';
	}
	return isMale ? '離' : '兌';                               // 下元
}

// ── 起元堂（动爻 1-6）──
// 阳时数本卦阳爻、阴时数阴爻；自下而上，count≤3 重数(M+M)再寄(O)，count≥4 直排(M+O)。
function yuanTang(lines, hourZhi, isMale, gua) {
	const yang = YANG_HOURS.includes(hourZhi);
	const hours = yang ? YANG_HOURS : YIN_HOURS;
	const hi = hours.indexOf(hourZhi);
	const match = yang ? 1 : 0;
	const M = [];
	const O = [];
	for (let p = 1; p <= 6; p += 1) { (lines[p - 1] === match ? M : O).push(p); }
	const k = M.length;
	if (k === 0 || k === 6) return yuanTangPure(gua, hourZhi, isMale);   // 乾/坤 纯卦
	const slots = (k <= 3 ? [...M, ...M, ...O] : [...M, ...O]).slice(0, 6);
	return slots[hi] || slots[slots.length - 1];
}

// 乾(纯阳)/坤(纯阴) 元堂：男女 + 节气半年（阳令 冬至后~夏至前；阴令 夏至后~冬至前）。
// 配时表（自下而上）：爻1 子卯, 爻2 丑辰, 爻3 寅巳, 爻4 午酉, 爻5 未戌, 爻6 申亥。
const PURE_HOUR_TO_YAO = { 子: 1, 卯: 1, 丑: 2, 辰: 2, 寅: 3, 巳: 3, 午: 4, 酉: 4, 未: 5, 戌: 5, 申: 6, 亥: 6 };
function yuanTangPure(gua, hourZhi, isMale) {
	const base = PURE_HOUR_TO_YAO[hourZhi] || 1;
	const yangLing = gua && gua.yangLing;   // true=冬至后夏至前
	let reverse = false;
	if (gua && gua.up === '乾') reverse = !isMale && yangLing;        // 乾：女命阳令 自上而下
	else reverse = isMale && !yangLing;                              // 坤：男命阴令 自上而下
	return reverse ? 7 - base : base;
}

// 翻元堂爻 → 后天卦（三至尊卦 坎为水/水雷屯/水山蹇 另有君位不易，见 transformHoutian）
function flipLine(lines, pos) { const l = lines.slice(); l[pos - 1] = l[pos - 1] ? 0 : 1; return l; }

export function nodeFromYao(lines, pos) { return flipLine(lines, pos); }

// ── 起命 ──
export function calculate({ fourPillars, gender = '男', hourZhi, birthYear, monthZhi, monthYangLing }) {
	const [yG, yZ] = splitGz(fourPillars.year);
	const pillars = ['year', 'month', 'day', 'hour'].map((k) => fourPillars[k]);
	let tian = 0;
	let di = 0;
	pillars.forEach((gz) => {
		const g = gz[0];
		const z = gz[1];
		const gn = GAN_NUM[g];
		if (gn % 2 === 1) tian += gn; else di += gn;
		const [odd, even] = ZHI_PAIR[z] || [0, 0];
		tian += odd; di += even;
	});
	const isMale = !(gender === '女' || gender === 'F' || gender === 'female' || gender === 0);
	const minguo = (birthYear || 0) - 1911;
	const yangGan = GAN.indexOf(yG) % 2 === 0;          // 甲丙戊庚壬=阳
	let tNum = reduceTian(tian);
	let dNum = reduceDi(di);
	const tGua = tNum === 5 ? wuJiGong(minguo, yangGan, isMale) : LUOSHU_TRIGRAM[tNum];
	const dGua = dNum === 5 ? wuJiGong(minguo, yangGan, isMale) : LUOSHU_TRIGRAM[dNum];

	// 相盪：阳命=子寅辰午申戌年；阳男阴女 天上地下，阴男阳女 天下地上
	const yangMing = YANG_ZHI.has(yZ);
	const tianTop = (isMale && yangMing) || (!isMale && !yangMing);   // 阳男 or 阴女 → 天数在上
	const up = tianTop ? tGua : dGua;
	const low = tianTop ? dGua : tGua;
	const xianLines = guaLines(up, low);
	const xianName = guaName(up, low);

	// 节气半年：阳令 冬至后~夏至前(子月~巳月 / 十一月~四月)；阴令 夏至后~冬至前。
	const yangLing = monthYangLing !== undefined
		? monthYangLing
		: ['子', '丑', '寅', '卯', '辰', '巳'].includes(monthZhi);
	const xianGuaCtx = { up, low, yangLing };

	const yuan = yuanTang(xianLines, hourZhi, isMale, xianGuaCtx);
	const { name: houName, lines: houLines, yuan: houYuan } = transformHoutian(xianName, xianLines, yuan, yangLing);

	return {
		gender: isMale ? '男' : '女',
		tian, di, tianNum: tNum, diNum: dNum, tianGua: tGua, diGua: dGua, tianTop,
		yangMing, yangGan, yangLing, hourZhi,
		xian: { name: xianName, up, low, lines: xianLines, yuan },
		hou: { name: houName, lines: houLines, yuan: houYuan },
	};
}

// 移外卦入内、内卦出外（上下三爻互换）
function swapTrigrams(l) { return [l[3], l[4], l[5], l[0], l[1], l[2]]; }
// 三至尊卦：坎為水/水雷屯/水山蹇。九五(爻5)阴令、上六(爻6)阳令 →「变而不易」(只翻爻、不互换上下卦、元堂位不动)。
// 阳令=冬至后~夏至前(子丑寅卯辰巳/十一~四月)；阴令=夏至后~冬至前(午~亥/五~十月)。
const ZHI_ZUN = new Set(['坎為水', '水雷屯', '水山蹇']);
export function transformHoutian(xianName, xianLines, yuan, yangLing) {
	const flipped = flipLine(xianLines, yuan);            // ① 元堂爻 阴阳互变
	if (ZHI_ZUN.has(xianName)) {
		const buYi = (yuan === 5 && !yangLing) || (yuan === 6 && yangLing); // 九五阴令 / 上六阳令
		if (buYi) {
			const { name } = linesToGua(flipped);        // 变而不易：不互换上下卦、元堂位不动
			return { name, lines: flipped, yuan };
		}
	}
	const houLines = swapTrigrams(flipped);              // ② 移外卦入内、内卦出外
	const houYuan = yuan > 3 ? yuan - 3 : yuan + 3;      // 元堂随上下卦互换而易位
	const { name } = linesToGua(houLines);
	return { name, lines: houLines, yuan: houYuan };
}

function splitGz(gz) { return [gz[0], gz[1]]; }

// ── 起运 ──
function ying(p) { return p <= 3 ? p + 3 : p - 3; }   // 应爻：1↔4 2↔5 3↔6
export function yearGanzhi(year) {
	return GAN[((year - 4) % 10 + 10) % 10] + ZHI[((year - 4) % 12 + 12) % 12];
}
function isYangYear(year) { return ((year - 4) % 10 + 10) % 10 % 2 === 0; } // 年干 甲丙戊庚壬

// 大限：先天卦元堂起、自下往上(绕行六爻)、阳爻9阴爻6年；行完先天接后天。虚岁(生即1)。
export function daYun(xian, hou, birthYear = 0) {
	const segOf = (g, startAge) => {
		let age = startAge;
		const segs = [];
		for (let i = 0; i < 6; i += 1) {
			const pos = ((g.yuan - 1 + i) % 6) + 1;
			const yang = g.lines[pos - 1] === 1;
			const yrs = yang ? 9 : 6;
			segs.push({
				gua: g.name, lines: g.lines.slice(), pos, yang, years: yrs,
				ageStart: age, ageEnd: age + yrs - 1,
				yearStart: birthYear ? birthYear + age - 1 : null,
			});
			age += yrs;
		}
		return { segs, endAge: age - 1 };
	};
	const a = segOf(xian, 1);
	const b = segOf(hou, a.endAge + 1);
	return { xian: a.segs, hou: b.segs, all: [...a.segs, ...b.segs], xianEndAge: a.endAge, endAge: b.endAge };
}

// 流年：在某大限爻内逐年起值年卦。每年在「上一年的卦」上变一爻——動爻自上一年動爻「往上一爻」(到上爻则回初爻)累变。
// 阳爻管9年：阳年首年本卦不变(動爻=元堂)、阴年首年先变元堂；第2、3年连变两次应爻(取上一年動爻之应)；第4年起从上一年動爻往上一爻累变。
// 阴爻管6年：首年先变元堂(不分阴阳年、无应爻步)，其后逐年往上一爻累变。每年返回 {age,year,ganzhi,gua,pos(動爻)}。
export function liuNian(seg, birthYear = 0) {
	const g = NAME_TO_TRI[seg.gua];
	if (!g) return [];
	let lines = guaLines(g.up, g.low);
	const out = [];
	const yearOf = (i) => (birthYear ? birthYear + seg.ageStart - 1 + i : null);
	const push = (i, ln, pos) => {
		const y = yearOf(i);
		out.push({
			age: seg.ageStart + i, year: y, ganzhi: y ? yearGanzhi(y) : '',
			gua: linesToGua(ln).name, lines: ln.slice(), pos,
		});
	};
	const up1 = (p) => (p % 6) + 1;   // 往上一爻：上爻(6)→初爻(1)
	if (seg.yang) {
		const firstYangYear = birthYear ? isYangYear(yearOf(0)) : true;
		if (!firstYangYear) { lines = flipLine(lines, seg.pos); }   // 阴年首年变元堂，阳年首年不变
		push(0, lines, seg.pos);
		const p1 = ying(seg.pos); lines = flipLine(lines, p1); push(1, lines, p1);   // 第2年变应爻
		const p2 = ying(p1); lines = flipLine(lines, p2); push(2, lines, p2);        // 第3年再变(上一年動爻之)应爻
		let prev = p2;
		for (let i = 3; i < seg.years; i += 1) { prev = up1(prev); lines = flipLine(lines, prev); push(i, lines, prev); }
	} else {
		lines = flipLine(lines, seg.pos); push(0, lines, seg.pos);   // 首年变元堂
		let prev = seg.pos;
		for (let i = 1; i < seg.years; i += 1) { prev = up1(prev); lines = flipLine(lines, prev); push(i, lines, prev); }
	}
	return out.slice(0, seg.years);
}

// 流月卦：以流年卦+动爻为本。阳月(正三五七九十一)自元堂后一爻起、逐奇月往上累变；
// 阴月(二四六八十十二)取前一奇月所变爻之应爻、在该奇月卦上变。返回 12 月。
const YUE_LABEL = ['正', '二', '三', '四', '五', '六', '七', '八', '九', '十', '十一', '十二'];
const YUE_ZHI = ['寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥', '子', '丑'];
export function liuYue(yearLines, yuanPos) {
	const out = [];
	let running = yearLines.slice();
	let lastOddLines = running.slice();
	let lastOddChanged = yuanPos;
	for (let mi = 1; mi <= 12; mi += 1) {
		let lines;
		let pos;
		if (mi % 2 === 1) {
			const step = (mi + 1) / 2;                       // 正1 三2 五3 … 十一6
			pos = ((yuanPos - 1 + step) % 6) + 1;
			running = flipLine(running, pos);
			lastOddLines = running.slice();
			lastOddChanged = pos;
			lines = running.slice();
		} else {
			pos = ying(lastOddChanged);                      // 应爻
			lines = flipLine(lastOddLines, pos);
		}
		out.push({ month: mi, label: YUE_LABEL[mi - 1], zhi: YUE_ZHI[mi - 1], gua: linesToGua(lines).name, lines, pos });
	}
	return out;
}

// 流日卦：以月卦为主、元堂爻不动；自后一爻起逐爻在月卦上变(非累变)得 5 个日卦，每卦管 6 日；
// 而每卦所辖 6 日内动爻自初爻行至上爻(一日一爻)。返回 30 日，每日 {dayInMonth, 卦(block), pos(动爻 1-6)}。
export function liuRi(monthLines, yuanPos) {
	const out = [];
	for (let b = 0; b < 5; b += 1) {
		const flipPos = ((yuanPos - 1 + b + 1) % 6) + 1;    // m+1,m+2,…m+5（跳过元堂 m）
		const lines = flipLine(monthLines, flipPos);
		const name = linesToGua(lines).name;
		for (let d = 1; d <= 6; d += 1) {
			out.push({ block: b + 1, dayInMonth: b * 6 + d, gua: name, lines, pos: d });
		}
	}
	return out;
}

// ── 命运篇 判断层 ──
// 元气/反元气：年干→天元气卦、年支→地元气卦（《河洛理数》元气总表）。
const GAN_YUAN = { 甲: '乾', 壬: '乾', 乙: '坤', 癸: '坤', 庚: '震', 辛: '巽', 戊: '坎', 己: '離', 丙: '艮', 丁: '兌' };
const ZHI_YUAN = { 戌: '乾', 亥: '乾', 未: '坤', 申: '坤', 卯: '震', 辰: '巽', 巳: '巽', 子: '坎', 午: '離', 丑: '艮', 寅: '艮', 酉: '兌' };
const GAN_FAN = { 甲: '坤', 壬: '坤', 乙: '乾', 癸: '乾', 庚: '巽', 辛: '震', 戊: '離', 己: '坎', 丙: '兌', 丁: '艮' };
const ZHI_FAN = { 戌: '坤', 亥: '坤', 未: '乾', 申: '乾', 卯: '巽', 辰: '震', 巳: '震', 子: '離', 午: '坎', 丑: '兌', 寅: '兌', 酉: '艮' };
// 化工/反化工 —— 准确法按月柱节气(中气四象限)取卦：
//   春分~夏至前=震/反巽，夏至~秋分前=離/反坎，秋分~冬至前=兌/反艮，冬至~春分前=坎/反離；
//   四立(立春夏秋冬)前十八日内 加 坤艮/反乾兌(土用，需命卦含之方应)。
// 由 solarTermHuagong() 据真实节气算；下面 MONTH_HG 仅作无节气信息时(单测)的月支近似回退。
const QUARTER_HG = { 震: { hg: '震', fh: '巽' }, 離: { hg: '離', fh: '坎' }, 兌: { hg: '兌', fh: '艮' }, 坎: { hg: '坎', fh: '離' } };
// 节气(节/气名)→所属中气象限化工卦（繁简兼容）
const JIEQI_QUARTER = {
	春分: '震', 清明: '震', 穀雨: '震', 谷雨: '震', 立夏: '震', 小滿: '震', 小满: '震', 芒種: '震', 芒种: '震',
	夏至: '離', 小暑: '離', 大暑: '離', 立秋: '離', 處暑: '離', 处暑: '離', 白露: '離',
	秋分: '兌', 寒露: '兌', 霜降: '兌', 立冬: '兌', 小雪: '兌', 大雪: '兌',
	冬至: '坎', 小寒: '坎', 大寒: '坎', 立春: '坎', 雨水: '坎', 驚蟄: '坎', 惊蛰: '坎',
};
// prevJieQiName=出生当下所处节气名；tuyong=是否在四立前18日土用内。返回 {hg:[],fh:[]} 化工/反化工候选。
export function solarTermHuagong(prevJieQiName, tuyong) {
	const q = JIEQI_QUARTER[prevJieQiName] || null;
	const base = (q && QUARTER_HG[q]) || { hg: '', fh: '' };
	const hg = base.hg ? [base.hg] : [];
	const fh = base.fh ? [base.fh] : [];
	if (tuyong) { hg.push('坤', '艮'); fh.push('乾', '兌'); }
	return { hg, fh, quarter: q, tuyong: !!tuyong };
}
const MONTH_HG = { 卯: ['震'], 辰: ['震'], 午: ['離'], 未: ['離'], 酉: ['兌'], 戌: ['兌'], 子: ['坎'], 丑: ['坎'], 寅: ['坤', '艮'], 巳: ['坤', '艮'], 申: ['坤', '艮'], 亥: ['坤', '艮'] };
const MONTH_FH = { 卯: ['巽'], 辰: ['巽'], 午: ['坎'], 未: ['坎'], 酉: ['艮'], 戌: ['艮'], 子: ['離'], 丑: ['離'], 寅: ['乾', '兌'], 巳: ['乾', '兌'], 申: ['乾', '兌'], 亥: ['乾', '兌'] };
// 八卦纳甲（得势）：trigram → 干支集
const NAJIA = {
	乾: ['壬戌', '壬申', '壬午', '甲辰', '甲寅', '甲子'], 坎: ['戊子', '戊戌', '戊申', '戊午', '戊辰', '戊寅'],
	艮: ['丙寅', '丙子', '丙戌', '丙申', '丙午', '丙辰'], 震: ['庚戌', '庚申', '庚午', '庚辰', '庚寅', '庚子'],
	巽: ['辛卯', '辛巳', '辛未', '辛酉', '辛亥', '辛丑'], 離: ['己巳', '己未', '己酉', '己亥', '己丑', '己卯'],
	坤: ['癸酉', '癸亥', '癸丑', '乙卯', '乙巳', '乙未'], 兌: ['丁未', '丁酉', '丁亥', '丁丑', '丁卯', '丁巳'],
};
// 得时：生月(节气)→卦月之卦（短名）
const MONTH_GUA = {
	寅: ['大有', '同人', '泰', '既濟', '咸', '恆', '蠱', '漸'], 卯: ['大壯', '晉', '小過', '大過', '革', '訟'],
	辰: ['井', '睽', '夬', '履', '渙'], 巳: ['乾', '艮', '巽', '離'], 午: ['姤', '旅', '困', '豫'],
	未: ['家人', '萃', '遯', '屯'], 申: ['節', '比', '隨', '益', '損', '師', '歸妹', '否', '未濟'],
	酉: ['中孚', '觀', '明夷', '无妄', '升', '蹇', '蒙', '需', '頤'], 戌: ['豐', '謙', '噬嗑', '剝'],
	亥: ['坎', '坤', '兌'], 子: ['小畜', '賁', '復'], 丑: ['大畜', '震', '解', '鼎', '臨'],
};
// 得体：日干→纳甲卦（present 则得体）
const DAY_TI = { 甲: '乾', 乙: '坤', 丙: '艮', 丁: '兌', 戊: '坎', 己: '離', 庚: '震', 辛: '巽', 壬: '乾', 癸: '坤' };

function trigramOf(b) { return Object.keys(TRIGRAM_BITS).find((t) => TRIGRAM_BITS[t].every((x, i) => x === b[i])); }
function sanCai(lines) { return [[0, 1, 2], [1, 2, 3], [2, 3, 4], [3, 4, 5]].map((ix) => trigramOf(ix.map((i) => lines[i]))); }
function shortName(name) { return name[1] === '為' ? name[0] : name.slice(2); }

// 某卦(六爻)含哪些目标三才卦：传 trigram 集，返回命中的。供逐段大限/流年卦气分析用。
export function guaSanCaiSet(lines) { return new Set(sanCai(lines)); }

// chart = calculate() 的返回；monthZhi 八字月支(回退用)；hgOverride={hg,fh} 准确节气化工(优先)。
// 返回各卦气判断 + 葉/不葉 + 元堂爻位。
export function judge(chart, fourPillars, monthZhi, hgOverride) {
	const yG = fourPillars.year[0];
	const yZ = fourPillars.year[1];
	const dG = fourPillars.day[0];
	const triSet = new Set([...sanCai(chart.xian.lines), ...sanCai(chart.hou.lines)]);   // 四三才卦(先后天)
	const baseTris = new Set([chart.xian.up, chart.xian.low, chart.hou.up, chart.hou.low]); // 基本上下卦
	const has = (t) => triSet.has(t);
	const mk = (gua) => ({ gua, present: has(gua) });

	const yuan = { tian: mk(GAN_YUAN[yG]), di: mk(ZHI_YUAN[yZ]) };
	const fanYuan = { tian: mk(GAN_FAN[yG]), di: mk(ZHI_FAN[yZ]) };
	const hgList = (hgOverride && hgOverride.hg) ? hgOverride.hg : (MONTH_HG[monthZhi] || []);
	const huagong = { guas: hgList, present: hgList.filter(has) };
	const fhList = (hgOverride && hgOverride.fh) ? hgOverride.fh : (MONTH_FH[monthZhi] || []);
	const fanhua = { guas: fhList, present: fhList.filter(has) };
	const deShi = [...baseTris].some((t) => (NAJIA[t] || []).includes(fourPillars.year)); // 得势(纳甲)
	const sn = [shortName(chart.xian.name), shortName(chart.hou.name)];
	const monthList = MONTH_GUA[monthZhi] || [];
	const deTime = sn.some((s) => monthList.includes(s));                                 // 得时(卦月)
	const deTi = mk(DAY_TI[dG]);                                                          // 得体(日干纳甲)
	// 葉/不葉：命卦藏任一元气或化工
	const xie = yuan.tian.present || yuan.di.present || huagong.present.length > 0;
	// 阴阳二数
	const erShu = {
		tian: chart.tian, di: chart.di,
		tianState: chart.tian > 25 ? '过' : (chart.tian < 25 ? '不足' : '得中'),
		diState: chart.di > 30 ? '过' : (chart.di < 30 ? '不足' : '得中'),
	};
	// 元堂爻位（取先天卦元堂）
	const yPos = chart.xian.yuan;
	const yYang = chart.xian.lines[yPos - 1] === 1;
	const yingPos = ying(yPos);
	const yuanTangInfo = {
		pos: yPos, yang: yYang,
		dangWei: (yPos % 2 === 1) === yYang,                                  // 当位：阳爻居奇位/阴爻居偶位
		youYing: chart.xian.lines[yingPos - 1] !== chart.xian.lines[yPos - 1], // 有应：与应爻异性相应
		heLi: chart.yangLing === yYang,                                        // 合理：阳月坐阳爻(顺气)
	};
	return { yuan, fanYuan, huagong, fanhua, deSheng: deShi, deTime, deTi, xie, erShu, yuanTang: yuanTangInfo };
}

// 某一时段卦(lines)所含的元气/化工等（命卦层 jg 给定各卦身份）→ 逐段表格用。
export function periodEnergies(lines, jg) {
	const s = new Set(sanCai(lines));
	const inSet = (g) => !!g && s.has(g);
	const list = (arr) => (arr || []).filter(inSet);
	const tags = [];
	if (inSet(jg.yuan.tian.gua)) tags.push('天元');
	if (inSet(jg.yuan.di.gua)) tags.push('地元');
	list(jg.huagong.guas).length && tags.push('化工');
	if (inSet(jg.fanYuan.tian.gua)) tags.push('反天元');
	if (inSet(jg.fanYuan.di.gua)) tags.push('反地元');
	list(jg.fanhua.guas).length && tags.push('反化');
	return {
		tianYuan: inSet(jg.yuan.tian.gua), diYuan: inSet(jg.yuan.di.gua),
		fanTian: inSet(jg.fanYuan.tian.gua), fanDi: inSet(jg.fanYuan.di.gua),
		huagong: list(jg.huagong.guas), fanhua: list(jg.fanhua.guas), tags,
	};
}

// ── Phase 1 起卦盘补全 ──
// 纳甲六亲世应在组件层用 六爻/统摄法 的 Gua64 计算（见 HeLuoMain.najia，按六爻 value 匹配）；
// 本纯函数模块不引 Gua64（其模块链含 antd/umi），只暴露按 value 匹配所需的 guaLines/linesToGua。
// 值月消息卦（12 辟卦）
const XIAOXI_GUA = { 子: '地雷復', 丑: '地澤臨', 寅: '地天泰', 卯: '雷天大壯', 辰: '澤天夬', 巳: '乾為天', 午: '天風姤', 未: '天山遯', 申: '天地否', 酉: '風地觀', 戌: '山地剝', 亥: '坤為地' };
const MONTH_NUM = { 寅: '正', 卯: '二', 辰: '三', 巳: '四', 午: '五', 未: '六', 申: '七', 酉: '八', 戌: '九', 亥: '十', 子: '十一', 丑: '十二' };
export function monthXiaoxi(monthZhi) { return { gua: XIAOXI_GUA[monthZhi] || '', monthLabel: MONTH_NUM[monthZhi] || '' }; }
// 覆卦=整体转180°(综,1↔6/2↔5/3↔4)；互卦=爻234为下卦、爻345为上卦；错卦=六爻全变(旁通)
function cuoLines(l) { return l.map((b) => (b ? 0 : 1)); }
export function fuLines(l) { return l.slice().reverse(); }                          // 覆卦(综)
export function huLines(l) { return [l[1], l[2], l[3], l[2], l[3], l[4]]; }         // 互卦(中爻)
export function duiGua(name) {
	const t = NAME_TO_TRI[name];
	if (!t) return { fu: '', hu: '', cuo: '' };
	const l = guaLines(t.up, t.low);
	return { fu: linesToGua(fuLines(l)).name, hu: linesToGua(huLines(l)).name, cuo: linesToGua(cuoLines(l)).name };
}
// 某时段卦 与 先天/后天命卦 的对体关系：正對(错=六爻全变) / 反對(综=覆/转180°) / 互。
// 参考董鴻煦盘："本卦正對後天卦" 等。
export function guaRelations(lines, chart) {
	const out = [];
	const eq = (a, b) => Array.isArray(a) && Array.isArray(b) && a.length === b.length && a.every((v, i) => v === b[i]);
	[['先天', chart.xian.lines], ['后天', chart.hou.lines]].forEach(([label, base]) => {
		if (!base) return;
		if (eq(lines, base)) out.push(`本卦即${label}卦`);
		else if (eq(lines, cuoLines(base))) out.push(`本卦正對${label}卦`);
		else if (eq(lines, fuLines(base))) out.push(`本卦反對${label}卦`);
		else if (eq(lines, huLines(base))) out.push(`本卦为${label}卦之互`);
	});
	return out;
}

// 某时段卦的「理数」：本卦(含)/互卦(藏)/覆卦(覆) 各取四三才卦，标出所含 元气/化工(正/反) 角色。
// 参考董鴻煦盘：含艮為天元、藏乾為地元、覆兌為化工、含艮反化工 等。
export function periodLiShu(lines, jg) {
	const roles = [
		['天元', jg.yuan.tian.gua, false], ['地元', jg.yuan.di.gua, false],
		['天元', jg.fanYuan.tian.gua, true], ['地元', jg.fanYuan.di.gua, true],
		...(jg.huagong.guas || []).map((g) => ['化工', g, false]),
		...(jg.fanhua.guas || []).map((g) => ['化工', g, true]),
	];
	const sources = [['含', lines], ['藏', huLines(lines)], ['覆', fuLines(lines)]];
	const items = [];
	const seen = new Set();
	sources.forEach(([label, ln]) => {
		const set = new Set(sanCai(ln));
		roles.forEach(([role, gua, fan]) => {
			if (!gua || !set.has(gua)) return;
			const text = `${label}${gua}${fan ? '反' : '為'}${role}`;
			if (seen.has(text)) return;
			seen.add(text);
			items.push({ label, gua, role, fan, text });
		});
	});
	return items;
}

// 先後天八卦變化之義：元堂所在三画卦 + 变上/中/下
export function bianYiYi(xian) {
	const inUp = xian.yuan >= 4;
	const tri = inUp ? xian.up : xian.low;
	const pos = inUp ? xian.yuan - 3 : xian.yuan;
	return `${tri}變${['下', '中', '上'][pos - 1]}`;
}
// 簡斷：居阳/阴爻 + 上/下卦 + 天数足否 + 值阳/阴令
export function jianDuan(chart) {
	const yPos = chart.xian.yuan;
	const yYang = chart.xian.lines[yPos - 1] === 1;
	return `居${yYang ? '陽' : '陰'}爻，在${yPos >= 4 ? '上' : '下'}卦，天數${chart.tian >= 25 ? '足' : '不足'}，值${chart.yangLing ? '陽' : '陰'}令`;
}
// 数理得中：基数(天25/地30)~危线(天40/地50) 得中；≥危线 太过；<基数 不足(至弱 天<9/地<13)
function shuState(num, base, danger, weak) {
	if (num >= danger) return '太過';
	if (num < weak) return '至弱';
	if (num < base) return '不足';
	return '得中';
}
const SEASON = { 寅: '春', 卯: '春', 辰: '春', 巳: '夏', 午: '夏', 未: '夏', 申: '秋', 酉: '秋', 戌: '秋', 亥: '冬', 子: '冬', 丑: '冬' };
const GUA_WUXING = { 乾: '金', 兌: '金', 離: '火', 震: '木', 巽: '木', 坎: '水', 艮: '土', 坤: '土' };
// 汇总起卦盘所有补充元素。opts: { season, sanhou, nayin } 由 HeLuoMain 据节气/八字提供。
export function chartExtras(chart, fourPillars, monthZhi, jg, opts = {}) {
	const shuLi = {
		tian: shuState(chart.tian, 25, 40, 9),
		di: shuState(chart.di, 30, 50, 13),
	};
	const season = opts.season || SEASON[monthZhi] || '';
	// 纳音居本位：年纳音五行 与 天/地元气卦五行 同
	const nayin = opts.nayin || '';
	const benWei = [];
	if (nayin && jg) {
		if (GUA_WUXING[jg.yuan.tian.gua] === nayin) benWei.push('天元居本位');
		if (GUA_WUXING[jg.yuan.di.gua] === nayin) benWei.push('地元居本位');
	}
	return {
		shuLi, season,
		jianDuan: jianDuan(chart),
		xiaoxi: monthXiaoxi(monthZhi),
		bianYi: bianYiYi(chart.xian),
		duiXian: duiGua(chart.xian.name),
		duiHou: duiGua(chart.hou.name),
		nayin, benWei, sanhou: opts.sanhou || '',
	};
}

// 爻辞查找：本卦元堂(动爻)之爻辞
export function yaoText(guaName2, pos) {
	const g = TIAOWEN[guaName2];
	if (!g || !g.yao[pos]) return null;
	return g.yao[pos];
}
export function guaInfo(guaName2) { return TIAOWEN[guaName2] || null; }

const YAO_LABEL = ['初', '二', '三', '四', '五', '上'];
export function yaoName(lines, pos) {
	const yang = lines[pos - 1] === 1;
	const num = pos === 1 ? '初' : (pos === 6 ? '上' : YAO_LABEL[pos - 1]);
	return pos === 1 ? `初${yang ? '九' : '六'}` : (pos === 6 ? `上${yang ? '九' : '六'}` : `${yang ? '九' : '六'}${num}`);
}

export function buildSnapshotText(chart, jg, dy) {
	if (!chart) return '';
	const lines = [];
	lines.push('[起命]');
	lines.push(`天数${chart.tian}→${chart.tianGua}　地数${chart.di}→${chart.diGua}`);
	lines.push(`先天卦：${chart.xian.name}　元堂 ${yaoName(chart.xian.lines, chart.xian.yuan)}`);
	lines.push(`后天卦：${chart.hou.name}　元堂 ${yaoName(chart.hou.lines, chart.hou.yuan)}`);
	const xt = yaoText(chart.xian.name, chart.xian.yuan);
	const ht = yaoText(chart.hou.name, chart.hou.yuan);
	if (xt) { lines.push(''); lines.push(`[先天·${chart.xian.name} 元堂爻辞]`); lines.push(`摘要：${xt.detail}`); lines.push(`诗歌：${xt.shige}`); }
	if (ht) { lines.push(''); lines.push(`[后天·${chart.hou.name} 元堂爻辞]`); lines.push(`摘要：${ht.detail}`); lines.push(`诗歌：${ht.shige}`); }
	if (jg) {
		lines.push('');
		lines.push('[命运篇]');
		lines.push(`天元气 ${jg.yuan.tian.gua}${jg.yuan.tian.present ? '(有)' : '(无)'}　地元气 ${jg.yuan.di.gua}${jg.yuan.di.present ? '(有)' : '(无)'}`);
		lines.push(`化工 ${jg.huagong.guas.join('/')}${jg.huagong.present.length ? `(有:${jg.huagong.present.join('')})` : '(无)'}　${jg.xie ? '葉' : '不葉'}`);
		lines.push(`得势${jg.deSheng ? '有' : '无'}　得时${jg.deTime ? '有' : '无'}　得体 ${jg.deTi.gua}${jg.deTi.present ? '(有)' : '(无)'}`);
		lines.push(`二数：天${jg.erShu.tian}(${jg.erShu.tianState}) 地${jg.erShu.di}(${jg.erShu.diState})`);
		lines.push(`元堂：${jg.yuanTang.dangWei ? '当位' : '不当位'}　${jg.yuanTang.youYing ? '有应' : '无应'}　${jg.yuanTang.heLi ? '顺气' : '逆气'}`);
	}
	if (dy && dy.all) {
		lines.push('');
		lines.push('[大限·岁运]');
		dy.all.forEach((s) => { lines.push(`${s.ageStart}-${s.ageEnd}岁 ${s.gua} ${yaoName(s.lines, s.pos)}（${s.yang ? '阳9' : '阴6'}）`); });
	}
	return lines.join('\n');
}

export { TRI_TO_NAME, NAME_TO_TRI, NAME_INDEX, guaName, guaLines, linesToGua, sanCai, shortName, GAN, ZHI, TIAOWEN };
export default calculate;
