







import * as LRConst from '../liureng/LRConst.js';
import { ZSList, ZhangSheng, } from '../liureng/LRZhangSheng.js';


// headless stub：comp/DateTime 是页面的日期时间类（moment 包装），只被行年回退链 cloneDateTimeSafe / buildBirthFields /
// buildFallbackRunYearByYearDiff 用到——金口诀非行年盘，headless 的 buildJinKouSnapshotText 以 runyear=null 调、不走这条链。
// 定义同名类让 stub 审计看到「已知且不可达」，真被调到时抛明确错误而不是 ReferenceError。
class DateTime { constructor(){ throw new Error('headless stub: comp/DateTime is not vendored'); } }
// utils/constants（含 ServerRoot，流水线按「后端 import」整条删）的缺省经纬度只在 buildBirthFields 里读，同一条不可达链；读到即抛。
const Constants = new Proxy({}, { get(_t, key){ throw new Error(`headless stub: utils/constants.${String(key)} is not vendored`); } });




import {
	JINKOU_BASHE_DOC,
	JINKOU_SIXIANG_SHU_COLS,
	JINKOU_SIXIANG_SHU_NOTES,
	JINKOU_SIXIANG_WUXING_COLS,
	JINKOU_SIXIANG_WUXING_NOTES,
} from './JinKouDoc.js';









import { defaultAfter23NewDay, defaultLateZiHourUseNextDay } from '../bazi/dayBoundary.js';




// 签名数组逐元素严格相等(引用/值);用于装配缓存命中判定(只多算、绝不少算)。
function sameSigArr(a, b){
	if(!a || !b || a.length !== b.length){
		return false;
	}
	for(let i = 0; i < a.length; i++){
		if(a[i] !== b[i]){
			return false;
		}
	}
	return true;
}

function cloneDateTimeSafe(val, fallback){
	if(val && val instanceof DateTime){
		return val.clone();
	}
	if(fallback && fallback instanceof DateTime){
		return fallback.clone();
	}
	return new DateTime();
}

function buildBirthFields(source, fallbackNow){
	const now = fallbackNow && fallbackNow instanceof DateTime ? fallbackNow : new DateTime();
	const src = source || {};
	const dateVal = src.date && src.date.value ? cloneDateTimeSafe(src.date.value, now.startOf('date')) : now.startOf('date');
	const timeVal = src.time && src.time.value ? cloneDateTimeSafe(src.time.value, now) : now.clone();
	return {
		date: { value: dateVal },
		time: { value: timeVal },
		ad: { value: src.ad && src.ad.value !== undefined ? src.ad.value : now.ad },
		zone: { value: src.zone && src.zone.value ? src.zone.value : now.zone },
		lat: { value: src.lat && src.lat.value ? src.lat.value : Constants.DefLat },
		lon: { value: src.lon && src.lon.value ? src.lon.value : Constants.DefLon },
		gpsLat: { value: src.gpsLat && src.gpsLat.value !== undefined ? src.gpsLat.value : Constants.DefGpsLat },
		gpsLon: { value: src.gpsLon && src.gpsLon.value !== undefined ? src.gpsLon.value : Constants.DefGpsLon },
		gender: { value: src.gender && src.gender.value !== undefined ? src.gender.value : 1 },
		after23NewDay: { value: src.after23NewDay && src.after23NewDay.value !== undefined ? src.after23NewDay.value : defaultAfter23NewDay() },
		lateZiHourUseNextDay: { value: src.lateZiHourUseNextDay && src.lateZiHourUseNextDay.value !== undefined ? src.lateZiHourUseNextDay.value : defaultLateZiHourUseNextDay() },
	};
}

