







import * as AstroConst from '../../constants/AstroConst.js';
import { littleEndian } from '../gua/littleEndian.js';



import { getGua64, Gua64, Gua8, randYao, ZiList, HourZi, SixGods, getXunEmpty, LiuQi } from '../gua/GuaConst.js';
import { pureGuaOf } from '../gua/LiuYaoEngine.js';   // [Q-448/T-411] 伏神卦(本宫首卦)——快照补完整装卦用

import { analyzeLiuyao } from '../gua/liuyaoFacade.js';
import { normalizeLiuyaoSettings, applyPreset, setOption, LIUYAO_SCHOOL_OPTIONS, LIUYAO_PRESETS, loadPersistedLiuyaoSettings, persistLiuyaoSettings } from '../gua/liuyaoSchools.js';

import { definePageSettings } from '../utils/pageSettingsStore.js';




import { duanJueLines, zhanleiLines, buildSnapshotAnalysis } from './liuyaoSnapshotEx.js';

import { CHISHI_JUE, FADONG_JUE, LIUSHEN_FADONG, YAOWEI_XIANG, ZHANLEI_GANGYAO } from '../gua/liuyaoReference.js';











// [视觉底线·2026-09-17] 最小尺寸是屏幕可读意图(物理 px),壳缩放 z 下按 1/z 折算成布局 px;z=1 恒等。



function guaText(gua){
	if(!gua){
		return '';
	}
	const ord = gua.ord !== undefined ? `第${gua.ord}卦` : '';
	const house = gua.house ? `${gua.house.name || ''}宫${gua.house.elem || ''}` : '';
	return `${ord} ${gua.name || ''} ${gua.desc || ''} ${house}`.trim();
}

function lineText(line){
	if(line === undefined || line === null){
		return '';
	}
	return `${line}`.trim();
}

// 从六爻线值(0阴/1阳,初爻→上爻)算任一卦对象。自给自足:AI挂载经 regenerateSixyaoSnapshot→buildTimeGua 时
// gua 无 guaDesc(故旧版只剩本卦),但 yao 六爻线值始终在 → 据此稳定算出 之/互/错/综卦,挂载与导出都全面。
function guaFromYaoValues(values){
	if(!values || values.length !== 6 || values.some((v)=>v !== 0 && v !== 1)){
		return null;
	}
	const g = getGua64(littleEndian(values));
	const idx = g ? g.index : null;
	return (idx !== null && idx !== undefined && Gua64[idx]) ? Gua64[idx] : null;
}

// 时间起卦（梅花/时间确定式法）——纯函数，供 AI 挂载「起课时间」无头复用（与 genTimeGua 同口径）。
export function buildTimeGua(nongli){
	if(!nongli || !nongli.year || !nongli.time || nongli.monthInt === undefined || nongli.dayInt === undefined){
		return null;
	}
	const y = ZiList.indexOf(('' + nongli.year).substr(1)) + 1;
	const m = nongli.monthInt;
	const d = nongli.dayInt;
	const t = ZiList.indexOf(('' + nongli.time).substr(1)) + 1;
	let up = (y + m + d) % 8 - 1; up = up < 0 ? 7 : up;
	let down = (y + m + d + t) % 8 - 1; down = down < 0 ? 7 : down;
	let cyao = (y + m + d + t) % 6 - 1; cyao = cyao < 0 ? 5 : cyao;
	const upGua = Gua8[up];
	const downGua = Gua8[down];
	if(!upGua || !downGua){ return null; }
	const yao = [0, 0, 0, 0, 0, 0].map(() => ({ value: -1, change: false, color: AstroConst.AstroColor.Stroke, name: null }));
	for(let i = 0; i < downGua.value.length; i++){ yao[i].value = downGua.value[i]; }
	for(let i = 0; i < upGua.value.length; i++){ yao[i + 3].value = upGua.value[i]; }
	yao[cyao].change = true;
	const gua = getGua64(littleEndian(yao.map((x) => x.value)));
	const guaidx = gua ? gua.index : null;
	if(guaidx !== null && Gua64[guaidx]){
		for(let i = 0; i < yao.length; i++){ yao[i].name = Gua64[guaidx].yaoname[i]; }
	}
	return { yao, currentGua: guaidx, nongli };
}

