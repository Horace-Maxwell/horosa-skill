// 天星择日双轮纯数学核(对照 Moira Calculate.computeAzimuth / City.parseMapPos /
// ChartData 座山与快盘投影段;全部可单测,轮盘组件只做摆放不做换算)。
//
// 度空间约定(全部在「罗盘空间」作图,永不携带 Moira 内部 135/315 盘度):
//   罗盘方位 az:0=子(北),顺时针 90=卯东?否——罗盘 90=东。传统盘「子下卯左」由
//   azTheta 负责:SVG y 向下,theta = 90 + az ⇒ az0 在正下、az90(东)在左。
import { SHAN_ORDER, SHAN_CENTER_DEG } from '../fengshui/fengshuiData.js';

export function normDeg(deg){
	let v = Number(deg) % 360;
	if(!Number.isFinite(v)){ return 0; }
	if(v < 0){ v += 360; }
	return v;
}

// swisseph/本地球面三角输出的方位角以南为零 → 罗盘向(0=北,顺时针)。
export function swissAzToCompass(azSouthZero){
	return normDeg(Number(azSouthZero) + 180);
}

// 罗盘方位 → SVG 极角(point() 用,y 向下):子在下、卯(东90)在左 —— 传统盘向。
// globalRot:整盘磁偏旋转角(度)。子正在下=开→0;关→−磁偏(不论子正正北/磁北,罗盘层随之偏转,磁北转到正下)。
export function azTheta(azCompass, globalRot = 0){
	return 90 + normDeg(azCompass) + (Number(globalRot) || 0);
}

// 二十四山:山中心 = SHAN_CENTER_DEG(子=0),盘别偏移 天盘+7.5 / 地盘0 / 人盘−7.5(照 Moira mountain_mode)。
export const PLATE_OFFSET = { tian: 7.5, di: 0, ren: -7.5 };

// SHAN_ORDER 以壬起(壬中心 345°);扇区计数以子(中心 0°)为 0,故取 SHAN_ORDER[(i+1)%24]。
export function shanIndexAt(azCompass, plate = 'di'){
	const off = PLATE_OFFSET[plate] !== undefined ? PLATE_OFFSET[plate] : 0;
	const adj = normDeg(azCompass - off + 7.5);
	return (Math.floor(adj / 15) + 1) % 24;
}

export function shanNameAt(azCompass, plate = 'di'){
	return SHAN_ORDER[shanIndexAt(azCompass, plate)];
}

// 山内分度(照 Moira 双列表「07子山30」):mountainDeg = (az − 山中心 + 7.5) mod 15。
// 输出 { deg(0-14), shan, minute(0-59), text '07子山30' }。默认地盘。
export function mountainPosition(azCompass, plate = 'di'){
	const idx = shanIndexAt(azCompass, plate);
	const shan = SHAN_ORDER[idx];
	const off = PLATE_OFFSET[plate] !== undefined ? PLATE_OFFSET[plate] : 0;
	const center = SHAN_CENTER_DEG[shan] + off;
	const inDeg = normDeg(azCompass - center + 7.5) % 15;
	const deg = Math.floor(inDeg);
	const minute = Math.floor((inDeg - deg) * 60);
	return {
		deg,
		shan,
		minute,
		text: `${String(deg).padStart(2, '0')}${shan}山${String(minute).padStart(2, '0')}`,
	};
}

// 黄道动盘(Moira quick_azimuth,Calculate.java:797-831):行星黄经按所在宫(选定分宫制
// cusps)内比例投影到等分 12 宫的动盘度;返回罗盘空间方位等效值(供 azTheta 摆放)。
// cusps: 长度 12,cusps[0]=第1宫宫头黄经(swisseph 顺序);lon=行星黄经(与 cusps 同制式)。
export function quickWheelAz(lonEcl, cusps){
	if(!Array.isArray(cusps) || cusps.length < 12){
		return null;
	}
	const lon = normDeg(lonEcl);
	let houseIdx = -1;
	let ratio = 0;
	for(let i = 0; i < 12; i++){
		const start = normDeg(cusps[i]);
		const end = normDeg(cusps[(i + 1) % 12]);
		const span = normDeg(end - start) || 30;
		const offset = normDeg(lon - start);
		if(offset < span){
			houseIdx = i;
			ratio = offset / span;
			break;
		}
	}
	if(houseIdx < 0){
		houseIdx = 0;
	}
	// Moira 盘度 chartDeg = 30·ratio + 180 + houseIdx·30;罗盘等效 az = 315 − chartDeg
	const chartDeg = 30 * ratio + 180 + houseIdx * 30;
	return normDeg(315 - chartDeg);
}

// 磁偏套用:ziZheng='magnetic' 时动盘各元素显示方位 = 罗盘方位 − 磁偏(东偏+)。
export function applyDeclination(azCompass, ziZheng, declination){
	if(ziZheng !== 'magnetic'){
		return normDeg(azCompass);
	}
	return normDeg(azCompass - (Number(declination) || 0));
}

// 二十四山五行(正体五行/化合五行,择日盘山环配色;正体=山字本行,化合=纳音化气口径)。
export const SHAN_WUXING_MAIN = {
	壬: '水', 子: '水', 癸: '水', 丑: '土', 艮: '土', 寅: '木', 甲: '木', 卯: '木', 乙: '木',
	辰: '土', 巽: '木', 巳: '火', 丙: '火', 午: '火', 丁: '火', 未: '土', 坤: '土', 申: '金',
	庚: '金', 酉: '金', 辛: '金', 戌: '土', 乾: '金', 亥: '水',
};
export const SHAN_WUXING_COMBO = {
	壬: '木', 子: '水', 癸: '金', 丑: '金', 艮: '火', 寅: '火', 甲: '火', 卯: '木', 乙: '水',
	辰: '水', 巽: '木', 巳: '金', 丙: '火', 午: '火', 丁: '木', 未: '木', 坤: '水', 申: '水',
	庚: '金', 酉: '金', 辛: '火', 戌: '火', 乾: '金', 亥: '木',
};
export const WUXING_COLOR = {
	木: 'var(--moira-green, #008000)',
	火: 'var(--moira-red, #ff0000)',
	土: 'var(--moira-brown, #8a5a2b)',
	金: 'var(--moira-gold, #b8860b)',
	水: 'var(--moira-blue, #000080)',
};

