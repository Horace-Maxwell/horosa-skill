// Moira 本命盘信息区四张表的纯函数移植(源:ChartData.java + moira prop 数据表):
// ① 难仇恩用四役表(度/宫/山三行,按主星五行查表) ② 虚实四柱(虚=甲子旬空支,实=柱支)
// ③ 飞限/小限(fly_seq/child_seq 查表) ④ 限度/至(limit_seq 逐宫年数推进,宫内线性插值)。
// 全部可 jest 直测;呈现层在 GuoLaoMoiraPanel。

export const GAN = ['甲', '乙', '丙', '丁', '戊', '己', '庚', '辛', '壬', '癸'];
export const ZHI = ['子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥'];

// 难/仇(财)/恩/用 查表(prop 難仇恩用X;繁体星名已简化,金水=金+水孛 等复合保持原样)
export const LIFE_HELPER_LABELS = ['难', '仇', '恩', '用'];
export const LIFE_HELPER_ALT_LABELS = ['难', '财', '恩', '用'];
export const LIFE_HELPER_TABLE = {
	日: ['木炁', '土计', '金水', '火罗'],
	月: ['土计', '火罗', '金水', '木炁'],
	金: ['火罗', '木炁', '土计', '水孛'],
	木: ['金', '土计', '水孛', '火罗'],
	水: ['土计', '火罗', '金', '木炁'],
	火: ['水孛', '金', '木炁', '土计'],
	土: ['木炁', '水孛', '火罗', '金'],
};

export function lifeHelperRow(element){
	return LIFE_HELPER_TABLE[element] || null;
}

// 虚宫(照 ChartData.computeWeakHouse):干支在六十甲子的序 i →
// index = 10 − 2*(i/10 取整)(即该旬的旬空对支);单支版:柱序奇数取 index+1。
const JIAZI = (()=>{
	const out = [];
	for(let i = 0; i < 60; i++){
		out.push(GAN[i % 10] + ZHI[i % 12]);
	}
	return out;
})();

export function weakBranchOf(ganzhi){
	const i = JIAZI.indexOf(`${ganzhi || ''}`.slice(0, 2));
	if(i < 0){
		return '';
	}
	let index = 10 - 2 * Math.floor(i / 10);
	if((i % 2) === 1){
		index++;
	}
	return ZHI[((index % 12) + 12) % 12];
}

export function solidBranchOf(ganzhi){
	const s = `${ganzhi || ''}`;
	return s.length >= 2 ? s.charAt(1) : '';
}

// 四柱虚实两行(输入 [年,月,日,时] 干支)
export function weakSolidPillars(pillars){
	const list = (pillars || []).map((p)=>`${p || ''}`);
	return {
		weak: list.map(weakBranchOf),
		solid: list.map(solidBranchOf),
	};
}

// 小限(照 getSmallLimit):命宫黄经 + (虚岁−1)×30 所落黄道支。
const SIGN_BRANCH = ['戌', '酉', '申', '未', '午', '巳', '辰', '卯', '寅', '丑', '子', '亥']; // 黄道星座序→地支(白羊=戌 镜像)

export function smallLimitBranch(lifeSignPos, age){
	const deg = (((Number(lifeSignPos) || 0) + (Math.max(1, age) - 1) * 30) % 360 + 360) % 360;
	return SIGN_BRANCH[Math.floor(deg / 30) % 12];
}

// 飞限(照 getFlyLimit):命宫星座序奇偶选 yang/ying 序列;童限前用 seq1,后用 seq2;
// fly_seq_half_shift 指定的岁段「两支各半年」。返回 {branches:[..], halfYear:bool}。
export const FLY_SEQ_YANG1 = [0, 0, 6, 6, 8, 4];
export const FLY_SEQ_YING1 = [0, 0, 6, 6, 4, 8];
export const FLY_SEQ_YANG2 = [11, 11, 5, 5, 3, 7, 11, 11, 5, 5, 10, 10, 4, 4, 6, 2, 10, 10, 4, 4, 6, 9, 9, 3, 3, 1, 5, 9, 9, 3, 3, 1, 5, 9, 9, 3, 8, 8, 2, 2, 4, 0, 8, 8, 7, 7, 1, 1, 11, 3, 7, 6, 6, 0, 0, 2, 10, 6, 6, 0, 0, 2, 5, 5, 11, 11, 9, 4, 4, 10, 10, 0, 3, 3, 9, 9, 7, 2, 2, 8, 8, 10, 1, 1, 7, 7, 5];
export const FLY_SEQ_YING2 = [11, 11, 5, 5, 7, 3, 11, 11, 5, 5, 10, 10, 4, 4, 2, 6, 10, 10, 4, 4, 2, 9, 9, 3, 3, 5, 1, 9, 9, 3, 3, 5, 1, 9, 9, 3, 8, 8, 2, 2, 0, 4, 8, 8, 7, 7, 1, 1, 3, 11, 7, 6, 6, 0, 0, 10, 2, 6, 6, 0, 0, 10, 5, 5, 11, 11, 1, 4, 4, 10, 10, 8, 3, 3, 9, 9, 11, 2, 2, 8, 8, 6, 1, 1, 7, 7, 9];
export const FLY_SEQ_HALF_SHIFT = [66, 71, 75, 88];

