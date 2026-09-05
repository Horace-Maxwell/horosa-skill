// 七政四余 Moira 层 headless wrapper（bespoke，非 vendor）。
//
// 两个入口（payload.action 分流）：
// 1. 缺省 / 'patterns'：政余格局（Moira DSL）—— payload.chart = /chart 七政四余响应；payload.fields/params
//    可选（headless 缺省走默认 lifeMode/昼夜/季节）。输出 snapshot_text = 与 星阙 buildGuolaoPatternSection
//    同源同格式的「喜格/忌格/察看」三行。
// 2. 'rules_sections'：[虚实]/[本命化曜]/[流年流曜] 三段 —— payload.moiraRules = Java `/qizheng/moira` 响应
//    （weakSolid / yearStars.birth / yearStars.transit / transitYearStars），payload.transitYearGz = 流年干支
//    兜底（Python 按流年时刻算）。三段 builder 逐字移植自 星阙 GuoLaoChartMain.js（buildGuolaoWeakSolidSection /
//    buildGuolaoBirthStarsSection / buildGuolaoTransitStarsSection，v44 硬缺修）；无数据回空串不产段。
//    ⚠ v0.36.0 之前这三段被当成「开源 astropy 无该路由」永久排除——实际 /qizheng/moira 是 **Java** 聚合层
//    （astrostudycn QizhengMoiraController）的路由，当年拿 Python chart 服务测的 500（docs/LESSONS.md）。
import { buildLocalMoiraPatterns, buildGodRowsFromChart } from '../vendor/guolao/guolaoMoira.js';

// 与上游 GuoLaoChartMain.js 逐字相同的三张参考表（十神序/天禄至天权年曜主项）。
const MOIRA_TEN_GOD_ORG = ['天禄', '天暗', '天福', '天耗', '天荫', '天贵', '天嗣', '天刑', '天印', '天囚', '天权'];
const MOIRA_TEN_GOD_ALT = ['比肩', '劫财', '食神', '伤官', '偏财', '正财', '七杀', '正官', '偏印', '正印'];
const MOIRA_YEAR_INFO_GROUPS = [
  ['天禄', '科名', '天马', '生官'],
  ['天暗', '科甲', '地驿'],
  ['天福', '文星', '禄元'],
  ['天耗', '魁星', '马元', '值难'],
  ['天荫', '官星', '天元', '职元'],
  ['天贵', '印星', '地元', '局主'],
  ['天嗣', '寿元', '人元', '天经'],
  ['天刑', '催官', '仁元', '地纬'],
  ['天印', '禄神', '血支'],
  ['天囚', '喜神', '血忌'],
  ['天权', '爵星', '产星', '伤官'],
];

function safeList(val) {
  return Array.isArray(val) ? val : [];
}

function safeMap(val) {
  return val && typeof val === 'object' && !Array.isArray(val) ? val : {};
}

// 上游 formatGodName：神煞项可能是字符串或 {name} 对象；这里只做同等的字符串化。
function formatGodName(item) {
  if (item === undefined || item === null) return '';
  if (typeof item === 'string') return item.trim();
  if (typeof item === 'object') return `${item.name || item.label || item.star || ''}`.trim();
  return `${item}`.trim();
}

function joinNames(list) {
  const arr = safeList(list).map(formatGodName).filter(Boolean);
  return arr.length ? arr.join('、') : '无';
}

// [虚实]：宫位 | 虚实 | 虚柱 | 实柱（GFM 表）+ 口径行。
export function buildGuolaoWeakSolidSection(moiraRules) {
  try {
    const rows = safeList(safeMap(safeMap(moiraRules).weakSolid).houses);
    if (!rows.length) return '';
    const out = [];
    out.push('| 宫位 | 虚实 | 虚柱 | 实柱 |');
    out.push('| --- | --- | --- | --- |');
    rows.forEach((house) => {
      out.push(`| ${house.house || '—'} | ${house.label || '—'} | ${joinNames(house.weakPillars) || '—'} | ${joinNames(house.solidPillars) || '—'} |`);
    });
    out.push('口径：虚宫按四柱旬空推虚；实宫按年、月、日、时四柱地支定实。');
    return out.join('\n');
  } catch (e) {
    return '';
  }
}

