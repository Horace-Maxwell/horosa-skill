// 对读引擎(马赛两两解读 TP2):十进对 · 和21互补对 · 配偶对 · 相邻度关系(进化/冲突/退行) · 视线互动。
// 纯函数,消费 reading.draws;数据依赖 degreeOf(度值)与 cardNotes.gaze(有则出提示,无则静默)。
import { degreeOf, marseilleNumber } from '../decks/marseilleMeanings.js';
import { isTrumpArcana } from './arcana.js'; // [QA-9] 王牌判据单一真值源(零依赖叶子)
import { noteOf } from '../decks/cardNotes.js';
import { CORE78 } from '../decks/core78.js';

// 对读体系按马赛编号运算(力量=XI/正义=VIII,经 marseilleNumber 换号;其余牌两派同号)——
// 十进对/和21 是该派原生框架,RWS 牌组上亦按此框架给对(couples 表与其自洽)。
const MAJORS = CORE78.filter((c) => c.arcana === 'major');
const byTdmNum = {};
MAJORS.forEach((c) => { byTdmNum[marseilleNumber(c)] = c; });
const majorByNum = (n) => byTdmNum[n] || null;

// 十进对:1..10 ↔ 11..20 同度两八度;0(愚人)↔21(世界) 为首尾特殊对。
export function decadePartner(card){
	// [QA-9] 认 *_trump:否则该两副的大牌对流恒空(段出得来、每行都是「—」)
	if(!card || !isTrumpArcana(card.arcana)){ return null; }
	const n = marseilleNumber(card);
	if(n === 0){ return { partner: majorByNum(21), kind: 'endless', note: '无限的起点与无限的终点互为一对' }; }
	if(n === 21){ return { partner: majorByNum(0), kind: 'endless', note: '无限的终点与无限的起点互为一对' }; }
	if(n >= 1 && n <= 10){ return { partner: majorByNum(n + 10), kind: 'octave', note: `同为第${n}度——此牌为「光明/社会」层,对牌为其「暗夜/内在」八度` }; }
	if(n >= 11 && n <= 20){ return { partner: majorByNum(n - 10), kind: 'octave', note: `同为第${n - 10}度——此牌为「暗夜/内在」层,对牌为其「光明/社会」八度` }; }
	return null;
}

// 和21互补对:n ↔ 21−n(每张大牌的「隐藏补牌」;愚人-世界与十进特殊对重合)。
export function sum21Partner(card){
	if(!card || !isTrumpArcana(card.arcana)){ return null; } // [QA-9] 同上
	const partner = majorByNum(21 - marseilleNumber(card));
	if(!partner){ return null; }
	return { partner, note: '两数相加为廿一——互为隐藏的补牌,一显则另一潜' };
}

// 配偶对(此派逐对论述的大牌对子;有据各对,原创转述一句)。键=排序后的 'sidA|sidB'。
export const MAJOR_COUPLES = {
	'the_fool|the_world': '起点与圆成:全部能量与全部实现,互为镜照。',
	'strength|the_magician': '初启之技与初醒之力:手艺遇上兽性能量,始能真正开工。',
	'high_priestess|the_hierophant': '内蓄之知与外传之教:一守圣所,一开讲席。',
	'the_emperor|the_empress': '创造之涌与承载之基:一个迸发,一个立骨架。',
	'the_chariot|the_star': '出征与安处:向外征旅,终在天地间找到自己的位置。',
	'the_hermit|justice': '独行之慧与持衡之断:内省供出证词,天平给出裁决。',
	'the_moon|the_sun': '母夜与父昼:接纳之满与辐射之热,轮转不息。',
};
export function coupleOf(a, b){
	if(!a || !b || !isTrumpArcana(a.arcana) || !isTrumpArcana(b.arcana)){ return null; }
	const key = [a.sid, b.sid].sort().join('|');
	return MAJOR_COUPLES[key] || null;
}

