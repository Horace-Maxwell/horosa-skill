// 飞宫小奇门 · 佈局层 —— 时上起青龙 / 乘龙见天星 / 甲乘龙而飞九宫 / 龙头开八门 / 定命宫。
// 纯函数,零 UI 零接线。
import {
	GAN, ZHI, ZHI_GONG, GAN_SLOTS, SHU_XU, FANG_WEI_RING,
	YUAN_SHEN, TIAN_XING, BA_MEN, GONG_GUA, TONG_WUXING_GAN,
} from './feigongConst.js';

const zhiIdx = (zhi) => ZHI.indexOf(zhi);

// ── 起局支解析 ─────────────────────────────────────────
// mode: 'hour'(默认,占事时辰)/ 'manualZhi'(手动指定支)/
//       'manualNum'(抓数:用十二除之,余数按一子二丑三寅作地支)/ 'yearZhi'(年命佈局,生年地支)。
export function resolveQiZhi({ mode = 'hour', hourZhi, zhi, num, yearZhi } = {}) {
	if (mode === 'hour') return ZHI.includes(hourZhi) ? hourZhi : null;
	if (mode === 'manualZhi') return ZHI.includes(zhi) ? zhi : null;
	if (mode === 'yearZhi') return ZHI.includes(yearZhi) ? yearZhi : null;
	if (mode === 'manualNum') {
		const n = Math.trunc(Number(num));
		if (!n || n < 1) return null;
		return ZHI[(((n - 1) % 12) + 12) % 12];
	}
	return null;
}

// ── 第一步:时上起青龙(十二原神顺佈) ────────────────────
export function yuanShenMap(qiZhi) {
	const i0 = zhiIdx(qiZhi);
	if (i0 < 0) return null;
	const map = {};
	for (let k = 0; k < 12; k += 1) map[ZHI[(i0 + k) % 12]] = YUAN_SHEN[k];
	return map;
}

// ── 第二步:乘龙见天星 ─────────────────────────────────
// 建星支 = (2×支序 + 7) mod 12(子=1..亥=12;余 0 作 12)。
// 与十二局图逐图所注完全一致:子午起申 / 丑未起戌 / 寅申起子 / 卯酉起寅 / 辰戌起辰 / 巳亥起午。
export function jianXingZhi(qiZhi) {
	const s = zhiIdx(qiZhi) + 1;
	if (!s) return null;
	const b = (2 * s + 7) % 12 || 12;
	return ZHI[b - 1];
}
export function tianXingMap(qiZhi) {
	const jz = jianXingZhi(qiZhi);
	if (!jz) return null;
	const i0 = zhiIdx(jz);
	const map = {};
	for (let k = 0; k < 12; k += 1) map[ZHI[(i0 + k) % 12]] = TIAN_XING[k];
	return map;
}

// ── 第三步:甲乘龙而飞九宫(十天干) ──────────────────────
// 甲入青龙宫,乙..癸依九宫数序顺飞;中宫两席(五与十),必得五合双干(戊癸/乙庚/丙辛/丁壬),唯甲己不入中。
export function tianGanMap(qiZhi) {
	const longGong = ZHI_GONG[qiZhi];
	if (!longGong) return null;
	const i0 = GAN_SLOTS.indexOf(longGong);
	const ganGong = {};        // 干 → 宫号 | '中'
	const gongGan = { 中: [] } // 宫 → [干]
	SHU_XU.forEach((g) => { gongGan[g] = []; });
	for (let k = 0; k < 10; k += 1) {
		const slot = GAN_SLOTS[(i0 + k) % 10];
		ganGong[GAN[k]] = slot;
		gongGan[slot].push(GAN[k]);
	}
	return { longGong, ganGong, gongGan, zhongGong: gongGan['中'].slice() };
}

// ── 第四步:龙头开八门 ─────────────────────────────────
// 休门宫 = 青龙宫依九宫数序(跳过中五)之下一宫;
// 休生伤杜景死惊开自休门宫起,按方位环序顺时针环佈。
export function xiuMenGong(qiZhi) {
	const longGong = ZHI_GONG[qiZhi];
	if (!longGong) return null;
	return SHU_XU[(SHU_XU.indexOf(longGong) + 1) % 8];
}
export function baMenMap(qiZhi) {
	const xiu = xiuMenGong(qiZhi);
	if (!xiu) return null;
	const i0 = FANG_WEI_RING.indexOf(xiu);
	const gongMen = {};  // 宫 → 门
	const menGong = {};  // 门 → 宫
	for (let k = 0; k < 8; k += 1) {
		const g = FANG_WEI_RING[(i0 + k) % 8];
		gongMen[g] = BA_MEN[k];
		menGong[BA_MEN[k]] = g;
	}
	return { xiuMenGong: xiu, gongMen, menGong };
}

