// 吠陀世运(古籍吠陀篇)。全程恒星黄道 + Lahiri 差值(可选 Raman)。
// L1 年度盘(梅沙入境求根/季盘/Muntha) L2 年之九主 L3 世运 Vimshottari
// L4 KP 副主 L5 二十七宿 L6 天气农业(云之孕/七潮盘/物价) L7 过境/分野。
// 显示层零章节号;九主出处按古籍纠错注明(后世历书传统,非某一原典);
// Kūrma 分野沿用中性数据政策(学术参考·非现实地缘断言)。

// 单模归一:x∈[0,360) 时 % 恒等零浮点损失;双模 ((x%360)+360)%360 会在宿界精确点
// (如 13°20′=NAK_WIDTH 整倍数)丢 1ulp → floor 除法宿序错位(与后端落宫双模坑同款)。
const norm360 = (x) => { const r = x % 360; return r < 0 ? r + 360 : r; };
const fwd = (from, to) => norm360(to - from);

// ── 星期主(vāra,固定)──
export const VARA_LORDS = ['sun', 'moon', 'mars', 'mercury', 'jupiter', 'venus', 'saturn'];   // 日..六
export const PLANET_CN_V = { sun: '日', moon: '月', mars: '火', mercury: '水', jupiter: '木', venus: '金', saturn: '土', rahu: '罗睺', ketu: '计都' };
const BENEFIC = ['jupiter', 'venus', 'mercury'];

// ── L2 年之九主(各职=该事件所在星期之主;事件=恒星入境/入宿/阴历年首)──
// 出处纠错(古籍明确):九主不出自某一原典,属后世历书传统 → UI 须注明(中性表述)。
// 完整历书另有约 21 子职(共约 30)——古籍未给全表,只做九主并标注。
export const NAVANAYAKA_OFFICES = [
	{ key: 'raja', cn: '王', event: 'lunar_new_year', eventCn: '阴历年首朔日', domain: '全年总基调、统治者、国运' },
	{ key: 'mantri', cn: '相', event: 'ingress_0', eventCn: '太阳入恒星白羊（阳历年首）', domain: '行政、内阁、治理' },
	{ key: 'senadhipati', cn: '军帅', event: 'ingress_120', eventCn: '太阳入恒星狮子', domain: '国防、军队、治安' },
	{ key: 'sasyadhipati', cn: '田主', event: 'ingress_90', eventCn: '太阳入恒星巨蟹', domain: '田间庄稼、收成' },
	{ key: 'dhanyadhipati', cn: '谷主', event: 'ingress_240', eventCn: '太阳入恒星射手', domain: '谷物、存粮' },
	{ key: 'arghadhipati', cn: '价主', event: 'ingress_60', eventCn: '太阳入恒星双子', domain: '物价、生活成本' },
	{ key: 'meghadhipati', cn: '云主', event: 'ingress_ardra', eventCn: '太阳入井宿区（雨季起点之宿）', domain: '云、降雨' },
	{ key: 'rasadhipati', cn: '汁主', event: 'ingress_180', eventCn: '太阳入恒星天秤', domain: '油、糖、盐、汁液类' },
	// 🔴 yearOffset=1:吠陀太阳年自梅沙(白羊)入境起,摩羯入境(01-14)落在**次一公历年**才属
	// 同一 samvatsara;曾与其余八职同传 year → 取到梅沙年首之前 3 个月的那次,归属上一年度。
	{ key: 'nirasadhipati', cn: '干主', cnVariant: '堡主', event: 'ingress_270', yearOffset: 1, eventCn: '太阳入恒星摩羯（属本年度，公历落次年 1 月）', domain: '金属、宝石、矿、干货（堡变体=要塞）' },
];
export const NAVANAYAKA_NOTES = [
	'日月为王相之吉星;火星为常任军帅本色。',
	'同一行星兼王与相 → 全年统治者受困、火盗之灾。一星可兼数职。',
	'吉星(木金水)任职 → 该领域佳;凶星(土火日)任职 → 歉收/灾难倾向。',
	'价主为日 → 物价跌;为月/水 → 涨。汁主为月 → 油糖涨;为日 → 跌。',
	'九主属后世历书传统(非出自某一原典);完整历书另有约 21 子职,此处只列九主。',
];

