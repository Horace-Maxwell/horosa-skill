// divination/data/egyptianData.js
// 埃及占星数据底座(纯数据,零副作用)。供占星本命「埃及」页派生使用。
// 内容:36 旬名录(两套旬序锚定 + 多套命名 + 塔罗双射 + 含义)、行星/恒星埃及名、
//       民用历(三季十二月名 + 五闰余神诞)、对角星钟(夜时授时表)、赫尔墨斯护符 melothesia、
//       希腊字母数值 isopsephy、Petosiris/Democritus 数字占分区、埃及吉凶日、占星地理。
// 凡转写存疑或抄本残/有歧义者一律标注「待核」,绝不臆造。
// 术语:旬=每 10° 一段;迦勒底序由慢到快 ♄♃♂☉♀☿☽;面主=旬星行星主管。

/* ============================================================
 * 通用:旬序锚定算法(E1 / E2.5)
 * ============================================================ */

export function norm360(x){ return ((x % 360) + 360) % 360; }

// 希腊化回归旬序(1..36, 白羊I=1) —— 占星默认锚定
export function greekDecan(lon){ return Math.floor(norm360(lon) / 10) + 1; }

// 古代恒星旬序(1..36, 天狼 Sothis=1, 对齐 0°巨蟹=90°) —— 理念性换算,展示原位
export function ancientDecan(lon){ return ((Math.floor(norm360(lon - 90) / 10)) % 36 + 36) % 36 + 1; }

/* ============================================================
 * E1 / E5 / E9:36 旬完整名录(跨流派对照 + 塔罗双射 + 含义)
 * ------------------------------------------------------------
 * 字段:
 *   greek      希腊化旬序(1..36, 白羊I=1)
 *   signId     星座 id  / decanInSign 座内第几旬(1/2/3) / range 度区间(回归)
 *   ancient    古代恒星序(岁差原位;天狼=1,对齐 0°巨蟹)
 *   egyptName  古埃及名(Budge 转写)
 *   copticGreek 科普特-希腊名
 *   hermesName 希腊赫尔墨斯名(亦即护符秘名,见 E6)
 *   star       星认定/识别(多数旬与现代星名对应未定,标「待核」)
 *   face       迦勒底面主(行星 id)
 *   tarotSuit/tarotPip/tarotTitle/tarotMeaning  旬星塔罗(小阿卡那)双射与含义
 * 数据系逐行转录;旬序绝对锚定白羊I=1→双鱼III=36。
 * ============================================================ */

