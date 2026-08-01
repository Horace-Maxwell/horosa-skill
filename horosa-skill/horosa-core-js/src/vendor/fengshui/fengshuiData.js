// 风水 · 正统理气六派 · 底层真值源（单一 ground-truth，纯常量，无 DOM）。
// 数据照正统堪舆诸家第一部 + golden 基准（飞星/三合/乾坤国宝/紫白）转录。
// UI 只引公有古籍（沈氏玄空学/地理五诀/青囊奥语/天玉经等）。

// ── 九宫洛书（数→方位名）+ 飞泊对宫 ──────────────────────────────────────
// 1坎北 2坤西南 3震东 4巽东南 5中 6乾西北 7兑西 8艮东北 9离南
export const GONG_NAME = { 1: '坎北', 2: '坤西南', 3: '震东', 4: '巽东南', 5: '中', 6: '乾西北', 7: '兑西', 8: '艮东北', 9: '离南' };
export const GONG_GUA = { 1: '坎', 2: '坤', 3: '震', 4: '巽', 5: '中', 6: '乾', 7: '兑', 8: '艮', 9: '离' };
// 对宫（坐↔向）。
export const OPP_GONG = { 1: 9, 9: 1, 2: 8, 8: 2, 3: 7, 7: 3, 4: 6, 6: 4 };

// ── 二十四山：名 → [卦宫洛书数, 元龙(地/天/人), 阴阳(+1阳/-1阴)] ──（内核基准 原表）
export const SHAN_24 = {
	壬: [1, '地', +1], 子: [1, '天', -1], 癸: [1, '人', -1],
	未: [2, '地', -1], 坤: [2, '天', +1], 申: [2, '人', +1],
	甲: [3, '地', +1], 卯: [3, '天', -1], 乙: [3, '人', -1],
	辰: [4, '地', -1], 巽: [4, '天', +1], 巳: [4, '人', +1],
	丙: [9, '地', +1], 午: [9, '天', -1], 丁: [9, '人', -1],
	庚: [7, '地', +1], 酉: [7, '天', -1], 辛: [7, '人', -1],
	戌: [6, '地', -1], 乾: [6, '天', +1], 亥: [6, '人', +1],
	丑: [8, '地', -1], 艮: [8, '天', +1], 寅: [8, '人', +1],
};
// 罗盘顺序（壬起，每山 15°，正北壬子癸…）。
export const SHAN_ORDER = ['壬', '子', '癸', '丑', '艮', '寅', '甲', '卯', '乙', '辰', '巽', '巳',
	'丙', '午', '丁', '未', '坤', '申', '庚', '酉', '辛', '戌', '乾', '亥'];
// 24 山中心度数：子=0°（正北），每山 15°；壬=子−15=345°。
export const SHAN_CENTER_DEG = (()=>{
	const out = {};
	// 子在 0°(正北)；SHAN_ORDER 从壬起，壬在 345°，依次 +15。
	SHAN_ORDER.forEach((s, i)=>{ out[s] = (345 + i * 15) % 360; });
	return out;
})();

// ── 三元九运（1864–2043）：运 → [起年, 止年] ────────────────────────────
export const YUN_YEARS = {
	1: [1864, 1883], 2: [1884, 1903], 3: [1904, 1923],
	4: [1924, 1943], 5: [1944, 1963], 6: [1964, 1983],
	7: [1984, 2003], 8: [2004, 2023], 9: [2024, 2043],
};

// ── 先天八卦方位（卦→方位洛书数）+ 后天方位（内核基准 原表）──────────────
export const XIANTIAN_POS = { 乾: 9, 坤: 1, 离: 3, 坎: 7, 震: 8, 巽: 2, 兑: 4, 艮: 6 };
export const HOUTIAN_POS = { 坎: 1, 坤: 2, 震: 3, 巽: 4, 乾: 6, 兑: 7, 艮: 8, 离: 9 };
export const POS_NAME = { 1: '坎(北)', 2: '坤(西南)', 3: '震(东)', 4: '巽(东南)', 6: '乾(西北)', 7: '兑(西)', 8: '艮(东北)', 9: '离(南)' };

// ── 三合 十二长生（内核基准）────────────────────────────────────────────
export const SANHE_ZHI = ['子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥'];
export const SANHE_SHUANGSHAN = {
	子: '壬子', 丑: '癸丑', 寅: '艮寅', 卯: '甲卯', 辰: '乙辰', 巳: '巽巳',
	午: '丙午', 未: '丁未', 申: '坤申', 酉: '庚酉', 戌: '辛戌', 亥: '乾亥',
};
export const SANHE_STAGE = ['长生', '沐浴', '冠带', '临官', '帝旺', '衰', '病', '死', '墓', '绝', '胎', '养'];
export const SANHE_JU_CS = { 火局: '寅', 金局: '巳', 水局: '申', 木局: '亥' };
// 长生十二阶吉凶定性（生旺墓库吉/沐浴病死绝凶；地理五诀）。
export const SANHE_STAGE_JX = {
	长生: 'good', 沐浴: 'bad', 冠带: 'good', 临官: 'good', 帝旺: 'good', 衰: 'neutral',
	病: 'bad', 死: 'bad', 墓: 'good', 绝: 'bad', 胎: 'neutral', 养: 'good',
};

// ── 紫白九星名 + 吉凶（8.1.5：一六八九吉、二三五七凶、四绿文昌吉、五黄大凶）──
export const ZIBAI_STAR = { 1: '一白', 2: '二黑', 3: '三碧', 4: '四绿', 5: '五黄', 6: '六白', 7: '七赤', 8: '八白', 9: '九紫' };
export const ZIBAI_JX = { 1: 'good', 2: 'bad', 3: 'bad', 4: 'good', 5: 'bad', 6: 'good', 7: 'bad', 8: 'good', 9: 'good' };

// ── 九星本义（玄空/紫白共用；当令为吉、失令为凶；沈氏玄空学）──────────────
export const NINE_STAR_MEANING = {
	1: { name: '一白贪狼', wuxing: '水', good: '文秀·官禄·智慧', bad: '漂泊·肾耳·血症' },
	2: { name: '二黑巨门', wuxing: '土', good: '田产·众望（当令）', bad: '病符·腹疾·寡母' },
	3: { name: '三碧禄存', wuxing: '木', good: '兴家·权威（当令）', bad: '蚩尤·官非·盗劫·肝足' },
	4: { name: '四绿文曲', wuxing: '木', good: '文昌·科甲·婚姻', bad: '荡子·风疾·自缢' },
	5: { name: '五黄廉贞', wuxing: '土', good: '至尊（当令暂吉）', bad: '正关煞·重病·死亡·灾祸' },
	6: { name: '六白武曲', wuxing: '金', good: '权威·武贵·官禄', bad: '亢龙·头骨·刑伤' },
	7: { name: '七赤破军', wuxing: '金', good: '偏财·口才（当令）', bad: '盗劫·火灾·口舌·肺喉' },
	8: { name: '八白左辅', wuxing: '土', good: '财帛·孝义·富贵（当令）', bad: '小口·脾鼻（失令）' },
	9: { name: '九紫右弼', wuxing: '火', good: '喜庆·科名·桃花', bad: '回禄·目疾·心血·官讼' },
};

