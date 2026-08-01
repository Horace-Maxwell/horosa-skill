// divination/horary/horarySchools.js
// 卜卦（西洋 Horary）流派轴（七档）+ 多流派可配置参数总表（00§5 全量落地）。
// 单一真值源：排盘请求（宫制/界/守护/双子界序/福点反转）与判读引擎（考量/完成/月亮/太阳/点/恒星/应期）共用。
//
// 设计约束：
//  - 默认 classical = 主流经典口径；其全部参数取「零回归值」——新增参数的 classical 取值
//    必须使引擎行为与参数不存在时逐字节一致（新门全关/新模式取 backend 或 heuristic）。
//  - 参数三作用域（spec.scope）：
//      'global' —— 非卜卦独有,统一在「设置 → 星盘设置」修改（utils/classicalChartGlobals +
//                  utils/divinationJudgeGlobals）,卜卦页不再提供修改入口;
//      'school' —— 流派学理绑定（切流派即变,页面不单独放控件;宫制与下方「盘面参数」重复亦归此类);
//      'horary' —— 卜卦专属判读参数,渲染在卜卦左栏「判读参数」面板。
//  - 优先级（四层,用户拍板）：引擎内建默认(judgeDefaults) < 全局仓(divinationJudgeOverrides)
//    < 流派差异集(SCHOOL_JUDGE_DIFF,学理显式绑定恒压过全局) < 页面 overrides。
//  - 预设 + 高级自定义：有效参数 = 预设值 ∪ extra.horaryOverrides（见 effectiveHoraryParams）。
//  - 术语依据均为「宫制/时代/星历口径」等公有方法名（Regiomontanus/Alcabitius/Placidus/整宫制、
//    Ptolemy/Dorotheus 三分制、埃及界/托勒密界经典传本/校勘本、1647 印本传承等），
//    显示层零内部溯源引用、零在世作者名。

export const HORARY_SCHOOL_ORDER = ['classical', 'renaissance', 'strict', 'sequence', 'hellenistic', 'medieval', 'modern'];

