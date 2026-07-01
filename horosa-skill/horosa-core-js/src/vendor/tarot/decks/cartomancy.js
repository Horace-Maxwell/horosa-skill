// P5 扑克卡牌占卜(52 张,塔罗的民间表亲)。源:英系/Hedgewitch 民俗(公有领域)。
// 花色:♥情感 ♣事业/运 ♦金钱/消息 ♠挑战;红牌偏吉、黑牌偏挑战;Joker 可选百搭。牌义原创中文转录(手册§8.1 择一锁定)。
const SUITS = [
	{ key: 'hearts', cn: '红桃', sym: '♥', polarity: 1, color: '#d6455a' },
	{ key: 'clubs', cn: '梅花', sym: '♣', polarity: -1, color: '#6fae74' },
	{ key: 'diamonds', cn: '方块', sym: '♦', polarity: 1, color: '#e0a64b' },
	{ key: 'spades', cn: '黑桃', sym: '♠', polarity: -1, color: '#9a8fd6' },
];
const RANK_CN = { 1: 'A', 2: '2', 3: '3', 4: '4', 5: '5', 6: '6', 7: '7', 8: '8', 9: '9', 10: '10', 11: 'J', 12: 'Q', 13: 'K' };
const RANK_EN = { 1: 'Ace', 2: 'Two', 3: 'Three', 4: 'Four', 5: 'Five', 6: 'Six', 7: 'Seven', 8: 'Eight', 9: 'Nine', 10: 'Ten', 11: 'Jack', 12: 'Queen', 13: 'King' };
// MEAN[suit][rank] 关键义(手册§8.1)
const MEAN = {
	hearts: { 1: '家·爱之始', 2: '结合·伴侣', 3: '情感需谨慎', 4: '婚姻·不愿变', 5: '嫉妒·犹豫', 6: '慷慨·信任', 7: '失诺·不可靠', 8: '邀约·拜访', 9: '许愿牌·心愿', 10: '好运·幸福', 11: '年轻友人/恋人', 12: '善良女子', 13: '慷慨男子·良谋' },
	clubs: { 1: '财富·好运', 2: '对立·失望', 3: '多次/婚姻(财)', 4: '变动·警惕', 5: '友人相助', 6: '生意成功', 7: '成功但防异性', 8: '钱财烦恼·欲', 9: '固执·争执·运', 10: '意外之财·旅行', 11: '可靠友人', 12: '自信迷人女子', 13: '忠诚男子' },
	diamonds: { 1: '戒指·讯息·钱', 2: '认真恋情', 3: '法律/家庭纠纷', 4: '遗产·钱变动', 5: '顺利·繁荣·子女', 6: '关系波折·早婚', 7: '博弈·被批评', 8: '迟来的关系', 9: '不安·钱讯', 10: '钱·旅行·变化', 11: '不可靠信使/亲戚', 12: '社交·风情女', 13: '固执男·权威' },
	spades: { 1: '重大转折·阻碍', 2: '分离·欺瞒·难择', 3: '别离·泪·远行', 4: '病·嫉妒·忧', 5: '挫折后成功·怒', 6: '渐好·改善', 7: '失·警告·哀', 8: '失望·警告', 9: '最凶·厄运/病', 10: '忧·不幸·黑夜', 11: '善意但不成熟者', 12: '寡居/危险女子', 13: '野心·审判男(律师)' },
};

const cards = [];
SUITS.forEach((suit, si) => {
	for(let rank = 1; rank <= 13; rank++){
		const kw = [MEAN[suit.key][rank]];
		cards.push({
			id: si * 13 + (rank - 1), sid: `card_${suit.key}_${String(rank).padStart(2, '0')}`,
			arcana: 'cartomancy', suit: suit.key, number: rank, court: rank >= 11 ? RANK_EN[rank].toLowerCase() : null,
			name_cn: `${suit.cn}${RANK_CN[rank]}`, name_en: `${RANK_EN[rank]} of ${suit.key.replace(/^\w/, (c) => c.toUpperCase())}`,
			names: null, element: '', symbol: suit.sym, suitColor: suit.color,
			hebrew: null, astro: null, path: null, decanTitle: null, decanPlanet: null, decanSign: null, courtEie: null, courtSpan: null,
			polarity: suit.polarity, countingValue: rank,
			keywords_upright: kw, keywords_reversed: kw, meanings: { up: kw, rev: kw },
		});
	}
});

export const CARTOMANCY_CARDS = cards;

export const CARTOMANCY_DECK = {
	id: 'cartomancy', title: '扑克占卜(52)', nameKey: 'rws', size: 52, structure: '52cart',
	usesReversals: false, pReversed: 0.5, dignities: false, variant: 'A', illustratedPips: false,
	group: '扑克', cards: CARTOMANCY_CARDS,
	caps: { reversals: false, dignities: false, variant: false, significator: false, numOverride: false, embeddedPlayingCard: false, readingMethod: 'cartomancy', colorScale: false, spreads: ['single', 'three', 'three_sit', 'celtic', 'lenormand_box9'] },
};