// ── 玄空进阶（替卦兼向 / 七星打劫 / 城门）正统古法 ──
// 二十四山替星表（沈氏通行本）：兼向起替时入中之数。口诀确定 12 山(巨2坤壬乙·破7艮丙辛·武6巽辰亥·贪1甲癸申)无争议。
export const TIXING_SHEN = {
	壬: 2, 子: 1, 癸: 1, 丑: 7, 艮: 7, 寅: 9,
	甲: 1, 卯: 2, 乙: 2, 辰: 6, 巽: 6, 巳: 6,
	丙: 7, 午: 9, 丁: 9, 未: 2, 坤: 2, 申: 1,
	庚: 9, 酉: 7, 辛: 7, 戌: 6, 乾: 6, 亥: 6,
};
// 各家有别的 12 山（◇）：右弼方案径用 9、本宫方案用本宫数；沈氏用上表。
export const TIXING_DISPUTED = new Set(['子', '卯', '午', '酉', '丑', '未', '寅', '戌', '巳', '乾', '庚', '丁']);
// 替星方案标签（左栏可切）。
export const TIXING_VARIANTS = [
	{ value: 'shen', label: '沈氏通行' },
	{ value: 'youbi', label: '右弼（子午卯酉等用9）' },
	{ value: 'bengong', label: '本宫数' },
];
// 七星打劫宫组（向星成父母三般卦连珠判据）：离宫打劫=离震乾(369)、坎宫打劫=坎巽兑(147)。
export const ROB_GROUPS = {
	li: { name: '离宫打劫（真）', gongs: [9, 3, 6], nature: 'good' },
	kan: { name: '坎宫打劫（假）', gongs: [1, 4, 7], nature: 'mild' },
};
// 后天方位环（顺时针）：城门取向首两旁宫。
export const FANGWEI_RING = [1, 8, 3, 4, 9, 2, 7, 6];

// ══════════════════════════════════════════════════════════════════════════
// 补齐波次数据底座（正统体系）。纯常量。
// ══════════════════════════════════════════════════════════════════════════

// ── 纳甲归卦（正统古法）：卦 → 所纳二十四山（干支）──────────────────────────
// 乾甲·坤乙·坎癸申辰·离壬寅戌·震庚亥未·巽辛·艮丙·兑丁巳丑。
export const NAJIA_GUA = {
	乾: ['甲'], 坤: ['乙'], 坎: ['癸', '申', '辰'], 离: ['壬', '寅', '戌'],
	震: ['庚', '亥', '未'], 巽: ['辛'], 艮: ['丙'], 兑: ['丁', '巳', '丑'],
};

// ── 净阴净阳（正统古法）：二十四山按纳甲卦归净阴/净阳（卦名取天元支）──
//   净阳:乾甲坤乙、坎(子)癸申辰、离(午)壬寅戌;净阴:艮丙巽辛、震(卯)庚亥未、兑(酉)丁巳丑。
export const JING_YANG = new Set(['乾', '甲', '坤', '乙', '子', '癸', '申', '辰', '午', '壬', '寅', '戌']);
export const JING_YIN = new Set(['艮', '丙', '巽', '辛', '卯', '庚', '亥', '未', '酉', '丁', '巳', '丑']);
// 六秀（艮丙巽辛兑丁，催官贵峰；催官篇）。
export const LIU_XIU = new Set(['艮', '丙', '巽', '辛', '兑', '丁']);

// ── 六十甲子纳音（正统古法）：干支 → {纳音名, 五行} ─────────────────────────
export const NAYIN_PAIRS = [
	['甲子', '乙丑', '海中金'], ['丙寅', '丁卯', '炉中火'], ['戊辰', '己巳', '大林木'],
	['庚午', '辛未', '路旁土'], ['壬申', '癸酉', '剑锋金'], ['甲戌', '乙亥', '山头火'],
	['丙子', '丁丑', '涧下水'], ['戊寅', '己卯', '城头土'], ['庚辰', '辛巳', '白蜡金'],
	['壬午', '癸未', '杨柳木'], ['甲申', '乙酉', '泉中水'], ['丙戌', '丁亥', '屋上土'],
	['戊子', '己丑', '霹雳火'], ['庚寅', '辛卯', '松柏木'], ['壬辰', '癸巳', '长流水'],
	['甲午', '乙未', '沙中金'], ['丙申', '丁酉', '山下火'], ['戊戌', '己亥', '平地木'],
	['庚子', '辛丑', '壁上土'], ['壬寅', '癸卯', '金箔金'], ['甲辰', '乙巳', '覆灯火'],
	['丙午', '丁未', '天河水'], ['戊申', '己酉', '大驿土'], ['庚戌', '辛亥', '钗钏金'],
	['壬子', '癸丑', '桑柘木'], ['甲寅', '乙卯', '大溪水'], ['丙辰', '丁巳', '沙中土'],
	['戊午', '己未', '天上火'], ['庚申', '辛酉', '石榴木'], ['壬戌', '癸亥', '大海水'],
];
export const NAYIN_60 = (()=>{
	const m = {};
	NAYIN_PAIRS.forEach(([a, b, name])=>{
		const wuxing = name.slice(-1);   // 末字即五行（金木水火土）
		m[a] = { name, wuxing }; m[b] = { name, wuxing };
	});
	return m;
})();

// ── 三合四大局立向（正统古法）：向法 → 向坐之十二长生阶（由长生环反推双山）──
//   四正向:正生=长生、正旺=帝旺、正墓=墓、正养=养;借库/文库:自生=临官、自旺=衰、沐浴=沐浴、衰向=衰。
export const SANHE_XIANGFA_STAGE = {
	正生向: '长生', 正旺向: '帝旺', 正墓向: '墓', 正养向: '养',
	自生向: '临官', 自旺向: '衰', 沐浴向: '沐浴', 衰向: '衰',
};
export const SANHE_XIANGFA_LIST = ['正生向', '正旺向', '正墓向', '正养向', '自生向', '自旺向', '沐浴向', '衰向'];
// 四正向来去水提要（救贫水法 5.4/5.10）。
export const SANHE_XIANGFA_NOTE = {
	正生向: '向坐长生·右水倒左·临官帝旺方来·出墓库 → 丁财大旺、福寿',
	正旺向: '向坐帝旺·左水倒右·长生养方来·出墓库 → 速发财丁',
	正墓向: '向坐墓库·生旺临官水朝堂·出绝方 → 旺丁聚财福厚',
	正养向: '向坐养·生旺水来·出胎绝方 → 富贵双全、人丁贵显',
	自生向: '向坐临官·借隔局之库消水（禄存流尽佩金鱼）',
	自旺向: '向坐衰位·借库消水（自旺）',
	沐浴向: '向坐沐浴·水出沐浴（文库消水，绝处逢生，最忌差错）',
	衰向: '向坐衰·借库消水',
};

