// 小六壬 · 起课与判读层 —— 三数起三传(主流六宫/道门九宫) / 三阶段 / 相邻生克 / 特例 / 拜解。
// 纯函数,零 UI 零接线。
import {
	MAIN_RING, DAO_RING, DAO_NINE, DAO_YI, BAI_JIE,
	SHENG_WO_DUAN, WO_KE_DUAN, TE_LI, STAGE_ROLES, ACROSS_NOTE, TONG_SHEN_NOTE,
	WUXING_SHENG, WUXING_KE,
} from './xiaoliurenConst.js';

// ── 起课 ───────────────────────────────────────────────
// 「任意取三个数数出结果,顺转,后一个数字的起点在上一个数字的开始。」
// 第一传自大安作 1 数 m;第二传自第一传作 1 数 d;第三传自第二传作 1 数 h。
// school: 'main'(主流六宫,环长 6)/ 'dao'(道门九宫,环长 9)。
export function sanChuan({ m, d, h, school = 'main' } = {}) {
	const ring = school === 'dao' ? DAO_RING : MAIN_RING;
	const nums = [m, d, h].map((v) => Math.trunc(Number(v)));
	if (nums.some((v) => !v || v < 1)) return null;
	let idx = 0; // 从大安起(两环之首均为大安)
	const chuan = nums.map((n) => {
		idx = (idx + n - 1) % ring.length;
		return ring[idx];
	});
	return { school, nums, chuan };
}

// ── 五行关系(a 对 b) ───────────────────────────────────
function wuxingOfShen(shen) {
	return DAO_NINE[shen] ? DAO_NINE[shen].wuxing : null;
}
function relOf(aElem, bElem) {
	if (!aElem || !bElem) return null;
	if (aElem === bElem) return '比和';
	if (WUXING_SHENG[aElem] === bElem) return '生';
	if (WUXING_KE[aElem] === bElem) return '克';
	if (WUXING_SHENG[bElem] === aElem) return '被生';
	if (WUXING_KE[bElem] === aElem) return '被克';
	return null;
}

// ── 特例侦测 ───────────────────────────────────────────
export function teLi(chuan) {
	if (!Array.isArray(chuan)) return [];
	const out = [];
	const count = (name) => chuan.filter((c) => c === name).length;
	if (count('留连') >= 2) out.push({ key: '两留连', text: TE_LI.两留连 });
	if (count('赤口') >= 2) out.push({ key: '两赤口', text: TE_LI.两赤口 });
	if (chuan.includes('空亡')) out.push({ key: '空亡', text: TE_LI.空亡 });
	return out;
}

// ── 判读 ───────────────────────────────────────────────
// 三传前(我)/中(他人外界)/后(结果);
// 道门:相邻两对(一↔二、二↔三)论生克,明载断语仅「生我=贵人相助」「我克=我克者为财」二条,
//       其余只标关系;一↔三仅列关系,注「文档无定论」。
// 主流:三传同名之神照道门含义,标「同神同义」。
export function analyze(result) {
	if (!result || !Array.isArray(result.chuan) || result.chuan.length !== 3) return null;
	const { school, chuan } = result;
	const stages = chuan.map((name, i) => ({
		pos: i + 1,
		role: STAGE_ROLES[i],
		name,
		info: DAO_NINE[name] || null,
		yi: DAO_YI[name] || null,
		tongShenTongYi: school !== 'dao' && !!DAO_YI[name], // 主流借道门同名神含义
	}));

	const pairs = [];
	const baiJie = [];
	if (school === 'dao') {
		[[0, 1], [1, 2]].forEach(([ia, ib]) => {
			const a = chuan[ia];
			const b = chuan[ib];
			const ea = wuxingOfShen(a);
			const eb = wuxingOfShen(b);
			const rel = relOf(ea, eb); // a 对 b:生/克/被生/被克/比和
			const pair = {
				a: { pos: ia + 1, name: a, wuxing: ea },
				b: { pos: ib + 1, name: b, wuxing: eb },
				rel,
				duan: null,
				note: null,
			};
			if (rel === '被生') {
				// 后一阶段生前一阶段 → 生我 → 贵人相助
				pair.duan = SHENG_WO_DUAN;
				pair.relText = `${b}${eb}生${a}${ea}(${ib + 1}生${ia + 1})`;
			} else if (rel === '克') {
				// 前一阶段克后一阶段 → 我克者为财
				pair.duan = `${WO_KE_DUAN};第${['一', '二', '三'][ib]}阶段为第${['一', '二', '三'][ia]}阶段之财`;
				pair.relText = `${a}${ea}克${b}${eb}(${ia + 1}克${ib + 1})`;
			} else {
				pair.relText = rel === '生' ? `${a}${ea}生${b}${eb}(${ia + 1}生${ib + 1})`
					: rel === '被克' ? `${b}${eb}克${a}${ea}(${ib + 1}克${ia + 1})`
						: `${a}${ea}与${b}${eb}比和`;
				pair.note = '文档未系断语,仅列生克关系';
			}
			// 拜解:被克之方,可拜克方所对应之神(「若被X在五行上克制:可拜Y」)
			if (rel === '克') baiJie.push({ victim: b, aggressor: a, bai: BAI_JIE[a] });
			if (rel === '被克') baiJie.push({ victim: a, aggressor: b, bai: BAI_JIE[b] });
			pairs.push(pair);
		});
	}

	// 一↔三:仅列关系,文档无定论
	const e1 = wuxingOfShen(chuan[0]);
	const e3 = wuxingOfShen(chuan[2]);
	const across = {
		a: { pos: 1, name: chuan[0], wuxing: e1 },
		b: { pos: 3, name: chuan[2], wuxing: e3 },
		rel: school === 'dao' ? relOf(e1, e3) : null,
		note: ACROSS_NOTE,
	};

	return {
		school,
		chuan: chuan.slice(),
		stages,
		pairs,
		across,
		teLi: teLi(chuan),
		baiJie,
		tongShenNote: school === 'dao' ? null : TONG_SHEN_NOTE,
	};
}

/** 起课+判读一步到位 */
export function qiKe(input) {
	const r = sanChuan(input);
	if (!r) return null;
	return { ...r, analysis: analyze(r) };
}
