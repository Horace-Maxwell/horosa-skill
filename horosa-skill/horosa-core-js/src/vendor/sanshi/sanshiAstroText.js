// 三式合一纯逻辑段（vendored SanShiUnitedMain.js 的 msg()）所需的 AstroText.AstroMsgCN 子集 ——
// **逐行抽自上游** constants/AstroText.js（:92-101 十行星、:128 上升、:130 天顶，原文原序），即 MAIN_STAR_IDS 十二体的中文名。
// msg(key) = AstroMsgCN[key] || key：共享 src/constants/AstroText.js 以缺 URANUS/NEPTUNE/PLUTO/MC 的共享 AstroConst shim 为键，
// 这四个键从未落下 → 外圈「星盘」行会印英文 id。键取本目录逐值抽出的 sanshiAstroConst.js。curated：上游源 sha 由 manifest 看守。
import * as AstroConst from './sanshiAstroConst.js';

export const AstroMsgCN = {};

AstroMsgCN[AstroConst.SUN] = '太阳';
AstroMsgCN[AstroConst.MOON] = '月亮';
AstroMsgCN[AstroConst.MERCURY] = '水星';
AstroMsgCN[AstroConst.VENUS] = '金星';
AstroMsgCN[AstroConst.MARS] = '火星';
AstroMsgCN[AstroConst.JUPITER] = '木星';
AstroMsgCN[AstroConst.SATURN] = '土星';
AstroMsgCN[AstroConst.URANUS] = '天王星';
AstroMsgCN[AstroConst.NEPTUNE] = '海王星';
AstroMsgCN[AstroConst.PLUTO] = '冥王星';
AstroMsgCN[AstroConst.ASC] = '上升';
AstroMsgCN[AstroConst.MC] = '天顶';
