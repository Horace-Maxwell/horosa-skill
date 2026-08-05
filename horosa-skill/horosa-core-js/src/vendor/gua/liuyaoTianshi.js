// 六爻 · 占天时(晴雨)古法判法 —— 六家分列,不合成单一结论。
//
// 为什么"分列"而不是给一个答案:古籍自己就说清了这件事 ——
//   「总体来看:则是以卦之阴阳、爻之水火、六亲及六神之五行属性为论。**则其为法而套用,
//     则多有冲突之处,使人不知所从**。」
// 六家(孙膑歌诀 / 天玄赋 / 卜筮元龟 / 洞林秘诀 / 海底眼 / 归纳评注)各成体系,同一卦按不同家
// 可得相反结论。故本模块只做「按家列出各自命中的条目 + 该条的原文依据」,把取舍留给用神者。
//
// 🔴 有一家**故意不实现**:鬼谷辨爻法的爻位表。原书今注明写「原书排列鬼谷辨爻法时有错位,
//    查他本多有不合,其中内容有些明显也有错误……仅供参考」,且仓内该表是逐字碎片(行列对应
//    已丢失)。据此重建"某爻主某天气"必然是臆造 —— 宁缺。
//
// 通行法('fumu' 档,父母主雨 / 子孙主晴)不走本模块,保持原有行为不变(零回归)。
import { LIUCHONG, TIANGAN_HE, TIANGAN_HE_HUA, shengKe, wuxingOf } from './LiuYaoConst.js';

// 三位爻象(自下而上)→ 八卦。与 liuyaoGuFa 同表。
const TRIGRAM_BY_BITS = { 111: '乾', 110: '兑', 101: '离', 100: '震', 11: '巽', 10: '坎', 1: '艮', 0: '坤' };
function trigramOf(bits){ return TRIGRAM_BY_BITS[String(Number(bits.join('')))] || TRIGRAM_BY_BITS[bits.join('')] || ''; }
// 内外卦去重:同卦只报一次,标「内外皆X」;不同则分报「内卦X」「外卦Y」。
function trigramPairs(inner, outer){
	if(inner && outer && inner === outer){ return [[inner, '内外皆']]; }
	const out = [];
	if(inner){ out.push([inner, '内卦']); }
	if(outer){ out.push([outer, '外卦']); }
	return out;
}

// ── 海底眼 ──────────────────────────────────────────────────────────────
// 「水动雨兮土动阴,木动生风火动晴」「金爻发动雨将成」
const HDY_WUXING = { 水: '雨', 土: '阴晦', 木: '风', 火: '晴', 金: '雨将成' };
// 「天象阴晴父母推……子孙霞气并云彩,财动乍晴阴不定,弟动风雾露霜持,鬼兴霹雳神龙舞」
const HDY_LIUQIN = { 父母: '雨(时雨时晴)', 妻财: '云雨/乍晴阴不定', 子孙: '虹霞霁色', 兄弟: '风雾露霜', 官鬼: '雷霆霹雳、冰雹、闪电' };
// 「以卦象论:纯阳卦(乾)主晴,坎主雨,离主晴,震主雷电,巽主风,坤、兑、艮主阴」
const HDY_GUA = { 乾: '晴', 坎: '雨', 离: '晴', 震: '雷电', 巽: '风', 坤: '阴', 兑: '阴', 艮: '阴' };
// 「以天干论:甲乙主风,丙丁主晴,壬癸主雨」
const HDY_GAN = { 甲: '风', 乙: '风', 丙: '晴', 丁: '晴', 壬: '雨', 癸: '雨' };
// 「以地支论:亥子主雨,寅卯主风」
const HDY_ZHI = { 亥: '雨', 子: '雨', 寅: '风', 卯: '风' };
// 「甲己化土无雨,丁壬化木将晴,乙庚化金作雨,丙辛化水必雨,戊癸化火主晴」(内外卦纳干相合)。
// 天干相合与化什么五行是通用命理常量,直接用 LiuYaoConst 的 TIANGAN_HE / TIANGAN_HE_HUA,
// 本表只补「化某五行 → 某天气」这一层(这才是本篇独有的部分)。
const HDY_HUA_WEATHER = { 土: '无雨', 木: '将晴', 金: '作雨', 水: '必雨', 火: '主晴' };
// 「取独发论……变乾,日月星;变坤,沙石雾;变震,雷电雪;巽风、离晴、坎雨、艮阴云、兑雨霖霖」
const HDY_DUFA_BIAN = { 乾: '日月星朗', 坤: '飞沙走石、雾气', 震: '雷鸣闪电、雪', 巽: '风', 离: '晴', 坎: '雨', 艮: '阴云', 兑: '阴雨霖霖' };

