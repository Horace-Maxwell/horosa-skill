// 铁板神数「可复原框架层」纯前端确定性引擎(零后端·零随机)。
// 只实现可由公开算例完整复原的框架件(存疑/无公开出处的秘传数系一律不做、不臆造):
//   太玄配数 · 八刻天干 · 四柱配六亲 · 八卦滚法(有完整算例)
//   · 九十六局 · 南北派 · 借用子系统结构 · 大定数 129600。
// 🔒 秘传层(乾坤甲流度全表/斗宫12刻/太玄起数调整数)与 ❌ 存疑秘数(×79/×314/+7130/+7600/+96)
//   一律不实现、不硬编:精确条文号仍由后端 kinastro 引擎提供,本层只呈现公开结构与可复原卦象。
//
// 八卦滚 §5.5.3 全例已逐卦验证(基本卦 天地否/数序 4410/下元乙丑 →
//   风山渐·天火同人·雷泽归妹·地水师·山天大畜·火风鼎·泽地萃·水雷屯),见 golden 测试。

// ── 八卦(先天序位)与卦爻(自下而上 6 位, 1=阳 0=阴) ──
const TRI_BITS = { 乾: [1, 1, 1], 兑: [1, 1, 0], 離: [1, 0, 1], 震: [1, 0, 0], 巽: [0, 1, 1], 坎: [0, 1, 0], 艮: [0, 0, 1], 坤: [0, 0, 0] };
const BITS_TRI = {};
Object.keys(TRI_BITS).forEach((t) => { BITS_TRI[TRI_BITS[t].join('')] = t; });
// 简繁兼容:离/離 統一走 離 键
const TRI_ALIAS = { 离: '離' };

// 先天八卦数(§4.3):乾1兑2离3震4巽5坎6艮7坤8
const XIANTIAN_NUM = { 乾: 1, 兑: 2, 離: 3, 震: 4, 巽: 5, 坎: 6, 艮: 7, 坤: 8 };
// 后天八卦数=洛书数(§4.3):坎1坤2震3巽4(中5)乾6兑7艮8离9
const HOUTIAN_NUM = { 坎: 1, 坤: 2, 震: 3, 巽: 4, 乾: 6, 兑: 7, 艮: 8, 離: 9 };
// 卦自然象(拼 64 卦全名用)
const TRI_IMAGE = { 乾: '天', 兑: '澤', 離: '火', 震: '雷', 巽: '風', 坎: '水', 艮: '山', 坤: '地' };

// ── 64 卦全名表(上卦|下卦 → 全名)。公有《易经》标准命名。 ──
const GUA64 = {
	'乾|乾': '乾為天', '乾|兑': '天澤履', '乾|離': '天火同人', '乾|震': '天雷無妄', '乾|巽': '天風姤', '乾|坎': '天水訟', '乾|艮': '天山遯', '乾|坤': '天地否',
	'兑|乾': '澤天夬', '兑|兑': '兑為澤', '兑|離': '澤火革', '兑|震': '澤雷隨', '兑|巽': '澤風大過', '兑|坎': '澤水困', '兑|艮': '澤山咸', '兑|坤': '澤地萃',
	'離|乾': '火天大有', '離|兑': '火澤睽', '離|離': '離為火', '離|震': '火雷噬嗑', '離|巽': '火風鼎', '離|坎': '火水未濟', '離|艮': '火山旅', '離|坤': '火地晉',
	'震|乾': '雷天大壯', '震|兑': '雷澤歸妹', '震|離': '雷火豐', '震|震': '震為雷', '震|巽': '雷風恆', '震|坎': '雷水解', '震|艮': '雷山小過', '震|坤': '雷地豫',
	'巽|乾': '風天小畜', '巽|兑': '風澤中孚', '巽|離': '風火家人', '巽|震': '風雷益', '巽|巽': '巽為風', '巽|坎': '風水渙', '巽|艮': '風山漸', '巽|坤': '風地觀',
	'坎|乾': '水天需', '坎|兑': '水澤節', '坎|離': '水火既濟', '坎|震': '水雷屯', '坎|巽': '水風井', '坎|坎': '坎為水', '坎|艮': '水山蹇', '坎|坤': '水地比',
	'艮|乾': '山天大畜', '艮|兑': '山澤損', '艮|離': '山火賁', '艮|震': '山雷頤', '艮|巽': '山風蠱', '艮|坎': '山水蒙', '艮|艮': '艮為山', '艮|坤': '山地剝',
	'坤|乾': '地天泰', '坤|兑': '地澤臨', '坤|離': '地火明夷', '坤|震': '地雷復', '坤|巽': '地風升', '坤|坎': '地水師', '坤|艮': '地山謙', '坤|坤': '坤為地',
};

