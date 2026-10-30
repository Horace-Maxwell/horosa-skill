// 六壬页 · AI 快照正文。
// 只被 components/lrzhan/LiuRengMain.js 与同目录 main/ 下的兄弟模块引用。
import * as LRConst from '../../liureng/LRConst.js';
import { liurengWangXiang, judgeKongWang } from '../../liureng/LRZhangSheng.js';
import { buildXiangContext } from '../../liureng/LRXiangDoc.js';
import { computeFrontendShenSha, computeYearShenSha, computeMonthShenSha } from '../../liureng/LRShenShaDoc.js';
import { detectJianChuan } from '../../liureng/LRJianChuanDoc.js';
import { analyzeKongLocations, analyzeDunGan, analyzeNianMing } from '../../liureng/LRKongDunNianDoc.js';
import { ZHANDUAN_DOC } from '../../liureng/LRZhanDuanDoc.js';
import { matchBiFa } from '../../liureng/LRBiFaDoc.js';
import { sanChuanRelationSnapshotLines } from '../../liureng/LRSanChuanRelationMini.js';   // 小图与快照共用同一纯函数
import { fmtValue, appendMapSection } from './birthRunYear.js';
import { buildQiZhengItems } from './ganzhiHelpers.js';
import { QI_METHODS, YUE_JIANG_METHODS, FEN_ZHOU_YE_METHODS, buildLiuRengCastOverride } from './castLayout.js';
import { buildLiuRengPanRows, buildLiuRengSanChuanRows, buildLiuRengSuiShaRows, buildLiuRengZhangShengRows } from './panData.js';
import { XIAO_JU_REFERENCE_TAB_KEYS } from './referenceData.js';
import { buildOverviewReferenceText, buildLiuRengReferenceBundle, appendReferenceSnapshotSection } from './referenceMatch.js';

