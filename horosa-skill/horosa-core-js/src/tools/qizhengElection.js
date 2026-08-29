import { mountainPosition, applyDeclination } from '../vendor/guolao/electionCore.js';

/**
 * 七政择日动盘（果老「择日双轮」headless 版）：/qizhengelection/pan|eclipses|azimuthsearch 的
 * 文本快照。数据往返按 §5 归 Python；本模块只做展示换算与排版。
 *
 * 展示语义逐字对照 GuoLaoElectionTable.js：
 *   - 黄道列 = eclToBranchText（地支镜像度「02未34」，白羊=戌起）——本文件 curated 抽取
 *     其 :12-33（SIGN_CN/eclToBranchText；整文件是 JSX 组件不可 vendor）。
 *   - 山位列 = mountainPosition(applyDeclination(azimuth))（vendored electionCore.js）+
 *     地平上下 +/−（altitudeTrue>=0）。
 *   - 态列：升殿失垣吃 /qizheng/moira —— 开源栈无此路由（LESSONS 排除台账），如实只标「逆/平」。
 *   - 搜索标题「X 到达 Y°(未来 N 天)」/「未来日食/月食」逐字取其 :104/:117。
 *
 * 日月食 kindFlag 为 swisseph 位标（SE_ECL_TOTAL=4/ANNULAR=8/PARTIAL=16/ANNULAR_TOTAL=32/
 * PENUMBRAL=64/CENTRAL=1/NONCENTRAL=2）——上游表格不解码（只显「食」），此处按官方常量表
 * 释名并保留原始位值，属 API 常量呈现而非任何技法推算。
 */

// —— curated 逐字：GuoLaoElectionTable.js:12,26-33 ——
const SIGN_CN = ['戌', '酉', '申', '未', '午', '巳', '辰', '卯', '寅', '丑', '子', '亥'];

function eclToBranchText(lon) {
  const v = ((Number(lon) % 360) + 360) % 360;
  const sign = Math.floor(v / 30);
  const inDeg = v - sign * 30;
  const deg = Math.floor(inDeg);
  const minute = Math.floor((inDeg - deg) * 60);
  return `${String(deg).padStart(2, '0')}${SIGN_CN[sign]}${String(minute).padStart(2, '0')}`;
}

const ECLIPSE_KIND_BITS = [
  [4, '全食'], [8, '环食'], [16, '偏食'], [32, '全环食'], [64, '半影食'],
];

function eclipseKindText(flag) {
  const f = Number(flag) || 0;
  const names = ECLIPSE_KIND_BITS.filter(([bit]) => (f & bit) !== 0).map(([, name]) => name);
  if (f & 1) { names.push('中心'); }
  else if (f & 2) { names.push('非中心'); }
  return names.length ? names.join('·') : `食(flag=${f})`;
}

function fmtNum(value, digits) {
  const n = Number(value);
  return Number.isFinite(n) ? n.toFixed(digits) : '—';
}

function headerLines(fields) {
  const f = fields && typeof fields === 'object' ? fields : {};
  const lines = ['[起盘信息]'];
  lines.push(`时间：${f.date || ''} ${f.time || ''}　时区：${f.zone || ''}`.trim());
  const place = [f.pos, f.lon, f.lat].filter((v) => v !== undefined && v !== null && `${v}` !== '').join('　');
  if (place) { lines.push(`地点：${place}`); }
  return lines;
}

