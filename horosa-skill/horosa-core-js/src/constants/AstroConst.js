// 极简 AstroConst shim（headless 六壬/七政 vendor 依赖闭合用）。
// 上游 星阙 AstroConst.js 含 1100+ 行占星常量；headless 路径只需 LIST_SIGNS（星座顺序，
// 供 LRConst.getSignZi 把行星星座 → 地支）。AstroColor 是 UI 配色，headless 不渲染，给空 stub
// 仅为满足 import + getSigColor/getHouseColor 不抛（被调用时返回 undefined，无害）。

export const ARIES = 'Aries';
export const TAURUS = 'Taurus';
export const GEMINI = 'Gemini';
export const CANCER = 'Cancer';
export const LEO = 'Leo';
export const VIRGO = 'Virgo';
export const LIBRA = 'Libra';
export const SCORPIO = 'Scorpio';
export const SAGITTARIUS = 'Sagittarius';
export const CAPRICORN = 'Capricorn';
export const AQUARIUS = 'Aquarius';
export const PISCES = 'Pisces';

export const LIST_SIGNS = [
  ARIES, TAURUS, GEMINI, CANCER, LEO, VIRGO, LIBRA,
  SCORPIO, SAGITTARIUS, CAPRICORN, AQUARIUS, PISCES,
];

export const SUN = 'Sun';
export const MOON = 'Moon';

// UI 配色 stub（headless 不渲染）；SignFill / 按星座取色被调用时返回 undefined。
export const AstroColor = { SignFill: {} };
