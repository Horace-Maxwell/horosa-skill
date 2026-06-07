// Vendored from 星阙 JinKouMain.js — 金口诀 AI 快照 20 段（buildJinKouSnapshotText + fmtValue/cleanKey/appendMapSection）。
// 网络/React 部分不取；纯格式化函数，消费 buildJinKouData(解读层) + liureng 前置数据。
import { ZSList, ZhangSheng } from '../liureng/LRZhangSheng.js';

function fmtValue(value){
	if(value === undefined || value === null || value === ''){
		return '无';
	}
	if(value instanceof Array){
		return value.join('、') || '无';
	}
	return `${value}`;
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
		lines.push(`日期：${params.date} ${params.time}`);
		lines.push(`时区：${params.zone}`);
		lines.push(`经纬度：${params.lon} ${params.lat}`);
	}
	if(nongli && nongli.birth){
		lines.push(`真太阳时：${nongli.birth}`);
	}
	if(liureng && liureng.fourColumns){
		const cols = liureng.fourColumns;
		lines.push(`四柱：${fmtValue(cols.year && cols.year.ganzi)}年 ${fmtValue(cols.month && cols.month.ganzi)}月 ${fmtValue(cols.day && cols.day.ganzi)}日 ${fmtValue(cols.time && cols.time.ganzi)}时`);
	}
	lines.push(`贵人体系：${guirenType}`);
	lines.push(`十二长生五行：${fmtValue(wuxing)}`);
	lines.push(`问测人性别：${xingbie}`);
	lines.push('');

	lines.push('[金口诀速览]');
	if(jinkouData && jinkouData.ready){
		lines.push(`地分：${fmtValue(jinkouData.topInfo.diFen)}`);
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
		lines.push(`空亡：${fmtValue(jinkouData.topInfo.xunKong)}`);
		lines.push(`四大空亡：${fmtValue(jinkouData.topInfo.siDaKong)}`);
		if(jinkouData.yongYao && jinkouData.yongYao.label){
			lines.push(`用爻判定：${jinkouData.yongYao.reason || ''}；取${jinkouData.yongYao.label}${jinkouData.yongYao.sign ? `(${jinkouData.yongYao.sign})` : ''}`);
		}
		for(let i=0; i<jinkouData.rows.length; i++){
			const row = jinkouData.rows[i];
			const nayin = row.nayin ? `；纳音=${fmtValue(row.nayin)}` : '';
			lines.push(`${row.label}：天干=${fmtValue(row.gan)}；内容=${fmtValue(row.content)}；神将=${fmtValue(row.shenjiang)}；状态=${fmtValue(row.power)}；空亡=${fmtValue(row.kong)}${nayin}`);
		}
	}else{
		lines.push('无');
	}
	lines.push('');

	lines.push('[金口诀三盘]');
	if(jinkouData && jinkouData.ready && jinkouData.plates && jinkouData.plates.length){
		for(let i=0; i<jinkouData.plates.length; i++){
			const row = jinkouData.plates[i];
			lines.push(`${fmtValue(row.di)}：天盘=${fmtValue(row.tian)}；将神=${fmtValue(row.jiang)}；神盘=${fmtValue(row.shen)}；贵神=${fmtValue(row.gui)}`);
		}
	}else{
		lines.push('无');
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

	lines.push('[四位生克]');
	if(jinkouData && jinkouData.relations && jinkouData.relations.length){
		for(let i=0; i<jinkouData.relations.length; i++){
			const r = jinkouData.relations[i];
			lines.push(`${r.from}${r.rel}${r.to}：${r.text || ''}`);
		}
	}else{
		lines.push('无');
	}
	lines.push('');

	lines.push('[应期]');
	if(jinkouData && jinkouData.yingQi){
		lines.push(`${jinkouData.yingQi.scope}：${jinkouData.yingQi.text}`);
	}else{
		lines.push('无');
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

	lines.push('[分类用神·求财]');
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
		for(let i=0; i<ZSList.length; i++){
			const item = ZSList[i];
			const key = `${wuxing}_${item}`;
			lines.push(`${item}：${fmtValue(ZhangSheng.wxphase[key])}`);
		}
	}else{
		lines.push('无');
	}
	return lines.join('\n').trim();
}
