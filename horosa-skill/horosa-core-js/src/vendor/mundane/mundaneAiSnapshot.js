// 世俗盘 AI 快照的「头行 / 判词 / 分析段 / 右栏卡」四件 —— 自上游 components/mundane/MundaneMain.js **逐字**抽出
// （bespoke，derived_from + derived_sha256 看守：上游 MundaneMain.js 一动即红，复核本文件后 --restamp）：
//   · buildMundaneAiSnapshotParts —— 上游类方法 `buildAiSnapshot(chart, fields, extra)`（MundaneMain.js:2849-2997）的正文，
//     headLines（盘型标题 / 规则集 / 盘型头行）+ judge（[世俗宫义]）+ extraSecs（[定局·年主/盘主] / [入境骨架] / [地理分野] /
//     [年之九主] / [世运问判] / [角化] / [地区盘推运]）+ cardSecs（buildMundaneCardSections）。
// 与上游的全部差异（声明式，重抽时必须保留）：
//   ① 类方法 → 具名导出函数，`this.state` → 第三参数 `state`（页面 React state：progFoundingYear / progTargetYear / srData /
//      secData / navanayaka…；headless 由 Python 按需给，缺键语义与上游「页面未算过」相同）；共 15 处；
//   ② 尾部 `const head / const body = buildAstroSnapshotContent(chart, fields) / return [...].join` 三行换成
//      `return { headLines, judge, extraSecs, cardSecs }`：盘面正文由 skill 侧 Python 的本命段 builder 出（与上游同一
//      buildAstroSnapshotContent 的段），拼接序 head / judge / extraSecs / cardSecs / body 由调用方（service.py）照上游 :2996 复现；
//   ③ 正文缩进保留上游类方法体的两级 tab（逐字节对照方便）。
// import 按 vendor 树改路径；AstroExtraCommon 不 vendor：chartRequestKey 恒 'headless'（同 MundaneMain.js 的 stub，[盘型格局]/
// 返照·次限的 `st.xxKey === chartRequestKey(chart)` 判定用），fmtDegree 只在 state.srData（页面按需拉取的返照）存在时才调到——
// headless 永不供给，故按 AGENTS §5「真不可达的引用：stub 定义同名、调到即抛明确错误」处理。
import { SIGNS } from '../divination/data/signs.js';
import { buildFacts } from '../divination/engine/chartFacts.js';
import { describeMundaneChart, describeIngressSkeleton, describeMundaneVictor, describeMundaneSyzygy, PLANET_CN as MUN_PLANET_CN } from './describe.js';
import { computeAngularity, rulerDeathSignature, describeSolunar } from './solunar.js';
import { PLANET_CN_V } from './vedicMundane.js';
import { MUNDANE_HORARY_KINDS, describeWarQuestion, describeWeatherQuestion, describePriceQuestion } from './mundaneHorary.js';
import { rulesetConfig } from './ruleset.js';
import { describeChorography } from './chorography.js';
import { mundaneProfection, mundaneFirdaria } from './progressions.js';
import {
	buildMundaneCardSections, formatMundaneHouseTable, formatMundaneChorographyTable,
	MUNDANE_ORB_SCHEME_CN, MUNDANE_INGRESS_RULE_CN, PLANET_CN, currentYear,
} from './MundaneMain.js';

const chartRequestKey = () => 'headless';
const fmtDegree = () => { throw new Error('fmtDegree（AstroExtraCommon）未 vendor：headless 不供给 state.srData，此路不可达 / fmtDegree is not vendored (headless never supplies state.srData)'); };

