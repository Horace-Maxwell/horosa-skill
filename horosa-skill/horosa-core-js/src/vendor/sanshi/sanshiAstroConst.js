// 三式合一纯逻辑段（vendored SanShiUnitedMain.js）所需的 AstroConst 子集 —— **逐值抽自上游** constants/AstroConst.js
// （:14-23 行星、:66-77 十二星座、:79-81 ASC/MC，原值原序）。
// 为什么不用 src/constants/AstroConst.js：那份共享 shim 没有 URANUS / NEPTUNE / PLUTO / MC —— SanShiUnitedMain 的
// MAIN_STAR_IDS 会收进四个 undefined（外圈「星盘」行静默少天王/海王/冥王/天顶），同一 shim 为键的 AstroText.AstroMsgCN
// 也因此从未落下这四个键。共享 shim 另有七政/卜卦/天星等消费方，不在本处改动它。curated：上游源 sha 由 manifest 看守。

export const SUN = 'Sun'
export const MOON = 'Moon'
export const MERCURY = 'Mercury'
export const VENUS = 'Venus'
export const MARS = 'Mars'
export const JUPITER = 'Jupiter'
export const SATURN = 'Saturn'
export const URANUS = 'Uranus'
export const NEPTUNE = 'Neptune'
export const PLUTO = 'Pluto'

export const ARIES = 'Aries'
export const TAURUS = 'Taurus'
export const GEMINI = 'Gemini'
export const CANCER = 'Cancer'
export const LEO = 'Leo'
export const VIRGO = 'Virgo'
export const LIBRA = 'Libra'
export const SCORPIO = 'Scorpio'
export const SAGITTARIUS = 'Sagittarius'
export const CAPRICORN = 'Capricorn'
export const AQUARIUS = 'Aquarius'
export const PISCES = 'Pisces'

export const ASC = 'Asc'
export const MC = 'MC'
