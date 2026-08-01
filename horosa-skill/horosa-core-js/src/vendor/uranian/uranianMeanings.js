// 量化盘(汉堡学派)含义词典 —— 单一真值源(SSOT)。
// 纯数据 + 纯函数,零副作用。含义文本为技法语义本身,不署来源。
// 流派中性名:原始汉堡 / 纯净派 / 美国对称 / 宇宙生物学。
//
// 结构:
//   FACTOR_MEANINGS —— 10 行星 + 8 虚星 + 5 个人点 基义(关键词);个人点附时间轴义。
//   PAIR_MEANINGS   —— 个人点轴中性义表(键 pairKey)。
//   CLASSIC_PAIR_MEANINGS —— 真实行星两两中点经典判语(45 对全谱;四层:原理/心理±/生理/社会,
//                     另 occupants=特定占据者的电报式判语)。生理层全程"倾向/留意"措辞。
//   PICTURE_MEANINGS—— 含虚星行星图样例。
//   MEDICAL_MIDPOINTS—四液中点(倾向/留意措辞,不替代医疗诊断)。
//   纯函数:pairKey / factorLabel / compose / composeShort / pairMeaning / classicPairMeaning /
//         pictureMeaning / medicalMeaning。
//   composeShort 两因子查表优先级:个人点轴义 → 经典判语 → 含虚星图样例 → 关键词合成。

import * as AstroConst from '../constants/AstroConst.js';

// ───────────────────────── 基义:因子关键词 ─────────────────────────
// keyword=合成主题用的简义;label=单因子中文标签;axis=个人点时间轴义(仅个人点)。
export const FACTOR_MEANINGS = {
	// — 10 真实行星(汉堡语境关键词)—
	[AstroConst.SUN]: { label: '太阳', keyword: '自我·生命力·身体·父亲·白天·当权者' },
	[AstroConst.MOON]: { label: '月亮', keyword: '情绪·女性·母亲·公众·容受' },
	[AstroConst.MERCURY]: { label: '水星', keyword: '思维·言语·信息·交易·神经·年轻人' },
	[AstroConst.VENUS]: { label: '金星', keyword: '爱·和谐·审美·女性魅力·价值' },
	[AstroConst.MARS]: { label: '火星', keyword: '能量·行动·冲动·性·争斗·男性' },
	[AstroConst.JUPITER]: { label: '木星', keyword: '扩张·幸运·成功·乐观·法律·宗教' },
	[AstroConst.SATURN]: { label: '土星', keyword: '限制·责任·时间·收缩·分离·苦干·损失' },
	[AstroConst.URANUS]: { label: '天王星', keyword: '突变·革命·闪现·科技·独立·惊扰' },
	[AstroConst.NEPTUNE]: { label: '海王星', keyword: '消融·幻想·灵性·欺瞒·海洋·媒介' },
	[AstroConst.PLUTO]: { label: '冥王星', keyword: '转化·权力·毁灭与再生·深层强迫' },

	// — 8 虚星(海外因子)—
	[AstroConst.CUPIDO]: { label: '丘比特', keyword: '聚合·群体·家庭·婚姻·社会·合伙·组织·艺术' },
	[AstroConst.HADES]: { label: '哈迪斯', keyword: '腐朽·匮乏·污垢·疾病·秘密·过去·古旧·深度·前世' },
	[AstroConst.ZEUS]: { label: '宙斯', keyword: '受控之能·定向能量·机器·创造·领导·火·军事·驱力' },
	[AstroConst.KRONOS]: { label: '克洛诺斯', keyword: '优越·最高品质·权威·政府·精通·顶尖·高处' },
	[AstroConst.APOLLON]: { label: '阿波罗', keyword: '倍增·扩张·众多·科学·商业·贸易·和平·大局观' },
	[AstroConst.ADMETOS]: { label: '阿德墨托斯', keyword: '稳固·不动·阻滞·原料·专精·耐久·收窄·起终·死亡·不动产' },
	[AstroConst.VULCANUS]: { label: '伏尔甘', keyword: '巨力·强度·势能·权力·命运·剧烈喷发' },
	[AstroConst.POSEIDON]: { label: '波塞冬', keyword: '灵性·真理·理念·启蒙·照明·智慧·文化·精神' },

	// — 个人点(Asc/MC/北交/白羊点;日/月已在真实行星条目)+ 时间轴义 —
	// 个人点是"自我"核心象征,触发器,筛盘优先级最高。
	[AstroConst.ASC]: { label: '上升', keyword: '我与所在环境·与之相遇者·地点', axis: '地点', axisDetail: '地点;会面发生之地' },
	[AstroConst.MC]: { label: '天顶', keyword: '我之核心·目标·生涯顶点·当下', axis: '分/瞬', axisDetail: '分/瞬;影响世界的当下一刻' },
	[AstroConst.NORTH_NODE]: { label: '北交', keyword: '纽带·联结·互补关系·血缘', axis: '联结', axisDetail: '纽带;互补关系;血缘联结' },
	[AstroConst.ARIES_POINT]: { label: '白羊点', keyword: '与世界/公众的连接·名声·社会意义', axis: '世界点', axisDetail: '世界点;与世界/每件事的连接;最广社会接触' },

	// — 可选点(B7;默认关,开启后入点集)—
	[AstroConst.EAST_POINT]: { label: '东点', keyword: '赤道上升·本人自视的门户·子午局 1 宫头' },
	[AstroConst.VERTEX]: { label: '宿命点', keyword: '卯酉圈西交点·非自主的际遇·被动相遇' },
};