// 相邻度关系:两牌都有度值且相差 1 → 进化(低→高)/退行(高→低);同度=共振;偶奇相邻另注「承受↔行动」张力。
export function degreeRelation(a, b){
	const da = degreeOf(a);
	const db = degreeOf(b);
	if(da === null || db === null){ return null; }
	if(da === db){ return { kind: 'resonance', text: `同为第${da}度——彼此共振,该度主题被加倍强调` }; }
	if(db === da + 1){
		const tension = (da % 2 === 0) ? '(偶→奇:由承受转入行动)' : '';
		return { kind: 'evolve', text: `第${da}度→第${db}度:进化之序,顺流而上${tension}` };
	}
	if(da === db + 1){
		const tension = (db % 2 === 0) ? '(奇→偶:由行动退回承受)' : '';
		return { kind: 'regress', text: `第${da}度→第${db}度:回落之序——或休整蓄力,或退行受阻${tension}` };
	}
	return null;
}

// 视线互动:按牌面朝向(cardNotes.gaze,观者坐标)与两牌在阵中的左右相对位置给提示;无数据静默。
export function gazeInteraction(a, b){
	const ga = noteOf(a);
	const gb = noteOf(b);
	const gazeA = ga && ga.gaze;
	const gazeB = gb && gb.gaze;
	if(!gazeA && !gazeB){ return null; }
	const lines = [];
	if(gazeA === 'right'){ lines.push(`${a.name_cn}面向右侧的${b.name_cn}——向其注入能量`); }
	if(gazeA === 'left'){ lines.push(`${a.name_cn}背向${b.name_cn}——正离开其所代表的处境`); }
	if(gazeB === 'left'){ lines.push(`${b.name_cn}面向左侧的${a.name_cn}——回望并承接其能量`); }
	if(gazeB === 'right'){ lines.push(`${b.name_cn}望向更右——越过此对望向下一步`); }
	if(gazeA === 'front'){ lines.push(`${a.name_cn}直视观者——邀请自省,讯息指向问者本人`); }
	if(gazeB === 'front'){ lines.push(`${b.name_cn}直视观者——邀请自省,讯息指向问者本人`); }
	return lines.length ? lines.join('；') : null;
}

// 对读总装:阵中大牌的十进/和21/配偶命中(含「同阵相会」高亮)+ 相邻对的度关系 + 视线提示。
export function buildPairReading(draws){
	const list = (draws || []).filter((d) => d && d.card);
	if(!list.length){ return null; }
	const inSpread = new Set(list.map((d) => d.card.sid));
	// [QA-9] 认 *_trump:此前写死 'major',维斯康蒂(马赛系,对读正是其看家读法)大牌对读恒空
	const majors = list.filter((d) => isTrumpArcana(d.card.arcana));
	const majorLines = majors.map((d) => {
		const c = d.card;
		const dec = decadePartner(c);
		const s21 = sum21Partner(c);
		const parts = [];
		if(dec && dec.partner){
			const here = inSpread.has(dec.partner.sid) ? '(同阵相会!)' : '';
			parts.push(`十进对=${dec.partner.name_cn}${here}`);
		}
		if(s21 && s21.partner && (!dec || !dec.partner || s21.partner.sid !== dec.partner.sid)){
			const here = inSpread.has(s21.partner.sid) ? '(同阵相会!)' : '';
			parts.push(`和21补牌=${s21.partner.name_cn}${here}`);
		}
		return { sid: c.sid, name: c.name_cn, text: parts.join('；') || '—', decNote: dec ? dec.note : null };
	});
	const adjacent = [];
	for(let i = 0; i + 1 < list.length; i++){
		const a = list[i].card;
		const b = list[i + 1].card;
		const rel = degreeRelation(a, b);
		const couple = coupleOf(a, b);
		const gaze = gazeInteraction(a, b);
		if(rel || couple || gaze){
			adjacent.push({ a: a.name_cn, b: b.name_cn, relation: rel ? rel.text : null, couple, gaze });
		}
	}
	// 阵内任意两大牌的配偶命中(不限相邻)
	const couplesHit = [];
	for(let i = 0; i < majors.length; i++){
		for(let j = i + 1; j < majors.length; j++){
			const g = coupleOf(majors[i].card, majors[j].card);
			if(g){ couplesHit.push({ a: majors[i].card.name_cn, b: majors[j].card.name_cn, text: g }); }
		}
	}
	if(!majorLines.length && !adjacent.length && !couplesHit.length){ return null; }
	return { majors: majorLines, adjacent, couples: couplesHit };
}
