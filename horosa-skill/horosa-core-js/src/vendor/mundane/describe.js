// divination/mundane/describe.js
// 世俗盘解读层（镜像 src/divination/horary/describe.js 的「数据 + 轻引擎」范式）。
// 输入 buildFacts(chart) 的 facts；输出可直接渲染的判词行。判词措辞中性、不带任何出处人名/书名。
import { buildFacts } from '../divination/engine/chartFacts.js';
import { SIGNS } from '../divination/data/signs.js';
import { computeAlmuten } from '../divination/lifespan/lifespanEngine.js';
import { rulesetConfig } from './ruleset.js';

// 行星的世俗象征（社会阶层 / 领域）。
export const PLANET_SIGNIFICATION = {
	sun: '元首 · 政府 · 权威 · 显贵',
	moon: '平民 · 妇女 · 民意 · 农粮 · 水',
	mercury: '媒体 · 商贸 · 文书 · 交通 · 青年',
	venus: '外务 · 艺术 · 女性 · 婚庆 · 娱乐',
	mars: '军务 · 暴力 · 火灾 · 工业 · 争端',
	jupiter: '司法 · 宗教 · 财富 · 银行 · 声望',
	saturn: '行政 · 老人 · 矿农 · 灾荒 · 死亡率',
	uranus: '能源 · 科技 · 变革 · 航空 · 罢工',
	neptune: '慈善 · 宗教团体 · 石油化工 · 海事 · 欺瞒',
	pluto: '底层 · 权力 · 剧变 · 秘藏财富 · 核能',
};

export const PLANET_CN = {
	sun: '太阳', moon: '月亮', mercury: '水星', venus: '金星', mars: '火星',
	jupiter: '木星', saturn: '土星', uranus: '天王星', neptune: '海王星', pluto: '冥王星',
};
export const PLANET_GLYPH = {
	sun: '☉', moon: '☽', mercury: '☿', venus: '♀', mars: '♂',
	jupiter: '♃', saturn: '♄', uranus: '♅', neptune: '♆', pluto: '♇',
};

// 12 世俗宫义（标准世俗占星宫位含义）。
export const MUNDANE_HOUSE_MEANINGS = {
	1: '整体民生 · 国运 · 公共卫生',
	2: '财政 · 国库 · 金融 · 证券',
	3: '交通 · 媒体 · 邮电 · 邻邦 · 基础教育',
	4: '土地 · 农业 · 矿藏 · 房产 · 在野势力',
	5: '娱乐 · 生育率 · 学校 · 股市投机 · 儿童',
	6: '劳工 · 公共卫生 · 军务后勤 · 疾病',
	7: '外交 · 争端 · 战争 · 对外贸易',
	8: '死亡率 · 公债 · 税收 · 外汇',
	9: '司法 · 宗教 · 航运 · 高教 · 科研',
	10: '执政 · 政府 · 元首 · 国家形象',
	11: '立法 · 议会 · 盟邦 · 国际支援',
	12: '监所 · 医院 · 慈善 · 隐患 · 秘敌',
};