export function flyLimitBranches(lifeSignPos, realAge, childAgeLimit = 5){
	const pos = (((Number(lifeSignPos) || 0)) % 360 + 360) % 360;
	const signIdx = Math.floor(pos / 30);
	const yang = (signIdx % 2) === 0;
	const branchAt = (offsetSigns)=>SIGN_BRANCH[Math.floor((((pos + 30 * offsetSigns) % 360) + 360) % 360 / 30) % 12];
	let age = Math.max(0, Math.floor(realAge));
	if(age < childAgeLimit){
		const seq = yang ? FLY_SEQ_YANG1 : FLY_SEQ_YING1;
		return { branches: [branchAt(seq[age % seq.length])], halfYear: false };
	}
	age -= childAgeLimit;
	const seq = yang ? FLY_SEQ_YANG2 : FLY_SEQ_YING2;
	if(age + 2 >= seq.length){
		return { branches: [], halfYear: false };
	}
	let last;
	let cur;
	if(age >= FLY_SEQ_HALF_SHIFT[0] && age < FLY_SEQ_HALF_SHIFT[1]){
		last = seq[age];
		cur = seq[age + 1];
	}else if(age >= FLY_SEQ_HALF_SHIFT[2] && age < FLY_SEQ_HALF_SHIFT[3]){
		last = seq[age + 1];
		cur = seq[age + 2];
	}else if(age >= FLY_SEQ_HALF_SHIFT[1]){
		// 照 Moira getFlyLimit 第三分支:调整龄 ≥half_shift[1] 段(含 [71,75) 与 ≥88)用 seq[age+1]
		// 而非 seq[age]——旧版漏此分支,约 81~85 岁飞限错位一支。四分支缺一即漂,不可并入 else。
		last = cur = seq[age + 1];
	}else{
		last = cur = seq[age];
	}
	if(last !== cur){
		return { branches: [branchAt(last), branchAt(cur)], halfYear: true };
	}
	return { branches: [branchAt(cur)], halfYear: false };
}

// 童限「定童限」base:Moira child_period —— 0=九年起(base 9,默认)、非0=十年起(base 10)。
// childBase 入参:9(默认)或 10。照 getChildLimit:day = (child_period?10:9 + 度/3)*365.25。
function childBaseOf(childBase){ return Number(childBase) === 10 ? 10 : 9; }
// 童限岁数上限(照 getChildLimit(round_to_year=true):base + 命度宫内度/3 四舍五入)。
// 入参=黄经命度(童限/飞限 childAgeLimit 边界;flyLimitBranches 的 childAgeLimit 必须传此值,勿用默认)。
export function childAgeLimitYears(lifeLonDeg, childBase){
	const inSign = (((Number(lifeLonDeg) || 0) % 30) + 30) % 30;
	return Math.max(1, Math.round(childBaseOf(childBase) + inSign / 3));
}
// 童限年数(限度度数推进用·不四舍;照 getChildLimit(false)/365.25 = base + 命度宫内度/3)。
// 🔴 与 childAgeLimitYears(四舍)不同:限度度数首宫用此不四舍值;飞限/童限边界用四舍值。二者勿混。
export function childYearsSpan(lifeLonDeg, childBase){
	const inSign = (((Number(lifeLonDeg) || 0) % 30) + 30) % 30;
	return childBaseOf(childBase) + inSign / 3;
}
// 童限地支(照 getChildLimit(cur_age):命宫黄经 + 30°·child_seq[cur_age])。realAge=虚岁(1 起);
// child_seq 逐字节取自 moira prop,超序列截断到末位。
export const CHILD_SEQ = [0, 1, 7, 6, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1, 0];
export function childLimitBranch(lifeSignPos, realAge){
	const cur = Math.max(0, Math.min(CHILD_SEQ.length - 1, Math.floor(Number(realAge) || 1) - 1));
	const deg = ((((Number(lifeSignPos) || 0) + 30 * CHILD_SEQ[cur]) % 360) + 360) % 360;
	return SIGN_BRANCH[Math.floor(deg / 30) % 12];
}

// 月限(照 Moira getMonthLimit,ChartData.java:7526):index = 今农历月 − 生农历月;
// 若 <0 则 +12 且 +(虚岁−2)(借上年小限为基),否则 +(虚岁−1);地支 = zodiac(命宫黄经 + index×30)。
// birthMonthNum / nowMonthNum = 农历月序(1-12);realAge = 虚岁。数据缺则返回 ''。
export function monthLimitBranch(lifeSignPos, realAge, birthMonthNum, nowMonthNum){
	const bm = Number(birthMonthNum);
	const nm = Number(nowMonthNum);
	if(!Number.isFinite(bm) || !Number.isFinite(nm)){ return ''; }
	let index = nm - bm;
	if(index < 0){ index += 12; index += Math.max(0, Math.floor(Number(realAge) || 1) - 2); }
	else { index += Math.max(0, Math.floor(Number(realAge) || 1) - 1); }
	const deg = ((((Number(lifeSignPos) || 0) + index * 30) % 360) + 360) % 360;
	return SIGN_BRANCH[Math.floor(deg / 30) % 12];
}
// 月支(月建地支)→ 农历月序(寅=正月 1、卯=2 …丑=十二月 12)。供月限取月数(月建口径,近 Moira 朔望农历月)。
export function lunarMonthNumFromBranch(zhi){
	const idx = ZHI.indexOf(`${zhi || ''}`.slice(-1));
	return idx < 0 ? NaN : ((idx - 2 + 12) % 12) + 1;
}

