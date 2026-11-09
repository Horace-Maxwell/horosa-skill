// A browser-shaped global for the 星阙 app's chart code (D3 writes into an <svg> found by id).
// linkedom instead of jsdom: it bundles into the single dist file, and renders were checked pixel-identical to jsdom.
// Everything here must be deterministic — the same engine data has to give the same SVG bytes on every OS.
import { parseHTML } from 'linkedom';

const { window, document } = parseHTML('<!doctype html><html><head></head><body></body></html>');

function memoryStorage() {
  const map = new Map();
  return {
    getItem: (k) => (map.has(k) ? map.get(k) : null),
    setItem: (k, v) => map.set(k, String(v)),
    removeItem: (k) => map.delete(k),
    clear: () => map.clear(),
    key: (i) => [...map.keys()][i] ?? null,
    get length() { return map.size; },
  };
}

// Fixed, OS-neutral navigator: the app nudges text by 2px when it detects a Mac.
const navigatorStub = { userAgent: 'Mozilla/5.0 (X11; Linux x86_64) HorosaSkill/headless', platform: 'Linux x86_64', language: 'zh-CN', languages: ['zh-CN'] };
const locationStub = new URL('http://localhost/');

const globals = {
  window,
  document,
  location: locationStub,
  localStorage: memoryStorage(),
  sessionStorage: memoryStorage(),
  requestAnimationFrame: (fn) => setTimeout(fn, 0),
  cancelAnimationFrame: (id) => clearTimeout(id),
  getComputedStyle: () => ({ getPropertyValue: () => '' }),
  ResizeObserver: class { observe() {} unobserve() {} disconnect() {} },
  matchMedia: () => ({ matches: false, addListener() {}, removeListener() {}, addEventListener() {}, removeEventListener() {} }),
  HTMLElement: window.HTMLElement,
  SVGElement: window.SVGElement,
  Element: window.Element,
  Node: window.Node,
};
for (const [key, value] of Object.entries(globals)) {
  Object.defineProperty(globalThis, key, { value, configurable: true, writable: true });
  if (key !== 'window' && key !== 'document') {
    try { window[key] = value; } catch { /* read-only on linkedom's window: the global is enough */ }
  }
}
Object.defineProperty(globalThis, 'navigator', { value: navigatorStub, configurable: true, writable: true });

// Seeded Math.random: the app names elements with random ids; reseeding per render keeps output byte-stable.
let seed = 1;
Math.random = () => {
  seed = (Math.imul(seed, 1103515245) + 12345) >>> 0;
  return (seed >>> 1) / 0x80000000;
};
export function reseed(value = 1) {
  seed = value >>> 0;
}

let counter = 0;
/** A fresh <svg id> of the given size in the document; clientWidth/Height are what the app's charts size themselves from. */
export function mountSvg(width, height) {
  counter += 1;
  const id = `horosa-chart-${counter}`;
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('id', id);
  svg.setAttribute('width', String(width));
  svg.setAttribute('height', String(height));
  Object.defineProperty(svg, 'clientWidth', { value: width, configurable: true });
  Object.defineProperty(svg, 'clientHeight', { value: height, configurable: true });
  document.body.appendChild(svg);
  return { id, svg };
}

/** A tooltip host div (the charts attach hover tooltips to it; never shown in a report). */
export function mountTooltip() {
  counter += 1;
  const id = `horosa-tip-${counter}`;
  const div = document.createElement('div');
  div.setAttribute('id', id);
  document.body.appendChild(div);
  return { id, div };
}

export function unmount(...nodes) {
  for (const node of nodes) {
    if (node && node.parentNode) node.parentNode.removeChild(node);
  }
}

export { window, document };
