// divination/data/naturalSignificators.js
// 七曜自然象征星完整对照（卜卦 05§4.3(a)）。供右栏「征象」Tab 的自然象征卡、
// 同主一星裁决(E 法)与专题模块(B1–B12)取自然象征使用。
// 与 planets.js 的 natural_sig 简表并存：本表为卜卦判读的完整口径（单一真值源），
// planets.natural_sig 为通用简表（其他技法沿用，勿删）。
// ⚠️ 父亲双归：太阳(昼盘)/土星(夜盘)——取用时须按盘 sect 分流。

export const NATURAL_SIGNIFICATORS = {
	sun: {
		cn: '太阳', glyph: '☉',
		persons: ['成熟男性', '王室/君主', '权威人物', '雇主', '父亲(昼盘)', '银行家'],
		things: ['黄金', '荣誉', '权力', '生命力'],
		note: '问者活力副象征；关系题可代男方男性特质；父亲象征限昼盘。',
	},
	moon: {
		cn: '月亮', glyph: '☽',
		persons: ['女性总称', '母亲', '王后', '护士', '漂泊者/逃亡者', '大众', '儿童'],
		things: ['变化与情绪', '海洋/水', '日常必需品'],
		note: '永远的问者副象征星，兼「事态流转」总象征。',
	},
	mercury: {
		cn: '水星', glyph: '☿',
		persons: ['商人', '信使', '教师/文员', '骗子'],
		things: ['书籍/文书/合同', '信息与消息', '车辆', '短途往来'],
		note: '消息真假题(B3)的自然象征。',
	},
	venus: {
		cn: '金星', glyph: '♀',
		persons: ['伴侣', '年轻女性'],
		things: ['珠宝', '金钱', '美物', '礼物', '艺术', '爱情/婚姻'],
		note: '婚恋题的自然象征。',
	},
	mars: {
		cn: '火星', glyph: '♂',
		persons: ['青壮年男性', '军人', '外科医生'],
		things: ['火', '战争/冲突', '兵器', '手术', '危险'],
		note: '',
	},
	jupiter: {
		cn: '木星', glyph: '♃',
		persons: ['成熟男性', '律师与法官', '神职人员', '外国人'],
		things: ['高等教育', '远行', '财富', '宗教与法律'],
		note: '诉讼题(B7-2)法官/法律侧自然象征。',
	},
	saturn: {
		cn: '土星', glyph: '♄',
		persons: ['老人', '父亲(夜盘)', '农人'],
		things: ['时间', '约束/延迟', '贫困损失', '土地', '死亡(普遍象征)'],
		note: '父亲象征限夜盘。',
	},
};

// 父亲自然象征按 sect 分流（05§4.3：the Sun by day and Saturn by night）。
export function fatherSignificator(isDiurnal){
	return isDiurnal ? 'sun' : 'saturn';
}

export default NATURAL_SIGNIFICATORS;
