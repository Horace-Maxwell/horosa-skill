// 西方择日子流派轴(五档)。单一真值源:引擎(红线/权重)与 UI(左栏选择器/快照)共用。
// 设计约束:默认 modern_main = 现状行为字节不变(hsys 不联动、三王星全权重);
// 其余档为「覆盖层」——宫制联动 + 三王星红线降为注记 + 后续 WP(宗派/月相/orb)按档取参。
// 术语依据:希腊化(整宫制/七曜/宗派为纲)、波斯-阿拉伯(Alcabitius/接纳与容许)、
// 文艺复兴(Regiomontanus/moiety 容许度)、现代古典复兴(整宫回归/七曜为主/宗派复兴)。

export const WEST_SCHOOL_ORDER = ['modern_main', 'hellenistic', 'persian', 'renaissance', 'modern_revival'];

export const WEST_SCHOOLS = {
	modern_main: {
		id: 'modern_main', cn: '现代主流', short: '现代',
		hsys: null,              // 不联动宫制(保持用户当前值=现状)
		modernPlanets: 'full',   // 三王星按现状全权重参与红线
		sectEmphasis: 'medium',  // 宗派强调档(WP-1 消费)
		orbProfile: 'modern',    // 容许度档(前端自算模块消费;后端相位不变)
		extraWeights: {},        // 新增分析模块不计入总分(总分构成与既往字节不变)
		desc: '心理/事件占星并用，三王星全权重，宫制随全局设置。',
	},
	hellenistic: {
		id: 'hellenistic', cn: '希腊化', short: '希腊化',
		hsys: 0,                 // 整宫制
		modernPlanets: 'annotate', // 三王星红线降为注记(不扣分)
		sectEmphasis: 'high',
		orbProfile: 'sign',      // 按星座整宫论相位倾向(紧 orb 供自算模块)
		extraWeights: { sect: 0.10, moon_mechanics: 0.08, antiscia: 0.04 },
		desc: '整宫制、七曜为纲、昼夜宗派为第一权重；三王星仅注记。',
	},
	persian: {
		id: 'persian', cn: '波斯-阿拉伯', short: '波斯',
		hsys: 1,                 // Alcabitius
		modernPlanets: 'annotate',
		sectEmphasis: 'high',
		orbProfile: 'moiety',
		extraWeights: { sect: 0.08, moon_mechanics: 0.10, planetary_hours: 0.05, mansions: 0.04, antiscia: 0.03, almuten: 0.04 },
		desc: 'Alcabitius 宫制、重接纳与容许度、月亮状态细则最全；三王星仅注记。',
	},
	renaissance: {
		id: 'renaissance', cn: '文艺复兴', short: '文艺复兴',
		hsys: 2,                 // Regiomontanus
		modernPlanets: 'annotate',
		sectEmphasis: 'medium',
		orbProfile: 'moiety',
		extraWeights: { sect: 0.05, moon_mechanics: 0.08, planetary_hours: 0.06, mansions: 0.05, antiscia: 0.03, radicality: 0.05, almuten: 0.03 },
		desc: 'Regiomontanus 宫制、可判性口径与 moiety 容许度；三王星仅注记。',
	},
	modern_revival: {
		id: 'modern_revival', cn: '古典复兴', short: '古典复兴',
		hsys: 0,                 // 整宫回归
		modernPlanets: 'annotate',
		sectEmphasis: 'high',
		orbProfile: 'moiety',
		extraWeights: { sect: 0.10, moon_mechanics: 0.08, antiscia: 0.03, parans: 0.04, radicality: 0.03 },
		desc: '当代古典复兴：整宫制+宗派复兴，七曜为主、三王星降权注记。',
	},
};

export function schoolOf(id){
	return WEST_SCHOOLS[id] || WEST_SCHOOLS.modern_main;
}

export default WEST_SCHOOLS;
