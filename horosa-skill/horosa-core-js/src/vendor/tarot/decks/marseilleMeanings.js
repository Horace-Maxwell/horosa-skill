// 「数字度」第三牌义体系(马赛传统:小牌不读场景图,按十度周期×四中心推演;原创中文转述)。
// 四花色↔四中心:宝剑=智力 · 圣杯=情感 · 权杖=性/创造 · 钱币=物质/身体;奇数主动、偶数接纳;
// 两个五度系列(1-5 下半周期/6-10 上半周期);每度自带「危险」(该度的失衡形态)。
// 宫廷四阶(此派等级序 侍从→王后→国王→骑士,骑士最高=携能量赴新层级的使者)。

// 十度通表:义 + 危险。
import { isTrumpArcana } from '../engine/arcana.js'; // [QA-9] 王牌判据单一真值源(零依赖叶子,不成环)
export const DEGREE_CORE = {
	1: { label: '潜能', text: '全部潜能与开始——未显化的整体', danger: '滞留于纸上谈兵,始终不落地' },
	2: { label: '积蓄', text: '积蓄、酝酿、预备——备而未发', danger: '按兵太久,积而不动则腐' },
	3: { label: '初绽', text: '无经验的初次迸发——带着热情的第一步', danger: '初尝失手便灰心乱作' },
	4: { label: '稳定', text: '稳定、安全、初步掌握', danger: '安稳成茧,停滞不再进化' },
	5: { label: '过渡', text: '过渡之桥——新理想、新视角与诱惑并至', danger: '言行不一,新旧两头落空' },
	6: { label: '愉悦', text: '愉悦与美——做所爱之事', danger: '自恋成环,乐而忘进' },
	7: { label: '行动', text: '在世界中的最高行动度', danger: '能量误用,行动转为破坏' },
	8: { label: '圆满', text: '接纳性的圆满、完美与平衡', danger: '圆满僵化,或盛极生乱' },
	9: { label: '危机', text: '危机与智慧——为新生让位', danger: '陷于永久危机,不肯翻页' },
	10: { label: '终始', text: '周期终结、整体达成——新周期前夜', danger: '拒绝重新做初学者' },
};

// 分花色数字度(四中心口径)。DEGREE_BY_SUIT[suit][1..10]。
export const DEGREE_BY_SUIT = {
	swords: {
		1: '智力的大潜能——一切想法皆有可能', 2: '思想在沉默中积蓄', 3: '理想主义的初绽', 4: '观念趋于稳定成形',
		5: '思想迎来新理想与新诱惑', 6: '思考与言说之乐', 7: '思想付诸世间行动', 8: '心智的接纳性圆满',
		9: '思想的危机——放下既有的确定', 10: '心智周期完结,向新的思维方式敞开',
	},
	cups: {
		1: '爱的全部潜能', 2: '关系在酝酿之中', 3: '情感的初次绽放', 4: '情感稳定(亦须防封闭)',
		5: '心的过渡——新的情感理想', 6: '爱之愉悦', 7: '爱推向世界的行动', 8: '情感的丰盈圆满',
		9: '情感危机——为新的爱让位', 10: '情感周期圆成,转向超越',
	},
	wands: {
		1: '原始生命力与创造的潜能', 2: '能量在体内积蓄', 3: '创造力的初次爆发', 4: '创造节律趋稳',
		5: '欲望的过渡——新的创造理想', 6: '创造之乐', 7: '全然投向他者的创造行动', 8: '创造能量凝聚至圆满',
		9: '能量的危机与转化', 10: '创造周期完结,升入新层',
	},
	pentacles: {
		1: '物质与身体的种子', 2: '交换的循环开始流动', 3: '物质初步生长', 4: '占有与根基稳固',
		5: '身体与物质的新理想', 6: '物质层面的享受', 7: '劳作结出行动之果', 8: '物质的繁荣圆满',
		9: '物质的收束与临产', 10: '富足的整体达成——周期完成',
	},
};

// 宫廷四阶(此派):侍从=接纳/学徒 · 王后=内化的掌握 · 国王=外化的施行 · 骑士=离位赴新层的使者(最高)。
export const COURT_STAGE_ORDER = ['page', 'queen', 'king', 'knight'];
export const COURT_STAGE_LABEL = { page: '学徒(蓄而待学)', queen: '内化掌握', king: '外化施行', knight: '使者(赴新层级)' };
export const COURT_STAGE = {
	swords: { page: '思想的学徒——先观察,不急断言', queen: '锐利而防卫的清醒心智', king: '以智力立权威、施裁断', knight: '为理念出征的使者' },
	cups: { page: '羞怯的情感学徒', queen: '内藏情感的财富(持而未启)', king: '向外奉献情感与关怀', knight: '携敞开之杯的爱之求索' },
	wands: { page: '创造能量的学徒——蓄势待学', queen: '认下自身的创造之力', king: '把创造力施行于世界', knight: '携火赴新层级的使者' },
	pentacles: { page: '物质经营的学徒——先看再接手', queen: '物质掌握内化——安家蓄积', king: '物质掌握外化——经营与担纲', knight: '凝视成果、携其奔赴新周期' },
};