export const EGYPT_DECANS = [
	{ greek: 1,  signId: 'aries',       decanInSign: 1, range: '0–10°',    ancient: 28, egyptName: 'Khent-kheru',            copticGreek: 'Xont-har',     hermesName: 'Chenlachori', star: '待核', face: 'Mars',    tarotSuit: 'wands',  tarotPip: 2,  tarotTitle: '支配 Dominion',      tarotMeaning: '开创、意志、掌控' },
	{ greek: 2,  signId: 'aries',       decanInSign: 2, range: '10–20°',   ancient: 29, egyptName: 'Qeṭ',                    copticGreek: 'Xont-χre',     hermesName: 'Chontaret',   star: '待核', face: 'Sun',     tarotSuit: 'wands',  tarotPip: 3,  tarotTitle: '既得之力 Virtue',    tarotMeaning: '远见、合作有成' },
	{ greek: 3,  signId: 'aries',       decanInSign: 3, range: '20–30°',   ancient: 30, egyptName: 'Sasaqeṭ',                copticGreek: 'Si-ket',       hermesName: 'Siket',       star: '待核', face: 'Venus',   tarotSuit: 'wands',  tarotPip: 4,  tarotTitle: '完成 Completion',    tarotMeaning: '和谐、安顿、阶段达成' },
	{ greek: 4,  signId: 'taurus',      decanInSign: 1, range: '30–40°',   ancient: 31, egyptName: 'Ārt',                    copticGreek: 'Xau',          hermesName: 'Soou',        star: '待核', face: 'Mercury', tarotSuit: 'coins',  tarotPip: 5,  tarotTitle: '物质忧虑 Worry',     tarotMeaning: '匮乏、不安、被排斥' },
	{ greek: 5,  signId: 'taurus',      decanInSign: 2, range: '40–50°',   ancient: 32, egyptName: 'Khau',                   copticGreek: 'Arat',         hermesName: 'Aron',        star: '待核', face: 'Moon',    tarotSuit: 'coins',  tarotPip: 6,  tarotTitle: '物质成功 Success',   tarotMeaning: '给予/获得、流通' },
	{ greek: 6,  signId: 'taurus',      decanInSign: 3, range: '50–60°',   ancient: 33, egyptName: 'Remen-ḥeru-an-Saḥ',      copticGreek: 'Remen-hare',   hermesName: 'Rhomenos',    star: '猎户 Saḥ 之肩臂', face: 'Saturn', tarotSuit: 'coins', tarotPip: 7, tarotTitle: '失败 Failure',       tarotMeaning: '停滞、怀疑、收成未达' },
	{ greek: 7,  signId: 'gemini',      decanInSign: 1, range: '60–70°',   ancient: 34, egyptName: 'Mestcher-Saḥ',           copticGreek: 'Θosalk',       hermesName: 'Xocha',       star: '猎户 Saḥ 相关', face: 'Jupiter', tarotSuit: 'swords', tarotPip: 8, tarotTitle: '受阻 Interference',  tarotMeaning: '束缚、进退失据' },
	{ greek: 8,  signId: 'gemini',      decanInSign: 2, range: '70–80°',   ancient: 35, egyptName: 'Remen-kher-Saḥ',         copticGreek: 'Uaret',        hermesName: 'Ouari',       star: '猎户 Saḥ 之下肩', face: 'Mars', tarotSuit: 'swords', tarotPip: 9, tarotTitle: '残酷 Cruelty',       tarotMeaning: '焦虑、噩梦、苦楚' },
	{ greek: 9,  signId: 'gemini',      decanInSign: 3, range: '80–90°',   ancient: 36, egyptName: 'A-Saḥ',                  copticGreek: 'Phu-hor',      hermesName: 'Pepisoth',    star: '猎户 Saḥ 相关', face: 'Sun', tarotSuit: 'swords', tarotPip: 10, tarotTitle: '毁灭 Ruin',         tarotMeaning: '崩盘、终结、触底' },
	{ greek: 10, signId: 'cancer',      decanInSign: 1, range: '90–100°',  ancient: 1,  egyptName: 'Sepṭet',                 copticGreek: 'Sopdet',       hermesName: 'Sotheir',     star: '天狼星 Sirius / Sothis', face: 'Venus', tarotSuit: 'cups', tarotPip: 2, tarotTitle: '爱 Love',            tarotMeaning: '结合、吸引、共鸣' },
	{ greek: 11, signId: 'cancer',      decanInSign: 2, range: '100–110°', ancient: 2,  egyptName: 'Ṭepā-Kenmut',            copticGreek: 'Seta',         hermesName: 'Ouphisit',    star: 'Kenmut 群「前」', face: 'Mercury', tarotSuit: 'cups', tarotPip: 3, tarotTitle: '丰盈 Abundance',     tarotMeaning: '喜庆、友情、丰收' },
	{ greek: 12, signId: 'cancer',      decanInSign: 3, range: '110–120°', ancient: 3,  egyptName: 'Kenmut',                 copticGreek: 'Knum',         hermesName: 'Chnouphos',   star: 'Chnoumis / Knum(狮蛇宝石旬)', face: 'Moon', tarotSuit: 'cups', tarotPip: 4, tarotTitle: '安逸 Luxury',        tarotMeaning: '满足/倦怠、停滞' },
	{ greek: 13, signId: 'leo',         decanInSign: 1, range: '120–130°', ancient: 4,  egyptName: 'Kher-khept-Kenmut',      copticGreek: 'Xar-Knum',     hermesName: 'Chnoumos',    star: 'Charchnoumis', face: 'Saturn', tarotSuit: 'wands', tarotPip: 5, tarotTitle: '争斗 Strife',        tarotMeaning: '竞争、摩擦' },
	{ greek: 14, signId: 'leo',         decanInSign: 2, range: '130–140°', ancient: 5,  egyptName: 'Ḥā-tchat',               copticGreek: 'Ha-tet',       hermesName: 'Ipi',         star: '待核', face: 'Jupiter', tarotSuit: 'wands', tarotPip: 6, tarotTitle: '胜利 Victory',       tarotMeaning: '凯旋、荣誉' },
	{ greek: 15, signId: 'leo',         decanInSign: 3, range: '140–150°', ancient: 6,  egyptName: 'Peḥui-tchat',            copticGreek: 'Phu-Tet',      hermesName: 'Phatiti',     star: '待核', face: 'Mars', tarotSuit: 'wands', tarotPip: 7, tarotTitle: '勇毅 Valour',        tarotMeaning: '坚守、以寡敌众' },
	{ greek: 16, signId: 'virgo',       decanInSign: 1, range: '150–160°', ancient: 7,  egyptName: 'Themat-ḥert',            copticGreek: 'Tom',          hermesName: 'Athoum',      star: '待核', face: 'Sun', tarotSuit: 'coins', tarotPip: 8, tarotTitle: '勤勉 Prudence',      tarotMeaning: '钻研、精进、积累' },
	{ greek: 17, signId: 'virgo',       decanInSign: 2, range: '160–170°', ancient: 8,  egyptName: 'Themat-khert',           copticGreek: 'Uste-bikot',   hermesName: 'Brysous',     star: '待核', face: 'Venus', tarotSuit: 'coins', tarotPip: 9, tarotTitle: '收益 Gain',          tarotMeaning: '自力丰收、独立' },
	{ greek: 18, signId: 'virgo',       decanInSign: 3, range: '170–180°', ancient: 9,  egyptName: 'Usthȧ',                  copticGreek: 'Aposot',       hermesName: 'Amphatham',   star: '待核', face: 'Mercury', tarotSuit: 'coins', tarotPip: 10, tarotTitle: '财富 Wealth',       tarotMeaning: '圆满、传承、家业' },
	{ greek: 19, signId: 'libra',       decanInSign: 1, range: '180–190°', ancient: 10, egyptName: 'Bekathȧ',                copticGreek: 'Souchos',      hermesName: 'Sphoukou',    star: '待核', face: 'Moon', tarotSuit: 'swords', tarotPip: 2, tarotTitle: '休战 Peace',         tarotMeaning: '平衡、僵持、抉择' },
	{ greek: 20, signId: 'libra',       decanInSign: 2, range: '190–200°', ancient: 11, egyptName: 'Ṭepā-khentet',           copticGreek: 'Tpa-χont',     hermesName: 'Nephthimes',  star: '待核', face: 'Saturn', tarotSuit: 'swords', tarotPip: 3, tarotTitle: '悲伤 Sorrow',        tarotMeaning: '心碎、分离' },
	{ greek: 21, signId: 'libra',       decanInSign: 3, range: '200–210°', ancient: 12, egyptName: 'Khentet-ḥert',           copticGreek: 'Xont-har',     hermesName: 'Phou',        star: '待核', face: 'Jupiter', tarotSuit: 'swords', tarotPip: 4, tarotTitle: '休整 Truce',         tarotMeaning: '静养、恢复' },
	{ greek: 22, signId: 'scorpio',     decanInSign: 1, range: '210–220°', ancient: 13, egyptName: 'Khentet-khert',          copticGreek: 'Spt-χne',      hermesName: 'Audameoth(待核)', star: '待核', face: 'Mars', tarotSuit: 'cups', tarotPip: 5, tarotTitle: '失落 Disappointment', tarotMeaning: '损失、遗憾' },
	{ greek: 23, signId: 'scorpio',     decanInSign: 2, range: '220–230°', ancient: 14, egyptName: 'Themes-en-khentet',      copticGreek: 'Sesme',        hermesName: 'Oustichos',   star: '待核', face: 'Sun', tarotSuit: 'cups', tarotPip: 6, tarotTitle: '欢愉 Pleasure',      tarotMeaning: '回忆、温情' },
	{ greek: 24, signId: 'scorpio',     decanInSign: 3, range: '230–240°', ancient: 15, egyptName: 'Sapt-khennu',            copticGreek: 'Si-sesme',     hermesName: 'Aphebis',     star: '待核', face: 'Venus', tarotSuit: 'cups', tarotPip: 7, tarotTitle: '沉湎 Debauch',       tarotMeaning: '幻象、过度' },
	{ greek: 25, signId: 'sagittarius', decanInSign: 1, range: '240–250°', ancient: 16, egyptName: 'Ḥer-ab-uȧa',             copticGreek: 'Hre-ua',       hermesName: 'Sebos',       star: '舟之中央(ḥry-ỉb wỉꜣ)', face: 'Mercury', tarotSuit: 'wands', tarotPip: 8, tarotTitle: '迅捷 Swiftness',     tarotMeaning: '消息、加速、推进' },
	{ greek: 26, signId: 'sagittarius', decanInSign: 2, range: '250–260°', ancient: 17, egyptName: 'Shesmu',                 copticGreek: 'Sesme',        hermesName: 'Teuchmos',    star: '待核', face: 'Moon', tarotSuit: 'wands', tarotPip: 9, tarotTitle: '韧力 Strength',      tarotMeaning: '戒备、积蓄之力' },
	{ greek: 27, signId: 'sagittarius', decanInSign: 3, range: '260–270°', ancient: 18, egyptName: 'Kenmu',                  copticGreek: 'Konime',       hermesName: 'Chthisar',    star: '待核', face: 'Saturn', tarotSuit: 'wands', tarotPip: 10, tarotTitle: '重压 Oppression',   tarotMeaning: '负担、过载' },
	{ greek: 28, signId: 'capricorn',   decanInSign: 1, range: '270–280°', ancient: 19, egyptName: 'Semṭet',                 copticGreek: 'Smat',         hermesName: 'Tair',        star: '待核', face: 'Jupiter', tarotSuit: 'coins', tarotPip: 2, tarotTitle: '变易 Change',        tarotMeaning: '调度、动态平衡' },
	{ greek: 29, signId: 'capricorn',   decanInSign: 2, range: '280–290°', ancient: 20, egyptName: 'Ṭepā-semṭ',              copticGreek: 'Srat',         hermesName: 'Epitek',      star: '待核', face: 'Mars', tarotSuit: 'coins', tarotPip: 3, tarotTitle: '营造 Works',         tarotMeaning: '匠艺、协作建造' },
	{ greek: 30, signId: 'capricorn',   decanInSign: 3, range: '290–300°', ancient: 21, egyptName: 'Sert',                   copticGreek: 'Si-srat',      hermesName: 'Epichnaus',   star: '待核', face: 'Sun', tarotSuit: 'coins', tarotPip: 4, tarotTitle: '权柄 Power',         tarotMeaning: '稳固、掌权、守成' },
	{ greek: 31, signId: 'aquarius',    decanInSign: 1, range: '300–310°', ancient: 22, egyptName: 'Sasa-sert',              copticGreek: 'Tpa-χu',       hermesName: 'Isi',         star: '待核', face: 'Venus', tarotSuit: 'swords', tarotPip: 5, tarotTitle: '落败 Defeat',        tarotMeaning: '失利、失和' },
	{ greek: 32, signId: 'aquarius',    decanInSign: 2, range: '310–320°', ancient: 23, egyptName: 'Kher-khept-sert',        copticGreek: 'Xu',           hermesName: 'Sosomo',      star: '待核', face: 'Mercury', tarotSuit: 'swords', tarotPip: 6, tarotTitle: '凭技得功 Science',   tarotMeaning: '过渡、方法、迁移' },
	{ greek: 33, signId: 'aquarius',    decanInSign: 3, range: '320–330°', ancient: 24, egyptName: 'Khukhu',                 copticGreek: 'Tpa-Biu',      hermesName: 'Chonoumous',  star: '待核', face: 'Moon', tarotSuit: 'swords', tarotPip: 7, tarotTitle: '徒劳 Futility',      tarotMeaning: '投机、半成、回避' },
	{ greek: 34, signId: 'pisces',      decanInSign: 1, range: '330–340°', ancient: 25, egyptName: 'Baba',                   copticGreek: 'Biu',          hermesName: 'Tetimo',      star: '待核', face: 'Saturn', tarotSuit: 'cups', tarotPip: 8, tarotTitle: '怠离 Indolence',     tarotMeaning: '抽身、舍弃' },
	{ greek: 35, signId: 'pisces',      decanInSign: 2, range: '340–350°', ancient: 26, egyptName: 'Khent-ḥeru',             copticGreek: 'Xont-Har',     hermesName: 'Sopphi',      star: '待核', face: 'Jupiter', tarotSuit: 'cups', tarotPip: 9, tarotTitle: '如愿 Happiness',     tarotMeaning: '心愿达成、满足' },
	{ greek: 36, signId: 'pisces',      decanInSign: 3, range: '350–360°', ancient: 27, egyptName: 'Ḥer-ȧb-khentu',          copticGreek: 'Tpi-biu',      hermesName: 'Syro',        star: '待核', face: 'Mars', tarotSuit: 'cups', tarotPip: 10, tarotTitle: '圆满 Satiety',      tarotMeaning: '丰盈、福泽、收束' },
];

