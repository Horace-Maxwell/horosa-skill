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
	three_mbs: {
		key: 'three_mbs', label: '三张牌·心-身-灵', meaning: '三张牌（最通用）的心-身-灵语义模板，从心智、身体、灵性三层速览。',
		positions: [
			{ i: 1, key: 'three_mbs_1', label: 'Mind 心智', meaning: 'Mind 心智', x: 0.25, y: 0.5 },
			{ i: 2, key: 'three_mbs_2', label: 'Body 身体', meaning: 'Body 身体', x: 0.5, y: 0.5 },
			{ i: 3, key: 'three_mbs_3', label: 'Spirit 灵性', meaning: 'Spirit 灵性', x: 0.75, y: 0.5 },
		],
	},
	three_pcs: {
		key: 'three_pcs', label: '三张牌·问题法', meaning: '三张牌（最通用）的问题法语义模板：问题→成因→解法。',
		positions: [
			{ i: 1, key: 'three_pcs_1', label: '问题 Problem', meaning: '问题 Problem', x: 0.25, y: 0.5 },
			{ i: 2, key: 'three_pcs_2', label: '成因 Cause', meaning: '成因 Cause', x: 0.5, y: 0.5 },
			{ i: 3, key: 'three_pcs_3', label: '解法 Solution', meaning: '解法 Solution', x: 0.75, y: 0.5 },
		],
	},
	three_choice: {
		key: 'three_choice', label: '三张牌·抉择', meaning: '三张牌（最通用）的抉择语义模板：选项A、选项B、关键考量/建议。',
		positions: [
			{ i: 1, key: 'three_choice_1', label: '选项A', meaning: '选项A', x: 0.25, y: 0.5 },
			{ i: 2, key: 'three_choice_2', label: '选项B', meaning: '选项B', x: 0.5, y: 0.5 },
			{ i: 3, key: 'three_choice_3', label: '关键考量/建议', meaning: '关键考量/建议', x: 0.75, y: 0.5 },
		],
	},
	horseshoe5: {
		key: 'horseshoe5', label: '马蹄铁（5张）', meaning: '马蹄铁牌阵5张版（U形），较7张版省去「隐藏影响」与「外部环境」两位。',
		positions: [
			{ i: 1, key: 'horseshoe5_1', label: '过去', meaning: '过去', x: 0.14, y: 0.66 },
			{ i: 2, key: 'horseshoe5_2', label: '现在', meaning: '现在', x: 0.31, y: 0.4 },
			{ i: 3, key: 'horseshoe5_3', label: '障碍（中央，部分版本有第4位于中）', meaning: '障碍（中央，部分版本有第4位于中）', x: 0.5, y: 0.28 },
			{ i: 4, key: 'horseshoe5_4', label: '建议', meaning: '建议', x: 0.69, y: 0.4 },
			{ i: 5, key: 'horseshoe5_5', label: '最终结果', meaning: '最终结果', x: 0.86, y: 0.66 },
		],
	},
	relation7: {
		key: 'relation7', label: '关系牌阵·进阶（关系十字）', meaning: '关系牌阵·进阶（Relationship Cross，7张）。',
		positions: [
			{ i: 1, key: 'relation7_1', label: '你', meaning: '你', x: 0.18, y: 0.55 },
			{ i: 2, key: 'relation7_2', label: '对方', meaning: '对方', x: 0.82, y: 0.55 },
			{ i: 3, key: 'relation7_3', label: '关系本质', meaning: '关系本质', x: 0.5, y: 0.5 },
			{ i: 4, key: 'relation7_4', label: '你给予/需求', meaning: '你给予/需求', x: 0.32, y: 0.82 },
			{ i: 5, key: 'relation7_5', label: '关系走向', meaning: '关系走向', x: 0.5, y: 0.86 },
			{ i: 6, key: 'relation7_6', label: '对方给予/需求', meaning: '对方给予/需求', x: 0.68, y: 0.82 },
			{ i: 7, key: 'relation7_7', label: '该学的课题/建议', meaning: '该学的课题/建议', x: 0.5, y: 0.12 },
		],
	},
	zodiac13: {
		key: 'zodiac13', label: '十二宫/星盘牌阵', meaning: '十二宫/星盘牌阵，12张围成钟面圈按生活领域各读一张，可选中心第13张为「全年主题/自我」。',
		positions: [
			{ i: 1, key: 'zodiac13_1', label: '自我/外貌', meaning: '自我/外貌', x: 0.5, y: 0.12 },
			{ i: 2, key: 'zodiac13_2', label: '金钱/价值', meaning: '金钱/价值', x: 0.69, y: 0.171 },
			{ i: 3, key: 'zodiac13_3', label: '沟通/学习', meaning: '沟通/学习', x: 0.829, y: 0.31 },
			{ i: 4, key: 'zodiac13_4', label: '家庭/根基', meaning: '家庭/根基', x: 0.88, y: 0.5 },
			{ i: 5, key: 'zodiac13_5', label: '创造/恋爱', meaning: '创造/恋爱', x: 0.829, y: 0.69 },
			{ i: 6, key: 'zodiac13_6', label: '健康/工作', meaning: '健康/工作', x: 0.69, y: 0.829 },
			{ i: 7, key: 'zodiac13_7', label: '伴侣/合作', meaning: '伴侣/合作', x: 0.5, y: 0.88 },
			{ i: 8, key: 'zodiac13_8', label: '共有资源/转化', meaning: '共有资源/转化', x: 0.31, y: 0.829 },
			{ i: 9, key: 'zodiac13_9', label: '旅行/信念', meaning: '旅行/信念', x: 0.171, y: 0.69 },
			{ i: 10, key: 'zodiac13_10', label: '事业/名声', meaning: '事业/名声', x: 0.12, y: 0.5 },
			{ i: 11, key: 'zodiac13_11', label: '朋友/愿望', meaning: '朋友/愿望', x: 0.171, y: 0.31 },
			{ i: 12, key: 'zodiac13_12', label: '潜意识/隐秘', meaning: '潜意识/隐秘', x: 0.31, y: 0.171 },
			{ i: 13, key: 'zodiac13_13', label: '中心', meaning: '全年主题/自我', x: 0.5, y: 0.5 },
		],
	},
	decision6: {
		key: 'decision6', label: '抉择牌阵', meaning: '抉择牌阵（两路对比，6张）。',
		positions: [
			{ i: 1, key: 'decision6_1', label: '1A 选项A现状', meaning: '1A 选项A现状', x: 0.25, y: 0.3 },
			{ i: 2, key: 'decision6_2', label: '2A 选A的结果', meaning: '2A 选A的结果', x: 0.25, y: 0.64 },
			{ i: 3, key: 'decision6_3', label: '3B 选项B现状', meaning: '3B 选项B现状', x: 0.75, y: 0.3 },
			{ i: 4, key: 'decision6_4', label: '4B 选B的结果', meaning: '4B 选B的结果', x: 0.75, y: 0.64 },
			{ i: 5, key: 'decision6_5', label: '5 高我建议', meaning: '5 高我建议', x: 0.5, y: 0.1 },
			{ i: 6, key: 'decision6_6', label: '6 你内心真实倾向', meaning: '6 你内心真实倾向', x: 0.5, y: 0.9 },
		],
	},
	career7: {
		key: 'career7', label: '事业牌阵', meaning: '事业牌阵（7张）。',
		positions: [
			{ i: 1, key: 'career7_1', label: '现状', meaning: '现状', x: 0.5, y: 0.5 },
			{ i: 2, key: 'career7_2', label: '你的技能优势', meaning: '你的技能优势', x: 0.2, y: 0.28 },
			{ i: 3, key: 'career7_3', label: '障碍', meaning: '障碍', x: 0.8, y: 0.28 },
			{ i: 4, key: 'career7_4', label: '隐藏机会', meaning: '隐藏机会', x: 0.2, y: 0.72 },
			{ i: 5, key: 'career7_5', label: '该采取的行动', meaning: '该采取的行动', x: 0.8, y: 0.72 },
			{ i: 6, key: 'career7_6', label: '他人/环境', meaning: '他人/环境', x: 0.5, y: 0.12 },
			{ i: 7, key: 'career7_7', label: '6–12月走向', meaning: '6–12月走向', x: 0.5, y: 0.88 },
		],
	},
	money5: {
		key: 'money5', label: '财务牌阵', meaning: '财务牌阵（5张）。',
		positions: [
			{ i: 1, key: 'money5_1', label: '当前财务状况', meaning: '当前财务状况', x: 0.5, y: 0.5 },
			{ i: 2, key: 'money5_2', label: '收入来源/潜力', meaning: '收入来源/潜力', x: 0.2, y: 0.34 },
			{ i: 3, key: 'money5_3', label: '漏洞/支出风险', meaning: '漏洞/支出风险', x: 0.8, y: 0.34 },
			{ i: 4, key: 'money5_4', label: '改善行动', meaning: '改善行动', x: 0.34, y: 0.82 },
			{ i: 5, key: 'money5_5', label: '中期前景', meaning: '中期前景', x: 0.66, y: 0.82 },
		],
	},
	chakra7: {
		key: 'chakra7', label: '脉轮牌阵', meaning: '脉轮牌阵（7张，纵向自下而上），逐位读该能量中心当前状态+失衡提示。',
		positions: [
			{ i: 1, key: 'chakra7_1', label: '海底 Root', meaning: '安全/生存', x: 0.5, y: 0.07 },
			{ i: 2, key: 'chakra7_2', label: '脐轮 Sacral', meaning: '情感/性/创造', x: 0.5, y: 0.213 },
			{ i: 3, key: 'chakra7_3', label: '太阳神经丛 Solar', meaning: '自我/力量', x: 0.5, y: 0.357 },
			{ i: 4, key: 'chakra7_4', label: '心轮 Heart', meaning: '爱/关系', x: 0.5, y: 0.5 },
			{ i: 5, key: 'chakra7_5', label: '喉轮 Throat', meaning: '表达/真实', x: 0.5, y: 0.643 },
			{ i: 6, key: 'chakra7_6', label: '眉心 Third-Eye', meaning: '直觉/洞察', x: 0.5, y: 0.787 },
			{ i: 7, key: 'chakra7_7', label: '顶轮 Crown', meaning: '灵性/连接', x: 0.5, y: 0.93 },
		],
	},
	year_wheel13: {
		key: 'year_wheel13', label: '年轮牌阵', meaning: '年轮牌阵（13张），12张按钟面圈布（1点钟=本月或1月，顺时针）代表各月，中心第13张=全年主线；按时间。',
		positions: [
			{ i: 1, key: 'year_wheel13_1', label: '第1月', meaning: '该月主题/事件/建议', x: 0.5, y: 0.12 },
			{ i: 2, key: 'year_wheel13_2', label: '第2月', meaning: '该月主题/事件/建议', x: 0.69, y: 0.171 },
			{ i: 3, key: 'year_wheel13_3', label: '第3月', meaning: '该月主题/事件/建议', x: 0.829, y: 0.31 },
			{ i: 4, key: 'year_wheel13_4', label: '第4月', meaning: '该月主题/事件/建议', x: 0.88, y: 0.5 },
			{ i: 5, key: 'year_wheel13_5', label: '第5月', meaning: '该月主题/事件/建议', x: 0.829, y: 0.69 },
			{ i: 6, key: 'year_wheel13_6', label: '第6月', meaning: '该月主题/事件/建议', x: 0.69, y: 0.829 },
			{ i: 7, key: 'year_wheel13_7', label: '第7月', meaning: '该月主题/事件/建议', x: 0.5, y: 0.88 },
			{ i: 8, key: 'year_wheel13_8', label: '第8月', meaning: '该月主题/事件/建议', x: 0.31, y: 0.829 },
			{ i: 9, key: 'year_wheel13_9', label: '第9月', meaning: '该月主题/事件/建议', x: 0.171, y: 0.69 },
			{ i: 10, key: 'year_wheel13_10', label: '第10月', meaning: '该月主题/事件/建议', x: 0.12, y: 0.5 },
			{ i: 11, key: 'year_wheel13_11', label: '第11月', meaning: '该月主题/事件/建议', x: 0.171, y: 0.31 },
			{ i: 12, key: 'year_wheel13_12', label: '第12月', meaning: '该月主题/事件/建议', x: 0.31, y: 0.171 },
			{ i: 13, key: 'year_wheel13_13', label: '中心', meaning: '全年主线', x: 0.5, y: 0.5 },
		],
	},
	seven_planets7: {
		key: 'seven_planets7', label: '七行星牌阵', meaning: '七行星牌阵（7张），按古典七行星各管一域。',
		positions: [
			{ i: 1, key: 'seven_planets7_1', label: '☽ Moon', meaning: '情绪/家宅/潜意识', x: 0.5, y: 0.14 },
			{ i: 2, key: 'seven_planets7_2', label: '☿ Mercury', meaning: '沟通/学习/旅行', x: 0.781, y: 0.276 },
			{ i: 3, key: 'seven_planets7_3', label: '♀ Venus', meaning: '爱/美/金钱', x: 0.851, y: 0.58 },
			{ i: 4, key: 'seven_planets7_4', label: '☉ Sun', meaning: '自我/活力/目标', x: 0.656, y: 0.824 },
			{ i: 5, key: 'seven_planets7_5', label: '♂ Mars', meaning: '行动/冲突/欲望', x: 0.344, y: 0.824 },
			{ i: 6, key: 'seven_planets7_6', label: '♃ Jupiter', meaning: '扩张/机遇/信念', x: 0.149, y: 0.58 },
			{ i: 7, key: 'seven_planets7_7', label: '♄ Saturn', meaning: '限制/责任/课题', x: 0.219, y: 0.276 },
		],
	},
	pyramid10: {
		key: 'pyramid10', label: '金字塔牌阵', meaning: '金字塔牌阵（10张，4层），自下而上读：基座(根基)→影响→趋势→顶(结论)。',
		positions: [
			{ i: 1, key: 'pyramid10_1', label: '基座', meaning: '现状根基', x: 0.2, y: 0.9 },
			{ i: 2, key: 'pyramid10_2', label: '基座', meaning: '现状根基', x: 0.4, y: 0.9 },
			{ i: 3, key: 'pyramid10_3', label: '基座', meaning: '现状根基', x: 0.6, y: 0.9 },
			{ i: 4, key: 'pyramid10_4', label: '基座', meaning: '现状根基', x: 0.8, y: 0.9 },
			{ i: 5, key: 'pyramid10_5', label: '第2层', meaning: '影响因素', x: 0.3, y: 0.63 },
			{ i: 6, key: 'pyramid10_6', label: '第2层', meaning: '影响因素', x: 0.5, y: 0.63 },
			{ i: 7, key: 'pyramid10_7', label: '第2层', meaning: '影响因素', x: 0.7, y: 0.63 },
			{ i: 8, key: 'pyramid10_8', label: '第3层', meaning: '趋势', x: 0.4, y: 0.36 },
			{ i: 9, key: 'pyramid10_9', label: '第3层', meaning: '趋势', x: 0.6, y: 0.36 },
			{ i: 10, key: 'pyramid10_10', label: '顶', meaning: '最终综合/灵性升华', x: 0.5, y: 0.1 },
		],
	},
	shadow5: {
		key: 'shadow5', label: '阴影/内在功课牌阵', meaning: '阴影/内在功课牌阵（5张），心理向牌阵，重在自我觉察而非预测。',
		positions: [
			{ i: 1, key: 'shadow5_1', label: '我压抑/否认的部分', meaning: '我压抑/否认的部分', x: 0.5, y: 0.12 },
			{ i: 2, key: 'shadow5_2', label: '它如何影响我', meaning: '它如何影响我', x: 0.28, y: 0.37 },
			{ i: 3, key: 'shadow5_3', label: '它的根源', meaning: '它的根源', x: 0.5, y: 0.5 },
			{ i: 4, key: 'shadow5_4', label: '如何整合它', meaning: '如何整合它', x: 0.72, y: 0.63 },
			{ i: 5, key: 'shadow5_5', label: '整合后的礼物', meaning: '整合后的礼物', x: 0.5, y: 0.88 },
		],
	},
	celtic6: {
		key: 'celtic6', label: '凯尔特十字·缩简版', meaning: '凯尔特十字缩简版（6张），仅留现状/横压/上/下/后/前（去掉右侧塔的自我-环境-希望-结果）。',
		positions: [
			{ i: 1, key: 'celtic6_1', label: '现状', meaning: '问者当前核心处境（"This covers him"）', x: 0.34, y: 0.5 },
			{ i: 2, key: 'celtic6_2', label: '横压', meaning: '阻碍或助力（横置；永远正读）', x: 0.34, y: 0.5 },
			{ i: 3, key: 'celtic6_3', label: '上', meaning: '目标、显意识、最佳结果、笼罩之事', x: 0.34, y: 0.14 },
			{ i: 4, key: 'celtic6_4', label: '下', meaning: '根基、潜意识、事件根源', x: 0.34, y: 0.86 },
			{ i: 5, key: 'celtic6_5', label: '后', meaning: '刚过去/正离开的影响', x: 0.08, y: 0.5 },
			{ i: 6, key: 'celtic6_6', label: '前', meaning: '即将到来', x: 0.6, y: 0.5 },
		],
	},
	celtic11: {
		key: 'celtic11', label: '凯尔特十字·加权版', meaning: '凯尔特十字加权版（11张），标准10张+第11张「高我总建议/精华牌」。',
		positions: [
			{ i: 1, key: 'celtic11_1', label: '现状', meaning: '问者当前核心处境（"This covers him"）', x: 0.3, y: 0.5 },
			{ i: 2, key: 'celtic11_2', label: '横压牌', meaning: '阻碍或助力（横置；永远正读）', x: 0.3, y: 0.5 },
			{ i: 3, key: 'celtic11_3', label: '上', meaning: '目标、显意识、最佳结果、笼罩之事', x: 0.3, y: 0.14 },
			{ i: 4, key: 'celtic11_4', label: '下', meaning: '根基、潜意识、事件根源', x: 0.3, y: 0.86 },
			{ i: 5, key: 'celtic11_5', label: '后', meaning: '刚过去/正离开的影响', x: 0.06, y: 0.5 },
			{ i: 6, key: 'celtic11_6', label: '前', meaning: '即将到来', x: 0.54, y: 0.5 },
			{ i: 7, key: 'celtic11_7', label: '自我', meaning: '问者态度、当前自我状态', x: 0.86, y: 0.85 },
			{ i: 8, key: 'celtic11_8', label: '环境', meaning: '他人、外部影响、家庭/社会', x: 0.86, y: 0.61 },
			{ i: 9, key: 'celtic11_9', label: '希望与恐惧', meaning: '内在期待与忧惧（两面）', x: 0.86, y: 0.37 },
			{ i: 10, key: 'celtic11_10', label: '结果', meaning: '综合最终走向', x: 0.86, y: 0.13 },
			{ i: 11, key: 'celtic11_11', label: '高我总建议/精华牌', meaning: '高我总建议/精华牌', x: 0.68, y: 0.85 },
		],
	},
	moon8: {
		key: 'moon8', label: '月相牌阵', meaning: '月相牌阵（8张，循环），对应一个项目/关系从「萌发→推进→高峰→收束」的8阶段。',
		positions: [
			{ i: 1, key: 'moon8_1', label: '新月', meaning: '新月', x: 0.5, y: 0.12 },
			{ i: 2, key: 'moon8_2', label: '盈凸', meaning: '盈凸', x: 0.769, y: 0.231 },
			{ i: 3, key: 'moon8_3', label: '上弦', meaning: '上弦', x: 0.88, y: 0.5 },
			{ i: 4, key: 'moon8_4', label: '盈', meaning: '盈', x: 0.769, y: 0.769 },
			{ i: 5, key: 'moon8_5', label: '满月', meaning: '满月', x: 0.5, y: 0.88 },
			{ i: 6, key: 'moon8_6', label: '亏凸', meaning: '亏凸', x: 0.231, y: 0.769 },
			{ i: 7, key: 'moon8_7', label: '下弦', meaning: '下弦', x: 0.12, y: 0.5 },
			{ i: 8, key: 'moon8_8', label: '残月', meaning: '残月', x: 0.231, y: 0.231 },
		],
	},
	morning3: {
		key: 'morning3', label: '晨间三牌', meaning: '晨间三牌（轻量日用）。',
		positions: [
			{ i: 1, key: 'morning3_1', label: '今日机会', meaning: '今日机会', x: 0.25, y: 0.5 },
			{ i: 2, key: 'morning3_2', label: '今日挑战', meaning: '今日挑战', x: 0.5, y: 0.5 },
			{ i: 3, key: 'morning3_3', label: '今日建议', meaning: '今日建议', x: 0.75, y: 0.5 },
		],
	},
	review3: {
		key: 'review3', label: '复盘三牌', meaning: '复盘三牌（轻量日用）。',
		positions: [
			{ i: 1, key: 'review3_1', label: '今日发生了什么', meaning: '今日发生了什么', x: 0.25, y: 0.5 },
			{ i: 2, key: 'review3_2', label: '我学到什么', meaning: '我学到什么', x: 0.5, y: 0.5 },
			{ i: 3, key: 'review3_3', label: '明日带走什么', meaning: '明日带走什么', x: 0.75, y: 0.5 },
		],
	},
	spiritual5: {
		key: 'spiritual5', label: '灵性指引牌阵', meaning: '灵性指引牌阵（5张十字）。',
		positions: [
			{ i: 1, key: 'spiritual5_1', label: '中心', meaning: '核心课题', x: 0.5, y: 0.5 },
			{ i: 2, key: 'spiritual5_2', label: '上', meaning: '高我指引', x: 0.5, y: 0.16 },
			{ i: 3, key: 'spiritual5_3', label: '下', meaning: '身体/现实', x: 0.5, y: 0.84 },
			{ i: 4, key: 'spiritual5_4', label: '左', meaning: '该放下的', x: 0.2, y: 0.5 },
			{ i: 5, key: 'spiritual5_5', label: '右', meaning: '该迎接的', x: 0.8, y: 0.5 },
		],
	},
	opening_of_key: {
		key: 'opening_of_key', label: '开钥(Opening of the Key·78张五操作)', meaning: '金色黎明/托特招牌大牌阵:全78张五操作,须选指示牌;读法走专属分堆视图。',
		positionCount: 78, ook: true,
		positions: [{ i: 1, key: 'ook', label: '开钥·五操作', meaning: '以指示牌为锚,五操作分堆计数配对', x: 0.5, y: 0.5 }],
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

// 通用塔罗牌阵清单(不含雷诺曼专属阵与 opening_of_key;全为位置制,最大 13 位 ≤ 22 张 → 22 大牌牌组亦可行)。
// 单一真值:78 张核心牌组、22 大牌牌组(Wirth/Egyptian)、BOTA 均取此清单,避免各处漂移。
export const TAROT_SPREADS = [
	'single', 'three', 'three_sit', 'three_mbs', 'three_pcs', 'three_choice', 'morning3', 'review3',
	'horseshoe', 'horseshoe5', 'celtic', 'celtic6', 'celtic11', 'croix', 'relation', 'relation7',
	'tree_of_life', 'zodiac', 'zodiac13', 'annual', 'year_wheel13',
	'decision6', 'career7', 'money5', 'chakra7', 'seven_planets7', 'pyramid10', 'shadow5', 'moon8', 'spiritual5',
];
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
