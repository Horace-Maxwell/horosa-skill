// 紫微快照「运限层」builder —— 自上游 components/ziwei/ZiWeiMain.js **逐字**抽出（bespoke，derived_from
// 由 contracts/vendor_manifest.json 的 derived_sha256 看守：上游 ZiWeiMain.js 一动即红，复核本文件后 --restamp）。
// 上游这些函数与 React 组件同在一个 1500+ 行文件里（整份 vendor 会把 JSX 带进来），故只抽纯函数闭包：
//   · buildZiweiPeriodOverviewLines —— [运限概览]（v3.11.0 #80，无条件段）
//   · buildZiweiPeriodLines / formatLuckLayerLines / findDaxianForYear —— [运限]（挂载所选运限层）
//   · buildZiweiOverlayLines —— [流派叠层]（流派开关 ground-truth）
// 函数体与两张模块级常量逐字未改；只有下方 import 按 vendor 树改了路径（上游是 ./ZWLuckPanel 等）。
// ⚠ ZWEngineOptions 是**可变单例**（ziweiOptions.js）：调用方负责按调用覆盖/还原（见 tools/ziweiExtras.js）。
import { ZWEngineOptions } from './ziweiOptions.js';
import { childLimits, zhongxianOf } from './ziweiCore.js';
import { qiShuWei, allBorrowedStars, taiSuiRuGua } from './ziweiOverlays.js';
import {
	buildDaxianItems,
	buildLiunianItems,
	buildXiaoxianItems,
	buildLiuyueItems,
	buildLiuriItems,
	buildLiushiItems,
	houseName as luckHouseName,
	houseIdxByBranch as luckHouseIdxByBranch,
} from './zwLuckItems.js';
import * as ZiWeiHelper from './ZiWeiHelper.js';

const ZW_PERIOD_LEVEL_LABEL = { daxian: '大限', liunian: '流年小限', liuyue: '流月', liuri: '流日', liushi: '流时' };

// 单层运限 → 文本块（四化落宫 + 流曜 + 三方四正星情, 复用 ZiWeiHelper.getLayerSihua/getFlowStars/collectFourPalaceStars,
// 与盘面交互卡同口径）。
// 用户增量(v1.9): 末尾追加"三方四正"四宫星曜列表,让 AI 看到该时段真实的三合宫位星情,提高流年判断准度。
function formatLuckLayerLines(chart, layer, levelLabel, subText){
	const lines = [];
	const mingIdx = layer.mingIndex;
	const oppIdx = ((mingIdx % 12) + 6) % 12;
	// [v2 试点] 头行加 ◆ 子题标记:呈现层(docx/PDF)映射 Heading3;纯文本仍整行可读(substring 断言不受影响)。
	const head = `◆ ${levelLabel}：${layer.ganzi || ''}${subText ? `（${subText}）` : ''}`
		+ `，命宫【${luckHouseName(chart, mingIdx, true)}】·对宫【${luckHouseName(chart, oppIdx, true)}】`;
	lines.push(head);
	// [B10-fix] 与面板同口径:消费期现算(effLayerSihuaGan),快照与 UI 恒同源
	const sihua = ZiWeiHelper.getLayerSihua(chart, ZiWeiHelper.effLayerSihuaGan(chart, layer)) || [];
	if(sihua.length > 0){
		const parts = sihua.map((h)=>`${h.star}化${h.hua}（${luckHouseName(chart, h.houseIndex, true)}）`);
		lines.push(`四化：${parts.join('、')}`);
	}
	// [D3] 流年神煞上盘开时:流年层追加 12 神落宫行(快照与盘面同源 getFlowJiangSui;默认关=基线字节稳)。
	if(ZWEngineOptions.flowShenshaOnChart && layer.zhi && levelLabel === ZW_PERIOD_LEVEL_LABEL.liunian){
		const fss = ZiWeiHelper.getFlowJiangSui(layer.zhi) || [];
		if(fss.length){
			const fmt = (g)=>fss.filter((x)=>x.group === g).map((x)=>`${x.name}(${x.zhi})`).join('、');
			lines.push(`流年神煞·将前：${fmt('jiang')}`);
			lines.push(`流年神煞·岁前：${fmt('sui')}`);
		}
	}
	const flowStars = ZiWeiHelper.getFlowStars(layer.gan, layer.zhi, ZiWeiHelper.hourZhiOf(chart)) || [];
	if(flowStars.length > 0){
		const parts = flowStars.map((s)=>`${s.name}（${luckHouseName(chart, luckHouseIdxByBranch(chart, s.zhi), true)}）`);
		lines.push(`流曜：${parts.join('、')}`);
	}
	// 运限三合(用户修正): 仅追加运财帛宫 + 运官禄宫(本宫和对宫已在 head 行).
	// label 用"运财帛宫【原命盘宫名·干支】" 让 AI 明确"这是该段时间的财帛宫,落在原命盘 X 宫位置"
	try {
		const sanhe = ZiWeiHelper.collectSanhePalaces(chart, mingIdx);
		if(sanhe && sanhe.length === 2){
			lines.push('运限三合：');
			sanhe.forEach((p)=>{
				const starsText = (p.stars && p.stars.length) ? p.stars.join('、') : '(无主辅星)';
				const gz = p.ganZhi ? `·${p.ganZhi}` : '';
				lines.push(`  ${p.runName}【${p.palaceName}${gz}】：${starsText}`);
			});
		}
	} catch(_) { /* defensive: 缺数据时不阻塞快照 */ }
	return lines;
}