// 旬星塔罗花色中文(权杖=火/圣杯=水/宝剑=风/星币=土)
export const TAROT_SUIT_CN = { wands: '权杖', cups: '圣杯', swords: '宝剑', coins: '星币' };
export const TAROT_SUIT_ELEMENT = { wands: '火', cups: '水', swords: '风', coins: '土' };

// 由黄经取旬(回归锚定),返回该旬完整记录
export function decanByLon(lon){
	const idx = greekDecan(lon) - 1;
	return EGYPT_DECANS[idx] || null;
}

/* ============================================================
 * E9:五星 + 关键恒星的埃及名
 * ------------------------------------------------------------
 * 命名存在异写与学派分歧(火/木/土均以「荷鲁斯+修饰」命名是显著特征)。
 * ============================================================ */

export const EGYPT_PLANET_NAMES = [
	{ id: 'Mercury', cn: '水星', egyptName: 'Sebegu / sbgw',                            literal: '与 Set 相关',       note: '有时归 Set' },
	{ id: 'Venus',   cn: '金星', egyptName: 'Seba-djai(「渡越之星」)/ 关联 Benu',     literal: '渡越者 / 晨星',     note: '晨昏星;Benu=贝努鸟/不死鸟' },
	{ id: 'Mars',    cn: '火星', egyptName: 'Hor-Desher(「红色荷鲁斯」)',              literal: '红荷鲁斯',          note: '又作 Sekded-ef-em-khetkhet「逆行而旅者」,指其留逆' },
	{ id: 'Jupiter', cn: '木星', egyptName: 'Hor-wepesh-tawy / Hor-up-sheta',          literal: '分判两地的荷鲁斯 / 开秘荷鲁斯', note: '' },
	{ id: 'Saturn',  cn: '土星', egyptName: 'Hor-ka-pet(Ḥr-kꜣ-pt)',                  literal: '天之公牛荷鲁斯',    note: '' },
];