// [本命化曜]：本命年柱 + ◆ 本命化曜（星：化X（同归：…））+ ◆ 十神序（参考）+ ◆ 天禄至天权（年曜主项）。
export function buildGuolaoBirthStarsSection(moiraRules) {
  try {
    const birthYearStars = safeMap(safeMap(safeMap(moiraRules).yearStars).birth);
    const planetRows = safeList(birthYearStars.planetRows);
    if (!planetRows.length) return '';
    const out = [];
    if (birthYearStars.yearPole) out.push(`本命年柱：${birthYearStars.yearPole}`);
    out.push('◆ 本命化曜');
    planetRows.forEach((row) => {
      const items = safeList(row.items).length ? joinNames(row.items) : '';
      out.push(`${row.star}：化${row.changeTo || '-'}${items && items !== '无' ? `（同归：${items}）` : ''}`);
    });
    out.push('◆ 十神序（参考）');
    out.push(`原十神序：${MOIRA_TEN_GOD_ORG.join('、')}`);
    out.push(`替代十神序：${MOIRA_TEN_GOD_ALT.join('、')}`);
    out.push('◆ 天禄至天权（年曜主项）');
    MOIRA_YEAR_INFO_GROUPS.forEach((items) => {
      out.push(`${items[0]}：${items.slice(1).join('、') || '主项'}`);
    });
    return out.join('\n');
  } catch (e) {
    return '';
  }
}

// [流年流曜]：流年干支 + ◆ 流年化曜 + ◆ 流曜落宫。上游从 fields 推流年干支（UI 专属）；
// headless 版由 Python 按流年时刻算好 transitYearGz 传入作兜底。
export function buildGuolaoTransitStarsSection(moiraRules, transitYearGz) {
  try {
    if (!moiraRules) return '';
    const currentYearStars = safeMap(safeMap(moiraRules.yearStars).transit);
    const planetRows = safeList(currentYearStars.planetRows);
    const signRows = safeList(moiraRules.transitYearStars);
    if (!planetRows.length && !signRows.length) return '';
    const out = [];
    const yearGz = currentYearStars.yearPole || transitYearGz || '';
    if (yearGz) out.push(`流年干支：${yearGz}`);
    if (planetRows.length) {
      out.push('◆ 流年化曜');
      planetRows.forEach((row) => {
        const items = safeList(row.items).length ? joinNames(row.items) : '';
        out.push(`${row.star}：化${row.changeTo || '-'}${items && items !== '无' ? `（同归：${items}）` : ''}`);
      });
    }
    if (signRows.length) {
      out.push('◆ 流曜落宫');
      signRows.forEach((row) => {
        const pos = [row.quality, row.zi, row.signName].filter(Boolean).join(' · ');
        out.push(`${row.name}：${row.star || '-'}（${row.shortName || '-'}${pos ? `；${pos}` : ''}）`);
      });
    }
    return out.join('\n');
  } catch (e) {
    return '';
  }
}

export function buildGuolaoMoiraSections(moiraRules, transitYearGz) {
  return {
    weakSolid: buildGuolaoWeakSolidSection(moiraRules),
    birthStars: buildGuolaoBirthStarsSection(moiraRules),
    transitStars: buildGuolaoTransitStarsSection(moiraRules, transitYearGz),
  };
}

export function runGuolaoMoira(payload) {
  if (payload && payload.action === 'rules_sections') {
    return {
      sections: buildGuolaoMoiraSections(payload.moiraRules || null, payload.transitYearGz || ''),
    };
  }
  const result = payload && payload.chart ? payload.chart : payload;
  const fields = (payload && payload.fields) || {};
  const params = (payload && payload.params) || {};
  try {
    const godRows = buildGodRowsFromChart(result, fields);
    const patterns = buildLocalMoiraPatterns(result, fields, params, godRows) || [];
    if (!patterns.length) {
      return { snapshot_text: '无', data: { patterns: [] } };
    }
    const fmt = (list) => list.map((it) => `${it.name}（${it.detail || it.dsl || ''}）`).join('；');
    const good = patterns.filter((it) => it.level === 'good');
    const bad = patterns.filter((it) => it.level === 'bad');
    const other = patterns.filter((it) => it.level !== 'good' && it.level !== 'bad');
    const out = [];
    out.push(`喜格：${good.length ? fmt(good) : '（无）'}`);
    out.push(`忌格：${bad.length ? fmt(bad) : '（无）'}`);
    if (other.length) {
      out.push(`察看：${fmt(other)}`);
    }
    return { snapshot_text: out.join('\n'), data: { patterns } };
  } catch (e) {
    // 降级「无」，不影响既有 guolao 段（与 星阙 buildGuolaoPatternSection 的 try/catch 一致）。
    return { snapshot_text: '无', data: { patterns: [], error: String(e) } };
  }
}