// ── 多流派可配置参数总表（00§5;分组供面板分栏渲染）────────────────────────
// 每项：{ key, group, scope('global'|'school'|'horary'), label, type('select'|'switch'|'number'),
//        options?, default(classical零回归值), sendToBackend(true→patchFields 重排盘;否则仅重跑判读), hint? }
export const HORARY_PARAM_SPEC = [
	// —— 起盘（scope:school/global —— 卜卦页不渲染;流派绑定或全局设置管辖）——
	{ key: 'hsys', group: '起盘', scope: 'school', label: '宫制', type: 'select', sendToBackend: true, default: 2,
		options: [ { value: 0, label: '整宫制' }, { value: 1, label: 'Alcabitius' }, { value: 2, label: 'Regiomontanus' }, { value: 3, label: 'Placidus' }, { value: 4, label: 'Campanus' }, { value: 5, label: 'Koch' }, { value: 7, label: 'Porphyry' } ] },
	{ key: 'termsVariant', group: '起盘', scope: 'global', label: '界系', type: 'select', sendToBackend: true, default: 2,
		options: [ { value: 0, label: '埃及界' }, { value: 1, label: '托勒密界·校勘本' }, { value: 2, label: '托勒密界·经典传本' }, { value: 3, label: '迦勒底界（推演）' } ] },
	{ key: 'geminiBoundEmended', group: '起盘', scope: 'global', label: '双子界序（经典传本）', type: 'select', sendToBackend: true, default: 0,
		options: [ { value: 0, label: '忠原书（♄21–25/♂25–30）' }, { value: 1, label: '校勘对调（♂21–25/♄25–30）' } ],
		hint: '仅作用于托勒密界·经典传本;1647 印本双子末两界与后世校勘本相反,两皆有据。' },
	{ key: 'tradition', group: '起盘', scope: 'school', label: '星群', type: 'select', sendToBackend: true, default: 1,
		options: [ { value: 1, label: '七政（古典）' }, { value: 0, label: '七政＋三王星' } ] },
	// —— 尊贵 ——
	{ key: 'tripSystem', group: '尊贵', scope: 'school', label: '三分制', type: 'select', default: 'ptolemaic',
		options: [ { value: 'ptolemaic', label: 'Ptolemy 二主（水象＝火星）' }, { value: 'dorothean', label: 'Dorotheus 三主（含共主）' } ] },
	{ key: 'accidentalMode', group: '尊贵', scope: 'horary', label: '偶然尊贵计分', type: 'select', default: 'heuristic',
		options: [ { value: 'heuristic', label: '启发式（现行）' }, { value: 'lilly', label: '1647 满分表（±38）' } ] },
	{ key: 'partileDef', group: '尊贵', scope: 'global', label: 'Partile 判据', type: 'select', default: 'same_degree',
		options: [ { value: 'same_degree', label: '同整数度（1647）' }, { value: 'le3', label: '≤3°（1677）' }, { value: 'le1', label: '≤1°（现代）' } ] },
	{ key: 'lotsSet', group: '尊贵', scope: 'horary', label: '阿拉伯点集', type: 'select', default: 'minimal',
		options: [ { value: 'minimal', label: '福点＋精神点' }, { value: 'core15', label: '核心可靠集（15 点）' } ] },
	{ key: 'pofReversal', group: '尊贵', scope: 'school', label: '福点昼夜反转', type: 'switch', default: false },
	// —— 相位 ——
	{ key: 'orbMode', group: '相位', scope: 'horary', label: '容许度模式', type: 'select', default: 'backend',
		options: [ { value: 'backend', label: '半距和（现行）' }, { value: 'sequence', label: '无-orb 序列（看最终精确）' } ] },
	{ key: 'interferenceTiming', group: '相位', scope: 'horary', label: '抢先判据', type: 'select', default: 'degree',
		options: [ { value: 'degree', label: '按度差（古典近似）' }, { value: 'speed', label: '按速度折算到达时间' } ] },
	{ key: 'detectAbscission', group: '相位', scope: 'horary', label: '光线切断识别', type: 'switch', default: false },
	{ key: 'refranationAsDestruction', group: '相位', scope: 'horary', label: '撤回作独立破坏', type: 'switch', default: false },
	{ key: 'refranationIncludeSignChange', group: '相位', scope: 'horary', label: '撤回含换座变体', type: 'switch', default: false },
	{ key: 'collectionRequireReception', group: '相位', scope: 'horary', label: '汇集须双方容纳', type: 'switch', default: false },
	{ key: 'oppositionVerdict', group: '相位', scope: 'horary', label: '冲相口径', type: 'select', default: 'no',
		options: [ { value: 'no', label: '无接纳即破坏' }, { value: 'yes_but', label: '可成但得而复失' } ] },
	// —— 太阳（阈值三项+同座限制 → 全局「星盘设置」;仅「合日即所求」豁免为卜卦专属）——
	{ key: 'cazimiOrb', group: '太阳', scope: 'global', label: '日心 cazimi', type: 'select', default: 17 / 60,
		options: [ { value: 17 / 60, label: '17′（1647）' }, { value: 16 / 60, label: '16′（中世纪）' }, { value: 1, label: '1°（早期）' } ] },
	{ key: 'combustOrb', group: '太阳', scope: 'global', label: '燃烧上界', type: 'select', default: 8.5,
		options: [ { value: 8.5, label: '8°30′（1647）' }, { value: 8, label: '8°（中世纪）' } ] },
	{ key: 'underBeamsOrb', group: '太阳', scope: 'global', label: '日光束外界', type: 'select', default: 17,
		options: [ { value: 17, label: '17°（1647）' }, { value: 15, label: '15°（较古）' } ] },
	{ key: 'combustMitigateSameSign', group: '太阳', scope: 'global', label: '燃烧限同座', type: 'switch', default: true },
	{ key: 'combustExemptConjAnswer', group: '太阳', scope: 'horary', label: '合日即所求时豁免', type: 'switch', default: false },
	// —— 月亮（空亡口径/计三王星 → 全局;豁免注记与燃烧之路为卜卦考量专属）——
	{ key: 'vocMode', group: '月亮', scope: 'global', label: '空亡口径', type: 'select', default: 'classic',
		// 标签勘误(2026-07):后端 isVOC 实为「无入相/正合主相位即空」(1647 口径),旧标「后端按座」系误录。
		options: [
			{ value: 'classic', label: '无入相即空（1647 · 现行）' }, { value: 'by_orb', label: '容许度 12°30′' },
			{ value: 'by_sign_perfect', label: '本座内须完成（现代）' }, { value: 'by_sign_orb', label: '本座内入容许度（16c）' },
			{ value: 'kenodromia', label: '30° 法（希腊化）' }, { value: 'exempt4', label: '按座＋四座豁免（中世纪）' },
		] },
	{ key: 'vocIncludeOuter', group: '月亮', scope: 'global', label: '空亡计三王星', type: 'switch', default: false },
	{ key: 'vocMitigateSigns', group: '月亮', scope: 'horary', label: '四座豁免注记', type: 'switch', default: false },
	{ key: 'viaCombustaVariant', group: '月亮', scope: 'global', label: '燃烧之路边界', type: 'select', default: 'standard',
		options: [ { value: 'standard', label: '天秤15°–天蝎15°' }, { value: 'narrow', label: '窄口径（天秤28°–天蝎7°）' }, { value: 'scorpioFull', label: '天秤后15°＋天蝎全宫' }, { value: 'bothFull', label: '天秤＋天蝎全段' } ] },
	// —— 技法（映点/恒星轨 → 全局）——
	{ key: 'antiscia', group: '技法', scope: 'global', label: '映点参与判读', type: 'switch', default: true },
	{ key: 'fixedStarOrb', group: '技法', scope: 'global', label: '恒星容许度(°)', type: 'select', default: 2,
		options: [ { value: 1, label: '1°' }, { value: 1.5, label: '1.5°' }, { value: 2, label: '2°' }, { value: 3, label: '3°' }, { value: 5, label: '5°' } ] },
	{ key: 'fixedStarOrbMode', group: '技法', scope: 'global', label: '恒星轨档', type: 'select', default: 'school',
		options: [ { value: 'school', label: '按流派平轨' }, { value: 'byMagnitude', label: '按星等（1等7°30′…王者≤5°）' } ] },
	// —— 判读 ——
	{ key: 'considerationsMode', group: '判读', scope: 'horary', label: '考量硬度', type: 'select', default: 'warn',
		options: [ { value: 'warn', label: '警示' }, { value: 'strict', label: '严格' }, { value: 'lenient', label: '宽松' }, { value: 'ignore', label: '几乎弃用' } ] },
	{ key: 'ascEarlyDeg', group: '判读', scope: 'horary', label: '命度过早阈值', type: 'select', default: 3,
		options: [ { value: 0, label: '不启用' }, { value: 2, label: '2°' }, { value: 3, label: '3°' }, { value: 5, label: '5°' } ] },
	{ key: 'ascLateDeg', group: '判读', scope: 'horary', label: '命度过晚阈值', type: 'select', default: 27,
		options: [ { value: 30, label: '不启用' }, { value: 28, label: '28°' }, { value: 27, label: '27°' }, { value: 25, label: '25°' } ] },
	{ key: 'hourAgreementVariant', group: '判读', scope: 'horary', label: '时主一致口径', type: 'select', default: 'either',
		options: [ { value: 'either', label: '两口径任一' }, { value: 'lilly', label: '行星统辖版' }, { value: 'bonatti', label: '落座元素版' } ] },
	{ key: 'perfectionStrict', group: '判读', scope: 'horary', label: '完成法严格度', type: 'select', default: 'standard',
		options: [ { value: 'standard', label: '标准' }, { value: 'strict', label: '严格' }, { value: 'lenient', label: '宽松' } ] },
	{ key: 'timingVariant', group: '判读', scope: 'horary', label: '应期基准星', type: 'select', default: 'applier',
		options: [ { value: 'applier', label: '看入相星（现行）' }, { value: 'applied', label: '看被入相星' }, { value: 'byHouse', label: '按宫（皆果→天/皆续→周/皆角→月）' } ] },
	{ key: 'timingModifiers', group: '判读', scope: 'horary', label: '应期修正链', type: 'switch', default: false },
	{ key: 'timingSecondLaw', group: '判读', scope: 'horary', label: '实时凌犯参考', type: 'switch', default: false },
	{ key: 'onePlanetBoth', group: '判读', scope: 'horary', label: '同主一星裁决', type: 'select', default: '',
		options: [ { value: '', label: '不特别处置（现行）' }, { value: 'A', label: '法A·紧连偏正面' }, { value: 'B', label: '法B·事在问者手' }, { value: 'C', label: '法C·看容纳' }, { value: 'D', label: '法D·问者改月亮' }, { value: 'E', label: '法E·almuten 拆分' } ] },
	{ key: 'parentHousesVariant', group: '判读', scope: 'horary', label: '父母宫', type: 'select', default: 'traditional',
		options: [ { value: 'traditional', label: '传统（4父/10母）' }, { value: 'modern', label: '现代（4母/10父）' } ] },
	{ key: 'includeOuter', group: '判读', scope: 'horary', label: '判读计三王星', type: 'switch', default: false },
];

