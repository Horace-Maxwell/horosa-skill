// divination/data/signFertility.js
// 择日育性四档(播种/理发共用;择日文档口径,与 signs.js 的卜卦三档 fertility 字段并行不混用):
//   最肥沃=水象三座;肥沃=金牛(摩羯宜根茎);半育=天秤/摩羯;不育=白羊/双子/狮子/室女/人马/宝瓶。
export const SIGN_FERTILITY_4 = {
	cancer: 'most_fertile', scorpio: 'most_fertile', pisces: 'most_fertile',
	taurus: 'fertile',
	libra: 'semi_fertile', capricorn: 'semi_fertile',
	aries: 'barren', gemini: 'barren', leo: 'barren', virgo: 'barren', sagittarius: 'barren', aquarius: 'barren',
};

export const FERTILITY_CN = {
	most_fertile: '最肥沃', fertile: '肥沃', semi_fertile: '半育', barren: '不育/干',
};

export const FERTILE_SET = ['cancer', 'scorpio', 'pisces', 'taurus'];          // 播种可用
export const MOST_FERTILE_SET = ['cancer', 'scorpio', 'pisces'];               // 首推
export const BARREN_SET = ['aries', 'gemini', 'leo', 'virgo', 'sagittarius', 'aquarius'];

export function fertilityOf(sign){
	return SIGN_FERTILITY_4[sign] || null;
}

export default SIGN_FERTILITY_4;
