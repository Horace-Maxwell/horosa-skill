// 塔罗：无后端引擎，纯前端牌系数据 + 确定性洗牌(SHA-256 种子→mulberry32→Fisher–Yates)。
// 喂 {spread, deck, seed/timeSeed, question, usesReversals, dignities, variant, verdictMode, birth, options}，
// buildReading → buildReadingText 直接产出独占段头 [牌阵综览]/[逐牌详解]/[综合断语]/[定局]/[生命牌]
// （单一真值源，段头逐一对齐 aiExport tarot preset；条件段无内容即不出，⊆ 语义天然豁免）。
//
// 🔴 sync311 F9/F11：设置与牌组/牌阵一律**锚到引擎自带词表**，不手抄会漂移的清单（AGENTS §5.12）：
//   * 设置键集 = resolveSettings(deck, {}) 的键（24 个；此前只透传 5 个，timingMethod/timingUnit 等 19 个不可达）；
//   * 取值合法性 = 让 resolveSettings 自己裁：值被它回落成别的 → 结构化报错（带引擎词表），绝不静默换默认；
//   * verdictMode = YESNO_MODES 八法（此前截成五法）；usesReversals 显式 true 也下发（此前只发 false）；
//   * deck / spread 不认识、或牌阵不在该牌组 caps.spreads 允许表内 → 结构化报错（此前静默换 rws / three）。
import { buildReading, resolveSettings } from '../vendor/tarot/engine/reading.js';
import { buildReadingText } from '../vendor/tarot/engine/reportText.js';
import { DEFAULT_DECK, getDeck, hasDeck, listDeckIds } from '../vendor/tarot/engine/deckRegistry.js';
import { SPREADS, DEFAULT_SPREAD } from '../vendor/tarot/engine/spreads.js';
import { YESNO_MODES } from '../vendor/tarot/engine/verdict.js';
import { REVERSAL_MODES } from '../vendor/tarot/engine/reversalModes.js';
import { TIMING_METHODS } from '../vendor/tarot/engine/timingMethods.js';

// 引擎自带词表（有导出者用导出；resolveSettings 里的内联二元枚举由它自己裁决）。
const ENGINE_VOCAB = {
  verdictMode: YESNO_MODES,
  reversalMode: REVERSAL_MODES,
  timingMethod: TIMING_METHODS,
};

function fail(code, message, details) {
  return { snapshot_text: '', data: { ok: false, error: { code, message, details: details || {} } } };
}

function toBool(value) {
  if (value === true || value === 1 || value === '1' || value === 'true') { return true; }
  if (value === false || value === 0 || value === '0' || value === 'false') { return false; }
  return null;
}

export function runTarot(payload) {
  try {
    const p = payload && typeof payload === 'object' ? payload : {};
    if (p.deck && !hasDeck(p.deck)) {
      return fail('unknown_deck', `未知牌组 ${p.deck}`, { deck: p.deck, allowed: listDeckIds() });
    }
    const deck = p.deck || DEFAULT_DECK;
    const deckObj = getDeck(deck);
    const allowedSpreads = (deckObj && deckObj.caps && Array.isArray(deckObj.caps.spreads)) ? deckObj.caps.spreads : Object.keys(SPREADS);
    let spread = p.spread;
    if (spread) {
      if (!SPREADS[spread]) {
        return fail('unknown_spread', `未知牌阵 ${spread}`, { spread, deck, allowed: allowedSpreads });
      }
      if (allowedSpreads.indexOf(spread) < 0) {
        return fail('unsupported_spread_for_deck', `牌组 ${deck} 不开放牌阵 ${spread}`, { spread, deck, allowed: allowedSpreads });
      }
    } else {
      // 未指定：缺省牌阵；该牌组不开放缺省牌阵时回落其允许表首项（上游 savedTarotState 同一条回落）。
      spread = allowedSpreads.indexOf(DEFAULT_SPREAD) >= 0 ? DEFAULT_SPREAD : (allowedSpreads[0] || DEFAULT_SPREAD);
    }
    const rawSeed = p.seed != null ? p.seed : p.timeSeed;
    const seed = `${rawSeed != null ? rawSeed : ''}`;
    if (!seed) {
      return fail('missing_seed', '塔罗需要种子（seed）');
    }
    const question = p.question || '';

    // 设置：顶层旧字段（usesReversals/dignities/variant/verdictMode/birth）+ options（引擎键）；options 优先。
    const engineKeys = Object.keys(resolveSettings(deckObj, {}));
    const raw = {};
    if (p.usesReversals !== undefined && p.usesReversals !== null) { raw.reversals = p.usesReversals; }
    ['dignities', 'variant', 'verdictMode', 'birth'].forEach((k) => {
      if (p[k] !== undefined && p[k] !== null && p[k] !== '') { raw[k] = p[k]; }
    });
    const ignored = [];
    const opts = p.options && typeof p.options === 'object' && !Array.isArray(p.options) ? p.options : {};
    Object.keys(opts).forEach((k) => {
      const key = k === 'usesReversals' ? 'reversals' : k;
      if (engineKeys.indexOf(key) < 0) { ignored.push(k); return; }
      if (opts[k] !== undefined && opts[k] !== null && opts[k] !== '') { raw[key] = opts[k]; }
    });
    const defaults = resolveSettings(deckObj, {});
    const settings = { question };
    for (const key of Object.keys(raw)) {
      let value = raw[key];
      if (key === 'birth') {
        // 生命牌：仅在给定出生年月日时产出该段（{year,month,day,refYear?}）。
        if (!value || typeof value !== 'object' || !value.year || !value.month || !value.day) {
          return fail('invalid_setting', 'birth 需 {year,month,day[,refYear]}', { key, value });
        }
        value = { year: Number(value.year), month: Number(value.month), day: Number(value.day), ...(value.refYear ? { refYear: Number(value.refYear) } : {}) };
      } else if (typeof defaults[key] === 'boolean') {
        const flag = toBool(value);
        if (flag === null) { return fail('invalid_setting', `${key} 需布尔值`, { key, value }); }
        value = flag;
      } else if (defaults[key] !== null && typeof defaults[key] === 'object') {
        if (!value || typeof value !== 'object' || Array.isArray(value)) {
          return fail('invalid_setting', `${key} 需对象`, { key, value });
        }
      } else {
        const effective = resolveSettings(deckObj, { [key]: value })[key];
        if (effective !== value) {
          return fail('invalid_setting', `${key}=${value} 不被引擎接受（引擎会回落为 ${effective}）`, {
            key, value, engine_fallback: effective, ...(ENGINE_VOCAB[key] ? { allowed: ENGINE_VOCAB[key] } : {}),
          });
        }
      }
      settings[key] = value;
    }
    const reading = buildReading(deck, spread, seed, settings);
    if (!reading) {
      return fail('reading_failed', 'buildReading 未返回牌阵');
    }
    // 新版 buildReadingText 已产出独占 [段头]，直通即可（不再做「—」分隔块重解析、不再丢弃生命牌）。
    const snapshotText = buildReadingText(reading, question);
    if (!snapshotText || !snapshotText.trim() || snapshotText.startsWith('【塔罗】尚未')) {
      return fail('reading_failed', 'buildReadingText 未产出快照');
    }
    const applied = Object.keys(settings).filter((k) => k !== 'question').sort();
    return {
      snapshot_text: snapshotText,
      deck,
      spread,
      data: { ok: true, deck, spread, params_applied: applied, params_ignored: ignored.sort() },
    };
  } catch (e) {
    return fail('reading_failed', `${(e && e.message) || e}`);
  }
}
