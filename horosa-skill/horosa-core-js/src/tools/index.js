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
import { runLingqi } from './lingqi.js';
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
import { runUranianExtra } from './uranianExtra.js';
import { runEgyptSection } from './egyptSection.js';
import { runBabylon } from './babylon.js';
import { runHuangli } from './huangli.js';
import { runTongshu } from './tongshu.js';
import { runCalendarExtras } from './calendarExtras.js';
import { runGuolaoStarDignity } from './guolaoStarDignity.js';
import { runMundaneHorary } from './mundaneHorary.js';
import { runMundaneSolunar } from './mundaneSolunar.js';
import { runMundaneNavanayaka } from './mundaneNavanayaka.js';
import { runBaziPeriod } from './baziPeriod.js';
import { runZiweiExtras } from './ziweiExtras.js';
import { runSanshiZiweiSihua } from './sanshiZiweiSihua.js';
import { runQimenZeri } from './qimenzeri.js';
import { runTianxing } from './tianxing.js';

const TOOL_RUNNERS = {
  uranian_extra: runUranianExtra,
  tieban_framework: runTiebanFramework,
  yanqin_yanfa: runYanqinYanfa,
  egypt_section: runEgyptSection,
  babylon: runBabylon,
  huangli: runHuangli,
  tongshu: runTongshu,
  calendar_extras: runCalendarExtras,
  guolao_star_dignity: runGuolaoStarDignity,
  mundane_horary: runMundaneHorary,
  mundane_solunar: runMundaneSolunar,
  mundane_navanayaka: runMundaneNavanayaka,
  bazi_period: runBaziPeriod,
  ziwei_extras: runZiweiExtras,
  sanshi_ziwei_sihua: runSanshiZiweiSihua,
  qimenzeri: runQimenZeri,
  tianxing: runTianxing,
  india_jyotish: runIndiaJyotish,
  qimen: runQimen,
  taiyi: runTaiyi,
  jinkou: runJinkou,
  liureng: runLiureng,
  liuyao: runLiuyao,
  bazi_geju: runBaziGeju,
  lingqi: runLingqi,
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
