// 六爻引擎最小依赖：从上游 utils/helper 抽出 littleEndian / randomNum（供 gua 引擎装卦用）。
import { randomInt } from '../utils/trueRandom.js';
export function littleEndian(bits) {
  let n = 0;
  for (let i = 0; i < bits.length; i++) {
    const v = bits[i];
    if (v < 0) {
      return -1;
    }
    n = n | (v << i);
  }
  return n;
}

// [0, 10^exp) 上等概率的整数(缺省四位)。起卦 / 掷骰用:取自系统随机源(见 trueRandom.js),不是 Math.random。
// （v3.15.0 上游「随机起卦一律真随机」：helper.randomNum 改走 trueRandom.randomInt。skill 的无头起卦是确定性起法，
//  不经这里；同步只为与上游同口径，环境无系统随机源时抛错而不是悄悄退回伪随机。）
export function randomNum(exp) {
  const expn = exp > 0 ? exp : 4;
  return randomInt(Math.pow(10, expn));
}
