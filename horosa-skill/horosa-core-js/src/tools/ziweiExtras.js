import { ZWEngineOptions } from '../vendor/ziwei/ziweiOptions.js';
import { qiShuWei, taiSuiRuGua, borrowedStars as borrowPalace } from '../vendor/ziwei/ziweiOverlays.js';
import { childLimits } from '../vendor/ziwei/ziweiCore.js';
import {
  buildDaxianItems,
  buildLiunianItems,
  buildXiaoxianItems,
  buildLiuyueItems,
  buildLiuriItems,
  buildLiushiItems,
  houseName as luckHouseName,
  houseIdxByBranch as luckHouseIdxByBranch,
} from '../vendor/ziwei/zwLuckItems.js';
import * as ZiWeiHelper from '../vendor/ziwei/ZiWeiHelper.js';

/**
 * 紫微两段：[运限]（指定时段）与 [流派叠层]（流派开关叠加层）。
 *
 * 上游这两段都由界面状态驱动 —— 前者是用户勾选的大限/流年/流月/流日/流时组合
 * （`body.length === 0` 就整段不产），后者读可变单例 `ZWEngineOptions` 的一组流派开关。
 * headless 没有界面，故把同一份选择开成显式入参：
 *   period  = { daxian:[…], liunian:[…], liuyue:[…], liuri:[…], liushi:[…] }
 *   schools = { childLimit, zhongxian, huoPan, qishuWei, borrowPalace, taiSuiRuGua, taiSuiRelatives:[…] }
 *
 * 两个 builder 的函数体逐字取自上游 ZiWeiMain.js，只把两张模块级表搬来。
 * `ZWEngineOptions` 是**可变单例**：这里按调用逐次覆盖再还原，避免跨调用串味。
 *
 * payload: { chart: <ziwei/birth 响应的 chart>, period?: {…}, schools?: {…} }
 * return : { text }
 */

// 以下两个模块级常量逐字取自上游 ZiWeiMain.js。
const ZW_PERIOD_LEVEL_LABEL = { daxian: '大限', liunian: '流年小限', liuyue: '流月', liuri: '流日', liushi: '流时' };
const ZW_PERIOD_MAX_SEGMENTS = 50;

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
			pushSeg(formatLuckLayerLines(chart, dx, ZW_PERIOD_LEVEL_LABEL.daxian, `${dx.start}~${dx.end}岁`));
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

function formatLuckLayerLines(chart, layer, levelLabel, subText){
	const lines = [];
	const mingIdx = layer.mingIndex;
	const oppIdx = ((mingIdx % 12) + 6) % 12;
	// [v2 试点] 头行加 ◆ 子题标记:呈现层(docx/PDF)映射 Heading3;纯文本仍整行可读(substring 断言不受影响)。
	const head = `◆ ${levelLabel}：${layer.ganzi || ''}${subText ? `（${subText}）` : ''}`
		+ `，命宫【${luckHouseName(chart, mingIdx, true)}】·对宫【${luckHouseName(chart, oppIdx, true)}】`;
	lines.push(head);
	const sihua = ZiWeiHelper.getLayerSihua(chart, layer.gan) || [];
	if(sihua.length > 0){
		const parts = sihua.map((h)=>`${h.star}化${h.hua}（${luckHouseName(chart, h.houseIndex, true)}）`);
		lines.push(`四化：${parts.join('、')}`);
	}
	const flowStars = ZiWeiHelper.getFlowStars(layer.gan, layer.zhi) || [];
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

function findDaxianForYear(chart, daxianItems, year){
	for(let i = 0; i < daxianItems.length; i++){
		const items = buildLiunianItems(chart, daxianItems[i]);
		if(items.some((x)=>x.year === year)){
			return { daxian: daxianItems[i], liunianItems: items, liunian: items.find((x)=>x.year === year) || null };
		}
	}
	return null;
}
const _OVERLAY_KEYS = ['childLimit', 'zhongxian', 'huoPan', 'qishuWei', 'borrowPalace', 'taiSuiRuGua', 'taiSuiRelatives'];

export function runZiweiExtras(payload) {
  const source = payload && typeof payload === 'object' ? payload : {};
  const chart = source.chart && typeof source.chart === 'object' ? source.chart : null;
  if (!chart) {
    return { text: '' };
  }
  const blocks = [];

  if (source.period && typeof source.period === 'object') {
    try {
      const lines = buildZiweiPeriodLines(chart, source.period) || [];
      const body = lines.filter((l) => l !== '');
      if (body.length) {
        blocks.push(body.join('\n'));
      }
    } catch (error) { /* 单段失败不带崩另一段 */ }
  }

  if (source.schools && typeof source.schools === 'object') {
    // ZWEngineOptions 是可变单例 —— 逐次覆盖后**必须还原**，否则同进程内下一次调用会串味。
    const saved = {};
    _OVERLAY_KEYS.forEach((k) => { saved[k] = ZWEngineOptions[k]; });
    try {
      _OVERLAY_KEYS.forEach((k) => {
        if (source.schools[k] !== undefined) { ZWEngineOptions[k] = source.schools[k]; }
      });
      const lines = buildZiweiOverlayLines(chart) || [];
      const body = lines.filter((l) => l !== '');
      if (body.length) {
        blocks.push(body.join('\n'));
      }
    } catch (error) { /* 同上 */ } finally {
      _OVERLAY_KEYS.forEach((k) => { ZWEngineOptions[k] = saved[k]; });
    }
  }

  return { text: blocks.join('\n\n') };
}

export default runZiweiExtras;