export function buildLiuRengSnapshotText(params, liureng, runyear, chartObj, guirengType, zhangshengElem, gender, castOpts){
	const lines = [];
	const _castOpts = castOpts || {};
	const nongli = liureng && liureng.nongli ? liureng.nongli : (chartObj && chartObj.nongli ? chartObj.nongli : {});
	// 调用方(三式合一)已按自家口径算好 castOverride 时直接用,不再按 castOpts 重算——
	// 此前三式把 override 对象当 castOpts 传进来,键名不匹配 → 断卦层按全默认盘重算,与同一快照 [大六壬] 四课三传两套盘。
	const castOverride = (_castOpts.castOverride && typeof _castOpts.castOverride === 'object')
		? _castOpts.castOverride
		: buildLiuRengCastOverride(chartObj, _castOpts);
	const refs = buildLiuRengReferenceBundle(liureng, chartObj, guirengType, runyear, castOverride, { benMingBranch: _castOpts.benmingZhi });
	const layout = refs.layout;
	const panStyle = refs && refs.context ? refs.context.panStyle : null;
	const keData = refs.keData;
	const sanChuan = refs.sanChuan;
	// 性别「未知」(-1)时计算按男排(行年 / 旬法皆以 gender≠0 取男表),快照却写「女」——
	//   同一份快照里「行年:男」与「性别:女」并存。与八字页口径统一:未知写「未知(按男排)」。
	const xingbie = `${gender}` === '1' ? '男' : (`${gender}` === '0' ? '女' : '未知(按男排)');

	lines.push('[起盘信息]');
	if(params){
		lines.push(`日期：${params.date} ${params.time}`);
		lines.push(`时区：${params.zone}`);
		lines.push(`经纬度：${params.lon} ${params.lat}`);
	}
	// 时间算法如实写:选「直接时间」时起课(盘面、四柱)按钟表时定时辰;真太阳时一行仍是真太阳时。缺省(真太阳时)不加行 = 字节级不变
	const _ta = params && params.timeAlg !== undefined && params.timeAlg !== null ? Number(params.timeAlg) : 0;
	if(_ta === 1){
		lines.push('时间算法：直接时间(按钟表时定时辰)');
		if(nongli && nongli.clockTime){ lines.push(`钟表时：${nongli.clockTime}`); }
	}
	if(nongli && nongli.birth){
		lines.push(`真太阳时：${nongli.birth}`);
	}
	if(liureng && liureng.fourColumns){
		const cols = liureng.fourColumns;
		lines.push(`四柱：${fmtValue(cols.year && cols.year.ganzi)}年 ${fmtValue(cols.month && cols.month.ganzi)}月 ${fmtValue(cols.day && cols.day.ganzi)}日 ${fmtValue(cols.time && cols.time.ganzi)}时`);
	}
	lines.push(`贵人体系：${['六壬法贵人', '遁甲法贵人', '星占法贵人', '甲戊兼牛羊', '干合阳阴贵'][guirengType] || '星占法贵人'}`);
	lines.push(`起课法：${(QI_METHODS.find((m)=>m.key === (_castOpts.castMethod || 'zheng')) || QI_METHODS[0]).name}`);
	if(_castOpts.castMethod === 'xuanshi' && _castOpts.xuanShiZhi){ lines.push(`选时：${_castOpts.xuanShiZhi}时`); }
	if((_castOpts.castMethod === 'yanshu' || _castOpts.castMethod === 'baoshu') && (_castOpts.yanShuNum || _castOpts.yanShuNum === 0)){ lines.push(`${_castOpts.castMethod === 'baoshu' ? '报数/端法(÷12定支)' : '演数'}：${_castOpts.yanShuNum}`); }
	lines.push(`换将：${(YUE_JIANG_METHODS.find((m)=>m.key === (_castOpts.yueJiangMethod || 'zhongqi')) || YUE_JIANG_METHODS[0]).name}`);
	lines.push(`分昼夜：${(FEN_ZHOU_YE_METHODS.find((m)=>m.key === (_castOpts.fenZhouYe || 'chenhun')) || FEN_ZHOU_YE_METHODS[0]).name}`);
	if((_castOpts.seHaiMethod && _castOpts.seHaiMethod !== 'app') || (_castOpts.seHaiBoundary && _castOpts.seHaiBoundary !== 'app') || _castOpts.shiRuKe){
		const _sm = { app: '仅下贼上(单向取)', standard: '标准深浅两向', mengzhongji: '直取孟仲季' }[_castOpts.seHaiMethod || 'app'];
		const _sb = { app: '计起点不计本家', both: '两端皆计', neither: '皆不计' }[_castOpts.seHaiBoundary || 'app'];
		lines.push(`涉害取舍：${_sm}·${_sb}${_castOpts.shiRuKe ? '·始入课单列(十法)' : ''}`);
	}
	lines.push(`十二长生五行：${fmtValue(zhangshengElem)}`);
	lines.push(`十二盘式：${fmtValue(panStyle && panStyle.name ? panStyle.name : '')}`);
	lines.push(`问测人性别：${xingbie}`);
	lines.push('');

	lines.push('[十二盘式]');
	if(panStyle && panStyle.name){
		lines.push(`盘式：${panStyle.name}`);
		lines.push(`月将：${fmtValue(panStyle.yueBranch)}；占时：${fmtValue(panStyle.timeBranch)}；位序：${fmtValue(panStyle.distanceLabel)}`);
	}else{
		lines.push('无');
	}
	lines.push('');

	lines.push('[十二地盘/十二天盘/十二贵神对应]');
	if(layout){
		buildLiuRengPanRows(layout).forEach((l)=>lines.push(l));
	}else{
		lines.push('无');
	}
	lines.push('');

	lines.push('[四课]');
	if(keData.lines.length){
		keData.lines.forEach((line)=>lines.push(line));
	}else{
		lines.push('无');
	}
	lines.push('');

	lines.push('[三传]');
	if(sanChuan){
		lines.push(`课式：${fmtValue(sanChuan.name)}`);
		buildLiuRengSanChuanRows(sanChuan).forEach((l)=>lines.push(l));
		// 三传递生递克 + 逐传空/禄/马徽记:右栏取象页签的小图早已画出,快照此前一个字都不带
		// (空亡可由 [旬空落点]、禄马可由 [常用神煞] 间接推得,但传间生克与逐传徽记无处可推)。与小图同一纯函数。
		const _scCtx = refs && refs.context ? refs.context : null;
		if(_scCtx && Array.isArray(_scCtx.sanChuanBranches) && _scCtx.sanChuanBranches.length >= 3){
			sanChuanRelationSnapshotLines({
				branches: _scCtx.sanChuanBranches,
				gans: _scCtx.sanChuanGans || [],
				dayGan: _scCtx.dayGan || '',
				dayZhi: _scCtx.dayZhi || '',
				xunKong: _scCtx.xunKongBranches || [],
			}).forEach((l)=>lines.push(l));
		}
	}else{
		lines.push('无');
	}
	lines.push('');

	lines.push('[行年]');
	if(runyear){
		lines.push(`行年干支：${fmtValue(runyear.year)}`);
		lines.push(`年龄：${fmtValue(runyear.age)}岁`);
		lines.push(`性别：${xingbie}`);
	}else{
		lines.push('无');
	}
	lines.push('');

	appendMapSection(lines, '旬日', liureng ? liureng.xun : null);
	appendMapSection(lines, '旺衰', liureng ? liureng.season : null);
	appendMapSection(lines, '基础神煞', liureng ? liureng.gods : null);
	appendMapSection(lines, '干煞', liureng ? liureng.godsGan : null);
	appendMapSection(lines, '月煞', liureng ? liureng.godsMonth : null);
	appendMapSection(lines, '支煞', liureng ? liureng.godsZi : null);

	lines.push('[岁煞]');
	const yearGods = liureng && liureng.godsYear ? liureng.godsYear.taisui1 : null;
	if(yearGods){
		buildLiuRengSuiShaRows(yearGods).forEach((l)=>lines.push(l));
	}else{
		lines.push('无');
	}
	lines.push('');

	lines.push('[十二长生]');
	if(zhangshengElem){
		buildLiuRengZhangShengRows(zhangshengElem).forEach((l)=>lines.push(l));
	}else{
		lines.push('无');
	}
	lines.push('');

	appendReferenceSnapshotSection(lines, '大格', refs.dage, 'dage');
	const xiaojuAllRefs = Array.isArray(refs.xiaoju) ? refs.xiaoju : [];
	const xiaojuMainRefs = xiaojuAllRefs.filter((item)=>!XIAO_JU_REFERENCE_TAB_KEYS.has(item.key));
	const xiaojuReferenceRefs = xiaojuAllRefs.filter((item)=>XIAO_JU_REFERENCE_TAB_KEYS.has(item.key));
	appendReferenceSnapshotSection(lines, '小局', xiaojuMainRefs, 'xiaoju');
	appendReferenceSnapshotSection(lines, '参考', xiaojuReferenceRefs, 'xiaoju');
	lines.push('[概览]');
	const overviewRefs = Array.isArray(refs.overview) ? refs.overview : [];
	if(overviewRefs.length){
		overviewRefs.forEach((item, idx)=>{
			const groupName = item.group === 'laiyi' ? '天将发用来意诀' : '天将杂主吉凶';
			lines.push(`${idx + 1}. ${groupName} · ${item.name}`);
			const docText = buildOverviewReferenceText(item);
			if(docText){
				docText.split('\n').forEach((line)=>{
					lines.push(line);
				});
			}
			if(item.evidence && item.evidence.length){
				lines.push(`依据：${item.evidence.join('；')}`);
			}
			lines.push('');
		});
	}else{
		lines.push('无');
		lines.push('');
	}
	const _ctx = refs && refs.context ? refs.context : null;
	if(_ctx){
		const shenSha = computeFrontendShenSha(_ctx.dayGan, _ctx.dayZhi, _ctx.courseBranches);
		lines.push('[常用神煞]');
		if(shenSha.length){
			shenSha.forEach((s)=>lines.push(`${s.name}：${s.branch}${s.inCourse ? '（入课传）' : ''}（${s.brief}）`));
		}else{
			lines.push('无');
		}
		lines.push('');

		const yearSS = computeYearShenSha(_ctx.yearBranch, _castOpts.yearShenShaSort || 'sanyuan', _ctx.courseBranches);
		const monthSS = computeMonthShenSha(_ctx.monthBranch, _ctx.courseBranches);
		if(yearSS.length || monthSS.length){
			// 段头独占一行(段头卫生:parseSectionTitleLine 仅认整行 [X]);年神序说明移正文行,否则段头带正文 → 认不出 → 整段并入上一段、且导出设置勾不到。
			lines.push('[年月神煞]');
			lines.push(`（年神＝${(_castOpts.yearShenShaSort === 'suigui') ? '太岁排轮' : '四利三元序'}）`);
			yearSS.concat(monthSS).forEach((s)=>lines.push(`${s.name}：${s.branch}${s.inCourse ? '（入课传）' : ''}`));
			lines.push('');
		}
		const jcS = detectJianChuan(_ctx.sanChuanBranches);
		if(jcS){ lines.push('[课体结构]'); lines.push(`${jcS.name}（${jcS.kind}${jcS.wuxing ? '·' + jcS.wuxing : ''}${jcS.dir ? '·' + jcS.dir + '间' : ''}）：${jcS.text}`); lines.push(''); }
		const _ws = (_ctx.sanChuanBranches || []).map((z, i) => { const wx = LRConst.GanZiWuXing[`${z || ''}`.trim().substring(0,1)] || ''; const w = liurengWangXiang(wx, _ctx.monthBranch, _castOpts.tuWangShuai); return w ? `${['初','中','末'][i]}传${z}${wx}${w}` : ''; }).filter(Boolean);
		if(_ws.length){ lines.push('[三传旺衰]'); lines.push(`${_ws.join('、')}`); lines.push(''); }
		const _kw = (_ctx.xunKongBranches || []).map((z) => { const wx = LRConst.GanZiWuXing[`${z||''}`.trim().substring(0,1)] || ''; const j = judgeKongWang(wx, _ctx.monthBranch, _castOpts.tuWangShuai); return j ? `${z}${wx}${j.kind}(${j.ws})` : ''; }).filter(Boolean);
		if(_kw.length){ lines.push('[空亡真假]'); lines.push(`${_kw.join('、')}`); lines.push(''); }
		const _kloc = analyzeKongLocations(_ctx);
		if(_kloc.hits.length){ lines.push('[旬空落点]'); lines.push(`${_kloc.hits.map((h)=>`${h.pos}${h.branch}空（${h.note}）`).join('；')}${_kloc.allSanChuanKong ? '；三传全空，守干上旺禄勿动' : ''}`); lines.push(''); }
		if(_kloc.xianKong.length){ lines.push('[陷空]'); lines.push(`${_kloc.xianKong.map((x)=>`${x.god}临地盘${x.seat}`).join('、')}（落于空地、虚而不实）`); lines.push(''); }
		const _dun = analyzeDunGan(_ctx);
		if(_dun.length){ lines.push('[遁干特殊]'); lines.push(`${_dun.map((d)=>`${d.pos}${d.branch}${d.gan ? '遁' + d.gan : ''}${d.flags.length ? '（' + d.flags.join('、') + '）' : ''}：${d.note}`).join('；')}`); lines.push(''); }
		const _nm = analyzeNianMing(_ctx);
		if(_nm.length){ lines.push('[年命上神]'); lines.push(`${_nm.map((n)=>`${n.label}${n.branch}——${n.note}`).join('；')}`); lines.push(''); }
		const bifaHits = matchBiFa(_ctx);
		lines.push('[毕法（已命中）]');
		lines.push('（以下为机械命中之断诀，烈度须合时令旺衰、年命制化，非定数）');
		if(bifaHits.length){
			bifaHits.forEach((b)=>{
				lines.push(`${b.no}. ${b.name}：${b.verse}`);
				lines.push(`释：${b.explain}`);
				if(b.evidence && b.evidence.length){ lines.push(`依据：${b.evidence.join('；')}`); }
			});
		}else{
			lines.push('无（本盘未机械命中可判定之毕法）');
		}
		lines.push('');

		const zhanKey = _castOpts.zhanCategory || 'general';
		if(zhanKey && zhanKey !== 'general' && ZHANDUAN_DOC[zhanKey]){
			const zd = ZHANDUAN_DOC[zhanKey];
			lines.push('[占断向导]');
			lines.push(`占事：${zd.name}`);
			lines.push(`主用神：${(zd.mainYong || []).map((y)=>`${y.role}=${y.mean}`).join('；')}`);
			const yongLuo = [];
			if(_ctx.ke1Up){ yongLuo.push(`日干上神=${_ctx.ke1Up}`); }
			if(_ctx.ke3Up){ yongLuo.push(`日支上神=${_ctx.ke3Up}`); }
			if(_ctx.runYearBranch){ yongLuo.push(`年命上神位=${_ctx.runYearBranch}`); }
			if(yongLuo.length){ lines.push(`用神落点：${yongLuo.join('；')}`); }
			const godValues = _ctx.branchGodMap ? Object.keys(_ctx.branchGodMap).map((k)=>_ctx.branchGodMap[k]) : [];
			const present = (zd.keyJiang || []).filter((j)=>godValues.indexOf(j) >= 0);
			const absent = (zd.keyJiang || []).filter((j)=>present.indexOf(j) < 0);
			lines.push(`关键神将：现=${present.join('、') || '—'}；缺=${absent.join('、') || '—'}`);
			lines.push(`宜：${(zd.favor || []).join('；')}`);
			lines.push(`忌：${(zd.avoid || []).join('；')}`);
			lines.push(`三传提示：${zd.sanChuanTip || ''}`);
			lines.push('');
		}

		// [取象] doctrine 段(默认关段:builder 恒产,导出层按设置控)：与右栏「取象」卡同源 buildXiangContext,
		// 只导本盘四课三传在位地支的 类象/五行/方位/六亲/刑冲合害/长生旺衰 条目(非全库十二支),象意原文零改写。
		const xiangBranches = Array.isArray(_ctx.courseBranches) ? _ctx.courseBranches : [];
		const xiangLines = [];
		xiangBranches.forEach((z)=>{
			const cx = buildXiangContext(z, _ctx.dayGan, zhangshengElem);
			if(!cx){
				return;
			}
			// 在位标注(初/中/末传、N课上/下)——派生定位信息,便于 AI 对位取象。
			const roles = [];
			(_ctx.sanChuanBranches || []).forEach((b, i)=>{ if(b === z){ roles.push(`${['初', '中', '末'][i] || ''}传`); } });
			(_ctx.keUpBranches || []).forEach((b, i)=>{ if(b === z){ roles.push(`${i + 1}课上`); } });
			(_ctx.keDownBranches || []).forEach((b, i)=>{ if(b === z){ roles.push(`${i + 1}课下`); } });
			xiangLines.push(`◆ ${cx.branch}${cx.shenName ? `（${cx.shenName}）` : ''}${roles.length ? `——${roles.join('、')}` : ''}`);
			const rowParts = [];
			if(cx.wuxing){ rowParts.push(`五行：${cx.wuxing}${cx.wuxingXiang ? `（${cx.wuxingXiang.keyword}）` : ''}`); }
			if(cx.direction){ rowParts.push(`方位：${cx.direction}`); }
			if(cx.liuqin){ rowParts.push(`六亲：${cx.liuqin}`); }
			if(cx.zhangsheng){ rowParts.push(`${cx.zhangshengElem}·长生：${cx.zhangsheng}`); }
			if(cx.yima){ rowParts.push(`驿马：${cx.yima}`); }
			if(rowParts.length){ xiangLines.push(rowParts.join('　')); }
			if(cx.symbol){ xiangLines.push(`类象：${cx.symbol}`); }
			if(cx.relations && cx.relations.length){ xiangLines.push(`刑冲合害：${cx.relations.join('　')}`); }
			if(cx.relationNotes && cx.relationNotes.length){ xiangLines.push(`断用：${cx.relationNotes.map((r)=>`${r.type}—${r.note}`).join('；')}`); }
			if(cx.wuxingXiang){ xiangLines.push(`五行取象：人物：${cx.wuxingXiang.person}；身体：${cx.wuxingXiang.body}；事：${cx.wuxingXiang.affair}`); }
		});
		if(xiangLines.length){
			lines.push('[取象]');
			lines.push('（本盘四课三传在位地支类象，供合盘断之）');
			xiangLines.forEach((l)=>lines.push(l));
			lines.push('');
		}
	}

	// [七政] 段(v44 硬缺修):七政 tab 整层此前显示了完全导不出——日月五星临宫/五行/度/逆行/月将
	// 是大六壬七政四余合参的独立断法层。值与 tab 网格同源(buildQiZhengItems);无星历数据不产段(零字节变化)。
	const qizhengItems = buildQiZhengItems(chartObj);
	if(qizhengItems.length){
		lines.push('[七政]');
		lines.push('| 七政 | 临支 | 五行 | 度数 | 逆行 | 备注 |');
		lines.push('| --- | --- | --- | --- | --- | --- |');
		qizhengItems.forEach((item)=>{
			const deg = item.deg != null ? `${item.deg.toFixed(0)}°` : '—';
			lines.push(`| ${item.name} | ${item.branch || '—'} | ${item.wx || '—'} | ${deg} | ${item.retro ? '逆' : '—'} | ${item.isYue ? '月将(太阳过宫)' : '—'} |`);
		});
		lines.push('');
	}

	return lines.join('\n').trim();
}
