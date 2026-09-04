// Guard: `src/tools/*.js` must not carry hand-copied vendor constant tables.
//
// v0.35.0 fixed a wrong 六亲 cell in vendored LRConst.ZiLiuQin and added a golden on the vendor
// export — while tools/liureng.js kept its own 24 hand-copied LRConst tables (ZI_LIU_QIN among them,
// with the same wrong cell), so the consumer stayed wrong and every vendor-level golden was
// structurally blind to it. A table copied by hand is a second source of truth that drifts silently.
//
// Rule: every top-level `const NAME = [...] | {...}` literal in a tool file that (a) matches an export
// of a vendor module the file imports by normalised name (ZI_LIU_QIN ~ ZiLiuQin), or (b) deep-equals
// any such export, is a hand copy → fail. Fix = destructure the vendor export
// (`const { ZiLiuQin: ZI_LIU_QIN } = LRConst`). Tables with no vendor counterpart (SIGN_TO_YUE) pass.
// A built-in negative control proves the analyzer still detects a planted copy. Exit non-zero on any
// finding so `npm test` / CI fails loudly. Stdlib-only.
import { readdirSync, readFileSync } from 'node:fs';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { dirname, join, resolve } from 'node:path';

const HERE = dirname(fileURLToPath(import.meta.url));
const TOOLS_DIR = join(HERE, '..', 'src', 'tools');
const MIN_SIZE = 4; // arrays shorter / objects smaller than this are not "tables"

