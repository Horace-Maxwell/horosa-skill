// 七政择日盘 — the app's own Moira wheel (components/guolao/GuoLaoMoiraWheel.js) as the 七政择日 page shows it: QizhengZeriMain
// embeds GuoLaoChartMain with the engine locked to 星阙七政 (QIZHENG_ZERI_LOCKED), whose default chart style is Moira
// (getStoredGuolaoChartStyle). Props exactly as GuoLaoChartMain.render passes them in that branch:
//   rootValue = the 七政 chart object (罗计 swapped by node mode, four pillars on chart.nongli), value = its chart with
//   aspects / lots attached, transitValue / transitParams = the 流年 chart at the transit moment, moiraRules = the
//   /qizheng/moira rules (the page uses its local fallback only when they are incomplete — not reproduced: we refuse),
//   electionData = the /qizhengelection/pan answer (static western houses), display flags = the stored-preference
//   getters with nothing stored (the app's defaults), fields = QizhengZeriMain.buildFields for the picked moment.
// All engine data comes from the report service (reports/aux_charts.py); nothing is computed here.
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import GuoLaoMoiraWheel from '@horosa-app/components/guolao/GuoLaoMoiraWheel.js';
import WHEEL_CSS from '@horosa-app/components/guolao/GuoLaoMoiraWheel.less';
import {
  getStoredGuolaoDisplay, getStoredGuolaoElection, getStoredMoiraTransitGodsVisible,
} from '@horosa-app/components/guolao/GuoLaoChartStyle.js';
import { isIncompleteMoiraRules } from '@horosa-app/components/guolao/main/format.js';
import { mkField, mkDT } from '@horosa-app/components/zeri/zeriHostUtils.js';
import { applyComponentCss } from '../css.js';

const HEIGHT = 740; // the wheel's own side cap (GuoLaoMoiraWheel.render: min(height, 740))

function hms(time) {
  const parts = `${time || '00:00:00'}`.split(':');
  while (parts.length < 3) parts.push('00');
  return parts.slice(0, 3).map((p) => p.padStart(2, '0')).join(':');
}

// QizhengZeriMain.buildFields for the picked moment: pickText + the scan's geo and options (su28Mode / nodeType / lilithType),
// which the report service passes as the 七政 cast payload (params).
function qizhengZeriFields(params) {
  const p = params || {};
  const t = mkDT(`${`${p.date || ''}`.replace(/\//g, '-')} ${hms(p.time)}`);
  return {
    date: mkField(t),
    time: mkField(t.clone ? t.clone() : t),
    ad: mkField(1),
    zone: mkField(p.zone !== undefined ? p.zone : '+08:00'),
    lon: mkField(p.lon),
    lat: mkField(p.lat),
    gpsLat: mkField(p.gpsLat),
    gpsLon: mkField(p.gpsLon),
    pos: mkField(p.pos || ''),
    gender: mkField(1),
    doubingSu28: mkField(p.doubingSu28 !== undefined && p.doubingSu28 !== null && `${p.doubingSu28}` !== '' ? Number(p.doubingSu28) : 2),
    guolaoLifeMode: mkField(p.guolaoLifeMode || 'asc'),
    guolaoLilithType: mkField(p.guolaoLilithType === 'true' ? 'true' : 'mean'),
    guolaoNodeType: mkField(p.guolaoNodeType === 'true' ? 'true' : 'mean'),
  };
}

function slashDate(params) {
  const m = `${params.date || ''}`.match(/^(-?\d+)-(\d{1,2})-(\d{1,2})$/);
  return m ? { ...params, date: `${m[1]}/${m[2]}/${m[3]}` } : params;
}

export function renderGuolaoMoira(data) {
  const root = data && data.root;
  if (!root || !root.chart || !Array.isArray(root.chart.objects)) throw new Error('guolao moira: needs the 七政 chart object');
  if (!data.transit || !data.transit.chart) throw new Error('guolao moira: needs the 流年 chart object');
  if (isIncompleteMoiraRules(data.rules)) {
    throw new Error('guolao moira: the Moira rules are incomplete (the app would draw its local fallback rules instead)');
  }
  const chart = { ...root.chart, aspects: root.aspects || {}, lots: root.lots || [] }; // GuoLaoChartMain.render
  const display = getStoredGuolaoDisplay();
  const props = {
    rootValue: root,
    value: chart,
    election: getStoredGuolaoElection(),
    electionData: data.election || null,
    transitValue: data.transit,
    // the page formats the 流年 date YYYY/MM/DD (paramsWithMoiraTransit); the skill keeps the engine's YYYY-MM-DD — same date
    transitParams: slashDate(data.transitParams || {}),
    transitLoading: false,
    showAspectsMode: display.showAspects === true,
    showMoiraTransitGods: getStoredMoiraTransitGodsVisible(),
    moiraRules: data.rules,
    aspectSet: display.aspects,
    aspectOrbs: display.aspectOrbs,
    hiddenPlanets: display.hiddenPlanets,
    hiddenGodsBirth: display.hiddenGodsBirth,
    hiddenGodsTransit: display.hiddenGodsTransit,
    showDignity: display.dignity,
    showMountains: display.mountains,
    showBirthGods: display.birthGods,
    showAgeRing: display.ageRing,
    limitChildBase: display.limitChildBase,
    onAgeClick: () => {},
    limitYearBoundary: display.limitYearBoundary,
    height: HEIGHT,
    fields: qizhengZeriFields(data.params),
    onTipClick: () => {},
  };
  const html = renderToStaticMarkup(createElement(GuoLaoMoiraWheel, props));
  const match = html.match(/<svg[\s\S]*<\/svg>/);
  if (!match) throw new Error('guolao moira: the wheel rendered no svg');
  const box = (match[0].match(/viewBox="([-\d.\s]+)"/) || [])[1];
  const side = HEIGHT;
  // the wheel sizes itself with style={{width, height}} (CSS px); a figure needs width / height attributes
  let svg = match[0].replace(/^<svg/, `<svg xmlns="http://www.w3.org/2000/svg" width="${side}" height="${side}"`);
  svg = svg.replace(/^(<svg[^>]*?)\sstyle="[^"]*"/, '$1');
  // the wheel lives inside .horosa-guolao-moira-wheel; its stylesheet carries the light tokens (--moira-*) and the svg font
  svg = applyComponentCss(svg, WHEEL_CSS, 'horosa-guolao-moira-wheel');
  void box;
  return { svg, width: side, height: side };
}
