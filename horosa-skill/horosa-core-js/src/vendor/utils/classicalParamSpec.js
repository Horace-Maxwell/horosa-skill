// utils/classicalParamSpec.js — 古典排盘参数单一真值源(spec 表)。
//
// [WP-1] 一键多方登记的病根:同一个键要在 ①CLASSICAL_GLOBAL_DEFAULTS ②INT/FLOAT_KEYS
// ③newEmptyFields 播种 ④ASTRO_CHART_FIELDS 挂载齿轮 ⑤ChartDisplaySelector 控件
// ⑥Java 白名单 ⑦快照自陈表 至少七处出现——历史上 viaCombustaVariant 漏③、三开关漏⑤
// 都是「多方手工登记漂移」实锤。本表把「键的身份」(默认值/类型/档位/标签/分组/下发形态)
// 收成单源;classicalChartGlobals 的 DEFAULTS/INT_KEYS/FLOAT_KEYS 由本表派生,
// 其余各方由契约测试 classicalParamSpec.contract.test.js 锁「与本表全等」(漏键即红)。
//
// 字段语义:
//   key        前端键名(fields/全局仓/record 同名)
//   group      「星盘设置」抽屉第③节子组名(spec 驱动分组渲染的锚)
//   label      控件标签(中文·文献风格,同时供快照自陈行复用)
//   type       'segmented'(≤4 档)|'select'(多档)|'switch'(0/1)
//   options    [{value,label}](switch 型省略)
//   default    默认值 == 后端现硬编码值(零回归锚,恒不下发侧)
//   valueType  'int'|'float'|'str' → 派生 INT_KEYS/FLOAT_KEYS(normalize 强转口径)
//   backendKey 前后端键名不同时的后端名(fixedStarOrb→starOrb)
//   send       'nonDefault'=非默认才进 /chart 请求体(经 classicalBackendOverrides 或
//              natalClassicalParams 头键段)|'never'=纯前端键(partileDef 类)
//   seed       'always'=newEmptyFields 恒播种 wrapper|'conditional'=仅全局非默认才播
//              (schema 历史无此键的,条件播保默认态键集逐字节不变)
//              |'never'=不播种=本机全局偏好层:不进 fields/record 链(存档不随盘,换机回本机值);
//              AI 快照面由 [F11] 快照敏感键收口、判读面由 judgeLayerOverrides 收口。
//              此集由 classicalSixthRoundParity.test.js 枚举冻结,扩张必须显式过审。
//   hint       控件旁次级提示(可选)
//
// 🔴 铁律:新增古典键**必须**先在本表登记,再走合同链(准则见 docs/DATA_MANAGEMENT_PLAYBOOK)。
// 🔴 default 必须等于后端 perchart/flatlib 现硬编码值——「默认即现状」被违反=全站口径漂移。