// 行星落世俗宫的判词（10 行星 × 12 宫）。措辞概括、需结合相位与宫主状态。
export const PLANET_IN_MUNDANE_HOUSE = {
	sun: {
		1: '国运昌隆、民心向政之象；受克则元首多病、政局不稳。',
		2: '利国库进项、货币前景明朗；受克则税费沉重、公帑虚耗。',
		3: '利交通媒体、文教活跃；受克则交通要员病损、舆论交锋。',
		4: '利土地农业、地产收益；受克则执政遇阻、农事不顺。',
		5: '利文教娱乐、生育率升；受克则剧场娱乐损耗、名伶病亡。',
		6: '利劳工与公卫、军务整饬；受克则疾患流行、海军受损。',
		7: '对外交涉显要；吉相邦交转好、凶相争端战危。',
		8: '显贵之死、税政更张；吉相得遗产税之利、凶相恐慌死亡。',
		9: '利司法宗教航运、科学新见；受克则法宗争议、远航受阻。',
		10: '元首得民望、政府强势；受克则政局困顿、有败战之危。',
		11: '利立法与议政、邦交友善；受克则议员不适、立法受挫。',
		12: '利公共机构整顿、官员显荣；受克则官非蒙羞、隐患滋生。',
	},
	moon: {
		1: '民情活跃、变动频仍；吉相大众得益、凶相骚动不满。',
		2: '财政与汇市波动；吉相国库进项、凶相银行金融倒账。',
		3: '邮路交通从业者动向；吉相条件改善、凶相罢工事故。',
		4: '利农业但天候多变；落固定座且临四宫头主地震之兆。',
		5: '大众趋于娱乐；受克则妇孺多扰、虐童案显。',
		6: '平民疾患与不满；吉相公卫向好、凶相海军失序。',
		7: '利婚嫁与公众仪典；受克则外务生扰、家变离合。',
		8: '平民大量死亡之虞，尤主妇女；受克则恐慌致众死。',
		9: '九宫诸事皆动；视成相之星定吉凶来向。',
		10: '国与政府得民望；受克则贵显病亡、政府失欢。',
		11: '议会与内阁更易；视成相之星定立法利弊。',
		12: '济贫增、大众病；受克则医慈机构丑闻、妇孺受害。',
	},
	mercury: {
		1: '大众研议活跃、新计层出；受克则人身攻讦、刊物互讦。',
		2: '财务变动；吉相商贸进益、凶相被骗失窃、市场诈伪。',
		3: '交通邮电出版活络；受克则运输下滑、文人病亡。',
		4: '农事活力（须吉相）；受克则矿工不满、农时不利。',
		5: '剧界新作冒险、利教育童福；受克则戏讼、学务争议。',
		6: '利劳工与文书事务；受克则劳资讦讼、舆情攻讦。',
		7: '对外协商频繁；吉相谈判成、凶相协约破、外交失言。',
		8: '文界出版与少年之死（受克）；立法涉遗产税。',
		9: '商法学术活跃；受克则商贸分歧、要案伪造。',
		10: '上层与政界活跃、王族出行；受克则政要不光彩、丑闻。',
		11: '议会与商教繁忙；受克则口角辩争、私斗。',
		12: '公共机构与济贫法变动；受克则诽谤、偷窃、伪造。',
	},
	venus: {
		1: '太平和顺、女性事务向好；受克则匮乏堕落、妇孺受害。',
		2: '进项增、国家受益；受克则沉重损失、公帑浪费。',
		3: '交通从业者条件改善；受克则名家病亡、铁路相关案。',
		4: '好天候好收成、农事成功；受克则潮湿失时、农损。',
		5: '生育率升、利妇孺；受克则不道德、虐童暴行。',
		6: '利下层与海军、改善其境；受克则匮乏疾患。',
		7: '邦交和平、婚嫁增多；受克则公共丑闻、离合罪案。',
		8: '遗产税之利；受克则女性艺人之死、名媛地主病亡。',
		9: '殖贸平稳、商势扩展；受克则法宗丑闻、要案缠讼。',
		10: '盛大公典、上层婚嫁；受克则贵妇病亡、上流丑闻。',
		11: '利妇女立法、议员联姻；受克则议员去世、议界丑闻。',
		12: '公益机构受益、捐遗增多；受克则公帑浪费、妇孺受害。',
	},
	mars: {
		1: '大众不满、罢工暴动放火之兆；吉相则军势强、侵略倾向。',
		2: '证券损耗、银行倒闭、恐慌；军费骤增致公帑大耗。',
		3: '铁路事故火灾、巨耗损失；受克则员工骚动、运输重祸。',
		4: '政府生扰、公建火灾、矿难地震；土地农业受损。',
		5: '剧场灾祸、名伶病亡、虐童；学校宴乐火险。',
		6: '热病炎症流行；战舰火灾、水手抗命；吉相则演武检阅。',
		7: '国际争端战危；敌方来向由火星所在座定。',
		8: '骤然惨死（火意外罪案）；军医钢铁军火界要人之死。',
		9: '法宗争议、放火与海难；法宗航界要人之死。',
		10: '主战（尤治七宫时）；贵显病亡、政府多难；吉相得胜。',
		11: '议界大扰大怒、党争分裂；军政军火多议。',
		12: '罪案谋杀煽动暴增；监所公所火灾、囚徒抗法。',
	},
	jupiter: {
		1: '国泰民丰、百业兴成；最顺之位；受克视来向减利。',
		2: '进项大增、财政改善、银商兴旺；亦或减税；受克则巨耗倒账。',
		3: '利铁路交通、工资工况改善、文教邮政繁忙。',
		4: '利地主农业好天候；受克且落固定座则矿难地震。',
		5: '利诸娱乐、生育率升、利学校教育；受克则娱乐巨耗、投机败。',
		6: '利公卫劳工、海军得益；受克则军费巨耗。',
		7: '利外交诸事、婚嫁增、名盟多；受克则与他邦财贸纠纷。',
		8: '遗产税之利国；受克则贵显法宗银界要人之死。',
		9: '利宗教商贸殖运；商势成功；受克则宗争财困巨耗。',
		10: '利政府、国誉上升、政平民安；受克则财困、要人或亡。',
		11: '极利之位：民主立法、商财向好；受克则宗财之争、债贬。',
		12: '利监所公所公益、增捐、管理改善；受克则巨耗官非。',
	},
	saturn: {
		1: '艰困不满、失业贸损、贫病之兆；吉相则坚忍渐起但少厚利。',
		2: '财政萧条、保险金融不振、钱事乏力；受克则证券大跌。',
		3: '员工不满、运输邮政收降、事故；文界要人病亡。',
		4: '阻滞政府、坏天候农损；矿难地震、地价贬、产权纠纷。',
		5: '生育率降、妇孺多扰高病亡、剧界压抑名伶病故。',
		6: '平民大量疾患（按所占座定病）、下层海军不满。',
		7: '极不利外务：邦交大困、外贸萧条；金星克之则离合罪案。',
		8: '老人显贵要职者大量死亡之位。',
		9: '害航运（海难碰撞多死）、法宗大困、此业要人病亡。',
		10: '不利之位：王族政府要人蒙羞遭难、要人病亡（尤土克日时）。',
		11: '不利（除吉相）：国事多难、议员病亡、党裂部辞。',
		12: '极不幸：罪案多、医所财困、官蒙羞失荣。',
	},
	uranus: {
		1: '罢工骚动政乱、激愤当权之兆；吉相则民求改革质询。',
		2: '财政意外得失（视相位）、市场异象、金融不安。',
		3: '铁路电讯汽车异常事故爆炸；员工罢工抗命、邮务受扰。',
		4: '水电公司大扰、矿难、公建爆炸；不利政府土地税。',
		5: '剧场学校娱乐场爆炸；不利教育、童与社交聚会灾。',
		6: '诸般异常失序；军舰爆炸、水手抗命叛乱；重大意外。',
		7: '外务难堪意外重难；激起反对骚动；金星克之则离合诉讼。',
		8: '骤死多（意外爆炸触电自戕等怪死）。',
		9: '爆炸海难火灾罢工；殖地骤变；吉相则重大科学发明。',
		10: '政界骤变需慎处、或败辞频仍；攻击义愤王族。',
		11: '议界异常困局、内阁突发须慎；多无法之争、议员险情。',
		12: '吉相则公所改革；受克则监所罪案纵火爆炸煽乱抗法。',
	},
	neptune: {
		1: '煽动密宣、社运罪案自戕；黑白颠倒背信之兆。',
		2: '欺骗失实、非法致财损、偷骗诈伪（受克更烈）。',
		3: '员工密谋秘运、社运计划、商损与诈骗渐露。',
		4: '难测之扰；土地税地价矿费相关社运暴动、政府大扰。',
		5: '邪秽不道、剧界丑闻、虐童、教育受扰、赌博激增。',
		6: '下层邪秽不道、社运宣传伤害；毒瘾鸦片害众健康。',
		7: '对他邦背信失言；密谋策动秘袭之警；离合罪案缠讼。',
		8: '溺水中毒毒瘾厄运过量致死多；精神错乱自戕增。',
		9: '法宗丑闻罪讼、商贸欺诈；招魂唯心骗子败露；吉相利玄秘发现。',
		10: '社运暴动抗元首政府、时髦人愁、要人丑事。',
		11: '社运暴动密行、议员采掘工作、丑事；社运立法现公选。',
		12: '济贫法医慈管理丑闻；待贫之社运方式引入；多骗术不快。',
	},
	pluto: {
		1: '民情深层剧变、权力底层暗涌；旧序瓦解重塑。',
		2: '隐秘财富与税政剧变；金融权力洗牌、暗资暗债。',
		3: '媒体交通深层变局、信息权重组。',
		4: '土地资源剧变、地下矿核之事、根基动摇。',
		5: '投机与娱乐的极端化、隐性操控。',
		6: '劳工底层之剧变、流行病与公卫深层冲击。',
		7: '外交权力博弈、强制与博弈式的对抗。',
		8: '生死税债之剧变、隐秘财与核能之事。',
		9: '司法宗教学术之颠覆、深层信念变迁。',
		10: '政权深层洗牌、强制变革、权力集中或崩解。',
		11: '立法与盟邦权力重组、群体力量爆发。',
		12: '隐患秘敌核与地下之事、深层危机酝酿。',
	},
};

