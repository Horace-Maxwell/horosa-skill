// Vendored from 星阙 JinKouMain.js —— 金口诀 AI 快照 32 段（buildJinKouSnapshotText + 5 个模块级
// 格式化助手）。网络/React 部分不取；纯格式化函数，消费 buildJinKouData(解读层) + liureng 前置数据。
//
// 与上游 JinKouMain.js 的差异仅为「去掉 React 与网络层」——段构建逻辑逐字未改，包括 pushMdRows
// 产出的 GFM 表格排版（金口诀四位/三盘/四位生克/十二长生 四段上游已表化）。
import { ZSList, ZhangSheng } from '../liureng/LRZhangSheng.js';
import { JINKOU_SIXIANG_SHU_COLS, JINKOU_SIXIANG_WUXING_COLS } from './JinKouDoc.js';

// 逐字取自上游 JinKouMain.js 的模块级常量（GFM 表格分隔行）。
const MD_DASH = '—';

function fmtValue(value){
	if(value === undefined || value === null || value === ''){
		return '无';
	}
	if(value instanceof Array){
		return value.join('、') || '无';
	}
	return `${value}`;
}

function pushMdRows(lines, header, rows){
	lines.push(`| ${header.join(' | ')} |`);
	lines.push(`| ${header.map(()=>'---').join(' | ')} |`);
	rows.forEach((cells)=>{
		lines.push(`| ${cells.map((c)=>(c === undefined || c === null || c === '' ? MD_DASH : `${c}`)).join(' | ')} |`);
	});
}

function cleanKey(key){
	const txt = `${key || ''}`;
	const idx = txt.indexOf('(');
	if(idx >= 0){
		return txt.substring(0, idx);
	}
	return txt;
}

function appendMapSection(lines, title, obj){
	lines.push(`[${title}]`);
	if(!obj || typeof obj !== 'object'){
		lines.push('无');
		lines.push('');
		return;
	}
	const keys = Object.keys(obj);
	if(keys.length === 0){
		lines.push('无');
		lines.push('');
		return;
	}
	for(let i=0; i<keys.length; i++){
		const key = keys[i];
		lines.push(`${cleanKey(key)}：${fmtValue(obj[key])}`);
	}
	lines.push('');
}

function mapObjToRows(obj){
	if(!obj || typeof obj !== 'object'){
		return [];
	}
	const keys = Object.keys(obj);
	const rows = [];
	for(let i=0; i<keys.length; i++){
		const key = keys[i];
		let value = obj[key];
		if(value instanceof Array){
			value = value.join('、');
		}
		rows.push({
			key: cleanKey(key),
			value: value === undefined || value === null || value === '' ? '—' : `${value}`,
		});
	}
	return rows;
}

