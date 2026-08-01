// 西方择日子流派轴(五档)。单一真值源:引擎(红线/权重/口径)与 UI(左栏选择器/流派口径区/快照)共用。
// 设计约束:默认 modern_main = 现状行为字节不变(hsys 不联动、三王星全权重、calibre 空=不绑定任何口径);
// 其余档为「覆盖层」——宫制联动 + 三王星红线降为注记 + calibre 差异集(界/三分/容许度/空亡/用星)按档取参。
// 术语依据:希腊化(整宫制/七曜/宗派为纲/埃及界/Dorotheus 三分/30°法空亡)、
// 波斯-阿拉伯(Alcabitius/埃及界/接纳与容许/四座豁免空亡)、
// 文艺复兴(Regiomontanus/埃及界/Ptolemy 两主水象＝火星/moiety 容许度/容许度法空亡)、
// 现代古典复兴(整宫回归/七曜为主/宗派复兴)。
//
// 字段语义:
//   calibre —— 流派口径差异集(键见 electionParams.ELECTION_PARAM_SPEC;学理显式绑定,
//              四层优先级中恒压过全局仓;modern_main 恒空 = 全随内建默认与全局设置)。
//   sectWeight —— 宗派模块进入总分的真实权重(scoring 消费;替代旧注记性 sectEmphasis 的计分职能,
//                 sectEmphasis 保留作 UI 强调徽标)。
//   moduleSet —— 该流派参与「评分」的核心模块白名单(缺省=全部核心模块;
//                白名单外的核心模块仅展示不进总分)。

export const WEST_SCHOOL_ORDER = ['modern_main', 'hellenistic', 'persian', 'renaissance', 'modern_revival'];

// 核心十模块 key(scoring.WEIGHTS 的键;moduleSet 从此集合裁剪)。
export const CORE_MODULE_KEYS = ['moon', 'asc_ruler', 'ascendant', 'topic_significators', 'angles', 'topic_house', 'sun', 'aspect_patterns', 'reception_fixedstar_midpoint', 'fixed_stars'];

export const WEST_SCHOOLS = {
	modern_main: {
		id: 'modern_main', cn: '现代主流', short: '现代',
		hsys: null,              // 不联动宫制(保持用户当前值=现状)
		modernPlanets: 'full',   // 三王星按现状全权重参与红线
		sectEmphasis: 'medium',  // 宗派强调徽标(计分职能已由 sectWeight 承担)
		orbProfile: 'modern',    // 容许度档(前端自算模块消费;后端相位不变)
		extraWeights: {},        // 新增分析模块不计入总分(总分构成与既往字节不变)
		calibre: {},             // 不绑定任何口径 → 全随内建默认与全局设置(零回归)
		desc: '心理/事件占星并用，三王星全权重，宫制随全局设置。',
	},
	hellenistic: {
		id: 'hellenistic', cn: '希腊化', short: '希腊化',
		hsys: 0,                 // 整宫制
		modernPlanets: 'annotate', // 三王星红线降为注记(不扣分)
		sectEmphasis: 'high',
		orbProfile: 'sign',      // 按星座整宫论相位(紧轨供自算模块)
		sectWeight: 0.10,
		extraWeights: { sect: 0.10, moon_mechanics: 0.08, antiscia: 0.04, malefic_handling: 0.04, lots: 0.05, bonification: 0.05 },
		// 希腊化不以「相位格局」(大三角/T 三角为现代概念框架)计分,仅展示。
		moduleSet: CORE_MODULE_KEYS.filter((k) => k !== 'aspect_patterns'),
		calibre: { termsVariant: 0, tripSystem: 'dorothean', orbProfile: 'sign', vocMode: 'kenodromia', bodySet: 'classical7' },
		desc: '整宫制、七曜为纲、昼夜宗派为第一权重；埃及界、Dorotheus 三分、30°法空亡；三王星仅注记。',
	},
	persian: {
		id: 'persian', cn: '波斯-阿拉伯', short: '波斯',
		hsys: 1,                 // Alcabitius
		modernPlanets: 'annotate',
		sectEmphasis: 'high',
		orbProfile: 'moiety',
		sectWeight: 0.08,
		extraWeights: { sect: 0.08, moon_mechanics: 0.10, planetary_hours: 0.05, mansions: 0.04, antiscia: 0.03, almuten: 0.04, malefic_handling: 0.04, lots: 0.04, bonification: 0.04 },
		calibre: { termsVariant: 0, tripSystem: 'dorothean', orbProfile: 'moiety', vocMode: 'exempt4', bodySet: 'classical7' },
		desc: 'Alcabitius 宫制、重接纳与容许度、月亮细则最全；埃及界、四座豁免空亡；三王星仅注记。',
	},
	renaissance: {
		id: 'renaissance', cn: '文艺复兴', short: '文艺复兴',
		hsys: 2,                 // Regiomontanus
		modernPlanets: 'annotate',
		sectEmphasis: 'medium',
		orbProfile: 'moiety',
		sectWeight: 0.05,
		extraWeights: { sect: 0.05, moon_mechanics: 0.08, planetary_hours: 0.06, mansions: 0.05, antiscia: 0.03, radicality: 0.05, almuten: 0.03, malefic_handling: 0.05, lots: 0.03, bonification: 0.04 },
		calibre: { termsVariant: 0, tripSystem: 'ptolemaic', orbProfile: 'moiety', vocMode: 'by_orb', bodySet: 'classical7' },
		desc: 'Regiomontanus 宫制、埃及界、Ptolemy 两主（水象＝火星）、moiety 容许度、容许度法空亡；三王星仅注记。',
	},
	modern_revival: {
		id: 'modern_revival', cn: '古典复兴', short: '古典复兴',
		hsys: 0,                 // 整宫回归
		modernPlanets: 'annotate',
		sectEmphasis: 'high',
		orbProfile: 'moiety',
		sectWeight: 0.10,
		extraWeights: { sect: 0.10, moon_mechanics: 0.08, antiscia: 0.03, parans: 0.04, radicality: 0.03, malefic_handling: 0.04, bonification: 0.04 },
		calibre: { termsVariant: 0, tripSystem: 'dorothean', orbProfile: 'moiety', vocMode: 'classic', bodySet: 'classical7' },
		desc: '当代古典复兴：整宫制+宗派复兴，埃及界、Dorotheus 三分，七曜为主、三王星降权注记。',
	},
};

export function schoolOf(id){
	return WEST_SCHOOLS[id] || WEST_SCHOOLS.modern_main;
}

export default WEST_SCHOOLS;