// 干支(简繁兼容)
const GAN = ['甲', '乙', '丙', '丁', '戊', '己', '庚', '辛', '壬', '癸'];
const ZHI = ['子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥'];

// ── §4.1-A 太玄数配数:天干地支共用同一数(相合干支同数);巳亥=4 无对应天干 ──
const TAIXUAN_GAN = { 甲: 9, 己: 9, 乙: 8, 庚: 8, 丙: 7, 辛: 7, 丁: 6, 壬: 6, 戊: 5, 癸: 5 };
const TAIXUAN_ZHI = { 子: 9, 午: 9, 丑: 8, 未: 8, 寅: 7, 申: 7, 卯: 6, 酉: 6, 辰: 5, 戌: 5, 巳: 4, 亥: 4 };

// ── §4.7 八刻配天干:初刻甲…八刻辛(0-120′ 八段, 每刻 15′) ──
const EIGHT_KE_GAN = ['甲', '乙', '丙', '丁', '戊', '己', '庚', '辛'];

// ── §4.2/§4.8 地支生成数(考刻六亲用):子1丑10寅3卯8辰5巳7午2未10申9酉4戌5亥6 ──
const ZHI_SHENGCHENG = { 子: 1, 丑: 10, 寅: 3, 卯: 8, 辰: 5, 巳: 7, 午: 2, 未: 10, 申: 9, 酉: 4, 戌: 5, 亥: 6 };
const SHENGXIAO = { 子: '鼠', 丑: '牛', 寅: '虎', 卯: '兔', 辰: '龍', 巳: '蛇', 午: '馬', 未: '羊', 申: '猴', 酉: '雞', 戌: '狗', 亥: '豬' };

// ── §5.4.2 四柱配六亲:年→父母 月→兄弟 日→夫妻 时→子女;天干(乾)主父·地支(坤)主母 ──
const PILLAR_LIUQIN = [
	{ pillar: 'year', label: '年柱', liuqin: '父母', note: '生肖·存殁·出身' },
	{ pillar: 'month', label: '月柱', liuqin: '兄弟', note: '人数·排行·雁行' },
	{ pillar: 'day', label: '日柱', liuqin: '夫妻', note: '配偶生肖·婚況' },
	{ pillar: 'hour', label: '時柱', liuqin: '子女', note: '数量·贤否' },
];

// ── §5.6 批断顺序:太极→父母→兄弟→夫妻→子女→本身→大运→流年 ──
const PIDUAN_ORDER = [
	{ key: 'taiji', name: '太極(總論)', pillar: '基本命數', duan: '一生大格局' },
	{ key: 'fumu', name: '父母', pillar: '年柱', duan: '父母生肖·存殁·出身' },
	{ key: 'xiongdi', name: '兄弟', pillar: '月柱', duan: '兄弟数·排行·雁行' },
	{ key: 'fuqi', name: '夫妻', pillar: '日柱', duan: '配偶生肖·婚姻' },
	{ key: 'zinv', name: '子女', pillar: '時柱', duan: '子女数·贤否' },
	{ key: 'benshen', name: '本身', pillar: '—', duan: '体貌·性格·才能' },
	{ key: 'dayun', name: '大運(行限)', pillar: '大運取數訣', duan: '每 10 年一運' },
	{ key: 'liunian', name: '流年', pillar: '流年取數訣', duan: '逐年吉凶' },
];

// ── §11.4 刻制 ──
const KE_SYSTEMS = {
	qing8: { label: '清制·八刻', perKe: 15, keCount: 8, juStruct: '12时辰×8刻＝96局', note: '一时辰8刻·每刻15′·96局主流(清道光本/南派)' },
	ming100: { label: '明制·百刻', perKe: 14.4, keCount: null, juStruct: '一日百刻·每刻14.4′', note: '随节气昼夜(《皇极数》底本);昼夜/宿分野细则秘传,框架按清八刻96局呈' },
	dou12: { label: '十二刻·斗宫', perKe: 10, keCount: 12, juStruct: '12时辰×12刻＝144局', note: '八刻考不中时的12刻补充(斗甲乙宫之败);细则秘传,框架按清八刻96局呈' },
};