// 事件目标恒星黄经(井宿区起点=第 6 宿起度 66°40′)。
const EVENT_TARGET = { ingress_0: 0, ingress_60: 60, ingress_90: 90, ingress_120: 120, ingress_180: 180, ingress_240: 240, ingress_270: 270, ingress_ardra: 66 + 40 / 60 };

// 恒星入境求根(牛顿迭代;lahiri,恒星黄道直读)。approxDay=入境近似日(种子)。
const APPROX_DAY = { ingress_0: '04-14', ingress_60: '06-15', ingress_90: '07-16', ingress_120: '08-17', ingress_180: '10-17', ingress_240: '12-16', ingress_270: '01-14', ingress_ardra: '06-22' };


// 星期主:当地日历日 → vāra 之主。
export function varaLordOf(momentStr){
	const d = new Date(String(momentStr).replace(/-/g, '/'));
	if(isNaN(d.getTime())){ return null; }
	return VARA_LORDS[d.getDay()];
}

// L2 主计算:9 事件求根 → 各职行星 + 兼职冲突 + 口诀判读。
// 阴历年首(王):取梅沙入境前最近一次新月(近似口径,卡内注明)。
// ── L3 世运 Vimshottari ──
export const VIMSHOTTARI_SEQ = [
	{ key: 'ketu', years: 7 }, { key: 'venus', years: 20 }, { key: 'sun', years: 6 },
	{ key: 'moon', years: 10 }, { key: 'mars', years: 7 }, { key: 'rahu', years: 18 },
	{ key: 'jupiter', years: 16 }, { key: 'saturn', years: 19 }, { key: 'mercury', years: 17 },
];
export const VIMSHOTTARI_MUNDANE_MEANINGS = {
	sun: '政府、元首、威望', moon: '民众、粮食、舆情', mars: '军事、战争、火灾',
	mercury: '贸易、媒体、交通、条约', jupiter: '司法、宗教、金融、扩张', venus: '财富、艺术、外交、和平',
	saturn: '劳工、农矿、紧缩、重构、艰难', rahu: '瘟疫、外事、突变、丑闻', ketu: '瘟疫、通胀、分离、突发',
};
const NAK_WIDTH = 13 + 20 / 60;   // 13°20′ = 800′

// 起运:恒星月亮黄经 → 宿主与余额;yearLen 360|365.2425(分歧→选项)。
export function vimshottariFromMoon(sidMoonLon, startDateStr, yearLen){
	const lon = norm360(sidMoonLon);
	const nakIdx = Math.floor(lon / NAK_WIDTH);            // 0..26
	const lordIdx = nakIdx % 9;
	const inMin = (lon - nakIdx * NAK_WIDTH) * 60;         // 入宿分(0..800)
	const balanceRatio = (800 - inMin) / 800;
	const seq = [];
	const dayMs = 86400000 * (yearLen === 360 ? 360 / 365.2425 : 1);   // 以公历日推进,360 制按比例缩
	let cursor = new Date(String(startDateStr).replace(/-/g, '/')).getTime();
	for(let i = 0; i < 9; i++){
		const p = VIMSHOTTARI_SEQ[(lordIdx + i) % 9];
		const spanYears = i === 0 ? p.years * balanceRatio : p.years;
		const from = new Date(cursor);
		cursor += spanYears * 365.2425 * dayMs;
		const to = new Date(cursor);
		// 子期:按 (子主年/120)×大期年,自本主起循环。
		const subs = [];
		let subCursor = from.getTime();
		for(let j = 0; j < 9; j++){
			const sp = VIMSHOTTARI_SEQ[(lordIdx + i + j) % 9];
			const subYears = (sp.years / 120) * spanYears;
			const sFrom = new Date(subCursor);
			subCursor += subYears * 365.2425 * dayMs;
			subs.push({ key: sp.key, cn: PLANET_CN_V[sp.key], fromYear: sFrom.getFullYear(), toYear: new Date(subCursor).getFullYear() });
		}
		seq.push({ key: p.key, cn: PLANET_CN_V[p.key], years: p.years, spanYears, fromYear: from.getFullYear(), toYear: to.getFullYear(), meaning: VIMSHOTTARI_MUNDANE_MEANINGS[p.key], subs });
	}
	return { nakIdx, lordKey: VIMSHOTTARI_SEQ[lordIdx].key, balanceRatio, periods: seq };
}