// 多选运限上限：所有层级合计段数封顶，防快照爆（超限截断 + 追加提示行）。
const ZW_PERIOD_MAX_SEGMENTS = 50;

// 找某公历年所属的大限：逐大限构造 10 流年，命中该年即返回（复用 buildLiunianItems，零新算法）。
function findDaxianForYear(chart, daxianItems, year){
	for(let i = 0; i < daxianItems.length; i++){
		const items = buildLiunianItems(chart, daxianItems[i]);
		if(items.some((x)=>x.year === year)){
			return { daxian: daxianItems[i], liunianItems: items, liunian: items.find((x)=>x.year === year) || null };
		}
	}
	return null;
}

// [#80] 无条件「运限概览」段。
//   病理:八字给 AI 的 [大运] / [流年行运概略] 是**无条件段**(不碰齿轮也有全大运 × 各 10 流年的公历年+干支);
//   紫微此前什么都不给 —— 除非用户在 40 项设置里翻到最末组、往一个叫「流年小限」的**文本框**里手打年份。
//   用户报障「紫微挂载设置里似乎没找着流年的勾选项」,AI 也如实答「有本命盘和大限,缺少完整流年、流月盘」。
//   照抄八字范式:每个大限一行,把该限 10 个流年「公历年-干支」打包进末列 —— 12 行给全 120 年的映射。
//   只用已有纯函数(ZWLuckPanel 的 build*Items,与盘面交互同源、零新算法);**不依赖「今天」**,同一盘快照恒定。
//   用户显式选了运限时,下面的 [运限] 段照旧另出(完整流曜与四化落宫),两者互不影响。
function buildZiweiPeriodOverviewLines(chart){
	if(!chart || !chart.houses){ return []; }
	const daxianItems = buildDaxianItems(chart);
	if(!daxianItems.length){ return []; }
	const lines = ['[运限概览]'];
	lines.push('全大限 × 流年一览(公历年与干支由代码算出,禁自行推算):');
	lines.push('| 虚岁 | 宫位 | 宫干支 | 该限流年（公历年-干支） |');
	lines.push('| --- | --- | --- | --- |');
	daxianItems.forEach((d)=>{
		const years = buildLiunianItems(chart, d).map((x)=>`${x.year}-${x.ganzi}`).join('、');
		lines.push(`| ${d.start}~${d.end} | ${luckHouseName(chart, d.mingIndex, true)} | ${d.ganzi} | ${years || '—'} |`);
	});
	lines.push('要某一年/某月的完整流曜与四化落宫,请在「挂载设置 → 运限」里选定年月(或直接说出年份)。');
	lines.push('');
	return lines;
}

