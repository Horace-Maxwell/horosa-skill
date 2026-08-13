// 宫廷牌多体系(TP7):元素两套/星座两套/年龄档/外貌色系/骑士行旅/伴牌触发星座检测/人物-事件双解规则。
// 皆为传统占验口径的原创中文转述;默认档=现行 GD 口径,零回归。
import { SUIT_ELEMENT, ELEMENT_CN, SIGN_CN } from './correspondences.js';

// 位阶元素两套:gd=现行「元素中元素」(courtEie 已带);alt=位阶制(王=土/后=水/骑=火/侍=风)。
export const COURT_RANK_ELEMENT_ALT = { king: 'earth', queen: 'water', knight: 'fire', page: 'air' };
export function courtEieOf(card, system){
	if(!card || !card.court){ return null; }
	if(system !== 'alt'){ return card.courtEie || null; }
	const suitEl = ELEMENT_CN[SUIT_ELEMENT[card.suit]] || '';
	const rankEl = ELEMENT_CN[COURT_RANK_ELEMENT_ALT[card.court]] || '';
	return `${suitEl}中之${rankEl}(位阶制)`;
}

// 宫廷星座两套:gd_span=现行跨段(courtSpan 已带);simple=单座制(后=本位/王=固定/骑=变动 各守一座;侍无星座)。
export const COURT_ZODIAC_SIMPLE = {
	wands: { king: 'Leo', queen: 'Aries', knight: 'Sagittarius', page: null },
	cups: { king: 'Scorpio', queen: 'Cancer', knight: 'Pisces', page: null },
	swords: { king: 'Aquarius', queen: 'Libra', knight: 'Gemini', page: null },
	pentacles: { king: 'Taurus', queen: 'Capricorn', knight: 'Virgo', page: null },
};
export function courtZodiacOf(card, system){
	if(!card || !card.court){ return null; }
	if(system !== 'simple'){ return card.courtSpan || null; }
	const sign = COURT_ZODIAC_SIMPLE[card.suit] && COURT_ZODIAC_SIMPLE[card.suit][card.court];
	return sign ? `${SIGN_CN[sign]}座(单座制)` : '侍从不配星座(单座制)';
}

// 年龄档(传统粗则,常有出入;性格定牌优先)。
export const COURT_AGE = {
	page: '少年/未熟之人(约22岁以下)', knight: '青年/进取之人(约21-30)',
	queen: '成年女性(约22以上)', king: '成年男性(约30以上)',
};
export const COURT_CHARACTER_NOTE = '指认以「性格」为先:同一人在不同情境可换牌;年龄与性别只是粗则。';

// 外貌色系(传统对照;伴牌花色可微调发色深浅)。
export const COURT_APPEARANCE = {
	wands: '发红/棕,眼蓝或灰', cups: '发棕,眼蓝或淡褐', swords: '发深,眼深', pentacles: '发黑,眼黑',
};
export const COURT_APPEARANCE_NOTE = '旁伴小牌花色可微调:伴钱币趋深、伴权杖趋红。';

// 骑士行旅对照(交通与天气意象)。
export const KNIGHT_VEHICLE = {
	wands: '陆路疾行;天意炎燥', cups: '水路舟行;天意潮润', swords: '飞航疾驰;天意风暴', pentacles: '班车慢行;天意阴稳',
};

// 伴牌触发式星座检测(传统条例的转述):宫廷牌 sid + 同阵伴牌 → 更笃定的星座指认。
const DETECT_RULES = [
	{ court: 'cups_king', companions: ['death'], sign: 'Scorpio' },
	{ court: 'swords_king', companions: ['the_star'], sign: 'Aquarius' },
	{ court: 'swords_king', companions: ['justice', 'the_empress'], sign: 'Libra' },
	{ court: 'swords_king', companions: ['the_lovers'], sign: 'Gemini' },
	{ court: 'swords_knight', companions: ['the_emperor', 'wands_king'], sign: 'Aries' },
	{ court: 'swords_knight', companions: ['the_lovers', 'swords_queen', 'swords_page'], sign: 'Gemini' },
	{ court: 'swords_queen', companions: ['the_hermit'], sign: 'Virgo' },
	{ court: 'cups_page', companions: ['high_priestess'], sign: 'Pisces' },
	{ court: 'pentacles_king', companions: ['the_lovers'], sign: 'Gemini' },
	{ court: 'wands_queen', companions: ['the_emperor'], sign: 'Aries' },
];

// 扫描 draws:每张宫廷牌给出 基础星座(单座制) + 伴牌触发命中 + 年龄/外貌/行旅三则。
// [QA-6] 年龄与外貌两表是四花色×四宫廷体系专有;扑克牌与吉普赛牌另有其宫廷(J/Q/K × 红桃黑桃…),
// 查这两表必落空。此前右栏卡片与快照各自查表、各自把 undefined 拼进文案(「梅花J=undefined;undefined」),
// 病根是同一判断散在两处。此处收敛:凡表中无载者不入此指认(该体系不作此推),三则也一并在此备好,
// 消费点只取结果不再查表 —— 日后新增牌组自动适用,不会再漏一处。
export function courtSignDetect(draws){
	const list = (draws || []).filter((d) => d && d.card);
	const sids = new Set(list.map((d) => d.card.sid));
	return list.filter((d) => d.card.court && COURT_AGE[d.card.court] && COURT_APPEARANCE[d.card.suit]).map((d) => {
		const c = d.card;
		const baseSign = COURT_ZODIAC_SIMPLE[c.suit] && COURT_ZODIAC_SIMPLE[c.suit][c.court];
		const hits = DETECT_RULES
			.filter((r) => r.court === c.sid && r.companions.some((sid) => sids.has(sid)))
			.map((r) => ({ sign: r.sign, signCn: SIGN_CN[r.sign], via: r.companions.filter((sid) => sids.has(sid)) }));
		return {
			sid: c.sid, name: c.name_cn, baseSign, baseSignCn: baseSign ? SIGN_CN[baseSign] : null, hits,
			age: COURT_AGE[c.court], appearance: COURT_APPEARANCE[c.suit],
			vehicle: c.court === 'knight' ? (KNIGHT_VEHICLE[c.suit] || '') : '',
		};
	});
}

// 人物/事件双解 + 建议位/环境位特则(定局宫廷指认卡文案)。
export const COURT_READING_RULES = [
	'宫廷牌先作「人物解」(当事人/相关者/某种性格面),人物解不通再作「事件解」。',
	'落在建议位:正位=宜采此牌作风行事;逆位=勿用此作风;亦可解为「该请教之人」。',
	'落在环境位:指周遭之人或群体气氛正如何影响此事。',
];