function panSections(data, options) {
  const opts = options && typeof options === 'object' ? options : {};
  const plate = opts.plate || 'di';
  const ziZheng = opts.ziZheng === 'magnetic' ? 'magnetic' : 'true';
  const declination = Number(opts.declination) || 0;
  const planets = Array.isArray(data.planets) ? data.planets : [];
  const lines = ['[择日动盘]'];
  const plateCn = { tian: '天盘', di: '地盘', ren: '人盘' }[plate] || plate;
  lines.push(`山位口径：二十四山·${plateCn}${ziZheng === 'magnetic' ? `　磁偏 ${fmtNum(declination, 1)}°(磁北)` : '　真北'}`);
  planets.forEach((pl) => {
    const az = applyDeclination(pl.azimuth, ziZheng, declination);
    const mp = mountainPosition(az, plate);
    const aboveHorizon = Number(pl.altitudeTrue) >= 0;
    const state = pl.retrograde ? '逆' : '平';
    lines.push(
      `${pl.label}：${eclToBranchText(pl.lonTropical)} | ${mp.text}${aboveHorizon ? '+' : '−'}`
      + ` | 方位 ${fmtNum(az, 1)}° 高度 ${fmtNum(pl.altitudeTrue, 1)}° | ${state}`,
    );
  });
  const extra = ['[天象要素]'];
  if (data.trueSolarTime) { extra.push(`真太阳时：${data.trueSolarTime}　均时差：${fmtNum(data.equationOfTimeMin, 2)} 分`); }
  const rise = data.rise && typeof data.rise === 'object' ? data.rise : {};
  if (rise.sunrise || rise.sunset) { extra.push(`日出：${rise.sunrise || '—'}　日没：${rise.sunset || '—'}`); }
  if (rise.moonrise || rise.moonset) { extra.push(`月出：${rise.moonrise || '—'}　月没：${rise.moonset || '—'}`); }
  if (Number.isFinite(Number(data.lifeDeg))) {
    const modeCn = { sunrise: '日出', sunset: '日没', custom: '自定时刻' }[opts.eleLifeMode || 'sunrise'] || opts.eleLifeMode;
    extra.push(`命度：${eclToBranchText(data.lifeDeg)}（${modeCn}起）`);
  }
  if (Number.isFinite(Number(data.sunAzimuthSpeedDegPerMin))) {
    extra.push(`太阳方位速度：${fmtNum(data.sunAzimuthSpeedDegPerMin, 3)}°/分`);
  }
  return extra.length > 1 ? [...lines, '', ...extra] : lines;
}

function eclipseSection(rows, options) {
  const kind = (options && options.kind) === 'lunar' ? 'lunar' : 'solar';
  // 标题逐字：GuoLaoElectionTable.js:117
  const lines = ['[日月食搜索]', kind === 'solar' ? '未来日食' : '未来月食'];
  const list = Array.isArray(rows) ? rows : [];
  if (!list.length) {
    lines.push('（区间内未搜到）');
    return lines;
  }
  list.forEach((row) => {
    lines.push(`${row.date} ${row.time}　${eclipseKindText(row.kindFlag)}`);
  });
  return lines;
}

function azimuthSection(rows, options) {
  const opts = options && typeof options === 'object' ? options : {};
  // 标题逐字：GuoLaoElectionTable.js:104
  const lines = ['[方位搜索]', `${opts.body || '日'} 到达 ${fmtNum(opts.targetAz, 1)}°(未来 ${opts.days || 3} 天)`];
  const list = Array.isArray(rows) ? rows : [];
  if (!list.length) {
    lines.push('（区间内未到达该方位）');
    return lines;
  }
  const plate = opts.plate || 'di';
  list.forEach((row) => {
    const mp = mountainPosition(row.azimuth, plate);
    lines.push(`${row.date} ${row.time}　${fmtNum(row.azimuth, 1)}°（${mp.text}）`);
  });
  return lines;
}

export function runQizhengElection(payload) {
  const input = payload && typeof payload === 'object' ? payload : {};
  const kind = `${input.kind || 'pan'}`;
  const data = input.data;
  if (!data || typeof data !== 'object') {
    return {
      tool: 'qizhengelection',
      action: 'snapshot',
      data: { ok: false, error: { code: 'missing_data', message: '缺少后端返回数据（data）。' } },
      snapshot_text: '',
    };
  }
  try {
    const parts = [headerLines(input.fields)];
    if (kind === 'pan') {
      parts.push(panSections(data, input.options));
    } else if (kind === 'eclipses') {
      parts.push(eclipseSection(data.rows, input.options));
    } else if (kind === 'azimuthsearch') {
      parts.push(azimuthSection(data.rows, input.options));
    } else {
      return {
        tool: 'qizhengelection',
        action: 'snapshot',
        data: { ok: false, error: { code: 'unknown_kind', message: `未知动作 ${kind}。` } },
        snapshot_text: '',
      };
    }
    const snapshot_text = parts.map((lines) => lines.join('\n')).join('\n\n');
    return { tool: 'qizhengelection', action: 'snapshot', data: { ok: true }, snapshot_text };
  } catch (error) {
    return {
      tool: 'qizhengelection',
      action: 'snapshot',
      data: { ok: false, error: { code: 'snapshot_failed', message: `${(error && error.message) || error}` } },
      snapshot_text: '',
    };
  }
}

export default runQizhengElection;