export const CLASSICAL_PARAM_SPEC = [
	// ── 界与尊贵 ──────────────────────────────────────────────────────────
	{ key: 'termsVariant', group: '界与尊贵', label: '界系（界主 · 尊贵 · 互容接纳）', type: 'segmented', valueType: 'int',
		default: 0, send: 'nonDefault', seed: 'conditional',
		options: [
			{ value: 0, label: '埃及界' },
			{ value: 1, label: '托勒密界·校勘本' },
			{ value: 2, label: '托勒密界·经典传本' },
			{ value: 3, label: '迦勒底界' },
			{ value: 4, label: '自定义界表' },   // [WP-7] 编辑器存表后生效;无表自动降级埃及
		] },
	{ key: 'geminiBoundEmended', group: '界与尊贵', label: '双子界序（1647 印本两皆有据）', type: 'segmented', valueType: 'int',
		default: 0, send: 'nonDefault', seed: 'conditional', enabledWhen: (v) => Number(v.termsVariant) === 2,
		options: [
			{ value: 0, label: '忠原书（♄21–25/♂25–30）' },
			{ value: 1, label: '校勘对调（♂21–25/♄25–30）' },
		] },
	{ key: 'leoBoundFirst', group: '界与尊贵', label: '托勒密界 · 狮子土星优先', type: 'switch', valueType: 'int',
		default: 0, send: 'nonDefault', seed: 'always', enabledWhen: (v) => Number(v.termsVariant) === 1,
		hint: '仅校勘本生效' },
	{ key: 'triplicity', group: '界与尊贵', label: '三分制（triplicity 主星体系）', type: 'segmented', valueType: 'str',
		default: 'Dorothean', send: 'nonDefault', seed: 'always',
		options: [
			{ value: 'Dorothean', label: '多罗特三主' },
			{ value: 'Ptolemaic', label: '托勒密二主' },
			{ value: 'PtolemaicWaterVariant', label: '水象变体' },
		] },
	// ── [WP-4] 尊贵与判定批 ──
	{ key: 'dignityDebilities', group: '界与尊贵', label: '弱陷计负分（陷 −5 · 落 −4）', type: 'switch', valueType: 'int',
		default: 1, send: 'nonDefault', seed: 'conditional' },
	{ key: 'peregrineScore', group: '界与尊贵', label: '游离（外来）减分', type: 'segmented', valueType: 'int',
		default: -5, send: 'never', seed: 'never',
		options: [
			{ value: -5, label: '−5（1647）' },
			{ value: 0, label: '不减分' },
		] },
	{ key: 'almutenTripMode', group: '界与尊贵', label: 'Almuten 三分计分', type: 'segmented', valueType: 'str',
		default: 'all', send: 'nonDefault', seed: 'conditional',
		options: [
			{ value: 'all', label: '三主全计' },
			{ value: 'sectRulerOnly', label: '仅当值主' },
		] },
	{ key: 'domicileMasterMethod', group: '昼夜与区分', label: '主宰主星判法（Domicile Master）', type: 'segmented', valueType: 'str',
		default: 'domicile', send: 'never', seed: 'never',
		options: [
			{ value: 'domicile', label: '庙主派（Porphyry·Antiochus）' },
			{ value: 'bound', label: '界主派（Valens·Rhetorius）' },
		] },
	{ key: 'dynamicalDivisions', group: '昼夜与区分', label: '动力学区分（象限强度分区）', type: 'switch', valueType: 'int',
		default: 0, send: 'never', seed: 'never' },
	{ key: 'busyPlaces', group: '昼夜与区分', label: '有利宫位（chrematistikoi）', type: 'select', valueType: 'str',
		default: '1,4,5,7,10,11', send: 'never', seed: 'never',
		options: [
			{ value: '1,4,5,7,10,11', label: '1·4·5·7·10·11（通行）' },
			{ value: '1,4,7,10', label: '仅四角宫' },
			{ value: '1,2,4,5,7,9,10,11', label: '含 2·9（宽集）' },
			{ value: '1,3,4,5,7,9,10,11', label: '含 3·9（宽集·三九向）' },
		] },
	{ key: 'planetaryHourMethod', group: '昼夜与区分', label: '行星时制式', type: 'segmented', valueType: 'str',
		default: 'sunrise', send: 'nonDefault', seed: 'conditional',
		options: [
			{ value: 'sunrise', label: '日出起算 · 等长时（现行）' },
			{ value: 'unequal', label: '昼夜不等时（传统）' },
			{ value: 'equal24', label: '廿四时等分' },
		] },
	// ── 昼夜与区分 ────────────────────────────────────────────────────────
	{ key: 'sectBuffer', group: '昼夜与区分', label: '区分判定（昼 / 夜 · sect）', type: 'segmented', valueType: 'str',
		default: 'geo', send: 'nonDefault', seed: 'always',
		options: [
			{ value: 'geo', label: '几何地平' },
			{ value: 'ptolemy5', label: 'Ptolemy 5°' },
			{ value: 'apparent', label: '视地平（真日出没·含折射）' },   // [WP-2] 第三档:swe rise_trans,极昼夜回落几何
		] },
	{ key: 'westNodeType', group: '昼夜与区分', label: '月交点（真 / 平 · 全盘随动）', type: 'segmented', valueType: 'str',
		default: 'mean', send: 'nonDefault', seed: 'always',
		options: [
			{ value: 'mean', label: '平交点' },
			{ value: 'true', label: '真交点' },
		] },
	{ key: 'nodeExaltation', group: '昼夜与区分', label: '交点入旺（北交旺双子 · 南交旺射手）', type: 'switch', valueType: 'int',
		default: 0, send: 'nonDefault', seed: 'conditional' },
	// saturnExalt20 已删档(2026-08-18 用户拍板):exalt 表 degree 位全仓零消费者=真死开关,照金字塔模式全链退场。
	// ── 太阳三态 ──────────────────────────────────────────────────────────
	{ key: 'cazimiOrb', group: '太阳三态', label: '日心 cazimi', type: 'segmented', valueType: 'float',
		default: 17 / 60, send: 'nonDefault', seed: 'always',
		options: [
			{ value: 17 / 60, label: '17′（1647）' },
			{ value: 16 / 60, label: '16′（中世纪）' },
			{ value: 1, label: '1°（早期）' },
		] },
	{ key: 'combustOrb', group: '太阳三态', label: '燃烧上界', type: 'segmented', valueType: 'float',
		default: 8.5, send: 'nonDefault', seed: 'always',
		options: [
			{ value: 8.5, label: '8°30′（1647）' },
			{ value: 8, label: '8°（中世纪）' },
			{ value: 15, label: '15°（希腊化）' },   // [WP-2] 流派分档:希腊化传统宽界
		] },
	{ key: 'combustOwnChariotExempt', group: '太阳三态', label: '界内三分内免燃烧（own chariot）', type: 'switch', valueType: 'int',
		default: 0, send: 'nonDefault', seed: 'conditional', hint: 'Porphyry' },
	{ key: 'underBeamsOrb', group: '太阳三态', label: '日光束外界（偕日相束级恒逐星弧）', type: 'segmented', valueType: 'float',
		default: 17, send: 'nonDefault', seed: 'always',
		options: [
			{ value: 17, label: '17°（1647）' },
			{ value: 15, label: '15°（较古）' },
		] },
	// ── 月亮与空亡 ────────────────────────────────────────────────────────
	{ key: 'vocMode', group: '月亮与空亡', label: '空亡口径（月亮 isVOC 全盘随动）', type: 'select', valueType: 'str',
		default: 'classic', defaultAliases: ['lilly', 'backend'], send: 'nonDefault', seed: 'always',
		options: [
			{ value: 'classic', label: '无入相即空（1647 · 现行）' },
			{ value: 'by_orb', label: '容许度 12°30′' },
			{ value: 'by_sign_perfect', label: '本座内须完成（现代）' },
			{ value: 'by_sign_orb', label: '本座内入容许度（16c）' },
			{ value: 'kenodromia', label: '30° 法（希腊化）' },
			{ value: 'exempt4', label: '无入相＋四座豁免（中世纪）' },
		] },
	{ key: 'vocIncludeOuter', group: '月亮与空亡', label: '空亡计三王星', type: 'switch', valueType: 'int',
		default: 0, send: 'nonDefault', seed: 'always', enabledWhen: (v) => v.vocMode !== undefined && v.vocMode !== 'classic',
		hint: '仅非 1647 口径生效' },
	{ key: 'westLilithType', group: '月亮与空亡', label: '黑月莉莉丝（真 / 平远地点）', type: 'segmented', valueType: 'str',
		default: 'mean', send: 'nonDefault', seed: 'conditional',
		options: [
			{ value: 'mean', label: '平均远地点' },
			{ value: 'true', label: '真实远地点（osculating）' },
		] },
	{ key: 'topocentricMoon', group: '月亮与空亡', label: '月亮站心视差修正', type: 'switch', valueType: 'int',
		default: 0, send: 'nonDefault', seed: 'conditional', hint: '影响月亮黄经 ≤1° · 福点随动' },
	{ key: 'viaCombustaVariant', group: '月亮与空亡', label: '燃烧之路边界（月亮凶区 · 全站随动）', type: 'select', valueType: 'str',
		default: 'standard', send: 'nonDefault', seed: 'always',
		options: [
			{ value: 'standard', label: '天秤15°–天蝎15°（传统）' },
			{ value: 'narrow', label: '窄口径（天秤28°–天蝎7°）' },
			{ value: 'scorpioFull', label: '天秤后15°＋天蝎全宫' },
			{ value: 'bothFull', label: '天秤＋天蝎全段' },
		] },
	// ── 希腊点 ────────────────────────────────────────────────────────────
	{ key: 'lotReversal', group: '希腊点', label: '福点按昼夜反转（关则恒昼式）', type: 'switch', valueType: 'int',
		default: 1, send: 'nonDefault', seed: 'always' },
	{ key: 'lotsDocReverse', group: '希腊点', label: '四点文档序公式（婚·子·友·疾）', type: 'switch', valueType: 'int',
		default: 0, send: 'nonDefault', seed: 'conditional' },
	// ── [WP-3] 希腊点变体批(perchart._applyLotVariants 一体后处理;默认=历史现值零回归) ──
	{ key: 'hermeticLotsReversal', group: '希腊点', label: '七星点按昼夜反转（关则恒同式）', type: 'switch', valueType: 'int',
		default: 1, send: 'nonDefault', seed: 'conditional', hint: '批判本校勘' },
	{ key: 'erosConstruction', group: '希腊点', label: '爱欲 · 必然构成', type: 'segmented', valueType: 'str',
		default: 'paulus', send: 'nonDefault', seed: 'conditional',
		options: [
			{ value: 'paulus', label: 'Paulus 式（金星·水星系）' },
			{ value: 'valens', label: 'Valens 式（福点·精神系）' },
		] },
	{ key: 'lotFortuneVariant', group: '希腊点', label: '福点公式变体', type: 'segmented', valueType: 'str',
		default: 'standard', send: 'nonDefault', seed: 'conditional',
		options: [
			{ value: 'standard', label: '标准昼夜式' },
			{ value: 'moonAboveNight', label: '月在地平上恒夜式' },
		] },
	{ key: 'lotFatherCombustAlt', group: '希腊点', label: '父点土星伏时替代式', type: 'switch', valueType: 'int',
		default: 0, send: 'nonDefault', seed: 'conditional', hint: 'Dorotheus 系' },
	{ key: 'lotProjection', group: '希腊点', label: '点度计数法', type: 'segmented', valueType: 'str',
		default: 'portion', send: 'nonDefault', seed: 'conditional',
		options: [
			{ value: 'portion', label: '度数投射（portion）' },
			{ value: 'sign', label: '整星座（sign）' },
		] },
	// ── 相位与容许度 ──────────────────────────────────────────────────────
	// ── [WP-5a] 容许度体系批(orbSystem 默认 perObject=flatlib 现状「任一星轨覆盖」;
	// 注意现状**不是**半距和——半距和判据只在择日 orbPolicy 判读层,勘察实锤) ──
	{ key: 'orbSystem', group: '相位与容许度', label: '容许度判据体系', type: 'select', valueType: 'str',
		default: 'perObject', send: 'nonDefault', seed: 'conditional',
		options: [
			{ value: 'perObject', label: '星体轨 · 任一覆盖（现行）' },
			{ value: 'byAspect', label: '按相位名（合冲刑拱 8° · 六合 4°）' },
			{ value: 'wholeSign', label: '整星座位相' },
			{ value: 'wholeSignMoiety', label: '整星座内 · 两轨半距和' },
		] },
	{ key: 'luminaryOrbBonus', group: '相位与容许度', label: '发光体 · 四轴轨加成', type: 'segmented', valueType: 'int',
		default: 0, send: 'nonDefault', seed: 'conditional',
		options: [
			{ value: 0, label: '0%' },
			{ value: 10, label: '10%' },
			{ value: 20, label: '20%' },
			{ value: 30, label: '30%' },
		] },
	{ key: 'transitOrb', group: '相位与容许度', label: '行运相位容许度（推运族）', type: 'segmented', valueType: 'float',
		default: 1, send: 'never', seed: 'never',   // 前端推运 asporb 的默认值源(请求仍发 asporb 键)
		options: [
			{ value: 1, label: '1°' },
			{ value: 2, label: '2°' },
			{ value: 3, label: '3°' },
			{ value: 5, label: '5°' },
		] },
	{ key: 'aspectShowOnlyApplying', group: '相位与容许度', label: '相位表只显入相', type: 'switch', valueType: 'int',
		default: 0, send: 'never', seed: 'never' },
	{ key: 'separatingOrbCap', group: '相位与容许度', label: '离相显示上限', type: 'select', valueType: 'float',
		default: 0, send: 'never', seed: 'never',
		options: [
			{ value: 0, label: '不限' },
			{ value: 1, label: '1°' },
			{ value: 2, label: '2°' },
			{ value: 3, label: '3°' },
		] },
	// ── [WP-5b] 相位参与对象扩展(默认全 0=响应零字段零回归;恒星汇合引用现成 chart.stars) ──
	{ key: 'aspectIncludeCusps', group: '相位与容许度', label: '宫头参与相位（≤3°）', type: 'switch', valueType: 'int',
		default: 0, send: 'nonDefault', seed: 'conditional' },
	{ key: 'aspectIncludeLots', group: '相位与容许度', label: '希腊点参与相位（点为受体 · ≤3°）', type: 'switch', valueType: 'int',
		default: 0, send: 'nonDefault', seed: 'conditional' },
	{ key: 'aspectIncludeMidpoints', group: '相位与容许度', label: '中点参与相位（日月四轴 · 硬相 ≤1.5°）', type: 'switch', valueType: 'int',
		default: 0, send: 'nonDefault', seed: 'conditional' },
	{ key: 'partileDef', group: '相位与容许度', label: '正相位 partile 判据（相位表标记 · 尊贵计分）', type: 'segmented', valueType: 'str',
		default: 'same_degree', send: 'never', seed: 'never',
		options: [
			{ value: 'same_degree', label: '同整数度（1647）' },
			{ value: 'le3', label: '≤3°（1677）' },
			{ value: 'le1', label: '≤1°（现代）' },
		] },
	{ key: 'antisciaOrb', group: '相位与容许度', label: '映点接触容许度', type: 'select', valueType: 'float',
		default: 1, send: 'nonDefault', seed: 'always',
		options: [0.5, 1, 1.5, 2, 3].map((v) => ({ value: v, label: `${v}°` })) },
	// ── 恒星与天象 ────────────────────────────────────────────────────────
	{ key: 'fixedStarOrbMode', group: '恒星与天象', label: '恒星轨档（汇合恒星 · 恒星触发）', type: 'segmented', valueType: 'str',
		default: 'school', send: 'nonDefault', seed: 'always', backendKey: 'starOrbMode',
		options: [
			{ value: 'school', label: '按流派平轨' },
			{ value: 'byMagnitude', label: '按星等' },
		] },
	{ key: 'fixedStarOrb', group: '恒星与天象', label: '恒星平轨值', type: 'select', valueType: 'float',
		default: 1, send: 'nonDefault', seed: 'always', backendKey: 'starOrb',
		options: [1, 1.5, 2, 3, 5].map((v) => ({ value: v, label: `${v}°` })) },
	{ key: 'stationMarking', group: '恒星与天象', label: '留驻判定（盘面 S·D 标）', type: 'select', valueType: 'str',
		default: 'off', send: 'nonDefault', seed: 'conditional',
		options: [
			{ value: 'off', label: '关（仅逆行 R 标）' },
			{ value: 'exactWindow', label: '距留点 ≤1 日' },
			{ value: 'distance', label: '距留点黄经 ≤2′' },
			{ value: 'absSpeed', label: '日速 <1′' },
			{ value: 'relSpeed', label: '日速 <3% 均速' },
		] },
	{ key: 'eclipseTimeMode', group: '恒星与天象', label: '食时刻口径（星历食相表）', type: 'segmented', valueType: 'str',
		default: 'max', send: 'never', seed: 'never',   // 走 /astroextra/ephemeris 独立构参,不进 /chart
		options: [
			{ value: 'max', label: '食甚时刻' },
			{ value: 'syzygy', label: '精确朔望' },
		] },
	// ── [WP-6] 返照与推运 ──
	{ key: 'solarReturnVariant', group: '返照与推运', label: '太阳返照法', type: 'segmented', valueType: 'str',
		default: 'precise', send: 'nonDefault', seed: 'conditional',
		options: [
			{ value: 'precise', label: '精确回归（现代）' },
			{ value: 'hellenistic', label: '希腊式（月定上升）' },
		] },
	{ key: 'returnLatitudeMode', group: '返照与推运', label: '返照落宫投影', type: 'segmented', valueType: 'str',
		default: 'ecliptic', send: 'nonDefault', seed: 'conditional',
		options: [
			{ value: 'ecliptic', label: '黄道度（常规）' },
			{ value: 'withLatitude', label: '计入黄纬（Umar al-Tabari 法）' },
		] },
	// ── 宫位与落宫 ────────────────────────────────────────────────────────
	{ key: 'houseCuspAdvance', group: '宫位与落宫', label: '行星落宫 · 宫头前移（整宫制豁免）', type: 'segmented', valueType: 'int',
		default: 5, send: 'nonDefault', seed: 'always',
		options: [
			{ value: 5, label: '5°（传统）' },
			{ value: 3, label: '3°' },
			{ value: 1, label: '1°' },
			{ value: 0, label: '0°（纯宫界）' },
		] },
	// ── [WP-8] 灵学扩展(近代推算体系;默认全关=零字段零卡) ──
	{ key: 'vulcanCalc', group: '灵学扩展', label: '祝融星（推算行星）', type: 'segmented', valueType: 'str',
		default: 'off', send: 'nonDefault', seed: 'conditional',
		options: [
			{ value: 'off', label: '关' },
			{ value: 'weston', label: '轨道根数法' },
			{ value: 'baker', label: '水星系推算' },
		] },
	{ key: 'rayWeighting', group: '灵学扩展', label: '七射线权重', type: 'segmented', valueType: 'str',
		default: 'off', send: 'never', seed: 'never',
		options: [
			{ value: 'off', label: '关' },
			{ value: 'equal', label: '等权' },
			{ value: 'weighted', label: '加权（发光体×3）' },
		] },
	// polarMcMode 已删档(2026-08-18 用户拍板):'aboveHorizon' swap 分支实测不可达(极区兜底后 MC
	// altitudeTrue 恒正,78N/89N×三季全天实证)=唯一非默认档死路;引擎恒走 equator 现状行为,零行为变化。
];

// ── 派生视图(供 classicalChartGlobals/契约测试消费;调用方零遍历成本) ──
export const CLASSICAL_SPEC_KEYS = CLASSICAL_PARAM_SPEC.map((s) => s.key);

export function specDefaults(){
	const out = {};
	CLASSICAL_PARAM_SPEC.forEach((s) => { out[s.key] = s.default; });
	return out;
}

export function specKeysByValueType(vt){
	return CLASSICAL_PARAM_SPEC.filter((s) => s.valueType === vt).map((s) => s.key);
}

export function specByKey(key){
	return CLASSICAL_PARAM_SPEC.find((s) => s.key === key) || null;
}

// 值 → 档位标签(快照自陈/挂载回显复用;无匹配档回原值字符串)。
export function specOptionLabel(key, value){
	const s = specByKey(key);
	if(!s || !s.options){ return `${value}`; }
	const hit = s.options.find((o) => o.value === value || `${o.value}` === `${value}`);
	return hit ? hit.label : `${value}`;
}
