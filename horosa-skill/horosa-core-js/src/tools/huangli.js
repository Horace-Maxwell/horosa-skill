import { buildHuangliSnapshotByDate } from '../vendor/calendar/huangliSnapshot.js';

/**
 * 老黄历日课十段（起盘信息 / 今日宜忌 / 值神值宿 / 彭祖百忌 / 吉神凶煞 / 冲煞·胎神·方位 /
 * 时辰吉凶 / 物候·六曜·数九三伏 / 流年年神方位 / 方法说明）。
 *
 * 上游这支是**纯前端本地推演、零后端往返**（`huangliDay.js` 顶部明写），数据全部来自
 * `lunar-javascript` 与 `fengshui/zeri.js` 的择日表，所以 headless 侧不需要任何 HTTP。
 *
 * payload: { year, month, day, hour? }（hour 为 0-23 整点小时，缺省 12；影响 [时辰吉凶] 的当前时标记）
 * return : { text }
 */
export function runHuangli(payload) {
  const source = payload && typeof payload === 'object' ? payload : {};
  const year = Number(source.year);
  const month = Number(source.month);
  const day = Number(source.day);
  if (!Number.isFinite(year) || !Number.isFinite(month) || !Number.isFinite(day)) {
    return { text: '' };
  }
  const hour = Number.isFinite(Number(source.hour)) ? Number(source.hour) : 12;
  const text = buildHuangliSnapshotByDate(year, month, day, hour) || '';
  return { text };
}

export default runHuangli;
