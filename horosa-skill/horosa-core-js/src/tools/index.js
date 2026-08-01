import { runAstroExtra } from './astroextra.js';
import { runCanping } from './canping.js';
import { runElectionTool } from './election.js';
import { runGuolaoMoira } from './guolaoMoira.js';
import { runHeluo } from './heluo.js';
import { runHoraryTool } from './horary.js';
import { runJinkou } from './jinkou.js';
import { runLiureng } from './liureng.js';
import { runLiuyao } from './liuyao.js';
import { runBaziGeju } from './baziGeju.js';
import { runTarot } from './tarot.js';
import { runProgExtra } from './progextra.js';
import { runQimen } from './qimen.js';
import { runTaiyi } from './taiyi.js';
import { runTongSheFa } from './tongshefa.js';
import { runYizhangjing } from './yizhangjing.js';
import { runXiaoLiuRen } from './xiaoliuren.js';
import { runFeiGong } from './feigong.js';
import { runXiaoChengTu } from './xiaochengtu.js';
import { runGuice } from './guice.js';
import { runZhengChuan } from './zhengchuan.js';
import { runIndiaJyotish } from './indiaJyotish.js';
import { runYanqinYanfa } from './yanqinYanfa.js';
import { runTiebanFramework } from './tiebanFramework.js';

const TOOL_RUNNERS = {
  tieban_framework: runTiebanFramework,
  yanqin_yanfa: runYanqinYanfa,
  india_jyotish: runIndiaJyotish,
  qimen: runQimen,
  taiyi: runTaiyi,
  jinkou: runJinkou,
  liureng: runLiureng,
  liuyao: runLiuyao,
  bazi_geju: runBaziGeju,
  tarot: runTarot,
  tongshefa: runTongSheFa,
  canping: runCanping,
  heluo: runHeluo,
  yizhangjing: runYizhangjing,
  xiaoliuren: runXiaoLiuRen,
  feigong: runFeiGong,
  xiaochengtu: runXiaoChengTu,
  guice: runGuice,
  zhengchuan: runZhengChuan,
  astroextra: runAstroExtra,
  progextra: runProgExtra,
  horary: runHoraryTool,
  election: runElectionTool,
  guolao_moira: runGuolaoMoira,
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
