// 通摄法 AI 快照文本与右栏说明段(世应 / 五行关系 / 五友 / 大格局变化 / 三十二观)
// 从 TongSheFaMain.js 按职责拆出(门面保留原导入路径与对外导出;读源码的检查读「子模块 + 门面」全集,见 scripts/source-sets.json)。
import { safeText, linePolarity, relationByElem, lineAdmit, lineVerb, shortGuaName, getBagua } from './model.js';
import { LEFT_YAO_META, RIGHT_YAO_META, POSITION_KEYS, POSITION_META, OBSERVE_32, FIVE_FRIEND_EXPLANATIONS } from './data.js';

function formatHexName(hex){
	return hex && hex.gua && hex.gua.name ? hex.gua.name : '—';
}

export function formatBaguaLabel(bagua){
	if(!bagua){
		return '—';
	}
	return safeText(bagua.cname || bagua.name);
}

function buildHexSnapshotSection(title, leftHex, rightHex){
	const lines = [];
	lines.push(`【${title}】`);
	lines.push('');
	lines.push(`左卦（${formatHexName(leftHex)}）：`);
	lines.push(`上卦（太阴·本体）：${formatBaguaLabel(leftHex ? leftHex.upper : null)}`);
	lines.push(`下卦（少阳·认识）：${formatBaguaLabel(leftHex ? leftHex.lower : null)}`);
	lines.push('');
	lines.push(`右卦（${formatHexName(rightHex)}）：`);
	lines.push(`上卦（太阳·方法）：${formatBaguaLabel(rightHex ? rightHex.upper : null)}`);
	lines.push(`下卦（少阴·宇宙）：${formatBaguaLabel(rightHex ? rightHex.lower : null)}`);
	return lines;
}

function buildYaoRowsByMain(lines, mainElem){
	const rows = [];
	for(let line=6; line>=1; line--){
		const info = lines[line - 1] || {};
		const polarity = linePolarity(info.value === 1 ? 1 : 0);
		const rel = relationByElem(mainElem, info.elem) || '';
		const relationTag = `${info.branch || ''}${rel}` || '—';
		rows.push(`${line}爻：${polarity}·${relationTag}`);
	}
	return rows;
}

function buildSixYaoMainSection(title, leftLines, rightLines, mainElem){
	const lines = [];
	lines.push(`「${title}」`);
	lines.push('左卦：');
	lines.push(...buildYaoRowsByMain(leftLines, mainElem));
	lines.push('');
	lines.push('右卦：');
	lines.push(...buildYaoRowsByMain(rightLines, mainElem));
	return lines;
}

// 「爻位」页签的逐爻取纳判语与「取舍总览」两块此前完全不进快照:页面逐爻写
// 「N爻(角色)为阳/阴(纳/拒)。我看重/蔑视【对象】」(左卦思想、右卦实践),末附取舍两栏。
// 与 UI 严格同源(同 LEFT/RIGHT_YAO_META + linePolarity/lineAdmit/lineVerb),并按裁决作**默认关候选段**
// (段名已登记 AI_EXPORT_PRESET_SECTIONS.tongshefa 与 DEFAULT_OFF;未自定义用户缺省不纳入=字节零回归)。
function buildYaoWeiSection(model){
	if(!model || !model.baseLeft || !model.baseRight
		|| !Array.isArray(model.baseLeft.lines) || !Array.isArray(model.baseRight.lines)){ return []; }
	const sideLines = (hex, meta)=>hex.lines.map((value, idx)=>{
		const m = meta[idx] || {};
		return `${idx + 1}爻（${m.role || ''}）为${linePolarity(value)}（${lineAdmit(value)}）。我${lineVerb(value)}【${m.target || ''}】。`;
	}).reverse();
	const pick = (value)=>model.baseLeft.lines.map((line, idx)=>(
		line === value && LEFT_YAO_META[idx] ? `思想·${LEFT_YAO_META[idx].role}：${LEFT_YAO_META[idx].target}` : null
	)).filter(Boolean).concat(model.baseRight.lines.map((line, idx)=>(
		line === value && RIGHT_YAO_META[idx] ? `实践·${RIGHT_YAO_META[idx].role}：${RIGHT_YAO_META[idx].target}` : null
	)).filter(Boolean));
	const lines = [];
	lines.push('【爻位】');
	lines.push('');
	lines.push(`左卦（${shortGuaName(model.baseLeft.gua ? model.baseLeft.gua.name : '左卦')}）· 思想上：`);
	sideLines(model.baseLeft, LEFT_YAO_META).forEach((t)=>lines.push(t));
	lines.push('');
	lines.push(`右卦（${shortGuaName(model.baseRight.gua ? model.baseRight.gua.name : '右卦')}）· 实践上：`);
	sideLines(model.baseRight, RIGHT_YAO_META).forEach((t)=>lines.push(t));
	const zhong = pick(0);
	const mie = pick(1);
	if(zhong.length || mie.length){
		lines.push('');
		lines.push('取舍总览：');
		lines.push(`我看重：${zhong.length ? zhong.join('；') : '—'}`);
		lines.push(`我蔑视：${mie.length ? mie.join('；') : '—'}`);
	}
	return lines;
}

