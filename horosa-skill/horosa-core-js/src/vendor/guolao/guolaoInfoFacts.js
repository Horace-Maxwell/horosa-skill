// 七政四余右栏「命身与限度 / 三主·化曜 / 难仇恩用 / 飞限·童限·小限·月限·限度 / 行运法」诸卡的事实层 ——
// 自上游 components/guolao/GuoLaoMoiraPanel.js **逐字**抽出 buildGuolaoMoiraInfoFacts 及其全部依赖闭包
// （bespoke，derived_from + derived_sha256 看守：上游 GuoLaoMoiraPanel.js 一动即红，复核本文件后 --restamp）。
// 上游该文件其余部分是 React 表格组件（JSX），整份 vendor 不可行。页面渲染与 AI 快照（[起盘信息] 命度/身度/宿主行、
// [三主与化曜]、[限法实算]）在上游同取此函数 ——「页面显示什么、快照就写什么」。只有下方 import 按 vendor 树改了路径。
import * as AstroConst from '../../constants/AstroConst.js';
import * as AstroText from '../../constants/AstroText.js';
import { moiraBuildLimitTable as buildLimitTable, moiraBirthYearBasis as birthYearBasis, moiraCurrentLimitIndex as currentLimitIndex } from './guolaoMoiraWheelLimits.js';
import { LIFE_HELPER_LABELS, lifeHelperRow, weakSolidPillars, smallLimitBranch, flyLimitBranches, limitDegreeSpan, childAgeLimitYears, childYearsSpan, childLimitBranch, monthLimitBranch, lunarMonthNumFromBranch, branchElementOf } from './guolaoMoiraTables.js';
import { PALACE_LORD as GL_PALACE_LORD, SU28 as GL_SU28, SU28_DEGREE_LORD as GL_SU28_LORD, HUAYAO_A as GL_HUAYAO_A } from './guolaoData.js';
import { computeDongwei as glDongwei, computeXiaoxian as glXiaoxian, computeTongxian as glTongxian, computeYuexian as glYuexian } from './guolaoTransit.js';

// 三主(命主/身主/度主)+ 命宫配干(五虎遁)+ 生年化曜:纯前端从命/身宫地支 + 命度宿 + 年干派生(古法立成)。
const GL_GAN = '甲乙丙丁戊己庚辛壬癸';

const GL_ZHI = '子丑寅卯辰巳午未申酉戌亥';

function glZiChar(zi){ const s = String(zi || ''); for(let i = 0; i < s.length; i++){ if(GL_ZHI.indexOf(s[i]) >= 0){ return s[i]; } } return ''; }

export function deriveGuolaoMasters(life, self, lifeSuName, yearStem, lifeMasterMode){
	const lz = glZiChar(life && life.zi);
	const sz = glZiChar(self && self.zi);
	const lmMode = (lifeMasterMode === 'du' || lifeMasterMode === 'dudegrade') ? lifeMasterMode : 'gong';
	const out = { mingPalaceZi: lz, bodyPalaceZi: sz, lifeMaster: '', bodyMaster: '', degMaster: '', mingStem: '', huayao: '', lifeMasterMode: lmMode, lifeMasterStar: '' };
	if(lz && GL_PALACE_LORD[lz]){ out.lifeMaster = GL_PALACE_LORD[lz][1]; }
	if(sz && GL_PALACE_LORD[sz]){ out.bodyMaster = GL_PALACE_LORD[sz][1]; }
	if(lifeSuName){ const i = GL_SU28.indexOf(glSuChar(lifeSuName)); if(i >= 0){ out.degMaster = GL_SU28_LORD[i]; } }
	const gi = GL_GAN.indexOf(yearStem || '');
	if(gi >= 0 && lz){ const yin = (gi * 2 + 2) % 10; const bi = GL_ZHI.indexOf(lz); out.mingStem = GL_GAN[(yin + (bi - 2 + 12) % 12) % 10]; }
	out.huayao = GL_HUAYAO_A[yearStem || ''] || '';
	// G22/G23 命主取法:gong=命宫宫主(默认)/du=命度度主/dudegrade=贬宫主专度主(果老)。两主始终都显于三主表。
	out.lifeMasterStar = ((out.lifeMasterMode === 'du' || out.lifeMasterMode === 'dudegrade') && out.degMaster) ? out.degMaster : out.lifeMaster;
	return out;
}

