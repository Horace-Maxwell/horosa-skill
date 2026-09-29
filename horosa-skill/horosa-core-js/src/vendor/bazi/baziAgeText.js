// 八字岁数显示单源:盘数据里的 direction[].age / 流年岁 / smallDirection[].age 一律是虚岁(出生即 1 岁,
// 本地引擎原生口径;公元前 / 域外年份回退 Java 的结果在取数入口已对齐为虚岁,见 BaZi.js alignJavaBaziAges)。
// 「年龄」档:nominal = 虚岁(默认) / real = 周岁(虚岁 − 1,出生 = 0 岁),与行运面板同一换算。
// 未传档的旧调用方(如反推八字直接读 Java 原始结果,原值即周岁式)→ 原样输出「N + legacySuffix」,行为不变。
export function baziAgeValue(age, ageStyle){
	const n = Number(age);
	return ageStyle === 'real' ? Math.max(0, n - 1) : n;
}

export function baziAgeText(age, ageStyle, legacySuffix = '周岁'){
	if(age === undefined || age === null || `${age}` === '' || !Number.isFinite(Number(age))){
		return '';
	}
	if(ageStyle === undefined || ageStyle === null || ageStyle === ''){
		return `${age}${legacySuffix}`;
	}
	return ageStyle === 'real' ? `${baziAgeValue(age, ageStyle)}周岁` : `${baziAgeValue(age, ageStyle)}岁`;
}
