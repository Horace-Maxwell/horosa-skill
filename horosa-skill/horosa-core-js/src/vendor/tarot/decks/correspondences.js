// 塔罗对应体系——纯事实型对照表(占星/希伯来字母/生命树路径/旬星 Lord/宫廷黄道度数/各派命名/元素友敌)。
// 这些是公有领域的体系事实(非受版权保护),据古典对应体系(Golden Dawn Book T 1888、传统占星界系)落数据。
// 单一真值源:大牌/小牌/宫廷的对应叠层与各流派命名皆出自此,供 cardSchema.display_name / astro_line 消费。

import { isTrumpArcana } from '../engine/arcana.js'; // [QA-9] 王牌判据单一真值源
export const SUITS = ['wands', 'cups', 'swords', 'pentacles'];
export const SUIT_ELEMENT = { wands: 'fire', cups: 'water', swords: 'air', pentacles: 'earth' };
export const ELEMENT_CN = { fire: '火', water: '水', air: '风', earth: '土' };
export const ELEMENT_SUIT = { fire: 'wands', water: 'cups', air: 'swords', earth: 'pentacles' };

export const SIGN_ELEMENT = {
	Aries: 'fire', Leo: 'fire', Sagittarius: 'fire',
	Taurus: 'earth', Virgo: 'earth', Capricorn: 'earth',
	Gemini: 'air', Libra: 'air', Aquarius: 'air',
	Cancer: 'water', Scorpio: 'water', Pisces: 'water',
};
export const SIGN_CN = {
	Aries: '白羊', Taurus: '金牛', Gemini: '双子', Cancer: '巨蟹',
	Leo: '狮子', Virgo: '处女', Libra: '天秤', Scorpio: '天蝎',
	Sagittarius: '射手', Capricorn: '摩羯', Aquarius: '水瓶', Pisces: '双鱼',
};
export const PLANET_CN = {
	Mars: '火星', Sun: '太阳', Venus: '金星', Mercury: '水星',
	Moon: '月亮', Saturn: '土星', Jupiter: '木星',
};
export const ELEMENT_EN_CN = { Air: '风', Water: '水', Fire: '火', Earth: '土' };

// 元素尊位友/敌(金色黎明/托特核心,逆位的替代法)
export const FRIEND = [['fire', 'air'], ['air', 'fire'], ['water', 'earth'], ['earth', 'water']];
export const ENEMY = [['fire', 'water'], ['water', 'fire'], ['air', 'earth'], ['earth', 'air']];
export function isFriend(a, b){ return FRIEND.some((p) => p[0] === a && p[1] === b); }
export function isEnemy(a, b){ return ENEMY.some((p) => p[0] === a && p[1] === b); }

// 大阿卡纳对应表:n=RWS 编号, id, 各派名, cn, heb 希伯来字母, astro 占星(行星/星座/元素), elem 元素, path 生命树路径(11..32)
export const MAJORS_CORR = [
	{ n: 0, id: 'the_fool', rws: 'The Fool', thoth: 'The Fool', tdm: 'Le Mat', cn: '愚者', heb: 'Aleph', astro: 'Air', elem: 'air', path: 11 },
	{ n: 1, id: 'the_magician', rws: 'The Magician', thoth: 'The Magus', tdm: 'Le Bateleur', cn: '魔术师', heb: 'Beth', astro: 'Mercury', elem: 'air', path: 12 },
	{ n: 2, id: 'high_priestess', rws: 'The High Priestess', thoth: 'The Priestess', tdm: 'La Papesse', cn: '女祭司', heb: 'Gimel', astro: 'Moon', elem: 'water', path: 13 },
	{ n: 3, id: 'the_empress', rws: 'The Empress', thoth: 'The Empress', tdm: "L'Impératrice", cn: '皇后', heb: 'Daleth', astro: 'Venus', elem: 'earth', path: 14 },
	{ n: 4, id: 'the_emperor', rws: 'The Emperor', thoth: 'The Emperor', tdm: "L'Empereur", cn: '皇帝', heb: 'Heh', astro: 'Aries', elem: 'fire', path: 15 },
	{ n: 5, id: 'the_hierophant', rws: 'The Hierophant', thoth: 'The Hierophant', tdm: 'Le Pape', cn: '教皇', heb: 'Vav', astro: 'Taurus', elem: 'earth', path: 16 },
	{ n: 6, id: 'the_lovers', rws: 'The Lovers', thoth: 'The Lovers', tdm: "L'Amoureux", cn: '恋人', heb: 'Zayin', astro: 'Gemini', elem: 'air', path: 17 },
	{ n: 7, id: 'the_chariot', rws: 'The Chariot', thoth: 'The Chariot', tdm: 'Le Chariot', cn: '战车', heb: 'Cheth', astro: 'Cancer', elem: 'water', path: 18 },
	{ n: 8, id: 'strength', rws: 'Strength', thoth: 'Lust', tdm: 'La Force', cn: '力量', heb: 'Teth', astro: 'Leo', elem: 'fire', path: 19 },
	{ n: 9, id: 'the_hermit', rws: 'The Hermit', thoth: 'The Hermit', tdm: "L'Hermite", cn: '隐士', heb: 'Yod', astro: 'Virgo', elem: 'earth', path: 20 },
	{ n: 10, id: 'wheel_of_fortune', rws: 'Wheel of Fortune', thoth: 'Fortune', tdm: 'La Roue de Fortune', cn: '命运之轮', heb: 'Kaph', astro: 'Jupiter', elem: null, path: 21 },
	{ n: 11, id: 'justice', rws: 'Justice', thoth: 'Adjustment', tdm: 'La Justice', cn: '正义', heb: 'Lamed', astro: 'Libra', elem: 'air', path: 22 },
	{ n: 12, id: 'hanged_man', rws: 'The Hanged Man', thoth: 'The Hanged Man', tdm: 'Le Pendu', cn: '倒吊人', heb: 'Mem', astro: 'Water', elem: 'water', path: 23 },
	{ n: 13, id: 'death', rws: 'Death', thoth: 'Death', tdm: '(XIII)', cn: '死神', heb: 'Nun', astro: 'Scorpio', elem: 'water', path: 24 },
	{ n: 14, id: 'temperance', rws: 'Temperance', thoth: 'Art', tdm: 'Tempérance', cn: '节制', heb: 'Samekh', astro: 'Sagittarius', elem: 'fire', path: 25 },
	{ n: 15, id: 'the_devil', rws: 'The Devil', thoth: 'The Devil', tdm: 'Le Diable', cn: '恶魔', heb: 'Ayin', astro: 'Capricorn', elem: 'earth', path: 26 },
	{ n: 16, id: 'the_tower', rws: 'The Tower', thoth: 'The Tower', tdm: 'La Maison Dieu', cn: '高塔', heb: 'Peh', astro: 'Mars', elem: null, path: 27 },
	{ n: 17, id: 'the_star', rws: 'The Star', thoth: 'The Star', tdm: "L'Étoile", cn: '星星', heb: 'Tzaddi', astro: 'Aquarius', elem: 'air', path: 28 },
	{ n: 18, id: 'the_moon', rws: 'The Moon', thoth: 'The Moon', tdm: 'La Lune', cn: '月亮', heb: 'Qoph', astro: 'Pisces', elem: 'water', path: 29 },
	{ n: 19, id: 'the_sun', rws: 'The Sun', thoth: 'The Sun', tdm: 'Le Soleil', cn: '太阳', heb: 'Resh', astro: 'Sun', elem: 'fire', path: 30 },
	{ n: 20, id: 'judgement', rws: 'Judgement', thoth: 'The Aeon', tdm: 'Le Jugement', cn: '审判', heb: 'Shin', astro: 'Fire', elem: 'fire', path: 31 },
	{ n: 21, id: 'the_world', rws: 'The World', thoth: 'The Universe', tdm: 'Le Monde', cn: '世界', heb: 'Tav', astro: 'Saturn', elem: 'earth', path: 32 },
];

