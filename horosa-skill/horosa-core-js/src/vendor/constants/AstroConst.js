// 汉堡学派（Uranian）虚星表所需的 AstroConst 子集 —— **逐值抽自上游** `constants/AstroConst.js`。
// 两条边界规则（都踩过）：① 块的终点是「下一个顶层 export const」而非分号——上游多数常量不带结尾
// 分号，按分号切会把后续所有声明卷进来（Identifier already declared）；② 必须保持**上游原序**，
// LIST_URANIAN 之类的聚合常量引用了排在其后的符号，重排会 ReferenceError（before initialization）。
// AGENTS §5：这类表以 AstroConst.* 为键，手写猜值会静默变成 undefined 键，故只做逐值抽取。

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
export const CUPIDO = 'Cupido'
export const HADES = 'Hades'
export const ZEUS = 'Zeus'
export const KRONOS = 'Kronos'
export const APOLLON = 'Apollon'
export const ADMETOS = 'Admetos'
export const VULCANUS = 'Vulcanus'
export const POSEIDON = 'Poseidon'
export const LIST_URANIAN = [CUPIDO, HADES, ZEUS, KRONOS, APOLLON, ADMETOS, VULCANUS, POSEIDON]
// 白羊点 / 世界轴（World Axis）——恒为黄经 0°，汉堡学派与 AS/MC 同级的个人点；90°盘上 0/90/180/270 等价。
export const ARIES_POINT = 'AriesPoint'
export const NORTH_NODE = 'North Node'
export const VERTEX = 'Vertex'
export const EAST_POINT = 'EastPoint'  // 赤道上升(子午局 1 宫头);量化盘可选点,读后端 houseFrames.eastPoint
export const ASC = 'Asc'
export const MC = 'MC'
