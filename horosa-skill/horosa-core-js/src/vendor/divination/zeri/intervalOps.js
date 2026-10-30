// 扫描结果区间工具(纯函数)。区间记录 = {start, end, startJd, endJd, durationMin}(半开 [s,e))。
import { parseDateParts, formatSignedDate, toSlashDate, civilJdnOfYmd, addDisplayYears } from '../../bazi/dateStrSafe.js';

/** 多段扫描结果拼接:按 startJd 排序,相邻/重叠(段界共点)合并——月界 23:59/00:00 无缝。 */
export function stitchIntervals(lists){
	const all = [];
	(lists || []).forEach((list)=>{ (list || []).forEach((iv)=>{ all.push(iv); }); });
	all.sort((a, b)=>a.startJd - b.startJd);
	const out = [];
	const EPS = 0.7 / 1440.0; // 边界并合容差:0.7 分钟(分钟精度取整后的段界共点)
	all.forEach((iv)=>{
		const last = out[out.length - 1];
		if(last && iv.startJd <= last.endJd + EPS){
			if(iv.endJd > last.endJd){
				last.endJd = iv.endJd;
				last.end = iv.end;
			}
		}else{
			out.push({ ...iv });
		}
	});
	out.forEach((iv)=>{ iv.durationMin = Math.round((iv.endJd - iv.startJd) * 1440 * 10) / 10; });
	return out;
}

/** 自然月切段:[start, end] → [{startDate,startTime,endDate,endTime}](半开衔接,末段收在 end)。 */
export function splitByMonth(startDate, startTime, endDate, endTime){
	// 年月日按民用日期串解析(公元前前导负号、1–5 位年都对);逐月推进按显示年(无公元 0 年),先后按儒略日序数比
	const parse = (d)=>{
		const p = parseDateParts(d);
		return p ? { y: p.year, m: p.month, d: p.day } : { y: NaN, m: NaN, d: NaN };
	};
	const fmt = (y, m, d)=>toSlashDate(formatSignedDate(y, m, d));
	const s = parse(startDate);
	const e = parse(endDate);
	const segs = [];
	let curDate = fmt(s.y, s.m, s.d);
	let curTime = startTime || '00:00:00';
	let y = s.y;
	let m = s.m;
	const endNum = civilJdnOfYmd(e.y, e.m, e.d);
	for(let guard = 0; guard < 800; guard++){
		m += 1;
		if(m > 12){ m = 1; y = addDisplayYears(y, 1); }
		const boundaryNum = civilJdnOfYmd(y, m, 1);
		if(!(boundaryNum <= endNum) || (boundaryNum === endNum && (endTime || '23:59:59') <= '00:00:00')){
			segs.push({ startDate: curDate, startTime: curTime, endDate: fmt(e.y, e.m, e.d), endTime: endTime || '23:59:59' });
			break;
		}
		const boundary = fmt(y, m, 1);
		segs.push({ startDate: curDate, startTime: curTime, endDate: boundary, endTime: '00:00:00' });
		curDate = boundary;
		curTime = '00:00:00';
	}
	return segs;
}
