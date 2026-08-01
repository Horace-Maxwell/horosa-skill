// divination/data/decanImages.js
// 十分度/面的人物意象（用于盗贼外貌，看上升所落面）。
// 来源：Sahl《论问题》§7.22 / 补充清单 A.1（36 条完整数据，直接录入）。
// 结构：[面1(0–10°), 面2(10–20°), 面3(20–30°)]
export const DECAN_IMAGES = {
	aries: ['穿白袍黑人', '穿红衣女人', '苍白红发男'],
	taurus: ['间谍/裸男', '拿钥匙裸男', '拿蛇和箭男'],
	gemini: ['拿棍男与仆人', '拿管子男与佝偻者', '寻武器男'],
	cancer: ['衣着考究男与少女', '戴花环非处女与处女', '一男一女'],
	leo: ['狮子与破衣男', '举手男与戴冠男', '拿鞭青年与丑陋悲伤男'],
	virgo: ['好女孩', '穿皮衣黑人与戴冠男', '失聪白女'],
	libra: ['拿管子愤怒男', '两个愤怒仆人', '拿弓男与裸男'],
	scorpio: ['美貌女子', '裸男女', '弯腰男'],
	sagittarius: ['破衣男', '穿衣女', '金肤色男'],
	capricorn: ['女人与黑人', '两女人', '精明黑女'],
	aquarius: ['男人', '长胡子男', '愤怒黑人'],
	pisces: ['衣着光鲜男', '美貌女', '裸男'],
};

