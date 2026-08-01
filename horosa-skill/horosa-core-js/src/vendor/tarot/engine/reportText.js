// 塔罗 AI/导出快照文本(确定性增强):头(牌组·牌阵·设置·种子·指示牌) + 逐牌(各派名·正逆·占象·含义·尊位)
//   + 综合块 + 可选定局/生命牌摘要。供 UI 直断与 AI 快照共用,单一真值源。
import { getDeck, getDeckCards } from './deckRegistry.js';
import { displayName, astroLine, cardMeaning } from './cardSchema.js';
import { orientationLabel } from './spreads.js';
import { synthesizeText, yesNo, quintessence, birthCards, yearCard, majorByNumber, countingChain } from './verdict.js';

// 含义列（G5 双轨 + G2 逆位模式）:按 meaningSystem/reversalMode 走 cardMeaning 单一真值。
function meaningOf(card, isReversed, system, reversalMode){
	return cardMeaning(card, isReversed, system, reversalMode);
}

// reading 来自 engine/reading.buildReading。question 可单独传(优先于 reading.question)。
export function buildReadingText(reading, question){
	if(!reading || !Array.isArray(reading.draws) || !reading.draws.length){
		return '【塔罗】尚未抽牌,请先在塔罗页抽牌后再导出。';
	}
	const deck = getDeck(reading.deckId);
	const eff = reading.settings || {};
	const q = question !== undefined && question !== null ? question : reading.question;
	// 段头独占一行([段]),供 AI 导出/挂载「纳入内容」按段裁剪(与 aiExport tarot preset 逐一对齐);
	// 各段为条件产出(无内容即不出该段头,⊆ 语义天然豁免)。段头仅进 AI 快照文本,不影响右栏牌面渲染。
	const lines = [];
	lines.push('[牌阵综览]');
	lines.push(`【${reading.deckTitle || (deck && deck.title) || '塔罗'}】${reading.spreadTitle || ''}(种子:${reading.seed})`);
	const meta = [eff.reversals ? '逆位 ON' : '逆位 OFF'];
	if(eff.dignities){ meta.push('元素尊位 ON'); }
	if(eff.variant){ meta.push(`变体 ${eff.variant}`); }
	lines.push(`设置:${meta.join(' · ')}`);
	if(q){ lines.push(`所问:${q}`); }
	if(reading.significator && reading.significator.card){
		lines.push(`指示牌:${displayName(reading.significator.card, deck)}`);
	}
	lines.push('[逐牌详解]');
	lines.push('| 位置 | 牌 | 正逆 | 占象 | 关键词 | 尊位 |');
	lines.push('| --- | --- | --- | --- | --- | --- |');
	reading.draws.forEach((d) => {
		const card = d.card;
		if(!card){ return; }
		const dig = d.dignity ? `${d.dignity.strength}(${d.dignity.notes})` : '—';
		lines.push(`| 位置${d.position.i}(${d.position.label}) | ${displayName(card, deck)} | ${orientationLabel(d.isReversed)} | ${astroLine(card, deck, eff.variant)} | ${meaningOf(card, d.isReversed, eff.meaningSystem, eff.reversalMode)} | ${dig} |`);
	});
	if(reading.summary){ lines.push('[综合断语]'); lines.push(synthesizeText(reading.summary)); }
	// 定局摘要(Yes/No + 精华牌)
	try{
		const cards = getDeckCards(reading.deckId);
		const v = yesNo(reading.draws, eff.verdictMode || 'majority');
		const quint = quintessence(reading.draws, cards);
		lines.push('[定局]');
		lines.push(`Yes/No=${v.verdict}(${eff.verdictMode || 'majority'},score ${v.score})${quint ? ` · 精华牌 ${displayName(quint, deck)}` : ''}`);
		// [X1·P2-34] 计数链与右栏定局 tab 同源(此前显示有而 AI 不见)。
		const chain = countingChain(reading.draws, 0, Math.min(reading.draws.length, 8));
		if(chain && chain.length > 1){ lines.push(`计数链:${chain.map((c)=>displayName(c, deck)).join(' → ')}`); }
	}catch(e){ /* 定局可选,失败不阻断 */ }
	// 生命牌(若给生日)
	if(eff.birth && eff.birth.year && eff.birth.month && eff.birth.day){
		try{
			const cards = getDeckCards(reading.deckId);
			const bc = birthCards(Number(eff.birth.year), Number(eff.birth.month), Number(eff.birth.day));
			const pc = majorByNumber(cards, bc.personality <= 21 ? bc.personality : 0);
			const sc = majorByNumber(cards, bc.soul);
			lines.push('[生命牌]');
			lines.push(`人格 ${pc ? displayName(pc, deck) : bc.personality} · 灵魂 ${sc ? displayName(sc, deck) : bc.soul}`);
			if(eff.birth.refYear){
				const yn = yearCard(Number(eff.birth.month), Number(eff.birth.day), Number(eff.birth.refYear));
				const yc = majorByNumber(cards, yn <= 21 ? yn : 0);
				lines.push(`${eff.birth.refYear} 流年牌:${yc ? displayName(yc, deck) : yn}`);
			}
		}catch(e){ /* 生命牌可选 */ }
	}
	// [开钥] G7:opening_of_key 五操作摘要(与右栏「开钥」tab 同源 reading.ook)。
	if(reading.ook){
		lines.push('[开钥]');
		if(reading.ook.error){ lines.push(reading.ook.error); }
		else if(reading.ook.operations){
			reading.ook.operations.forEach((op) => {
				const chain = (op.chain || []).slice(0, 6).map((it) => displayName(it.card, deck)).join(' → ');
				lines.push(`操作${op.op} ${op.name}→落「${op.pileLabel}」(堆${op.pileSize}张)；计数链:${chain || '—'}`);
			});
			if(reading.ook.op5){ lines.push(`收束:${reading.ook.op5.summary}`); }
		}
	}
	if(reading.draws.length === 1){ lines.push('（单张牌阵:以上即为对所问之事的一句核心指引。）'); }
	// [组合读法] 雷诺曼一系专属段:与右栏「组合读法」renderLenormand 同源 reading.lenormand
	// (仅 lenormand 读法牌组由 buildReading 挂载该数据;塔罗/神谕牌组不产段)。内容为本盘组合对读,非全库。
	const len = reading.lenormand;
	if(len){
		const fmtNames = (arr) => (arr || []).filter(Boolean).join('·') || '—';
		const lenLines = [];
		if(len.kind === 'pair' && len.pair){
			lenLines.push(`◆ 成句(名词×修饰)：${len.pair}`);
		}else if(len.kind === 'box9' && len.box9){
			lenLines.push('◆ 9 宫盒');
			lenLines.push(`焦点：${len.box9.center ? len.box9.center.name_cn : '—'}`);
			lenLines.push(`环绕：${(len.box9.around || []).map((c) => c && c.name_cn).filter(Boolean).join('、') || '—'}`);
		}else if(len.kind === 'gt' && len.gt){
			const gt = len.gt;
			lenLines.push('◆ 指示牌定位');
			lenLines.push(`男（${gt.manName || '本人'}）：${gt.man ? `行${gt.man.row + 1} 列${gt.man.col + 1}` : '未在阵中'}　女（${gt.womanName || '本人'}）：${gt.woman ? `行${gt.woman.row + 1} 列${gt.woman.col + 1}` : '未在阵中'}`);
			if(gt.manLines){
				lenLines.push('◆ 男·贯穿线');
				lenLines.push(`过去：${fmtNames(gt.manLines.past)}`);
				lenLines.push(`未来：${fmtNames(gt.manLines.future)}`);
				lenLines.push(`显意(上)：${fmtNames(gt.manLines.above)}　潜意(下)：${fmtNames(gt.manLines.below)}`);
			}
			lenLines.push('◆ 跳马 / 四角');
			lenLines.push(`男·跳马：${fmtNames(gt.manKnight)}`);
			lenLines.push(`四角(结论)：${fmtNames(gt.corners)}`);
			const houseReads = (gt.houses || []).slice(0, 12).filter((h) => h && h.read);
			if(houseReads.length){
				lenLines.push('◆ 宫位叠读(前12)');
				houseReads.forEach((h) => lenLines.push(`${h.pos}. ${h.read}`));
			}
		}
		if(lenLines.length){
			lines.push('[组合读法]');
			lenLines.forEach((l) => lines.push(l));
		}
	}
	return lines.join('\n');
}

export default buildReadingText;
