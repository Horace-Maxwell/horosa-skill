// 六爻古法体系引擎(断易天机系):月建六神/直符四直/升降/十六变/卦生/过去未来/三限/八节卦气/世身/纳音/逐爻天干。
// 纯函数、确定性;全部输出为「结构真值+原文断义标签」,吉凶解读交 AI。起例逐字忠于《断易天机》(校注中性称「今注」)。
import { littleEndian } from './guaHelper.js';
import { getGua64 } from './GuaConst.js';
import { DIZHI, TIANGAN, ZHI_WUXING, WUXING_SHENG, LIUCHONG } from './LiuYaoConst.js';
import { parseYaoName, palaceTypeOf, guaShenOf } from './LiuYaoEngine.js';

const ZI = DIZHI; // ['子'..'亥']
const zi = (i) => ZI[((i % 12) + 12) % 12];
const ziIdx = (z) => ZI.indexOf(z);

// ── 逐爻天干(纳甲干):内卦三爻用下卦干、外卦三爻用上卦干;乾甲壬、坤乙癸,余六卦内外同干 ──
const NAJIA_GAN = { 乾: ['甲', '壬'], 坤: ['乙', '癸'], 震: ['庚', '庚'], 巽: ['辛', '辛'], 坎: ['戊', '戊'], 离: ['己', '己'], 艮: ['丙', '丙'], 兑: ['丁', '丁'] };
const TRIGRAM_BY_BITS = { '111': '乾', '110': '兑', '101': '离', '100': '震', '011': '巽', '010': '坎', '001': '艮', '000': '坤' };
export function ganForYaos(gua){
	if(!gua || !gua.value){ return null; }
	const lower = TRIGRAM_BY_BITS[gua.value.slice(0, 3).join('')];
	const upper = TRIGRAM_BY_BITS[gua.value.slice(3, 6).join('')];
	if(!lower || !upper){ return null; }
	const gi = NAJIA_GAN[lower][0], go = NAJIA_GAN[upper][1];
	return [gi, gi, gi, go, go, go];
}

// ── 六十甲子序号 + 纳音(三十律) ──
export function jiaziIndex(gan, zhiC){
	const g = TIANGAN.indexOf(gan), z = ziIdx(zhiC);
	if(g < 0 || z < 0){ return -1; }
	for(let n = 0; n < 60; n++){ if(n % 10 === g && n % 12 === z){ return n; } }
	return -1;
}
export const NAYIN_LIST = ['海中金', '炉中火', '大林木', '路旁土', '剑锋金', '山头火', '涧下水', '城头土', '白蜡金', '杨柳木',
	'泉中水', '屋上土', '霹雳火', '松柏木', '长流水', '沙中金', '山下火', '平地木', '壁上土', '金箔金',
	'覆灯火', '天河水', '大驿土', '钗钏金', '桑柘木', '大溪水', '沙中土', '天上火', '石榴木', '大海水'];
export function nayinOf(gan, zhiC){
	const n = jiaziIndex(gan, zhiC);
	if(n < 0){ return null; }
	const name = NAYIN_LIST[Math.floor(n / 2)];
	return { name, wuxing: name.substr(name.length - 1, 1) };
}

// ── 世身(两套起例,区别于月卦身):以世爻地支定「身」在第几爻 ──
// standard(《断易天机》定卦身):子午持世身居初、丑未二、寅申三、卯酉四、辰戌五、巳亥六
// lichunfeng(李淳风法):亥子持世身居初、丑戌二、寅申三、卯酉四、辰未五、巳午六
const SHISHEN_STD = { 子: 1, 午: 1, 丑: 2, 未: 2, 寅: 3, 申: 3, 卯: 4, 酉: 4, 辰: 5, 戌: 5, 巳: 6, 亥: 6 };
const SHISHEN_LCF = { 亥: 1, 子: 1, 丑: 2, 戌: 2, 寅: 3, 申: 3, 卯: 4, 酉: 4, 辰: 5, 未: 5, 巳: 6, 午: 6 };
export function shiShenOf(gua, mode){
	if(!mode || mode === 'off'){ return null; }
	const pt = palaceTypeOf(gua);
	if(!pt){ return null; }
	const shiZhi = parseYaoName((gua.yaoname && gua.yaoname[pt.shi - 1]) || '').zhi;
	const map = mode === 'lichunfeng' ? SHISHEN_LCF : SHISHEN_STD;
	const pos = map[shiZhi];
	if(!pos){ return null; }
	const at = parseYaoName((gua.yaoname && gua.yaoname[pos - 1]) || '');
	return { mode, shiZhi, pos, zhi: at.zhi, wuxing: at.wuxing, liuqin: at.liuqin };
}