export const EGYPT_STAR_NAMES = [
	{ cn: '天狼星 Sirius',    egyptName: 'Sopdet(spdt)/ Sothis',  literal: '女神',          note: '新年/泛滥标志' },
	{ cn: '猎户座 Orion',     egyptName: 'Sah(sꜣḥ)',              literal: '关联 Osiris',   note: '旬 #6–9 与之相关' },
	{ cn: '北斗/大熊 Ursa Major', egyptName: 'Meskhetiu(msḫtjw)', literal: '公牛前腿/锛',   note: '拱极星,非旬星' },
];

/* ============================================================
 * E2:民用历(游移年)月名 + 五闰余神诞 + Sothic 周期
 * ------------------------------------------------------------
 * 一年 = 3 季 × 4 月 × 30 天 + 5 闰余日 = 365;无闰日,逐年漂移 ≈ 1 天/4 年。
 * dayOfYear = season*120 + month*30 + day(1..360);闰余 e∈1..5 → 360+e。
 * ============================================================ */

export const EGYPT_CIVIL_SEASONS = [
	{ id: 'akhet', cn: '泛滥季', translit: 'Akhet', months: ['Thoth', 'Phaophi', 'Athyr', 'Choiak'] },
	{ id: 'peret', cn: '生长季', translit: 'Peret', months: ['Tybi', 'Mechir', 'Phamenoth', 'Pharmuthi'] },
	{ id: 'shemu', cn: '收获季', translit: 'Shemu', months: ['Pachon', 'Payni', 'Epiphi', 'Mesore'] },
];

