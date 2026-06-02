// Minimal 星阙 AstroConst / AstroText stub for the vendored progression builders (balbillus etc.).
// These builders only need the 7 classical planet ids + LIST_SIGNS + the AstroTxtMsg display map — NOT
// the full 1128-line AstroConst tree. Keeping this tiny avoids vendoring AstroColor0-8 etc.
export const SUN = 'Sun';
export const MOON = 'Moon';
export const MERCURY = 'Mercury';
export const VENUS = 'Venus';
export const MARS = 'Mars';
export const JUPITER = 'Jupiter';
export const SATURN = 'Saturn';
export const ASC = 'Asc';
export const MC = 'MC';
export const LIST_SIGNS = [
  'Aries', 'Taurus', 'Gemini', 'Cancer', 'Leo', 'Virgo',
  'Libra', 'Scorpio', 'Sagittarius', 'Capricorn', 'Aquarius', 'Pisces',
];

// = 星阙 AstroText.AstroTxtMsg (planet/sign/point subset the progression builders display).
export const AstroTxtMsg = {
  Sun: '太阳', Moon: '月亮', Mercury: '水星', Venus: '金星', Mars: '火星',
  Jupiter: '木星', Saturn: '土星', Uranus: '天王星', Neptune: '海王星', Pluto: '冥王星',
  'North Node': '北交', 'South Node': '南交', 'Pars Fortuna': '福点', Chiron: '凯龙',
  Asc: '上升', Desc: '下降', MC: '中天', IC: '天底',
  Aries: '白羊', Taurus: '金牛', Gemini: '双子', Cancer: '巨蟹', Leo: '狮子', Virgo: '室女',
  Libra: '天秤', Scorpio: '天蝎', Sagittarius: '射手', Capricorn: '摩羯', Aquarius: '宝瓶', Pisces: '双鱼',
};
