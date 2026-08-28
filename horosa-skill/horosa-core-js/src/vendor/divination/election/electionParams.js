// divination/election/electionParams.js
// 择日「流派口径」参数层（对齐卜卦 horarySchools 的四层优先级范式）：
//   内建默认(零回归值) < 全局仓(judgeLayerOverrides,只含用户改过的键)
//   < 流派差异集(westernSchools[id].calibre,学理显式绑定恒压过全局) < 页面「流派口径」逐项覆盖。
// 设计约束：electionCalibreDefaults() 的全部取值必须使引擎行为与参数不存在时逐字节一致
// （modern_main 不绑定任何口径 → 默认档输出与既往 golden 完全相同）。
import { schoolOf } from './westernSchools.js';

// ── 页面「流派口径」控件总表（UI 渲染 + 有效值解析共用单一真值）────────────────
// scope: 'calibre'=左栏流派口径区渲染; 'lots'=阿拉伯点构造(亦渲染于流派口径区);
// 每项 options 由 UI 前置一枚 { value:'', label:'随流派' }。
export const ELECTION_PARAM_SPEC = [
	{ key: 'termsVariant', group: '尊贵', label: '界系（判读层）', type: 'select', default: 0,
		options: [
			{ value: 0, label: '埃及界' }, { value: 1, label: '托勒密界·校勘本' },
			{ value: 2, label: '托勒密界·经典传本' }, { value: 3, label: '迦勒底界（推演）' },
		],
		hint: '作用于胜利星/尊贵矩阵等判读层界主查询；中栏盘面界环仍由「设置→星盘设置」的全局界系控制。' },
	{ key: 'tripSystem', group: '尊贵', label: '三分制', type: 'select', default: 'dorothean',
		options: [
			{ value: 'dorothean', label: 'Dorotheus 三主（含共主）' },
			{ value: 'ptolemaic', label: 'Ptolemy 二主（水象＝火星）' },
		] },
	{ key: 'orbProfile', group: '相位', label: '容许度档', type: 'select', default: 'modern',
		options: [
			{ value: 'modern', label: '现代宽轨（后端半距和原样）' },
			{ value: 'moiety', label: '古典 moiety（光半径和收紧）' },
			{ value: 'sign', label: '整宫紧轨（须同座位相）' },
		],
		hint: '前端按档二次收紧后端返回的相位；月相机制/凶星处理/格局等自算模块随之变。' },
	{ key: 'vocMode', group: '月亮', label: '空亡口径', type: 'select', default: 'classic',
		options: [
			{ value: 'classic', label: '无入相即空（1647·现行）' }, { value: 'by_orb', label: '容许度 12°30′' },
			{ value: 'by_sign_perfect', label: '本座内须完成（现代）' }, { value: 'by_sign_orb', label: '本座内入容许度（16c）' },
			{ value: 'kenodromia', label: '30° 法（希腊化）' }, { value: 'exempt4', label: '按座＋四座豁免（中世纪）' },
		] },
	{ key: 'bodySet', group: '用星', label: '用星集', type: 'select', default: 'modern10',
		options: [
			{ value: 'modern10', label: '含三王星（十星）' },
			{ value: 'classical7', label: '七曜为纲（三王星仅注记）' },
		] },
	{ key: 'mansionAnchor', group: '月宿', label: '28宿锚点', type: 'select', default: 'equal_aries0',
		options: [
			{ value: 'equal_aries0', label: '白羊0°均分（Agrippa）' },
			{ value: 'sheratan', label: '实星锚 Sheratan（Picatrix 抄本·随岁差）' },
		] },
	// ── 阿拉伯点构造（WP-B）───────────────────────────────────────────
	{ key: 'marriageTradition', group: '点', label: '婚姻点传统', type: 'select', default: 'valens',
		options: [
			{ value: 'valens', label: '金土式（Valens·Lilly 承之）' },
			{ value: 'paulus', label: '金日/火月式（Paulus·昼夜不反）' },
		] },
	{ key: 'querentGender', group: '点', label: '婚点视角', type: 'select', default: 'male',
		hint: '当事人视角,仅作用于婚姻点公式的男/女式选取。',
		options: [ { value: 'male', label: '男方' }, { value: 'female', label: '女方' } ] },
	{ key: 'erosConstruction', group: '点', label: '爱欲/必然构造', type: 'select', default: 'paulus',
		options: [
			{ value: 'paulus', label: '金/水式（Paulus）' },
			{ value: 'valens', label: '福-精神对式（Valens）' },
		] },
	{ key: 'lotsReversal', group: '点', label: '点位昼夜反转', type: 'select', default: 'classic',
		options: [
			{ value: 'classic', label: '按区分反转（传世标准）' },
			{ value: 'schmidt', label: '外层不反转（近人实验说）' },
		],
		hint: '仅作用于爱欲/必然/勇气/胜利/报应五点的外层星；内嵌福/精神点恒随区分。' },
	// ── 合参（时主/回归/主限;WP-H）────────────────────────────────────
	{ key: 'firdariaNightOrder', group: '合参', label: '法达夜生交点位', type: 'select', default: 'nodes_after_mars',
		options: [
			{ value: 'nodes_after_mars', label: '交点承火星后（现行）' },
			{ value: 'nodes_end', label: '交点缀七曜末' },
		] },
	{ key: 'zrLot', group: '合参', label: 'ZR 释放点', type: 'select', default: 'fortune',
		options: [ { value: 'fortune', label: '幸运点（身体/境遇）' }, { value: 'spirit', label: '精神点（事业/行动）' } ] },
	{ key: 'pdTimeKey', group: '合参', label: '主限时间钥匙', type: 'select', default: 'Ptolemy',
		options: [
			{ value: 'Ptolemy', label: '1°=1年' }, { value: 'Naibod', label: '0°59′08″（日均行）' },
			{ value: 'Cardan', label: '0°59′12″' }, { value: 'Placidus', label: '半弧三分框架' },
		],
		hint: '仅作用于「合参」页主限命中列表的补拉请求;主限引擎与默认路径只读不碰。' },
];

