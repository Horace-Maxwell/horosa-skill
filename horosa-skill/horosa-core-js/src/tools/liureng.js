const ZI_LIST = ['子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥'];
const GAN_LIST = ['甲', '乙', '丙', '丁', '戊', '己', '庚', '辛', '壬', '癸'];
const SIGN_TO_YUE = {
  Aries: '戌',
  Taurus: '酉',
  Gemini: '申',
  Cancer: '未',
  Leo: '午',
  Virgo: '巳',
  Libra: '辰',
  Scorpio: '卯',
  Sagittarius: '寅',
  Capricorn: '丑',
  Aquarius: '子',
  Pisces: '亥',
  牡羊: '戌',
  白羊: '戌',
  金牛: '酉',
  双子: '申',
  巨蟹: '未',
  狮子: '午',
  室女: '巳',
  处女: '巳',
  天秤: '辰',
  天蝎: '卯',
  射手: '寅',
  摩羯: '丑',
  宝瓶: '子',
  水瓶: '子',
  双鱼: '亥',
};

const SUMMER_ZI_LIST = ['巳', '午', '未', '申', '酉', '戌'];
const YANG_ZI = ['子', '寅', '辰', '午', '申', '戌'];
const YING_ZI = ['丑', '卯', '巳', '未', '酉', '亥'];
const YANG_GAN = ['甲', '丙', '戊', '庚', '壬'];
const TIAN_JIANG = ['贵人', '螣蛇', '朱雀', '六合', '勾陈', '青龙', '天空', '白虎', '太常', '玄武', '太阴', '天后'];
const GAN_JI_ZI = {
  甲: '寅',
  乙: '辰',
  丙: '巳',
  丁: '未',
  戊: '巳',
  己: '未',
  庚: '申',
  辛: '戌',
  壬: '亥',
  癸: '丑',
};
const ZI_HAN_GAN = {
  寅: '甲',
  辰: '乙',
  巳: '丙戊',
  未: '丁己',
  申: '庚',
  戌: '辛',
  亥: '壬',
  丑: '癸',
};
const DAY_GUI = {
  甲: '丑',
  乙: '子',
  丙: '亥',
  丁: '亥',
  戊: '丑',
  己: '子',
  庚: '丑',
  辛: '午',
  壬: '巳',
  癸: '巳',
};
const NIGHT_GUI = {
  甲: '未',
  乙: '申',
  丙: '酉',
  丁: '酉',
  戊: '未',
  己: '申',
  庚: '未',
  辛: '寅',
  壬: '卯',
  癸: '卯',
};
const GAN_HE = {
  甲: '己',
  乙: '庚',
  丙: '辛',
  丁: '壬',
  戊: '癸',
  己: '甲',
  庚: '乙',
  辛: '丙',
  壬: '丁',
  癸: '戊',
};
const ZI_MENG = ['寅', '申', '巳', '亥'];
const ZI_ZONG = ['子', '午', '卯', '酉'];
const ZI_XING = {
  子: '卯',
  丑: '戌',
  寅: '巳',
  卯: '子',
  辰: '辰',
  巳: '申',
  午: '午',
  未: '丑',
  申: '寅',
  酉: '酉',
  戌: '未',
  亥: '亥',
};
const ZI_CONG = {
  子: '午',
  丑: '未',
  寅: '申',
  卯: '酉',
  辰: '戌',
  巳: '亥',
  午: '子',
  未: '丑',
  申: '寅',
  酉: '卯',
  戌: '辰',
  亥: '巳',
};
const ZI_YI_MA = {
  子: '寅',
  丑: '亥',
  寅: '申',
  卯: '巳',
  辰: '寅',
  巳: '亥',
  午: '申',
  未: '巳',
  申: '寅',
  酉: '亥',
  戌: '申',
  亥: '巳',
};
const ZI_SANG_HE = {
  子: ['申', '辰'],
  丑: ['酉', '巳'],
  寅: ['戌', '午'],
  卯: ['亥', '未'],
  辰: ['子', '申'],
  巳: ['丑', '酉'],
  午: ['寅', '戌'],
  未: ['卯', '亥'],
  申: ['辰', '子'],
  酉: ['巳', '丑'],
  戌: ['午', '寅'],
  亥: ['未', '卯'],
};
const GAN_ZI_RESTRAIN = {
  甲: ['戊', '己', '辰', '戌', '丑', '未'],
  乙: ['戊', '己', '辰', '戌', '丑', '未'],
  丙: ['庚', '辛', '申', '酉'],
  丁: ['庚', '辛', '申', '酉'],
  戊: ['壬', '癸', '子', '亥'],
  己: ['壬', '癸', '子', '亥'],
  庚: ['甲', '乙', '寅', '卯'],
  辛: ['甲', '乙', '寅', '卯'],
  壬: ['丙', '丁', '巳', '午'],
  癸: ['丙', '丁', '巳', '午'],
  子: ['丙', '丁', '巳', '午'],
  丑: ['壬', '癸', '子', '亥'],
  寅: ['戊', '己', '辰', '戌', '丑', '未'],
  卯: ['戊', '己', '辰', '戌', '丑', '未'],
  辰: ['壬', '癸', '子', '亥'],
  巳: ['庚', '辛', '申', '酉'],
  午: ['庚', '辛', '申', '酉'],
  未: ['壬', '癸', '子', '亥'],
  申: ['甲', '乙', '寅', '卯'],
  酉: ['甲', '乙', '寅', '卯'],
  戌: ['壬', '癸', '子', '亥'],
  亥: ['丙', '丁', '巳', '午'],
};
const ZI_LIU_QIN = {
  子: { 甲: '父母', 乙: '父母', 丙: '官鬼', 丁: '官鬼', 戊: '妻财', 己: '妻财', 庚: '子孙', 辛: '子孙', 壬: '兄弟', 癸: '兄弟' },
  丑: { 甲: '妻财', 乙: '妻财', 丙: '子孙', 丁: '子孙', 戊: '兄弟', 己: '兄弟', 庚: '父母', 辛: '父母', 壬: '官鬼', 癸: '官鬼' },
  寅: { 甲: '兄弟', 乙: '兄弟', 丙: '父母', 丁: '父母', 戊: '官鬼', 己: '官鬼', 庚: '妻财', 辛: '妻财', 壬: '子孙', 癸: '子孙' },
  卯: { 甲: '兄弟', 乙: '兄弟', 丙: '父母', 丁: '父母', 戊: '官鬼', 己: '官鬼', 庚: '妻财', 辛: '妻财', 壬: '子孙', 癸: '子孙' },
  辰: { 甲: '妻财', 乙: '妻财', 丙: '子孙', 丁: '子孙', 戊: '兄弟', 己: '兄弟', 庚: '父母', 辛: '父母', 壬: '官鬼', 癸: '官鬼' },
  巳: { 甲: '子孙', 乙: '父母', 丙: '兄弟', 丁: '兄弟', 戊: '父母', 己: '父母', 庚: '官鬼', 辛: '官鬼', 壬: '妻财', 癸: '妻财' },
  午: { 甲: '子孙', 乙: '父母', 丙: '兄弟', 丁: '兄弟', 戊: '父母', 己: '父母', 庚: '官鬼', 辛: '官鬼', 壬: '妻财', 癸: '妻财' },
  未: { 甲: '妻财', 乙: '妻财', 丙: '子孙', 丁: '子孙', 戊: '兄弟', 己: '兄弟', 庚: '父母', 辛: '父母', 壬: '官鬼', 癸: '官鬼' },
  申: { 甲: '官鬼', 乙: '官鬼', 丙: '妻财', 丁: '妻财', 戊: '子孙', 己: '子孙', 庚: '兄弟', 辛: '兄弟', 壬: '父母', 癸: '父母' },
  酉: { 甲: '官鬼', 乙: '官鬼', 丙: '妻财', 丁: '妻财', 戊: '子孙', 己: '子孙', 庚: '兄弟', 辛: '兄弟', 壬: '父母', 癸: '父母' },
  戌: { 甲: '妻财', 乙: '妻财', 丙: '子孙', 丁: '子孙', 戊: '兄弟', 己: '兄弟', 庚: '父母', 辛: '父母', 壬: '官鬼', 癸: '官鬼' },
  亥: { 甲: '父母', 乙: '父母', 丙: '官鬼', 丁: '官鬼', 戊: '妻财', 己: '妻财', 庚: '子孙', 辛: '子孙', 壬: '兄弟', 癸: '兄弟' },
};

