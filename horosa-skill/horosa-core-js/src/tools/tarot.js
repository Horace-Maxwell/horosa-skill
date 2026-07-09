// 塔罗：无后端引擎，纯前端牌系数据 + 确定性洗牌(SHA-256 种子→mulberry32→Fisher–Yates)。
// 喂 {spread, deck, seed/timeSeed, question, usesReversals, dignities, variant, verdictMode, birth}，
// buildReading → buildReadingText 直接产出独占段头 [牌阵综览]/[逐牌详解]/[综合断语]/[定局]/[生命牌]
// （单一真值源，段头逐一对齐 aiExport tarot preset；条件段无内容即不出，⊆ 语义天然豁免）。任一步失败回空。
import { buildReading } from '../vendor/tarot/engine/reading.js';
import { buildReadingText } from '../vendor/tarot/engine/reportText.js';
import { DEFAULT_DECK, hasDeck } from '../vendor/tarot/engine/deckRegistry.js';
import { SPREADS, DEFAULT_SPREAD } from '../vendor/tarot/engine/spreads.js';

export function runTarot(payload) {
  try {
    const p = payload && typeof payload === 'object' ? payload : {};
    const deck = (p.deck && hasDeck(p.deck)) ? p.deck : DEFAULT_DECK;
    const spread = (p.spread && SPREADS && SPREADS[p.spread]) ? p.spread : DEFAULT_SPREAD;
    const rawSeed = p.seed != null ? p.seed : p.timeSeed;
    const seed = `${rawSeed != null ? rawSeed : ''}`;
    if (!seed) {
      return { snapshot_text: '' };
    }
    const question = p.question || '';
    // settings 透传到 resolveSettings：usesReversals→reversals（旧 shim 误写 usesReversals 键，被 resolveSettings 忽略）。
    const settings = { question };
    if (p.usesReversals !== undefined) { settings.reversals = !!p.usesReversals; }
    if (p.dignities !== undefined) { settings.dignities = !!p.dignities; }
    if (p.variant) { settings.variant = p.variant; }
    // verdictMode 归一到已知集合（非法值回退 majority），避免 [定局] 段打印原始非法串。
    const VERDICT_MODES = ['majority', 'orientation', 'single', 'numeric', 'polarity'];
    if (p.verdictMode) { settings.verdictMode = VERDICT_MODES.includes(p.verdictMode) ? p.verdictMode : 'majority'; }
    // 生命牌：仅在给定出生年月日时产出该段（TarotInput.birth = {year,month,day,refYear?}）。
    if (p.birth && p.birth.year && p.birth.month && p.birth.day) {
      settings.birth = {
        year: Number(p.birth.year),
        month: Number(p.birth.month),
        day: Number(p.birth.day),
      };
      if (p.birth.refYear) { settings.birth.refYear = Number(p.birth.refYear); }
    }
    const reading = buildReading(deck, spread, seed, settings);
    if (!reading) {
      return { snapshot_text: '' };
    }
    // 新版 buildReadingText 已产出独占 [段头]，直通即可（不再做「—」分隔块重解析、不再丢弃生命牌）。
    const snapshotText = buildReadingText(reading, question);
    if (!snapshotText || !snapshotText.trim() || snapshotText.startsWith('【塔罗】尚未')) {
      return { snapshot_text: '' };
    }
    return { snapshot_text: snapshotText, deck, spread };
  } catch (e) {
    return { snapshot_text: '' };
  }
}
