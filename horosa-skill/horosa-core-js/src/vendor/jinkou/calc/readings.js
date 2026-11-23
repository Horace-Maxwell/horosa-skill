// 断法层(上):生克关系、比和、年月日、动爻、地分取法、二遁、刺克、移星、时间、专题与专题诀
// 从 JinKouCalc.js 按职责拆出(门面保留原导入路径与对外导出;读源码的检查读「子模块 + 门面」全集,见 scripts/source-sets.json)。
import * as LRConst from '../../liureng/LRConst.js';
import { JINKOU_RELATION_DOC, JINKOU_BIHE_DOC, JINKOU_GUISHEN_XIANGYI, JINKOU_YUEJIANG_DOC, JINKOU_DONG_DOC, JINKOU_ZHAI_NEIJING, JINKOU_ZHAI_NOTES, JINKOU_DAJING_SHUIZHI, JINKOU_DAJING_NOTES, JINKOU_BANZHI_GAN, JINKOU_BANZHI_BUWEI, JINKOU_BANZHI_NOTES, JINKOU_GUIJIAN_JUE } from '../JinKouDoc.js';
import { JinKouWuXingSheng, JinKouWuXingKe, JinKouGuiShenSeq } from './tables.js';
import { shiftZi, rowZhi, getStemByWuZiDun, getJiangZiAtDiFen } from './basics.js';

// —— 解读层：五行生克 / 地支关系 / 四位生克 / 太玄数 / 用神强弱 / 应期 / 神煞判语 ——
export function wuxingRelation(a, b){
	if(!a || !b){ return ''; }
	if(a === b){ return '比和'; }
	if(JinKouWuXingSheng[a] === b){ return '生'; }
	if(JinKouWuXingSheng[b] === a){ return '被生'; }
	if(JinKouWuXingKe[a] === b){ return '克'; }
	if(JinKouWuXingKe[b] === a){ return '被克'; }
	return '';
}

export function branchRelTypes(a, b){
	if(!a || !b){ return []; }
	const res = [];
	const both = (map)=>map && (map[a] === b || map[b] === a);
	const bothArr = (map)=>map && ((map[a] && map[a].indexOf(b) >= 0) || (map[b] && map[b].indexOf(a) >= 0));
	if(both(LRConst.ZiCong)){ res.push('冲'); }
	if(both(LRConst.ZiHe)){ res.push('合'); }
	if(bothArr(LRConst.ZiSangHe)){ res.push('三合'); }
	if(both(LRConst.ZiHai)){ res.push('害'); }
	if(both(LRConst.ZiPo)){ res.push('破'); }
	if(both(LRConst.ZiXing)){ res.push('刑'); }
	return res;
}

export function buildJinKouRelations(rows){
	const byLabel = {};
	rows.forEach((r)=>{ byLabel[r.label] = r; });
	const pairs = [['贵神', '人元'], ['将神', '贵神'], ['地分', '将神'], ['地分', '人元'], ['地分', '贵神'], ['将神', '人元']];
	const out = [];
	pairs.forEach((pair)=>{
		const a = byLabel[pair[0]];
		const b = byLabel[pair[1]];
		if(!a || !b || !a.elem || !b.elem){ return; }
		const rel = wuxingRelation(a.elem, b.elem);
		if(!rel){ return; }
		const key = `${pair[0]}_${rel}_${pair[1]}`;
		const text = JINKOU_RELATION_DOC[key] || JINKOU_RELATION_DOC[`_${rel}_`] || '';
		out.push({ from: pair[0], to: pair[1], rel: rel, fromElem: a.elem, toElem: b.elem, text: text });
	});
	// 干元类（§10.3）：神干(贵神之遁干) ↔ 将干(将神之遁干)，先判天干五合（合局），否则按五行生克。
	const shenRow = byLabel['贵神'], jiangRow = byLabel['将神'];
	if(shenRow && jiangRow && shenRow.gan && jiangRow.gan && shenRow.gan !== '-' && jiangRow.gan !== '-' && shenRow.ganElem && jiangRow.ganElem){
		const rel = (LRConst.GanHe[shenRow.gan] === jiangRow.gan) ? '合' : wuxingRelation(shenRow.ganElem, jiangRow.ganElem);
		if(rel){
			const key = `神干_${rel}_将干`;
			const text = JINKOU_RELATION_DOC[key] || JINKOU_RELATION_DOC[`_${rel}_`] || '';
			out.push({ from: '神干', to: '将干', rel: rel, fromElem: shenRow.ganElem, toElem: jiangRow.ganElem, text: text });
		}
	}
	return out;
}

