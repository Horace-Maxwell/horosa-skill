/**
 * Jyotish（印度占星）快照段构造器 —— 自上游 `astrostudyui/src/components/astro/IndiaChart.js`
 * **逐字 vendor**（仅剥掉 React 外壳）：`gfmTable` 助手 + `buildJyotishSnapshotLines`。
 *
 * 为什么 verbatim 而非 Python 移植：它是 578 行**纯格式化**逻辑，读后端已算好的 `chartObj.jyotish`
 * 树（panchanga / jaimini / kp / shadbala / dasha …共 30 个子树）产出 51 个具名段。逐字段手抄成
 * Python 有 600 行的抄写面，任何一处措辞漂移都会让导出与星阙桌面端不一致；verbatim 拷贝则天然
 * 逐字同源。闭包极小：除下方 `gfmTable` 外零外部依赖（`PCN` 是块内局部常量），无需任何 shim。
 *
 * 同步须知：上游改这两段时，重跑 `scripts/verify_upstream_sync.py` 会按 basename 逐文件比对报红。
 *
 * 另自同一文件逐字抽出（v3.11 西占补段）：[大运Dasha] 的体系切换 builder（IndiaChart.js:298-494：
 * DASHA_SYSTEM_SNAPSHOT_LABEL / snapshotBirthDate / buildExtendedDashaSnapshotLines / buildAntardashaTableLines /
 * buildDashaSnapshotLines）与 [起盘信息] 流派/分盘头行（:149-170 resolveIndiaFractal/resolveIndiaLabel +
 * buildIndiaSnapshotText:1154-1177 的内联行，收成 buildIndiaSchoolHeaderLines）。常量走 curated ./indiaConst.js。
 */
import * as AstroConst from './indiaConst.js';