// 5 闰余日(epagomenae)各系一神诞辰
export const EGYPT_EPAGOMENAL = [
	{ day: 1, deity: 'Osiris' },
	{ day: 2, deity: 'Horus' },
	{ day: 3, deity: 'Seth' },
	{ day: 4, deity: 'Isis' },
	{ day: 5, deity: 'Nephthys' },
];

export const SOTHIC_CYCLE_YEARS = 1460; // ≈1461 民用年 ≈1460 儒略年

// 全部 12 月扁平名录(序号 1..12)
export function egyptCivilMonths(){
	const out = [];
	EGYPT_CIVIL_SEASONS.forEach((s, si) => {
		s.months.forEach((m, mi) => {
			out.push({ index: si * 4 + mi + 1, season: s.cn, seasonTranslit: s.translit, name: m });
		});
	});
	return out;
}

// 民用历日 → 序号(1..360),闰余 → 361..365
export function civilDayOfYear(season, month, day){ return season * 120 + month * 30 + day; }
export function civilEpagomenalDayOfYear(e){ return 360 + e; }

/* ============================================================
 * E4:对角星钟(夜时授时表)
 * ------------------------------------------------------------
 * 列 = 全年 36 旬(每 10 天一列);行 = 夜 12 时。
 * STAR[c][h] = 该旬该夜时升起的旬星(古代恒星序,以天狼=1 起的「对角」推移)。
 * 推算规则(rising 法,对角星表的理想化形式):
 *   某旬列 c(0..35) 的夜里第 1 时升起的旬星 = 古代序 (c) 之后第 11 颗(因 12 时跨越 11 旬间隔);
 *   逐时 +1,沿对角线推移。这里给出一种自洽的理想对角推移派生(非具体某墓本数值,
 *   各墓本网格互异 → 具体「星—网格—夜时」三元组属「待核」)。
 * 我们以「古代恒星旬序号」标记格内旬星,授时表纯算法派生,供展示对角推移规律。
 * ============================================================ */

