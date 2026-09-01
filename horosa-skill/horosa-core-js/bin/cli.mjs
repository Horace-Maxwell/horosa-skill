#!/usr/bin/env node
import process from 'node:process';

import { listTools, runTool } from '../src/tools/index.js';

async function readStdin() {
  const chunks = [];
  for await (const chunk of process.stdin) {
    chunks.push(chunk);
  }
  return Buffer.concat(chunks).toString('utf8');
}

function printJson(data) {
  process.stdout.write(`${JSON.stringify(data, null, 2)}\n`);
}

async function main() {
  const [command = 'help', arg] = process.argv.slice(2);
  if (command === 'list') {
    printJson({ ok: true, tools: listTools() });
    return;
  }
  if (command !== 'run' || !arg) {
    printJson({
      ok: false,
      error: {
        code: 'cli.invalid_arguments',
        message: 'Usage: horosa-core-js list | horosa-core-js run <tool>',
      },
    });
    process.exitCode = 2;
    return;
  }

  try {
    const raw = await readStdin();
    const parsed = raw.trim() ? JSON.parse(raw) : {};
    // Coerce a null / scalar payload (e.g. stdin is literally `null`, a number, or a string) to {}
    // so tools degrade to a structured "insufficient input" result instead of throwing on
    // `payload.field`. Objects and arrays pass through unchanged (they already degrade gracefully).
    const payload = parsed && typeof parsed === 'object' ? parsed : {};
    // await：多数 runner 同步（await 对其为 no-op），zhengchuan 因异步载条文正文库返 Promise。
    const result = await runTool(arg, payload);
    // 顶层 `ok` 是**传输层**语义（CLI 跑起来没有），Python 侧 js_client 读完即 pop；
    // 技法自身的成败一律走 `data.ok`（两层不能混）。展开放在前面、传输标志放在后面 ——
    // 反过来写的话，任何返回顶层 ok 的 tool 都能把传输标志顶掉，语义失败会被误报成引擎崩溃。
    if (result && typeof result === 'object' && Object.prototype.hasOwnProperty.call(result, 'ok')) {
      process.stderr.write(`[horosa-core-js] warning: tool '${arg}' returned a top-level 'ok'; 技法成败请放 data.ok。\n`);
    }
    printJson({ ...result, ok: true });
  } catch (error) {
    printJson({
      ok: false,
      error: {
        code: 'cli.execution_failed',
        message: error instanceof Error ? error.message : String(error),
      },
    });
    process.exitCode = 1;
  }
}

await main();
