const BAGUA = {
  乾: { name: '乾', cname: '天', elem: '金', value: [1, 1, 1], symbol: '☰' },
  兑: { name: '兑', cname: '泽', elem: '金', value: [1, 1, 0], symbol: '☱' },
  离: { name: '离', cname: '火', elem: '火', value: [1, 0, 1], symbol: '☲' },
  震: { name: '震', cname: '雷', elem: '木', value: [1, 0, 0], symbol: '☳' },
  巽: { name: '巽', cname: '风', elem: '木', value: [0, 1, 1], symbol: '☴' },
  坎: { name: '坎', cname: '水', elem: '水', value: [0, 1, 0], symbol: '☵' },
  艮: { name: '艮', cname: '山', elem: '土', value: [0, 0, 1], symbol: '☶' },
  坤: { name: '坤', cname: '地', elem: '土', value: [0, 0, 0], symbol: '☷' },
};

const DEFAULT_SELECTION = {
  taiyin: '巽',
  taiyang: '坤',
  shaoyang: '震',
  shaoyin: '震',
};

const HEXAGRAM_NAMES = {
  '乾-乾': '乾为天',
  '乾-兑': '天泽履',
  '乾-离': '天火同人',
  '乾-震': '天雷无妄',
  '乾-巽': '天风姤',
  '乾-坎': '天水讼',
  '乾-艮': '天山遁',
  '乾-坤': '天地否',
  '兑-乾': '泽天夬',
  '兑-兑': '兑为泽',
  '兑-离': '泽火革',
  '兑-震': '泽雷随',
  '兑-巽': '泽风大过',
  '兑-坎': '泽水困',
  '兑-艮': '泽山咸',
  '兑-坤': '泽地萃',
  '离-乾': '火天大有',
  '离-兑': '火泽睽',
  '离-离': '离为火',
  '离-震': '火雷噬嗑',
  '离-巽': '火风鼎',
  '离-坎': '火水未济',
  '离-艮': '火山旅',
  '离-坤': '火地晋',
  '震-乾': '雷天大壮',
  '震-兑': '雷泽归妹',
  '震-离': '雷火丰',
  '震-震': '震为雷',
  '震-巽': '雷风恒',
  '震-坎': '雷水解',
  '震-艮': '雷山小过',
  '震-坤': '雷地豫',
  '巽-乾': '风天小畜',
  '巽-兑': '风泽中孚',
  '巽-离': '风火家人',
  '巽-震': '风雷益',
  '巽-巽': '巽为风',
  '巽-坎': '风水涣',
  '巽-艮': '风山渐',
  '巽-坤': '风地观',
  '坎-乾': '水天需',
  '坎-兑': '水泽节',
  '坎-离': '水火既济',
  '坎-震': '水雷屯',
  '坎-巽': '水风井',
  '坎-坎': '坎为水',
  '坎-艮': '水山蹇',
  '坎-坤': '水地比',
  '艮-乾': '山天大畜',
  '艮-兑': '山泽损',
  '艮-离': '山火贲',
  '艮-震': '山雷颐',
  '艮-巽': '山风蛊',
  '艮-坎': '山水蒙',
  '艮-艮': '艮为山',
  '艮-坤': '山地剥',
  '坤-乾': '地天泰',
  '坤-兑': '地泽临',
  '坤-离': '地火明夷',
  '坤-震': '地雷复',
  '坤-巽': '地风升',
  '坤-坎': '地水师',
  '坤-艮': '地山谦',
  '坤-坤': '坤为地',
};

const SHENG = { 木: '火', 火: '土', 土: '金', 金: '水', 水: '木' };
const KE = { 木: '土', 土: '水', 水: '火', 火: '金', 金: '木' };

// 京房八宫 palace element per hexagram, mirrored from 星阙 GuaConst.js (`Gua64[i].house.elem`).
// 统摄法 derives a hexagram's element from its 京房本宫五行 — NOT its upper trigram. These disagree
// for 32 of 64 hexagrams (e.g. 火地晋 → 金 not 火; 天泽履 → 土 not 金), so the palace table is required.
const HEXAGRAM_PALACE_ELEM = (() => {
  const palaces = [
    ['金', ['乾为天', '天风姤', '天山遁', '天地否', '风地观', '山地剥', '火地晋', '火天大有']], // 乾宫
    ['水', ['坎为水', '水泽节', '水雷屯', '水火既济', '泽火革', '雷火丰', '地火明夷', '地水师']], // 坎宫
    ['土', ['艮为山', '山火贲', '山天大畜', '山泽损', '火泽睽', '天泽履', '风泽中孚', '风山渐']], // 艮宫
    ['木', ['震为雷', '雷地豫', '雷水解', '雷风恒', '地风升', '水风井', '泽风大过', '泽雷随']], // 震宫
    ['木', ['巽为风', '风天小畜', '风火家人', '风雷益', '天雷无妄', '火雷噬嗑', '山雷颐', '山风蛊']], // 巽宫
    ['火', ['离为火', '火山旅', '火风鼎', '火水未济', '山水蒙', '风水涣', '天水讼', '天火同人']], // 离宫
    ['土', ['坤为地', '地雷复', '地泽临', '地天泰', '雷天大壮', '泽天夬', '水天需', '水地比']], // 坤宫
    ['金', ['兑为泽', '泽水困', '泽地萃', '泽山咸', '水山蹇', '地山谦', '雷山小过', '雷泽归妹']], // 兑宫
  ];
  const map = {};
  for (const [elem, names] of palaces) {
    for (const name of names) map[name] = elem;
  }
  return map;
})();