// 日/月既是真实行星也是个人点,其时间轴义另存(不污染上方真实行星基义)。
export const PERSONAL_POINT_AXIS = {
	[AstroConst.SUN]: { axis: '日', axisDetail: '日;自我·生命·父' },
	[AstroConst.MOON]: { axis: '时', axisDetail: '时;情绪·公众·母' },
	[AstroConst.ASC]: { axis: '地点', axisDetail: '地点;会面发生之地' },
	[AstroConst.MC]: { axis: '分/瞬', axisDetail: '分/瞬;影响世界的当下一刻' },
	[AstroConst.NORTH_NODE]: { axis: '联结', axisDetail: '纽带;互补关系;血缘联结' },
	[AstroConst.ARIES_POINT]: { axis: '世界点', axisDetail: '世界点;与世界/每件事的连接;最广社会接触' },
};

// 五个人点 id(日/月/上升/天顶/北交);白羊点为原始汉堡第六个人点,另列以便两派区分。
export const PERSONAL_POINTS_FIVE = [
	AstroConst.SUN, AstroConst.MOON, AstroConst.ASC, AstroConst.MC, AstroConst.NORTH_NODE,
];
export const PERSONAL_POINT_ARIES = AstroConst.ARIES_POINT;

// ───────────────────────── 纯函数:键 / 标签 ─────────────────────────

// 对称排序键:pairKey(a,b) === pairKey(b,a)。用于 PAIR/MEDICAL 查表。
export function pairKey(a, b){
	return [a, b].sort().join('|');
}

// 单因子中文标签(优先 FACTOR_MEANINGS.label,缺则回退 id)。
export function factorLabel(id){
	const f = FACTOR_MEANINGS[id];
	if (f && f.label) return f.label;
	return id == null ? '' : String(id);
}

// 取单因子合成用关键词主题(缺则回退标签)。
function factorKeyword(id){
	const f = FACTOR_MEANINGS[id];
	if (f && f.keyword) return f.keyword;
	return factorLabel(id);
}

// 取个人点时间轴义(日/时/分/地点/世界);非个人点返回 null。
export function axisOf(id){
	const a = PERSONAL_POINT_AXIS[id];
	return a ? a.axis : null;
}

