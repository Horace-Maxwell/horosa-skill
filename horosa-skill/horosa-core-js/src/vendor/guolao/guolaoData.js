// 七政四余 / 果老星宗 前端数据镜像(对齐 astropy/astrostudy/guolao_const.py 真值源)。
// 供资料页(G35)显示 + 未来左栏选项;纯数据,无副作用。中性词(无软件名/版权书名)。

export const SU28 = '角亢氐房心尾箕斗牛女虚危室壁奎娄胃昴毕觜参井鬼柳星张翼轸'.split('');
export const SU28_DISTANCE = [11, 10, 18, 5, 8, 15, 9, 24, 8, 12, 10, 20, 15, 14, 11, 13, 13, 9, 15, 1, 10, 31, 4, 17, 9, 18, 17, 13];
const DUZHU_CYCLE = ['木', '金', '土', '日', '月', '火', '水'];
export const SU28_DEGREE_LORD = SU28.map((_, i)=>DUZHU_CYCLE[i % 7]);
export const SU28_JIAO_START_MODERN = 203.84;   // 今宿 J2000(+50.29″/年)
export const SU28_JIAO_START_ANCIENT = 199.43;  // 古宿(冻结)
export const EQUATORIAL_TOTAL_DEGREE = 365.25;  // 赤道古度

export const DIZHI = '子丑寅卯辰巳午未申酉戌亥'.split('');
// 地支 → [黄道宫(西名/十二次), 宫主曜, 旺曜或'—', 旺度或'']
export const PALACE_LORD = {
	子: ['宝瓶·玄枵', '土', '—', ''], 丑: ['摩羯·星纪', '土', '火', '28°'],
	寅: ['射手·析木', '木', '—', ''], 卯: ['天蝎·大火', '火', '—', ''],
	辰: ['天秤·寿星', '金', '土', '21°'], 巳: ['处女·鹑尾', '水', '水', '15°'],
	午: ['狮子·鹑火', '日', '—', ''], 未: ['巨蟹·鹑首', '月', '木', '15°'],
	申: ['双子·实沈', '水', '—', ''], 酉: ['金牛·大梁', '金', '月', '3°'],
	戌: ['白羊·降娄', '火', '日', '19°'], 亥: ['双鱼·娵訾', '木', '金', '27°'],
};

// G25 擢升度数(旺度峰值)派生:旺曜→{signIndex,deg}。signIndex 黄道序(白羊0..双鱼11);
// 地支宫古法 戌=白羊(降娄),子=宝瓶,故 signIndex=(10-地支序+12)%12。单一真值源=PALACE_LORD。
export const EXALT_DEGREE = (function(){
	const out = {};
	DIZHI.forEach((zhi, zi)=>{
		const row = PALACE_LORD[zhi];
		if(!row){ return; }
		const star = row[2];
		const deg = parseInt(row[3], 10);
		if(!star || star === '—' || !Number.isFinite(deg)){ return; }
		out[star] = { signIndex: (10 - zi + 12) % 12, deg };
	});
	return out;
})();

// 庙旺七政 7×12(行=曜,列=子..亥)
export const DIGNITY_TABLE = {
	日: ['陷', '平', '平', '平', '落', '平', '庙', '平', '平', '平', '旺', '平'],
	月: ['平', '陷', '平', '落', '平', '平', '平', '庙', '平', '旺', '平', '平'],
	水: ['平', '平', '陷', '平', '平', '庙', '平', '平', '庙', '平', '平', '陷'],
	金: ['平', '平', '平', '陷', '庙', '落', '平', '平', '平', '庙', '陷', '旺'],
	火: ['平', '旺', '平', '庙', '陷', '平', '平', '落', '平', '陷', '庙', '平'],
	木: ['平', '落', '庙', '平', '平', '陷', '平', '旺', '陷', '平', '平', '庙'],
	土: ['庙', '庙', '平', '平', '旺', '平', '陷', '陷', '平', '平', '落', '平'],
};