export function buildJinKouSnapshotText(params, liureng, runyear, jinkouData, wuxing, guirengType, gender){
	const lines = [];
	const nongli = liureng && liureng.nongli ? liureng.nongli : {};
	const xingbie = `${gender}` === '1' ? '男' : '女';
	const guirenType = jinkouData && jinkouData.source === 'kinjinkou' ? 'kinjinkou 贵人歌诀' : (guirengType === 0 ? '六壬法贵人' : (guirengType === 1 ? '遁甲法贵人' : '星占法贵人'));
	const briefKong = (txt)=>{
		const val = `${txt || ''}`;
		const hasEmpty = val.indexOf('空亡') >= 0;
		const hasSiKong = val.indexOf('四大空亡') >= 0;
		if(hasEmpty && hasSiKong){
			return '空&四空';
		}
		if(hasEmpty){
			return '空';
		}
		if(hasSiKong){
			return '四空';
		}
		return '';
	};
	const findRow = (name)=>{
		if(!jinkouData || !jinkouData.rows){
			return null;
		}
		for(let i=0; i<jinkouData.rows.length; i++){
			const row = jinkouData.rows[i];
			if(row && row.label === name){
				return row;
			}
		}
		return null;
	};
	const appendBriefRow = (name, withShenjiang)=>{
		const row = findRow(name);
		if(!row){
			lines.push(`${name}：无`);
			return;
		}
		const main = fmtValue(row.content);
		const shenjiang = withShenjiang && row.shenjiang && row.shenjiang !== '-' ? `（${row.shenjiang}）` : '';
		const power = row.power && row.power !== '—' ? row.power : '无';
		const kong = briefKong(row.kong);
		let line = `${name}：${main}${shenjiang}；（${power}）`;
		if(kong){
			line = `${line}；${kong}`;
		}
		lines.push(line);
	};

	lines.push('[起盘信息]');
	if(params){
		// 逐字段 fmtValue —— 原先整体判 params 非空后就裸插值，任一字段缺失即把字面量
		// 「undefined」写进快照、直送 AI 提示词。与本函数其余各行同律用 fmtValue（缺 → 无）。
		lines.push(`日期：${fmtValue(params.date)} ${fmtValue(params.time)}`);
		lines.push(`时区：${fmtValue(params.zone)}`);
		lines.push(`经纬度：${fmtValue(params.lon)} ${fmtValue(params.lat)}`);
	}
	if(nongli && nongli.birth){
		lines.push(`真太阳时：${nongli.birth}`);
	}
	if(liureng && liureng.fourColumns){
		const cols = liureng.fourColumns;
		lines.push(`四柱：${fmtValue(cols.year && cols.year.ganzi)}年 ${fmtValue(cols.month && cols.month.ganzi)}月 ${fmtValue(cols.day && cols.day.ganzi)}日 ${fmtValue(cols.time && cols.time.ganzi)}时`);
	}
	lines.push(`贵人体系：${guirenType}`);
	// 土之长生随流派(申/寅);默认「水土同宫·申」时不写此括注 → 既有快照逐字零回归。
	const soilNote = wuxing === '土' && jinkouData && jinkouData.schools && jinkouData.schools.soilChangSheng === 'yin'
		? '（火土同宫·寅）' : '';
	lines.push(`十二长生五行：${fmtValue(wuxing)}${soilNote}`);
	// 昼夜依「真实地平」时才写口径行(有盘可依);无盘回落时支粗判,不写 → 既有快照零回归。
	if(jinkouData && jinkouData.dayBasis === 'horizon'){
		lines.push(`昼夜：${jinkouData.isDay ? '昼占' : '夜占'}（${fmtValue(jinkouData.dayBasisText)}）`);
	}
	lines.push(`问测人性别：${xingbie}`);
	lines.push('');

	lines.push('[金口诀速览]');
	if(jinkouData && jinkouData.ready){
		lines.push(`地分：${fmtValue(jinkouData.topInfo.diFen)}`);
		// [X1·P2-14] 月将/占时与中栏顶行同源入快照(此前 AI 看不到这两个排盘参数)。
		if(jinkouData.topInfo.yuejiang){ lines.push(`月将：${fmtValue(jinkouData.topInfo.yuejiang)}`); }
		if(jinkouData.topInfo.zhanshi){ lines.push(`占时：${fmtValue(jinkouData.topInfo.zhanshi)}`); }
		lines.push(`空亡：${fmtValue(jinkouData.topInfo.xunKong)}`);
		lines.push(`四大空亡：${fmtValue(jinkouData.topInfo.siDaKong)}`);
		if(jinkouData.yongYao && jinkouData.yongYao.label){
			lines.push(`用爻：${jinkouData.yongYao.label}${jinkouData.yongYao.sign ? `(${jinkouData.yongYao.sign})` : ''}`);
		}
		appendBriefRow('人元', false);
		appendBriefRow('贵神', true);
		appendBriefRow('将神', true);
		appendBriefRow('地分', false);
	}else{
		lines.push('无');
	}
	lines.push('');

	lines.push('[金口诀四位]');
	if(jinkouData && jinkouData.ready){
		lines.push(`地分：${fmtValue(jinkouData.topInfo.diFen)}`);
		// [X1·P2-14] 月将/占时与中栏顶行同源入快照(此前 AI 看不到这两个排盘参数)。
		if(jinkouData.topInfo.yuejiang){ lines.push(`月将：${fmtValue(jinkouData.topInfo.yuejiang)}`); }
		if(jinkouData.topInfo.zhanshi){ lines.push(`占时：${fmtValue(jinkouData.topInfo.zhanshi)}`); }
		lines.push(`空亡：${fmtValue(jinkouData.topInfo.xunKong)}`);
		lines.push(`四大空亡：${fmtValue(jinkouData.topInfo.siDaKong)}`);
		if(jinkouData.yongYao && jinkouData.yongYao.label){
			lines.push(`用爻判定：${jinkouData.yongYao.reason || ''}；取${jinkouData.yongYao.label}${jinkouData.yongYao.sign ? `(${jinkouData.yongYao.sign})` : ''}`);
		}
		// 四位(人元/贵神/将神/地分)→ GFM 表:位/天干/内容/神将/状态/空亡/纳音(纳音缺 → —)。
		const siWeiRows = jinkouData.rows.map((row)=>[
			row.label, fmtValue(row.gan), fmtValue(row.content), fmtValue(row.shenjiang), fmtValue(row.power), fmtValue(row.kong), row.nayin ? fmtValue(row.nayin) : '',
		]);
		pushMdRows(lines, ['位', '天干', '内容', '神将', '状态', '空亡', '纳音'], siWeiRows);
	}else{
		lines.push('无');
	}
	lines.push('');

	lines.push('[金口诀三盘]');
	if(jinkouData && jinkouData.ready && jinkouData.plates && jinkouData.plates.length){
		// 三盘逐地分 → GFM 表:地分/天盘/将神/神盘/贵神。
		const plateRows = jinkouData.plates.map((row)=>[
			fmtValue(row.di), fmtValue(row.tian), fmtValue(row.jiang), fmtValue(row.shen), fmtValue(row.gui),
		]);
		pushMdRows(lines, ['地分', '天盘', '将神', '神盘', '贵神'], plateRows);
	}else{
		lines.push((jinkouData && jinkouData.platesNote) || '无');
	}
	lines.push('');

	lines.push('[四位神煞]');
	if(jinkouData && jinkouData.shenshaRows && jinkouData.shenshaRows.length){
		for(let i=0; i<jinkouData.shenshaRows.length; i++){
			const row = jinkouData.shenshaRows[i];
			lines.push(`${row.label}：${fmtValue(row.value)}`);
		}
	}else{
		lines.push('无');
	}
	lines.push('');

	lines.push('[用神强弱]');
	lines.push(jinkouData && jinkouData.yongStrength ? jinkouData.yongStrength.text : '无');
	lines.push('');

	lines.push('[发用·五动三动]');
	const jkDongSnap = jinkouData && jinkouData.dong ? jinkouData.dong : { wu: [], san: [] };
	const jkAllDong = [].concat(jkDongSnap.wu || [], jkDongSnap.san || []);
	if(jkAllDong.length){
		// 五动/三动 → GFM 表:动象/起→落/逢空/断语(逢空缺、断语缺 → —)。
		const dongRows = jkAllDong.map((d)=>[`${d.type}动`, `${d.from}→${d.to}`, d.kong ? '逢空' : '', d.text || '']);
		pushMdRows(lines, ['动象', '起→落', '逢空', '断语'], dongRows);
	}else{
		lines.push('四位无显著动象');
	}
	lines.push('');

	lines.push('[格局]');
	if(jinkouData && jinkouData.geju && jinkouData.geju.length){
		for(let i=0; i<jinkouData.geju.length; i++){
			lines.push(`${jinkouData.geju[i].name}：${jinkouData.geju[i].text || ''}`);
		}
	}else{
		lines.push('无');
	}
	lines.push('');

	lines.push('[四位生克]');
	if(jinkouData && jinkouData.relations && jinkouData.relations.length){
		// 四位生克 → GFM 表:主/关系/宾/断语(断语缺 → —)。
		const relRows = jinkouData.relations.map((r)=>[r.from, r.rel, r.to, r.text || '']);
		pushMdRows(lines, ['主', '关系', '宾', '断语'], relRows);
	}else{
		lines.push('无');
	}
	if(jinkouData && jinkouData.bihe && jinkouData.bihe.length){
		for(let i=0; i<jinkouData.bihe.length; i++){
			lines.push(jinkouData.bihe[i].text);
		}
	}
	lines.push('');

	lines.push('[应期]');
	if(jinkouData && jinkouData.yingQi){
		lines.push(`${jinkouData.yingQi.scope}：${jinkouData.yingQi.text}`);
		const yqm = jinkouData.yingQi.methods || [];
		for(let i=0; i<yqm.length; i++){
			lines.push(`${yqm[i].fa}（${yqm[i].when}）：${yqm[i].text}`);
		}
	}else{
		lines.push('无');
	}
	lines.push('');

	lines.push('[太岁月建]');
	if(jinkouData && jinkouData.nianYueRi && jinkouData.nianYueRi.length){
		// 太岁月建 → GFM 表:名/地支/入课/断语(未入课 → —)。
		const nyrRows = jinkouData.nianYueRi.map((it)=>[it.name, it.zhi, it.hit ? '入课' : '', it.text]);
		pushMdRows(lines, ['名', '地支', '入课', '断语'], nyrRows);
	}else{
		lines.push('无');
	}
	if(jinkouData && jinkouData.jishi && jinkouData.jishi.hit){
		lines.push(`忌时：${jinkouData.jishi.text}`);
	}
	lines.push('');

	lines.push('[地支关系]');
	if(jinkouData && jinkouData.branchRelations && jinkouData.branchRelations.length){
		for(let i=0; i<jinkouData.branchRelations.length; i++){
			const b = jinkouData.branchRelations[i];
			lines.push(`${b.aLabel}${b.a} ${b.type} ${b.bLabel}${b.b}`);
		}
	}else{
		lines.push('无');
	}
	lines.push('');

	lines.push('[相关神煞]');
	if(jinkouData && jinkouData.relevantShensha && jinkouData.relevantShensha.length){
		for(let i=0; i<jinkouData.relevantShensha.length; i++){
			const it = jinkouData.relevantShensha[i];
			lines.push(`${it.position}·${it.name}：${it.desc || ''}`);
		}
	}else{
		lines.push('无');
	}
	lines.push('');

	// 阴盘三层（仅盘式=阴盘时附段；阳盘不产此段 → 既有快照逐字零回归）。
	if(jinkouData && jinkouData.yinPan && jinkouData.yinPan.wangScore && jinkouData.yinPan.wangScore.length){
		const yp = jinkouData.yinPan;
		const qinBy = {};
		(yp.liuqin || []).forEach((it)=>{ qinBy[it.wei] = it.qin; });
		const shenBy = {};
		(yp.liushen || []).forEach((it)=>{ shenBy[it.wei] = it.name; });
		lines.push('[阴盘·六亲六神旺衰]');
		lines.push(`以日干 ${fmtValue(yp.self)}（${fmtValue(yp.selfElem)}）为我；${yp.scoreNote}`);
		lines.push('| 位 | 五行 | 六亲 | 六神 | 旺衰 | 分值 | 依据 |');
		lines.push('| --- | --- | --- | --- | --- | --- | --- |');
		yp.wangScore.forEach((s)=>{
			lines.push(`| ${s.wei} | ${fmtValue(s.elem)} | ${fmtValue(qinBy[s.wei])} | ${fmtValue(shenBy[s.wei])} | ${fmtValue(s.level)} | ${s.score > 0 ? `+${s.score}` : s.score} | ${s.detail.length ? s.detail.join('、') : '—'} |`);
		});
		lines.push('');
	}

	// 专题起式（仅左栏选定专题/测年月日/行年时附段；未选则整段不产 → 既有快照逐字零回归）。
	if(jinkouData && (jinkouData.topic || jinkouData.shiJian || jinkouData.xingNian)){
		lines.push('[专题起式]');
		const tp = jinkouData.topic;
		if(tp){
			lines.push(`专题：${fmtValue(tp.title)}——${fmtValue(tp.note)}`);
			if(tp.ready === false){
				lines.push(`待补：${fmtValue(tp.needText)}`);
			}else{
				if(tp.result){ lines.push(`结论：${tp.result}`); }
				if(tp.rows && tp.rows.length){
					lines.push('| 方位 | 将神 | 将名 | 将干 |');
					lines.push('| --- | --- | --- | --- |');
					tp.rows.forEach((r)=>{
						lines.push(`| ${r.fang} | ${fmtValue(r.jiangZi)} | ${fmtValue(r.jiangName)} | ${fmtValue(r.gan)} |`);
					});
				}
			}
		}
		const jue = jinkouData.topicJue;
		if(jue && jue.items && jue.items.length){
			lines.push(`断诀（${jue.kind}）：`);
			jue.items.forEach((it)=>{
				lines.push(`- ${it.wei}${it.zhi ? `·${it.zhi}` : ''}：${fmtValue(it.xiang)}`);
			});
			(jue.notes || []).forEach((n)=>{ lines.push(`- ${n}`); });
		}
		const sj = jinkouData.shiJian;
		if(sj){
			lines.push(`${sj.title}：月将加于 ${fmtValue(sj.addAt)}，数至 ${fmtValue(sj.diFen)}，得将神 ${fmtValue(sj.jiangZi)}（${fmtValue(sj.jiangName)}）；${sj.note}`);
		}
		const xn = jinkouData.xingNian;
		if(xn){
			lines.push(`金口诀行年（旬法）：${xn.gender}·${xn.age}岁 → 行年 ${xn.ganZhi}（${xn.zhi}）；生年 ${xn.birthGanZi} 属 ${xn.xunHead} 旬，一岁起 ${xn.startGanZi}。`);
			if(xn.ge){ lines.push(`- 灾福歌：${xn.ge}`); }
		}
		lines.push('');
	}

	// 四象所属图 / 四象五行图（右栏「用神」页有、快照此前全缺 → AI 看不到用户看的取象表）。
	if(jinkouData && jinkouData.sixiangShu && jinkouData.sixiangShu.length){
		lines.push('[四象所属]');
		lines.push(`| 位 | 干支 | ${JINKOU_SIXIANG_SHU_COLS.map((c)=>c.label).join(' | ')} |`);
		lines.push(`| --- | --- | ${JINKOU_SIXIANG_SHU_COLS.map(()=>'---').join(' | ')} |`);
		jinkouData.sixiangShu.forEach((r)=>{
			lines.push(`| ${r.label} | ${fmtValue(r.ganzhi)} | ${JINKOU_SIXIANG_SHU_COLS.map((c)=>fmtValue(r[c.key])).join(' | ')} |`);
		});
		lines.push('');
	}
	if(jinkouData && jinkouData.sixiangWuxing && jinkouData.sixiangWuxing.rows && jinkouData.sixiangWuxing.rows.length){
		const sw = jinkouData.sixiangWuxing;
		lines.push('[四象五行]');
		if(sw.mainElem){ lines.push(`主象：${fmtValue(sw.mainElem)}${sw.tianqiText ? `　${sw.tianqiText}` : ''}`); }
		lines.push(`| 位 | 五行 | ${JINKOU_SIXIANG_WUXING_COLS.map((c)=>c.label).join(' | ')} |`);
		lines.push(`| --- | --- | ${JINKOU_SIXIANG_WUXING_COLS.map(()=>'---').join(' | ')} |`);
		sw.rows.forEach((r)=>{
			lines.push(`| ${r.label}${r.kong ? '·空' : ''} | ${fmtValue(r.elem)} | ${JINKOU_SIXIANG_WUXING_COLS.map((c)=>fmtValue(r[c.key])).join(' | ')} |`);
		});
		lines.push('');
	}
	// 方位神煞（飞天五鬼 / 喜神）：右栏「神煞」页有。
	if(jinkouData && jinkouData.fangWeiShensha && jinkouData.fangWeiShensha.length){
		lines.push('[方位神煞]');
		jinkouData.fangWeiShensha.forEach((it)=>{
			lines.push(`${fmtValue(it.name)}：${fmtValue(it.fang)}${it.desc ? `——${it.desc}` : ''}`);
		});
		lines.push('');
	}
	// 合占扣题 + 课分内外：右栏「用神」页有。
	if(jinkouData && (jinkouData.hezhan || jinkouData.neiwai)){
		lines.push('[合占扣题与内外]');
		const hz = jinkouData.hezhan;
		if(hz){
			lines.push(`取用：${fmtValue(hz.usePosition)}　时段：${fmtValue(hz.timeLabel)}${hz.askLabel ? `　所问：${hz.askLabel}` : ''}`);
			// chain 是纯字符串数组（每条自带「取事：/时段：/取用：」前缀），不是对象。
			(hz.chain || []).forEach((c)=>{ if(`${c || ''}`.trim()){ lines.push(`- ${c}`); } });
		}
		const nw = jinkouData.neiwai;
		if(nw && nw.rows && nw.rows.length){
			lines.push(`课分内外：${nw.rows.map((r)=>`${r.side}·${r.label}${r.yong ? '(用)' : ''}=${fmtValue(r.content)}`).join('　')}`);
		}
		lines.push('');
	}
	// 二遁人元 / 次客法 / 移星换将：右栏「专题」页恒产出，AI 此前全看不到。
	if(jinkouData && (jinkouData.erDun || (jinkouData.cike && jinkouData.cike.length) || jinkouData.yiXing)){
		lines.push('[二遁与次客]');
		const ed = jinkouData.erDun;
		if(ed){
			lines.push(`二遁人元：原人元 ${fmtValue(ed.yuan)} → 二遁 ${fmtValue(ed.gan)}、三遁 ${fmtValue(ed.thirdGan)}；衣色 ${fmtValue(ed.se)}、住宅物象 ${fmtValue(ed.xiang)}。`);
		}
		(jinkouData.cike || []).forEach((c)=>{
			const extra = [
				c.guiName ? `次课贵神＝${c.guiName}` : '',
				c.altTimeZi ? `代时之支＝${c.altTimeZi.filter(Boolean).join('、')}` : '',
				c.altDayGan ? `换日干＝${c.altDayGan.filter(Boolean).join('、')}` : '',
				c.altDiFen ? `新地分＝${c.altDiFen}` : '',
				c.jiangZi ? `将神＝${c.jiangZi}` : '',
			].filter(Boolean).join('；');
			lines.push(`- ${fmtValue(c.method)}：${fmtValue(c.note)}${extra ? `（${extra}）` : ''}`);
		});
		const yx = jinkouData.yiXing;
		if(yx){ lines.push(`- 移星换将：${fmtValue(yx.note)}（前日干 ${fmtValue(yx.prevDayGan)}、后日干 ${fmtValue(yx.nextDayGan)}）`); }
		lines.push('');
	}

	lines.push('[贵神月将象意]');
	if(jinkouData && jinkouData.xiangyi){
		const gs = jinkouData.xiangyi.guishen;
		const yj = jinkouData.xiangyi.yuejiang;
		if(gs){ lines.push(`贵神·${gs.name}（${gs.shiti || ''}）：${gs.desc || ''}`); }
		if(yj){ lines.push(`将神·${yj.name}：${yj.desc || ''}`); }
		if(!gs && !yj){ lines.push('无'); }
	}else{
		lines.push('无');
	}
	lines.push('');

	lines.push('[分类用神]');
	if(jinkouData && jinkouData.categoryRules){
		const qc = jinkouData.categoryRules.filter((c)=>c.texts && c.texts.length);
		if(qc.length){
			for(let i=0; i<qc.length; i++){
				lines.push(`${qc[i].name}（用神：${qc[i].yongHint || ''}）`);
				for(let j=0; j<qc[i].texts.length; j++){
					lines.push(`- ${qc[i].texts[j]}`);
				}
			}
		}else{
			lines.push('细则完善中');
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
	appendMapSection(lines, '岁煞', liureng && liureng.godsYear ? liureng.godsYear.taisui1 : null);

	lines.push('[十二长生]');
	if(wuxing){
		// 十二长生 → GFM 表:阶段/地支。土之长生随流派(申/寅),故优先取引擎 phaseTable,
		// 缺省回落共用 wxphase(=默认水土同宫,既有快照逐字零回归)。
		const zsPhase = jinkouData && jinkouData.phaseTable ? jinkouData.phaseTable : null;
		const zsRows = ZSList.map((item)=>[item, fmtValue((zsPhase && zsPhase[item]) || ZhangSheng.wxphase[`${wuxing}_${item}`])]);
		pushMdRows(lines, ['阶段', '地支'], zsRows);
	}else{
		lines.push('无');
	}

	// [YA v42] A 类硬缺:分析 tab「数理 · 太玄数」(renderTaixuan)显示了却不入快照。
	// 取数与 UI 同源(jinkouData.taixuan,行文案同 renderTaixuan 的 value 拼法);无数据不产段。
	const jkTaixuan = jinkouData && jinkouData.taixuan && jinkouData.taixuan.length ? jinkouData.taixuan : [];
	if(jkTaixuan.length){
		lines.push('');
		lines.push('[数理]');
		for(let i=0; i<jkTaixuan.length; i++){
			const t = jkTaixuan[i];
			lines.push(`${t.label}：${t.tokens || '—'}　太玄数 ${t.num}`);
		}
	}
	return lines.join('\n').trim();
}