export function shanColor(shan, wuxingMode = 'main'){
	const table = wuxingMode === 'combo' ? SHAN_WUXING_COMBO : SHAN_WUXING_MAIN;
	return WUXING_COLOR[table[shan]] || 'var(--moira-ink, #000000)';
}

// 环向推挤(照 Moira computeSignShift 语义):按角升序,相邻(含环绕)间距<minGap 时
// 双向各推一半,迭代收敛 —— 行星恒排单圈、不重叠;真实方位另由引线指示。
// lockedSet(可选,Set/array of 原始下标)= Moira sign_lock:锁定项钉在原位不动,
// 推量全部由未锁邻居承担(aspects 模式升/顶锁定即此);不传 = 旧行为字节不变。
export function resolveRingShifts(azList, minGapDeg, lockedSet){
	const isLocked = (idx)=>!!(lockedSet && (lockedSet.has ? lockedSet.has(idx) : lockedSet.indexOf(idx) >= 0));
	const items = azList.map((az, idx)=>({ idx, az: ((az % 360) + 360) % 360, locked: isLocked(idx) }))
		.sort((a, b)=>a.az - b.az);
	items.forEach((it)=>{ it.shifted = it.az; });
	if(items.length > 1 && minGapDeg > 0){
		for(let round = 0; round < 16; round++){
			let moved = false;
			for(let i = 0; i < items.length; i++){
				const L = items[i];
				const R = items[(i + 1) % items.length];
				const gap = i + 1 < items.length ? (R.shifted - L.shifted) : (R.shifted + 360 - L.shifted);
				if(gap < minGapDeg - 0.01){
					const push = (minGapDeg - gap) / 2 + 0.05;
					if(L.locked && R.locked){
						continue;
					}
					if(L.locked){
						R.shifted += push * 2;
					}else if(R.locked){
						L.shifted -= push * 2;
					}else{
						L.shifted -= push;
						R.shifted += push;
					}
					moved = true;
				}
			}
			if(!moved){
				break;
			}
		}
	}
	const out = new Array(azList.length);
	items.forEach((it)=>{ out[it.idx] = ((it.shifted % 360) + 360) % 360; });
	return out;
}

// 择日盘三套布局(照 Moira PICK_MODE 三档 prefix:恒星>罗盘>基本;数值=moira prop 逐值):
// slots 键=1-based 环号减一的 [内界,外界] 槽;markBands=座山箭头刻带(mark_up/mark_down 键位)。
// compass/fixstar 布局无神煞带(被罗盘宿/恒星带取代,slots 不含 gods 即自动不画)。
export const PICK_LAYOUTS = {
	pick: {
		ringPos: [0.19, 0.31, 0.37, 0.43, 0.51, 0.54, 0.60, 0.68, 0.71, 0.77, 0.92, 0.95, 1.0],
		slots: { nowPlanets: [6, 7], mountainTick: [7, 8], mountain: [8, 9], gods: [9, 10], degreeTick: [10, 11] },
		markBands: [[4, 5], [7, 8], [10, 11]],
	},
	compass: {
		ringPos: [0.19, 0.31, 0.37, 0.43, 0.51, 0.54, 0.60, 0.66, 0.72, 0.75, 0.83, 0.86, 0.92, 0.95, 1.0],
		slots: { nowPlanets: [9, 10], mountain: [7, 8], compassRing: [11, 12], degreeTick: [12, 13] },
		markBands: [[4, 5], [10, 11], [13, 14]],
	},
	fixstar: {
		ringPos: [0.16, 0.28, 0.34, 0.40, 0.48, 0.50, 0.56, 0.58, 0.72, 0.78, 0.80, 0.93, 0.95, 1.0],
		slots: { nowPlanets: [10, 11], mountain: [8, 9], starRing: [7, 8], degreeTick: [11, 12] },
		markBands: [[4, 5], [7, 8], [12, 13]],
	},
};

export function pickLayoutMode(ele){
	if(ele && ele.showFixstar === true){
		return 'fixstar';
	}
	// 择日盘恒用 pick 布局(用户钦定:必须带本命神煞环 + 红座山指北针)。
	// pick 布局 slots 含 gods(神煞带),compass 布局用罗盘宿环取代神煞——
	// 曾误强制 compass 导致神煞整环消失、盘面错位,已回退;showCompass 开关已撤,恒 pick。
	return 'pick';
}

// 罗盘宿带(compass 布局):28 宿名按方位度数排(compass_stellar_names 原值,娄起宿序),经 electionTheta 上盘。
export const COMPASS_STELLAR = [
	['娄', 16], ['胃', 29], ['昴', 44], ['毕', 55], ['觜', 70.5], ['参', 71], ['井', 80],
	['鬼', 110], ['柳', 113], ['星', 126], ['张', 133], ['翼', 150], ['轸', 170],
	['角', 189], ['亢', 201], ['氐', 211], ['房', 227], ['心', 233], ['尾', 239], ['箕', 256],
	['斗', 266], ['牛', 288], ['女', 295], ['虚', 306], ['危', 315], ['室', 331], ['壁', 349], ['奎', 358],
];
