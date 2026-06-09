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
	return out;
}
