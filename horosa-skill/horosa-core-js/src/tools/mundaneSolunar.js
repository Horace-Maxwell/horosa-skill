import {
  describeSolunar,
  computeAngularity,
  rulerDeathSignature,
} from '../vendor/mundane/solunar.js';
import { PLANET_CN as MUN_PLANET_CN } from '../vendor/mundane/describe.js';
import { buildFacts } from '../vendor/divination/engine/chartFacts.js';

/**
 * 恒星派入境两段：[恒星派入境]（盘型头）与 [角化]（星入角判读）。
 *
 * 上游 MundaneMain.js:2510/2562 —— 前者是 describeSolunar(type, weights) 的静态口径行，
 * 后者是 computeAngularity(facts, orb) + rulerDeathSignature(facts, orb) 的纯函数判读。
 * 入境时刻的求根（solveSiderealIngress）走 HTTP，按 §5 归 Python；这里只吃已经算好的盘。
 *
 * payload: {
 *   chart: <入境时刻 /chart 响应（恒星黄道 fagan_bradley · Campanus）>,
 *   solunarType?: 'capsolar'|'arisolar'|'cansolar'|'libsolar'|'caplunar'|'arilunar'|'canlunar'|'liblunar',
 *   solunarWeights?: 'scheme_a'|…, solunarOrb?: number, moment?: string
 * }
 * return : { text }
 */
export function runMundaneSolunar(payload) {
  const source = payload && typeof payload === 'object' ? payload : {};
  const chart = source.chart && typeof source.chart === 'object' ? source.chart : null;
  if (!chart) {
    return { text: '' };
  }
  const typeKey = source.solunarType || 'capsolar';
  const orb = Number(source.solunarOrb) || 3;
  const blocks = [];

  const st = describeSolunar(typeKey, source.solunarWeights || 'scheme_a');
  const head = ['[恒星派入境]'];
  if (st) {
    head.push(`盘型：${st.cn}`, `影响期：${st.span}`, `权重：${st.weight}（${st.weightsCn}）`);
  }
  if (source.moment) {
    head.push(`入境时刻：${source.moment}`);
  }
  head.push('坐标：恒星黄道 Fagan/Bradley · Campanus 宫制');
  blocks.push(head.join('\n'));

  try {
    const facts = buildFacts(chart);
    const ang = computeAngularity(facts, orb);
    if (ang) {
      const fg = ang.rows.filter((r) => r.foreground);
      const lines = [
        '[角化]',
        `容许 ${ang.orb}°(卯酉圈等分量角);${fg.length ? '' : '休眠盘——无星入角,无信息可略过'}`,
      ];
      fg.forEach((r) => {
        lines.push(
          `${MUN_PLANET_CN[r.planet] || r.planet} 距${r.axisCn} ${r.dist.toFixed(1)}°`
          + `${r.strong ? '(尤强)' : ''}${r.omen ? ' → ' + r.omen.text : ''}`,
        );
      });
      if (rulerDeathSignature(facts, orb)) {
        lines.push('⚠ 复合判据命中:土星与太阳皆在角且彼此无相位');
      }
      blocks.push(lines.join('\n'));
    }
  } catch (error) {
    /* 角化失败只丢该段，盘型头照常 —— 与上游 try/catch 同口径 */
  }
  return { text: blocks.join('\n\n') };
}

export default runMundaneSolunar;
