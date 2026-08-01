// tongshuData.js — 通书择日跨法共享数据（用事术语库 + 事项分类枚举）。
//
// 术语/事项名皆闭合词表：一律手写简体（繁简规程①，不机器转），已逐字避开
// 乾/干（此表无八卦名）、徵/征 等一简对多繁雷区。释义忠于古籍择日通行义，概括从简。
// 各法专属大表（董公全量断语 / 玄空 60 甲子配卦 / 乌兔九星 / 奇门叠数 / 三垣吉曜）
// 就近置于各自 tongshu/<法>.js 内，便于算法与数据同处校核。

// —— 用事术语库（6 类）——
export const TONGSHU_TERMS = {
	婚姻: [
		{ name: '冠笄', desc: '男弱冠女及笄，青少年成年礼（约十六岁）。' },
		{ name: '问名', desc: '婚议仪式，男女各取年庚供于神案，过三日无事再议。' },
		{ name: '订盟', desc: '俗称订婚、文定、小聘、过订。' },
		{ name: '纳采', desc: '收授聘金，俗称完聘、大聘、大定。' },
		{ name: '裁衣', desc: '裁制新娘新衣，或指做寿衣。' },
		{ name: '安床', desc: '新婚安置新床；久不受胎或事业不顺亦重新安床。' },
		{ name: '嫁娶', desc: '举行结婚典礼迎亲之日。' },
		{ name: '纳婿', desc: '同嫁娶，男方入赘女家为婿。' },
		{ name: '归宁', desc: '新婚后新娘与新郎首次回娘家。' },
		{ name: '求嗣', desc: '向神明祈求后嗣。' },
		{ name: '合帐', desc: '制作蚊帐，今指安置窗帘。' },
		{ name: '进人口', desc: '收纳养子女，或认干儿女。' },
	],
	营建: [
		{ name: '移徙', desc: '迁移住所，俗称搬家。' },
		{ name: '入宅', desc: '迁入新居。' },
		{ name: '安香', desc: '安土地公或祖先神位。' },
		{ name: '开山', desc: '动土为开山，谓兴造。' },
		{ name: '动土', desc: '阳宅、工程、建筑开始动工。' },
		{ name: '安门', desc: '新建房屋安设大门、装设门户。' },
		{ name: '上梁', desc: '装上建筑屋顶大梁，或指屋顶灌浆。' },
		{ name: '修造', desc: '阳宅改建修缮，或整修仓库。' },
		{ name: '破屋', desc: '破土坏垣拆卸，拆除房屋围墙。' },
		{ name: '补垣', desc: '塞穴填坑覆井，堵塞洞穴蚁穴。' },
		{ name: '平整', desc: '适宜道涂，铺修马路。' },
		{ name: '破土', desc: '阴宅埋葬破土（与阳宅动土不同）。' },
		{ name: '立向', desc: '定向为立向，谓兴造。' },
		{ name: '开池', desc: '开凿水池鱼池。' },
		{ name: '开厕', desc: '建厕所开工。' },
		{ name: '启钻', desc: '拾骨骸洗骨。' },
		{ name: '竖柱', desc: '架马起工架，指建筑鹰架。' },
		{ name: '掘井', desc: '开渠筑阴沟、开鱼池、开凿水井池塘。' },
	],
	工商: [
		{ name: '开市', desc: '新公司行号开业开幕，年初开张开业。' },
		{ name: '立契', desc: '建立买卖契约。' },
		{ name: '交易', desc: '买卖之事，约定买卖。' },
		{ name: '挂匾', desc: '店铺行号悬挂名号招牌匾额。' },
		{ name: '立券', desc: '订立各种契约互相买卖。' },
		{ name: '纳财', desc: '五谷入仓，置货、收租、收帐、借款购屋。' },
		{ name: '开仓', desc: '商贾出货销货、放债贷款。' },
		{ name: '造车器', desc: '制造陆路交通工具（适交新车）。' },
		{ name: '安机械', desc: '安装机械及试车，安纺车。' },
		{ name: '造舟船', desc: '制造水路交通工具（适交新船）。' },
		{ name: '经络', desc: '织布、收蚕、安纺车、机器。' },
		{ name: '酝酿', desc: '割蜜、造曲酿酒、养蜂取蜜。' },
	],
	祭祀: [
		{ name: '祭祀', desc: '祠堂拜祭祖先或庙宇祭拜神明。' },
		{ name: '祈福', desc: '祈求神明降福、酬神谢神、设醮还愿。' },
		{ name: '开光', desc: '佛像塑成后安座前点眼入神之仪式。' },
		{ name: '沐浴', desc: '祈福设醮或还愿时清洁身体。' },
		{ name: '斋醮', desc: '庙宇建醮前的斋戒仪式。' },
		{ name: '设醮', desc: '建立道场祈求平安祈福（三醮五醮之分）。' },
		{ name: '酬神', desc: '还愿，答谢神恩。' },
		{ name: '塑绘', desc: '寺庙雕刻神像、描绘神像。' },
		{ name: '普渡', desc: '祭祀超渡阴界好兄弟。' },
		{ name: '造庙', desc: '建造寺、庙、宫、观、堂。' },
		{ name: '出火', desc: '移动神明之位。' },
	],
	生活: [
		{ name: '会亲友', desc: '会友、宴请亲友、访亲友。' },
		{ name: '求医', desc: '看病、治疗疾病及动手术。' },
		{ name: '出行', desc: '远行、旅行、观光游览、业务考察。' },
		{ name: '赴任', desc: '就任之事。' },
		{ name: '剃头', desc: '初生儿女首次理发（剃胎头），或新娘挽面。' },
		{ name: '迁徙', desc: '搬家迁移住所。' },
		{ name: '分居', desc: '大家庭分家，另起炉灶。' },
		{ name: '习艺', desc: '学习特殊技艺，行拜师礼。' },
		{ name: '栽种', desc: '栽种植物或接枝。' },
		{ name: '牧养', desc: '牧养动物。' },
		{ name: '纳畜', desc: '买入家畜、家禽、宠物。' },
		{ name: '捕捉', desc: '扑灭家中蚂蚁或农作物害虫。' },
		{ name: '放水', desc: '清理池塘水族后将水注入蓄池。' },
	],
	丧葬: [
		{ name: '修坟', desc: '修理坟墓。' },
		{ name: '启钻', desc: '洗骨，俗谓拾金（拣骨）。' },
		{ name: '安葬', desc: '埋葬棺木或将骨缶放入墓穴的进金仪式。' },
		{ name: '行丧', desc: '到丧家慰问遗族，丧葬之事总称。' },
		{ name: '立碑', desc: '竖立墓碑或纪念碑。' },
		{ name: '谢土', desc: '新建寺庙大厦坟墓完工后所举行的祭祀。' },
		{ name: '成服', desc: '穿上丧服。' },
		{ name: '除服', desc: '脱下除去丧服。' },
		{ name: '移柩', desc: '行葬仪时将棺木移出屋外。' },
		{ name: '入殓', desc: '将尸体放入棺材、盖棺。' },
		{ name: '解除', desc: '扫舍，冲洗宅舍解除灾厄。' },
		{ name: '开生坟', desc: '人未死先找地作坟墓。' },
		{ name: '合寿木', desc: '人未死先作棺木。' },
	],
};