function glSuChar(name){ const s = String(name || ''); for(let i = 0; i < s.length; i++){ if(GL_SU28.indexOf(s[i]) >= 0){ return s[i]; } } return ''; }

const STEM_BRANCHES = ['甲子', '乙丑', '丙寅', '丁卯', '戊辰', '己巳', '庚午', '辛未', '壬申', '癸酉', '甲戌', '乙亥', '丙子', '丁丑', '戊寅', '己卯', '庚辰', '辛巳', '壬午', '癸未', '甲申', '乙酉', '丙戌', '丁亥', '戊子', '己丑', '庚寅', '辛卯', '壬辰', '癸巳', '甲午', '乙未', '丙申', '丁酉', '戊戌', '己亥', '庚子', '辛丑', '壬寅', '癸卯', '甲辰', '乙巳', '丙午', '丁未', '戊申', '己酉', '庚戌', '辛亥', '壬子', '癸丑', '甲寅', '乙卯', '丙辰', '丁巳', '戊午', '己未', '庚申', '辛酉', '壬戌', '癸亥'];

function safeList(val){
	return val && val.length ? val : [];
}

function safeMap(val){
	return val && typeof val === 'object' ? val : {};
}

function mergeDefined(){
	const res = {};
	for(let i=0; i<arguments.length; i++){
		const obj = safeMap(arguments[i]);
		Object.keys(obj).forEach((key)=>{
			if(obj[key] !== undefined && obj[key] !== null && obj[key] !== ''){
				res[key] = obj[key];
			}
		});
	}
	return res;
}

function msg(id){
	if(id === undefined || id === null){
		return '';
	}
	return AstroText.AstroMsgCN[id] || AstroText.AstroTxtMsg[id] || AstroText.AstroMsg[id] || `${id}`;
}

function norm(deg){
	let val = Number(deg);
	if(!Number.isFinite(val)){
		return 0;
	}
	val %= 360;
	if(val < 0){
		val += 360;
	}
	return val;
}

// 黄仪/赤仪显示口径(chart.displayCoord 单一真值源;旧数据回退恒星制旧判据)。
function isEclipticDisplay(chart){
	const coord = chart && chart.displayCoord;
	if(coord === 'ecliptic'){ return true; }
	if(coord === 'equatorial'){ return false; }
	const params = chart && chart.params ? chart.params : {};
	return Number(params.doubingSu28) === 4 || Number(params.guolaoZhengSidereal) === 1;
}

function objectLon(obj, preferLon = false){
	const num = Number(obj && (preferLon && obj.lon !== undefined ? obj.lon : (obj.ra !== undefined ? obj.ra : obj.lon)));
	if(Number.isFinite(num)){
		return norm(num);
	}
	const sign = obj && obj.sign ? AstroConst.LIST_SIGNS.indexOf(obj.sign) : -1;
	const signlon = Number(obj && obj.signlon);
	if(sign >= 0 && Number.isFinite(signlon)){
		return norm(sign * 30 + signlon);
	}
	return null;
}

function degreeText(lon){
	const val = norm(lon);
	const deg = Math.floor(val % 30);
	const min = Math.floor(((val % 30) - deg) * 60);
	return `${deg}度${min}分`;
}

function suDegreeText(lon){
	const val = norm(lon);
	const deg = Math.floor(val);
	const min = Math.floor((val - deg) * 60);
	return `${deg}度${min}分`;
}

