// Changed top-level declarations between two upstream astrostudyui/src trees (helper of audit_upstream_ports.py).
//
//   NODE_PATH=<Horosa-Public>/Horosa-Web/astrostudyui/node_modules node scripts/upstream_decl_diff.mjs <old_src> <new_src>
//
// Prints a JSON array of [name, "changed" | "removed"]: every top-level function / class / variable whose
// comment-stripped, compact-normalised code differs between the trees (or that vanished). Parses with the
// upstream tree's own @babel/parser + @babel/generator (read-only; nothing is installed or written).
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';

const require = createRequire(path.join(process.env.NODE_PATH || process.cwd(), 'noop.js'));
const parser = require('@babel/parser');
const generate = require('@babel/generator').default;
const OPTS = { sourceType: 'module', errorRecovery: true, plugins: ['jsx', 'classProperties'] };

function walk(dir, acc) {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) {
      if (!/node_modules|__tests__/.test(e.name)) walk(p, acc);
    } else if (/\.jsx?$/.test(e.name)) {
      acc.push(p);
    }
  }
  return acc;
}

function index(root) {
  const out = new Map();
  for (const file of walk(root, [])) {
    let ast;
    try { ast = parser.parse(fs.readFileSync(file, 'utf8'), OPTS); } catch (e) { continue; }
    for (let node of ast.program.body) {
      if ((node.type === 'ExportNamedDeclaration' || node.type === 'ExportDefaultDeclaration') && node.declaration) node = node.declaration;
      const put = (name, n) => {
        const code = generate(n, { comments: false, compact: true }).code;
        if (!out.has(name)) out.set(name, new Set());
        out.get(name).add(code);
      };
      if ((node.type === 'FunctionDeclaration' || node.type === 'ClassDeclaration') && node.id) put(node.id.name, node);
      else if (node.type === 'VariableDeclaration') {
        for (const d of node.declarations) if (d.id && d.id.type === 'Identifier') put(d.id.name, d);
      }
    }
  }
  return out;
}

const [oldRoot, newRoot] = process.argv.slice(2);
if (!oldRoot || !newRoot) {
  console.error('usage: node upstream_decl_diff.mjs <old_src> <new_src>');
  process.exit(2);
}
const before = index(oldRoot);
const after = index(newRoot);
const changed = [];
for (const [name, codes] of before) {
  const now = after.get(name);
  if (!now) { changed.push([name, 'removed']); continue; }
  const same = [...codes].every((c) => now.has(c)) && [...now].every((c) => codes.has(c));
  if (!same) changed.push([name, 'changed']);
}
changed.sort((a, b) => (a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0));
process.stdout.write(JSON.stringify(changed));
