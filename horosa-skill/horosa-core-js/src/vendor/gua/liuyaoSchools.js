// 六爻流派体系(WP-J):5 预设 + 独立开关并存。预设套默认开关组,改单项→school 标「自定义」。
// 分歧点全做成可切换设置(土长生/月破/卦身/飞伏/变卦装法/变爻作用范围/神煞),不自裁。默认=通用(新功能全显,不破坏既有显示)。
import { DEFAULT_SHENSHA_SET } from './liuyaoShenSha.js';

// 通用默认(default preset):各分歧取主流口径,新结构数据全显于新面(既有中栏/快照行不变=零回归)
export const DEFAULT_LIUYAO_SETTINGS = {
	school: 'default',
	askType: 'self',            // 占测事项 → 用神取用(liuyaoYongShen)
	yuepoMode: 'inMonth',       // 月破:当月有效
	tuChangsheng: 'water',      // 土长生:水土同宫(申);'fire' 火土同宫(寅);'off' 关
	bianyaoScope: 'traditional', // 变爻作用范围:传统(回头本位) / 'blind'(盲派扩展)
	guashen: true,              // 卦身显示(卜筮正宗/易隐重;增删卜易/新派/盲派弃)
	fushen: 'missing',          // 飞伏:'missing' 仅缺用神取 / 'all' 逐爻全标
	biangua: 'movingOnly',      // 变卦:'movingOnly' 仅装变爻 / 'full' 全装变卦六亲
	shensha: { on: true, set: DEFAULT_SHENSHA_SET.slice(), base: 'day' },
	sixGods: true,              // 六神显示
	yearBoundary: 'lichun',     // 定年界线(年起神煞):'lichun' 立春 / 'lunar' 正月初一
	coinFace: 'standard',       // 起卦字背口径(WP-I)
	writeDir: 'bottomUp',       // 初爻在下
};

// 5 预设 → 开关覆盖(只列与 default 不同项;其余继承 default)
export const LIUYAO_PRESETS = {
	default: { label: '通用', overrides: {} },
	zengshan: { label: '增删卜易(野鹤)', overrides: { guashen: false, fushen: 'missing', shensha: { on: false } }, note: '重用神旺衰、删繁就简、弃卦身、几弃神煞' },
	bushi: { label: '卜筮正宗', overrides: { guashen: true, shensha: { on: true, set: DEFAULT_SHENSHA_SET.slice() } }, note: '重卦身、用神生克、神煞中等' },
	yiyin: { label: '易隐', overrides: { guashen: true, fushen: 'all', shensha: { on: true, set: DEFAULT_SHENSHA_SET.concat(['文昌']) } }, note: '重卦身、逐爻全标飞伏、神煞极繁' },
	xinpai: { label: '邵伟华新派', overrides: { guashen: false, shensha: { on: false }, askType: 'self' }, note: '先世爻旺衰再定喜忌、弱化神煞、不用卦身' },
	mangpai: { label: '盲派', overrides: { bianyaoScope: 'blind', guashen: false, shensha: { on: false } }, note: '重象、扩大变爻作用范围(变爻可作用本卦他爻)' },
};

export const LIUYAO_SCHOOL_OPTIONS = Object.keys(LIUYAO_PRESETS).map((k) => ({ value: k, label: LIUYAO_PRESETS[k].label }));

function deepMergeShensha(base, ov){
	if(!ov){ return { ...base }; }
	return { on: ov.on != null ? ov.on : base.on, set: ov.set ? ov.set.slice() : base.set.slice(), base: ov.base || base.base };
}

// 套用预设:返回完整 settings(预设 overrides 盖在 default 上)
export function applyPreset(presetKey){
	const p = LIUYAO_PRESETS[presetKey] || LIUYAO_PRESETS.default;
	const ov = p.overrides || {};
	const merged = { ...DEFAULT_LIUYAO_SETTINGS, ...ov, school: presetKey };
	merged.shensha = deepMergeShensha(DEFAULT_LIUYAO_SETTINGS.shensha, ov.shensha);
	return merged;
}

// 改单开关:覆盖该项;若结果偏离所选预设 → school 标 'custom'
export function setOption(settings, key, value){
	const next = { ...(settings || DEFAULT_LIUYAO_SETTINGS) };
	if(key === 'shensha'){ next.shensha = { ...next.shensha, ...value }; }
	else { next[key] = value; }
	// 判定是否仍等于当前预设
	const presetKey = next.school === 'custom' ? null : next.school;
	if(presetKey && !sameAsPreset(next, presetKey)){ next.school = 'custom'; }
	return next;
}

function sameAsPreset(settings, presetKey){
	const base = applyPreset(presetKey);
	const keys = Object.keys(DEFAULT_LIUYAO_SETTINGS).filter((k) => k !== 'school');
	return keys.every((k) => {
		if(k === 'shensha'){
			return base.shensha.on === settings.shensha.on && base.shensha.base === settings.shensha.base
				&& JSON.stringify(base.shensha.set) === JSON.stringify(settings.shensha.set);
		}
		return base[k] === settings[k];
	});
}

// 规整(旧档迁移 + 缺省补全)
export function normalizeLiuyaoSettings(raw){
	if(!raw || typeof raw !== 'object'){ return { ...DEFAULT_LIUYAO_SETTINGS, shensha: { ...DEFAULT_LIUYAO_SETTINGS.shensha, set: DEFAULT_LIUYAO_SETTINGS.shensha.set.slice() } }; }
	const out = { ...DEFAULT_LIUYAO_SETTINGS, ...raw };
	out.shensha = deepMergeShensha(DEFAULT_LIUYAO_SETTINGS.shensha, raw.shensha);
	if(!LIUYAO_PRESETS[out.school] && out.school !== 'custom'){ out.school = 'default'; }
	return out;
}

// 选项键(任一变 → 重算中右栏 + AI 快照,仿 getQimenOptionsKey)
export function getLiuyaoOptionsKey(settings){
	const s = normalizeLiuyaoSettings(settings);
	return [s.school, s.askType, s.yuepoMode, s.tuChangsheng, s.bianyaoScope, s.guashen, s.fushen, s.biangua,
		s.shensha.on, s.shensha.base, (s.shensha.set || []).join('|'), s.sixGods, s.yearBoundary, s.coinFace, s.writeDir].join(',');
}