// 大陆派(Lévi/Papus/Wirth/Egyptian)希伯来字母——较 Golden Dawn 整体晚一格(Magician=Aleph 起、Fool=Shin)。
// 变体 C 用此表;两派唯一一致 World=Tav。键=sid。
export const CONTINENTAL_HEBREW = {
	the_fool: 'Shin', the_magician: 'Aleph', high_priestess: 'Beth', the_empress: 'Gimel',
	the_emperor: 'Daleth', the_hierophant: 'Heh', the_lovers: 'Vav', the_chariot: 'Zayin',
	strength: 'Kaph', the_hermit: 'Teth', wheel_of_fortune: 'Yod', justice: 'Cheth',
	hanged_man: 'Lamed', death: 'Mem', temperance: 'Nun', the_devil: 'Samekh',
	the_tower: 'Ayin', the_star: 'Peh', the_moon: 'Tzaddi', the_sun: 'Qoph',
	judgement: 'Resh', the_world: 'Tav',
};

// 8/11 编号在各派的显示号(力量↔正义)
export const NUM_OVERRIDE = {
	strength: { rws: 8, golden_dawn: 8, tdm: 11, thoth: 11 },
	justice: { rws: 11, golden_dawn: 11, tdm: 8, thoth: 8 },
};

// 36 旬星 Lord 标题 + 行星 in 星座(迦勒底序,0°白羊起);DECAN[suit][rank 2..10]=[title,planet,sign]
export const DECAN = {
	wands: { 2: ['Dominion', 'Mars', 'Aries'], 3: ['Virtue', 'Sun', 'Aries'], 4: ['Completion', 'Venus', 'Aries'], 5: ['Strife', 'Saturn', 'Leo'], 6: ['Victory', 'Jupiter', 'Leo'], 7: ['Valour', 'Mars', 'Leo'], 8: ['Swiftness', 'Mercury', 'Sagittarius'], 9: ['Strength', 'Moon', 'Sagittarius'], 10: ['Oppression', 'Saturn', 'Sagittarius'] },
	cups: { 2: ['Love', 'Venus', 'Cancer'], 3: ['Abundance', 'Mercury', 'Cancer'], 4: ['Luxury', 'Moon', 'Cancer'], 5: ['Disappointment', 'Mars', 'Scorpio'], 6: ['Pleasure', 'Sun', 'Scorpio'], 7: ['Debauch', 'Venus', 'Scorpio'], 8: ['Indolence', 'Saturn', 'Pisces'], 9: ['Happiness', 'Jupiter', 'Pisces'], 10: ['Satiety', 'Mars', 'Pisces'] },
	swords: { 2: ['Peace', 'Moon', 'Libra'], 3: ['Sorrow', 'Saturn', 'Libra'], 4: ['Truce', 'Jupiter', 'Libra'], 5: ['Defeat', 'Venus', 'Aquarius'], 6: ['Science', 'Mercury', 'Aquarius'], 7: ['Futility', 'Moon', 'Aquarius'], 8: ['Interference', 'Jupiter', 'Gemini'], 9: ['Cruelty', 'Mars', 'Gemini'], 10: ['Ruin', 'Sun', 'Gemini'] },
	pentacles: { 2: ['Change', 'Jupiter', 'Capricorn'], 3: ['Works', 'Mars', 'Capricorn'], 4: ['Power', 'Sun', 'Capricorn'], 5: ['Worry', 'Mercury', 'Taurus'], 6: ['Success', 'Moon', 'Taurus'], 7: ['Failure', 'Saturn', 'Taurus'], 8: ['Prudence', 'Sun', 'Virgo'], 9: ['Gain', 'Venus', 'Virgo'], 10: ['Wealth', 'Mercury', 'Virgo'] },
};