// 参数 → spec 查表
export const HORARY_PARAM_BY_KEY = {};
HORARY_PARAM_SPEC.forEach((p) => { HORARY_PARAM_BY_KEY[p.key] = p; });
const BACKEND_KEYS = HORARY_PARAM_SPEC.filter((p) => p.sendToBackend).map((p) => p.key);
// 判读域键集（judgeDefaults 的键;全局仓合并时按此白名单收编,防外来键渗入 opts）。
const JUDGE_KEYS = HORARY_PARAM_SPEC.filter((p) => !p.sendToBackend && p.key !== 'tripSystem').map((p) => p.key);
// 🔴 spec 之外的判读消费键必须在此显式收编,否则全局设置对卜卦静默无效
// (antisciaOrb:映点表容许度,消费在 HoraryJudgment.buildAntisciaTable;曾恒 undefined 兜底 1°)。
JUDGE_KEYS.push('antisciaOrb');

// classical 的 judge 零回归基值（= 参数不存在时的引擎行为）。
function judgeDefaults(){
	const out = {};
	HORARY_PARAM_SPEC.forEach((p) => { if(!p.sendToBackend && p.key !== 'tripSystem'){ out[p.key] = p.default; } });
	return out;
}

// ── 各档判读差异集（学理显式绑定;即使与基线同值也算「绑定」,恒压过全局仓）─────────
// 拆出独立常量的目的：horaryJudgeOpts 四层合并需要区分「流派绑定」与「继承基线」——
// 只有此表里的键才压过用户全局设置;表外键随 全局仓>内建默认 走。
export const SCHOOL_JUDGE_DIFF = {
	classical: {
		ascEarlyDeg: 3, ascLateDeg: 27, considerationsMode: 'warn',
		vocMode: 'classic', vocMitigateSigns: false, combustMitigateSameSign: true,
		pofReversal: false, fixedStarOrb: 2, perfectionStrict: 'standard', includeOuter: false,
	},
	renaissance: {
		ascEarlyDeg: 3, ascLateDeg: 27, considerationsMode: 'warn',
		vocMode: 'by_orb', vocMitigateSigns: true, combustMitigateSameSign: true,
		pofReversal: false, fixedStarOrb: 5, fixedStarOrbMode: 'byMagnitude', perfectionStrict: 'standard', includeOuter: false,
		accidentalMode: 'lilly', lotsSet: 'core15', partileDef: 'same_degree',
		detectAbscission: true, refranationAsDestruction: true, refranationIncludeSignChange: false,
		oppositionVerdict: 'yes_but', combustExemptConjAnswer: true, interferenceTiming: 'speed',
		timingModifiers: true, timingSecondLaw: true, hourAgreementVariant: 'either', onePlanetBoth: 'A',
	},
	strict: {
		ascEarlyDeg: 3, ascLateDeg: 27, considerationsMode: 'strict',
		vocMode: 'classic', vocMitigateSigns: false, combustMitigateSameSign: true,
		pofReversal: true, fixedStarOrb: 2, perfectionStrict: 'strict', includeOuter: false,
		collectionRequireReception: true, refranationAsDestruction: true,
	},
	sequence: {
		ascEarlyDeg: 0, ascLateDeg: 30, considerationsMode: 'ignore',
		vocMode: 'classic', vocMitigateSigns: false, combustMitigateSameSign: true,
		pofReversal: false, fixedStarOrb: 1, perfectionStrict: 'strict', includeOuter: false,
		orbMode: 'sequence', collectionRequireReception: true, refranationAsDestruction: true,
		refranationIncludeSignChange: true, interferenceTiming: 'speed', combustExemptConjAnswer: true,
		onePlanetBoth: 'D',
	},
	hellenistic: {
		ascEarlyDeg: 2, ascLateDeg: 28, considerationsMode: 'lenient',
		vocMode: 'kenodromia', vocMitigateSigns: false, combustMitigateSameSign: false,
		pofReversal: true, fixedStarOrb: 1.5, perfectionStrict: 'standard', includeOuter: false,
		lotsSet: 'core15', cazimiOrb: 1, underBeamsOrb: 15,
	},
	medieval: {
		ascEarlyDeg: 3, ascLateDeg: 27, considerationsMode: 'warn',
		vocMode: 'exempt4', vocMitigateSigns: true, combustMitigateSameSign: true,
		pofReversal: true, fixedStarOrb: 3, perfectionStrict: 'standard', includeOuter: false,
		cazimiOrb: 16 / 60, combustOrb: 8, underBeamsOrb: 15, hourAgreementVariant: 'bonatti',
		collectionRequireReception: true, timingVariant: 'byHouse',
	},
	modern: {
		ascEarlyDeg: 0, ascLateDeg: 30, considerationsMode: 'ignore',
		vocMode: 'classic', vocMitigateSigns: false, combustMitigateSameSign: true,
		pofReversal: false, fixedStarOrb: 5, perfectionStrict: 'lenient', includeOuter: true,
		vocIncludeOuter: true, partileDef: 'le1', oppositionVerdict: 'yes_but', parentHousesVariant: 'modern',
	},
};