function valueText(value) {
  if (value === undefined || value === null || value === '') {
    return '无';
  }
  if (Array.isArray(value)) {
    return value.join('、') || '无';
  }
  if (typeof value === 'object') {
    if (value.ganzi) {
      return `${value.ganzi}`;
    }
    if (value.cell) {
      return `${value.cell}`;
    }
    return JSON.stringify(value);
  }
  return `${value}`;
}

function branchOf(value) {
  const match = `${value || ''}`.match(/[子丑寅卯辰巳午未申酉戌亥]/);
  return match ? match[0] : '';
}

function stemOf(value) {
  const match = `${value || ''}`.match(/[甲乙丙丁戊己庚辛壬癸]/);
  return match ? match[0] : '';
}

function normalizeChart(payload) {
  const chart = payload.chart && payload.chart.chart ? payload.chart.chart : payload.chart;
  const liureng = payload.liureng || {};
  const chartObj = chart && typeof chart === 'object' ? { ...chart } : {};
  chartObj.nongli = {
    ...(liureng.nongli || {}),
    ...(chartObj.nongli || {}),
  };
  if (!chartObj.nongli.dayGanZi && liureng.fourColumns && liureng.fourColumns.day) {
    chartObj.nongli.dayGanZi = valueText(liureng.fourColumns.day.ganzi || liureng.fourColumns.day);
  }
  if (!chartObj.nongli.time && liureng.fourColumns && liureng.fourColumns.time) {
    chartObj.nongli.time = valueText(liureng.fourColumns.time.ganzi || liureng.fourColumns.time);
  }
  if (chartObj.isDiurnal === undefined || chartObj.isDiurnal === null) {
    chartObj.isDiurnal = payload.isDiurnal !== undefined && payload.isDiurnal !== null ? !!payload.isDiurnal : true;
  }
  return chartObj;
}

