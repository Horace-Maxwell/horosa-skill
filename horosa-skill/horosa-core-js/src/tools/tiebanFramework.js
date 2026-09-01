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
// 时辰内第几刻：一时辰 120 分 = 8 刻 × 15′。时辰从**奇数**小时起（子 23、丑 1、寅 3…），
// 所以奇数小时取时内分钟、偶数小时要加 60。落在 1..8。
function keFromClock(hour, minute) {
  const h = Number(hour);
  const m = Number(minute);
  if (!Number.isFinite(h) || !Number.isFinite(m)) { return 1; }
  const offset = (((h % 2) + 2) % 2 === 1) ? m : 60 + m;
  return Math.min(8, Math.max(1, Math.floor(offset / 15) + 1));
}

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
    // 🔴 引擎读的是 `ke`（:253），从不读 `minute` —— 此前传 minute 等于没传：
    // `opts.ke` 恒 undefined → 刻恒为 1 → eightKe.active 恒高亮初刻、96 局（12 时辰 × 8 刻）
    // 塌缩成 12 个可达值，14:47 与 14:03 出同一局。刻分正是铁板神数的立身之本。
    ke: keFromClock(source.hour, source.minute),
  });
  if (!framework) {
    return {
      text: '',
      data: { ok: false, error: { code: 'incomplete_four_pillars', message: '四柱不全（需 year/month/day/hour），框架推演层不出。' } },
    };
  }
  const lines = buildTiebanFrameworkSnapshot(framework) || [];
  return { text: Array.isArray(lines) ? lines.join('\n') : `${lines}` };
}
