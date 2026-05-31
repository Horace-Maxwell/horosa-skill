// divination/data/signs.js
// 星座属性（引擎最依赖的表）。来源：卜卦构建清单 §1.2/§1.6/§1.7 + 择日清单 §2.2/§2.7。
// crooked_straight: straight=事顺直快 / crooked=曲折拖延（Dorotheus Ch2）
// shape: human(人形,受克=人为伤害) / bestial(兽性,受克=动物伤害) / water
// direction: 择日清单 §2.7 先天十二宫方位（按星座，优于宫位）

export const SIGNS = {
	aries: {
		id: 'aries', cn: '白羊', palace_cn: '戌', en: 'Aries', glyph: '♈',
		element: 'fire', modality: 'cardinal', gender: 'masculine', sect: 'diurnal',
		crooked_straight: 'crooked', fertility: 'barren', bicorporeal: false, shape: 'bestial',
		body_parts: ['头', '脸', '眼', '鼻', '耳'], direction: '东',
		domicile: 'mars', exaltation: { planet: 'sun', degree: 19 }, detriment: ['venus'], fall: 'saturn',
	},
	taurus: {
		id: 'taurus', cn: '金牛', palace_cn: '酉', en: 'Taurus', glyph: '♉',
		element: 'earth', modality: 'fixed', gender: 'feminine', sect: 'nocturnal',
		crooked_straight: 'crooked', fertility: 'neutral', bicorporeal: false, shape: 'bestial',
		body_parts: ['喉', '颈', '甲状腺'], direction: '南偏东',
		domicile: 'venus', exaltation: { planet: 'moon', degree: 3 }, detriment: ['mars'], fall: null,
	},
	gemini: {
		id: 'gemini', cn: '双子', palace_cn: '申', en: 'Gemini', glyph: '♊',
		element: 'air', modality: 'mutable', gender: 'masculine', sect: 'diurnal',
		crooked_straight: 'crooked', fertility: 'neutral', bicorporeal: true, shape: 'human',
		body_parts: ['手臂', '肩', '肺', '神经', '气管'], direction: '西偏南',
		domicile: 'mercury', exaltation: { planet: 'north_node', degree: 3 }, detriment: ['jupiter'], fall: null,
	},
	cancer: {
		id: 'cancer', cn: '巨蟹', palace_cn: '未', en: 'Cancer', glyph: '♋',
		element: 'water', modality: 'cardinal', gender: 'feminine', sect: 'nocturnal',
		crooked_straight: 'straight', fertility: 'fertile', bicorporeal: false, shape: 'water',
		body_parts: ['胃', '胸', '子宫', '卵巢', '牙'], direction: '北',
		domicile: 'moon', exaltation: { planet: 'jupiter', degree: 15 }, detriment: ['saturn'], fall: 'mars',
	},
	leo: {
		id: 'leo', cn: '狮子', palace_cn: '午', en: 'Leo', glyph: '♌',
		element: 'fire', modality: 'fixed', gender: 'masculine', sect: 'diurnal',
		crooked_straight: 'straight', fertility: 'barren', bicorporeal: false, shape: 'bestial',
		body_parts: ['心脏', '脊椎', '背', '脊髓'], direction: '东偏北',
		domicile: 'sun', exaltation: null, detriment: ['saturn'], fall: null,
	},
	virgo: {
		id: 'virgo', cn: '处女', palace_cn: '巳', en: 'Virgo', glyph: '♍',
		element: 'earth', modality: 'mutable', gender: 'feminine', sect: 'nocturnal',
		crooked_straight: 'straight', fertility: 'barren', bicorporeal: true, shape: 'human',
		body_parts: ['小肠', '胰', '脾', '腹', '十二指肠'], direction: '南偏西',
		domicile: 'mercury', exaltation: { planet: 'mercury', degree: 15 }, detriment: ['jupiter'], fall: 'venus',
	},
	libra: {
		id: 'libra', cn: '天秤', palace_cn: '辰', en: 'Libra', glyph: '♎',
		element: 'air', modality: 'cardinal', gender: 'masculine', sect: 'diurnal',
		crooked_straight: 'straight', fertility: 'neutral', bicorporeal: false, shape: 'human',
		body_parts: ['下背', '肾', '静脉', '卵巢'], direction: '西',
		domicile: 'venus', exaltation: { planet: 'saturn', degree: 21 }, detriment: ['mars'], fall: 'sun',
	},
	scorpio: {
		id: 'scorpio', cn: '天蝎', palace_cn: '卯', en: 'Scorpio', glyph: '♏',
		element: 'water', modality: 'fixed', gender: 'feminine', sect: 'nocturnal',
		crooked_straight: 'straight', fertility: 'fertile', bicorporeal: false, shape: 'bestial',
		body_parts: ['生殖', '排泄', '结肠', '膀胱', '摄护腺'], direction: '北偏东',
		domicile: 'mars', exaltation: null, detriment: ['venus'], fall: 'moon',
		modern_domicile: 'pluto',
	},
	sagittarius: {
		id: 'sagittarius', cn: '射手', palace_cn: '寅', en: 'Sagittarius', glyph: '♐',
		element: 'fire', modality: 'mutable', gender: 'masculine', sect: 'diurnal',
		crooked_straight: 'straight', fertility: 'neutral', bicorporeal: true, shape: 'human',
		body_parts: ['大腿', '臀', '坐骨神经', '肝', '动脉'], direction: '东偏南',
		domicile: 'jupiter', exaltation: null, detriment: ['mercury'], fall: null,
	},
	capricorn: {
		id: 'capricorn', cn: '摩羯', palace_cn: '丑', en: 'Capricorn', glyph: '♑',
		element: 'earth', modality: 'cardinal', gender: 'feminine', sect: 'nocturnal',
		crooked_straight: 'crooked', fertility: 'neutral', bicorporeal: false, shape: 'bestial',
		body_parts: ['膝', '关节', '胆囊', '头发', '皮肤'], direction: '南',
		domicile: 'saturn', exaltation: { planet: 'mars', degree: 28 }, detriment: ['moon'], fall: 'jupiter',
	},
	aquarius: {
		id: 'aquarius', cn: '水瓶', palace_cn: '子', en: 'Aquarius', glyph: '♒',
		element: 'air', modality: 'fixed', gender: 'masculine', sect: 'diurnal',
		crooked_straight: 'crooked', fertility: 'neutral', bicorporeal: false, shape: 'human',
		body_parts: ['小腿', '踝', '血液循环', '脊髓'], direction: '西偏北',
		domicile: 'saturn', exaltation: null, detriment: ['sun'], fall: null,
		modern_domicile: 'uranus',
	},
	pisces: {
		id: 'pisces', cn: '双鱼', palace_cn: '亥', en: 'Pisces', glyph: '♓',
		element: 'water', modality: 'mutable', gender: 'feminine', sect: 'nocturnal',
		crooked_straight: 'crooked', fertility: 'fertile', bicorporeal: true, shape: 'water',
		body_parts: ['脚掌', '淋巴'], direction: '北偏西',
		domicile: 'jupiter', exaltation: { planet: 'venus', degree: 27 }, detriment: ['mercury'], fall: 'mercury',
		modern_domicile: 'neptune',
	},
};

export const SIGN_ORDER = ['aries', 'taurus', 'gemini', 'cancer', 'leo', 'virgo', 'libra', 'scorpio', 'sagittarius', 'capricorn', 'aquarius', 'pisces'];

// 三方四正用法（择日核心，择日清单 §2.2）
export const MODALITY_USAGE = {
	cardinal: '开创·冒险·攻击·快速·不持久。适合开创新领域、速成、社交、比赛攻击力；婚姻次选。',
	fixed: '稳定·扎根·持续 → 择日最佳，尤婚姻/事业。Taurus(酉) 第一（实质收入），次 Leo/Scorpio/Aquarius。',
	mutable: '变动·不稳·短期·灵活。婚姻/事业忌；适合宴会、几小时内结束的社交。',
};

// 命度度数规则：Asc 尽量不选 28° 之后（变动气质）；固定特质要强取 1°–5°。
export const ASC_DEGREE_RULE = { lateThreshold: 28, strongFixedRange: [1, 5] };

export function signInfo(id){
	return SIGNS[id] || null;
}

// 经度 → 星座 id
export function signOfLon(lon){
	const idx = Math.floor(((lon % 360) + 360) % 360 / 30);
	return SIGN_ORDER[idx];
}

export default SIGNS;