// 食的元素判词（按被食光体所在座之元素）。
export const ECLIPSE_ELEMENT = {
	fire: '主战乱、火灾、君王显贵之厄、牲畜五谷之损（火象）。',
	earth: '主旱歉、地震、矿难、农产不足（土象）。',
	air: '主疫病、风灾、动荡与有害风暴（风象）。',
	water: '主水患、航海与近水生灵之损、大众多死（水象）。',
};

// 食落各座分度（前期 0–10° / 中期 10–20° / 后期 20–30°）的概括判词。
export const ECLIPSE_DECAN = {
	aries: ['战乱纷争、军队调动、空气过燥。', '君王囚伤哀恸、果树作物腐损。', '人多悲苦、贵妇之死、牲畜之损。'],
	taurus: ['商贸冲突、庄稼粮作毁损。', '旅者与孕产妇女之险。', '主瘟疫与饥荒。'],
	gemini: ['宗教教派纷争、法纪受蔑。', '海盗偷窃与谋杀。', '君王之死、国家生乱。'],
	cancer: ['大气扰动、天候剧变。', '河泉枯涸、女性放纵。', '煽乱、瘟疫与大疾。'],
	leo: ['权贵相争、宫廷生变。', '君王显贵之厄、火灾。', '名望受损、骄横致祸。'],
	virgo: ['劳工与文书之扰、谷物受损。', '疾病流行、卫生堪忧。', '商贸纠葛、欺伪显露。'],
	libra: ['外交失衡、契约纷争。', '婚事与合伙生变。', '法政失序、公议汹汹。'],
	scorpio: ['暗争密谋、毒害与暴力。', '死亡率升、税债之厄。', '水患与隐祸、骤变将至。'],
	sagittarius: ['宗教法律之争、远行受阻。', '航运出版生变、外事波折。', '理念冲突、信仰动摇。'],
	capricorn: ['政权阻滞、行政多艰。', '老人显贵之厄、矿难。', '土地产权之争、根基动摇。'],
	aquarius: ['变革激荡、社团骚动。', '科技能源异象、突发改革。', '群体动荡、旧序瓦解。'],
	pisces: ['海事水患、欺瞒丑闻。', '瘟疫毒害、精神之困。', '隐秘消散、虚妄迷茫。'],
};

// ═══════════ §13 世运判读真值源(WP-3;措辞中性,无人名书名;高转录风险表标 TODO 待校)═══════════

// §13.1 十二宫世运义(三栏:国家本体 / 机构团体 / 事务·所断)。
export const MUNDANE_HOUSE_FULL = {
	1: { body: '国家/全体国民、国势总貌、国民健康与士气', institution: '—', affairs: '国家总体状态、声誉、人口、公共卫生总览' },
	2: { body: '国家财政/经济/财富、货币', institution: '银行、国库、证券(财富面)', affairs: 'GDP、贸易收入、币值、国家流动性、税收所得' },
	3: { body: '通讯、交通、邻国', institution: '媒体/报刊、铁路公路、邮电、基础教育', affairs: '流言舆论、国内交通、与邻国往来、短途运输' },
	4: { body: '国土、土地、农业、矿产、不动产', institution: '在野党/反对派、内政、气候收成', affairs: '房地产、矿业、领土、事情的结局、反对势力' },
	5: { body: '出生率、儿童、享乐', institution: '娱乐/剧院/体育、证券交易/投机', affairs: '国民生育、文体活动、社交、青少年、投机风潮' },
	6: { body: '公共卫生/疾病、劳工', institution: '军队(服役面)、公务员、工会、卫生系统', affairs: '疫病、罢工、劳资、军需后勤、底层民生' },
	7: { body: '外交、战与和、公开的敌人', institution: '条约、国际关系、外国', affairs: '战争/和平、外交纠纷、外国势力、国际诉讼、联姻' },
	8: { body: '死亡率、国债、涉外财务', institution: '税务(涉外)、利率、保险', affairs: '国民死亡、外债、利率、危机、神秘/隐秘事务' },
	9: { body: '宗教、法律、司法、高等教育', institution: '教会、法院/法官、大学、远洋外贸', affairs: '信仰、长途/国际、科学、出版、公共道德、航运' },
	10: { body: '政府、元首(君主/总统)、执政当局', institution: '当权派、最高权威、国家声望', affairs: '国运走向、政权、王朝、当局威信(最重)' },
	11: { body: '立法机构(议会/国会)、盟友', institution: '地方议会、友邦、社团', affairs: '立法、国家目标/愿景、结盟、改革诉求' },
	12: { body: '监狱、医院、收容机构、暗敌', institution: '间谍、社会福利、秘密机关', affairs: '隐患、阴谋、犯罪、流放、自我消耗、瘟疫隔离' },
};

// §13.2 十曜世运义(两栏:人·权力 / 领域·行业·群体)。
export const PLANET_MUNDANE_FULL = {
	sun: { powerRole: '元首/君主/总统、政府权威、国家活力', domains: '显贵、领导阶层、国家整体' },
	moon: { powerRole: '平民/大众、公众情绪与舆论、女性', domains: '民生、家庭、人口流动、生育、日常用品、海事(潮)' },
	mercury: { powerRole: '媒体/新闻、青年、文书', domains: '报刊、贸易、交通、通讯、教育、文学、条约文件' },
	venus: { powerRole: '外交/和平、青年女性', domains: '艺术/文化、货币、娱乐、时尚、社会和谐、结盟' },
	mars: { powerRole: '军队/军人、警察', domains: '战争/暴力、工业制造、罢工动乱、火灾事故、外科、能源' },
	jupiter: { powerRole: '司法/法官、神职/教会、贵族富人', domains: '法律、银行金融、扩张繁荣、外贸、乐观、保险' },
	saturn: { powerRole: '劳工/工人阶级、老年、当权的旧秩序', domains: '国土/农业/矿业、死亡、紧缩/萧条、限制、基建、国家机器' },
	uranus: { powerRole: '革命者/激进派、改革者', domains: '革命/政变、航空航天、科技/电力/电子、突变、独立运动、罢工' },
	neptune: { powerRole: '理想主义者、社会主义/共产主义', domains: '石油/天然气、海洋/海军、丑闻腐败欺诈、影视、毒品瘟疫、化工、意识形态幻象' },
	pluto: { powerRole: '极权/独裁、地下势力、群众运动', domains: '核/原子、权力剧变、有组织犯罪、人口/世代力量、恐怖主义、深层重构' },
};

