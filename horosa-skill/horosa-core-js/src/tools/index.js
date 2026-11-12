import '../shared/lunarYearCache.js';

// 每个技法模块按需加载：cli.mjs 一次只跑一个工具，静态 import 全部约 50 个模块（连同它们的 vendored 引擎）每次 spawn 要多花
// 约 0.12 s——天星择日一次调用 spawn 7 次，光加载就占 1 s。懒加载只载用到的那个；副作用补丁（lunarYearCache）仍在最前面静态装上。
// 另一个好处：任何一个模块加载失败（缺依赖、上游删了导出）只挂它自己，不再让全部 JS 技法一起挂。
// 地名检索早就是懒加载的：它带进 npm `tz-lookup` 与 3.9 MB 城市库，缺 tz-lookup 的 node_modules（开发树没重跑 npm ci、
// 旧 runtime 只换了代码）由 Python 侧报成 place.runtime_outdated。全部模块能否加载由 test/loadcheck.mjs 逐个 import 把关。
function lazy(specifier, exportName) {
  return async () => {
    const runner = (await import(specifier))[exportName];
    if (typeof runner !== 'function') {
      throw new Error(`horosa-core-js: ${specifier} does not export ${exportName}`);
    }
    return runner;
  };
}

const TOOL_RUNNERS = {
  place_search: lazy('./placeSearch.js', 'runPlaceSearch'),
  zeri_conditions: lazy('./zeriConditions.js', 'runZeriConditions'),  // 择日条件词表 / 条件回显（skill 自有）
  uranian_extra: lazy('./uranianExtra.js', 'runUranianExtra'),
  tieban_framework: lazy('./tiebanFramework.js', 'runTiebanFramework'),
  yanqin_yanfa: lazy('./yanqinYanfa.js', 'runYanqinYanfa'),
  egypt_section: lazy('./egyptSection.js', 'runEgyptSection'),
  babylon: lazy('./babylon.js', 'runBabylon'),
  huangli: lazy('./huangli.js', 'runHuangli'),
  tongshu: lazy('./tongshu.js', 'runTongshu'),
  calendar_extras: lazy('./calendarExtras.js', 'runCalendarExtras'),
  guolao_star_dignity: lazy('./guolaoStarDignity.js', 'runGuolaoStarDignity'),
  mundane_horary: lazy('./mundaneHorary.js', 'runMundaneHorary'),
  mundane_solunar: lazy('./mundaneSolunar.js', 'runMundaneSolunar'),
  mundane_navanayaka: lazy('./mundaneNavanayaka.js', 'runMundaneNavanayaka'),
  mundane_cards: lazy('./mundaneCards.js', 'runMundaneCards'),
  bazi_period: lazy('./baziPeriod.js', 'runBaziPeriod'),
  bazi_local: lazy('./baziLocal.js', 'runBaziLocal'),
  ziwei_extras: lazy('./ziweiExtras.js', 'runZiweiExtras'),
  ziwei_birth: lazy('./ziweiBirth.js', 'runZiweiBirth'),
  suzhan: lazy('./suzhan.js', 'runSuzhan'),
  sanshi_ziwei_sihua: lazy('./sanshiZiweiSihua.js', 'runSanshiZiweiSihua'),
  sanshiunited: lazy('./sanshiUnited.js', 'runSanshiUnited'),
  qimenzeri: lazy('./qimenzeri.js', 'runQimenZeri'),
  // 择日十技法（上游 v3.10.0）：六个本地扫描成员共用一个入口（technique 选路），
  // 七政/印度两个后端扫描成员共用另一个（只做 compile 校验 + 排版）。
  zeri_scan: lazy('./zeriScan.js', 'runZeriScan'),
  zeri_scan_remote: lazy('./zeriScan.js', 'runZeriScanRemote'),
  tianxing: lazy('./tianxing.js', 'runTianxing'),
  qizhengelection: lazy('./qizhengElection.js', 'runQizhengElection'),
  india_jyotish: lazy('./indiaJyotish.js', 'runIndiaJyotish'),
  acg_section: lazy('./acgSection.js', 'runAcgSection'),
  qimen: lazy('./qimen.js', 'runQimen'),
  taiyi: lazy('./taiyi.js', 'runTaiyi'),
  jinkou: lazy('./jinkou.js', 'runJinkou'),
  liureng: lazy('./liureng.js', 'runLiureng'),
  liuyao: lazy('./liuyao.js', 'runLiuyao'),
  bazi_geju: lazy('./baziGeju.js', 'runBaziGeju'),
  classical_derived: lazy('./classicalDerived.js', 'runClassicalDerived'),
  lingqi: lazy('./lingqi.js', 'runLingqi'),
  tarot: lazy('./tarot.js', 'runTarot'),
  tongshefa: lazy('./tongshefa.js', 'runTongSheFa'),
  canping: lazy('./canping.js', 'runCanping'),
  heluo: lazy('./heluo.js', 'runHeluo'),
  yizhangjing: lazy('./yizhangjing.js', 'runYizhangjing'),
  xiaoliuren: lazy('./xiaoliuren.js', 'runXiaoLiuRen'),
  feigong: lazy('./feigong.js', 'runFeiGong'),
  xiaochengtu: lazy('./xiaochengtu.js', 'runXiaoChengTu'),
  guice: lazy('./guice.js', 'runGuice'),
  zhengchuan: lazy('./zhengchuan.js', 'runZhengChuan'),
  astroextra: lazy('./astroextra.js', 'runAstroExtra'),
  progextra: lazy('./progextra.js', 'runProgExtra'),
  horary: lazy('./horary.js', 'runHoraryTool'),
  election: lazy('./election.js', 'runElectionTool'),
  guolao_moira: lazy('./guolaoMoira.js', 'runGuolaoMoira'),
};

export function listTools() {
  return Object.keys(TOOL_RUNNERS);
}

// 只加载模块、取出 runner，不跑：test/loadcheck.mjs 逐个解析，钉住「表里每一项都指向真实存在的导出」。
export async function resolveRunner(toolName) {
  const load = Object.prototype.hasOwnProperty.call(TOOL_RUNNERS, toolName) ? TOOL_RUNNERS[toolName] : undefined;
  if (!load) {
    throw new Error(`Unsupported horosa-core-js tool: ${toolName}`);
  }
  return load();
}

export async function runTool(toolName, payload) {
  const runner = await resolveRunner(toolName);
  return runner(payload);
}
