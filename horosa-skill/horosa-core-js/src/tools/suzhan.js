import { buildSuzhanSnapshotText, suzhanAscRaModeOf } from '../vendor/suzhan/SuZhanMain.js';
import { ASC_RA_MODE_CLASSIC, ASC_RA_MODE_IMPROVED, chartHasEastPoint } from '../vendor/utils/ascRaMode.js';
import { DEFAULT_OBJECTS } from '../constants/AstroConst.js';

/**
 * 宿占（suzhan）快照 = 上游 buildSuzhanSnapshotText（vendored suzhan/SuZhanMain.js，verbatim：上游全文件 + 声明式 deviation）。
 *
 * 上游的 `fields` 是 dva 表单对象（`fields.date.value.format('YYYY-MM-DD')`、其余 `.value`）；headless 用同形薄适配。
 * 与上游页面一致的两条口径：
 *   · 外盘 / 盘型两行只在调用方显式给了 szchart / szshape 时出（上游 astro 模型缺省不带这两键，SuZhanInput 改了才写入）；
 *   · 宿法 / 人事十二宫起盘两行恒出（模型缺省 doubingSu28=0、houseStartMode=0，models/astro.js:117-119/:312-316）。
 * planetDisplay 缺省 = 上游 app 模型缺省 DEFAULT_OBJECTS（models/app.js:255）。
 * 人事十二宫「八字公式起盘」读 chart.nongli.bazi（只有 Java /chart 带）；缺它 computeAscSignIndex 回落 ASC（上游同），
 * 本工具把「是否拿到了农历时支」回报给 Python（data.nongliHour），由 Python 决定是否进 warnings。
 *
 * 上升取法（上游 v3.14.0 utils/ascRaMode.js，只在 ASC 起盘时起作用）：params.ascRaMode = 'improved' 真赤经（缺省）| 'classic' 东点黄经。
 * 给了就进 fields.ascRaMode（上游无头重算 suzhanFieldsForRecord 同形），由 vendored suzhanAscRaModeOf / withAscRaModeRoot 换上升点、
 * ascRaModeSnapshotLine 写明档位；实际生效档与本盘有没有东点黄经回报在 data.ascRaMode / data.eastPointAvailable。
 *
 * payload: { chart: </chart 整份响应>, params: {date, time, zone, lon, lat, szchart?, szshape?, doubingSu28, houseStartMode, ascRaMode?}, planetDisplay? }
 * return : { text, data: { ok, nongliHour, ascRaMode, eastPointAvailable } }
 */
export function runSuzhan(payload) {
  const source = payload && typeof payload === 'object' ? payload : {};
  const chartObj = source.chart && typeof source.chart === 'object' ? source.chart : {};
  const p = source.params && typeof source.params === 'object' ? source.params : {};
  const moment = { format: (fmt) => (fmt === 'HH:mm:ss' ? `${p.time || ''}` : `${p.date || ''}`) };
  const fields = {
    date: { value: moment },
    time: { value: moment },
    zone: { value: p.zone },
    lon: { value: p.lon },
    lat: { value: p.lat },
    doubingSu28: { value: p.doubingSu28 },
    houseStartMode: { value: p.houseStartMode },
  };
  if (p.ascRaMode === ASC_RA_MODE_IMPROVED || p.ascRaMode === ASC_RA_MODE_CLASSIC) {
    fields.ascRaMode = { value: p.ascRaMode };
  }
  ['szchart', 'szshape'].forEach((key) => {
    if (p[key] !== undefined && p[key] !== null && p[key] !== '') {
      fields[key] = { value: p[key] };
    }
  });
  const planetDisplay = Array.isArray(source.planetDisplay) && source.planetDisplay.length ? source.planetDisplay : DEFAULT_OBJECTS;
  const chart = chartObj.chart || {};
  const bazi = (chart.nongli && chart.nongli.bazi) || (chartObj.nongli && chartObj.nongli.bazi) || null;
  const hourZhi = bazi && bazi.time && bazi.time.branch ? bazi.time.branch.cell : null;
  const text = buildSuzhanSnapshotText(chartObj, fields, planetDisplay) || '';
  return {
    text,
    data: {
      ok: !!text,
      nongliHour: hourZhi || null,
      // 实际生效档（八字公式起盘恒 improved）与本盘上升点带不带东点黄经（经典档没有它 = 回落真赤经，快照行照实写）。
      ascRaMode: suzhanAscRaModeOf(fields),
      eastPointAvailable: chartHasEastPoint(chart),
    },
  };
}

export default runSuzhan;
