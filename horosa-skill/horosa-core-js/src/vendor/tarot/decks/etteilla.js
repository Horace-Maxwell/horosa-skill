// P3 Etteilla 埃特拉(史上第一个职业塔罗系统,首创逐牌正逆位)。
// 结构:78 张、阿拉伯 0–77 编号、droit(正)/renversé(逆)双义、男(Card1)/女(Card8)双指示牌、前 8 张=创世周主题。
// 注:Etteilla 大牌全重排重命名,逐牌精确名因复原版而异(手册 defer),故沿用 78 骨架与原创中文双义,
//     叠加 Etteilla 的「创世周」框架与双指示牌结构(均为 Etteilla 体系的公有领域设定)。
import { CORE78 } from './core78.js';

// 创世周(Grand Etteilla 前 8 张的宇宙主题):Card1 男问者 / 2–7 创世 / Card8 女问者·休憩。
export const ETTEILLA_WEEK = [
	'Etteilla / 男问者(光与混沌)', '启蒙 Éclaircissement', '谈论 Propos', '剥夺 Dépouillement',
	'旅程 Voyage', '夜 La Nuit', '支持 Appui', 'Etteilla / 女问者(休憩 Repos)',
];

// Etteilla 牌:CORE78 + Etteilla 序号(0..77 按牌库顺序)+ 前 8 创世周注 + 双指示牌标记(首/末)。
function buildEtteilla(){
	return CORE78.map((c, idx) => {
		const card = { ...c, etteillaNumber: idx };
		if(idx < ETTEILLA_WEEK.length){ card.etteillaWeek = ETTEILLA_WEEK[idx]; }
		if(idx === 0){ card.etteillaSig = 'man'; }
		if(idx === 7){ card.etteillaSig = 'woman'; }
		return card;
	});
}

export const ETTEILLA_CARDS = buildEtteilla();

export const ETTEILLA_DECK = {
	id: 'etteilla', title: 'Etteilla 埃特拉(78,0–77)', nameKey: 'rws', size: 78, structure: '78major56minor',
	usesReversals: true, pReversed: 0.5, dignities: false, variant: 'A', illustratedPips: true,
	group: '重排体系', cards: ETTEILLA_CARDS,
	// 双指示牌(男 Card1 / 女 Card8)经 significator etteillaDual 处理;不用 GD/大陆字母变体。
	caps: { reversals: true, dignities: false, variant: false, significator: true, etteillaDual: true, numOverride: true, embeddedPlayingCard: false, readingMethod: 'tarot', colorScale: false, spreads: ['single', 'three', 'three_sit', 'horseshoe', 'celtic', 'relation'] },
};
