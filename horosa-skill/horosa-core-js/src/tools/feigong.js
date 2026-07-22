// 飞宫小奇门 formatter —— 时上起青龙·甲乘龙飞九宫，纯函数进程内计算，零后端。
// 局为【冻结值】：起支（时支/选支/数取/年支）一经定局即不重起；命宫年龄性别只重排命宫目。
// 占时起局（时支 + 日干支）由 service.py 前置 /nongli/time 派生后传入，JS 层不发 HTTP（AGENTS §4）。
import { resolveQiZhi, buildJu } from '../vendor/feigong/feigongJu.js';
import { buildFeiGongSnapshotText } from '../vendor/feigong/feigongSnapshot.js';

function insufficient(normalized, reason, message) {
  return {
    tool: 'feigong',
    technique: 'feigong',
    input_normalized: normalized,
    data: { ok: false, reason, message: message || '' },
    snapshot_text: '',
  };
}

export function runFeiGong(payload) {
  const input = payload && typeof payload === 'object' ? payload : {};
  const qiMode = input.qiMode || 'hour';
  const qiZhi = input.qiZhi
    || resolveQiZhi({ mode: qiMode, hourZhi: input.hourZhi, zhi: input.zhi, num: input.num, yearZhi: input.yearZhi });
  const dayGan = input.dayGan || null;
  const dayZhi = input.dayZhi || null;
  const mingGender = input.mingGender === 'female' ? 'female' : 'male';
  const koujing = input.koujing === 'yi' ? 'yi' : 'zheng';
  const opts = {
    askEvent: `${input.askEvent ?? ''}`.trim(),
    mingAge: input.mingAge != null ? Math.trunc(Number(input.mingAge)) : null,
    mingGender,
    liuYueMonth: input.liuYueMonth != null ? Math.trunc(Number(input.liuYueMonth)) : null,
    koujing,
    timeLines: Array.isArray(input.timeLines) ? input.timeLines : [],
  };
  const normalized = {
    qiMode, qiZhi, dayGan, dayZhi,
    mingAge: opts.mingAge, mingGender, liuYueMonth: opts.liuYueMonth, koujing,
    askEvent: opts.askEvent || null,
  };
  if (!qiZhi) {
    return insufficient(normalized, 'invalid_qizhi', 'feigong requires a resolvable 起支 (qiZhi via mode hour/manualZhi/manualNum/yearZhi).');
  }
  const ju = buildJu({ zhi: qiZhi, dayGan, dayZhi });
  if (!ju) {
    return insufficient(normalized, 'buildju_failed', 'feigong could not build 局 from the given 起支/日干支.');
  }
  const snapshot_text = buildFeiGongSnapshotText(ju, opts);
  return {
    tool: 'feigong',
    technique: 'feigong',
    input_normalized: normalized,
    data: {
      qiZhi: ju.qiZhi,
      jianZhi: ju.jianZhi,
      longGong: ju.longGong,
      dayGan,
      dayZhi,
      zhongGong: ju.tianGan.zhongGong,
    },
    snapshot_text,
  };
}
