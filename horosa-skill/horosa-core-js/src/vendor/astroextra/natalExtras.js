// 本命增补 (v2.4.0 西占): 12分度 (Dodekatemoria) / 主宰星链 (dispositor chains) / 寿命格局 (Hyleg·Alcocoden).
//
// Ported from 星阙 astroAiSnapshot.js's buildDodecaSection / buildDispositorSection / buildLifespanSection.
// This module does the COMPUTE only (math + the vendored Ptolemy lifespan engine) and returns structured
// data; the skill's Python layer formats it to Chinese with its own _astro_msg (= 星阙 AstroTxtMsg).
// Lifespan uses the vendored divination/lifespan engine (Hyleg/Alcocoden, Ptolemy method).
import { buildFacts } from '../divination/engine/chartFacts.js';
import { runLifespan } from '../divination/lifespan/lifespanEngine.js';

// 行星/点 id 顺序 (= 星阙 AstroConst.LIST_OBJECTS). chart object ids match these strings verbatim.
const LIST_OBJECTS = [
  'Sun', 'Moon', 'Mercury', 'Venus', 'Mars', 'Jupiter', 'Saturn',
  'Uranus', 'Neptune', 'Pluto', 'North Node',
  'South Node', 'Dark Moon', 'Purple Clouds', 'Syzygy', 'Pars Fortuna',
  'Intp_Apog', 'Intp_Perg', 'Chiron', 'Pholus', 'Ceres', 'Pallas', 'Juno', 'Vesta',
  'LifeMasterDeg74',
];
const LIST_SIGNS = [
  'Aries', 'Taurus', 'Gemini', 'Cancer', 'Leo', 'Virgo',
  'Libra', 'Scorpio', 'Sagittarius', 'Capricorn', 'Aquarius', 'Pisces',
];
// 星座庙主(传统七政), index 0=Aries…11=Pisces (= 星阙 TRAD_SIGN_RULERS).
const TRAD_SIGN_RULERS = [
  'Mars', 'Venus', 'Mercury', 'Moon', 'Sun', 'Mercury',
  'Venus', 'Mars', 'Jupiter', 'Saturn', 'Saturn', 'Jupiter',
];
// 主宰链只走七政 (= 星阙 TRAD list inside buildDispositorSection).
const DISPOSITOR_PLANETS = ['Sun', 'Moon', 'Mercury', 'Venus', 'Mars', 'Jupiter', 'Saturn'];

function norm360Lon(x) {
  let v = Number(x) % 360;
  if (v < 0) {
    v += 360;
  }
  return v;
}

function getObjectsMap(chartObj) {
  const map = {};
  const chart = chartObj && chartObj.chart ? chartObj.chart : null;
  if (chart && Array.isArray(chart.objects)) {
    for (const obj of chart.objects) {
      if (obj && obj.id) {
        map[obj.id] = obj;
      }
    }
  }
  return map;
}

// 星体绝对黄经: 优先 obj.lon, 缺则用 sign+signlon 还原.
function objAbsLon(obj) {
  if (obj && obj.lon !== undefined && obj.lon !== null && !Number.isNaN(Number(obj.lon))) {
    return Number(obj.lon);
  }
  if (obj && obj.sign !== undefined && obj.signlon !== undefined && obj.signlon !== null) {
    const idx = LIST_SIGNS.indexOf(obj.sign);
    if (idx >= 0) {
      return idx * 30 + Number(obj.signlon);
    }
  }
  return null;
}

function dodecaLonOf(lon) {
  const L = norm360Lon(lon);
  return norm360Lon(Math.floor(L / 30) * 30 + (L % 30) * 12);
}

function rulerIdOfLon(lon) {
  return TRAD_SIGN_RULERS[Math.floor(norm360Lon(lon) / 30) % 12];
}

