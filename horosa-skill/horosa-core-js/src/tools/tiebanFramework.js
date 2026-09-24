import {
  buildTiebanFramework,
  buildTiebanFrameworkSnapshot,
} from '../vendor/tieban/tiebanFrameworkLocal.js';

/**
 * 铁板神数「框架推演层」五段（流派刻制 / 考刻六亲 / 八卦滚 / 批断顺序 / 借用子系统）。
 *
 * kinastro 后端出盘面与条文，这一层是上游前端按四柱本地推演的（刻分 / 三元 / 八卦滚等），
 * 与盘面互补。后端响应里的 `pillars` 就是它要的四柱。
 *
 * payload: { pillars: [{key,ganzhi}…] 或 fourPillars: {year,month,day,hour}, birthYear, gender,
 *            tiebanSchool, tiebanKeSystem, tiebanKe }
 * return : { text }
 *
 * 口径与上游无头挂载逐项相同（KinAstroMain.buildKinAstroSnapshotForFields :329-346）：
 *   school  = tiebanSchool   || 'south'
 *   keSystem= tiebanKeSystem || 'qing8'
 *   ke      = tiebanKe（空=1，即「初刻」）
 *   gender  = gender（未给按 '1' 男）
 * 🔴 考刻是占者按六亲佐证「考」出来后手定的刻位，**不由钟点换算**：此前本工具按时分折算清八刻、读的又是
 * 上游不存在的 school/keSystem 键——十二刻·斗宫 9–12 刻永远到不了、流派/刻制旋钮一个都不生效（sync311 F8）。
 */
export function runTiebanFramework(payload) {
  const source = payload || {};
  let fourPillars = source.fourPillars;
  if (!fourPillars && Array.isArray(source.pillars)) {
    fourPillars = {};
    for (const item of source.pillars) {
      if (item && item.key && item.ganzhi) {
        fourPillars[item.key] = item.ganzhi;
      }
    }
  }
  const rawKe = source.tiebanKe;
  const ke = rawKe !== undefined && rawKe !== null && rawKe !== '' ? Number(rawKe) : 1;
  const framework = buildTiebanFramework(fourPillars, {
    school: source.tiebanSchool || 'south',
    keSystem: source.tiebanKeSystem || 'qing8',
    ke,
    gender: source.gender !== undefined && source.gender !== null ? source.gender : '1',
    birthYear: Number(source.birthYear) || 0,
  });
  if (!framework) {
    return {
      text: '',
      data: { ok: false, error: { code: 'incomplete_four_pillars', message: '四柱不全（需 year/month/day/hour），框架推演层不出。' } },
    };
  }
  const lines = buildTiebanFrameworkSnapshot(framework) || [];
  return {
    text: Array.isArray(lines) ? lines.join('\n') : `${lines}`,
    data: { ok: true, school: framework.school, keSystem: framework.keSystem, ke: framework.ke },
  };
}
