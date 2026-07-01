// 牌阵注册(通用)。位置序列权威取自公有领域(Waite《Pictorial Key》§7 凯尔特十字等)。
// position={ i, key, label, meaning, alwaysUpright?(恒正位), x?,y?(真实几何,P7 用) }。
// 现有 5 个(single/three/celtic/relation/annual)逐字保留 → facade 零回归;其余为新增。
import { getCard } from '../decks/core78.js'; // 仅占位:实际 getCard 由 reading 注入 deck 卡池

const MONTHS_CN = ['一月', '二月', '三月', '四月', '五月', '六月', '七月', '八月', '九月', '十月', '十一月', '十二月'];

export const SPREADS = {
	single: {
		key: 'single', label: '单张',
		positions: [{ i: 1, key: 'single', label: '核心', meaning: '对所问之事的核心回答', x: 0.5, y: 0.5 }],
	},
	three: {
		key: 'three', label: '三张(过去·现在·未来)',
		positions: [
			{ i: 1, key: 'past', label: '过去', meaning: '已过去或正在消退的影响', x: 0.25, y: 0.5 },
			{ i: 2, key: 'present', label: '现在', meaning: '当前处境与影响', x: 0.5, y: 0.5 },
			{ i: 3, key: 'future', label: '未来', meaning: '正在到来、即将生效的影响', x: 0.75, y: 0.5 },
		],
	},
	three_sit: {
		key: 'three_sit', label: '三张(情况·行动·结果)',
		positions: [
			{ i: 1, key: 'situation', label: '情况', meaning: '当前的处境与背景', x: 0.25, y: 0.5 },
			{ i: 2, key: 'action', label: '行动', meaning: '可采取的行动或态度', x: 0.5, y: 0.5 },
			{ i: 3, key: 'outcome', label: '结果', meaning: '依此行动的可能结果', x: 0.75, y: 0.5 },
		],
	},
	horseshoe: {
		key: 'horseshoe', label: '马蹄铁(7张)',
		positions: [
			{ i: 1, key: 'past', label: '过去', meaning: '已过去的影响', x: 0.12, y: 0.7 },
			{ i: 2, key: 'present', label: '现在', meaning: '当前处境', x: 0.26, y: 0.42 },
			{ i: 3, key: 'hidden', label: '隐藏影响', meaning: '尚未显露的因素', x: 0.4, y: 0.25 },
			{ i: 4, key: 'obstacle', label: '障碍', meaning: '主要的阻碍', x: 0.5, y: 0.2 },
			{ i: 5, key: 'environment', label: '外部环境', meaning: '周围环境与他人态度', x: 0.6, y: 0.25 },
			{ i: 6, key: 'advice', label: '建议', meaning: '可采取的态度或行动', x: 0.74, y: 0.42 },
			{ i: 7, key: 'outcome', label: '最终结果', meaning: '诸影响汇聚的结果', x: 0.88, y: 0.7 },
		],
	},
	celtic: {
		key: 'celtic', label: '凯尔特十字',
		// 十字臂(后/前)与十字中心横向留足,使交叉牌(旋转90°,横向占其高)不压邻牌;权杖列右置。
		positions: [
			{ i: 1, key: 'covers', label: '环绕(现状)', meaning: '笼罩此事的整体氛围与影响', x: 0.30, y: 0.5 },
			{ i: 2, key: 'crosses', label: '交叉(阻碍)', meaning: '阻碍的性质,横压于第一张之上', x: 0.30, y: 0.5 },
			{ i: 3, key: 'crowns', label: '上方(目标)', meaning: '所求的理想、可达成的最好结果(尚未成真)', x: 0.30, y: 0.16 },
			{ i: 4, key: 'beneath', label: '下方(基础)', meaning: '事情的根基,已成为现实的部分', x: 0.30, y: 0.84 },
			{ i: 5, key: 'behind', label: '后方(过去)', meaning: '刚过去或正在消退的影响', x: 0.06, y: 0.5 },
			{ i: 6, key: 'before', label: '前方(未来)', meaning: '即将生效、近期的影响', x: 0.54, y: 0.5 },
			{ i: 7, key: 'himself', label: '自身(态度)', meaning: '问卜者在此境况中的位置与态度', x: 0.86, y: 0.85 },
			{ i: 8, key: 'house', label: '环境(关系)', meaning: '外在环境、亲友影响与趋势', x: 0.86, y: 0.62 },
			{ i: 9, key: 'hopes_fears', label: '希望与恐惧', meaning: '问卜者意识中的希望或恐惧', x: 0.86, y: 0.39 },
			{ i: 10, key: 'outcome', label: '结果(最终)', meaning: '诸影响汇聚而成的最终结果', x: 0.86, y: 0.16 },
		],
	},
	relation: {
		key: 'relation', label: '关系牌阵',
		positions: [
			{ i: 1, key: 'person_a', label: '人物A', meaning: '第一人的感受、视角与处境', x: 0.22, y: 0.5 },
			{ i: 2, key: 'person_b', label: '人物B', meaning: '第二人的感受、视角与处境', x: 0.78, y: 0.5 },
			{ i: 3, key: 'relationship', label: '关系', meaning: '当前关系的动态与本质', x: 0.5, y: 0.18 },
			{ i: 4, key: 'challenge', label: '挑战', meaning: '需面对的主要障碍', x: 0.5, y: 0.5 },
			{ i: 5, key: 'outcome', label: '前景', meaning: '关系的走向', x: 0.5, y: 0.82 },
		],
	},
	croix: {
		key: 'croix', label: '马赛十字(5张)',
		positions: [
			{ i: 1, key: 'self', label: '当事人/现状', meaning: '问卜者当前的处境', x: 0.5, y: 0.5 },
			{ i: 2, key: 'cross', label: '阻碍/影响', meaning: '横亘的影响因素', x: 0.25, y: 0.5 },
			{ i: 3, key: 'above', label: '上方/目标', meaning: '志向与可能', x: 0.5, y: 0.22 },
			{ i: 4, key: 'below', label: '下方/根基', meaning: '潜在根基', x: 0.5, y: 0.78 },
			{ i: 5, key: 'outcome', label: '综合/结论', meaning: '综合的指引', x: 0.75, y: 0.5 },
		],
	},
	tree_of_life: {
		key: 'tree_of_life', label: '生命之树(10质点)',
		// y 间距尽量均匀(同柱最小纵距≥0.18),使真实牌面纵向不挤叠。
		positions: [
			{ i: 1, key: 'kether', label: '1 Kether 王冠', meaning: '最高目标/灵性根源', x: 0.5, y: 0.05 },
			{ i: 2, key: 'chokmah', label: '2 Chokmah 智慧', meaning: '创造冲动/父性', x: 0.74, y: 0.22 },
			{ i: 3, key: 'binah', label: '3 Binah 理解', meaning: '理解/限制/母性', x: 0.26, y: 0.22 },
			{ i: 4, key: 'chesed', label: '4 Chesed 慈悲', meaning: '扩张/恩慈/财务', x: 0.74, y: 0.42 },
			{ i: 5, key: 'geburah', label: '5 Geburah 严厉', meaning: '约束/冲突/勇气', x: 0.26, y: 0.42 },
			{ i: 6, key: 'tiphareth', label: '6 Tiphareth 美', meaning: '核心自我/健康', x: 0.5, y: 0.52 },
			{ i: 7, key: 'netzach', label: '7 Netzach 胜利', meaning: '情感/欲望/关系', x: 0.74, y: 0.66 },
			{ i: 8, key: 'hod', label: '8 Hod 荣耀', meaning: '理智/沟通/事业', x: 0.26, y: 0.66 },
			{ i: 9, key: 'yesod', label: '9 Yesod 基础', meaning: '潜意识/想象', x: 0.5, y: 0.78 },
			{ i: 10, key: 'malkuth', label: '10 Malkuth 王国', meaning: '物质结果/身体', x: 0.5, y: 0.96 },
		],
	},
	zodiac: {
		key: 'zodiac', label: '十二宫(12宫)',
		positions: Array.from({ length: 12 }, (_, idx) => {
			const labels = ['自我/外貌', '金钱/价值', '沟通/学习', '家庭/根基', '创造/恋爱', '健康/工作', '伴侣/合作', '共有资源/转化', '旅行/信念', '事业/名声', '朋友/愿望', '潜意识/隐秘'];
			const ang = (Math.PI / 2) - (idx * Math.PI / 6); // 1宫在左,逆时针
			return { i: idx + 1, key: `house_${idx + 1}`, label: `${idx + 1}宫`, meaning: labels[idx], x: 0.5 + 0.4 * Math.cos(ang + Math.PI), y: 0.5 - 0.4 * Math.sin(ang + Math.PI) };
		}),
	},
	annual: {
		key: 'annual', label: '年度牌阵(12月)',
		positions: [
			{ i: 1, key: 'year_theme', label: '年度主题', meaning: '全年的整体主题与能量' },
		].concat(MONTHS_CN.map((m, idx) => ({ i: idx + 2, key: `month_${idx + 1}`, label: m, meaning: `${m}的运势重点` }))),
	},
	// --- Lenormand/神谕 专属牌阵(无逆位,读法走 lenormandReading) ---
	lenormand_3: {
		key: 'lenormand_3', label: '雷诺曼三张(成句)',
		positions: [
			{ i: 1, key: 'noun', label: '主题', meaning: '核心名词(主题)', alwaysUpright: true, x: 0.25, y: 0.5 },
			{ i: 2, key: 'mod1', label: '修饰一', meaning: '修饰主题', alwaysUpright: true, x: 0.5, y: 0.5 },
			{ i: 3, key: 'mod2', label: '修饰二', meaning: '进一步修饰/落点', alwaysUpright: true, x: 0.75, y: 0.5 },
		],
	},
	lenormand_box9: {
		key: 'lenormand_box9', label: '雷诺曼 9 宫盒(3×3)',
		positions: Array.from({ length: 9 }, (_, i) => ({ i: i + 1, key: `box_${i + 1}`, label: i === 4 ? '焦点' : `位${i + 1}`, meaning: i === 4 ? '核心焦点' : '环绕影响', alwaysUpright: true, x: (i % 3 + 0.5) / 3, y: (Math.floor(i / 3) + 0.5) / 3 })),
	},
	grand_tableau: {
		key: 'grand_tableau', label: '雷诺曼 Grand Tableau(36)',
		positions: Array.from({ length: 36 }, (_, i) => ({ i: i + 1, key: `gt_${i + 1}`, label: `${i + 1}`, meaning: '位置宫义×牌义', alwaysUpright: true, x: ((i % 8) + 0.5) / 8, y: (Math.floor(i / 8) + 0.5) / 5 })),
	},
};

export const SPREAD_KEYS = Object.keys(SPREADS);
export const DEFAULT_SPREAD = 'three';

export function getSpread(spreadType){
	return SPREADS[spreadType] || null;
}

// 抽牌:spreadType + 已洗 {order,reversed} + 卡池(deck.cards,缺省 core getCard)→ [{position,cardId,isReversed,card}]
export function drawSpread(spreadType, shuffleResult, cardResolver){
	const spread = SPREADS[spreadType];
	if(!spread || !shuffleResult || !Array.isArray(shuffleResult.order)){ return []; }
	const resolve = typeof cardResolver === 'function' ? cardResolver : getCard;
	const { order, reversed } = shuffleResult;
	return spread.positions.map((position, idx) => {
		const cardId = order[idx];
		const isReversed = position.alwaysUpright ? false : !!(reversed && reversed[idx]);
		return { position, cardId, isReversed, card: resolve(cardId) };
	});
}

export function orientationLabel(isReversed){
	return isReversed ? '逆位' : '正位';
}
