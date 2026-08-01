// divination/babylon/microzodiac.js —— 微黄道三算法(×12 / ×13 / ×277,皆 mod 360)。
// 恒等式:13 × 277 = 3601 ≡ 1 (mod 360) —— ×277 是 ×13 的模逆(楔文 277 写作 4,37)。
// 变体(结果黄经可差 ~29°):
//   A(希腊-罗马标准):dodecatemorion = 宫起点 + 12×D(D=宫内度)
//   B(楔文/古典默认):dodecatemorion = 该点本身 + 12×D = 宫起点 + 13×D
// 永远是宫内度 D(0–30)被乘,绝非绝对黄经、绝非宫号。

import { norm360, lonToSignDeg, signDegToLon } from './units.js';

// 简单 dodecatemoria:输入绝对黄经 L,返回 { lon(变体结果), microSign(命名微段宫号1-12), microIndex(1-12) }
export function dodeca12(L, variant){
	const { sign, deg } = lonToSignDeg(L);
	const signStart = (sign - 1) * 30;
	const product = 12 * deg;
	const lon = variant === 'A'
		? norm360(signStart + product)
		: norm360(signStart + 13 * deg);   // 变体 B:加到点本身(= 13D + 宫起点)
	// 命名微段:每宫 12 段各 2;30°,首段=本宫、顺黄道
	const k = Math.min(11, Math.floor(deg / 2.5));           // 0 基段号
	const microSign = ((sign - 1 + k) % 12) + 1;
	return { lon, microSign, microIndex: k + 1, sign, deg };
}

// 144 微段网格:宫 S(1–12)第 k 段(1–12)所属微宫
export function microSegment(S, k){
	return ((S - 1 + k - 1) % 12) + 1;
}

// 宫 S 第 k 段的黄经区间 [from, to)
export function microSegmentRange(S, k){
	const from = (S - 1) * 30 + (k - 1) * 2.5;
	return { from, to: from + 2.5 };
}

// Kalendertext 函数对(互逆):
// ×13:日期(太阳位)→ 图式月位;×277:月位 → 历日/日位
export function kalendertextD(Lsun){ return norm360(13 * Lsun); }
export function kalendertextK(Lmoon){ return norm360(277 * Lmoon); }

// (月 M, 日 d) ↔ (宫, 度) 的图式恒等(1°/日;月 M ≡ 宫 M)
export function schematicDateToLon(M, d){ return signDegToLon(M, d); }
export function lonToSchematicDate(L){
	const { sign, deg } = lonToSignDeg(L);
	return { M: sign, d: deg };
}

// 生成全 144 微段(供网格渲染):[{S, k, microSign, from, to}]
export function buildMicroGrid(){
	const out = [];
	for(let S = 1; S <= 12; S++){
		for(let k = 1; k <= 12; k++){
			const r = microSegmentRange(S, k);
			out.push({ S, k, microSign: microSegment(S, k), from: r.from, to: r.to });
		}
	}
	return out;
}
