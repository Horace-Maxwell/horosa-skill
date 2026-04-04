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
    const payload = raw.trim() ? JSON.parse(raw) : {};
    const result = runTool(arg, payload);
    printJson({ ok: true, ...result });
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
