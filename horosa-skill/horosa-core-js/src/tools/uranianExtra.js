import {
  tnpReferenceList,
  TNP_CALIBRE_NOTE,
  TNP_GROUP_LABEL,
} from '../vendor/uranian/uranianTnpReference.js';

/**
 * 量化盘的两段附注：[虚星参考] 与 [戴维森盘]。
 *
 * - 虚星参考：静态口径表（8 颗 TNP 的三套周期并列），让 AI 知道落点是按哪套基准算的；
 *   逐字取自上游 `data/uranianTnpReference.js`，不在这里重写文案。
 * - 戴维森盘：时空中点真实起盘，数据随后端 `/germany/midpoint` 的 `davison` 字段回来，
 *   这里只做与上游 `AstroMidpoint.js` 同构的排版。
 *
 * payload: { davison?: <后端 davison 对象>, school?: string, showTnp?: boolean, labels?: {id:名} }
 * return : { text }
 */
export function runUranianExtra(payload) {
  const source = payload || {};
  const labels = source.labels && typeof source.labels === 'object' ? source.labels : {};
  const msg = (id) => labels[id] || id;
  const out = [];

  const dav = source.davison && typeof source.davison === 'object' ? source.davison : null;
  if (dav && Array.isArray(dav.points) && dav.points.length) {
    out.push('[戴维森盘]');
    out.push(
      `时空中点真实起盘：UT ${dav.utc || '—'} · 纬 ${Number(dav.lat).toFixed(3)}° · 经 ${Number(dav.lon).toFixed(3)}°`,
    );
    dav.points.slice(0, 24).forEach((pt) => {
      out.push(`  ${msg(pt.id)}：${Number(pt.lon).toFixed(2)}°${Number(pt.lonspeed) < 0 ? '（逆）' : ''}`);
    });
    if (dav.angles) {
      Object.keys(dav.angles).forEach((aid) => out.push(`  ${msg(aid)}：${Number(dav.angles[aid]).toFixed(2)}°`));
    }
  }

  // 上游：`disp.showTnp !== false && disp.school !== 'cosmo'`（宇宙流派不用虚星）。
  if (source.showTnp !== false && source.school !== 'cosmo') {
    out.push('[虚星参考]');
    out.push(TNP_CALIBRE_NOTE);
    tnpReferenceList().forEach((r) => {
      const pc = r.periodC != null ? `/丙${r.periodC}` : '';
      out.push(
        `  ${r.label}(${TNP_GROUP_LABEL[r.group]})：周期 甲${r.periodA}/乙${r.periodB}${pc} 年 · ${r.au}AU · ${r.keyword}`,
      );
    });
  }
  return { text: out.join('\n') };
}
