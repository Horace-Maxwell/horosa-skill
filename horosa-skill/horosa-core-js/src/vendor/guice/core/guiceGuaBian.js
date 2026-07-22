// 皇极轨策 · 卦变代数 —— 纯函数、零副作用。
//
// 🔴 三条硬规则（古籍明载，修正了「互卦作六十四卦」之常见误解）：
//   ① 互卦只作两个八卦，不作六十四卦重名论断 ——
//      「將互卦又做一個完整的卦來論和斷是不對的、功能不同，不能這麼用。只做體互，用互單獨使用」。
//      构造：去初爻与上爻，中间四爻分作两卦 → 下互 = 爻2·3·4，上互 = 爻3·4·5。
//   ② 乾坤无互，互其变卦 —— 互卦与本卦同者（唯乾坤如是）改取变卦之互。
//   ③ 体互/用互：体卦在上则上互为体之互、下互为用之互；体卦在下则反之。
//
// ⚠️ 仓内 tiebanFrameworkLocal 亦有 huTiGua，其构造相同（爻2·3·4 与 爻3·4·5）但返六十四卦，
//    与本法「只出两个八卦」之要求不合 → 本层自实现，不动 tieban（零回归）。
import { Gua8 } from '../../gua/GuaConst.js';

const TRI_KEY = Gua8.reduce((m, g) => { m[g.value.join('')] = g.name; return m; }, {});
/** 三爻（bottom-first）→ 八卦名 */
export function triOf(bits) { return TRI_KEY[bits.join('')] || null; }
/** 六爻（bottom-first）→ {up, lo} */
export function trigramsOf(lines) {
	return (Array.isArray(lines) && lines.length === 6)
		? { lo: triOf(lines.slice(0, 3)), up: triOf(lines.slice(3, 6)) } : null;
}
/** {up, lo} → 六爻（bottom-first） */
export function linesOf(up, lo) {
	const gu = Gua8.find((g) => g.name === up); const gl = Gua8.find((g) => g.name === lo);
	return (gu && gl) ? [...gl.value, ...gu.value] : null;
}

/** 变卦：动爻反转 */
export function bianGua(lines, dongYao) {
	if (!Array.isArray(lines) || lines.length !== 6) return null;
	if (!Number.isInteger(dongYao) || dongYao < 1 || dongYao > 6) return null;
	const l = lines.slice();
	l[dongYao - 1] = l[dongYao - 1] ? 0 : 1;
	return l;
}
/** 错卦：全爻反转 */
export function cuoGua(lines) {
	return Array.isArray(lines) && lines.length === 6 ? lines.map((b) => (b ? 0 : 1)) : null;
}
/** 综卦：倒置 */
export function zongGua(lines) {
	return Array.isArray(lines) && lines.length === 6 ? lines.slice().reverse() : null;
}

/**
 * 互卦 —— 只出两个八卦，不作六十四卦。
 * 下互 = 爻2·3·4；上互 = 爻3·4·5。
 * 乾坤无互（其互即本卦）→ 互其变卦。
 */
export function huGua(lines, dongYao) {
	if (!Array.isArray(lines) || lines.length !== 6) return null;
	const raw = () => ({ xiaHu: triOf(lines.slice(1, 4)), shangHu: triOf(lines.slice(2, 5)) });
	const t = trigramsOf(lines);
	const r = raw();
	// 互与本同者唯乾坤 —— 此时互其变卦
	const same = t && r.xiaHu === t.lo && r.shangHu === t.up;
	if (!same) return { ...r, fromBian: false };
	const bl = bianGua(lines, dongYao);
	if (!bl) return { ...r, fromBian: false, note: '互与本卦同（乾坤无互），然无动爻可变，仍出本互' };
	return {
		xiaHu: triOf(bl.slice(1, 4)), shangHu: triOf(bl.slice(2, 5)),
		fromBian: true, note: '乾坤无互，互其变卦',
	};
}

/** 体用：动爻所在为用卦、另一为体卦 */
export function tiYong(lines, dongYao) {
	const t = trigramsOf(lines);
	if (!t || !Number.isInteger(dongYao) || dongYao < 1 || dongYao > 6) return null;
	const yongZai = dongYao <= 3 ? 'lo' : 'up';
	return {
		yongGua: yongZai === 'lo' ? t.lo : t.up,
		tiGua: yongZai === 'lo' ? t.up : t.lo,
		yongZai, tiZai: yongZai === 'lo' ? 'up' : 'lo',
	};
}

/**
 * 体互/用互：体卦在上 → 上互为体之互、下互为用之互；体卦在下 → 反之。
 */
export function tiHuYongHu(lines, dongYao) {
	const hu = huGua(lines, dongYao);
	const ty = tiYong(lines, dongYao);
	if (!hu || !ty) return null;
	const tiShang = ty.tiZai === 'up';
	return {
		...hu, ...ty,
		tiHu: tiShang ? hu.shangHu : hu.xiaHu,
		yongHu: tiShang ? hu.xiaHu : hu.shangHu,
	};
}

/** 一盘之全变：本／互（两八卦）／变／错／综 + 体用 */
export function guaBianAll(up, lo, dongYao) {
	const lines = linesOf(up, lo);
	if (!lines) return null;
	const bl = bianGua(lines, dongYao);
	return {
		ben: { up, lo, lines },
		hu: tiHuYongHu(lines, dongYao),           // 🔴 只出八卦，不产六十四卦名
		bian: bl ? { ...trigramsOf(bl), lines: bl } : null,
		cuo: { ...trigramsOf(cuoGua(lines)), lines: cuoGua(lines) },
		zong: { ...trigramsOf(zongGua(lines)), lines: zongGua(lines) },
		dongYao,
	};
}

export default { huGua, tiYong, tiHuYongHu, bianGua, cuoGua, zongGua, guaBianAll, trigramsOf, linesOf };