// 五比同类（§10.4）：四位两两五行同气定名；四位全同气优先取「合比」。
export function buildJinKouBihe(rows){
	const byLabel = {};
	rows.forEach((r)=>{ byLabel[r.label] = r; });
	const elemOf = (label)=>{ const r = byLabel[label]; return r && r.elem ? r.elem : ''; };
	const out = [];
	const elems = ['人元', '贵神', '将神', '地分'].map(elemOf);
	if(elems[0] && elems.every((e)=>e === elems[0])){
		out.push({ name: '合比', text: JINKOU_BIHE_DOC['合比'].text });
		return out;
	}
	['正比', '近比', '远比', '次比'].forEach((name)=>{
		const def = JINKOU_BIHE_DOC[name];
		const ea = elemOf(def.pair[0]);
		const eb = elemOf(def.pair[1]);
		if(ea && eb && ea === eb){
			out.push({ name: name, text: def.text });
		}
	});
	return out;
}

// 象意（§4.7/§4.8）：当前贵神(断事之性质) + 将神月将(断经过/媒介)的象意。
export function buildJinKouXiangyi(guiName, jiangName){
	const gs = guiName && JINKOU_GUISHEN_XIANGYI[guiName] ? Object.assign({ name: guiName }, JINKOU_GUISHEN_XIANGYI[guiName]) : null;
	const yj = jiangName && JINKOU_YUEJIANG_DOC[jiangName] ? { name: jiangName, desc: JINKOU_YUEJIANG_DOC[jiangName].desc } : null;
	return { guishen: gs, yuejiang: yj };
}

// 太岁月建系统（§9.9）：据年/月/日支算各项落支，命中四位者高亮。
const JINKOU_NIANYUERI_DEFS = [
	{ name: '岁君', text: '太岁所临，神将与之相生主当年迁进吉庆、受克主尊长灾困、仕人利见大人。' },
	{ name: '真太岁', text: '课中干支与太岁干支相同（伏吟），主君长领导宠用；临门户日辰年命之上，反主尊长有凶。', kind: 'ganzi' },
	{ name: '岁破', text: '太岁对冲，主道路音信、财物破散、家宅损耗、人事阻隔。' },
	{ name: '岁宅', text: '岁前五辰为宅神，主田宅争讼、家族兴衰；宅神受制则人口灾忧。' },
	{ name: '月建', text: '当月之支，旺则物盛数多、谋望有成、吉凶力壮、动则立应。' },
	{ name: '月破', text: '冲破月建，主器破忧散、病败财空、孕育不顺，反可解凶神。' },
	{ name: '月厌', text: '正戌逆行之位，主咒诅冤仇、厌恶不明之事，占病连绵。' },
	{ name: '日建', text: '将神与日辰相同，主一日之事：吉则先凶后吉、凶则先吉后凶。', kind: 'jiangDay' },
	{ name: '日冲', text: '课被日辰冲破，主器物破坏、望事难成、人情不和；旺相逢冲即发、休囚逢破则空。' },
];

// extras（可选）：{ yearGanZi, dayGanZi, jiangZi } —— 真太岁比对整柱干支、日建比对将神与日辰，
// 二者判据非「四位含某支」，故单列 kind 分支；不传 extras 时该两项自动跳过（旧调用零回归）。
export function buildJinKouNianYueRi(yearZi, monthZi, monthIdx, dayZi, fourBranches, extras){
	const four = fourBranches || [];
	const ex = extras || {};
	const zhiMap = {
		'岁君': yearZi || '',
		'岁破': yearZi ? shiftZi(yearZi, 6) : '',
		'岁宅': yearZi ? shiftZi(yearZi, 5) : '',
		'月建': monthZi || '',
		'月破': monthZi ? shiftZi(monthZi, 6) : '',
		'月厌': monthIdx > 0 ? shiftZi('戌', -(monthIdx - 1)) : '',
		'日冲': dayZi ? shiftZi(dayZi, 6) : '',
	};
	const out = [];
	JINKOU_NIANYUERI_DEFS.forEach((d)=>{
		if(d.kind === 'ganzi'){
			// 真太岁：四位所见干支柱与太岁整柱相同（贵神/将神带干支，故比对其干支串）。
			const cols = ex.fourGanZi || [];
			if(!ex.yearGanZi || !cols.length){ return; }
			const hit = cols.indexOf(ex.yearGanZi) >= 0;
			out.push({ name: d.name, zhi: ex.yearGanZi, hit: hit, text: d.text });
			return;
		}
		if(d.kind === 'jiangDay'){
			// 日建：将神与日辰同支即成（古法以将神落日辰为一日之主）。
			if(!ex.jiangZi || !dayZi){ return; }
			out.push({ name: d.name, zhi: dayZi, hit: ex.jiangZi === dayZi, text: d.text });
			return;
		}
		const zhi = zhiMap[d.name];
		if(!zhi){ return; }
		out.push({ name: d.name, zhi: zhi, hit: four.indexOf(zhi) >= 0, text: d.text });
	});
	return out;
}

