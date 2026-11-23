// 六壬页 · 概览参考:毕法检索、参考文档正文、概览参考段与按课盘匹配概览参考(上下文 / 大格 / 小局匹配在 referenceMatch)。
// 只被 components/lrzhan/LiuRengMain.js 与同目录 main/ 下的兄弟模块引用。
import * as LRConst from '../../liureng/LRConst.js';
import { normalizeLiuRengJiangName } from '../../liureng/LRShenJiangDoc.js';
import { MONTH_BRANCH_SEQUENCE, uniqueStrings, safeRestrain, getSeasonStateForBranch, isWangXiangState } from './ganzhiHelpers.js';
import { matchesUserQuery } from '../../utils/scriptMode.js';
import { DA_GE_REFERENCE_TEXT } from './referenceDaGe.js';
import { XIAO_JU_REFERENCE_TEXT } from './referenceXiaoJu.js';

// 毕法 tab 的「全部毕法」检索:法号 + 法名 + 诀文 + 释义里含检索词(分大小写,与原先同口径);
// 比对经 matchesUserQuery —— 界面繁体时照屏幕输入繁体也能命中;简体模式与原先逐字节等价。
export function filterBiFaListByQuery(list, query){
	const src = Array.isArray(list) ? list : [];
	const q = `${query || ''}`.trim();
	if(!q){ return src; }
	return src.filter((b)=>matchesUserQuery(`${b.no}${b.name}${b.verse}${b.explain}`, q, { ci: false }));
}

export function buildReferenceDocumentText(item, type){
	if(!item){
		return '';
	}
	const dict = type === 'dage' ? DA_GE_REFERENCE_TEXT : (type === 'xiaoju' ? XIAO_JU_REFERENCE_TEXT : null);
	const detail = dict && item.key ? dict[item.key] : null;
	const parts = [];
	if(detail && detail.poem){
		parts.push(`${detail.poem}`.trim());
	}
	const xunzhuLines = [];
	if(detail && detail.note){
		xunzhuLines.push(`${detail.note}`.trim());
	}
	if(detail && detail.jushi){
		xunzhuLines.push(`局式： ${detail.jushi}`);
	}
	if(detail && detail.juyi){
		xunzhuLines.push(`局义： ${detail.juyi}`);
	}
	if(detail && detail.juzhu){
		xunzhuLines.push(`局注： ${detail.juzhu}`);
	}
	if(xunzhuLines.length){
		parts.push(`荀注：\n${xunzhuLines.join('\n')}`.trim());
	}
	if(detail && detail.basis){
		parts.push(`依据：\n${detail.basis}`.trim());
	}
	if(parts.length){
		return parts.join('\n\n').trim();
	}
	const fallback = [];
	if(item.condition){
		fallback.push(`局式： ${item.condition}`);
	}
	if(item.summary){
		fallback.push(`局义： ${item.summary}`);
	}
	return fallback.join('\n');
}

export const GU_CHEN_GUA_SU_BY_SEASON = {
	spring: { guchen: '巳', guasu: '丑' },
	summer: { guchen: '申', guasu: '辰' },
	autumn: { guchen: '亥', guasu: '未' },
	winter: { guchen: '寅', guasu: '戌' },
};

export const TIANJIANG_JI = ['贵人', '六合', '青龙', '太常', '太阴', '天后'];
export const TIANJIANG_XIONG = ['螣蛇', '朱雀', '勾陈', '天空', '白虎', '玄武'];
const FOUR_SEASON_BRANCHES = ['辰', '戌', '丑', '未'];
const ZHUQUE_KAIKOU_MONTH_BRANCH = ['巳', '辰', '午', '未', '卯', '寅', '申', '酉', '丑', '子', '戌', '亥'];
const ZHUQUE_XIANWU_MONTH_BRANCH = ['酉', '巳', '丑', '子', '申', '辰', '卯', '亥', '未', '午', '寅', '戌'];
const GOUCHEN_BAJIAN_MONTH_BRANCH = ['巳', '辰', '卯', '寅', '丑', '子', '亥', '戌', '酉', '申', '未', '午'];

function normalizeOverviewGodName(name){
	const raw = `${name || ''}`.trim();
	if(!raw){
		return '';
	}
	return normalizeLiuRengJiangName(raw);
}

function getMonthIndexByBranch(branch){
	const idx = MONTH_BRANCH_SEQUENCE.indexOf(branch);
	return idx >= 0 ? idx + 1 : -1;
}

