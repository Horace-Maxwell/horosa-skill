// 六壬「取象 / 类象」解读层数据与聚合（纯前端，解读层，零回归——仅被「取象」开关开启时使用）。
//
// 复用既有数据，不重建：
//   · 地支类象  ← LRShenJiangDoc.SHEN_INFO[支].symbol（六壬已有）
//   · 天干象意  ← 遁甲 QimenXiangDoc 的「十天干」（buildQimenXiangTipObj('stem', 干)）
// 本文件只新增「五行取象 + 方位」，并提供一个聚合函数 buildXiangContext，
// 把某地支的 类象 / 五行 / 方位 / 六亲 / 刑冲合害 / 驿马 / 长生旺衰 汇成一个对象，供右栏「取象」卡使用。
//
// 注：渲染层一律不标技法出处（不写人名/书名）。

import * as LRConst from './LRConst.js';
import { ZhangSheng, ZSList } from './LRZhangSheng.js';
import { getShenPublic } from './LRShenJiangDoc.js';
import { buildQimenXiangTipObj } from '../dunjia/QimenXiangDoc.js';

// 五行取象（含克应口诀）。公版常识，重编。
export const WUXING_XIANG = {
	'木': { keyword: '生发·条达', person: '仁人 / 文士 / 林木业', body: '肝胆 / 筋 / 头发 / 四肢', affair: '升迁 / 谋划 / 草创 / 竞争', prosper: '得财、向上、伸展', restrain: '受制、折损、口舌' },
	'火': { keyword: '光明·礼文', person: '文人 / 美人 / 电业', body: '心 / 血 / 眼目 / 小肠', affair: '文书 / 信息 / 口舌 / 喜庆', prosper: '光显、文章、热络', restrain: '惊恐、虚耗、目疾' },
	'土': { keyword: '厚载·稼穑', person: '田农 / 中人 / 信厚者', body: '脾胃 / 肌肉 / 腹', affair: '田宅 / 财货 / 中介 / 守成', prosper: '稳实、聚财、得众', restrain: '壅滞、湿病、迟疑' },
	'金': { keyword: '肃杀·刚决', person: '武人 / 工匠 / 金玉业', body: '肺 / 骨 / 牙', affair: '刀兵 / 决断 / 财帛 / 道路', prosper: '刚断、得权、利器', restrain: '血光、刀伤、肃杀' },
	'水': { keyword: '润下·智巧', person: '妇女 / 智者 / 水产业', body: '肾 / 膀胱 / 耳 / 精血', affair: '阴私 / 智谋 / 盗讼 / 漂泊', prosper: '聪慧、流通、暗助', restrain: '溺险、阴病、奸盗' },
};

// 十二支方位（公版）。
export const ZI_DIRECTION = {
	'子': '正北', '丑': '东北偏北', '寅': '东北偏东', '卯': '正东', '辰': '东南偏东', '巳': '东南偏南',
	'午': '正南', '未': '西南偏南', '申': '西南偏西', '酉': '正西', '戌': '西北偏西', '亥': '西北偏北',
};

const REL_TABLES = [
	['刑', LRConst.ZiXing],
	['冲', LRConst.ZiCong],
	['六合', LRConst.ZiHe],
	['害', LRConst.ZiHai],
	['破', LRConst.ZiPo],
];

// 刑冲破害合·断用(§22.2)。蜜中砒霜=合中带刑害(外合内离)单列。
const REL_NOTE = {
	'刑': '刑伤、官非、互害(子卯无礼凶意最甚;辰午酉亥自刑,自寻烦恼)',
	'冲': '冲动、离散、急速、变动(返吟全冲主动荡、聚散无常)',
	'六合': '和合、成就,亦主牵绊迟缓(占病讼逢合反缠绕难了)',
	'害': '妨害、暗损、骨肉相残(六壬「涉害课」≠地支六害,勿混)',
	'破': '破败、分离(六壬中地位最弱,多作辅参)',
	'三合': '党类众助、成事(三传成局即全局课)',
};

// 选定五行于某支的十二长生状态（沿用既有「十二长生」口径：ZhangSheng.wxphase['<五行>_<长生名>'] = 支，此处反查支→长生名）。
function getZhangShengState(elem, branch){
	try{
		if(!elem || !branch || !ZhangSheng || !ZhangSheng.wxphase || !Array.isArray(ZSList)){
			return '';
		}
		for(let i=0; i<ZSList.length; i++){
			if(ZhangSheng.wxphase[`${elem}_${ZSList[i]}`] === branch){
				return ZSList[i];
			}
		}
		return '';
	}catch(e){
		return '';
	}
}

