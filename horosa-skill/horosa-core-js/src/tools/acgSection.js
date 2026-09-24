import { setAcgSnapshot, clearAcgSnapshot, buildAcgSectionText } from '../vendor/utils/acgSnapshot.js';

/**
 * 占星地图 [占星地图] 段（上游 utils/acgSnapshot.js，vendored 逐字）。
 *
 * 上游页面每次 /location/acg 响应后 `setAcgSnapshot(acgData, snapshotUiState(pointReport))`（AstroAcg.js:333），
 * aiExport 再 `buildAcgSectionText()` 拼进导出（aiExport.js:6823-6829）。headless 一次调用内走完同一对纯函数：
 * Python 取 /location/acg（+ 可选 /location/acgpoint）响应，uiState 与页面同形——
 *   { pointReport, paranMode, showStarParans, showLS, showGeodetic, geodeticZero }（AstroAcg.js:277-287）。
 *
 * payload: { acgData: <后端 ACGraph 响应>, uiState?: {...} }
 * return : { text }   // 首行为上游的 `【占星地图】` 段头；无 planets 时空串（上游同降级）
 */
export function runAcgSection(payload) {
  const source = payload && typeof payload === 'object' ? payload : {};
  clearAcgSnapshot();   // 模块级「最近一次地图状态」：同一进程内先清，杜绝串盘
  setAcgSnapshot(source.acgData || null, source.uiState && typeof source.uiState === 'object' ? source.uiState : {});
  const text = buildAcgSectionText() || '';
  clearAcgSnapshot();
  return { text };
}

export default runAcgSection;
