// 八字快照 builder —— 自上游 components/cntradition/BaZi.js **逐字**抽出（bespoke，derived_from 由
// contracts/vendor_manifest.json 的 derived_sha256 看守：上游 BaZi.js 一动即红，复核本文件后 --restamp）。
// 上游这些纯函数与 React 组件同在一个 1200+ 行文件里（整份 vendor 会把 JSX/antd 带进来），故只抽快照闭包：
//   · gzText / gzCells —— [四柱与三元] 表格单元（BaZi.js:34-43 / :79-100）
//   · buildBaziPeriodLines 及其常量/查找函数 —— [多运限·指定时段]（BaZi.js:102-265）
//   · buildBaziSnapshotText —— 整份八字 AI 快照（BaZi.js:267-610）
//   · normalizeBaziGender / normalizeBaziResult —— 取数后的结果归一（BaZi.js:658-687）
// 函数体与模块级常量逐字未改；只有下方 import 按 vendor 树改了路径（上游是 ../../utils/xxx）。
// 上游页面主路径（fetchBaziCached，BaZi.js:716-755）= 本地 buildLocalBaziResult 优先、抛错才回退 Java
// /bazi/birth；两条路都经 normalizeBaziResult → buildBaziSnapshotText。编排见 tools/baziLocal.js。
import { Solar } from 'lunar-javascript';
import { buildTimeBasisLine } from '../utils/timeBasisLine.js';
import { buildFlowDays, buildFlowHours, buildFlowMonthsByYear, getSelfZuo } from './baziLunarLocal.js';
import { filterShenShaByGroups } from './baziShenShaLocal.js';
import { parseDateParts } from './dateStrSafe.js';

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

// [四柱与三元]4 主柱 GFM 表化用:把 gzText/gzDetailText 的同源值逐字拆成单元格(干支/藏干/十神/纳音/星运/自坐/空亡)。
// 值表达式与 gzText/gzDetailText 逐字同源(stem.cell/branch.cell/relative、stemInBranch、naying、getSelfZuo、xunEmpty)。
function gzCells(zhu, dayGan, phaseType){
	const gan = zhu && zhu.stem && zhu.stem.cell ? zhu.stem.cell : '';
	const zhi = zhu && zhu.branch && zhu.branch.cell ? zhu.branch.cell : '';
	const stemRel = zhu && zhu.stem && zhu.stem.relative ? zhu.stem.relative : '';
	const branchRel = zhu && zhu.branch && zhu.branch.relative ? zhu.branch.relative : '';
	const hidden = zhu && Array.isArray(zhu.stemInBranch)
		? zhu.stemInBranch.map((item)=>`${(item && item.cell) || ''}${(item && item.relative) || ''}`).filter(Boolean)
		: [];
	return {
		ganzhi: `${gan}${zhi}` || '—',
		cang: hidden.length ? hidden.join('、') : '—',
		shishen: [stemRel, branchRel].filter(Boolean).join('·') || '—',
		naying: (zhu && zhu.naying) || '—',
		// [Q-431/T-394] 纳音长生(各柱纳音五行坐该支的十二长生位;古法盘「纳音长生」行 / 纳音古法信息卡同源字段 nayingPhase)
		nayingPhase: (zhu && zhu.nayingPhase) || '—',
		xingYun: getSelfZuo(dayGan, zhi, phaseType) || '—',
		ziZuo: getSelfZuo(gan, zhi, phaseType) || '—',
		kong: (zhu && zhu.xunEmpty) || '—',
	};
}

// 多运限段数封顶（批A）：流年/流月/流日/流时合计封顶，防快照爆；超限截断 + 提示行。
const BAZI_PERIOD_MAX_SEGMENTS = 50;
const SHICHEN_LABEL = ['子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥'];
// 节气月号 1–12 → 该月起始「节」名（立春=1…小寒=12；万年不变常量，镜像 BaZiLuckFlowPanel.FLOW_JIEQI_TERMS）。
// 用于按节气月号匹配 flowMonths（生年的 flowMonths 会过滤掉出生前的早月、数组<12 项，不能用数组下标 ord-1 索引）。
const FLOW_MONTH_TERMS = ['立春', '惊蛰', '清明', '立夏', '芒种', '小暑', '立秋', '白露', '寒露', '立冬', '大雪', '小寒'];
// 按节气月号 ord(1–12) 在某流年的 flowMonths 中找对应项（按 term 匹配，非数组下标）。找不到 → null（生年早月被过滤）。
function findFlowMonthByOrd(months, ord){
	const term = FLOW_MONTH_TERMS[ord - 1];
	if(!term || !Array.isArray(months)){
		return null;
	}
	return months.find((m)=>m && m.term === term) || null;
}

