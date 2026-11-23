import { buildMundaneCardSections } from '../vendor/mundane/main/cards.js';
import { MUNDANE_ORB_SCHEME_CN, MUNDANE_INGRESS_RULE_CN, BARBAULT_SETS } from '../vendor/mundane/main/tables.js';
import {
  MUNDANE_CYCLE_TABLES, MUNDANE_CYCLE_OPTIONS, MUNDANE_CYCLE_DEFAULTS,
  mundaneCycleFields, mundaneCycleRequestFields, mundaneCycleTable, buildMundaneCycleText,
} from '../vendor/utils/mundaneCycles.js';
import { MUNDANE_HORARY_KINDS } from '../vendor/mundane/mundaneHorary.js';
import { MUNDANE_RULESETS, rulesetConfig } from '../vendor/mundane/ruleset.js';
import { buildMundaneAiSnapshotParts } from '../vendor/mundane/mundaneAiSnapshot.js';
import { allRegions, regionCandidates } from '../vendor/divination/data/regionCharts.js';
import { SIGN_ORDER } from '../vendor/divination/data/signs.js';
import { leadingYearOf } from '../vendor/bazi/dateStrSafe.js';

/**
 * 世运右栏卡片段（上游 v3.11 [Q-444/T-407]）：`buildMundaneCardSections(chart, extra, state, facts)`
 * （上游 components/mundane/MundaneMain.js:232，vendored 逐字，UI 尾部由 manifest 的 truncate_before 剥离）。
 *
 * 上游在页面里把「按需拉取物」（四季种子 / 相位格局 / 木土会合 / Barbault / 食时长 / 梅沙入境时刻…）
 * 放在 React state 里，再原样喂给这个纯函数。headless 侧由 Python 取数（请求型编排归 Python，
 * AGENTS §5），这里只负责把 Python 给的 extra/state 原样交给上游 builder —— **不改键、不补默认值**
 * （跨边界改键是 issue #15 家族的形状）。
 *
 * 一次可跑多张盘（jobs）：skill 的世俗盘恒以入宫盘为底，盘型专属卡另在该盘型自己的盘上算
 * （新月/满月子盘、食盘、恒星入境盘、梅沙入境盘…），合在一个 Node 进程里省一次冷启动。
 *
 * v3.14.0：行星周期盘型另有 `action: 'cycles_request'`（Barbault 慢星组合 → 行星名表、世运周期表的请求字段，全部取自
 * vendored 上游表 / 函数）；cycles job 的 state 带 cycleTableResult / cycleTableRequest 时由上游 buildMundaneCycleText 出
 * [世运周期表] 正文。
 *
 * payload: { jobs: [{ id, chart: <完整 /chart 响应>, extra: {...}, state: {...} }] }
 * return : { tool, data: { ok, jobs: [{ id, ok, cards: [{ title, text }], error? }] } }
 *   - cards 保持上游产出顺序；title 按上游 aiExport.parseSectionTitleLine（:1140）同一口径
 *     `^\[(.+)\]$` 从首行解析，解析不出（如上游 `[地区盘·12世俗宫]（地区名）` 首行带尾巴）记 null。
 */

// 与 vendored MundaneMain.js 顶部 AstroExtraCommon stub 的 `chartRequestKey = () => 'headless'` 成对：
// 上游 [盘型格局] 以 `st.patKey === chartRequestKey(chart)` 判定相位格局属于本盘（:387）。headless 的
// 相位格局就是 Python 对同一张盘现取的 /astroextra/analysis，故恒等键即正解。
export const HEADLESS_PAT_KEY = 'headless';

const TITLE_RE = /^\[(.+)\]$/;

function splitCard(block) {
  const text = `${block || ''}`;
  const first = text.split('\n')[0].trim();
  const m = first.match(TITLE_RE);
  return { title: m ? m[1] : null, text };
}

