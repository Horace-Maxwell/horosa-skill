import { unwrapNamedObject, unwrapResultEnvelope } from '../shared/unpack.js';
import * as LRConst from '../vendor/liureng/LRConst.js';
import { buildJinKouData, normalizeKinjinkouData } from '../vendor/jinkou/JinKouCalc.js';
import { resolveJinKouDiFen } from '../vendor/jinkou/JinKouState.js';
import { buildJinKouSnapshotText } from '../vendor/jinkou/JinKouSnapshot.js';

function normalizeTimeBranch(timeValue) {
  const text = `${timeValue || ''}`;
  const match = text.match(/[子丑寅卯辰巳午未申酉戌亥]/);
  return match ? match[0] : '';
}

function buildJinkouParams(payload) {
  return {
    date: payload.date || '',
    // 上游 genGodsParams 取 format('HH:mm')（JinKouMain.js:1370），快照「日期」行是时:分。
    time: `${payload.time || ''}`.slice(0, 5),
    zone: payload.zone || '',
    lat: payload.lat || '',
    lon: payload.lon || '',
  };
}

// 上游 JinKouMain.schoolsAllDefault（JinKouMain.js:1288-1294）逐字：五项流派/盘法全缺省才采用 ken 盘。
function schoolsAllDefault(o) {
  return (o.schoolYueJiang || 'zhongqi') === 'zhongqi'
    && (o.schoolGuiTable || 'shiwu') === 'shiwu'
    && (o.schoolGuiPan || 'di') === 'di'
    && (o.panShi || 'yang') === 'yang'
    && (o.soilChangSheng || 'shen') === 'shen';
}

export function runJinkou(payload) {
  const liureng = unwrapNamedObject(payload.liureng, 'liureng');
  if (!liureng || typeof liureng !== 'object') {
    throw new Error('Jinkou requires a liureng calculation payload.');
  }
  const options = { ...(payload.options || {}) };
  options.diFen = resolveJinKouDiFen(
    options.diFen || payload.diFen || '',
    options.diFenAuto === true,
    normalizeTimeBranch(liureng?.nongli?.time),
    false,
  );
  if (payload.guirengType !== undefined && payload.guirengType !== null && options.guirengType === undefined) {
    options.guirengType = payload.guirengType;
  }
  // 贵神体系恒 0（六壬法）——上游 JinKouMain.js:895 [B6·P2]；此前缺省 undefined → 本地盘贵人按 0 起、
  // [起盘信息]「贵人体系」却标「星占法贵人」（JinKouSnapshot 对 undefined 落第三档）。
  if (options.guirengType === undefined || options.guirengType === null) {
    options.guirengType = 0;
  }
  if (payload.isDiurnal !== undefined && options.isDiurnal === undefined) {
    options.isDiurnal = payload.isDiurnal;
  }
  // 十二长生五行：上游缺省随日干（JinKouMain.js:1551 wx = GanZiWuXing[dayGan]，wuxingAuto），同时喂本地引擎
  // （phaseTable）与快照；此前 skill 把「四位旺相五行」(wangElem) 当十二长生五行传给快照，两个概念混了。
  const dayGan = `${(liureng.nongli && liureng.nongli.dayGanZi) || ''}`.substr(0, 1);
  const wuxing = options.wuxing || LRConst.GanZiWuXing[dayGan] || '土';
  options.wuxing = wuxing;
  const local = buildJinKouData(liureng, options);
  if (!local || local.ready !== true) {
    throw new Error('Jinkou calculation returned no result.');
  }
  // 路由（上游 JinKouMain.assembleJinKouData:1255-1270）：五项全缺省且两源日柱对齐 → ken(kinjinkou) 行叠本地脚手架；
  // 否则本地 buildJinKouData（ken 不认五项流派；/liureng/gods 不吃时间基准，跨日界时两源日柱会差一天）。
  const isDefault = schoolsAllDefault(options);
  const ken = unwrapResultEnvelope(payload.ken_response ?? payload.kenResponse);
  const hasKen = !!(ken && typeof ken === 'object' && Array.isArray(ken.rows));
  if (!isDefault && hasKen) {
    throw new Error('jinkou route drift: schools are non-default (local engine) but a ken_response was supplied');
  }
  let data = local;
  let reason = isDefault ? 'no_ken' : 'school';
  if (isDefault && hasKen) {
    const panDay = ken.ganzhi ? ken.ganzhi.day : '';
    const lrDay = liureng.nongli ? liureng.nongli.dayGanZi : '';
    const dayAligned = !panDay || !lrDay || `${panDay}` === `${lrDay}`;
    if (dayAligned) {
      data = normalizeKinjinkouData(ken, local);
      reason = 'ken';
    } else {
      data.daySourceNote = `课时跨日界：后端盘按「${panDay}」日、历法按「${lrDay}」日，已统一取「${lrDay}」日推算（改「时间基准」为真太阳时可使两者一致）。`;
      reason = 'day_misaligned';
    }
  }
  if (!isDefault && (!data.plates || !data.plates.length)) {
    data.platesNote = '月将或占时未定，三盘环待起课后产出 —— 先以上方四位盘为准';
  }
  // 星阙 buildJinKouSnapshotText(params, liureng, runyear, jinkouData, wuxing, guirengType, gender)：
  // 20 段含解读层（用神强弱/四位生克/应期/地支关系/相关神煞/分类用神·求财）。runyear=null（金口诀非行年盘）。
  const snapshot_text = buildJinKouSnapshotText(
    buildJinkouParams(payload),
    liureng,
    payload.runyear ?? null,
    data,
    wuxing,
    options.guirengType,
    payload.gender,
  );
  return {
    tool: 'jinkou',
    technique: 'jinkou',
    input_normalized: { ...payload, options },
    data,
    route: { schoolsDefault: isDefault, source: data.source === 'kinjinkou' ? 'kinjinkou' : 'local', reason },
    snapshot_text,
  };
}
