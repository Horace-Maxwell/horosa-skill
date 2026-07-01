// 塔罗对应体系——纯事实型对照表(占星/希伯来字母/生命树路径/旬星 Lord/宫廷黄道度数/各派命名/元素友敌)。
// 这些是公有领域的体系事实(非受版权保护),据古典对应体系(Golden Dawn Book T 1888、传统占星界系)落数据。
// 单一真值源:大牌/小牌/宫廷的对应叠层与各流派命名皆出自此,供 cardSchema.display_name / astro_line 消费。

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
