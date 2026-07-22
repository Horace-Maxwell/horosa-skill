// 六爻应期引擎:按用神状态归集诸法候选应期(值/冲/合/填实/冲空/出月/冲墓/逢生/进退到位),
// 另附出空填空冲空的短中长期口径与占类专用规则(期日章)。只出「候选支+依据」,不作绝对日期断言。
import { DIZHI, TIANGAN, LIUCHONG, LIUHE, CHANGSHENG_START, CHANGSHENG_START_ALT } from './LiuYaoConst.js';

const zi = (i) => DIZHI[((i % 12) + 12) % 12];
const idx = (z) => DIZHI.indexOf(z);
// 五行墓支(水土同宫:金丑木未火戌水土辰;火土同宫:土戌)
export function muZhiOf(wx, tuMode){
	if(wx === '金'){ return '丑'; } if(wx === '木'){ return '未'; } if(wx === '火'){ return '戌'; }
	if(wx === '水'){ return '辰'; }
	if(wx === '土'){ return tuMode === 'fire' ? '戌' : '辰'; }
	return '';
}
export function changShengZhiOf(wx, tuMode){
	const m = tuMode === 'fire' ? CHANGSHENG_START_ALT : CHANGSHENG_START;
	return m[wx] || '';
}

// 未来 60 日内某支的命中日偏移(0=今日):由日支序推,UI 再换算日期
export function futureZhiOffsets(targetZhi, dayZhi, span){
	const t = idx(targetZhi), d = idx(dayZhi);
	if(t < 0 || d < 0){ return []; }
	const out = [];
	for(let k = 0; k <= (span || 60); k++){ if((d + k) % 12 === t){ out.push(k); } }
	return out;
}

// yong: { zhi, wuxing, moving, xunKong, voidKind, yuePo, ruMu, wangShuai, changsheng }
// dong: 该爻动变信息(可空){ jinShen, tuiShen, bian:{zhi} }
// ctx: { dayZhi, monthZhi, tuMode }
export function computeYingQi(yong, dong, ctx){
	if(!yong || !yong.zhi){ return []; }
	const c = ctx || {};
	const rules = [];
	const push = (rule, targets, scope, source, hint) => {
		const t = (targets || []).filter(Boolean);
		if(t.length){ rules.push({ rule, targets: t, scope: scope || '日/月', source, hint: hint || '' }); }
	};
	const strong = yong.wangShuai === '旺' || yong.wangShuai === '相';
	if(!yong.moving && strong && !yong.xunKong && !yong.yuePo){
		push('静而旺相:逢值或逢冲', [yong.zhi, LIUCHONG[yong.zhi]], '日/月', '通行应期法');
	}
	if(yong.moving){
		push('发动:逢合(绊住)或逢值', [LIUHE[yong.zhi], yong.zhi], '日/月', '通行应期法');
	}
	if(yong.xunKong){
		push('旬空:填实(值空支)', [yong.zhi], '短=日/中=月/长=年', '出空填实冲空三法', '事应在填实之时,按事之大小取日/月/年');
		push('旬空:冲空(激活,应事急巧)', [LIUCHONG[yong.zhi]], '日/月/年', '出空填实冲空三法', '冲空不稳,所诱之事激烈突然');
	}
	if(yong.yuePo){
		push('月破:出月后逢填实或逢合', [yong.zhi, LIUHE[yong.zhi]], '日(出月后)', '通行应期法', '当月为破,出月不破');
	}
	if(yong.ruMu){
		const mu = muZhiOf(yong.wuxing, c.tuMode);
		push('入墓:冲开墓库', [LIUCHONG[mu]], '日', '通行应期法');
	}
	if(yong.changsheng === '绝'){
		const shengWx = ({ 金: '土', 木: '水', 水: '金', 火: '木', 土: '火' })[yong.wuxing];
		push('临绝:绝处逢生(生我五行之日)', shengWx ? DIZHI.filter((z) => ({ 子: '水', 丑: '土', 寅: '木', 卯: '木', 辰: '土', 巳: '火', 午: '火', 未: '土', 申: '金', 酉: '金', 戌: '土', 亥: '水' })[z] === shengWx) : [], '日', '通行应期法');
	}
	if(dong && dong.jinShen && dong.bian){ push('化进神:进至到位之支', [dong.bian.zhi], '日/月', '通行应期法'); }
	if(dong && dong.tuiShen && dong.bian){ push('化退神:退回之支,事多反复', [dong.bian.zhi], '日/月', '通行应期法'); }
	// 补充:用神值日得信、用神长生之月渐愈生发
	push('用神值日(得信/应事)', [yong.zhi], '时/日', '今说应期补充');
	push('用神长生之月(生发到位)', [changShengZhiOf(yong.wuxing, c.tuMode)], '月', '今说应期补充');
	return rules;
}

// 期日章(占类专用应期,《断易天机》):按占测事项追加规则
export function qiRiByAsk(askKey, parts){
	const p = parts || {}; // { yongZhi, yongWx, ziSunZhi, guiWx, shiZhi, guaShenBody, tuMode }
	const out = [];
	const add = (rule, targets, hint) => { const t = (targets || []).filter(Boolean); if(t.length){ out.push({ rule, targets: t, scope: '日', source: '断易天机·期日章', hint: hint || '' }); } };
	const cs = (wx) => changShengZhiOf(wx, p.tuMode);
	const diWang = (wx) => ({ 金: '酉', 木: '卯', 水: '子', 火: '午', 土: p.tuMode === 'fire' ? '午' : '子' })[wx];
	if(askKey === 'wealth'){ add('求财:用爻长生→帝旺,加墓库日', [cs(p.yongWx), diWang(p.yongWx), muZhiOf(p.yongWx, p.tuMode)]); }
	if(askKey === 'illness' || askKey === 'doctor'){
		add('占病:子孙生旺日病瘥', [cs(({ 子: '水', 丑: '土', 寅: '木', 卯: '木', 辰: '土', 巳: '火', 午: '火', 未: '土', 申: '金', 酉: '金', 戌: '土', 亥: '水' })[p.ziSunZhi]), p.ziSunZhi], '子孙临日辰为神医');
		if(p.guiWx){ add('占病:鬼爻墓旺日病势反复', [muZhiOf(p.guiWx, p.tuMode)]); }
	}
	if(askKey === 'marriage_m' || askKey === 'marriage_f'){ add('婚姻:月卦身之月', [p.guaShenBody]); }
	if(askKey === 'opponent'){ add('谒见:世应相合之时', [p.shiZhi ? LIUHE[p.shiZhi] : '']); }
	if(askKey === 'career'){ add('求官:官鬼旺相之日', [p.yongZhi]); }
	return out;
}