// ───────────────────── 个人点轴中性义表(上色前) ─────────────────────
// 键统一用 pairKey(对称)。义为中性轴义,临盘按上下文上色。
const RAW_PAIR = [
	[AstroConst.MC, AstroConst.ARIES_POINT, '自我于世界;命运;影响世界的"一刻"'],
	[AstroConst.MC, AstroConst.SUN, '自我的肉身表达;我的身体;个人生活体验;对父亲的体验'],
	[AstroConst.MC, AstroConst.ASC, '市场;日常事务/与人互动'],
	[AstroConst.MC, AstroConst.MOON, '对潜意识的感知;我的情绪/反应/人格;对母亲的体验'],
	[AstroConst.MC, AstroConst.NORTH_NODE, '个人关系;对家庭的体验'],
	[AstroConst.ARIES_POINT, AstroConst.SUN, '地上的生命;知名人物与世界级事物'],
	[AstroConst.ARIES_POINT, AstroConst.ASC, '地上的某处;会面发生之地'],
	[AstroConst.ARIES_POINT, AstroConst.MOON, '民族/部落/人群;公众情绪与人气'],
	[AstroConst.ARIES_POINT, AstroConst.NORTH_NODE, '知名的结合;公开条约/协议;全球连接'],
	[AstroConst.SUN, AstroConst.ASC, '肉身在场;男性影响;父之屋'],
	[AstroConst.SUN, AstroConst.MOON, '身与魂;男与女;人格的肉身显化;内在平衡("内在婚姻")'],
	[AstroConst.ASC, AstroConst.MOON, '某地之氛围;公共场所;情感伙伴;母之屋'],
	[AstroConst.MOON, AstroConst.NORTH_NODE, '情感联结;本能纽带;母系连接;国家联盟'],
];
export const PAIR_MEANINGS = RAW_PAIR.reduce((acc, [a, b, txt]) => {
	acc[pairKey(a, b)] = txt;
	return acc;
}, {});

// 个人点轴中性义查表(对称);无则 null。
export function pairMeaning(a, b){
	return PAIR_MEANINGS[pairKey(a, b)] || null;
}