export const TONGSHU_TERM_CATEGORIES = ['婚姻', '营建', '工商', '祭祀', '生活', '丧葬'];

// 术语名 → 类别（反查，供 UI/AI 归类）。
export const TERM_TO_CATEGORY = (()=>{
	const m = {};
	TONGSHU_TERM_CATEGORIES.forEach((cat)=>{
		(TONGSHU_TERMS[cat] || []).forEach((t)=>{ m[t.name] = cat; });
	});
	return m;
})();

// —— 事项分类法（吉日榜 / 日子馆共用）：每类映射到一组 lunar「宜」关键词 ——
// yiKeys 为 lunar getDayYi() 词表中的实际用词（探针已证：嫁娶/纳采/入宅/移徙/开市/动土/上梁/竖柱/安床/安葬/祭祀/祈福/出行/交易/立券 皆在）。
export const EVENT_CATEGORIES = [
	{ key: 'marriage', label: '婚嫁', yiKeys: ['嫁娶', '纳采', '订婚', '订盟', '安床'], group: '婚姻' },
	{ key: 'start', label: '起基', yiKeys: ['开市', '动土', '上梁', '竖柱', '起基', '修造'], group: '营建' },
	{ key: 'move', label: '新居入伙', yiKeys: ['入宅', '移徙', '安香', '进人口'], group: '营建' },
	{ key: 'bed', label: '安床', yiKeys: ['安床'], group: '婚姻' },
	{ key: 'trade', label: '交易立券', yiKeys: ['交易', '立券', '纳财', '开市', '挂匾'], group: '工商' },
	{ key: 'travel', label: '出行', yiKeys: ['出行', '赴任'], group: '生活' },
	{ key: 'pray', label: '祭祀祈福', yiKeys: ['祭祀', '祈福', '开光', '斋醮'], group: '祭祀' },
	{ key: 'burial', label: '安葬', yiKeys: ['安葬', '破土', '启钻', '立碑'], group: '丧葬', sensitive: true },
];

