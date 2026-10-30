// 等宽分段的段号(0 起)单一来源:与计算服务 astrostudy/india/primitives.segment_index 同算法。
//
// 病理:宽度不能整除时(27 宿 360/27、28 宿 360/28、13°20′ …)k × 宽度在浮点里常比真段界小一点点
// (7 × 360/27 = 93.33333333333333,再 ÷ 360/27 = 6.999999999999999),裸 Math.floor(x / 宽度) 把恰在段界上的点落进前一段。
// 由段首反推出来的点、度数取整后的点都会撞上。这里先加 1e-9 的宽容再取整:精确段界一律归后一段,再夹到 [0, 段数 − 1]。
// 护栏:segmentBoundaryGuard.test.js(Math.floor(… / 非整除宽度) 即红)。
const SEG_EPS = 1e-9;

export function segmentIndex(value, span, count){
	const idx = Math.floor(Number(value) / Number(span) + SEG_EPS);
	if(!Number.isFinite(idx)){ return NaN; }
	const n = Math.trunc(Number(count));
	return Math.max(0, Math.min(n - 1, idx));
}

export default segmentIndex;
