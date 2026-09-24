// 世运盘 WP-2 分布型(§17.1 Jones 七型 + 元素/模式/半球)+ 相位格局(§17.2)世运义。
// 分布/平衡纯前端从 facts.planets 算;相位格局 surfacing 后端 /astroextra/analysis(detect_patterns)。

const SIGN_ORDER = ['aries', 'taurus', 'gemini', 'cancer', 'leo', 'virgo', 'libra', 'scorpio', 'sagittarius', 'capricorn', 'aquarius', 'pisces'];
const SIGN_ELEMENT = { aries: 'fire', leo: 'fire', sagittarius: 'fire', taurus: 'earth', virgo: 'earth', capricorn: 'earth', gemini: 'air', libra: 'air', aquarius: 'air', cancer: 'water', scorpio: 'water', pisces: 'water' };
const SIGN_MODE = { aries: 'cardinal', cancer: 'cardinal', libra: 'cardinal', capricorn: 'cardinal', taurus: 'fixed', leo: 'fixed', scorpio: 'fixed', aquarius: 'fixed', gemini: 'mutable', virgo: 'mutable', sagittarius: 'mutable', pisces: 'mutable' };
const ELEMENT_CN = { fire: '火', earth: '土', air: '风', water: '水' };
const MODE_CN = { cardinal: '基本', fixed: '固定', mutable: '变动' };
// 七曜(古典/中世纪规则集只用此七)+ 外行星(现代/Barbault 加 ♅♆♇)。分布型用真实天体,不含虚点。
const CLASSICAL_KEYS = ['sun', 'moon', 'mercury', 'venus', 'mars', 'jupiter', 'saturn'];
const DIST_KEYS = [...CLASSICAL_KEYS, 'uranus', 'neptune', 'pluto'];

// §17.1 Jones 七型世运义 + 元素/模式偏盛义。
export const DISTRIBUTION_MUNDANE = {
	splash: { cn: '散布型 Splash', text: '诸事并起、议题分散、影响面广而无单一焦点;多元但易失重心。' },
	bundle: { cn: '集束型 Bundle', text: '高度聚焦于单一议题/领域;力量集中、视野偏窄,易走极端。' },
	bowl: { cn: '碗型 Bowl', text: '半盘自足、单向推进;有明确主题阵营与"未竟的另一半"待补。' },
	bucket: { cn: '桶型 Bucket', text: '一柄星为枢纽出口——该星所主之事/人成为全局宣泄口与决策枢轴。' },
	sling: { cn: '投石索型 Sling', text: '紧聚主群+孤柄提把——全局能量经把手星单点掷出,较桶型更聚焦、更具爆发指向。' },
	locomotive: { cn: '火车头型 Locomotive', text: '强劲自驱、目标明确;领头星(开口前缘)定推进方向与动能。' },
	seesaw: { cn: '跷跷板型 Seesaw', text: '两大阵营对峙、议题两极化;在对立中权衡、需调停与平衡。' },
	splay: { cn: '展开型 Splay', text: '数股各行其是的力量各据一方;结构松散、自成派系、难以统一。' },
};
export const ELEMENT_MUNDANE = { fire: '火盛:冲动、战事、能源、行动力强而躁进。', earth: '土盛:务实、财经土地、保守稳定、变革迟缓。', air: '风盛:舆论、外交、通讯思潮活跃、易浮议。', water: '水盛:民情、危机、隐秘、情绪与意识形态主导。' };
export const MODE_MUNDANE = { cardinal: '基本盛:开创、发起、危机即转折,事态推进快。', fixed: '固定盛:稳固、僵持、积重难返,变革阻力大。', mutable: '变动盛:多变、过渡、适应与摇摆,局势流动。' };

// §17.2 相位格局世运义(对应后端 detect_patterns 的 type)。
export const PATTERN_MUNDANE = {
	grand_trine: { cn: '大三角', text: '三方和谐自足之局——某领域顺遂自洽,但易自满停滞、缺推动力。' },
	grand_cross: { cn: '大十字', text: '四正硬相绷紧——多方角力、压力交逼,重大危机或结构性转折。' },
	t_square: { cn: 'T 三角', text: '顶点星(apex)为张力出口——该星所主议题成为冲突焦点与行动驱力。' },
	yod: { cn: '上帝之指 Yod', text: '尖点星被双六分所指——宿命性的调整议题,迫使转向与抉择。' },
	kite: { cn: '风筝', text: '大三角 + 对冲尾星——和谐之局有了发力点与现实出口。' },
	mystic_rectangle: { cn: '神秘矩形', text: '软硬相位交织的稳定张力——在制衡中务实运作、机会与压力并存。' },
	stellium_sign: { cn: '星群(同座)', text: '多星聚一座——该座/宫所主领域成为压倒性焦点,力量集中而偏颇。' },
	stellium_orb: { cn: '紧密星群', text: '多星紧聚一处——高度集中的议题引爆点。' },
	grand_sextile: { cn: '大六角', text: '六星互六分、两套大三角嵌套——罕见的全局机遇平衡之局,资源与助力多方齐备,惟须主动取用方不致虚掷。' },
	cradle: { cn: '摇篮', text: '半盘弧上三连六分承接一组对冲——张力有缓冲与转圜出口,危机可经斡旋逐级化解。' },
};