// [v2 表化] GFM 表助手：表头词组 + 行单元格数组 → GFM 表行(表头/分隔/数据)；单元格值逐字同源仅以 | 分隔。
// 置于函数前(模块层)：不占函数体内字符偏移，护段头 22k 源切片哨兵；散文行由调用方 spread 混排。
const gfmTable = (heads, rows)=>{
	const bar = (cells)=>`| ${cells.join(' | ')} |`;
	return [bar(heads), bar(heads.map(()=>'---')), ...rows.map(bar)];
};
// AI 挂载补充：把后端 jyotish 真值(Panchanga / 8 卡拉卡 / 节点主照)一并写进快照。
// 全部读 chartObj.jyotish.*（单一真值源），缺省则该段跳过；不硬编码任何常量。
export function buildJyotishSnapshotLines(chartObj){
	const j = chartObj && chartObj.jyotish;
	if(!j){ return {}; }
	const fx = (x, d)=>(typeof x === 'number' && Number.isFinite(x)) ? x.toFixed(d) : (x !== undefined && x !== null ? `${x}` : '—');
	const lordOf = (l)=>(l && (l.label || l.key)) || '—';
	const out = {};
	// 🔴 skill 偏离（v3.11.x 同步发现的**上游 bug**，上游 IndiaChart.js HEAD 9b74714b 仍在）：SIGN_CN_S / scS 两行在上游
	// 定义于下方「印占 P0 接 UI 同步」块（IndiaChart.js:932-933），而 [Q-127/T-35] 三旗盘逐月净分块（:721-732）在它之前
	// 就调用 scS → const 暂时性死区 ReferenceError：后端一带 jyotish.tripataki（opt-in indiaTripataki）整个
	// buildJyotishSnapshotLines 抛出，上游 buildIndiaSnapshotText 无 try → 整份印度快照失败；skill 侧则全部 jyotish 段缺席。
	// 两行原样上提（值逐字不变），其余逐字不动。重新从上游抽取本文件时必须保留此上提，直到上游修掉。
	const SIGN_CN_S = { Aries: '白羊', Taurus: '金牛', Gemini: '双子', Cancer: '巨蟹', Leo: '狮子', Virgo: '处女', Libra: '天秤', Scorpio: '天蝎', Sagittarius: '射手', Capricorn: '摩羯', Aquarius: '水瓶', Pisces: '双鱼' };
	const scS = (s)=>SIGN_CN_S[s] || s || '—';

	const p = j.panchanga;
	if(p){
		const pl = [];
		if(p.vara){ pl.push(`星期(Vara)：${p.vara.label || p.vara.name || '—'}（主 ${lordOf(p.vara.lord)}）`); }
		if(p.tithi){ pl.push(`月相(Tithi)：${`${p.tithi.paksha || ''} ${p.tithi.name || ''}`.trim() || '—'}（第 ${p.tithi.index} 日）`); }
		if(p.nakshatra){
			pl.push(`月宿(Nakshatra)：${p.nakshatra.label || p.nakshatra.name || p.nakshatra.key || '—'}`);
			const nd = p.nakshatra.detail;
			if(nd){
				const bits = [];
				if(nd.deity){ bits.push(`司神 ${nd.deity}`); }
				if(nd.symbol){ bits.push(`象征 ${nd.symbol}`); }
				if(nd.gana){ bits.push(`族类 ${nd.gana}`); }
				if(nd.yoniAnimal){ bits.push(`瑜尼 ${nd.yoniAnimal}`); }
				if(nd.gunas){ bits.push(`三德 ${nd.gunas}`); }
				if(nd.purushartha){ bits.push(`人生目标 ${nd.purushartha}`); }
				if(bits.length){ pl.push(`　月宿详情：${bits.join('·')}`); }
			}
		}
		if(p.yoga){ pl.push(`瑜伽(Yoga)：${p.yoga.name || '—'}`); }
		if(p.karana){ pl.push(`半日(Karana)：${(p.karana.name || p.karana.label) || '—'}`); }
		if(pl.length){ out['Panchanga 五要素'] = pl; }
	}

	const ck = j.jaimini && j.jaimini.charaKarakas;
	if(Array.isArray(ck) && ck.length){
		// [Q-135/T-43 (b)] 段名是 aiExport 登记键(不改),但 7 卡拉卡档下仍称「8」并列 7 行会误导 →
		// 段内首行写明所用方案(引擎回传 karakaScheme:'7' 古典不含 Rāhu / '8' 含 Rāhu)。
		const _scheme = String((j.jaimini && j.jaimini.karakaScheme) || (ck.length === 7 ? '7' : '8'));
		out['卡拉卡（8 Chara Karakas）'] = [
			`方案：${_scheme === '7' ? '7 卡拉卡（古典，不含 Rāhu）' : '8 卡拉卡（含 Rāhu）'}，共 ${ck.length} 行`,
			...gfmTable(['卡拉卡', '星曜', '本命落座', '用度'], ck.map((k)=>[
			`${k.karakaLabel || ''} ${k.karaka || ''}`, `${k.label || k.planet}`, `${k.signLabel || k.sign} ${fx(k.signlon, 2)}°`, `用度 ${fx(k.karakaDegree, 2)}°`,
		])),
		];
	}

	const nd = j.nodeRasiDrishti;
	if(Array.isArray(nd) && nd.length){
		out['节点主照（Rasi Drishti）'] = gfmTable(['给照', '受照'], nd.map((d)=>[`${d.giverLabel || d.giver}`, `${d.targetSignLabel || d.targetSign}`]));
	}

	const ps = j.strengths && j.strengths.planetaryStates;
	if(Array.isArray(ps) && ps.length){
		out['星曜状态'] = gfmTable(['星曜', '座度·宫', '庙旺态', '标记'], ps.map((s)=>{
			const flags = [];
			if(s.vargottama){ flags.push('Vargottama'); }
			if(s.retrograde){ flags.push('逆行'); }
			if(s.combust){ flags.push('燃烧'); }
			const baladi = s.baladi ? `·${s.baladi.label}` : '';
			const nak = s.nakshatra ? `·${s.nakshatra.name}P${s.nakshatra.pada}` : '';
			const lajj = Array.isArray(s.lajjitadi) && s.lajjitadi.length ? `·态[${s.lajjitadi.map((la)=>la.label).join('')}]` : '';
			return [`${s.label}`, `${s.signLabel || s.sign} ${fx(s.signlon, 1)}°·宫${s.house || '—'}`, `${s.dignity}${baladi}${lajj}${nak}`, `${flags.length ? flags.join('/') : ''}`];
		}));
	}

	// WP-E1 Vimśopaka（§5.7）：各 varga 组居自/友/旺的分盘数 → 吉位名(越多越吉)。
	const vd = j.strengths && j.strengths.vargaDignity;
	if(Array.isArray(vd) && vd.length){
		out['分盘吉位 Vimśopaka'] = gfmTable(['分盘（本盘）', '连座吉位'], vd.map((row)=>{
			const a = row.amsa || {};
			const parts = [];
			const grp = (label, g)=>{ const x = a[g]; if(x && x.count){ parts.push(`${label}${x.count}${x.amsa ? '·' + x.amsa : ''}`); } };
			grp('六', 'shadvarga'); grp('七', 'saptavarga'); grp('十', 'dasavarga'); grp('十六', 'shodasavarga');
			return [`${row.label}（本盘${row.d1}）`, `${parts.length ? parts.join(' ') : '无连座吉位'}`];
		}));
	}

	const av = j.ashtakavarga;
	if(av && av.available && Array.isArray(av.sarvaBySign)){
		const total = av.sarvaBySign.reduce((s, x)=>s + (x.bindu || 0), 0);
		// [v2 排版] 12 座 SAV 由单行并列改 GFM 表(单元格值表达式逐字同源:x.label/x.bindu);
		// 首行总点数摘要保持裸行不动(夹具锚 [0])。
		out['八分点 SAV'] = [
			`总点数 ${total}（标准 337）`,
			'| 星座 | 分值 |',
			'| --- | --- |',
			...av.sarvaBySign.map((x)=>`| ${x.label} | ${x.bindu} |`),
		];
	}

	// P0-6 Sodhya Pinda 凝量（削减后 BAV × 座/曜乘数）。
	if(av && av.sodhyaPinda){
		const PCN = { Sun: '日', Moon: '月', Mars: '火', Mercury: '水', Jupiter: '木', Venus: '金', Saturn: '土' };
		const spRows = ['Sun', 'Moon', 'Mars', 'Mercury', 'Jupiter', 'Venus', 'Saturn']
			.filter((p)=>av.sodhyaPinda[p])
			.map((p)=>[PCN[p], `${av.sodhyaPinda[p].total}`, `座${av.sodhyaPinda[p].rasiPinda}+曜${av.sodhyaPinda[p].grahaPinda}`]);
		if(spRows.length){ out['Sodhya Pinda 凝量'] = gfmTable(['曜', '凝量', '座+曜'], spRows); }
	}

	const sb = j.shadbala && j.shadbala.planets;
	if(Array.isArray(sb) && sb.length){
		// [YG 表化] 星×总力同构记录转 GFM 表(值表达式逐字复用;测试锚已随格式同步更新)。
		out['Shadbala 六力'] = [
			'| 星曜 | 总力 |',
			'| --- | --- |',
			...sb.map((x)=>`| ${x.label} | ${fx(x.totalRupa, 2)} Rupa |`),
		];
		// QW8 Ishta/Kashta（吉果/凶果）：仅在引擎给出时输出。
		const ik = sb.filter((x)=>x.ishta !== undefined && x.ishta !== null);
		if(ik.length){
			out['Ishta/Kashta 吉凶果'] = gfmTable(['星曜', '吉果', '凶果', '出曜力'], ik.map((x)=>[`${x.label}`, `吉果 ${fx(x.ishta, 1)}`, `凶果 ${fx(x.kashta, 1)}`, `出曜力 ${fx(x.uchchaBala, 1)}`]));
		}
	}

	// P0-8 Vimśopaka 分盘 20 分力（四组）。读 shadbalaBphs[planet].vimsopaka。
	const bphsAll = j.shadbalaBphs;
	if(bphsAll){
		const PCN = { Sun: '日', Moon: '月', Mars: '火', Mercury: '水', Jupiter: '木', Venus: '金', Saturn: '土' };
		const vpRows = ['Sun', 'Moon', 'Mars', 'Mercury', 'Jupiter', 'Venus', 'Saturn']
			.filter((p)=>bphsAll[p] && bphsAll[p].vimsopaka)
			.map((p)=>{ const v = bphsAll[p].vimsopaka; return [PCN[p], `六${v.shadvarga.total}`, `七${v.saptavarga.total}`, `十${v.dasavarga.total}`, `十六${v.shodasavarga.total}`]; });
		if(vpRows.length){ out['Vimśopaka 分盘 20 分力'] = gfmTable(['曜', '六', '七', '十', '十六'], vpRows); }
	}

	// P0-7 Hora 行星时（昼夜各 12 段，日出首段=当日 vara 主）。
	const mu = j.muhurta;
	if(mu && mu.horaTable && Array.isArray(mu.horaTable.rows) && mu.horaTable.rows.length){
		const fmt = (s)=>{ const m = String(s || '').match(/(\d{1,2}:\d{2})/); return m ? m[1] : (s || '—'); };
		out['Hora 行星时'] = gfmTable(['序主星', '起'], mu.horaTable.rows.map((r)=>[`${r.index}.${r.lordCN || r.lord}`, fmt(r.start)]));
	}

	// P1 Choghadia 民用择时（昼夜各 8 段，吉/凶）。
	if(mu && mu.choghadia && Array.isArray(mu.choghadia.rows) && mu.choghadia.rows.length){
		const fmt = (s)=>{ const m = String(s || '').match(/(\d{1,2}:\d{2})/); return m ? m[1] : (s || '—'); };
		const NAT = { good: '吉', bad: '凶' };
		out['Choghadia 民用择时'] = gfmTable(['时段', '吉凶', '起'], mu.choghadia.rows.map((r)=>[`${r.period === 'day' ? '昼' : '夜'}${r.index}.${r.cn}`, `${NAT[r.nature] || ''}`, fmt(r.start)]));
	}

	// §24.2 Panchaka 五忌 + Abhijit 须臾。
	if(mu && (mu.panchaka || mu.abhijit)){
		const lines = [];
		if(mu.panchaka){ lines.push(`Panchaka：${mu.panchaka.typeLabel}（余${mu.panchaka.remainder}，${mu.panchaka.isPanchaka ? '忌' : '吉'}）`); }
		if(mu.abhijit){ lines.push(`Abhijit：第 8 昼须臾${mu.abhijit.auspicious ? '·大吉' : '·周三不取'}`); }
		out['择时 Panchaka/Abhijit'] = lines;
	}

	// P1 Mūla 大运（Lagna Kendrādi Graha · 首轮年龄段）。
	const mula = j.dasha && j.dasha.mula;
	if(mula && mula.available && Array.isArray(mula.mahadashas) && mula.mahadashas.length){
		out['Mūla 大运'] = gfmTable(['主星', '宫', '年数'], mula.mahadashas.filter((m)=>m.round === 1)
			.map((m)=>[m.planetCN, `宫${m.house}`, `${m.years}年`]));
	}

	// P1 Sudarśana Chakra（3 轮·当前年）。
	const sudc = j.dasha && j.dasha.sudarshanaChakra;
	if(sudc && sudc.available && Array.isArray(sudc.rows)){
		const cur = sudc.rows.find((r)=>r.current);
		const scOut = gfmTable(['年', '日轮', '月轮', '升轮'], sudc.rows.map((r)=>[`年${r.year}${r.current ? '◀' : ''}`, `日${r.slLabel}`, `月${r.clLabel}`, `升${r.jlLabel}`]));
		if(cur){ scOut.unshift(`当前年${cur.year}：日轮${cur.slLabel}·月轮${cur.clLabel}·升轮${cur.jlLabel}（三处并读,全合最强）`); }
		out['Sudarśana Chakra 大运'] = scOut;
	}

	// P1 Naisargika 自然大运（7 曜固定 120 年 · 年龄段）。
	const naisargika = j.dasha && j.dasha.naisargika;
	if(naisargika && naisargika.available && Array.isArray(naisargika.periods) && naisargika.periods.length){
		out['Naisargika 自然大运'] = gfmTable(['曜', '年数', '年龄段', '起', '止'], naisargika.periods.map((p)=>[p.planetCN, `${p.years}年`, `${p.startAge}–${p.endAge}岁`, `${p.start || ''}`, `${p.end || ''}`]));
	}

	// P1 补充上升（含 Indu 财富上升）。
	const supL = j.supplementaryLagnas;
	if(supL && supL.available){
		const items = [supL.chandraLagna, supL.paakaLagna, supL.karakamsa, supL.swamsa, supL.induLagna, supL.varnadaLagna].filter((x)=>x && x.sign);
		if(items.length){
			out['补充上升（Supplementary Lagnas）'] = gfmTable(['上升', '座', '附注'], items.map((it)=>[`${it.label}`, `${it.signLabel || it.sign}`, `${it.key === 'induLagna' && it.sumKala ? `Kala和 ${it.sumKala}·第${it.stepS}座` : (it.key === 'varnadaLagna' && it.step ? `A${it.countLagna}/B${it.countHora}·N${it.step}` : '')}`]));
		}
	}

	// P2 Nāḍī · Bhrigu Bindu（Rahu/Moon 短弧中点）。
	const nadi = j.nadi;
	// [Q-393① 裁决 2026-09-18] 所绘为分盘时注明口径:Nāḍī 一组恒取 D1(引擎 Q-393② 已恒取 d1_chart),
	// 否则读者会以为它跟着所选分盘走。D1(缺省)不出此行 → 缺省快照字节不变。
	const nadiVargaNote = Number((j.engine || {}).chartnum || 1) !== 1
		? `Nāḍī 一组(BB / D150 / 同座合 / 木星推进)恒按 D1 本命盘绝对黄经计算,不随所绘分盘 D${Number((j.engine || {}).chartnum)} 漂移。`
		: '';
	if(nadi && nadi.available && nadi.bhriguBindu){
		const bb = nadi.bhriguBindu;
		const nk = bb.nakshatra || {};
		out['Nāḍī · Bhrigu Bindu 福点'] = [`${bb.signLabel || bb.sign}${nk.name ? '·' + nk.name + (nk.pada ? 'P' + nk.pada : '') : ''}（黄经 ${(+bb.lon).toFixed(2)}°）`].concat(nadiVargaNote ? [nadiVargaNote] : []);
	}
	if(nadi && nadi.available && nadi.d150 && nadi.d150.length){
		const PCN = { Sun: '日', Moon: '月', Mars: '火', Mercury: '水', Jupiter: '木', Venus: '金', Saturn: '土', Rahu: '罗', Ketu: '计', 'North Node': '罗', 'South Node': '计' };
		out['Nāḍī · D150 纳地盘'] = gfmTable(['曜', '纳地', '座'], nadi.d150.map((x)=>[PCN[x.planet] || x.planet, `第${x.nadiamsa}/150`, `${x.signLabel || x.sign}`]));
		// D2:Nadi 组合/交换/木星推进(结构层,断语字典待供源不臆造)
		if(Array.isArray(nadi.combinations) && nadi.combinations.length){
			out['Nāḍī · 行星组合(同座合)'] = nadi.combinations.map((c)=>`${c.signLabel}：${(c.planets || []).map((x)=>PCN[x] || x).join('+')}（${c.count} 曜）`);
		}
		if(Array.isArray(nadi.exchanges) && nadi.exchanges.length){
			out['Nāḍī · 星座交换'] = nadi.exchanges.map((ex)=>`${PCN[ex.a] || ex.a}(${ex.aSignLabel}) ⇄ ${PCN[ex.b] || ex.b}(${ex.bSignLabel})${ex.dualLord ? '·含双主宫' : ''}`);
		}
		if(nadi.jupiterProgression && Array.isArray(nadi.jupiterProgression.segments)){
			const jp = nadi.jupiterProgression;
			out['Nāḍī · 木星推进时间轴'] = [jp.ruleLabel].concat(
				jp.segments.slice(0, 12).map((sg)=>`${sg.startAge}-${sg.endAge}岁 ${sg.signLabel}${(sg.natalPlanets || []).length ? '（' + sg.natalPlanets.map((x)=>PCN[x] || x).join('、') + '）' : ''}`));
		}
	}
	// D2:Jaimini 三对法寿命(档位参考,标注版本)
	const ayurTP = j.jaimini && j.jaimini.ayurTriPair;
	if(ayurTP && ayurTP.available){
		out['Jaimini 三对法寿命'] = ayurTP.pairs.map((pr)=>`${pr.name}：${pr.verdictLabel}`)
			.concat([`三票多数：${ayurTP.bandLabel}`, ayurTP.note]);
	}
	// D2:Tripataki 宿距三旗(年盘)
	const triNak = j.tajaka && j.tajaka.tripatakiNak;
	if(triNak && triNak.available){
		const PCN2 = { Sun: '日', Moon: '月', Mars: '火', Mercury: '水', Jupiter: '木', Venus: '金', Saturn: '土', 'North Node': '罗', 'South Node': '计' };
		out['Tripataki 宿距三旗'] = gfmTable(['曜', '宿距', '旗', 'Tārā', '断'],
			triNak.rows.map((r)=>[PCN2[r.planet] || r.planet, `${r.distance}`, `${r.flag}`, r.taraLabel, r.verdict]));
	}
	// [Q-127/T-35] 三旗盘(opt-in 齿轮 tripataki):后端 jyotish.tripataki 此前快照零读者 → 逐月净分(有效吉−凶)按月心/土心各一行;仅开启才产段(缺省字节不变)。
	const triY = j.tripataki;
	if(triY && triY.available && triY.byCenter){
		const triRows = [];
		[['moon', '月心'], ['saturn', '土心']].forEach(([ck, cl])=>{
			const c = triY.byCenter[ck];
			if(c && c.available && Array.isArray(c.months) && c.months.length){
				// 🔴 skill 偏离（上游 bug 之二）：后端 tripataki.month_rows 的月序键是 `month`（astrostudy/india/tripataki.py:51），
				// 上游此处读 `m.index`（只在后端**入参** months 上存在）→ 每格都是「undefined:净分」。优先读 index（上游修键后零变化）、
				// 缺则读 month。
				triRows.push([cl, c.centerSign ? scS(c.centerSign) : '—', c.months.map((m)=>`${m.index !== undefined ? m.index : m.month}:${m.score ? m.score.net : '-'}`).join(' ')]);
			}
		});
		if(triRows.length){ out['Tripataki 三旗盘逐月净分'] = gfmTable(['中心', '座', '逐月净分(月序:有效吉−凶)'], triRows); }
	}

	// P2 Āyurdāya 寿命基础（Piṇḍāyu 度式贡献 + Nisargāyu;未施 haraṇa）。
	const ayu = j.ayurdaya;
	if(ayu && ayu.available && ayu.pindayu){
		const lines = [`基础 Piṇḍāyu：${ayu.pindayu.baseYears} 年（未施 haraṇa 减）`];
		(ayu.pindayu.contributions || []).forEach((c)=>{ lines.push(`${c.planetCN}：满${c.fullYears} → ${c.years} 年`); });
		if(ayu.nisargayu){ lines.push(`Nisargāyu 自然寿表 120 年（${(ayu.nisargayu.naturalYears || []).map((n)=>n.planetCN + n.years).join(' ')}）`); }
		if(ayu.amsayu){ lines.push(`Aṁśāyu（÷200·Bharaṇa）基础 ${ayu.amsayu.baseYears} 年（${(ayu.amsayu.contributions || []).map((c)=>c.planetCN + c.years + (c.multiplier > 1 ? '×' + c.multiplier : '')).join(' ')}）`); }
		if(ayu.harana && ayu.harana.available && Array.isArray(ayu.harana.profiles)){
			ayu.harana.profiles.forEach((p)=>{ lines.push(`haraṇa·${p.label}：${p.solarYears} 太阳年`); });
			if(ayu.haranaNisarga && Array.isArray(ayu.haranaNisarga.profiles)){
				ayu.haranaNisarga.profiles.forEach((p)=>{ lines.push(`Nisargāyu haraṇa·${p.label}：${p.solarYears} 太阳年`); });
			}
			if(ayu.amsayu && Array.isArray(ayu.amsayu.bharanaVariants)){
				lines.push('Aṁśāyu Bharaṇa 流派：' + ayu.amsayu.bharanaVariants.map((v)=>`${v.label.replace(/（[^）]*）/, '')}${v.baseYears}`).join(' · '));
			}
			const kr = ayu.harana.krurodaya;
			if(kr && kr.applies){ lines.push(`Krurodaya ${kr.planetCN} 升 Lagna${kr.mitigated ? '（吉星望减半）' : ''}：式A −${kr.formulaA}`); }
		}
		out['Āyurdāya 寿命基础'] = lines;
	}

	// D60 六十分盘吉凶（Krūra 恶段为凶）。
	// 特殊上升 BL/HL/GL/SL + Praṇapada(日出/出生太阳双变体)。
	const upagrahaObj = j.upagraha;
	const splag = upagrahaObj && upagrahaObj.specialLagnas;
	if(splag){
		const SPLSIGN = ['白羊','金牛','双子','巨蟹','狮子','处女','天秤','天蝎','射手','摩羯','水瓶','双鱼'];
		const flag = (l)=>{ const v = (((l % 360) + 360) % 360); return `${SPLSIGN[Math.floor(v / 30)]} ${(v % 30).toFixed(1)}°`; };
		const splRows = [];
		['bhavaLagna','horaLagna','ghatikaLagna','sreeLagna'].forEach((k)=>{ if(splag[k]){ splRows.push([`${splag[k].label}`, flag(splag[k].lon)]); } });
		if(splag.pranapada){
			splRows.push([`Praṇapada·日出太阳(BPHS)`, flag(splag.pranapada.variantSunrise)]);
			if(splag.pranapada.variantBirth !== undefined){ splRows.push([`Praṇapada·出生太阳(现代变体)`, flag(splag.pranapada.variantBirth)]); }
		}
		if(splRows.length){ out['特殊上升 Special Lagnas'] = gfmTable(['名', '位置'], splRows); }
	}

	const shashti = j.shashtiamsa;
	if(shashti && shashti.available && shashti.planets && shashti.planets.length){
		const SPCN = { Sun: '日', Moon: '月', Mars: '火', Mercury: '水', Jupiter: '木', Venus: '金', Saturn: '土', Rahu: '罗', Ketu: '计', 'North Node': '罗', 'South Node': '计' };
		out['D60 六十分盘吉凶'] = [
			...gfmTable(['曜', '分段', '座', '吉凶'], shashti.planets.map((x)=>[SPCN[x.planet] || x.planet, `第${x.segment}/60`, `${x.signLabel || x.sign}`, x.nature === 'malefic' ? '凶' : '吉'])),
			`合计 吉${shashti.beneficCount}·凶${shashti.maleficCount}`,
		];
	}

	// 分盘变体对照（D2/D3/D24/D30 各流派落座差异）。
	const vargaVar = j.vargaVariants;
	if(vargaVar && vargaVar.available && Array.isArray(vargaVar.charts)){
		const VPCN = { Sun: '日', Moon: '月', Mars: '火', Mercury: '水', Jupiter: '木', Venus: '金', Saturn: '土', Rahu: '罗', Ketu: '计', 'North Node': '罗', 'South Node': '计' };
		const vvRows = [];
		vargaVar.charts.forEach((ch)=>{
			const diff = (ch.planets || []).filter((r)=>r.differs);
			if(!diff.length){ return; }
			vvRows.push([`${ch.label}（${ch.variants.map((v)=>v.label).join('/')}）`, diff.map((r)=>`${VPCN[r.planet] || r.planet}${r.cells.map((c)=>c.signLabel).join('→')}`).join('，')]);
		});
		if(vvRows.length){ out['分盘变体对照'] = gfmTable(['分盘（流派）', '差异落座'], vvRows); }
	}

	// QW1 功能吉凶（按命主星落舍判每曜功能性质）。
	const fn = j.functionalNature && j.functionalNature.grahas;
	if(Array.isArray(fn) && fn.length){
		const FN_CN = { benefic: '功能吉', malefic: '功能凶', neutral: '功能中', yogakaraka: '瑜伽点', maraka: '马拉卡' };
		out['功能吉凶（Functional Nature）'] = gfmTable(['星曜', '功能性质', '主管宫', '标记'], fn.map((g)=>{
			const tags = [];
			if(g.isYogakaraka){ tags.push('Yogakaraka'); }
			if(g.isMaraka){ tags.push('Maraka'); }
			if(g.isBadhaka){ tags.push('Badhaka'); }
			const ruled = Array.isArray(g.housesRuled) && g.housesRuled.length ? `主${g.housesRuled.join('/')}宫` : '';
			return [`${g.planetLabel || g.planet}`, `${FN_CN[g.functionalNature] || g.functionalNature}`, ruled, `${tags.length ? tags.join('/') : ''}`];
		}));
	}

	// QW7 Bhava Bala（宫位力，12 宫排名 + 最强/最弱）。
	const bb = j.bhavaBala;
	if(bb && bb.available && Array.isArray(bb.houses) && bb.houses.length){
		// [v2 排版] 12 宫力量改 GFM 表(单元格值表达式逐字同源:h.house/fx(h.rupas,2)/h.rank);最强/最弱摘要保持裸行。
		const bl = [
			'| 宫位 | 力量 | 名次 |',
			'| --- | --- | --- |',
			...bb.houses.map((h)=>`| 第${h.house}宫 | ${fx(h.rupas, 2)} Rupa | ${h.rank} |`),
		];
		if(bb.strongest){ bl.push(`最强宫：第 ${bb.strongest} 宫`); }
		if(bb.weakest){ bl.push(`最弱宫：第 ${bb.weakest} 宫`); }
		out['宫位力（Bhava Bala）'] = bl;
	}

	// QW3 Graha Yuddha（星曜战，<1° 同宫近战）。
	const gy = j.grahaYuddha;
	if(gy && gy.available && Array.isArray(gy.pairs) && gy.pairs.length){
		out['星曜战（Graha Yuddha）'] = gfmTable(['胜负', '相距'], gy.pairs.map((pr)=>[
			`${(pr.winnerLabel || pr.winner)} 胜 ${(pr.loserLabel || pr.loser)}`, `相距 ${fx(pr.sepDeg, 2)}°`,
		]));
	}

	// QW10/11 扩展大运（8 条件 Nakshatra 大运 + Chara Jaimini）：仅列可用与首主星。
	const ed = j.extendedDashas;
	if(ed){
		const edRows = [];
		const cond = ed.conditional || {};
		Object.keys(cond).forEach((key)=>{
			const c = cond[key];
			if(!c){ return; }
			const fl = c.firstLord ? (c.firstLord.label || c.firstLord.key) : '—';
			edRows.push([`${c.label || key}`, `${c.totalYears || '?'} 年`, `${c.available ? '条件满足·启用' : '条件未满足·仅备览'}，首主星 ${fl}`]);
		});
		const edOut = edRows.length ? gfmTable(['大运', '年数', '状态·首主星'], edRows) : [];
		if(ed.chara && Array.isArray(ed.chara.mahadashas) && ed.chara.mahadashas.length){
			const first = ed.chara.mahadashas[0];
			edOut.push(`Chara（耆那 ${ed.chara.seedLabel || ed.chara.seed} 起·${ed.chara.direction === 'reverse' ? '逆' : '顺'}行）：首运 ${first.rasiLabel || first.rasi}（${first.years} 年）`);
		}
		if(edOut.length){ out['扩展大运（Conditional / Chara）'] = edOut; }
	}

	// QW4 Kartari 夹击格局。
	const kt = j.kartari;
	if(kt && kt.available && Array.isArray(kt.yogas) && kt.yogas.length){
		out['Kartari 夹击格局'] = gfmTable(['目标', '类型', '夹击'], kt.yogas.map((y)=>[`${y.targetLabel}`, `${y.typeLabel}`, `${(y.prevLabels || []).join('')} 夹 ${(y.nextLabels || []).join('')}`]));
	}
	// QW4 Sudarshana 三盘合参(命/日/月分别为上升)。
	const sdc = j.sudarshana;
	if(sdc && sdc.available && Array.isArray(sdc.rows) && sdc.rows.length){
		out['Sudarshana 三盘（命/日/月起）'] = gfmTable(['星曜', '命盘', '日盘', '月盘'], sdc.rows.map((r)=>[`${r.planetLabel}`, `命第${r.houseFromLagna}宫`, `日第${r.houseFromSun}宫`, `月第${r.houseFromMoon}宫`]));
	}

	// QW6 KP 六级细分 + 当令星(供 AI 择时/事项判定)。
	const kp = j.kp;
	if(kp){
		const kl = [];
		const rp = kp.rulingPlanets;
		if(rp && Array.isArray(rp.set) && rp.set.length){ kl.push(`当令星 Ruling Planets：${rp.set.join('、')}`); }
		const lv = kp.kpLevels;
		if(lv && typeof lv === 'object'){
			const lvRows = Object.keys(lv).filter((pk)=>lv[pk]).map((pk)=>{ const x = lv[pk]; return [pk, x.Nak, x.Sub, x.Prati, x.Sook, x.Praana, x.Deha]; });
			if(lvRows.length){ kl.push(...gfmTable(['星曜', 'Nak星', 'Sub子', 'Prati', 'Sook', 'Praana', 'Deha'], lvRows)); }
		}
		const csl = kp.cuspalSubLords;
		if(Array.isArray(csl) && csl.length){
			// [v2 排版] 12 宫头主星链改 GFM 表(单元格值表达式逐字同源:c.house/c.starLord/c.subLord;列名同 UI 星主/子主口径)。
			out['KP 宫头次主星 CSL'] = [
				'| 宫位 | 星主 | 子主 |',
				'| --- | --- | --- |',
				...csl.map((c)=>`| 第${c.house}宫 | ${c.starLord} | ${c.subLord} |`),
			];
		}
		const sig = kp.significators;
		if(sig && typeof sig === 'object'){
			const sl = Object.keys(sig).map((pk)=>[pk, `司宫 ${(sig[pk].ranked || []).join('·')}`]);
			if(sl.length){ out['KP 意义者 Significators'] = gfmTable(['星曜', '司宫'], sl); }
		}
		if(kl.length){ out['KP 六级细分 / 当令星'] = kl; }
	}

	// WP-G 敌友 复合五分(Pañcadhā Maitrī,非对称) — 古籍第6章。
	const gm = j.grahaMaitri;
	if(gm && gm.available && Array.isArray(gm.matrix) && gm.matrix.length){
		// [v2 排版] 星×星矩阵改 GFM 表(与 renderMaitriPanel 同构:行=本星/列=对方/自身格「—」;
		// 单元格值表达式逐字同源:planetLabel/compoundCn)。列头取 planetLabels,缺省由首行 cells 推导;
		// 任一行列数不齐则回退旧平铺行(防列错位)。
		const gmLabels = Array.isArray(gm.planetLabels) && gm.planetLabels.length
			? gm.planetLabels
			: ((gm.matrix[0] && gm.matrix[0].cells) || []).map((c)=>c.planetLabel);
		const gmAligned = gmLabels.length > 0 && gm.matrix.every((row)=>Array.isArray(row.cells) && row.cells.length === gmLabels.length);
		if(gmAligned){
			out['敌友（复合五分）'] = [
				`| 本星＼对方 | ${gmLabels.join(' | ')} |`,
				`| --- | ${gmLabels.map(()=>'---').join(' | ')} |`,
				...gm.matrix.map((row)=>`| ${row.planetLabel} | ${row.cells.map((c)=>(c.self ? '—' : (c.compoundCn || '—'))).join(' | ')} |`),
			];
		}else{
			out['敌友（复合五分）'] = gm.matrix.map((row)=>{
				const rel = (row.cells || []).filter((c)=>!c.self && c.compoundCn).map((c)=>`${c.planetLabel} ${c.compoundCn}`).join('、');
				return `${row.planetLabel} 看：${rel}`;
			});
		}
	}

	// WP-E4 行运 Gochara（从月 + 八分点 SAV/BAV + Sade Sati）→ AI 挂载。
	const goc = j.gochara;
	if(goc && goc.available && Array.isArray(goc.fromMoon) && goc.fromMoon.length){
		const sa = goc.saturnAfflictions || {};
		const ss = sa.sadeSati || {};
		const gmoRows = goc.fromMoon.map((it)=>{
			const av = it.av && it.av.savBindu !== undefined ? `SAV${it.av.savBindu}/BAV${it.av.bavBindu}` : '';
			return [`${it.planetLabel || it.planet}`, `${it.signLabel || ''} 从月第${it.house}宫`, `${(it.good || it.auspicious) ? '吉' : '凶'}${it.effective === false ? '(Vedha遮)' : ''}`, av];
		});
		const gmoOut = gfmTable(['星曜', '座·从月宫', '吉凶', '八分点'], gmoRows);
		if(ss.active){ gmoOut.unshift(`Sade Sati 进行中（${ss.phaseLabel || ss.phase || ''}）`); }
		out['行运 Gochara（从月·八分点）'] = gmoOut;
	}

	// WP-E2 化解（信息·非处方）→ AI 挂载。
	const rem = j.remedies;
	if(rem && Array.isArray(rem.table) && rem.table.length){
		out['化解（信息·非处方）'] = gfmTable(['曜', '宝石', '金属', '咒·守护'], rem.table.map((g)=>[`${g.planetCn || g.planet}`, `${g.gem}`, `${g.metal || ''}`, `${g.mantraCount ? '诵' + g.mantraCount : ''}${Array.isArray(g.deity) && g.deity.length ? '·守护' + g.deity.join('/') : ''}`]));
	}

	// 印占 P0 接 UI 同步进 AI 挂载:Argala / 座运 Rasi Dashas / 年盘强度·年内大运 / Gochara 从命。
	// （SIGN_CN_S / scS 两行已上提到函数开头 —— 见该处 🔴 skill 偏离注释。）
	const arg = j.arudha && j.arudha.argala;
	if(arg && typeof arg === 'object'){
		const argRows = Object.keys(arg).sort((a, b)=>(Number(a) - Number(b))).map((h)=>{
			const g = arg[h] || {};
			const net = g.netStronger === 'argala' ? '干涉占优' : (g.netStronger === 'virodha' ? '反制占优' : '势均');
			return [`第${h}宫`, net, `干涉${g.argalaCount || 0}/反制${g.virodhaCount || 0}`];
		});
		if(argRows.length){ out['Jaimini Argala 干涉'] = gfmTable(['宫位', '净势', '干涉/反制'], argRows); }
	}
	const rdj = j.rasiDasha;
	if(rdj){
		[['narayana', 'Narayana'], ['lagnaKendradi', 'Lagna-Kendradi'], ['sudasa', 'Sudasa'], ['drigdasa', 'Drig'], ['shoola', 'Shoola'], ['niryanaShoola', 'Niryana-Shoola'], ['kalachakra', 'Kalachakra'], ['taraLagna', 'Tara-Lagna'], ['sthira', 'Sthira-固定'], ['yogardha', 'Yogardha-平均'], ['manduka', 'Manduka-蛙跳']].forEach((pair)=>{
			const d = rdj[pair[0]];
			if(d && d.available !== false && Array.isArray(d.mahadashas) && d.mahadashas.length){
				const tbl = gfmTable(['座', '年数', '神'], d.mahadashas.slice(0, 12).map((m)=>[scS(m.rasi), `${fx(m.years, 1)}年`, `${m.deity || ''}`]));
				// [Q-125/T-33] Kālachakra「适用条件」开关此前只挂 applicability 对象、页面/快照零读者 → 写明主用/备览
				const ap = d.applicability;
				out[`座运·${pair[1]}`] = ap ? [tbl, `适用性(${ap.mode === 'navamsa_stronger' ? '月亮 navamsa 座强于 rasi 座才主用' : ap.mode || '通用'})：${ap.applicable === true ? '主用' : (ap.applicable === false ? '备览(条件不成立)' : '判据不足')}`] : tbl;
			}
		});
	}
	const tjj = j.tajaka;
	if(tjj){
		if(tjj.harshaBala){ out['Tajika Harsha Bala'] = gfmTable(['星曜', 'Harsha力'], Object.keys(tjj.harshaBala).map((pk)=>[pk, `${fx(tjj.harshaBala[pk].total, 1)}`])); }
		if(tjj.panchaVargeeyaBala){ out['Tajika Pancha-Vargeeya'] = gfmTable(['星曜', '五分力'], Object.keys(tjj.panchaVargeeyaBala).map((pk)=>[pk, `${fx((tjj.panchaVargeeyaBala[pk] || {}).total, 2)}`])); }
		if(tjj.dasas && tjj.dasas.mudda && tjj.dasas.mudda.available && Array.isArray(tjj.dasas.mudda.sequence)){
			out['Tajika Mudda 年运'] = gfmTable(['段', '天数'], tjj.dasas.mudda.sequence.map((m)=>[m.key, `${fx(m.days, 1)}天`]));
		}
	}
	const gocL = j.gochara && j.gochara.fromLagna;
	if(Array.isArray(gocL) && gocL.length){
		out['行运 Gochara（从命）'] = gfmTable(['星曜', '从命宫', '吉凶'], gocL.map((it)=>[`${it.planetLabel || it.label || it.planet}`, `从命第${it.house}宫`, `${(it.good || it.auspicious) ? '吉位' : '凶位'}`]));
	}

	// A 类硬缺：Yoga 面板成立清单（renderYogaPanel 已显示但此前不入快照）。只列成立项：
	// 名+类别+强弱分+涉及星（planetLabels），不带长释义；类别中文映射与 UI YOGA_CATEGORY_LABELS 一致（缺映射回退原键）。
	// 无数据/available=false → 不产段。
	const yg = j.yogas;
	if(yg && yg.available !== false && Array.isArray(yg.items) && yg.items.length){
		const YOGA_CAT_CN = {
			'Pancha Mahapurusha': '五大人瑜伽', Lunar: '月亮瑜伽', Solar: '太阳瑜伽', Raja: '王瑜伽',
			Dhana: '财富瑜伽', Viparita: '逆转王瑜伽', Parivartana: '交换瑜伽', Nabhasa: '形态瑜伽',
			Challenge: '挑战/煞', Support: '保护瑜伽', Association: '星体关联', Spiritual: '出离/灵性',
		};
		const sum = yg.summary || {};
		const ygRows = yg.items.map((it)=>{
			const disp = it.zhName && it.zhName !== it.name ? `${it.zhName}（${it.name}）` : (it.name || it.zhName || '—');
			const planets = Array.isArray(it.planetLabels) && it.planetLabels.length ? it.planetLabels.join('、') : '';
			return [disp, `${YOGA_CAT_CN[it.category] || it.category || '—'}`, `${it.levelLabel || it.level || '—'}`, `${it.score || 0}分`, `${planets ? '涉及 ' + planets : ''}`];
		});
		out['瑜伽格局 Yogas'] = [
			`命中 ${sum.total || yg.items.length} 个（强${sum.strong || 0}/中${sum.medium || 0}/弱${sum.weak || 0}）`,
			...gfmTable(['瑜伽', '类别', '强弱', '分', '涉及星'], ygRows),
		];
	}

	// A 类硬缺：副星本体位置（renderUpagrahaPanel 的 时基 Gulika/Maandi 等 + 日基）与外行星天海冥
	// （jyotish.outerPlanets，信息性虚星）已显示但此前不入快照；特殊上升已有独立段不重复。
	// upagraha.available 为假或三组皆空 → 不产段。
	const upg = j.upagraha;
	if(upg && upg.available){
		const UPG_SIGN = ['白羊', '金牛', '双子', '巨蟹', '狮子', '处女', '天秤', '天蝎', '射手', '摩羯', '水瓶', '双鱼'];
		const upgLon = (l)=>{ const v = (((l || 0) % 360) + 360) % 360; return `${UPG_SIGN[Math.floor(v / 30)]} ${(v % 30).toFixed(1)}°`; };
		const upLines = [];
		if(Array.isArray(upg.timeBased) && upg.timeBased.length){
			upLines.push('◆ 时基副星（Gulika/Maandi 等）');
			upLines.push(...gfmTable(['副星', '位置'], upg.timeBased.map((it)=>[`${it.key}`, `${upgLon(it.lon)}${it.note ? `（${it.note}）` : ''}`])));
		}
		if(Array.isArray(upg.sunBased) && upg.sunBased.length){
			upLines.push('◆ 日基副星');
			upLines.push(...gfmTable(['副星', '位置'], upg.sunBased.map((it)=>[`${it.key}`, `${upgLon(it.lon)}${it.note ? `（${it.note}）` : ''}`])));
		}
		const outerObj = j.outerPlanets;
		const outer = outerObj && outerObj.available && Array.isArray(outerObj.planets) ? outerObj.planets : [];
		if(outer.length){
			upLines.push('◆ 外行星 Ur/Ne/Pl（虚星·信息性，不入九曜强弱）');
			upLines.push(...gfmTable(['外行星', '座度', '宫', '宿'], outer.map((o)=>[`${o.label}`, `${o.signLabel || o.sign || '—'} ${fx(o.signlon, 1)}°${o.retrograde ? ' R' : ''}`, `宫${o.house || '—'}`, `${o.nakshatra ? `${o.nakshatra}P${o.pada}` : ''}`])));
		}
		if(upLines.length){ out['副星 Upagraha'] = upLines; }
	}

	// [G2/G3/G4] 敏感点(生育点/界位/风险因子仅标注)。降级态不出段(零噪音);绝不出寿数。
	const spx = j.sensitivePoints;
	if(spx && spx.available){
		const sl = [];
		const bk = spx.beejaKshetra || {};
		for(const [key, label] of [['beeja', 'Beeja 生育点(日+金+木)'], ['kshetra', 'Kshetra 生育点(月+火+木)']]){
			const it = bk[key];
			if(it && it.available){
				sl.push(`${label}：${(it.rasi || {}).signLabel || ''}（D9 ${(it.navamsa || {}).signLabel || ''}）· ${it.verdictLabel || ''}`);
			}
		}
		const gnd = (spx.gandanta || {}).hits || [];
		gnd.forEach((h)=>{
			const parts = [];
			if(h.gandanta){ parts.push(`Gandanta ${h.gandanta.junctionLabel} 距界 ${h.gandanta.arcminToBoundary}′`); }
			if(h.rasiSandhi){ parts.push(`Rasi Sandhi ${h.rasiSandhi.position === 'sign_end' ? '座末' : '座初'} ${h.rasiSandhi.arcminToBoundary}′`); }
			sl.push(`${h.bodyLabel || h.body}：${parts.join('；')}`);
		});
		const di = spx.deathIndicators;
		if(di && di.available){
			sl.push(`22nd Drekkana 主(自 Lagna)：${di.drekkana22.lordLabel}；64th Navamsa 主：自 Moon ${di.navamsa64FromMoon ? di.navamsa64FromMoon.lordLabel : '—'} / 自 Lagna ${di.navamsa64FromLagna ? di.navamsa64FromLagna.lordLabel : '—'}（仅风险标注,不构成任何寿命预测）`);
		}
		if(sl.length){ out['敏感点 Sphuta'] = sl; }
	}

	// [G7] 全吉盘:降级态只输出一句免责 —— 绝不把占位格位当权威喂给 AI。
	const sbc = j.sarvatobhadra;
	if(sbc && sbc.available){
		if(sbc.vedhaEnabled){
			out['全吉盘 SBC'] = (sbc.hits || []).length
				? sbc.hits.map((h)=>`${h.planet} 过运冲 ${h.ref}(第${h.refNak28}宿)`)
				: ['本命参照宿当前无凶星 Vedha 命中'];
		}else{
			out['全吉盘 SBC'] = ['SBC 经典环锚待录入,当前为占位布局,Vedha 判定未启用(不作任何克应结论)'];
		}
	}

	// [G1/G12] 问事 Praśna(仅已起卦时有 payload;裁决链逐条给 AI 作证据)。
	const pr = j.prashna;
	if(pr && pr.available){
		const pl2 = [`问事时刻：${pr.questionTime}；事项：${pr.matter}`];
		const kp2 = pr.kp;
		if(kp2 && kp2.available){
			const jj = kp2.judgement || {};
			pl2.push(`KP 问数 ${kp2.number}（宿主 ${(kp2.segment || {}).starLord} / 子主 ${(kp2.segment || {}).subLord}；宫始 ${kp2.cuspMode}）`);
			(jj.chain || []).forEach((c)=>pl2.push(c));
			const rp = (kp2.rulingPlanets || {}).set || [];
			if(rp.length){ pl2.push(`RP：${rp.join('、')}`); }
			(kp2.timingWindows || []).slice(0, 3).forEach((w)=>pl2.push(`应期候选：${w.levelName} ${w.lord} ${w.start}~${w.end}（分 ${w.score}）`));
		}
		if(pr.parashari && pr.parashari.available){
			const pa = pr.parashari;
			pl2.push(`Parāśarī：问时 Lagna ${((pa.lagna || {}).signLabel) || ''}；Tārā ${(pa.taraBala || {}).name || '—'}；Chandra 第${(pa.chandraBala || {}).house || '—'}宫`);
		}
		if(pr.tajika && pr.tajika.available){
			const tj2 = pr.tajika;
			const it2 = tj2.ithasala;
			pl2.push(`Tājika：Lagna主 ${tj2.lagnaLord || '—'} × 事项主 ${tj2.karyaLord || '—'} → ${it2 ? (it2.type === 'eesarpha' ? '离相不成' : `入相 ${it2.type || ''}`) : (tj2.selfLordNote || '无相位')}`);
		}
		out['问事 Praśna'] = pl2;
	}



	// 寿命判读(Ayurdaya 判读层):方法选定/并入总值+档位/三对法/致死因子/投影(带免责)。
	const af = j.ayurdayaFinal;
	if(af && af.available){
		const al = [];
		const M_CN = { pindayu: 'Pindayu', nisargayu: 'Nisargayu', amsayu: 'Amsayu' };
		const sel = af.methodSelection || {};
		al.push(`选定方法：${M_CN[sel.selected] || sel.selected || '—'}${sel.override === 'auto' ? '（自动:最强定法;上升以其主代比,平局取上升）' : '（手动指定）'}`);   // [Q-393①/T-375] 注明代比与平局规则
		if(af.selectedFinal && af.selectedFinal.solarYears != null){
			al.push(`并入减算总值：${af.selectedFinal.solarYears} 太阳年（${af.selectedFinal.savanaYears} Savana）`);
		}
		if(af.ayuClass){ al.push(`寿命档：${af.ayuClass.label}`); }
		if(af.triPairYears != null){
			const v = af.triPairVotes || {};
			al.push(`三对法离散寿数：${af.triPairYears} 年（长${v.purna || 0}/中${v.madhya || 0}/短${v.alpa || 0}）`);
		}
		if(af.maraka){
			al.push(`Maraka 因子：${(af.maraka.lords || []).join('/') || '—'}${(af.maraka.occupants || []).length ? `（落宫 ${(af.maraka.occupants || []).join('/')}）` : ''}`);
		}
		if(af.trishula){ al.push(`Trishula 座：${(af.trishula.signs || []).join('/')}`); }
		if(af.drekkana22){ al.push(`22nd Drekkana：${af.drekkana22.sign} · 主 ${af.drekkana22.lord || '—'}`); }
		if(af.navamsa64){ al.push(`64th Navamsa：${af.navamsa64.sign} · 主 ${af.navamsa64.lord || '—'}`); }
		if(af.projection && af.projection.mahaLord){
			const pj = af.projection;
			al.push(`寿龄投影：${(pj.mahaLord || {}).label || '—'} 大运${pj.mahaIsMaraka ? '（maraka 命中）' : ''}${pj.antarLord ? ` / ${(pj.antarLord || {}).label} 中运` : ''}`);
		}
		al.push(`※ ${af.disclaimer || '仅信息·非处方'}`);
		out['寿命判读'] = al;
	}

	return out;
}