// ── 黄泉八曜煞（正统古法）：坐山卦 → 忌之官鬼爻方（见水来/路冲/恶砂大凶）──
//   坎龙(辰)坤兔(卯)震山猴(申)巽鸡(酉)乾马(午)兑蛇(巳)艮虎(寅)离猪(亥)。
export const BA_YAO_SHA = { 坎: '辰', 坤: '卯', 震: '申', 巽: '酉', 乾: '午', 兑: '巳', 艮: '寅', 离: '亥' };
// 四大黄泉（杀人/救贫黄泉，双关）：向 → 忌之方（去水大凶）。庚丁坤·乙丙巽·甲癸艮·辛壬乾。
export const SI_DA_HUANGQUAN = { 庚: '坤', 丁: '坤', 乙: '巽', 丙: '巽', 甲: '艮', 癸: '艮', 辛: '乾', 壬: '乾' };

// ── 玄空大卦 六十四卦（正统古法）：下卦(内)×上卦(外) → 重卦名 ─────────────────
export const GUA8_XIANTIAN_NUM = { 乾: 1, 兑: 2, 离: 3, 震: 4, 巽: 5, 坎: 6, 艮: 7, 坤: 8 };   // 先天数(邵雍)
export const GUA8_BIN = {   // [下,中,上] 阳1阴0
	乾: [1, 1, 1], 兑: [1, 1, 0], 离: [1, 0, 1], 震: [1, 0, 0],
	巽: [0, 1, 1], 坎: [0, 1, 0], 艮: [0, 0, 1], 坤: [0, 0, 0],
};
export const GUA64_TABLE = {
	乾: { 乾: '乾为天', 兑: '泽天夬', 离: '火天大有', 震: '雷天大壮', 巽: '风天小畜', 坎: '水天需', 艮: '山天大畜', 坤: '地天泰' },
	兑: { 乾: '天泽履', 兑: '兑为泽', 离: '火泽睽', 震: '雷泽归妹', 巽: '风泽中孚', 坎: '水泽节', 艮: '山泽损', 坤: '地泽临' },
	离: { 乾: '天火同人', 兑: '泽火革', 离: '离为火', 震: '雷火丰', 巽: '风火家人', 坎: '水火既济', 艮: '山火贲', 坤: '地火明夷' },
	震: { 乾: '天雷无妄', 兑: '泽雷随', 离: '火雷噬嗑', 震: '震为雷', 巽: '风雷益', 坎: '水雷屯', 艮: '山雷颐', 坤: '地雷复' },
	巽: { 乾: '天风姤', 兑: '泽风大过', 离: '火风鼎', 震: '雷风恒', 巽: '巽为风', 坎: '水风井', 艮: '山风蛊', 坤: '地风升' },
	坎: { 乾: '天水讼', 兑: '泽水困', 离: '火水未济', 震: '雷水解', 巽: '风水涣', 坎: '坎为水', 艮: '山水蒙', 坤: '地水师' },
	艮: { 乾: '天山遁', 兑: '泽山咸', 离: '火山旅', 震: '雷山小过', 巽: '风山渐', 坎: '水山蹇', 艮: '艮为山', 坤: '地山谦' },
	坤: { 乾: '天地否', 兑: '泽地萃', 离: '火地晋', 震: '雷地豫', 巽: '风地观', 坎: '水地比', 艮: '山地剥', 坤: '坤为地' },
};
// 卦运合十对（正统古法）：1⇄9·2⇄8·3⇄7·4⇄6·5居中；上元1-4(+上五)、下元6-9(+下五)。
export const GUAYUN_PAIRS = { 1: 9, 9: 1, 2: 8, 8: 2, 3: 7, 7: 3, 4: 6, 6: 4, 5: 5 };
export const GUAYUN_YUAN = { 1: '上元', 2: '上元', 3: '上元', 4: '上元', 5: '中(上下五分)', 6: '下元', 7: '下元', 8: '下元', 9: '下元' };

// ── 干支基础（60 甲子·地支方位，择日/线法共用）────────────────────────────
export const TIANGAN = ['甲', '乙', '丙', '丁', '戊', '己', '庚', '辛', '壬', '癸'];
export const DIZHI = ['子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥'];
export const GANZHI_60 = (()=>{ const out = []; for (let i = 0; i < 60; i++) { out.push(TIANGAN[i % 10] + DIZHI[i % 12]); } return out; })();
// 地支 → 后天宫（方位盘落宫）。子1·丑寅8艮·卯3·辰巳4巽·午9·未申2坤·酉7·戌亥6乾。
export const ZHI_TO_GONG = { 子: 1, 丑: 8, 寅: 8, 卯: 3, 辰: 4, 巳: 4, 午: 9, 未: 2, 申: 2, 酉: 7, 戌: 6, 亥: 6 };
// 地支 → 二十四山中该支之山（本支即山名）。
export const ZHI_CHONG = { 子: '午', 午: '子', 卯: '酉', 酉: '卯', 寅: '申', 申: '寅', 巳: '亥', 亥: '巳', 辰: '戌', 戌: '辰', 丑: '未', 未: '丑' };
// 地支三合局（年支定局，三煞用）。
export const ZHI_SANHE_JU = {
	申: '水', 子: '水', 辰: '水', 寅: '火', 午: '火', 戌: '火',
	亥: '木', 卯: '木', 未: '木', 巳: '金', 酉: '金', 丑: '金',
};

// ── 择日 · 年家凶煞（正统古法）───────────────────────────────────────────
// 三煞：三合局帝旺对冲之三山。水局(申子辰)煞南巳午未·火局(寅午戌)煞北亥子丑·木局(亥卯未)煞西申酉戌·金局(巳酉丑)煞东寅卯辰。
export const SANSHA_BY_JU = { 水: ['巳', '午', '未'], 火: ['亥', '子', '丑'], 木: ['申', '酉', '戌'], 金: ['寅', '卯', '辰'] };
// 十二岁君神（自太岁支顺行）：太岁·太阳·丧门·太阴·官符·死符·岁破·龙德·白虎·福德·吊客·病符。
export const TWELVE_YEAR_GODS = ['太岁', '太阳', '丧门', '太阴', '官符', '死符', '岁破', '龙德', '白虎', '福德', '吊客', '病符'];
export const YEAR_GOD_JX = {
	太岁: 'caution', 太阳: 'good', 丧门: 'bad', 太阴: 'good', 官符: 'bad', 死符: 'bad',
	岁破: 'bad', 龙德: 'good', 白虎: 'bad', 福德: 'good', 吊客: 'bad', 病符: 'bad',
};