// withSling:第八型开关。默认 false = 世俗盘既有七型口径零回归;
// true 时先做把手型检测(独立于 g1≥180 门槛——旧口径 bucket 分支 g1≥180∧g2≥60 数学上
// 蕴含主群 span≤120,即全是紧聚提把;宽群+把手会漏到 seesaw/splay):
// ∃星 两侧空档均≥60° 且其余空档全<60°(主群连贯) → span≤120°=sling,否则=bucket。
// 与 Python election_scan._jones_type 双端 fixture 对拍(判据阈值两侧逐字同款,勿单边改)。
export function jonesType(lons, withSling = false) {
	const s = lons.map((x) => (((x % 360) + 360) % 360)).sort((a, b) => a - b);
	const n = s.length;
	if(n < 3){ return null; }
	const gaps = [];
	for(let i = 0; i < n; i++){ gaps.push((i + 1 < n ? s[i + 1] : s[0] + 360) - s[i]); }
	if(withSling && n >= 5){
		for(let i = 0; i < n; i++){
			const a = gaps[(i - 1 + n) % n];
			const b = gaps[i];
			if(Math.min(a, b) < 60){ continue; }
			const rest = gaps.filter((_, j) => j !== i && j !== (i - 1 + n) % n);
			if(rest.length && Math.max(...rest) < 60){
				return (360 - a - b) <= 120 ? 'sling' : 'bucket';
			}
		}
	}
	const sortedG = [...gaps].sort((a, b) => b - a);
	const g1 = sortedG[0], g2 = sortedG[1] || 0;
	if(g1 >= 240){ return 'bundle'; }                 // 占≤120°
	if(g1 >= 180){ return (g2 >= 60) ? 'bucket' : 'bowl'; }   // 占≤180°;第二大空档≥60°(孤柄)→桶
	if(g1 >= 120){ return (g2 >= 90) ? 'seesaw' : 'locomotive'; }   // 占≤240°;两大空档对峙→跷跷板
	if(g1 < 62){ return 'splash'; }                   // 无大空档(≤2 空座)
	return 'splay';
}

// 纯前端:从 facts 算分布型 + 元素/模式/半球平衡。
// allowOuter===false(古典/中世纪规则集)→ 只取七曜,排盘判读真随流派联动;默认含外行星(现代)。
export function mundaneDistribution(facts, allowOuter) {
	if(!facts || !facts.planets){ return null; }
	const P = facts.planets;
	const keys = (allowOuter === false) ? CLASSICAL_KEYS : DIST_KEYS;
	const lons = [];
	const el = { fire: 0, earth: 0, air: 0, water: 0 };
	const mo = { cardinal: 0, fixed: 0, mutable: 0 };
	const hemi = { east: 0, west: 0, above: 0, below: 0 };
	const ascLon = facts.meta ? facts.meta.ascLon : null;
	const mcLon = facts.meta ? facts.meta.mcLon : null;
	keys.forEach((k) => {
		const p = P[k];
		if(!p || p.lon == null){ return; }
		lons.push(p.lon);
		const sign = p.sign || SIGN_ORDER[Math.floor((((p.lon % 360) + 360) % 360) / 30)];
		if(SIGN_ELEMENT[sign]){ el[SIGN_ELEMENT[sign]]++; }
		if(SIGN_MODE[sign]){ mo[SIGN_MODE[sign]]++; }
		if(ascLon != null && mcLon != null){
			hemi[((p.lon - ascLon) % 360 + 360) % 360 < 180 ? 'below' : 'above']++;
			hemi[((p.lon - mcLon) % 360 + 360) % 360 < 180 ? 'east' : 'west']++;
		}
	});
	if(lons.length < 3){ return null; }
	const jt = jonesType(lons);
	const domEl = Object.keys(el).sort((a, b) => el[b] - el[a])[0];
	const domMo = Object.keys(mo).sort((a, b) => mo[b] - mo[a])[0];
	return {
		jones: jt, jonesInfo: jt ? DISTRIBUTION_MUNDANE[jt] : null,
		elements: el, modes: mo, hemispheres: hemi,
		domElement: domEl, domElementCn: ELEMENT_CN[domEl], domElementText: ELEMENT_MUNDANE[domEl],
		domMode: domMo, domModeCn: MODE_CN[domMo], domModeText: MODE_MUNDANE[domMo],
		count: lons.length, classical: allowOuter === false,
	};
}

// 后端 patterns 数组 → 配世运义(供 surfacing)。
export function mundanePatternMeaning(type) { return PATTERN_MUNDANE[type] || null; }

export { ELEMENT_CN as MUNDANE_ELEMENT_CN, MODE_CN as MUNDANE_MODE_CN };