// 按挂载所选运限层（多选）产出 [运限] 段。
// period={daxian:[mingIndex...], liunian:[year...], liuyue:[month...], liuri:[day...], liushi:[hourIdx...]}。
// 语义（用户拍板）：大限/流年/流月对所选每项各产一段（流年×流月笛卡尔）；流日/流时锚定到所选的第一个上层。
// 总段数封顶 ZW_PERIOD_MAX_SEGMENTS，超限截断并追加提示行。全空 → 不产段（上游已用 null 守现状）。
function buildZiweiPeriodLines(chart, period){
	if(!chart || !chart.houses || !period){
		return [];
	}
	const daxianItems = buildDaxianItems(chart);
	if(daxianItems.length === 0){
		return [];
	}
	const arr = (v)=>(Array.isArray(v) ? v : []);
	const daxianSel = arr(period.daxian);
	const liunianSel = arr(period.liunian);
	const liuyueSel = arr(period.liuyue);
	const liuriSel = arr(period.liuri);
	const liushiSel = arr(period.liushi);

	const body = [];
	let truncated = false;
	// 推入一段（已含层文本）；到达上限即停止后续推入并标记截断。
	const pushSeg = (segLines)=>{
		if(truncated){ return; }
		if(body.length >= ZW_PERIOD_MAX_SEGMENTS){
			truncated = true;
			return;
		}
		body.push(segLines);
	};

	// 1) 大限：每个所选宫位序各一段。
	daxianSel.forEach((mingIndex)=>{
		const dx = daxianItems.find((d)=>d.mingIndex === mingIndex);
		if(dx){
			const seg = formatLuckLayerLines(chart, dx, ZW_PERIOD_LEVEL_LABEL.daxian, `${dx.start}~${dx.end}岁`);
			// [Q-432/T-395④] 「沈氏三限」齿轮开着时,页面在所选大限下画出四段中限(各 2.5 年),
			// 而快照此前只在「传本设置」里多一行注记 —— AI 看不到分段。开关开启时把四段真列出来
			// (宫位沿该大限宫,与 ziweiCore.zhongxianOf 同源;缺省关=零增行)。
			if(ZWEngineOptions.zhongxian && Array.isArray(seg)){
				try{
					const zx = zhongxianOf(dx.start, dx.mingIndex) || [];
					if(zx.length){
						seg.push(`沈氏三限（大限内四分，各 2.5 年；宫位沿本大限宫）：${zx.map((z, i)=>`中限${i + 1} ${z.startAge}~${z.endAge}岁`).join('、')}`);
					}
				}catch(e){ /* 分段失败不影响主段 */ }
			}
			pushSeg(seg);
		}
	});

	// 2) 流年：每个所选公历年各一段（解析其所属大限）。
	// 坑修：所选流年超出全部大限范围 → 补提示行而非静默跳过（与八字「超出大运范围」口径对齐）。
	const inRangeYears = [];
	liunianSel.forEach((year)=>{
		const ctx = findDaxianForYear(chart, daxianItems, year);
		if(ctx && ctx.liunian){
			inRangeYears.push(year);
			{
				const seg = formatLuckLayerLines(chart, ctx.liunian, ZW_PERIOD_LEVEL_LABEL.liunian, `${ctx.liunian.year}年`);
				// 小限并入「流年小限」段(需求6B)：同年小限按虚岁对齐，作附带信息列在 head 之后。
				const xx = buildXiaoxianItems(chart, ctx.daxian).find((x)=> x.age === ctx.liunian.age);
				if(xx){
					seg.splice(1, 0, `小限：${xx.ganzi}（${xx.age}虚岁），命宫【${luckHouseName(chart, xx.mingIndex, true)}】`);
				}
				pushSeg(seg);
			}
		}else{
			pushSeg([`◆ 流年：${year}年（超出大限范围，未列流年）`]);
		}
	});

	// 流月/流日/流时所需的基准年集合：所选流年中「在大限范围内」的年（避免流年不列、流月却列的语义错位）；
	// 若未选流年，则用首个大限的首年兜底（绝不抛）。
	const baseYears = liunianSel.length
		? inRangeYears
		: [(buildLiunianItems(chart, daxianItems[0])[0] || {}).year].filter((y)=>Number.isFinite(y));

	// 3) 流月：流年 × 流月 笛卡尔——每个 (year, month) 各一段。
	if(liuyueSel.length){
		baseYears.forEach((year)=>{
			const liuyueItems = buildLiuyueItems(chart, year);
			liuyueSel.forEach((month)=>{
				const ly = liuyueItems.find((x)=>x.month === month);
				if(ly){
					pushSeg(formatLuckLayerLines(chart, ly, ZW_PERIOD_LEVEL_LABEL.liuyue, `${year}年${ly.month}月`));
				}
			});
		});
	}

	// 锚定上层：流日 → 第一个 (year, month)；流时 → 第一个 (year, month, day)。
	const anchorYear = Number.isFinite(baseYears[0]) ? baseYears[0] : null;
	const anchorMonth = liuyueSel.length ? liuyueSel[0] : null;

	// 4) 流日：锚定 (anchorYear, anchorMonth)；anchorMonth 缺省取该年首月（正月）。
	if(liuriSel.length && anchorYear !== null){
		const liuyueItems = buildLiuyueItems(chart, anchorYear);
		const anchorLiuyue = anchorMonth !== null
			? (liuyueItems.find((x)=>x.month === anchorMonth) || liuyueItems[0])
			: liuyueItems[0];
		if(anchorLiuyue){
			const liuriItems = buildLiuriItems(chart, anchorYear, anchorLiuyue);
			liuriSel.forEach((day)=>{
				const lr = liuriItems.find((x)=>x.day === day);
				if(lr){
					pushSeg(formatLuckLayerLines(chart, lr, ZW_PERIOD_LEVEL_LABEL.liuri, `${anchorYear}年${anchorLiuyue.month}月${lr.day}日`));
				}
			});
		}
	}

	// 5) 流时：锚定 (anchorYear, anchorMonth, 首个所选流日/否则初一)。
	if(liushiSel.length && anchorYear !== null){
		const liuyueItems = buildLiuyueItems(chart, anchorYear);
		const anchorLiuyue = anchorMonth !== null
			? (liuyueItems.find((x)=>x.month === anchorMonth) || liuyueItems[0])
			: liuyueItems[0];
		if(anchorLiuyue){
			const liuriItems = buildLiuriItems(chart, anchorYear, anchorLiuyue);
			const anchorDay = liuriSel.length ? liuriSel[0] : null;
			const anchorLiuri = anchorDay !== null
				? (liuriItems.find((x)=>x.day === anchorDay) || liuriItems[0])
				: liuriItems[0];
			if(anchorLiuri){
				const liushiItems = buildLiushiItems(chart, anchorLiuri);
				liushiSel.forEach((hourIdx)=>{
					const ls = liushiItems[hourIdx];
					if(ls){
						pushSeg(formatLuckLayerLines(chart, ls, ZW_PERIOD_LEVEL_LABEL.liushi,
							`${anchorYear}年${anchorLiuyue.month}月${anchorLiuri.day}日`));
					}
				});
			}
		}
	}

	if(body.length === 0){
		return [];
	}
	const lines = ['[运限]'];
	body.forEach((segLines)=>{ lines.push(...segLines); });
	if(truncated){
		lines.push(`（运限段已达上限 ${ZW_PERIOD_MAX_SEGMENTS} 段，余下所选组合已省略）`);
	}
	lines.push('');
	return lines;
}