// ── [大运Dasha] 体系切换：IndiaChart.js:298-494 逐字 ──
// Vimshottari 大运（120 年周期）：后端 jyotish.dasha.vimshottari 已算好，挂载快照一并输出。
// 字段形态与命盘 Dasha 面板(buildVimshottariDasha)一致;无数据则返回空(快照跳过该段)。
const DASHA_SYSTEM_SNAPSHOT_LABEL = {
	vimshottari: 'Vimshottari（120 年周期）',
	yogini: 'Yogini（36 年 · 8 女神）',
	ashtottari: 'Ashtottari（108 年 · Ardradi）',
	tribhagi: 'Tribhāgī（Vimśottarī÷3 · 3 遍×40=120 年）',
	shodashottari: 'Shodashottari（116 年 · 条件）',
	dvadashottari: 'Dvadashottari（112 年 · 条件）',
	panchottari: 'Panchottari（105 年 · 条件）',
	shatabdika: 'Shatabdika（100 年 · 条件）',
	chaturashitiSama: 'Chaturashiti-sama（84 年 · 条件）',
	dwisaptatiSama: 'Dwisaptati-sama（72 年 · 条件）',
	shashtihayani: 'Shashtihayani（60 年 · 条件）',
	shattrimshaSama: 'Shattrimsha-sama（36 年 · 条件）',
	chara: 'Chara 耆那星座大运（Jaimini · 按座推）',
	taraDasha: 'Tāra 大运（kendra 强度序 · Vimshottari 年表）',
	akkg: 'AKKG（Karaka Kendradi Graha · AK 播种）',
};

