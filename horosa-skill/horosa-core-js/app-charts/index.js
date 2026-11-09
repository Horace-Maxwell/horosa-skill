// Entry of the app-chart bundle (dist/app-charts.cjs). `./dom.js` must be imported first: the app's modules read
// `window` / `navigator` while they load.
import { reseed } from './dom.js';
import { renderBiWheel, renderNatalWheel } from './adapters/astro.js';
import { renderZiwei } from './adapters/ziwei.js';
import { renderGuolao } from './adapters/guolao.js';
import { renderTaiyi } from './adapters/taiyi.js';
import { renderLiureng } from './adapters/liureng.js';
import { renderLiuyao } from './adapters/liuyao.js';
import { renderUranianDial } from './adapters/uranian.js';
import { renderJinkou } from './adapters/jinkou.js';
import { renderSuzhan } from './adapters/suzhan.js';
import { renderBabylon } from './adapters/babylon.js';
import { renderFeigong } from './adapters/feigong.js';
import { renderMichon } from './adapters/michon.js';
import { renderQizhengKin } from './adapters/qizhengkin.js';
import { makeKinZiwei } from './adapters/kinziwei.js';
import THEME from 'horosa-theme-tokens';
import SCOPES from 'horosa-theme-scopes';

const VAR = /var\(\s*(--[\w-]+)\s*(?:,\s*((?:[^()]|\([^()]*\))*))?\)/g;

/** Resolve `var(--x, fallback)` the way the app's light theme does (tokens from its own stylesheets, see theme.mjs). */
export function resolveThemeVars(svg, scope) {
  // a page scope (theme.mjs: `.horosa-workspace-shell .<scope>`) overrides the global tokens for that page's boards
  const tokens = scope && SCOPES[scope] ? { ...THEME, ...SCOPES[scope] } : THEME;
  let out = svg;
  for (let round = 0; round < 6; round += 1) {
    const next = out.replace(VAR, (_m, name, fallback) => (tokens[name] !== undefined ? tokens[name] : (fallback || '').trim()));
    if (next === out) break;
    out = next;
  }
  // currentColor：svglib 不认；取图里第一个（已解析的）color 属性——app 的图都是在根组上给一次 color、子元素 stroke="currentColor"。
  if (out.includes('currentColor')) {
    const color = (out.match(/\scolor="(?!currentColor)([^"]+)"/) || [])[1] || THEME['--horosa-chart-stroke'] || '#3b3b3b';
    out = out.replace(/currentColor/g, color);
  }
  return out;
}

export const RENDERERS = {
  natal_wheel: renderNatalWheel,
  bi_wheel: renderBiWheel,
  ziwei: renderZiwei,
  guolao: renderGuolao,
  taiyi: renderTaiyi,
  liureng: renderLiureng,
  liuyao: renderLiuyao,
  uranian_dial: renderUranianDial,
  jinkou: renderJinkou,
  suzhan: renderSuzhan,
  babylon: renderBabylon,
  feigong: renderFeigong,
  michon: renderMichon,
  qizhengkin: renderQizhengKin,
  cetian: makeKinZiwei('cetian'),
  xianqin: makeKinZiwei('xianqin'),
};

/**
 * Render a batch of figures. Each request is { kind, data, options }; each answer is { ok, svg, width, height } or
 * { ok: false, error }. One bad figure never sinks the others — the Python side falls back to its own drawing for it.
 */
export function renderCharts(requests) {
  return (Array.isArray(requests) ? requests : []).map((request) => {
    const render = RENDERERS[request && request.kind];
    if (!render) {
      return { ok: false, error: `unknown chart kind: ${request && request.kind}` };
    }
    reseed(1);
    try {
      const drawn = render(request.data, request.options || {});
      const { themeScope, ...rest } = drawn;
      return { ok: true, ...rest, svg: resolveThemeVars(drawn.svg, themeScope) };
    } catch (error) {
      return { ok: false, error: error instanceof Error ? error.message : String(error) };
    }
  });
}

export function listKinds() {
  return Object.keys(RENDERERS);
}