// ── 择日 · 建除十二神（正统古法）：建日=日支==月建支，顺布 ─────────────────
export const JIANCHU_12 = ['建', '除', '满', '平', '定', '执', '破', '危', '成', '收', '开', '闭'];
export const JIANCHU_JX = {
	建: 'neutral', 除: 'good', 满: 'neutral', 平: 'neutral', 定: 'good', 执: 'good',
	破: 'bad', 危: 'neutral', 成: 'good', 收: 'neutral', 开: 'good', 闭: 'bad',
};

// ── 择日 · 黄道黑道十二值神（正统古法）────────────────────────────────────
export const HUANG_HEI_ORDER = ['青龙', '明堂', '天刑', '朱雀', '金匮', '天德', '白虎', '玉堂', '天牢', '玄武', '司命', '勾陈'];
export const HUANGDAO_SET = new Set(['青龙', '明堂', '金匮', '天德', '玉堂', '司命']);
// 青龙起支（按月支）：子午→申·丑未→戌·寅申→子·卯酉→寅·辰戌→辰·巳亥→午。
export const QINGLONG_START = { 子: '申', 午: '申', 丑: '戌', 未: '戌', 寅: '子', 申: '子', 卯: '寅', 酉: '寅', 辰: '辰', 戌: '辰', 巳: '午', 亥: '午' };

// ── 择日 · 二十八宿值日（正统古法）：四象七宿 + 吉凶（吉宿造葬多用）──────────
export const XIU_28 = [
	{ n: '角', x: '东青龙', jx: 'good' }, { n: '亢', x: '东青龙', jx: 'bad' }, { n: '氐', x: '东青龙', jx: 'neutral' },
	{ n: '房', x: '东青龙', jx: 'good' }, { n: '心', x: '东青龙', jx: 'neutral' }, { n: '尾', x: '东青龙', jx: 'good' }, { n: '箕', x: '东青龙', jx: 'good' },
	{ n: '斗', x: '北玄武', jx: 'good' }, { n: '牛', x: '北玄武', jx: 'bad' }, { n: '女', x: '北玄武', jx: 'bad' },
	{ n: '虚', x: '北玄武', jx: 'neutral' }, { n: '危', x: '北玄武', jx: 'neutral' }, { n: '室', x: '北玄武', jx: 'good' }, { n: '壁', x: '北玄武', jx: 'good' },
	{ n: '奎', x: '西白虎', jx: 'good' }, { n: '娄', x: '西白虎', jx: 'good' }, { n: '胃', x: '西白虎', jx: 'good' },
	{ n: '昴', x: '西白虎', jx: 'neutral' }, { n: '毕', x: '西白虎', jx: 'good' }, { n: '觜', x: '西白虎', jx: 'neutral' }, { n: '参', x: '西白虎', jx: 'neutral' },
	{ n: '井', x: '南朱雀', jx: 'good' }, { n: '鬼', x: '南朱雀', jx: 'bad' }, { n: '柳', x: '南朱雀', jx: 'neutral' },
	{ n: '星', x: '南朱雀', jx: 'bad' }, { n: '张', x: '南朱雀', jx: 'good' }, { n: '翼', x: '南朱雀', jx: 'neutral' }, { n: '轸', x: '南朱雀', jx: 'good' },
];

// ── 三合线法 · 穿山72龙/透地60龙/120分金（正统古法，通行三合盘·需按门派校）──
// 分金天干旺相/孤虚/空亡（口诀「取丙丁庚辛旺相、避甲乙戊己壬癸孤虚空亡」）。
export const FENJIN_GAN_JX = {
	丙: 'good', 丁: 'good', 庚: 'good', 辛: 'good',   // 旺相
	甲: 'bad', 乙: 'bad', 壬: 'bad', 癸: 'bad',        // 孤虚/旁气
	戊: 'void', 己: 'void',                            // 龟甲空亡
};
// 起点常量（子山正中=0°；通行盘 甲子起壬山初）。度数分区在 liqiCore 用之，皆注需按门派校。
export const XIANFA_START = { 子中: 0, chuanshanStartDeg: 337.5, toudiStartDeg: 337.5, fenjinStartDeg: 337.5 };