// ── 月建六神(每月六神所在定局):青龙正月寅顺、朱雀巳顺、勾陈丑顺、白虎申顺、玄武亥顺;螣蛇正月辰逆 ──
const YUE_LIUSHEN_START = { 青龙: 2, 朱雀: 5, 勾陈: 1, 白虎: 8, 玄武: 11 }; // 支序号(正月),顺行
export function yueLiuShen(monthNum){ // monthNum: 1-12(正月=1,寅月)
	if(!monthNum || monthNum < 1 || monthNum > 12){ return null; }
	const m = monthNum - 1;
	const out = {};
	Object.keys(YUE_LIUSHEN_START).forEach((k) => { out[k] = zi(YUE_LIUSHEN_START[k] + m); });
	out['螣蛇'] = zi(4 - m); // 正月辰逆行
	return out; // {六神名→本月所值地支}
}
export function yueLiuShenOnYaos(yaos, monthNum){
	const map = yueLiuShen(monthNum);
	if(!map){ return null; }
	return { map, perYao: (yaos || []).map((y) => ({ pos: y.pos, hits: Object.keys(map).filter((k) => map[k] === y.zhi) })) };
}

// ── 直符四建(年建天符、月建直符、日建传符、时建时符——原文「时建直符」,今注取「时符」以别于月) ──
export function zhiFuOf(yaos, ctx){
	const c = ctx || {};
	const defs = [
		{ name: '天符', zhi: c.yearZhi, jian: '年建' },
		{ name: '直符', zhi: c.monthZhi, jian: '月建' },
		{ name: '传符', zhi: c.dayZhi, jian: '日建' },
		{ name: '时符', zhi: c.hourZhi, jian: '时建' },
	].filter((d) => d.zhi);
	const perFu = defs.map((d) => ({
		...d,
		wuxing: ZHI_WUXING[d.zhi] || '',
		yaoPos: (yaos || []).filter((y) => y.zhi === d.zhi).map((y) => y.pos),
	}));
	// 四直章:卦中全无四直之爻 →「所为先聚后相抛」
	const noneOn = perFu.length > 0 && perFu.every((d) => d.yaoPos.length === 0);
	return { perFu, noneOn };
}

