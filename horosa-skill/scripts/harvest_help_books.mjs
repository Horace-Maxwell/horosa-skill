#!/usr/bin/env node
// 把上游「操作手册」(一页一本书、一技法一章,v3.14.0 起)按上游自己的数据结构展开成 JSON,交给 gen_knowledge_packs.py 落包。
//
//   node scripts/harvest_help_books.mjs --source-root <Horosa-Public> [--worktree]   → stdout: JSON
//
// 不拿正则去猜 JSX。做法是把上游的手册模块原样打成一个包(esbuild,文件内容取自 HEAD blob),然后:
//   · 书的清单 = 上游注册表 TECHNIQUE_HELP_DOCS(帮助弹窗用的同一张表);每册 = Doc.book = { title, groups:[{ key, label, chapters }] };
//   · 章的清单 = 上游 HelpBook.bookChapters(book)(界面左栏菜单用的同一个函数);
//   · 每章正文 = chapter.render() 的 React 元素树,按上游 utils/aiTools/helpText.js 的走树规则(类组件实例化、__helpPure 部件
//     直接调用、其余函数组件不调用只走 children)转成 Markdown;
//   · 逐章对账:同一棵元素树再交给上游自己的 helpElementToText(给外部 AI 的纯文本),两边去掉排版记号后必须逐字相同——
//     丢字、串段、把代码当正文,任何一种都会在这里红,而不是静默落进知识包。
// 解析不了的结构一律报错退出(非 0):未知标签、渲染抛错、空章、重复章节键、注册表里没有 book 的手册、桩模块的值被当成正文。
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import { createRequire } from 'node:module';
import os from 'node:os';
import path from 'node:path';
import process from 'node:process';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const CORE = path.resolve(HERE, '..', 'horosa-core-js');
const coreRequire = createRequire(path.join(CORE, 'package.json'));
const SRC_REL = 'Horosa-Web/astrostudyui/src';
const REGISTRY = 'components/help/techniqueHelpRegistry.js';
const HELP_TEXT = 'utils/aiTools/helpText.js';
// 手册外壳与样式件:每册都 import,不算哪一册的正文文件
const SHELL_FILES = new Set(['components/help/HelpBook.js', 'components/help/helpDocStyle.js', REGISTRY]);

class HarvestError extends Error {}
function fail(message) {
  throw new HarvestError(message);
}

function arg(name) {
  const i = process.argv.indexOf(name);
  return i >= 0 ? process.argv[i + 1] : undefined;
}

// ---- 上游文件来源:HEAD blob(缺省)或工作区(--worktree,只给非 git 的快照目录用) ----
function makeSource(sourceRoot, worktree) {
  const git = (...args) => execFileSync('git', ['-C', sourceRoot, ...args], { encoding: 'utf8', maxBuffer: 256 * 1024 * 1024 });
  let files;
  if (worktree) {
    files = new Set();
    const root = path.join(sourceRoot, SRC_REL);
    const visit = (dir) => {
      for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
        const full = path.join(dir, entry.name);
        if (entry.isDirectory()) visit(full);
        else files.add(path.relative(root, full).split(path.sep).join('/'));
      }
    };
    visit(root);
  } else {
    files = new Set(git('ls-tree', '-r', '--name-only', 'HEAD', `${SRC_REL}/`).split('\n').filter(Boolean).map((line) => line.slice(SRC_REL.length + 1)));
  }
  const cache = new Map();
  return {
    has: (rel) => files.has(rel),
    read(rel) {
      if (!cache.has(rel)) {
        cache.set(rel, worktree ? fs.readFileSync(path.join(sourceRoot, SRC_REL, rel), 'utf8') : git('show', `HEAD:${SRC_REL}/${rel}`));
      }
      return cache.get(rel);
    },
  };
}

// 相对路径 → 上游树里的文件(webpack 的解析顺序:原名 / .js / .jsx / .json / 目录下的 index.js)
function resolveUpstream(source, importer, request) {
  const base = path.posix.normalize(path.posix.join(path.posix.dirname(importer), request));
  for (const candidate of [base, `${base}.js`, `${base}.jsx`, `${base}.json`, `${base}/index.js`]) {
    if (source.has(candidate)) return candidate;
  }
  return null;
}

