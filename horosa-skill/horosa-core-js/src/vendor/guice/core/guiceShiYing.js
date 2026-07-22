// 皇极轨策 · 三要十应 —— 纯函数。
//
// 三套名目并存（所载不同，故可切，见 SHIYING_SETS）：
//   ① 心易发微版（默认）：正应/互应/变应/方应/日应/外应/物应/天文/地理/人事
//   ② 梅花原书版：天时/地理/人事/时令/方卦/动物/静物/言语/声音/五色
//      —— 以体卦为主，内外卦参看：内不吉而外吉可解、内吉而外不吉反破
//   ③ 论事十大应·日辰秘文版：行/立/坐/卧/语/默/喜/怒/得/失
//
// 正应/互应/变应由卦自出（auto）；其余须由左栏据所见所闻而录 —— 古籍此处重在人之审量，
// 机不能代，故不臆造，缺者显式标「未录」。
import { SHIYING_SETS } from './guiceConst.js';
import { tiHuYongHu, guaBianAll } from './guiceGuaBian.js';
import { tiYongShengKe } from './guiceDuanfa.js';
import { Gua8 } from '../../gua/GuaConst.js';

export const SHIYING_SET_KEYS = Object.keys(SHIYING_SETS);

/** 自动派生之三应：正应=本之用、互应=用互、变应=变之用 —— 皆以体卦较之 */
export function autoYing(up, lo, dongYao) {
	const gu = Gua8.find((g) => g.name === up); const gl = Gua8.find((g) => g.name === lo);
	if (!gu || !gl) return null;
	const lines = [...gl.value, ...gu.value];
	const hu = tiHuYongHu(lines, dongYao);
	const all = guaBianAll(up, lo, dongYao);
	if (!hu || !all) return null;
	const bianYong = hu.tiZai === 'up' ? all.bian.lo : all.bian.up;
	return {
		zheng: { gua: hu.yongGua, ...tiYongShengKe(hu.tiGua, hu.yongGua) },
		hu: { gua: hu.yongHu, ...tiYongShengKe(hu.tiGua, hu.yongHu) },
		bian: { gua: bianYong, ...tiYongShengKe(hu.tiGua, bianYong) },
		tiGua: hu.tiGua,
	};
}

/**
 * 三要十应。
 * set    —— 三套之一（默认心易发微版）
 * inputs —— 各应之所录（键同 SHIYING_SETS[set].items[].key）；未录者显式标之，不臆造。
 */
export function shiYing({ up, lo, dongYao, set = 'xinyifawei', inputs = {} }) {
	const S = SHIYING_SETS[set] || SHIYING_SETS.xinyifawei;
	const auto = autoYing(up, lo, dongYao);
	const items = S.items.map((it) => {
		if (it.auto && auto) {
			const a = auto[it.key];
			return a
				? { ...it, gua: a.gua, key2: a.key, duan: a.duan, from: '卦自出' }
				: { ...it, from: '卦自出', missing: true };
		}
		const v = inputs[it.key];
		return v
			? { ...it, value: v, from: '所录' }
			: { ...it, from: '所录', missing: true, note: '未录 —— 此应须据所见所闻而录，机不能代' };
	});
	return {
		set, label: S.label, note: S.note || '', tiGua: auto ? auto.tiGua : null,
		items,
		recorded: items.filter((x) => !x.missing).length,
		total: items.length,
	};
}

export default { shiYing, autoYing, SHIYING_SET_KEYS };