// 大牌关键词(马赛口径,原创转录;与 Waite 义并行的第三口径)。键=sid。
export const MAJOR_KW_TDM = {
	the_fool: '自由、巨大能量、行旅、寻觅、无定之力',
	the_magician: '开始与选择、机敏、青春、潜能落地',
	high_priestess: '积蓄、圣所、耐心、孕而未发、母系智慧',
	the_empress: '迸发、创造力、诱惑、丰盛、青春期之力',
	the_emperor: '稳定、支撑、治理、物质秩序、父性',
	the_hierophant: '新理想、沟通两界、教导、中介、榜样',
	the_lovers: '愉悦、心之所向、结合或抉择、社交生活',
	the_chariot: '世间行动、征旅、播种拓殖、意气风发',
	strength: '兽性能量的觉醒、开口、创造之始、驯化',
	the_hermit: '危机中的智慧、独行、放手、照亮、承受',
	wheel_of_fortune: '周期终始、谜与解、待外力摇柄、无常',
	justice: '称量、平衡、完满无增减、裁汰、准许与禁止',
	hanged_man: '不选择、自献、悬止、孕育、换位',
	death: '拆毁与革命、转化、清扫、迅疾前行(无名之牌)',
	temperance: '护佑、调和、循环、疗愈、度量',
	the_devil: '深层能量的宝藏、诱惑、契约、创造潜流',
	the_tower: '欢庆的破出、开启、迁居、神殿落成',
	the_star: '找到位置、灌溉世界、赤诚给予、机运',
	the_moon: '接纳之满、直觉、梦境、母性之光、诗',
	the_sun: '新的建构、兄弟情、辐射之爱、成功',
	judgement: '不可抗的召唤、新意识诞生、家之团聚',
	the_world: '大圆满、总实现、舞于世界之心',
};

// 取一张牌的数字度义(马赛口径显示串)。大牌=马赛关键词;数字=度义(附危险);宫廷=四阶义。无则 null。
export function degreesMeaningOf(card){
	if(!card){ return null; }
	if(isTrumpArcana(card.arcana)){ return MAJOR_KW_TDM[card.sid] || null; }
	if(card.court){
		const st = COURT_STAGE[card.suit] && COURT_STAGE[card.suit][card.court];
		if(!st){ return null; }
		return `${st}(${COURT_STAGE_LABEL[card.court]})`;
	}
	if(card.number >= 1 && card.number <= 10){
		const d = DEGREE_BY_SUIT[card.suit] && DEGREE_BY_SUIT[card.suit][card.number];
		const core = DEGREE_CORE[card.number];
		if(!d || !core){ return null; }
		return `第${card.number}度·${d}(危险:${core.danger})`;
	}
	return null;
}

// 马赛编号(此派原生框架:正义=VIII/力量=XI,与 RWS 对调;其余同号)。度/十进对/和21 皆按此运算。
export function marseilleNumber(card){
	// [QA-9] 认 *_trump:此前写死 'major',维斯康蒂/米兰凯特的王牌走不到下面的换号,
	// 力量↔正义的马赛换号对这两副静默失效(而马赛对读整套都建立在此编号上)。
	if(!card || !isTrumpArcana(card.arcana)){ return card ? card.number : null; }
	if(card.sid === 'strength'){ return 11; }
	if(card.sid === 'justice'){ return 8; }
	return card.number;
}

// 牌的「度」值(度间关系引擎用):数字牌=面值;大牌按马赛编号 1..10↔11..20 同度(n>10 取 n-10),0/21 在周期外;宫廷插位不入度。
export function degreeOf(card){
	if(!card){ return null; }
	if(isTrumpArcana(card.arcana)){ // [QA-9] 同上
		const n = marseilleNumber(card);
		if(n >= 1 && n <= 10){ return n; }
		if(n >= 11 && n <= 20){ return n - 10; }
		return null; // 愚人/世界在十度周期之外
	}
	if(card.court){ return null; }
	if(card.number >= 1 && card.number <= 10){ return card.number; }
	return null;
}