// 世运口径（上游页面设置 MUNDANE_PAGE_SETTINGS，MundaneMain.js:526-533）：规则集四派 + 两个页面级覆盖 + 吠陀世运三键。
// 值域锚定引擎自带表（MUNDANE_RULESETS / MUNDANE_ORB_SCHEME_CN / MUNDANE_INGRESS_RULE_CN / SIGN_ORDER），认不出的回执 invalid。
function settingsCheck(settings) {
  const s = settings && typeof settings === 'object' ? settings : {};
  const invalid = [];
  const oneOf = (key, allowed) => {
    const v = s[key];
    if (v !== undefined && v !== null && v !== '' && allowed.indexOf(v) < 0) invalid.push({ key, value: v, allowed });
  };
  oneOf('mundaneRuleset', MUNDANE_RULESETS.map((r) => r.key));
  oneOf('mundaneOrbScheme', ['auto', ...Object.keys(MUNDANE_ORB_SCHEME_CN)]);
  oneOf('mundaneIngressRule', ['auto', ...Object.keys(MUNDANE_INGRESS_RULE_CN)]);
  oneOf('vedicDashaYearLen', [365.2425, 360]);
  oneOf('vedicNatalAsc', SIGN_ORDER);
  // v3.14.0 世运周期表（utils/mundaneCycles.js）：当前表 + 14 个选项键，值域 = 引擎自带的 MUNDANE_CYCLE_TABLES / MUNDANE_CYCLE_OPTIONS。
  // 后端 mundane_cycles._choice 对认不出的值静默取缺省（表也一样）——所以在这里拒。
  oneOf('cycleTable', MUNDANE_CYCLE_TABLES.map((t) => t.value));
  Object.keys(MUNDANE_CYCLE_OPTIONS).forEach((key) => oneOf(key, MUNDANE_CYCLE_OPTIONS[key].map((o) => o.value)));
  // Barbault 慢星组合（页面设置 bbSet，v3.14.0 进 MUNDANE_PAGE_SETTINGS）：值域 = BARBAULT_SETS。谐波 bbHarm 的值域是后端
  // compute_barbault 的 1–12（页面下拉只列 1–4），由 Python 判整数与范围。
  oneOf('bbSet', BARBAULT_SETS.map((b) => b.key));
  const cfg = rulesetConfig(s.mundaneRuleset);
  return {
    invalid,
    // 快照头三行的查名（上游 buildAiSnapshot:2852-2866：规则集行恒出；两条页面级覆盖行只在非 auto 时出）。
    meta: {
      ruleset: cfg.key,
      rulesetLabel: cfg.label,
      orbSchemeLabel: s.mundaneOrbScheme && s.mundaneOrbScheme !== 'auto' ? (MUNDANE_ORB_SCHEME_CN[s.mundaneOrbScheme] || s.mundaneOrbScheme) : null,
      ingressRuleLabel: s.mundaneIngressRule && s.mundaneIngressRule !== 'auto' ? (MUNDANE_INGRESS_RULE_CN[s.mundaneIngressRule] || s.mundaneIngressRule) : null,
    },
  };
}

// 地区盘（上游 MundaneMain.applyRegion :715-733）：按 regionKey 从 allRegions()（预置 REGION_CHARTS；headless 无 localStorage →
// 用户自定义盘恒空）取建置记录，多候选盘取 regionCandidate（缺省首候选 = 最通行者），返回上游 patchFields 的同一组盘面字段与
// setExtra 的同一组 extra（regionCn = rec.cn + ' · ' + cand.label；regionFoundingYear = 日期前四位）。认不出的键回执 keys 供报错。
function resolveRegion(source) {
  const regions = allRegions();
  const keys = Object.keys(regions);
  const key = source.regionKey !== undefined && source.regionKey !== null ? `${source.regionKey}` : '';
  const rec = regions[key];
  if (!rec) {
    return { ok: false, error: { code: 'unknown_region', message: `未知地区盘 regionKey=${key || '(空)'}` }, keys, candidates: {} };
  }
  const cands = regionCandidates(key);
  const wanted = source.regionCandidate !== undefined && source.regionCandidate !== null && `${source.regionCandidate}` !== '' ? `${source.regionCandidate}` : null;
  let cand = null;
  if (cands) {
    cand = wanted ? cands.find((c) => c.key === wanted) || null : cands[0];   // 多候选盘:默认首候选(最通行者)
    if (wanted && !cand) {
      return { ok: false, error: { code: 'unknown_region_candidate', message: `地区盘 ${key} 无候选时刻 ${wanted}` }, keys, candidates: { [key]: cands.map((c) => c.key) } };
    }
  } else if (wanted) {
    return { ok: false, error: { code: 'unknown_region_candidate', message: `地区盘 ${key} 只有一个建置时刻，不接受 regionCandidate` }, keys, candidates: {} };
  }
  const useTime = (cand && cand.time) ? cand.time : (rec.time || '12:00:00');
  return {
    ok: true,
    keys,
    region: { key, cn: rec.cn, note: rec.note || '', candidate: cand ? { key: cand.key, label: cand.label, note: cand.note || '' } : null },
    fields: { date: rec.date, time: useTime, zone: rec.zone || '+00:00', lon: rec.lon, lat: rec.lat, gpsLon: rec.gpsLon, gpsLat: rec.gpsLat, pos: rec.cn },
    extra: {
      mundaneType: 'region', regionKey: key, regionCn: rec.cn + (cand ? ` · ${cand.label}` : ''),
      // 上游 v3.13.0 MundaneMain.js:735 leadingYearOf(rec.date)（带符号 1–5 位年；slice(0, 4) 会把 '-0753' 切成 -75）。
      regionFoundingYear: leadingYearOf(rec.date) || null,
    },
  };
}