function signNameFromLon(lon){
	const idx = Math.floor(norm(lon) / 30) % 12;
	return msg(AstroConst.LIST_SIGNS[idx]);
}

function ziFromLon(lon){
	// 七政「宫位序↔地支」镜像:支 = (10 − 宫序 + 12) % 12(白羊=戌、巨蟹=未、水瓶=子)。
	// 旧版把宫序直接当支序(巨蟹→卯),致「位置」列地支与盘面严重错位——已纠正。
	const list = ['子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥'];
	const signIdx = Math.floor(norm(lon) / 30) % 12;
	return list[(10 - signIdx + 12) % 12] || '';
}

function anchorFromObject(chart, id, fallbackId, label){
	const obj = findObject(chart, id) || findObject(chart, fallbackId);
	const lon = objectLon(obj, isEclipticDisplay(chart));
	if(!obj || lon === null){
		return {};
	}
	return {
		longitude: lon,
		signName: signNameFromLon(lon),
		degreeText: degreeText(lon),
		zi: ziFromLon(lon),
		area: msg(obj.id) || label,
		moiraHouse: msg(obj.house) || '',
	};
}

function suHostForLon(chart, lon){
	const val = Number(lon);
	const stars = safeList(chart && chart.fixedStarSu28).map((item)=>({
		name: item.name || item.label || '',
		ra: Number(item.ra),
	})).filter((item)=>item.name && Number.isFinite(item.ra)).sort((a, b)=>a.ra - b.ra);
	if(!stars.length || !Number.isFinite(val)){
		return null;
	}
	const degree = norm(val);
	let star = stars[stars.length - 1];
	for(let i = 0; i < stars.length; i++){
		if(stars[i].ra <= degree){
			star = stars[i];
		}else {
			break;
		}
	}
	const offset = norm(degree - star.ra);
	return {
		name: star.name,
		offset,
		degreeText: suDegreeText(offset),
		value: `${star.name} ${suDegreeText(offset)}`,
	};
}

function stemBranchForYear(year){
	const idx = ((Number(year) - 1984) % 60 + 60) % 60;
	return STEM_BRANCHES[idx] || '';
}

function yearFromParams(params){
	const raw = params && params.date ? `${params.date}` : '';
	const match = raw.match(/-?\d{3,4}/);
	return match ? Number(match[0]) : new Date().getFullYear();
}

function getBazi(root){
	const chart = root && root.chart ? root.chart : {};
	return (chart.nongli && chart.nongli.bazi) || (root && root.nongli && root.nongli.bazi) || {};
}

function textFromBaziPole(value){
	if(value === undefined || value === null || value === ''){
		return '';
	}
	if(typeof value === 'string' || typeof value === 'number'){
		return `${value}`;
	}
	if(typeof value !== 'object'){
		return '';
	}
	const direct = value.text || value.name || value.value || value.ganzi || value.ganZi || value.pillar || value.column;
	if(direct){
		return `${direct}`;
	}
	const stem = safeMap(value.stem);
	const branch = safeMap(value.branch);
	const stemText = stem.cell || stem.text || stem.name || stem.value || value.gan || value.stemText || value.tianGan || '';
	const branchText = branch.cell || branch.text || branch.name || branch.value || value.zhi || value.branchText || value.diZhi || '';
	return `${stemText || ''}${branchText || ''}`;
}

function readBaziPole(bazi, key){
	const data = safeMap(bazi);
	const fourColumns = safeMap(data.fourColumns || data.fourcolumns || data.fourPillars || data.pillars);
	const fourZhuMap = safeMap(fourColumns.fourZhuMap || data.fourZhuMap);
	const zhKeys = {
		year: '年',
		month: '月',
		day: '日',
		time: '时',
	};
	const candidates = [
		data[key],
		fourColumns[key],
		data[`${key}Pole`],
		fourColumns[`${key}Pole`],
		data[`${key}Pillar`],
		fourColumns[`${key}Pillar`],
		data[`${key}Column`],
		fourColumns[`${key}Column`],
		data[`${key}Ganzi`],
		fourColumns[`${key}Ganzi`],
		zhKeys[key] ? fourZhuMap[zhKeys[key]] : '',
	];
	for(const item of candidates){
		const text = textFromBaziPole(item).trim();
		if(text){
			return text;
		}
	}
	return '';
}