// 出生时刻(本地钟表时)轻量解析:仅供扩展大运快照推日期;BC(ad=0)或缺字段 → null(段退化为无日期序列)。
function snapshotBirthDate(fields){
	if(!fields || !fields.date || !fields.time || !fields.date.value || !fields.time.value){ return null; }
	if(fields.ad && fields.ad.value !== undefined && Number(fields.ad.value) === 0){ return null; }
	const d = fields.date.value, t = fields.time.value;
	if(!d.format || !t.format){ return null; }
	const dt = new Date(`${d.format('YYYY-MM-DD')}T${t.format('HH:mm:ss')}`);
	return Number.isFinite(dt.getTime()) ? dt : null;
}

// Chara/8 条件宿系大运的快照段:后端只给年数序列(extendedDashas),日期与右栏组树同口径
// (条件系 start = birth − firstElapsedYears;chara 自出生起逐段累加;年长同 vimshottari.yearLengthDays)。
function buildExtendedDashaSnapshotLines(chartObj, sys, fields){
	const j = chartObj && chartObj.jyotish;
	const ed = j && j.extendedDashas;
	if(!ed){ return []; }
	const yearDays = (j.dasha && j.dasha.vimshottari && Number(j.dasha.vimshottari.yearLengthDays)) || 365.25;
	const birth = snapshotBirthDate(fields);
	const dayMs = 86400000;
	// 本地切日(与解析同时区自洽,亦与右栏 moment 组树同口径);toISOString 的 UTC 切日会偏一天。
	const fmt = (ms)=>{
		const d = new Date(ms);
		const p = (x)=>String(x).padStart(2, '0');
		return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
	};
	const nowMs = Date.now();
	const out = [];
	const pushSeq = (rows)=>{
		out.push('大运序列：');
		out.push('| 主 | 年数 | 起 | 讫 |');
		out.push('| --- | --- | --- | --- |');
		rows.forEach((r)=>out.push(`| ${r.name}${r.active ? '（当前）' : ''} | ${r.years} | ${r.start} | ${r.end} |`));
	};
	if(sys === 'chara'){
		const c = ed.chara;
		if(!c || !Array.isArray(c.mahadashas) || !c.mahadashas.length){ return []; }
		out.push(`系统：${DASHA_SYSTEM_SNAPSHOT_LABEL.chara}`);
		out.push(`起座：${c.seedLabel || c.seed || '—'}（${c.direction === 'reverse' ? '逆推' : '顺推'}）`);
		let cur = birth ? birth.getTime() : null;
		pushSeq(c.mahadashas.map((m)=>{
			const years = m.years || 0;
			let startS = '—', endS = '—', active = false;
			if(cur !== null){
				const end = cur + years * yearDays * dayMs;
				active = nowMs >= cur && nowMs < end;
				startS = fmt(cur); endS = fmt(end);
				cur = end;
			}
			return { name: m.rasiLabel || m.rasi, years: `${years}`, start: startS, end: endS, active };
		}));
		return out;
	}
	const c = ed.conditional && ed.conditional[sys];
	if(!c || !Array.isArray(c.mahadashas) || !c.mahadashas.length){ return []; }
	out.push(`系统：${DASHA_SYSTEM_SNAPSHOT_LABEL[sys] || c.label || sys}`);
	const nameOfLord = (lord)=>(lord && (lord.label || lord.key)) || '—';
	out.push(`首运：${nameOfLord(c.firstLord)}（已历 ${(+c.firstElapsedYears || 0).toFixed(1)} 年、余 ${(+c.firstBalanceYears || 0).toFixed(1)} 年）`);
	let cur = birth ? (birth.getTime() - (+c.firstElapsedYears || 0) * yearDays * dayMs) : null;
	pushSeq(c.mahadashas.map((m, i)=>{
		// 起点是 cycle_start(出生−已历),故每段(含首段)一律满期年;首段取余额会令整轴前移。
		const years = (m.fullYears != null ? m.fullYears : m.years) || 0;
		let startS = '—', endS = '—', active = false;
		if(cur !== null){
			const end = cur + years * yearDays * dayMs;
			active = nowMs >= cur && nowMs < end;
			startS = fmt(cur); endS = fmt(end);
			cur = end;
		}
		const yearsS = (i === 0 && m.balance) ? `${years}（含出生前已历 ${(+c.firstElapsedYears || 0).toFixed(1)} 年）` : `${years}`;
		return { name: nameOfLord(m.lord), years: yearsS, start: startS, end: endS, active };
	}));
	return out;
}

