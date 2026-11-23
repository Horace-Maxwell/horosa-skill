// Snapshot text the 星阙 app builds with code that cannot be vendored on its own (its module drags in the page / React tree):
// the bundle already carries that closure (antd / dva / request stubbed, React real), so these entries call the app's own
// functions on data the Python side fetched — the same data the app feeds them. Nothing here re-implements app logic.
//
//   germany_hamburg   — AstroMidpoint.buildHamburgLines(disp, dialPoints, result, snapOrb)        → [汉堡学派要素] …
//   germany_transit   — AstroMidpoint.uranianTransitContactText(natalPts, transitPts, {base, orb, at}) → [行运接触]
//   germany_gephem    — AstroMidpoint.gephemRangeOf / graphicEphemerisText + UranianGraphicEphemeris defaults → [图形星历]
//   germany_points    — UranianDialMain.chartToPoints(chart) (+ TNP), the point set both time-layer sections read
//   chart_detail_full — chartDetailTablesText.buildChartDetailFullTables(result, tables, settings) → ■ 全表·… blocks
//   uranian_dial      — utils/uranianDial.js pure functions + stableOrder.tieSort (parity probe for the Python port)
import {
  buildHamburgLines, uranianTransitContactText, graphicEphemerisText, gephemRangeOf,
} from '@horosa-app/components/germany/AstroMidpoint.js';
import {
  DEFAULT_PLANETS as GEPHEM_DEFAULT_PLANETS, natalLines as gephemNatalLines, storedGephemDisp,
} from '@horosa-app/components/germany/UranianGraphicEphemeris.js';
import { chartToPoints } from '@horosa-app/components/germany/UranianDialMain.js';
import { buildChartDetailFullTables, CHART_DETAIL_TABLE_KEYS } from '@horosa-app/components/astro/chartDetailTablesText.js';
import * as UD from '@horosa-app/utils/uranianDial.js';
import { tieSort } from '@horosa-app/utils/stableOrder.js';
import * as AstroConst from '@horosa-app/constants/AstroConst.js';

function germanyPoints(args) {
  const pts = chartToPoints(args.chart || {});
  (Array.isArray(args.tnp) ? args.tnp : []).forEach((t) => { if (t && t.id) pts.push({ id: t.id, lon: t.lon }); });
  return pts;
}

export const TEXTS = {
  germany_hamburg: (a) => buildHamburgLines(a.disp || {}, a.dialPoints || [], a.result || {}, a.snapOrb, a.extras).join('\n'),
  germany_transit: (a) => uranianTransitContactText(a.natalPts || [], a.transitPts || [], a.opts || {}),
  germany_points: (a) => germanyPoints(a),
  germany_gephem_plan: (a) => {
    // 区间 + 行运星集 + 盘基：与 uranianGraphicEphemerisSection 同一套（页面保存的显示口径缺省、挂载盘基覆盖）。
    const rg = gephemRangeOf(a.disp || {});
    if (!rg) return null;
    const st = storedGephemDisp();
    const base = [90, 45, 22.5].indexOf(Number((a.disp || {}).dialBase)) >= 0 ? Number(a.disp.dialBase) : st.base;
    const planets = st.includeMoon ? [AstroConst.MOON, ...GEPHEM_DEFAULT_PLANETS] : GEPHEM_DEFAULT_PLANETS.slice();
    return { range: rg, base, planets };
  },
  germany_gephem: (a) => graphicEphemerisText(a.rows || [], a.planets || [], gephemNatalLines(a.chart || {}), a.base, a.range),
  chart_detail_full: (a) => buildChartDetailFullTables(a.result || null, a.tables || [], a.settings || {}),
  chart_detail_table_keys: () => CHART_DETAIL_TABLE_KEYS.slice(),
  uranian_dial: (a) => {
    const fn = UD[a.fn];
    if (a.fn === 'tieSortProbe') {
      return tieSort(a.items || [], ...(a.keys || []).map((k) => (row) => row[k]));
    }
    if (typeof fn !== 'function') throw new Error(`uranianDial has no ${a.fn}`);
    return fn(...(a.args || []));
  },
};

/** Run a batch of text calls: [{ name, args }] → [{ ok, value } | { ok: false, error }]; one bad call never sinks the rest. */
export function runTexts(calls) {
  return (Array.isArray(calls) ? calls : []).map((call) => {
    const run = TEXTS[call && call.name];
    if (!run) return { ok: false, error: `unknown text: ${call && call.name}` };
    try {
      return { ok: true, value: run(call.args || {}) };
    } catch (error) {
      return { ok: false, error: error instanceof Error ? error.message : String(error) };
    }
  });
}

export function listTexts() {
  return Object.keys(TEXTS);
}