// hsys: 0=整宫 1=Alcabitius 2=Regiomontanus 3=Placidus（null=不联动，保持用户当前值）
// termsVariant: 0=埃及界 1=托勒密界(校勘本 Tetrabiblos) 2=托勒密界(经典传本,默认档所用) 3=迦勒底界(推演)
// tripSystem: 'ptolemaic'（水象三分主=火星）| 'dorothean'（三主含参与、水象日主=金星）
// tradition: 1=七曜 0=七曜+三王星
// lotReversal: 后端福点昼夜反转(1=反转/0=恒昼式) —— 与本档判读 pofReversal 同值,保证
//   盘面福点(后端算)与判读阿拉伯点(前端算)口径一致(此前默认档盘面反转/判读不反转,潜在错位)。
export const HORARY_SCHOOLS = {
	classical: {
		id: 'classical', cn: '经典主流', short: '经典',
		backend: { hsys: 2, termsVariant: 2, tripSystem: 'ptolemaic', tradition: 1, westNodeType: null, geminiBoundEmended: 0, lotReversal: 0 },
		judge: { ...judgeDefaults(), ...SCHOOL_JUDGE_DIFF.classical },
		desc: 'Regiomontanus 宫制、托勒密界（经典传本）、Ptolemy 三分制；可判性以警示为主，福点不按昼夜反转。',
	},
	renaissance: {
		id: 'renaissance', cn: '文艺复兴', short: '文艺复兴',
		backend: { hsys: 2, termsVariant: 2, tripSystem: 'ptolemaic', tradition: 1, westNodeType: null, geminiBoundEmended: 0, lotReversal: 0 },
		judge: { ...judgeDefaults(), ...SCHOOL_JUDGE_DIFF.renaissance },
		desc: '1647 事实标准基线：Regiomontanus、托勒密界（经典传本）、水象＝火星；空亡按容许度 12°30′，满分表计分、映点恒星全参与，冲相「成而复失」细分。',
	},
	strict: {
		id: 'strict', cn: '当代严谨', short: '严谨',
		backend: { hsys: 2, termsVariant: 0, tripSystem: 'dorothean', tradition: 1, westNodeType: null, geminiBoundEmended: 0, lotReversal: 1 },
		judge: { ...judgeDefaults(), ...SCHOOL_JUDGE_DIFF.strict },
		desc: 'Regiomontanus 宫制、埃及界、Dorotheus 三分制；紧容许度、严格可判性门槛，汇集须容纳、撤回即破坏，福点按昼夜反转。',
	},
	sequence: {
		id: 'sequence', cn: '序列判读', short: '序列',
		backend: { hsys: 2, termsVariant: 2, tripSystem: 'ptolemaic', tradition: 1, westNodeType: null, geminiBoundEmended: 0, lotReversal: 0 },
		judge: { ...judgeDefaults(), ...SCHOOL_JUDGE_DIFF.sequence },
		desc: '无-orb 序列口径：只看相位能否最终精确（线性外推、本座内完成），几乎弃用判前考量；恒星仅取紧轨。',
	},
	hellenistic: {
		id: 'hellenistic', cn: '希腊化', short: '希腊化',
		backend: { hsys: 0, termsVariant: 0, tripSystem: 'dorothean', tradition: 1, westNodeType: null, geminiBoundEmended: 0, lotReversal: 1 },
		judge: { ...judgeDefaults(), ...SCHOOL_JUDGE_DIFF.hellenistic },
		desc: '整宫制、埃及界、宗派为纲；月空按 30° 内无准确相位（不拘星座界），点集全启用，福点按昼夜反转。',
	},
	medieval: {
		id: 'medieval', cn: '中世纪', short: '中世纪',
		backend: { hsys: 1, termsVariant: 0, tripSystem: 'dorothean', tradition: 1, westNodeType: null, geminiBoundEmended: 0, lotReversal: 1 },
		judge: { ...judgeDefaults(), ...SCHOOL_JUDGE_DIFF.medieval },
		desc: 'Alcabitius 宫制、埃及界、Dorotheus 三分制；日心 16′/燃烧 8°、时主按落座元素口径，月在金牛/巨蟹/射手/双鱼豁免空相。',
	},
	modern: {
		id: 'modern', cn: '现代心理', short: '现代',
		backend: { hsys: 3, termsVariant: 2, tripSystem: 'ptolemaic', tradition: 0, westNodeType: null, geminiBoundEmended: 0, lotReversal: 0 },
		judge: { ...judgeDefaults(), ...SCHOOL_JUDGE_DIFF.modern },
		desc: 'Placidus 宫制、含三王星；不以命度早晚拒判，空亡计三王星，恒星容许放宽，福点不反转。',
	},
};

