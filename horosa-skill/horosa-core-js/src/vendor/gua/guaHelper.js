// 六爻引擎最小依赖：从上游 utils/helper 抽出 littleEndian / randomNum（供 gua 引擎装卦用）。
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

export function randomNum(exp) {
  const expn = exp > 0 ? exp : 4;
  const p = Math.pow(10, expn);
  return Math.floor(Math.random() * p);
}