// ── §3.1/§5.8/§11.7 南北派 ──
const SCHOOLS = {
	south: { label: '南派(岭南/江南)', zhuGan: '日干支＋时干支', guaPref: '后天(洛书)', quShu: '太玄数为主', tiaowen: '12000', note: '港台东南亚主流·活跃' },
	north: { label: '北派(洛阳/中州)', zhuGan: '月柱＋时干支', guaPref: '先天(河图)', quShu: '先天数为主', tiaowen: '较少', note: '近代几近失传' },
};

// ── §15 借用子系统(结构性·公有古籍来源,不臆造精确星表) ──
const SUBSYSTEMS = [
	{ key: 'dadingshu', name: '大定数(129600)', source: '邵雍《皇极经世》元会运世', struct: '1元=12会=360运=4320世=129600年(1世30年/1运360年/1会10800年)', use: '把人事套入宇宙大周期的标尺' },
	{ key: 'shiganbianyao', name: '十干变曜', source: '《果老星宗》十干化曜', struct: '十天干各化某星曜(星学版十神)', use: '求六亲数时把天干转星曜属性参与取数;完整对照见《果老星宗》' },
	{ key: 'ziwei', name: '紫微八宫正数', source: '《紫微斗数全书》', struct: '定命宫→定五行局(纳音)→起紫微→顺逆安十四主星', use: '借紫微命盘若干宫「正数」参与运算(八宫正数映射各家存疑)' },
	{ key: 'najia', name: '京房纳甲', source: '京房八宫', struct: '乾纳甲壬·坤纳乙癸·震庚·巽辛·坎戊·離己·艮丙·兑丁;阳卦地支顺·阴卦逆', use: '六亲爻取数时借用' },
	{ key: 'qizheng', name: '七政四余', source: '《果老星宗》', struct: '七政=日月+金木水火土;四余=罗睺计都紫炁月孛', use: '偶借年命星曜参与取数(非主线)' },
	{ key: 'ershiba', name: '二十八宿', source: '四象七宿', struct: '东青龙 角亢氐房心尾箕/北玄武 斗牛女虚危室壁/西白虎 奎娄胃昴毕觜参/南朱雀 井鬼柳星张翼轸', use: '明制百刻定局时的星宿分野' },
];

// ── 卦工具(纯函数) ──
function normTri(t) { return TRI_ALIAS[t] || t; }
function triOf(bits3) { return BITS_TRI[bits3.join('')] || null; }
// lines 自下而上 6 位 → { upper, lower, name }
function guaOfLines(lines) {
	const lower = triOf(lines.slice(0, 3));
	const upper = triOf(lines.slice(3, 6));
	if (!upper || !lower) return null;
	return { upper, lower, name: GUA64[`${upper}|${lower}`] || `${TRI_IMAGE[upper]}${TRI_IMAGE[lower]}`, lines: lines.slice() };
}
function linesOfGua(upper, lower) { return [...TRI_BITS[normTri(lower)], ...TRI_BITS[normTri(upper)]]; }
// 互体(§5.5.3 第一卦):爻2-4 为内(下)、爻3-5 为外(上)
function huTiGua(lines) { return guaOfLines([...lines.slice(1, 4), ...lines.slice(2, 5)]); }
// 错卦(complement,全爻阴阳互变);§5.5.3「互卦」步用此(已验渐→归妹/同人→师)
function cuoGua(lines) { return guaOfLines(lines.map((b) => (b ? 0 : 1))); }
// 变爻(翻转指定爻位 1-6)
function bianYao(lines, positions) { const l = lines.slice(); positions.forEach((p) => { if (p >= 1 && p <= 6) l[p - 1] = l[p - 1] ? 0 : 1; }); return l; }
// 上下卦对调
function swapTrigrams(lines) { return [...lines.slice(3, 6), ...lines.slice(0, 3)]; }

export function taixuanPeishu(ganOrZhi) { return TAIXUAN_GAN[ganOrZhi] !== undefined ? TAIXUAN_GAN[ganOrZhi] : (TAIXUAN_ZHI[ganOrZhi] !== undefined ? TAIXUAN_ZHI[ganOrZhi] : null); }