function getChartYue(chartObj, explicitYue) {
  if (branchOf(explicitYue)) {
    return branchOf(explicitYue);
  }
  const objects = Array.isArray(chartObj.objects) ? chartObj.objects : [];
  const sun = objects.find((item) => item && (item.id === 'Sun' || item.id === '日' || item.name === 'Sun' || item.name === '日'));
  return sun ? (SIGN_TO_YUE[sun.sign] || branchOf(sun.sign)) : '';
}

function getGuiZi(chartObj, guirengType) {
  const dayGan = stemOf(chartObj?.nongli?.dayGanZi);
  if (!dayGan) {
    return '';
  }
  return (chartObj.isDiurnal ? DAY_GUI : NIGHT_GUI)[dayGan] || '';
}

function buildLayout(payload, chartObj) {
  if (!chartObj?.nongli?.dayGanZi || !chartObj?.nongli?.time) {
    return null;
  }
  const yue = getChartYue(chartObj, payload.yue);
  const timezi = branchOf(chartObj.nongli.time);
  if (!yue || !timezi) {
    return null;
  }
  const yueIdx = ZI_LIST.indexOf(yue);
  const timeIdx = ZI_LIST.indexOf(timezi);
  if (yueIdx < 0 || timeIdx < 0) {
    return null;
  }
  const downZi = ZI_LIST.slice();
  const upZi = ZI_LIST.slice();
  const yueIndexs = [];
  const delta = yueIdx - timeIdx;
  for (let i = 0; i < 12; i += 1) {
    const idx = (i + delta + 12) % 12;
    yueIndexs[i] = idx;
    upZi[i] = ZI_LIST[idx];
  }
  const houseTianJiang = TIAN_JIANG.slice();
  const guizi = getGuiZi(chartObj, payload.guirengType ?? 0);
  let houseidx = 0;
  for (let i = 0; i < 12; i += 1) {
    if (ZI_LIST[yueIndexs[i]] === guizi) {
      houseidx = i;
      break;
    }
  }
  const housezi = ZI_LIST[houseidx];
  if (SUMMER_ZI_LIST.includes(housezi)) {
    for (let i = 0; i < 12; i += 1) {
      houseTianJiang[i] = TIAN_JIANG[(houseidx - i + 12) % 12];
    }
  } else {
    for (let i = 0; i < 12; i += 1) {
      houseTianJiang[i] = TIAN_JIANG[(i - houseidx + 12) % 12];
    }
  }
  return { yue, timezi, guizi, downZi, upZi, houseTianJiang };
}