// [#80] 小运(Antardasha)全展:此前只在「当前大运」里挑出当下这一支,其余八个大运的小运
// 后端本就随每个 mahadasha 一并返回(IndiaChartMain 逐条渲染在用),快照却整片不出 ——
// AI 因此答「没有完整的 Dasha 表」。9×9=81 行 ≈4 千字,在挂载预算内;超上限则截断并明说截了。
export const DASHA_ANTAR_ROW_MAX = 120;
export function buildAntardashaTableLines(mahadashas, helpers){
	const list = Array.isArray(mahadashas) ? mahadashas : [];
	const { nameOf, fmtDate, n1 } = helpers || {};
	if(!list.length || typeof nameOf !== 'function'){
		return [];
	}
	const now = Date.now();
	const rows = [];
	let truncated = false;
	list.forEach((m)=>{
		if(!m || !Array.isArray(m.antardashas) || !m.antardashas.length){ return; }
		m.antardashas.forEach((a)=>{
			if(!a){ return; }
			if(rows.length >= DASHA_ANTAR_ROW_MAX){ truncated = true; return; }
			const st = a.start ? new Date(a.start).getTime() : NaN;
			const en = a.end ? new Date(a.end).getTime() : NaN;
			const live = Number.isFinite(st) && Number.isFinite(en) && st <= now && now < en;
			rows.push(`| ${live ? '▶' : (m.active ? '·' : '')} | ${nameOf(m.lord)} | ${nameOf(a.lord)} | ${fmtDate(a.start)} | ${fmtDate(a.end)} | ${n1(a.years).toFixed(1)} 年 |`);
		});
	});
	if(!rows.length){
		return [];
	}
	const out = ['小运序列(Antardasha,全大运展开;▶=当下、·=当前大运内):',
		'| 标记 | 大运主星 | 小运主星 | 起 | 止 | 年数 |',
		'| --- | --- | --- | --- | --- | --- |',
		...rows];
	if(truncated){
		out.push(`（小运行数超过 ${DASHA_ANTAR_ROW_MAX} 已截断;未列出的不代表不存在,勿臆补。）`);
	}
	return out;
}

