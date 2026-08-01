import { varaLordOf, PLANET_CN_V, NAVANAYAKA_NOTES } from '../vendor/mundane/vedicMundane.js';

/**
 * [年之九主]：九职各按其事件时刻的 vāra（星期主）定职星。
 *
 * 九次入境求根与「王」职的朔搜索都走 HTTP，按 §5 归 Python；这里只吃已解出的时刻，
 * 用 vendored 的 `varaLordOf` 定星、按上游 MundaneMain.js:2540-2544 的排版出段。
 *
 * payload: { offices: [{key, cn, domain, moment|null}…] }
 * return : { text }
 */
export function runMundaneNavanayaka(payload) {
  const source = payload && typeof payload === 'object' ? payload : {};
  const offices = Array.isArray(source.offices) ? source.offices : [];
  if (!offices.length) {
    return { text: '' };
  }
  const lines = ['[年之九主]'];
  offices.forEach((o) => {
    const lord = o && o.moment ? varaLordOf(o.moment) : null;
    lines.push(`${o.cn}：${lord ? (PLANET_CN_V[lord] || lord) : '—'} · ${o.domain || ''}`);
  });
  (NAVANAYAKA_NOTES || []).forEach((n) => lines.push(typeof n === 'string' ? n : `${n.text || ''}`));
  lines.push('（九主属后世历书传统,非出自某一原典）');
  return { text: lines.join('\n') };
}

export default runMundaneNavanayaka;