function buildKe(layout, chartObj) {
  const result = { raw: [], lines: [] };
  const dayGanZi = chartObj?.nongli?.dayGanZi || '';
  const daygan = stemOf(dayGanZi);
  const dayzi = branchOf(dayGanZi);
  if (!layout || !daygan || !dayzi || !GAN_JI_ZI[daygan]) {
    return result;
  }
  const make = (down) => {
    const idx = layout.downZi.indexOf(down);
    return idx >= 0 ? [layout.houseTianJiang[idx], layout.upZi[idx], down] : ['', '', down];
  };
  const ke1 = make(GAN_JI_ZI[daygan]);
  const ke2 = make(ke1[1]);
  const ke3 = make(dayzi);
  const ke4 = make(ke3[1]);
  result.raw = [
    [ke1[0], ke1[1], daygan],
    ke2,
    ke3,
    ke4,
  ];
  ['一课', '二课', '三课', '四课'].forEach((name, index) => {
    const item = result.raw[index];
    result.lines.push(`${name}：地盘=${item[2] || '无'}，天盘=${item[1] || '无'}，贵神=${item[0] || '无'}`);
  });
  return result;
}

function uniqueZiList(items) {
  return [...new Set((items || []).filter(Boolean))];
}

function isRestrain(left, right) {
  return (GAN_ZI_RESTRAIN[left] || []).includes(right);
}

function sameYingYang(gan, ziAry) {
  const target = YANG_GAN.includes(gan) ? YANG_ZI : YING_ZI;
  const data = (ziAry || []).filter((item) => target.includes(item));
  if (data.length) {
    return { cnt: data.length, data };
  }
  return { cnt: 0, data: ziAry || [] };
}

function getXun(gan, zi) {
  const ganIdx = GAN_LIST.indexOf(gan);
  const ziIdx = ZI_LIST.indexOf(zi);
  const firstZiIdx = (ziIdx - ganIdx + 12) % 12;
  const lastZiIdx = (ziIdx + 9 - ganIdx) % 12;
  if (firstZiIdx === 0) {
    return ZI_LIST.slice(0, 10);
  }
  const delta = 12 - firstZiIdx;
  if (delta >= 10) {
    return ZI_LIST.slice(firstZiIdx, lastZiIdx + 1);
  }
  return ZI_LIST.slice(firstZiIdx, 12).concat(ZI_LIST.slice(0, lastZiIdx + 1));
}

class SanChuanBuilder {
  constructor(layout, ke, chartObj) {
    this.layout = layout;
    this.ke = ke;
    this.nongli = chartObj.nongli || {};
    this.upZi = layout.upZi;
    this.downZi = layout.downZi;
    this.tianJiang = layout.houseTianJiang;
  }

  getCuang(cuang0) {
    const idx1 = this.downZi.indexOf(cuang0);
    const cuang1 = idx1 >= 0 ? this.upZi[idx1] : '';
    const idx2 = this.downZi.indexOf(cuang1);
    const cuang2 = idx2 >= 0 ? this.upZi[idx2] : '';
    return [cuang0, cuang1, cuang2];
  }

  getSeHaiCount(cuang) {
    let count = 0;
    let upidx = this.upZi.indexOf(cuang);
    let downidx = this.downZi.indexOf(cuang);
    if (upidx < 0 || downidx < 0) {
      return count;
    }
    downidx = downidx >= upidx ? downidx : downidx + 12;
    for (let i = upidx; i < downidx; i += 1) {
      const zi = this.downZi[i % 12];
      if (isRestrain(zi, cuang)) {
        count += 1;
      }
      const hidden = ZI_HAN_GAN[zi];
      if (hidden) {
        for (const gan of hidden.split('')) {
          if (isRestrain(gan, cuang)) {
            count += 1;
          }
        }
      }
    }
    return count;
  }

  getSeHais(cuangs) {
    const ziList = uniqueZiList(cuangs);
    if (!ziList.length) {
      return null;
    }
    let max = 0;
    let stack = [];
    for (const zi of ziList) {
      const count = this.getSeHaiCount(zi);
      if (count > max) {
        max = count;
        stack = [zi];
      } else if (count === max) {
        stack.push(zi);
      }
    }
    if (stack.length === 1) {
      return { cuang: this.getCuang(stack[0]), name: '涉害课' };
    }
    let selected = stack.filter((zi) => ZI_MENG.includes(this.downZi[this.upZi.indexOf(zi)]));
    if (selected.length === 1) {
      return { cuang: this.getCuang(selected[0]), name: '见机课' };
    }
    selected = stack.filter((zi) => ZI_ZONG.includes(this.downZi[this.upZi.indexOf(zi)]));
    if (selected.length === 1) {
      return { cuang: this.getCuang(selected[0]), name: '察微课' };
    }
    const daygan = stemOf(this.nongli.dayGanZi);
    const ke = YANG_GAN.includes(daygan) ? this.ke[0] : this.ke[2];
    return { cuang: this.getCuang(ke[1]), name: '缀瑕课' };
  }

