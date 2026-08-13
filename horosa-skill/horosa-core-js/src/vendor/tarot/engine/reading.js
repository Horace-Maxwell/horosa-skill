// 抽牌编排器:buildReading(deckId, spreadType, seed, settings)。单一真值源,中栏+右栏皆从返回 reading 渲染。
// deck/变体/尊位/逆位 不重洗(同 order,仅换呈现/掩朝向);指示牌/牌阵/种子 重抽(改池)。
import { getDeck, getDeckCards, DEFAULT_DECK } from './deckRegistry.js';
import { makeBlankCard } from '../decks/core78.js';
import { SPREADS, DEFAULT_SPREAD, drawSpread } from './spreads.js';
import { shuffle } from './shuffle.js';
import { resolveSignificatorSid } from './significator.js';
import { dignify } from './dignities.js';
import { synthesize, YESNO_MODES } from './verdict.js';
import { cardElement, isTrumpArcana } from './cardSchema.js';
import { grandTableau, box9, pairString } from './lenormandReading.js';
import { openingOfKey } from './openingOfKey.js';
import { buildPairReading } from './pairReading.js';
import { REVERSAL_MODES } from './reversalModes.js';

// 解析有效设置:用户值优先,缺省回落 deck 默认。
// [QA-7] 枚举键一律走白名单判定:非法值(拼错的档名、数字、对象)回落默认档。
// 三处曾用 `s.x || 默认` 短路 —— 任何非空值都会原样穿透,传入对象即被 `${}` 串成
// 「变体 [object Object]」写进设置行与快照。白名单化后,非法值不再污染显示与导出。
const inEnum = (v, list, dft) => (list.indexOf(v) >= 0 ? v : dft);
export function resolveSettings(deck, settings){
	const s = settings || {};
	return {
		reversals: s.reversals === undefined ? !!deck.usesReversals : !!s.reversals,
		dignities: s.dignities === undefined ? !!deck.dignities : !!s.dignities,
		variant: inEnum(s.variant, ['A', 'B', 'C'], inEnum(deck.variant, ['A', 'B', 'C'], 'A')),
		showCorrespondences: s.showCorrespondences === undefined ? (deck.variant === 'B' || deck.dignities) : !!s.showCorrespondences,
		sig: (s.sig && typeof s.sig === 'object' && !Array.isArray(s.sig)) ? s.sig : { mode: 'none' },
		verdictMode: inEnum(s.verdictMode, YESNO_MODES, 'majority'),
		birth: (s.birth && typeof s.birth === 'object' && !Array.isArray(s.birth)) ? s.birth : null,
		// TP2 三轨牌义:manual/waite/degrees;缺省吸附 deck.meaningDefault(马赛系默认数字度),再回落 manual。
		meaningSystem: (s.meaningSystem === 'waite' || s.meaningSystem === 'degrees' || s.meaningSystem === 'manual')
			? s.meaningSystem : (deck.meaningDefault || 'manual'),
		reversalMode: inEnum(s.reversalMode, REVERSAL_MODES, 'stored'), // G2→TP1 逆位十三式,默认预存
		suitElementSwap: !!s.suitElementSwap, // G4 火/风互换,默认 off
		ookTable: s.ookTable === 'sephira' ? 'sephira' : 'standard', // 开钥计数表:通行(默认)/质点(此前恒 undefined,质点版 UI 不可达——已通)
		reversalGen: s.reversalGen === 'fingers3' || s.reversalGen === 'all' ? s.reversalGen : 'shuffle', // TP1 逆位产生:洗牌(默认)/三指定牌/全逆
		crossingUpright: s.crossingUpright === undefined ? true : !!s.crossingUpright, // TP1 凯尔特交叉牌恒正读(横置第三态,古法默认开)
		quintMode: s.quintMode === 'fool22' ? 'fool22' : 'standard', // TP2 精华牌口径:通行(0/22归愚人0)/马赛(愚人计22,数值加法用)
		showBottomCard: !!s.showBottomCard, // TP2 牌底牌(基调):默认关
		edVersion: s.edVersion === 'mathers' ? 'mathers' : 'modern', // TP3 尊位版本:现行三档(默认)/原典四档(火土·风水=稍微支持)
		astroModern: !!s.astroModern, // TP3 三元素大牌附现代行星注(天/海/冥):默认关
		timingMethod: ['major_number', 'major_zodiac', 'decan_full', 'ace_hunt'].includes(s.timingMethod) ? s.timingMethod : 'suit_unit', // TP4 计时五法
		timingUnit: s.timingUnit === '天' || s.timingUnit === '月' ? s.timingUnit : '周', // TP4 大牌数字法单位
		majorsOverlay: !!s.majorsOverlay, // TP4 大牌加盖(≥4 大牌或过半→每大牌自余牌盖一张小牌):默认关
		showCutCard: !!s.showCutCard, // TP4 切牌(问卜者心态):默认关
		includeBlank: !!s.includeBlank, // TP4 空白牌入池(78+1):默认关
		courtElementSystem: s.courtElementSystem === 'alt' ? 'alt' : 'gd', // TP7 宫廷元素:现行元素中元素(默认)/位阶制(王土后水骑火侍风)
		courtZodiacSystem: s.courtZodiacSystem === 'simple' ? 'simple' : 'gd_span', // TP7 宫廷星座:现行跨段(默认)/单座制
	};
}

