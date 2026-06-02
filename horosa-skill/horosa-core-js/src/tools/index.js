import { runAstroExtra } from './astroextra.js';
import { runCanping } from './canping.js';
import { runElectionTool } from './election.js';
import { runHeluo } from './heluo.js';
import { runHoraryTool } from './horary.js';
import { runJinkou } from './jinkou.js';
import { runLiureng } from './liureng.js';
import { runProgExtra } from './progextra.js';
import { runQimen } from './qimen.js';
import { runTaiyi } from './taiyi.js';
import { runTongSheFa } from './tongshefa.js';

const TOOL_RUNNERS = {
  qimen: runQimen,
  taiyi: runTaiyi,
  jinkou: runJinkou,
  liureng: runLiureng,
  tongshefa: runTongSheFa,
  canping: runCanping,
  heluo: runHeluo,
  astroextra: runAstroExtra,
  progextra: runProgExtra,
  horary: runHoraryTool,
  election: runElectionTool,
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
