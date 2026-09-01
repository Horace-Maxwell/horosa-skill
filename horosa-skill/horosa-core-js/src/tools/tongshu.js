import { buildTongshuSnapshotText } from '../vendor/calendar/tongshuSnapshot.js';
import { DEFAULT_TONGSHU_SETTINGS } from '../vendor/calendar/tongshuSchools.js';

/**
 * 通书择日两段（通书择日 / 方法说明）。
 *
 * 五流派分派——董公 / 奇门叠数 / 三垣列宿 / 天元乌兔 / 三元玄空大卦——各自落到独立的断语表，
 * 同一天在不同流派下结论可以完全相反，所以 `school` 是结果敏感设置：Python 侧走
 * `ask_if_missing`，不静默取默认值。这里保留上游 DEFAULT_TONGSHU_SETTINGS 作为兜底，
 * 只是为了让缺参调用不炸，不代表可以省略询问。
 *
 * 同样是纯前端推演，零后端往返。
 *
 * payload: { date: 'YYYY-MM-DD', school?, event?, liexiuUse?, mingYear? }
 * return : { text }
 */
export function runTongshu(payload) {
  const source = payload && typeof payload === 'object' ? payload : {};
  const ymd = `${source.date || ''}`.trim();
  if (!ymd) {
    return { text: '' };
  }
  const settings = {
    ...DEFAULT_TONGSHU_SETTINGS,
    ...Object.fromEntries(
      ['school', 'event', 'liexiuUse', 'mingYear']
        .filter((k) => source[k] !== undefined && source[k] !== null && `${source[k]}` !== '')
        .map((k) => [k, source[k]]),
    ),
    date: ymd,
  };
  const text = buildTongshuSnapshotText(settings, ymd) || '';
  return { text };
}

export default runTongshu;