// 星座键 → 中世纪「月不空」豁免（Moon in Taurus/Cancer/Sagittarius/Pisces）。
export const VOC_EXEMPT_SIGNS = ['taurus', 'cancer', 'sagittarius', 'pisces'];

export function schoolOf(id){
	return HORARY_SCHOOLS[id] || HORARY_SCHOOLS.classical;
}

// 取某档下发 /chart 的字段补丁（仅含非 null 后端字段；tripSystem 仅前端消费不下发）。
// overrides（可选）：高级面板逐项覆盖（仅收编 spec 内 sendToBackend 的键）。
export function horaryBackendFields(id, overrides){
	const b = schoolOf(id).backend || {};
	const out = {};
	if(b.hsys !== null && b.hsys !== undefined) out.hsys = b.hsys;
	if(b.termsVariant !== null && b.termsVariant !== undefined) out.termsVariant = b.termsVariant;
	if(b.tradition !== null && b.tradition !== undefined) out.tradition = b.tradition;
	if(b.westNodeType !== null && b.westNodeType !== undefined) out.westNodeType = b.westNodeType;
	if(b.geminiBoundEmended) out.geminiBoundEmended = b.geminiBoundEmended;
	// 福点反转随档下发（0=恒昼式,与判读 pofReversal 对齐;买通盘面与判读的福点口径）。
	if(b.lotReversal !== null && b.lotReversal !== undefined) out.lotReversal = b.lotReversal;
	if(overrides){
		BACKEND_KEYS.forEach((k) => {
			if(overrides[k] !== undefined && overrides[k] !== null){ out[k] = overrides[k]; }
		});
	}
	return out;
}

