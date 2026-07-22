// 六爻流派体系:7 预设 + 独立开关并存。预设套默认开关组,改单项→school 标「自定义」。
// 分歧点全做成可切换设置(土长生/月破/卦身/世身/飞伏/变卦装法/变爻作用范围/神煞/六神起法/长生用法/天时法/进退神土路径),不自裁。
// 新增开关默认值一律=既有行为等价 → 升级零回归;「断诀/应期」为纯新增面,默认开。
import { DEFAULT_SHENSHA_SET } from './liuyaoShenSha.js';
import { safeLocalStorageGet, safeLocalStorageSet } from './safeStorage.js';

export const DEFAULT_LIUYAO_SETTINGS = {
	school: 'default',
	askType: 'self',            // 占测事项 → 用神取用(liuyaoYongShen)
	yongOverride: '',           // 手动指定用神六亲(''=跟占测事项自动;父母/兄弟/子孙/妻财/官鬼/世/应)
	yuepoMode: 'inMonth',       // 月破:当月有效 / 'always' 长期标破
	tuChangsheng: 'water',      // 土长生:水土同宫(申)/'fire' 火土同宫(寅)/'off' 关
	bianyaoScope: 'traditional', // 变爻作用范围:传统(回头本位)/'blind' 盲派扩展
	guashen: true,              // 月卦身显示
	fushen: 'missing',          // 飞伏:'missing' 仅缺用神取 / 'all' 逐爻全标
	biangua: 'full',            // 变卦:'full' 全装变卦表(=旧版恒显之卦,零回归默认) / 'movingOnly' 仅显变爻行
	shensha: { on: true, set: DEFAULT_SHENSHA_SET.slice(), base: 'day' }, // 基础神煞(既有 10 种)
	sixGods: true,              // 六神显示
	yearBoundary: 'lichun',     // 定年界线(年支类神煞):'lichun' 立春 / 'lunar' 正月初一
	coinFace: 'standard',       // 摇钱字背口径:'standard' 背为阳 / 'alt' 字为阳(手动录入与寻物盘用)
	writeDir: 'bottomUp',       // 装卦表行序:'bottomUp' 上爻在上(默认)/'topDown' 初爻在上
	// —— 扩展(断易天机/古法/断诀/应期) ——
	shenshaEx: { on: false, set: null }, // 扩展神煞:set=null 表示启用时全选
	shishen: 'off',             // 世身:'off'/'standard'(子午持世身居初)/'lichunfeng'(亥子持世身居初)
	yueLiushen: false,          // 月建六神并注(不替代日干六神)
	jinTuiTu: 'chain',          // 进退神土路径:'chain' 丑辰未戌连环(含戌→丑)/'break' 戌丑断开
	changshengYinYang: 'ziping', // 开局信息卡生旺墓:'ziping' 分阴阳 / 'classic' 古法不分
	changshengUse: 'full12',    // 长生显示口径:'full12' 十二宫全用 / 'four' 只标生旺墓绝
	tianshiSchool: 'fumu',      // 天时占法:'fumu' 父母雨子孙晴(通行)/'ancient' 古法多套
	yuqi: false,                // 四墓月余气加强附标
	yingqi: true,               // 应期卡
	doctrine: true,             // 断诀命中/占类断语 总开关
	gufa: false,                // 古法进阶组(三限/十六变/升降/卦生/直符/八节卦气)
	benming: '',                // 占者本命年支(随官入墓·命式用;空则跳过)
};

export const LIUYAO_PRESETS = {
	default: { label: '通用', overrides: {} },
	zengshan: { label: '增删卜易(野鹤)', overrides: { guashen: false, fushen: 'missing', shensha: { on: false }, changshengUse: 'four' }, note: '重用神旺衰、删繁就简、弃卦身、几弃神煞;长生只取生旺墓绝' },
	bushi: { label: '卜筮正宗', overrides: { guashen: true, shensha: { on: true, set: DEFAULT_SHENSHA_SET.slice() } }, note: '重卦身、用神生克、神煞中等' },
	yiyin: { label: '易隐', overrides: { guashen: true, fushen: 'all', shensha: { on: true, set: DEFAULT_SHENSHA_SET.concat(['文昌']) }, shenshaEx: { on: true, set: null } }, note: '重卦身、逐爻全标飞伏、神煞极繁' },
	xinpai: { label: '邵伟华新派', overrides: { guashen: false, shensha: { on: false }, askType: 'self', changshengUse: 'four' }, note: '先世爻旺衰再定喜忌、弱化神煞、不用卦身;附旺衰量化' },
	mangpai: { label: '盲派', overrides: { bianyaoScope: 'blind', guashen: false, shensha: { on: false } }, note: '重象、扩大变爻作用范围(变爻可作用本卦他爻)' },
	tianji: { label: '断易天机(古法)', overrides: { guashen: true, shishen: 'standard', fushen: 'all', shensha: { on: true, set: DEFAULT_SHENSHA_SET.slice() }, shenshaEx: { on: true, set: null }, yueLiushen: true, changshengUse: 'full12', tianshiSchool: 'ancient', gufa: true, doctrine: true }, note: '火珠林古法:全神煞+飞伏生克+卦身世身并用+月建六神+十六变升降三限' },
};