  isJinKe0() {
    const stack = uniqueZiList(this.ke.filter((item) => isRestrain(item[2], item[1])).map((item) => item[1]));
    if (stack.length === 1) {
      return { cuang: this.getCuang(stack[0]), name: '重审课' };
    }
    if (stack.length > 1) {
      const yinyang = sameYingYang(stemOf(this.nongli.dayGanZi), stack);
      const data = uniqueZiList(yinyang.data);
      return yinyang.cnt === 1 ? { cuang: this.getCuang(data[0]), name: '比用课' } : this.getSeHais(data);
    }
    return null;
  }

  isJinKe1() {
    const stack = uniqueZiList(this.ke.filter((item) => isRestrain(item[1], item[2])).map((item) => item[1]));
    if (stack.length === 1) {
      return { cuang: this.getCuang(stack[0]), name: '元首课' };
    }
    if (stack.length > 1) {
      const yinyang = sameYingYang(stemOf(this.nongli.dayGanZi), stack);
      const data = uniqueZiList(yinyang.data);
      return yinyang.cnt === 1 ? { cuang: this.getCuang(data[0]), name: '知一课' } : this.getSeHais(data);
    }
    return null;
  }

  isYaoKe0() {
    const gan = this.ke[0][2];
    const stack = uniqueZiList(this.ke.slice(1).filter((item) => isRestrain(item[1], gan)).map((item) => item[1]));
    if (stack.length === 1) {
      return { cuang: this.getCuang(stack[0]), name: '蒿矢课' };
    }
    if (stack.length > 1) {
      const yinyang = sameYingYang(gan, stack);
      const data = uniqueZiList(yinyang.data);
      return yinyang.cnt === 1 ? { cuang: this.getCuang(data[0]), name: '蒿矢课' } : this.getSeHais(data);
    }
    return null;
  }

  isYaoKe1() {
    const gan = this.ke[0][2];
    const stack = uniqueZiList(this.ke.slice(1).filter((item) => isRestrain(gan, item[1])).map((item) => item[1]));
    if (stack.length === 1) {
      return { cuang: this.getCuang(stack[0]), name: '弹射课' };
    }
    if (stack.length > 1) {
      const yinyang = sameYingYang(gan, stack);
      const data = uniqueZiList(yinyang.data);
      return yinyang.cnt === 1 ? { cuang: this.getCuang(data[0]), name: '弹射课' } : this.getSeHais(data);
    }
    return null;
  }

  isMaoXing() {
    const gan = this.ke[0][2];
    if (YANG_GAN.includes(gan)) {
      return { cuang: [this.upZi[this.downZi.indexOf('酉')], this.ke[2][1], this.ke[0][1]], name: '虎视课' };
    }
    return { cuang: [this.downZi[this.upZi.indexOf('酉')], this.ke[0][1], this.ke[2][1]], name: '掩目课' };
  }

  isFuYin() {
    if (this.downZi[0] !== this.upZi[0]) {
      return null;
    }
    const jin = this.isJinKe0() || this.isJinKe1();
    if (jin) {
      const cuang0 = this.ke[0][1];
      const cuang1 = ZI_XING[cuang0] === cuang0 ? this.ke[2][1] : ZI_XING[cuang0];
      const cuang2 = ZI_XING[cuang1] === cuang1 ? ZI_CONG[cuang1] : ZI_XING[cuang1];
      return { cuang: [cuang0, cuang1, cuang2], name: '不虞课' };
    }
    const gan = this.ke[0][2];
    const cuang0 = YANG_GAN.includes(gan) ? this.ke[0][1] : this.ke[2][1];
    const cuang1 = ZI_XING[cuang0] === cuang0 ? (YANG_GAN.includes(gan) ? this.ke[2][1] : this.ke[0][1]) : ZI_XING[cuang0];
    const cuang2 = ZI_XING[cuang1] === cuang1 ? ZI_CONG[cuang1] : ZI_XING[cuang1];
    return { cuang: [cuang0, cuang1, cuang2], name: YANG_GAN.includes(gan) ? '自任课' : '杜传课' };
  }

