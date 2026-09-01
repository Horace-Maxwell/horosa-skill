import { Solar } from 'lunar-javascript';
import { buildFlowMonthsByYear, buildFlowDays, buildFlowHours } from '../vendor/bazi/baziLunarLocal.js';
import { parseDateParts } from '../vendor/bazi/dateStrSafe.js';
import { buildLocalBaziResult } from '../vendor/bazi/baziLunarLocal.js';

/**
 * 八字 [多运限·指定时段] 段。
 *
 * 上游该段由用户在界面**勾选**具体的流年/流月/流日/流时组合驱动（`body.length === 0` 就整段不产）。
 * headless 没有界面，故把同一份选择开成显式入参 `period`：
 *   { liunian:[公历年…], liuyue:[月序 1–12…], liuri:[公历日…], liushi:[时辰序 0–11…] }
 * 语义与上游一致：流年 × 流月笛卡尔各一段；流日/流时锚定到所选的第一个上层；总段数封顶 50。
 *
 * 函数体（gzText / findFlowMonthByOrd / findBaziLiunian / buildBaziPeriodLines）逐字取自上游
 * BaZi.js，只把两张模块级表与封顶常量一并搬来。
 *
 * payload: { birth: {date, time, gender, …}, period: {…} }
 * return : { text }
 */

// 以下三个模块级常量逐字取自上游 BaZi.js。
const BAZI_PERIOD_MAX_SEGMENTS = 50;
const SHICHEN_LABEL = ['子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥'];
const FLOW_MONTH_TERMS = ['立春', '惊蛰', '清明', '立夏', '芒种', '小暑', '立秋', '白露', '寒露', '立冬', '大雪', '小寒'];