// ── L4 KP 副主(243=27×9;arc=(主年/120)×800′;半开区间;卜卦号 249 仅查表非除数)──
export function kpSubLordAt(sidLon){
	const lon = norm360(sidLon);
	const nakIdx = Math.floor(lon / NAK_WIDTH);
	const starLord = VIMSHOTTARI_SEQ[nakIdx % 9];
	const offMin = (lon - nakIdx * NAK_WIDTH) * 60;   // 宿内分
	let acc = 0;
	for(let i = 0; i < 9; i++){
		const p = VIMSHOTTARI_SEQ[(nakIdx % 9 + i) % 9];
		const arcMin = (p.years / 120) * 800;
		if(offMin >= acc && offMin < acc + arcMin){
			return { nakIdx, starLord: starLord.key, subLord: p.key, subIndex: nakIdx * 9 + i };
		}
		acc += arcMin;
	}
	return { nakIdx, starLord: starLord.key, subLord: VIMSHOTTARI_SEQ[(nakIdx % 9 + 8) % 9].key, subIndex: nakIdx * 9 + 8 };
}
export const KP_NOTES = [
	'层级:座 → 宿主(场域) → 副主(定成败) → 子副。',
	'宫始副主示该宫事组 → 许诺;示其否定组 → 否决。应期在示因星之大/子/孙期。',
	'示因四步:居宫星之宿主 → 居宫星 → 宫主之宿主 → 宫主。合相容 3°20′。',
	'世运用法系现代移植(机制套至国家/事件/入境/会合盘),非原典官方口径。',
];

// ── L5 二十七宿(要点宿标注;第 28 宿仅入七潮盘,不入 Vimshottari/KP)──
export const NAKSHATRA_27 = ['娄宿区', '胃宿区', '昴宿区', '毕宿区', '觜宿区', '井宿区', '鬼宿区', '柳宿区', '星宿区', '张宿区', '翼宿区', '轸宿区', '角宿区', '亢宿区', '氐宿区', '房宿区', '心宿区', '尾宿区', '箕宿区', '斗宿区', '牛宿区', '女宿区', '虚宿区', '危宿区', '室宿区', '壁宿区', '奎宿区'];
export const NAK_KEYPOINTS = {
	3: '关键雨兆之宿', 5: '风暴/季风起点之宿', 14: '风暴·贸易·独立之宿', 18: '根基动荡之宿', 19: '水云受孕之宿',
};