// ── 升降章(12 中气→升/降爻位;阳升冬至起、阴降对宫) ──
// 冬至升阳初/降阴上;大寒2/5;雨水3/4;春分4/3;谷雨5/2;小满6/1;夏至升阴初/降阳上;大暑2/5;处暑3/4;秋分4/3;霜降5/2;小雪6/1
const SHENGJIANG = {
	冬至: { up: '阳', upPos: 1, downPos: 6 }, 大寒: { up: '阳', upPos: 2, downPos: 5 }, 雨水: { up: '阳', upPos: 3, downPos: 4 },
	春分: { up: '阳', upPos: 4, downPos: 3 }, 谷雨: { up: '阳', upPos: 5, downPos: 2 }, 小满: { up: '阳', upPos: 6, downPos: 1 },
	夏至: { up: '阴', upPos: 1, downPos: 6 }, 大暑: { up: '阴', upPos: 2, downPos: 5 }, 处暑: { up: '阴', upPos: 3, downPos: 4 },
	秋分: { up: '阴', upPos: 4, downPos: 3 }, 霜降: { up: '阴', upPos: 5, downPos: 2 }, 小雪: { up: '阴', upPos: 6, downPos: 1 },
};
export const SHENGJIANG_ZHONGQI = Object.keys(SHENGJIANG);
export function shengJiangOf(gua, zhongqi, movingSet, shiPos){
	const def = SHENGJIANG[zhongqi];
	if(!def || !gua || !gua.value){ return null; }
	const upYin = def.up === '阴';
	const upYao = { pos: def.upPos, name: (upYin ? '升阴' : '升阳'), zhi: parseYaoName((gua.yaoname || [])[def.upPos - 1] || '').zhi };
	const downYao = { pos: def.downPos, name: (upYin ? '降阳' : '降阴'), zhi: parseYaoName((gua.yaoname || [])[def.downPos - 1] || '').zhi };
	// 得度:升阳爻逢阳爻(或世为阳)主进益;阴阳反度主退损
	const upMatch = (gua.value[def.upPos - 1] === (upYin ? 0 : 1));
	const shiMatch = shiPos ? (gua.value[shiPos - 1] === (upYin ? 0 : 1)) : null;
	// 动爻克升爻 → 应在升爻地支之月主凶(原文「至月须当哭泣凶」)
	const moving = movingSet || new Set();
	const upWx = ZHI_WUXING[upYao.zhi];
	let keSheng = null;
	(gua.yaoname || []).forEach((nm, i) => {
		if(!moving.has(i + 1) || i + 1 === upYao.pos){ return; }
		const wx = parseYaoName(nm || '').wuxing;
		if(wx && upWx && ({ 木: '土', 土: '水', 水: '火', 火: '金', 金: '木' })[wx] === upWx){ keSheng = { fromPos: i + 1, atZhi: upYao.zhi }; }
	});
	return { zhongqi, upYao, downYao, upMatch, shiMatch, keSheng, fanDu: !upMatch };
}

// ── 京房十六变:自初至五(一世..五世)→下飞四(游魂)三(外戒)二(内戒)初(归魂)→上飞二(绝命)三(血脉)四(肌肉)五(骸骨)→下飞四(棺椁)三(坟墓)二(还本体) ──
const SIXTEEN_OPS = [1, 2, 3, 4, 5, 4, 3, 2, 1, 2, 3, 4, 5, 4, 3, 2];
const SIXTEEN_NAMES = ['一世', '二世', '三世', '四世', '五世', '游魂', '外戒', '内戒', '归魂', '绝命', '血脉', '肌肉', '骸骨', '棺椁', '坟墓', '还本体'];
export const SIXTEEN_DUAN = {
	外戒: '吉凶从外来', 内戒: '祸福从内起', 血脉: '主血疾漏下', 肌肉: '多梦、精神恍惚',
	骸骨: '主瘦瘠、病者难安', 棺椁: '占病凶', 绝命: '事多反覆、孤独', 游魂: '精神恍惚、行人未归',
	归魂: '事归、可成', 坟墓: '事归美、可成', 还本体: '还归本宫,灾福应本宫', 一世: '', 二世: '', 三世: '', 四世: '', 五世: '',
};
export function sixteenChangesOf(pureGua){
	if(!pureGua || !pureGua.value){ return null; }
	const seq = [];
	const v = pureGua.value.slice();
	for(let i = 0; i < 16; i++){
		const p = SIXTEEN_OPS[i];
		v[p - 1] = v[p - 1] ? 0 : 1;
		const g = getGua64(littleEndian(v));
		seq.push({ step: i + 1, flip: p, name: g ? g.name : '', vname: SIXTEEN_NAMES[i], duan: SIXTEEN_DUAN[SIXTEEN_NAMES[i]] || '' });
	}
	return seq;
}
export function sixteenPositionOf(gua, pureGua){
	const seq = sixteenChangesOf(pureGua);
	if(!seq || !gua){ return null; }
	const hit = seq.find((s) => s.name === gua.name);
	return hit || null;
}