function buildDashaSnapshotLines(chartObj, system, fields){
	const sys = AstroConst.normalizeIndiaDashaSystem(system);
	const j = chartObj && chartObj.jyotish;
	const ed = j && j.extendedDashas;
	// chara/条件系:树在 extendedDashas(引擎 4 树以外),快照与右栏所见同体系(账实一致)。
	if(sys === 'chara' || (ed && ed.conditional && ed.conditional[sys])){
		const extLines = buildExtendedDashaSnapshotLines(chartObj, sys, fields);
		if(extLines.length){ return extLines; }
	}
	const dashaRoot = chartObj && chartObj.jyotish && chartObj.jyotish.dasha;
	// AKKG:平铺形状(planetCN/years/cycle/start/end,无 lord 树)→ 专段(勿走 4 树表,否则全 '—')。
	if(sys === 'akkg'){
		const a = dashaRoot && dashaRoot.akkg;
		if(a && a.available && Array.isArray(a.mahadashas) && a.mahadashas.length){
			const out = [];
			out.push(`系统：${DASHA_SYSTEM_SNAPSHOT_LABEL.akkg}`);
			out.push(`Ātmakāraka：${a.atmakaraka || '—'}（座 ${a.seedSign || '—'}）`);
			out.push('大运序列：');
			out.push('| 主 | 轮 | 年数 | 起 | 讫 |');
			out.push('| --- | --- | --- | --- | --- |');
			a.mahadashas.forEach((m)=>{
				out.push(`| ${m.planetCN || m.planet} | ${m.cycle} | ${m.years} | ${m.start || '—'} | ${m.end || '—'} |`);
			});
			return out;
		}
		return [];
	}
	const v = dashaRoot && (dashaRoot[sys] || dashaRoot.vimshottari);
	if(!v || !v.available || !Array.isArray(v.mahadashas) || !v.mahadashas.length){
		return [];
	}
	const nameOf = (lord)=>(lord && (lord.label || lord.key)) || '—';
	const fmtDate = (d)=>{ const s = `${d || ''}`; const m = s.match(/^(\d{4}-\d{2}-\d{2})/); return m ? m[1] : (s || '—'); };
	const n1 = (x)=>(Number.isFinite(+x) ? (+x) : 0);
	const out = [];
	const nak = v.moonNakshatra || {};
	out.push(`系统：${DASHA_SYSTEM_SNAPSHOT_LABEL[sys] || DASHA_SYSTEM_SNAPSHOT_LABEL.vimshottari}`);
	out.push(`月宿：${nak.label || nak.name || nak.key || '—'}（宿主星 ${nameOf(v.firstLord)}）`);
	out.push(`首运：已历 ${n1(v.firstElapsedYears).toFixed(1)} 年、余 ${n1(v.firstBalanceYears).toFixed(1)} 年`);
	const active = v.mahadashas.find((m)=>m && m.active);
	if(active){
		out.push(`当前大运（Mahadasha）：${nameOf(active.lord)}（${fmtDate(active.start)} → ${fmtDate(active.end)}，${n1(active.startAge).toFixed(0)}–${n1(active.endAge).toFixed(0)} 岁）`);
		if(Array.isArray(active.antardashas) && active.antardashas.length){
			const now = new Date();
			const sub = active.antardashas.find((s)=>{
				if(!s || !s.start || !s.end){ return false; }
				const st = new Date(s.start); const en = new Date(s.end);
				return st <= now && now < en;
			});
			if(sub){
				out.push(`当前小运（Antardasha）：${nameOf(sub.lord)}（${fmtDate(sub.start)} → ${fmtDate(sub.end)}）`);
			}
		}
	}
	out.push('大运序列：');
	// [v2 排版] 平铺大运时间表改 GFM 表(经归一器直通、docx/PDF 渲染真表)。
	// 单元格值表达式逐字同源:nameOf/fmtDate/n1;标记列 ▶=当前、·=出生余量(原行首标记原义)。
	out.push('| 标记 | 主星 | 起 | 止 | 年数 | 年龄段 |');
	out.push('| --- | --- | --- | --- | --- | --- |');
	v.mahadashas.forEach((m)=>{
		const mark = m.active ? '▶' : (m.birthBalance ? '·' : '');
		out.push(`| ${mark} | ${nameOf(m.lord)} | ${fmtDate(m.start)} | ${fmtDate(m.end)} | ${n1(m.years).toFixed(1)} 年 | ${n1(m.startAge).toFixed(0)}–${n1(m.endAge).toFixed(0)} 岁 |`);
	});
	out.push(...buildAntardashaTableLines(v.mahadashas, { nameOf, fmtDate, n1 }));
	return out;
}