// ── 形势派参考（正统体系，判定清单用；纯参考文本）────────────────────────
export const XINGSHI_9STAR = [   // 寻龙九星形体（2.2，廖公《泄天机》）
	{ name: '贪狼', wuxing: '木', shape: '尖耸如笋、文笔', jx: 'good', zhu: '文贵' },
	{ name: '巨门', wuxing: '土', shape: '方平如屏、御屏', jx: 'good', zhu: '财富禄位' },
	{ name: '禄存', wuxing: '土', shape: '顿鼓多脚、犬牙', jx: 'bad', zhu: '病讼' },
	{ name: '文曲', wuxing: '水', shape: '摆动如蛇、波浪', jx: 'neutral', zhu: '淫荡漂荡' },
	{ name: '廉贞', wuxing: '火', shape: '尖峭破碎、火焰', jx: 'bad', zhu: '凶（作祖山则贵）' },
	{ name: '武曲', wuxing: '金', shape: '圆顶如钟釜', jx: 'good', zhu: '武贵富足' },
	{ name: '破军', wuxing: '金', shape: '破碎欹斜如破伞', jx: 'bad', zhu: '败绝' },
	{ name: '左辅', wuxing: '金土', shape: '幞头馒头', jx: 'good', zhu: '辅佐' },
	{ name: '右弼', wuxing: '水', shape: '平地隐脉、无形', jx: 'neutral', zhu: '隐曜' },
];
export const LONG_RUSHOU_5 = ['直龙（正受·气壮）', '横龙（旁落·结侧）', '回龙（顾祖·盘旋）', '飞龙（高结·仰势）', '潜龙（平地隐脉·铺毡结突）'];
export const LONG_5SHI = ['正势（朝南）', '侧势', '逆势', '顺势', '回势'];
export const XUE_4TYPE = [
	{ name: '窝穴', desc: '凹窝如燕巢，多在高山（深窝/浅窝/阔窝/狭窝）' },
	{ name: '钳穴', desc: '双臂相钳开口向外（直钳/曲钳/长钳/短钳/双钳）' },
	{ name: '乳穴', desc: '中间微突如乳（长乳/短乳/大乳/小乳/双乳/三乳）' },
	{ name: '突穴', desc: '平地圆突如泡，多在平洋（大突/小突/双突/三突）' },
];
export const XUE_5STAR = ['金星穴（圆·窝/突）', '木星穴（直·难结）', '水星穴（曲动·结泡）', '火星穴（尖·不结取荫）', '土星穴（方·窝/角）'];
export const DINGXUE_9 = ['太极定穴', '两仪（阴阳）定穴', '三停（高中低）定穴', '四杀（藏杀避煞）定穴', '八卦定穴', '枕乐（靠乐山）定穴', '朝山定穴', '天心（十道）定穴', '界水（合襟）定穴'];
export const ZHENGXUE_10 = ['朝山证', '案山证', '乐山证', '鬼星证', '龙虎证', '缠护证', '水势证', '明堂证', '唇毡证', '天心十道证'];
export const DAOZHANG_12 = [   // 杨公倒杖十二法（2.10）
	{ name: '顺杖', use: '脉缓', pt: '顺脉直放，承其来气' }, { name: '逆杖', use: '脉急', pt: '逆脉挫放，杀其冲气' },
	{ name: '缩杖', use: '脉直急', pt: '缩上就脉头，避硬' }, { name: '缀杖', use: '脉短促', pt: '缀下垂就，接余气' },
	{ name: '开杖', use: '脉粗顽', pt: '分开放两旁，泄其杀' }, { name: '穿杖', use: '脉横', pt: '横穿取气，截受' },
	{ name: '离杖', use: '脉脱卸', pt: '离脉就堂，乘脱气' }, { name: '没杖', use: '脉藏', pt: '深取没入，求隐气' },
	{ name: '对杖', use: '脉正', pt: '正对中放' }, { name: '截杖', use: '脉长', pt: '截其一段受' },
	{ name: '犯杖', use: '脉斜', pt: '犯煞调整' }, { name: '顿杖', use: '脉顿驻', pt: '就驻气顿放' },
];
export const SHA_NAMES = {
	贵砂: '文笔峰·三台·笔架·诰轴·华盖·御屏·天马·旗·鼓·金箱玉印·笏·剑（主功名权位）',
	富砂: '仓·库·堆·柜·米堆·金钟·玉釜·眠弓·案如几席（主财帛）',
	水口砂: '华表·捍门·罗星·北辰·禽星·狮象把门（关锁去水，最贵）',
	凶砂: '探头砂(盗)·献花砂(淫)·反背砂(忤逆)·断头破碎砂(败绝)·刀枪砂(伤)·扫帚砂(败财)·孝服砂(哭丧)·提箩砂(贫)',
};
export const SHUICHENG_5 = [
	{ name: '金城', shape: '圆抱', jx: 'good' }, { name: '水城', shape: '屈曲', jx: 'good' },
	{ name: '木城', shape: '直', jx: 'neutral' }, { name: '火城', shape: '尖射', jx: 'bad' }, { name: '土城', shape: '方正横抱', jx: 'neutral' },
];
export const SHUI_12 = {
	吉水: '朝水·聚水·环抱水(玉带/金城)·绕城水·衣带水·仓板水',
	凶水: '反弓水·直射水·穿心水·割脚水·淋头水·瀑面漏腮水·刑杀水',
};

// ═══════════════════════════════════════════════════════════════════════════
// 综合罗经 / 玄空门派 / 玄空六法 / 命理派 / 形体图 / 六十四卦圆图（第二批补齐）
// ═══════════════════════════════════════════════════════════════════════════

// ── 后天九宫中心度数（0°=正北，顺时针）；八卦层/九星层共用 ────────────────
export const GONG_CENTER_DEG = { 1: 0, 8: 45, 3: 90, 4: 135, 9: 180, 2: 225, 7: 270, 6: 315 };
// 先天八卦方位度数（乾南·坤北·离东·坎西，由 XIANTIAN_POS 落宫换算）。
export const XIANTIAN_DEG = (()=>{
	const out = {};
	Object.keys(XIANTIAN_POS).forEach((g)=>{ out[g] = GONG_CENTER_DEG[XIANTIAN_POS[g]]; });
	return out;
})();
// 八卦五行（命理派/六法卦气共用）。
export const GUA8_WUXING = { 乾: '金', 兑: '金', 离: '火', 震: '木', 巽: '木', 坎: '水', 艮: '土', 坤: '土' };
// 五行方位/颜色/河图数（1.1）。
export const WUXING_FANGWEI = { 木: '东', 火: '南', 土: '中', 金: '西', 水: '北' };
export const WUXING_COLOR = { 木: '青绿', 火: '赤红', 土: '土黄', 金: '素白', 水: '玄黑' };
export const WUXING_HEX = { 木: '#3f9a63', 火: '#c0392b', 土: '#b8862f', 金: '#8b93a5', 水: '#2f5fa8' };
export const WUXING_HETU_NUM = { 水: '一·六', 火: '二·七', 木: '三·八', 金: '四·九', 土: '五·十' };
export const WUXING_SHENG = { 木: '火', 火: '土', 土: '金', 金: '水', 水: '木' };   // 我生
export const WUXING_KE = { 木: '土', 土: '水', 水: '火', 火: '金', 金: '木' };       // 我克

// ── 三针偏移（正针格龙立向 / 人盘中针消砂 −7.5° / 天盘缝针纳水 +7.5°）──────
export const NEEDLE_OFFSET = { zheng: 0, ren: -7.5, feng: 7.5 };
export const NEEDLE_USE = {
	zheng: '地盘正针 · 格龙立向定坐向',
	ren: '人盘中针 · 消砂（较正针退半山 7.5°）',
	feng: '天盘缝针 · 纳水（较正针进半山 7.5°）',
};

// 内部：环形取模与等分切段（仅本文件用，不导出）。
function _norm360(d) { return ((Number(d) % 360) + 360) % 360; }
// 由 24 山生成一圈山格（offsetDeg = 三针偏移）。
function _shanRing(offsetDeg) {
	return SHAN_ORDER.map((s)=>{
		const c = _norm360(SHAN_CENTER_DEG[s] + offsetDeg);
		const meta = SHAN_24[s] || [];
		return { label: s, deg0: _norm360(c - 7.5), deg1: _norm360(c + 7.5), gong: meta[0], yuanlong: meta[1], yinyang: meta[2] };
	});
}
// 由 8 卦生成一圈卦格（degMap: 卦→中心度）。
function _guaRing(degMap, extra) {
	return Object.keys(degMap).map((g)=>{
		const c = degMap[g];
		return { label: g, deg0: _norm360(c - 22.5), deg1: _norm360(c + 22.5), ...(extra ? extra(g) : null) };
	}).sort((a, b)=>a.deg0 - b.deg0);
}