export const LIUYAO_SCHOOL_OPTIONS = Object.keys(LIUYAO_PRESETS).map((k) => ({ value: k, label: LIUYAO_PRESETS[k].label }));

function deepMergeShensha(base, ov){
	if(!ov){ return { ...base }; }
	return { on: ov.on != null ? ov.on : base.on, set: ov.set ? ov.set.slice() : base.set.slice(), base: ov.base || base.base };
}
function deepMergeShenshaEx(base, ov){
	if(!ov){ return { on: base.on, set: base.set ? base.set.slice() : null }; }
	return { on: ov.on != null ? ov.on : base.on, set: ov.set === undefined ? (base.set ? base.set.slice() : null) : (ov.set ? ov.set.slice() : null) };
}

export function applyPreset(presetKey){
	const p = LIUYAO_PRESETS[presetKey] || LIUYAO_PRESETS.default;
	const ov = p.overrides || {};
	const merged = { ...DEFAULT_LIUYAO_SETTINGS, ...ov, school: presetKey };
	merged.shensha = deepMergeShensha(DEFAULT_LIUYAO_SETTINGS.shensha, ov.shensha);
	merged.shenshaEx = deepMergeShenshaEx(DEFAULT_LIUYAO_SETTINGS.shenshaEx, ov.shenshaEx);
	return merged;
}

export function setOption(settings, key, value){
	const next = { ...(settings || DEFAULT_LIUYAO_SETTINGS) };
	if(key === 'shensha'){ next.shensha = { ...next.shensha, ...value }; }
	else if(key === 'shenshaEx'){ next.shenshaEx = { ...next.shenshaEx, ...value }; }
	else { next[key] = value; }
	const presetKey = next.school === 'custom' ? null : next.school;
	if(presetKey && !sameAsPreset(next, presetKey)){ next.school = 'custom'; }
	return next;
}

function sameAsPreset(settings, presetKey){
	const base = applyPreset(presetKey);
	const keys = Object.keys(DEFAULT_LIUYAO_SETTINGS).filter((k) => k !== 'school' && k !== 'benming'); // 本命属输入非流派
	return keys.every((k) => {
		if(k === 'shensha'){
			return base.shensha.on === settings.shensha.on && base.shensha.base === settings.shensha.base
				&& JSON.stringify(base.shensha.set) === JSON.stringify(settings.shensha.set);
		}
		if(k === 'shenshaEx'){
			return base.shenshaEx.on === settings.shenshaEx.on && JSON.stringify(base.shenshaEx.set) === JSON.stringify(settings.shenshaEx.set);
		}
		return base[k] === settings[k];
	});
}

export function normalizeLiuyaoSettings(raw){
	if(!raw || typeof raw !== 'object'){
		return { ...DEFAULT_LIUYAO_SETTINGS, shensha: { ...DEFAULT_LIUYAO_SETTINGS.shensha, set: DEFAULT_LIUYAO_SETTINGS.shensha.set.slice() }, shenshaEx: { ...DEFAULT_LIUYAO_SETTINGS.shenshaEx } };
	}
	const out = { ...DEFAULT_LIUYAO_SETTINGS, ...raw };
	out.shensha = deepMergeShensha(DEFAULT_LIUYAO_SETTINGS.shensha, raw.shensha);
	out.shenshaEx = deepMergeShenshaEx(DEFAULT_LIUYAO_SETTINGS.shenshaEx, raw.shenshaEx);
	if(!LIUYAO_PRESETS[out.school] && out.school !== 'custom'){ out.school = 'default'; }
	return out;
}

// 选项键(任一变 → 重算中右栏 + AI 快照)
export function getLiuyaoOptionsKey(settings){
	const s = normalizeLiuyaoSettings(settings);
	return [s.school, s.askType, s.yuepoMode, s.tuChangsheng, s.bianyaoScope, s.guashen, s.fushen, s.biangua,
		s.shensha.on, s.shensha.base, (s.shensha.set || []).join('|'), s.sixGods, s.yearBoundary, s.coinFace, s.writeDir,
		s.shenshaEx.on, (s.shenshaEx.set || ['ALL']).join('|'), s.shishen, s.yueLiushen, s.jinTuiTu,
		s.changshengYinYang, s.changshengUse, s.tianshiSchool, s.yuqi, s.yingqi, s.doctrine, s.gufa, s.benming].join(',');
}

// ── 跨会话持久化(独立轻量,不依赖 AI 存储;走 safeStorage=配额满自动清理重试,FL-4 治理口径) ──
const LS_KEY = 'horosa.liuyao.settings.v1';
export function loadPersistedLiuyaoSettings(){
	try{
		const raw = safeLocalStorageGet(LS_KEY);
		return raw ? normalizeLiuyaoSettings(JSON.parse(raw)) : null;
	}catch(e){ return null; }
}
export function persistLiuyaoSettings(s){
	try{
		const o = normalizeLiuyaoSettings(s);
		safeLocalStorageSet(LS_KEY, JSON.stringify({ ...o, benming: o.benming || '' }));
	}catch(e){ /* 配额/隐私模式静默忽略 */ }
}