// 断课避讳忌时（§10.7）：月三合局忌时(=局沐浴时) + 日干忌时；命中占时则准确率偏低。
const JINKOU_JISHI_BY_YUE = { '寅': '卯', '午': '卯', '戌': '卯', '亥': '子', '卯': '子', '未': '子', '申': '酉', '子': '酉', '辰': '酉', '巳': '午', '酉': '午', '丑': '午' };

const JINKOU_JISHI_BY_GAN = { '甲': '酉', '乙': '酉', '丙': '子', '丁': '子', '戊': '卯', '己': '卯', '庚': '午', '辛': '午', '壬': '未', '癸': '未' };

export function buildJinKouJishi(monthZi, dayGan, timeZi){
	const byYue = JINKOU_JISHI_BY_YUE[monthZi] || '';
	const byGan = JINKOU_JISHI_BY_GAN[dayGan] || '';
	const hit = !!(timeZi && (timeZi === byYue || timeZi === byGan));
	return { byYue: byYue, byGan: byGan, timeZi: timeZi || '', hit: hit, text: hit ? '当前占时为断课忌时，准确率偏低，宜另择时辰或多重印证。' : '' };
}

// 五动三动（§4.4/§10.1/§10.2）：以四位两两生克定门户。干=人元、神=贵神、将=将神、方=地分。
//   五动(克)：妻=干克方、官=神克干、贼=神克将、财=将克神、鬼=方克干。
//   三动(生·同)：父母=方生干、子孙=干生方、兄弟=干方同气。逢空(关键位地支落旬空)则减断。
export function buildJinKouDong(rows, xunKongBranches, yongLabel){
	const byLabel = {};
	rows.forEach((r)=>{ byLabel[r.label] = r; });
	const gan = byLabel['人元'], shen = byLabel['贵神'], jiang = byLabel['将神'], fang = byLabel['地分'];
	if(!gan || !shen || !jiang || !fang){ return { wu: [], san: [] }; }
	const kongSet = {};
	(xunKongBranches || []).forEach((z)=>{ kongSet[z] = true; });
	const zhiOf = (r)=>rowZhi(r);
	const isKong = (...rs)=>rs.some((r)=>{ const z = zhiOf(r); return z && kongSet[z]; });
	const mk = (type, fromR, toR)=>({
		type: type,
		from: fromR.label,
		to: toR.label,
		kong: isKong(fromR, toR),
		yong: yongLabel === fromR.label || yongLabel === toR.label,
		text: JINKOU_DONG_DOC[type] || '',
	});
	const rel = (a, b)=>wuxingRelation(a && a.elem, b && b.elem);
	const wu = [];
	if(rel(gan, fang) === '克'){ wu.push(mk('妻', gan, fang)); }
	if(rel(shen, gan) === '克'){ wu.push(mk('官', shen, gan)); }
	if(rel(shen, jiang) === '克'){ wu.push(mk('贼', shen, jiang)); }
	if(rel(jiang, shen) === '克'){ wu.push(mk('财', jiang, shen)); }
	if(rel(fang, gan) === '克'){ wu.push(mk('鬼', fang, gan)); }
	const san = [];
	if(rel(fang, gan) === '生'){ san.push(mk('父母', fang, gan)); }
	if(rel(gan, fang) === '生'){ san.push(mk('子孙', gan, fang)); }
	if(gan.elem && fang.elem && gan.elem === fang.elem){ san.push(mk('兄弟', gan, fang)); }
	return { wu: wu, san: san };
}