// §13.3 十二座世运气质(模式·元素 + 气质)。
export const SIGN_MUNDANE_TEMPER = {
	aries: { modeElement: '基本·火', temper: '开创、军事、冲动、战争与新政权的发起' },
	taurus: { modeElement: '固定·土', temper: '财富、土地、农业、货币稳定、固执' },
	gemini: { modeElement: '变动·风', temper: '媒体舆论、交通、贸易、谈判、善变' },
	cancer: { modeElement: '基本·水', temper: '民众情绪、国土家园、民族主义、海事' },
	leo: { modeElement: '固定·火', temper: '王权/元首、威望、专制、娱乐与盛典' },
	virgo: { modeElement: '变动·土', temper: '劳工、公共卫生、官僚、批评、效率' },
	libra: { modeElement: '基本·风', temper: '外交、法律、条约、和平/战争的均衡' },
	scorpio: { modeElement: '固定·水', temper: '危机、税收/国债、隐秘权力、死亡与重生' },
	sagittarius: { modeElement: '变动·火', temper: '宗教、司法、外贸、远方、扩张与理想' },
	capricorn: { modeElement: '基本·土', temper: '国家结构、当权、紧缩、传统建制' },
	aquarius: { modeElement: '固定·风', temper: '革命、立法、科技、群众、理想社会' },
	pisces: { modeElement: '变动·水', temper: '意识形态、瓦解、瘟疫、海洋、牺牲与混沌' },
};

const _SIGN_BASE = { aries: 0, taurus: 30, gemini: 60, cancer: 90, leo: 120, virgo: 150, libra: 180, scorpio: 210, sagittarius: 240, capricorn: 270, aquarius: 300, pisces: 330 };

// §13.4 世运恒星(22 主星;sign+signlon 为 ≈2000 回归黄经位置;royal=四王星方位。lon2000 = 座基+座内度)。
// ⚠ 高转录风险:黄经按古籍 ≈2000 现值,用时以 mundaneStarLon 按盘日岁差(~50.29″/yr)校正。
export const MUNDANE_FIXED_STARS = [
	{ key: 'algol', nameCn: '大陵五', name: 'Algol', sign: 'taurus', signlon: 26 + 10 / 60, nature: '♄/♃', meaning: '最凶之星;失首、暴力、群体灾祸', royal: null },
	{ key: 'alcyone', nameCn: '昴宿(七姊妹)', name: 'Alcyone', sign: 'gemini', signlon: 0, nature: '☽/♂', meaning: '哭泣、失明、悲伤、群体之殇', royal: null },
	{ key: 'aldebaran', nameCn: '毕宿五', name: 'Aldebaran', sign: 'gemini', signlon: 9 + 47 / 60, nature: '♂', meaning: '荣誉正直、军功;受克则暴力倾覆', royal: '东' },
	{ key: 'rigel', nameCn: '参宿七', name: 'Rigel', sign: 'gemini', signlon: 16 + 50 / 60, nature: '♃/♄', meaning: '技术/军事显赫、财富', royal: null },
	{ key: 'bellatrix', nameCn: '参宿五', name: 'Bellatrix', sign: 'gemini', signlon: 20 + 57 / 60, nature: '♂/☿', meaning: '决断、军功、事故', royal: null },
	{ key: 'capella', nameCn: '五车二', name: 'Capella', sign: 'gemini', signlon: 21 + 51 / 60, nature: '♂/☿', meaning: '好奇、显位', royal: null },
	{ key: 'betelgeuse', nameCn: '参宿四', name: 'Betelgeuse', sign: 'gemini', signlon: 28 + 45 / 60, nature: '♂/☿', meaning: '武功、好运', royal: null },
	{ key: 'sirius', nameCn: '天狼', name: 'Sirius', sign: 'cancer', signlon: 14 + 5 / 60, nature: '♃/♂', meaning: '荣名、财富、灼热', royal: null },
	{ key: 'castor', nameCn: '北河二', name: 'Castor', sign: 'cancer', signlon: 20 + 14 / 60, nature: '☿', meaning: '文才、骤起骤落', royal: null },
	{ key: 'pollux', nameCn: '北河三', name: 'Pollux', sign: 'cancer', signlon: 23 + 13 / 60, nature: '♂', meaning: '恶少年、争斗、暴力', royal: null },
	{ key: 'procyon', nameCn: '南河三', name: 'Procyon', sign: 'cancer', signlon: 25 + 47 / 60, nature: '☿/♂', meaning: '骤升后跌、躁动', royal: null },
	{ key: 'praesepe', nameCn: '鬼宿星团', name: 'Praesepe', sign: 'leo', signlon: 7 + 20 / 60, nature: '♂/☽', meaning: '眼疾、群体不幸', royal: null },
	{ key: 'regulus', nameCn: '轩辕十四', name: 'Regulus', sign: 'leo', signlon: 29 + 50 / 60, nature: '♂/♃', meaning: '王权、军功、权位;报复则倾覆', royal: '北' },
	{ key: 'vindemiatrix', nameCn: '东次将', name: 'Vindemiatrix', sign: 'libra', signlon: 9 + 57 / 60, nature: '♄/☿', meaning: '寡妇制造者、损失', royal: null },
	{ key: 'spica', nameCn: '角宿一', name: 'Spica', sign: 'libra', signlon: 23 + 50 / 60, nature: '♀/♂', meaning: '最吉之星;天赋、繁荣、护佑', royal: null },
	{ key: 'arcturus', nameCn: '大角', name: 'Arcturus', sign: 'libra', signlon: 24 + 14 / 60, nature: '♂/♃', meaning: '远行致富、新路', royal: null },
	{ key: 'antares', nameCn: '心宿二', name: 'Antares', sign: 'sagittarius', signlon: 9 + 46 / 60, nature: '♂/♃', meaning: '武勋;鲁莽、毁灭、极端', royal: '西' },
	{ key: 'vega', nameCn: '织女一', name: 'Vega', sign: 'capricorn', signlon: 15 + 19 / 60, nature: '♀/☿', meaning: '艺术、魅力、易逝', royal: null },
	{ key: 'altair', nameCn: '河鼓二(牛郎)', name: 'Altair', sign: 'aquarius', signlon: 1 + 47 / 60, nature: '♂/♃', meaning: '大胆、骤名、危险', royal: null },
	{ key: 'fomalhaut', nameCn: '北落师门', name: 'Fomalhaut', sign: 'pisces', signlon: 3 + 52 / 60, nature: '♀/☿', meaning: '名望、理想;亦可堕落', royal: '南' },
	{ key: 'markab', nameCn: '室宿一', name: 'Markab', sign: 'pisces', signlon: 23 + 29 / 60, nature: '♂/☿', meaning: '火器/兵刃之险', royal: null },
	{ key: 'scheat', nameCn: '室宿二', name: 'Scheat', sign: 'pisces', signlon: 29 + 22 / 60, nature: '♂/☿(♄)', meaning: '灾难、溺水、极端不幸', royal: null },
].map((st) => Object.assign(st, { lon2000: (_SIGN_BASE[st.sign] + st.signlon) % 360 }));

