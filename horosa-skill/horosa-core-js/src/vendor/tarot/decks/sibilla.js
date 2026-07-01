// P4 Sibilla 西比拉(意大利 19 世纪「命运女神」52 张,场景化日常占卜)。
// 历史上 Sibilla 多由扑克牌衍生;手册仅给结构(52 张、场景化),逐牌场景因版本而异(不臆断),
// 故以扑克 52 结构为底(意式 Sibilla 的历史基础)+ Sibilla 命运框架命名。读法走扑克同构。
import { CARTOMANCY_CARDS } from './cartomancy.js';

export const SIBILLA_CARDS = CARTOMANCY_CARDS.map((c) => ({ ...c, sid: c.sid.replace('card_', 'sibilla_'), arcana: 'sibilla' }));

export const SIBILLA_DECK = {
	id: 'sibilla', title: 'Sibilla 西比拉(52)', nameKey: 'rws', size: 52, structure: '52cart',
	usesReversals: false, pReversed: 0.5, dignities: false, variant: 'A', illustratedPips: false,
	group: '神谕牌', cards: SIBILLA_CARDS,
	caps: { reversals: false, dignities: false, variant: false, significator: false, numOverride: false, embeddedPlayingCard: false, readingMethod: 'cartomancy', colorScale: false, spreads: ['single', 'three', 'three_sit', 'lenormand_box9'] },
};