// ───────────────── 经典中点判语:真实行星两两全谱(45 对) ─────────────────
// 四层结构:principle 原理 / psych 心理(plus 正·minus 负) / bio 生理(倾向/留意措辞) / socio 社会。
// occupants:特定占据者(C=A/B)的电报式判语,仅收传世点名者。
// 键用 pairKey(对称)。重点 9 对为完整四层;其余 36 对按造句法给基础层(原理+心理两极)。
// 生理层为体质倾向参考,展示层须并附「不替代医疗诊断」免责(B3 词典面板/医学卡同口径)。
const RAW_CLASSIC_PAIR = [
	// —— 点名九对(完整四层)——
	[AstroConst.SUN, AstroConst.MOON, {
		principle: '身与魂的合一;意识与无意识;夫与妻("内在婚姻")',
		psych: { plus: '内外平衡·身心和谐·关系圆融', minus: '内在失衡·身心相违·伴侣张力' },
		bio: '整体生命力与节律的倾向;留意作息与恢复。',
		socio: '婚姻与伴侣之事;男女合作;身心一体的公众形象。',
		occupants: {
			[AstroConst.SATURN]: '伴侣分离;孤独感;关系中的责任与迟滞',
			[AstroConst.URANUS]: '突发结合或离异;独立诉求引发的骤变',
		},
	}],
	[AstroConst.MARS, AstroConst.SATURN, {
		principle: '受阻之能;苦干;克制的力量("死亡轴"·事故病弱之轴)',
		psych: { plus: '坚忍·纪律·持久耐力', minus: '挫败·压抑之怒·消耗感' },
		bio: '能量耗损与筋骨劳损的倾向;留意过劳与磕碰。',
		socio: '艰苦劳动;损耗性事务;裁减与哀事。',
		occupants: {
			[AstroConst.SUN]: '苦干者;过度则耗竭,生命力受压(留意休养)',
		},
	}],
	[AstroConst.SATURN, AstroConst.PLUTO, {
		principle: '苦役与重负;克己;艰难的转化',
		psych: { plus: '极强承压与自律;于逆境中重建', minus: '冷酷·强迫性克制·崩解感' },
		bio: '慢性消耗与深层压力反应的倾向;留意积劳。',
		socio: '重负之责;受制的权力;大厦倾覆后的重建。',
	}],
	[AstroConst.SATURN, AstroConst.NEPTUNE, {
		principle: '形与无形之争;心身之病;缓慢消融的结构',
		psych: { plus: '化理想为持久之功;朴素克欲', minus: '疑惧·悲观·意志消沉' },
		bio: '心身性、慢性、难以名状之症的倾向;留意长期情绪压力的躯体化。',
		socio: '隐忍之苦;慢性事务;幻想的清算。',
	}],
	[AstroConst.MARS, AstroConst.URANUS, {
		principle: '骤发之力;手术;突然的行动',
		psych: { plus: '决断如电;技术胆识', minus: '冲动爆裂·鲁莽急躁' },
		bio: '心律与神经张力波动的倾向;留意外伤与骤发状况(古义"手术·心律")。',
		socio: '突发事件;技术性介入;果断的改革。',
	}],
	[AstroConst.MERCURY, AstroConst.VENUS, {
		principle: '优雅的表达;审美之思',
		psych: { plus: '谈吐动人;艺术感受力', minus: '耽于形式·言辞浮华' },
		bio: '神经与感官偏好愉悦的倾向;留意松弛有度。',
		socio: '文艺;社交辞令;美的交流与交易。',
	}],
	[AstroConst.MERCURY, AstroConst.MARS, {
		principle: '锐利之思;果决之言',
		psych: { plus: '思辨敏捷;执行的头脑', minus: '言语交锋·急躁武断' },
		bio: '神经紧张与用脑过度的倾向;留意节奏。',
		socio: '辩论;批评;实干型沟通与指令。',
	}],
	[AstroConst.VENUS, AstroConst.MARS, {
		principle: '爱之冲动;激情',
		psych: { plus: '热烈的感情;创造性的吸引', minus: '情欲冲突·爱中之争' },
		bio: '激情消长牵动身心张弛的倾向。',
		socio: '恋爱;两性关系;艺术中的力度。',
	}],
	[AstroConst.MARS, AstroConst.JUPITER, {
		principle: '成功的能量;为胜而动',
		psych: { plus: '进取·竞胜·行动带来的幸运', minus: '好大喜功·冒进' },
		bio: '精力旺盛的倾向;留意运动损耗。',
		socio: '竞技;拓业;果断的决断与远征。',
		occupants: {
			[AstroConst.SUN]: '为求胜而生的意志与体魄;经自我聚焦的成功能量',
		},
	}],
	// —— 其余 36 对(造句法基础层:原理 + 心理两极)——
	[AstroConst.SUN, AstroConst.MERCURY, { principle: '意志之思;自我的表达', psych: { plus: '清晰自知·言为心声', minus: '固执己见·自我中心的言谈' } }],
	[AstroConst.SUN, AstroConst.VENUS, { principle: '爱与美的自我;价值感', psych: { plus: '温暖魅力·审美的生命', minus: '虚荣·耽于安逸' } }],
	[AstroConst.SUN, AstroConst.MARS, { principle: '意志之力;行动的身体', psych: { plus: '勇健果敢·生命力旺', minus: '好斗急躁·亢奋耗损(留意过劳)' } }],
	[AstroConst.SUN, AstroConst.JUPITER, { principle: '幸运的生命;扩张的自我', psych: { plus: '乐观健旺·得道多助', minus: '自满·奢望' } }],
	[AstroConst.SUN, AstroConst.SATURN, { principle: '受限的自我;责任之身', psych: { plus: '沉稳持重·有担当', minus: '压抑·自贬·与尊长之隔' } }],
	[AstroConst.SUN, AstroConst.URANUS, { principle: '骤变的自我;独立', psych: { plus: '独创·觉醒', minus: '突兀反复·紧张' } }],
	[AstroConst.SUN, AstroConst.NEPTUNE, { principle: '消融的自我;易感之身', psych: { plus: '灵感·慈悲', minus: '虚弱·迷失(留意作息与恢复)' } }],
	[AstroConst.SUN, AstroConst.PLUTO, { principle: '转化的自我;权力意志', psych: { plus: '再生之力·深度掌控', minus: '强迫·独断' } }],
	[AstroConst.MOON, AstroConst.MERCURY, { principle: '情思;心声', psych: { plus: '体察入微·善述心绪', minus: '多思善感·情绪化言语' } }],
	[AstroConst.MOON, AstroConst.VENUS, { principle: '柔情;和美之感', psych: { plus: '温柔亲和·家宅之美', minus: '依恋·情感耽溺' } }],
	[AstroConst.MOON, AstroConst.MARS, { principle: '情绪之力;冲动的感受', psych: { plus: '直率热忱·护持之勇', minus: '易怒·情绪风暴' } }],
	[AstroConst.MOON, AstroConst.JUPITER, { principle: '丰盈之情;民心所向', psych: { plus: '宽厚乐群·有人气', minus: '情绪夸张·放纵' } }],
	[AstroConst.MOON, AstroConst.SATURN, { principle: '克制之情;孤寂', psych: { plus: '情感自律·可靠', minus: '抑郁·疏离·亲缘之限' } }],
	[AstroConst.MOON, AstroConst.URANUS, { principle: '骤变之情;直觉闪现', psych: { plus: '敏锐直觉·情感独立', minus: '情绪骤变·不安' } }],
	[AstroConst.MOON, AstroConst.NEPTUNE, { principle: '感应;梦境之情', psych: { plus: '共情如水·想象丰沛', minus: '情绪迷雾·易受浸染' } }],
	[AstroConst.MOON, AstroConst.PLUTO, { principle: '深层情感;情之强迫', psych: { plus: '情感深挚·洞察人心', minus: '占有·情绪操控' } }],
	[AstroConst.MERCURY, AstroConst.JUPITER, { principle: '广博之思;成功的言说', psych: { plus: '博学明断·善谋', minus: '言过其实' } }],
	[AstroConst.MERCURY, AstroConst.SATURN, { principle: '严谨之思;沉重的消息', psych: { plus: '缜密务实·深思', minus: '迟疑悲观·讯息之阻' } }],
	[AstroConst.MERCURY, AstroConst.URANUS, { principle: '闪念;技术之思', psych: { plus: '灵光敏捷·创新', minus: '神经紧绷·思绪散乱' } }],
	[AstroConst.MERCURY, AstroConst.NEPTUNE, { principle: '想象之思;朦胧的信息', psych: { plus: '诗性直觉·艺术表达', minus: '混淆·讹传·自欺' } }],
	[AstroConst.MERCURY, AstroConst.PLUTO, { principle: '洞穿之思;言语之力', psych: { plus: '探究入骨·有说服力', minus: '多疑·言辞胁迫' } }],
	[AstroConst.VENUS, AstroConst.JUPITER, { principle: '大乐;丰美', psych: { plus: '慷慨优雅·福泽', minus: '奢逸·过度享乐' } }],
	[AstroConst.VENUS, AstroConst.SATURN, { principle: '克制之爱;迟来的美', psych: { plus: '忠贞持久·朴素之美', minus: '情感匮乏·爱之隔' } }],
	[AstroConst.VENUS, AstroConst.URANUS, { principle: '骤然心动;非常之爱', psych: { plus: '新奇魅力·艺术新意', minus: '情感无常·聚散无端' } }],
	[AstroConst.VENUS, AstroConst.NEPTUNE, { principle: '梦幻之爱;至美', psych: { plus: '浪漫灵感·艺境', minus: '幻恋·审美沉溺' } }],
	[AstroConst.VENUS, AstroConst.PLUTO, { principle: '深情;爱之强度', psych: { plus: '深挚吸引·艺术张力', minus: '占有之爱·情感权斗' } }],
	[AstroConst.MARS, AstroConst.NEPTUNE, { principle: '消融之力;无形之扰', psych: { plus: '灵感驱动·济弱之行', minus: '力不从心·暗耗(留意虚损)' } }],
	[AstroConst.MARS, AstroConst.PLUTO, { principle: '强力;彻底之行', psych: { plus: '超常执行·攻坚', minus: '暴烈·强制' } }],
	[AstroConst.JUPITER, AstroConst.SATURN, { principle: '张弛之衡;久成之业', psych: { plus: '稳步扩张·制度化的成功', minus: '时运起落·迟滞之运' } }],
	[AstroConst.JUPITER, AstroConst.URANUS, { principle: '骤来之幸;解放', psych: { plus: '机遇突至·远见', minus: '侥幸投机' } }],
	[AstroConst.JUPITER, AstroConst.NEPTUNE, { principle: '理想之扩;信念', psych: { plus: '慈惠·愿景', minus: '虚夸·投机幻想' } }],
	[AstroConst.JUPITER, AstroConst.PLUTO, { principle: '大权;巨富之势', psych: { plus: '组织伟力·资源整合', minus: '权欲膨胀' } }],
	[AstroConst.SATURN, AstroConst.URANUS, { principle: '张力;破与立', psych: { plus: '于变局中立规·坚韧革新', minus: '突然之阻·紧张断裂' } }],
	[AstroConst.URANUS, AstroConst.NEPTUNE, { principle: '觉醒与消融;时代之潮', psych: { plus: '灵性革新·超越', minus: '神经过敏·莫名骚动' } }],
	[AstroConst.URANUS, AstroConst.PLUTO, { principle: '剧变;革命之力', psych: { plus: '除旧布新·突破', minus: '动荡·颠覆' } }],
	[AstroConst.NEPTUNE, AstroConst.PLUTO, { principle: '深层消融;世代暗流', psych: { plus: '玄思·深层直觉', minus: '隐秘侵蚀·集体迷狂' } }],
];
export const CLASSIC_PAIR_MEANINGS = RAW_CLASSIC_PAIR.reduce((acc, [a, b, entry]) => {
	acc[pairKey(a, b)] = entry;
	return acc;
}, {});