function isBranchSetIncludes(target, arr){
	if(!target || !arr || !arr.length){
		return false;
	}
	return arr.indexOf(target) >= 0;
}

export function buildOverviewReferenceText(item){
	if(!item){
		return '';
	}
	const parts = [];
	if(item.verse){
		parts.push(`${item.verse}`.trim());
	}
	if(item.note){
		parts.push(`荀注：${item.note}`.trim());
	}
	return parts.join('\n\n').trim();
}

function mergeOverviewRefsByName(items){
	if(!Array.isArray(items) || items.length === 0){
		return [];
	}
	const merged = [];
	const mergeMap = {};
	const mergeText = (a, b, sep = '\n')=>{
		const parts = uniqueStrings([a, b].filter(Boolean).map((item)=>`${item}`.trim())).filter(Boolean);
		return parts.join(sep);
	};
	items.forEach((item)=>{
		if(!item){
			return;
		}
		const mergeKey = `${item.group || ''}_${item.name || ''}`;
		if(!mergeKey.trim()){
			merged.push(item);
			return;
		}
		const existed = mergeMap[mergeKey];
		if(!existed){
			const one = {
				...item,
				evidence: uniqueStrings(item.evidence || []),
			};
			mergeMap[mergeKey] = one;
			merged.push(one);
			return;
		}
		existed.evidence = uniqueStrings([...(existed.evidence || []), ...((item && item.evidence) || [])]);
		existed.verse = mergeText(existed.verse, item.verse, '\n');
		existed.note = mergeText(existed.note, item.note, '；');
		existed.summary = mergeText(existed.summary, item.summary, '；');
		existed.key = mergeText(existed.key, item.key, '__');
	});
	return merged;
}