// 主函数。settings 可选;缺省 → deck 默认(rws 两参旧调用零回归)。
export function buildReading(deckId, spreadType, seed, settings){
	const deck = getDeck(deckId || DEFAULT_DECK);
	const type = SPREADS[spreadType] ? spreadType : DEFAULT_SPREAD;
	const eff = resolveSettings(deck, settings);
	// TP4 空白牌:支持牌组且开关开→池尾加第 79 张(id=deck.size);洗牌 size 随池。
	// TP5 大牌子集阵(因果七杯):池=纯大牌廿二张(其 id 恰为 0..21 连续,shuffle 排列即大牌 id 排列);子集阵不加空白牌。
	let cards = getDeckCards(deck.id);
	const subsetMajors = SPREADS[type] && SPREADS[type].subset === 'majors';
	if(subsetMajors){
		// [QA-9] 认 *_trump(各牌组王牌 id 皆自 0 起连续,shuffle 的 id 排列前提仍成立);
		// 现行 caps 未对这两副开放子集阵,此改为判据一致,免日后放开时池空。
		cards = cards.filter((c) => isTrumpArcana(c.arcana));
	}else if(eff.includeBlank && deck.caps && deck.caps.blank){
		cards = cards.concat([makeBlankCard(deck.size)]);
	}
	const poolSize = cards.length;
	const byId = {};
	cards.forEach((c) => { byId[c.id] = c; });
	const resolve = (id) => byId[id] || null;

	// 指示牌:从池中剔除其 id(保持 size 排列确定性)
	let sigCard = null;
	let sigId = null;
	if(deck.caps && deck.caps.significator){
		const sid = resolveSignificatorSid(eff.sig);
		if(sid){
			sigCard = cards.find((c) => c.sid === sid) || null;
			if(sigCard){ sigId = sigCard.id; }
		}
	}

	const sh = shuffle(seed, { size: poolSize, usesReversals: eff.reversals, pReversed: deck.pReversed });
	let order = sh.order;
	let reversed = sh.reversed;
	// TP1 逆位产生方式(仅逆位开启时生效;order 恒不变=同一副牌只换朝向):
	//   fingers3=「三指定牌」古法:全副转正,由独立种子流确定性选 3 张翻转(出现在阵中则权重大增);all=全逆位阵。
	if(eff.reversals && eff.reversalGen === 'fingers3'){
		const chosen = new Set(shuffle(`${seed}|fof`, { size: poolSize, usesReversals: false }).order.slice(0, 3));
		reversed = order.map((cid) => chosen.has(cid));
	}else if(eff.reversals && eff.reversalGen === 'all'){
		reversed = order.map(() => true);
	}
	// 剔除指示牌 index:order 去掉 sigId,reversed 同步去掉(保持对齐)
	if(sigId !== null && sigId !== undefined){
		const keep = order.map((v, i) => ({ v, r: reversed[i] })).filter((x) => x.v !== sigId);
		order = keep.map((x) => x.v);
		reversed = keep.map((x) => x.r);
	}
	const spread = SPREADS[type];
	// TP1 单张逆位占卜:沿已洗牌序逐张翻至「第一张逆位牌」,以其为唯一解读对象;翻牌数=能量诊断。
	let firstReversal = null;
	let draws;
	let consumed = 0; // TP4:本次抽牌消费的 order 张数(余牌序=order.slice(consumed),计时法/加盖用)
	if(spread.firstReversal){
		if(!eff.reversals){
			draws = [];
			firstReversal = { error: '此占法以「第一张逆位牌」为讯息载体,须先在左栏开启逆位。' };
		}else{
			let hit = -1;
			for(let i = 0; i < order.length; i++){ if(reversed[i]){ hit = i; break; } }
			if(hit < 0){
				draws = [];
				firstReversal = { error: '整副皆正位——此次没有逆位讯息,可视为能量通畅,或换个问题再占。' };
			}else{
				draws = [{ position: spread.positions[0], cardId: order[hit], isReversed: true, card: resolve(order[hit]) }];
				consumed = hit + 1;
				const count = hit + 1;
				const level = count <= 2 ? '强而活跃' : count <= 5 ? '中等在场' : count <= 10 ? '深藏无意识' : '意义有限';
				const note = count <= 2 ? '前两张即现逆位:此议题能量很强、当前非常活跃。'
					: count <= 5 ? '数张内现逆位:议题在场,可正常展开解读。'
					: count <= 10 ? '翻过五张方见逆位:内容深藏于无意识,或机会窗尚远。'
					: '翻过十张才见逆位:此问当下意义不大——改日再问,或换个问法。';
				firstReversal = { count, level, note, questions: spread.questions || [] };
			}
		}
	}else{
		draws = drawSpread(type, { order, reversed }, resolve);
		consumed = draws.length;
	}
	// TP1 交叉牌第三态(古法:凯尔特「横压之牌」恒正读,标「横置」):默认开;关=沿旧行为按洗牌朝向读。
	if(eff.crossingUpright){
		draws.forEach((d) => {
			if(d.position && d.position.crossFixed){
				d.crossed = true;
				if(d.isReversed){ d.isReversed = false; }
			}
		});
	}

	// 元素尊位(线性邻接;TP3 版本可切 modern/mathers)
	if(eff.dignities){
		const elems = draws.map((d) => (d.card ? cardElement(d.card, eff.suitElementSwap) : null));
		draws.forEach((d, i) => {
			const le = i > 0 ? elems[i - 1] : null;
			const re = i < draws.length - 1 ? elems[i + 1] : null;
			d.dignity = dignify(elems[i], le, re, eff.edVersion);
		});
	}

	// G7 开钥:opening_of_key + 支持 ook 的牌组(gd/thoth)+ 已选指示牌 → 五操作挂 reading.ook。
	let ook = null;
	if(type === 'opening_of_key' && deck.caps && deck.caps.ook){
		ook = openingOfKey(cards, sigId, seed, { table: eff.ookTable });
	}
	// Lenormand 读法:Grand Tableau / 9 宫盒 / 成句 分析挂到 reading.lenormand
	let lenormand = null;
	if(deck.caps && deck.caps.readingMethod === 'lenormand'){
		if(type === 'grand_tableau'){ lenormand = { kind: 'gt', gt: grandTableau(draws, 8) }; }
		else if(type === 'lenormand_box9'){ lenormand = { kind: 'box9', box9: box9(draws) }; }
		else{ lenormand = { kind: 'pair', pair: pairString(draws) }; }
	}
	// TP2 对读(马赛两两解读):塔罗读法牌组挂 reading.pairs(十进对/和21补牌/配偶/相邻度关系/视线)。
	let pairs = null;
	if(deck.caps && deck.caps.readingMethod === 'tarot'){
		pairs = buildPairReading(draws);
	}
	// TP2 牌底牌(基调):开关开启时暴露剔除指示牌后的牌堆底张(含朝向)。
	let bottomCard = null;
	if(eff.showBottomCard && order.length){
		const last = order.length - 1;
		bottomCard = { card: resolve(order[last]), isReversed: !!reversed[last] };
	}
	// TP4 余牌序(确定性;计时法「另取大牌/翻至王牌」与「大牌加盖」的单一来源)。
	const restIds = order.slice(consumed);
	const restReversed = reversed.slice(consumed);
	// TP4 大牌加盖:大牌 ≥4 或过半 → 每张大牌自余牌序依次盖一张小牌(含其朝向)。
	if(eff.majorsOverlay && deck.caps && deck.caps.readingMethod === 'tarot' && !spread.firstReversal && draws.length >= 4){
		const majorsIn = draws.filter((d) => d.card && isTrumpArcana(d.card.arcana));
		if(majorsIn.length >= 4 || majorsIn.length > draws.length / 2){
			let ptr = 0;
			majorsIn.forEach((d) => {
				while(ptr < restIds.length){
					const c = resolve(restIds[ptr]);
					const rv = restReversed[ptr];
					ptr += 1;
					if(c && c.arcana === 'minor'){ d.overlay = { cardId: c.id, card: c, isReversed: !!rv }; break; }
				}
			});
		}
	}
	// TP4 切牌(问卜者对此问的心态):独立种子流定切位,取当前池该位牌(含朝向);不动抽牌。
	let cutCard = null;
	if(eff.showCutCard && order.length){
		const cutIdx = shuffle(`${seed}|cut`, { size: poolSize, usesReversals: false }).order[0] % order.length;
		cutCard = { card: resolve(order[cutIdx]), isReversed: !!reversed[cutIdx] };
	}
	return {
		deckId: deck.id, deckTitle: deck.title, deckCaps: deck.caps,
		spreadType: type, spreadTitle: spread.label, seed,
		question: (settings && settings.question) || '',
		settings: eff,
		significator: sigCard ? { sid: sigCard.sid, cardId: sigCard.id, card: sigCard } : null,
		draws,
		summary: synthesize(draws, eff.suitElementSwap),
		lenormand,
		ook,
		firstReversal,
		pairs,
		bottomCard,
		restIds,
		cutCard,
	};
}

export default buildReading;
