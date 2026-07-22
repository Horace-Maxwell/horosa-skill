// 小成图 formatter —— 洛书九宫佈局·正旁推·四象·应期·股市研判，纯函数进程内计算，零后端。
// 卦为【冻结值】：起卦（手动 manual / 两数 number / 股价 stock / 大衍 dayan / 占时 time）一经起出即不重起。
// 占时=梅花时间卦（年支序+农历月+日 为上数、加时支序为下数），由 service.py 前置 /nongli/time 算 upNum/loNum
// 后作 number 模式传入。大衍 dayan 须显式 seed 或 manualCounts，禁静默随机（不吐用户没见过的卦）。
import { qiGuaManual, qiGuaByNumbers, qiGuaByStock, qiGuaByDaYan } from '../vendor/xiaochengtu/xiaochengtuQiGua.js';
import { buildPan } from '../vendor/xiaochengtu/xiaochengtuPan.js';
import { buildXiaoChengTuSnapshotText } from '../vendor/xiaochengtu/xiaochengtuSnapshot.js';

function insufficient(normalized, reason, message) {
  return {
    tool: 'xiaochengtu',
    technique: 'xiaochengtu',
    input_normalized: normalized,
    data: { ok: false, reason, message: message || '' },
    snapshot_text: '',
  };
}

export function runXiaoChengTu(payload) {
  const input = payload && typeof payload === 'object' ? payload : {};
  const fa = input.qiguaFa || 'manual';
  const yongGong = input.yongGong != null ? Math.trunc(Number(input.yongGong)) : 1;
  const askEvent = `${input.askEvent ?? ''}`.trim();
  const timeLines = Array.isArray(input.timeLines) ? input.timeLines : [];
  const kline = input.kline && typeof input.kline === 'object' ? input.kline : null;
  const normalized = { qiguaFa: fa, yongGong, askEvent: askEvent || null };
  let qi = null;
  if (fa === 'manual') {
    qi = qiGuaManual({ up: input.up, lo: input.lo, dongYaos: Array.isArray(input.dongYaos) ? input.dongYaos : [] });
  } else if (fa === 'number' || fa === 'time') {
    qi = qiGuaByNumbers({ upNum: input.upNum, loNum: input.loNum, qiguaShu: input.qiguaShu || 'tiandi', dongYaos: Array.isArray(input.dongYaos) ? input.dongYaos : [] });
  } else if (fa === 'stock') {
    // 价格务必字符串传（保留末尾 0，如 '1563.60'）；qiGuaByStock 按位数起卦。
    qi = qiGuaByStock({ open: input.open, close: input.close });
  } else if (fa === 'dayan') {
    if ((input.seed === undefined || input.seed === null || input.seed === '') && !Array.isArray(input.manualCounts)) {
      return insufficient(normalized, 'dayan_seed_required', 'xiaochengtu dayan (大衍蓍草) mode requires an explicit seed or manualCounts — no silent random cast.');
    }
    qi = qiGuaByDaYan({ seed: input.seed, manualCounts: input.manualCounts });
  } else {
    return insufficient(normalized, 'invalid_qiguaFa', `unknown qiguaFa: ${fa} (use manual/number/stock/dayan/time).`);
  }
  if (!qi || !qi.ben) {
    return insufficient(normalized, 'qigua_failed', 'xiaochengtu could not derive 本卦 from the given input.');
  }
  const pan = buildPan(qi);
  if (!pan) {
    return insufficient(normalized, 'buildpan_failed', 'xiaochengtu could not build the 九宫 layout.');
  }
  const snapshot_text = buildXiaoChengTuSnapshotText(pan, qi, { yongGong, askEvent, kline, timeLines });
  return {
    tool: 'xiaochengtu',
    technique: 'xiaochengtu',
    input_normalized: normalized,
    data: {
      mode: qi.mode,
      ben: qi.ben && qi.ben.name,
      zhi: qi.zhi && qi.zhi.name,
      dongYaos: qi.dongYaos || [],
      yongGong,
    },
    snapshot_text,
  };
}