// ── 全局佈局 ───────────────────────────────────────────
export function buildJu({ zhi, dayGan, dayZhi } = {}) {
	if (!ZHI.includes(zhi)) return null;
	const yuanShen = yuanShenMap(zhi);
	const jianZhi = jianXingZhi(zhi);
	const tianXing = tianXingMap(zhi);
	const tianGan = tianGanMap(zhi);
	const baMen = baMenMap(zhi);
	const ju = {
		qiZhi: zhi,
		longGong: tianGan.longGong,
		yuanShen,               // 支 → 原神
		jianZhi,                // 建星支
		tianXing,               // 支 → 天星
		tianGan,                // { longGong, ganGong, gongGan, zhongGong }
		baMen,                  // { xiuMenGong, gongMen, menGong }
		gongGua: { ...GONG_GUA },
	};
	if (GAN.includes(dayGan)) {
		ju.dayGan = dayGan;
		ju.dayGanGong = tianGan.ganGong[dayGan];   // 日干之宫(主)
	}
	if (ZHI.includes(dayZhi)) {
		ju.dayZhi = dayZhi;
		ju.dayZhiGong = ZHI_GONG[dayZhi];          // 日支之宫(客)
		ju.dayZhiShen = yuanShen[dayZhi];
		ju.dayZhiXing = tianXing[dayZhi];
	}
	return ju;
}

// ── 流年(从日支起,男顺女逆,一支一岁) ──────────────────
// 第 k 岁落支 = 日支顺/逆行 (k−1) 位;取该支之 宫/原神/天星/门。命宫损益由断语/UI 层比较。
export function liuNian({ dayZhi, gender = 'male', maxAge = 12, ju } = {}) {
	const i0 = zhiIdx(dayZhi);
	if (i0 < 0 || !ju) return [];
	const dir = gender === 'female' ? -1 : 1;
	const n = Math.max(1, Math.min(120, Math.trunc(Number(maxAge)) || 12));
	const out = [];
	for (let k = 1; k <= n; k += 1) {
		const zhi = ZHI[(((i0 + dir * (k - 1)) % 12) + 12) % 12];
		const gong = ZHI_GONG[zhi];
		out.push({
			age: k, zhi, gong,
			shen: ju.yuanShen ? ju.yuanShen[zhi] : null,
			xing: ju.tianXing ? ju.tianXing[zhi] : null,
			men: (ju.baMen && ju.baMen.gongMen) ? ju.baMen.gongMen[gong] : null,
		});
	}
	return out;
}

// ── 流月 / 当年运气(月建定月位) ─────────────────────────
// 正月建寅…十二月建丑;取月建支之 宫/原神/天星/门(与命宫之生克损益由断语/UI 层做)。
export function liuYue({ ju, monthNum } = {}) {
	const m = Math.trunc(Number(monthNum));
	if (!ju || !m || m < 1 || m > 12) return null;
	const zhi = ZHI[(m + 1) % 12]; // 1→寅(2) … 11→子(0) … 12→丑(1)
	const gong = ZHI_GONG[zhi];
	return {
		monthNum: m, zhi, gong,
		shen: ju.yuanShen ? ju.yuanShen[zhi] : null,
		xing: ju.tianXing ? ju.tianXing[zhi] : null,
		men: (ju.baMen && ju.baMen.gongMen) ? ju.baMen.gongMen[gong] : null,
	};
}

// ── 定命宫法 ───────────────────────────────────────────
// 「十几岁减二,二十几岁减一。三十几岁不动,四十几岁加一。五十几岁加二,六十几岁加三。
//   男命值五宫看戊。女命值五宫又看己。」去十位用个位。
// 1-9 岁:今传本按语「几岁之中应减三」,标「原典存疑」;70+ 每十岁递加一,标「按规律推断,原典未载」;
// 个位为 0:原典未载 → null 须手动;值五宫之干入中宫 → 看其同五行之干(壬看癸、癸看壬、戊看己)。
export function mingGong({ age, gender = 'male', ju } = {}) {
	const a = Math.trunc(Number(age));
	if (!a || a < 1) return { gong: null, flags: ['年龄无效'] };
	const decade = Math.floor(a / 10);
	const delta = decade - 3;
	const flags = [];
	if (decade === 0) flags.push('原典存疑(今传本按语:几岁之中应减三)');
	if (decade >= 7) flags.push('按规律推断,原典未载(七十以上每十岁递加一)');
	const adjusted = a + delta;
	if (adjusted <= 0) return { gong: null, adjusted, flags: [...flags, '数不及位,须手动定宫'] };
	const digit = adjusted % 10;
	if (digit === 0) return { gong: null, adjusted, digit, flags: [...flags, '个位为零,原典未载,须手动定宫'] };
	if (digit !== 5) return { gong: digit, adjusted, digit, flags };
	// 值五宫:男看戊,女看己,取其所飞之宫。
	const gan = gender === 'female' ? '己' : '戊';
	const via = [gan];
	if (!ju || !ju.tianGan) {
		return { gong: null, adjusted, digit, zhiWu: true, via, flags: [...flags, '值五宫须给定局盘以查干所飞宫'] };
	}
	let g = ju.tianGan.ganGong[gan];
	if (g === '中') {
		// 「凡天干入中宫皆看其同五行即是」
		const alt = TONG_WUXING_GAN[gan];
		via.push(alt);
		g = ju.tianGan.ganGong[alt];
		if (g === '中') {
			return { gong: null, adjusted, digit, zhiWu: true, via, flags: [...flags, '同五行之干亦入中宫,须手动'] };
		}
		return { gong: g, adjusted, digit, zhiWu: true, via, flags: [...flags, `值五宫看${gan},其干入中宫,转看同五行之${alt}`] };
	}
	return { gong: g, adjusted, digit, zhiWu: true, via, flags };
}
