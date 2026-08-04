// 贵神特殊态（毕法级，解读层）：贵人临狱(辰戌) / 贵人坐空(旬空)。纯函数，只读 context，无副作用。
// 与「毕法 tab」互补：此处把最常用的两个贵人态直接在「概览」点出。

export function detectGuiSpecials(ctx){
	if(!ctx || !ctx.guizi){ return []; }
	const guizi = `${ctx.guizi}`.substring(0, 1);
	const out = [];
	if(guizi === '辰' || guizi === '戌'){
		out.push({ type: '贵人临狱', level: 'bad', note: `贵人临${guizi}（辰戌为牢狱、贵人不临之地）。告贵求贵多阻；惟乙辛日反宜临干投贵。` });
	}
	if(ctx.xunKongBranches && ctx.xunKongBranches.indexOf(guizi) >= 0){
		out.push({ type: '贵人坐空', level: 'bad', note: `贵人所临${guizi}值旬空。告贵多虚喜，有费而少实。` });
	}
	// 贵人治事(§22.3):贵人所临地盘宫(seat)定励德/贵登天门;顺逆布=顺逆治;天罡辰加天门亥=魁度天门(关隔)。
	const seat = ctx.branchGodMap ? Object.keys(ctx.branchGodMap).find((b)=>ctx.branchGodMap[b] === '贵人') : '';
	if(seat === '卯' || seat === '酉'){
		out.push({ type: '励德', level: 'good', note: `贵人临${seat}（二八门、阴阳交易之位）。主官位迁动、反复不定；谦退者升、妄进者黜。` });
	}
	if(seat === '亥'){
		out.push({ type: '贵登天门', level: 'good', note: '贵人临地盘亥（天门）。六凶将受制、六吉将得位、诸煞潜藏，「神藏煞没」择吉第一格。' });
	}
	if(typeof ctx.guirenForward === 'boolean' && (seat || ctx.guizi)){
		out.push(ctx.guirenForward
			? { type: '顺治', level: 'good', note: '贵人落地盘亥—辰（天门后地户前）、顺布顺治。治事和顺，纵遇凶将凶亦不深。' }
			: { type: '逆治', level: 'neutral', note: '贵人落地盘巳—戌（地户）、逆布逆治。治事乖戾，纵得吉将福亦不厚（利于阴私）。' });
	}
	if(ctx.branchUpMap && ctx.branchUpMap['亥'] === '辰'){
		out.push({ type: '魁度天门（关隔）', level: 'bad', note: '天罡辰加临天门亥（毕法51）。关隔不通、阻滞难行，与「贵登天门」相对。' });
	}
	return out;
}
