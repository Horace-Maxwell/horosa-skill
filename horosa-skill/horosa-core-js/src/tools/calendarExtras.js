import { buildHuangliSnapshotText } from '../vendor/calendar/huangliSnapshot.js';
import { buildHuangliDay } from '../vendor/calendar/huangliDay.js';
import { buildTongshuSnapshotText } from '../vendor/calendar/tongshuSnapshot.js';
import { DEFAULT_TONGSHU_SETTINGS } from '../vendor/calendar/tongshuSchools.js';
import { buildRiziSnapshotText } from '../vendor/calendar/riziSnapshot.js';
import { personBazi, buildPersonalizedDates } from '../vendor/calendar/riziEngine.js';

/**
 * 黄历页的三个「子模块」段块，供 `calendar` 聚合键使用。
 *
 * 上游 `calendar` 是**页面聚合快照**：NongLi（走后端 /calendar/month）+ HuangLi + Tongshu + Rizi
 * 四子并出。后三子全是纯前端推演，这里一次跑完，Python 把它们插进 NongLi 那三段之后。
 *
 * 段的取舍（避免与 NongLi 段重复）：
 * - huangli：只取中间 8 段，丢掉它自带的 [起盘信息] 与 [方法说明]（calendar 已由 NongLi 提供）；
 * - tongshu：只取 [通书择日]，同样丢掉它的 [方法说明]；
 * - rizi：[日子馆·个性化择日] + [当事人八字]，**只有传了 persons 才产**（无当事人就没有个性化可言）。
 *
 * payload: {
 *   year, month, day, hour?,                       // 选中日
 *   tongshu?: {school, event, liexiuUse, mingYear},
 *   rizi?: {event, year, topN?, persons:[{name, date, time, gender, role}]}
 * }
 * return : { text }   // 已按上游段序拼好，段间空行分隔
 */
export function runCalendarExtras(payload) {
  const source = payload && typeof payload === 'object' ? payload : {};
  const year = Number(source.year);
  const month = Number(source.month);
  const day = Number(source.day);
  if (!Number.isFinite(year) || !Number.isFinite(month) || !Number.isFinite(day)) {
    return { text: '' };
  }
  const blocks = [];

  // —— 老黄历八段（去掉首尾两段，它们与 NongLi 的同名段重复）
  try {
    const hour = Number.isFinite(Number(source.hour)) ? Number(source.hour) : 12;
    const raw = buildHuangliSnapshotText(buildHuangliDay(year, month, day, hour)) || '';
    const kept = raw
      .split(/\n(?=\[)/)
      .filter((block) => !block.startsWith('[起盘信息]') && !block.startsWith('[方法说明]'));
    if (kept.length) {
      blocks.push(kept.join('\n').trim());
    }
  } catch (error) {
    /* 单子模块失败不带崩其余段 —— 与上游「取不到就不出该段」同口径 */
  }

  // —— 通书择日一段
  try {
    const ts = source.tongshu && typeof source.tongshu === 'object' ? source.tongshu : {};
    const ymd = `${year}-${`${month}`.padStart(2, '0')}-${`${day}`.padStart(2, '0')}`;
    const settings = { ...DEFAULT_TONGSHU_SETTINGS, ...ts, date: ymd };
    const raw = buildTongshuSnapshotText(settings, ymd) || '';
    const kept = raw.split(/\n(?=\[)/).filter((block) => block.startsWith('[通书择日]'));
    if (kept.length) {
      blocks.push(kept.join('\n').trim());
    }
  } catch (error) {
    /* 同上 */
  }

  // —— 日子馆两段（仅在给了当事人时产出）
  try {
    const rz = source.rizi && typeof source.rizi === 'object' ? source.rizi : null;
    const people = rz && Array.isArray(rz.persons) ? rz.persons : [];
    if (people.length) {
      // 上游 RiziMain.baziOf：person 本身保留，八字挂在它的 `bazi` 字段上（riziSnapshot 用
      // `persons.filter(p => p && p.bazi)` 决定 [当事人八字] 段出不出）。
      // 🔴 `time` 必须是**纯时刻**。下游 parseDateTime（baziLunarLocal.js:265）做
      // `time.split(':')` 后 Number()，传完整日期时间串时首段 '2020-01-01 14' → NaN → hour 恒 0，
      // 于是每个当事人都按 00:30 起盘、时柱恒子时、23 点日界永不触发；而这些喜忌又喂
      // scoreDayForPerson，整个 [日子馆·个性化择日] 排名都建立在错盘上。
      const persons = people.map((p) => {
        let bazi = null;
        try {
          bazi = personBazi({
            date: `${p.date || ''}`.slice(0, 10),
            time: `${p.time || '12:00:00'}`.slice(0, 8),
            gender: p.gender,
          });
        } catch (error) {
          bazi = null;
        }
        return { ...p, bazi };
      });
      const event = rz.event || 'marriage';
      const rzYear = Number(rz.year) || year;
      const result = buildPersonalizedDates({
        event,
        persons,
        year: rzYear,
        topN: Number(rz.topN) || 15,
      });
      const raw = buildRiziSnapshotText({ event, year: rzYear, persons, result }) || '';
      if (raw.trim()) {
        // 两处段头收拾：
        // (a) `[个性化吉日榜 Top N／全年候选 M]` 是**动态段头**，上游 preset 里也没有它 —— 写进
        //     preset 会因 N/M 随输入变化而永远对不上，不写又会被判 unknown。去掉该行让它的表格
        //     并入前一段 [日子馆·个性化择日]，内容一行不丢。
        // (b) rizi 自带的 [方法说明] 与 calendar 由 NongLi 提供的同名段重复，丢掉。
        const cleaned = raw
          .split(/\n(?=\[)/)
          .filter((block) => !block.startsWith('[方法说明]'))
          .join('\n')
          .replace(/^\[个性化吉日榜[^\]]*\]\n?/gm, '');
        if (cleaned.trim()) {
          blocks.push(cleaned.trim());
        }
      }
    }
  } catch (error) {
    /* 同上 */
  }

  return { text: blocks.join('\n\n') };
}

export default runCalendarExtras;