// 取某档传入 runHorary 的判读 opts（含 tripSystem 供尊贵注记 + 四层合并）。
// globals（可选）：utils/divinationJudgeGlobals.divinationJudgeOverrides() 的产物
//   （只含用户改过的键）。divination/ 层保持纯净——不在此处直接读 localStorage,
//   由 UI 调用方（HoraryJudgment/aiAnalysisContext/择日）显式传入;缺省 = 无全局层（现行为）。
export function horaryJudgeOpts(id, overrides, globals){
	const sc = schoolOf(id);
	const base = { school: sc.id, tripSystem: sc.backend.tripSystem, termsVariant: sc.backend.termsVariant, geminiEmended: !!(sc.backend.geminiBoundEmended), ...judgeDefaults() };
	// 第 2 层：全局仓（只收编判读域白名单键,防外来键渗入）。
	if(globals && typeof globals === 'object'){
		JUDGE_KEYS.forEach((k) => {
			if(globals[k] !== undefined && globals[k] !== null){ base[k] = globals[k]; }
		});
	}
	// 第 3 层：流派差异集（学理绑定,恒压过全局）。
	Object.assign(base, SCHOOL_JUDGE_DIFF[sc.id] || {});
	// 第 4 层：页面 overrides。
	if(overrides && typeof overrides === 'object'){
		Object.keys(overrides).forEach((k) => {
			if(overrides[k] === undefined || overrides[k] === null) return;
			if(k === 'geminiBoundEmended'){ base.geminiEmended = !!overrides[k]; return; }
			base[k] = overrides[k];
		});
	}
	return base;
}