// 理想对角推移:第 c 旬(古代序,1..36)夜第 h 时(1..12)升起者的古代序号
// 实现:晨(第12时末)将偕日升的旬星即「今日旬星」c;往前回溯,夜越早升起者古代序越大(更靠后已升)
// 取 ((c + (12 - h)) - 1) mod 36 + 1 给出沿对角推移的旬序(理想化)。
export function diagonalStar(decadeCol /*1..36*/, nightHour /*1..12*/){
	return ((decadeCol + (12 - nightHour) - 1) % 36 + 36) % 36 + 1;
}

export const DIAGONAL_NOTE = '对角星钟:夜里依次升起 12 颗旬星标记夜 12 时;每过 10 天进下一列,同一旬星沿对角线移动(故名)。各墓本网格数值互异,此处按理想对角推移派生展示规律(具体墓本三元组待核)。';

/* ============================================================
 * E6:赫尔墨斯护符 melothesia(逐旬 秘名/宝石/身体部位/疾病)
 * ------------------------------------------------------------
 * 秘名 = EGYPT_DECANS[i].hermesName。身体部位 = 该旬所属宫 melothesia 的三分细分。
 * 12 宫身体对应(head→feet)给出宫级部位;旬级细分(上/中/下)由 decanInSign 派生。
 * 宝石/草木:完整 36 旬清单抄本间差异大,仅 Chnoumis 一例传世实物丰富、可确证;
 * 其余逐旬宝石/草木一律标「待核」(不臆造)。
 * ============================================================ */

// 12 宫身体部位(黄道 melothesia)
export const ZODIAC_MELOTHESIA = {
	aries: '头/面', taurus: '颈/喉', gemini: '肩/臂/手', cancer: '胸/乳/胃',
	leo: '心/背', virgo: '腹/肠', libra: '腰/肾', scorpio: '生殖器',
	sagittarius: '大腿/臀', capricorn: '膝', aquarius: '小腿/踝', pisces: '足',
};

// 旬级身体细分(座内第几旬 → 上/中/下段)
export function decanBodyPart(signId, decanInSign){
	const base = ZODIAC_MELOTHESIA[signId] || '待核';
	const seg = decanInSign === 1 ? '上段' : (decanInSign === 2 ? '中段' : '下段');
	return `${base}(${seg})`;
}

// 逐旬护符表(greek 旬序为 key);仅可确证项填实,余标「待核」
// stone 宝石 / plant 草木 / disease 主管疾病(疾病随宫部位推定,标注「按部位」者为派生)
export const HERMES_TALISMAN = {
	12: { stone: '绿碧玉 / 血石(green jasper / heliotrope)', plant: '待核', disease: '胃/消化(Chnoumis 狮首蛇身护符,传世实物最丰富)', confirmed: true },
	// 其余 35 旬:宝石/草木逐项待核(抄本差异大,不臆造);疾病按宫 melothesia 部位推定
};