  isFangYin() {
    if (this.downZi[0] !== ZI_CONG[this.upZi[0]]) {
      return null;
    }
    const jin = this.isJinKe0() || this.isJinKe1();
    if (jin) {
      return { ...jin, name: '无依课' };
    }
    const dayzi = branchOf(this.nongli.dayGanZi);
    return { cuang: [ZI_YI_MA[dayzi], this.ke[2][1], this.ke[0][1]], name: '无亲课' };
  }

  isBieZe() {
    const repeated = this.ke[0][1] === this.ke[1][1] || this.ke[0][1] === this.ke[3][1]
      || this.ke[1][1] === this.ke[2][1] || this.ke[1][1] === this.ke[3][1]
      || this.ke[2][1] === this.ke[3][1];
    if (!repeated) {
      return null;
    }
    const direct = this.isJinKe0() || this.isJinKe1() || this.isYaoKe0() || this.isYaoKe1();
    if (direct) {
      return direct;
    }
    const gan = this.ke[0][2];
    const dayzi = branchOf(this.nongli.dayGanZi);
    const cuang0 = YANG_GAN.includes(gan)
      ? this.upZi[this.downZi.indexOf(GAN_JI_ZI[GAN_HE[gan]])]
      : (ZI_SANG_HE[dayzi] || [])[1];
    return { cuang: [cuang0, this.ke[0][1], this.ke[0][1]], name: '芜淫课' };
  }

  isBaZhuang() {
    if (this.ke[0][1] !== this.ke[2][1]) {
      return null;
    }
    const direct = this.isJinKe0() || this.isJinKe1();
    if (direct) {
      return direct;
    }
    const gan = this.ke[0][2];
    const idx = YANG_GAN.includes(gan)
      ? (this.upZi.indexOf(this.ke[0][1]) + 2) % 12
      : (this.upZi.indexOf(this.ke[3][1]) + 10) % 12;
    return { cuang: [this.upZi[idx], this.ke[0][1], this.ke[0][1]], name: '八专课' };
  }

  getSangCuang() {
    return this.isFuYin()
      || this.isFangYin()
      || this.isJinKe0()
      || this.isJinKe1()
      || this.isBaZhuang()
      || this.isYaoKe0()
      || this.isYaoKe1()
      || this.isBieZe()
      || this.isMaoXing();
  }

  build() {
    const base = this.getSangCuang();
    if (!base || !Array.isArray(base.cuang)) {
      return null;
    }
    const daygan = stemOf(this.nongli.dayGanZi);
    const dayzi = branchOf(this.nongli.dayGanZi);
    const xun = getXun(daygan, dayzi);
    const xunGanMap = {};
    xun.slice(0, GAN_LIST.length).forEach((zi, index) => {
      xunGanMap[zi] = GAN_LIST[index];
    });
    const gz = [];
    const tianJiang = [];
    const liuQin = [];
    for (let i = 0; i < 3; i += 1) {
      const zi = base.cuang[i];
      const idx = this.upZi.indexOf(zi);
      tianJiang[i] = idx >= 0 ? this.tianJiang[idx] : '无';
      liuQin[i] = (ZI_LIU_QIN[zi] || {})[daygan] || '无';
      gz[i] = xunGanMap[zi] ? `${xunGanMap[zi]}${zi}` : `空${zi}`;
    }
    return { ...base, cuang: gz, tianJiang, liuQin };
  }
}

function buildSanChuan(layout, keRaw, chartObj) {
  if (!layout || !Array.isArray(keRaw) || keRaw.length !== 4 || !chartObj?.nongli?.dayGanZi) {
    return null;
  }
  return new SanChuanBuilder(layout, keRaw, chartObj).build();
}

function mapSectionLines(title, obj) {
  const lines = [`[${title}]`];
  if (!obj || typeof obj !== 'object' || !Object.keys(obj).length) {
    lines.push('无', '');
    return lines;
  }
  Object.keys(obj).forEach((key) => {
    lines.push(`${key.split('(')[0]}：${valueText(obj[key])}`);
  });
  lines.push('');
  return lines;
}

