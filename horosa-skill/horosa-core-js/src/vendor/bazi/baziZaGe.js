// 杂格识别器（八字大全 §9.4，古格）。规约：正格能取者优先取正格，正格不成方论杂格；
//   逢填实/刑冲破多破格。只收「规则明确、可机械匹配」者（四干四支同气、日时柱专格），
//   「虚邀暗冲（飞天禄马/井栏叉/六乙鼠贵…）」需「多X + 局无X」模糊条件，暂不臆断纳入。
//   flagged 候选（与变格同性质，不覆盖正格/用神），面板与 AI 标注「需复核填实刑冲」。

function gz(p){ return p && p.stem && p.branch ? `${p.stem.cell || ''}${p.branch.cell || ''}` : ''; }

// 日柱专格（§9.4）
const RI_DE = new Set(['甲寅', '丙辰', '戊辰', '庚辰', '壬戌']);            // 日德格
const RI_GUI = new Set(['丁酉', '丁亥', '癸卯', '癸巳']);                  // 日贵格（日坐天乙）
const FU_DE_XIU = new Set(['乙巳', '乙酉', '乙丑']);                       // 福德秀气格
const JIN_SHEN = new Set(['癸酉', '己巳', '乙丑']);                        // 金神格（时柱）

const PILLARS = ['year', 'month', 'day', 'time'];

// 返回 [{name, cond, note}] 或 null
export function computeZaGe(four){
	if(!four || !four.day){ return null; }
	const out = [];
	const stems = PILLARS.map((k) => four[k] && four[k].stem && four[k].stem.cell).filter(Boolean);
	const zhis = PILLARS.map((k) => four[k] && four[k].branch && four[k].branch.cell).filter(Boolean);
	const dayGz = gz(four.day);
	const timeGz = gz(four.time);

	if(stems.length === 4 && new Set(stems).size === 1){
		out.push({ name: '天元一气格', cond: '四天干相同', note: '纯而有用为贵，全看地支配合。' });
	}
	if(zhis.length === 4 && new Set(zhis).size === 1){
		out.push({ name: '地支一气格', cond: '四地支相同', note: '一气专纯，最忌冲破。' });
	}
	if(stems.length === 4 && new Set(stems).size === 2){
		out.push({ name: '两干不杂格', cond: '四柱天干仅两干交互', note: '清纯为贵。' });
	}
	const els = new Set();
	PILLARS.forEach((k) => {
		const p = four[k];
		if(!p){ return; }
		if(p.stem && p.stem.element){ els.add(p.stem.element); }
		if(p.branch && p.branch.element){ els.add(p.branch.element); }
	});
	if(els.size === 5){
		out.push({ name: '五行俱足格', cond: '五行齐全流通', note: '周流不滞为贵。' });
	}
	if(RI_DE.has(dayGz)){
		out.push({ name: '日德格', cond: `日柱${dayGz}`, note: '喜身旺，忌刑冲、忌叠魁罡。' });
	}
	if(RI_GUI.has(dayGz)){
		out.push({ name: '日贵格', cond: `日坐天乙（${dayGz}）`, note: '忌刑冲破害、空亡。' });
	}
	if(FU_DE_XIU.has(dayGz)){
		out.push({ name: '福德秀气格', cond: `日柱${dayGz}`, note: '喜身旺有制。' });
	}
	if(JIN_SHEN.has(timeGz)){
		out.push({ name: '金神格', cond: `时柱${timeGz}`, note: '需火制：喜火炼、忌水。' });
	}
	return out.length ? out : null;
}

export default computeZaGe;