// §4.7 刻位(1-8)→天干;fenWithinHour=时辰内分钟(0-120),keSystem 只影响每刻分长(精确条文仍走八刻)
export function eightKeGan(ke) { return EIGHT_KE_GAN[(ke - 1) % 8] || null; }
export function keOfFen(fenWithinHour, keSystem = 'qing8') {
	const per = (KE_SYSTEMS[keSystem] || KE_SYSTEMS.qing8).perKe;
	const ke = Math.min(8, Math.floor((fenWithinHour || 0) / per) + 1);
	return { ke, gan: eightKeGan(ke), perKe: per };
}

// §11.3 九十六局:某时辰第 N 刻 = 全日第 K 刻(K=(时辰序-1)×8+刻)
export function ninetySixJu(hourZhi, ke) {
	const idx = ZHI.indexOf(hourZhi);
	if (idx < 0 || !(ke >= 1 && ke <= 8)) return null;
	const k = idx * 8 + ke;
	return { hourZhi, ke, quanRiKe: k, label: `${hourZhi}时${['初', '二', '三', '四', '五', '六', '七', '八'][ke - 1]}刻＝全日第${k}刻`, total: 96 };
}

// §5.4.2 四柱配六亲(展示层;不重复算后端条文)
export function liuQinFromPillars(fourPillars) {
	return PILLAR_LIUQIN.map((p) => {
		const gz = `${fourPillars[p.pillar] || ''}`;
		const gan = gz.charAt(0);
		const zhi = gz.charAt(1);
		return {
			...p,
			ganzhi: gz,
			gan,
			zhi,
			shengxiao: SHENGXIAO[zhi] || '',
			taixuanGan: taixuanPeishu(gan),
			taixuanZhi: taixuanPeishu(zhi),
			zhiShu: ZHI_SHENGCHENG[zhi] !== undefined ? ZHI_SHENGCHENG[zhi] : null,
		};
	});
}

// 三元(按出生年):上元<1924 / 中元 1924-1983 / 下元 1984-2043(60 年一元循环)
export function sanYuanOf(birthYear) {
	if (!(birthYear > 0)) return 'zhong';
	const base = ((birthYear - 1864) % 180 + 180) % 180; // 1864 上元甲子
	if (base < 60) return 'shang';
	if (base < 120) return 'zhong';
	return 'xia';
}

// §5.5.3 三元年取数权重(太玄数):上元 干×10+支×1 / 下元 支×10+干×1 / 中元阳男阴女 干×100+支×10 / 中元阳女阴男 支×100+干×10
export function sanYuanWeight(yearGan, yearZhi, sanyuan, isYangManYinNv) {
	const g = taixuanPeishu(yearGan) || 0;
	const z = taixuanPeishu(yearZhi) || 0;
	if (sanyuan === 'shang') return g * 10 + z;
	if (sanyuan === 'xia') return z * 10 + g;
	return isYangManYinNv ? (g * 100 + z * 10) : (z * 100 + g * 10);
}

// ── §5.5.3 八卦滚法(完整可复原;输出 8 卦卦象/动爻,不输出精确条文号) ──
// baseLines=基本卦(自下而上6位);baseNum=基本数序;yearGz=出生年干支;opts{sanyuan,isYangManYinNv}
export function baguaGun(baseLines, baseNum, yearGz, opts = {}) {
	const yGan = `${yearGz}`.charAt(0);
	const yZhi = `${yearGz}`.charAt(1);
	const sanyuan = opts.sanyuan || sanYuanOf(opts.birthYear || 0);
	const weight = sanYuanWeight(yGan, yZhi, sanyuan, opts.isYangManYinNv !== false);
	const total = (baseNum || 0) + weight;
	const r9 = ((total % 9) + 9) % 9;   // →卦2 变爻位
	const r6 = ((total % 6) + 6) % 6;   // →卦5-8 变爻位
	const posFrom = (r) => (((r - 1) % 6) + 6) % 6 + 1; // 余数→爻位 1-6
	const pos9 = posFrom(r9 || 9);
	const ying = pos9 > 3 ? pos9 - 3 : pos9 + 3;        // 应爻(±3)同变
	const pos6 = posFrom(r6 || 6);

	const gua1 = huTiGua(baseLines);                                   // 互体(基本卦)
	const gua2 = guaOfLines(bianYao(gua1.lines, [pos9, ying]));        // 卦1 本爻+应爻同变
	const gua3 = cuoGua(gua1.lines);                                   // 卦1 错卦
	const gua4 = cuoGua(gua2.lines);                                   // 卦2 错卦
	// 卦5-8:卦1-4 各 第pos6爻变 + 上下对调
	const rollOne = (g) => guaOfLines(swapTrigrams(bianYao(g.lines, [pos6])));
	const gua5 = rollOne(gua1);
	const gua6 = rollOne(gua2);
	const gua7 = rollOne(gua3);
	const gua8 = rollOne(gua4);

	const seq = [gua1, gua2, gua3, gua4, gua5, gua6, gua7, gua8].map((g, i) => ({
		idx: i + 1,
		name: g.name,
		upper: g.upper,
		lower: g.lower,
		lines: g.lines,
	}));
	return {
		base: guaOfLines(baseLines),
		baseNum,
		yearGz,
		sanyuan,
		weight,
		total,
		bianYao9: { pos: pos9, ying, remainder: r9 },
		bianYao6: { pos: pos6, remainder: r6 },
		seq,               // 8 卦
		verseCount: seq.length * 6, // 每卦 6 条(结构性,非精确号)
	};
}