function fmtValue(value){
	if(value === undefined || value === null || value === ''){
		return '无';
	}
	if(value instanceof Array){
		return value.join('、') || '无';
	}
	return `${value}`;
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

function cleanKey(key){
	const txt = `${key || ''}`;
	const idx = txt.indexOf('(');
	if(idx >= 0){
		return txt.substring(0, idx);
	}
	return txt;
}

function appendMapSection(lines, title, obj){
	lines.push(`[${title}]`);
	if(!obj || typeof obj !== 'object'){
		lines.push('无');
		lines.push('');
		return;
	}
	const keys = Object.keys(obj);
	if(keys.length === 0){
		lines.push('无');
		lines.push('');
		return;
	}
	for(let i=0; i<keys.length; i++){
		const key = keys[i];
		lines.push(`${cleanKey(key)}：${fmtValue(obj[key])}`);
	}
	lines.push('');
}

function extractGanZi(text){
	const raw = `${text || ''}`.trim();
	if(raw.length < 2){
		return '';
	}
	if(LRConst.GanList.indexOf(raw.substr(0, 1)) >= 0 && LRConst.ZiList.indexOf(raw.substr(1, 1)) >= 0){
		return raw.substr(0, 2);
	}
	for(let i=0; i<raw.length - 1; i++){
		const gan = raw.substr(i, 1);
		const zi = raw.substr(i + 1, 1);
		if(LRConst.GanList.indexOf(gan) >= 0 && LRConst.ZiList.indexOf(zi) >= 0){
			return gan + zi;
		}
	}
	return '';
}

function resolveGuaYearGanZi(liureng){
	if(!liureng){
		return '';
	}
	const fourYear = liureng.fourColumns ? liureng.fourColumns.year : null;
	if(fourYear){
		if(typeof fourYear === 'string'){
			const got = extractGanZi(fourYear);
			if(got){
				return got;
			}
		}else if(fourYear.ganzi){
			const got = extractGanZi(fourYear.ganzi);
			if(got){
				return got;
			}
		}
	}
	const nongli = liureng.nongli ? liureng.nongli : {};
	const fallback = [
		nongli.yearGanZi,
		nongli.yearJieqi,
		nongli.year,
	];
	for(let i=0; i<fallback.length; i++){
		const got = extractGanZi(fallback[i]);
		if(got){
			return got;
		}
	}
	return '';
}

const JiaZiList = (()=>{
	const list = [];
	for(let i=0; i<60; i++){
		list.push(`${LRConst.GanList[i % 10]}${LRConst.ZiList[i % 12]}`);
	}
	return list;
})();

function buildRunYearList(startGanZi, delta){
	const list = [];
	let idx = JiaZiList.indexOf(startGanZi);
	if(idx < 0){
		return list;
	}
	for(let i=0; i<60; i++){
		list.push(JiaZiList[idx]);
		idx = (idx + delta + 60) % 60;
	}
	return list;
}

const MaleRunYearList = buildRunYearList('丙寅', 1);
const FemaleRunYearList = buildRunYearList('壬申', -1);

function resolveCycleYear(ganzi, approxYear){
	const idx = JiaZiList.indexOf(ganzi);
	if(idx < 0){
		return approxYear;
	}
	const base = 1984 + idx; // 1984 = 甲子
	const k = Math.floor((approxYear - base) / 60);
	const c1 = base + k * 60;
	const c2 = c1 + 60;
	return Math.abs(c2 - approxYear) < Math.abs(c1 - approxYear) ? c2 : c1;
}

function calcRunYearLocal(birthGanZi, guaGanZi, gender, birthYear, guaYear){
	const bIdx = JiaZiList.indexOf(extractGanZi(birthGanZi));
	const gIdx = JiaZiList.indexOf(extractGanZi(guaGanZi));
	if(bIdx < 0 || gIdx < 0){
		return null;
	}
	const ageCycle = (gIdx - bIdx + 60) % 60;
	let age = ageCycle;
	if(Number.isFinite(birthYear) && Number.isFinite(guaYear)){
		const bSolar = resolveCycleYear(JiaZiList[bIdx], birthYear);
		const gSolar = resolveCycleYear(JiaZiList[gIdx], guaYear);
		const diff = gSolar - bSolar;
		if(diff >= 0){
			age = diff;
		}
	}
	const male = `${gender}` !== '0';
	const yearList = male ? MaleRunYearList : FemaleRunYearList;
	return {
		age,
		ageCycle,
		year: yearList[ageCycle] || '',
	};
}

function getSolarYearFromField(field){
	if(!field || !field.value){
		return NaN;
	}
	const dt = field.value;
	const y = Number(dt.year);
	if(!Number.isFinite(y)){
		return NaN;
	}
	const ad = Number(dt.ad || 1);
	return ad >= 0 ? y : -y;
}

function buildFallbackRunYearByYearDiff(birth, guaFields){
	const birthYear = getSolarYearFromField(birth && birth.date ? birth.date : null);
	const guaYear = getSolarYearFromField(guaFields && guaFields.date ? guaFields.date : null);
	if(!Number.isFinite(birthYear) || !Number.isFinite(guaYear) || guaYear < birthYear){
		return null;
	}
	const genderVal = birth && birth.gender ? birth.gender.value : 1;
	const age = guaYear - birthYear;
	const ageCycle = ((age % 60) + 60) % 60;
	const yearList = `${genderVal}` === '0' ? FemaleRunYearList : MaleRunYearList;
	return {
		age: age,
		ageCycle: ageCycle,
		year: yearList[ageCycle] || '',
	};
}

// export 供金标直测(与六壬同律,见 LiuRengMain.resolveDisplayRunYear 注)。
export function resolveDisplayRunYear(runyear, birth, guaFields){
	const fallback = buildFallbackRunYearByYearDiff(birth, guaFields);
	if(!fallback){
		return runyear;
	}
	const currAge = runyear && runyear.age !== undefined && runyear.age !== null ? Number(runyear.age) : NaN;
	const currAgeCycle = runyear && runyear.ageCycle !== undefined && runyear.ageCycle !== null ? Number(runyear.ageCycle) : NaN;
	const currYear = runyear && runyear.year ? `${runyear.year}` : '';
	const ageDelta = Number.isFinite(currAge) ? Math.abs(currAge - fallback.age) : NaN;
	const cycleDelta = Number.isFinite(currAgeCycle)
		? Math.min(Math.abs(currAgeCycle - fallback.ageCycle), 60 - Math.abs(currAgeCycle - fallback.ageCycle))
		: NaN;
	const hardMismatch = (Number.isFinite(ageDelta) && ageDelta >= 2)
		|| (Number.isFinite(cycleDelta) && cycleDelta >= 2);
	const sameAgeYearMismatch = Number.isFinite(currAge)
		&& currAge === fallback.age
		&& currYear !== ''
		&& fallback.year !== ''
		&& currYear !== fallback.year;
	const useFallback = !runyear
		|| !Number.isFinite(currAge)
		|| (currAge === 0 && fallback.age > 0)
		|| currYear === ''
		|| (currYear === '丙寅' && fallback.age > 0)
		|| hardMismatch
		|| sameAgeYearMismatch;
	if(!useFallback){
		return runyear;
	}
	// 走 fallback 时每次都新建对象 → 该引用进了中栏重绘签名（JinKouChart 的 runyear 项），
	// sameChartDrawSig 恒判「变了」，切右栏 tab 都会触发整棵 d3 重建，重绘守卫在这条路上形同虚设。
	// 按内容做一层记忆：内容不变则返回同一引用。
	const merged = { ...(runyear || {}), ...fallback };
	const key = JSON.stringify(merged);
	if(resolveDisplayRunYear._key === key && resolveDisplayRunYear._val){
		return resolveDisplayRunYear._val;
	}
	resolveDisplayRunYear._key = key;
	resolveDisplayRunYear._val = merged;
	return merged;
}

export function buildJinKouSnapshotText(params, liureng, runyear, jinkouData, wuxing, guirengType, gender){
	const lines = [];
	const nongli = liureng && liureng.nongli ? liureng.nongli : {};
	// 性别「未知」(-1)时计算按男排(行年 / 旬法皆以 gender≠0 取男表),快照却写「女」——
	//   同一份快照里「行年:男」与「性别:女」并存。与八字页口径统一:未知写「未知(按男排)」。
	const xingbie = `${gender}` === '1' ? '男' : (`${gender}` === '0' ? '女' : '未知(按男排)');
	const guirenType = jinkouData && jinkouData.source === 'kinjinkou' ? 'kinjinkou 贵人歌诀' : (guirengType === 0 ? '六壬法贵人' : (guirengType === 1 ? '遁甲法贵人' : '星占法贵人'));
	const briefKong = (txt)=>{
		const val = `${txt || ''}`;
		const hasEmpty = val.indexOf('空亡') >= 0;
		const hasSiKong = val.indexOf('四大空亡') >= 0;
		if(hasEmpty && hasSiKong){
			return '空&四空';
		}
		if(hasEmpty){
			return '空';
		}
		if(hasSiKong){
			return '四空';
		}
		return '';
	};
	const findRow = (name)=>{
		if(!jinkouData || !jinkouData.rows){
			return null;
		}
		for(let i=0; i<jinkouData.rows.length; i++){
			const row = jinkouData.rows[i];
			if(row && row.label === name){
				return row;
			}
		}
		return null;
	};
	const appendBriefRow = (name, withShenjiang)=>{
		const row = findRow(name);
		if(!row){
			lines.push(`${name}：无`);
			return;
		}
		const main = fmtValue(row.content);
		const shenjiang = withShenjiang && row.shenjiang && row.shenjiang !== '-' ? `（${row.shenjiang}）` : '';
		const power = row.power && row.power !== '—' ? row.power : '无';
		const kong = briefKong(row.kong);
		let line = `${name}：${main}${shenjiang}；（${power}）`;
		if(kong){
			line = `${line}；${kong}`;
		}
		lines.push(line);
	};

	lines.push('[起盘信息]');
	if(params){
		// 逐字段 fmtValue —— 原先整体判 params 非空后就裸插值，任一字段缺失即把字面量
		// 「undefined」写进快照、直送 AI 提示词。与本函数其余各行同律用 fmtValue（缺 → 无）。
		lines.push(`日期：${fmtValue(params.date)} ${fmtValue(params.time)}`);
		lines.push(`时区：${fmtValue(params.zone)}`);
		lines.push(`经纬度：${fmtValue(params.lon)} ${fmtValue(params.lat)}`);
	}
	if(nongli && nongli.birth){
		lines.push(`真太阳时：${nongli.birth}`);
	}
	if(liureng && liureng.fourColumns){
		const cols = liureng.fourColumns;
		lines.push(`四柱：${fmtValue(cols.year && cols.year.ganzi)}年 ${fmtValue(cols.month && cols.month.ganzi)}月 ${fmtValue(cols.day && cols.day.ganzi)}日 ${fmtValue(cols.time && cols.time.ganzi)}时`);
	}
	lines.push(`贵人体系：${guirenType}`);
	// 土之长生随流派(申/寅);默认「水土同宫·申」时不写此括注 → 既有快照逐字零回归。
	const soilNote = wuxing === '土' && jinkouData && jinkouData.schools && jinkouData.schools.soilChangSheng === 'yin'
		? '（火土同宫·寅）' : '';
	lines.push(`十二长生五行：${fmtValue(wuxing)}${soilNote}`);
	// 昼夜依「真实地平」时才写口径行(有盘可依);无盘回落时支粗判,不写 → 既有快照零回归。
	if(jinkouData && jinkouData.dayBasis === 'horizon'){
		lines.push(`昼夜：${jinkouData.isDay ? '昼占' : '夜占'}（${fmtValue(jinkouData.dayBasisText)}）`);
	}
	lines.push(`问测人性别：${xingbie}`);
	lines.push('');

	lines.push('[金口诀速览]');
	if(jinkouData && jinkouData.ready){
		lines.push(`地分：${fmtValue(jinkouData.topInfo.diFen)}`);
		// 月将/占时与中栏顶行同源入快照(此前 AI 看不到这两个排盘参数)。
		if(jinkouData.topInfo.yuejiang){ lines.push(`月将：${fmtValue(jinkouData.topInfo.yuejiang)}`); }
		if(jinkouData.topInfo.zhanshi){ lines.push(`占时：${fmtValue(jinkouData.topInfo.zhanshi)}`); }
		lines.push(`空亡：${fmtValue(jinkouData.topInfo.xunKong)}`);
		lines.push(`四大空亡：${fmtValue(jinkouData.topInfo.siDaKong)}`);
		if(jinkouData.yongYao && jinkouData.yongYao.label){
			lines.push(`用爻：${jinkouData.yongYao.label}${jinkouData.yongYao.sign ? `(${jinkouData.yongYao.sign})` : ''}`);
		}
		appendBriefRow('人元', false);
		appendBriefRow('贵神', true);
		appendBriefRow('将神', true);
		appendBriefRow('地分', false);
	}else{
		lines.push('无');
	}
	lines.push('');

	lines.push('[金口诀四位]');
	if(jinkouData && jinkouData.ready){
		lines.push(`地分：${fmtValue(jinkouData.topInfo.diFen)}`);
		// 月将/占时与中栏顶行同源入快照(此前 AI 看不到这两个排盘参数)。
		if(jinkouData.topInfo.yuejiang){ lines.push(`月将：${fmtValue(jinkouData.topInfo.yuejiang)}`); }
		if(jinkouData.topInfo.zhanshi){ lines.push(`占时：${fmtValue(jinkouData.topInfo.zhanshi)}`); }
		lines.push(`空亡：${fmtValue(jinkouData.topInfo.xunKong)}`);
		lines.push(`四大空亡：${fmtValue(jinkouData.topInfo.siDaKong)}`);
		if(jinkouData.yongYao && jinkouData.yongYao.label){
			lines.push(`用爻判定：${jinkouData.yongYao.reason || ''}；取${jinkouData.yongYao.label}${jinkouData.yongYao.sign ? `(${jinkouData.yongYao.sign})` : ''}`);
		}
		// 四位(人元/贵神/将神/地分)→ GFM 表:位/天干/内容/神将/状态/空亡/纳音(纳音缺 → —)。
		const siWeiRows = jinkouData.rows.map((row)=>[
			row.label, fmtValue(row.gan), fmtValue(row.content), fmtValue(row.shenjiang), fmtValue(row.power), fmtValue(row.kong), row.nayin ? fmtValue(row.nayin) : '',
		]);
		pushMdRows(lines, ['位', '天干', '内容', '神将', '状态', '空亡', '纳音'], siWeiRows);
		// 四位类象参考行(右栏「四位」tab 渲染有快照无;固定类象表,与渲染同文)。
		lines.push('四位类象：四人元=尊、客、天、君、祖、外；三贵神=上、主、宰相、臣、父、官禄；二月将=中、己身、妻财、亲戚、内；一地分=下、田宅、子孙、奴仆、鞍马、六畜');
	}else{
		lines.push('无');
	}
	lines.push('');

	lines.push('[金口诀三盘]');
	if(jinkouData && jinkouData.ready && jinkouData.plates && jinkouData.plates.length){
		// 三盘逐地分 → GFM 表:地分/天盘/将神/神盘/贵神。
		const plateRows = jinkouData.plates.map((row)=>[
			fmtValue(row.di), fmtValue(row.tian), fmtValue(row.jiang), fmtValue(row.shen), fmtValue(row.gui),
		]);
		pushMdRows(lines, ['地分', '天盘', '将神', '神盘', '贵神'], plateRows);
	}else{
		lines.push((jinkouData && jinkouData.platesNote) || '无');
	}
	lines.push('');

	lines.push('[四位神煞]');
	if(jinkouData && jinkouData.shenshaRows && jinkouData.shenshaRows.length){
		for(let i=0; i<jinkouData.shenshaRows.length; i++){
			const row = jinkouData.shenshaRows[i];
			lines.push(`${row.label}：${fmtValue(row.value)}`);
		}
	}else{
		lines.push('无');
	}
	lines.push('');

	lines.push('[用神强弱]');
	lines.push(jinkouData && jinkouData.yongStrength ? jinkouData.yongStrength.text : '无');
	lines.push('');

	lines.push('[发用·五动三动]');
	const jkDongSnap = jinkouData && jinkouData.dong ? jinkouData.dong : { wu: [], san: [] };
	const jkAllDong = [].concat(jkDongSnap.wu || [], jkDongSnap.san || []);
	if(jkAllDong.length){
		// 五动/三动 → GFM 表:动象/起→落/逢空/断语(逢空缺、断语缺 → —)。
		const dongRows = jkAllDong.map((d)=>[`${d.type}动`, `${d.from}→${d.to}`, d.kong ? '逢空' : '', d.text || '']);
		pushMdRows(lines, ['动象', '起→落', '逢空', '断语'], dongRows);
	}else{
		lines.push('四位无显著动象');
	}
	lines.push('');

	lines.push('[格局]');
	if(jinkouData && jinkouData.geju && jinkouData.geju.length){
		for(let i=0; i<jinkouData.geju.length; i++){
			lines.push(`${jinkouData.geju[i].name}：${jinkouData.geju[i].text || ''}`);
		}
	}else{
		lines.push('无');
	}
	lines.push('');

	lines.push('[四位生克]');
	if(jinkouData && jinkouData.relations && jinkouData.relations.length){
		// 四位生克 → GFM 表:主/关系/宾/断语(断语缺 → —)。
		const relRows = jinkouData.relations.map((r)=>[r.from, r.rel, r.to, r.text || '']);
		pushMdRows(lines, ['主', '关系', '宾', '断语'], relRows);
	}else{
		lines.push('无');
	}
	if(jinkouData && jinkouData.bihe && jinkouData.bihe.length){
		for(let i=0; i<jinkouData.bihe.length; i++){
			lines.push(jinkouData.bihe[i].text);
		}
	}
	lines.push('');

	lines.push('[应期]');
	if(jinkouData && jinkouData.yingQi){
		lines.push(`${jinkouData.yingQi.scope}：${jinkouData.yingQi.text}`);
		const yqm = jinkouData.yingQi.methods || [];
		for(let i=0; i<yqm.length; i++){
			lines.push(`${yqm[i].fa}（${yqm[i].when}）：${yqm[i].text}`);
		}
	}else{
		lines.push('无');
	}
	lines.push('');

	lines.push('[太岁月建]');
	if(jinkouData && jinkouData.nianYueRi && jinkouData.nianYueRi.length){
		// 太岁月建 → GFM 表:名/地支/入课/断语(未入课 → —)。
		const nyrRows = jinkouData.nianYueRi.map((it)=>[it.name, it.zhi, it.hit ? '入课' : '', it.text]);
		pushMdRows(lines, ['名', '地支', '入课', '断语'], nyrRows);
	}else{
		lines.push('无');
	}
	if(jinkouData && jinkouData.jishi && jinkouData.jishi.hit){
		lines.push(`忌时：${jinkouData.jishi.text}`);
	}
	lines.push('');

	lines.push('[地支关系]');
	if(jinkouData && jinkouData.branchRelations && jinkouData.branchRelations.length){
		for(let i=0; i<jinkouData.branchRelations.length; i++){
			const b = jinkouData.branchRelations[i];
			// 补关系说明句 b.desc(右栏渲染有快照无)。
			lines.push(`${b.aLabel}${b.a} ${b.type} ${b.bLabel}${b.b}${b.desc ? `：${b.desc}` : ''}`);
		}
	}else{
		lines.push('无');
	}
	lines.push('');

	lines.push('[相关神煞]');
	if(jinkouData && jinkouData.relevantShensha && jinkouData.relevantShensha.length){
		for(let i=0; i<jinkouData.relevantShensha.length; i++){
			const it = jinkouData.relevantShensha[i];
			lines.push(`${it.position}·${it.name}：${it.desc || ''}`);
		}
	}else{
		lines.push('无');
	}
	lines.push('');

	// 阴盘三层（仅盘式=阴盘时附段；阳盘不产此段 → 既有快照逐字零回归）。
	if(jinkouData && jinkouData.yinPan && jinkouData.yinPan.wangScore && jinkouData.yinPan.wangScore.length){
		const yp = jinkouData.yinPan;
		const qinBy = {};
		(yp.liuqin || []).forEach((it)=>{ qinBy[it.wei] = it.qin; });
		const shenBy = {};
		(yp.liushen || []).forEach((it)=>{ shenBy[it.wei] = it.name; });
		lines.push('[阴盘·六亲六神旺衰]');
		lines.push(`以日干 ${fmtValue(yp.self)}（${fmtValue(yp.selfElem)}）为我；${yp.scoreNote}`);
		lines.push('| 位 | 五行 | 六亲 | 六神 | 旺衰 | 分值 | 依据 |');
		lines.push('| --- | --- | --- | --- | --- | --- | --- |');
		yp.wangScore.forEach((s)=>{
			lines.push(`| ${s.wei} | ${fmtValue(s.elem)} | ${fmtValue(qinBy[s.wei])} | ${fmtValue(shenBy[s.wei])} | ${fmtValue(s.level)} | ${s.score > 0 ? `+${s.score}` : s.score} | ${s.detail.length ? s.detail.join('、') : '—'} |`);
		});
		lines.push('');
	}

	// 专题起式（仅左栏选定专题/测年月日/行年时附段；未选则整段不产 → 既有快照逐字零回归）。
	if(jinkouData && (jinkouData.topic || jinkouData.shiJian || jinkouData.xingNian)){
		lines.push('[专题起式]');
		const tp = jinkouData.topic;
		if(tp){
			lines.push(`专题：${fmtValue(tp.title)}——${fmtValue(tp.note)}`);
			if(tp.ready === false){
				lines.push(`待补：${fmtValue(tp.needText)}`);
			}else{
				if(tp.result){ lines.push(`结论：${tp.result}`); }
				if(tp.rows && tp.rows.length){
					lines.push('| 方位 | 将神 | 将名 | 将干 |');
					lines.push('| --- | --- | --- | --- |');
					tp.rows.forEach((r)=>{
						lines.push(`| ${r.fang} | ${fmtValue(r.jiangZi)} | ${fmtValue(r.jiangName)} | ${fmtValue(r.gan)} |`);
					});
				}
			}
		}
		const jue = jinkouData.topicJue;
		if(jue && jue.items && jue.items.length){
			lines.push(`断诀（${jue.kind}）：`);
			jue.items.forEach((it)=>{
				lines.push(`- ${it.wei}${it.zhi ? `·${it.zhi}` : ''}：${fmtValue(it.xiang)}`);
			});
			(jue.notes || []).forEach((n)=>{ lines.push(`- ${n}`); });
		}
		const sj = jinkouData.shiJian;
		if(sj){
			lines.push(`${sj.title}：月将加于 ${fmtValue(sj.addAt)}，数至 ${fmtValue(sj.diFen)}，得将神 ${fmtValue(sj.jiangZi)}（${fmtValue(sj.jiangName)}）；${sj.note}`);
		}
		const xn = jinkouData.xingNian;
		if(xn){
			lines.push(`金口诀行年（旬法）：${xn.gender}·${xn.age}岁 → 行年 ${xn.ganZhi}（${xn.zhi}）；生年 ${xn.birthGanZi} 属 ${xn.xunHead} 旬，一岁起 ${xn.startGanZi}。`);
			if(xn.ge){ lines.push(`- 灾福歌：${xn.ge}`); }
		}
		lines.push('');
	}

	// 四象所属图 / 四象五行图（右栏「用神」页有、快照此前全缺 → AI 看不到用户看的取象表）。
	if(jinkouData && jinkouData.sixiangShu && jinkouData.sixiangShu.length){
		lines.push('[四象所属]');
		lines.push(`| 位 | 干支 | ${JINKOU_SIXIANG_SHU_COLS.map((c)=>c.label).join(' | ')} |`);
		lines.push(`| --- | --- | ${JINKOU_SIXIANG_SHU_COLS.map(()=>'---').join(' | ')} |`);
		jinkouData.sixiangShu.forEach((r)=>{
			lines.push(`| ${r.label} | ${fmtValue(r.ganzhi)} | ${JINKOU_SIXIANG_SHU_COLS.map((c)=>fmtValue(r[c.key])).join(' | ')} |`);
		});
		lines.push('');
	}
	if(jinkouData && jinkouData.sixiangWuxing && jinkouData.sixiangWuxing.rows && jinkouData.sixiangWuxing.rows.length){
		const sw = jinkouData.sixiangWuxing;
		lines.push('[四象五行]');
		if(sw.mainElem){ lines.push(`主象：${fmtValue(sw.mainElem)}${sw.tianqiText ? `　${sw.tianqiText}` : ''}`); }
		lines.push(`| 位 | 五行 | ${JINKOU_SIXIANG_WUXING_COLS.map((c)=>c.label).join(' | ')} |`);
		lines.push(`| --- | --- | ${JINKOU_SIXIANG_WUXING_COLS.map(()=>'---').join(' | ')} |`);
		sw.rows.forEach((r)=>{
			lines.push(`| ${r.label}${r.kong ? '·空' : ''} | ${fmtValue(r.elem)} | ${JINKOU_SIXIANG_WUXING_COLS.map((c)=>fmtValue(r[c.key])).join(' | ')} |`);
		});
		lines.push('');
	}
	// 方位神煞（飞天五鬼 / 喜神）：右栏「神煞」页有。
	if(jinkouData && jinkouData.fangWeiShensha && jinkouData.fangWeiShensha.length){
		lines.push('[方位神煞]');
		jinkouData.fangWeiShensha.forEach((it)=>{
			lines.push(`${fmtValue(it.name)}：${fmtValue(it.fang)}${it.desc ? `——${it.desc}` : ''}`);
		});
		lines.push('');
	}
	// 合占扣题 + 课分内外：右栏「用神」页有。
	if(jinkouData && (jinkouData.hezhan || jinkouData.neiwai)){
		lines.push('[合占扣题与内外]');
		const hz = jinkouData.hezhan;
		if(hz){
			lines.push(`取用：${fmtValue(hz.usePosition)}　时段：${fmtValue(hz.timeLabel)}${hz.askLabel ? `　所问：${hz.askLabel}` : ''}`);
			// chain 是纯字符串数组（每条自带「取事：/时段：/取用：」前缀），不是对象。
			(hz.chain || []).forEach((c)=>{ if(`${c || ''}`.trim()){ lines.push(`- ${c}`); } });
		}
		const nw = jinkouData.neiwai;
		if(nw && nw.rows && nw.rows.length){
			lines.push(`课分内外：${nw.rows.map((r)=>`${r.side}·${r.label}${r.yong ? '(用)' : ''}=${fmtValue(r.content)}`).join('　')}`);
		}
		lines.push('');
	}
	// 二遁人元 / 次客法 / 移星换将：右栏「专题」页恒产出，AI 此前全看不到。
	if(jinkouData && (jinkouData.erDun || (jinkouData.cike && jinkouData.cike.length) || jinkouData.yiXing)){
		lines.push('[二遁与次客]');
		const ed = jinkouData.erDun;
		if(ed){
			lines.push(`二遁人元：原人元 ${fmtValue(ed.yuan)} → 二遁 ${fmtValue(ed.gan)}、三遁 ${fmtValue(ed.thirdGan)}；衣色 ${fmtValue(ed.se)}、住宅物象 ${fmtValue(ed.xiang)}。`);
		}
		(jinkouData.cike || []).forEach((c)=>{
			const extra = [
				c.guiName ? `次课贵神＝${c.guiName}` : '',
				c.altTimeZi ? `代时之支＝${c.altTimeZi.filter(Boolean).join('、')}` : '',
				c.altDayGan ? `换日干＝${c.altDayGan.filter(Boolean).join('、')}` : '',
				c.altDiFen ? `新地分＝${c.altDiFen}` : '',
				c.jiangZi ? `将神＝${c.jiangZi}` : '',
			].filter(Boolean).join('；');
			lines.push(`- ${fmtValue(c.method)}：${fmtValue(c.note)}${extra ? `（${extra}）` : ''}`);
		});
		const yx = jinkouData.yiXing;
		if(yx){ lines.push(`- 移星换将：${fmtValue(yx.note)}（前日干 ${fmtValue(yx.prevDayGan)}、后日干 ${fmtValue(yx.nextDayGan)}）`); }
		lines.push('');
	}

	lines.push('[贵神月将象意]');
	if(jinkouData && jinkouData.xiangyi){
		const gs = jinkouData.xiangyi.guishen;
		const yj = jinkouData.xiangyi.yuejiang;
		if(gs){ lines.push(`贵神·${gs.name}（${gs.shiti || ''}）：${gs.desc || ''}`); }
		if(yj){ lines.push(`将神·${yj.name}：${yj.desc || ''}`); }
		if(!gs && !yj){ lines.push('无'); }
	}else{
		lines.push('无');
	}
	lines.push('');

	lines.push('[分类用神]');
	if(jinkouData && jinkouData.categoryRules){
		const qc = jinkouData.categoryRules.filter((c)=>c.texts && c.texts.length);
		if(qc.length){
			for(let i=0; i<qc.length; i++){
				lines.push(`${qc[i].name}（用神：${qc[i].yongHint || ''}）`);
				for(let j=0; j<qc[i].texts.length; j++){
					lines.push(`- ${qc[i].texts[j]}`);
				}
			}
		}else{
			lines.push('细则完善中');
		}
	}else{
		lines.push('无');
	}
	lines.push('');

	lines.push('[行年]');
	if(runyear){
		lines.push(`行年干支：${fmtValue(runyear.year)}`);
		lines.push(`年龄：${fmtValue(runyear.age)}岁`);
		lines.push(`性别：${xingbie}`);
	}else{
		lines.push('无');
	}
	lines.push('');

	appendMapSection(lines, '旬日', liureng ? liureng.xun : null);
	appendMapSection(lines, '旺衰', liureng ? liureng.season : null);
	appendMapSection(lines, '基础神煞', liureng ? liureng.gods : null);
	appendMapSection(lines, '干煞', liureng ? liureng.godsGan : null);
	appendMapSection(lines, '月煞', liureng ? liureng.godsMonth : null);
	appendMapSection(lines, '支煞', liureng ? liureng.godsZi : null);
	appendMapSection(lines, '岁煞', liureng && liureng.godsYear ? liureng.godsYear.taisui1 : null);

	lines.push('[十二长生]');
	if(wuxing){
		// 十二长生 → GFM 表:阶段/地支。土之长生随流派(申/寅),故优先取引擎 phaseTable,
		// 缺省回落共用 wxphase(=默认水土同宫,既有快照逐字零回归)。
		const zsPhase = jinkouData && jinkouData.phaseTable ? jinkouData.phaseTable : null;
		const zsRows = ZSList.map((item)=>[item, fmtValue((zsPhase && zsPhase[item]) || ZhangSheng.wxphase[`${wuxing}_${item}`])]);
		pushMdRows(lines, ['阶段', '地支'], zsRows);
	}else{
		lines.push('无');
	}

	// A 类硬缺:分析 tab「数理 · 太玄数」(renderTaixuan)显示了却不入快照。
	// 取数与 UI 同源(jinkouData.taixuan,行文案同 renderTaixuan 的 value 拼法);无数据不产段。
	const jkTaixuan = jinkouData && jinkouData.taixuan && jinkouData.taixuan.length ? jinkouData.taixuan : [];
	if(jkTaixuan.length){
		lines.push('');
		lines.push('[数理]');
		for(let i=0; i<jkTaixuan.length; i++){
			const t = jkTaixuan[i];
			lines.push(`${t.label}：${t.tokens || '—'}　太玄数 ${t.num}`);
		}
	}
	return lines.join('\n').trim();
}

function mapObjToRows(obj){
	if(!obj || typeof obj !== 'object'){
		return [];
	}
	const keys = Object.keys(obj);
	const rows = [];
	for(let i=0; i<keys.length; i++){
		const key = keys[i];
		let value = obj[key];
		if(value instanceof Array){
			value = value.join('、');
		}
		rows.push({
			key: cleanKey(key),
			value: value === undefined || value === null || value === '' ? '—' : `${value}`,
		});
	}
	return rows;
}


// 本命属相 / 行年虚岁：单一真值源 = 问测人出生时间（不再手填，免两处输入打架）。
//   属相 = 生年干支之地支（runyear.birthGanZi 由 requestBirthYearGanZi 取回并留档）；
//   虚岁 = 卜卦年 − 生年 + 1（runyear.age 是年份差，0 即出生当年 → 虚岁 1）。
// 生年干支未取回时属相为空，专题引擎按「需填属相」提示而非乱算（缺参不臆造）。
export function deriveBenMingFromRunYear(runyear){
	const gz = runyear && runyear.birthGanZi ? `${runyear.birthGanZi}` : '';
	const zhi = gz.length >= 2 ? gz.charAt(1) : '';
	return LRConst.ZiList.indexOf(zhi) >= 0 ? zhi : '';
}
export function deriveXuSuiFromRunYear(runyear){
	const age = runyear && runyear.age !== undefined && runyear.age !== null ? Number(runyear.age) : NaN;
	return Number.isFinite(age) && age >= 0 ? age + 1 : '';
}