// 宫廷牌占星:元素中元素 + 黄道跨度。键=RWS 内部位阶(page/knight/queen/king)
export const COURT_ASTRO = {
	wands: { king: ['火中火 Fire of Fire', '20°天蝎→20°射手'], queen: ['火中水 Water of Fire', '20°双鱼→20°白羊'], knight: ['火中风 Air of Fire', '20°巨蟹→20°狮子'], page: ['火中土 Earth of Fire', '象限 巨蟹–狮子–处女'] },
	cups: { king: ['水中火 Fire of Water', '20°水瓶→20°双鱼'], queen: ['水中水 Water of Water', '20°双子→20°巨蟹'], knight: ['水中风 Air of Water', '20°天秤→20°天蝎'], page: ['水中土 Earth of Water', '象限 天秤–天蝎–射手'] },
	swords: { king: ['风中火 Fire of Air', '20°金牛→20°双子'], queen: ['风中水 Water of Air', '20°处女→20°天秤'], knight: ['风中风 Air of Air', '20°摩羯→20°水瓶'], page: ['风中土 Earth of Air', '象限 摩羯–水瓶–双鱼'] },
	pentacles: { king: ['土中火 Fire of Earth', '20°狮子→20°处女'], queen: ['土中水 Water of Earth', '20°射手→20°摩羯'], knight: ['土中风 Air of Earth', '20°白羊→20°金牛'], page: ['土中土 Earth of Earth', '象限 白羊–金牛–双子'] },
};

export const COURT_ORDER = ['page', 'knight', 'queen', 'king']; // RWS 规范内部键(由低到高)

// 各派花色/位阶命名(EN + CN)
export const SUIT_NAME = {
	rws: { wands: 'Wands', cups: 'Cups', swords: 'Swords', pentacles: 'Pentacles' },
	golden_dawn: { wands: 'Wands', cups: 'Cups', swords: 'Swords', pentacles: 'Disks' },
	thoth: { wands: 'Wands', cups: 'Cups', swords: 'Swords', pentacles: 'Disks' },
	tdm: { wands: 'Bâtons', cups: 'Coupes', swords: 'Épées', pentacles: 'Deniers' },
};
export const SUIT_CN = { wands: '权杖', cups: '圣杯', swords: '宝剑', pentacles: '钱币' };
export const PIP_NAME_EN = { 1: 'Ace', 2: 'Two', 3: 'Three', 4: 'Four', 5: 'Five', 6: 'Six', 7: 'Seven', 8: 'Eight', 9: 'Nine', 10: 'Ten' };
export const PIP_NAME_CN = { 1: '一', 2: '二', 3: '三', 4: '四', 5: '五', 6: '六', 7: '七', 8: '八', 9: '九', 10: '十' };
export const COURT_NAME = {
	rws: { page: 'Page', knight: 'Knight', queen: 'Queen', king: 'King' },
	golden_dawn: { page: 'Princess', knight: 'Prince', queen: 'Queen', king: 'Knight' },
	thoth: { page: 'Princess', knight: 'Prince', queen: 'Queen', king: 'Knight' },
	tdm: { page: 'Valet', knight: 'Cavalier', queen: 'Reine', king: 'Roi' },
};
export const COURT_CN = {
	rws: { page: '侍从', knight: '骑士', queen: '王后', king: '国王' },
	golden_dawn: { page: '公主', knight: '王子', queen: '王后', king: '骑士' },
	thoth: { page: '公主', knight: '王子', queen: '王后', king: '骑士' },
	tdm: { page: '侍从', knight: '骑士', queen: '王后', king: '国王' },
};

// 大牌占星 → 元素(供尊位):元素型直接,星座型经 SIGN_ELEMENT,行星型无元素
export function majorElement(corr){
	if(corr.elem){ return corr.elem; }
	if(corr.astro && SIGN_ELEMENT[corr.astro]){ return SIGN_ELEMENT[corr.astro]; }
	return null;
}

// —— 对应叠层补全（卡巴拉质点 / 路径连质点 / Ace 象限 / 花色↔极性季节扑克）——
// 数据源:古典对应体系(生命之树 10 质点、22 路径、天界象限、四花色社会/元素属性),公有领域体系事实。

