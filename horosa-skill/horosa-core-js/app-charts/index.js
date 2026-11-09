// Entry of the app-chart bundle (dist/app-charts.cjs). `./dom.js` must be imported first: the app's modules read
// `window` / `navigator` while they load.
import { reseed } from './dom.js';
import { renderBiWheel, renderNatalWheel } from './adapters/astro.js';
import { renderZiwei } from './adapters/ziwei.js';
import { renderGuolao } from './adapters/guolao.js';
import { renderTaiyi } from './adapters/taiyi.js';
import THEME from 'horosa-theme-tokens';

const VAR = /var\(\s*(--[\w-]+)\s*(?:,\s*((?:[^()]|\([^()]*\))*))?\)/g;

/** Resolve `var(--x, fallback)` the way the app's light theme does (tokens from its own stylesheets, see theme.mjs). */
export function resolveThemeVars(svg) {
  let out = svg;
  for (let round = 0; round < 6; round += 1) {
    const next = out.replace(VAR, (_m, name, fallback) => (THEME[name] !== undefined ? THEME[name] : (fallback || '').trim()));
    if (next === out) break;
    out = next;
  }
  return out;
}

export const RENDERERS = {
  natal_wheel: renderNatalWheel,
  bi_wheel: renderBiWheel,
  ziwei: renderZiwei,
  guolao: renderGuolao,
  taiyi: renderTaiyi,
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
      return { ok: true, ...drawn, svg: resolveThemeVars(drawn.svg) };
    } catch (error) {
      return { ok: false, error: error instanceof Error ? error.message : String(error) };
    }
  });
}

export function listKinds() {
  return Object.keys(RENDERERS);
}
