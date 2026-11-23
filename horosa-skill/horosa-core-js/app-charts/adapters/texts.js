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
import { getStoredUranianDisplay } from '@horosa-app/components/germany/UranianDialStyle.js';
import { buildChartDetailFullTables, CHART_DETAIL_TABLE_KEYS } from '@horosa-app/components/astro/chartDetailTablesText.js';
import * as UD from '@horosa-app/utils/uranianDial.js';
import { tieSort } from '@horosa-app/utils/stableOrder.js';
import * as AstroConst from '@horosa-app/constants/AstroConst.js';

function germanyPoints(args) {
  const pts = chartToPoints(args.chart || {});
  (Array.isArray(args.tnp) ? args.tnp : []).forEach((t) => { if (t && t.id) pts.push({ id: t.id, lon: t.lon }); });
  return pts;
}

// 无头挂载的显示口径 = 显示仓缺省 ⊕ 挂载覆盖（buildGermanySnapshotForFields 的 dispReq）；Python 只传用户给了的键。
const dispOf = (a) => ({ ...getStoredUranianDisplay(), ...((a && a.disp) || {}) });

export const TEXTS = {
  // buildGermanySnapshotText 末尾：SNAP_ORB = disp.orb（>0）否则 1，交给 buildHamburgLines
  germany_hamburg: (a) => {
    const disp = dispOf(a);
    const snapOrb = Number.isFinite(Number(disp.orb)) && Number(disp.orb) > 0 ? Number(disp.orb) : 1;
    return buildHamburgLines(disp, a.dialPoints || [], a.result || {}, snapOrb, a.extras).join('\n');
  },
  // uranianTransitSection 的末两行：盘基 / 容许度随显示口径（挂载可覆盖），at = transitAt 原串
  germany_transit: (a) => {
    const disp = dispOf(a);
    const opts = { base: Number(disp.dialBase) > 0 ? Number(disp.dialBase) : 90, orb: Number(disp.orb) > 0 ? Number(disp.orb) : 1, at: `${disp.transitAt}`.trim() };
    return uranianTransitContactText(a.natalPts || [], a.transitPts || [], opts);
  },
  germany_points: (a) => germanyPoints(a),
  germany_gephem_plan: (a) => {
    // 区间 + 行运星集 + 盘基：与 uranianGraphicEphemerisSection 同一套（页面保存的显示口径缺省、挂载盘基覆盖）。
    const disp = dispOf(a);
    const rg = gephemRangeOf(disp);
    if (!rg) return null;
    const st = storedGephemDisp();
    const base = [90, 45, 22.5].indexOf(Number(disp.dialBase)) >= 0 ? Number(disp.dialBase) : st.base;
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
    // opts 的 personal / uranian 是 Set（JSON 传不了）：数组原样转 Set，其余键不动
    const toSets = (x) => (x && typeof x === 'object' && !Array.isArray(x)
      ? Object.fromEntries(Object.entries(x).map(([k, v]) => [k, (k === 'personal' || k === 'uranian') && Array.isArray(v) ? new Set(v) : v]))
      : x);
    return fn(...(a.args || []).map(toSets));
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