// ── 六十四卦圆图（6.1 · 伏羲先天方圆图之圆图，绕周天）──────────────────────
// 结构（可推不臆造）：八卦宫按先天方位各辖 45°（＝三山），宫内八重卦依先天序
// 乾兑离震巽坎艮坤排布；东半(乾兑离震宫)度数递减、西半(巽坎艮坤宫)递增，
// 即传统圆图「左阳右阴」两仪分翼。起点 337.5°（坤宫首卦天地否）——恰合古法
// 「自坤(北偏)起顺布」，且八宫界与二十四山界严丝合缝（坤宫＝壬子癸三山）。
// 每卦 5.625°、每爻 0.9375°。卦运/爻序方向各家易盘略异，须按所宗盘校。
export const GUA64_CIRCLE_META = {
	startDeg: 337.5, clockwise: true, sectorDeg: 45, degPerGua: 5.625, degPerYao: 0.9375,
	note: '伏羲先天圆图·八宫各辖三山；须按所宗易盘校',
};
export const XIANTIAN_ORDER8 = ['乾', '兑', '离', '震', '巽', '坎', '艮', '坤'];   // 先天序（邵雍）
export const YAO_NAMES = ['初', '二', '三', '四', '五', '上'];
export const GUA64_CIRCLE = (()=>{
	const EAST = new Set(['乾', '兑', '离', '震']);   // 东半：宫内度数递减
	const out = [];
	XIANTIAN_ORDER8.forEach((lower)=>{
		const c = XIANTIAN_DEG[lower];
		const desc = EAST.has(lower);
		XIANTIAN_ORDER8.forEach((upper, j)=>{
			const d0 = desc ? (c + 22.5 - (j + 1) * 5.625) : (c - 22.5 + j * 5.625);
			out.push({
				name: GUA64_TABLE[lower][upper], lower, upper,
				sector: lower, sectorDeg: c, descending: desc,
				deg0: _norm360(d0), deg1: _norm360(d0 + 5.625),
				center: _norm360(d0 + 2.8125),
			});
		});
	});
	// 按起点 337.5° 顺时针排序，index 即圆图顺布序（0＝天地否）。
	const key = (d)=>_norm360(d - 337.5);
	out.sort((a, b)=>key(a.deg0) - key(b.deg0));
	out.forEach((g, i)=>{ g.index = i; });
	return out;
})();

// ── 二十八宿层（10.6）：四象七宿等分示意，逆时针（房居卯·虚居子·昴居酉·星居午）
// ⚠ 古籍只给四象七宿与吉凶，无周天盈缩实度 → 此层为等分近似，UI 须明标。
export const XIU28_RING = (()=>{
	const SEC = { 东青龙: 90, 北玄武: 0, 西白虎: 270, 南朱雀: 180 };
	const W = 360 / 28;
	const out = [];
	['东青龙', '北玄武', '西白虎', '南朱雀'].forEach((x)=>{
		const start = SEC[x] + 45;   // 象界上缘，逆时针递减
		XIU_28.filter((u)=>u.x === x).forEach((u, i)=>{
			const d1 = start - i * W;
			out.push({ label: u.n, xiang: x, jx: u.jx, deg0: _norm360(d1 - W), deg1: _norm360(d1) });
		});
	});
	return out.sort((a, b)=>a.deg0 - b.deg0);
})();

// ── 线法三层（穿山72/透地60/120分金）环格；与 liqiCore 的 chuanshanAt/toudiAt/
//    fenjinAt 同源同起点(337.5°甲子起壬山初)，测试逐格对拍防双写漂移。────────
function _ganzhiRing(count, degPer, decorate) {
	const out = [];
	for (let i = 0; i < count; i++) {
		const gz = GANZHI_60[i % 60];
		out.push({ label: gz, ganzhi: gz, deg0: _norm360(337.5 + i * degPer), deg1: _norm360(337.5 + (i + 1) * degPer), ...(decorate ? decorate(i, gz) : null) });
	}
	return out;
}
export const CHUANSHAN_72 = _ganzhiRing(72, 5, (i)=>({ sub: i % 3, jx: (i % 3) === 1 ? 'good' : 'bad', positional: (i % 3) === 1 ? '正气旺相' : '孤虚（边龙）' }));
export const TOUDI_60 = _ganzhiRing(60, 6, (i, gz)=>{ const kong = gz[0] === '甲' || gz[0] === '己'; return { kong, jx: kong ? 'bad' : 'good', nayin: NAYIN_60[gz] || null }; });
export const FENJIN_120 = _ganzhiRing(120, 3, (i, gz)=>{
	const sub = i % 5; const wang = sub >= 1 && sub <= 3; const ganJx = FENJIN_GAN_JX[gz[0]] || 'neutral';
	return { sub, ganJx, positional: wang ? '旺相(取)' : '空亡(避)', jx: (wang && ganJx === 'good') ? 'good' : ((!wang || ganJx === 'void') ? 'bad' : 'neutral') };
});