// 卡巴拉十质点 Sephiroth:序号 = 小牌 Ace–10 的对应(每花色一套);name/中文 + 生命之树标准坐标(x,y∈[0,1],供 G6 可视化)。
export const SEPHIROTH = {
	1: { name: 'Kether', cn: '王冠', x: 0.5, y: 0.05 },
	2: { name: 'Chokmah', cn: '智慧', x: 0.74, y: 0.18 },
	3: { name: 'Binah', cn: '理解', x: 0.26, y: 0.18 },
	4: { name: 'Chesed', cn: '仁慈', x: 0.74, y: 0.40 },
	5: { name: 'Geburah', cn: '严厉', x: 0.26, y: 0.40 },
	6: { name: 'Tiphareth', cn: '美', x: 0.5, y: 0.53 },
	7: { name: 'Netzach', cn: '胜利', x: 0.74, y: 0.72 },
	8: { name: 'Hod', cn: '荣耀', x: 0.26, y: 0.72 },
	9: { name: 'Yesod', cn: '根基', x: 0.5, y: 0.84 },
	10: { name: 'Malkuth', cn: '王国', x: 0.5, y: 0.97 },
};
// 小牌数字 → Sephira 文本(Ace=Kether…10=Malkuth)
export function sephiraLabel(n){ const s = SEPHIROTH[n]; return s ? `${s.name} ${s.cn}` : null; }
// 宫廷牌 → 质点(YHVH 四界):Knight/RWS-King=Chokmah、Queen=Binah、Prince/RWS-Knight=Tiphareth、Princess/RWS-Page=Malkuth
export const COURT_SEPHIRA = { king: 2, queen: 3, knight: 6, page: 10 };

// 大牌路径连接的两质点(「连接质点」列;变体 A=Golden Dawn)。键=sid,值=[质点号a, 质点号b]。
export const PATH_JOIN = {
	the_fool: [1, 2], the_magician: [1, 3], high_priestess: [1, 6], the_empress: [2, 3],
	the_emperor: [2, 6], the_hierophant: [2, 4], the_lovers: [3, 6], the_chariot: [3, 5],
	strength: [4, 5], the_hermit: [4, 6], wheel_of_fortune: [4, 7], justice: [5, 6],
	hanged_man: [5, 8], death: [6, 7], temperance: [6, 9], the_devil: [6, 8],
	the_tower: [7, 8], the_star: [7, 9], the_moon: [7, 10], the_sun: [8, 9],
	judgement: [8, 10], the_world: [9, 10],
};
// 变体 B(托特 Tzaddi/Heh 互换):星座不变、字母+路径整对对调 → Emperor 走 Star 路径、Star 走 Emperor 路径。
export const PATH_JOIN_VARIANT_B = { the_emperor: [7, 9], the_star: [2, 6] };
export function pathJoin(sid, variant){
	if(variant === 'B' && PATH_JOIN_VARIANT_B[sid]){ return PATH_JOIN_VARIANT_B[sid]; }
	return PATH_JOIN[sid] || null;
}

// 四张 Ace / 四位 Princess 守护的 90° 天界象限(三星座 + 季节起点)。键=花色。
export const ACE_QUADRANT = {
	wands: { signs: '巨蟹–狮子–处女', season: '夏至' },
	cups: { signs: '天秤–天蝎–射手', season: '秋分' },
	swords: { signs: '摩羯–水瓶–双鱼', season: '冬至' },
	pentacles: { signs: '白羊–金牛–双子', season: '春分' },
};

// 花色 ↔ 极性 / 季节方位 / 扑克花色(通用框架;季节非硬规则,仅占卜参考)。键=花色。
export const SUIT_POLARITY = { wands: '阳·主动', cups: '阴·接受', swords: '阳·主动', pentacles: '阴·接受' };
export const SUIT_SEASON = { wands: '南·春', cups: '西·夏', swords: '东·秋', pentacles: '北·冬' };
export const SUIT_PLAYING_CARD = { wands: '♣ Clubs', cups: '♥ Hearts', swords: '♠ Spades', pentacles: '♦ Diamonds' };
export const SUIT_ESTATE = { wands: '农民 Peasants', cups: '教士 Clergy', swords: '贵族 Nobility', pentacles: '商人 Merchants' };

// 36 旬星「大致日期」段（对应 DECAN 的 suit/rank；供计时法附日期）。DECAN_DATE[suit][rank 2..10]。
export const DECAN_DATE = {
	wands: { 2: '03-21~03-30', 3: '03-31~04-10', 4: '04-11~04-20', 5: '07-22~08-01', 6: '08-02~08-11', 7: '08-12~08-22', 8: '11-23~12-02', 9: '12-03~12-12', 10: '12-13~12-21' },
	cups: { 2: '06-21~07-01', 3: '07-02~07-11', 4: '07-12~07-21', 5: '10-23~11-01', 6: '11-02~11-12', 7: '11-13~11-22', 8: '02-19~02-29', 9: '03-01~03-10', 10: '03-11~03-20' },
	swords: { 2: '09-23~10-02', 3: '10-03~10-12', 4: '10-13~10-22', 5: '01-20~01-29', 6: '01-30~02-08', 7: '02-09~02-18', 8: '05-21~05-31', 9: '06-01~06-10', 10: '06-11~06-20' },
	// [TP-DATA 真bug修] 钱币三组日期段原互相错位(2-4 摩羯旬误挂金牛日期/5-7 误挂处女/8-10 误挂摩羯),
	// 与 DECAN 旬星表(2-4=Capricorn·5-6-7=Taurus·8-9-10=Virgo)自相矛盾;tarotDataFoundation 派生锚咬出,按旬星归位。
	pentacles: { 2: '12-22~12-30', 3: '12-31~01-09', 4: '01-10~01-19', 5: '04-21~04-30', 6: '05-01~05-10', 7: '05-11~05-20', 8: '08-23~09-01', 9: '09-02~09-11', 10: '09-12~09-22' },
};
export function decanDate(card){
	if(!card || card.court || !card.suit || !(card.number >= 2 && card.number <= 10)){ return null; }
	return (DECAN_DATE[card.suit] && DECAN_DATE[card.suit][card.number]) || null;
}