// ── 卦生章:月卦身之支五行所生之五行,卦中该五行之爻=卦生爻;配所临六神断来意 ──
export function guaShengOf(gua, yaos, liuShen){
	const gs = guaShenOf(gua);
	if(!gs || !gs.body){ return null; }
	const bodyWx = ZHI_WUXING[gs.body];
	const target = WUXING_SHENG[bodyWx]; // 卦身所生五行
	const hits = (yaos || []).filter((y) => y.wuxing === target).map((y) => ({
		pos: y.pos, zhi: y.zhi, liuqin: y.liuqin,
		liushen: liuShen && liuShen[y.pos - 1] ? liuShen[y.pos - 1].liushen : '',
	}));
	return { body: gs.body, bodyWx, target, hits };
}

// ── 过去未来章:以月卦身临爻为准,位在其上言未来、位在其下言过去 ──
export function pastFutureOf(gua, yaos){
	const gs = guaShenOf(gua);
	if(!gs || !gs.onChart || !gs.holders.length){ return null; }
	const anchor = gs.holders[0];
	return {
		anchor,
		perYao: (yaos || []).map((y) => ({ pos: y.pos, phase: y.pos === anchor ? '当位' : (y.pos > anchor ? '未来' : '过去') })),
	};
}

// ── 三限荣枯(之卦断前后十五年):内三爻管一至十五年(每爻五年)、外三爻管十六至三十年;
// 之卦内三爻主财、外三爻主生死;流年自世上起一年一位,阳世顺数、阴世逆数 ──
export function sanXianOf(gua, bianGua, movingSet){
	const pt = palaceTypeOf(gua);
	if(!gua || !pt){ return null; }
	const seg = [];
	for(let i = 0; i < 6; i++){
		const p = parseYaoName((gua.yaoname || [])[i] || '');
		seg.push({
			pos: i + 1, zhi: p.zhi, wuxing: p.wuxing, liuqin: p.liuqin,
			years: `${i * 5 + 1}-${i * 5 + 5}`, side: i < 3 ? '内(1-15年)' : '外(16-30年)',
			moving: movingSet ? movingSet.has(i + 1) : false,
		});
	}
	let bianSeg = null;
	if(bianGua && bianGua.yaoname){
		bianSeg = [];
		for(let i = 0; i < 6; i++){
			const p = parseYaoName(bianGua.yaoname[i] || '');
			bianSeg.push({ pos: i + 1, zhi: p.zhi, wuxing: p.wuxing, zhu: i < 3 ? '之卦内·主财' : '之卦外·主生死' });
		}
	}
	// 流年:世上起 1 年,阳世顺行爻位、阴世逆行(一年一位,循环)
	const shiYang = gua.value[pt.shi - 1] === 1;
	const liuNian = [];
	for(let y = 0; y < 12; y++){ // 给 12 年展示窗,UI 可翻页
		const pos = shiYang ? ((pt.shi - 1 + y) % 6) + 1 : ((pt.shi - 1 - y) % 6 + 6) % 6 + 1;
		const p = parseYaoName((gua.yaoname || [])[pos - 1] || '');
		liuNian.push({ year: y + 1, pos, zhi: p.zhi, liuqin: p.liuqin });
	}
	return { seg, bianSeg, shiYang, liuNian };
}