// 行星周期盘型（mundaneType='cycles'）两份请求的构参，全部取自 vendored 上游表 / 函数（Python 只发请求，不手抄）：
//   · barbault —— 上游 computeBarbault（MundaneMain.js:807-828）：`planets: set.planets`、`harm` 只在 >1 时下发；
//     set = BARBAULT_SETS.find(key === bbSet) || BARBAULT_SETS[0]。
//   · cycleTable —— 上游 MundaneCycleTables.body() / MundaneMain.ensureCycleTableText（:3022-3035）：
//     `mundaneCycleRequestFields(settings, { startYear, endYear })`，settings = 页面保存的设置（缺键取 MUNDANE_CYCLE_DEFAULTS）。
//     ignored = 给了却对当前表不起作用的选项键（页面上该表不显示这些下拉；mundaneCycleFields 是同一判据）与年份键。
function cyclesRequest(source) {
  const given = source.settings && typeof source.settings === 'object' ? source.settings : {};
  const years = source.years && typeof source.years === 'object' ? source.years : {};
  const set = BARBAULT_SETS.find((b) => b.key === given.bbSet) || BARBAULT_SETS[0];
  const settings = { ...MUNDANE_CYCLE_DEFAULTS };
  Object.keys(MUNDANE_CYCLE_DEFAULTS).forEach((key) => {
    if (given[key] !== undefined && given[key] !== null && given[key] !== '') settings[key] = given[key];
  });
  const def = mundaneCycleTable(settings.cycleTable);
  const active = mundaneCycleFields(settings);
  const ignored = Object.keys(MUNDANE_CYCLE_OPTIONS)
    .filter((key) => given[key] !== undefined && given[key] !== null && given[key] !== '' && active.indexOf(key) < 0);
  if (years.startYear !== undefined && years.startYear !== null && !(def.range || def.year)) ignored.push('cycleStartYear');
  if (years.endYear !== undefined && years.endYear !== null && !def.range) ignored.push('cycleEndYear');
  return {
    ok: true,
    barbault: { setKey: set.key, planets: set.planets.slice() },
    cycleTable: {
      table: def.value,
      label: def.label,
      fields: mundaneCycleRequestFields(settings, { startYear: years.startYear, endYear: years.endYear }),
      ignored,
    },
  };
}

// [世运周期表]：上游 MundaneCycleTables.load → onText(buildMundaneCycleText(result, body), chartRequestKey(chart)) →
// MundaneMain state.cycleTableText / cycleTableKey（:2814）；buildMundaneCardSections 在 cycles 分支按键相等才成段（:506）。
// headless：Python 把 /astroextra/mundanecycles 的响应与发出的请求体原样给进 state（cycleTableResult / cycleTableRequest），
// 这里用同一个上游函数出正文、键用同一个恒等常量。结果为空 / 接口报错 → 正文空串 → 不成段（上游同）。
function attachCycleTableText(state) {
  if (!state.cycleTableResult || typeof state.cycleTableResult !== 'object') return state;
  const text = buildMundaneCycleText(state.cycleTableResult, state.cycleTableRequest || {});
  const next = { ...state };
  delete next.cycleTableResult;
  delete next.cycleTableRequest;
  if (text) {
    next.cycleTableText = text;
    next.cycleTableKey = HEADLESS_PAT_KEY;
  }
  return next;
}

