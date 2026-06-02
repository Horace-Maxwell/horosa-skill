// divination/data/dorotheusDegrees.js
// Dorotheus 专项度数/星座表（卜卦 Dorotheus 包 + 择日 §6.15 surgery 共用）。
// Ch18 堕胎危险度数（避免堕胎/取死胎）；Ch37–40 医疗手术宜忌星座。

// 堕胎危险度数（命中=危险，避免堕胎）。[from,to] 黄经度数（座内 0–30）；'all'=全度数。
export const ABORTION_DANGER_DEGREES = {
	aries: [[1, 11]], gemini: 'all', cancer: [[1, 15]], leo: [[1, 11]],
	virgo: 'all', libra: [[11, 30]], scorpio: [[11, 30]], sagittarius: [[1, 11]],
	capricorn: [[1, 15]], aquarius: [[20, 30]],
};

export function isAbortionDangerDegree(signId, deg){
	const rule = ABORTION_DANGER_DEGREES[signId];
	if(!rule) return false;
	if(rule === 'all') return true;
	const d = ((deg % 30) + 30) % 30;
	return rule.some((seg) => d >= seg[0] && d < seg[1]);
}

// Ch37–40 医疗手术宜忌（看上升/月亮所落星座）
export const MEDICAL_ELECTION = {
	exorcism: { // 驱邪
		good: ['aries', 'taurus', 'gemini', 'virgo', 'libra', 'sagittarius', 'capricorn', 'pisces'],
		avoid: ['cancer', 'leo', 'scorpio', 'aquarius'],
		extra: '木/金合月或在 1 宫最佳。',
	},
	emetic_head: { // 催吐/头部用药：月减光，趋上升星座
		good: ['aries', 'taurus'], note: '月减光，在白羊/金牛（上升趋势）。',
	},
	purge_bowel: { // 清肠/腹泻药：月在下降趋势星座
		good: ['libra', 'scorpio'], note: '月在天秤/天蝎（下降趋势）。',
	},
	limb_surgery: { // 肢体手术：月减光、入相吉星
		avoidMoonSigns: ['taurus', 'virgo', 'capricorn', 'pisces'], // 易痉挛
		note: '月减光入相吉星；忌月在对应身体部位星座；忌火星在 1 宫或刑克月亮/1 宫。',
	},
	eye_surgery: { // 眼部手术：月增光提速，木/金合或相月，绝对避火星
		note: '月增光、提速，木/金合相/成相位月亮，绝对避开火星。',
	},
};

export default ABORTION_DANGER_DEGREES;
