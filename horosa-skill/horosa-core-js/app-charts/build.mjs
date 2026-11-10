#!/usr/bin/env node
// Build dist/app-charts.cjs: the 星阙 app's own chart-drawing code (from a Horosa-Public checkout) + the adapters in
// this folder + linkedom + d3, as ONE self-contained CommonJS file. The report renderer runs it with the runtime's
// Node; nothing is fetched at run time.
//
//   node app-charts/build.mjs --source-root <Horosa-Public checkout> [--check]
//
// Determinism: inputs are staged under fixed names (stage/app, stage/core, stage/node_modules) and esbuild keeps those
// symlinked paths, so the bundle bytes do not depend on where either checkout lives. `--check` rebuilds in memory and
// exits 1 when dist/ or the manifest differs (that is how re-vendor proves the committed bundle matches the pinned tree).
//
// Bare npm imports made BY APP FILES resolve for real only for the drawing stack (d3 family, moment); everything else
// they import (antd, react, dva, request helpers…) is a no-op stub — it is UI / network code that the draw path never
// calls. The adapters' tests prove that: an un-stubbed jsdom build renders pixel-identical SVG (scripts: see AGENTS).
import { createHash } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import process from 'node:process';
import { fileURLToPath } from 'node:url';

import * as esbuild from 'esbuild';

import { lightThemeTokens } from './theme.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const CORE = path.resolve(HERE, '..');
const PKG = path.resolve(CORE, '..');
const DIST = path.join(CORE, 'dist');
const BUNDLE = path.join(DIST, 'app-charts.cjs');
const NOTICE = path.join(DIST, 'app-charts.LICENSES.txt');
const MANIFEST = path.join(PKG, 'contracts', 'app_charts_bundle.json');
const APP_SRC_REL = path.join('Horosa-Web', 'astrostudyui', 'src');
// App files that are never on a board's draw path — page UI (the time / place picker panel and the map + city databases
// behind it, saved-case drawers, the page's time-draft plumbing) and SIBLING pages a page module imports for its other
// tabs (KinAstroMain → 参评 / 河洛 / 正传 / 一掌经 pages with their verse databases, the 演禽 side panels, 铁板 framework).
// A board method that lives in such a page module (FeiGongMain.renderCenter, KinAstroMain.renderZiWeiCopiedCenter) would
// otherwise drag 4–5 MB into the bundle. Same no-op stub as the npm UI packages; a new entry must leave every committed
// kind's SVG byte-identical (checked when added; tests/test_app_charts.py guards size and renders every kind).
const APP_UI_ONLY = new RegExp([
  '^components/amap/', '^components/comp/SpaceTimePanel$', '^utils/kentangCaseSave$', '^utils/divinationTimeDraft$',
  '^data/cit(ies|y)[A-Za-z]*\\.json$',
  '^components/shusuan/(CanPingMain|HeLuoMain|ZhengChuanMain)$', '^components/yizhangjing/YiZhangJingMain$',
  '^components/yanqin/(YanQinBranchPanel|YanQinControls)$', '^utils/tiebanFrameworkLocal$',
  '^components/tarot/CardDetailDrawer$', // 塔罗单牌详情抽屉（点牌才开）：带进 ~140 KB 牌义表，牌阵图不用
].join('|'));
const CSS_MODULES = /components\/sanshi\/SanShiUnitedMain\.less$/;
// react-dom: only its server renderer is real (SSR'd boards). The client renderer is a stub — a board reaches it only for
// hover popups (GuoLaoMoiraWheel's createPortal tooltip, never drawn on paper), and loading it starts React's scheduler,
// whose MessageChannel keeps any process that loads the bundle alive forever (the build's own kinds probe hung on it).
const REAL_FOR_APP = /^(d3(-[a-z-]+)?|internmap|delaunator|robust-predicates|moment|react|react-dom\/server|scheduler|object-assign|lunar-javascript)(\/|$)/;

function stubModule(pkg, importer) {
  const source = fs.readFileSync(importer, 'utf8');
  const names = new Set();
  const esc = pkg.replace(/[.*+?^${}()|[\]\\/]/g, '\\$&');
  const re = new RegExp(`(?:import|export)\\s+(?:[\\w$]+\\s*,\\s*)?\\{([^}]*)\\}\\s*from\\s*['"]${esc}['"]`, 'g');
  for (const m of source.matchAll(re)) {
    for (const part of m[1].split(',')) {
      const name = part.trim().split(/\s+as\s+/)[0].trim();
      if (/^[A-Za-z_$][\w$]*$/.test(name) && name !== 'default') names.add(name);
    }
  }
  const proxy = 'const h={get:(t,k)=>k==="__esModule"?true:(k==="default"?p:(k===Symbol.toPrimitive?()=>"":p))};'
    + 'const p=new Proxy(function(){return p},Object.assign(h,{apply:()=>p,construct:()=>p}));';
  return `${proxy}export default p;${[...names].sort().map((n) => `export const ${n}=p;`).join('')}`;
}

function arg(name) {
  const i = process.argv.indexOf(name);
  return i >= 0 ? process.argv[i + 1] : undefined;
}

