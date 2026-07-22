// 皇极轨策 · 时方 —— 方应（可算）+ 时方神煞（古籍未载其表，标缺不补）。
//
// ── 何谓「时方」 ────────────────────────────────────────────────
// 古籍论先后天，于「时方」有两层，且两层的处境截然不同：
//
//  ① 方应 —— 十应之一，法在古籍明载，可算：
//     「以体为主，看来占之人在何方位上，即看其所坐立之方位。宜生体卦，又宜与体比和，
//       则吉；如克体卦则凶，如体卦生之，亦不吉矣。」
//     即以所在之方配后天八卦，以其卦为用、本卦之体为主，仍走体用四诀 → 本层实现之。
//
//  ② 时方神煞 —— 「于六十甲子之日，取其时方之魁、破、败、亡、灭迹等，以助决断」。
//     🔴 其【表】不在本古籍：古籍只出其名目与一则占例（某日某时为「灭迹」、某方为
//        「祸害」），而明言此表载于另一辑本。名目有而取法无 → 无从复原。
//        故本层【显式标缺】，绝不臆补 —— 造一张查不到出处的神煞表，比不做更坏。
//
// ── 何以另立「数系」一档 ────────────────────────────────────────
// 两传本之别，恰在此时方神煞用与不用：
//   · 前身本（周易数一路）其占例【用】时方神煞；
//   · 后出定本【删去】之 —— 且非为藏私，是编者以为「历象选时并于周易不相涉，不可用也」，
//     故意剔除。定本更因删之而改了应期（同一占例，旧本断三日、定本断二十一日）。
// 故「数系」不是装饰：择周易数则参时方一层，择梅花则一概不参。两存而不代裁。
// 五行生克之判尽在 tiYongShengKe 内（其自带 ELEM_OF 与生/克），此处不另造一套 —— 两套必漂。
import { tiYongShengKe } from './guiceDuanfa.js';

/** 后天八卦方位 —— 占者所坐立之方，配卦 */
export const FANG_WEI = [
	{ key: 'S', label: '南', gua: '离' },
	{ key: 'N', label: '北', gua: '坎' },
	{ key: 'E', label: '东', gua: '震' },
	{ key: 'W', label: '西', gua: '兑' },
	{ key: 'SE', label: '东南', gua: '巽' },
	{ key: 'SW', label: '西南', gua: '坤' },
	{ key: 'NW', label: '西北', gua: '乾' },
	{ key: 'NE', label: '东北', gua: '艮' },
];
export const FANG_BY_KEY = FANG_WEI.reduce((m, f) => { m[f.key] = f; return m; }, {});

/** 🔴 时方神煞之名目 —— 有名而无表（其表载于另一辑本），故只出名、不出断 */
export const SHI_FANG_SHEN_SHA_NAMES = ['魁', '破', '败', '亡', '灭迹'];

/**
 * 方应：以所坐立之方配后天八卦为用、本卦之体为主，走体用四诀。
 * @param {string} tiGua 体卦（八卦名）
 * @param {string} fangKey 方位键（FANG_WEI 之 key）；未录则返 null（显式标缺，不臆断）
 */
export function fangYing(tiGua, fangKey) {
	const f = FANG_BY_KEY[fangKey];
	if (!tiGua || !f) return null;
	const sk = tiYongShengKe(tiGua, f.gua);
	if (!sk) return null;
	return { fang: f.label, gua: f.gua, ti: tiGua, key: sk.key, duan: sk.duan, ji: sk.ji };
}

/**
 * 时方一层之全。古籍之「时方」本是一物两层，故此处亦分两层，各由其开关掌之：
 *   · 方应   —— 法在古籍明载，可算（恒出，随「参时方」开关）；
 *   · 时方神煞 —— 「取其【时方之】魁、破、败、亡、灭迹」，与方应同属时方一门，
 *                 表却载于另一辑本 → 由「参神煞」开关掌其出与不出，出亦只出名目与标缺。
 * @param {object} p { tiGua, fangKey, shuXi, shenSha }
 * @returns null 表示整层不参（梅花一路）
 */
export function shiFang({ tiGua, fangKey, shuXi, shenSha } = {}) {
	// 梅花一路不参时方 —— 定本明言其「不可用」,故择梅花即整层不出(非出个空壳)
	if (shuXi === 'meihua') return null;
	return {
		ying: fangYing(tiGua, fangKey),
		fangMissing: !FANG_BY_KEY[fangKey],
		// 🔴 不参神煞则并此块亦不出 —— 出一个恒「标缺」的空块 = 又一个死控件
		shenSha: shenSha ? {
			names: SHI_FANG_SHEN_SHA_NAMES.slice(),
			missing: true,
			note: '古籍只出其名目与一则占例，其表载于另一辑本 —— 取法无从复原，本轮标缺不臆补',
		} : null,
	};
}

export default { fangYing, shiFang, FANG_WEI, FANG_BY_KEY, SHI_FANG_SHEN_SHA_NAMES };