function normalizeSelection(payload) {
  const next = { ...DEFAULT_SELECTION };
  for (const key of Object.keys(next)) {
    const value = payload?.[key];
    if (value && BAGUA[value]) {
      next[key] = value;
    }
  }
  return next;
}

function getBagua(name) {
  return BAGUA[name] || BAGUA[DEFAULT_SELECTION.taiyin];
}

function getBaguaByLines(lines) {
  return Object.values(BAGUA).find((item) => item.value.join(',') === lines.join(',')) || null;
}

function buildHex(upper, lower) {
  const lines = [...lower.value, ...upper.value];
  const name = HEXAGRAM_NAMES[`${upper.name}-${lower.name}`] || `${upper.cname}${lower.cname}`;
  return {
    name,
    upper,
    lower,
    lines,
    symbol: `${upper.symbol}${lower.symbol}`,
  };
}

function buildMutualHex(hex) {
  const lines = [hex.lines[1], hex.lines[2], hex.lines[3], hex.lines[2], hex.lines[3], hex.lines[4]];
  const lower = getBaguaByLines(lines.slice(0, 3)) || BAGUA.乾;
  const upper = getBaguaByLines(lines.slice(3, 6)) || BAGUA.乾;
  return buildHex(upper, lower);
}

function buildOppositeHex(hex) {
  const lines = hex.lines.map((item) => (item === 1 ? 0 : 1));
  const lower = getBaguaByLines(lines.slice(0, 3)) || BAGUA.乾;
  const upper = getBaguaByLines(lines.slice(3, 6)) || BAGUA.乾;
  return buildHex(upper, lower);
}

function hexElem(hex) {
  // Mirror 星阙 getHexElem: the 京房本宫 palace element, falling back to the upper trigram only if
  // the hexagram name is unknown (it never is — HEXAGRAM_PALACE_ELEM covers all 64).
  return (hex && HEXAGRAM_PALACE_ELEM[hex.name]) || (hex && hex.upper ? hex.upper.elem : '');
}

function relationByElem(leftElem, rightElem) {
  if (leftElem === rightElem) return '思同实';
  if (SHENG[leftElem] === rightElem) return '思生实';
  if (KE[leftElem] === rightElem) return '思克实';
  if (SHENG[rightElem] === leftElem) return '实生思';
  if (KE[rightElem] === leftElem) return '实克思';
  return '思同实';
}

function buildSixLineSummary(leftHex, rightHex) {
  const rows = [];
  for (let index = 5; index >= 0; index -= 1) {
    rows.push(`第${index + 1}爻：左${leftHex.lines[index] === 1 ? '阳' : '阴'} / 右${rightHex.lines[index] === 1 ? '阳' : '阴'} / ${leftHex.lines[index] === rightHex.lines[index] ? '不变' : '已变'}`);
  }
  return rows.join('\n');
}

function buildSnapshot(model) {
  return [
    '[本卦]',
    `左卦：${model.baseLeft.name}（上卦${model.baseLeft.upper.name} / 下卦${model.baseLeft.lower.name}）`,
    `右卦：${model.baseRight.name}（上卦${model.baseRight.upper.name} / 下卦${model.baseRight.lower.name}）`,
    '',
    '[六爻]',
    buildSixLineSummary(model.baseLeft, model.baseRight),
    '',
    '[潜藏]',
    `左潜藏：${model.mutualLeft.name}`,
    `右潜藏：${model.mutualRight.name}`,
    '',
    '[亲和]',
    `左亲和：${model.oppositeLeft.name}`,
    `右亲和：${model.oppositeRight.name}`,
  ].join('\n').trim();
}

export function runTongSheFa(payload) {
  const selected = normalizeSelection(payload || {});
  const taiyin = getBagua(selected.taiyin);
  const taiyang = getBagua(selected.taiyang);
  const shaoyang = getBagua(selected.shaoyang);
  const shaoyin = getBagua(selected.shaoyin);
  const baseLeft = buildHex(taiyin, shaoyang);
  const baseRight = buildHex(taiyang, shaoyin);
  const mutualLeft = buildMutualHex(baseLeft);
  const mutualRight = buildMutualHex(baseRight);
  const oppositeLeft = buildOppositeHex(baseLeft);
  const oppositeRight = buildOppositeHex(baseRight);
  const data = {
    selected,
    baseLeft,
    baseRight,
    mutualLeft,
    mutualRight,
    oppositeLeft,
    oppositeRight,
    left_elem: hexElem(baseLeft),
    right_elem: hexElem(baseRight),
    main_relation: relationByElem(hexElem(baseLeft), hexElem(baseRight)),
  };
  return {
    tool: 'tongshefa',
    technique: 'tongshefa',
    input_normalized: selected,
    data,
    snapshot_text: buildSnapshot(data),
  };
}
