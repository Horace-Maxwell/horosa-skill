// P6 Minchiate(佛罗伦萨 97 张,塔罗最大扩展,公有领域)。
// 97 = 41 trump + 56 minor。trump = 21 标准大牌(去女教皇) + 12 星座 + 4 元素 + 4 德(信/望/爱/审慎)。
// minor = 4 花色×14(宫廷含女侍 Maid)。精确佛罗伦萨编号序手册 defer Dummett,此处按文档类目顺序构造。
import { CORE78 } from './core78.js';

const ZODIAC = ['白羊座', '金牛座', '双子座', '巨蟹座', '狮子座', '处女座', '天秤座', '天蝎座', '射手座', '摩羯座', '水瓶座', '双鱼座'];
const ELEMENTS = ['火', '水', '气', '土'];
const VIRTUES = [['信德', '信仰、虔诚、坚信'], ['望德', '希望、期盼、前景'], ['仁德', '仁爱、慈悲、给予'], ['审慎', '审慎、节度、远虑']];

function buildMinchiate(){
	const cards = [];
	let id = 0;
	// 41 trump:21 标准大牌(去女教皇 high_priestess)
	CORE78.filter((c) => c.arcana === 'major' && c.sid !== 'high_priestess').forEach((c) => {
		cards.push({ ...c, id: id++, arcana: 'minchiate_trump', suit: 'minchiate' });
	});
	// + 4 德
	VIRTUES.forEach((v, i) => {
		cards.push({ id: id++, sid: `minchiate_virtue_${i}`, arcana: 'minchiate_trump', suit: 'minchiate', number: null, court: null, name_cn: v[0], name_en: ['Faith', 'Hope', 'Charity', 'Prudence'][i], names: null, element: '', symbol: '✠', polarity: 1, countingValue: 0, keywords_upright: [v[1]], keywords_reversed: [v[1]], meanings: { up: [v[1]], rev: [v[1]] } });
	});
	// + 4 元素
	ELEMENTS.forEach((e, i) => {
		cards.push({ id: id++, sid: `minchiate_elem_${i}`, arcana: 'minchiate_trump', suit: 'minchiate', number: null, court: null, name_cn: `元素·${e}`, name_en: ['Fire', 'Water', 'Air', 'Earth'][i], names: null, element: '', symbol: '🜂', polarity: 0, countingValue: 0, keywords_upright: [`${e}元素之力`], keywords_reversed: [`${e}元素之力`], meanings: { up: [`${e}元素之力`], rev: [`${e}元素之力`] } });
	});
	// + 12 星座
	ZODIAC.forEach((z, i) => {
		cards.push({ id: id++, sid: `minchiate_zod_${i}`, arcana: 'minchiate_trump', suit: 'minchiate', number: null, court: null, name_cn: z, name_en: z, names: null, element: '', symbol: '♈', polarity: 0, countingValue: 0, keywords_upright: [`${z}主题`], keywords_reversed: [`${z}主题`], meanings: { up: [`${z}主题`], rev: [`${z}主题`] } });
	});
	// 56 minor(宫廷含女侍 Maid;沿用 CORE78 小牌结构)
	CORE78.filter((c) => c.arcana === 'minor').forEach((c) => {
		cards.push({ ...c, id: id++, arcana: 'minchiate_minor' });
	});
	return cards;
}

export const MINCHIATE_CARDS = buildMinchiate();

export const MINCHIATE_DECK = {
	id: 'minchiate', title: 'Minchiate 佛罗伦萨(97)', nameKey: 'rws', size: MINCHIATE_CARDS.length, structure: '97minchiate',
	usesReversals: false, pReversed: 0.5, dignities: false, variant: 'A', illustratedPips: false,
	group: '历史扩展', cards: MINCHIATE_CARDS,
	caps: { reversals: false, dignities: false, variant: false, significator: false, numOverride: true, embeddedPlayingCard: false, readingMethod: 'tarot', colorScale: false, spreads: ['single', 'three', 'three_sit', 'celtic', 'horseshoe'] },
};