// 🔴 Moira 星辰庙旺（殿垣庙旺乐喜怒）——抄自 moira_t.prop:1845-1858（繁→简：廟→庙 / 樂→乐，数据 byte-perfect）。
// sign_status_seq=殿,垣,庙,旺,乐,喜,怒（呈现/优先序）；「殿」=升殿，另由躔擢升度峰值判（EXALT_DEGREE±容差），不在此表。
// 同一地支可多态叠加（如金在酉=垣庙乐）。天海冥=现代星，古法无庙旺之位，不列（所属留空）。地支采古法宫序（戌=白羊）。
export const SIGN_STATUS_SEQ = ['殿', '垣', '庙', '旺', '乐', '喜', '怒'];
const SIGN_STATUS_RAW = {
	日: '午:垣,午:庙,巳:旺,戌:旺,午:乐,辰:乐,寅:喜',
	月: '未:垣,戌:庙,酉:旺,未:乐,卯:喜,亥:喜',
	金: '酉:垣,辰:垣,酉:庙,辰:庙,午:旺,亥:旺,酉:乐,辰:乐,巳:喜,寅:怒',
	木: '寅:垣,亥:垣,亥:庙,未:旺,寅:乐,亥:乐,未:喜,子:怒',
	水: '申:垣,巳:垣,午:庙,申:旺,巳:旺,子:旺,申:乐,巳:乐,辰:喜,戌:怒',
	火: '卯:垣,戌:垣,卯:庙,丑:旺,卯:乐,申:喜,丑:喜,酉:怒',
	土: '丑:垣,子:垣,丑:庙,子:庙,辰:旺,卯:旺,丑:乐,子:乐,午:喜,巳:怒',
	计: '巳:庙,亥:庙,卯:旺,寅:旺,戌:旺,卯:乐,子:喜',
	罗: '午:庙,寅:庙,卯:旺,戌:喜',
	炁: '申:庙,丑:旺,亥:旺,戌:喜',
	孛: '未:庙,巳:旺,寅:旺,子:乐,酉:乐,亥:喜',
};
// 解析为 { 星: { 地支: [状态…] } }；同地支多态按 SIGN_STATUS_SEQ 序去重排列。单一真值源。
export const SIGN_STATUS_TABLE = (function(){
	const seqIdx = (s)=>SIGN_STATUS_SEQ.indexOf(s);
	const out = {};
	Object.keys(SIGN_STATUS_RAW).forEach((star)=>{
		const m = {};
		SIGN_STATUS_RAW[star].split(',').forEach((pair)=>{
			const parts = pair.split(':');
			const zhi = parts[0];
			const st = parts[1];
			if(!zhi || !st){ return; }
			if(!m[zhi]){ m[zhi] = []; }
			if(m[zhi].indexOf(st) < 0){ m[zhi].push(st); }
		});
		Object.keys(m).forEach((zhi)=>{ m[zhi].sort((a, b)=>seqIdx(a) - seqIdx(b)); });
		out[star] = m;
	});
	return out;
})();

// 某曜在地支 zhi 的 Moira 庙旺所属（殿垣庙旺乐喜怒）；atExaltPeak=true 时前置「殿」（升殿=躔擢升度峰值）。
// star=曜简名(日月金木水火土计罗炁孛);天海冥/升顶等无表项 → 返回 []（或仅「殿」若峰值，天海冥无擢升故不会）。
export function starDignityStatuses(star, zhi, atExaltPeak){
	const base = (SIGN_STATUS_TABLE[star] && SIGN_STATUS_TABLE[star][zhi]) ? SIGN_STATUS_TABLE[star][zhi].slice() : [];
	if(atExaltPeak){ base.unshift('殿'); }
	return base;
}