// 非破坏地补出 buildFacts 需要的 objectMap/houseMap.
function chartObjWithFactsMaps(chartObj) {
  if (!chartObj || !chartObj.chart) {
    return chartObj;
  }
  let objectMap = chartObj.objectMap;
  if (!objectMap && Array.isArray(chartObj.chart.objects)) {
    objectMap = {};
    chartObj.chart.objects.forEach((o) => { if (o && o.id) { objectMap[o.id] = o; } });
  }
  let houseMap = chartObj.houseMap;
  if (!houseMap && Array.isArray(chartObj.chart.houses)) {
    houseMap = {};
    chartObj.chart.houses.forEach((h) => { if (h && h.id) { houseMap[h.id] = h; } });
  }
  return Object.assign({}, chartObj, { objectMap, houseMap });
}

// 12分度: 每星本命黄经 → dodecaLonOf 落入的分度黄经.
function buildDodeca(chartObj) {
  const out = [];
  const objectMap = getObjectsMap(chartObj);
  LIST_OBJECTS.forEach((id) => {
    const lon = objAbsLon(objectMap[id]);
    if (lon === null) {
      return;
    }
    out.push({ id, natalLon: norm360Lon(lon), dodecaLon: dodecaLonOf(lon) });
  });
  return out;
}

// 主宰星链: 七政各落星座的庙主, 顺链至落自家星座的终极主宰(或互容成环).
function buildDispositor(chartObj) {
  const out = [];
  const objectMap = getObjectsMap(chartObj);
  DISPOSITOR_PLANETS.forEach((id) => {
    if (objAbsLon(objectMap[id]) === null) {
      return;
    }
    const chain = [id];
    let cur = id;
    let guard = 0;
    while (guard < 12) {
      const lon = objAbsLon(objectMap[cur]);
      if (lon === null) {
        break;
      }
      const ruler = rulerIdOfLon(lon);
      if (!ruler || ruler === cur) {
        break;
      }
      chain.push(ruler);
      if (chain.indexOf(ruler) !== chain.length - 1) {
        break;
      }
      cur = ruler;
      guard += 1;
    }
    out.push({ id, chain });
  });
  return out;
}

// 取主法三档（上游 components/astro/AstroLifespan.js:14-18 METHODS；缺省 ptolemy）。
const LIFESPAN_METHODS = ['ptolemy', 'alcabitius', 'dorotheus'];

// 寿命格局: Hyleg/Alcocoden (= 星阙 astroAiSnapshot.js:1123-1136 buildLifespanSection 的 runLifespan 调用)。
// [SURF-3] 太阳三态阈值随设置：上游优先本盘回显 params.{cazimiOrb,combustOrb,underBeamsOrb}（缺则全局仓，其缺省
// 17′/8.5°/17° 恰为引擎内建值 → 这里缺则不传、引擎用内建值，等价）；[D4] 取主法随用户选择（上游读 localStorage
// horosa.lifespan.method，skill 由调用方 opts.lifespanMethod 传入），缺省 ptolemy。
function buildLifespan(chartObj, opts) {
  try {
    const params = (chartObj && chartObj.params) || {};
    const pick = (k) => (params[k] !== undefined && params[k] !== null && params[k] !== '' ? Number(params[k]) : undefined);
    const facts = buildFacts(chartObjWithFactsMaps(chartObj), {
      cazimiOrb: pick('cazimiOrb'), combustOrb: pick('combustOrb'), underBeamsOrb: pick('underBeamsOrb'),
    });
    const wanted = opts && opts.lifespanMethod;
    const method = LIFESPAN_METHODS.indexOf(wanted) >= 0 ? wanted : 'ptolemy';
    return facts ? runLifespan(facts, { method }) : null;
  } catch (error) {
    return null;
  }
}

export function buildNatalExtras(chartObj, opts) {
  if (!chartObj || !chartObj.chart) {
    return { dodeca: [], dispositor: [], lifespan: null };
  }
  return {
    dodeca: buildDodeca(chartObj),
    dispositor: buildDispositor(chartObj),
    lifespan: buildLifespan(chartObj, opts),
  };
}

export default buildNatalExtras;
