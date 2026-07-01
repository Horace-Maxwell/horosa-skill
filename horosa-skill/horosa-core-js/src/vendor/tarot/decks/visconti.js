// P6 Visconti-Sforza 及历史意大利牌(15 世纪米兰手绘金箔,公有领域)。
// 原牌无编号无名(号与名后世所加);现存约 74 张(部分缺失/后补);大牌序按 Dummett A/B/C 地区序。
// 以 78 骨架为底,提供「无编号」历史呈现 + 地区 trump 序设置(C 米兰=现代主流);逐张华贵图义沿用原创转录。
import { CORE78 } from './core78.js';

// Dummett 三大牌序(A 南方 Bologna/Florence / B 东方 Ferrara / C 西方 Milan=现代主流)
// 差异集中在三美德(Justice/Strength/Temperance)与 World/Judgement 顶端位次;C 序=现状(8/11 同马赛)。
export const DUMMETT_ORDERS = {
	C: { label: 'C 西方(米兰·现代主流)', note: 'Justice=8、Strength=11(实为 C 型 VIII/XI)、World 居顶' },
	A: { label: 'A 南方(Bologna/Florence)', note: '三美德相邻成组;Angel(审判)常为最高牌;四教皇同阶可互换' },
	B: { label: 'B 东方(Ferrara)', note: '美德分散;World 与 Angel 相对位次不同' },
};

export const VISCONTI_CARDS = CORE78.map((c) => ({ ...c, arcana: c.arcana === 'major' ? 'visconti_trump' : c.arcana }));

export const VISCONTI_DECK = {
	id: 'visconti', title: 'Visconti-Sforza(历史·~78)', nameKey: 'tdm', size: 78, structure: '78major56minor',
	usesReversals: false, pReversed: 0.5, dignities: false, variant: 'C', illustratedPips: false,
	group: '历史扩展', cards: VISCONTI_CARDS, dummettOrder: 'C',
	caps: { reversals: false, dignities: false, variant: true, significator: false, numOverride: true, embeddedPlayingCard: false, readingMethod: 'tarot', colorScale: false, dummett: true, spreads: ['single', 'three', 'three_sit', 'celtic', 'croix'] },
};