// ══ 专题起式引擎（定局法）：定地分辅助取法 / 二遁人元 / 次客法 / 测年月日 / 七专题 ══
// 起式法多只改「定地分」或「加临之位」，其余三位仍按常规法；本组统一产出 {rows-like 四位, 说明}。

// —— 定地分辅助取法 ——
// 取数法：报数/笔画 ÷12 取余（余 1 子…余 11 戌，整除取亥）。
export function jinKouZiByNumber(num){
	const n = Math.floor(Math.abs(Number(num) || 0));
	if(!n){ return ''; }
	const r = n % 12;
	return LRConst.ZiList[(r + 11) % 12];
}

// 颜色法：青绿木寅卯、赤红火巳午、黄土辰戌丑未、白金申酉、黑蓝水亥子（取该色首支）。
const JINKOU_COLOR_ZI = {
	'青': '寅', '绿': '卯', '碧': '寅', '红': '午', '赤': '巳', '朱': '午',
	'黄': '辰', '土黄': '丑', '白': '申', '金': '酉', '银': '酉',
	'黑': '亥', '蓝': '子', '灰': '戌',
};

export function jinKouZiByColor(color){
	const c = `${color || ''}`;
	const keys = Object.keys(JINKOU_COLOR_ZI);
	for(let i = 0; i < keys.length; i++){
		if(c.indexOf(keys[i]) >= 0){ return JINKOU_COLOR_ZI[keys[i]]; }
	}
	return '';
}

// 本命法：属相 → 地支。
const JINKOU_SHENGXIAO_ZI = { '鼠': '子', '牛': '丑', '虎': '寅', '兔': '卯', '龙': '辰', '蛇': '巳', '马': '午', '羊': '未', '猴': '申', '鸡': '酉', '狗': '戌', '猪': '亥' };

export function jinKouZiByShengXiao(name){
	const t = `${name || ''}`;
	const keys = Object.keys(JINKOU_SHENGXIAO_ZI);
	for(let i = 0; i < keys.length; i++){
		if(t.indexOf(keys[i]) >= 0){ return JINKOU_SHENGXIAO_ZI[keys[i]]; }
	}
	return LRConst.ZiList.indexOf(t) >= 0 ? t : '';
}

// 统一入口：按取法与输入求地分（翻书法＝页数/字数走取数法）。
export function resolveDiFenBySource(method, input){
	if(method === 'number' || method === 'stroke' || method === 'book'){ return jinKouZiByNumber(input); }
	if(method === 'color'){ return jinKouZiByColor(input); }
	if(method === 'shengxiao'){ return jinKouZiByShengXiao(input); }
	return LRConst.ZiList.indexOf(`${input || ''}`) >= 0 ? `${input}` : '';
}

// —— 二遁人元法：以原人元为新日干，五鼠遁到原地分即得；可再遁第三层 ——
const JINKOU_YIWU_SE = { '甲': '青', '乙': '蓝', '丙': '大红', '丁': '浅红', '戊': '素黄', '己': '紫·土黄', '庚': '太白', '辛': '葱白', '壬': '黑绿', '癸': '明绿' };

const JINKOU_ERDUN_XIANG = { '甲': '树木', '乙': '树木', '丙': '高岭', '丁': '高岭', '戊': '坟陇', '己': '坟陇', '庚': '斜道', '辛': '斜道', '壬': '沟渠水泽', '癸': '沟渠水泽' };

export function buildJinKouErDun(renYuanGan, diFen){
	if(!renYuanGan || !diFen){ return null; }
	const second = getStemByWuZiDun(renYuanGan, diFen);
	const third = second ? getStemByWuZiDun(second, diFen) : '';
	return {
		yuan: renYuanGan,
		gan: second,
		thirdGan: third,
		se: JINKOU_YIWU_SE[second] || '',
		xiang: JINKOU_ERDUN_XIANG[second] || '',
		note: '二遁人元＝以原人元为日干、五鼠遁至原地分之干；用于测衣色、住宅物象等细象。',
	};
}

// —— 次客法（同一时辰同一地分立多课）——
// 移神法：只换贵神，依十二贵神序逐课取；换将法：阳将后三前五、阴将前三后五（换将不换神）；
// 换日辰法：逐日换日干；用爻支合法：取用爻地支六合处作新地分；用爻干合法：用爻天干五合之支；
// 月将加日：以月将加日支（非时支）寻将神。
const JINKOU_ZHI_LIUHE = { '子': '丑', '丑': '子', '寅': '亥', '亥': '寅', '卯': '戌', '戌': '卯', '辰': '酉', '酉': '辰', '巳': '申', '申': '巳', '午': '未', '未': '午' };