// 取某旬护符记录(确证项 + 派生部位/秘名)
export function talismanByDecan(greekIdx){
	const d = EGYPT_DECANS[greekIdx - 1];
	if(!d) return null;
	const extra = HERMES_TALISMAN[greekIdx] || {};
	return {
		secretName: d.hermesName,
		bodyPart: decanBodyPart(d.signId, d.decanInSign),
		stone: extra.stone || '待核',
		plant: extra.plant || '待核',
		disease: extra.disease || `${ZODIAC_MELOTHESIA[d.signId] || '待核'} 部位(按宫 melothesia 推定)`,
		confirmed: !!extra.confirmed,
	};
}

/* ============================================================
 * E7:数字占(isopsephy + Petosiris + Democritus)
 * ------------------------------------------------------------
 * isopsephy:希腊字母 → 数值(27 字母含 3 个古字母 ϛ/ϟ/ϡ)。
 * Petosiris:R = (N + D) mod 29(部分抄本 mod 30) → 上/下半区分大中小生死。
 * Democritus:pythmenes 位根(以 9 为模约简)。
 * 多套抄本(模 29/30、分区)互异 → 分区映射标「待核(择本)」。
 * ============================================================ */

// 希腊字母数值表(27 值;键含小写希腊字母 + 古字母)
export const GREEK_ISOPSEPHY = [
	{ letter: 'α', name: 'alpha',   value: 1 },   { letter: 'β', name: 'beta',    value: 2 },   { letter: 'γ', name: 'gamma',  value: 3 },
	{ letter: 'δ', name: 'delta',   value: 4 },   { letter: 'ε', name: 'epsilon', value: 5 },   { letter: 'ϛ', name: 'stigma', value: 6 },
	{ letter: 'ζ', name: 'zeta',    value: 7 },   { letter: 'η', name: 'eta',     value: 8 },   { letter: 'θ', name: 'theta',  value: 9 },
	{ letter: 'ι', name: 'iota',    value: 10 },  { letter: 'κ', name: 'kappa',   value: 20 },  { letter: 'λ', name: 'lambda', value: 30 },
	{ letter: 'μ', name: 'mu',      value: 40 },  { letter: 'ν', name: 'nu',      value: 50 },  { letter: 'ξ', name: 'xi',     value: 60 },
	{ letter: 'ο', name: 'omicron', value: 70 },  { letter: 'π', name: 'pi',      value: 80 },  { letter: 'ϟ', name: 'koppa',  value: 90 },
	{ letter: 'ρ', name: 'rho',     value: 100 }, { letter: 'σ', name: 'sigma',   value: 200 }, { letter: 'τ', name: 'tau',    value: 300 },
	{ letter: 'υ', name: 'upsilon', value: 400 }, { letter: 'φ', name: 'phi',     value: 500 }, { letter: 'χ', name: 'chi',    value: 600 },
	{ letter: 'ψ', name: 'psi',     value: 700 }, { letter: 'ω', name: 'omega',   value: 800 }, { letter: 'ϡ', name: 'sampi',  value: 900 },
];

// 字母 → 值映射(含终止 sigma ς 归 σ;古字母补充)
const ISOPSEPHY_MAP = (() => {
	const m = {};
	GREEK_ISOPSEPHY.forEach((r) => { m[r.letter] = r.value; });
	m['ς'] = 200; // 终止 sigma
	return m;
})();

// 名字 isopsephy:逐字母求和(仅计已知希腊字母,忽略其他字符)
export function isopsephy(name){
	if(!name) return 0;
	let sum = 0;
	for(const ch of String(name).toLowerCase()){
		if(ISOPSEPHY_MAP[ch] != null) sum += ISOPSEPHY_MAP[ch];
	}
	return sum;
}

// pythmenes 位根(以 9 为模,1..9;0 归 9)—— Democritus 法
export function pythmen(n){
	let x = Math.abs(Math.floor(n));
	if(x === 0) return 0;
	const r = x % 9;
	return r === 0 ? 9 : r;
}

// Petosiris:R = (N + D) mod modulo,落上/下半区
export function petosirisRemainder(nameValue, lunarDay, modulo /*29|30*/){
	const mod = modulo === 30 ? 30 : 29;
	return ((nameValue + lunarDay) % mod + mod) % mod;
}

