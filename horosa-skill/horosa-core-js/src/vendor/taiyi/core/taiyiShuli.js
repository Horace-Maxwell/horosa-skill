// 太乙「数理十类」标签(卷二 §22)。纯派生:据主算/客算/定算等数字 + 太乙宫阴阳,
// 贴重阳/重阴/上和/次和/下和/无门/三才(无天无地无人)/长短/不和 等标签。文案为公有领域术数通则,逐字取自方法骨架。
// 移植自文档「古法复原」引擎 shuli_label;前端纯函数,零触碰后端立成表 golden。

// 八正宫阴阳(§22:艮震巽离为阳,坤兑乾坎为阴;中宫不计)。键=太乙宫名(pan.taiyiPalace)。
export const PALACE_YINYANG = {
	艮: '阳', 震: '阳', 巽: '阳', 离: '阳',
	坤: '阴', 兑: '阴', 乾: '阴', 坎: '阴',
};

// 太乙落点名 → 卦名。引擎的 pan.taiyiPalace 四正宫用地支名(午/卯/酉/子)、四维用卦名
// (乾/艮/坤/巽),而上表以卦名为键 —— 不归一则四正宫恒查不到,「不和」标签与厄会宫阴阳
// 对半数落点静默失效(同款坑在 taiyiGeju 的注释里已记过:「离宫落点=午非离」)。
const PALACE_ALIAS = { 午: '离', 卯: '震', 酉: '兑', 子: '坎' };

export function palaceYinYang(palace){
	if(!palace){ return ''; }
	const raw = String(palace).charAt(0); // 兼容「艮」「艮宫」
	const key = PALACE_ALIAS[raw] || raw;
	return PALACE_YINYANG[key] || '';
}

// 数字 n 的数理标签列表;taiyiYinYang 为太乙宫阴阳(用于「不和」判定),缺省则跳过不和。
export function shuliLabel(n, taiyiYinYang){
	if(n === undefined || n === null || isNaN(n)){ return ['—']; }
	const tags = [];
	if(n === 33 || n === 39){ tags.push('重阳数(主火·亢旱)'); }
	if(n === 22 || n === 26){ tags.push('重阴数(主水·阴疫)'); }
	if([12, 16, 21, 27, 34, 38].includes(n)){ tags.push('下和数'); }
	if([1, 4, 8].includes(n)){ tags.push('上和数'); }
	if([2, 6, 3, 9].includes(n)){ tags.push('次和数'); }
	if([5, 15, 25, 35].includes(n)){ tags.push('无门·主大灾'); }
	if(n >= 1 && n <= 9){ tags.push('无天(无十)·短'); }
	if(n >= 11){ tags.push('长数'); }
	if(n % 10 === 0){ tags.push('无人(无一)'); }
	// —— 数理十类补 3 子类(§22 散文表)。歧义处理=共存双标:1/4/8 既属上和数、又落下列子类
	//    (源表「上和」与「无地/阴中重阳/阳中重阴」自相重叠,忠于原文并列,精度以排盘复核) ——
	// 无地:个位∈{1,2,3,4}(未及五、无三才之地;例「一至四、十一至十四」)
	if([1, 2, 3, 4].includes(n % 10)){ tags.push('无地(未及五)'); }
	// 阴中重阳:n∈{1,7}(阴数位藏重阳、微阳内动)
	if([1, 7].includes(n)){ tags.push('阴中重阳'); }
	// 阳中重阴:n∈{4,8}(阳数位藏重阴、微阴内伏)
	if([4, 8].includes(n)){ tags.push('阳中重阴'); }
	if(taiyiYinYang === '阳' && n % 2 === 1){ tags.push('不和(阳宫得奇)'); }
	if(taiyiYinYang === '阴' && n % 2 === 0){ tags.push('不和(阴宫得偶)'); }
	return tags.length ? tags : ['平'];
}

// 标签吉凶倾向(用于 UI 着色):凶 / 吉 / 中。
// ⚠️ 子类判定须早于通用正则:「阴中重阳/阳中重阴」含「重阳/重阴」子串,若落通用正则会误判凶;
//    子类是微妙转化(非重阳数/重阴数之灾),归中性;「无地」属三才缺(结构性),与无天/无人同归中性。
export function shuliTone(tag){
	if(/阴中重阳|阳中重阴|无地/.test(tag)){ return 'neutral'; }
	if(/大灾|重阳|重阴|不和/.test(tag)){ return 'bad'; }
	if(/上和|次和|下和/.test(tag)){ return 'good'; }
	return 'neutral';
}

// 据 pan 计算三算数理:{ home:[...], away:[...], set:[...], yinYang }。
export function computeTaiyiShuli(pan){
	if(!pan){ return null; }
	const yy = palaceYinYang(pan.taiyiPalace);
	const toNum = (v) => (typeof v === 'number' ? v : parseInt(v, 10));
	return {
		yinYang: yy,
		home: shuliLabel(toNum(pan.homeCal), yy),
		away: shuliLabel(toNum(pan.awayCal), yy),
		set: shuliLabel(toNum(pan.setCal), yy),
	};
}
