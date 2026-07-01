// P2 大陆派/RWS 衍生牌组:Wirth(22 大牌)/ BOTA(78)/ Egyptian(22 大牌)。共享 CORE78 骨架,差异=配置。
import { CORE78 } from './core78.js';

const MAJORS22 = CORE78.filter((c) => c.arcana === 'major'); // 22 大牌(id 0..21)

// Wirth 维尔特(仅 22 大牌·大陆派变体C·无小牌·无逆位·炼金共济会象征)
export const WIRTH_DECK = {
	id: 'wirth', title: 'Oswald Wirth 维尔特(22 大牌)', nameKey: 'tdm', size: 22, structure: '22major',
	usesReversals: false, pReversed: 0.5, dignities: false, variant: 'C', illustratedPips: false,
	group: '大牌系', cards: MAJORS22,
	caps: { reversals: false, dignities: false, variant: true, significator: false, numOverride: true, embeddedPlayingCard: false, readingMethod: 'tarot', colorScale: false, spreads: ['single', 'three', 'three_sit', 'celtic', 'croix'] },
};

// BOTA(78·RWS 骨架·印希伯来字母变体A·King 色阶·黑白待上色)
export const BOTA_DECK = {
	id: 'bota', title: 'BOTA(Paul Foster Case,78)', nameKey: 'rws', size: 78, structure: '78major56minor',
	usesReversals: true, pReversed: 0.5, dignities: false, variant: 'A', illustratedPips: true,
	group: '七十八张体系', cards: CORE78,
	caps: { reversals: true, dignities: false, variant: true, significator: true, numOverride: true, embeddedPlayingCard: false, readingMethod: 'tarot', colorScale: true, spreads: ['single', 'three', 'three_sit', 'horseshoe', 'celtic', 'relation', 'tree_of_life', 'zodiac', 'annual'] },
};

// Egyptian "埃及式"(22 大牌·大陆派 Fool=Shin·占星-数字-埃及意象)
export const EGYPTIAN_DECK = {
	id: 'egyptian', title: '埃及式塔罗(22 大牌)', nameKey: 'tdm', size: 22, structure: '22major',
	usesReversals: false, pReversed: 0.5, dignities: false, variant: 'C', illustratedPips: false,
	group: '大牌系', cards: MAJORS22,
	caps: { reversals: false, dignities: false, variant: true, significator: false, numOverride: true, embeddedPlayingCard: false, readingMethod: 'tarot', colorScale: false, spreads: ['single', 'three', 'three_sit', 'celtic', 'croix'] },
};

export const CONTINENTAL_DECKS = [WIRTH_DECK, BOTA_DECK, EGYPTIAN_DECK];