const JINKOU_GAN_WUHE = { '甲': '己', '己': '甲', '乙': '庚', '庚': '乙', '丙': '辛', '辛': '丙', '丁': '壬', '壬': '丁', '戊': '癸', '癸': '戊' };

const JINKOU_GAN_LU = { '甲': '寅', '乙': '卯', '丙': '巳', '丁': '午', '戊': '巳', '己': '午', '庚': '申', '辛': '酉', '壬': '亥', '癸': '子' };

const JINKOU_YANG_ZI = ['子', '寅', '辰', '午', '申', '戌'];

export function buildJinKouCiKe(ctx){
	const { yuejiang, timeZi, diFen, dayGan, guiName, yongZhi, yongGan, dayZi } = ctx || {};
	const out = [];
	const push = (method, note, patch)=>{ out.push({ method: method, note: note, ...patch }); };
	// ① 移神法：贵神依序推次课（十二课一轮）
	if(guiName){
		const idx = JinKouGuiShenSeq.indexOf(guiName);
		if(idx >= 0){
			const next = JinKouGuiShenSeq[(idx + 1) % 12];
			push('移神法', '只换贵神、不换月将，十二贵神依序逐课取（一时辰一方位可立十二课）。', { guiName: next });
		}
	}
	// ② 换将法：阳将后三前五 / 阴将前三后五（换将不换神）
	if(yuejiang && timeZi){
		const isYang = JINKOU_YANG_ZI.indexOf(yuejiang) >= 0;
		const second = shiftZi(timeZi, isYang ? -3 : 3);
		const third = shiftZi(timeZi, isYang ? 5 : -5);
		push('换将法', `${isYang ? '阳将后三前五' : '阴将前三后五'}：另取代时之支再起将神，地分贵神不变。`, { altTimeZi: [second, third] });
	}
	// ③ 换日辰法：前一日/后一日之日干另起贵神
	if(dayGan){
		const gi = LRConst.GanList.indexOf(dayGan);
		if(gi >= 0){
			push('换日辰法', '地分月将不变，逐日换日干求贵神与人元（十课一轮）。', {
				altDayGan: [LRConst.GanList[(gi + 9) % 10], LRConst.GanList[(gi + 1) % 10]],
			});
		}
	}
	// ④ 用爻支合法：用爻地支之六合处为新地分
	if(yongZhi && JINKOU_ZHI_LIUHE[yongZhi]){
		push('用爻支合法', '取用爻地支之六合处作新地分再起一课。', { altDiFen: JINKOU_ZHI_LIUHE[yongZhi] });
	}
	// ⑤ 用爻干合法：用爻天干五合之干，取其禄支为新地分
	if(yongGan && JINKOU_GAN_WUHE[yongGan]){
		const heGan = JINKOU_GAN_WUHE[yongGan];
		push('用爻干合法', '取用爻天干五合之干，以其所临之支作新地分再起一课。', { heGan: heGan, altDiFen: JINKOU_GAN_LU[heGan] || '' });
	}
	// ⑥ 月将加日：以日支代时支寻将神（多用于测当日天气、出行、日内吉凶）
	if(dayZi && yuejiang && diFen){
		push('月将加日', '以月将加日支（非占时）寻将神，贵神人元法不变；多用于测当日吉凶。', {
			jiangZi: getJiangZiAtDiFen(yuejiang, dayZi, diFen).zi,
		});
	}
	return out;
}

// —— 移星换将：换星法（贵神改用邻日日干起）——
export function buildJinKouYiXing(dayGan){
	if(!dayGan){ return null; }
	const gi = LRConst.GanList.indexOf(dayGan);
	if(gi < 0){ return null; }
	return {
		prevDayGan: LRConst.GanList[(gi + 9) % 10],
		nextDayGan: LRConst.GanList[(gi + 1) % 10],
		note: '换星法：以前一日或后一日之日干另起贵神（其余三位不变），得参考式与原式互验；切忌主次不分。',
	};
}