// 框架起卦(公开·太玄配数派生基本卦,非秘传起数):
//   上卦 by (年+月 干支太玄数和) mod 8 → 先天卦;下卦 by (日+时) mod 8。school 影响卦数偏好显示,不改卦象。
export function baseGuaFromPillars(fourPillars) {
	const sum = (gz) => (taixuanPeishu(`${gz}`.charAt(0)) || 0) + (taixuanPeishu(`${gz}`.charAt(1)) || 0);
	const XIAN_ORDER = ['乾', '兑', '離', '震', '巽', '坎', '艮', '坤']; // 先天数 1-8
	const upIdx = ((sum(fourPillars.year) + sum(fourPillars.month)) % 8 + 8) % 8;
	const loIdx = ((sum(fourPillars.day) + sum(fourPillars.hour)) % 8 + 8) % 8;
	const upper = XIAN_ORDER[upIdx];
	const lower = XIAN_ORDER[loIdx];
	return guaOfLines(linesOfGua(upper, lower));
}
// 框架数序(公开·太玄数和;真基本数序需秘传,故标示例)。驱动八卦滚变爻位。
export function frameworkNumber(fourPillars) {
	return ['year', 'month', 'day', 'hour'].reduce((acc, k) => {
		const gz = `${fourPillars[k] || ''}`;
		return acc + (taixuanPeishu(gz.charAt(0)) || 0) * 10 + (taixuanPeishu(gz.charAt(1)) || 0);
	}, 0);
}
// 卦→数(按流派卦数偏好:南派后天洛书/北派先天河图)
export function guaNumberBySchool(triName, school) {
	const t = normTri(triName);
	return school === 'north' ? (XIANTIAN_NUM[t] || null) : (HOUTIAN_NUM[t] || null);
}

// ── 汇总:据四柱+流派+刻制 产出完整框架 model ──
export function buildTiebanFramework(fourPillars, opts = {}) {
	if (!fourPillars || !fourPillars.year || !fourPillars.month || !fourPillars.day || !fourPillars.hour) return null;
	const school = opts.school === 'north' ? 'north' : 'south';
	const keSystem = KE_SYSTEMS[opts.keSystem] ? opts.keSystem : 'qing8';
	const birthYear = opts.birthYear || 0;
	const sanyuan = sanYuanOf(birthYear);
	const yGan = `${fourPillars.year}`.charAt(0);
	const isYang = GAN.indexOf(yGan) % 2 === 0;               // 阳年干
	const isMale = !(opts.gender === 0 || opts.gender === '0' || opts.gender === '女' || opts.gender === 'Female');
	const isYangManYinNv = (isYang && isMale) || (!isYang && !isMale);
	const hourZhi = `${fourPillars.hour}`.charAt(1);
	const ke = opts.ke && opts.ke >= 1 && opts.ke <= 8 ? opts.ke : 1;

	const baseGua = baseGuaFromPillars(fourPillars);
	const fwNum = frameworkNumber(fourPillars);
	const roll = baguaGun(baseGua.lines, fwNum, fourPillars.year, { sanyuan, isYangManYinNv, birthYear });

	return {
		school,
		schoolInfo: SCHOOLS[school],
		keSystem,
		keSystemInfo: KE_SYSTEMS[keSystem],
		sanyuan,
		sanyuanLabel: { shang: '上元', zhong: '中元', xia: '下元' }[sanyuan],
		isYangManYinNv,
		liuQin: liuQinFromPillars(fourPillars),
		// §4.7 八刻天干表本身=清八刻(每刻15′,与刻制§11.4 日分制正交);active=当前考刻刻位
		eightKe: EIGHT_KE_GAN.map((gan, i) => ({ ke: i + 1, gan, seg: `${i * 15}–${(i + 1) * 15}′`, active: (i + 1) === ke })),
		ke,
		ju: ninetySixJu(hourZhi, ke),
		baseGua: { name: baseGua.name, upper: baseGua.upper, lower: baseGua.lower, num: guaNumberBySchool(baseGua.upper, school) },
		frameworkNum: fwNum,
		roll,
		piduan: PIDUAN_ORDER,
		subsystems: SUBSYSTEMS,
		taixuanTable: { gan: TAIXUAN_GAN, zhi: TAIXUAN_ZHI },
	};
}

