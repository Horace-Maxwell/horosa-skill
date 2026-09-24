// 七政四余 AI 快照段 builder —— 自上游 components/guolao/GuoLaoChartMain.js **逐字**抽出
// （bespoke，derived_from + derived_sha256 看守：上游 GuoLaoChartMain.js 一动即红，复核本文件后 --restamp）：
//   · buildGuolaoAnchorLines —— [起盘信息] 命度 / 身度 / 命度宿主·身度宿主 行（v3.11.0 [Q-231/Q-434]）
//   · buildGuolaoMastersSection —— [三主与化曜]（v3.11.0 [Q-435]）
//   · buildGuolaoLimitCalcSection —— [限法实算]（v3.11.0 [Q-435]）
//   · buildGuolaoLimitSection —— [大限]（GFM 表 + 所选行运法结构；[Q-188/T-125] 年界 / 定童限）
// 上游该文件 4350 行，其余是 React 组件与取数编排；政余格局闭包另在 guolaoMoira.js（同源不同段）。
// 只有下方 import 按 vendor 树改了路径（上游 import 名：moiraLifeDegree as lifeDegree 等，逐字保留别名）。
import * as AstroConst from '../../constants/AstroConst.js';
import { moiraBuildLimitTable as buildLimitTable, moiraLifeDegree as lifeDegree, moiraBirthYearBasis } from './guolaoMoiraWheelLimits.js';
import { computeDongwei as glDongwei, computeTongxian as glTongxian } from './guolaoTransit.js';

function safeList(val){
	return Array.isArray(val) ? val : [];
}

function findChartObject(chart, id){
	return safeList(chart.objects).find((obj)=>obj && obj.id === id);
}

// [Q-231/Q-434] [起盘信息] 命度实值 / 身度 / 命度宿主 / 身度宿主 四行(右栏「命身与限度」卡同源)。
function buildGuolaoAnchorLines(info){
	if(!info || !info.life){ return []; }
	const out = [];
	const anchorText = (a, extra)=>{
		const main = `${a.signName || '随盘面'} ${a.degreeText || ''}`.trim();
		const tail = [a.zi, a.area, a.moiraHouse].concat(extra || []).filter(Boolean).join(' · ');
		return tail ? `${main}（${tail}）` : main;
	};
	out.push(`命度：${anchorText(info.life, [info.lifeModeName])}`);
	if(info.self && (info.self.signName || info.self.degreeText)){
		out.push(`身度：${anchorText(info.self)}`);
	}
	out.push(`命度宿主：${info.lifeSuHost ? info.lifeSuHost.value : '随盘面'}；身度宿主：${info.selfSuHost ? info.selfSuHost.value : '随盘面'}`);
	return out;
}

// [Q-435] [三主与化曜] 段:三主(命主/宫主/度主/身主)+ 命宫配干 + 生年化曜 + 难仇恩用(度/宫两役行)。
// 「命主取法」齿轮在此对正文生效(命主(宫主)/命主(度主) 与难仇恩用主星随之改变)。
export function buildGuolaoMastersSection(info){
	try{
		if(!info){ return ''; }
		const out = [];
		if(info.masterItems && info.masterItems.length){
			out.push(`◆ 三主 · 命宫配干 · 化曜（${info.useDu ? '专度主' : '主宫主'}）`);
			info.masterItems.forEach((it)=>{ out.push(`${it.label}：${it.value}`); });
		}
		if(info.helperRows && info.helperRows.length){
			out.push('◆ 难仇恩用（主星五行四役）');
			const labels = info.helperLabels || ['难', '仇', '恩', '用'];
			info.helperRows.forEach((row)=>{
				out.push(`${row.head}(${row.main})：${labels.map((lab, li)=>`${lab}=${row.roles[li] || '-'}`).join('，')}`);
			});
		}
		return out.join('\n');
	}catch(e){
		return '';
	}
}

// [Q-435] [限法实算] 段:飞限 / 童限 / 小限 / 月限 / 限度(当年虚岁实算)+ 所选「行运法」的实算
// (洞微本年吊度 / 童限顺排 / 小限宫 / 月限宫)。「行运法」齿轮在此对正文生效(此前只改 [大限] 段一行标签)。
export function buildGuolaoLimitCalcSection(info){
	try{
		if(!info){ return ''; }
		const out = [];
		const lim = info.limits;
		if(lim && lim.items && lim.items.length){
			out.push(`◆ 飞限 · 童限 · 小限 · 月限 · 限度（${lim.age} 岁 · ${lim.transitYearText}年）`);
			out.push(lim.items.map((it)=>`${it.label}：${it.value}`).join('；'));
		}
		const rl = info.runLaw;
		if(rl && rl.type === 'dongwei'){
			out.push(`◆ 行运法实算 · 洞微大限（起限 ${rl.startAge} 岁）`);
			out.push(rl.curDiaodu ? `本年飞星吊度 ≈ ${rl.curDiaodu.deg}°（${rl.age} 岁）` : '本年飞星吊度：需年龄');
		}else if(rl && rl.type === 'tong'){
			out.push(`◆ 行运法实算 · 童限（基数${rl.baseName}）`);
			out.push(`童限顺排：${(rl.palaces || []).join('→')}；出童限(约)：${rl.exitAge} 岁`);
		}else if(rl && rl.type === 'month'){
			out.push(`◆ 行运法实算 · 月限（小限宫起生月逆寻 · 生月${rl.bMonth}）`);
			out.push(rl.palaceName ? `月限(${rl.age}岁)：${rl.palaceName}（${rl.palaceZi}）` : '月限：需年龄/生月');
		}else if(rl && rl.type === 'minor'){
			out.push('◆ 行运法实算 · 小限（生年支加命宫逆数）');
			out.push(rl.palaceName ? `小限(${rl.age}岁)：${rl.palaceName}（${rl.palaceZi}）` : '小限：需年龄');
		}
		return out.join('\n');
	}catch(e){
		return '';
	}
}

