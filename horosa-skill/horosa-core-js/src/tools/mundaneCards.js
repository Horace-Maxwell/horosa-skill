import { buildMundaneCardSections, MUNDANE_ORB_SCHEME_CN, MUNDANE_INGRESS_RULE_CN } from '../vendor/mundane/MundaneMain.js';
import { MUNDANE_HORARY_KINDS } from '../vendor/mundane/mundaneHorary.js';
import { MUNDANE_RULESETS, rulesetConfig } from '../vendor/mundane/ruleset.js';
import { SIGN_ORDER } from '../vendor/divination/data/signs.js';

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

// 世运口径（上游页面设置 MUNDANE_PAGE_SETTINGS，MundaneMain.js:519-526）：规则集四派 + 两个页面级覆盖 + 吠陀世运三键。
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

export function runMundaneCards(payload) {
  const source = payload && typeof payload === 'object' ? payload : {};
  if (source.action === 'settings') {
    return { tool: 'mundane_cards', data: { ok: true, ...settingsCheck(source.settings) } };
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
    const state = { ...(j.state && typeof j.state === 'object' ? j.state : {}) };
    if (Array.isArray(state.patData)) {
      state.patKey = HEADLESS_PAT_KEY;
    }
    try {
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