// 经典判语查表(对称);返回 {principle, psych, bio?, socio?, occupants?} 或 null。
export function classicPairMeaning(a, b){
	return CLASSIC_PAIR_MEANINGS[pairKey(a, b)] || null;
}

// ───────────────────── 含虚星的行星图样例(重构) ─────────────────────
// 按造句法重构的两因子图样,键用 pairKey。
const RAW_PICTURE = [
	[AstroConst.SUN, AstroConst.CUPIDO, '自我融入群体/家庭;善社交者;自我的"成婚";艺术家'],
	[AstroConst.MARS, AstroConst.ZEUS, '受控定向之力;工程/武器/受命之火;有目标的进取;生殖驱力'],
	[AstroConst.JUPITER, AstroConst.KRONOS, '大成功 + 高权威;登顶;幸运的专家;经官方而扩张'],
	[AstroConst.MERCURY, AstroConst.APOLLON, '思维广远;心智倍增;科学/商业沟通;教学/出版/贸易;多念并起'],
	[AstroConst.SATURN, AstroConst.HADES, '腐朽成痼;慢病/贫困/深匮;旧弃之物;哀伤;对深埋过往的研究'],
	[AstroConst.SATURN, AstroConst.ADMETOS, '深重阻塞;彻底停滞;收束至一点;不可移之障;深刻的终/始;严酷收缩'],
	[AstroConst.MARS, AstroConst.VULCANUS, '巨力;压倒性的力量施加;蛮力;爆发性能量;不可挡之推进'],
	[AstroConst.NEPTUNE, AstroConst.POSEIDON, '纯然灵性与照明;高度灵感 vs 幻惑;非物质/通灵;对"灵"的启蒙或欺瞒'],
];
export const PICTURE_MEANINGS = RAW_PICTURE.reduce((acc, [a, b, txt]) => {
	acc[pairKey(a, b)] = txt;
	return acc;
}, {});