// 桩:手册正文不会用到的东西(界面库、样式表、图片)。任何把桩当文字用的地方都要炸——静默成空串等于丢字。
const STUB_SOURCE = `
const REACT_STATICS = new Set(['$$typeof', 'defaultProps', 'propTypes', 'displayName', 'name', 'contextType', 'contextTypes', 'childContextTypes', 'getDefaultProps', 'then']);
const boom = (what) => { throw new Error('help harvest: a stubbed module value was used ' + what + ' (' + __STUB__ + ')'); };
const handler = {
  get(target, key) {
    if (key === '__esModule') return true;
    if (key === '__helpStub') return __STUB__;
    if (key === 'default') return proxy;
    if (key === Symbol.toPrimitive || key === 'toString' || key === 'valueOf') return () => boom('as text');
    if (key === Symbol.iterator) return undefined;
    if (key === 'prototype') return target.prototype;
    // React.createElement 会读这几个静态属性;给它 undefined,让桩组件以元素的样子走到下面的走树里,在那儿点名报错
    if (REACT_STATICS.has(key)) return undefined;
    return proxy;
  },
  apply: () => proxy,
  construct: () => proxy,
  getPrototypeOf: () => proxy, // esbuild 的 __toESM 以「模块的原型」建具名导入的容器:具名导入沿原型链落回本桩
};
const proxy = new Proxy(function helpStub() {}, handler);
module.exports = proxy;
`;

const REAL_PACKAGES = /^(react|react\/jsx-runtime|react\/jsx-dev-runtime|object-assign)$/;
const ASSET = /\.(less|css|scss|png|jpe?g|gif|svg|webp|woff2?|ttf|otf|mp3|wav)(\?.*)?$/;