// ── P0-1 罗盘层序表（10.7 自内向外·综合盘典型）──────────────────────────
// r0/r1 = 归一化半径（0=盘心 1=外缘），驱动 LuopanDial 多环渲染，勿硬编码段数。
export const LUOPAN_LAYERS = [
	{ key: 'tianchi', label: '天池', type: 'text', r0: 0, r1: 0.1, use: '磁针指南·定子午线', cells: [] },
	{ key: 'xiantian', label: '先天八卦', type: 'ring', r0: 0.1, r1: 0.15, use: '先天为体·乾南坤北',
		cells: _guaRing(XIANTIAN_DEG, (g)=>({ wuxing: GUA8_WUXING[g], num: GUA8_XIANTIAN_NUM[g] })) },
	{ key: 'houtian', label: '后天八卦', type: 'ring', r0: 0.15, r1: 0.2, use: '后天为用·坎北离南',
		cells: _guaRing((()=>{ const m = {}; Object.keys(HOUTIAN_POS).forEach((g)=>{ m[g] = GONG_CENTER_DEG[HOUTIAN_POS[g]]; }); return m; })(), (g)=>({ wuxing: GUA8_WUXING[g], gong: HOUTIAN_POS[g] })) },
	{ key: 'luoshu', label: '洛书九星 · 三元九运', type: 'ring', r0: 0.2, r1: 0.255, use: '九星入中飞泊·元运当令',
		cells: Object.keys(GONG_CENTER_DEG).map((n)=>{
			const g = +n;
			return { label: ZIBAI_STAR[g], deg0: _norm360(GONG_CENTER_DEG[g] - 22.5), deg1: _norm360(GONG_CENTER_DEG[g] + 22.5), gong: g, jx: ZIBAI_JX[g], yun: YUN_YEARS[g] ? `${g}运 ${YUN_YEARS[g][0]}–${YUN_YEARS[g][1]}` : '' };
		}).sort((a, b)=>a.deg0 - b.deg0) },
	{ key: 'dipan', label: '地盘正针 · 二十四山', type: 'needle', needle: 'zheng', main: true, r0: 0.255, r1: 0.355,
		use: NEEDLE_USE.zheng, cells: _shanRing(0) },
	{ key: 'chuanshan', label: '穿山七十二龙', type: 'ring', r0: 0.355, r1: 0.43, use: '格入首龙·中龙正气边龙孤虚', cells: CHUANSHAN_72 },
	{ key: 'toudi', label: '透地六十龙', type: 'ring', r0: 0.43, r1: 0.505, use: '定中气·取纳音·甲己龙空亡', cells: TOUDI_60 },
	{ key: 'renpan', label: '人盘中针 · 二十四山', type: 'needle', needle: 'ren', r0: 0.505, r1: 0.58,
		use: NEEDLE_USE.ren, cells: _shanRing(NEEDLE_OFFSET.ren) },
	{ key: 'fenjin', label: '百二十分金', type: 'ring', r0: 0.58, r1: 0.655, use: '坐度细分·避空亡骑缝', cells: FENJIN_120 },
	{ key: 'tianpan', label: '天盘缝针 · 二十四山', type: 'needle', needle: 'feng', r0: 0.655, r1: 0.73,
		use: NEEDLE_USE.feng, cells: _shanRing(NEEDLE_OFFSET.feng) },
	{ key: 'gua64', label: '六十四卦 · 三百八十四爻', type: 'ring', r0: 0.73, r1: 0.865, use: '玄空大卦三元盘·线度分金',
		cells: GUA64_CIRCLE.map((g)=>({ label: g.name, deg0: g.deg0, deg1: g.deg1, sector: g.sector })) },
	{ key: 'xiu28', label: '二十八宿', type: 'ring', r0: 0.865, r1: 0.925, use: '四象七宿·天星（等分示意·非盈缩实度）', approx: true, cells: XIU28_RING },
	{ key: 'zhoutian', label: '周天三百六十度', type: 'tick', r0: 0.925, r1: 1, use: '外缘刻度', tick: { major: 15, minor: 5 }, cells: [] },
];
// 默认可见层（防信息过载）：三针 + 天池 + 周天。
export const LUOPAN_DEFAULT_LAYERS = ['tianchi', 'dipan', 'renpan', 'tianpan', 'zhoutian'];

// ── P0-2 玄空门派（8.5）────────────────────────────────────────────────────
// 🔴 古籍只列「分歧维度」，从未把某度界/某替星表指名归某派 → 严禁臆造映射。
//    唯一明载可联动：中州「五黄分属二·八」＝两元八运。其余维度独立可调。
export const XUANKONG_SCHOOLS = [
	{ key: 'shen', name: '沈氏（无锡）', person: '沈竹礽', desc: '今最通行，公开下卦/起星/替卦全体系；本模块现有算法即此一路。',
		focus: ['下卦替卦公开体系', '三盘九宫飞泊'], auto: null },
	{ key: 'wuchang', name: '无常（章仲山）', person: '章仲山', desc: '飞星正源，重心法、阴阳动静、峦头合十，秘而少宣。',
		focus: ['心法', '阴阳动静', '峦头合十'], auto: null },
	{ key: 'zhongzhou', name: '中州（王亭之）', person: '王亭之', desc: '重七星打劫、城门、峦头理气合参；五黄分属二·八运，更强调三元龙阴阳起星。',
		focus: ['七星打劫', '城门', '三元龙阴阳起星'], auto: { wuHuangSplit: 'liangyuan' } },
	{ key: 'guangdong', name: '广东（岭南）', person: '', desc: '岭南传承，重兼向替卦之实用。',
		focus: ['兼向替卦实用'], auto: null },
];
export const XUANKONG_SCHOOL_KEYS = XUANKONG_SCHOOLS.map((s)=>s.key);
// 兼向起替度界：各家不一，独立可选，与门派解耦。
export const JIAN_BOUNDARY_OPTIONS = [
	{ value: 3, label: '出中 3°' }, { value: 4.5, label: '出中 4.5°' }, { value: 6, label: '出中 6°' },
];
export const JIAN_BOUNDARY_NOTE = '起替度界各家不一，请按所宗罗盘选定。';
// 五黄分运：下卦运（沈氏多用）/ 两元八运（五黄分属二·八）。仅改元属标注，不动飞星。
export const WUHUANG_SPLIT_OPTIONS = [
	{ value: 'xiagua', label: '下卦运（五运自成一运）', desc: '五运二十年整体作五运论，元属「中（上下五分）」。' },
	{ value: 'liangyuan', label: '两元八运（五黄分属二·八）', desc: '五运前十年归二运（上元）、后十年归八运（下元），周天只作八运论。' },
];
// 两元八运下五运的前后十年归属。
export const WUHUANG_LIANGYUAN = { first: { yun: 2, yuan: '上元', years: [1944, 1953] }, second: { yun: 8, yuan: '下元', years: [1954, 1963] } };

// ── P0-3 玄空六法（8.6 · 谈养吾）────────────────────────────────────────
export const LIUFA_ITEMS = [
	{ key: 'lingzheng', name: '玄空（零正）', desc: '当元正神、零神之辨；正神宜山、零神宜水，「正神正位装、拨水入零堂」。' },
	{ key: 'cixiong', name: '雌雄', desc: '山水阴阳交媾（雌雄交会），龙、向、水阴阳相配。' },
	{ key: 'jinlong', name: '金龙', desc: '「金龙一经一纬」动而不动之机，辨动静以定挨排。' },
	{ key: 'aixing', name: '挨星', desc: '大卦挨星（非飞星），以卦气挨排，论生旺衰死。' },
	{ key: 'chengmen', name: '城门', desc: '向旁通气放水之诀，收城门一卦之旺气。' },
	{ key: 'taisui', name: '太岁', desc: '以太岁加临定流年应期吉凶。' },
];
export const LIUFA_NOTE = '六法以零正为体、挨星为用，重山水雌雄与金龙动静；不排三盘九宫，与飞星分流。';
// 卦气生旺衰死四档（六法挨星用，按当元卦运与元运之距定档，不套飞星星表）。
export const GUAQI_STAGES = [
	{ key: 'wang', name: '旺', jx: 'good', desc: '当元当令之气' },
	{ key: 'sheng', name: '生', jx: 'good', desc: '未来将令之气（进气）' },
	{ key: 'shuai', name: '衰', jx: 'neutral', desc: '甫过之气（退气）' },
	{ key: 'si', name: '死', jx: 'bad', desc: '久过失令之气' },
];