// GFM 表化同构数据行(空 cell → —),供 AI 导出/挂载可读化;数据层零变化——表行可逆变换逐字复原旧格式行。
const MD_DASH = '—';
function pushMdRows(lines, header, rows){
	lines.push(`| ${header.join(' | ')} |`);
	lines.push(`| ${header.map(()=>'---').join(' | ')} |`);
	rows.forEach((cells)=>{
		lines.push(`| ${cells.map((c)=>(c === undefined || c === null || c === '' ? MD_DASH : `${c}`)).join(' | ')} |`);
	});
}

// [Q-208/T-162] 年干支取法单一化:此前只有 [断卦结构] 段按「定年界线」取(lunar 档取农历年支),
// 而 [起盘信息] 首段与左栏概览恒取立春系 → 立春↔正月初一窗口内同一快照/同一页出现两个年干支。
// 缺省(lichun)档与既有取法逐字相同,只有 lunar 档且落在该窗口内的盘首段文字才变。
function yearGzByBoundary(nongli, settings){
	const n = nongli || {};
	const lichun = n.yearJieqi || n.year || n.yearGanZi;
	return (normalizeLiuyaoSettings(settings).yearBoundary === 'lunar') ? (n.yearGZByLunar || lichun) : lichun;
}

// 六爻断卦结构段(流派/用神/旺衰/飞伏/卦身/动变/神煞/六神),供 AI 挂载/导出/储存复用(单一真值源=analyzeLiuyao)。
// st 缺 liuyaoSettings 时用默认设置(默认全显,零回归既有行只追加)。
export function liuyaoStructLines(st){
	try{
		const nowGua = st && st.currentGua !== null && st.currentGua !== undefined && Gua64[st.currentGua] ? Gua64[st.currentGua] : null;
		const yao = st && st.yao ? st.yao : [];
		if(!nowGua || !(yao && yao.length === 6 && yao.every((y)=>y && (y.value === 0 || y.value === 1)))){ return []; }
		const nongli = (st && st.nongli) || {};
		const settings = normalizeLiuyaoSettings(st && st.liuyaoSettings);
		// [X1] 与 liuyaoSnapshotEx.buildSnapshotAnalysis 同口径(三处同口径铁律):
		// 年界线吃 settings.yearBoundary(正月初一派取 yearGZByLunar);ctx 补 hourZhi/jieqiName
		// (缺则时辰类神煞/节气派生在本段空转,与断诀段结论可不一致)。
		const yearGz = lineText((settings.yearBoundary === 'lunar'
			? (nongli.yearGZByLunar || nongli.yearGanZi || nongli.yearJieqi)
			: (nongli.yearJieqi || nongli.yearGanZi || nongli.yearGZByLunar)) || nongli.year);
		const monthGz = lineText(nongli.monthGanZi);
		const dayGz = lineText(nongli.dayGanZi);
		const hourGz = lineText(nongli.timeGanZi || nongli.hourGanZi);
		const ctx = {
			dayGan: dayGz.length >= 2 ? dayGz[0] : null, dayZhi: dayGz.length >= 2 ? dayGz[1] : null,
			monthGan: monthGz.length >= 2 ? monthGz[0] : null, monthZhi: monthGz.length >= 2 ? monthGz[1] : null,
			monthNum: (['寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥', '子', '丑'].indexOf(monthGz.length >= 2 ? monthGz[1] : '') + 1) || null,
			yearGan: yearGz.length >= 2 ? yearGz[0] : null, yearZhi: yearGz.length >= 2 ? yearGz[1] : null,
			hourZhi: hourGz.length >= 2 ? hourGz[1] : null,
			jieqiName: lineText(nongli.jieqi || nongli.jieqiName) || null,
		};
		const moving = [];
		yao.forEach((y, i)=>{ if(y.change){ moving.push(i + 1); } });
		const a = analyzeLiuyao(nowGua, moving, ctx, settings);
		if(!a){ return []; }
		const lines = [];
		const presetLabel = (LIUYAO_PRESETS[settings.school] && LIUYAO_PRESETS[settings.school].label) || (settings.school === 'custom' ? '自定义' : settings.school);
		lines.push('');
		lines.push('[断卦结构]');
		lines.push(`流派：${presetLabel}`);
		if(a.palaceType){ lines.push(`卦序：${a.palaceType.palace}宫·${a.palaceType.type}(世${a.palaceType.shi}应${a.palaceType.ying})`); }
		if(a.guaXing && a.guaXing.ben){ lines.push(`卦象：${a.guaXing.ben}${a.guaXing.bian ? '→' + a.guaXing.bian + '(卦变)' : ''}`); }
		if(a.heHui && a.heHui.length){ lines.push(`成局：${a.heHui.map((h)=>`${h.type}${h.zhis}${h.wuxing}${h.hasMoving ? '(有动)' : ''}`).join('、')}`); }
		if(a.yongShen){
			const ys = a.yongShen;
			const loc = (l)=>{ if(!l || !l.candidates || !l.candidates.length){ return '不上卦'; } return l.candidates.map((c)=>`${c.pos}爻`).join('/'); };
			lines.push(`占测：${ys.label}　用神：${ys.yong}(${loc(ys.located.yong)})`);
			// [Q-448/T-411] 次用神与取用说明:页面用神卡两行俱有(LiuYaoBoard「次用神」「取用说明」),
			// 快照此前只给 用/原/忌/仇 —— AI 看不到取用之由,遇「兄弟兼看」一类双用神更直接漏一半。
			if(ys.secondary && ys.located && ys.located.secondary){ lines.push(`次用神：${ys.secondary}(${loc(ys.located.secondary)})`); }
			if(ys.roles){ lines.push(`原神：${ys.roles.yuan}(${loc(ys.located.yuan)})　忌神：${ys.roles.ji}(${loc(ys.located.ji)})　仇神：${ys.roles.chou}(${loc(ys.located.chou)})`); }
			if(ys.note){ lines.push(`取用说明：${ys.note}`); }
		}
		if(a.guaShen){ lines.push(`卦身：${a.guaShen.body}${a.guaShen.onChart ? '(上卦)' : '(不上卦)'}`); }
		// 逐爻结构(初→上)→ GFM 表:爻/六神/地支/五行/六亲/世应/旺衰/状态/伏神/神煞(空 cell —);旧「逐爻(初→上)：六神│…」图例行由表头承接。
		const yaoRows = a.yaos.map((y, i)=>{
			const liu = a.liuShen && a.liuShen[i] ? a.liuShen[i].liushen : '';
			const fu = (a.fushenAll && a.fushenAll[i]) || y.fushen;
			const fuTxt = fu && fu.liuqin ? `伏${fu.liuqin}${fu.zhi}${fu.wuxing}` : '';
			const sha = a.shenSha && a.shenSha.perYao && a.shenSha.perYao[i] ? (a.shenSha.perYao[i].shensha || []).join(',') : '';
			// [Q-448/T-411] 岁破/日破逐爻标:页面装卦表状态列早有(LiuYaoBoard 取 y.sanCeng 的这两项),
			// 快照状态列此前只到 月破/旬空/入墓/长生帝旺绝 —— [断诀命中] 首行虽给出岁破日破之支,但要 AI 自行
			// 逐爻比对才知道落在哪根爻上。与页面同源取 sanCeng,只取这两项(其余三层另有段)。
			const sanCengPo = (y.sanCeng || []).filter((t)=>t === '岁破' || t === '日破');
			const stat = [y.yuePo ? '月破' : '', ...sanCengPo, y.xunKong ? (y.voidKind || '旬空') : '', y.ruMu ? '入墓' : '', y.changsheng === '长生' || y.changsheng === '帝旺' || y.changsheng === '绝' ? y.changsheng : ''].filter(Boolean).join(',');
			return [`第${y.pos}爻`, liu, y.zhi, y.wuxing, y.liuqin, y.shiYing, y.wangShuai, stat, fuTxt, sha];
		});
		pushMdRows(lines, ['爻', '六神', '地支', '五行', '六亲', '世应', '旺衰', '状态', '伏神', '神煞'], yaoRows);
		// 动变 → GFM 表:爻/本卦/变卦/标记(空 cell —)
		if(a.dongBian && a.dongBian.movingCount > 0){
			lines.push(`变卦：${a.dongBian.bianGua ? a.dongBian.bianGua.name : ''}${a.dongBian.guaFuYin ? '(卦伏吟)' : ''}${a.dongBian.guaFanYin ? '(卦反吟)' : ''}`);
			const moveRows = a.dongBian.moves.map((m)=>{
				const tags = [m.jinShen ? '进神' : '', m.tuiShen ? '退神' : '', m.fanYin ? '反吟' : '', m.fuYin ? '伏吟' : '', m.huiTou.sheng ? '回头生' : '', m.huiTou.ke ? '回头克' : '', m.huiTou.chong ? '回头冲' : '', m.huiTou.he ? '回头合' : '', m.huaKong ? '化空' : '', m.huaPo ? '化破' : '', m.huaMu ? '化墓' : '', m.huaJue ? '化绝' : ''].filter(Boolean).join('·');
				return [`第${m.pos}爻`, `${m.ben.liuqin}${m.ben.zhi}${m.ben.wuxing}`, `${m.bian.liuqin}${m.bian.zhi}${m.bian.wuxing}`, tags];
			});
			pushMdRows(lines, ['爻', '本卦', '变卦', '标记'], moveRows);
			// [Q-201/T-144] 变爻范围=盲派(作用他爻)时页面有「盲派·变爻作用他爻」卡而快照无 → 齿轮对挂载零字节;仅 blind 且非空时出行(缺省 traditional 字节不变)。
			if(Array.isArray(a.dongBian.blindEffects) && a.dongBian.blindEffects.length){
				lines.push(`盲派作用：${a.dongBian.blindEffects.map((e)=>`第${e.from}爻→第${e.to}爻(${e.toLiuqin || ''})${e.rel}`).join('、')}`);
			}
		}
		return lines;
	}catch(e){
		return [];
	}
}

