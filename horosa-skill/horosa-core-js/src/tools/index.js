import { runJinkou } from './jinkou.js';
import { runQimen } from './qimen.js';
import { runTaiyi } from './taiyi.js';

const TOOL_RUNNERS = {
  qimen: runQimen,
  taiyi: runTaiyi,
  jinkou: runJinkou,
};

export function listTools() {
  return Object.keys(TOOL_RUNNERS);
}

export function runTool(toolName, payload) {
  const runner = TOOL_RUNNERS[toolName];
  if (!runner) {
    throw new Error(`Unsupported horosa-core-js tool: ${toolName}`);
  }
  return runner(payload);
}
