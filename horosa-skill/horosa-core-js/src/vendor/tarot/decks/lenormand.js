// P4 Lenormand 雷诺曼(36 张具象神谕牌)。源:Game of Hope(1799,公有领域)体系。
// 无大小阿卡纳、无逆位;读法靠位置/邻接/组合成句(名词×修饰)+ Grand Tableau 宫位/镜像/跳马。
// 36 张:编号/名称/嵌扑克/关键词/polarity(固定吉凶) 据手册公有领域表;关键词原创中文转录。

// [id0..35] = [num, cn, en, 扑克, [关键词], polarity, symbol]
const L = [
	[1, '骑士', 'Rider', '9♥', ['消息', '到来', '移动', '青年男子'], 0, '🐎'],
	[2, '三叶草', 'Clover', '6♦', ['小幸运', '短暂机会', '希望'], 1, '🍀'],
	[3, '船', 'Ship', '10♠', ['旅行', '远方', '贸易', '离开'], 0, '⛵'],
	[4, '房子', 'House', 'K♥', ['家庭', '稳定', '不动产', '安全'], 0, '🏠'],
	[5, '树', 'Tree', '7♥', ['健康', '成长', '根基', '缓慢', '宿命'], 0, '🌳'],
	[6, '云', 'Clouds', 'K♣', ['困惑', '不确定', '麻烦'], -1, '☁'],
	[7, '蛇', 'Snake', 'Q♣', ['背叛', '纠葛', '欲望', '迂回'], -1, '🐍'],
	[8, '棺材', 'Coffin', '9♦', ['结束', '失去', '疾病', '转化'], -1, '⚰'],
	[9, '花束', 'Bouquet', 'Q♠', ['礼物', '美好', '邀请', '满意'], 1, '💐'],
	[10, '镰刀', 'Scythe', 'J♦', ['突然切断', '危险', '决断', '收获'], -1, '⚔'],
	[11, '鞭', 'Whip', 'J♣', ['争吵', '重复', '冲突', '运动'], -1, '〰'],
	[12, '鸟', 'Birds', '7♦', ['闲谈', '焦虑', '沟通', '忙碌'], 0, '🐦'],
	[13, '孩子', 'Child', 'J♠', ['新开始', '小', '纯真', '孩子'], 0, '🧒'],
	[14, '狐狸', 'Fox', '9♣', ['狡猾', '工作', '欺骗', '自利'], -1, '🦊'],
	[15, '熊', 'Bear', '10♣', ['力量', '上司', '财力', '保护者'], 0, '🐻'],
	[16, '星', 'Star', '6♥', ['希望', '指引', '清晰', '灵性', '成功'], 1, '⭐'],
	[17, '鹳', 'Stork', 'Q♥', ['改变', '迁移', '改善', '怀孕'], 0, '🦩'],
	[18, '狗', 'Dog', '10♥', ['友谊', '忠诚', '信任'], 0, '🐕'],
	[19, '塔', 'Tower', '6♠', ['机构', '权威', '孤立', '长久'], 0, '🗼'],
	[20, '花园', 'Garden', '8♠', ['公众', '社交', '网络', '活动'], 0, '🌷'],
	[21, '山', 'Mountain', '8♣', ['障碍', '阻滞', '延迟', '敌人'], -1, '⛰'],
	[22, '岔路', 'Crossroads', 'Q♦', ['选择', '多重路径', '决定'], 0, '🛤'],
	[23, '老鼠', 'Mice', '7♣', ['损耗', '压力', '失窃', '消减'], -1, '🐁'],
	[24, '心', 'Heart', 'J♥', ['爱', '感情', '浪漫'], 1, '❤'],
	[25, '戒指', 'Ring', 'A♣', ['承诺', '契约', '婚姻', '循环'], 0, '💍'],
	[26, '书', 'Book', '10♦', ['秘密', '知识', '教育', '未知'], 0, '📖'],
	[27, '信', 'Letter', '7♠', ['信息', '文件', '消息', '沟通'], 0, '✉'],
	[28, '男人', 'Man', 'A♥', ['男问者本人', '生命中的男性'], 0, '👤'],
	[29, '女人', 'Woman', 'A♠', ['女问者本人', '生命中的女性'], 0, '👩'],
	[30, '百合', 'Lily', 'K♠', ['成熟', '和平', '德行', '家庭', '伦理'], 0, '⚜'],
	[31, '太阳', 'Sun', 'A♦', ['成功', '活力', '能量', '幸福'], 1, '☀'],
	[32, '月亮', 'Moon', '8♥', ['情感', '名誉', '认可', '直觉'], 1, '🌙'],
	[33, '钥匙', 'Key', '8♦', ['解答', '确定', '突破', '命中'], 1, '🗝'],
	[34, '鱼', 'Fish', 'K♦', ['金钱', '生意', '丰盛', '财务'], 1, '🐟'],
	[35, '锚', 'Anchor', '9♠', ['稳定', '工作', '目标', '坚持'], 1, '⚓'],
	[36, '十字', 'Cross', '6♣', ['负担', '苦难', '命运', '信仰', '终结'], -1, '✝'],
];

export const LENORMAND_CARDS = L.map((row, idx) => {
	const [num, cn, en, pc, kw, pol, sym] = row;
	return {
		id: idx, sid: `lenormand_${String(num).padStart(2, '0')}`, arcana: 'lenormand', suit: 'lenormand',
		number: num, court: null, name_cn: cn, name_en: en, names: null,
		element: '', symbol: sym, hebrew: null, astro: null, path: null,
		decanTitle: null, decanPlanet: null, decanSign: null, courtEie: null, courtSpan: null,
		polarity: pol, countingValue: num, playingCard: pc,
		houseName: cn, // 宫位法:位置 num 的宫义 = 该牌名(位置1=骑士宫…位置36=十字宫)
		keywords_upright: kw, keywords_reversed: kw, meanings: { up: kw, rev: kw },
	};
});

export const LENORMAND_DECK = {
	id: 'lenormand', title: 'Lenormand 雷诺曼(36)', nameKey: 'rws', size: 36, structure: '36object',
	usesReversals: false, pReversed: 0, dignities: false, variant: 'A', illustratedPips: false,
	group: '神谕牌', cards: LENORMAND_CARDS,
	caps: { reversals: false, dignities: false, variant: false, significator: false, numOverride: false, embeddedPlayingCard: true, readingMethod: 'lenormand', colorScale: false, spreads: ['single', 'lenormand_3', 'lenormand_box9', 'grand_tableau'] },
};