// ═══════════ 对应叠层二期(五书补齐·TP-DATA):以下全为公有领域体系事实 ═══════════
// 据 Book T(1888)/Liber 777/《创世之书》字母传统/古典占星尊贵体系落数据;中文为原创转录。

// 大牌 GD 秘传称号(Book T 原文,公有领域)。键=sid。
export const ESOTERIC_TITLE_MAJOR = {
	the_fool: 'The Spirit of Ether', the_magician: 'The Magus of Power', high_priestess: 'The Priestess of the Silver Star',
	the_empress: 'Daughter of the Mighty Ones', the_emperor: 'Son of the Morning, Chief Among the Mighty',
	the_hierophant: 'Magus of the Eternal Gods', the_lovers: 'Children of the Voice Divine',
	the_chariot: 'Child of the Power of the Waters, Lord of the Triumph of Light',
	strength: 'Daughter of the Flaming Sword, Leader of the Lion', the_hermit: 'Magus of the Voice of Light, Prophet of the Gods',
	wheel_of_fortune: 'The Lord of the Forces of Life', justice: 'Daughter of the Lord of Truth, Holder of the Balances',
	hanged_man: 'The Spirit of the Mighty Waters', death: 'Child of the Great Transformers, Lord of the Gates of Death',
	temperance: 'Daughter of the Reconcilers, Bringer Forth of Life', the_devil: 'Lord of the Gates of Matter, Child of the Forces of Time',
	the_tower: 'Lord of the Hosts of the Mighty', the_star: 'Daughter of the Firmament, Dweller Between the Waters',
	the_moon: 'Ruler of Flux and Reflux, Child of the Sons of the Mighty', the_sun: 'Lord of the Fire of the World',
	judgement: 'The Spirit of the Primal Fire', the_world: 'The Great One of the Night of Time',
};

// 宫廷 Book T 称号(公有领域;RWS 内部键)。COURT_TITLE[suit][court]。
export const COURT_TITLE = {
	wands: { king: 'Lord of the Flame and the Lightning; King of the Spirits of Fire', queen: 'Queen of the Thrones of Flame', knight: 'Prince of the Chariot of Fire', page: 'Princess of the Shining Flame; the Rose of the Palace of Fire' },
	cups: { king: 'Lord of the Waves and the Waters; King of the Hosts of the Sea', queen: 'Queen of the Thrones of the Waters', knight: 'Prince of the Chariot of the Waters', page: 'Princess of the Waters; Lotus of the Palace of Floods' },
	swords: { king: 'Lord of the Winds and the Breezes; King of the Spirit of Air', queen: 'Queen of the Thrones of Air', knight: 'Prince of the Chariots of the Winds', page: 'Princess of the Rushing Winds; Lotus of the Palace of Air' },
	pentacles: { king: 'Lord of the Wide and Fertile Land; King of the Spirits of Earth', queen: 'Queen of the Thrones of Earth', knight: 'Prince of the Chariot of Earth', page: 'Princess of the Echoing Hills; Rose of the Palace of Earth' },
};

// 希伯来字母元数据(《创世之书》传统):kind 母/双/单 · sense 字母义 · value 数值 · gift 天赋属性 · gateway 身体门户 · note 音符。键=sid。
export const LETTER_META = {
	the_fool: { kind: '母', sense: '牛·力量', value: '1', gift: '风(温)', gateway: '胸', note: 'E' },
	the_magician: { kind: '双', sense: '房屋·在内', value: '2', gift: '生与死', gateway: '右眼', note: 'E' },
	high_priestess: { kind: '双', sense: '骆驼·行旅', value: '3', gift: '智与愚', gateway: '右耳', note: 'G#' },
	the_empress: { kind: '双', sense: '门·出入', value: '4', gift: '和平与战争', gateway: '右鼻孔', note: 'F#' },
	the_emperor: { kind: '单', sense: '窗·显示', value: '5', gift: '视觉', gateway: '右足', note: 'C' },
	the_hierophant: { kind: '单', sense: '钉·连结', value: '6', gift: '听觉', gateway: '右肾', note: 'C#' },
	the_lovers: { kind: '单', sense: '剑·切分', value: '7', gift: '嗅觉', gateway: '左足', note: 'D' },
	the_chariot: { kind: '单', sense: '篱·护域', value: '8', gift: '言语', gateway: '右手', note: 'D#' },
	strength: { kind: '单', sense: '蛇·盘绕', value: '9', gift: '味觉', gateway: '左肾', note: 'E' },
	the_hermit: { kind: '单', sense: '手·授受', value: '10', gift: '交合', gateway: '左手', note: 'F' },
	wheel_of_fortune: { kind: '双', sense: '掌·承接', value: '20/500', gift: '富与贫', gateway: '左眼', note: 'G#' },
	justice: { kind: '单', sense: '刺棒·驱策', value: '30', gift: '工作', gateway: '胆', note: 'F#' },
	hanged_man: { kind: '母', sense: '水·众流', value: '40/600', gift: '地(冷)', gateway: '腹', note: 'G#' },
	death: { kind: '单', sense: '鱼·繁衍', value: '50/700', gift: '运动', gateway: '肠', note: 'G' },
	temperance: { kind: '单', sense: '支柱·扶持', value: '60', gift: '怒', gateway: '下腹', note: 'G#' },
	the_devil: { kind: '单', sense: '眼·看见', value: '70', gift: '笑', gateway: '肝', note: 'A' },
	the_tower: { kind: '双', sense: '口·言说', value: '80/800', gift: '恩典与义愤', gateway: '左耳', note: 'C' },
	the_star: { kind: '单', sense: '鱼钩·牵引', value: '90/900', gift: '想象', gateway: '胃', note: 'A#' },
	the_moon: { kind: '单', sense: '后脑·回环', value: '100', gift: '睡眠', gateway: '生殖', note: 'B' },
	the_sun: { kind: '双', sense: '头·首领', value: '200', gift: '丰与瘠', gateway: '左鼻孔', note: 'D' },
	judgement: { kind: '母', sense: '齿·锐化', value: '300', gift: '火(热)', gateway: '头', note: 'C' },
	the_world: { kind: '双', sense: '印记·十字', value: '400', gift: '权能与奴役', gateway: '口', note: 'A' },
};

