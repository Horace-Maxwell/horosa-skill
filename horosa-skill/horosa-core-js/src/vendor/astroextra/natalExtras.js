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

// 寿命格局: Hyleg/Alcocoden, Ptolemy 取主法 (= 星阙 buildLifespanSection 的 runLifespan 调用).
function buildLifespan(chartObj) {
  try {
    const facts = buildFacts(chartObjWithFactsMaps(chartObj));
    return facts ? runLifespan(facts, { method: 'ptolemy' }) : null;
  } catch (error) {
    return null;
  }
}

export function buildNatalExtras(chartObj) {
  if (!chartObj || !chartObj.chart) {
    return { dodeca: [], dispositor: [], lifespan: null };
  }
  return {
    dodeca: buildDodeca(chartObj),
    dispositor: buildDispositor(chartObj),
    lifespan: buildLifespan(chartObj),
  };
}

export default buildNatalExtras;
