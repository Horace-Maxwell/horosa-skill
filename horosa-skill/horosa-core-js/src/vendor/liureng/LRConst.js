export const ZiList = ['子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥'];
export const GanList = ['甲', '乙', '丙', '丁', '戊', '己', '庚', '辛', '壬', '癸'];

export const YangZi = ['子', '寅', '辰', '午', '申', '戌'];
export const YingZi = ['丑', '卯', '巳', '未', '酉', '亥'];
export const YangGan = ['甲', '丙', '戊', '庚', '壬'];
export const YingGan = ['乙', '丁', '己', '辛', '癸'];

export const DayGui = {
  甲: '未',
  乙: '申',
  丙: '酉',
  丁: '亥',
  戊: '午',
  己: '子',
  庚: '丑',
  辛: '寅',
  壬: '卯',
  癸: '巳',
};

export const NightGui = {
  甲: '丑',
  乙: '子',
  丙: '亥',
  丁: '酉',
  戊: '寅',
  己: '申',
  庚: '未',
  辛: '午',
  壬: '巳',
  癸: '卯',
};

export const DayGuiLiuReng = {
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

export const NightGuiLiuReng = {
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

export const DayGuiDunJia = {
  甲: '未',
  乙: '申',
  丙: '酉',
  丁: '亥',
  戊: '丑',
  己: '子',
  庚: '丑',
  辛: '寅',
  壬: '卯',
  癸: '巳',
};

export const NightGuiDunJia = {
  甲: '丑',
  乙: '子',
  丙: '亥',
  丁: '酉',
  戊: '未',
  己: '申',
  庚: '未',
  辛: '午',
  壬: '巳',
  癸: '卯',
};

export const GuiRengs = [
  { day: DayGuiLiuReng, night: NightGuiLiuReng },
  { day: DayGuiDunJia, night: NightGuiDunJia },
  { day: DayGui, night: NightGui },
];

export const ZiHe = {
  子: '丑',
  丑: '子',
  寅: '亥',
  卯: '戌',
  辰: '酉',
  巳: '申',
  午: '未',
  未: '午',
  申: '巳',
  酉: '辰',
  戌: '卯',
  亥: '寅',
};

export const GanZiWuXing = {
  戊: '土',
  己: '土',
  辰: '土',
  戌: '土',
  丑: '土',
  未: '土',
  庚: '金',
  辛: '金',
  申: '金',
  酉: '金',
  壬: '水',
  癸: '水',
  亥: '水',
  子: '水',
  甲: '木',
  乙: '木',
  寅: '木',
  卯: '木',
  丙: '火',
  丁: '火',
  午: '火',
  巳: '火',
};