// 历史别名(早期意/法牌张登记名,仅录有据者,公有史实)。键=sid。
export const MAJOR_ALIAS = {
	the_fool: 'Il Matto', the_magician: 'Il Bagatto', high_priestess: 'La Papesse(女教皇)',
	the_hierophant: 'Le Pape(教皇)', the_hermit: 'Rerum Edax(蚀万物者)', wheel_of_fortune: 'Omnium Dominatrix(万物主宰)',
	hanged_man: 'Il Traditore(叛徒)', death: 'L’Arcane sans Nom(无名之牌)', the_tower: 'La Maison Dieu(神之家)',
	the_star: 'Inclitum Sydus(煌煌之星)', judgement: 'L’Ange(天使)',
};

// 现代行星补充对应(三元素大牌的近代增补;显示层可选注,不改传统七曜主线)。键=sid。
export const MODERN_PLANET = { the_fool: 'Uranus', hanged_man: 'Neptune', judgement: 'Pluto' };
export const MODERN_PLANET_CN = { Uranus: '天王星', Neptune: '海王星', Pluto: '冥王星' };

// 行星曜日(古典七曜,计时法用)。
export const PLANET_WEEKDAY = { Sun: '周日', Moon: '周一', Mars: '周二', Mercury: '周三', Jupiter: '周四', Venus: '周五', Saturn: '周六' };

// 宫廷↔三态模式(Queen 全本位/Knight(RWS)全固定/King(RWS)全变动;Page 辖一季近固定)。
export const COURT_MODE = { king: '变动', queen: '本位', knight: '固定', page: '(一季)' };

// 宫廷黄道跨段(结构化:前一星座末旬 + 本星座前两旬;Page 辖三星座象限)。COURT_SPAN_SIGNS[suit][court]=[跨入星座,本位星座] / page=[三星座]。
export const COURT_SPAN_SIGNS = {
	wands: { king: ['Scorpio', 'Sagittarius'], queen: ['Pisces', 'Aries'], knight: ['Cancer', 'Leo'], page: ['Cancer', 'Leo', 'Virgo'] },
	cups: { king: ['Aquarius', 'Pisces'], queen: ['Gemini', 'Cancer'], knight: ['Libra', 'Scorpio'], page: ['Libra', 'Scorpio', 'Sagittarius'] },
	swords: { king: ['Taurus', 'Gemini'], queen: ['Virgo', 'Libra'], knight: ['Capricorn', 'Aquarius'], page: ['Capricorn', 'Aquarius', 'Pisces'] },
	pentacles: { king: ['Leo', 'Virgo'], queen: ['Sagittarius', 'Capricorn'], knight: ['Aries', 'Taurus'], page: ['Aries', 'Taurus', 'Gemini'] },
};

// 宫廷辖下小牌(King/Queen/Knight 各 3 张=跨段三旬;Page 辖其象限 9 张)。值=sid 数组(Book T 口径;含对底本两处错行的勘正)。
export const COURT_SHADOW_PIPS = {
	wands: { king: ['cups_07', 'wands_08', 'wands_09'], queen: ['cups_10', 'wands_02', 'wands_03'], knight: ['cups_04', 'wands_05', 'wands_06'], page: ['cups_02', 'cups_03', 'cups_04', 'wands_05', 'wands_06', 'wands_07', 'pentacles_08', 'pentacles_09', 'pentacles_10'] },
	cups: { king: ['swords_07', 'cups_08', 'cups_09'], queen: ['swords_10', 'cups_02', 'cups_03'], knight: ['swords_04', 'cups_05', 'cups_06'], page: ['swords_02', 'swords_03', 'swords_04', 'cups_05', 'cups_06', 'cups_07', 'wands_08', 'wands_09', 'wands_10'] },
	swords: { king: ['pentacles_07', 'swords_08', 'swords_09'], queen: ['pentacles_10', 'swords_02', 'swords_03'], knight: ['pentacles_04', 'swords_05', 'swords_06'], page: ['pentacles_02', 'pentacles_03', 'pentacles_04', 'swords_05', 'swords_06', 'swords_07', 'cups_08', 'cups_09', 'cups_10'] },
	pentacles: { king: ['wands_07', 'pentacles_08', 'pentacles_09'], queen: ['wands_10', 'pentacles_02', 'pentacles_03'], knight: ['wands_04', 'pentacles_05', 'pentacles_06'], page: ['wands_02', 'wands_03', 'wands_04', 'pentacles_05', 'pentacles_06', 'pentacles_07', 'swords_08', 'swords_09', 'swords_10'] },
};