// 🔴 Moira 星曜速度状态阈值（moira_t.prop:714-724，五星专用，顺序=金木水火土；单位=度/日 黄经日行度）。
// speed_state=顺,逆,蚀,留,伏,迟,速；stationary_gap→留、invisible_gap(合日3°)→伏、slow_speed→迟、fast_speed→速。
export const STAR_SPEED_SPEC = {
	金: { stat: 0.15, invisible: 3.0, slow: 0.71, fast: 1.245 },
	木: { stat: 0.07, invisible: 3.0, slow: 0.05, fast: 0.23 },
	水: { stat: 0.10, invisible: 3.0, slow: 0.88, fast: 1.50 },
	火: { stat: 0.20, invisible: 3.0, slow: 0.40, fast: 0.70 },
	土: { stat: 0.05, invisible: 3.0, slow: 0.02, fast: 0.13 },
};
// 天海冥（现代星，古法无速度档）——Horosa 依平均日行度派生阈值，与五星同风格（非 Moira 金标，实现层扩展）。
export const OUTER_SPEED_SPEC = {
	天: { stat: 0.004, slow: 0.020, fast: 0.050 },
	海: { stat: 0.003, slow: 0.012, fast: 0.032 },
	冥: { stat: 0.003, slow: 0.012, fast: 0.030 },
};
// 星点速度状态（照 Moira 顺逆留伏迟速；蚀由 eclipse 另判）：
// name=曜简名;speed=度/日;combust=合日3°内(仅五星判伏)。升顶(角点)无自行→''；计罗无速度→逆(平交点)。
export function starMotionState(name, speed, combust){
	const sp = Number(speed);
	const spec = STAR_SPEED_SPEC[name] || OUTER_SPEED_SPEC[name];
	if(!Number.isFinite(sp)){
		return (name === '计' || name === '罗') ? '逆' : '';
	}
	const a = Math.abs(sp);
	const parts = [];
	if(combust && STAR_SPEED_SPEC[name]){ parts.push('伏'); }   // 伏（合日）仅五星
	if(spec && a < spec.stat){
		parts.push('留');
		return parts.join('·');
	}
	parts.push(sp < -1e-7 ? '逆' : '顺');
	if(spec){
		if(a < spec.slow){ parts.push('迟'); }
		else if(a > spec.fast){ parts.push('速'); }
	}
	return parts.join('·');
}

// 合日「伏」判据(照 Moira invisible_gap=3.0，Calculate.java 以 <= 判)：仅五星，与太阳黄经角距 ≤ 阈值即伏。
// 🔴 单一真值源：右栏星点动态表(motionState)与 AI 快照共用，消「面板 8° 焦伤 vs Moira 3° 伏」双口径分歧。
// 注：isCombustObj(面板 8°)是 Horosa 另一套「焦伤」语义，不与此混用；本函数专供 Moira 速度态「伏」。
export function starCombust(name, lon, sunLon){
	const spec = STAR_SPEED_SPEC[name];
	const l = Number(lon);
	const s = Number(sunLon);
	if(!spec || !Number.isFinite(l) || !Number.isFinite(s)){ return false; }
	const sep = Math.abs((((l - s) % 360) + 540) % 360 - 180);
	return sep <= spec.invisible;
}

// 十干化曜 A 诀(化曜) / 魁星 B 诀(≠化曜,仅备注)
export const HUAYAO_A = { 甲: '火', 乙: '月孛', 丙: '木', 丁: '金', 戊: '土', 己: '太阴', 庚: '水', 辛: '紫炁', 壬: '计都', 癸: '罗睺' };
export const KUIXING_B = { 甲: '太阴', 乙: '太阳', 丙: '罗睺', 丁: '计都', 戊: '炎', 己: '金', 庚: '水', 辛: '月孛', 壬: '紫炁', 癸: '木' };
// 十化次序 · 所管宫 · ≈紫微四化
export const SHIHUA_ORDER = [
	['天禄', '官禄', '化禄'], ['天暗', '相貌', ''], ['天福', '财/福德/迁移', ''],
	['天耗', '兄弟', ''], ['天荫', '妻妾', ''], ['天贵', '男女', '化科'],
	['天刑', '奴仆', '化忌'], ['天印', '田宅', ''], ['天囚', '疾厄', ''], ['天权', '命宫', '化权'],
];

