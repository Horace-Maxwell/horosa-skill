// divination/data/planets.js
// 行星属性（古典七政 + 南北交点 + 三王星 + 福点）。
// 来源：卜卦构建清单 §1.1（Sibly 共同征象星/颜色/自然征象）+ 择日清单 §2.1（吉凶/sect/关键字/行业/身体）。
// nature: benefic|malefic|neutral|conditional ; sect: diurnal|nocturnal|none
// 注：火星本性属夜间宗派(nocturnal)，但「昼间最凶」=出宗派时为害最烈；土星属昼间宗派，夜间最凶，同理。

export const PLANETS = {
	sun: {
		id: 'sun', cn: '太阳', en: 'Sun', glyph: '☉',
		nature: 'neutral', // 中性偏吉
		sect: 'diurnal', isLight: true,
		gender: 'masculine', qualities: ['hot', 'dry'],
		color: '橄榄/栗色',
		natural_sig: ['父', '君主', '权威', '名望'],
		keywords: ['精力', '权力', '名望', '贵气', '自信', '独断', '虚荣'],
		industries: ['名誉', '贵气', '权威', '政治活动'],
		body_parts: ['心脏', '脊椎', '背'],
	},
	moon: {
		id: 'moon', cn: '月亮', en: 'Moon', glyph: '☽',
		nature: 'neutral', // 盈吉/亏弱
		sect: 'nocturnal', isLight: true,
		gender: 'feminine', qualities: ['cold', 'moist'],
		color: '白色或染所合星颜色',
		natural_sig: ['母', '女主', '公众', '妻'],
		keywords: ['情绪', '变动', '生产', '母性', '公众面孔', '储藏'],
		industries: ['餐饮', '食品', '水相关', '日用品', '不动产', '公众事务'],
		body_parts: ['胃', '胸', '子宫', '卵巢'],
	},
	mercury: {
		id: 'mercury', cn: '水星', en: 'Mercury', glyph: '☿',
		nature: 'neutral', // 随相邻星
		sect: 'common', // 随东出(昼)/西入(夜)
		gender: 'common', qualities: ['common'],
		color: '浅铅白色',
		natural_sig: ['年轻家人', '朋友', '作家', '商人', '密友'],
		keywords: ['思考', '沟通', '口才', '机灵', '多才', '好奇'],
		industries: ['教育', '知识', '写作', '传播', '计算', '交通', '旅行', '推销'],
		body_parts: ['手臂', '肺', '神经系统'],
	},
	venus: {
		id: 'venus', cn: '金星', en: 'Venus', glyph: '♀',
		nature: 'benefic', // 第二吉星
		sect: 'nocturnal',
		gender: 'feminine', qualities: ['cold', 'moist'],
		color: '黄色',
		natural_sig: ['妻', '女', '情人'],
		keywords: ['金钱', '艺术', '美感', '爱情', '享乐', '合伙', '时尚'],
		industries: ['金融', '珠宝', '艺术', '美容', '服饰', '休闲娱乐', '仲裁'],
		body_parts: ['喉', '肾', '腰'],
	},
	mars: {
		id: 'mars', cn: '火星', en: 'Mars', glyph: '♂',
		nature: 'malefic',
		sect: 'nocturnal', // 昼间最凶(出宗派)
		gender: 'masculine', qualities: ['hot', 'dry'],
		color: '火象座为疤痕红/他座红痣',
		natural_sig: ['兄弟', '子', '战士', '军官'],
		keywords: ['冒险', '爆发', '斗争', '暴力', '性急', '开拓', '活力'],
		industries: ['火/金属/切割相关', '军事', '外科', '激烈运动'],
		body_parts: ['头', '肌肉', '生殖排泄'],
	},
	jupiter: {
		id: 'jupiter', cn: '木星', en: 'Jupiter', glyph: '♃',
		nature: 'benefic', // 第一吉星
		sect: 'diurnal', // 昼间最吉
		gender: 'masculine', qualities: ['hot', 'moist'],
		color: '紫蓝色',
		natural_sig: ['长兄', '朋友', '贵族', '不被怀疑者'],
		keywords: ['幸运', '扩展', '成长', '乐观', '博爱', '宗教', '法律', '国外'],
		industries: ['慈善', '宗教', '法律', '哲学', '国际事务', '高等教育', '海空运'],
		body_parts: ['大腿', '肝'],
	},
	saturn: {
		id: 'saturn', cn: '土星', en: 'Saturn', glyph: '♄',
		nature: 'malefic',
		sect: 'diurnal', // 夜间最凶(出宗派)
		gender: 'masculine', qualities: ['cold', 'dry'],
		color: '黑/深色',
		natural_sig: ['老者', '仆', '奴隶', '外人'],
		keywords: ['结构', '限制', '责任', '耐久', '节俭', '传统', '延迟', '僵硬'],
		industries: ['行政', '劳动', '农业', '土地', '土木', '裁缝', '传统行业'],
		body_parts: ['膝', '关节', '骨', '皮肤'],
	},
	uranus: {
		id: 'uranus', cn: '天王星', en: 'Uranus', glyph: '♅',
		nature: 'conditional', // 多偏凶(科技/团体/科研例外)
		sect: 'none', gender: 'masculine', qualities: [],
		color: '',
		natural_sig: ['革新者', '怪人'],
		keywords: ['突发', '与众不同', '发明', '革新', '人道', '自由思想'],
		industries: ['现代科技', '电子', '航空', '心理学', '占星', '人权', '新型行业'],
		body_parts: ['小腿', '踝', '循环'],
	},
	neptune: {
		id: 'neptune', cn: '海王星', en: 'Neptune', glyph: '♆',
		nature: 'conditional', // 多偏凶(创作例外;不利健康)
		sect: 'none', gender: 'feminine', qualities: [],
		color: '',
		natural_sig: ['神秘者', '艺术家'],
		keywords: ['幻想', '灵感', '迷恋', '混乱', '虚弱', '神秘', '艺术'],
		industries: ['艺术(意境)', '宗教/社服', '玄学', '化学(石油煤气)', '医药', '水/酒'],
		body_parts: ['脚', '淋巴'],
	},
	pluto: {
		id: 'pluto', cn: '冥王星', en: 'Pluto', glyph: '♇',
		nature: 'conditional', // 多偏凶(投资理财例外)
		sect: 'none', gender: 'masculine', qualities: [],
		color: '',
		natural_sig: ['暗中者', '改造者'],
		keywords: ['巨变', '破坏', '重生', '专制', '深沉', '复原', '暗中行动'],
		industries: ['侦探/间谍', '心理分析', '殡葬', '废物处理', '核能', '外科'],
		body_parts: ['生殖', '排泄'],
	},
	north_node: {
		id: 'north_node', cn: '北交点(罗喉)', en: 'North Node', glyph: '☊',
		nature: 'benefic', // 偏吉(弱于实体星)
		sect: 'none', gender: 'masculine', qualities: [],
		color: '绿/金',
		natural_sig: ['名声', '保护'],
		keywords: ['名声', '保护', '增益'],
		industries: [], body_parts: [],
	},
	south_node: {
		id: 'south_node', cn: '南交点(计都)', en: 'South Node', glyph: '☋',
		nature: 'malefic', // 偏凶(弱于实体星)
		sect: 'none', gender: 'feminine', qualities: [],
		color: '',
		natural_sig: ['伤害', '错误'],
		keywords: ['伤害', '错误', '减损'],
		industries: [], body_parts: [],
	},
	fortune: {
		id: 'fortune', cn: '福点', en: 'Part of Fortune', glyph: '⊗',
		nature: 'benefic', // 偏吉
		sect: 'none', gender: 'common', qualities: [],
		color: '',
		natural_sig: ['好运', '财富'],
		keywords: ['好运点', '财富', '身体'],
		industries: [], body_parts: [],
	},
};

// 逆行解读口径（择日清单 §2.1）。retro_weakens 可配置（Marion March 一派不认为逆行必弱）。
export const RETROGRADE_NOTES = {
	mercury: '必避：签约、沟通、交通、购车、商业谈判。',
	venus: '婚姻、买高价物品必避（除非破镜重圆式复合婚）；财务买卖避。',
	mars: '购买机械/汽机车避；行动力类事项避。',
	jupiter: '旅行/法律事务避（尤忌主管 9/7 宫且逆行）；多代表缺乏好运、经济不景气。',
	outer: '三王星逆行太普遍通常不计；但若主管命宫/用事宫，仍不宜逆行。',
	rule: '主管命宫/用事宫的内行星逆行始终标红。',
};

export const CLASSICAL_PLANETS = ['saturn', 'jupiter', 'mars', 'sun', 'venus', 'mercury', 'moon'];
export const DIURNAL_SECT = ['sun', 'jupiter', 'saturn'];
export const NOCTURNAL_SECT = ['moon', 'venus', 'mars'];

export function planetInfo(id){
	return PLANETS[id] || null;
}

export default PLANETS;