// 限度/至(照 ChartData:3900 段):age 的分数年沿 limit_seq(童限首宫用实际童限年数)逐宫消耗,
// 宫内 30° 线性插值;返回 {from, to} 黄经(度)。fromDeg=命宫下一宫头 − 插值(Moira 反向排限)。
export const LIMIT_SEQ = [11.0, 10.0, 11.0, 15.0, 8.0, 7.0, 11.0, 4.5, 4.5, 4.5, 5.0, 5.0];

export function limitDegreeSpan(lifeSignPos, fractionalAge, childLimitYears = LIMIT_SEQ[0]){
	const norm = (d)=>((d % 360) + 360) % 360;
	const solve = (val)=>{
		let degreeOffset = 0;
		for(let i = 0; i < LIMIT_SEQ.length; i++){
			const year = i === 0 ? childLimitYears : LIMIT_SEQ[i];
			if(val < year){
				return degreeOffset + 30.0 * val / year;
			}
			degreeOffset += 30.0;
			val -= year;
		}
		return degreeOffset;
	};
	const startVal = Math.max(0, fractionalAge - 1);
	const s = solve(startVal);
	const e = solve(startVal + 1);
	const base = Math.floor(norm(lifeSignPos) / 30.0) * 30.0 + 30.0;
	return {
		from: norm(base - s),
		to: norm(base - e),
	};
}

// 十二长生环(照 Moira getStarSigns):起字=年柱纳音五行(甲子行第11项抽验:甲子金/庚午土/癸亥水/戊辰木/丙午水 全中),
// 起宫查 LONG_LIFE_POS(金4 木10 水1 土1 火7),沿 TWELVE_SIGNS_REV(酉申未午巳辰卯寅丑子亥戌,逆时针支序)顺布 12 字。
// 丙午(纳音水)→n=1→申长生、未养(与 Moira 实机截图逐宫一致)。固定画,不进神煞筛选(Moira 同款)。
export const NAYIN_WUXING = (function(){
	const pairs = ['金', '火', '木', '土', '金', '火', '水', '土', '金', '木', '水', '土', '火', '木', '水', '金', '火', '木', '土', '金', '火', '水', '土', '金', '木', '水', '土', '火', '木', '水'];
	const out = {};
	for(let i = 0; i < 60; i++){
		out[GAN[i % 10] + ZHI[i % 12]] = pairs[Math.floor(i / 2)];
	}
	return out;
})();
export const LONG_LIFE_SIGNS = ['长生', '养', '胎', '绝', '墓', '死', '病', '衰', '帝旺', '临官', '冠带', '沐浴'];
export const LONG_LIFE_POS = { 金: 4, 木: 10, 水: 1, 土: 1, 火: 7 };
export const TWELVE_SIGNS_REV = ['酉', '申', '未', '午', '巳', '辰', '卯', '寅', '丑', '子', '亥', '戌'];

export function longLifeMapForYear(yearGZ){
	const elem = NAYIN_WUXING[`${yearGZ || ''}`.slice(0, 2)];
	const n = LONG_LIFE_POS[elem];
	if(n === undefined){
		return null;
	}
	const map = {};
	for(let j = 0; j < 12; j++){
		map[TWELVE_SIGNS_REV[(n + j) % 12]] = LONG_LIFE_SIGNS[j];
	}
	return map;
}

// 地支五行(七政口径,含日月主支:午日未月——与轮盘 RING1 土子/木亥同源)
export const BRANCH_ELEMENT = {
	子: '土', 丑: '土', 寅: '木', 卯: '火', 辰: '金', 巳: '水',
	午: '日', 未: '月', 申: '水', 酉: '金', 戌: '火', 亥: '木',
};

// 28 宿五行字(角木蛟序,七曜配宿 木金土日月火水 循环)——「07井木47」式显示用。
export const SU_ELEMENT = {
	角: '木', 亢: '金', 氐: '土', 房: '日', 心: '月', 尾: '火', 箕: '水',
	斗: '木', 牛: '金', 女: '土', 虚: '日', 危: '月', 室: '火', 壁: '水',
	奎: '木', 娄: '金', 胃: '土', 昴: '日', 毕: '月', 觜: '火', 参: '水',
	井: '木', 鬼: '金', 柳: '土', 星: '日', 张: '月', 翼: '火', 轸: '水',
};

// 黄道经度 → 28 宿名+五行字(照 full_stellar 序;宿界按均分近似仅供四役查表,精确宿度以盘面为准)
export function branchElementOf(branch){
	return BRANCH_ELEMENT[branch] || '';
}