// ── L6 天气与农业 ──
export const GARBHA_CONST = { gestationDays: 195, note: '云之孕:自月入水云受孕之宿起观(约 11–12 月,日在射手);孕期固定 195 日,月回受孕宿之日降雨——白半孕→黑半产,正午孕→午夜产,间隔皆 195 日。' };
export const GARBHA_OMENS = { good: '孕兆吉:柔风、日月白晕、浓黑云、虹、雷电;吉星会照 → 丰沛好雨。', bad: '凶星与日/月同度 → 冰雹烈雷。' };
export function garbhaDeliveryDate(conceptionDateStr){
	const ms = new Date(String(conceptionDateStr).replace(/-/g, '/')).getTime();
	if(isNaN(ms)){ return null; }
	const d = new Date(ms + GARBHA_CONST.gestationDays * 86400000);
	const pad = (n) => (n < 10 ? '0' + n : '' + n);
	return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

// 七潮盘:自昴宿区(第 3 宿)起、28 宿(含第 28 宿)蛇行入 7 列。
export const SAPTA_NADI_COLS = [
	{ key: 'canda', cn: '烈风潮', tone: 'dry' }, { key: 'vayu', cn: '多风潮', tone: 'dry' }, { key: 'dahana', cn: '燥热潮', tone: 'dry' },
	{ key: 'saumya', cn: '和润潮(木)', tone: 'wet' }, { key: 'nira', cn: '水润潮(金)', tone: 'wet' }, { key: 'jala', cn: '流水潮(水)', tone: 'wet' }, { key: 'amrta', cn: '甘霖潮(月·大雨)', tone: 'wet' },
];
export function buildSaptaNadi(){
	// 28 宿(27+第28 宿,插于斗牛之间=索引 20 后)自第 3 宿(昴)起蛇行:0..6,6..0,…
	const names28 = [...NAKSHATRA_27.slice(0, 21), '第廿八宿', ...NAKSHATRA_27.slice(21)];
	const startIdx = 2;   // 昴宿区
	const cols = SAPTA_NADI_COLS.map(() => []);
	for(let i = 0; i < 28; i++){
		const nak = names28[(startIdx + i) % 28];
		const round = Math.floor(i / 7);
		const pos = i % 7;
		const col = (round % 2 === 0) ? pos : 6 - pos;
		cols[col].push(nak);
	}
	return cols;
}
export const SAPTA_NADI_READING = '水性主星(金水月木)聚雨潮列 → 好季风;聚风/热列 → 旱。';

// 物价(古籍仅给金例+通则,不扩表):
export const ARGHA_RULES = {
	commodities: [{ cn: '金', signs: ['aries', 'capricorn'] }],
	rule: '火/土行于商品座之第 3/6/10/11 宫(自商品座起数) → 该商品涨;新/满月日逢凶兆(食/彗/晕/异象) → 物价涨,他日 → 主战;歉收(孕败/旱) → 价高。',
};

// ── L7 过境/分野 ──
export const TRANSIT_RULES = [
	{ cn: '木星过某国之座', span: '约 1 年/座', effect: '该国约 12 个月昌盛' },
	{ cn: '土星过某国之座', span: '约 2.5 年/座', effect: '该国艰难期' },
	{ cn: '土木同宿', span: '—', effect: '要邑受损' },
	{ cn: '火星过境', span: '约 1.5 月/座', effect: '军事紧张' },
	{ cn: '交点过境', span: '约 18 月/座', effect: '动荡' },
	{ cn: '土星+火星(或食)同入某国之座', span: '—', effect: '复合危机' },
];
export const ECLIPSE_VEDIC_RULES = [
	'受影响地 = 食所在宿/座的龟形分野。',
	'14 日内两食 → 暗杀/战争之兆。日食影响约 1 小时 1 年;及食前后 6 个月与食路所经国。',
	'彗星:可见几日 → 应验几月,越 3 周起效。',
];
// 龟形分野(现代座级表,古籍仅给数例——只录已给,余不臆造;沿用中性数据政策)。
export const KURMA_MODERN = [
	{ sign: 'aries', region: '英伦' }, { sign: 'gemini', region: '北美' }, { sign: 'virgo', region: '南亚次大陆' },
	{ sign: 'libra', region: '日本列岛' }, { sign: 'aquarius', region: '俄地' },
];
export const KURMA_DISCLAIMER = '龟形分野系传统占星学术参考(27 宿九组自中心向四方辐射+现代座级增补),多源各有出入,非任何现实地缘断言;座级表仅录古籍已给数例。';

// Muntha(年进一座):建国上升座 + 盘龄 mod 12。
const SIGN_KEYS_V = ['aries', 'taurus', 'gemini', 'cancer', 'leo', 'virgo', 'libra', 'scorpio', 'sagittarius', 'capricorn', 'aquarius', 'pisces'];
export function munthaSign(natalAscSign, age){
	const i = SIGN_KEYS_V.indexOf(String(natalAscSign || '').toLowerCase());
	if(i < 0 || age == null || age < 0){ return null; }
	return SIGN_KEYS_V[(i + Math.floor(age)) % 12];
}

export default { VARA_LORDS, NAVANAYAKA_OFFICES, NAVANAYAKA_NOTES, varaLordOf, VIMSHOTTARI_SEQ, VIMSHOTTARI_MUNDANE_MEANINGS, vimshottariFromMoon, kpSubLordAt, KP_NOTES, NAKSHATRA_27, NAK_KEYPOINTS, GARBHA_CONST, garbhaDeliveryDate, buildSaptaNadi, SAPTA_NADI_COLS, ARGHA_RULES, TRANSIT_RULES, ECLIPSE_VEDIC_RULES, KURMA_MODERN, munthaSign };