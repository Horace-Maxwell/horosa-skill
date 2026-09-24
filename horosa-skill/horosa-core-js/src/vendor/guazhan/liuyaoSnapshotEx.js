// AI 快照扩展段构建:与 liuyaoStructLines 同源取数(analyzeLiuyao 单一真值源),产 [断诀命中]/[占类断语] 两段。
// 🔴 取数逻辑与 GuaZhanMain.liuyaoStructLines / getLiuyaoAnalysis 三处同口径(年界线/hourZhi 扩展含在内),
// 任一处改动须同步(单测 liuyaoDuanJue.test 抵着引擎,本文件只做包装)。
import { Gua64 } from '../gua/GuaConst.js';
import { analyzeLiuyao } from '../gua/liuyaoFacade.js';
import { normalizeLiuyaoSettings } from '../gua/liuyaoSchools.js';
import { guaLoreOf } from '../gua/data/tianjiGuaLore.js';
import { getDoctrine, doctrineSummaryFor } from '../gua/data/liuyaoDoctrineCache.js';

export function buildSnapshotAnalysis(st){
	try{
		const nowGua = st && st.currentGua !== null && st.currentGua !== undefined && Gua64[st.currentGua] ? Gua64[st.currentGua] : null;
		const yao = (st && st.yao) || [];
		if(!nowGua || !(yao.length === 6 && yao.every((y)=>y && (y.value === 0 || y.value === 1)))){ return null; }
		const nongli = (st && st.nongli) || {};
		const settings = normalizeLiuyaoSettings(st && st.liuyaoSettings);
		const yearGz = `${(settings.yearBoundary === 'lunar'
			? (nongli.yearGZByLunar || nongli.yearGanZi || nongli.yearJieqi)
			: (nongli.yearJieqi || nongli.yearGanZi || nongli.yearGZByLunar)) || nongli.year || ''}`.trim();
		const monthGz = `${nongli.monthGanZi || ''}`.trim();
		const dayGz = `${nongli.dayGanZi || ''}`.trim();
		const hourGz = `${nongli.timeGanZi || nongli.hourGanZi || ''}`.trim();
		const ctx = {
			dayGan: dayGz.length >= 2 ? dayGz[0] : null, dayZhi: dayGz.length >= 2 ? dayGz[1] : null,
			monthGan: monthGz.length >= 2 ? monthGz[0] : null, monthZhi: monthGz.length >= 2 ? monthGz[1] : null,
			// 月建索引(寅=正月=1):月令神煞/月建六神起例——AI 快照 ctx 此前也缺,导致导出侧同样空转,与显示对齐补上。
			monthNum: (['寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥', '子', '丑'].indexOf(monthGz.length >= 2 ? monthGz[1] : '') + 1) || null,
			yearGan: yearGz.length >= 2 ? yearGz[0] : null, yearZhi: yearGz.length >= 2 ? yearGz[1] : null,
			hourZhi: hourGz.length >= 2 ? hourGz[1] : null,
			jieqiName: `${nongli.jieqi || nongli.jieqiName || ''}`.trim() || null,
		};
		const moving = [];
		yao.forEach((y, i)=>{ if(y.change){ moving.push(i + 1); } });
		const a = analyzeLiuyao(nowGua, moving, ctx, settings);
		if(a){ a.gua = a.gua || { name: nowGua.name }; }
		return a || null;
	}catch(e){
		return null;
	}
}

