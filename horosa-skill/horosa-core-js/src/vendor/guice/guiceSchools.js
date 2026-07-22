// 皇极轨策 · 流派体系：4 预设 + 10 独立开关并存。预设套默认开关组，改单项 → school 标「自定义」。
// 分歧点全做成可切换设置，不自裁（照 gua/liuyaoSchools 之范式）。
//
// 两条贯穿铁律：
//   ·「默认即现状」—— 缺省 undefined → 引擎兜底默认 → 输出逐字节不变，零回归。
//   ·「分歧全做成可切换设置，不自裁」。
//
// 🔴 getGuiceOptionsKey 是关键：须汇总【全部十个开关】→ 任一变则中右栏重算 + AI 快照刷新。
//    漏它 = 「勾了半天中间和右边没变」类 bug。
import { QI_GUA_FA } from './core/guiceQiGua.js';
import { SHIYING_SETS, JI_GONG_MODES } from './core/guiceConst.js';
import { LIUSHIJIAZI_DINGSHU } from './core/guiceJiaziShu.js';

export const DEFAULT_GUICE_SETTINGS = {
	school: 'default',
	qiguaFa: 'time',          // 起卦法：十二法之一（默认年月日时起例）
	yanshuFa: 'ce',           // 演数：策数★ / 轨数
	jiGongMode: 'ganrou',     // 五与十之寄宫：刚柔日动态★ / 五寄艮 / 五寄坤
	qiguaShu: 'xiantian',     // 数字配卦之系：五行生成数★ / 后天正数 / 九畴数
	shenSha: false,           // 神煞★关
	shiFang: false,           // 时方★关
	shuXi: 'zhouyi',          // 数系：周易数★ / 梅花
	dadingTable: 'xinyifawei', // 六十甲子天地立成定数：心易发微本★ / 别本
	shiyingSet: 'xinyifawei', // 十应名目：心易发微版★ / 梅花原书版 / 日辰秘文版
};
// 🔴 何以无「加时」一项:加与不加由起卦法【自身定死】——年月日时起例加时、丈尺占不加时、
//    尺寸占加时…,且多数法之下卦即时数,关之连卦都起不出。做成开关必是死控件(它曾是:
//    有控件、入选项键、进储存,而引擎零消费,翻之毫无动静)。今改由左栏 hint 照实说其法
//    加时与否(见 schoolNeeds().addHour),不做成可翻之项。

export const GUICE_PRESETS = {
	default: { label: '通用（周易数）', overrides: {} },
	meihua: {
		label: '梅花',
		// 梅花不用神煞与时方 —— 两书皆明载「策轨数…不用时方应」
		overrides: { shuXi: 'meihua', shenSha: false, shiFang: false, shiyingSet: 'meihua' },
	},
	zhouyishu: { label: '周易数', overrides: { shuXi: 'zhouyi', yanshuFa: 'ce', qiguaShu: 'xiantian' } },
	dading: { label: '大定', overrides: { qiguaShu: 'jiuchou', dadingTable: 'xinyifawei' } },
};
export const GUICE_SCHOOL_OPTIONS = Object.keys(GUICE_PRESETS).map((k) => ({ value: k, label: GUICE_PRESETS[k].label }));

/** 左栏控件之元（自动渲染；needs 控显隐） */
// 🔴 起卦法不列于此 —— 其于左栏顶部专渲（它决定下方专属输入之显隐，与诸开关不同列）；
//    列之则控件重出。然其仍属十开关之一（见 GUICE_OPTION_KEYS 与 getGuiceOptionsKey）。
export const GUICE_OPTION_META = [
	{ key: 'yanshuFa', label: '演数', type: 'segmented', options: [{ value: 'ce', label: '策数' }, { value: 'gui', label: '轨数' }] },
	{ key: 'qiguaShu', label: '数字配卦', type: 'select', options: [
		{ value: 'xiantian', label: '五行生成数（先天）' }, { value: 'houtian', label: '后天正数' }, { value: 'jiuchou', label: '九畴数（大定）' },
	] },
	{ key: 'jiGongMode', label: '五·十寄宫', type: 'select', needs: { jiGong: true },
		options: Object.keys(JI_GONG_MODES).map((k) => ({ value: k, label: JI_GONG_MODES[k].label })) },
	{ key: 'shuXi', label: '数系', type: 'segmented', options: [{ value: 'zhouyi', label: '周易数' }, { value: 'meihua', label: '梅花' }] },
	{ key: 'shenSha', label: '神煞', type: 'switch', needs: { shenSha: true } },
	{ key: 'shiFang', label: '时方', type: 'switch', needs: { shiFang: true } },
	{ key: 'dadingTable', label: '六十甲子定数', type: 'select', needs: { dading: true },
		options: Object.keys(LIUSHIJIAZI_DINGSHU).map((k) => ({ value: k, label: LIUSHIJIAZI_DINGSHU[k].label })) },
	{ key: 'shiyingSet', label: '十应名目', type: 'select',
		options: Object.keys(SHIYING_SETS).map((k) => ({ value: k, label: SHIYING_SETS[k].label })) },
];

/**
 * 声明式互斥/联动 —— 死控件隐藏，不留「勾了不生效」之惑。
 *   · 梅花数系 → 神煞与时方强制关且置灰（两书明载梅花不用时方应）
 *   · 五与十之寄宫 → 仅后天正数与九畴数用得着（五行生成数无寄宫）
 *   · 加时 → 丈尺占本不加时，其法下此开关无用
 *   · 六十甲子定数 → 唯大定用之
 */