function buildSnapshotText(payload, liureng, runyear, chartObj, data) {
  const lines = [];
  const nongli = liureng.nongli || chartObj.nongli || {};
  const cols = liureng.fourColumns || {};
  lines.push('[起盘信息]');
  lines.push(`日期：${payload.date || '—'} ${payload.time || '—'}`);
  lines.push(`时区：${payload.zone || '—'}`);
  lines.push(`经纬度：${payload.lon || '—'} ${payload.lat || '—'}`);
  if (nongli.birth) {
    lines.push(`真太阳时：${nongli.birth}`);
  }
  if (cols.year || cols.month || cols.day || cols.time) {
    lines.push(`四柱：${valueText(cols.year)}年 ${valueText(cols.month)}月 ${valueText(cols.day)}日 ${valueText(cols.time)}时`);
  }
  lines.push('贵人体系：六壬法贵人');
  lines.push(`十二盘式：${data.panStyleName || '无'}`);
  lines.push('');

  lines.push('[十二盘式]');
  if (data.layout) {
    lines.push(`月将：${data.layout.yue}；占时：${data.layout.timezi}；贵人：${data.layout.guizi}`);
  } else {
    lines.push('无');
  }
  lines.push('');

  lines.push('[十二地盘/十二天盘/十二贵神对应]');
  if (data.layout) {
    for (let i = 0; i < 12; i += 1) {
      lines.push(`${i + 1}. 地盘${data.layout.downZi[i]} -> 天盘${data.layout.upZi[i]} -> 贵神${data.layout.houseTianJiang[i]}`);
    }
  } else {
    lines.push('无');
  }
  lines.push('');

  lines.push('[四课]');
  if (data.ke && data.ke.lines.length) {
    lines.push(...data.ke.lines);
  } else {
    lines.push('无');
  }
  lines.push('');

  lines.push('[三传]');
  if (data.sanChuan) {
    lines.push(`课式：${valueText(data.sanChuan.name)}`);
    ['初传', '中传', '末传'].forEach((name, index) => {
      lines.push(`${name}：干支=${data.sanChuan.cuang[index] || '无'}；六亲=${data.sanChuan.liuQin[index] || '无'}；贵神=${data.sanChuan.tianJiang[index] || '无'}`);
    });
  } else {
    lines.push('无');
  }
  lines.push('');

  lines.push('[行年]');
  if (runyear) {
    lines.push(`行年干支：${valueText(runyear.year)}`);
    lines.push(`年龄：${valueText(runyear.age)}岁`);
  } else {
    lines.push('无');
  }
  lines.push('');

  lines.push(...mapSectionLines('旬日', liureng.xun));
  lines.push(...mapSectionLines('旺衰', liureng.season));
  lines.push(...mapSectionLines('基础神煞', liureng.gods));
  lines.push(...mapSectionLines('干煞', liureng.godsGan));
  lines.push(...mapSectionLines('月煞', liureng.godsMonth));
  lines.push(...mapSectionLines('支煞', liureng.godsZi));
  lines.push(...mapSectionLines('岁煞', liureng.godsYear && liureng.godsYear.taisui1 ? liureng.godsYear.taisui1 : liureng.godsYear));
  lines.push('[十二长生]', '无', '');
  lines.push('[大格]', data.sanChuan ? `课式：${data.sanChuan.name}` : '无', '');
  lines.push('[小局]', '无', '');
  lines.push('[参考]', '无', '');
  lines.push('[概览]');
  if (data.sanChuan) {
    lines.push(`四课、三传已由本地 headless 六壬引擎根据离线盘面生成。`);
    lines.push(`三传：${data.sanChuan.cuang.join(' -> ')}；贵神：${data.sanChuan.tianJiang.join(' -> ')}`);
  } else {
    lines.push('本次盘面材料不足，无法生成四课三传；请检查日期、时间、时区、经纬度和本地 runtime 状态。');
  }
  return lines.join('\n').trim();
}

export function runLiureng(payload) {
  const liureng = payload.liureng || {};
  const runyear = payload.runyear || null;
  const chartObj = normalizeChart(payload);
  const layout = buildLayout(payload, chartObj);
  const ke = buildKe(layout, chartObj);
  const sanChuan = buildSanChuan(layout, ke.raw, chartObj);
  const data = {
    layout,
    ke,
    sanChuan,
    panStyleName: layout ? `${layout.yue}将加${layout.timezi}时` : '',
    runtime_note: 'local_headless_liureng',
  };
  return {
    data,
    snapshot_text: buildSnapshotText(payload, liureng, runyear, chartObj, data),
  };
}
