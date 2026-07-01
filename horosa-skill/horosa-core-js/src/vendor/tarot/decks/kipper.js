// P4 Kipper 基帕(36 张具名人物/情境牌,德语区 19 世纪,公有领域)。无逆位;极重位置/朝向/距离,叙事 literal;用 Grand Tableau。
// 标准 Kipperkarten 36 张次序与名(历史公有);关键词原创中文转录。
// [num, cn, en, [关键词], polarity]
const K = [
	[1, '主牌·男', 'Main Man', ['本人(男)', '当事男性', '焦点'], 0],
	[2, '主牌·女', 'Main Woman', ['本人(女)', '当事女性', '焦点'], 0],
	[3, '婚姻', 'Marriage', ['结合', '婚姻', '伴侣关系'], 1],
	[4, '会面', 'Meeting', ['相聚', '会面', '交往'], 0],
	[5, '好先生', 'Good Lord', ['可靠男性', '善意', '助力'], 1],
	[6, '好女士', 'Good Lady', ['可靠女性', '善意', '关怀'], 1],
	[7, '愉快的信', 'Pleasant Letter', ['好消息', '文件', '沟通'], 1],
	[8, '虚伪之人', 'False Person', ['欺瞒', '不诚', '提防'], -1],
	[9, '变化', 'Change', ['转变', '调整', '不定'], 0],
	[10, '旅行', 'Journey', ['出行', '远方', '移动'], 0],
	[11, '赢得大钱', 'Lots of Money', ['财获', '大钱', '富足'], 1],
	[12, '富家女', 'Rich Girl', ['年轻女子', '财力', '机遇'], 0],
	[13, '富贵先生', 'Rich Lord', ['有力男性', '财富', '地位'], 1],
	[14, '悲伤消息', 'Sad News', ['坏消息', '忧', '挫折'], -1],
	[15, '爱的顺遂', 'Love & Success', ['恋爱顺遂', '情感', '亲密'], 1],
	[16, '他的心思', 'His Thoughts', ['念头', '意图', '内心'], 0],
	[17, '礼物', 'A Gift', ['馈赠', '善意', '惊喜'], 1],
	[18, '孩子', 'A Child', ['新生', '小', '纯真'], 0],
	[19, '丧事', 'Bereavement', ['终结', '失去', '哀'], -1],
	[20, '房子', 'House', ['家', '稳定', '不动产'], 0],
	[21, '起居室', 'Living Room', ['私域', '家内', '亲近'], 0],
	[22, '军/高位者', 'Military Person', ['权威', '纪律', '高位'], 0],
	[23, '法庭', 'Court', ['诉讼', '裁断', '官非'], -1],
	[24, '盗窃/失', 'Theft', ['损失', '失窃', '消减'], -1],
	[25, '高荣誉', 'High Honors', ['荣誉', '认可', '提升'], 1],
	[26, '大幸运', 'Great Fortune', ['大吉', '好运', '成功'], 1],
	[27, '意外之财', 'Unexpected Money', ['横财', '意外', '收入'], 1],
	[28, '期待', 'Expectation', ['等待', '期盼', '悬而未决'], 0],
	[29, '监狱', 'Prison', ['束缚', '受限', '阻滞'], -1],
	[30, '法律人/律师', 'Legal Person', ['法务', '裁判', '权威'], 0],
	[31, '短病', 'Short Illness', ['小恙', '短暂不适', '恢复'], -1],
	[32, '忧愁与逆境', 'Grief & Adversity', ['困顿', '逆境', '愁'], -1],
	[33, '阴郁心思', 'Melancholy', ['消沉', '阴郁', '内耗'], -1],
	[34, '工作/事务', 'Work', ['事务', '职责', '耕耘'], 0],
	[35, '远路', 'Long Road', ['长途', '迂回', '持久'], 0],
	[36, '希望·大水', 'Hope & Big Water', ['希望', '情感之海', '前景'], 1],
];

export const KIPPER_CARDS = K.map((row, idx) => {
	const [num, cn, en, kw, pol] = row;
	return {
		id: idx, sid: `kipper_${String(num).padStart(2, '0')}`, arcana: 'kipper', suit: 'kipper',
		number: num, court: null, name_cn: cn, name_en: en, names: null,
		element: '', symbol: '🂠', hebrew: null, astro: null, path: null,
		decanTitle: null, decanPlanet: null, decanSign: null, courtEie: null, courtSpan: null,
		polarity: pol, countingValue: num, houseName: cn,
		keywords_upright: kw, keywords_reversed: kw, meanings: { up: kw, rev: kw },
	};
});

export const KIPPER_DECK = {
	id: 'kipper', title: 'Kipper 基帕(36)', nameKey: 'rws', size: 36, structure: '36object',
	usesReversals: false, pReversed: 0, dignities: false, variant: 'A', illustratedPips: false,
	group: '神谕牌', cards: KIPPER_CARDS,
	caps: { reversals: false, dignities: false, variant: false, significator: false, numOverride: false, embeddedPlayingCard: false, readingMethod: 'lenormand', colorScale: false, spreads: ['single', 'lenormand_3', 'lenormand_box9', 'grand_tableau'] },
};