export function buildGuaSnapshotText(fields, st){
	const lines = [];
	const nowGua = st && st.currentGua !== null && Gua64[st.currentGua] ? Gua64[st.currentGua] : null;
	const yao = st && st.yao ? st.yao : [];
	const nongli = st && st.nongli ? st.nongli : {};
	const guaDesc = st && st.guaDesc ? st.guaDesc : {};
	// [Q-205/T-150] 六神关 → 快照不得再逐爻带六神:state.yao 的 god 由 fillYaoGods 就地写入(存档也带),
	// 与设置无关;闸口与中间栏同一处口径(见 renderChart 的 _liuSet.sixGods 清 god),否则「关掉的块不进快照」失信。
	const _liuSettings = normalizeLiuyaoSettings(st && st.liuyaoSettings);
	const showSixGods = !!_liuSettings.sixGods;
	const fieldTime = (fields && fields.date && fields.time)
		? `${fields.date.value.format('YYYY-MM-DD')} ${fields.time.value.format('HH:mm:ss')}`
		: '';
	const startTime = lineText(nongli.birth) || fieldTime;
	const yearGz = lineText(yearGzByBoundary(nongli, st && st.liuyaoSettings));
	const monthGz = lineText(nongli.monthGanZi);
	const dayGz = lineText(nongli.dayGanZi);
	const timeGz = lineText(nongli.time || nongli.timeGanZi);
	const monthXunEmpty = monthGz.length >= 2 ? getXunEmpty(monthGz.substr(0, 1), monthGz.substr(1, 1)) : '';
	const dayXunEmpty = dayGz.length >= 2 ? getXunEmpty(dayGz.substr(0, 1), dayGz.substr(1, 1)) : '';

	lines.push('[起盘信息]');
	if(fieldTime){
		lines.push(`日期：${fieldTime}`);
	}
	if(fields && fields.zone){
		lines.push(`时区：${fields.zone.value}`);
	}
	if(fields && fields.lon && fields.lat){
		lines.push(`经纬度：${fields.lon.value} ${fields.lat.value}`);
	}
	// 求测人性别(Win issue #29):本页引擎不读它取用神(占婚男女由「占测事项」的 marriage_m/marriage_f 两档决定),
	// 但它是判语语境的一部分 → 随挂载/导出给 AI(与帮助「仅作随盘记录」同口径)。
	if(fields && fields.gender && (fields.gender.value === 0 || fields.gender.value === 1)){
		lines.push(`求测人性别：${fields.gender.value === 1 ? '男' : '女'}`);
	}
	if(startTime){
		lines.push(`起卦时间：${startTime}${timeGz ? ` ${timeGz}时` : ''}`);
	}
	if(yearGz || monthGz || dayGz || timeGz){
		lines.push(`干支：年${yearGz || '无'} 月${monthGz || '无'} 日${dayGz || '无'} 时${timeGz || '无'}`);
	}
	if(monthXunEmpty || dayXunEmpty){
		lines.push(`旬空：月空${monthXunEmpty || '无'} 日空${dayXunEmpty || '无'}`);
	}

	lines.push('');
	// 之卦/互卦/错卦/综卦：从六爻线值直接计算(不依赖 guaDesc) → 挂载经 buildTimeGua(无 guaDesc)时也能全面输出,
	// 修「AI分析挂载六爻只有本卦」。yao 缺失时回落 guaDesc。
	// 提升到函数作用域，供下方[六爻与动爻]给之卦/互卦逐爻装卦复用。
	const yaoVals = (yao && yao.length === 6 && yao.every((y)=>y && (y.value === 0 || y.value === 1))) ? yao.map((y)=>y.value) : null;
	const hasMoving = !!(yao && yao.some((y)=>y.change));
	let huGua = null;
	let bianGua = null;
	let cuoGua = null;
	let zongGua = null;
	if(yaoVals){
		huGua = guaFromYaoValues([yaoVals[1], yaoVals[2], yaoVals[3], yaoVals[2], yaoVals[3], yaoVals[4]]);
		bianGua = guaFromYaoValues(yao.map((y)=>y.change ? (y.value === 1 ? 0 : 1) : y.value));
		cuoGua = guaFromYaoValues(yaoVals.map((v)=>(v === 1 ? 0 : 1)));
		zongGua = guaFromYaoValues([...yaoVals].reverse());
	}
	lines.push('[卦象]');
	if(nowGua){
		lines.push(`本卦：${guaText(nowGua)}`);
	}else{
		lines.push('本卦：未生成');
	}
	if(yaoVals){
		if(huGua){ lines.push(`互卦：${guaText(huGua)}`); }
		else if(guaDesc.guaMiddle){ lines.push(`互卦：${guaText(guaDesc.guaMiddle)}`); }
		if(hasMoving){
			if(bianGua){ lines.push(`之卦(变卦)：${guaText(bianGua)}`); }
			else if(guaDesc.guaRes){ lines.push(`之卦(变卦)：${guaText(guaDesc.guaRes)}`); }
		}else{
			lines.push('之卦(变卦)：无动爻,卦不变');
		}
		if(cuoGua){ lines.push(`错卦(阴阳全变)：${guaText(cuoGua)}`); }
		if(zongGua){ lines.push(`综卦(上下颠倒)：${guaText(zongGua)}`); }
	}else{
		if(guaDesc.guaMiddle){ lines.push(`互卦：${guaText(guaDesc.guaMiddle)}`); }
		if(guaDesc.guaRes){ lines.push(`之卦：${guaText(guaDesc.guaRes)}`); }
	}

	lines.push('');
	lines.push('[六爻与动爻]');
	if(!yao || yao.length === 0){
		lines.push('暂无爻线数据');
	}else{
		// 本卦逐爻（保持原样）：阴阳/动静 + 六神(六兽) + 爻名(纳甲=地支/五行/六亲/世应)。
		yao.forEach((item, idx)=>{
			const yaoType = item.value === 1 ? '阳爻' : (item.value === 0 ? '阴爻' : '未定');
			const moving = item.change ? '（动）' : '（静）';
			const god = (showSixGods && item.god) ? `，六神:${item.god}` : '';
			const name = item.name ? `，爻名:${item.name}` : '';
			lines.push(`第${idx + 1}爻：${yaoType}${moving}${god}${name}`);
		});
		// 之卦(变卦)/互卦逐爻装卦：地支/五行/世应取自该卦 yaoname;但【六亲必须以「本卦之宫」五行论】——
		// 京房纳甲:用神系统锚定本卦,之卦/互卦的六亲不按其自身宫五行(否则与中间栏显示错位,Win issue #30:
		// 之卦酉金应为妻财[本卦离宫火克金],却被算成兄弟[变卦乾宫金比和])。六神沿用本卦同位(按日干起、各卦同序)。
		const godAt = (i)=>((showSixGods && yao[i] && yao[i].god) ? `，六神:${yao[i].god}` : '');
		const benGongElem = (nowGua && nowGua.house && nowGua.house.elem) || null;
		// 把「该卦自身宫论出的六亲」(yaoname 第3-4字)改成「按本卦宫论」;保留地支五行(前2字)与世应(第5字起)。
		const fixLiuqinToBenGong = (nm)=>{
			if(!benGongElem || typeof nm !== 'string' || nm.length < 4){ return nm; }
			const branchElem = nm[1]; // 爻地支五行(金/木/水/火/土)
			const lq = LiuQi[benGongElem] && LiuQi[benGongElem][branchElem];
			return lq ? (nm.slice(0, 2) + lq + nm.slice(4)) : nm;
		};
		const pushGuaYao = (label, gua)=>{
			if(!gua || !Array.isArray(gua.yaoname)){ return; }
			lines.push(`${label}逐爻（初→上）：`);
			gua.yaoname.forEach((nm0, idx)=>{
				const nm = fixLiuqinToBenGong(nm0); // 六亲改按本卦宫(与显示一致),地支五行/世应不变
				// 阴阳爻取该卦线值 gua.value[idx]（1=阳/0=阴），与本卦逐爻一致。
				const v = Array.isArray(gua.value) ? gua.value[idx] : undefined;
				const yinYang = v === 1 ? '阳爻' : (v === 0 ? '阴爻' : '');
				lines.push(`第${idx + 1}爻：${yinYang ? `${yinYang}，` : ''}爻名:${nm}${godAt(idx)}`);
			});
		};
		// [Q-448/T-411] 关联卦完整装卦:页面「关联卦」区给 之/互/伏神/综/错 五卦各自完整装卦,
		// 快照此前逐爻只给之卦与互卦,错/综只写卦名、伏神卦一字不提 —— 页面看得见、AI 看不见。
		// [Q-208/T-161 同律] 受左栏「关联卦显示」勾选控制:页面隐藏的卡不进快照(null=全显=缺省)。
		const _relSel = Array.isArray(_liuSettings.relatedCards) ? _liuSettings.relatedCards : null;
		const relOn = (k)=>(!_relSel || _relSel.indexOf(k) >= 0);
		if(hasMoving && bianGua && relOn('bian')){ pushGuaYao('之卦(变卦)', bianGua); }
		if(huGua && relOn('hu')){ pushGuaYao('互卦', huGua); }
		const fuGua = nowGua ? pureGuaOf(nowGua) : null;
		if(fuGua && relOn('fu')){ pushGuaYao('伏神卦(本宫首卦)', fuGua); }
		if(zongGua && relOn('zong')){ pushGuaYao('综卦', zongGua); }
		if(cuoGua && relOn('cuo')){ pushGuaYao('错卦', cuoGua); }
	}

	// 断卦结构(流派/用神/旺衰/飞伏/卦身/动变/神煞/六神)——追加于既有段之后,既有行字节不变(零回归)。
	const structLines = liuyaoStructLines(st);
	if(structLines && structLines.length){ structLines.forEach((l)=>lines.push(l)); }

	lines.push('');
	lines.push('[卦辞与断语]');
	['guaOrg', 'guaMiddle', 'guaRes'].forEach((key)=>{
		const one = guaDesc[key];
		if(!one){
			return;
		}
		const label = key === 'guaOrg' ? '本卦' : (key === 'guaMiddle' ? '互卦' : '之卦');
		lines.push(`${label}：${guaText(one)}`);
		if(one['卦辞']){
			lines.push(`卦辞：${one['卦辞']}`);
		}
		if(one['彖']){
			lines.push(`彖曰：${one['彖']}`);
		}
		if(one['象']){
			lines.push(`象曰：${one['象']}`);
		}
		const yaoci = one['爻辞'] || [];
		const yaox = one['爻象'] || [];
		yaoci.forEach((text, idx)=>{
			const xiang = yaox[idx] ? `；象曰：${yaox[idx]}` : '';
			lines.push(`第${idx + 1}爻辞：${text}${xiang}`);
		});
		lines.push('');
	});

	// [判语库·参考诀表] doctrine 段(默认关段:builder 恒产,导出层按设置控)：与右栏「参考」页 LiuYaoReference 同源,
	// 五表原文引自 liuyaoReference 常量(诸爻持世诀/六亲发动诀/六神发动歌/爻位象/常见占类断法纲要),判语零改写。
	const refLiuqinList = ['父母', '兄弟', '子孙', '妻财', '官鬼'];
	const refLiushenList = ['青龙', '朱雀', '勾陈', '螣蛇', '白虎', '玄武'];
	lines.push('[判语库·参考诀表]');
	lines.push('◆ 诸爻持世诀');
	refLiuqinList.forEach((lq)=>lines.push(`${lq}持世：${CHISHI_JUE[lq]}`));
	lines.push('◆ 六亲发动诀(发动必生一克一)');
	refLiuqinList.forEach((lq)=>lines.push(`${lq}动：${FADONG_JUE[lq].ke}　${FADONG_JUE[lq].sheng}`));
	lines.push('◆ 六神发动歌');
	refLiushenList.forEach((sn)=>lines.push(`${sn}动：${LIUSHEN_FADONG[sn]}`));
	lines.push('◆ 爻位象(身/宅/人事)');
	YAOWEI_XIANG.forEach((y)=>lines.push(`${['初', '二', '三', '四', '五', '上'][y.pos - 1]}爻：${y.body}｜${y.home}｜${y.person}`));
	lines.push('◆ 常见占类断法纲要');
	ZHANLEI_GANGYAO.forEach((z)=>lines.push(`${z.name}：用神${z.yong}；吉：${z.ji}；凶：${z.xiong}`));

	// [断诀命中]/[占类断语](六爻补齐 A8:builder 恒产,导出层按设置控;既有段字节不变)
	const _snapA = buildSnapshotAnalysis(st);
	if(_snapA){
		lines.push('');
		duanJueLines(_snapA).forEach((l)=>lines.push(l));
		lines.push('');
		zhanleiLines(_snapA, _snapA.gua && _snapA.gua.name).forEach((l)=>lines.push(l));
	}

	return lines.join('\n');
}

// 排盘设置跨会话保留:自定义起卦 / 数字起卦的「动爻取法」。这两个下拉把**取法**(先天卦数 / 随机数 / 时辰,负值)
// 与**直接点某一爻**(0–5,是这一卦的输入)混在一起 —— 只保留取法:候选只列负值,点了具体某一爻时落盘自动被拒、
// 库里仍是上一次选的取法。(铜钱字面 / 缺省爻态等另由六爻设置 liuyaoSettings 保留。)
export const GUAZHAN_PAGE_SETTINGS = definePageSettings('horosa.guazhan.settings.v1', {
	custGuaDongYao: { def: -1, oneOf: [-3, -2, -1] },
	numGuaDongYao: { def: -1, oneOf: [-3, -2, -1] },
});
