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
			{ i: 2, key: 'crosses', label: '交叉(阻碍)', meaning: '阻碍的性质,横压于第一张之上', crossFixed: true, x: 0.30, y: 0.5 },
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
			{ i: 2, key: 'celtic6_2', label: '横压', meaning: '阻碍或助力（横置；永远正读）', crossFixed: true, x: 0.34, y: 0.5 },
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
			{ i: 2, key: 'celtic11_2', label: '横压牌', meaning: '阻碍或助力（横置；永远正读）', crossFixed: true, x: 0.3, y: 0.5 },
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
	first_reversal: {
		key: 'first_reversal', label: '单张逆位占卜', firstReversal: true,
		meaning: '沿已洗牌序逐张翻至「第一张逆位牌」,以其为唯一讯息载体;翻牌张数即能量诊断(须开启逆位)。',
		positions: [{ i: 1, key: 'first_rx', label: '首张逆位牌', meaning: '受阻/内向/待突破之处的讯息', x: 0.5, y: 0.5 }],
		questions: [
			'什么受到了阻碍或延误?',
			'我没有看到自己内在的什么?',
			'我在哪里遭遇困难?',
			'我在突破或颠覆什么?',
			'有什么新的观念在等我认同?',
			'这个情况的窍门在哪里?',
		],
	},
	// ═══════════ TP5 牌阵扩容(五书补齐):以下 35 阵按古法位义原创转述;缺阵图者按位义自拟几何 ═══════════
	// —— 双牌/三牌协议族 ——
	conflict2: {
		key: 'conflict2', label: '冲突两阶(2张)', meaning: '一愿一障两阶段读:障碍先横压于愿望之上;判其可克,则移至愿望之下为承托。',
		positions: [
			{ i: 1, key: 'wish', label: '愿望/情境', meaning: '所愿之事或当前情境', x: 0.38, y: 0.5 },
			{ i: 2, key: 'obstacle', label: '障碍(两阶)', meaning: '阻碍所在——先横压其上;能克则移其下为踏脚', x: 0.62, y: 0.5 },
		],
	},
	family3: {
		key: 'family3', label: '家庭三角(3张)', meaning: '母系-自我-父系三角构图:两股来处之力如何汇入中间的我。',
		positions: [
			{ i: 1, key: 'mother', label: '母系/阴性影响', meaning: '来自母系/承受端的塑造', x: 0.2, y: 0.32 },
			{ i: 2, key: 'self', label: '中心/自我', meaning: '承接两股影响的我', x: 0.5, y: 0.78 },
			{ i: 3, key: 'father', label: '父系/阳性影响', meaning: '来自父系/主动端的塑造', x: 0.8, y: 0.32 },
		],
	},
	forces3: {
		key: 'forces3', label: '力之作用(3张)', meaning: '承受力-中心-主动力:两翼是托举中心还是压埋中心,一眼见分晓。',
		positions: [
			{ i: 1, key: 'receptive', label: '承受之力', meaning: '接纳/滋养端的力量', x: 0.22, y: 0.68 },
			{ i: 2, key: 'center', label: '中心', meaning: '事情/我自身', x: 0.5, y: 0.35 },
			{ i: 3, key: 'active', label: '主动之力', meaning: '推动/行动端的力量', x: 0.78, y: 0.68 },
		],
	},
	sentence3: {
		key: 'sentence3', label: '句子读法(3张)', meaning: '三张连成一句话:主语-谓语-宾语,以句意直断。',
		positions: [
			{ i: 1, key: 'subject', label: '主语', meaning: '谁/什么在发动', x: 0.25, y: 0.5 },
			{ i: 2, key: 'verb', label: '谓语', meaning: '正在如何作用', x: 0.5, y: 0.5 },
			{ i: 3, key: 'object', label: '宾语', meaning: '落在何处/何人', x: 0.75, y: 0.5 },
		],
	},
	yes_but3: {
		key: 'yes_but3', label: '是-但-所以(3张)', meaning: '肯定-转折-出路的三段句式,专解「能不能」类犹疑。',
		positions: [
			{ i: 1, key: 'yes', label: '是(可行处)', meaning: '此事可行/已具备的', x: 0.25, y: 0.5 },
			{ i: 2, key: 'but', label: '但(碍难处)', meaning: '横亘的转折与限制', x: 0.5, y: 0.5 },
			{ i: 3, key: 'so', label: '所以(中道)', meaning: '兼顾两端的行法', x: 0.75, y: 0.5 },
		],
	},
	protagonist3: {
		key: 'protagonist3', label: '主角-调停-对手(3张)', meaning: '相争两造与居中调停;若问者自落对手位,倒置本身即讯息。',
		positions: [
			{ i: 1, key: 'protagonist', label: '主角', meaning: '发起的一方(常为问者)', x: 0.2, y: 0.5 },
			{ i: 2, key: 'mediator', label: '调停', meaning: '居中转圜的力量', x: 0.5, y: 0.3 },
			{ i: 3, key: 'antagonist', label: '对手', meaning: '相持的另一方', x: 0.8, y: 0.5 },
		],
	},
	yesno3: {
		key: 'yesno3', label: '是非题(3张)', meaning: '三张判是非:全正=是,全逆=否,二比一=倾向;正位牌兼示可用资源,逆位牌兼示待解之结。',
		positions: [
			{ i: 1, key: 'yn1', label: '其一', meaning: '正=可用长处;逆=需解之碍', x: 0.25, y: 0.5 },
			{ i: 2, key: 'yn2', label: '其二(权重加倍)', meaning: '中位之牌,判是非时计两分', x: 0.5, y: 0.5 },
			{ i: 3, key: 'yn3', label: '其三', meaning: '正=可用长处;逆=需解之碍', x: 0.75, y: 0.5 },
		],
	},
	firstmeet3: {
		key: 'firstmeet3', label: '一见倾心(3张)', meaning: '初识心仪对象专用:两造第一印象与发展可能。',
		positions: [
			{ i: 1, key: 'my_view', label: '我对其印象', meaning: '我眼中的对方', x: 0.25, y: 0.5 },
			{ i: 2, key: 'their_view', label: '其对我印象', meaning: '对方眼中的我', x: 0.75, y: 0.5 },
			{ i: 3, key: 'potential', label: '发展可能', meaning: '这段缘分的走向', x: 0.5, y: 0.85 },
		],
	},
	// —— 四/五/六/七张协议族 ——
	doubt4: {
		key: 'doubt4', label: '疑惑之解(4张)', meaning: '本人在下,疑惑两面斜置其上,顶张为化解之钥。',
		positions: [
			{ i: 1, key: 'self', label: '本人', meaning: '身处疑惑中的我', x: 0.5, y: 0.85 },
			{ i: 2, key: 'doubt_a', label: '疑惑一面', meaning: '犹疑的一端', x: 0.32, y: 0.5 },
			{ i: 3, key: 'doubt_b', label: '疑惑另一面', meaning: '犹疑的另一端', x: 0.68, y: 0.5 },
			{ i: 4, key: 'key', label: '化解之钥', meaning: '解开两难的枢机', x: 0.5, y: 0.15 },
		],
	},
	liberation5: {
		key: 'liberation5', label: '解缚五张(十字)', meaning: '「什么阻止我做自己」:束缚居下,手段/当行/蜕变横列,顶为目的。',
		positions: [
			{ i: 1, key: 'bond', label: '束缚', meaning: '阻止我做自己的是什么', x: 0.5, y: 0.85 },
			{ i: 2, key: 'means', label: '解放手段', meaning: '可借之力', x: 0.2, y: 0.5 },
			{ i: 3, key: 'act', label: '当行之动', meaning: '此刻该做的一步', x: 0.5, y: 0.5 },
			{ i: 4, key: 'becoming', label: '导向的蜕变', meaning: '解缚后走向什么', x: 0.8, y: 0.5 },
			{ i: 5, key: 'aim', label: '目的/命数', meaning: '这段功课的归趣', x: 0.5, y: 0.15 },
		],
	},
	hero5: {
		key: 'hero5', label: '英雄之旅(5张)', meaning: '处境与目标分踞两端,中间双障,上方为钥匙/盟友;障碍前后各读一遍。',
		positions: [
			{ i: 1, key: 'state', label: '处境', meaning: '出发点', x: 0.08, y: 0.62 },
			{ i: 2, key: 'goal', label: '目标', meaning: '要抵达之地', x: 0.92, y: 0.62 },
			{ i: 3, key: 'obstacle_a', label: '障碍一', meaning: '路上的第一重关', x: 0.37, y: 0.62 },
			{ i: 4, key: 'obstacle_b', label: '障碍二', meaning: '路上的第二重关', x: 0.63, y: 0.62 },
			{ i: 5, key: 'ally', label: '钥匙/盟友', meaning: '越关之助', x: 0.5, y: 0.2 },
		],
	},
	world5: {
		key: 'world5', label: '四中心之界(5张)', meaning: '仿「世界」构图:中为本质,四角为智力(鹰)/情感(天使)/性与创造(狮)/物质(牛)四中心。',
		positions: [
			{ i: 1, key: 'essence', label: '本质/高我', meaning: '居中的核心', x: 0.5, y: 0.5 },
			{ i: 2, key: 'mind', label: '智力(鹰)', meaning: '头脑之域', x: 0.78, y: 0.18 },
			{ i: 3, key: 'heart', label: '情感(天使)', meaning: '心之域', x: 0.22, y: 0.18 },
			{ i: 4, key: 'desire', label: '性/创造(狮)', meaning: '欲望与创造之域', x: 0.78, y: 0.82 },
			{ i: 5, key: 'body', label: '物质(牛)', meaning: '身体与生计之域', x: 0.22, y: 0.82 },
		],
	},
	spirit5_d: {
		key: 'spirit5_d', label: '精神方向(5张)', meaning: '身体-方向-课题-替代之路-过去影响,一排读尽当下修行坐标。',
		positions: [
			{ i: 1, key: 'health', label: '健康(身)', meaning: '身体的当下', x: 0.1, y: 0.5 },
			{ i: 2, key: 'direction', label: '当前精神方向', meaning: '此刻心之所向', x: 0.3, y: 0.5 },
			{ i: 3, key: 'lesson', label: '立即课题', meaning: '眼下可学之事', x: 0.5, y: 0.5 },
			{ i: 4, key: 'alt', label: '替代之路', meaning: '若于现路不安,可取之道', x: 0.7, y: 0.5 },
			{ i: 5, key: 'past', label: '过去影响', meaning: '仍在作用的旧事', x: 0.9, y: 0.5 },
		],
	},
	lesson5: {
		key: 'lesson5', label: '课题五张', meaning: '课题-障碍-机会-资源-更大课题,层层剥开一门功课。',
		positions: [
			{ i: 1, key: 'lesson', label: '立即课题', meaning: '当前功课', x: 0.1, y: 0.5 },
			{ i: 2, key: 'block', label: '学习障碍', meaning: '卡在哪里', x: 0.3, y: 0.5 },
			{ i: 3, key: 'chance', label: '衍生机会', meaning: '功课带来的机会', x: 0.5, y: 0.5 },
			{ i: 4, key: 'support', label: '支持资源', meaning: '可倚之助(情感或资财)', x: 0.7, y: 0.5 },
			{ i: 5, key: 'bigger', label: '更大课题', meaning: '此课所属的更大主题', x: 0.9, y: 0.5 },
		],
	},
	statement5: {
		key: 'statement5', label: '陈述之局(5张·双结局)', meaning: '有利/对抗横列,上为失控之势,下为可控之择;中位为不行使抉择时的默认走向。',
		positions: [
			{ i: 1, key: 'favor', label: '有利因素', meaning: '站在我这边的力量', x: 0.2, y: 0.5 },
			{ i: 2, key: 'against', label: '对抗因素', meaning: '与我相持的力量', x: 0.8, y: 0.5 },
			{ i: 3, key: 'uncontrolled', label: '失控之势及其后果', meaning: '非我能控的走向', x: 0.5, y: 0.15 },
			{ i: 4, key: 'controlled', label: '可控之择(行使之果)', meaning: '若行使自由抉择,结果如何', x: 0.5, y: 0.85 },
			{ i: 5, key: 'default', label: '默认走向', meaning: '不作为时事情自行滑向何处', x: 0.5, y: 0.5 },
		],
	},
	choice5_e: {
		key: 'choice5_e', label: '二择一(5张)', meaning: '顶为本人心态,左右两路各示过程与结果;A/B 所指须在占前定死,不可事后指认。',
		positions: [
			{ i: 1, key: 'mind', label: '本人心态', meaning: '面对抉择的底层心态', x: 0.5, y: 0.12 },
			{ i: 2, key: 'a_course', label: '选A·过程', meaning: '走 A 路的经过', x: 0.3, y: 0.45 },
			{ i: 3, key: 'b_course', label: '选B·过程', meaning: '走 B 路的经过', x: 0.7, y: 0.45 },
			{ i: 4, key: 'a_result', label: '选A·结果', meaning: 'A 路的落点', x: 0.22, y: 0.8 },
			{ i: 5, key: 'b_result', label: '选B·结果', meaning: 'B 路的落点', x: 0.78, y: 0.8 },
		],
	},
	love4: {
		key: 'love4', label: '感情四张', meaning: '双方心态与现况未来;先看两心落差,再论走向可否经营。',
		positions: [
			{ i: 1, key: 'me', label: '我的心态', meaning: '我在此段关系中的心', x: 0.25, y: 0.5 },
			{ i: 2, key: 'them', label: '对方心态', meaning: '对方在此段关系中的心', x: 0.75, y: 0.5 },
			{ i: 3, key: 'now', label: '目前状况', meaning: '关系现况', x: 0.5, y: 0.18 },
			{ i: 4, key: 'future', label: '未来发展', meaning: '照此下去的走向(可经营而变)', x: 0.5, y: 0.82 },
		],
	},
	aspects4: {
		key: 'aspects4', label: '四面向(4张)', meaning: '身-情-心-灵四层剖面,专答「何以至此」。',
		positions: [
			{ i: 1, key: 'body', label: '身体', meaning: '身体层的状态', x: 0.14, y: 0.5 },
			{ i: 2, key: 'feeling', label: '情感', meaning: '情感层的状态', x: 0.38, y: 0.5 },
			{ i: 3, key: 'mind', label: '心智', meaning: '心智层(含促成现状的心念)', x: 0.62, y: 0.5 },
			{ i: 4, key: 'spirit', label: '精神(课题)', meaning: '精神层与其功课', x: 0.86, y: 0.5 },
		],
	},
	elements4: {
		key: 'elements4', label: '四元素诊断(4张)', meaning: '火/水/风/土四位各落一张:落牌元素与位元素相生则该层通畅,相制则该层受阻(逆位加一层待疏)。',
		positions: [
			{ i: 1, key: 'fire_slot', label: '火位(行动)', meaning: '行动与意志之层', x: 0.14, y: 0.5, slotElement: 'fire' },
			{ i: 2, key: 'water_slot', label: '水位(情感)', meaning: '情感与关系之层', x: 0.38, y: 0.5, slotElement: 'water' },
			{ i: 3, key: 'air_slot', label: '风位(思虑)', meaning: '思虑与沟通之层', x: 0.62, y: 0.5, slotElement: 'air' },
			{ i: 4, key: 'earth_slot', label: '土位(现实)', meaning: '身体与生计之层', x: 0.86, y: 0.5, slotElement: 'earth' },
		],
	},
	relation6_e: {
		key: 'relation6_e', label: '人际六张', meaning: '中排时间线(过去-现在-未来),上下为两造心态,斜出为环境;刚识者可略过去位。',
		positions: [
			{ i: 1, key: 'my_mind', label: '我的心态', meaning: '我对此关系的心', x: 0.5, y: 0.85 },
			{ i: 2, key: 'their_mind', label: '对方的心态', meaning: '对方对此关系的心', x: 0.5, y: 0.15 },
			{ i: 3, key: 'past', label: '过去', meaning: '关系的来路', x: 0.26, y: 0.5 },
			{ i: 4, key: 'present', label: '现在', meaning: '关系的当下', x: 0.5, y: 0.5 },
			{ i: 5, key: 'future', label: '未来发展', meaning: '照此走的去向', x: 0.74, y: 0.5 },
			{ i: 6, key: 'env', label: '环境', meaning: '外缘与旁人之力', x: 0.88, y: 0.28 },
		],
	},
	core4: {
		key: 'core4', label: '直指核心(4张)', meaning: '锥形直入:顶为问题核心,下扇三张为短处/对策/长处;长处位逆=长处未被启用,短处位逆=未自觉或已克。',
		positions: [
			{ i: 1, key: 'core', label: '问题核心', meaning: '此事的本质', x: 0.5, y: 0.15 },
			{ i: 2, key: 'weakness', label: '障碍/短处', meaning: '逆位=尚未自觉或已在克服', x: 0.25, y: 0.68 },
			{ i: 3, key: 'action', label: '对策', meaning: '具体的解决之道', x: 0.5, y: 0.78 },
			{ i: 4, key: 'strength', label: '资源/长处', meaning: '逆位=长处尚未被发现或善用', x: 0.75, y: 0.68 },
		],
	},
	plans6: {
		key: 'plans6', label: '两个蓝图(6张)', meaning: '上排为心之蓝图(自选之愿),下排为承袭之图(外界期望);两图相照,见何者在真正驱动我。',
		positions: [
			{ i: 1, key: 'utopia_1', label: '心图·一', meaning: '自选蓝图的起点', x: 0.25, y: 0.3 },
			{ i: 2, key: 'utopia_2', label: '心图·二', meaning: '自选蓝图的展开', x: 0.5, y: 0.3 },
			{ i: 3, key: 'utopia_3', label: '心图·三', meaning: '自选蓝图的归宿', x: 0.75, y: 0.3 },
			{ i: 4, key: 'legacy_1', label: '承袭·一', meaning: '被期望之图的起点', x: 0.25, y: 0.7 },
			{ i: 5, key: 'legacy_2', label: '承袭·二', meaning: '被期望之图的展开', x: 0.5, y: 0.7 },
			{ i: 6, key: 'legacy_3', label: '承袭·三', meaning: '被期望之图的归宿', x: 0.75, y: 0.7 },
		],
	},
	choice7_tdm: {
		key: 'choice7_tdm', label: '抉择两路(7张)', meaning: '顶为问者本人,左右两路各三张(起点-发展-结果);本人牌面朝向亦可参偏好。',
		positions: [
			{ i: 1, key: 'self', label: '问者', meaning: '面临抉择的我', x: 0.5, y: 0.12 },
			{ i: 2, key: 'a_start', label: '甲路·起点', meaning: '可能一的入口', x: 0.32, y: 0.42 },
			{ i: 3, key: 'b_start', label: '乙路·起点', meaning: '可能二的入口', x: 0.68, y: 0.42 },
			{ i: 4, key: 'a_mid', label: '甲路·发展', meaning: '可能一的中途', x: 0.24, y: 0.66 },
			{ i: 5, key: 'a_end', label: '甲路·结果', meaning: '可能一的落点', x: 0.16, y: 0.9 },
			{ i: 6, key: 'b_mid', label: '乙路·发展', meaning: '可能二的中途', x: 0.76, y: 0.66 },
			{ i: 7, key: 'b_end', label: '乙路·结果', meaning: '可能二的落点', x: 0.84, y: 0.9 },
		],
	},
	seven_v: {
		key: 'seven_v', label: '七张V形', meaning: '大V摆位:过去(约一年半内)-现在(前后月余)-近期(约一季)-核心(本人或答案)-环绕能量-希望与恐惧-结果(两年内)。',
		positions: [
			{ i: 1, key: 'past', label: '过去(≤18月)', meaning: '一年半内的来路', x: 0.08, y: 0.25 },
			{ i: 2, key: 'present', label: '现在(±4周)', meaning: '前后月余的当下', x: 0.22, y: 0.5 },
			{ i: 3, key: 'near', label: '近期(≈3月)', meaning: '约一季内的走向', x: 0.36, y: 0.75 },
			{ i: 4, key: 'core', label: '核心(本人/答案)', meaning: '通占=本人;问事=问题的答案', anchor: true, x: 0.5, y: 0.9 },
			{ i: 5, key: 'around', label: '环绕能量', meaning: '旁人态度与周遭气场', x: 0.64, y: 0.75 },
			{ i: 6, key: 'hopes', label: '希望与恐惧', meaning: '心中期待与忧惧(一体两面)', x: 0.78, y: 0.5 },
			{ i: 7, key: 'outcome', label: '结果(≤24月)', meaning: '两年内的落点', x: 0.92, y: 0.25 },
		],
	},
	hanged6: {
		key: 'hanged6', label: '悬吊之局(6张·内外双读)', meaning: '仿「倒吊人」构图逐位叠放;每位皆读两遍:先外在处境,再内在修行。',
		positions: [
			{ i: 1, key: 'tree', label: '所悬之树', meaning: '外:我在外界倚赖什么；内:我在内心倚赖什么', x: 0.5, y: 0.08 },
			{ i: 2, key: 'rope', label: '缚足之绳', meaning: '外:何事困住我；内:困局里积出什么体悟', x: 0.5, y: 0.3 },
			{ i: 3, key: 'right_leg', label: '意识(直腿)', meaning: '外:显意识如何看待；内:我正穿过哪扇门', x: 0.66, y: 0.55 },
			{ i: 4, key: 'left_leg', label: '无意识(曲腿)', meaning: '外:哪些暗流与意愿相抵；内:冲突如何化为成长', x: 0.34, y: 0.55 },
			{ i: 5, key: 'hands', label: '背手', meaning: '外:我正放下/牺牲什么；内:须完成什么内修', x: 0.5, y: 0.78 },
			{ i: 6, key: 'halo', label: '发光之首', meaning: '外:处境如何磨我谦卑；内:什么新见地正照亮暗处', x: 0.5, y: 0.95 },
		],
	},
	anjila8: {
		key: 'anjila8', label: '双人对读(8张)', meaning: '两人各四张(付出/角色/得到/真正想要);对读法:甲之付出对乙之得到互照,末看两人所得与所欲之差。纯检视,不作预测。',
		pairRule: '甲1↔乙3、乙1↔甲3、甲2↔乙2、(甲3,乙3)对(甲4,乙4)',
		positions: [
			{ i: 1, key: 'a1', label: '甲·付出', meaning: '甲在关系中付出了什么', x: 0.3, y: 0.14 },
			{ i: 2, key: 'a2', label: '甲·角色', meaning: '甲扮演了什么角色', x: 0.3, y: 0.38 },
			{ i: 3, key: 'a3', label: '甲·得到', meaning: '甲从关系中得到什么', x: 0.3, y: 0.62 },
			{ i: 4, key: 'a4', label: '甲·真欲', meaning: '甲真正想要什么', x: 0.3, y: 0.86 },
			{ i: 5, key: 'b1', label: '乙·付出', meaning: '乙在关系中付出了什么', x: 0.7, y: 0.14 },
			{ i: 6, key: 'b2', label: '乙·角色', meaning: '乙扮演了什么角色', x: 0.7, y: 0.38 },
			{ i: 7, key: 'b3', label: '乙·得到', meaning: '乙从关系中得到什么', x: 0.7, y: 0.62 },
			{ i: 8, key: 'b4', label: '乙·真欲', meaning: '乙真正想要什么', x: 0.7, y: 0.86 },
		],
	},
	life_inventory7: {
		key: 'life_inventory7', label: '生活盘点(7张)', meaning: '七域巡检:亲缘-滋养-玩乐-使命-意象-运动-职责;逆位=该域能量匮乏、抗拒或正在改换。',
		positions: [
			{ i: 1, key: 'support', label: '亲缘支持', meaning: '关系与后盾', x: 0.08, y: 0.5 },
			{ i: 2, key: 'nourish', label: '滋养', meaning: '正在吸收消化什么', x: 0.22, y: 0.5 },
			{ i: 3, key: 'play', label: '玩乐', meaning: '何事带来喜悦与天真', x: 0.36, y: 0.5 },
			{ i: 4, key: 'purpose', label: '生命目的', meaning: '灵性的方向', x: 0.5, y: 0.5 },
			{ i: 5, key: 'imagery', label: '意象', meaning: '静观/直觉/梦境', x: 0.64, y: 0.5 },
			{ i: 6, key: 'movement', label: '运动', meaning: '身体的舒张', x: 0.78, y: 0.5 },
			{ i: 7, key: 'work', label: '工作职责', meaning: '义务与承担', x: 0.92, y: 0.5 },
		],
	},
	realization10: {
		key: 'realization10', label: '自我圆成(10张)', meaning: '「若一切顺遂,我的圆满是什么」:底为主角与内在对手,中为调停,两翼为顺缘与试炼,上为中道,顶为最深之秘。',
		positions: [
			{ i: 1, key: 'self', label: '主角(自我观)', meaning: '我如何看待自己', x: 0.3, y: 0.9 },
			{ i: 2, key: 'inner_foe', label: '内在对手', meaning: '与我相抗的内在一面', x: 0.7, y: 0.9 },
			{ i: 3, key: 'mediate', label: '调停之果', meaning: '两者相调后的现况', x: 0.5, y: 0.72 },
			{ i: 4, key: 'comet_1', label: '顺缘·一', meaning: '迎面而来的助缘', x: 0.72, y: 0.52 },
			{ i: 5, key: 'comet_2', label: '顺缘·二', meaning: '进一步的际遇', x: 0.88, y: 0.38 },
			{ i: 6, key: 'trial_1', label: '试炼·一', meaning: '途中的负面际遇/诱惑', x: 0.28, y: 0.52 },
			{ i: 7, key: 'trial_2', label: '试炼·二', meaning: '更深的考验', x: 0.12, y: 0.38 },
			{ i: 8, key: 'middle_1', label: '中道·一', meaning: '兼摄两翼的行路', x: 0.38, y: 0.24 },
			{ i: 9, key: 'middle_2', label: '中道·二', meaning: '中道的深化', x: 0.62, y: 0.24 },
			{ i: 10, key: 'secret', label: '至深之秘', meaning: '此问最底层的东西', x: 0.5, y: 0.08 },
		],
	},
	causal7: {
		key: 'causal7', label: '因果七杯(仅大牌·7张)', meaning: '只用廿二大牌;以「圣杯七」居中为图钥,七杯各摄一域:角色-家感-物力-己力-无意识-性与创造-精神我。诊断优缺,非预言。',
		subset: 'majors', fixedCenter: 'cups_07',
		positions: [
			{ i: 1, key: 'face', label: '有脸之杯(角色)', meaning: '我面对世界的角色', x: 0.5, y: 0.1 },
			{ i: 2, key: 'castle', label: '城堡杯(家感)', meaning: '家的感受(童年所形塑)', x: 0.82, y: 0.28 },
			{ i: 3, key: 'jewel', label: '珠宝杯(物力)', meaning: '物质力量与吸引资财之能', x: 0.88, y: 0.64 },
			{ i: 4, key: 'wreath', label: '花圈杯(己力)', meaning: '个人力量:取舍与应战方式', x: 0.62, y: 0.9 },
			{ i: 5, key: 'demon', label: '幽影杯(无意识)', meaning: '无意识:梦与直觉的通道', x: 0.38, y: 0.9 },
			{ i: 6, key: 'snake', label: '蛇杯(性与创造)', meaning: '性与创造能量的通塞', x: 0.12, y: 0.64 },
			{ i: 7, key: 'shroud', label: '覆纱杯(精神我)', meaning: '精神层次的自我与方向', x: 0.18, y: 0.28 },
		],
	},
	problem_solving9: {
		key: 'problem_solving9', label: '解题九步(9张)', meaning: '界定(症状/根因)→描述(应该/谁说/依据)→出路(两解+最狂想)→愿望之果;末步不占牌:四十八小时内做一件小事。',
		layout: 'matrix',
		matrix: { cols: 3, rowLabels: ['界定', '描述', '出路', '愿望'] },
		positions: [
			{ i: 1, key: 'symptom', label: '症状', meaning: '可见的影响', row: 0, col: 0 },
			{ i: 2, key: 'root', label: '根因', meaning: '潜在的需求/动机/原因', row: 0, col: 1 },
			{ i: 3, key: 'should', label: '「应该」', meaning: '看起来必须做的', row: 1, col: 0 },
			{ i: 4, key: 'who_says', label: '谁在说', meaning: '这声音来自谁', row: 1, col: 1 },
			{ i: 5, key: 'belief', label: '依据', meaning: '「应该」背后的信念', row: 1, col: 2 },
			{ i: 6, key: 'alt_1', label: '另解·一', meaning: '别的解决办法', row: 2, col: 0 },
			{ i: 7, key: 'alt_2', label: '另解·二', meaning: '再一个办法', row: 2, col: 1 },
			{ i: 8, key: 'wild', label: '最狂想之解', meaning: '最疯狂的办法(常藏真解)', row: 2, col: 2 },
			{ i: 9, key: 'wish', label: '愿望之果', meaning: '希望解决后带来什么', row: 3, col: 1 },
		],
	},
	world15: {
		key: 'world15', label: '四中心之界·放大(15张)', meaning: '五位各成三张一句(本质居中,四角四中心);花色错位即诊断(如钱币落智力位=钱在心头)。',
		layout: 'matrix',
		matrix: { cols: 3, rowLabels: ['本质·高我', '智力(鹰)', '情感(天使)', '性/创造(狮)', '物质(牛)'] },
		positions: Array.from({ length: 15 }, (_, idx) => {
			const rows = ['essence', 'mind', 'heart', 'desire', 'body'];
			const rowCn = ['本质', '智力', '情感', '性/创造', '物质'];
			const r = Math.floor(idx / 3);
			const c = idx % 3;
			return { i: idx + 1, key: `w15_${rows[r]}_${c + 1}`, label: `${rowCn[r]}·${c + 1}`, meaning: `${rowCn[r]}域三张成句之第${c + 1}字`, row: r, col: c };
		}),
	},
	hero22: {
		key: 'hero22', label: '英雄×四中心(22张)', meaning: '首尾两张框住全局(本质存在/本质目标);四行=智力/情感/性创造/物质,每行五张:现状-内障-外障-钥匙-该域目标。',
		layout: 'matrix',
		matrix: { cols: 5, rowLabels: ['本质(首尾)', '智力(头)', '情感(心)', '性/创造(盆)', '物质(足)'], colLabels: ['现状', '内在障碍', '外在障碍', '钥匙/盟友', '目标'] },
		positions: (() => {
			const out = [
				{ i: 1, key: 'h22_being', label: '本质存在', meaning: '「我本质上是」——框住全局的左柱', row: 0, col: 0 },
				{ i: 2, key: 'h22_goal', label: '本质目标', meaning: '「我本质上要去向」——框住全局的右柱', row: 0, col: 4 },
			];
			const centers = [['mind', '智力'], ['heart', '情感'], ['desire', '性/创造'], ['body', '物质']];
			const cols = ['现状', '内在障碍', '外在障碍', '钥匙/盟友', '目标'];
			centers.forEach(([k, cn], r) => {
				cols.forEach((cLabel, c) => {
					out.push({ i: out.length + 1, key: `h22_${k}_${c + 1}`, label: `${cn}·${cLabel}`, meaning: `${cn}域的${cLabel}`, row: r + 1, col: c });
				});
			});
			return out;
		})(),
	},
	choice22: {
		key: 'choice22', label: '抉择×四中心(22张)', meaning: '首尾两张(我本质上是/我本质上想要);四行四中心,每行:接纳型可能两张-现状居中-主动型可能两张。',
		layout: 'matrix',
		matrix: { cols: 5, rowLabels: ['本质(首尾)', '智力', '情感', '性/创造', '物质'], colLabels: ['承受·一', '承受·二', '现状', '主动·一', '主动·二'] },
		positions: (() => {
			const out = [
				{ i: 1, key: 'c22_am', label: '我本质上是', meaning: '左柱:本然之我', row: 0, col: 0 },
				{ i: 2, key: 'c22_want', label: '我本质上想要', meaning: '右柱:本然之欲', row: 0, col: 4 },
			];
			const centers = [['mind', '智力'], ['heart', '情感'], ['desire', '性/创造'], ['body', '物质']];
			const cols = ['承受型可能·一', '承受型可能·二', '现状', '主动型可能·一', '主动型可能·二'];
			centers.forEach(([k, cn], r) => {
				cols.forEach((cLabel, c) => {
					out.push({ i: out.length + 1, key: `c22_${k}_${c + 1}`, label: `${cn}·${cLabel}`, meaning: `${cn}域的${cLabel}`, row: r + 1, col: c });
				});
			});
			return out;
		})(),
	},
	latent26: {
		key: 'latent26', label: '潜流全景(26张)', meaning: '五行功能层(意念火/感受水/态度风/结果土/潜在动机)×五列时间轴(远过去→远未来)+底行深因一张;对角线自左下深因走向右上灵感。',
		layout: 'matrix',
		matrix: { cols: 5, rowLabels: ['意念/灵感(火)', '感受/幻想(水)', '头脑/态度(风)', '物质/结果(土)', '潜在动机', '更深之因'], colLabels: ['遥远过去', '最近过去', '现在', '将临未来', '更远未来'] },
		positions: (() => {
			const out = [];
			const rows = ['fire', 'water', 'air', 'earth', 'motive'];
			const rowCn = ['意念', '感受', '态度', '结果', '潜在动机'];
			const colCn = ['遥远过去', '最近过去', '现在', '将临未来', '更远未来'];
			rows.forEach((rk, r) => {
				for(let c = 0; c < 5; c++){
					out.push({ i: out.length + 1, key: `lt_${rk}_${c + 1}`, label: `${rowCn[r]}·${colCn[c]}`, meaning: `${rowCn[r]}层于${colCn[c]}`, row: r, col: c });
				}
			});
			out.push({ i: 26, key: 'lt_deep', label: '更深之因', meaning: '藏得最深、权重最大的一张', row: 5, col: 2 });
			return out;
		})(),
	},
	week7: {
		key: 'week7', label: '周历(7张)', meaning: '未来七日逐日一张,依序为第一至第七日。',
		positions: Array.from({ length: 7 }, (_, i) => ({ i: i + 1, key: `wk_${i + 1}`, label: `第${i + 1}日`, meaning: '该日主题/事件/建议', x: (i + 0.5) / 7, y: 0.5 })),
	},
	calendar31: {
		key: 'calendar31', label: '月历(31张)', meaning: '未来一月逐日一张(按月取用 28-31 天,多余弃读);哪一日之牌最有望,即以为期。',
		layout: 'matrix',
		matrix: { cols: 7, rowLabels: ['一', '二', '三', '四', '五'] },
		positions: Array.from({ length: 31 }, (_, i) => ({ i: i + 1, key: `day_${i + 1}`, label: `${i + 1}日`, meaning: '该日主题', row: Math.floor(i / 7), col: i % 7 })),
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

// 通用塔罗牌阵清单(不含雷诺曼专属阵与 opening_of_key;全为位置制,≤22 张 → 22 大牌牌组亦可行)。
// 单一真值:78 张核心牌组、22 大牌牌组(Wirth/Egyptian)、BOTA 均取此清单,避免各处漂移。
export const TAROT_SPREADS = [
	'single', 'three', 'three_sit', 'three_mbs', 'three_pcs', 'three_choice', 'morning3', 'review3',
	'horseshoe', 'horseshoe5', 'celtic', 'celtic6', 'celtic11', 'croix', 'relation', 'relation7',
	'tree_of_life', 'zodiac', 'zodiac13', 'annual', 'year_wheel13',
	'decision6', 'career7', 'money5', 'chakra7', 'seven_planets7', 'pyramid10', 'shadow5', 'moon8', 'spiritual5',
	// TP5 扩容(≤22 张位置制)
	'conflict2', 'family3', 'forces3', 'sentence3', 'yes_but3', 'protagonist3', 'yesno3', 'firstmeet3',
	'doubt4', 'liberation5', 'hero5', 'world5', 'spirit5_d', 'lesson5', 'statement5', 'choice5_e', 'love4',
	'aspects4', 'elements4', 'relation6_e', 'core4', 'plans6', 'choice7_tdm', 'seven_v', 'hanged6', 'anjila8',
	'life_inventory7', 'realization10', 'problem_solving9', 'week7', 'world15', 'hero22', 'choice22',
];
// TP5:仅 78 张家族(rws/tdm/thoth/golden_dawn/bota/etteilla)追加的三阵:大牌子集因果七杯 / 26 张潜流全景 / 31 张月历。
export const TAROT_SPREADS_78_EXTRA = ['causal7', 'latent26', 'calendar31'];
export const DEFAULT_SPREAD = 'three';

// TP5 牌阵分组(左栏下拉 OptGroup 用;组内顺序即显示顺序;渲染端按 caps.spreads 过滤后仍走本表分组)。
export const SPREAD_GROUPS = [
	{ group: '基础与三张', items: ['single', 'three', 'three_sit', 'three_mbs', 'three_pcs', 'sentence3', 'yes_but3', 'yesno3', 'morning3', 'review3', 'firstmeet3', 'conflict2'] },
	{ group: '时间与历法', items: ['seven_v', 'annual', 'year_wheel13', 'week7', 'calendar31', 'moon8'] },
	{ group: '关系', items: ['relation', 'relation7', 'relation6_e', 'love4', 'anjila8', 'family3', 'protagonist3'] },
	{ group: '抉择', items: ['three_choice', 'decision6', 'choice5_e', 'choice7_tdm', 'plans6', 'statement5', 'choice22'] },
	{ group: '事业与生活', items: ['career7', 'money5', 'life_inventory7', 'problem_solving9', 'core4', 'horseshoe', 'horseshoe5'] },
	{ group: '内在与灵性', items: ['shadow5', 'spiritual5', 'chakra7', 'hanged6', 'liberation5', 'doubt4', 'hero5', 'forces3', 'aspects4', 'elements4', 'causal7', 'realization10', 'spirit5_d', 'lesson5', 'first_reversal'] },
	{ group: '结构大阵', items: ['celtic', 'celtic6', 'celtic11', 'croix', 'tree_of_life', 'zodiac', 'zodiac13', 'seven_planets7', 'pyramid10', 'world5', 'world15', 'hero22', 'latent26', 'opening_of_key'] },
	{ group: '雷诺曼', items: ['lenormand_3', 'lenormand_box9', 'grand_tableau'] },
];

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
