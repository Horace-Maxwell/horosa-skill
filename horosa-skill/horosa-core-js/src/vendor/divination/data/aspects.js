// divination/data/aspects.js
// 五个古典相位 + 映点；容许度（古典 moiety / 光体半径制，可配置）。
// 来源：卜卦构建清单 §1.4 + 择日清单 §2.4。

export const ASPECTS = {
	conjunction: { id: 'conjunction', cn: '合相', en: 'conjunction', angle: 0, nature: 'neutral', symbol: '☌' },
	sextile: { id: 'sextile', cn: '六合', en: 'sextile', angle: 60, nature: 'benefic', symbol: '⚹' },
	square: { id: 'square', cn: '四分', en: 'square', angle: 90, nature: 'malefic', symbol: '□' },
	trine: { id: 'trine', cn: '三合', en: 'trine', angle: 120, nature: 'benefic', symbol: '△' },
	opposition: { id: 'opposition', cn: '对分', en: 'opposition', angle: 180, nature: 'malefic', symbol: '☍' },
};

export const ASPECT_ANGLES = [0, 60, 90, 120, 180];

// 单星容许度（moiety，度）。两星相位容许度 = 双方平均（construct §1.4）。
export const PLANET_ORB = {
	sun: 15, moon: 12, mercury: 7, venus: 7, mars: 8, jupiter: 9, saturn: 9,
	uranus: 5, neptune: 5, pluto: 5, north_node: 3, south_node: 3, fortune: 3,
};

export function aspectByAngle(angle){
	const a = Math.round(angle);
	return Object.values(ASPECTS).find((x) => x.angle === a) || null;
}

// 两星合相容许度（取 moiety 平均）
export function pairOrb(a, b){
	const oa = PLANET_ORB[a] !== undefined ? PLANET_ORB[a] : 6;
	const ob = PLANET_ORB[b] !== undefined ? PLANET_ORB[b] : 6;
	return (oa + ob) / 2;
}

export default ASPECTS;