function baziStemBranch(root, key, fallbackYear){
	const bazi = getBazi(root);
	const pole = readBaziPole(bazi, key);
	if(pole){
		return pole;
	}
	if(key === 'year'){
		return stemBranchForYear(fallbackYear);
	}
	return '';
}

function findObject(chart, id){
	const objects = chart && chart.objects ? chart.objects : [];
	return objects.find((obj)=>obj.id === id);
}

// [Q-231/Q-434/Q-435] 右栏「命身与限度」「三主·命宫配干·化曜」「难仇恩用」「飞限·童限·小限·月限·限度」「行运法」
// 诸卡的事实层单源:面板渲染与 AI 快照([起盘信息] 命度/身度/宿主行、[三主与化曜]、[限法实算])都从这里取值,
// 保证「页面显示什么、快照就写什么」。纯函数、零 React。transitValue 缺(无头挂载)时,月限所需的流年月支
// 由调用方传入本地历法算得的伪 root(见 GuoLaoChartMain.buildGuolaoInfoFactsForSnapshot),缺则月限行省略。
export function buildGuolaoMoiraInfoFacts(input){
	const o = input || {};
	const rootValue = o.rootValue || {};
	const value = o.value || {};
	const birthChart = rootValue.chart || {};
	const transitRoot = o.transitValue || {};
	const params = mergeDefined(value.params, rootValue.params, o.params);
	const transitParams = safeMap(o.transitParams);
	const display = o.display || {};
	const fields = o.fields || {};
	const limitChildBase = Number(display.limitChildBase) === 10 ? 10 : 9;   // 定童限 base,与大限环同口径
	const anchors = value.anchors || {};
	const life = anchors.life && Object.keys(anchors.life).length
		? anchors.life
		: anchorFromObject(birthChart, AstroConst.LIFEMASTERDEG74, AstroConst.ASC, '命度点');
	const self = anchors.self && Object.keys(anchors.self).length
		? anchors.self
		: anchorFromObject(birthChart, AstroConst.MOON, AstroConst.ASC, '身度参考');
	const lifeSuHost = suHostForLon(birthChart, life.longitude);
	const selfSuHost = suHostForLon(birthChart, self.longitude);
	const birthYear = yearFromParams(params);
	const transitYear = yearFromParams(transitParams);
	const birthYearText = baziStemBranch(rootValue, 'year', birthYear);
	const transitYearText = stemBranchForYear(transitYear);
	const age = transitYear - birthYear + 1;
	const lifeModeName = anchors.lifeModeName || value.lifeModeName || '';

	// 三主(命主/身主/度主)+ 命宫配干(五虎遁)+ 生年化曜:纯前端派生(古法立成)。
	const masters = deriveGuolaoMasters(life, self, lifeSuHost && lifeSuHost.name, (birthYearText || '').slice(0, 1), display.lifeMasterMode);
	const useDu = masters.lifeMasterMode === 'du' || masters.lifeMasterMode === 'dudegrade';
	const masterItems = [];
	if(masters.lifeMasterStar){ masterItems.push({ label: useDu ? '命主(度主)' : '命主(宫主)', value: masters.lifeMasterStar }); }
	if(masters.lifeMaster){ masterItems.push({ label: '命宫宫主', value: masters.lifeMaster }); }
	if(masters.degMaster){ masterItems.push({ label: '命度度主(宿主曜)', value: masters.degMaster }); }
	if(masters.bodyMaster){ masterItems.push({ label: '身主(身宫宫主)', value: masters.bodyMaster }); }
	if(masters.mingStem && masters.mingPalaceZi){ masterItems.push({ label: '命宫配干(五虎遁)', value: `${masters.mingStem}${masters.mingPalaceZi}` }); }
	if(masters.huayao){ masterItems.push({ label: '生年化曜(A诀)', value: masters.huayao }); }

	// 难仇恩用(度/宫两役行,主星五行查表)。
	const helperRows = [];
	const duElem = masters.degMaster ? `${masters.degMaster}`.charAt(0) : '';
	const gongElem = masters.lifeMaster ? `${masters.lifeMaster}`.charAt(0) : branchElementOf(life && life.zi ? `${life.zi}`.slice(-1) : '');
	const duRow = lifeHelperRow(duElem);
	const gongRow = lifeHelperRow(gongElem);
	if(duRow){ helperRows.push({ head: '度', main: duElem, roles: duRow }); }
	if(gongRow){ helperRows.push({ head: '宫', main: gongElem, roles: gongRow }); }

	// 虚实四柱(虚=旬空)。
	const baziObj = getBazi(rootValue);
	const pillarOf = (key)=>{
		const col = baziObj && baziObj[key];
		if(!col){ return ''; }
		if(col.text){ return col.text; }
		const stem = col.stem && col.stem.cell ? col.stem.cell : '';
		const branch = col.branch && col.branch.cell ? col.branch.cell : '';
		return `${stem}${branch}`;
	};
	const pillars = [pillarOf('year'), pillarOf('month'), pillarOf('day'), pillarOf('time')];
	const weakSolid = pillars.some(Boolean) ? weakSolidPillars(pillars) : null;

	// 飞限/童限/小限/月限/限度(照 Moira):童限边界=四舍值;限度首宫=不四舍值。
	const lifeLon = Number(life && life.longitude);
	const hasLife = Number.isFinite(lifeLon) && Number.isFinite(age);
	const SIGN_BRANCH_LOCAL = ['戌', '酉', '申', '未', '午', '巳', '辰', '卯', '寅', '丑', '子', '亥'];
	const fmtLimitDeg = (deg)=>{
		const v = ((Number(deg) % 360) + 360) % 360;
		const sign = Math.floor(v / 30);
		const inDeg = v - sign * 30;
		const d = Math.floor(inDeg);
		const m = Math.floor((inDeg - d) * 60);
		return `${String(d).padStart(2, '0')}${SIGN_BRANCH_LOCAL[sign]}${String(m).padStart(2, '0')}`;
	};
	let limits = null;
	if(hasLife){
		const childLimit = childAgeLimitYears(lifeLon, limitChildBase);
		const childSpan = childYearsSpan(lifeLon, limitChildBase);
		const fly = flyLimitBranches(lifeLon, Math.max(0, age - 1), childLimit);
		const span = limitDegreeSpan(lifeLon, age, childSpan);
		const childZhi = age <= childLimit ? childLimitBranch(lifeLon, age) : '';
		// 月限(照 Moira getMonthLimit):生月支 / 流年时刻月支 → 农历月序(月建口径);数据缺则空。
		const monthBranchCell = (col)=>{ const b = col && col.branch; return (b && (b.cell || b.text)) || ''; };
		const monthZhi = monthLimitBranch(lifeLon, age,
			lunarMonthNumFromBranch(monthBranchCell(baziObj.month) || glZiChar((baziStemBranch(rootValue, 'month') || '').slice(-1))),
			lunarMonthNumFromBranch(monthBranchCell(getBazi(transitRoot).month) || glZiChar((baziStemBranch(transitRoot, 'month') || '').slice(-1))));
		limits = {
			age, transitYearText,
			fly: fly && fly.branches.length ? fly.branches.join('/') + (fly.halfYear ? '（各半年）' : '') : '',
			childZhi,
			small: smallLimitBranch(lifeLon, age),
			monthZhi,
			spanFrom: span ? fmtLimitDeg(span.from) : '',
			spanTo: span ? fmtLimitDeg(span.to) : '',
		};
		limits.items = [
			limits.fly ? { label: '飞限', value: limits.fly } : null,
			childZhi ? { label: '童限', value: childZhi } : null,
			{ label: '小限', value: limits.small },
			monthZhi ? { label: '月限', value: monthZhi } : null,
			limits.spanFrom ? { label: '限度', value: limits.spanFrom } : null,
			limits.spanTo ? { label: '至', value: limits.spanTo } : null,
		].filter(Boolean);
	}

	// 行运法(类B):''古度限度法(默认)/dongwei洞微大限/minor小限/month月限/tong童限。
	let runLaw = null;
	const limitType = display.minorLimitType || '';
	const sunLon = objectLon(findObject(birthChart, AstroConst.SUN), isEclipticDisplay(birthChart));
	const mz = life && life.zi;
	if(limitType === '' && Number.isFinite(Number(life.longitude)) && Number.isFinite(birthYear)){
		const limitBasis = birthYearBasis(birthChart, fields, display.limitYearBoundary || 'gregorian');
		const rows = buildLimitTable(Number(life.longitude), birthYear + limitBasis.yearShift, limitChildBase, limitBasis.frac);
		runLaw = { type: '', rows, curIdx: Number.isFinite(age) ? currentLimitIndex(rows, age) : -1 };
	}else if(limitType !== '' && Number.isFinite(Number(sunLon)) && mz){
		if(limitType === 'dongwei'){
			const dw = glDongwei(Number(sunLon) % 30);
			let curDiaodu = null;
			if(Number.isFinite(age)){
				const curRow = dw.rows.find((rr)=> age >= rr.fromAge && age < rr.toAge);
				if(curRow && curRow.diaodu && curRow.diaodu.length){
					curDiaodu = curRow.diaodu.reduce((best, d)=> (d.age <= age + 1e-6 && (!best || d.age > best.age)) ? d : best, null) || curRow.diaodu[0];
				}
			}
			runLaw = { type: 'dongwei', startAge: dw.startAge, rows: dw.rows, curDiaodu, age };
		}else if(limitType === 'tong'){
			const tx = glTongxian(Number(sunLon), display.tongxianBase || 'tong10');
			const baseName = { tong10: '通行十年', gu9: '古九岁', xu11: '虚十一(早不过11)' }[tx.baseVariant] || '通行十年';
			runLaw = { type: 'tong', baseName, palaces: tx.palaces, exitAge: tx.exitAge };
		}else if(limitType === 'month'){
			// 生月按月柱地支(节气月,寅=正月);月柱缺则回退阳历月。
			const monthZhi = glZiChar((baziStemBranch(rootValue, 'month') || '').slice(-1));
			let bMonth = 1;
			const mzi = GL_ZHI.indexOf(monthZhi);
			if(mzi >= 0){ bMonth = ((mzi - 2) % 12 + 12) % 12 + 1; }
			else { const bp = String((params && (params.birth || params.date)) || '').replace(/[/T-]/g, ' ').trim().split(/\s+/); bMonth = bp.length >= 2 ? (parseInt(bp[1], 10) || 1) : 1; }
			const yx = Number.isFinite(age) ? glYuexian(mz, age, bMonth) : null;
			runLaw = { type: 'month', bMonth, age, palaceName: yx ? yx.palaceName : '', palaceZi: yx ? yx.palaceZi : '' };
		}else{
			const xx = Number.isFinite(age) ? glXiaoxian(mz, age) : null;
			runLaw = { type: 'minor', age, palaceName: xx ? xx.palaceName : '', palaceZi: xx ? xx.palaceZi : '' };
		}
	}

	return {
		anchors, life, self, lifeSuHost, selfSuHost, lifeModeName,
		birthYear, transitYear, birthYearText, transitYearText, age,
		masters, useDu, masterItems,
		helperRows, helperLabels: LIFE_HELPER_LABELS,
		weakSolid, limits, runLaw,
	};
}
