// Entry of the app-chart bundle (dist/app-charts.cjs). `./dom.js` must be imported first: the app's modules read
// `window` / `navigator` while they load.
import { reseed } from './dom.js';
import { renderNatalWheel } from './adapters/astro.js';
import { renderZiwei } from './adapters/ziwei.js';

export const RENDERERS = {
  natal_wheel: renderNatalWheel,
  ziwei: renderZiwei,
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
      return { ok: true, ...render(request.data, request.options || {}) };
    } catch (error) {
      return { ok: false, error: error instanceof Error ? error.message : String(error) };
    }
  });
}

export function listKinds() {
  return Object.keys(RENDERERS);
}
