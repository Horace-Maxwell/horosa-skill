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
// 七政四余 政余格局 (guolaoMoira) 闭包 + AstroText 名表另需的对象 id（flatlib 标识，与排盘响应 objects[].id 一致）。
export const MERCURY = 'Mercury';
export const VENUS = 'Venus';
export const MARS = 'Mars';
export const JUPITER = 'Jupiter';
export const SATURN = 'Saturn';
export const NORTH_NODE = 'North Node';
export const SOUTH_NODE = 'South Node';
export const DARKMOON = 'Dark Moon';
export const PURPLE_CLOUDS = 'Purple Clouds';
export const ASC = 'Asc';
export const LIFEMASTERDEG74 = 'LifeMasterDeg74';

// UI 配色 stub（headless 不渲染）；SignFill / 按星座取色被调用时返回 undefined。
export const AstroColor = { SignFill: {} };

// 星座属性表（庙/旺/陷/落/三分主星）—— 三分主星推运(triplicityRulers) 用 SignsProp[sign].Trip/.Ruler/.Exalt/.Exile/.Fall。
// vendored verbatim from 星阙 AstroConst.SignsProp（只引用本文件已定义的 7 颗行星常量）。
export const SignsProp = {
    Aries:{
        Ruler: MARS,
        Exalt: SUN,
        Exile: VENUS,
        Fall: SATURN,
        Trip: [SUN, JUPITER, SATURN],
        FallDeg: 21,
        ExaltDeg: 19,
    },
    Taurus:{
        Ruler: VENUS,
        Exalt: MOON,
        Exile: MARS,
        Fall: null,
        Trip: [VENUS, MOON, MARS],
        FallDeg: null,
        ExaltDeg: 3,
    },
    Gemini:{
        Ruler: MERCURY,
        Exalt: null,
        Exile: JUPITER,
        Fall: null,
        Trip: [SATURN, MERCURY, JUPITER],
        FallDeg: 28,
        ExaltDeg: 15,
    },
    Cancer:{
        Ruler: MOON,
        Exalt: JUPITER,
        Exile: SATURN,
        Fall: MARS,
        Trip: [VENUS, MARS, MOON],
    },
    Leo:{
        Ruler: SUN,
        Exalt: null,
        Exile: SATURN,
        Fall: null,
        Trip: [SUN, JUPITER, SATURN],
        FallDeg: null,
        ExaltDeg: null,
    },
    Virgo:{
        Ruler: MERCURY,
        Exalt: MERCURY,
        Exile: JUPITER,
        Fall: VENUS,
        Trip: [VENUS, MOON, MARS],
        FallDeg: 27,
        ExaltDeg: 15,
    },
    Libra:{
        Ruler: VENUS,
        Exalt: SATURN,
        Exile: MARS,
        Fall: SUN,
        Trip: [SATURN, MERCURY, JUPITER],
        FallDeg: 19,
        ExaltDeg: 21,
    },
    Scorpio:{
        Ruler: MARS,
        Exalt: null,
        Exile: VENUS,
        Fall: MOON,
        Trip: [VENUS, MARS, MOON],
        FallDeg: 3,
        ExaltDeg: null,
    },
    Sagittarius:{
        Ruler: JUPITER,
        Exalt: null,
        Exile: MERCURY,
        Fall: null,
        Trip: [SUN, JUPITER, SATURN],
        FallDeg: null,
        ExaltDeg: null,
    },
    Capricorn:{
        Ruler: SATURN,
        Exalt: MARS,
        Exile: MOON,
        Fall: JUPITER,
        Trip: [VENUS, MOON, MARS],
        FallDeg: 15,
        ExaltDeg: 28,
    },
    Aquarius:{
        Ruler: SATURN,
        Exalt: null,
        Exile: SUN,
        Fall: null,
        Trip: [SATURN, MERCURY, JUPITER],
        FallDeg: null,
        ExaltDeg: null,
    },
    Pisces:{
        Ruler: JUPITER,
        Exalt: VENUS,
        Exile: MERCURY,
        Fall: MERCURY,
        Trip: [VENUS, MARS, MOON],
        FallDeg: 15,
        ExaltDeg: 27,
    },
};