// Petosiris 分区判读(上半=生/吉,下半=死/凶;再分大中小)。
// 具体分区边界各抄本不同 → 此处给「上下半区 + 三档」的理念派生,精确边界标「待核(择本)」。
export function petosirisVerdict(remainder, modulo /*29|30*/){
	const mod = modulo === 30 ? 30 : 29;
	const half = mod / 2;
	const upper = remainder < half;            // 上半区
	const within = upper ? remainder : (remainder - half);
	const tier = within < half / 3 ? '大' : (within < (2 * half) / 3 ? '中' : '小');
	return { life: upper, label: `${upper ? '生/吉' : '死/凶'}(${tier})`, note: '分区边界各抄本不同,精确档位待核(择本)。' };
}

/* ============================================================
 * E8:埃及吉凶日历(吉/平/凶 三段日)
 * ------------------------------------------------------------
 * 真·古埃及择日(非黄道占星),与民用历挂钩;为每个民用日给晨/午/暮三段吉凶 + 神话/宜忌。
 * 全年 365 日逐日判语残损 → 不逐日复制;仅给结构 + 已确证规则 + 5 闰余神诞。
 * 此处不提供逐日判语数据(待核:逐日判语需据 P.Cairo 86637 等抄本誊录,本仓不复制)。
 * 提供:三段标记图例 + 闰余神诞(已在 EGYPT_EPAGOMENAL)+ 周期注记。
 * ============================================================ */

export const HEMEROLOGY_PARTS = ['晨', '午', '暮'];
export const HEMEROLOGY_MARKS = { good: '吉(nfr)', neutral: '平', bad: '凶' };
export const HEMEROLOGY_NOTE = '逐日判语据神话事件(如荷鲁斯与赛特之战、诸神诞辰)投射到日;吉凶分布含太阴月周期(≈29.6 天)与民用历周期,疑含大陵五(Algol≈2.85 天)变光周期。逐日全表残损,需据原始抄本誊录,本页只示结构与图例(逐日数据待核)。';

/* ============================================================
 * E3:占星地理(行星 ↔ 地理对应;世运盘地理叠加)
 * ------------------------------------------------------------
 * 四分法:世界按四三分性分四象限(西北火/东北土/东南风/西南水),各象限内细分给三星座。
 * 星座 → 代表地域(浓缩选列);行星共主见三分性。
 * ============================================================ */

// 四象限(三分性 → 方位 + 风向 + 行星共主)
export const CHOROGRAPHY_QUARTERS = [
	{ element: '火', signs: ['aries', 'leo', 'sagittarius'], quarter: '西北', wind: '西风/北风' },
	{ element: '土', signs: ['taurus', 'virgo', 'capricorn'], quarter: '东北', wind: '东风/南风' },
	{ element: '风', signs: ['gemini', 'libra', 'aquarius'],  quarter: '东南', wind: '东风' },
	{ element: '水', signs: ['cancer', 'scorpio', 'pisces'],  quarter: '西南', wind: '西风/南风' },
];

// 星座 → 代表地域(浓缩选列,举要)。完整原典更细 → 标注为「举要」。
export const CHOROGRAPHY_REGIONS = {
	aries:       '不列颠、高卢、日耳曼尼亚;(中)叙利亚-巴勒斯坦、犹地亚',
	taurus:      '帕提亚、米底、波斯;(中)基克拉泽斯、塞浦路斯、小亚海岸',
	gemini:      '亚美尼亚、许尔卡尼亚;昔兰尼加、下埃及',
	cancer:      '努米底亚、迦太基、阿非利加;比提尼亚、弗里吉亚',
	leo:         '意大利、西西里、阿普利亚;腓尼基、迦勒底',
	virgo:       '美索不达米亚、巴比伦尼亚、亚述;希腊、阿凯亚、克里特',
	libra:       '巴克特里亚、Serica(丝国);(中)埃及底比斯绿洲一带',
	scorpio:     '毛里塔尼亚、Gaetulia;叙利亚、卡帕多奇亚',
	sagittarius: '提尔列尼亚、凯尔特、西班牙;阿拉伯福地',
	capricorn:   '印度、Ariana、Gedrosia;色雷斯、马其顿、伊利里亚',
	aquarius:    'Sauromatica、Sogdiana;阿拉伯、中埃及',
	pisces:      'Phazania、Garamantica;吕底亚、奇里乞亚、潘菲利亚;红海-印度方向',
};

export default EGYPT_DECANS;