// AI 快照:框架文本段(段名与报告层/aiExport 契约一致)
export function buildTiebanFrameworkSnapshot(fw) {
	if (!fw) return '';
	const lines = [];
	lines.push('[框架·流派刻制]');
	lines.push(`流派:${fw.schoolInfo.label}(主算柱 ${fw.schoolInfo.zhuGan}·卦数偏好 ${fw.schoolInfo.guaPref}·条文 ${fw.schoolInfo.tiaowen})`);
	lines.push(`刻制:${fw.keSystemInfo.label}(${fw.keSystemInfo.note})　三元:${fw.sanyuanLabel}`);
	lines.push('');
	lines.push('[框架·考刻六亲]');
	lines.push('起卦诀:考时定刻用乾坤,乾为父兮母为坤。二十四条明日月,八刻天干又一村。');
	fw.liuQin.forEach((q) => lines.push(`${q.label}→${q.liuqin}(${q.note}):${q.ganzhi} ${q.shengxiao ? '属' + q.shengxiao : ''} 太玄干${q.taixuanGan}/支${q.taixuanZhi}`));
	lines.push(`八刻天干:${fw.eightKe.map((k) => `${['初', '二', '三', '四', '五', '六', '七', '八'][k.ke - 1]}刻${k.gan}${k.active ? '(考刻)' : ''}`).join(' ')}`);
	if (fw.ju) lines.push(`九十六局:${fw.ju.label} · ${fw.keSystemInfo.juStruct}`);
	lines.push('');
	lines.push('[框架·八卦滚]');
	lines.push(`框架起卦(太玄配数):${fw.baseGua.name}　框架数序(示例):${fw.frameworkNum}`);
	lines.push(`三元取数(${fw.sanyuanLabel}):权重 ${fw.roll.weight}　变爻余(÷9)${fw.roll.bianYao9.remainder}→${fw.roll.bianYao9.pos}·${fw.roll.bianYao9.ying}爻　(÷6)${fw.roll.bianYao6.remainder}→${fw.roll.bianYao6.pos}爻`);
	lines.push(`八卦滚八卦:${fw.roll.seq.map((g) => g.name).join('、')}`);
	lines.push('（每卦滚 6 条、8 卦共 48 条为结构总量;精确条文号由坤集密码表定,属秘传,本框架不推。）');
	lines.push('');
	lines.push('[框架·批断顺序]');
	lines.push(fw.piduan.map((p, i) => `${i + 1}.${p.name}(${p.pillar})`).join(' → '));
	lines.push('');
	lines.push('[框架·借用子系统]');
	fw.subsystems.forEach((s) => lines.push(`${s.name}:${s.struct}（源 ${s.source}）`));
	return lines.join('\n');
}

export const TIEBAN_SCHOOLS = SCHOOLS;
export const TIEBAN_KE_SYSTEMS = KE_SYSTEMS;
export const TIEBAN_TAIXUAN = { gan: TAIXUAN_GAN, zhi: TAIXUAN_ZHI };
export const TIEBAN_EIGHT_KE = EIGHT_KE_GAN;
export const TIEBAN_SUBSYSTEMS = SUBSYSTEMS;
export const TIEBAN_PIDUAN = PIDUAN_ORDER;
export { GUA64, guaOfLines, huTiGua, cuoGua, swapTrigrams, bianYao, linesOfGua };