const sourceRoot = arg('--source-root') || process.env.HOROSA_SOURCE_ROOT;
const check = process.argv.includes('--check');
if (!sourceRoot || !fs.existsSync(path.join(sourceRoot, APP_SRC_REL))) {
  console.error(`app-charts: --source-root (or HOROSA_SOURCE_ROOT) must be a Horosa-Public checkout containing ${APP_SRC_REL}`);
  process.exit(2);
}

const stage = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), 'horosa-app-charts-')));
fs.symlinkSync(path.resolve(sourceRoot, APP_SRC_REL), path.join(stage, 'app'), 'dir');
fs.symlinkSync(HERE, path.join(stage, 'core'), 'dir');
fs.symlinkSync(path.join(CORE, 'node_modules'), path.join(stage, 'node_modules'), 'dir');

const appPrefix = `${path.join(stage, 'app')}${path.sep}`;
const theme = lightThemeTokens(path.resolve(sourceRoot, APP_SRC_REL));
const plugin = {
  name: 'horosa-app',
  setup(build) {
    // `@horosa-app/x.less?text` = the stylesheet's text for an adapter (css.js / a board that reads its own rules)
    build.onResolve({ filter: /^@horosa-app\/.*\.less\?text$/ }, (a) => ({ path: path.join(stage, 'app', a.path.slice('@horosa-app/'.length, -'?text'.length)), namespace: 'lesstext' }));
    build.onLoad({ filter: /.*/, namespace: 'lesstext' }, (a) => ({ contents: fs.readFileSync(a.path, 'utf8'), loader: 'text' }));
    build.onResolve({ filter: /^@horosa-app\// }, (a) => ({ path: path.join(stage, 'app', a.path.slice('@horosa-app/'.length)) }));
    // CSS-module stylesheets (`import styles from './X.less'` then styles.cls): in the app the bundler hashes the class names;
    // here they resolve to the plain rule names, so the rendered markup says which rule each element wears.
    build.onLoad({ filter: CSS_MODULES }, () => ({ contents: 'export default new Proxy({}, { get: (t, k) => (typeof k === "string" ? k : undefined) });', loader: 'js' }));
    build.onResolve({ filter: /^[^./]/ }, (a) => {
      if (!a.importer.startsWith(appPrefix) || REAL_FOR_APP.test(a.path)) return undefined;
      // one stub module per (package, importer): it exports exactly the names that file imports, so module-level code
      // such as `XQSelect.Option = Select.Option` sees a callable no-op instead of undefined (a CJS Proxy has no own keys
      // for esbuild's named-import interop to copy).
      return { path: `${a.path}::${path.relative(stage, a.importer)}`, namespace: 'stub', pluginData: { pkg: a.path, importer: a.importer } };
    });
    build.onResolve({ filter: /^\.\.?\// }, (a) => {
      if (!a.importer.startsWith(appPrefix)) return undefined;
      const rel = path.relative(path.join(stage, 'app'), path.resolve(path.dirname(a.importer), a.path)).split(path.sep).join('/');
      if (!APP_UI_ONLY.test(rel.replace(/\.js$/, ''))) return undefined;
      return { path: `${a.path}::${path.relative(stage, a.importer)}`, namespace: 'stub', pluginData: { pkg: a.path, importer: a.importer } };
    });
    build.onLoad({ filter: /.*/, namespace: 'stub' }, (a) => ({ contents: stubModule(a.pluginData.pkg, a.pluginData.importer), loader: 'js' }));
    // the app's light-theme tokens (theme.mjs), baked in at build time
    build.onResolve({ filter: /^horosa-theme-tokens$/ }, () => ({ path: 'horosa-theme-tokens', namespace: 'theme' }));
    build.onLoad({ filter: /^horosa-theme-tokens$/, namespace: 'theme' }, () => ({ contents: JSON.stringify(theme.tokens), loader: 'json' }));
    build.onResolve({ filter: /^horosa-theme-scopes$/ }, () => ({ path: 'horosa-theme-scopes', namespace: 'theme' }));
    build.onLoad({ filter: /^horosa-theme-scopes$/, namespace: 'theme' }, () => ({ contents: JSON.stringify(theme.scopes), loader: 'json' }));
  },
};

let result;
try {
  result = await esbuild.build({
    absWorkingDir: stage,
    entryPoints: ['core/index.js'],
    bundle: true,
    platform: 'node',
    format: 'cjs',
    target: 'node20',
    minify: !process.env.HOROSA_APP_CHARTS_DEBUG,
    define: { 'process.env.NODE_ENV': '"production"' },
    legalComments: 'none',
    preserveSymlinks: true,
    nodePaths: [path.join(stage, 'node_modules')],
    // app 由 umi 3 + React 17 编译：自动 JSX 运行时（文件里不 import React 也能写 JSX，如 BabylonHoroscope）
    jsx: 'automatic',
    loader: { '.js': 'jsx', '.png': 'dataurl', '.jpg': 'dataurl', '.svg': 'text', '.less': 'text', '.css': 'text', '.json': 'json' },
    plugins: [plugin],
    metafile: true,
    write: false,
    logLevel: 'error',
    banner: { js: '/* Generated by horosa-core-js/app-charts/build.mjs from the open-source 星阙 (Horosa-Public) tree — do not edit; see contracts/app_charts_bundle.json */' },
  });
} finally {
  fs.rmSync(stage, { recursive: true, force: true });
}

const bundle = Buffer.from(result.outputFiles[0].contents);
const sha = (buf) => createHash('sha256').update(buf).digest('hex');
const appFiles = {};
const packages = new Set();
for (const input of Object.keys(result.metafile.inputs).sort()) {
  if (input.startsWith('app/')) {
    appFiles[input.slice(4)] = sha(fs.readFileSync(path.join(sourceRoot, APP_SRC_REL, input.slice(4))));
  }
  const m = input.match(/node_modules\/((?:@[^/]+\/)?[^/]+)/);
  if (m) packages.add(m[1]);
}
for (const [rel, text] of Object.entries(theme.inputs)) appFiles[rel] = sha(Buffer.from(text, 'utf8'));
let upstreamCommit = null;
try {
  upstreamCommit = execFileSync('git', ['-C', sourceRoot, 'rev-parse', 'HEAD'], { encoding: 'utf8' }).trim();
} catch { /* not a git checkout — the per-file hashes still pin the inputs */ }

const notices = [...packages].sort().map((name) => {
  const dir = path.join(CORE, 'node_modules', name);
  const meta = JSON.parse(fs.readFileSync(path.join(dir, 'package.json'), 'utf8'));
  const licenseFile = fs.readdirSync(dir).find((f) => /^licen[cs]e/i.test(f));
  const text = licenseFile ? fs.readFileSync(path.join(dir, licenseFile), 'utf8').trim() : `(license: ${meta.license})`;
  return `== ${name}@${meta.version} (${meta.license}) ==\n${text}\n`;
}).join('\n');
const noticeText = `Third-party packages bundled into app-charts.cjs (the 星阙 app's own chart code is AGPL-3.0-only, as is this repo).\n\n${notices}`;

const manifest = {
  _comment: 'Provenance of horosa-core-js/dist/app-charts.cjs. Rebuild: node horosa-core-js/app-charts/build.mjs --source-root <Horosa-Public>; --check verifies.',
  upstream_commit: upstreamCommit,
  esbuild: esbuild.version,
  bundle_sha256: sha(bundle),
  bundle_bytes: bundle.length,
  kinds: null,
  theme_tokens: Object.keys(theme.tokens).length,
  theme_scopes: Object.keys(theme.scopes).length,
  packages: [...packages].sort().map((name) => `${name}@${JSON.parse(fs.readFileSync(path.join(CORE, 'node_modules', name, 'package.json'), 'utf8')).version}`),
  app_files: appFiles,
};

// kinds: load the fresh bundle once and ask it (keeps the manifest honest about what it can draw)
const tmpBundle = path.join(os.tmpdir(), `horosa-app-charts-${process.pid}.cjs`);
fs.writeFileSync(tmpBundle, bundle);
try {
  const { createRequire } = await import('node:module');
  manifest.kinds = createRequire(import.meta.url)(tmpBundle).listKinds();
} finally {
  fs.rmSync(tmpBundle, { force: true });
}
const manifestText = `${JSON.stringify(manifest, null, 2)}\n`;

if (check) {
  const problems = [];
  if (!fs.existsSync(BUNDLE) || sha(fs.readFileSync(BUNDLE)) !== manifest.bundle_sha256) problems.push('dist/app-charts.cjs');
  if (!fs.existsSync(NOTICE) || fs.readFileSync(NOTICE, 'utf8') !== noticeText) problems.push('dist/app-charts.LICENSES.txt');
  const committed = fs.existsSync(MANIFEST) ? JSON.parse(fs.readFileSync(MANIFEST, 'utf8')) : {};
  const { upstream_commit: _ignored, ...rest } = manifest;
  const { upstream_commit: _ignored2, ...committedRest } = committed;
  if (JSON.stringify(rest) !== JSON.stringify(committedRest)) problems.push('contracts/app_charts_bundle.json');
  if (problems.length) {
    console.error(`app-charts: out of date vs ${sourceRoot} — rebuild with node horosa-core-js/app-charts/build.mjs --source-root …:\n  ${problems.join('\n  ')}`);
    process.exit(1);
  }
  console.log(`app-charts: up to date (${manifest.kinds.length} kinds, ${Object.keys(appFiles).length} app files, ${bundle.length} bytes)`);
} else {
  fs.mkdirSync(DIST, { recursive: true });
  fs.writeFileSync(BUNDLE, bundle);
  fs.writeFileSync(NOTICE, noticeText);
  fs.writeFileSync(MANIFEST, manifestText);
  console.log(`app-charts: wrote dist/app-charts.cjs (${bundle.length} bytes, ${manifest.kinds.length} kinds, ${Object.keys(appFiles).length} app files)`);
}