// §13.5 相位世运框(硬/软、入/出相、紧密 orb)。
export const MUNDANE_ASPECT_FRAME = {
	hard: '合/对分/四分(硬相位):事件、张力、冲突、转折;凶星(♂♄)及外行星(♅♆♇)硬相位克四轴/日月 → 危机、动荡、灾害。',
	soft: '三分/六分(软相位):顺遂、缓和、机遇、建设。',
	applying: '入相位(applying)定未发将发与应期;出相位(separating)表已过之事。',
	tight: '世运重紧密容许度(≤1–3°)与触发时点(流运精确合/克地区盘或入境盘关键点的日期)。',
};

// 恒星按盘日岁差校正后的当前黄经(2000→year,线性 ~50.29″/yr ≈ 1°/71.6 年前移)。
export function mundaneStarLon(star, year){
	if(!star){ return null; }
	const base = (typeof star.lon2000 === 'number') ? star.lon2000 : (_SIGN_BASE[star.sign] + (star.signlon || 0));
	const y = (typeof year === 'number' && isFinite(year)) ? year : 2000;
	return ((base + (y - 2000) * (50.29 / 3600)) % 360 + 360) % 360;
}

// 给定若干「点」{key,lon}(行星/四轴),返回每点合恒星的命中(默认 orb 1.5°,按盘年岁差校正)。
export function mundaneFixedStarHits(points, year, orb){
	const o = (typeof orb === 'number' && orb > 0) ? orb : 1.5;
	const hits = [];
	(points || []).forEach((pt) => {
		if(!pt || typeof pt.lon !== 'number'){ return; }
		MUNDANE_FIXED_STARS.forEach((st) => {
			const slon = mundaneStarLon(st, year);
			let d = Math.abs(((pt.lon - slon + 180) % 360 + 360) % 360 - 180);
			if(d <= o){
				hits.push({ point: pt.key, pointCn: pt.cn || pt.key, star: st.key, starCn: st.nameCn,
					nature: st.nature, meaning: st.meaning, royal: st.royal, orb: Math.round(d * 100) / 100, starLon: slon });
			}
		});
	});
	return hits;
}


const MUNDANE_PLANET_KEYS = ['sun', 'moon', 'mercury', 'venus', 'mars', 'jupiter', 'saturn', 'uranus', 'neptune', 'pluto'];

// 描述一张世俗盘：逐个行星落宫的世俗判词。返回行数组。
export function describeMundaneChart(facts){
	if(!facts || !facts.planets){ return []; }
	const rows = [];
	MUNDANE_PLANET_KEYS.forEach((k) => {
		const p = facts.planets[k];
		if(!p || !p.house){ return; }
		const houseMeaning = MUNDANE_HOUSE_MEANINGS[p.house] || '';
		const table = PLANET_IN_MUNDANE_HOUSE[k] || {};
		const text = table[p.house] || '';
		rows.push({
			planet: k,
			planetCn: PLANET_CN[k] || k,
			planetGlyph: PLANET_GLYPH[k] || '',
			signification: PLANET_SIGNIFICATION[k] || '',
			planetMundane: PLANET_MUNDANE_FULL[k] || null,
			sign: p.sign,
			signTemper: p.sign ? SIGN_MUNDANE_TEMPER[p.sign] || null : null,
			house: p.house,
			houseMeaning,
			houseFull: MUNDANE_HOUSE_FULL[p.house] || null,
			angularity: p.angularity,
			retro: p.retro,
			text,
		});
	});
	return rows;
}

// 从 facts 取 10 行星 + 上升/天顶 各点(供 §13.4 恒星命中检测)。
export function buildMundaneStarPoints(facts){
	if(!facts || !facts.planets){ return []; }
	const pts = [];
	MUNDANE_PLANET_KEYS.forEach((k) => {
		const pl = facts.planets[k];
		if(pl && pl.lon != null){ pts.push({ key: k, cn: PLANET_CN[k] || k, lon: pl.lon }); }
	});
	const lons = facts.lons || {};
	if(lons.asc != null){ pts.push({ key: 'asc', cn: '上升', lon: lons.asc }); }
	if(lons.mc != null){ pts.push({ key: 'mc', cn: '天顶', lon: lons.mc }); }
	return pts;
}