// 四余每日平行度(古法立成) + 周期 + 五行
export const SIYU_DAILY_RATE = { 罗睺: -0.05296, 计都: -0.05296, 月孛: 0.11137, 紫炁: 0.03520 };
export const SIYU_PERIOD_YEAR = { 罗睺: 18.61, 计都: 18.61, 月孛: 8.85, 紫炁: 28.0 };
export const SIYU_WUXING = { 罗睺: '火', 计都: '土', 月孛: '水', 紫炁: '木' };

// 洞微大限 各宫年数(自命宫顺行)
export const DONGWEI_PALACE_YEARS = [
	['命宫', 15], ['相貌', 10], ['福德', 11], ['官禄', 15], ['迁移', 8], ['妻妾', 11],
	['奴仆', 4.5], ['男女', 4.5], ['田宅', 4.5], ['财帛', 5], ['兄弟', 5], ['疾厄', 7],
];

// ── 宿度制(用制)单一真值源:黄仪(黄道坐标)/赤仪(赤道坐标)分组 + 订正标签。──
// WP-A:消除旧 SU28_MODE_OPTIONS/GuoLaoInput内联/_su28Name 三套漂移标签。下拉、查名一律走此。
// 黄仪=按黄经置宿(byLon);赤仪=按赤经置宿(byRA)。第6档「授时历古法」由 WP-D 追加于黄仪组末位。
export const SU28_MODE_GROUPS = [
	{ header: '黄仪（黄道）', options: [
		{ value: 2, label: '回归今宿' },
		{ value: 3, label: '回归古制开禧' },
		{ value: 4, label: '恒星制' },
		{ value: 6, label: '授时历古法' },
	] },
	{ header: '赤仪（赤道）', options: [
		{ value: 0, label: '荀爽距星(19年测)' },
		{ value: 1, label: '斗柄定房法' },
		{ value: 5, label: '恒星制·现代天赤' },
		{ value: 7, label: '赤道回归(元明)' },
		{ value: 8, label: '赤道回归(实时)' },
	] },
];
// 扁平查表:value→label(供 _su28Name 等单点取名,杜绝第三套漂移)。
export const SU28_MODE_LABEL = SU28_MODE_GROUPS.reduce((acc, g)=>{ g.options.forEach((o)=>{ acc[o.value] = o.label; }); return acc; }, {});

