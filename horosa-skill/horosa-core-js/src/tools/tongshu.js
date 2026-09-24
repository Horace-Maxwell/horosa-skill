import { buildTongshuSnapshotText } from '../vendor/calendar/tongshuSnapshot.js';
import { DEFAULT_TONGSHU_SETTINGS, TONGSHU_SCHOOLS, TONGSHU_SCHOOL_MAP } from '../vendor/calendar/tongshuSchools.js';

/**
 * 流派键核验（锚到引擎自带词表 TONGSHU_SCHOOLS，不手抄）。认不出的键上游 builder 会照印
 * 「流派：<原键>」+「（该流派待实现）」——看起来像一份结论，其实什么都没算。所以这里回结构化失败，
 * 由 Python 侧抛 tool.tongshu_unknown_school（v0.40 前 skill 文档把 sanyuan 写成三垣、xuankong 写成玄空，
 * 而引擎键是 sanyuanliexiu=三垣列宿 / sanyuan=三元玄空大卦，照文档传 xuankong 恰好落进这个坑）。
 */
export function tongshuSchoolCheck(school) {
  if (school === undefined || school === null || `${school}` === '' || TONGSHU_SCHOOL_MAP[school]) {
    return null;
  }
  return {
    ok: false,
    reason: 'unknown_school',
    message: `通书流派 ${school} 不在引擎词表内（${TONGSHU_SCHOOLS.map((s) => s.key).join(' / ')}）`,
    school: `${school}`,
    valid: TONGSHU_SCHOOLS.map((s) => ({ key: s.key, label: s.label })),
  };
}

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
  const bad = tongshuSchoolCheck(settings.school);
  if (bad) {
    return { text: '', data: { ...bad, ok: false } };
  }
  const text = buildTongshuSnapshotText(settings, ymd) || '';
  return { text };
}

export default runTongshu;