// ── 八节卦气(八卦×八态):轮序 艮震巽离坤兑乾坎;立春起艮、春分震、立夏巽、夏至离、立秋坤、秋分兑、立冬乾、冬至坎。
// 状态序原书两处异文并存:家宅章[旺相胎没死囚休废] / 生育章[旺相胎没死休囚废] ──
const BAJIE_WHEEL = ['艮', '震', '巽', '离', '坤', '兑', '乾', '坎'];
const BAJIE_START = { 立春: '艮', 春分: '震', 立夏: '巽', 夏至: '离', 立秋: '坤', 秋分: '兑', 立冬: '乾', 冬至: '坎' };
export const BAJIE_STATES_HOME = ['旺', '相', '胎', '没', '死', '囚', '休', '废'];
export const BAJIE_STATES_BIRTH = ['旺', '相', '胎', '没', '死', '休', '囚', '废'];
export const BAJIE_LIST = Object.keys(BAJIE_START);
export function baJieGuaQi(jieName, statesVariant){
	const startGua = BAJIE_START[jieName];
	if(!startGua){ return null; }
	const states = statesVariant === 'birth' ? BAJIE_STATES_BIRTH : BAJIE_STATES_HOME;
	const s = BAJIE_WHEEL.indexOf(startGua);
	const out = {};
	for(let i = 0; i < 8; i++){ out[BAJIE_WHEEL[(s + i) % 8]] = states[i]; }
	return out; // {卦名→态}
}
// 内胎(生育):内卦逢当节「胎」卦 → 已成胎之象
export function neiTaiOf(jieName, innerGuaName){
	const map = baJieGuaQi(jieName, 'birth');
	if(!map || !innerGuaName){ return null; }
	return { state: map[innerGuaName] || '', isTai: map[innerGuaName] === '胎' };
}

// ── 由公历节气名归一到八节/中气(供 UI 从 nongli.jieqi 字段接线;缺节气输入时返 null 由上层隐藏卡) ──
const ZHONGQI_SET = new Set(SHENGJIANG_ZHONGQI);
const BAJIE_SET = new Set(BAJIE_LIST);
export function pickZhongQi(jieqiName){ return jieqiName && ZHONGQI_SET.has(jieqiName) ? jieqiName : null; }
export function pickBaJie(jieqiName){ return jieqiName && BAJIE_SET.has(jieqiName) ? jieqiName : null; }
// 按月支近似回退:无精确节气名时,以月支推最近已过八节/中气(寅月=立春后…),保证卡片可用
const MONTH_TO_BAJIE = { 寅: '立春', 卯: '春分', 辰: '春分', 巳: '立夏', 午: '夏至', 未: '夏至', 申: '立秋', 酉: '秋分', 戌: '秋分', 亥: '立冬', 子: '冬至', 丑: '冬至' };
const MONTH_TO_ZHONGQI = { 子: '冬至', 丑: '大寒', 寅: '雨水', 卯: '春分', 辰: '谷雨', 巳: '小满', 午: '夏至', 未: '大暑', 申: '处暑', 酉: '秋分', 戌: '霜降', 亥: '小雪' };
export function baJieByMonth(monthZhi){ return MONTH_TO_BAJIE[monthZhi] || null; }
export function zhongQiByMonth(monthZhi){ return MONTH_TO_ZHONGQI[monthZhi] || null; }

// ── 八宫化入墓死亡表 + 棺椁四卦(占病用) ──
const HUA_MU_DEATH = { 乾艮: '父', 坤巽: '母', 震坤: '长男', 巽坤: '长女', 坎巽: '中男', 离乾: '中女', 艮巽: '少男', 兑艮: '少女' };
export function huaRuMuOf(benGua, bianGua){
	if(!benGua || !bianGua || !benGua.house || !bianGua.house){ return null; }
	const key = benGua.house.name + bianGua.house.name;
	const who = HUA_MU_DEATH[key];
	return who ? { from: benGua.house.name, to: bianGua.house.name, who, duan: `${benGua.house.name}化入${bianGua.house.name},应${who}之忧` } : null;
}
export function guanGuoOf(guaNames){ // 传入盘面涉及的卦名(本/之/互),含 震=棺 巽=椁 坤=墓 艮=坟;四者全见大凶
	const set = new Set();
	(guaNames || []).forEach((nm) => {
		if(!nm){ return; }
		if(nm.indexOf('震') >= 0 || nm.indexOf('雷') >= 0){ set.add('棺(震)'); }
		if(nm.indexOf('巽') >= 0 || nm.indexOf('风') >= 0){ set.add('椁(巽)'); }
		if(nm.indexOf('坤') >= 0 || nm.indexOf('地') >= 0){ set.add('墓(坤)'); }
		if(nm.indexOf('艮') >= 0 || nm.indexOf('山') >= 0){ set.add('坟(艮)'); }
	});
	return { hits: Array.from(set), all: set.size >= 4 };
}