// ── P0-4 命理派（8.4 · 以命配宅，不另起方位盘）────────────────────────────
export const MINGLI_NOTE = '此派不另起方位盘，以命卦、喜用配宅之坐向与吉方，依附八宅、玄空、三合而行。';
// 命卦（八宅命卦，五数寄坤/艮）→ 五行 / 宜居方位 / 宜用色。
export const MINGLI_GUA_PROFILE = (()=>{
	const out = {};
	Object.keys(GUA8_WUXING).forEach((g)=>{
		const wx = GUA8_WUXING[g];
		out[g] = { wuxing: wx, fangwei: WUXING_FANGWEI[wx], color: WUXING_COLOR[wx], hex: WUXING_HEX[wx], hetu: WUXING_HETU_NUM[wx], sheng: WUXING_SHENG[wx], ke: WUXING_KE[wx] };
	});
	return out;
})();
// 人—宅五行关系口径（宅卦五行 对 命卦五行）。
export const MINGLI_RELATION = {
	same: { label: '比和', jx: 'good', text: '宅命同气，安稳相守。' },
	zhaiShengMing: { label: '宅生命', jx: 'good', text: '宅气生扶命主，最为得力。' },
	mingShengZhai: { label: '命生宅', jx: 'neutral', text: '命主泄气养宅，费力而可居。' },
	zhaiKeMing: { label: '宅克命', jx: 'bad', text: '宅气克身，久居不利，宜化不宜斗。' },
	mingKeZhai: { label: '命克宅', jx: 'neutral', text: '命主制宅，可用而需调。' },
};

// ── P0-5 形体图（2.2/2.9/2.10/2.12）──────────────────────────────────────
// 忠实转绘既有文字形体，不新增古籍外形体。统一画布 100×60，地平线 y=56。
// path 仅作形体示意（山形轮廓/水城走势/杖法示意），非实测地形。
export const XINGSHI_SHAPES = {
	// 寻龙九星形体（对应 XINGSHI_9STAR 之 shape 文字）
	long9: [
		{ key: '贪狼', d: 'M10 56 C30 51 41 39 50 8 C59 39 70 51 90 56 Z' },
		{ key: '巨门', d: 'M10 56 L17 22 L83 22 L90 56 Z' },
		{ key: '禄存', d: 'M14 56 C14 27 30 15 50 15 C70 15 86 27 86 56 Z', feet: 'M14 56 L22 46 L30 56 L38 46 L46 56 L54 46 L62 56 L70 46 L78 56 L86 46' },
		{ key: '文曲', d: 'M4 44 C18 28 28 52 42 38 C56 24 66 48 80 36 C86 31 92 35 96 33', stroke: true },
		{ key: '廉贞', d: 'M6 56 L19 30 L27 42 L39 12 L49 34 L60 6 L71 40 L80 27 L94 56 Z' },
		{ key: '武曲', d: 'M14 56 C14 25 30 13 50 13 C70 13 86 25 86 56 Z' },
		{ key: '破军', d: 'M8 56 L25 41 L33 47 L43 19 L55 31 L61 23 L70 45 L79 35 L92 56 Z' },
		{ key: '左辅', d: 'M10 56 C10 33 21 23 33 23 C41 23 46 27 50 33 C54 25 62 17 72 17 C84 17 90 31 90 56 Z' },
		{ key: '右弼', d: 'M4 49 C24 45 40 47 52 44 C66 41 82 45 96 43', stroke: true, dash: '5 4' },
	],
	// 窝钳乳突四穴形（2.9）——虚线为界水合襟，圆点为穴心。
	xue4: [
		{ key: '窝穴', d: 'M6 20 C20 18 28 44 50 44 C72 44 80 18 94 20', stroke: true, pt: [50, 38] },
		{ key: '钳穴', d: 'M30 14 C30 42 39 51 50 51 C61 51 70 42 70 14', stroke: true, stem: 'M50 12 L50 30', pt: [50, 43] },
		{ key: '乳穴', d: 'M10 50 C30 48 36 22 50 22 C64 22 70 48 90 50', stroke: true, pt: [50, 33] },
		{ key: '突穴', d: 'M4 46 L33 46 C37 30 63 30 67 46 L96 46', stroke: true, pt: [50, 40] },
	],
	// 水城五星（2.12）——曲线为水，圆点为穴/宅。
	shui5: [
		{ key: '金城', d: 'M6 16 C18 52 82 52 94 16', stroke: true, pt: [50, 26] },
		{ key: '水城', d: 'M4 40 C20 18 30 52 46 32 C60 14 70 46 84 28 C88 23 92 26 96 24', stroke: true, pt: [50, 50] },
		{ key: '木城', d: 'M6 34 L94 34', stroke: true, pt: [50, 48] },
		{ key: '火城', d: 'M4 54 L64 20', stroke: true, barb: 'M64 20 L52 22 M64 20 L58 32', pt: [76, 14] },
		{ key: '土城', d: 'M10 14 L10 44 L90 44 L90 14', stroke: true, pt: [50, 28] },
	],
	// 倒杖十二法（2.10）——mai=来脉示意，zhang=下杖示意（虚线），pt=放棺处。
	daozhang12: [
		{ key: '顺杖', mai: 'M8 12 C30 20 46 34 92 44', zhang: 'M56 34 L74 40', pt: [66, 38] },
		{ key: '逆杖', mai: 'M8 8 C26 18 40 34 60 50', zhang: 'M60 46 L42 34', pt: [50, 40] },
		{ key: '缩杖', mai: 'M8 10 C24 16 40 30 88 46', zhang: 'M30 20 L44 26', pt: [34, 22] },
		{ key: '缀杖', mai: 'M8 12 C28 18 44 30 88 40', zhang: 'M70 36 L78 50', pt: [76, 47] },
		{ key: '开杖', mai: 'M50 6 L50 30', zhang: 'M50 30 L26 48 M50 30 L74 48', pt: [50, 30] },
		{ key: '穿杖', mai: 'M6 28 L94 28', zhang: 'M50 8 L50 48', pt: [50, 28] },
		{ key: '离杖', mai: 'M8 10 C26 18 40 28 58 34', zhang: 'M70 42 L86 46', pt: [78, 44] },
		{ key: '没杖', mai: 'M8 14 C30 20 48 30 92 42', zhang: 'M56 30 L56 48', pt: [56, 45] },
		{ key: '对杖', mai: 'M50 6 L50 34', zhang: 'M34 40 L66 40', pt: [50, 40] },
		{ key: '截杖', mai: 'M6 14 C30 22 60 34 94 44', zhang: 'M46 20 L54 36', pt: [50, 28] },
		{ key: '犯杖', mai: 'M10 10 C30 20 46 30 88 44', zhang: 'M52 26 L72 24', pt: [62, 25] },
		{ key: '顿杖', mai: 'M8 12 C26 20 36 30 46 30 L70 30 C78 34 84 40 92 46', zhang: 'M50 24 L66 24', pt: [58, 30] },
	],
};
export const XINGSHI_SHAPE_NOTE = '形体图为古法形容之示意，非实测地形；实勘须以现场峦头为准。';