// ── [起盘信息] 流派 / 分盘头行：IndiaChart.js:149-170 逐字 ──
function resolveIndiaFractal(chartnum, hook){
	let fractal = parseInt(chartnum, 10);
	if(Number.isNaN(fractal) || fractal <= 0){
		if(hook && hook.fractal){
			fractal = parseInt(hook.fractal, 10);
		}
	}
	if(Number.isNaN(fractal) || fractal <= 0){
		fractal = 1;
	}
	return fractal;
}

function resolveIndiaLabel(fractal, hook){
	if(hook && hook.txt){
		return hook.txt;
	}
	if(fractal === 1){
		return '命盘';
	}
	return `${fractal}分盘`;
}

// buildIndiaSnapshotText（:1131-1194）起首的流派/分盘四行（:1154-1177 内联逐字；ensureSection 的第三参数组收成返回值）。
export function buildIndiaSchoolHeaderLines(fields, chartnum, hook){
	const fractal = resolveIndiaFractal(chartnum, hook);
	const label = resolveIndiaLabel(fractal, hook);
	const schoolVal = fields && fields.indiaSchool && fields.indiaSchool.value
		? AstroConst.normalizeIndiaSchool(fields.indiaSchool.value) : AstroConst.INDIA_SCHOOL_DEFAULT;
	const schoolDef = AstroConst.getIndiaSchoolDefaults(schoolVal) || {};
	const schoolOpt = AstroConst.INDIA_SCHOOL_OPTIONS.find((o)=>o.value === schoolVal) || {};
	const PARA_CN = { graha: '七政相映', rasi: '星座相位', tajika: 'Tajika 容许度', kp: 'significator 链', nadi: '同座/交换' };
	const DF_CN = { vimshottari: 'Vimshottari', chara: 'Chara', mudda: 'Mudda(年内)', jupiterProgression: '木星推进' };
	const variantMap = AstroConst.normalizeIndiaDashaVariants(
		fields && fields.indiaDashaVariants ? fields.indiaDashaVariants.value : null);
	const variantKeys = Object.keys(variantMap).sort();
	const variantLine = variantKeys.length
		? [`大运流派开关：已自定义 ${variantKeys.length} 项（${variantKeys.map((k)=>{
			const spec = AstroConst.INDIA_DASHA_VARIANT_SPECS.find((it)=>it.key === k) || {};
			const opt = (spec.options || []).find((o)=>o.value === variantMap[k]) || {};
			return `${spec.label || k}=${(opt.label || variantMap[k]).replace(/（.*?）/g, '')}`;
		}).join('、')}）`]
		: [];
	return [
		`流派：${schoolOpt.label || schoolVal}（相位范式 ${PARA_CN[schoolDef.aspectParadigm] || schoolDef.aspectParadigm || '七政相映'} · 主运取向 ${DF_CN[schoolDef.dashaFocus] || 'Vimshottari'}）`,
		...variantLine,
		`当前分盘：${label}`,
		`分盘：D${fractal}`,
	];
}

