import * as LRConst from './LRConst.js';

// 三传「初→中→末」递生递克关系小图（纯 SVG，仅在右栏「取象」tab 顶部显示，绝不画进中栏盘）。
// props.data = { branches:[初,中,末], gans:[遁干×3], dayGan, dayZhi, xunKong:[...] }
// 关系（上→下）：比和 / 生(上生下) / 克(上克下) / 生入(下生上) / 克入(下克上)。

// 五行 / 生克色走明暗成对的主题色(svg 属性里的 var() 随主题即时换值;旧写死色只为暗底挑,金 #b9b3a3 在亮底 2.0:1)
const WX_COLOR = { '木': 'var(--horosa-liureng-stem-wood)', '火': 'var(--horosa-liureng-stem-fire)', '土': 'var(--horosa-liureng-stem-earth)', '金': 'var(--horosa-liureng-stem-metal)', '水': 'var(--horosa-liureng-stem-water)' };
const SHENG = { '木': '火', '火': '土', '土': '金', '金': '水', '水': '木' };
const KE = { '木': '土', '土': '水', '水': '火', '火': '金', '金': '木' };
const POS = ['初传', '中传', '末传'];

function relOf(a, b){
	if(!a || !b){ return null; }
	if(a === b){ return { label: '比和', color: 'var(--horosa-muted, #9a8f7d)' }; }
	if(SHENG[a] === b){ return { label: '生', color: 'var(--horosa-jx-ji)' }; }
	if(KE[a] === b){ return { label: '克', color: 'var(--horosa-jx-xiong)' }; }
	if(SHENG[b] === a){ return { label: '生入', color: 'var(--horosa-hue-teal)' }; }
	if(KE[b] === a){ return { label: '克入', color: 'var(--horosa-hue-orange)' }; }
	return null;
}

// 日禄表(日干临官之支):与小图内联表同一份,抽出供纯函数与组件双用。
const LU_TABLE = { 甲: '寅', 乙: '卯', 丙: '巳', 丁: '午', 戊: '巳', 己: '午', 庚: '申', 辛: '酉', 壬: '亥', 癸: '子' };

// 三传递生递克 + 逐传空/禄/马徽记的**纯函数单源**:此前只有右栏小图会算(relOf 是组件内
// 私有函数),AI 快照的 [三传] 表只有 干支/六亲/贵神,传间生克与逐传徽记一个字都不进 —— 页面看得见、
// AI 看不见。现抽为纯函数,小图与快照(大六壬 + 三式合一)三处同供,永不分叉。
// data = { branches:[初,中,末], gans, dayGan, dayZhi, xunKong:[...] }
export function buildSanChuanRelationFacts(data){
	const d = data || {};
	const branches = Array.isArray(d.branches) ? d.branches.map((b)=>`${b || ''}`.substring(0, 1)) : [];
	if(branches.length < 3 || branches.some((b)=>!b)){ return null; }
	const dayGan = d.dayGan ? `${d.dayGan}`.substring(0, 1) : '';
	const dayZhi = d.dayZhi ? `${d.dayZhi}`.substring(0, 1) : '';
	const xunKong = Array.isArray(d.xunKong) ? d.xunKong.map((z)=>`${z || ''}`.substring(0, 1)) : [];
	const yima = dayZhi ? (LRConst.ZiYiMa[dayZhi] || '') : '';
	const lu = dayGan ? (LU_TABLE[dayGan] || '') : '';
	const wxs = branches.map((b)=>LRConst.GanZiWuXing[b] || '');
	const nodes = branches.map((b, i)=>{
		const tags = [];
		if(xunKong.indexOf(b) >= 0){ tags.push('空'); }
		if(b === lu){ tags.push('禄'); }
		if(b === yima){ tags.push('马'); }
		return { pos: POS[i], branch: b, wuxing: wxs[i], tags };
	});
	const links = [0, 1].map((i)=>{
		const rel = relOf(wxs[i], wxs[i + 1]);
		return { from: POS[i], to: POS[i + 1], rel: rel ? rel.label : '' };
	}).filter((x)=>x.rel);
	return { nodes, links };
}

// 快照/导出用一行摘要:「初传→中传 生;中传→末传 克入」+「初传丑(空·禄)…」;无可算内容返 ''。
export function sanChuanRelationSnapshotLines(data){
	const facts = buildSanChuanRelationFacts(data);
	if(!facts){ return []; }
	const out = [];
	if(facts.links.length){
		out.push(`三传递生递克：${facts.links.map((l)=>`${l.from}→${l.to} ${l.rel}`).join('；')}`);
	}
	const marked = facts.nodes.filter((n)=>n.tags.length);
	if(marked.length){
		out.push(`逐传徽记：${marked.map((n)=>`${n.pos}${n.branch}(${n.tags.join('·')})`).join('；')}`);
	}
	return out;
}
