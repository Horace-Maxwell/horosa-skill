// 岁差大年与时代(古籍时代篇)。纯前端常量+派生:岁差周期/柏拉图月/时代逆行/边界三法/
// 各家定年统计表。key 与显示层一律中性化(方法描述,零人名——项目铁律);
// Fagan/Bradley·Lahiri 为公开天文差值体系技术名词,可显示。
// ayanamsa 用锚点+线性率近似(世纪级误差角秒量级,卡内注明;golden 锚:
// Fagan 1950=24°02′31″、Lahiri 1900=22°27′38″/2000≈23°51′)。

export const GREAT_YEAR_CONST = {
	precessionYears: 25772,          // 岁差周期(大年)
	roundedYears: 25920,             // 常圆整值(被 12 整除)
	platonicMonthYears: [2148, 2160], // 柏拉图月(一个时代)区间
	rateArcsecPerYear: 50.29,        // 岁差率 ″/yr(西退)
};

// 时代逆行序(春分点西退):…金牛→白羊→双鱼→宝瓶…
export const AGE_SEQUENCE_NOTE = '时代逆行:金牛(约前4000–2000)→白羊(约前2000–公元初)→双鱼(公元初至今)→宝瓶(将至)。';

// 边界三法。
export const AGE_BOUNDARY_METHODS = [
	{ key: 'equal', cn: '等分 30°', how: '黄道十二等份(按古典定型时星座名),春分点退过 330° 即入宝瓶', boundary: '随所选差值体系推得(恒星锚等分口径约 2376)', users: '多数西方占星实务' },
	{ key: 'iau', cn: '天文实界', how: '1930 年国际天文学界 88 星座实际边界(大小不一)', boundary: '约 2597 CE(≈2600,春分点过双鱼/宝瓶实界)', users: '天文学界', boundaryYear: 2597 },
	{ key: 'star_anchor', cn: '恒星标定', how: '锚定亮星量分点', boundary: '角宿一锚 → 2376;轩辕十四 2012 入室女 → 2012', users: '恒星派 / 象征派', anchors: [{ key: 'spica', cn: '角宿一锚', year: 2376 }, { key: 'regulus', cn: '轩辕十四锚', year: 2012 }] },
];

// 宝瓶座时代各家定年(公开统计口径,区间 1447–3597;key 中性化=起年,依据列写方法不写人名)。
export const AGE_CLAIMS = [
	{ key: 'claim_1447', year: '1447', basis: '黎明/子周期推算(最早提案)' },
	{ key: 'claim_1844', year: '约 1844', basis: '十度分段法推算' },
	{ key: 'claim_1957', year: '1957-10-04', basis: '以人造卫星首发为象征纪元' },
	{ key: 'claim_1962', year: '1962-02-04', basis: '当日宝瓶群星会聚+日食' },
	{ key: 'claim_1997', year: '约 1997–2154', basis: '春分点出双鱼(深度心理学派著述)' },
	{ key: 'claim_2012', year: '2012', basis: '王者星轴恒星逻辑(轩辕十四入室女)' },
	{ key: 'claim_2020', year: '2020-12-21', basis: '木土合 0° 宝瓶于冬至' },
	{ key: 'claim_2376', year: '2376', basis: '角宿一锚(恒星派量分点等分)' },
	{ key: 'claim_2597', year: '2597', basis: '天文实界(春分点过双鱼/宝瓶边界)' },
	{ key: 'claim_3573', year: '3573', basis: '等分 2160 年(双鱼时代自 1413 起算)' },
	{ key: 'claim_3597', year: '3597', basis: '谐波/等分推算(最晚提案)' },
];
export const AGE_CLAIMS_RANGE = '1447–3597 CE(以 20 世纪提案最多)';
export const TIDAL_NOTE = '「潮汐渐变」说:时代无确切起点,如潮水渐涨——化解边界之争的折中观点。';

// 差值体系(ayanamsa)锚点线性近似。
const AYANAMSA_MODELS = {
	fagan: { cn: 'Fagan/Bradley', epoch: 1950, valueDeg: 24 + 2 / 60 + 31 / 3600, ratePerYear: 50.29 / 3600 },
	lahiri: { cn: 'Lahiri', epoch: 1900, valueDeg: 22 + 27 / 60 + 38 / 3600, ratePerYear: ((23 + 51 / 60) - (22 + 27 / 60 + 38 / 3600)) / 100 },
};

export function ayanamsaAt(year, model){
	const m = AYANAMSA_MODELS[model] || AYANAMSA_MODELS.fagan;
	return m.valueDeg + (year - m.epoch) * m.ratePerYear;
}

const SIGN_KEYS = ['aries', 'taurus', 'gemini', 'cancer', 'leo', 'virgo', 'libra', 'scorpio', 'sagittarius', 'capricorn', 'aquarius', 'pisces'];
const SIGN_CN = { aries: '白羊', taurus: '金牛', gemini: '双子', cancer: '巨蟹', leo: '狮子', virgo: '室女', libra: '天秤', scorpio: '天蝎', sagittarius: '射手', capricorn: '摩羯', aquarius: '宝瓶', pisces: '双鱼' };

// 当前春分点恒星位置与时代:λ_sid(春分点)=360−ayanamsa;落双鱼(330–360)=双鱼时代,
// 退入 <330° 即宝瓶。等分法边界年 = year + (λ−330)×3600/50.29。
export function computeCurrentAge(year, model){
	const ay = ayanamsaAt(year, model);
	const lon = (((360 - ay) % 360) + 360) % 360;
	const signIdx = Math.floor(lon / 30);
	const sign = SIGN_KEYS[signIdx];
	const degInSign = lon % 30;
	const yearsToAquarius = lon >= 330 ? (lon - 330) * 3600 / GREAT_YEAR_CONST.rateArcsecPerYear : 0;
	return {
		ayanamsa: ay, lon, sign, signCn: SIGN_CN[sign], degInSign,
		currentAgeCn: SIGN_CN[sign] + '座时代',
		equalBoundaryYear: lon >= 330 ? Math.round(year + yearsToAquarius) : null,
		inAquarius: lon < 330 && lon >= 300,
	};
}

export default { GREAT_YEAR_CONST, AGE_BOUNDARY_METHODS, AGE_CLAIMS, ayanamsaAt, computeCurrentAge };