async function bundle(source) {
  const esbuild = coreRequire('esbuild');
  const stubbed = new Set();
  const plugin = {
    name: 'horosa-help-books',
    setup(build) {
      build.onResolve({ filter: /^@up\// }, (a) => ({ path: a.path.slice(4), namespace: 'up' }));
      build.onResolve({ filter: /.*/, namespace: 'up' }, (a) => {
        if (ASSET.test(a.path)) return { path: `asset:${a.path}`, namespace: 'stub' };
        if (a.path.startsWith('.')) {
          const resolved = resolveUpstream(source, a.importer, a.path);
          if (!resolved) return { errors: [{ text: `help harvest: cannot resolve ${a.path} from ${a.importer}` }] };
          return { path: resolved, namespace: 'up' };
        }
        if (REAL_PACKAGES.test(a.path)) return { path: coreRequire.resolve(a.path) };
        stubbed.add(a.path);
        return { path: `pkg:${a.path}`, namespace: 'stub' };
      });
      build.onLoad({ filter: /.*/, namespace: 'up' }, (a) => ({
        contents: source.read(a.path),
        loader: a.path.endsWith('.json') ? 'json' : 'jsx',
        resolveDir: CORE,
      }));
      build.onLoad({ filter: /.*/, namespace: 'stub' }, (a) => ({ contents: STUB_SOURCE.replaceAll('__STUB__', JSON.stringify(a.path)), loader: 'js' }));
    },
  };
  const entry = `
    import * as React from 'react';
    import { TECHNIQUE_HELP_DOCS } from '@up/${REGISTRY}';
    import HelpBook, { bookChapters } from '@up/components/help/HelpBook.js';
    import * as style from '@up/components/help/helpDocStyle.js';
    import { helpElementToText } from '@up/${HELP_TEXT}';
    export { React, TECHNIQUE_HELP_DOCS, HelpBook, bookChapters, style, helpElementToText };
  `;
  const result = await esbuild.build({
    stdin: { contents: entry, resolveDir: CORE, loader: 'js' },
    bundle: true,
    write: false,
    format: 'cjs',
    platform: 'node',
    jsx: 'automatic',
    keepNames: true,
    metafile: true,
    logLevel: 'silent',
    define: { 'process.env.NODE_ENV': '"production"' },
    plugins: [plugin],
  });
  return { code: result.outputFiles[0].text, metafile: result.metafile, stubbed: [...stubbed].sort() };
}

// ---- 元素树 → Markdown。走树规则与上游 helpText.js 的 walk 相同;差别只在排版记号(标题层级、加粗、表格)。 ----
const BLOCK = new Set(['div', 'p', 'ul', 'ol', 'section', 'table', 'thead', 'tbody', 'blockquote', 'pre', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'nav', 'main']);
const INLINE = new Set(['span', 'i', 'em', 'u', 'small', 'sub', 'sup', 'a', 'label', 'code', 'kbd']);
const HEADING_TAG = { h1: '# ', h2: '## ', h3: '### ', h4: '#### ', h5: '#### ', h6: '#### ' };

function makeWalker(mod, where) {
  const { React, HelpBook, style } = mod;
  const headingOf = new Map([[style.title, '# '], [style.h, '## '], [style.ct, '### ']]);
  const called = new Map();
  const classOf = (props) => (typeof props.className === 'string' ? props.className : '');
  const hasClass = (props, name) => new RegExp(`(^|\\s)${name}(\\s|$)`).test(classOf(props));

  // 行内文字(标题 / 表格单元格 / 键值的键):块结构压成空格
  const inline = (node) => {
    const out = [];
    walk(node, out, 0, { inline: true });
    return out.join('').replace(/\s*\n\s*/g, ' ').replace(/[ \t]{2,}/g, ' ').trim();
  };

  function walk(node, out, depth, ctx) {
    if (node === null || node === undefined || typeof node === 'boolean') return;
    if (depth > 200) fail(`${where()}: element tree deeper than 200 levels`);
    if (typeof node === 'string' || typeof node === 'number') {
      // 段首的「#」在 Markdown 里会被读成标题(上游有「# 与原位之别」这样的行):转义
      if (!ctx.inline && /^\s*#/.test(`${node}`) && (!out.length || /\n\s*$/.test(out[out.length - 1]))) out.push('\\');
      out.push(`${node}`);
      return;
    }
    if (Array.isArray(node)) { node.forEach((child) => walk(child, out, depth + 1, ctx)); return; }
    if (!React.isValidElement(node)) fail(`${where()}: a non-element object reached the text walker (${Object.prototype.toString.call(node)})`);
    const { type } = node;
    const props = node.props || {};
    if (type === HelpBook) fail(`${where()}: a HelpBook nested inside a chapter`);
    if (type === React.Fragment) { walk(props.children, out, depth + 1, ctx); return; }
    if (typeof type === 'function') {
      if (type.__helpStub) fail(`${where()}: chapter renders a stubbed component (${type.__helpStub})`);
      if (type.__helpPure) { walk(type(props), out, depth + 1, ctx); return; }
      if (type.prototype && type.prototype.isReactComponent) {
        const instance = new type(props);
        instance.props = props;
        if (!instance.state) instance.state = {};
        walk(instance.render(), out, depth + 1, ctx);
        return;
      }
      // 没标 __helpPure 的函数组件:帮助弹窗里 React 照样渲染它,用户看得到这段字;上游给 AI 的纯文本(helpText.js)却不调用它,
      // 那段字就丢了(v3.14.0:星运手册的 TimeBlockNote,七章各少一段)。这里按界面所见调用它,并把它标成 __helpPure,
      // 让下面的对账在同一口径下进行;名字记进输出,生成器会打印出来。带 hooks 的组件在这里调用会抛错 → 整个收割失败。
      const name = type.displayName || type.name || '(anonymous)';
      called.set(name, (called.get(name) || 0) + 1);
      type.__helpPure = true;
      walk(type(props), out, depth + 1, ctx);
      return;
    }
    if (typeof type !== 'string') fail(`${where()}: unsupported element type ${String(type && type.$$typeof ? type.$$typeof : type)}`);

    if (headingOf.has(props.style) || HEADING_TAG[type]) {
      const text = inline(props.children);
      if (text) out.push(ctx.inline ? ` ${text} ` : `\n\n${headingOf.get(props.style) || HEADING_TAG[type]}${text}\n\n`);
      return;
    }
    if (type === 'div' && hasClass(props, 'horosa-help-kv')) {
      // 键值行:界面上键是加粗的淡色定宽列。写成「- **键**：值」——列表项不会并段,键以「#」「-」开头也不会被读成标题 / 列表
      const cells = React.Children.toArray(props.children).map((child) => inline(child));
      if (cells.length !== 2) fail(`${where()}: a key-value row with ${cells.length} cells`);
      const key = cells[0].replace(/\*\*/g, '');
      if (ctx.inline) out.push(` ${key}：${cells[1]} `);
      else out.push(`\n${'  '.repeat(ctx.list || 0)}- ${key ? `**${key}**：` : ''}${cells[1]}\n`);
      return;
    }
    if (type === 'div' && hasClass(props, 'horosa-help-tip')) {
      // 提示框:首个子元素是标签(提示 / 说明 / 注意),其余是正文
      const [label, ...rest] = React.Children.toArray(props.children);
      const text = `${inline(label)}：${inline(rest)}`;
      out.push(ctx.inline ? ` ${text} ` : `\n\n> ${text}\n\n`);
      return;
    }
    if (hasClass(props, 'horosa-help-step-no')) { out.push(`${inline(props.children)}. `); return; }
    if (type === 'table') {
      if (ctx.inline) { walk(props.children, out, depth + 1, ctx); return; }
      const rows = [];
      const collect = (child, header) => {
        React.Children.toArray(child).forEach((item) => {
          if (!React.isValidElement(item)) { if (`${item}`.trim()) fail(`${where()}: loose text inside <table>`); return; }
          if (item.type === 'thead') collect(item.props.children, true);
          else if (item.type === 'tbody' || item.type === 'tfoot') collect(item.props.children, false);
          else if (item.type === 'tr') {
            const cells = React.Children.toArray(item.props.children).map((cell) => {
              if (!React.isValidElement(cell) || (cell.type !== 'td' && cell.type !== 'th')) fail(`${where()}: <tr> holds something other than td / th`);
              return inline(cell.props.children).replace(/\|/g, '\\|');
            });
            rows.push({ cells, header: header || React.Children.toArray(item.props.children).every((cell) => cell.type === 'th') });
          } else if (item.type === 'colgroup' || item.type === 'caption') {
            if (item.type === 'caption') out.push(`\n\n${inline(item.props.children)}\n`);
          } else fail(`${where()}: unsupported <table> child <${String(item.type)}>`);
        });
      };
      collect(props.children, false);
      out.push('\n\n');
      rows.forEach((row, index) => {
        out.push(`| ${row.cells.join(' | ')} |\n`);
        if (row.header && !(rows[index + 1] && rows[index + 1].header)) out.push(`|${row.cells.map(() => ' --- |').join('')}\n`);
      });
      out.push('\n');
      return;
    }
    if (type === 'td' || type === 'th' || type === 'tr' || type === 'thead' || type === 'tbody') fail(`${where()}: <${type}> outside a <table>`);
    if (type === 'br') { out.push(ctx.inline ? ' ' : '\n'); return; }
    if (type === 'hr') { if (!ctx.inline) out.push('\n\n'); return; }
    if (type === 'b' || type === 'strong') {
      const text = inline(props.children);
      if (text) out.push(`**${text}**`);
      return;
    }
    if (type === 'ol' && !ctx.inline) {
      out.push('\n\n');
      React.Children.toArray(props.children).forEach((item, index) => {
        if (!React.isValidElement(item) || item.type !== 'li') fail(`${where()}: <ol> holds something other than <li>`);
        const text = [];
        walk(item.props.children, text, depth + 1, { ...ctx, inline: true });
        const line = text.join('').replace(/\s*\n\s*/g, ' ').replace(/[ \t]{2,}/g, ' ').trim();
        // 上游 Steps 部件自己带步骤号(horosa-help-step-no → 「1. 」);没有号的 <ol> 这里补上
        out.push(/^\d+\. /.test(line) ? `${line}\n` : `${index + 1}. ${line}\n`);
      });
      out.push('\n');
      return;
    }
    if (type === 'li') {
      if (ctx.inline) { out.push(' '); walk(props.children, out, depth + 1, ctx); out.push(' '); return; }
      const text = [];
      walk(props.children, text, depth + 1, { ...ctx, list: (ctx.list || 0) + 1 });
      const lines = text.join('').split('\n').map((line) => line.trim()).filter(Boolean);
      // 列表项里再套列表:子项已经各自带「- 」,缩两格挂在父项下面
      out.push(`\n${'  '.repeat(ctx.list || 0)}- ${lines.join(`\n${'  '.repeat((ctx.list || 0) + 1)}`)}\n`);
      return;
    }
    if (BLOCK.has(type)) {
      if (ctx.inline) { out.push(' '); walk(props.children, out, depth + 1, ctx); out.push(' '); return; }
      out.push('\n\n');
      walk(props.children, out, depth + 1, ctx);
      out.push('\n\n');
      return;
    }
    if (INLINE.has(type)) { walk(props.children, out, depth + 1, ctx); return; }
    fail(`${where()}: unsupported tag <${type}> — teach scripts/harvest_help_books.mjs how to render it`);
  }

  return {
    called,
    markdown(element) {
      const out = [];
      walk(element, out, 0, {});
      const lines = out.join('').split('\n').map((line) => line.replace(/[ \t\u00a0]+$/g, '').replace(/^[ \t\u00a0]+/g, (indent) => (/^( {2})+$/.test(indent) ? indent : '')));
      const kept = [];
      for (const line of lines) {
        if (!line.trim()) { if (kept.length && kept[kept.length - 1] !== '') kept.push(''); continue; }
        kept.push(line);
      }
      while (kept.length && kept[kept.length - 1] === '') kept.pop();
      // 相邻的列表项 / 键值行之间不留空行(每个块元素前后各推了一次换行)
      const joined = [];
      const kindOf = (line) => (/^\s*- /.test(line) ? 'bullet' : (/^\s*\d+\. /.test(line) ? 'step' : (line.startsWith('|') ? 'row' : '')));
      for (let i = 0; i < kept.length; i += 1) {
        if (kept[i] === '' && i > 0 && i + 1 < kept.length && kindOf(kept[i - 1]) && kindOf(kept[i - 1]) === kindOf(kept[i + 1])) continue;
        joined.push(kept[i]);
      }
      return joined.join('\n');
    },
  };
}

// 对账口径:只比「字」。两边的排版记号不同(上游纯文本用「· 」「:」「 | 」,这里用 Markdown),空白与这些记号都不算字。
const NOT_TEXT = /[\s#*\-|·:：.\\>]/g;
const bare = (text) => text.replace(NOT_TEXT, '');

function firstDifference(a, b) {
  let i = 0;
  while (i < a.length && i < b.length && a[i] === b[i]) i += 1;
  return `at char ${i}: ours …${a.slice(Math.max(0, i - 20), i + 30)}… vs upstream …${b.slice(Math.max(0, i - 20), i + 30)}…`;
}

async function main() {
  const sourceRoot = arg('--source-root') || process.env.HOROSA_SOURCE_ROOT;
  const worktree = process.argv.includes('--worktree');
  if (!sourceRoot || !fs.existsSync(path.join(sourceRoot, 'Horosa-Web'))) fail('--source-root (or HOROSA_SOURCE_ROOT) must point at a Horosa-Public checkout');
  const source = makeSource(path.resolve(sourceRoot), worktree);
  if (!source.has(REGISTRY)) fail(`upstream has no ${REGISTRY} — the help registry moved; re-read the upstream help layout before touching this script`);
  if (!source.has(HELP_TEXT)) fail(`upstream has no ${HELP_TEXT} — the reference text walker moved`);

  const built = await bundle(source);
  const stage = fs.mkdtempSync(path.join(os.tmpdir(), 'horosa-help-books-'));
  if (process.argv.includes('--list-inputs')) {
    process.stdout.write(`${Object.keys(built.metafile.inputs).sort().join('\n')}\n`);
    return;
  }
  let mod;
  try {
    const file = path.join(stage, 'bundle.cjs');
    fs.writeFileSync(file, built.code);
    mod = createRequire(file)(file);
  } finally {
    fs.rmSync(stage, { recursive: true, force: true });
  }

  // 模块在包里的位置:esbuild 在每个模块前写一行「// <namespace>:<path>」。章节的 render 函数原文落在哪个模块,那一章就出自哪个文件。
  const marks = [...built.code.matchAll(/^\/\/ up:(.+)$/gm)].map((m) => ({ at: m.index, file: m[1] }));
  const fileOf = (fn) => {
    const text = Function.prototype.toString.call(fn);
    const at = built.code.indexOf(text);
    if (at < 0) return null;
    let found = null;
    for (const mark of marks) { if (mark.at <= at) found = mark.file; else break; }
    return found;
  };

  // 注册表:页签键 → 组件;组件 → 文件(取自注册表自己的 import 行)
  const registrySource = source.read(REGISTRY);
  const importOf = new Map();
  for (const m of registrySource.matchAll(/^import\s+(\w+)\s+from\s+'([^']+)';?\s*$/gm)) {
    const resolved = resolveUpstream(source, REGISTRY, m[2]);
    if (!resolved) fail(`${REGISTRY}: import ${m[1]} from '${m[2]}' does not resolve`);
    importOf.set(m[1], resolved);
  }

  // 每个上游文件的依赖闭包(metafile):一册手册的正文可能分在几个文件里(direction/chapters*.js)
  const inputs = built.metafile.inputs;
  const closure = (file) => {
    const seen = new Set();
    const queue = [`up:${file}`];
    while (queue.length) {
      const current = queue.pop();
      if (seen.has(current) || !inputs[current]) continue;
      seen.add(current);
      for (const dep of inputs[current].imports) queue.push(dep.path);
    }
    return [...seen].filter((name) => name.startsWith('up:')).map((name) => name.slice(3)).sort();
  };

  const books = [];
  let current = '';
  const walker = makeWalker(mod, () => current);
  for (const [tab, Doc] of Object.entries(mod.TECHNIQUE_HELP_DOCS)) {
    current = `help book ${tab}`;
    if (typeof Doc !== 'function') fail(`${current}: registry value is not a component`);
    const component = Doc.name;
    const file = importOf.get(component);
    if (!file) fail(`${current}: component ${component} has no import line in ${REGISTRY}`);
    const book = Doc.book;
    if (!book || !Array.isArray(book.groups)) fail(`${current}: ${component} has no static book — upstream promised every manual is a HelpBook (helpBookCoverage.test.js)`);
    if (typeof book.title !== 'string' || !book.title.trim()) fail(`${current}: book has no title`);
    const chapters = mod.bookChapters(book);
    if (!chapters.length) fail(`${current}: book has no chapters`);
    const seenKeys = new Set();
    const groups = [];
    for (const group of book.groups) {
      if (!group || !(group.chapters || []).length) continue;
      const entry = { key: `${group.key ?? ''}`, label: `${group.label ?? ''}`, hint: typeof group.hint === 'string' ? group.hint : '', chapters: [] };
      for (const chapter of group.chapters) {
        if (!chapter || !chapter.key) fail(`${current}: group ${entry.key} holds a chapter without a key`);
        const key = `${chapter.key}`;
        current = `help book ${tab} / chapter ${key}`;
        if (seenKeys.has(key)) fail(`${current}: duplicate chapter key`);
        seenKeys.add(key);
        if (typeof chapter.label !== 'string' || !chapter.label.trim()) fail(`${current}: chapter has no label`);
        if (typeof chapter.render !== 'function') fail(`${current}: chapter has no render function`);
        const element = chapter.render();
        const markdown = walker.markdown(element);
        const reference = mod.helpElementToText(element);
        if (!reference.trim()) fail(`${current}: upstream's own help text for this chapter is empty`);
        if (bare(markdown) !== bare(reference)) fail(`${current}: harvested text differs from upstream helpElementToText — ${firstDifference(bare(markdown), bare(reference))}`);
        entry.chapters.push({
          key,
          label: chapter.label.trim(),
          aliases: (chapter.aliases || []).map((alias) => `${alias}`),
          file: fileOf(chapter.render) || file,
          text: markdown,
          chars: bare(markdown).length,
        });
      }
      groups.push(entry);
    }
    if (seenKeys.size !== chapters.length) fail(`help book ${tab}: bookChapters() lists ${chapters.length} chapters, groups hold ${seenKeys.size}`);
    books.push({ tab, component, file, title: book.title.trim(), files: closure(file).filter((name) => (name === file || name.startsWith('components/help/')) && !SHELL_FILES.has(name)), groups });
  }
  if (!books.length) fail('the upstream help registry is empty');
  process.stdout.write(`${JSON.stringify({ schema: 'horosa.help_books.v1', registry: REGISTRY, books, stubbed_packages: built.stubbed, unmarked_function_components: Object.fromEntries([...walker.called].sort()) }, null, 1)}\n`);
}

main().catch((error) => {
  const errors = error && Array.isArray(error.errors) ? error.errors.map((item) => item.text).join('; ') : '';
  console.error(`harvest-help-books: FAIL — ${errors || (error instanceof HarvestError ? error.message : (error && error.stack) || error)}`);
  process.exit(1);
});