// —— 测年 / 测月 / 测日三式：月将加在不同「时间支」上，再数到本相/地分 ——
// 测年＝月将加太岁宫、数到属相；测月＝月将加月支、数到属相；测日＝月将加属相、以日支为地分。
export function buildJinKouShiJian(kind, ctx){
	const { yuejiang, yearZi, monthZi, dayZi, benMing } = ctx || {};
	if(!yuejiang){ return null; }
	if(kind === 'year'){
		if(!yearZi || !benMing){ return null; }
		const j = getJiangZiAtDiFen(yuejiang, yearZi, benMing);
		return { kind: 'year', title: '测一年吉凶', addAt: yearZi, diFen: benMing, jiangZi: j.zi, jiangName: j.name, note: '月将加临太岁宫，数至本相（属相）看吉凶。' };
	}
	if(kind === 'month'){
		if(!monthZi || !benMing){ return null; }
		const j = getJiangZiAtDiFen(yuejiang, monthZi, benMing);
		return { kind: 'month', title: '测一月吉凶', addAt: monthZi, diFen: benMing, jiangZi: j.zi, jiangName: j.name, note: '月将加于月支，数至本位（属相）而断。' };
	}
	if(kind === 'day'){
		if(!dayZi || !benMing){ return null; }
		const j = getJiangZiAtDiFen(yuejiang, benMing, dayZi);
		return { kind: 'day', title: '测一日吉凶', addAt: benMing, diFen: dayZi, jiangZi: j.zi, jiangName: j.name, note: '月将加临本相之上，以当日日支为地分；星座克日则有凶来。' };
	}
	return null;
}

// —— 七专题起式（各只改定地分或加临之位）——
const JINKOU_TOPIC_DEFS = {
	yunyu: { title: '测孕育', need: ['benMing'], note: '太乙将（巳）加孕妇属相，数到地分得将神；将神阳支主男、阴支主女。' },
	xuntiangang: { title: '寻天罡·失物作案', need: [], note: '天罡（辰将）落于何地盘位，即以该位为新地分另起一式，新式用爻即作案人/盗者。' },
	jiazhai: { title: '测家宅', need: [], note: '取太岁（或本命）前五辰为宅神作地分另起宅课。' },
	guijian: { title: '测人贵贱', need: [], note: '取行年方位，月将加于人元所处，辨其旺相坐中而言，配十二贵神断贵贱。' },
	banzhi: { title: '测瘢痣', need: [], note: '人元二遁至命宫定部位，再起人元之干定痣色痕质。' },
	dajing: { title: '测打井', need: [], note: '写十二地支任抽一张作地分，常规起式；孟咸仲甘、四季泉少。' },
	fujiashi: { title: '复加时·十二方位', need: [], note: '月将复加于占时之上，沿十二方位各立一课，扫描宅院四周物象。' },
};