// ── 天玄赋 ──────────────────────────────────────────────────────────────
// 「(六神)青龙临水动,甘雨即沾濡……」整段六条
const TXF_LIUSHEN = [
	{ god: '青龙', label: '临水动', cond: (x)=>x.wuxing === '水', out: '甘雨沾濡' },
	{ god: '青龙', label: '值木爻动', cond: (x)=>x.wuxing === '木', out: '阴云不舒' },
	{ god: '朱雀', label: '入火动', cond: (x)=>x.wuxing === '火', out: '必然启大明' },
	{ god: '朱雀', label: '飞入土爻发', cond: (x)=>x.wuxing === '土', out: '云中光射人' },
	{ god: '勾陈', label: '临土动', cond: (x)=>x.wuxing === '土', out: '阴雾接天涯' },
	{ god: '勾陈', label: '遇卯辰动', cond: (x)=>x.zhi === '卯' || x.zhi === '辰', out: '光中云渐开' },
	{ god: '螣蛇', label: '申酉动', cond: (x)=>x.zhi === '申' || x.zhi === '酉', out: '掣电走金蛇;纵无雨亦阴云遮日' },
	{ god: '白虎', label: '临木动', cond: (x)=>x.wuxing === '木', out: '须防折木风' },
	{ god: '玄武', label: '临水动', cond: (x)=>x.wuxing === '水', out: '连朝雨不休' },
];
// 「占雨:初旺浓云密布,无气淡烟薄雾;二旺飞电扬光……」/「占晴,初旺天虽晴云尚密……」
const TXF_POS_RAIN = ['浓云密布', '飞电扬光', '大风卷屋', '轰雷大震', '滂沱大雨', '必多雨水'];
const TXF_POS_RAIN_WEAK = ['淡烟薄雾', '云中虚闪', '布暖微风', '隐隐轻雷', '细雨沾濡', ''];
const TXF_POS_SUN = ['天虽晴云尚密', '草缀露珠', '朝霞散漫', '长虹截雨', '大明中照', '天浸冰壶'];
const TXF_POS_SUN_WEAK = ['薄云将散', '微施薄露', '日落霞明', '半扫浮云', '日色淡泊', ''];
// 「三冲六位,伫看掣电腾空;四克五爻,会见长虹贯日」及其注的爻位互动
const TXF_POS_PAIRS = [
	{ from: 3, to: 6, rel: '冲', out: '骤雨倾盆(掣电腾空)' },
	{ from: 4, to: 5, rel: '克', out: '长虹贯日' },
	{ from: 3, to: 1, rel: '克', out: '风卷残云散九霄' },
	{ from: 3, to: 1, rel: '生', out: '风送浓云六合包' },
	{ from: 2, to: 4, rel: '生', out: '电掣雷轰' },
	{ from: 1, to: 2, rel: '生', out: '云散雾收(转晴)' },
	{ from: 2, to: 1, rel: '克', out: '云散雾收(转晴)' },
	{ from: 5, to: 3, rel: '生', out: '日照霞明' },
];