// §16.2 年主/盘主 victor:5 hylegiacal 点(ASC/☉/☽/福点/产前朔望)各 5 重尊贵(庙5旺4三分3界2外观1)累加 + 偶然(宫位)
// → 累分最高者 = 年主/盘主。复用主限法 computeAlmuten(同一尊贵引擎);缺福点/产前朔望则按可用点累计,不臆造。
// rulesetKey(可选)：传入世运规则集 → 按其 termsVariant/triplicityVariant 给 computeAlmuten 换界主/三分主表;
// 缺省=默认现状(modern=埃及界+多罗修斯,零回归)。中世纪档 termsVariant='ptolemaic' → 界主换托勒密界、
// 年主/盘主据之重算(切档真换 victor);三分各档暂皆多罗修斯(换表机制已打通,供日后档位选用)。
// [G6] 偶然加减分层(定局偶然状态口径,叠加在五点尊贵+宫位分之上;只在世运 victor 卡生效,
// 绝不回写 computeAlmuten/寿命引擎 —— 主限链 byte-perfect 不碰)。
// 古籍此节仅定性(「当令昼/夜主加分;隐宫/焦伤/逆行/被围攻降格」,宫位分已由 HOUSE_SCORES 承担),
// 数值为本引擎统一刻度(与尊贵 5..1 同源),明细逐项回显供稽核。
const SECT_DIURNAL = ['sun', 'jupiter', 'saturn'];
const SECT_NOCTURNAL = ['moon', 'venus', 'mars'];
function mundaneAccidentalAdjust(facts){
	const sect = (facts.meta && facts.meta.sect) || 'day';
	const besieged = new Set();
	try{
		const atk = facts.result && facts.result.surround && facts.result.surround.attacks;
		(atk || []).forEach((a) => { const t = a && (a.target || a.planet || a.id); if(t){ besieged.add(String(t).toLowerCase()); } });
	}catch(e){ /* 无围攻数据则零减分 */ }
	const out = {};
	['sun', 'moon', 'mercury', 'venus', 'mars', 'jupiter', 'saturn'].forEach((k) => {
		const p = facts.planets[k];
		if(!p){ return; }
		let delta = 0;
		const items = [];
		const inSect = (sect === 'day' && SECT_DIURNAL.indexOf(k) >= 0) || (sect === 'night' && SECT_NOCTURNAL.indexOf(k) >= 0);
		if(inSect){ delta += 3; items.push({ cn: '当令(得时)', v: +3 }); }
		if(p.combustion === 'combust'){ delta -= 5; items.push({ cn: '焦伤', v: -5 }); }
		else if(p.combustion === 'under_beams'){ delta -= 2; items.push({ cn: '日光束下', v: -2 }); }
		if(p.retro){ delta -= 5; items.push({ cn: '逆行', v: -5 }); }
		if(besieged.has(k)){ delta -= 4; items.push({ cn: '被围攻', v: -4 }); }
		if(items.length){ out[k] = { delta, items }; }
	});
	return out;
}

export function describeMundaneVictor(facts, rulesetKey){
	if(!facts || !facts.planets || !facts.meta){ return null; }
	const cfg = rulesetConfig(rulesetKey);
	const variants = { termsVariant: cfg.termsVariant, triplicityVariant: cfg.triplicityVariant };
	let alm = null;
	try{ alm = computeAlmuten(facts, variants); }catch(e){ return null; }
	if(!alm || !alm.winner){ return null; }
	// [G6] 偶然层叠加:基分(五点尊贵+宫位)+偶然增减 → 终分排序;胜者可能因焦伤/逆行易主。
	const acc = mundaneAccidentalAdjust(facts);
	const scores = Object.keys(alm.totals || {})
		.map((k) => {
			const base = alm.totals[k];
			const a = acc[k] || null;
			return {
				planet: k, cn: PLANET_CN[k] || k, glyph: PLANET_GLYPH[k] || '',
				base, accidental: a ? a.delta : 0, accidentalItems: a ? a.items : [],
				score: base + (a ? a.delta : 0),
			};
		})
		.sort((a, b) => b.score - a.score);
	const winner = scores.length ? scores[0].planet : alm.winner;
	const POINT_CN = { asc: '上升', sun: '太阳', moon: '月亮', fortune: '福点', syzygy: '产前朔望' };
	return {
		victor: winner, victorCn: PLANET_CN[winner] || winner, victorGlyph: PLANET_GLYPH[winner] || '',
		victorMundane: PLANET_MUNDANE_FULL[winner] || null,
		scores,
		points: (alm.points || []).map((pt) => POINT_CN[pt] || pt),
		maxScore: scores.length ? scores[0].score : 0,
		hasAccidentals: Object.keys(acc).length > 0,
	};
}

// §8.5 入境盘判读骨架:上升座+主星(状态) / 第10宫主星+太阳=政权 / 月亮=民生 / 临四轴星(凶星标红) / 外行星落宫。
export function describeIngressSkeleton(facts){
	if(!facts || !facts.planets){ return null; }
	const P = facts.planets;
	const H = facts.houses || {};
	const ascSign = (facts.meta && facts.meta.ascSign) || (H[1] && H[1].sign) || null;
	const ascMeta = ascSign ? SIGNS[ascSign] : null;
	const ascRulerKey = ascMeta ? ascMeta.domicile : null;
	const arP = ascRulerKey ? P[ascRulerKey] : null;
	const tenthRuler = H[10] ? H[10].ruler : null;
	const tenthRulerP = tenthRuler ? P[tenthRuler] : null;
	const hInfo = (pl) => (pl && pl.house) ? { house: pl.house, houseMeaning: MUNDANE_HOUSE_MEANINGS[pl.house] || '', sign: pl.sign } : null;
	const angular = MUNDANE_PLANET_KEYS.filter((k) => P[k] && P[k].angularity === 'angular');
	const outers = ['uranus', 'neptune', 'pluto'].filter((k) => P[k] && P[k].house)
		.map((k) => ({ key: k, cn: PLANET_CN[k] || k, house: P[k].house, houseMeaning: MUNDANE_HOUSE_MEANINGS[P[k].house] || '', sign: P[k].sign }));
	return {
		ascSign, ascSignCn: ascMeta ? ascMeta.cn : ascSign,
		ascTemper: ascSign ? SIGN_MUNDANE_TEMPER[ascSign] || null : null,
		ascRuler: ascRulerKey, ascRulerCn: PLANET_CN[ascRulerKey] || ascRulerKey,
		ascRulerHouse: arP ? arP.house : null, ascRulerSign: arP ? arP.sign : null,
		ascRulerAngular: !!(arP && arP.angularity === 'angular'), ascRulerRetro: !!(arP && arP.retro),
		sun: hInfo(P.sun), moon: hInfo(P.moon),
		tenthRuler, tenthRulerCn: PLANET_CN[tenthRuler] || tenthRuler,
		tenthRulerHouse: tenthRulerP ? tenthRulerP.house : null,
		tenthPlanets: ((H[10] && H[10].planets) || []).map((k) => ({ key: k, cn: PLANET_CN[k] || k })),
		angular: angular.map((k) => ({ key: k, cn: PLANET_CN[k] || k, house: P[k].house, malefic: k === 'mars' || k === 'saturn' })),
		outers,
	};
}