// AI 快照·大限段：复用 Moira 命盘轮的命度→十二宫大限算法（moiraBuildLimitTable/lifeDegree），
// 保证导出/挂载与盘面「命身与限度·大限」列表完全同口径。出生年取自 params.date（YYYY/MM/DD）。
// [Q-188/T-125] limitOpts:{ limitYearBoundary, limitChildBase } 与右栏/大限环同源(缺省 元旦/9 → 段逐字同旧)。
export function buildGuolaoLimitSection(chart, fields, params, minorLimitType, tongxianBase, limitOpts){
	try{
		const lifeDeg = lifeDegree(chart, fields);
		const lo = limitOpts && typeof limitOpts === 'object' ? limitOpts : {};
		const limitBasis = moiraBirthYearBasis(chart, fields, lo.limitYearBoundary || 'gregorian');
		const limitChildBase = Number(lo.limitChildBase) === 10 ? 10 : 9;
		const birthYear = (Number(String(params.date || '').split('/')[0]) || 0) + limitBasis.yearShift;
		const rows = buildLimitTable(lifeDeg, birthYear, limitChildBase, limitBasis.frac);
		const out = [];
		if(rows && rows.length){
			// GFM 表化(段内排版,值零变化):cell 沿用旧行字面片段(第N限/a-b岁/a-b年/约N年),
			// fact-multiset 证明见 guolaoSnapshotTables.test.js。
			out.push('古度限度法（命度十二宫大限）：');
			out.push('| 限 | 宫 | 起讫岁 | 起讫年 | 年数 |');
			out.push('| --- | --- | --- | --- | --- |');
			rows.forEach((row)=>{
				out.push(`| 第${row.index}限 | ${row.palace || '—'} | ${row.fromAge}-${row.toAge}岁 | ${row.fromYear}-${row.toYear}年 | 约${row.years}年 |`);
			});
		}
		// WP-E：所选行运法(类B minorLimitType)结构同入快照——洞微大限含飞星吊度,童限顺排,小限/月限注明法。
		const mlt = String(minorLimitType || '');
		if(mlt === 'dongwei'){
			const sun = findChartObject(chart, AstroConst.SUN);
			if(sun && Number.isFinite(Number(sun.lon))){
				const dw = glDongwei(((Number(sun.lon) % 30) + 30) % 30);
				out.push('');
				out.push(`洞微大限（命宫顺行·飞星吊度·起限${dw.startAge}岁）：`);
				out.push('| 限 | 宫 | 起讫岁 | 年数 | 吊度 |');
				out.push('| --- | --- | --- | --- | --- |');
				dw.rows.forEach((r)=>{
					out.push(`| 第${r.index}限 | ${r.palace || '—'} | ${r.fromAge}-${r.toAge}岁 | ${r.years}年 | 入${r.entryDeg}°·每年吊度${r.perYearDeg}° |`);
				});
			}
		}else if(mlt === 'tong'){
			const sun = findChartObject(chart, AstroConst.SUN);
			if(sun && Number.isFinite(Number(sun.lon))){
				const tx = glTongxian(Number(sun.lon), tongxianBase || 'tong10');
				out.push('');
				out.push(`童限：命财疾妻福顺排（${tx.palaces.join('→')}），出童限约${tx.exitAge}岁。`);
			}
		}else if(mlt === 'minor'){
			out.push('');
			out.push('小限：生年支加命宫逆数（age1=命宫宫支，逐年逆行一宫，12年一轮）。');
		}else if(mlt === 'month'){
			out.push('');
			out.push('月限：由当年小限宫起生月、按月逆寻（节气月口径）。');
		}
		return out.join('\n');
	}catch(e){
		return '';
	}
}

// 上游 buildGuolaoAnchorLines 是模块私有（快照拼装内部用）；headless 快照在 skill 侧拼装，故补具名导出。
export { buildGuolaoAnchorLines };