// 含虚星行星图样例查表(对称);无则 null。
export function pictureMeaning(a, b){
	return PICTURE_MEANINGS[pairKey(a, b)] || null;
}

// ─────────────────────── 医学:四液中点 ───────────────────────
// 四体液中点(键用 pairKey);仅在被激活(占据/触发)时显示病理倾向。
// 措辞全程"倾向/留意",末句明示不替代医疗诊断。
const MED_DISCLAIMER = '仅为体质倾向参考,不替代医疗诊断。';
const RAW_MEDICAL = [
	[AstroConst.SUN, AstroConst.MARS, '胆汁质', '偏热、偏动、易急躁亢奋的体质倾向;留意上火、炎症与冲动耗损。'],
	[AstroConst.VENUS, AstroConst.JUPITER, '多血质', '偏温润、丰盈、循环旺盛的体质倾向;留意过盈、代谢与糖脂负担。'],
	[AstroConst.MERCURY, AstroConst.SATURN, '忧郁质', '偏冷、偏燥、偏紧的体质倾向;留意神经紧张、消化迟滞与情绪低落。'],
	[AstroConst.MOON, AstroConst.NEPTUNE, '黏液质', '偏湿、偏寒、偏滞的体质倾向;留意水湿停聚、易倦怠与免疫波动。'],
];
export const MEDICAL_MIDPOINTS = RAW_MEDICAL.reduce((acc, [a, b, temperament, note]) => {
	acc[pairKey(a, b)] = { temperament, note: note + MED_DISCLAIMER };
	return acc;
}, {});