// 天干象意（复用遁甲「十天干」）。返回去标题的文本行数组；遁甲数据缺失时返回空数组。
export function getGanXiangLines(gan){
	const g = `${gan || ''}`.trim().substring(0, 1);
	if(!g){
		return [];
	}
	try{
		const tip = buildQimenXiangTipObj('stem', g);
		if(tip && Array.isArray(tip.tips)){
			return tip.tips.map((t)=>`${t || ''}`.replace(/\*\*/g, '').trim()).filter(Boolean);
		}
	}catch(e){
		/* 遁甲数据不可用则跳过 */
	}
	return [];
}

// 聚合某地支的取象上下文（供右栏「取象」卡 / 后续悬浮补充）。无效支返回 null。
export function buildXiangContext(branch, dayGan, elem){
	const zhi = `${branch || ''}`.trim().substring(0, 1);
	if(!zhi || LRConst.ZiList.indexOf(zhi) < 0){
		return null;
	}
	const shen = typeof getShenPublic === 'function' ? getShenPublic(zhi) : null;
	const wx = LRConst.GanZiWuXing[zhi] || '';
	const gan = `${dayGan || ''}`.trim().substring(0, 1);
	const liuqin = (gan && LRConst.ZiLiuQin[zhi]) ? (LRConst.ZiLiuQin[zhi][gan] || '') : '';
	const relations = [];
	REL_TABLES.forEach(([label, table])=>{
		const t = table ? table[zhi] : null;
		if(!t){
			return;
		}
		if(Array.isArray(t)){
			if(t.length){ relations.push(`${label}：${t.join('、')}`); }
		}else if(t === zhi){
			relations.push(`自${label}`);
		}else{
			relations.push(`${label}：${t}`);
		}
	});
	const sangHe = LRConst.ZiSangHe[zhi];
	if(Array.isArray(sangHe) && sangHe.length){
		relations.push(`三合：${sangHe.join('、')}`);
	}
	// 刑冲破害合 断语(§22.2):五类通则每支皆有(刑/冲/六合/六害/六破 均为 12 键全映射),
	// 故此五条对任何支恒列出=通则说明,不是「该支独有」——[Issue#75 同批] 注释按实修正,行为不变。
	const relationNotes = [];
	const hasRel = (label, table)=>{ const t = table ? table[zhi] : null; return Array.isArray(t) ? t.length > 0 : !!t; };
	['刑', '冲', '六合', '害', '破'].forEach((label)=>{
		const tbl = (REL_TABLES.find((r)=>r[0] === label) || [])[1];
		if(hasRel(label, tbl)){ relationNotes.push({ type: label, note: REL_NOTE[label] }); }
	});
	if(Array.isArray(sangHe) && sangHe.length){ relationNotes.push({ type: '三合', note: REL_NOTE['三合'] }); }
	// 蜜中砒霜:本支的**六合之支**恰又与本支相刑或相害(外合内离)。
	// [Issue#75 同批] 旧判据 hasRel('六合')&&(hasRel('刑')||hasRel('害')) 三张表都是 12 键全映射
	// → 条件恒真,十二支全被标「蜜中砒霜」并红字高亮(10 例假阳),AI 快照亦逐支下「外合内离」断语。
	// 正解按「合支 ≡ 刑支/害支」判:全域实测仅 巳/申 命中(巳申既六合又在寅巳申三刑内)。
	const _he = LRConst.ZiHe ? LRConst.ZiHe[zhi] : null;
	const _xing = LRConst.ZiXing ? LRConst.ZiXing[zhi] : null;
	const _hai = LRConst.ZiHai ? LRConst.ZiHai[zhi] : null;
	const _heHitsXingHai = !!_he && (
		_xing === _he || _hai === _he
		|| (LRConst.ZiXing && LRConst.ZiXing[_he] === zhi)
		|| (LRConst.ZiHai && LRConst.ZiHai[_he] === zhi)
	);
	if(_heHitsXingHai){
		relationNotes.push({ type: '蜜中砒霜', note: '合中带刑害——外合内离、看似团结实则分裂' });
	}
	return {
		branch: zhi,
		shenName: shen && shen.name ? shen.name : '',     // 月将古名（如「神后」）
		symbol: shen && shen.symbol ? shen.symbol : '',   // 类象串
		wuxing: wx,
		wuxingXiang: WUXING_XIANG[wx] || null,
		direction: ZI_DIRECTION[zhi] || '',
		liuqin,
		relations,
		relationNotes,
		yima: LRConst.ZiYiMa[zhi] || '',
		zhangsheng: getZhangShengState(elem, zhi),
		zhangshengElem: `${elem || ''}`,
	};
}
