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
 * payload: { pillars: [{key,ganzhi}…] 或 fourPillars: {year,month,day,hour}, birthYear, gender, school, keSystem, minute }
 * return : { text }
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
  const framework = buildTiebanFramework(fourPillars, {
    school: source.school,
    keSystem: source.keSystem,
    birthYear: Number(source.birthYear) || 0,
    gender: source.gender,
    minute: Number(source.minute) || 0,
  });
  if (!framework) {
    return { text: '' };
  }
  const lines = buildTiebanFrameworkSnapshot(framework) || [];
  return { text: Array.isArray(lines) ? lines.join('\n') : `${lines}` };
}