export const ELECTION_PARAM_BY_KEY = {};
ELECTION_PARAM_SPEC.forEach((p) => { ELECTION_PARAM_BY_KEY[p.key] = p; });

// 全局仓可渗入判读层的键（judgeLayerOverrides 产物白名单;只收编择日消费的）。
const GLOBAL_JUDGE_KEYS = [
	'cazimiOrb', 'combustOrb', 'underBeamsOrb',
	'vocMode', 'vocIncludeOuter', 'viaCombustaVariant',
	'fixedStarOrb', 'fixedStarOrbMode', 'partileDef', 'antisciaOrb',
	// [R5-P2] 判读两键(抽屉④节 scope note 明言「作用于卜卦盘/择日盘」——此前只接了卜卦腿)
	'combustMitigateSameSign', 'antiscia',
];

// 内建默认 = 引擎既有硬编码行为（零回归锚）。
export function electionCalibreDefaults(){
	return {
		termsVariant: 0, tripSystem: 'dorothean', orbProfile: 'modern',
		vocMode: 'classic', vocIncludeOuter: false, vocMitigateSigns: false,
		viaCombustaVariant: 'standard', bodySet: 'modern10', mansionAnchor: 'equal_aries0',
		fixedStarOrb: 1, fixedStarOrbMode: 'school', partileDef: 'same_degree', antisciaOrb: 1,
		marriageTradition: 'valens', querentGender: 'male', erosConstruction: 'paulus', lotsReversal: 'classic',
		firdariaNightOrder: 'nodes_after_mars', zrLot: 'fortune', pdTimeKey: 'Ptolemy',
	};
}

// 四层合并 → 有效口径 eff。globals=UI 传入的 judgeLayerOverrides() 展开物（可夹杂其它 opts 键,按白名单收编）;
// overrides=extra.electionParams（''/null/undefined 视为「随流派」跳过）。
export function resolveElectionParams(westSchoolId, globals, overrides){
	const sc = schoolOf(westSchoolId);
	const eff = electionCalibreDefaults();
	if(globals && typeof globals === 'object'){
		GLOBAL_JUDGE_KEYS.forEach((k) => {
			if(globals[k] !== undefined && globals[k] !== null){ eff[k] = globals[k]; }
		});
	}
	Object.assign(eff, sc.calibre || {});
	if(overrides && typeof overrides === 'object'){
		Object.keys(overrides).forEach((k) => {
			const v = overrides[k];
			if(v === undefined || v === null || v === '') return;
			eff[k] = v;
		});
	}
	eff.schoolId = sc.id;
	return eff;
}

// 已自定义项数（供左栏徽标）。
export function calibreOverrideCount(overrides){
	if(!overrides) return 0;
	return Object.keys(overrides).filter((k) => overrides[k] !== undefined && overrides[k] !== null && overrides[k] !== '').length;
}

// 口径摘要（AI 快照 [流派口径] 段 + 帮助显示;只报判读真消费面）。
export function calibreSummary(eff){
	const label = (key, val) => {
		const spec = ELECTION_PARAM_BY_KEY[key];
		if(!spec) return String(val);
		const hit = (spec.options || []).find((o) => o.value === val);
		return hit ? hit.label : String(val);
	};
	return [
		`界系(判读层)：${label('termsVariant', eff.termsVariant)}`,
		`三分制：${label('tripSystem', eff.tripSystem)}`,
		`容许度档：${label('orbProfile', eff.orbProfile)}`,
		`空亡口径：${label('vocMode', eff.vocMode)}${eff.vocIncludeOuter ? '（计三王星）' : ''}`,
		`用星集：${label('bodySet', eff.bodySet)}`,
		`28宿锚点：${label('mansionAnchor', eff.mansionAnchor)}`,
		`婚姻点：${label('marriageTradition', eff.marriageTradition)}·${eff.querentGender === 'female' ? '女方' : '男方'}视角`,
		`爱欲/必然构造：${label('erosConstruction', eff.erosConstruction)}`,
	];
}

export default resolveElectionParams;
