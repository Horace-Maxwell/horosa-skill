// A board whose look lives in its component stylesheet (`.scope { --x: … }` + `.scope .cls { fill: … }`), not in inline
// attributes. svglib reads neither CSS classes nor custom properties, so we do what the browser does in the app's light
// theme, for that one stylesheet only:
//   tokens       — `.scope { --x }` then `:root[data-horosa-appearance='light'] .scope { --x }` (light wins), substituted
//                  into var(--x, …) before the global theme resolution
//   class rules  — `.scope <sel> { fill | stroke | … }` (base, then light) set as presentation attributes on the matched
//                  svg elements (a CSS rule beats a presentation attribute, so overwriting is the browser's order too)
// Only presentation properties are applied; layout (width, display, background of HTML boxes) has no meaning in a figure.
import { DOMParser } from 'linkedom';

const PRESENTATION = new Set(['fill', 'stroke', 'stroke-width', 'opacity', 'fill-opacity', 'stroke-opacity', 'stroke-dasharray',
  'font-size', 'font-weight', 'font-family']);
const LIGHT = /^(?::root|html)\[data-horosa-appearance=['"]?light['"]?\]\s+/;

function strip(text) {
  return text.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:])\/\/[^\n]*/g, '$1');
}

/** Flat rules of a component stylesheet: [{ selector, light, decls: [[prop, value]] }] (nested / @ blocks are skipped). */
export function parseRules(cssText) {
  const out = [];
  const re = /([^{}]+)\{([^{}]*)\}/g;
  for (const m of strip(cssText).matchAll(re)) {
    const decls = m[2].split(';').map((d) => d.split(':')).filter((p) => p.length >= 2)
      .map(([k, ...v]) => [k.trim().toLowerCase(), v.join(':').replace(/\s*!important\s*$/, '').trim()]);
    for (const raw of m[1].split(',')) {
      const sel = raw.trim().replace(/\s+/g, ' ');
      if (!sel || sel.startsWith('@')) continue;
      out.push({ selector: sel.replace(LIGHT, ''), light: LIGHT.test(sel), decls });
    }
  }
  return out;
}

/** svg markup drawn inside `.scope` → the same svg with the stylesheet's light-theme tokens and class rules inlined. */
export function applyComponentCss(svgMarkup, cssText, scope) {
  const head = `.${scope}`;
  const rules = parseRules(cssText).filter((r) => r.selector === head || r.selector.startsWith(`${head} `));
  const ordered = [...rules.filter((r) => !r.light), ...rules.filter((r) => r.light)];
  const tokens = {};
  ordered.filter((r) => r.selector === head).forEach((r) => r.decls.forEach(([k, v]) => { if (k.startsWith('--')) tokens[k] = v; }));
  const doc = new DOMParser().parseFromString(svgMarkup, 'image/svg+xml');
  const root = doc.documentElement;
  for (const rule of ordered) {
    const rest = rule.selector.slice(head.length).trim();
    const props = rule.decls.filter(([k]) => PRESENTATION.has(k));
    if (!rest || !props.length) continue;
    const targets = rest === 'svg' ? [root] : [...root.querySelectorAll(rest.replace(/^svg\s+/, ''))];
    targets.forEach((el) => props.forEach(([k, v]) => el.setAttribute(k, v)));
  }
  let svg = root.toString();
  for (let round = 0; round < 4; round += 1) {
    const next = svg.replace(/var\(\s*(--[\w-]+)\s*(?:,\s*((?:[^()]|\([^()]*\))*))?\)/g, (m, name) => (tokens[name] !== undefined ? tokens[name] : m));
    if (next === svg) break;
    svg = next;
  }
  return svg;
}
