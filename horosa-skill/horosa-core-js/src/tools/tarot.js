// 塔罗：无后端引擎，纯前端牌系数据 + 确定性洗牌(SHA-256 种子→mulberry32→Fisher–Yates)。
// 喂 {spread, deck, seed/timeSeed, question, usesReversals}，buildReading→buildReadingText(扁平 reading 文本)，
// 按 「—」分隔块拆成 [起卦信息]/[牌阵直断]/[牌阵细论]/[综合建议] 段。任一步失败回空。
import { buildReading } from '../vendor/tarot/engine/reading.js';
import { buildReadingText } from '../vendor/tarot/engine/reportText.js';
import { DEFAULT_DECK, hasDeck } from '../vendor/tarot/engine/deckRegistry.js';
import { SPREADS, DEFAULT_SPREAD } from '../vendor/tarot/engine/spreads.js';

export function runTarot(payload) {
  try {
    const deck = (payload && payload.deck && hasDeck(payload.deck)) ? payload.deck : DEFAULT_DECK;
    const spread = (payload && payload.spread && SPREADS && SPREADS[payload.spread]) ? payload.spread : DEFAULT_SPREAD;
    const seed = `${payload && (payload.seed != null ? payload.seed : payload.timeSeed) != null ? (payload.seed != null ? payload.seed : payload.timeSeed) : ''}`;
    if (!seed) {
      return { snapshot_text: '' };
    }
    const question = (payload && payload.question) || '';
    const settings = { question };
    if (payload && payload.usesReversals === false) {
      settings.usesReversals = false;
    }
    const reading = buildReading(deck, spread, seed, settings);
    if (!reading) {
      return { snapshot_text: '' };
    }
    const raw = buildReadingText(reading, question);
    if (!raw || !raw.trim()) {
      return { snapshot_text: '' };
    }
    // 按「—」分隔线拆块：块0=头(起卦信息)、块1=逐位(牌阵细论)、块2=综合+定局。
    const blocks = [];
    let cur = [];
    raw.split('\n').forEach((ln) => {
      if (/^[—–-]+$/.test(ln.trim())) {
        blocks.push(cur.join('\n').trim());
        cur = [];
      } else {
        cur.push(ln);
      }
    });
    blocks.push(cur.join('\n').trim());
    const header = blocks[0] || '';
    const positions = blocks[1] || '';
    const footer = blocks.slice(2).join('\n');
    const footerLines = footer.split('\n').map((l) => l.trim()).filter(Boolean);
    const zonghe = footerLines.filter((l) => l.startsWith('综合')).join('\n');
    const dingju = footerLines.filter((l) => l.startsWith('定局')).join('\n');
    const out = [];
    out.push('[起卦信息]');
    out.push(header || '—');
    if (dingju) {
      out.push('');
      out.push('[牌阵直断]');
      out.push(dingju);
    }
    if (positions) {
      out.push('');
      out.push('[牌阵细论]');
      out.push(positions);
    }
    if (zonghe) {
      out.push('');
      out.push('[综合建议]');
      out.push(zonghe);
    }
    return { snapshot_text: out.join('\n'), deck, spread };
  } catch (e) {
    return { snapshot_text: '' };
  }
}
