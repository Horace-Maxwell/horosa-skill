// 月律分野（人元司令）——月令藏干非整月匀力，按「节后第几天」轮值司令。
// 两版本并列（中性命名）：通行版（今法常用，每月恰 30 日，余气→中气→本气）、
//   法诀版（古法诀，寅余气作己、卯中气见癸、申分四段、酉见丁、子见辛等）。
// 学理与日数对照见 八字大全 §月律分野；纯展示派生，不改四柱/大运/神煞。

// 每段 [天干, 节后日数]；首段=余气、末段=本气、其余=中气。末段按余日承接至下一节（catch-all）。
const FENYE_COMMON = {
	寅: [['戊', 7], ['丙', 7], ['甲', 16]],
	卯: [['甲', 10], ['乙', 20]],
	辰: [['乙', 9], ['癸', 3], ['戊', 18]],
	巳: [['戊', 7], ['庚', 7], ['丙', 16]],
	午: [['丙', 10], ['己', 9], ['丁', 11]],
	未: [['丁', 9], ['乙', 3], ['己', 18]],
	申: [['戊', 7], ['壬', 7], ['庚', 16]],
	酉: [['庚', 10], ['辛', 20]],
	戌: [['辛', 9], ['丁', 3], ['戊', 18]],
	亥: [['戊', 7], ['甲', 7], ['壬', 16]],
	子: [['壬', 10], ['癸', 20]],
	丑: [['癸', 9], ['辛', 3], ['己', 18]],
};
const FENYE_FAJUE = {
	寅: [['己', 7], ['丙', 5], ['甲', 18]],
	卯: [['甲', 9], ['癸', 3], ['乙', 18]],
	辰: [['乙', 9], ['癸', 3], ['戊', 18]],
	巳: [['戊', 7], ['庚', 5], ['丙', 18]],
	午: [['丙', 9], ['己', 3], ['丁', 18]],
	未: [['丁', 7], ['乙', 5], ['己', 18]],
	申: [['己', 7], ['戊', 3], ['壬', 3], ['庚', 17]],
	酉: [['庚', 7], ['丁', 3], ['辛', 20]],
	戌: [['辛', 7], ['丁', 5], ['戊', 18]],
	亥: [['戊', 7], ['甲', 5], ['壬', 18]],
	子: [['壬', 9], ['辛', 3], ['癸', 18]],
	丑: [['癸', 7], ['辛', 5], ['己', 18]],
};

const TABLES = { common: FENYE_COMMON, fajue: FENYE_FAJUE };
const VERSION_LABEL = { common: '通行版', fajue: '法诀版' };

function posLabel(idx, len){
	if(idx === 0){ return '余气'; }
	if(idx === len - 1){ return '本气'; }
	return '中气';
}

// monthZhi: 月支字符；daysAfterJie: 节后天数（含小数，≥0）；version: 'common'|'fajue'
// 返回 { version, versionLabel, monthZhi, daysAfterJie, segments:[{gan,days,start,end,pos}], ruler }
export function computeFenYe(monthZhi, daysAfterJie, version){
	const v = version === 'fajue' ? 'fajue' : 'common';
	const segsRaw = TABLES[v][monthZhi];
	if(!segsRaw){ return null; }
	const d = Math.max(0, Number(daysAfterJie) || 0);
	let cum = 0;
	const segments = segsRaw.map((s, i) => {
		const start = cum;
		cum += s[1];
		return { gan: s[0], days: s[1], start, end: cum, pos: posLabel(i, segsRaw.length) };
	});
	let ruler = segments[segments.length - 1];
	for(let i = 0; i < segments.length; i += 1){
		if(d < segments[i].end){ ruler = segments[i]; break; }
	}
	return {
		version: v,
		versionLabel: VERSION_LABEL[v],
		monthZhi,
		daysAfterJie: Math.round(d * 10) / 10,
		segments,
		ruler,
	};
}

export default computeFenYe;