// 四液中点查表(对称);返回 {temperament, note} 或 null。
export function medicalMeaning(a, b){
	return MEDICAL_MIDPOINTS[pairKey(a, b)] || null;
}

// ───────────────────────── 造句法 ─────────────────────────
// 中点对 A/B 取主题,占据者 C 定"经何显现"。
// 句式:C = A/B → "[A/B 主题] 通过 [C] 表达"。

// compose(a,b,c):完整造句。c 可省(仅给主题)。
export function compose(a, b, c){
	const theme = factorKeyword(a) + '/' + factorKeyword(b);
	if (c == null || c === '') {
		return factorLabel(a) + '/' + factorLabel(b) + ' 主题:' + theme;
	}
	return '[' + factorLabel(a) + '/' + factorLabel(b) + ' 主题] 通过 [' + factorLabel(c) + '] 表达';
}

// composeShort(...):读数行短句。
//   1 因子 → 单星基义;2 因子 → 标签对 + 优先查个人点轴义/行星图样例;3 因子 → C=A/B 造句。
export function composeShort(a, b, c){
	// 单因子:标签 + 基义关键词。
	if ((b == null || b === '') && (c == null || c === '')) {
		const kw = factorKeyword(a);
		return factorLabel(a) + (kw && kw !== factorLabel(a) ? ' · ' + kw : '');
	}
	// 三因子:C = A/B。
	if (c != null && c !== '') {
		const head = factorLabel(c) + ' = ' + factorLabel(a) + '/' + factorLabel(b);
		const theme = factorKeyword(a) + '/' + factorKeyword(b);
		return head + ' · ' + theme + ' 经 ' + factorLabel(c) + ' 显现';
	}
	// 两因子:优先个人点轴中性义 → 经典判语(A1) → 含虚星图样例 → 合成主题。
	// 轴义/样例命中的返回与既往逐字一致;经典判语只接管原走关键词合成兜底的真实行星对。
	const pm = pairMeaning(a, b);
	if (pm) return factorLabel(a) + '/' + factorLabel(b) + ' · ' + pm;
	const cls = classicPairMeaning(a, b);
	if (cls && cls.principle) return factorLabel(a) + '/' + factorLabel(b) + ' · ' + cls.principle;
	const pic = pictureMeaning(a, b);
	if (pic) return factorLabel(a) + '/' + factorLabel(b) + ' · ' + pic;
	return factorLabel(a) + '/' + factorLabel(b) + ' · ' + factorKeyword(a) + '/' + factorKeyword(b);
}

// 兼容旧 URANIAN_MEANING 形态:8 虚星 id → 单行关键词串(从 FACTOR_MEANINGS 派生,物理唯一份)。
export const URANIAN_MEANING = AstroConst.LIST_URANIAN.reduce((acc, id) => {
	const f = FACTOR_MEANINGS[id];
	if (f && f.keyword) acc[id] = f.keyword;
	return acc;
}, {});