// 高级面板「当前有效值」：预设 ∪ overrides（含 backend 键;供控件回显）。
export function effectiveHoraryParams(id, overrides){
	const sc = schoolOf(id);
	const eff = { ...sc.backend, ...sc.judge, ...(overrides || {}) };
	delete eff.westNodeType;
	return eff;
}

// 已自定义项数（与任一预设精确匹配则 0）。
export function overrideCount(overrides){
	return overrides ? Object.keys(overrides).filter((k) => overrides[k] !== undefined && overrides[k] !== null).length : 0;
}

// 反查：给定当前 fields（后端字段）反推最贴合的档（用于「档与手动改动不一致」时的显示回落）。
// 仅按 hsys 主键匹配；匹配不到回落 classical。
export function presetOf(fields){
	const hsys = fields && fields.hsys && fields.hsys.value !== undefined ? fields.hsys.value : null;
	if(hsys === null) return 'classical';
	const hit = HORARY_SCHOOL_ORDER.find((id) => HORARY_SCHOOLS[id].backend.hsys === hsys);
	return hit || 'classical';
}

// 精确匹配版：overrides 为空 → 显预设名;有覆盖 → 『预设名·已自定义 N 项』语义由 UI 拼装。
export function presetLabelOf(id, overrides){
	const n = overrideCount(overrides);
	const sc = schoolOf(id);
	return n > 0 ? `${sc.cn} ·（已自定义 ${n} 项）` : sc.cn;
}

// 选择器 options（antd Select）。
export function horarySchoolSelectOptions(){
	return HORARY_SCHOOL_ORDER.map((id) => ({ label: HORARY_SCHOOLS[id].cn, value: id }));
}

export default HORARY_SCHOOLS;