export function matchLiuRengOverviewReferences(context){
	if(!context){
		return [];
	}
	const refs = [];
	const refMap = {};
	const push = (group, key, title, verse, summary, evidence, note = '')=>{
		const uniqEvidence = uniqueStrings(evidence || []);
		if(uniqEvidence.length === 0){
			return;
		}
		const uniqKey = `${group}_${key}`;
		const existed = refMap[uniqKey];
		if(existed){
			existed.evidence = uniqueStrings([...(existed.evidence || []), ...uniqEvidence]);
			if(!existed.note && note){
				existed.note = note;
			}
			if(!existed.summary && summary){
				existed.summary = summary;
			}
			if(!existed.verse && verse){
				existed.verse = verse;
			}
			return;
		}
		const one = {
			group,
			key: `${group}_${key}`,
			name: title,
			verse,
			note,
			summary,
			evidence: uniqEvidence,
		};
		refMap[uniqKey] = one;
		refs.push(one);
	};
	const firstRole = {
		role: '发用',
		god: normalizeOverviewGodName(context.firstGod),
		branch: context.firstBranch,
		gan: context.firstGan,
	};
	const dayRole = {
		role: '日干上神',
		god: normalizeOverviewGodName(context.branchGodMap ? context.branchGodMap[context.ke1Up] : ''),
		branch: context.ke1Up,
		gan: context.ke1UpGan,
	};
	const roles = [firstRole, dayRole];
	const monthBranch = context.monthBranch;
	const monthIndex = getMonthIndexByBranch(monthBranch);
	const dayHeGan = context.dayGan ? LRConst.GanHe[context.dayGan] : '';
	const hasMonthTianDe = !!(
		context.dayGodMap
		&& context.dayGodMap.base
		&& (context.dayGodMap.base['月德'] || context.dayGodMap.base['天德'])
	);
	roles.forEach((roleObj)=>{
		const roleName = roleObj.role;
		const god = roleObj.god;
		const branch = roleObj.branch;
		const gan = roleObj.gan;
		if(!god || !branch){
			return;
		}
		if(god === '天乙' && isBranchSetIncludes(branch, ['丑', '未'])){
			push(
				'laiyi',
				'tianyi',
				'天乙决',
				'贵人丑未下，定危问小儿。',
				'贵人加丑未，多主择日、急务或小儿相关之问。',
				[`${roleName}见天乙临${branch}`],
			);
		}
		if(god === '六合' && (branch === context.dayGanBranch || (context.horseBranches || []).indexOf(branch) >= 0)){
			push(
				'laiyi',
				'liuhe_luma',
				'六合决',
				'六合加禄马，行职最宜鞍。',
				'六合临禄马，多主行职、差遣、出行、赴任之问。',
				[
					`${roleName}见六合临${branch}`,
					branch === context.dayGanBranch ? `临禄位（${context.dayGanBranch}）` : '',
					(context.horseBranches || []).indexOf(branch) >= 0 ? `临驿马（${branch}）` : '',
				],
			);
		}
		if(god === '螣蛇' && isBranchSetIncludes(branch, ['巳', '午', '卯'])){
			push(
				'laiyi',
				'tengshe',
				'螣蛇决',
				'螣蛇巳午卯，梦寝虚惊怪。若非戾财失，即是众悖乖。',
				'螣蛇临巳午卯，多见虚惊怪梦、财失或人事乖悖。',
				[`${roleName}见螣蛇临${branch}`],
			);
		}
		if(god === '朱雀'){
			push(
				'laiyi',
				'zhuque',
				'朱雀决',
				'朱雀信息来，杀神应官灾。遇月天两德，呼为炉冶财。',
				'朱雀主信息文书；并杀气则偏官灾，得月德天德可转炉冶财利。',
				[
					`${roleName}见朱雀临${branch}`,
					hasMonthTianDe ? '盘中见月德/天德' : '',
				],
			);
		}
		if(god === '六合' && isBranchSetIncludes(branch, ['卯', '酉'])){
			push(
				'laiyi',
				'liuhe_maoyou',
				'六合决',
				'六合乘卯酉，婚孕事分明。若临日辰上，唇舌钱立生。',
				'六合临卯酉偏婚孕与合议；并临日辰，口舌财事并发。',
				[
					`${roleName}见六合临${branch}`,
					(branch === context.dayGanBranch || branch === context.dayZhi) ? '并临日辰位' : '',
				],
			);
		}
		if(god === '勾陈' && (context.season === 'spring' || isBranchSetIncludes(branch, ['卯', '酉']))){
			push(
				'laiyi',
				'gouchen',
				'勾陈决',
				'勾陈春二八，官讼要争论。阳绝并阴绝，病者连绵昏。',
				'勾陈见春或卯酉，多主官讼争执，病事则绵延不解。',
				[
					`${roleName}见勾陈临${branch}`,
					context.season === 'spring' ? '时在春令' : '',
				],
				'春为寅卯，二八为卯酉。',
			);
		}
		if(god === '青龙' && (gan === dayHeGan || branch === context.dayGanBranch)){
			push(
				'laiyi',
				'qinglong',
				'青龙诀',
				'青龙当干合，财隆百事安。求官并借职，书信往来传。',
				'青龙得干合/禄位，多主财禄与求官、往来文书之利。',
				[
					`${roleName}见青龙临${branch}`,
					gan && dayHeGan && gan === dayHeGan ? `与日干成合（${context.dayGan}↔${gan}）` : '',
					branch === context.dayGanBranch ? `临日干禄位（${context.dayGanBranch}）` : '',
				],
			);
		}
		if(god === '天空'){
			push(
				'laiyi',
				'tiankong',
				'天空决',
				'天空有失亡，魁罡仆不良。若临干旺相，营作运行商。',
				'天空主失亡虚耗；逢魁罡偏仆役不良，旺相可转营作与行商。',
				[
					`${roleName}见天空临${branch}`,
					isBranchSetIncludes(branch, ['辰', '戌']) ? '临魁罡位' : '',
					isWangXiangState(getSeasonStateForBranch(context.seasonMap, branch)) ? '临旺相地' : '',
				],
			);
		}
		if(god === '白虎'){
			push(
				'laiyi',
				'baihu',
				'白虎决',
				'白虎临门叹，病侵老幼俩。午未兼申酉，殴斗事起他。',
				'白虎多主病灾惊惧；临午未申酉，斗殴冲突之象更显。',
				[
					`${roleName}见白虎临${branch}`,
					isBranchSetIncludes(branch, ['午', '未', '申', '酉']) ? '临午未申酉位' : '',
				],
			);
		}
		if(god === '太常'){
			push(
				'laiyi',
				'taichang',
				'太常决',
				'太常旺今朝，衣裳财文章。禄上加合上，筵开亲戚招。',
				'太常偏衣食筵会与财文；得旺、禄、合时更主亲友宴集。',
				[
					`${roleName}见太常临${branch}`,
					isWangXiangState(getSeasonStateForBranch(context.seasonMap, branch)) ? '太常临旺相' : '',
				],
			);
		}
		if(god === '元武' && isBranchSetIncludes(branch, ['亥', '子', '辰'])){
			push(
				'laiyi',
				'yuanwu',
				'元武决',
				'元武亥子辰，临卯酉盗伤。加午未迁官，推详莫妄陈。',
				'元武临亥子辰偏盗失暗伤；兼卯酉午未时需细辨迁官与是非。',
				[`${roleName}见元武临${branch}`],
			);
		}
		if(god === '太阴' && isBranchSetIncludes(branch, ['巳', '午'])){
			push(
				'laiyi',
				'taiyin',
				'太阴决',
				'太阴巳午焚，结聚起异心。欺瞒官长上，口舌到知音。',
				'太阴临巳午，主隐私聚结、异心欺瞒与口舌暗耗。',
				[`${roleName}见太阴临${branch}`],
			);
		}
		if(god === '天后'){
			push(
				'laiyi',
				'tianhou',
				'天后决',
				'天后因女子，土旺彩衣嫔。午未兼壬癸，万事无一真。',
				'天后主女子私情；若并午未壬癸，虚饰失真之象更显。',
				[
					`${roleName}见天后临${branch}`,
					isBranchSetIncludes(branch, ['午', '未']) ? '并午未位' : '',
					isBranchSetIncludes(context.dayGan, ['壬', '癸']) ? `日干为${context.dayGan}` : '',
				],
			);
		}
		if(god === '螣蛇' && (safeRestrain(branch, context.midBranch) || safeRestrain(context.midBranch, branch))){
			push(
				'zazhu',
				'tengshe_dazhan',
				'螣蛇大战',
				'螣蛇大战，毒气相凌。',
				'往来上下相克，惊疑与冲突烈度上升。',
				[
					`${roleName}见螣蛇临${branch}`,
					`与中传${context.midBranch || '—'}互克`,
				],
				'大战，往来上下相克也。',
			);
		}
		if(god === '螣蛇' && isBranchSetIncludes(branch, ['子', '午', '卯', '酉'])){
			push(
				'zazhu',
				'tengshe_danglu',
				'螣蛇当路',
				'螣蛇当路，鬼怪殃藏。',
				'螣蛇居四仲，怪异与暗殃信息上浮。',
				[`${roleName}见螣蛇临${branch}`],
				'当路，子午卯酉也。',
			);
		}
		if(god === '六合' && isBranchSetIncludes(branch, ['酉', '卯', '午'])){
			push(
				'zazhu',
				'liuhe_buhe',
				'六合不合',
				'六合不合，阴私相坏。',
				'六合落酉卯午，和合反折，私线易坏。',
				[`${roleName}见六合临${branch}`],
			);
		}
		if(god === '太常'){
			const taichangCond = (context.season === 'spring' && branch === '辰')
				|| (context.season === 'autumn' && branch === '卯')
				|| (context.season === 'summer' && branch === '酉')
				|| (context.season === 'winter' && branch === '巳');
			if(taichangCond){
				push(
					'zazhu',
					'taichang_bobo',
					'太常被剥',
					'太常被剥，官事消铄。',
					'太常遇季节剥位，官事华饰与体面受损。',
					[`${roleName}见太常临${branch}`],
					'春辰、秋卯、夏酉、冬巳。',
				);
			}
		}
		if(god === '朱雀' && monthIndex > 0 && ZHUQUE_KAIKOU_MONTH_BRANCH[monthIndex - 1] === branch){
			push(
				'zazhu',
				'zhuque_kaikou',
				'朱雀开口',
				'朱雀开口，发主喧斗。',
				'朱雀值月开口位，喧争口舌与争辩信息增强。',
				[`${roleName}见朱雀临${branch}；月建序=${monthIndex}`],
			);
		}
		if(god === '青龙' && isBranchSetIncludes(branch, ['寅', '酉', '戌'])){
			push(
				'zazhu',
				'qinglong_kaiyan',
				'青龙开眼',
				'青龙开眼，万事无灾。',
				'青龙得开眼位，行事顺畅度提升。',
				[`${roleName}见青龙临${branch}`],
				'孟寅，仲酉，季戌。',
			);
		}
		if(god === '青龙' && branch === '巳'){
			push(
				'zazhu',
				'qinglong_wobing',
				'青龙卧病',
				'青龙卧病，财散人灾。',
				'青龙陷巳，财气易散且伴人事耗损。',
				[`${roleName}见青龙临巳`],
			);
		}
		if(god === '天空' && isBranchSetIncludes(gan, ['壬', '癸']) && isBranchSetIncludes(context.dayGan, ['壬', '癸'])){
			push(
				'zazhu',
				'tiankong_luolei',
				'天空落泪',
				'天空落泪，哀声聒耳。',
				'天空与壬癸同会，哀戚与失落情绪放大。',
				[`${roleName}见天空临${branch}；所携天干=${gan}`],
				'六甲旬中居壬癸地，见壬癸。',
			);
		}
		if(god === '天乙' && isBranchSetIncludes(branch, ['辰', '戌'])){
			push(
				'zazhu',
				'tianyi_yugyu',
				'天乙归狱',
				'天乙归狱，诸事不治。',
				'贵人陷辰戌狱地，主事阻滞。',
				[`${roleName}见天乙临${branch}`],
			);
		}
		if(god === '勾陈' && monthIndex > 0 && GOUCHEN_BAJIAN_MONTH_BRANCH[monthIndex - 1] === branch){
			push(
				'zazhu',
				'gouchen_bajian',
				'勾陈拔剑',
				'勾陈拔剑，病患相伤。',
				'勾陈值月拔剑位，病患与冲突风险上扬。',
				[`${roleName}见勾陈临${branch}；月建序=${monthIndex}`],
				'正月起巳，逆行十二辰。',
			);
		}
		if(god === '勾陈' && isBranchSetIncludes(branch, ['辰', '戌', '丑', '未'])){
			push(
				'zazhu',
				'gouchen_xianghui',
				'勾陈相会',
				'勾陈相会，连绵祸深。',
				'勾陈临四季土，祸患拖延不散（辰戌重、丑未轻）。',
				[`${roleName}见勾陈临${branch}`],
				'辰戌大凶，丑未小凶。',
			);
		}
		if(god === '天后' && isBranchSetIncludes(branch, ['申', '酉'])){
			push(
				'zazhu',
				'tianhou_yinsi',
				'天后阴私',
				'天后阴私，申阳酉阴。',
				'天后居申酉，私隐议题更重。',
				[`${roleName}见天后临${branch}`],
			);
		}
		if(god === '朱雀' && monthIndex > 0 && ZHUQUE_XIANWU_MONTH_BRANCH[monthIndex - 1] === branch){
			push(
				'zazhu',
				'zhuque_xianwu',
				'朱雀衔物',
				'朱雀衔物，婚姻和合。',
				'朱雀值月衔物位，婚姻与和合议题突出。',
				[`${roleName}见朱雀临${branch}；月建序=${monthIndex}`],
			);
		}
		if(god === '太阴' && isBranchSetIncludes(branch, ['申', '酉'])){
			push(
				'zazhu',
				'taiyin_bajian',
				'太阴拔剑',
				'太阴拔剑，阴谋相害。',
				'太阴居申酉，暗谋与相害风险偏高。',
				[`${roleName}见太阴临${branch}`],
			);
		}
		if(god === '元武' && isBranchSetIncludes(monthBranch, FOUR_SEASON_BRANCHES)){
			push(
				'zazhu',
				'yuanwu_hengjie',
				'元武横截',
				'元武横截，盗贼兵发。',
				'四季土月见元武，盗兵、截阻与暗线风险增。',
				[`${roleName}见元武临${branch}；月建=${monthBranch}`],
				'四季。',
			);
		}
		if(god === '白虎' && isBranchSetIncludes(branch, ['巳', '午'])){
			push(
				'zazhu',
				'baihu_zaoqin',
				'白虎遭擒',
				'白虎遭擒，已免灾咎。',
				'白虎落巳午，凶力受制，灾咎可缓。',
				[`${roleName}见白虎临${branch}`],
			);
		}
		if(god === '白虎' && isBranchSetIncludes(monthBranch, FOUR_SEASON_BRANCHES)){
			push(
				'zazhu',
				'baihu_yangshi',
				'白虎仰视',
				'白虎仰视，凶恶之甚。',
				'四季土月遇白虎，凶烈度显著上扬。',
				[`${roleName}见白虎临${branch}；月建=${monthBranch}`],
				'四季。',
			);
		}
	});
	const mergedRefs = mergeOverviewRefsByName(refs);
	return mergedRefs.sort((a, b)=>{
		const ga = a.group === 'laiyi' ? 0 : 1;
		const gb = b.group === 'laiyi' ? 0 : 1;
		if(ga !== gb){
			return ga - gb;
		}
		return a.name.localeCompare(b.name, 'zh-Hans-CN');
	});
}
