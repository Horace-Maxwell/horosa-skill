// 七政四余 AI 快照段 builder —— 自上游 components/guolao/GuoLaoChartMain.js **逐字**抽出
// （bespoke，derived_from + derived_sha256 看守：上游 GuoLaoChartMain.js 一动即红，复核本文件后 --restamp）：
//   · buildGuolaoAnchorLines —— [起盘信息] 命度 / 身度 / 命度宿主·身度宿主 行（v3.11.0 [Q-231/Q-434]）
//   · buildGuolaoMastersSection —— [三主与化曜]（v3.11.0 [Q-435]）
//   · buildGuolaoLimitCalcSection —— [限法实算]（v3.11.0 [Q-435]）
//   · buildGuolaoLimitSection —— [大限]（GFM 表 + 所选行运法结构；[Q-188/T-125] 年界 / 定童限）
//   · buildGuolaoSetupLines —— [起盘信息] 口径六行（七政命度 / 罗计 / 报时星太阳时 / 罗计取法·月孛取法 /
//     宿度制·身宫法 / 命主取法·行运法；_buildGuolaoSnapshotTextV2Core:2047-2073 的内联行收成函数，行文逐字）
//     及其查名助手 guolaoLifeModeName / guolaoNodeModeName / guolaoSu28ModeFromFields / guolaoFieldValue（逐字）。
// 上游该文件 4350 行，其余是 React 组件与取数编排；政余格局闭包另在 guolaoMoira.js（同源不同段）。
// 只有下方 import 按 vendor 树改了路径（上游 import 名：moiraLifeDegree as lifeDegree 等，逐字保留别名）。
import * as AstroConst from '../../constants/AstroConst.js';
import { moiraBuildLimitTable as buildLimitTable, moiraLifeDegree as lifeDegree, moiraBirthYearBasis } from './guolaoMoiraWheelLimits.js';
import { computeDongwei as glDongwei, computeTongxian as glTongxian } from './guolaoTransit.js';
import { normalizeGuolaoLifeMode, GUOLAO_LIFE_MODE_ASC, GUOLAO_LIFE_MODE_YUMAO, GUOLAO_LIFE_MODE_COTRANS } from './guolaoMoiraWheelLimits.js';
import { SU28_MODE_LABEL } from './guolaoData.js';

// ── GuoLaoChartStyle.js 的罗计口径（逐字）与 getStored* 的 headless 缺省（上游读不到 localStorage 键时的返回值）──
export const GUOLAO_NODE_MODE_NORTH_KETU = 'northKetuSouthRahu';
export const GUOLAO_NODE_MODE_NORTH_RAHU = 'northRahuSouthKetu';
export const GUOLAO_DEFAULT_SU28_MODE = 2;
export function normalizeGuolaoNodeMode(val){
	if(val === GUOLAO_NODE_MODE_NORTH_RAHU){
		return GUOLAO_NODE_MODE_NORTH_RAHU;
	}
	return GUOLAO_NODE_MODE_NORTH_KETU;
}
const getStoredGuolaoLifeMode = ()=>GUOLAO_LIFE_MODE_ASC;
const getStoredGuolaoNodeMode = ()=>GUOLAO_NODE_MODE_NORTH_KETU;
const getStoredGuolaoSu28Mode = ()=>GUOLAO_DEFAULT_SU28_MODE;
const getStoredGuolaoTrueSolarTime = ()=>'true';
const getStoredGuolaoNodeType = ()=>'mean';
const getStoredGuolaoLilithType = ()=>'mean';
const getStoredGuolaoBodyMode = ()=>'taiyin';

// GuoLaoChartMain.js:1190-1200（逐字）。
function guolaoNodeModeFromFields(fields){
	if(fields && fields.guolaoNodeMode && fields.guolaoNodeMode.value !== undefined && fields.guolaoNodeMode.value !== null){
		return normalizeGuolaoNodeMode(fields.guolaoNodeMode.value);
	}
	return getStoredGuolaoNodeMode();
}

function guolaoNodeModeName(mode){
	const normalized = normalizeGuolaoNodeMode(mode);
	return normalized === GUOLAO_NODE_MODE_NORTH_RAHU ? '北罗南计' : '北计南罗';
}

// GuoLaoChartMain.js:1531-1566（逐字）。
function guolaoLifeModeFromFields(fields){
	if(fields && fields.guolaoLifeMode && fields.guolaoLifeMode.value !== undefined && fields.guolaoLifeMode.value !== null){
		return normalizeGuolaoLifeMode(fields.guolaoLifeMode.value);
	}
	return getStoredGuolaoLifeMode();
}