// MundaneMain.js:2849 `buildAiSnapshot(chart, fields, extra){` —— 正文逐字（见头注 ①②③）。
export function buildMundaneAiSnapshotParts(chart, extra, state){
		const ex = extra || {};
		const type = ex.mundaneType || 'ingress';
		const TITLE = { ingress: '世俗入宫', newmoon: '新月图', fullmoon: '满月图', solecl: '日食图', lunecl: '月食图', region: '地区盘', cycles: '行星周期', solunar: '恒星派入境', vedicmundane: '吠陀世运', mundanehorary: '世运卜卦' };
		const headLines = [`[${TITLE[type] || '世俗入宫'}]`, `规则集：${rulesetConfig(ex.mundaneRuleset).label}`];
		// [Q-150/T-60] 两个页面级覆盖此前不进快照:页面改了、AI 拿到的仍是流派缺省值。
		// 只在显式覆盖(非 auto)且本盘型真消费时补行 —— 缺省态快照逐字节不变。
		if(type === 'ingress'){
			headLines.push(`入宫节气：${ex.ingressTerm || '-'}`, `年份：${ex.ingressYear || '-'}`);
			if(ex.mundaneIngressRule && ex.mundaneIngressRule !== 'auto'){
				headLines.push(`入境主管制：${MUNDANE_INGRESS_RULE_CN[ex.mundaneIngressRule] || ex.mundaneIngressRule}（页面级覆盖）`);
			}
		}
		else if(type === 'newmoon' || type === 'fullmoon'){ headLines.push(`时刻：${ex.selectedMoment || '-'}`); }
		else if(type === 'solecl' || type === 'lunecl'){
			headLines.push(`时刻：${ex.selectedMoment || '-'}`, `类型：${ex.eclipseTypeText || '-'}`);
			if(ex.mundaneOrbScheme && ex.mundaneOrbScheme !== 'auto'){
				headLines.push(`受冲容许度：${MUNDANE_ORB_SCHEME_CN[ex.mundaneOrbScheme] || ex.mundaneOrbScheme}（页面级覆盖）`);
			}
		}
		else if(type === 'region'){ headLines.push(`地区：${ex.regionCn || '-'}`); }
		else if(type === 'solunar'){
			const st = describeSolunar(ex.solunarType || 'capsolar', ex.solunarWeights || 'scheme_a');
			if(st){ // [V6-W2] 体系行=盘种固定设计(solunar 恒 Fagan/Bradley+Campanus,非可调参数)=事实标注;
			// 若未来做成可调参数,必须改从实际计算参数取值(禁字面量)。
			headLines.push(`盘种：${st.cn}`, `有效期：${st.span} · 权重 ${st.weight}`, '体系：恒星黄道 Fagan/Bradley · Campanus 量角化'); }
		}
		else if(type === 'vedicmundane'){
			headLines.push(`年份：${ex.vedicYear || currentYear()}`, '体系：恒星黄道 Lahiri · 梅沙入境为年度主盘');
		}
		else if(type === 'mundanehorary'){
			const kindCn = (MUNDANE_HORARY_KINDS.find((k) => k.key === (ex.mhKind || 'war')) || {}).cn || '战争';
			headLines.push(`问题类型：${kindCn}`, '机制同卜卦,问主=公众/国家,宫义按世运读');
		}
		// 世俗宫义判词段 + 定局/分野/骨架/推运 分析段(全部从 facts 派生,供 AI 解读)
		let judge = '';
		const extraSecs = [];
		try{
			const facts = buildFacts(chart);
			const rows = describeMundaneChart(facts);
			if(rows && rows.length){ judge = '[世俗宫义]\n' + formatMundaneHouseTable(rows); }
			const v = describeMundaneVictor(facts, ex.mundaneRuleset);
			if(v){
				// [Q-444] 年主卡逐星得分与偶然项明细(此前只有年主一行)。
				const scoreLines = (v.scores || []).filter((x) => x.score > 0).map((x) => `- ${x.cn} ${x.score}${x.accidentalItems && x.accidentalItems.length ? `（${x.accidentalItems.map((it) => `${it.cn} ${it.v > 0 ? '+' + it.v : it.v}`).join('，')}）` : ''}`);
				extraSecs.push(`[定局·年主/盘主]\n年主星：${v.victorCn}（累分 ${v.maxScore}）${v.victorMundane ? ' · ' + v.victorMundane.powerRole : ''}；取点 ${v.points.join(' / ')}${scoreLines.length ? '\n' + scoreLines.join('\n') : ''}`);
			}
			if(type === 'ingress'){
				const sk = describeIngressSkeleton(facts);
				if(sk){
					// [Q-444] 骨架卡补:上升气质/十宫内星/产前朔望/临四轴/外行星。
					let syz = null; try{ syz = describeMundaneSyzygy(facts); }catch(e){ syz = null; }
					const more = [];
					if(sk.ascTemper){ more.push(`上升气质 ${sk.ascTemper.temper}`); }
					if(sk.tenthPlanets && sk.tenthPlanets.length){ more.push(`10宫内 ${sk.tenthPlanets.map((x) => x.cn).join('、')}`); }
					if(syz){ more.push(`产前朔望 ${syz.signCn} ${syz.signlon != null ? syz.signlon.toFixed(1) + '°' : ''}${syz.kind ? '（' + syz.kind + '）' : ''}`); }
					more.push(`临四轴 ${sk.angular && sk.angular.length ? sk.angular.map((a) => `${a.cn}(第${a.house}宫)${a.malefic ? '⚠' : ''}`).join('、') : '无'}`);
					if(sk.outers && sk.outers.length){ more.push(`外行星 ${sk.outers.map((o) => `${o.cn} ${o.houseMeaning}`).join('；')}`); }
					extraSecs.push(`[入境骨架]\n上升 ${sk.ascSignCn} · 主星 ${sk.ascRulerCn} 落 ${sk.ascRulerHouse} 宫${sk.ascRulerAngular ? '(临轴)' : ''}${sk.ascRulerRetro ? '(逆)' : ''}；政权 10宫主 ${sk.tenthRulerCn} · 太阳 ${sk.sun ? sk.sun.house : '-'} 宫；民生 月亮 ${sk.moon ? sk.moon.house : '-'} 宫\n${more.join('；')}`);
				}
			}
			if(type === 'ingress' || type === 'region'){
				const ch = describeChorography(facts, rulesetConfig(ex.mundaneRuleset).chorographyDataset);
				if(ch && ch.axes.length){
					// [Q-444] 分野卡补:托勒密四象限三方主管。
					const quads = (ch.quadrants || []).map((q) => `${q.cn}（${q.signs.map((sg) => (SIGNS[sg] || {}).cn || sg).join('/')}）主星 ${PLANET_CN[q.rulers.day]}/${PLANET_CN[q.rulers.night]} · ${q.region}`).join('；');
					extraSecs.push('[地理分野]\n数据集：' + ch.datasetMeta.label + '\n' + formatMundaneChorographyTable(ch.axes) + (quads ? '\n托勒密四象限：' + quads : '') + '\n（多源综合·传统占星学术参考,非现实地缘断言）');
				}
			}
			if(type === 'vedicmundane' && state.navanayaka && state.navanayakaYear === (ex.vedicYear || currentYear())){
				const nv = state.navanayaka;
				const lines = ['[年之九主]'];
				nv.offices.forEach((o) => { lines.push(`${o.cn}：${o.lord ? (PLANET_CN_V[o.lord] || o.lord) : '—'} · ${o.domain}`); });
				nv.readings.forEach((t) => lines.push(t));
				lines.push('（九主属后世历书传统,非出自某一原典）');
				extraSecs.push(lines.join('\n'));
			}
			if(type === 'mundanehorary'){
				const kind = ex.mhKind || 'war';
				const lines = ['[世运问判]'];
				if(kind === 'war'){
					const w = describeWarQuestion(facts);
					if(w){ lines.push(`己方 ${w.us.cn}(${w.us.total}) vs 敌方 ${w.them.cn}(${w.them.total})${w.reception ? ' · 互容' : ''}`, w.verdict.text); }
				}else if(kind === 'weather'){
					const wq = describeWeatherQuestion(facts);
					if(wq){ lines.push(`月宿 ${wq.moonMansion || '-'} · ${wq.tone}`); }
				}else{
					const pq = describePriceQuestion(facts);
					if(pq){ lines.push(pq.trend.text, pq.cropNote); }
				}
				if(lines.length > 1){ extraSecs.push(lines.join('\n')); }
			}
			if(type === 'solunar'){
				const ang = computeAngularity(facts, ex.solunarOrb || 3);
				if(ang){
					const fg = ang.rows.filter((r) => r.foreground);
					const lines = ['[角化]', `容许 ${ang.orb}°(卯酉圈等分量角);${fg.length ? '' : '休眠盘——无星入角,无信息可略过'}`];
					fg.forEach((r) => { lines.push(`${MUN_PLANET_CN[r.planet] || r.planet} 距${r.axisCn} ${r.dist.toFixed(1)}°${r.strong ? '(尤强)' : ''}${r.omen ? ' → ' + r.omen.text : ''}`); });
					if(rulerDeathSignature(facts, ex.solunarOrb || 3)){ lines.push('⚠ 复合判据命中:土星与太阳皆在角且彼此无相位'); }
					extraSecs.push(lines.join('\n'));
				}
			}
			if(type === 'region'){
				const founding = (state.progFoundingYear != null) ? state.progFoundingYear : (ex.regionFoundingYear || null);
				const target = (state.progTargetYear != null) ? state.progTargetYear : currentYear();
				if(founding != null && facts.meta && facts.meta.ascSign){
					const age = Math.max(0, target - founding);
					const prof = mundaneProfection(facts.meta.ascSign, age);
					const fird = mundaneFirdaria(facts.meta.sect, age);
					const lines = ['[地区盘推运]', `盘龄 ${age} 年（建置 ${founding} → 目标 ${target}）`];
					if(prof){
						lines.push(`小限：年小限 ${prof.profectedSignCn} · 激活第 ${prof.activatedHouse} 宫(${prof.houseTheme}) · 年主 ${prof.lordCn}`);
						// [Q-444] 逐月小限 / 法达序列 / 返照 / 次限(后两者页面按需拉取,算过才成行)。
						if(prof.months && prof.months.length){ lines.push(`逐月小限：${prof.months.map((mm) => `${mm.month}月 ${(SIGNS[mm.sign] || {}).cn || mm.sign}`).join('、')}`); }
					}
					if(fird){
						lines.push(`法达(${fird.sectCn})：大期 ${fird.major.planetCn}（盘龄 ${fird.major.start}–${fird.major.end}）${fird.sub ? ' · 子期 ' + fird.sub.planetCn : ' · 交点期不分子期'}`);
						if(fird.sequence && fird.sequence.length){ lines.push(`法达序：${fird.sequence.map((x) => `${x.planetCn}${x.years}`).join(' · ')}（七政 70+南北交 5 = 75 年一轮）`); }
					}
					if(state.srData && state.srYear === target && state.srKey === chartRequestKey(chart)){
						const sr = state.srData;
						lines.push(`太阳返照 ${target}：返照时刻 ${sr.solarReturn ? sr.solarReturn.datetime : '-'}；返照上升 ${fmtDegree(sr.solarAsc)}${sr.lunarReturn ? '；首个月返照 ' + sr.lunarReturn.datetime : ''}`);
					}
					if(state.secData && state.secYear === target && state.secKey === chartRequestKey(chart)){
						const sec = state.secData; const pos = sec.positions || [];
						const pSun = pos.find((p) => p.id === 'Sun'); const pMoon = pos.find((p) => p.id === 'Moon');
						const natalSun = (facts.planets && facts.planets.sun) ? facts.planets.sun.lon : null;
						const arc = (pSun && natalSun != null) ? (((pSun.lon - natalSun) % 360 + 360) % 360) : null;
						const sCn2 = (sg) => (SIGNS[String(sg || '').toLowerCase()] || {}).cn || sg;
						const ASP_CN = { 0: '合', 60: '六合', 90: '刑', 120: '三合', 180: '冲' };
						const parts = [];
						if(pSun){ parts.push(`次限太阳 ${sCn2(pSun.sign)} ${pSun.signlon != null ? pSun.signlon.toFixed(1) + '°' : ''}`); }
						if(pMoon){ parts.push(`次限月亮 ${sCn2(pMoon.sign)} ${pMoon.signlon != null ? pMoon.signlon.toFixed(1) + '°' : ''}`); }
						if(arc != null){ parts.push(`太阳弧 ${arc.toFixed(1)}°`); }
						if(sec.aspectsToNatal && sec.aspectsToNatal.length){ parts.push(`应期 ${sec.aspectsToNatal.slice(0, 6).map((a) => `次限${MUN_PLANET_CN[String(a.a).toLowerCase()] || a.a}${ASP_CN[a.aspect] || a.aspect + '°'}本命${MUN_PLANET_CN[String(a.b).toLowerCase()] || a.b}(${a.orb != null ? a.orb.toFixed(1) : '?'}°)`).join('、')}`); }
						if(parts.length){ lines.push(`次限·太阳弧 ${target}：${parts.join('；')}`); }
					}
					extraSecs.push(lines.join('\n'));
				}
			}
		}catch(e){ /* noop */ }
		// [Q-444/T-407] 其余右栏卡(概览/判读/恒星/推运/各盘型专卡)折入既有盘型段:与 render*Card 同源纯函数,按需拉取物取自 state。
		let cardSecs = [];
		try{ cardSecs = buildMundaneCardSections(chart, ex, state, null); }catch(e){ cardSecs = []; }
		return { headLines, judge, extraSecs, cardSecs };
}