// ── 36 面形像全表(Agrippa《三论神秘哲学》II.37 / Picatrix II 卷,公开古籍;择日「尊贵强弱」页消费)──
// 每座三面:{ agrippa, picatrix, meaning }。射手第3面 Picatrix 逐字未经核实 → 只录 Agrippa 形并注待核。
export const DECAN_IMAGES_AGRIPPA = {
	aries: [
		{ agrippa: '黑人立、白衣束带、身巨赤目、如怒者', picatrix: '躁动黑人、巨身赤目、持斧、白布束身', meaning: '胆识、刚毅、高傲、无耻' },
		{ agrippa: '女子外披红衣、内白衣垂足', picatrix: '绿衣女、缺一腿', meaning: '高贵、王国之高、统御之大' },
		{ agrippa: '躁动男子持金镯、红衣、如怒', picatrix: '同式——持金镯红衣、欲行善而不能', meaning: '机敏而求善不得' },
	],
	taurus: [
		{ agrippa: '裸男为弓手/收割者/农夫,出而播种耕建', picatrix: '卷发女、伴一火衣之子', meaning: '农耕、营建、几何、播种' },
		{ agrippa: '裸男持钥', picatrix: '驼身男、指如牛蹄、披破麻布', meaning: '权力、贵显、统御万民' },
		{ agrippa: '男手持蛇与镖', picatrix: '赤色男、露白大齿、象身长腿、伴马犬犊', meaning: '必然与利益、亦贫苦奴役' },
	],
	gemini: [
		{ agrippa: '男持杖、似侍他人', picatrix: '擅针黹之美女、伴二犊二马', meaning: '智慧、数、无利之艺' },
		{ agrippa: '男持笛、另一俯身掘地', picatrix: '鹫面男、头巾铅甲铁盔丝冠、弓矢', meaning: '不名誉之灵巧、苦寻' },
		{ agrippa: '男寻械、愚者右手持鸟左手持笛', picatrix: '着甲男、持弓矢箭袋', meaning: '健忘、怒、鲁莽、无益之言' },
	],
	cancer: [
		{ agrippa: '少女盛装戴冠', picatrix: '曲指曲头男、马身白足、身覆无花果叶', meaning: '感官敏锐、机智、人之爱' },
		{ agrippa: '美装男(或男女对坐弈戏)', picatrix: '求欢歌唱之美女、绿桃金娘冠、持睡莲茎', meaning: '财富、欢乐、女人之爱' },
		{ agrippa: '猎人持矛号角、率犬而猎', picatrix: '男持蛇、龟足、戴金饰', meaning: '纷争、追逐、以武取物' },
	],
	leo: [
		{ agrippa: '男骑狮', picatrix: '污衣男、伴望北之熊犬状骑主', meaning: '胆勇、暴烈、残忍、劳苦' },
		{ agrippa: '戴冠之男举手、右手出鞘剑左手盾', picatrix: '白桃金娘冠男、持箭、骑马', meaning: '隐秘之争、不为人知之胜' },
		{ agrippa: '持鞭青年、与极忧愁恶相之男', picatrix: '黑污老人、口含果肉、手持铜壶', meaning: '爱与社交、为息争而失己权' },
	],
	virgo: [
		{ agrippa: '善良少女与播种之男', picatrix: '裹麻布披旧袍之少女、持石榴', meaning: '敛财、调饮食、耕播' },
		{ agrippa: '披皮黑男、与蓬发持袋之男', picatrix: '肤色佳男、着皮革', meaning: '获利、聚财、贪婪' },
		{ agrippa: '白衣聋女(或老人倚杖)', picatrix: '倚杖老人,或聋哑白女', meaning: '虚弱、疾病、肢残' },
	],
	libra: [
		{ agrippa: '怒男持笛、与读书之男', picatrix: '右手持矛、左手持倒挂之鸟', meaning: '扶弱抗暴、正义善判' },
		{ agrippa: '二男狂怒、与着美衣坐椅之男', picatrix: '婚宴上之黑男、伴一嬉戏者', meaning: '对恶之愤、生活安足' },
		{ agrippa: '呕吐之男(或聋老倚杖)', picatrix: '男骑驴、前有狼', meaning: '祛恶、亦虚弱毁损' },
	],
	scorpio: [
		{ agrippa: '容貌端好之女、二男击之', picatrix: '一手持矛、一手提断首之男', meaning: '美貌,亦争斗奸诈毁谤' },
		{ agrippa: '裸男裸女、与坐地男、前有二犬相咬', picatrix: '骑驼男、持蝎', meaning: '无耻、欺诈、人间争斗' },
		{ agrippa: '跪伏之男、女以杖击之', picatrix: '一马与一兔', meaning: '醉酒、淫乱、怒、暴' },
	],
	sagittarius: [
		{ agrippa: '着锁子甲、持裸剑之男', picatrix: '着甲三人、持剑弓', meaning: '胆识、自由、骑士德' },
		{ agrippa: '哭泣覆衣之女', picatrix: '牵牛之男、前有熊与猿', meaning: '悲伤、恐惧、阻碍' },
		{ agrippa: '金色之男(或持杖嬉戏之懒人)', picatrix: null, meaning: '任己意、固执、争斗辩论（Picatrix 逐字待核）' },
	],
	capricorn: [
		{ agrippa: '女子、与负满袋之男', picatrix: '右手持芦、左手持戴胜鸟之男', meaning: '欣然出行、得失参半、行善' },
		{ agrippa: '二女、与望飞鸟之男', picatrix: '前有一猿之男', meaning: '求不可成之事、寻不可知之知' },
		{ agrippa: '身洁慧巧之女、与桌上聚钱之银钱商', picatrix: '开合书卷之男、前有鱼尾', meaning: '审慎治事、贪财吝啬' },
	],
	aquarius: [
		{ agrippa: '审慎之男、与纺线之女', picatrix: '携孔雀之无首男', meaning: '为利之思与劳、贫与卑' },
		{ agrippa: '长须男', picatrix: '似王之傲男、自纵轻视所见', meaning: '理解、温和、谦逊、善仪' },
		{ agrippa: '黑而怒之男', picatrix: '断首之男', meaning: '傲慢无礼、恶意' },
	],
	pisces: [
		{ agrippa: '肩负重物、衣着齐整之男', picatrix: '双身男、双手作致意状', meaning: '旅行、迁徙、衣食之虑' },
		{ agrippa: '容貌姣好、装饰华美之女', picatrix: '倒立之男、持空盘', meaning: '欲图高远、厚赏强志' },
		{ agrippa: '裸男(或少年)、近一花冠美少女', picatrix: '裸男裸女与一驴', meaning: '安逸、闲散、欢愉、淫乱' },
	],
};

export function agrippaFaceImage(signId, faceIndex){
	const arr = DECAN_IMAGES_AGRIPPA[signId];
	return arr ? arr[Math.max(0, Math.min(2, faceIndex))] || null : null;
}

export function decanImageAt(signId, deg){
	const d = ((deg % 30) + 30) % 30;
	const idx = Math.min(2, Math.floor(d / 10));
	return (DECAN_IMAGES[signId] || [])[idx] || null;
}

export default DECAN_IMAGES;