const IMPORT_RE = /^import\s+(?:[^'"]+?\s+from\s+)?['"](\.\.\/vendor\/[^'"]+)['"]/gm;
const CONST_RE = /^(?:export\s+)?const\s+([A-Za-z_$][\w$]*)\s*=\s*(?=[[{])/gm;

function matchBracket(src, start) {
  const open = src[start];
  const close = open === '[' ? ']' : '}';
  let depth = 0;
  let i = start;
  while (i < src.length) {
    const ch = src[i];
    if (ch === '/' && src[i + 1] === '/') {
      i = src.indexOf('\n', i);
      if (i < 0) return -1;
      continue;
    }
    if (ch === '/' && src[i + 1] === '*') {
      i = src.indexOf('*/', i + 2);
      if (i < 0) return -1;
      i += 2;
      continue;
    }
    if (ch === "'" || ch === '"' || ch === '`') {
      let j = i + 1;
      while (j < src.length && src[j] !== ch) {
        if (src[j] === '\\') j += 1;
        j += 1;
      }
      i = j + 1;
      continue;
    }
    if (ch === '[' || ch === '{') depth += 1;
    if (ch === ']' || ch === '}') {
      depth -= 1;
      if (depth === 0) return ch === close ? i : -1;
    }
    i += 1;
  }
  return -1;
}

function sizeOf(value) {
  if (Array.isArray(value)) return value.length;
  if (value && typeof value === 'object') return Object.keys(value).length;
  return 0;
}

function canonical(value) {
  if (Array.isArray(value)) return `[${value.map(canonical).join(',')}]`;
  if (value && typeof value === 'object') {
    return `{${Object.keys(value).sort().map((k) => `${JSON.stringify(k)}:${canonical(value[k])}`).join(',')}}`;
  }
  return JSON.stringify(value);
}

const norm = (name) => name.replace(/[_$]/g, '').toLowerCase();

export function topLevelLiterals(src) {
  const out = [];
  let m;
  CONST_RE.lastIndex = 0;
  while ((m = CONST_RE.exec(src))) {
    const start = m.index + m[0].length;
    const end = matchBracket(src, start);
    if (end < 0) continue;
    let value;
    try {
      value = new Function(`"use strict"; return (${src.slice(start, end + 1)});`)();
    } catch {
      continue; // references identifiers / calls → not a pure literal copy
    }
    if (sizeOf(value) < MIN_SIZE) continue;
    out.push({ name: m[1], value, line: src.slice(0, m.index).split('\n').length });
  }
  return out;
}

export async function vendorExports(src, baseDir) {
  const tables = [];
  const seen = new Set();
  let m;
  IMPORT_RE.lastIndex = 0;
  while ((m = IMPORT_RE.exec(src))) {
    const rel = m[1];
    if (seen.has(rel)) continue;
    seen.add(rel);
    let mod;
    try {
      mod = await import(pathToFileURL(resolve(baseDir, rel)).href);
    } catch {
      continue; // a vendor module that cannot load here is loadcheck's problem, not this guard's
    }
    for (const [name, value] of Object.entries(mod)) {
      if (typeof value === 'function' || sizeOf(value) < MIN_SIZE) continue;
      tables.push({ module: rel, name, norm: norm(name), canonical: canonical(value) });
    }
  }
  return tables;
}

export async function analyze(src, baseDir) {
  const findings = [];
  const literals = topLevelLiterals(src);
  if (!literals.length) return findings;
  const exportsList = await vendorExports(src, baseDir);
  for (const lit of literals) {
    const litCanon = canonical(lit.value);
    const litNorm = norm(lit.name);
    const byName = exportsList.find((e) => e.norm === litNorm);
    const byValue = exportsList.find((e) => e.canonical === litCanon);
    const hit = byName || byValue;
    if (!hit) continue;
    const state = hit.canonical === litCanon ? 'identical copy' : 'DRIFTED copy';
    findings.push(`line ${lit.line}: const ${lit.name} is a ${state} of ${hit.module} → ${hit.name}`);
  }
  return findings;
}

async function main() {
  let failures = 0;

  // Negative control: a planted hand copy must be detected, or the guard is decorative.
  const planted = [
    "import * as LRConst from '../vendor/liureng/LRConst.js';",
    "const ZI_LIST = ['子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥'];",
    "const RENAMED_TIANJIANG = ['贵人', '螣蛇', '朱雀', '六合', '勾陈', '青龙', '天空', '白虎', '太常', '玄武', '太阴', '天后'];",
    "const DRIFT = { '子': '未', '未': '子', '丑': '午', '午': '丑', '寅': '巳', '巳': '寅', '卯': '辰', '辰': '卯', '申': '亥', '亥': '申', '酉': '戌', '戌': '子' };",
    'const { ZiXing: ZI_XING } = LRConst;',
  ].join('\n');
  const control = await analyze(planted, TOOLS_DIR);
  const wantNames = ['ZI_LIST', 'RENAMED_TIANJIANG'];
  if (!wantNames.every((n) => control.some((f) => f.includes(`const ${n} `)))) {
    console.error(`handcopy: negative control FAILED — analyzer missed a planted copy: ${JSON.stringify(control)}`);
    failures += 1;
  }
  if (control.some((f) => f.includes('const ZI_XING') || f.includes('DRIFT'))) {
    console.error(`handcopy: negative control FAILED — destructuring or a non-matching table was flagged: ${JSON.stringify(control)}`);
    failures += 1;
  }

  const files = readdirSync(TOOLS_DIR).filter((f) => f.endsWith('.js')).sort();
  let scanned = 0;
  for (const file of files) {
    const src = readFileSync(join(TOOLS_DIR, file), 'utf8');
    const findings = await analyze(src, TOOLS_DIR);
    scanned += 1;
    for (const f of findings) {
      console.error(`handcopy: ${file}: ${f}`);
      failures += 1;
    }
  }
  if (failures) {
    console.error(`handcopy: FAIL — ${failures} finding(s). Destructure the vendor export instead of copying the table.`);
    process.exit(1);
  }
  console.log(`handcopy: OK — ${scanned} tool file(s) carry no hand-copied vendor tables (negative control passed)`);
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch((error) => {
    console.error(`handcopy: crashed: ${error && error.stack ? error.stack : error}`);
    process.exit(1);
  });
}
