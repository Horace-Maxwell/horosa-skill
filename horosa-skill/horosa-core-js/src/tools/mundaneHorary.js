import {
  MUNDANE_HORARY_KINDS,
  describeWarQuestion,
  describeWeatherQuestion,
  describePriceQuestion,
} from '../vendor/mundane/mundaneHorary.js';
import { buildFacts } from '../vendor/divination/engine/chartFacts.js';

/**
 * 世运卜卦两段：[世运卜卦]（盘型头 + 问题类型）与 [世运问判]（按问类出断语）。
 *
 * 上游 MundaneMain.js 对 `mundaneType==='mundanehorary'` 走的就是「问事时刻的普通 /chart →
 * buildFacts → describeXQuestion」——机制同卜卦，只是问主 = 公众/国家、宫义按世运读。
 * 三个 describe 都是纯 `(facts)` 函数，零外部依赖，故整支可 headless。
 *
 * 已知口径瑕疵（上游同款，非本仓引入）：`describeWeatherQuestion` 读 `m.su28`（28 宿），
 * 而 `buildFacts` 不填该字段 → `moonMansion` 恒为 null，段内显示「-」。不影响成段。
 *
 * payload: { chart: <问事时刻 /chart 响应>, mhKind?: 'war'|'weather'|'price', ruleset?: string }
 * return : { text }
 */
export function runMundaneHorary(payload) {
  const source = payload && typeof payload === 'object' ? payload : {};
  const chart = source.chart && typeof source.chart === 'object' ? source.chart : null;
  if (!chart) {
    return { text: '' };
  }
  const kind = MUNDANE_HORARY_KINDS.some((k) => k.key === source.mhKind) ? source.mhKind : 'war';
  const kindCn = (MUNDANE_HORARY_KINDS.find((k) => k.key === kind) || {}).cn || '战争';
  const blocks = [];
  blocks.push(['[世运卜卦]', `问题类型：${kindCn}`, '机制同卜卦,问主=公众/国家,宫义按世运读'].join('\n'));
  try {
    const facts = buildFacts(chart);
    const lines = ['[世运问判]'];
    if (kind === 'war') {
      const w = describeWarQuestion(facts);
      if (w) {
        lines.push(
          `己方 ${w.us.cn}(${w.us.total}) vs 敌方 ${w.them.cn}(${w.them.total})${w.reception ? ' · 互容' : ''}`,
          w.verdict.text,
        );
      }
    } else if (kind === 'weather') {
      const wq = describeWeatherQuestion(facts);
      if (wq) {
        lines.push(`月宿 ${wq.moonMansion || '-'} · ${wq.tone}`);
      }
    } else {
      const pq = describePriceQuestion(facts);
      if (pq) {
        lines.push(pq.trend.text, pq.cropNote);
      }
    }
    if (lines.length > 1) {
      blocks.push(lines.join('\n'));
    }
  } catch (error) {
    /* 判词失败只丢 [世运问判]，盘型头照常 —— 与上游 try/catch 同口径 */
  }
  return { text: blocks.join('\n\n') };
}

export default runMundaneHorary;