// Ace 象限三星座(结构化,配 ACE_QUADRANT 显示串)。
export const ACE_QUADRANT_SIGNS = {
	wands: ['Cancer', 'Leo', 'Virgo'], cups: ['Libra', 'Scorpio', 'Sagittarius'],
	swords: ['Capricorn', 'Aquarius', 'Pisces'], pentacles: ['Aries', 'Taurus', 'Gemini'],
};

// 四花色扩展对应(古典四元素学说链:性质/体液/气质/感官/时辰/节气点/四字母/四界/斯芬克斯四力/大天使/四活物/元素灵)。
export const SUIT_EXTENDED = {
	wands: { quality: '热+干', humor: '黄胆汁', temperament: '胆汁质(奋发)', sense: '视', hour: '正午', festival: '夏至', letter: 'Yod', world: 'Atziluth 原型界', power: '意志 Velle', archangel: 'Michael', creature: '狮', elemental: '火精 Salamander' },
	cups: { quality: '冷+湿', humor: '黏液', temperament: '黏液质(沉静)', sense: '味', hour: '日落', festival: '秋分', letter: 'Heh', world: 'Briah 创造界', power: '敢为 Audere', archangel: 'Gabriel', creature: '鹰', elemental: '水精 Undine' },
	swords: { quality: '热+湿', humor: '血液', temperament: '多血质(活跃)', sense: '嗅', hour: '黎明', festival: '春分', letter: 'Vav', world: 'Yetzirah 形成界', power: '知晓 Scire', archangel: 'Raphael', creature: '人/天使', elemental: '风精 Sylph' },
	pentacles: { quality: '冷+干', humor: '黑胆汁', temperament: '抑郁质(沉稳)', sense: '触', hour: '午夜', festival: '冬至', letter: 'Heh(末)', world: 'Assiah 行动界', power: '缄默 Tacere', archangel: 'Auriel', creature: '牛', elemental: '地精 Gnome' },
};

// 数字 1-10 元数据:行星(托勒密天球序)/几何/辩证(开端·对立·平衡两级嵌套)/旬相(上升·续座·下降)。
export const NUMBER_META = {
	1: { planet: '原动天', geometry: '点(单子)', papus: '开端之开端', phase: null },
	2: { planet: '黄道带', geometry: '线(二元)', papus: '开端之对立', phase: '上升(初发)' },
	3: { planet: 'Saturn', geometry: '三角(面)', papus: '开端之平衡', phase: '续座(全盛)' },
	4: { planet: 'Jupiter', geometry: '四方(体)', papus: '对立之开端', phase: '下降(收变)' },
	5: { planet: 'Mars', geometry: '五角星', papus: '对立之对立', phase: '上升(初发)' },
	6: { planet: 'Sun', geometry: '六芒星', papus: '对立之平衡', phase: '续座(全盛)' },
	7: { planet: 'Venus', geometry: '七芒星', papus: '平衡之开端', phase: '下降(收变)' },
	8: { planet: 'Mercury', geometry: '八芒星', papus: '平衡之对立', phase: '上升(初发)' },
	9: { planet: 'Moon', geometry: '九芒星', papus: '平衡之平衡', phase: '续座(全盛)' },
	10: { planet: 'Earth', geometry: '十点阵', papus: '循环归元', phase: '下降(收变)' },
};

// 星座三态模式(本位/固定/变动)与行星主题词/星座性情词(归组主题线用,原创短语)。
export const SIGN_MODE = {
	Aries: '本位', Cancer: '本位', Libra: '本位', Capricorn: '本位',
	Leo: '固定', Scorpio: '固定', Aquarius: '固定', Taurus: '固定',
	Sagittarius: '变动', Pisces: '变动', Gemini: '变动', Virgo: '变动',
};
export const PLANET_THEME = {
	Saturn: '限制/边界/时间', Jupiter: '扩张/机遇/幸运', Mars: '激烈/切割/勇进', Sun: '创造/自我/成功',
	Venus: '吸引/和合/美', Mercury: '沟通/思辨/往来', Moon: '流变/直觉/滋养',
};
export const SIGN_BRIEF = {
	Aries: '冲动开拓', Taurus: '沉稳固执', Gemini: '多才善言', Cancer: '护巢重情',
	Leo: '张扬慷慨', Virgo: '勤谨挑剔', Libra: '权衡重谊', Scorpio: '专注隐深',
	Sagittarius: '坦率尚自由', Capricorn: '谨慎善谋', Aquarius: '博爱独行', Pisces: '敏感可塑',
};

// 古典行星尊贵表(庙/陷/旺/弱;传统占星公有口径)。
export const PLANET_DIGNITY = {
	Saturn: { domicile: ['Capricorn', 'Aquarius'], detriment: ['Cancer', 'Leo'], exaltation: 'Libra', fall: 'Aries' },
	Jupiter: { domicile: ['Sagittarius', 'Pisces'], detriment: ['Gemini', 'Virgo'], exaltation: 'Cancer', fall: 'Capricorn' },
	Mars: { domicile: ['Aries', 'Scorpio'], detriment: ['Libra', 'Taurus'], exaltation: 'Capricorn', fall: 'Cancer' },
	Sun: { domicile: ['Leo'], detriment: ['Aquarius'], exaltation: 'Aries', fall: 'Libra' },
	Venus: { domicile: ['Taurus', 'Libra'], detriment: ['Scorpio', 'Aries'], exaltation: 'Pisces', fall: 'Virgo' },
	Mercury: { domicile: ['Gemini', 'Virgo'], detriment: ['Sagittarius', 'Pisces'], exaltation: 'Virgo', fall: 'Pisces' },
	Moon: { domicile: ['Cancer'], detriment: ['Capricorn'], exaltation: 'Taurus', fall: 'Scorpio' },
};

