// 历史会合三层说(木土大会合的历史分期语义层)。数据/口径照录古籍会合篇:
// 三层周期(名义 vs 天文并列)、元素轮转 火→土→风→水、平行三元、土火合巨蟹专论。
// 输入=已有 greatconj/planetcycles 结果行,纯前端派生,零新后端。
// 显示层零章节号、历史人名不入代码键(传承线以中性词呈现)。

export const ELEMENT_ORDER = ['fire', 'earth', 'air', 'water'];
export const ELEMENT_CN = { fire: '火', earth: '土', air: '风', water: '水' };

// 三层周期表(名义值系古典口径,天文实测并列——两者并列呈现是古籍明确要求)。
export const CONJUNCTION_LAYERS = [
	{ key: 'lesser', cn: '大会合', trigger: '每次木土合（同三方内）', nominalYears: 20, observedYears: '≈19.86', meaning: '君王兴替、先知出现' },
	{ key: 'greater', cn: '更大会合（变迁）', trigger: '会合首次进入新元素', nominalYears: 240, observedYears: '≈200', meaning: '教派/律法/王朝转移——宗教与政权更迭' },
	{ key: 'greatest', cn: '最大会合', trigger: '新循环首合于白羊（回火象起点）', nominalYears: 960, observedYears: '≈800', meaning: '帝国兴亡、文明级巨变、洪水与地震' },
];

// 平行三元(古典-中世纪传承的补充周期组):更大=木土;中=火土;小=木火。
export const PARALLEL_TRIADS = [
	{ key: 'greater', cn: '更大三元', p1: 'jupiter', p2: 'saturn', note: '时代主钟（约 20 年一会）' },
	{ key: 'middle', cn: '中三元', p1: 'mars', p2: 'saturn', note: '战争与灾厄节拍（约 2 年一会；合于巨蟹尤重）' },
	{ key: 'lesser', cn: '小三元', p1: 'jupiter', p2: 'mars', note: '扩张与冲突的短周期（约 2.2 年一会）' },
];

const SIGN_ELEMENT = {
	aries: 'fire', leo: 'fire', sagittarius: 'fire',
	taurus: 'earth', virgo: 'earth', capricorn: 'earth',
	gemini: 'air', libra: 'air', aquarius: 'air',
	cancer: 'water', scorpio: 'water', pisces: 'water',
};
const SIGN_KEYS = ['aries', 'taurus', 'gemini', 'cancer', 'leo', 'virgo', 'libra', 'scorpio', 'sagittarius', 'capricorn', 'aquarius', 'pisces'];

function rowElement(row){
	if(!row){ return null; }
	if(row.element && SIGN_ELEMENT[row.sign] === undefined){ return row.element; }
	const signKey = typeof row.sign === 'number' ? SIGN_KEYS[row.sign] : String(row.sign || '').toLowerCase();
	return SIGN_ELEMENT[signKey] || row.element || null;
}

// 历史会合分期:对(按年升序的)木土合相行序列,判每个元素变化点的性质。
// 四态(工程判据,与参考纪年表标注语义对齐;1802 与 1980 在数学上对称,史学称谓差异由静态表 note 呈现):
//   stable_shift  稳定变迁——进入新元素且后续两次仍同元素(如 2020→风,此后全风)
//   precursor     变迁前奏——进入新元素,下一次跳回旧元素,但其后两次起稳定进入同一新元素
//                 (如 1802→土(1821 回火后 1842 起稳定)、1980→风(2000 回土后 2020 起稳定))
//   oscillation   过渡振荡——单次跳出后即回,且其后并未稳定进入该元素(如 1643 水、1821 火)
//   greatest      大变迁——stable_shift 且新元素=火(走遍四元素回火起点)
export function computeConjunctionEras(gcRows){
	const rows = (gcRows || []).map((r) => ({ ...r, _el: rowElement(r) })).filter((r) => r._el && r.year != null)
		.sort((a, b) => a.year - b.year);
	if(rows.length < 2){ return { rows, marks: [], segments: [] }; }
	const marks = [];
	for(let i = 1; i < rows.length; i++){
		if(rows[i]._el === rows[i - 1]._el){ continue; }
		const el = rows[i]._el;
		const n1 = rows[i + 1] ? rows[i + 1]._el : null;
		const n2 = rows[i + 2] ? rows[i + 2]._el : null;
		const n3 = rows[i + 3] ? rows[i + 3]._el : null;
		let kind = 'oscillation';
		if(n1 === el){
			kind = 'stable_shift';
		}else if(n1 !== null && n2 === el && (n3 === el || n3 === null)){
			kind = 'precursor';   // 跳回一次后稳定进入
		}
		if(kind === 'stable_shift' && el === 'fire'){ kind = 'greatest'; }
		marks.push({ year: rows[i].year, element: el, elementCn: ELEMENT_CN[el], kind, row: rows[i] });
	}
	// 元素分段(时间轴条):以 stable_shift/greatest 为段界;precursor 起点并入下一稳定段的前奏区。
	const segments = [];
	let segStart = rows[0];
	let segEl = rows[0]._el;
	marks.forEach((m) => {
		if(m.kind === 'stable_shift' || m.kind === 'greatest'){
			segments.push({ from: segStart.year, to: m.year, element: segEl, elementCn: ELEMENT_CN[segEl] });
			segStart = m.row; segEl = m.element;
		}
	});
	segments.push({ from: segStart.year, to: rows[rows.length - 1].year, element: segEl, elementCn: ELEMENT_CN[segEl] });
	return { rows, marks, segments };
}

// 土火合于巨蟹(约 30 年一遇,主大灾/战;其前白羊入境盘列高级主管盘):
// 从 planetcycles(mars×saturn,合相)事件行里筛巨蟹座。
export function detectMarsSaturnCancer(rows){
	return (rows || []).filter((r) => {
		const signKey = typeof r.sign === 'number' ? SIGN_KEYS[r.sign] : String(r.sign || '').toLowerCase();
		return signKey === 'cancer';
	});
}

export default { CONJUNCTION_LAYERS, PARALLEL_TRIADS, computeConjunctionEras, detectMarsSaturnCancer, ELEMENT_CN };
