// 判读引擎「全局层」headless 版 —— 自上游 utils/judgeLayerOverrides.js 抽出（bespoke，derived_from +
// derived_sha256 看守：上游该文件一动即红，复核本文件后 --restamp）。
//
// 上游 judgeLayerOverrides() 从两个 localStorage 仓各取「用户改过（≠缺省）」的键，组装卜卦
// horaryJudgeOpts / 择日 runElection 的第 2 层（全局层；四层 = 内建默认 < 全局层 < 流派差异集 < 页面覆盖）：
//   · classicalChartGlobals（排盘级）：classicalGlobalOverrides() = 按 classicalParamSpec 值型归一后 !== 缺省；
//   · divinationJudgeGlobals（纯判读级）：divinationJudgeOverrides() = bool 归一后 !== 缺省。
// headless 没有持久化偏好 —— skill 请求**顶层**的古典键就是用户的全局设置（与它们随 /chart 下发的是同一组值）。
// 所以这里把「仓」换成请求体，其余照搬：同一白名单、同一归一、同一「等于缺省不进」语义、同一 vocIncludeOuter→bool。
//
// 与上游仅四处不同（都是「请求体」这个来源带来的，存储里不会出现 —— 上游 UI 只写得进档内值）：
//   ① 键名双轨：skill 的 BirthInput 以后端名 starOrb/starOrbMode 声明恒星轨，前端名 fixedStarOrb/fixedStarOrbMode
//      优先、后端名兜底 —— 与 classicalBackendOverrides 的 [SURF-R2b] 双名回退同一口径；
//   ② int 键收 bool（true→1 / false→0）—— 与 classicalBackendOverrides 的「boolean 归一」同一口径
//      （上游仓里的旧 bool 由迁移代码先转成 0/1；请求体没有那道迁移，parseInt('true') 会静默丢开）；
//   ③ 判读仓两键收 0/1/'0'/'1'/'true'/'false'（上游 `!!raw` 会把字符串 '0'/'false' 当真）；
//   ④ 字符串枚举键（vocMode/viaCombustaVariant/partileDef/fixedStarOrbMode）值不在 spec 档内 → 进 invalid 回执
//      （调用方报错，不静默当缺省用）；defaultAliases 同义词（vocMode 的 lilly/backend）算缺省 —— 与
//      classicalBackendOverrides 的「值域校验 / 同义词也算默认」同一口径。数值键不设档（引擎吃任意有限值）。
import { CLASSICAL_GLOBAL_DEFAULTS } from './classicalChartGlobals.js';
import { specByKey } from './classicalParamSpec.js';
import { DIVINATION_JUDGE_DEFAULTS } from './divinationJudgeGlobals.js';

// 上游 judgeLayerOverrides.js:15-20 逐字。
const JUDGE_KEYS_FROM_CLASSICAL = [
	'cazimiOrb', 'combustOrb', 'underBeamsOrb',
	'vocMode', 'vocIncludeOuter', 'fixedStarOrb', 'fixedStarOrbMode',
	'viaCombustaVariant', 'partileDef',
	'antisciaOrb',   // [R5-P1] 两接收端(horarySchools JUDGE_KEYS/electionParams 白名单)早已就位,发送端漏此一行=卜卦映点表/择日映点模块恒 1° 兜底
];

const BACKEND_ALIASES = { fixedStarOrb: 'starOrb', fixedStarOrbMode: 'starOrbMode' };

function present(v){
	return v !== undefined && v !== null && v !== '';
}

// classicalChartGlobals.normalize 的单键版（int → parseInt / float → Number / 其余 → 字符串）。
function normalizeClassical(key, raw){
	const spec = specByKey(key);
	const vt = spec ? spec.valueType : 'str';
	if(vt === 'int'){
		const n = raw === true ? 1 : (raw === false ? 0 : parseInt(raw + '', 10));
		return Number.isFinite(n) ? n : undefined;
	}
	if(vt === 'float'){
		const f = Number(raw);
		return Number.isFinite(f) ? f : undefined;
	}
	return raw + '';
}

function normalizeBool(raw){
	if(raw === true || raw === 1 || raw === '1' || raw === 'true'){ return true; }
	if(raw === false || raw === 0 || raw === '0' || raw === 'false'){ return false; }
	return undefined;
}

// plain = 请求顶层（Python 传入的 payload 子集）。
// 返回 { overrides, invalid }：overrides 与上游 judgeLayerOverrides() 同形（只含「改过」的键）；
// invalid = [{ key, value, allowed }]（值认不出的键，不进 overrides）。
export function judgeLayerFromPlain(plain){
	const p = plain && typeof plain === 'object' ? plain : {};
	const out = {};
	const invalid = [];
	JUDGE_KEYS_FROM_CLASSICAL.forEach((k) => {
		const alias = BACKEND_ALIASES[k];
		let raw = p[k];
		let from = k;
		if(!present(raw) && alias){ raw = p[alias]; from = alias; }
		if(!present(raw)){ return; }
		const spec = specByKey(k);
		const v = normalizeClassical(k, raw);
		if(v === undefined){
			invalid.push({ key: from, value: raw, allowed: 'number' });
			return;
		}
		if(v === CLASSICAL_GLOBAL_DEFAULTS[k]){ return; }
		if(spec && spec.valueType === 'str'){
			if(Array.isArray(spec.defaultAliases) && spec.defaultAliases.indexOf(v) >= 0){ return; }
			if(Array.isArray(spec.options) && !spec.options.some((o) => o.value === v)){
				invalid.push({ key: from, value: raw, allowed: spec.options.map((o) => o.value) });
				return;
			}
		}
		out[k] = (k === 'vocIncludeOuter') ? !!v : v;
	});
	Object.keys(DIVINATION_JUDGE_DEFAULTS).forEach((k) => {
		if(!present(p[k])){ return; }
		const v = normalizeBool(p[k]);
		if(v === undefined){
			invalid.push({ key: k, value: p[k], allowed: [true, false] });
			return;
		}
		if(v === DIVINATION_JUDGE_DEFAULTS[k]){ return; }
		out[k] = v;
	});
	return { overrides: out, invalid };
}

export default judgeLayerFromPlain;