export function buildTongSheFaSnapshot(model){
	const parts = [];
	parts.push(...buildHexSnapshotSection('本卦', model.baseLeft, model.baseRight));
	parts.push('');
	parts.push('【六爻】');
	parts.push('');
	parts.push(...buildSixYaoMainSection(
		`左卦（${safeText(model.leftElem)}；思想；${safeText(model.leftHouseLabel)}）为主`,
		model.leftLines,
		model.rightLines,
		model.leftElem
	));
	parts.push('');
	parts.push(...buildSixYaoMainSection(
		`右卦（${safeText(model.rightElem)}；实践；${safeText(model.rightHouseLabel)}）为主`,
		model.leftLines,
		model.rightLines,
		model.rightElem
	));
	parts.push('');
	parts.push(...buildHexSnapshotSection('潜藏', model.mutualLeft, model.mutualRight));
	parts.push('');
	parts.push(...buildHexSnapshotSection('亲和', model.oppositeLeft, model.oppositeRight));
	// A 类硬缺(全场最薄):纳甲筮法 tab 的整个计算分析层(世应/左右五行/五友/大局升降爻变)
	// UI 已显示(renderNaJiaTab 系列卡片)却此前不入快照。段名已登记 AI_EXPORT_PRESET_SECTIONS.tongshefa;
	// 取数与 UI 严格同源(同 model 派生、同 relationByElem/groupFiveFriendItems/fmtRise 等函数);空数据不产段。
	[
		buildYaoWeiSection(model),
		buildObserve32Section(model),
		buildShiYingSection(model),
		buildWuXingRelationSection(model),
		buildFiveFriendSection(model),
		buildBigPatternChangeSection(model),
	].forEach((sectionLines)=>{
		if(sectionLines.length){
			parts.push('');
			parts.push(...sectionLines);
		}
	});
	return parts.join('\n').replace(/\n{3,}/g, '\n\n').trim();
}

function fmtRise(attacks){
	if(!attacks || attacks.length === 0){
		return '无';
	}
	return attacks.map((item)=>{
		return `${item.from}爻击${item.targets.join('、')}爻`;
	}).join('；');
}

function fmtPatternDetail(pattern){
	if(!pattern || !pattern.details){
		return '—';
	}
	return pattern.details.map((item)=>`${item.from}/${item.to}:${item.branchPair || '—'}${item.status === '无' ? '' : item.status}`).join('，');
}

export function groupFiveFriendItems(mainElem, leftLines, rightLines){
	const list = [];
	leftLines.forEach((info, idx)=>{
		list.push({
			relation: relationByElem(mainElem, info.elem),
			label: `左${idx + 1}`,
			role: LEFT_YAO_META[idx] ? LEFT_YAO_META[idx].role : `${idx + 1}爻`,
			branch: info.branch || '',
			elem: info.elem || '',
		});
	});
	rightLines.forEach((info, idx)=>{
		list.push({
			relation: relationByElem(mainElem, info.elem),
			label: `右${idx + 1}`,
			role: RIGHT_YAO_META[idx] ? RIGHT_YAO_META[idx].role : `${idx + 1}爻`,
			branch: info.branch || '',
			elem: info.elem || '',
		});
	});
	return list.reduce((acc, item)=>{
		const key = item.relation || '—';
		if(!acc[key]){
			acc[key] = [];
		}
		acc[key].push(item);
		return acc;
	}, {});
}

