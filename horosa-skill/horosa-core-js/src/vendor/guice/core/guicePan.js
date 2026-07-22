// 皇极轨策 · 整合层 —— 起卦所得（冻结值）+ 设置 → 一盘之全。
//
// 🔴 中栏与右栏皆消费此一盘，故必同源、同时随设置而变 ——
//    从源头杜绝「改了选项某一栏不动」之病（非事后补显示）。
//
// 🔴 起卦所得（卦与动爻）为冻结值：报数/字占/时辰之所出，一经起出即不可按时重算 ——
//    重算即伪造一个不同之卦。故上层以 payload 存之，不入按时重排之列。
import { yanShu } from './guiceEngine.js';
import { guaBianAll } from './guiceGuaBian.js';
import { duanfa } from './guiceDuanfa.js';
import { shiYing } from './guiceShiYing.js';
import { calcDading } from './guiceDading.js';
import { lishi } from './guiceLishi.js';
import { shiFang } from './guiceShiFang.js';
import { normalizeGuiceSettings } from '../guiceSchools.js';
import { Gua64 } from '../../gua/GuaConst.js';

/**
 * 构一盘。
 *   gua   —— 起卦所得之冻结值 { up, lo, dongYao, fa, steps }
 *   ctx   —— 时地之context { yearZhi, monthZhi, lunarMonth, lunarDay, hourZhi, year, pillars, askEvent }
 *   settings —— 十开关
 *   shiyingInputs —— 十应之所录
 */
export function buildGuicePan({ gua, ctx = {}, settings, shiyingInputs = {} }) {
	const s = normalizeGuiceSettings(settings);
	if (!gua || !gua.up || !gua.lo || !gua.dongYao) return null;
	const { up, lo, dongYao } = gua;

	const yan = yanShu(up, lo, dongYao, { ...s, dayGan: ctx.dayGan });
	if (!yan) return null;
	const bian = guaBianAll(up, lo, dongYao);
	const duan = duanfa({ up, lo, dongYao, monthZhi: ctx.monthZhi, siwei: yan.siwei });
	const ying = shiYing({ up, lo, dongYao, set: s.shiyingSet, inputs: shiyingInputs });
	const shi = lishi({ year: ctx.year, monthZhi: ctx.monthZhi });
	// 时方一层：唯「参时方」开着、且非梅花一路时出之(定本明言梅花不用时方,故梅花下整层不出)。
	// 其内「方应」可算(以所坐立之方配后天八卦为用、体为主,走体用四诀);
	// 「时方神煞」有名而无表 → 显式标缺，不臆补(见 guiceShiFang 头注)。
	const fang = s.shiFang
		? shiFang({ tiGua: duan && duan.tiYong ? duan.tiYong.tiGua : null, fangKey: ctx.fangKey, shuXi: s.shuXi, shenSha: s.shenSha })
		: null;
	// 大定唯九畴数之系（或大定预设）用之；缺四柱则不出，不臆造
	const dading = (s.qiguaShu === 'jiuchou' || s.school === 'dading') && Array.isArray(ctx.pillars) && ctx.pillars.length === 4
		? calcDading({ pillars: ctx.pillars, up, lo, dadingTable: s.dadingTable })
		: null;

	return {
		module: 'guice',
		gua: { up, lo, dongYao, fa: gua.fa, steps: gua.steps || [], name: gua64NameOf(bian.ben.lines) },
		bianName: bian.bian ? gua64NameOf(bian.bian.lines) : null,
		yan, bian, duan, ying, lishi: shi, dading, shiFang: fang,
		settings: s, ctx,
		askEvent: ctx.askEvent || '',
	};
}

/** 六爻（bottom-first）→ 六十四卦之名（只此一处用六十四卦名；互卦之处绝不用） */
function gua64NameOf(lines) {
	if (!Array.isArray(lines) || lines.length !== 6) return null;
	const g = Gua64.find((x) => x.value && x.value.join('') === lines.join(''));
	return g ? g.name : null;
}

export default buildGuicePan;
