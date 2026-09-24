// 世运盘 WP-6 地区盘推运(§11.2):纯前端可算的两法——小限 Profections + 法达 Firdaria。
// 以地区盘(建置/政权宣告时刻)为基准,age = 目标年 − 建置年。返照/次限走后端(见 MundaneMain)。

const SIGN_ORDER = ['aries', 'taurus', 'gemini', 'cancer', 'leo', 'virgo', 'libra', 'scorpio', 'sagittarius', 'capricorn', 'aquarius', 'pisces'];
const SIGN_CN = { aries: '白羊', taurus: '金牛', gemini: '双子', cancer: '巨蟹', leo: '狮子', virgo: '室女', libra: '天秤', scorpio: '天蝎', sagittarius: '射手', capricorn: '摩羯', aquarius: '宝瓶', pisces: '双鱼' };
// 古典七曜庙主(与盘面 SIGNS[key].domicile 一致)。
const SIGN_LORD = { aries: 'mars', taurus: 'venus', gemini: 'mercury', cancer: 'moon', leo: 'sun', virgo: 'mercury', libra: 'venus', scorpio: 'mars', sagittarius: 'jupiter', capricorn: 'saturn', aquarius: 'saturn', pisces: 'jupiter' };
const PLANET_CN = { sun: '太阳', moon: '月亮', mercury: '水星', venus: '金星', mars: '火星', jupiter: '木星', saturn: '土星', northnode: '北交', southnode: '南交' };
// 各宫世俗主题(简,与 describe MUNDANE_HOUSE 同口径)。
const HOUSE_THEME = {
	1: '民众/局势总貌', 2: '财政/经济/货币', 3: '通讯/交通/邻国', 4: '辖境/在野派/收成', 5: '生育/文体/投机', 6: '公共卫生/劳工/军需',
	7: '外交/战和/公敌', 8: '死亡率/债务/危机', 9: '宗教/司法/外贸', 10: '政府/当局/运势', 11: '立法/盟友/改革', 12: '监狱/暗敌/隐患',
};

export { SIGN_ORDER as MUNDANE_PROG_SIGN_ORDER, SIGN_CN as MUNDANE_SIGN_CN, PLANET_CN as MUNDANE_PROG_PLANET_CN };

// §11.2 小限 Profections(整宫制):每年上升前进一整座,12 年一轮。
export function mundaneProfection(ascSignKey, age) {
	const i0 = SIGN_ORDER.indexOf(ascSignKey);
	if (i0 < 0 || !(age >= 0)) return null;
	const a = Math.floor(age);
	const step = ((a % 12) + 12) % 12;
	const signIdx = (i0 + step) % 12;
	const sign = SIGN_ORDER[signIdx];
	const house = step + 1;                       // 激活宫(从1宫起)
	const lord = SIGN_LORD[sign];
	// 月小限:以年小限座为起点,每月进一座
	const months = [];
	for (let m = 0; m < 12; m++) {
		const ms = SIGN_ORDER[(signIdx + m) % 12];
		months.push({ month: m + 1, sign: ms, signCn: SIGN_CN[ms], lord: SIGN_LORD[ms], lordCn: PLANET_CN[SIGN_LORD[ms]] });
	}
	return {
		age: a, step,
		profectedSign: sign, profectedSignCn: SIGN_CN[sign],
		activatedHouse: house, houseTheme: HOUSE_THEME[house],
		lord, lordCn: PLANET_CN[lord],
		months,
	};
}

// §11.2 法达 Firdaria:昼/夜定序,七政合 70 年(+南北交 5 = 75);每行星大期再七分子期。
const FIRDARIA_DAY = [['sun', 10], ['venus', 8], ['mercury', 13], ['moon', 9], ['saturn', 11], ['jupiter', 12], ['mars', 7], ['northnode', 3], ['southnode', 2]];
const FIRDARIA_NIGHT = [['moon', 9], ['saturn', 11], ['jupiter', 12], ['mars', 7], ['sun', 10], ['venus', 8], ['mercury', 13], ['northnode', 3], ['southnode', 2]];

export function mundaneFirdaria(sect, age) {
	if (!(age >= 0)) return null;
	const isNight = (sect === 'night');
	const seq = isNight ? FIRDARIA_NIGHT : FIRDARIA_DAY;
	const planetSeq = seq.filter((x) => x[0] !== 'northnode' && x[0] !== 'southnode').map((x) => x[0]); // 7 政,供子期循环
	// 75 年一轮,超出取模
	const a = age % 75;
	let acc = 0, major = null, majorStart = 0;
	for (let i = 0; i < seq.length; i++) {
		if (a < acc + seq[i][1] || i === seq.length - 1) { major = seq[i]; majorStart = acc; break; }
		acc += seq[i][1];
	}
	const majorKey = major[0], majorYears = major[1];
	const isNode = (majorKey === 'northnode' || majorKey === 'southnode');
	let sub = null;
	if (!isNode) {
		// 子期:自大期主星起,按七政序循环 7 段,每段 majorYears/7
		const subLen = majorYears / 7;
		const startIdx = planetSeq.indexOf(majorKey);
		const within = a - majorStart;
		const subPos = Math.min(6, Math.floor(within / subLen));
		const subKey = planetSeq[(startIdx + subPos) % 7];
		sub = { planet: subKey, planetCn: PLANET_CN[subKey], years: Math.round(subLen * 100) / 100, index: subPos + 1 };
	}
	return {
		sect: isNight ? 'night' : 'day', sectCn: isNight ? '夜生' : '昼生',
		ageInCycle: Math.round(a * 100) / 100,
		major: { planet: majorKey, planetCn: PLANET_CN[majorKey], years: majorYears, start: majorStart, end: majorStart + majorYears, isNode },
		sub,
		sequence: seq.map((x) => ({ planet: x[0], planetCn: PLANET_CN[x[0]], years: x[1] })),
	};
}