export function duanJueLines(a){
	const out = ['[断诀命中]'];
	if(!a){ return out; }
	const e = a.env || {};
	out.push(`三层环境：太岁${e.taiSui || '—'}(岁破${e.suiPo || '—'})　月建${e.yueJian || '—'}(月破${e.yuePo || '—'})　日建${e.riZhi || '—'}(日破${e.riPo || '—'})`);
	// [X1] 开局信息与显示同源补齐:日辰纳音(断诀页开局卡显示,此前 AI 不见)。
	if(a.nayinDay){ out.push(`日辰纳音：${a.nayinDay.name}(${a.nayinDay.wuxing})`); }
	// [X1] 装卦「余气强」(settings.yuqi 开时逐爻标注,断诀/装卦表显示):
	if(Array.isArray(a.yaos)){
		const yq = a.yaos.filter((y)=>y && y.yuqiStrong).map((y)=>`第${y.pos}爻${y.zhi}`);
		if(yq.length){ out.push(`余气强：${yq.join('、')}(月建余气助之)`); }
	}
	// 典籍补齐派生(与显示层「世应·卦变·动态·间爻」同源):
	if(a.shiYingRel){ out.push(`世应关系：世${a.shiYingRel.shiPos}(${a.shiYingRel.shiYao.liuqin}${a.shiYingRel.shiYao.zhi})${a.shiYingRel.rel || '—'}应${a.shiYingRel.yingPos}(${a.shiYingRel.yingYao.liuqin}${a.shiYingRel.yingYao.zhi})${a.shiYingRel.bothVoid ? '·世应俱空' : ''}${a.shiYingRel.note ? '·' + a.shiYingRel.note : ''}`); }
	if(a.guaBianDuan){ out.push(`卦变：${a.guaBianDuan.ben}→${a.guaBianDuan.bian}·${a.guaBianDuan.duan}`); }
	if(a.dongTai){ out.push(`动态：${a.dongTai.tai}(${a.dongTai.count}爻动)${a.dongTai.note ? '·' + a.dongTai.note : ''}`); }
	if(a.jianYao && a.jianYao.length){ out.push(`间爻：${a.jianYao.map((j) => `第${j.pos}爻${j.liuqin}`).join('、')}(世应之间·中介/媒人/第三方)`); }
	if(a.shiShen){ out.push(`世身：第${a.shiShen.pos}爻 ${a.shiShen.zhi}${a.shiShen.wuxing}${a.shiShen.liuqin}`); }
	// 日月生克逐爻(古法以日月为最重要外力):日辰/月建 对每爻 生扶克制冲合刑值墓。显示层新加,AI 同源补齐。
	if(a.riYue && a.riYue.perYao){
		const ry = a.riYue.perYao.filter((p)=>(p.day.tags.length || p.month.tags.length)).map((p)=>{
			const d = p.day.tags.map((t)=>t.t).join('');
			const m = p.month.tags.map((t)=>t.t).join('');
			return `第${p.pos}爻${p.gan}${p.zhi}${p.liuqin}[日:${d || '平'}·月:${m || '平'}]`;
		});
		if(ry.length){ out.push(`日月生克：${ry.join('　')}`); }
	}
	if(a.shenShaEx && a.shenShaEx.perYao){
		const ss = a.shenShaEx.perYao.filter((p)=>p.shensha.length).map((p)=>`第${p.pos}爻(${p.zhi}):${p.shensha.join('·')}`);
		if(ss.length){ out.push(`扩展/月令神煞：${ss.join('　')}`); }
	}
	if(a.yueLiuShenAnn && a.yueLiuShenAnn.perYao){
		const yl = a.yueLiuShenAnn.perYao.filter((p)=>p.hits.length).map((p)=>`第${p.pos}爻:${p.hits.join('·')}`);
		if(yl.length){ out.push(`月建六神：${yl.join('　')}`); }
	}
	const dj = a.duanJue;
	if(dj){
		if(dj.anDong && dj.anDong.length){ out.push(`暗动：${dj.anDong.map((p)=>`第${p}爻`).join('、')}`); }
		// [X1] 通例命中与断诀页同源补齐(此前显示有而 AI 不见):日破冲散/承刚/泄气/金锁八要素。
		if(dj.chongSan && dj.chongSan.length){ out.push(`日破冲散：${dj.chongSan.map((p)=>`第${p}爻`).join('、')}`); }
		if(dj.chengGang && dj.chengGang.length){ out.push(`承刚：${dj.chengGang.map((p)=>`第${p}爻`).join('、')}(阴居阳下)`); }
		(dj.xieQi || []).forEach((x)=>out.push(`泄气：第${x.pos}爻${x.duan}`));
		if(dj.jinSuoShi && dj.jinSuoShi.length){
			const on = dj.jinSuoShi.filter((el)=>el.on).map((el)=>el.k);
			out.push(`金锁八要素(世)：${on.length ? `命中 ${on.join('·')}` : '八项皆平'}`);
		}
		(dj.jueSheng || []).forEach((j)=>out.push(`绝处逢生：第${j.pos}爻${j.liuqin}(动爻${j.savers.join('/')}生之)`));
		(dj.heChong || []).forEach((j)=>out.push(`合处逢冲：第${j.pos}爻${j.liuqin}被日${j.by}`));
		if(dj.suiGuan){ out.push(`随鬼入墓：${dj.suiGuan.hits.map((h)=>`${h.kind}(第${h.pos}爻)`).join('、')}${dj.suiGuan.shaMu ? '·杀墓' : ''}`); }
		if(dj.zhuGui){ out.push(`助鬼伤身：${dj.zhuGui.duan}`); }
		if(dj.wuGui){ out.push('无鬼无气'); }
		if(dj.mieMo){ out.push(`四卦${dj.mieMo.kind}例(${dj.mieMo.season})`); }
		(dj.suiJinFu || []).forEach((ch)=>out.push(`碎金赋：${ch.kind}(第${ch.from}爻${ch.liuqin})${ch.notes.length ? '——' + ch.notes.join(';') : ''}`));
		(dj.feiFu || []).forEach((f)=>out.push(`飞伏：第${f.pos}爻${f.rel}${f.usable ? (f.usable.usable ? '(伏可用)' : '(伏难出)') : ''}`));
		if(dj.xinpaiShi){ out.push(`新派量化(世)：${dj.xinpaiShi.score}分→${dj.xinpaiShi.grade}`); }
		if(dj.xinpaiYong){ out.push(`新派量化(用神${dj.xinpaiYongLiuqin || ''})：${dj.xinpaiYong.score}分→${dj.xinpaiYong.grade}`); }
	}
	if(a.yingqi){
		a.yingqi.rules.concat(a.yingqi.byAsk || []).forEach((r)=>out.push(`应期·${r.rule}：${r.targets.join('/')}[${r.scope}]`));
	}
	return out;
}