export function schoolNeeds(settings) {
	const s = normalizeGuiceSettings(settings);
	const meihua = s.shuXi === 'meihua';
	return {
		jiGong: s.qiguaShu === 'houtian',           // 九畴之借由口诀自载，非寄宫 → 不需此项
		shenSha: !meihua,
		shiFang: !meihua,
		// 「本法加时否」只作照实之说明(左栏 hint),非控件之显隐 —— 其非可选项
		addHour: s.qiguaFa !== 'zhangchi',
		dading: s.qiguaShu === 'jiuchou' || s.school === 'dading',
		disabled: {
			shenSha: meihua ? '梅花不用神煞' : null,
			shiFang: meihua ? '梅花不用时方' : null,
			addHour: s.qiguaFa === 'zhangchi' ? '丈尺占本不加时' : null,
		},
	};
}

/** 起卦法所需之输入（控件按需显隐） */
export const QIGUA_FA_INPUTS = {
	time: ['time'], baoshu: ['nums'], wushu: ['wuShu'], shengyin: ['shengShu'],
	zizhan: ['text', 'shu', 'tones'], zhangchi: ['zhang', 'chi'], chicun: ['chi', 'cun'],
	weiren: ['qu', 'shu'], ziji: ['qu', 'shu'], dongwu: ['wuGuaNum', 'fangGuaNum'],
	jingwu: ['kind', 'time'], duanfa: ['wuGuaNum', 'fangGuaNum'],
};
export function qiguaFaInputs(fa) { return QIGUA_FA_INPUTS[fa] || []; }

export function applyPreset(presetKey) {
	const p = GUICE_PRESETS[presetKey] || GUICE_PRESETS.default;
	return { ...DEFAULT_GUICE_SETTINGS, ...(p.overrides || {}), school: presetKey };
}

function sameAsPreset(settings, presetKey) {
	const base = applyPreset(presetKey);
	return Object.keys(DEFAULT_GUICE_SETTINGS)
		.filter((k) => k !== 'school')
		.every((k) => base[k] === settings[k]);
}

/** 改单开关：覆盖该项；若结果偏离所选预设 → school 标 'custom' */
export function setOption(settings, key, value) {
	const next = { ...normalizeGuiceSettings(settings), [key]: value };
	// 梅花不用神煞/时方 —— 切至梅花即强制关之（免留「勾着却不生效」之死控件）
	if (key === 'shuXi' && value === 'meihua') { next.shenSha = false; next.shiFang = false; }
	const presetKey = next.school === 'custom' ? null : next.school;
	if (presetKey && !sameAsPreset(next, presetKey)) next.school = 'custom';
	return next;
}

/** 规整（旧档迁移 + 缺省补全） */
export function normalizeGuiceSettings(raw) {
	if (!raw || typeof raw !== 'object') return { ...DEFAULT_GUICE_SETTINGS };
	const out = { ...DEFAULT_GUICE_SETTINGS, ...raw };
	if (!GUICE_PRESETS[out.school] && out.school !== 'custom') out.school = 'default';
	if (QI_GUA_FA.every((f) => f.key !== out.qiguaFa)) out.qiguaFa = DEFAULT_GUICE_SETTINGS.qiguaFa;
	if (['ce', 'gui'].indexOf(out.yanshuFa) < 0) out.yanshuFa = 'ce';
	if (['xiantian', 'houtian', 'jiuchou'].indexOf(out.qiguaShu) < 0) out.qiguaShu = 'xiantian';
	if (!JI_GONG_MODES[out.jiGongMode]) out.jiGongMode = 'ganrou';
	if (['zhouyi', 'meihua'].indexOf(out.shuXi) < 0) out.shuXi = 'zhouyi';
	if (!LIUSHIJIAZI_DINGSHU[out.dadingTable]) out.dadingTable = 'xinyifawei';
	if (!SHIYING_SETS[out.shiyingSet]) out.shiyingSet = 'xinyifawei';
	delete out.addHour;   // 🔴 加时非设置(由法自定)——旧档存过此键者一并抹去,免留死值
	// 梅花不用神煞/时方 —— 旧档若存着开，规整时一并关之（与 setOption 同则）
	if (out.shuXi === 'meihua') { out.shenSha = false; out.shiFang = false; }
	return out;
}

/**
 * 🔴 选项键：汇总【全部十个开关】→ 作重算触发 + memo 签名 + AI 快照刷新触发。
 *    禁止只监听单项 —— 漏一个即该开关「勾了没变」。
 */
export function getGuiceOptionsKey(settings) {
	const s = normalizeGuiceSettings(settings);
	return [
		s.school, s.qiguaFa, s.yanshuFa, s.jiGongMode, s.qiguaShu,
		s.shenSha, s.shiFang, s.shuXi, s.dadingTable, s.shiyingSet,
	].join(',');
}

/** 开关之全（哨兵与测试据此机械核对，免手抄漏项） */
export const GUICE_OPTION_KEYS = Object.keys(DEFAULT_GUICE_SETTINGS).filter((k) => k !== 'school');

export default {
	DEFAULT_GUICE_SETTINGS, GUICE_PRESETS, GUICE_OPTION_META, GUICE_OPTION_KEYS,
	applyPreset, setOption, normalizeGuiceSettings, getGuiceOptionsKey, schoolNeeds, qiguaFaInputs,
};