function gzText(zhu){
	if(!zhu){
		return '';
	}
	const gan = zhu.stem && zhu.stem.cell ? zhu.stem.cell : '';
	const zhi = zhu.branch && zhu.branch.cell ? zhu.branch.cell : '';
	const relGan = zhu.stem && zhu.stem.relative ? `，干十神:${zhu.stem.relative}` : '';
	const relZhi = zhu.branch && zhu.branch.relative ? `，支十神:${zhu.branch.relative}` : '';
	return `${gan}${zhi}${relGan}${relZhi}`;
}
function findFlowMonthByOrd(months, ord){
	const term = FLOW_MONTH_TERMS[ord - 1];
	if(!term || !Array.isArray(months)){
		return null;
	}
	return months.find((m)=>m && m.term === term) || null;
}
function findBaziLiunian(bazi, year){
	const blocks = (bazi && Array.isArray(bazi.direction)) ? bazi.direction : [];
	for(let i = 0; i < blocks.length; i++){
		const subs = (blocks[i] && Array.isArray(blocks[i].subDirect)) ? blocks[i].subDirect : [];
		const hit = subs.find((s)=>Number(s.year) === year);
		if(hit){
			return hit;
		}
	}
	return null;
}
function buildBaziPeriodLines(bazi, period, params){
	if(!bazi || !period){
		return [];
	}
	const arr = (v)=>(Array.isArray(v) ? v : []);
	const liunianSel = arr(period.liunian);
	const liuyueSel = arr(period.liuyue);
	const liuriSel = arr(period.liuri);
	const liushiSel = arr(period.liushi);

	const four = bazi.fourColumns || {};
	const dayGz = gzText(four.day);
	const dayGan = (four.day && (four.day.ganzi || four.day.ganZhi) ? `${four.day.ganzi || four.day.ganZhi}` : `${dayGz}`).charAt(0);
	// perf 惰性化：非「当前公历年所在大运」的流年 flowMonths=null（buildLocalBaziResult 只 eager 算当前大运）。
	// 多运限读到 null 时按公历年 on-demand 补算（buildFlowMonthsByYear，与 eager 逐字等价）。birthSolar 仅用于
	// 生年早月过滤（大运流年几乎非生年，不影响），由 params.date 重建。
	let birthSolar = null;
	try{
		if(params && params.date){
			const _bp = parseDateParts(`${params.date}`) || {};
			const by = _bp.year, bm = _bp.month, bd = _bp.day;
			if(Number.isFinite(by) && Number.isFinite(bm) && Number.isFinite(bd)){
				birthSolar = Solar.fromYmd(by, bm, bd);
			}
		}
	}catch(e){ birthSolar = null; }
	const flowMonthsOf = (ln)=>{
		if(ln && Array.isArray(ln.flowMonths)){
			return ln.flowMonths;
		}
		if(ln && ln.flowMonths === null && Number.isFinite(Number(ln.year))){
			return buildFlowMonthsByYear(Number(ln.year), birthSolar, dayGan);
		}
		return [];
	};

	const body = [];
	let truncated = false;
	const pushLine = (line)=>{
		if(truncated){ return; }
		if(body.length >= BAZI_PERIOD_MAX_SEGMENTS){ truncated = true; return; }
		body.push(line);
	};
	const flowText = (item)=>gzText(item) || `${(item && (item.ganzi || item.ganZhi)) || ''}`;

	// 1) 流年：每个所选公历年各一段。
	liunianSel.forEach((year)=>{
		const ln = findBaziLiunian(bazi, year);
		if(ln){
			pushLine(`流年：${year}年 ${flowText(ln)}`);
		}else{
			pushLine(`流年：${year}年（超出大运范围，未列流年）`);
		}
	});

	// 流月/流日/流时所需的基准年集合：所选流年；若未选流年，则用大运数据里最早的流年兜底（绝不抛）。
	const firstAvailYear = (()=>{
		const blocks = Array.isArray(bazi.direction) ? bazi.direction : [];
		for(let i = 0; i < blocks.length; i++){
			const subs = (blocks[i] && Array.isArray(blocks[i].subDirect)) ? blocks[i].subDirect : [];
			if(subs.length && Number.isFinite(Number(subs[0].year))){
				return Number(subs[0].year);
			}
		}
		return null;
	})();
	const baseYears = liunianSel.length ? liunianSel : (firstAvailYear !== null ? [firstAvailYear] : []);

	// 2) 流月：流年 × 流月（节气月序1–12）笛卡尔。
	// 坑修：按节气月号(term)匹配 flowMonths，而非数组下标 ord-1。生年的 flowMonths 从「出生月之节气」起过滤
	// （数组<12 项），用 months[ord-1] 会整体错位、且选「第1月」可能取到非立春月或落空被静默丢。改 term 匹配后
	// 非生年逐字不变（全 12 项时 term 顺序 === ord 顺序），生年缺的早月 → 打印提示行而非静默丢。
	if(liuyueSel.length){
		baseYears.forEach((year)=>{
			const ln = findBaziLiunian(bazi, year);
			const months = flowMonthsOf(ln);
			liuyueSel.forEach((ord)=>{
				const fm = findFlowMonthByOrd(months, ord);
				if(fm){
					// 第12月(小寒)是命理年最后一个节气月,其公历日期落在「次年」年初(spillover,见 baziLunarLocal buildFlowMonths
					// year+1 分支)。故 date 显次年-01-… 属正常,加「(跨次年初)」注明,免与行首 ${year}年 看似错位。
					const crossYearNote = ord === 12 ? '（跨次年初）' : '';
					pushLine(`流月：${year}年 第${ord}月（${fm.term || ''}，${fm.date || ''}${crossYearNote}）${flowText(fm)}`);
				}else{
					pushLine(`流月：${year}年 第${ord}月（${FLOW_MONTH_TERMS[ord - 1] || ''}）（生年此月在出生前/无）`);
				}
			});
		});
	}

	// 锚定上层：流日 → 第一个 (流年, 流月)；流时 → 第一个 (流年, 流月, 流日)。
	const anchorYear = baseYears.length ? baseYears[0] : null;
	const anchorLn = anchorYear !== null ? findBaziLiunian(bazi, anchorYear) : null;
	const anchorMonths = flowMonthsOf(anchorLn);
	// 锚定流月对象（取所选首月序，否则首个 flowMonth）→ 其公历 (year, month) 供枚举流日。
	// 按节气月号匹配（与流月段同口径）；生年所选首月若被过滤则回退首个可用 flowMonth，避免流日/流时锚定落空。
	const anchorFm = liuyueSel.length
		? (findFlowMonthByOrd(anchorMonths, liuyueSel[0]) || anchorMonths[0])
		: anchorMonths[0];

	// 3) 流日：buildFlowDays(锚定流月的公历 year, month)；对每个所选日各一段。
	if(liuriSel.length && anchorFm && Number.isFinite(anchorFm.year) && Number.isFinite(anchorFm.month)){
		const days = buildFlowDays(anchorFm.year, anchorFm.month, dayGan);
		liuriSel.forEach((d)=>{
			const fd = days.find((x)=>x.day === d);
			if(fd){
				pushLine(`流日：${fd.date || `${anchorFm.year}-${anchorFm.month}-${d}`} ${flowText(fd)}`);
			}
		});
	}

	// 4) 流时：buildFlowHours(锚定流月公历 year, month, 首个所选流日)；对每个所选时辰各一段。
	if(liushiSel.length && anchorFm && Number.isFinite(anchorFm.year) && Number.isFinite(anchorFm.month)){
		const anchorDay = liuriSel.length ? liuriSel[0] : 1;
		const hours = buildFlowHours(anchorFm.year, anchorFm.month, anchorDay, dayGan);
		liushiSel.forEach((h)=>{
			const fh = hours.find((x)=>x.hourIdx === h);
			if(fh){
				pushLine(`流时：${anchorFm.year}-${anchorFm.month}-${anchorDay} ${SHICHEN_LABEL[h] || h}时 ${flowText(fh)}`);
			}
		});
	}

	if(body.length === 0){
		return [];
	}
	const lines = ['', '[多运限·指定时段]'];
	body.forEach((l)=>lines.push(l));
	if(truncated){
		lines.push(`（多运限段已达上限 ${BAZI_PERIOD_MAX_SEGMENTS} 段，余下所选组合已省略）`);
	}
	return lines;
}

export function runBaziPeriod(payload) {
  const source = payload && typeof payload === 'object' ? payload : {};
  const period = source.period && typeof source.period === 'object' ? source.period : null;
  if (!period || !source.birth) {
    return { text: '' };
  }
  try {
    const local = buildLocalBaziResult(source.birth);
    const bazi = local && local.bazi ? local.bazi : null;
    if (!bazi) {
      return { text: '' };
    }
    const lines = buildBaziPeriodLines(bazi, period, source.birth) || [];
    if (!lines.length) {
      return { text: '', error: { code: 'empty_period_lines', message: '所选运限时段未产出任何行（period 选择可能不含有效项）。' } };
    }
    return { text: lines.filter((l) => l !== '').join('\n') };
  } catch (error) {
    // 🔴 裸 catch 回空 = 调用方拿不到任何信号，段消失得像「本来就没有」。
    return { text: '', error: { code: 'period_build_failed', message: error instanceof Error ? error.message : `${error}` } };
  }
}

export default runBaziPeriod;