// ── [起盘信息] 印占实际口径行：IndiaChart.js:1109-1129 逐字（v3.11 wave3b）──
// [挂载自检 F-39·P0] 印占实际口径行:盘按恒星黄道(印占岁差)+ 印度分宫制算,但 buildAstroSnapshotContent 读的是
// fields.zodiacal/hsys(印占 fields 恒 0/1)→ [起盘信息] 印「回归黄道，Alcabitus」与实算相反。与 fieldsToParams 同一派生。
export function indiaCalibreLine(fields, overrides = {}){
	const f = fields || {};
	const hsysVal = overrides.indiaHsys !== undefined && overrides.indiaHsys !== null
		? AstroConst.normalizeIndiaHouseSystem(overrides.indiaHsys)
		: (f.indiaHsys ? AstroConst.normalizeIndiaHouseSystem(f.indiaHsys.value) : AstroConst.INDIA_HOUSE_SYSTEM_DEFAULT);
	const ayan = overrides.indiaAyanamsa !== undefined && overrides.indiaAyanamsa !== null
		? AstroConst.normalizeIndiaAyanamsa(overrides.indiaAyanamsa)
		: (f.indiaAyanamsa ? AstroConst.normalizeIndiaAyanamsa(f.indiaAyanamsa.value) : AstroConst.INDIA_AYANAMSA_DEFAULT);
	const hit = AstroConst.INDIA_HOUSE_SYSTEM_OPTIONS.find((o)=>`${o.value}` === `${hsysVal}`);
	return `${AstroConst.zodiacalDisplayText(1, ayan)}，${hit ? hit.label : `分宫制 ${hsysVal}`}`;
}
export function replaceIndiaCalibreLine(baseInfoLines, calibreLine){
	const lines = Array.isArray(baseInfoLines) ? baseInfoLines.slice() : [];
	const idx = lines.findIndex((l)=>/^(回归黄道|恒星黄道)/.test(`${l}`.trim()));
	if(idx >= 0){ lines[idx] = calibreLine; }else if(calibreLine){ lines.push(calibreLine); }
	return lines;
}

export { buildDashaSnapshotLines };