// @deprecated 旧标签(误标黄/赤、漂移);保留仅防外部引用,新代码一律用 SU28_MODE_GROUPS/SU28_MODE_LABEL。
export const SU28_MODE_OPTIONS = [
	{ value: 0, label: '黄道·荀爽(赤经置宿)' }, { value: 1, label: '黄道·今宿' },
	{ value: 2, label: '黄道·回归今宿' }, { value: 3, label: '黄道·古宿(永不变盘)' },
	{ value: 4, label: '黄道恒星制' }, { value: 5, label: '赤道恒星制(365.25古度)' },
];
export const LIFE_MODE_OPTIONS = [
	{ value: 'asc', label: '占星上升(默认)' }, { value: 'yumao', label: '日出安命' },
	{ value: 'gumao', label: '遇卯安命(古法)' }, { value: 'cotrans', label: '赤黄转换' },
];
export const BODY_MODE_OPTIONS = [
	{ value: 'taiyin', label: '太阴落宫(果老)' }, { value: 'youjin', label: '逢酉(琴堂)' },
];
// 子~亥 地支:直接作命度/身宫法下拉里的「自定命宫/身宫」选项(值=地支,后端按地支当 custom 算)。
export const GUOLAO_DIZHI_LIST = '子丑寅卯辰巳午未申酉戌亥'.split('');
export const LIFE_CUSTOM_ZHI_OPTIONS = GUOLAO_DIZHI_LIST.map((z)=>({ value: z, label: `自定命宫·${z}` }));
export const BODY_CUSTOM_ZHI_OPTIONS = GUOLAO_DIZHI_LIST.map((z)=>({ value: z, label: `自定身宫·${z}` }));
export const QINTANG_DIR_OPTIONS = [
	{ value: 'you', label: '逆数至酉(命卯身酉)' }, { value: 'mao', label: '顺数至卯' },
];
export const LIFE_MASTER_MODE_OPTIONS = [
	{ value: 'gong', label: '宫主(默认)' }, { value: 'du', label: '度主' }, { value: 'dudegrade', label: '贬宫主专度主' },
];
export const TRUE_SOLAR_TIME_OPTIONS = [
	{ value: 'true', label: '真太阳时(经度+均时差)' }, { value: 'mean', label: '平太阳时(仅经度)' }, { value: 'off', label: '钟表时' },
];
export const NODE_TYPE_OPTIONS = [{ value: 'mean', label: '平交点' }, { value: 'true', label: '真交点' }];
export const LILITH_TYPE_OPTIONS = [{ value: 'mean', label: '平远地点' }, { value: 'true', label: '真远地点' }];
// 紫炁取法:仅「今法真算」一档生效。'tablet'(28年立成)后端 perchart 零消费、无核实立成历元,
// 属假开关——暂隐藏不投 UI;待考订立成历元、后端落地后再恢复该档(保留注释作占位)。
export const ZIQI_MODE_OPTIONS = [
	{ value: 'real', label: '今法真算(默认)' },
	// { value: 'tablet', label: '28年立成' }, // TODO 待后端 perchart 实现立成历元后恢复
];
// 授时历古法(用制 6)子选项:推变黄道术法 + 古宿随岁差。仅 mode6 生效。
export const TUIBIAN_METHOD_OPTIONS = [
	{ value: 'jiyuan', label: '纪元闭式(默认)' }, { value: 'jintui', label: '进退法(大衍)' }, { value: 'huiyuan', label: '会圆术(授时)' },
];
export const GUFA_PRECESS_OPTIONS = [
	{ value: 0, label: '钉死元时(默认)' }, { value: 1, label: '随岁差东移' },
];
// 赤道回归制(用制 7 元明立成 / 用制 8 实时距星)子选项:黄道零点锚定。dongzhi 牛前冬至(默认)/ chunfen 春分壁2.3。
export const EQ_TROPICAL_ANCHOR_OPTIONS = [
	{ value: 'dongzhi', label: '牛前·冬至270°(默认)' }, { value: 'chunfen', label: '春分·壁2.3°' },
];
export const MINOR_LIMIT_TYPE_OPTIONS = [
	{ value: 'minor', label: '小限' }, { value: 'month', label: '月限' }, { value: 'tong', label: '童限' }, { value: 'dongwei', label: '洞微大限' },
];
// 童限基数分歧(古籍 ch.4 论辩;坊间排盘软件即出 9/10 两版)做成可选。默认 tong10=现状零回归。
export const TONGXIAN_BASE_OPTIONS = [
	{ value: 'tong10', label: '通行十年(默认)' }, { value: 'gu9', label: '古九岁' }, { value: 'xu11', label: '虚十一·早不过11岁' },
];
export const SCHOOL_PRESET_OPTIONS = [
	{ value: 'custom', label: '自定' }, { value: 'qintang', label: '琴堂五星' },
	{ value: 'guolao', label: '果老星宗' }, { value: 'tianguan', label: '天官/耶律' }, { value: 'huujiao', label: '弧角天星' },
];

// 分宫制(西占宫位格/择日西占带共用)单一真值源:code(swisseph hsys 字母)→ 显示名。
// 下拉、盘面 tooltip、四角标注三处一律引此,杜绝「盘上显示原始字母 B 制」类漂移。
export const HSYS_OPTIONS = [
	['P', 'Placidus'], ['K', 'Koch'], ['O', 'Porphyrius'], ['R', 'Regiomontanus'],
	['C', 'Campanus'], ['A', 'Equal'], ['V', 'Vehlow'], ['X', 'Meridian'],
	['H', 'Horizontal'], ['T', 'Topocentric'], ['B', 'Alcabitius'],
];
export const HSYS_NAME = HSYS_OPTIONS.reduce((acc, [v, l])=>{ acc[v] = l; return acc; }, {});
export function hsysDisplayName(code){ return HSYS_NAME[code] || HSYS_NAME.P; }