export function buildJinKouTopic(topicKey, ctx){
	const def = JINKOU_TOPIC_DEFS[topicKey];
	if(!def){ return null; }
	const { yuejiang, timeZi, diFen, yearZi, benMing, renYuanGan, dayGan } = ctx || {};
	const base = { key: topicKey, title: def.title, note: def.note };
	if(topicKey === 'yunyu'){
		if(!benMing){ return { ...base, ready: false, needText: '需填孕妇属相' }; }
		// 太乙巳将加孕妇属相 → 数到地分
		const j = getJiangZiAtDiFen('巳', benMing, diFen);
		const isYang = JINKOU_YANG_ZI.indexOf(j.zi) >= 0;
		return { ...base, ready: true, addAt: benMing, diFen: diFen, jiangZi: j.zi, jiangName: j.name, result: `将神${j.zi}（${j.name}）为${isYang ? '阳' : '阴'}支，主${isYang ? '男' : '女'}。` };
	}
	if(topicKey === 'xuntiangang'){
		if(!yuejiang || !timeZi){ return { ...base, ready: false, needText: '需月将与占时' }; }
		// 天罡辰将落地盘位：月将加时后，天盘辰落于地盘之支 = 辰 −(月将−时)
		const newDiFen = shiftZi('辰', -((LRConst.ZiList.indexOf(yuejiang) - LRConst.ZiList.indexOf(timeZi) + 12) % 12));
		return { ...base, ready: true, newDiFen: newDiFen, result: `天罡（辰将）落地盘${newDiFen}位，即以${newDiFen}为新地分另起一式，其用爻为作案人。` };
	}
	if(topicKey === 'jiazhai'){
		const anchor = yearZi || benMing;
		if(!anchor){ return { ...base, ready: false, needText: '需太岁或本命' }; }
		const zhaiZi = shiftZi(anchor, 5);
		return { ...base, ready: true, newDiFen: zhaiZi, result: `${anchor}前五辰为${zhaiZi}，以${zhaiZi}为宅神作地分起宅课。` };
	}
	if(topicKey === 'guijian'){
		if(!yuejiang || !renYuanGan){ return { ...base, ready: false, needText: '需月将与人元' }; }
		// 月将加于人元所临之支（人元居地分之上，故以地分为其处）
		const j = getJiangZiAtDiFen(yuejiang, diFen, diFen);
		return { ...base, ready: true, addAt: diFen, jiangZi: j.zi, jiangName: j.name, result: `月将加于人元所处（${diFen}），得${j.zi}（${j.name}），辨其旺相与所乘贵神断贵贱。` };
	}
	if(topicKey === 'banzhi'){
		if(!renYuanGan || !benMing){ return { ...base, ready: false, needText: '需人元与命宫（属相）' }; }
		const erdun = getStemByWuZiDun(renYuanGan, benMing);
		return { ...base, ready: true, erDunGan: erdun, result: `人元${renYuanGan}二遁至命宫${benMing}得${erdun}，以其部位与痕质定瘢痣所在。` };
	}
	if(topicKey === 'dajing'){
		return { ...base, ready: true, newDiFen: diFen, result: `以所抽之支（现取${diFen}）为地分常规起式，按孟仲季断水质。` };
	}
	if(topicKey === 'fujiashi'){
		if(!yuejiang || !timeZi){ return { ...base, ready: false, needText: '需月将与占时' }; }
		const list = LRConst.ZiList.map((zi)=>{
			const j = getJiangZiAtDiFen(yuejiang, timeZi, zi);
			return { fang: zi, jiangZi: j.zi, jiangName: j.name, gan: dayGan ? getStemByWuZiDun(dayGan, j.zi) : '' };
		});
		return { ...base, ready: true, rows: list, result: '沿十二方位各立一课，逐位读将神以断该方物象。' };
	}
	return { ...base, ready: false };
}

export const JINKOU_TOPIC_KEYS = Object.keys(JINKOU_TOPIC_DEFS);

// —— 专题断诀取数（数据在 JinKouDoc，此处只做「按当前课取值」）——
export function buildJinKouTopicJue(topicKey, ctx){
	const { diFen, jiangZi, guiName, erDunGan, rows } = ctx || {};
	if(topicKey === 'jiazhai' || topicKey === 'fujiashi'){
		const items = (rows || []).map((r)=>{
			const zhi = rowZhi(r);
			return zhi ? { wei: r.label, zhi: zhi, xiang: JINKOU_ZHAI_NEIJING[zhi] || '' } : null;
		}).filter(Boolean);
		return { kind: '宅内景', items: items, notes: JINKOU_ZHAI_NOTES };
	}
	if(topicKey === 'dajing'){
		const keys = Object.keys(JINKOU_DAJING_SHUIZHI);
		const hit = keys.find((k)=>JINKOU_DAJING_SHUIZHI[k].zhis.indexOf(diFen) >= 0);
		return {
			kind: '水质',
			items: hit ? [{ wei: '地分', zhi: diFen, xiang: JINKOU_DAJING_SHUIZHI[hit].text }] : [],
			notes: JINKOU_DAJING_NOTES,
		};
	}
	if(topicKey === 'banzhi'){
		const items = [];
		if(erDunGan){
			items.push({ wei: '二遁人元', zhi: erDunGan, xiang: JINKOU_BANZHI_GAN[erDunGan] || '' });
		}
		[diFen, jiangZi].filter(Boolean).forEach((z)=>{
			if(JINKOU_BANZHI_BUWEI[z]){ items.push({ wei: '所临之支', zhi: z, xiang: JINKOU_BANZHI_BUWEI[z] }); }
		});
		return { kind: '瘢痣部位', items: items, notes: JINKOU_BANZHI_NOTES };
	}
	if(topicKey === 'guijian'){
		return {
			kind: '贵贱',
			items: guiName ? [{ wei: '所乘贵神', zhi: guiName, xiang: JINKOU_GUIJIAN_JUE[guiName] || '' }] : [],
			notes: ['行年方位＋月将加人元处起式，按用爻所乘贵神断贵贱。'],
		};
	}
	return null;
}
