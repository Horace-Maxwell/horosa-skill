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

// 映点（antiscion）：力量 ≈ 六合/三合（构建清单 §1.4「Position」段）。
export const ANTISCION = { cn: '映点', en: 'antiscion', strength: 'sextile/trine' };

// 单星容许度（moiety，度）。两星相位容许度 = 双方平均（construct §1.4）。
export const PLANET_ORB = {
	sun: 15, moon: 12, mercury: 7, venus: 7, mars: 8, jupiter: 9, saturn: 9,
	uranus: 5, neptune: 5, pluto: 5, north_node: 3, south_node: 3, fortune: 3,
};

// 择日容许度（择日清单 §2.4，可配置）；角点相位仅取 ≤3°。
export const ELECTION_ORBS = {
	luminary: { conj_opp: 8, trine_sextile: 6, square: 6 },
	angle: 3,
	planet: { conj_opp: 7, trine_sextile: 5, square: 5 },
	moonDecisive: 1.5, // 月亮「决定性」门槛
	fixedStar: 1,      // 恒星会合 ≤1°(最多1.5)
	midpoint: 3,
	timing: 1,         // 应期 1°=1 时间单位
};

// 相位优先级（强→弱）：0 > 180 > 90 > 120 > 60（择日 §2.4）
export const ASPECT_PRIORITY = [0, 180, 90, 120, 60];

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