// 七政宿度制(su28Mode 0-4)：优先 fields.doubingSu28（页面选/存盘值，数据丢失修复后保真），
// 缺省回退 getStoredGuolaoSu28Mode（AI 挂载抽屉「宿度制」/全局默认 2）。与 命度/罗计 同口径。
export function guolaoSu28ModeFromFields(fields){
	if(fields && fields.doubingSu28 && fields.doubingSu28.value !== undefined && fields.doubingSu28.value !== null){
		const v = Number(fields.doubingSu28.value);
		// [挂载自检 F-16] 值域单源 SU28_MODE_LABEL(含 8=赤道回归实时);此前手抄 [0..7] 漏 8 → 存 8 的盘回退全局档。
		if(Number.isFinite(v) && Object.prototype.hasOwnProperty.call(SU28_MODE_LABEL, v)){
			return v;
		}
	}
	return getStoredGuolaoSu28Mode();
}

function guolaoLifeModeName(mode){
	const normalized = normalizeGuolaoLifeMode(mode);
	if(normalized === GUOLAO_LIFE_MODE_YUMAO){
		return '日出安命';
	}
	if(normalized === GUOLAO_LIFE_MODE_COTRANS){
		return '赤黄转换';
	}
	if(normalized === 'gumao'){
		return '遇卯安命(古法)';
	}
	if('子丑寅卯辰巳午未申酉戌亥'.indexOf(normalized) >= 0){
		return `自定命宫·${normalized}`;
	}
	return '占星上升';
}

// GuoLaoChartMain.js:2403-2408（逐字）。
function guolaoFieldValue(fields, key, fallbackGetter){
	if(fields && fields[key] && fields[key].value !== undefined && fields[key].value !== null && `${fields[key].value}` !== ''){
		return `${fields[key].value}`;
	}
	return fallbackGetter ? fallbackGetter() : '';
}

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

// [起盘信息] 口径六行：_buildGuolaoSnapshotTextV2Core（GuoLaoChartMain.js:2047-2073）内联的 lines.push 逐字收成函数。
// _gDisp = 页面显示偏好（命主取法/行运法），headless 由调用方按挂载齿轮四键给（Python _guolao_display_settings）。
export function buildGuolaoSetupLines(fields, _gDisp){
	const lines = [];
	lines.push(`七政命度：${guolaoLifeModeName(guolaoLifeModeFromFields(fields))}`);
	lines.push(`罗计：${guolaoNodeModeName(guolaoNodeModeFromFields(fields))}`);
	// G6/G10/G11 起盘设置注入快照(AI 据此解读报时星/四余取法)。
	const _gTs = guolaoFieldValue(fields, 'guolaoTrueSolarTime', getStoredGuolaoTrueSolarTime);
	const _gNt = guolaoFieldValue(fields, 'guolaoNodeType', getStoredGuolaoNodeType);
	const _gLt = guolaoFieldValue(fields, 'guolaoLilithType', getStoredGuolaoLilithType);
	lines.push(`报时星太阳时：${_gTs === 'off' ? '钟表时' : (_gTs === 'mean' ? '平太阳时(仅经度)' : '真太阳时(经度+均时差)')}`);
	lines.push(`罗计取法：${_gNt === 'true' ? '真交点' : '平交点'}；月孛取法：${_gLt === 'true' ? '真远地点' : '平远地点'}`);
	// G20/G22/G31/G3 身宫法/命主取法/行运法/宿度制 注入快照。身宫法读 fields(类A);命主取法/行运法读全局显示偏好(类B)。
	const _gBody = guolaoFieldValue(fields, 'guolaoBodyMode', getStoredGuolaoBodyMode);
	const _gDispSafe = _gDisp || {};
	const _su28Name = SU28_MODE_LABEL[guolaoSu28ModeFromFields(fields)] || '回归今宿';   // 单源 SU28_MODE_LABEL(WP-A,消第三套漂移)
	const _lmName = { gong: '宫主', du: '度主', dudegrade: '贬宫主专度主' }[_gDispSafe.lifeMasterMode || 'gong'] || '宫主';
	const _mlName = { '': '古度限度法', dongwei: '洞微大限', minor: '小限', month: '月限', tong: '童限' }[_gDispSafe.minorLimitType || ''] || '古度限度法';
	const _gBodyName = _gBody === 'youjin' ? '逢酉(琴堂)' : ('子丑寅卯辰巳午未申酉戌亥'.indexOf(_gBody) >= 0 ? `自定身宫·${_gBody}` : '太阴落宫(果老)');
	lines.push(`宿度制：${_su28Name}；身宫法：${_gBodyName}`);
	lines.push(`命主取法：${_lmName}；行运法：${_mlName}`);
	return lines;
}

// 上游 buildGuolaoAnchorLines 是模块私有（快照拼装内部用）；headless 快照在 skill 侧拼装，故补具名导出。
export { buildGuolaoAnchorLines };