// 数字牌旬星尊贵:decanPlanet 在 decanSign 的庙旺陷弱标注(无则 null)。
export function pipDignity(card){
	if(!card || card.court || !card.decanPlanet || !card.decanSign){ return null; }
	const d = PLANET_DIGNITY[card.decanPlanet];
	if(!d){ return null; }
	if(d.domicile.includes(card.decanSign)){ return { status: 'domicile', label: '入庙(本垣得力)' }; }
	if(d.exaltation === card.decanSign){ return { status: 'exaltation', label: '入旺(高扬得势)' }; }
	if(d.detriment.includes(card.decanSign)){ return { status: 'detriment', label: '入陷(客乡失势)' }; }
	if(d.fall === card.decanSign){ return { status: 'fall', label: '入弱(沉降受抑)' }; }
	return null;
}

// 占星值 → 大牌 sid 反查(行星/星座各一张;元素型不参与)。
const MAJOR_BY_ASTRO = {};
MAJORS_CORR.forEach((m) => { MAJOR_BY_ASTRO[m.astro] = m.id; });
export function majorSidByAstro(astro){ return MAJOR_BY_ASTRO[astro] || null; }

// 「大牌读小牌」:数字牌 → 其旬星的行星大牌+星座大牌(二连);宫廷 → 跨段两星座大牌;Ace/Page → 象限三星座大牌。
export function decanMajors(card){
	if(!card || isTrumpArcana(card.arcana)){ return null; }
	if(card.court){
		const spans = COURT_SPAN_SIGNS[card.suit] && COURT_SPAN_SIGNS[card.suit][card.court];
		if(!spans){ return null; }
		return { kind: card.court === 'page' ? 'quadrant' : 'span', majors: spans.map((s) => majorSidByAstro(s)).filter(Boolean) };
	}
	if(card.number === 1){
		const signs = ACE_QUADRANT_SIGNS[card.suit] || [];
		return { kind: 'quadrant', majors: signs.map((s) => majorSidByAstro(s)).filter(Boolean) };
	}
	if(card.decanPlanet && card.decanSign){
		return { kind: 'decan', majors: [majorSidByAstro(card.decanPlanet), majorSidByAstro(card.decanSign)].filter(Boolean) };
	}
	return null;
}

// 星座日期段(由 36 旬日期派生,单一真值不另立日期表):起=该星座首旬起,止=末旬止。
const SIGN_DATE_CACHE = {};
export function signDateRange(sign){
	if(SIGN_DATE_CACHE[sign] !== undefined){ return SIGN_DATE_CACHE[sign]; }
	let start = null;
	let end = null;
	SUITS.forEach((suit) => {
		Object.keys(DECAN[suit]).forEach((rank) => {
			const [, , dSign] = DECAN[suit][rank];
			if(dSign !== sign){ return; }
			const dd = DECAN_DATE[suit][rank];
			if(!dd){ return; }
			const [a, b] = dd.split('~');
			// 旬序内此星座的三旬:rank%3==2 为首旬(2/5/8),==1 为末旬(4/7/10)
			const r = Number(rank);
			if(r === 2 || r === 5 || r === 8){ start = a; }
			if(r === 4 || r === 7 || r === 10){ end = b; }
		});
	});
	const out = start && end ? `${start}~${end}` : null;
	SIGN_DATE_CACHE[sign] = out;
	return out;
}

// 生命树:质点 m↔n 之间的大牌路径。直连=返回该大牌;无直连=BFS 全部最短路(可多解),每跳带 {sid, from, to}。
export function pathsBetween(m, n, variant){
	if(!(m >= 1 && m <= 10 && n >= 1 && n <= 10) || m === n){ return []; }
	const edges = [];
	MAJORS_CORR.forEach((mc) => {
		const j = pathJoin(mc.id, variant);
		if(j){ edges.push({ sid: mc.id, a: j[0], b: j[1] }); }
	});
	const adj = {};
	edges.forEach((e) => {
		(adj[e.a] = adj[e.a] || []).push({ to: e.b, sid: e.sid });
		(adj[e.b] = adj[e.b] || []).push({ to: e.a, sid: e.sid });
	});
	// BFS 层级 + 回溯全部最短路
	const dist = { [m]: 0 };
	const prev = {}; // node -> [{from, sid}]
	let frontier = [m];
	while(frontier.length && dist[n] === undefined){
		const next = [];
		frontier.forEach((u) => {
			(adj[u] || []).forEach(({ to, sid }) => {
				if(dist[to] === undefined){ dist[to] = dist[u] + 1; next.push(to); }
				if(dist[to] === dist[u] + 1){ (prev[to] = prev[to] || []).push({ from: u, sid }); }
			});
		});
		frontier = next;
	}
	if(dist[n] === undefined){ return []; }
	const routes = [];
	const walk = (node, acc) => {
		if(node === m){ routes.push(acc.slice().reverse()); return; }
		(prev[node] || []).forEach(({ from, sid }) => walk(from, acc.concat({ sid, from, to: node })));
	};
	walk(n, []);
	return routes;
}