export function runMundaneCards(payload) {
  const source = payload && typeof payload === 'object' ? payload : {};
  if (source.action === 'settings') {
    return { tool: 'mundane_cards', data: { ok: true, ...settingsCheck(source.settings) } };
  }
  if (source.action === 'cycles_request') {
    return { tool: 'mundane_cards', data: cyclesRequest(source) };
  }
  if (source.action === 'region') {
    return { tool: 'mundane_cards', data: resolveRegion(source) };
  }
  if (source.action === 'analysis') {
    // 上游 buildAiSnapshot 的头行 / 判词 / 分析段 / 右栏卡（vendored 逐字抽出件）：chart = 该盘型自己的盘，extra 与 state
    // 由 Python 原样给（不改键、不补默认值）。整函数级失败上报，不静默成空段。
    const chart = source.chart && typeof source.chart === 'object' ? source.chart : null;
    if (!chart) {
      return { tool: 'mundane_cards', data: { ok: false, error: { code: 'missing_chart', message: '缺少盘面（chart）。' } } };
    }
    const extra = source.extra && typeof source.extra === 'object' ? source.extra : {};
    const state = { ...(source.state && typeof source.state === 'object' ? source.state : {}) };
    if (Array.isArray(state.patData)) {
      state.patKey = HEADLESS_PAT_KEY;
    }
    try {
      const parts = buildMundaneAiSnapshotParts(chart, extra, state);
      return { tool: 'mundane_cards', data: { ok: true, ...parts, cards: (parts.cardSecs || []).map(splitCard) } };
    } catch (error) {
      return { tool: 'mundane_cards', data: { ok: false, error: { code: 'analysis_builder_failed', message: `${(error && error.message) || error}` } } };
    }
  }
  const jobs = Array.isArray(source.jobs) ? source.jobs : [];
  const results = jobs.map((job, index) => {
    const j = job && typeof job === 'object' ? job : {};
    const id = j.id !== undefined && j.id !== null ? `${j.id}` : `${index}`;
    const chart = j.chart && typeof j.chart === 'object' ? j.chart : null;
    if (!chart) {
      return { id, ok: false, cards: [], error: { code: 'missing_chart', message: '缺少盘面（chart）。' } };
    }
    let extra = j.extra && typeof j.extra === 'object' ? j.extra : {};
    // 问类只认引擎自带词表（MUNDANE_HORARY_KINDS）：上游 UI 下拉给不出词表外的值，builder 对它的兜底是
    // 「非 war/weather 即 price」（:462-465），而同一份快照的 [世运问判] 由 tools/mundaneHorary.js 按
    // 「词表外即 war」出——两段问类必须一致，故这里与那边同口径。
    if (extra.mundaneType === 'mundanehorary' && !MUNDANE_HORARY_KINDS.some((k) => k.key === extra.mhKind)) {
      extra = { ...extra, mhKind: 'war' };
    }
    let state = { ...(j.state && typeof j.state === 'object' ? j.state : {}) };
    if (Array.isArray(state.patData)) {
      state.patKey = HEADLESS_PAT_KEY;
    }
    try {
      state = attachCycleTableText(state);
      const blocks = buildMundaneCardSections(chart, extra, state, null);
      return { id, ok: true, cards: (Array.isArray(blocks) ? blocks : []).map(splitCard) };
    } catch (error) {
      // builder 每张卡自带 try/catch（上游「异常降级为不产段」）；能冒到这里的是整函数级失败，必须上报。
      return {
        id,
        ok: false,
        cards: [],
        error: { code: 'card_builder_failed', message: `${(error && error.message) || error}` },
      };
    }
  });
  return { tool: 'mundane_cards', data: { ok: results.every((r) => r.ok), jobs: results, meta: settingsCheck(source.settings).meta } };
}

export default runMundaneCards;
