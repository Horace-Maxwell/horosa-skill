import '../shared/lunarYearCache.js';
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
import { runClassicalDerived } from './classicalDerived.js';
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
import { runMundaneCards } from './mundaneCards.js';
import { runBaziPeriod } from './baziPeriod.js';
import { runBaziLocal } from './baziLocal.js';
import { runZiweiExtras } from './ziweiExtras.js';
import { runZiweiBirth } from './ziweiBirth.js';
import { runSuzhan } from './suzhan.js';
import { runSanshiZiweiSihua } from './sanshiZiweiSihua.js';
import { runSanshiUnited } from './sanshiUnited.js';
import { runQimenZeri } from './qimenzeri.js';
import { runZeriScan, runZeriScanRemote } from './zeriScan.js';
import { runTianxing } from './tianxing.js';
import { runQizhengElection } from './qizhengElection.js';
import { runAcgSection } from './acgSection.js';

// 地名检索懒加载：它带进 npm `tz-lookup` 与 3.9 MB 城市库。静态 import 的话，任何一份缺 tz-lookup 的 node_modules
// （开发树没重跑 npm ci、旧 runtime 只换了代码）会让本文件加载失败 = 全部 JS 技法一起挂；懒加载把影响收在
// place_search 自己身上（Python 侧把「缺依赖 / 不认识这个工具」报成 place.runtime_outdated）。
const runPlaceSearch = (payload) => import('./placeSearch.js').then((m) => m.runPlaceSearch(payload));
// 择日条件词表 / 条件回显（skill 自有）：只在择日结果与指引生成时用，懒加载。
const runZeriConditions = (payload) => import('./zeriConditions.js').then((m) => m.runZeriConditions(payload));

const TOOL_RUNNERS = {
  place_search: runPlaceSearch,
  zeri_conditions: runZeriConditions,
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
  mundane_cards: runMundaneCards,
  bazi_period: runBaziPeriod,
  bazi_local: runBaziLocal,
  ziwei_extras: runZiweiExtras,
  ziwei_birth: runZiweiBirth,
  suzhan: runSuzhan,
  sanshi_ziwei_sihua: runSanshiZiweiSihua,
  sanshiunited: runSanshiUnited,
  qimenzeri: runQimenZeri,
  // 择日十技法（上游 v3.10.0）：六个本地扫描成员共用一个入口（technique 选路），
  // 七政/印度两个后端扫描成员共用另一个（只做 compile 校验 + 排版）。
  zeri_scan: runZeriScan,
  zeri_scan_remote: runZeriScanRemote,
  tianxing: runTianxing,
  qizhengelection: runQizhengElection,
  india_jyotish: runIndiaJyotish,
  acg_section: runAcgSection,
  qimen: runQimen,
  taiyi: runTaiyi,
  jinkou: runJinkou,
  liureng: runLiureng,
  liuyao: runLiuyao,
  bazi_geju: runBaziGeju,
  classical_derived: runClassicalDerived,
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