export function zhanleiLines(a, guaName){
	const out = ['[占类断语]'];
	const lore = guaName ? guaLoreOf(guaName) : null;
	if(lore){ out.push(`历史占例：${lore.who}${lore.event},${lore.result}`); }
	// [Q-205/T-152] 古法进阶引擎产七项、断诀页也画七卡,快照此前只取「十六变」一行 —— 开了齿轮
	// 等于只多一行,其余六项 AI 完全看不到。按页面同口径逐项摘要(缺项不产行;齿轮关=整段零增)。
	if(a && a.gufa){
		const gf = a.gufa;
		if(gf.sixteenPos){ out.push(`十六变：第${gf.sixteenPos.step}变·${gf.sixteenPos.vname}${gf.sixteenPos.duan ? `(${gf.sixteenPos.duan})` : ''}`); }
		if(gf.shengJiang && gf.shengJiang.upYao && gf.shengJiang.downYao){
			const sj = gf.shengJiang;
			out.push(`升降(${sj.zhongqi})：${sj.upYao.name}=第${sj.upYao.pos}爻(${sj.upYao.zhi})${sj.upMatch ? '·得度' : '·阴阳反度(主退损)'}；${sj.downYao.name}=第${sj.downYao.pos}爻(${sj.downYao.zhi})${sj.keSheng ? `；动爻第${sj.keSheng.fromPos}爻克升爻,应${sj.keSheng.atZhi}月凶` : ''}`);
		}
		if(gf.guaSheng && (gf.guaSheng.hits || []).length){
			out.push(`卦生：卦身${gf.guaSheng.body}(${gf.guaSheng.bodyWx})生${gf.guaSheng.target} → ${gf.guaSheng.hits.map((h)=>`第${h.pos}爻${h.liuqin}${h.liushen ? `(${h.liushen})` : ''}`).join('、')}`);
		}
		if(gf.zhiFu && Array.isArray(gf.zhiFu.perFu) && gf.zhiFu.perFu.length){
			out.push(`直符四建：${gf.zhiFu.perFu.map((f)=>`${f.jian}${f.name}(${f.zhi}${f.wuxing})${(f.yaoPos || []).length ? `临第${f.yaoPos.join('/')}爻` : '不上卦'}`).join('；')}${gf.zhiFu.noneOn ? '；四直皆不上卦(所为先聚后相抛)' : ''}`);
		}
		if(gf.sanXian && Array.isArray(gf.sanXian.seg) && gf.sanXian.seg.length){
			out.push(`三限荣枯：${gf.sanXian.seg.map((sg)=>`${sg.side}·第${sg.pos}爻${sg.zhi}${sg.wuxing}${sg.liuqin}管${sg.years}年${sg.moving ? '·动' : ''}`).join('；')}`);
		}
		if(gf.baJie && gf.baJie.map){
			const m = gf.baJie.map;
			out.push(`八节卦气(${gf.baJie.jie})：${Object.keys(m).map((k)=>`${k}${m[k]}`).join(' ')}${gf.baJie.neiTai ? `；内卦气=${gf.baJie.neiTai.state || '—'}${gf.baJie.neiTai.isTai ? '(内胎之象)' : ''}` : ''}`);
		}
		if(gf.pastFuture && Array.isArray(gf.pastFuture.perYao) && gf.pastFuture.perYao.length){
			out.push(`过去未来(以卦身为界)：${gf.pastFuture.perYao.map((x)=>`${x.pos}爻${x.phase}`).join('、')}`);
		}
	}
	// WP-6:《断易天机》断语库按占测事项【有界摘要】入快照(总断门纲领 + 命中门 top-N,硬上限 20 条,每条带出处)。
	// 缓存已由 GuaZhanMain mount 预热(loadDoctrine);未载则省略(不阻断同步快照)。
	const askType = a && a.settings && a.settings.askType;
	const doctItems = doctrineSummaryFor(askType, getDoctrine(), { perMen: 4, cap: 20 });
	doctItems.forEach((it) => out.push(`断语·${it.men}·${it.source}：${(it.text || '').replace(/\s+/g, ' ').slice(0, 70)}`));
	// 占天时古法(仅「天时占法」设为古法档时有;通行档 a.tianshi 为 null → 本块整体不出)。
	// 与上面 doctrine 摘要同段、同为「有界摘要 + 带出处」:天时本就是占类之一,不另开段头
	// —— 新增段头须同步登记 aiExport 的 preset 注册表,而这里并入既有段即可,零登记风险。
	// 🔴 必带「各家分列、不合成单一结论」的口径,否则 AI 会把互相冲突的各家判语当成一个结论。
	if(a && a.tianshi && Array.isArray(a.tianshi.houses) && a.tianshi.houses.length){
		out.push(`天时·古法分列(${a.tianshi.houses.length} 家;各家自成体系、彼此有冲突,不可合成单一结论)`);
		let n = 0;
		a.tianshi.houses.forEach((h)=>{
			h.hits.slice(0, 3).forEach((x)=>{
				if(n >= 12){ return; }
				out.push(`天时·${h.source}：${x.rule}(${x.detail})`);
				n += 1;
			});
		});
		(a.tianshi.notImplemented || []).forEach((ni)=>out.push(`天时·未采:${ni.source}(${ni.why})`));
	}
	return out;
}