export const EVENT_KEY_TO_CATEGORY = (()=>{
	const m = {};
	EVENT_CATEGORIES.forEach((c)=>{ m[c.key] = c; });
	return m;
})();

// 关键凶煞（吉日榜/日子馆硬扣分/淘汰用；名取通书通行）。
export const KEY_XIONG_SHA = ['月破', '受死', '四废', '四离', '四绝', '往亡', '岁破', '天贼', '大耗', '重丧', '五墓'];
// 关键吉神（加分用）。
export const KEY_JI_SHEN = ['天德', '月德', '天德合', '月德合', '天愿', '天赦', '天喜', '三合', '六合', '天医', '福生', '天贵'];

// 董公「用事」真值驱动：以当日通书宜/忌（lunar 权威表，含建除+神煞择净）判该用事宜/忌。
// 多数用事在 lunar 宜忌表内有直名；少数用异名 → 下表校准同义映射（皆经 lunar 2026 全年词表核对）。
// 🔴 同义 = 真同名/真异名,绝不含「相关但不同」的事项:
//   曾把 破土/成服/除服 当安葬同义 → 通书明写「忌安葬」的日子(全表 135/1800 组合)
//   被判成「宜安葬」;动土/开山把阳宅动土与阴宅破土混同(本文件上方自注二者不同)。
//   启攢=繁体死值(表内实名「启钻」);开池须补 lunar 组合词「开井开池」(忌段确有 4 条)。
export const YONGSHI_YIJI_SYN = {
	平整: ['平治道涂', '修饰垣墙'],
	立向: ['竖柱', '上梁', '修造'],
	开山: ['动土', '起基'],
	开池: ['开池', '开渠', '开井开池'],
	启攒: ['启钻'],
	破屋: ['破屋', '坏垣'],
	补垣: ['补垣', '塞穴', '修饰垣墙'],
	动土: ['动土'],
	安葬: ['安葬'],
	// 与既有条目同义的重复术语(此前无映射 → 董公用事栏对其恒「无明确宜忌」)
	立契: ['立券'],
	造舟船: ['造船'],
	设醮: ['斋醮', '齐醮'],
	迁徙: ['移徙'],
};

// day 需带 { yi:[], ji:[] }（buildHuangliDay 产出）。返回 { level:'yi'|'ji'|'neutral', hits:[命中词] }。
export function yongshiVerdict(day, event) {
	const ev = `${event || ''}`.trim();
	if (!ev || !day) { return { level: 'neutral', hits: [] }; }
	const keys = YONGSHI_YIJI_SYN[ev] || [ev];
	const yi = Array.isArray(day.yi) ? day.yi : [];
	const ji = Array.isArray(day.ji) ? day.ji : [];
	const yiHit = keys.filter((k)=> yi.includes(k));
	const jiHit = keys.filter((k)=> ji.includes(k));
	// 宜忌同时命中 → 判冲突(凶优先):曾宜先命中即定,同义词组内一宜一忌时
	// 会把「忌」直接吃掉,与同页黄历卡的忌栏自相矛盾。
	if (yiHit.length && jiHit.length) { return { level: 'conflict', hits: yiHit.concat(jiHit) }; }
	if (yiHit.length) { return { level: 'yi', hits: yiHit }; }
	if (jiHit.length) { return { level: 'ji', hits: jiHit }; }
	return { level: 'neutral', hits: [] };
}

export default TONGSHU_TERMS;