// 描述一张食盘：被食光体（日食看太阳、月食看月亮）的元素 + 分度判词。
export function describeEclipse(facts, kind){
	if(!facts || !facts.planets){ return null; }
	const lumKey = kind === 'lunar' ? 'moon' : 'sun';
	const lum = facts.planets[lumKey];
	if(!lum){ return null; }
	const sign = lum.sign;
	const signMeta = sign ? SIGNS[sign] : null;
	const element = signMeta ? signMeta.element : null;
	const decan = (lum.signlon != null) ? Math.min(2, Math.floor(lum.signlon / 10)) : 0;
	const decanArr = sign ? ECLIPSE_DECAN[sign] : null;
	return {
		kind: kind === 'lunar' ? 'lunar' : 'solar',
		luminary: lumKey,
		luminaryCn: PLANET_CN[lumKey],
		sign,
		signCn: signMeta ? signMeta.cn : sign,
		element,
		elementText: element ? ECLIPSE_ELEMENT[element] : '',
		decan,
		decanLabel: ['前期(0–10°)', '中期(10–20°)', '后期(20–30°)'][decan],
		decanText: decanArr ? decanArr[decan] : '',
		house: lum.house,
		houseMeaning: lum.house ? MUNDANE_HOUSE_MEANINGS[lum.house] : '',
	};
}

// §10.3 食增强:受冲行星(对食点 合/刑/冲 硬相位,凶星标红)+ 食点落宫。受冲星定受影响主题。
// orbScheme(可选):'by_aspect'(现代,默认 ≤3° — 零回归) / 'moiety'(古典 moiety,收紧至 ≤2°,更严择受冲星)。
const ECLIPSE_ORB_BY_SCHEME = { by_aspect: 3, moiety: 2 };
export function describeEclipseAfflictions(facts, kind, orbScheme){
	if(!facts || !facts.planets){ return null; }
	const lumKey = kind === 'lunar' ? 'moon' : 'sun';
	const lum = facts.planets[lumKey];
	if(!lum || lum.lon == null){ return null; }
	const eLon = lum.lon;
	const maxOrb = ECLIPSE_ORB_BY_SCHEME[orbScheme] != null ? ECLIPSE_ORB_BY_SCHEME[orbScheme] : ECLIPSE_ORB_BY_SCHEME.by_aspect;
	const ASP = [{ deg: 0, cn: '合' }, { deg: 90, cn: '刑' }, { deg: 180, cn: '冲' }];
	const MAL = ['mars', 'saturn', 'uranus', 'neptune', 'pluto'];
	const afflictors = [];
	['mars', 'saturn', 'jupiter', 'venus', 'mercury', 'uranus', 'neptune', 'pluto'].forEach((k) => {
		if(k === lumKey){ return; }
		const p = facts.planets[k];
		if(!p || p.lon == null){ return; }
		const d = Math.abs(((p.lon - eLon + 180) % 360 + 360) % 360 - 180);
		let best = null;
		ASP.forEach((a) => { const orb = Math.abs(d - a.deg); if(orb <= maxOrb && (!best || orb < best.orb)){ best = { aspect: a.cn, orb: Math.round(orb * 10) / 10 }; } });
		if(best){ afflictors.push({ planet: k, cn: PLANET_CN[k] || k, glyph: PLANET_GLYPH[k] || '', aspect: best.aspect, orb: best.orb, malefic: MAL.indexOf(k) >= 0 }); }
	});
	afflictors.sort((a, b) => a.orb - b.orb);
	return { afflictors, house: lum.house || null, houseMeaning: lum.house ? (MUNDANE_HOUSE_MEANINGS[lum.house] || '') : '', orbScheme: orbScheme || 'by_aspect', maxOrb };
}

// §14.2 托勒密天气占星(astrometeorology,best-effort):入境/朔望盘中「临角」或「合月(≤12°)」之行星 → 该季/旬天气倾向。
const WEATHER_PLANET = {
	saturn: '寒冷·阴湿·霜雪', mars: '炎热·干旱·雷火', jupiter: '温和·多风·晴好', venus: '多云·阵雨·和暖',
	mercury: '多变·疾风·骤雨', sun: '合于时令·偏燥', moon: '潮湿·多雨·雾',
};
const WEATHER_KEYS = ['saturn', 'mars', 'jupiter', 'venus', 'mercury', 'sun', 'moon'];
export function describeMundaneWeather(facts){
	if(!facts || !facts.planets){ return null; }
	const P = facts.planets;
	const moonLon = (P.moon && P.moon.lon != null) ? P.moon.lon : null;
	const sep = (a, b) => Math.abs(((a - b + 180) % 360 + 360) % 360 - 180);
	const factors = [];
	WEATHER_KEYS.forEach((k) => {
		const p = P[k];
		if(!p){ return; }
		const angular = p.angularity === 'angular';
		const nearMoon = (k !== 'moon' && moonLon != null && p.lon != null) ? (sep(p.lon, moonLon) <= 12) : false;
		if(angular || nearMoon){
			factors.push({ key: k, cn: PLANET_CN[k] || k, weather: WEATHER_PLANET[k], angular, nearMoon, malefic: (k === 'saturn' || k === 'mars') });
		}
	});
	if(!factors.length){ return null; }
	return { factors };
}

// §8.4 产前朔望:入境/盘前最近一次新/满月(后端 Result 已含 Syzygy 对象;victor 定局已取其度,此处独立展示)。
export function describeMundaneSyzygy(facts){
	if(!facts || !facts.result){ return null; }
	const r = facts.result;
	let o = (r.objectMap && r.objectMap.Syzygy) || null;
	if(!o){ const objs = (r.chart && r.chart.objects) || []; for(let i = 0; i < objs.length; i++){ if(objs[i].id === 'Syzygy'){ o = objs[i]; break; } } }
	if(!o || o.lon == null){ return null; }
	const sign = o.sign ? String(o.sign).toLowerCase() : Object.keys(_SIGN_BASE)[Math.floor((((o.lon % 360) + 360) % 360) / 30)];
	const signlon = (o.signlon != null) ? o.signlon : (((o.lon % 30) + 30) % 30);
	const phase = (facts.meta && facts.meta.moonPhase) ? facts.meta.moonPhase.phase : null;
	// 渐盈(waxing)→ 盘前最近朔望=新月(日月合);渐亏(waning)→ 满月(日月冲)。
	const kind = (phase === 'waxing') ? '新月(日月合)' : (phase === 'waning' ? '满月(日月冲)' : null);
	return { sign, signCn: sign ? ((SIGNS[sign] || {}).cn || sign) : null, signlon, lon: o.lon, kind };
}

