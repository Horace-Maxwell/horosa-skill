// 小六壬 formatter —— 三数起三传（主流六宫/道门九宫），纯函数进程内计算，零后端。
// 起课为【冻结值】：三数一经起出即不重起，改流派只重排判读。占时起数（农历月/日/时支序）由
// service.py 前置 /nongli/time 派生后作 nums 传入，JS 层不发 HTTP（AGENTS §4）。
import { qiKe } from '../vendor/xiaoliuren/xiaoliurenKe.js';
import { buildXiaoLiuRenSnapshotText } from '../vendor/xiaoliuren/xiaoliurenSnapshot.js';

function insufficient(normalized, reason, message) {
  return {
    tool: 'xiaoliuren',
    technique: 'xiaoliuren',
    input_normalized: normalized,
    data: { ok: false, reason, message: message || '' },
    snapshot_text: '',
  };
}

export function runXiaoLiuRen(payload) {
  const input = payload && typeof payload === 'object' ? payload : {};
  const nums = Array.isArray(input.nums) ? input.nums.map((v) => Math.trunc(Number(v))) : null;
  const school = input.school === 'dao' ? 'dao' : 'main';
  const showOneThree = input.showOneThree === undefined || input.showOneThree === null ? true : !!input.showOneThree;
  const askEvent = `${input.askEvent ?? ''}`.trim();
  const timeLines = Array.isArray(input.timeLines) ? input.timeLines : [];
  const normalized = { nums, school, showOneThree, askEvent: askEvent || null };
  if (!nums || nums.length !== 3 || nums.some((v) => !Number.isFinite(v) || v < 1)) {
    return insufficient(normalized, 'invalid_nums', 'xiaoliuren requires three positive integers (nums=[月,日,时]).');
  }
  const ke = qiKe({ m: nums[0], d: nums[1], h: nums[2], school });
  if (!ke) {
    return insufficient(normalized, 'qike_failed', 'xiaoliuren could not derive 三传 from the given numbers.');
  }
  const snapshot_text = buildXiaoLiuRenSnapshotText(ke, askEvent, { showOneThree, timeLines });
  return {
    tool: 'xiaoliuren',
    technique: 'xiaoliuren',
    input_normalized: normalized,
    data: { school: ke.school, nums: ke.nums, chuan: ke.chuan, analysis: ke.analysis },
    snapshot_text,
  };
}
