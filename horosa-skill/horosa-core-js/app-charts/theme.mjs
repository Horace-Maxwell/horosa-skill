// Build-time: the 星阙 app's light-theme design tokens, read from its own stylesheets (layouts/app/*.less).
//
// The app's chart code paints with `var(--horosa-…, fallback)`. The fallback is NOT reliably the light value (the
// 六壬 board's background falls back to the dark #090b0e), so a report must resolve each variable the way the browser
// does in the app's light theme: the root carries data-horosa-appearance="light" and no light-flavor attribute
// (paper is the default). Declarations on `:root` / `html` apply; attribute-qualified root selectors that match light
// mode win over them (higher specificity); `body` ones win over both (nearer ancestor). Descendant selectors
// (`:root .ant-dropdown`) never reach a free-standing chart, so they are ignored.
import fs from 'node:fs';
import path from 'node:path';

function stripComments(text) {
  let out = '';
  let i = 0;
  let quote = null;
  let depth = 0; // parentheses — `//` inside url(...) is not a comment
  while (i < text.length) {
    const c = text[i];
    const n = text[i + 1];
    if (quote) {
      out += c;
      if (c === '\\') { out += n ?? ''; i += 2; continue; }
      if (c === quote) quote = null;
      i += 1;
      continue;
    }
    if (c === '"' || c === "'") { quote = c; out += c; i += 1; continue; }
    if (c === '/' && n === '*') { const end = text.indexOf('*/', i + 2); i = end < 0 ? text.length : end + 2; continue; }
    if (c === '/' && n === '/' && depth === 0) { const end = text.indexOf('\n', i); i = end < 0 ? text.length : end; continue; }
    if (c === '(') depth += 1;
    if (c === ')') depth = Math.max(0, depth - 1);
    out += c;
    i += 1;
  }
  return out;
}

const norm = (sel) => sel.replace(/\s+/g, ' ').replace(/["']/g, '').replace(/\s*([[\]=():])\s*/g, '$1').trim();

// selector (normalised) → rank; higher rank wins regardless of order, equal rank → later wins
const LIGHT_ROOT_RANKS = new Map([
  [':root', 1],
  ['html', 1],
  [':root[data-horosa-appearance=light]', 2],
  [':root:not([data-horosa-appearance=dark])', 2],
  ['html[data-horosa-appearance=light]', 2],
  ['html:not([data-horosa-appearance=dark])', 2],
  ['body', 3],
  ['body[data-horosa-appearance=light]', 4],
  ['body:not([data-horosa-appearance=dark])', 4],
]);

function expand(parents, own) {
  const children = own.split(',').map((s) => s.trim()).filter(Boolean);
  if (!parents.length) return children;
  const out = [];
  for (const parent of parents) {
    for (const child of children) {
      out.push(child.includes('&') ? child.replace(/&/g, parent) : `${parent} ${child}`);
    }
  }
  return out;
}

/** { tokens: { '--horosa-x': 'value' }, files: { relPath: text } } for the app checkout at `appSrc`. */
export function lightThemeTokens(appSrc) {
  const dir = path.join(appSrc, 'layouts', 'app');
  const files = fs.readdirSync(dir).filter((f) => f.endsWith('.less')).sort();
  const best = new Map(); // name → { rank, order, value }
  const inputs = {};
  let order = 0;
  for (const file of files) {
    const raw = fs.readFileSync(path.join(dir, file), 'utf8');
    inputs[path.posix.join('layouts', 'app', file)] = raw;
    const text = stripComments(raw);
    const stack = []; // expanded selector lists, `:global` treated as transparent
    let buf = '';
    for (const ch of text) {
      if (ch === '{') {
        const own = buf.trim();
        buf = '';
        const parent = stack.length ? stack[stack.length - 1] : [];
        stack.push(own === ':global' || own.startsWith('@') ? parent : expand(parent, own));
      } else if (ch === '}') {
        buf = '';
        stack.pop();
      } else if (ch === ';') {
        const decl = buf.trim();
        buf = '';
        const m = decl.match(/^(--[\w-]+)\s*:\s*([\s\S]+)$/);
        if (!m || !stack.length) continue;
        order += 1;
        let rank = 0;
        for (const sel of stack[stack.length - 1]) rank = Math.max(rank, LIGHT_ROOT_RANKS.get(norm(sel)) || 0);
        if (!rank) continue;
        const value = m[2].replace(/\s*!important\s*$/, '').trim();
        const prev = best.get(m[1]);
        if (!prev || rank > prev.rank || (rank === prev.rank && order > prev.order)) best.set(m[1], { rank, order, value });
      } else {
        buf += ch;
      }
    }
  }
  const tokens = {};
  for (const [name, { value }] of [...best.entries()].sort(([a], [b]) => a.localeCompare(b))) tokens[name] = value;
  return { tokens, inputs };
}