// §16.3 会合盘指示星:木/土谁在会合座更得力 → 该纪元偏吉(扩张)/凶(紧缩);会合座元素 → 气候与领域。
const ELEMENT_CLIMATE = {
	fire: '炎热干旱、能源与战事、行动激进而易躁',
	earth: '务实保守、农业土地与财经、稳定而变革迟缓',
	air: '思潮舆论、外交通讯与科技、多议而善变',
	water: '民情危机、水患疫病、情绪与意识形态主导',
};
export function mundaneConjunctionIndicator(facts){
	if(!facts || !facts.planets){ return null; }
	const J = facts.planets.jupiter, S = facts.planets.saturn;
	if(!J || !S || J.lon == null || S.lon == null){ return null; }
	const sep = Math.abs(((J.lon - S.lon + 180) % 360 + 360) % 360 - 180);
	if(sep > 12){ return null; }   // 仅木土会合盘(角距 ≤12°)显示指示星
	const signKey = J.sign || Object.keys(_SIGN_BASE)[Math.floor((((J.lon % 360) + 360) % 360) / 30)];
	const meta = SIGNS[signKey] || {};
	const exP = meta.exaltation ? meta.exaltation.planet : null;
	let stronger = null;
	if(meta.domicile === 'jupiter' || exP === 'jupiter'){ stronger = 'jupiter'; }
	else if(meta.domicile === 'saturn' || exP === 'saturn'){ stronger = 'saturn'; }
	let tone, toneText;
	if(stronger === 'jupiter'){ tone = '吉'; toneText = '木星得力 → 该纪元偏扩张繁荣、法制与宗教昌明、外贸金融活跃。'; }
	else if(stronger === 'saturn'){ tone = '凶'; toneText = '土星得力 → 该纪元偏紧缩萧条、旧秩序强化、结构性限制与危机。'; }
	else { tone = '平'; toneText = '木土均无本质尊贵 → 吉凶相参,主导力量看落宫与所受相位。'; }
	return {
		sep: +sep.toFixed(2), signKey, signCn: meta.cn || signKey,
		element: meta.element || '', climate: meta.element ? ELEMENT_CLIMATE[meta.element] : '',
		stronger, strongerCn: stronger ? (PLANET_CN[stronger] || stronger) : '木土均势',
		tone, toneText,
	};
}

// 便捷：直接传 chart（Result）。
export function describeMundaneFromChart(chart){
	try{ return describeMundaneChart(buildFacts(chart)); }catch(e){ return []; }
}

// [G11] 四轴特殊点(赤道上升点 EastPoint / 天顶点 Vertex / 反天顶 Antivertex)。
// 公式照录古籍坐标篇:λ_EQ = atan2(cos RAMC, −sin RAMC·cos ε)(即 RA=RAMC+90° 的黄道点);
// Vertex = 以余纬(90−|φ|)代入 ASC 公式、取西半球交点;Antivertex = Vertex+180°。
// RAMC 由 λ_MC 反推(黄纬 0:RA = atan2(sin λ·cos ε, cos λ));ε 取平均黄赤交角 23.4367°
// (世纪变率 <0.02°,对 0.1° 级显示足够;卡内注明)。纬度自 params.lat('39N54' 形)解析。
const MEAN_OBLIQUITY = 23.4367;
function parseLatText(latText){
	const m = String(latText || '').trim().match(/^(\d+(?:\.\d+)?)\s*([NnSs])\s*(\d+(?:\.\d+)?)?/);
	if(!m){ const f = parseFloat(latText); return Number.isFinite(f) ? f : null; }
	const deg = parseFloat(m[1]) + (m[3] ? parseFloat(m[3]) / 60 : 0);
	return /[Ss]/.test(m[2]) ? -deg : deg;
}
const D2R = Math.PI / 180;
const norm360 = (x) => (((x % 360) + 360) % 360);
export function describeSpecialAxes(facts){
	if(!facts || !facts.meta || facts.meta.mcLon == null){ return null; }
	const mcLon = facts.meta.mcLon;
	const ascLon = facts.meta.ascLon;
	const latText = facts.result && facts.result.params ? facts.result.params.lat : null;
	const phi = parseLatText(latText);
	const eps = MEAN_OBLIQUITY * D2R;
	// RAMC:MC 黄经 → 赤经(黄纬 0)。
	const lm = mcLon * D2R;
	const ramc = Math.atan2(Math.sin(lm) * Math.cos(eps), Math.cos(lm));
	// EastPoint(赤道上升点)。
	const eastPoint = norm360(Math.atan2(Math.cos(ramc), -Math.sin(ramc) * Math.cos(eps)) / D2R);
	let vertex = null;
	if(phi != null && Math.abs(phi) < 89.9){
		const coLat = (90 - Math.abs(phi)) * D2R;   // 余纬代入 ASC 公式
		const r2 = ramc + Math.PI;                  // 取西半球交点(RAMC+180 支)
		let v = norm360(Math.atan2(Math.cos(r2), -(Math.sin(r2) * Math.cos(eps) + Math.tan(coLat) * Math.sin(eps))) / D2R);
		// 西半球守卫:Vertex 必落上升点起的西半圆((λ−ASC)∈(180,360));落东侧则取对点。
		if(ascLon != null && norm360(v - ascLon) < 180){ v = norm360(v + 180); }
		vertex = v;
	}
	return {
		eastPoint,
		vertex,
		antivertex: vertex != null ? norm360(vertex + 180) : null,
		note: '赤道上升点=纬度 0° 处的上升(轴宫制第 1 宫头);天顶点取西半球交点,与人事被动遭逢相关。黄赤交角按平均值近似。',
	};
}

export default { describeMundaneChart, mundaneConjunctionIndicator, describeEclipse, describeEclipseAfflictions, describeMundaneWeather, describeMundaneSyzygy, describeMundaneFromChart, describeIngressSkeleton, describeMundaneVictor, buildMundaneStarPoints, mundaneFixedStarHits, mundaneStarLon, MUNDANE_HOUSE_MEANINGS, MUNDANE_HOUSE_FULL, PLANET_IN_MUNDANE_HOUSE, PLANET_SIGNIFICATION, PLANET_MUNDANE_FULL, SIGN_MUNDANE_TEMPER, MUNDANE_FIXED_STARS, MUNDANE_ASPECT_FRAME, ECLIPSE_ELEMENT, ECLIPSE_DECAN };