// 在全部 direction 板块的 subDirect 中找某公历年的流年项（含其 ganzi/flowMonths）。
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

// 多运限段（批A）：流年/流月读现成 subDirect[].flowMonths；流日/流时调 buildFlowDays/Hours（与四柱同口径）。
// period={liunian:[year...], liuyue:[月序1–12...], liuri:[公历日...], liushi:[时辰序0–11...]}。
// 语义：流年/流月对所选每项各一段（流年×流月笛卡尔）；流日/流时锚定到所选的第一个上层。总段数封顶。
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

function buildBaziSnapshotText(params, result){
	const bazi = result && result.bazi ? result.bazi : {};
	const four = bazi.fourColumns || {};
	const lines = [];
	const labelMap = {
		gender: {
			'-1': '未知',
			'0': '女',
			'1': '男',
		},
		timeAlg: {
			'0': '真太阳时',
			'1': '直接时间',
			'2': '春分定卯时',
			'3': '平太阳时(仅经度)',
		},
		adjustJieqi: {
			'0': '不调整节气',
			'1': '节气按纬度调整',
		},
	};
	const getGz = (item)=>{
		if(!item){
			return '';
		}
		return item.ganzhi || item.ganzi || item.ganZhi || '';
	};
	const formatLabel = (dictName, value)=>{
		const dict = labelMap[dictName] || {};
		const key = `${value}`;
		if(dict[key] !== undefined){
			return dict[key];
		}
		return value;
	};
	const getNongliLine = (nongli)=>{
		if(!nongli){
			return '';
		}
		const leap = nongli.leap ? '闰' : '';
		return `${nongli.year || ''}年${leap}${nongli.month || ''}${nongli.day || ''}`;
	};
	const appendIf = (label, value)=>{
		if(value === undefined || value === null || value === ''){
			return;
		}
		lines.push(`${label}：${value}`);
	};
	const collectGodNames = (node)=>{
		if(!node){
			return [];
		}
		const all = [];
		if(Array.isArray(node.goodGods)){
			all.push(...node.goodGods);
		}
		if(Array.isArray(node.neutralGods)){
			all.push(...node.neutralGods);
		}
		if(Array.isArray(node.badGods)){
			all.push(...node.badGods);
		}
		// 神煞分组过滤(所见即所得:快照与面板同一 groups;默认全开=原样零回归)。
		return filterShenShaByGroups(all.filter(Boolean), params && params.shenshaGroups);
	};
	const gzGodText = (zhu)=>{
		if(!zhu){
			return '无';
		}
		const whole = collectGodNames(zhu);
		const stem = collectGodNames(zhu.stem);
		const branch = collectGodNames(zhu.branch);
		const taiSui = zhu.branch && Array.isArray(zhu.branch.taisuiGods) ? zhu.branch.taisuiGods.filter(Boolean) : [];
		const wholeTxt = whole.length ? whole.join('、') : '无';
		const stemTxt = stem.length ? stem.join('、') : '无';
		const branchTxt = branch.length ? branch.join('、') : '无';
		const taiSuiTxt = taiSui.length ? taiSui.join('、') : '无';
		return `整柱=${wholeTxt}；天干=${stemTxt}；地支=${branchTxt}；太岁=${taiSuiTxt}`;
	};
	let baziGender = bazi && bazi.gender === 'Female' ? '坤造' : (bazi && bazi.gender === 'Male' ? '乾造' : '');
	if(!baziGender){
		if(Number(params.gender) === 0){
			baziGender = '坤造';
		}else if(Number(params.gender) === 1){
			baziGender = '乾造';
		}
	}

	lines.push('[起盘信息]');
	appendIf('日期', `${params.date} ${params.time}`);
	appendIf('时区', params.zone);
	appendIf('经纬度', `${params.lon} ${params.lat}`);
	appendIf('性别', formatLabel('gender', params.gender));
	appendIf('时间算法', formatLabel('timeAlg', params.timeAlg));
	lines.push(buildTimeBasisLine({ timeAlg: params.timeAlg, lateZiHourUseNextDay: params.lateZiHourUseNextDay, after23NewDay: params.after23NewDay }));
	appendIf('节气修正', formatLabel('adjustJieqi', params.adjustJieqi));
	appendIf('命造', baziGender);
	const nongli = bazi && bazi.nongli ? bazi.nongli : {};
	const nltxt = getNongliLine(nongli);
	const clockTm = nongli.clockTime || `${params.date} ${params.time}`;
	const solarTm = nongli.solarTime || nongli.birth || `${params.date} ${params.time}`;
	lines.push(`农历：${nltxt || '未知'}`);
	// [Q-191/T-135] 生肖归属(立春 / 正月初一)此前只在页面卡片上出现,快照没有 —— AI 只能自己猜岁首,
	// 而两档在正月初一与立春之间出生的人正好差一个生肖。缺档按页面缺省(立春)。
	const zodiacByLunar = `${params.zodiacBoundary || ''}` === 'lunar';
	const shengXiao = zodiacByLunar ? nongli.shengXiaoLunar : nongli.shengXiaoLichun;
	if(shengXiao){
		lines.push(`生肖：${shengXiao}（岁首=${zodiacByLunar ? '正月初一' : '立春'}）`);
	}
	lines.push(`直接时间：${clockTm || '未知'}　真太阳时：${solarTm || '未知'}`);
	const jiedelta = nongli.jiedelta || '';
	const chef = nongli.chef || '';
	const tiaohou = Array.isArray(bazi.tiaohou) ? bazi.tiaohou.join('，') : '';
	const fixedLine = [jiedelta, chef].filter(Boolean).join('，');
	const fixedBase = (fixedLine || '立春后信息：无').replace(/[；，\s]+$/g, '');
	lines.push(`${fixedBase}； 调候：${tiaohou || '无'}`);

	lines.push('');
	lines.push('[四柱与三元]');
	// 每柱行尾补明细括注（藏干/纳音/星运/自坐/空亡，中栏四柱板同源）；行首「干支+干支十神」前缀逐字不动（段内纯增）。
	const dayGanCell = four.day && four.day.stem ? four.day.stem.cell : '';
	// [Q-431/T-394] 加「纳音长生」列:按纳音古法论命时缺「纳音坐支长生」判据(此前只写纳音名)。
	lines.push('| 柱 | 干支 | 藏干 | 十神 | 纳音 | 纳音长生 | 星运 | 自坐 | 空亡 |');
	lines.push('| --- | --- | --- | --- | --- | --- | --- | --- | --- |');
	[['年柱', four.year], ['月柱', four.month], ['日柱', four.day], ['时柱', four.time]].forEach(([label, zhu])=>{
		const c = gzCells(zhu, dayGanCell, params && params.phaseType);
		lines.push(`| ${label} | ${c.ganzhi} | ${c.cang} | ${c.shishen} | ${c.naying} | ${c.nayingPhase} | ${c.xingYun} | ${c.ziZuo} | ${c.kong} |`);
	});
	lines.push(`胎元：${gzText(four.tai)}`);
	// [Q-367/T-348] 公元前等本地引擎不可用而回退 Java 的域:Java 只识 xingming,tongxing/shufa 都走子平数法表 → 按实际口径如实标注。
	const _mgLabel = (params && params.minggongMethod === 'shufa') ? '子平数法' : ((result && result.local) ? '通行版' : '子平数法(本域回退)');
	lines.push(`命宫：${gzText(four.ming)}（起法：${_mgLabel}）`);
	lines.push(`身宫：${gzText(four.shen)}`);
	// 十二串宫(中栏四柱板「串宫」芯片,快照曾恒缺——同段胎元/命宫/身宫都有独漏此项):
	// 支为主,星/神煞/卦 best-effort 随源(仅后端盘带),字段与 ZhuMing12 组件同源;缺 zhi 不产行。
	const m12 = four.ming12 || {};
	if(m12.zhi){
		const m12Extra = [m12.star, (Array.isArray(m12.gods) && m12.gods.length) ? m12.gods.join('，') : '', m12.gua]
			.filter(Boolean).join('；');
		lines.push(`十二串宫：${m12.zhi}${m12Extra ? `（${m12Extra}）` : ''}`);
	}

	lines.push('');
	lines.push('[神煞（四柱与三元）]');
	lines.push(`年柱：${gzGodText(four.year)}`);
	lines.push(`月柱：${gzGodText(four.month)}`);
	lines.push(`日柱：${gzGodText(four.day)}`);
	lines.push(`时柱：${gzGodText(four.time)}`);
	lines.push(`胎元：${gzGodText(four.tai)}`);
	lines.push(`命宫：${gzGodText(four.ming)}`);
	lines.push(`身宫：${gzGodText(four.shen)}`);

	if(bazi.wuxingStat && Array.isArray(bazi.wuxingStat.scores) && bazi.wuxingStat.scores.length){
		const st = bazi.wuxingStat;
		lines.push('');
		lines.push('[五行力量]');
		lines.push(st.cangVersion === 'fenye'
			? '（分野加权：天干100/本气100/中气60/余气30；月柱仅当令司令吃月令×1.5，余月支藏干不加月乘）'
			: '（通行示例权重：天干100/本气100/中气60/余气30/月令×1.5）');
		lines.push('| 五行 | 占比 |');
		lines.push('| --- | --- |');
		st.scores.forEach((s)=>{ lines.push(`| ${s.label} | ${s.percent}% |`); });
		lines.push(`最旺：${st.dominant}　最弱：${st.weakest}`);
		if(st.dayMaster){
			lines.push(`日主${st.dayMaster.element}：${st.dayMaster.verdict}（同党印比 ${st.dayMaster.samePercent}% · 异党 ${Math.round((100 - st.dayMaster.samePercent) * 10) / 10}%）`);
		}
		if(st.dimensions){
			const d = st.dimensions;
			lines.push(`三维分列：${d.summary}`);
			if(d.deLing){ lines.push(`· 得令：月令${d.deLing.state}（${d.deLing.score > 0 ? '+' : ''}${d.deLing.score}）`); }
			if(d.deDi && d.deDi.roots && d.deDi.roots.length){
				lines.push(`· 得地：${d.deDi.roots.map((r)=>`${r.pillar}${r.branch}(${r.type})`).join('、')}（+${d.deDi.score}）`);
			}else{
				lines.push('· 得地：四支无根（虚浮）');
			}
			if(d.deShi && d.deShi.count){
				lines.push(`· 得势：${d.deShi.stems.map((s)=>`${s.pillar}${s.gan}(${s.rel})`).join('、')}（+${d.deShi.score}）`);
			}else{
				lines.push('· 得势：印比不透干');
			}
		}
	}

	if(bazi.gejuYongShen && (bazi.gejuYongShen.geju || bazi.gejuYongShen.yongshen)){
		const gy = bazi.gejuYongShen;
		const SCHOOL_LABEL = { zonghe: '传统综合', fuyi: '扶抑派', geju: '格局派', tiaohou: '调候派', bingyao: '病药派', mangpai: '盲派', nayin: '纳音古法', tongguan: '通关派' };
		lines.push('');
		lines.push('[格局·用神]');
		lines.push(`当前主用流派：${SCHOOL_LABEL[(params && params.school)] || '传统综合'}（各派取用可异，下列多派对照）`);
		if(gy.geju){
			lines.push(`格局：${gy.geju.name}（月令${gy.geju.tenGod || '—'}·${gy.geju.via}）`);
		}
		if(gy.chengBai){
			lines.push(`成败：${gy.chengBai.verdict}——${gy.chengBai.reason}（${gy.chengBai.note}）`);
		}
		if(Array.isArray(gy.schools) && gy.schools.length){
			lines.push('多派用神对照：');
			lines.push('| 流派 | 喜用 | 忌 | 备注 |');
			lines.push('| --- | --- | --- | --- |');
			gy.schools.forEach((s)=>{
				lines.push(`| ${s.school}${s.verdict ? `·${s.verdict}` : ''} | ${(s.xi && s.xi.join('·')) || '—'} | ${(s.ji && s.ji.length ? s.ji.join('·') : '—')} | ${s.note} |`);
			});
		}else if(gy.yongshen){
			const yo = gy.yongshen;
			lines.push(`用神（${yo.school}·${yo.verdict}）：喜用 ${yo.xi.join('·') || '—'}　忌 ${yo.ji.join('·') || '—'}`);
			lines.push(`说明：${yo.note}`);
		}
		if(Array.isArray(gy.bianGe) && gy.bianGe.length){
			lines.push('疑似变格（需复核）：');
			gy.bianGe.forEach((b)=>{
				lines.push(`· ${b.type}·${b.name}（${b.cond}）→ 若成立用${b.yong}、忌${b.bei}；${b.note}`);
			});
		}
		if(Array.isArray(gy.zaGe) && gy.zaGe.length){
			lines.push('杂格（正格优先，需复核填实刑冲；虚邀暗冲类附真/假判定）：');
			gy.zaGe.forEach((b)=>{
				const tag = b.quality ? `【${b.quality}${b.broken && b.broken.length ? `·${b.broken.join('、')}` : ''}】` : '';
				lines.push(`· ${b.name}${tag}（${b.cond}）：${b.note}`);
			});
		}
	}

	if(bazi.mangpai && Array.isArray(bazi.mangpai.cells)){
		const mp = bazi.mangpai;
		lines.push('');
		lines.push('[盲派结构]');
		lines.push('（象法·参考，与扶抑/格局体系不同）');
		lines.push(`宾主：${mp.cells.map((c)=>`${c.label}${c.role}(${c.gan}${c.zhi})`).join(' ')}`);
		if(mp.zuogong && mp.zuogong.length){
			lines.push('做功路线：');
			mp.zuogong.forEach((z)=>lines.push(`· ${z.text}`));
		}else{
			lines.push('做功：主位之体未直接取宾位之用（多看刑冲合害引动）。');
		}
		if(mp.feishen && mp.feishen.length){ lines.push(`废神：${mp.feishen.join('、')}`); }
	}

	if(bazi.fenYe && bazi.fenYe.ruler){
		const fy = bazi.fenYe;
		lines.push('');
		lines.push('[月令司令（分野）]');
		lines.push(`版本：${fy.versionLabel}`);
		lines.push(`节后 ${fy.daysAfterJie} 日，当令：${fy.ruler.gan}（${fy.ruler.pos}）`);
		lines.push(`轮值：${fy.segments.map((s)=>`${s.gan}${s.pos}${s.days}日`).join(' → ')}`);
	}

	// [干支合冲] legacy 天干/地支两 tab 的刑冲合害全表,快照曾恒缺。字段与 GanHeCong/ZiHeCong
	// 组件同源(four.ganHe/ganCong + ziHe6合/ziHe3拱/ziHui会/ziXing刑/ziCong冲/ziCuan穿/ziPo破);全空不产段。
	const relLine = (label, rec)=>{
		const parts = [];
		Object.keys(rec || {}).forEach((key)=>{
			const ary = rec[key];
			if(Array.isArray(ary) && ary.length){
				parts.push(`${ary.map((item)=>`${(item && item.cell) || ''}（${(item && item.zhu) || ''}）`).join(' ')}→${key}`);
			}
		});
		return parts.length ? `${label}：${parts.join('；')}` : '';
	};
	const heCongLines = [
		relLine('干合', four.ganHe), relLine('干冲', four.ganCong),
		relLine('支合', four.ziHe6), relLine('支拱', four.ziHe3), relLine('支会', four.ziHui),
		relLine('支刑', four.ziXing), relLine('支冲', four.ziCong), relLine('支穿', four.ziCuan), relLine('支破', four.ziPo),
	].filter(Boolean);
	if(heCongLines.length){
		lines.push('');
		lines.push('[干支合冲]');
		lines.push(...heCongLines);
	}

	// 小运(legacy 小运 tab,快照曾恒缺):逐年小运/流年并列,字段与 SmallDirection 同源(d.direct/d.yearGanzi)。
	const smallDirs = Array.isArray(bazi.smallDirection) ? bazi.smallDirection : [];
	if((bazi.mainDirection && bazi.mainDirection.length) || smallDirs.length){
		lines.push('');
		lines.push('[大运]');
		// [挂载自检 F-54] 起运(页面信息面板恒显;精度随「起运精度」档):快照此前只有逐步起运年 → AI 不知几岁几月起运,且精度齿轮无处落地。
		if(bazi.directInfo){ lines.push(`起运：${bazi.directInfo}`); }
		if(bazi.mainDirection && bazi.mainDirection.length){
			// [v2 排版批量·表化] 同构逐条行改 GFM 表（紫微宫位总览范式）：段头/值表达式零变更
			// （第N步/item.year/getGz 逐字复用），仅排版骨架换表头+分隔行+数据行；归一器/docx/PDF 表块直通。
			lines.push('| 步序 | 起运年 | 干支 |');
			lines.push('| --- | --- | --- |');
			bazi.mainDirection.forEach((item, idx)=>{
				const y = item.year !== undefined ? `${item.year}` : '';
				const gz = getGz(item);
				lines.push(`| 第${idx + 1}步 | ${y} | ${gz} |`);
			});
		}
		if(smallDirs.length){
			// [Q-191/T-135] 表头此前恒写「周岁」,而 d.age 是虚岁(出生=1 岁,与页面小运表同源)——
			// AI 按周岁读会整体差一岁。改为跟「年龄」档(虚岁默认 / 周岁 = 虚岁 −1),表头与数值同一口径。
			const realAge = `${params.ageStyle || ''}` === 'real';
			lines.push('小运（逐年，与流年并列）：');
			lines.push(`| 年份 | ${realAge ? '周岁' : '虚岁'} | 小运 | 流年 |`);
			lines.push('| --- | --- | --- | --- |');
			smallDirs.forEach((dir)=>{
				const d = dir || {};
				const sub = d.direct || {};
				const yr = d.yearGanzi || {};
				const ageVal = d.age === undefined || d.age === null || !Number.isFinite(Number(d.age))
					? '无'
					: (realAge ? Math.max(0, Number(d.age) - 1) : Number(d.age));
				lines.push(`| ${d.year !== undefined ? d.year : '无'} | ${ageVal} | ${sub.ganzi || '无'} | ${yr.ganzi || '无'} |`);
			});
		}
	}

	if(bazi.direction && bazi.direction.length){
		lines.push('');
		lines.push('[流年行运概略]');
		// [v2 排版批量·表化] 每板块「概略+流年」两行并为一表行：值表达式逐字复用
		// （startYear/startAge/dayunGz/yearGzs 组装式不动），旧行标签词（起始年/起始年龄/大运/流年）上移表头。
		lines.push('| 板块 | 起始年 | 起始年龄 | 大运 | 流年 |');
		lines.push('| --- | --- | --- | --- | --- |');
		bazi.direction.forEach((block, idx)=>{
			const startYear = block && block.startYear !== undefined ? `${block.startYear}` : '';
			const startAge = block && block.age !== undefined ? `${block.age}` : '';
			const dayunGz = getGz(block ? block.mainDirect : null);
			const startYearNum = block && block.startYear !== undefined ? Number(block.startYear) : null;
			const yearGzs = (block && block.subDirect && block.subDirect.length ? block.subDirect : [])
				.map((sub, subIdx)=>{
					const gz = getGz(sub);
					if(!gz){
						return '';
					}
					const yearNum = Number.isFinite(startYearNum) ? startYearNum + subIdx : null;
					if(Number.isFinite(yearNum)){
						return `${yearNum}-${gz}`;
					}
					return gz;
				})
				.filter(Boolean);
			lines.push(`| 板块${idx + 1} | ${startYear} | ${startAge}岁 | ${dayunGz} | ${yearGzs.join(' ')} |`);
		});
	}

	// 多运限（批A）：仅挂载「每技法设置」显式选了流年/流月/流日/流时时追加；缺省不追加 → 快照与现状逐字一致。
	if(params && params.period){
		const periodLines = buildBaziPeriodLines(bazi, params.period, params);
		if(periodLines.length > 0){
			lines.push(...periodLines);
		}
	}
	return lines.join('\n');
}

function normalizeBaziGender(gender){
	if(gender === 'Male' || gender === 'Female'){
		return gender;
	}
	if(gender === false || `${gender}` === '0'){
		return 'Female';
	}
	if(gender === true || `${gender}` === '1'){
		return 'Male';
	}
	return '';
}

function normalizeBaziResult(result, params){
	if(!result){
		return result;
	}
	const next = {
		...result,
	};
	const bazi = {
		...(next.bazi || {}),
	};
	if(!bazi.gender){
		bazi.gender = next.gender || normalizeBaziGender(params ? params.gender : null);
	}
	next.bazi = bazi;
	next.coreOnly = !Array.isArray(bazi.direction) || bazi.direction.length === 0;
	return next;
}

export { gzText, gzCells, buildBaziPeriodLines, buildBaziSnapshotText, normalizeBaziGender, normalizeBaziResult };