export function fiveFriendDynamicText(key, items){
	if(!items || items.length === 0){
		return '当前未见此类关系。';
	}
	const positions = items.map((item)=>`${item.label}（${item.role}·${item.branch}${item.elem}）`).join('、');
	const roles = items.map((item)=>item.role).join('、');
	switch(key){
		case '鬼':
			return `${positions}为鬼；这些层面会形成压力与拘束，使人服从、顾忌，难以轻易越界。`;
		case '爱':
			return `${positions}为爱；这些层面是心之所向，显示人希望得到、亲近或成就的方向。`;
		case '制':
			return `${positions}为制；这些层面容易被看作可掌控、可支配、可调用的资源。`;
		case '同':
			return `${positions}为同；这些层面与自身目标相近，既可共利同行，也可能因同类相争而冲突。`;
		case '义':
			return `${positions}为义；${roles}会成为助力、保护与恩惠之源，给人力量。`;
		default:
			return positions;
	}
}

export function patternExplanation(context, type){
	if(type === '六穿'){
		return `${context}上见全局相穿：心智的不同层面互相战斗，互不相让，互相否定，为的是分出一个胜者。穿，是锋芒、战斗与一击致命的意象。`;
	}
	if(type === '六合'){
		return `${context}上见全局相合：有混元一切的倾向。对于事实、行为、遭遇，一口吞下，平等看待，认为万物一体，混同你我。`;
	}
	return '';
}

// 三十二观(右栏默认首 tab 的核心观文层)入快照 —— 与 renderObserveTab 严格同源
// (同 POSITION_KEYS/META、同 OBSERVE_32 取文);此前 AI 只见卦名不见本法核心解读。
function buildObserve32Section(model){
	const out = [];
	if(!model || !model.selected){ return out; }
	out.push('【三十二观】');
	POSITION_KEYS.forEach((posKey)=>{
		const meta = POSITION_META[posKey];
		const trigram = model.selected[posKey];
		const bagua = getBagua(trigram);
		if(!meta || !bagua){ return; }
		const observe = OBSERVE_32[meta.observeKey];
		const desc = observe && observe.items ? observe.items[bagua.key] : '';
		if(desc){ out.push(`${meta.label}·${bagua.symbol || ''}${bagua.cname || ''}:${observe.intro || ''}${desc}`); }
	});
	return out.length > 1 ? out : [];
}

// ——以下四个函数为 AI 快照新增段(纳甲筮法 tab 的计算分析层),供 buildTongSheFaSnapshot 调用——
// 与 UI 严格同源:世应/五行展开取 model.leftLines/rightLines(renderShiYingCard/renderNaJiaTab 同一数据),
// 五友取 groupFiveFriendItems+fiveFriendDynamicText(renderFiveFriendsCard 同一函数),
// 大局/升降/爻变取 leftBigPattern/leftRise/yaoChanges(renderBigPatternDetailCard/renderRiseDetailCard/renderYaoChangeDetailCard 同一数据)。

// [世应] 单侧行:与 renderShiYingSide 同构(idx+1 爻·爻位角色·地支五行+本卦关系),无标记时与 UI 同文案。
function buildShiYingSideLines(title, lines, metas){
	const out = [];
	out.push(`◆ ${title}`);
	const items = [];
	(lines || []).forEach((info, idx)=>{
		if(!info || !info.shiYing){
			return;
		}
		const meta = metas[idx] || {};
		const rel = info.ownRel || '';
		items.push(`| ${info.shiYing} | ${idx + 1}爻 | ${meta.role || `${idx + 1}爻`} | ${info.branch || ''}${info.elem || ''}${rel} |`);
	});
	if(items.length === 0){
		out.push('未标出世应');
	}else{
		out.push('| 世应 | 爻 | 爻位 | 地支五行 |');
		out.push('| --- | --- | --- | --- |');
		out.push(...items);
	}
	return out;
}

export function buildShiYingSection(model){
	const leftLines = model && model.leftLines ? model.leftLines : [];
	const rightLines = model && model.rightLines ? model.rightLines : [];
	const hasAny = leftLines.some((info)=>info && info.shiYing) || rightLines.some((info)=>info && info.shiYing);
	if(!hasAny){
		return [];
	}
	const parts = [];
	parts.push('【世应】');
	parts.push('世爻=着眼点；应爻=吸引点。');
	parts.push(...buildShiYingSideLines('左卦 · 思想', leftLines, LEFT_YAO_META));
	parts.push(...buildShiYingSideLines('右卦 · 实践', rightLines, RIGHT_YAO_META));
	return parts;
}