// ── 卜筮元龟 ────────────────────────────────────────────────────────────
// 「坎为雨师巽为龙……坎入巽宫雨后风,坎之坤卦阴霾蒙;坤震往来雷电至,坤兑相资烟雾浓」
const YG_GUA_PAIR = [
	{ inner: '坎', outer: '巽', out: '先雨后风' },
	{ from: '坎', to: '坤', bian: true, out: '天气阴沉(阴霾蒙)' },
	{ any: ['坤', '震'], label: '坤震往来', out: '将有雷电' },
	// 「相资」与「往来」同联句同句式,沿用 any 判定器既有域 = 本卦+变卦四槽含齐两卦即成
	// (与上行「坤震往来」逐字同判;孙膑歌诀 kun_dui 只查本卦是另一书另一句,勿混)。
	// 🔴 曾写成 inner兑/outer坤 的有向判 —— 坤内兑外时恒不命中,与同句自相矛盾。
	{ any: ['坤', '兑'], label: '坤兑相资', out: '烟雾迷漫' },
];
// 「青龙属水定为雨,若是天阴属金土;入木之时雨便晴,寅动风生须白虎」
const YG_QINGLONG = { 水: '定为雨', 金: '天阴', 土: '天阴', 木: '雨便晴' };

// ── 洞林秘诀 ────────────────────────────────────────────────────────────
// 「远论晴时离作日,坎卦为雨旺须疾;乾象青天兑象云,坤艮平晴止雨毕。巽象为风震象雷」
const DL_GUA = { 离: '晴(为日)', 坎: '雨(旺则急)', 乾: '青天', 兑: '阴云', 坤: '雨止天晴', 艮: '雨止天晴', 巽: '风', 震: '雷' };

// ── 孙膑歌诀 ────────────────────────────────────────────────────────────
// 逐句都有原注,故可精确判。注号与原书括注对应。
const SB_RULES = [
	{ key: 'xuanwu_renkui', text: '玄武若居壬癸水,淋淋苦雨无休息', out: '淫雨霏霏不止' },
	{ key: 'kan_xun_move', text: '坎为雨师巽为龙,若逢发动雨蒙蒙', out: '阴雨迷蒙' },
	{ key: 'mushi_tushen', text: '木世土身主晴霁', out: '一定晴朗' },
	{ key: 'bing_ren', text: '丙壬相治掣金蛇(壬持世丙为应)', out: '一定见闪电' },
	{ key: 'geng_yi', text: '世庚应乙轰雷车', out: '雷声隆隆' },
	{ key: 'shi_fire', text: '世从火出乌轮灿', out: '阳光灿烂' },
	{ key: 'pure_yang', text: '纯阳定主多亢旱', out: '久晴天旱' },
	{ key: 'gen_to_kun', text: '艮若之坤即阴沉', out: '天阴沉沉' },
	{ key: 'ying_ke_ri', text: '应爻克日即收云', out: '即可收云' },
	{ key: 'li_in_wood', text: '离入木宫彩霞见', out: '云蒸霞蔚' },
	{ key: 'gui_xuanwu', text: '鬼临玄武雨已遍', out: '大部分地区有雨' },
	{ key: 'yang_to_yin', text: '阳化为阴雨又来', out: '雨又会来' },
	{ key: 'yin_to_yang', text: '阴入阳宫斗转魁', out: '星光灿烂' },
	{ key: 'haizi_xuanwu', text: '亥子爻中有玄武,四海尽沾天雨露', out: '雨露润泽' },
	{ key: 'li_gua', text: '离卦本是晴之原', out: '晴天的根源' },
	{ key: 'kun_gua', text: '坤是微阴薄润天', out: '天气微阴' },
	{ key: 'li_zhen', text: '离震往来雷电光', out: '雷电交加' },
	{ key: 'kun_dui', text: '坤兑相须烟雾寒', out: '主烟雾起' },
	{ key: 'water_rain', text: '大凡水爻终是雨', out: '终是雨' },
	{ key: 'fire_clear', text: '晴朗定向火爻起', out: '晴朗' },
];

function pushHit(list, rule, detail, tag){ list.push({ rule, detail, tag }); }

