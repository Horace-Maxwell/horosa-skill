// tongshu/sanyuanLiexiu.js — 三垣列宿加临（古法）引擎（纯前端·约略版）。
// 原理：三垣吉曜与地球黄道运行合会之时加临；缺星历时以「节气 ± 日数」约略定位。
// 源仅明载天帝加临（芒种+4日 & 大雪+3日）；余 15 曜精确加临须星历，此处仅列断语库、不臆造节气日。
import { Solar } from 'lunar-javascript';
import { SANYUAN_STARS } from './sanyuanData.js';

// 当年 24 节气公历日期（按年缓存）。
const jieqiCache = {};
function jieqiTableOf(y) {
	if (!jieqiCache[y]) { jieqiCache[y] = Solar.fromYmd(y, 6, 1).getLunar().getJieQiTable(); }
	return jieqiCache[y];
}
function dayDiff(y1, m1, d1, y2, m2, d2) {
	const a = new Date(y1, m1 - 1, d1).getTime();
	const b = new Date(y2, m2 - 1, d2).getTime();
	return Math.round((a - b) / 86400000);
}

// 判某日各吉曜是否加临（约略版；tol=容差日，默认 ±1）。
export function sanyuanLiexiuDay({ y, m, d }, tol = 1) {
	const tbl = jieqiTableOf(y);
	const stars = SANYUAN_STARS.map((star)=>{
		let hit = false;
		let hitInfo = null;
		let hitDate = null;
		(star.jieqiOffsets || []).forEach(([jq, off])=>{
			const base = tbl[jq];
			if (base) {
				const day0 = base.next(off);
				const diff = Math.abs(dayDiff(y, m, d, day0.getYear(), day0.getMonth(), day0.getDay()));
				if (diff <= tol) { hit = true; hitInfo = `${jq}+${off}日`; hitDate = day0.toYmd(); }
			}
		});
		return { ...star, hit, hitInfo, hitDate, positional: (star.jieqiOffsets || []).length > 0 };
	});
	return { y, m, d, stars, hitStars: stars.filter((s)=> s.hit) };
}

// 天帝加临日历点位（当年，供中栏展示）：仅有节气偏移的曜。
export function sanyuanYearPoints(y) {
	const tbl = jieqiTableOf(y);
	const points = [];
	SANYUAN_STARS.forEach((star)=>{
		(star.jieqiOffsets || []).forEach(([jq, off])=>{
			const base = tbl[jq];
			if (base) { points.push({ name: star.name, ymd: base.next(off).toYmd(), info: `${jq}+${off}日` }); }
		});
	});
	return points.sort((a, b)=> (a.ymd < b.ymd ? -1 : 1));
}

export default sanyuanLiexiuDay;
