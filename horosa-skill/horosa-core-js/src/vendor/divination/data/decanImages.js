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

export function decanImageAt(signId, deg){
	const d = ((deg % 30) + 30) % 30;
	const idx = Math.min(2, Math.floor(d / 10));
	return (DECAN_IMAGES[signId] || [])[idx] || null;
}

export default DECAN_IMAGES;