// [五行关系] = 左右卦主关系(mainRelation) + 左右卦五行展开表(renderNaJiaTab baseRows 同构:
// 逐爻 阴阳画 + 地支五行 + 对本卦五行关系 + 世应标记),含 UI 同款图例行。
export function buildWuXingRelationSection(model){
	const leftLines = model && model.leftLines ? model.leftLines : [];
	const rightLines = model && model.rightLines ? model.rightLines : [];
	if(leftLines.length === 0 && rightLines.length === 0){
		return [];
	}
	const parts = [];
	parts.push('【五行关系】');
	parts.push(`主关系：${model.mainRelation}（${model.mainRelationLabel || ''}）`);
	parts.push(`左卦：${model.leftElem || '—'}（思想） · ${model.leftHouseLabel}`);
	parts.push(`右卦：${model.rightElem || '—'}（实践） · ${model.rightHouseLabel}`);
	parts.push('◆ 左右卦五行展开');
	parts.push('| 爻 | 左 | 右 |');
	parts.push('| --- | --- | --- |');
	for(let line=6; line>=1; line--){
		const idx = line - 1;
		const left = leftLines[idx] || {};
		const right = rightLines[idx] || {};
		const leftOwn = relationByElem(model.leftElem, left.elem);
		const rightOwn = relationByElem(model.rightElem, right.elem);
		const leftFive = `${safeText(left.branch, '')}${safeText(left.elem, '')}${leftOwn || ''}` || '—';
		const rightFive = `${safeText(right.branch, '')}${safeText(right.elem, '')}${rightOwn || ''}` || '—';
		const leftSY = left.shiYing ? `（${left.shiYing}）` : '';
		const rightSY = right.shiYing ? `（${right.shiYing}）` : '';
		parts.push(`| ${line}爻 | ${left.pattern || '—'} ${leftFive}${leftSY} | ${right.pattern || '—'} ${rightFive}${rightSY} |`);
	}
	parts.push('鬼=压力与拘束；爱=心之所向；制=我所欲控；同=竞争关系；义=恩人贵人。');
	parts.push('世爻=着眼点；应爻=吸引点。');
	return parts;
}

// [五友] = 左卦为主/右卦为主 两侧五类关系分组(鬼/爱/制/同/义),判语用 fiveFriendDynamicText
// (含爻位归组即计算结果本体;长静态定义文案不重复导出)。
function buildFiveFriendSection(model){
	const leftLines = model && model.leftLines ? model.leftLines : [];
	const rightLines = model && model.rightLines ? model.rightLines : [];
	if(leftLines.length === 0 && rightLines.length === 0){
		return [];
	}
	const parts = [];
	parts.push('【五友】');
	[
		{ title: '左卦为主', context: '思想', mainElem: model.leftElem },
		{ title: '右卦为主', context: '实践', mainElem: model.rightElem },
	].forEach((side)=>{
		parts.push(`◆ ${side.title}（${side.mainElem || '—'}·${side.context}）`);
		const groups = groupFiveFriendItems(side.mainElem, leftLines, rightLines);
		FIVE_FRIEND_EXPLANATIONS.forEach((item)=>{
			const rows = groups[item.key] || [];
			parts.push(`${item.key}（${item.title}）：${fiveFriendDynamicText(item.key, rows)}`);
		});
	});
	return parts;
}

// [大局与动变] = 六穿/六合大局(fmtPatternDetail 逐对明细+成局判语) + 升降(fmtRise) + 逐爻爻变。
function buildBigPatternChangeSection(model){
	if(!model){
		return [];
	}
	const yaoChanges = model.yaoChanges || [];
	const hasCore = model.leftBigPattern || model.rightBigPattern
		|| (model.leftRise && model.leftRise.length) || (model.rightRise && model.rightRise.length)
		|| yaoChanges.length;
	if(!hasCore){
		return [];
	}
	const parts = [];
	parts.push('【大局与动变】');
	parts.push('◆ 大局');
	[
		{ title: '左卦（思想）', context: '思想', pattern: model.leftBigPattern },
		{ title: '右卦（实践）', context: '实践', pattern: model.rightBigPattern },
	].forEach((side)=>{
		const type = side.pattern && side.pattern.type ? side.pattern.type : '无';
		parts.push(`${side.title}：${type}；${fmtPatternDetail(side.pattern)}`);
		const explanation = patternExplanation(side.context, type);
		if(explanation){
			parts.push(explanation);
		}
	});
	parts.push('◆ 升降');
	parts.push(`左卦（思想）：${fmtRise(model.leftRise)}`);
	parts.push(`右卦（实践）：${fmtRise(model.rightRise)}`);
	parts.push('◆ 爻变');
	if(yaoChanges.length){
		parts.push(yaoChanges.map((item)=>`${item.line}爻${item.changed ? '有变' : '不变'}`).join('；'));
	}else{
		parts.push('无');
	}
	return parts;
}