/**
 * 古法天时判法(六家分列)。
 * @param res analyzeLiuyao 已算出的中间结果:{ yaos, liuShen, gans, guaShen, palaceType, moves, gua, bianGua, ctx }
 * @returns { disclaimer, notImplemented, houses:[{source, hits:[{rule,detail,tag}]}] }
 */
export function analyzeTianshiAncient(res){
	if(!res || !Array.isArray(res.yaos) || !res.yaos.length){ return null; }
	const yaos = res.yaos;
	const moves = Array.isArray(res.moves) ? res.moves : [];
	const movingSet = new Set(moves);
	const gans = Array.isArray(res.gans) ? res.gans : [];
	const liuShen = Array.isArray(res.liuShen) ? res.liuShen : [];
	const godAt = (pos)=>{ const g = liuShen.find((x)=>x.pos === pos); return g ? g.liushen : ''; };
	const yaoAt = (pos)=>yaos.find((y)=>y.pos === pos) || null;
	const pt = res.palaceType || null;
	const shiYao = pt ? yaoAt(pt.shi) : null;
	const yingYao = pt ? yaoAt(pt.ying) : null;
	const val = res.gua && Array.isArray(res.gua.value) ? res.gua.value : null;
	const inner = val ? trigramOf(val.slice(0, 3)) : '';
	const outer = val ? trigramOf(val.slice(3, 6)) : '';
	const bVal = res.bianGua && Array.isArray(res.bianGua.value) ? res.bianGua.value : null;
	const bInner = bVal ? trigramOf(bVal.slice(0, 3)) : '';
	const bOuter = bVal ? trigramOf(bVal.slice(3, 6)) : '';
	const c = res.ctx || {};
	const hasWater = yaos.some((y)=>y.wuxing === '水');
	const hasFire = yaos.some((y)=>y.wuxing === '火');
	const movingYaos = yaos.filter((y)=>movingSet.has(y.pos));
	const pureYang = val ? val.every((v)=>v === 1) : false;
	const pureYin = val ? val.every((v)=>v === 0) : false;

	// ── 海底眼 ──
	const hdy = [];
	movingYaos.forEach((y)=>{
		if(HDY_WUXING[y.wuxing]){ pushHit(hdy, `${y.wuxing}爻动主${HDY_WUXING[y.wuxing]}`, `${y.pos}爻 ${y.zhi}${y.wuxing} 动`, HDY_WUXING[y.wuxing]); }
		if(HDY_LIUQIN[y.liuqin]){ pushHit(hdy, `${y.liuqin}动主${HDY_LIUQIN[y.liuqin]}`, `${y.pos}爻 ${y.liuqin} 动`, HDY_LIUQIN[y.liuqin]); }
		if(HDY_ZHI[y.zhi]){ pushHit(hdy, `${y.zhi}主${HDY_ZHI[y.zhi]}`, `${y.pos}爻 ${y.zhi} 动`, HDY_ZHI[y.zhi]); }
		const g = gans[y.pos - 1];
		if(g && HDY_GAN[g]){ pushHit(hdy, `${g}主${HDY_GAN[g]}`, `${y.pos}爻纳干 ${g}`, HDY_GAN[g]); }
	});
	if(!hasWater){ pushHit(hdy, '卦中无水必无雨', '六爻无水爻', '无雨'); }
	if(!hasFire){ pushHit(hdy, '六爻无火不光明', '六爻无火爻', '不开晴'); }
	// 内外同卦时只出一条(否则「坎为水」这类纯卦会把同一条规则报两遍)
	trigramPairs(inner, outer).forEach(([t, where])=>{ if(HDY_GUA[t]){ pushHit(hdy, `${t}主${HDY_GUA[t]}`, `${where} ${t}`, HDY_GUA[t]); } });
	// 天干化合:内外卦纳干相合 → 查化神五行 → 该篇给的天气
	const gIn = gans[0], gOut = gans[5];
	if(gIn && gOut && TIANGAN_HE[gIn] === gOut){
		const hua = TIANGAN_HE_HUA[gIn + gOut] || TIANGAN_HE_HUA[gOut + gIn] || '';
		const w = HDY_HUA_WEATHER[hua];
		if(w){ pushHit(hdy, `${gIn}${gOut}化${hua} → ${w}`, `内卦纳干 ${gIn} 与外卦纳干 ${gOut} 相合`, w); }
	}
	// 独发(只一爻动)取变卦外卦定体
	if(moves.length === 1 && bOuter && HDY_DUFA_BIAN[bOuter]){
		pushHit(hdy, `独发变${bOuter} → ${HDY_DUFA_BIAN[bOuter]}`, `仅 ${moves[0]} 爻独发,变卦外卦 ${bOuter}`, HDY_DUFA_BIAN[bOuter]);
	}

	// ── 天玄赋 ──
	const txf = [];
	if(!hasWater){ pushHit(txf, '六爻无水必无雨', '六爻无水爻', '无雨'); }
	if(!hasFire){ pushHit(txf, '六爻无火不开晴', '六爻无火爻', '不开晴'); }
	movingYaos.forEach((y)=>{
		const god = godAt(y.pos);
		TXF_LIUSHEN.forEach((r)=>{
			// rule 必须带上条件(「青龙动 → 阴云不舒」看不出是"临木爻"才成立,读者无法核对条文)
			if(r.god === god && r.cond(y)){ pushHit(txf, `${r.god}${r.label} → ${r.out}`, `${y.pos}爻 ${god}·${y.zhi}${y.wuxing} 动`, r.out); }
		});
		// 水火爻与世的生克(「水爻动来克世,骤雨忽然至;生世乃细雨」「火动克世必遭亢旱」)
		if(shiYao && y.pos !== shiYao.pos){
			const sk = shengKe(y.wuxing, shiYao.wuxing);
			if(y.wuxing === '水' && sk === '克'){ pushHit(txf, '水爻动来克世 → 骤雨忽至', `${y.pos}爻 ${y.zhi}水 动克世(${shiYao.zhi}${shiYao.wuxing})`, '骤雨'); }
			if(y.wuxing === '水' && sk === '生'){ pushHit(txf, '水爻动生世 → 细雨', `${y.pos}爻 ${y.zhi}水 动生世`, '细雨'); }
			if(y.wuxing === '火' && sk === '克'){ pushHit(txf, '火动克世 → 必遭亢旱', `${y.pos}爻 ${y.zhi}火 动克世`, '亢旱'); }
		}
		// 爻位旺衰档(旺相以「日月不伤且非空破」粗判 —— 原书用旺相休囚,此处只报档位与两种可能)
		const idx = y.pos - 1;
		const weak = !!(y.xunKong || y.yuePo);
		pushHit(txf, `占雨·${y.pos}爻${weak ? '无气' : '旺'} → ${weak ? (TXF_POS_RAIN_WEAK[idx] || '—') : TXF_POS_RAIN[idx]}`,
			`${y.pos}爻动${weak ? '(空/破,作无气)' : ''}`, weak ? TXF_POS_RAIN_WEAK[idx] : TXF_POS_RAIN[idx]);
		pushHit(txf, `占晴·${y.pos}爻${weak ? '无气' : '旺'} → ${weak ? (TXF_POS_SUN_WEAK[idx] || '—') : TXF_POS_SUN[idx]}`,
			`${y.pos}爻动${weak ? '(空/破,作无气)' : ''}`, weak ? TXF_POS_SUN_WEAK[idx] : TXF_POS_SUN[idx]);
	});
	// 世应=地天(苍屏云:世为地,应为天。应克世无雨,世克应大雨)
	if(shiYao && yingYao){
		const skYS = shengKe(yingYao.wuxing, shiYao.wuxing);
		if(skYS === '克'){ pushHit(txf, '应(天)克世(地) → 无雨', `应 ${yingYao.zhi}${yingYao.wuxing} 克世 ${shiYao.zhi}${shiYao.wuxing}`, '无雨'); }
		const skSY = shengKe(shiYao.wuxing, yingYao.wuxing);
		if(skSY === '克'){ pushHit(txf, '世(地)克应(天) → 大雨', `世 ${shiYao.zhi}${shiYao.wuxing} 克应 ${yingYao.zhi}${yingYao.wuxing}`, '大雨'); }
	}
	// 爻位互动(仅在两爻至少一动时判,「动则急」)
	TXF_POS_PAIRS.forEach((p)=>{
		const a = yaoAt(p.from), b = yaoAt(p.to);
		if(!a || !b || (!movingSet.has(a.pos) && !movingSet.has(b.pos))){ return; }
		let ok = false;
		if(p.rel === '冲'){ ok = LIUCHONG[a.zhi] === b.zhi; }
		else if(p.rel === '克'){ ok = shengKe(a.wuxing, b.wuxing) === '克'; }
		else if(p.rel === '生'){ ok = shengKe(a.wuxing, b.wuxing) === '生'; }
		if(ok){ pushHit(txf, `${p.from}爻${p.rel}${p.to}爻 → ${p.out}`, `${a.pos}爻 ${a.zhi}${a.wuxing} ${p.rel} ${b.pos}爻 ${b.zhi}${b.wuxing}`, p.out); }
	});
	if(pureYang){ pushHit(txf, '卦值纯阳 → 雨未可望', '六爻皆阳', '雨未可望'); }
	if(pureYin){ pushHit(txf, '纯阴卦静则有雨,动则生阳、雨未可望', `六爻皆阴,${moves.length ? '有动爻' : '静'}`, moves.length ? '雨未可望' : '有雨'); }

	// ── 卜筮元龟 ──
	const yg = [];
	if(shiYao && yingYao){
		// 「世贞为地……应悔为雨及为天;天克地兮天无雨,地克天兮寸霈然」
		if(shengKe(yingYao.wuxing, shiYao.wuxing) === '克'){ pushHit(yg, '天(应)克地(世) → 无雨', `应 ${yingYao.zhi}${yingYao.wuxing} 克世`, '无雨'); }
		if(shengKe(shiYao.wuxing, yingYao.wuxing) === '克'){ pushHit(yg, '地(世)克天(应) → 霈然有雨', `世 ${shiYao.zhi}${shiYao.wuxing} 克应`, '有雨'); }
	}
	YG_GUA_PAIR.forEach((r)=>{
		if(r.inner && r.outer){ if(inner === r.inner && outer === r.outer){ pushHit(yg, `${r.inner}(内)配${r.outer}(外) → ${r.out}`, `内 ${inner} 外 ${outer}`, r.out); } return; }
		if(r.bian){ if(inner === r.from || outer === r.from){ if(bInner === r.to || bOuter === r.to){ pushHit(yg, `${r.from}变${r.to} → ${r.out}`, `本卦含 ${r.from},变卦含 ${r.to}`, r.out); } } return; }
		if(r.any){ if(r.any.every((t)=>t === inner || t === outer || t === bInner || t === bOuter)){ pushHit(yg, `${r.label || (r.any.join('') + '往来')} → ${r.out}`, `本/变卦含 ${r.any.join('、')}`, r.out); } }
	});
	movingYaos.forEach((y)=>{
		const god = godAt(y.pos);
		if(god === '青龙' && YG_QINGLONG[y.wuxing]){ pushHit(yg, `青龙临${y.wuxing}爻动 → ${YG_QINGLONG[y.wuxing]}`, `${y.pos}爻 青龙·${y.zhi}${y.wuxing} 动`, YG_QINGLONG[y.wuxing]); }
		if(god === '白虎' && y.zhi === '寅'){ pushHit(yg, '寅木临白虎动 → 有风', `${y.pos}爻 白虎·寅 动`, '风'); }
		if(god === '玄武' && y.liuqin === '官鬼'){ pushHit(yg, '玄武临鬼爻动 → 有雨', `${y.pos}爻 玄武·官鬼 动`, '雨'); }
		if(god === '玄武'){
			const g = gans[y.pos - 1];
			if(g === '壬' || g === '癸'){ pushHit(yg, '玄武临壬癸动 → 连绵阴雨、雨涝', `${y.pos}爻 玄武·纳干 ${g}`, '涝'); }
			if(y.zhi === '亥' || y.zhi === '子'){ pushHit(yg, '玄武临亥子动 → 连绵阴雨甚至水灾', `${y.pos}爻 玄武·${y.zhi}`, '霖'); }
		}
		if(god === '勾陈' && ['辰', '戌', '丑', '未'].indexOf(y.zhi) >= 0){ pushHit(yg, '辰戌丑未勾陈发,土能克水 → 晴', `${y.pos}爻 勾陈·${y.zhi}土 动`, '晴'); }
	});
	if(pureYang){ pushHit(yg, '纯阳旺相 → 无雨,还忧亢旱', '六爻皆阳', '亢旱'); }

	// ── 洞林秘诀 ──
	const dl = [];
	movingYaos.forEach((y)=>{
		if(y.wuxing === '水'){ pushHit(dl, '水爻表示雨', `${y.pos}爻 ${y.zhi}水 动`, '雨'); }
		if(y.wuxing === '火'){ pushHit(dl, '火爻表示晴', `${y.pos}爻 ${y.zhi}火 动`, '晴'); }
		const god = godAt(y.pos);
		if(god === '朱雀' && y.wuxing === '火'){ pushHit(dl, '朱雀属火,旺相有气与火爻同推', `${y.pos}爻 朱雀·火 动`, '晴'); }
		if(god === '玄武' && y.wuxing === '水'){ pushHit(dl, '玄武属水,临水爻动主雨', `${y.pos}爻 玄武·水 动`, '雨'); }
	});
	trigramPairs(inner, outer).forEach(([t, where])=>{ if(DL_GUA[t]){ pushHit(dl, `${t} → ${DL_GUA[t]}`, `${where} ${t}`, DL_GUA[t]); } });
	if((inner === '坎' || outer === '坎') && moves.length){ pushHit(dl, '坎卦动时中雹子', `含坎卦且有动爻`, '冰雹'); }

	// ── 孙膑歌诀 ──
	const sb = [];
	const rule = (key)=>SB_RULES.find((r)=>r.key === key);
	const sbHit = (key, detail)=>{ const r = rule(key); if(r){ pushHit(sb, r.text, detail, r.out); } };
	movingYaos.forEach((y)=>{
		const god = godAt(y.pos);
		const g = gans[y.pos - 1];
		if(god === '玄武' && (g === '壬' || g === '癸') && y.wuxing === '水'){ sbHit('xuanwu_renkui', `${y.pos}爻 玄武·${g}${y.zhi}水`); }
		if(god === '玄武' && (y.zhi === '亥' || y.zhi === '子')){ sbHit('haizi_xuanwu', `${y.pos}爻 玄武·${y.zhi}`); }
		if(god === '玄武' && y.liuqin === '官鬼'){ sbHit('gui_xuanwu', `${y.pos}爻 玄武·官鬼`); }
		if(y.wuxing === '水'){ sbHit('water_rain', `${y.pos}爻 ${y.zhi}水 动`); }
		if(y.wuxing === '火'){ sbHit('fire_clear', `${y.pos}爻 ${y.zhi}火 动`); }
	});
	if((inner === '坎' || outer === '坎' || inner === '巽' || outer === '巽') && moves.length){ sbHit('kan_xun_move', `含坎/巽卦且有动爻`); }
	// 「木世土身主晴霁」:世爻属木 + 卦身属土。
	// 注:guaShenOf 返回 { body, holders, onChart } —— body 是**地支字符**,无 wuxing 字段,
	// 故五行须自己经 wuxingOf(body) 取(此处曾按 .wuxing 写错,实证字段形状后修正)。
	const shenZhi = res.guaShen && res.guaShen.body ? res.guaShen.body : '';
	if(shiYao && shiYao.wuxing === '木' && shenZhi && wuxingOf(shenZhi) === '土'){
		sbHit('mushi_tushen', `世 ${shiYao.zhi}木、卦身 ${shenZhi}土`);
	}
	// 「丙壬相治掣金蛇」:壬持世、丙为应
	if(shiYao && yingYao){
		const gs = gans[shiYao.pos - 1], gy = gans[yingYao.pos - 1];
		if(gs === '壬' && gy === '丙'){ sbHit('bing_ren', `世纳壬、应纳丙`); }
		if(gs === '庚' && gy === '乙'){ sbHit('geng_yi', `世纳庚、应纳乙`); }
	}
	if(shiYao && shiYao.wuxing === '火'){ sbHit('shi_fire', `世 ${shiYao.zhi}火`); }
	if(pureYang){ sbHit('pure_yang', '六爻皆阳'); }
	if((inner === '艮' || outer === '艮') && (bInner === '坤' || bOuter === '坤')){ sbHit('gen_to_kun', '本卦含艮、变卦含坤'); }
	if(yingYao && c.dayZhi){
		// 🔴 日辰五行直查支表:纳甲六爻的六支同奇偶,日支落另一半时在卦内根本找不到
		// (曾写 yaos.find(zhi===dayZhi) → 半数日子 dayEl=undefined,整条判据静默失效)。
		const dayEl = wuxingOf(c.dayZhi);
		if(dayEl && shengKe(yingYao.wuxing, dayEl) === '克'){ sbHit('ying_ke_ri', `应 ${yingYao.zhi}${yingYao.wuxing} 克日辰 ${c.dayZhi}`); }
	}
	if((inner === '离' || outer === '离') && [inner, outer, bInner, bOuter].some((t)=>t === '震' || t === '巽')){ sbHit('li_in_wood', '离入震/巽(木)宫'); }
	if(inner === '离' || outer === '离'){ sbHit('li_gua', `含离卦`); }
	if(inner === '坤' || outer === '坤'){ sbHit('kun_gua', `含坤卦`); }
	// 「往来」双向对称(主↔变任一方向;曾只判本离→变震单向)
	if(([inner, outer].indexOf('离') >= 0 && [bInner, bOuter].indexOf('震') >= 0)
		|| ([inner, outer].indexOf('震') >= 0 && [bInner, bOuter].indexOf('离') >= 0)){ sbHit('li_zhen', '离震往来'); }
	if([inner, outer].sort().join('') === ['坤', '兑'].sort().join('')){ sbHit('kun_dui', '坤兑相须'); }
	// 阴阳互化(主卦↔之卦阴阳)
	if(bVal){
		const yangCount = val.filter((v)=>v === 1).length, bYang = bVal.filter((v)=>v === 1).length;
		if(yangCount > 3 && bYang <= 3){ sbHit('yang_to_yin', '阳卦化阴卦'); }
		if(yangCount <= 3 && bYang > 3){ sbHit('yin_to_yang', '阴卦化阳宫'); }
	}

	const houses = [
		{ source: '孙膑歌诀', hits: sb },
		{ source: '天玄赋', hits: txf },
		{ source: '卜筮元龟', hits: yg },
		{ source: '洞林秘诀', hits: dl },
		{ source: '海底眼', hits: hdy },
	].filter((h)=>h.hits.length);

	return {
		houses,
		disclaimer: '古法各家自成体系、彼此多有冲突,古籍亦自称「其为法而套用,则多有冲突之处,使人不知所从」。此处按家分列各自命中的条目与依据,不合成单一结论,取舍由用神者定。',
		notImplemented: [{
			source: '鬼谷辨爻法(爻位表)',
			why: '原书今注明载此表排列有错位、与他本多有不合、内容亦有错误,仅供参考;据其重建逐爻主应会失真,故不实现。',
		}],
	};
}

export default analyzeTianshiAncient;