// 河洛气数位/中州借宫/紫云太岁/童限的可读 ground-truth 行(仅对应开关开时产出)。
// 统一收敛到单一 AI 导出段 [流派叠层]:子技法用「·标题」内联小标题(非方括号/全角段头,不触发段过滤器),
// 故 AI 导出设置只多一个可勾段(与「运限」条件分析层同范式),而非 4 个常驻空勾框;登记见 aiExport ziwei preset。
function buildZiweiOverlayLines(chart){
	if(!chart || !chart.houses){ return []; }
	const hn = (idx)=>((chart.houses[idx] || {}).name || `#${idx}`);
	const blocks = [];   // [子标题, [行...]];仅开关开且有数据时入
	if(ZWEngineOptions.childLimit){
		const cl = childLimits(chart.wuxingJu, chart.lifeHouseIndex);
		if(cl.length){ blocks.push(['童限', [cl.map((x)=>`${x.age}岁·${hn(x.houseIndex)}`).join('、')]]); }
	}
	if(ZWEngineOptions.qishuWei){
		const q = qiShuWei(chart);
		if(q){
			blocks.push(['河洛气数位', [
				`气数位=官禄宫(${hn(q.qiShuIdx)})，宫干${q.stem || '?'}`,
				`四化落宫：${['禄', '权', '科', '忌'].map((h)=>`${h}${(q.huaLanding[h] && q.huaLanding[h].star) || ''}→${q.huaLanding[h] && q.huaLanding[h].houseIndex >= 0 ? hn(q.huaLanding[h].houseIndex) : '未上盘'}${q.huaLanding[h] && q.huaLanding[h].backToLife ? '(回照本宫)' : ''}`).join('；')}`,
				`一六共宗：命↔疾厄(${hn(q.yiLiuGongZong['疾厄(6)'])})、命↔官禄气数位(${hn(q.qiShuIdx)})`,
			]]);
		}
	}
	if(ZWEngineOptions.borrowPalace){
		const all = allBorrowedStars(chart);
		const rows = [];
		for(let i = 0; i < 12; i++){ if(all[i]){ rows.push(`${hn(i)}(空)借对宫：${all[i].map((s)=>`${s.name}${s.starlight ? `·${s.starlight}` : ''}`).join('、')}`); } }
		if(rows.length){ blocks.push(['中州借宫安星', rows]); }
	}
	if(ZWEngineOptions.taiSuiRuGua && Array.isArray(ZWEngineOptions.taiSuiRelatives) && ZWEngineOptions.taiSuiRelatives.length){
		const t = taiSuiRuGua(chart, ZWEngineOptions.taiSuiRelatives);
		if(t.length){ blocks.push(['紫云太岁入卦', [t.map((r)=>`生肖${r.branch}${r.role ? `(${r.role})` : ''}→${r.houseIndex >= 0 ? hn(r.houseIndex) : '?'}·${r.dou}`).join('、')]]); }
	}
	if(!blocks.length){ return []; }
	const out = ['[流派叠层]'];
	blocks.forEach(([title, rows])=>{
		out.push(`· ${title}`);
		rows.forEach((r)=>out.push(`  ${r}`));
	});
	out.push('');
	return out;
}

export { ZW_PERIOD_LEVEL_LABEL, ZW_PERIOD_MAX_SEGMENTS, buildZiweiPeriodOverviewLines, buildZiweiPeriodLines, buildZiweiOverlayLines, formatLuckLayerLines, findDaxianForYear };
