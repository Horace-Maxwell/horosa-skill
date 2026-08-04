// 天星择日·征象条件注册表(前端单源)。
// ⚠ 与 Python astropy/astrostudy/election_scan.py 的 CONDITION_TYPES/GROUP_TYPES 成对:
//   两边键集必须恒等(conditionTypesSync 哨兵机器比对,双向差空);只登记「后端已实现求值器」
//   的类型——绝不先登前端(否则用户可选、后端 invalid_conditions = 死开关)。
// UI 树(带 negate 开关) → compileTree() → 后端条件树(negate 编译为 not 包裹,单通道)。
// 每类 fields = 元数据驱动的参数表单描述(ConditionParamsForm 按 kind 渲染)。

export const GROUP_TYPES = ['all', 'any', 'not', 'xor'];

// 连接门中文单一真值源:工作台行首徽标/连接门四钮/AI 快照树文本三处共用。
export const JOINER_CN = { all: '且', any: '或', xor: '异或' };

// 引擎支持的天体键(与后端 _SWE_BODY + Node 派生一致;label 由 AstroText.AstroMsgCN 取)
export const SCAN_BODIES = [
	'Sun', 'Moon', 'Mercury', 'Venus', 'Mars', 'Jupiter', 'Saturn',
	'Uranus', 'Neptune', 'Pluto', 'North Node', 'South Node', 'Chiron',
];
export const SEVEN_BODIES = ['Sun', 'Moon', 'Mercury', 'Venus', 'Mars', 'Jupiter', 'Saturn'];

const SEVEN_CN = { Sun: '太阳', Moon: '月亮', Mercury: '水星', Venus: '金星', Mars: '火星', Jupiter: '木星', Saturn: '土星' };
export const SEVEN_OPTIONS = SEVEN_BODIES.map((v) => ({ value: v, label: SEVEN_CN[v] }));
export const SEVEN_ANY_OPTIONS = [{ value: 'any', label: '任意' }].concat(SEVEN_OPTIONS);

// ── R3 判读条件族选项(与 election_scan_ext.py 契约同名同值) ──
export const LIGHT_DYNAMICS_ITEM_OPTIONS = [
	{ value: 'translation', label: '传光 Translation' },
	{ value: 'collection', label: '聚光 Collection' },
	{ value: 'prohibition', label: '阻止 Prohibition' },
	{ value: 'frustration', label: '挫败 Frustration' },
	{ value: 'refranation', label: '收回 Refranation' },
	{ value: 'aversion', label: '不合意 Aversion' },
	{ value: 'bending', label: '交点弯曲 Bending' },
	{ value: 'void', label: '空亡(页签口径)' },
];
export const ROYAL_SLOT_OPTIONS = [
	{ value: 'first_occidental', label: '第一西没' },
	{ value: 'first_oriental', label: '第一东升' },
	{ value: 'any_occidental', label: '西没侧(任一)' },
	{ value: 'any_oriental', label: '东升侧(任一)' },
];
export const SECT_JOY_ITEM_OPTIONS = [
	{ value: 'diurnal', label: '昼盘(日在地平上)' },
	{ value: 'of_sect', label: '某星同宗 of-sect' },
	{ value: 'hayyiz', label: '得时 Hayyiz' },
	{ value: 'house_joy', label: '宫喜乐(整宫制)' },
	{ value: 'sign_joy', label: '座喜乐' },
];
export const HAYYIZ_LEVEL_OPTIONS = [
	{ value: 'Hayyiz', label: '得时 Hayyiz' },
	{ value: 'DemiHayyiz', label: '半得时(火星夜阴座)' },
	{ value: 'InWrongPos', label: '失位' },
	{ value: 'None', label: '无' },
];
export const DEGREE_ITEM_OPTIONS = [
	{ value: 'mansion', label: '月站(28宿)' },
	{ value: 'monomoiria', label: '单度主星' },
	{ value: 'darijan', label: 'Darijan 十度分主' },
	{ value: 'quality', label: '度数性质(明暗空烟)' },
	{ value: 'special', label: '特殊度数' },
];
// 与 astropy classical_tables.LUNAR_MANSIONS cn 列逐字(1 基)
const MANSION_CN = ['初星', '腹星', '昴聚', '随星', '冠星', '印星', '臂星', '气星', '目星', '额星',
	'鬃星', '转星', '吠星', '独星', '覆星', '螯星', '冕星', '心星', '尾星', '鸵星',
	'荒星', '屠者吉', '吞者吉', '至吉', '帐吉', '前泻', '后泻', '鱼腹'];
export const MANSION_OPTIONS = MANSION_CN.map((cn, i) => ({ value: i + 1, label: `第${i + 1}宿·${cn}` }));
export const DEGREE_QUALITY_OPTIONS = [
	{ value: 'B', label: '明 Bright' }, { value: 'D', label: '暗 Dark' },
	{ value: 'E', label: '空 Empty' }, { value: 'S', label: '烟 Smoky' },
];
export const SPECIAL_DEGREE_OPTIONS = [
	{ value: 'pitted', label: '陷度 Pitted' },
	{ value: 'azemene', label: '慢病度 Azemene' },
	{ value: 'increasing_fortune', label: '增福度' },
];
export const CLASSICAL_PATTERN_OPTIONS = [
	{ value: 'doryphory', label: '持矛护卫 Doryphory' },
	{ value: 'overcoming', label: '优势压制 Overcoming' },
	{ value: 'besieging_degree', label: '度数围攻(±7°夹)' },
];
export const EMINENCE_BAND_OPTIONS = [
	{ value: 'eminent', label: '显赫(≥8)' },
	{ value: 'notable', label: '显著(6-8)' },
	{ value: 'ordinary', label: '平凡(3-6)' },
	{ value: 'obscure', label: '暗晦(<3)' },
];
export const BEHENIAN_STARS = ['Algol', 'Alcyone', 'Aldebaran', 'Capella', 'Sirius', 'Procyon',
	'Regulus', 'Algorab', 'Spica', 'Arcturus', 'Alphecca', 'Antares', 'Vega', 'Deneb Algedi', 'Fomalhaut'];
export const STAR_OPTIONS = BEHENIAN_STARS.map((v) => {
	const royal = { Aldebaran: '王者·东', Regulus: '王者·北', Antares: '王者·西', Fomalhaut: '王者·南' }[v];
	return { value: v, label: royal ? `${v}(${royal})` : v };
});
export const DECAN_MODE_OPTIONS = [
	{ value: 'planet_in', label: '星体落旬' },
	{ value: 'ruler_is', label: '所落旬主是' },
	{ value: 'talisman', label: '护符择时(ASC或月正当旬)' },
];
export const OVERVIEW_ITEM_OPTIONS = [
	{ value: 'dragon_embrace', label: '龙拥(七星聚一侧)' },
	{ value: 'dragon_intercept', label: '龙截(孤星/双联结)' },
	{ value: 'lone_moon', label: '孤月独明' },
	{ value: 'apriori_power', label: '先验权力(8·12/8·1联结)' },
	{ value: 'eight_kill', label: '八杀朝天(先验+夜生)' },
	{ value: 'strong_jupiter', label: '强吉木星' },
	{ value: 'afflicted_ruler', label: '后天凶星(主6/8/12)' },
	{ value: 'sentient_link', label: '有情/无情联结' },
];
export const APRIORI_WHICH_OPTIONS = [
	{ value: 'any', label: '任意' }, { value: '8_12', label: '8·12 联结' }, { value: '8_1', label: '8·1 联结' },
];
export const PURITY_OPTIONS = [
	{ value: 'any_pure', label: '任一有情档' },
	{ value: 'mundane_pure', label: '有情·世俗纯粹' },
	{ value: 'eso_pure', label: '有情·玄纯粹' },
	{ value: 'eso_mundane', label: '有情·玄谋世俗' },
	{ value: 'insentient', label: '无情' },
];
export const DISPOSITOR_MODE_OPTIONS = [
	{ value: 'final_is', label: '终极主宰是某星' },
	{ value: 'final_exists', label: '存在终极主宰' },
	{ value: 'in_loop', label: '某星在互容环中' },
	{ value: 'loop_exists', label: '存在互容环' },
];
export const DECAN_OPTIONS = Array.from({ length: 36 }, (_, i) => {
	const signCn = ['白羊', '金牛', '双子', '巨蟹', '狮子', '处女', '天秤', '天蝎', '射手', '摩羯', '水瓶', '双鱼'][Math.floor(i / 3)];
	return { value: i + 1, label: `第${i + 1}旬·${signCn}${(i % 3) * 10}-${(i % 3) * 10 + 10}°` };
});

export const ASPECT_ANGLE_OPTIONS = [0, 30, 45, 60, 90, 120, 135, 150, 180];

export const SIGN_OPTIONS = [
	{ value: 0, label: '白羊' }, { value: 1, label: '金牛' }, { value: 2, label: '双子' },
	{ value: 3, label: '巨蟹' }, { value: 4, label: '狮子' }, { value: 5, label: '处女' },
	{ value: 6, label: '天秤' }, { value: 7, label: '天蝎' }, { value: 8, label: '射手' },
	{ value: 9, label: '摩羯' }, { value: 10, label: '水瓶' }, { value: 11, label: '双鱼' },
];
export const HOUSE_OPTIONS = Array.from({ length: 12 }, (_, i) => ({ value: i + 1, label: `${i + 1} 宫` }));

export const LEVEL_OPTIONS = [
	{ value: 'ruler', label: '庙' }, { value: 'exalt', label: '旺' },
	{ value: 'trip', label: '三分' }, { value: 'term', label: '界' }, { value: 'face', label: '面' },
];

export const DIGNITY_STATE_OPTIONS = [
	{ value: 'ruler', label: '入庙' }, { value: 'exalt', label: '入旺' },
	{ value: 'trip', label: '得三分' }, { value: 'term', label: '得界' }, { value: 'face', label: '得面' },
	{ value: 'detriment', label: '落陷(失势)' }, { value: 'fall', label: '入弱(落)' },
	{ value: 'peregrine', label: '游走 Peregrine' },
	{ value: 'cazimi', label: '日心 Cazimi' }, { value: 'combust', label: '燃烧' },
	{ value: 'under_beams', label: '日光下' }, { value: 'free_of_sun', label: '脱离日光' },
	{ value: 'oriental', label: '东出' }, { value: 'occidental', label: '西入' },
	{ value: 'direct', label: '顺行' }, { value: 'retrograde', label: '逆行' }, { value: 'station', label: '留' },
	{ value: 'fast', label: '快速(逾均速)' }, { value: 'slow', label: '迟缓(低均速)' },
	{ value: 'angular', label: '角宫(偶然尊贵)' }, { value: 'succedent', label: '续宫' }, { value: 'cadent', label: '果宫' },
	{ value: 'feral', label: '无相位 Feral' }, { value: 'oob', label: '出界 OOB' },
];

export const CONSIDERATION_ITEM_OPTIONS = [
	{ value: 'moon_voc', label: '月亮空亡 VOC' },
	{ value: 'moon_waxing', label: '月亮增光' }, { value: 'moon_waning', label: '月亮减光' },
	{ value: 'moon_fast', label: '月亮快速' }, { value: 'moon_slow', label: '月亮迟缓' },
	{ value: 'via_combusta', label: '月在燃烧之路' },
	{ value: 'moon_early_sign', label: '月在星座初度' }, { value: 'moon_late_sign', label: '月在星座末度' },
	{ value: 'asc_near_boundary', label: '上升近星座边界' },
	{ value: 'sun_above_horizon', label: '日在地平线上' }, { value: 'sun_below_horizon', label: '日在地平线下' },
];

export const VOC_MODE_OPTIONS = [
	{ value: 'classic', label: '经典(1647)' }, { value: 'by_sign_orb', label: '本座内入容许度' },
	{ value: 'by_sign_perfect', label: '本座内须完成' }, { value: 'by_orb', label: '容许度 12°30′' },
	{ value: 'kenodromia', label: '希腊化 30°' }, { value: 'exempt4', label: '四座豁免' },
];

export const PATTERN_OPTIONS = [
	{ value: 't_square', label: 'T 三角' }, { value: 'grand_trine', label: '大三角' },
	{ value: 'grand_cross', label: '大十字' }, { value: 'kite', label: '风筝' },
	{ value: 'yod', label: '上帝之指 Yod' }, { value: 'mystic_rectangle', label: '神秘矩形' },
];

export const SHAPE_OPTIONS = [
	{ value: 'splash', label: '散布 Splash' }, { value: 'bundle', label: '集束 Bundle' },
	{ value: 'bowl', label: '碗型 Bowl' }, { value: 'locomotive', label: '火车头' },
	{ value: 'seesaw', label: '跷跷板' }, { value: 'sling', label: '投石索 Sling' },
	{ value: 'bucket', label: '桶型 Bucket' }, { value: 'splay', label: '展开 Splay' },
];

export const NUMERIC_FIELD_OPTIONS = [
	{ value: 'Long', label: '黄经 Long', circular: true }, { value: 'Lat', label: '黄纬 Lat' },
	{ value: 'LongSpeed', label: '黄经速度' }, { value: 'LatSpeed', label: '黄纬速度' },
	{ value: 'RA', label: '赤经 RA', circular: true }, { value: 'RASpeed', label: '赤经速度' },
	{ value: 'Decl', label: '赤纬 Decl' }, { value: 'DeclSpeed', label: '赤纬速度' },
	{ value: 'Azimuth', label: '方位角', circular: true }, { value: 'Altitude', label: '地平高度' },
];

export const POINT_KIND_OPTIONS = [
	{ value: 'angle', label: '四轴点' }, { value: 'planet', label: '星体' },
	{ value: 'lot', label: '福点' }, { value: 'fixedLon', label: '固定黄经' },
];
export const ANGLE_ID_OPTIONS = [
	{ value: 'ASC', label: '上升 ASC' }, { value: 'MC', label: '天顶 MC' },
	{ value: 'DESC', label: '下降 DESC' }, { value: 'IC', label: '天底 IC' },
];
export const RELATION_OPTIONS = [
	{ value: 'any', label: '任意主相位' }, { value: 'soft', label: '任意软相位(60/120)' },
	{ value: 'hard', label: '任意硬相位(0/90/180)' }, { value: 'angles', label: '指定相位角' },
	{ value: 'parallel', label: '赤纬平行' }, { value: 'contraparallel', label: '赤纬反平行' },
];

export const MODULUS_OPTIONS = [360, 90, 45, 22.5, 11.25];

const isBody = (v) => SCAN_BODIES.indexOf(v) >= 0;
const nonEmptyArr = (v) => Array.isArray(v) && v.length > 0;

// fields.kind: body | select | multiselect | number | toggle | time | point | midtarget
export const CONDITION_TYPES = {
	aspect: {
		category: 'continuous',
		label: '星体相位',
		defaults: { planetA: 'Moon', planetB: 'Sun', angle: 90, orb: 3, motion: 'any', side: 'any', partile: 'off' },
		fields: [
			{ key: 'planetA', kind: 'body', label: 'A星' },
			{ key: 'planetB', kind: 'body', label: 'B星' },
			{ key: 'angle', kind: 'select', label: '相位', options: ASPECT_ANGLE_OPTIONS.map((a) => ({ value: a, label: `${a}°` })) },
			{ key: 'orb', kind: 'number', label: 'orb', min: 0.1, max: 30, step: 0.5 },
			{ key: 'motion', kind: 'select', label: '入出', options: [{ value: 'any', label: '任意' }, { value: 'applying', label: '入相位' }, { value: 'separating', label: '出相位' }] },
			{ key: 'side', kind: 'select', label: '左右', options: [{ value: 'any', label: '不限左右' }, { value: 'dexter', label: '右相位' }, { value: 'sinister', label: '左相位' }] },
			{ key: 'partile', kind: 'select', label: '正相位', options: [{ value: 'off', label: '不限' }, { value: 'same_degree', label: '正(同度)' }, { value: 'le3', label: '正(≤3°)' }, { value: 'le1', label: '正(≤1°)' }] },
		],
		validate(p){
			if(!isBody(p.planetA) || !isBody(p.planetB)){ return '需选择两颗星体'; }
			if(p.planetA === p.planetB){ return '两端不能是同一星体'; }
			if(!(Number(p.angle) >= 0 && Number(p.angle) <= 180)){ return '相位角需在 0-180°'; }
			if(!(Number(p.orb) > 0 && Number(p.orb) <= 30)){ return '容许度需在 0-30°'; }
			return '';
		},
	},
	in_sign: {
		category: 'continuous',
		label: '星体入座',
		defaults: { planet: 'Moon', signs: [0] },
		fields: [
			{ key: 'planet', kind: 'body', label: '星体' },
			{ key: 'signs', kind: 'multiselect', label: '星座', options: SIGN_OPTIONS },
		],
		validate(p){
			if(!isBody(p.planet)){ return '需选择星体'; }
			if(!nonEmptyArr(p.signs)){ return '至少选一个星座'; }
			return '';
		},
	},
	in_house: {
		category: 'boolean',
		label: '星体入宫',
		defaults: { planet: 'Moon', houses: [1] },
		fields: [
			{ key: 'planet', kind: 'body', label: '星体' },
			{ key: 'houses', kind: 'multiselect', label: '宫位', options: HOUSE_OPTIONS },
		],
		validate(p){
			if(!isBody(p.planet)){ return '需选择星体'; }
			if(!nonEmptyArr(p.houses)){ return '至少选一个宫位'; }
			return '';
		},
	},
	reception: {
		category: 'boolean',
		label: '接纳',
		defaults: { planetA: 'Venus', planetB: 'Moon', levels: ['ruler', 'exalt'], match: 'any', requireAspect: true },
		fields: [
			{ key: 'planetA', kind: 'body', label: '接纳方 A' },
			{ key: 'planetB', kind: 'body', label: '被纳方 B' },
			{ key: 'levels', kind: 'multiselect', label: '层级', options: LEVEL_OPTIONS },
			{ key: 'match', kind: 'select', label: '命中', options: [{ value: 'any', label: '任一层级' }, { value: 'all', label: '全部层级' }] },
			{ key: 'requireAspect', kind: 'toggle', label: '须成相位(古典严格)' },
		],
		validate(p){
			if(!isBody(p.planetA) || !isBody(p.planetB)){ return '需选择两颗星体'; }
			if(p.planetA === p.planetB){ return '两端不能相同'; }
			if(!nonEmptyArr(p.levels)){ return '至少选一个层级'; }
			return '';
		},
	},
	mutual_reception: {
		category: 'boolean',
		label: '互容',
		defaults: { planetA: 'Mercury', planetB: 'Venus', levels: ['ruler', 'exalt'], pairing: 'any_pair', requireAspect: true },
		fields: [
			{ key: 'planetA', kind: 'body', label: 'A星' },
			{ key: 'planetB', kind: 'body', label: 'B星' },
			{ key: 'levels', kind: 'multiselect', label: '层级', options: LEVEL_OPTIONS },
			{ key: 'pairing', kind: 'select', label: '配对', options: [{ value: 'any_pair', label: '任意层级对' }, { value: 'same_level', label: '同级互容' }] },
			{ key: 'requireAspect', kind: 'toggle', label: '须成相位(古典严格)' },
		],
		validate(p){
			if(!isBody(p.planetA) || !isBody(p.planetB)){ return '需选择两颗星体'; }
			if(p.planetA === p.planetB){ return '两端不能相同'; }
			if(!nonEmptyArr(p.levels)){ return '至少选一个层级'; }
			return '';
		},
	},
	rulership: {
		category: 'boolean',
		label: '主宰关系',
		defaults: { planetA: 'Moon', planetB: 'Mars', mode: 'dispositor_is' },
		fields: [
			{ key: 'planetA', kind: 'body', label: 'A星' },
			{ key: 'planetB', kind: 'body', label: 'B星' },
			{ key: 'mode', kind: 'select', label: '方向', options: [{ value: 'dispositor_is', label: 'A 的主宰星是 B' }, { value: 'rules', label: 'A 主宰 B(所在座)' }] },
		],
		validate(p){
			if(!isBody(p.planetA) || !isBody(p.planetB)){ return '需选择两颗星体'; }
			if(p.planetA === p.planetB){ return '两端不能相同'; }
			return '';
		},
	},
	besieged: {
		category: 'boolean',
		label: '围攻',
		defaults: {
			target: 'Moon', besiegerA: 'Mars', besiegerB: 'Saturn', mode: 'body',
			orbLeft: 8, orbRight: 8,
			rescueEnabled: true, rescuers: ['Venus', 'Jupiter'], rescueByBody: true, rescueByRay: false,
			mitigationReception: false,
		},
		fields: [
			{ key: 'target', kind: 'body', label: '被围星' },
			{ key: 'besiegerA', kind: 'body', label: '攻星一' },
			{ key: 'besiegerB', kind: 'body', label: '攻星二' },
			{ key: 'mode', kind: 'select', label: '围式', options: [{ value: 'body', label: '体围(实体夹)' }, { value: 'ray', label: '光线围' }] },
			{ key: 'orbLeft', kind: 'number', label: '前侧 orb', min: 0.5, max: 30, step: 0.5 },
			{ key: 'orbRight', kind: 'number', label: '后侧 orb', min: 0.5, max: 30, step: 0.5 },
			{ key: 'rescueEnabled', kind: 'toggle', label: '计救援' },
			{ key: 'rescuers', kind: 'multiselect', label: '救星', options: SEVEN_BODIES.map((b) => ({ value: b, label: b })) },
			{ key: 'rescueByBody', kind: 'toggle', label: '实体救援' },
			{ key: 'rescueByRay', kind: 'toggle', label: '光线救援' },
			{ key: 'mitigationReception', kind: 'toggle', label: '接纳缓解视为解围' },
		],
		validate(p){
			if(!isBody(p.target) || !isBody(p.besiegerA) || !isBody(p.besiegerB)){ return '需选择三颗星体'; }
			if(new Set([p.target, p.besiegerA, p.besiegerB]).size !== 3){ return '三星必须互异'; }
			return '';
		},
		compile(p){
			return {
				target: p.target, besiegerA: p.besiegerA, besiegerB: p.besiegerB, mode: p.mode,
				orbLeft: Number(p.orbLeft), orbRight: Number(p.orbRight),
				rescue: { enabled: !!p.rescueEnabled, rescuers: p.rescuers || [], byBody: !!p.rescueByBody, byRay: !!p.rescueByRay },
				mitigation: { receptionBreaks: !!p.mitigationReception },
			};
		},
	},
	dignity_state: {
		category: 'boolean',
		label: '尊贵状态',
		defaults: { planet: 'Moon', states: ['ruler'], require: 'all' },
		fields: [
			{ key: 'planet', kind: 'body', label: '星体' },
			{ key: 'states', kind: 'multiselect', label: '状态', options: DIGNITY_STATE_OPTIONS },
			{ key: 'require', kind: 'select', label: '命中', options: [{ value: 'all', label: '全部满足' }, { value: 'any', label: '任一满足' }] },
		],
		validate(p){
			if(!isBody(p.planet)){ return '需选择星体'; }
			if(!nonEmptyArr(p.states)){ return '至少选一个状态'; }
			return '';
		},
	},
	considerations: {
		category: 'boolean',
		label: '择日考量',
		defaults: { item: 'moon_voc', vocMode: 'classic', speedMode: 'ramesey', variant: 'standard', earlyDeg: 3, lateDeg: 27 },
		fields: [
			{ key: 'item', kind: 'select', label: '考量项', options: CONSIDERATION_ITEM_OPTIONS },
			{ key: 'vocMode', kind: 'select', label: 'VOC 口径', options: VOC_MODE_OPTIONS, showIf: (p) => p.item === 'moon_voc' },
			{ key: 'speedMode', kind: 'select', label: '快慢口径', options: [{ value: 'ramesey', label: '13°10′' }, { value: 'mean', label: '平均日速' }, { value: 'twelve', label: '12°' }], showIf: (p) => p.item === 'moon_fast' || p.item === 'moon_slow' },
			{ key: 'variant', kind: 'select', label: '燃烧之路口径', options: [{ value: 'standard', label: '天秤15°-天蝎15°' }, { value: 'scorpioFull', label: '天秤15°-天蝎尾' }, { value: 'bothFull', label: '天秤头-天蝎尾' }, { value: 'narrow', label: '窄口径 208-217' }], showIf: (p) => p.item === 'via_combusta' },
			{ key: 'earlyDeg', kind: 'number', label: '初度阈', min: 0, max: 15, step: 0.5, showIf: (p) => p.item === 'moon_early_sign' || p.item === 'asc_near_boundary' },
			{ key: 'lateDeg', kind: 'number', label: '末度阈', min: 15, max: 30, step: 0.5, showIf: (p) => p.item === 'moon_late_sign' || p.item === 'asc_near_boundary' },
		],
		validate(p){
			if(!p.item){ return '需选择考量项'; }
			return '';
		},
	},
	aspect_pattern: {
		category: 'boolean',
		label: '相位格局',
		defaults: { pattern: 't_square', apex: 'any', members: 'any', orb: 6 },
		fields: [
			{ key: 'pattern', kind: 'select', label: '格局', options: PATTERN_OPTIONS },
			{ key: 'apex', kind: 'select', label: '顶点星', options: [{ value: 'any', label: '任意' }, ...SCAN_BODIES.map((b) => ({ value: b, label: b }))], showIf: (p) => p.pattern === 't_square' || p.pattern === 'yod' },
			{ key: 'orb', kind: 'number', label: 'orb', min: 1, max: 12, step: 0.5 },
		],
		validate(p){
			if(PATTERN_OPTIONS.every((o) => o.value !== p.pattern)){ return '需选择格局'; }
			if(!(Number(p.orb) > 0 && Number(p.orb) <= 12)){ return 'orb 需在 0-12°'; }
			return '';
		},
	},
	point_relation: {
		category: 'continuous',
		label: '星体与点',
		defaults: { planet: 'Moon', pointKind: 'angle', pointId: 'ASC', pointLon: 0, relation: 'any', angles: [0], orb: 3 },
		fields: [
			{ key: 'planet', kind: 'body', label: '星体' },
			{ key: 'pointKind', kind: 'select', label: '点类型', options: POINT_KIND_OPTIONS },
			{ key: 'pointId', kind: 'select', label: '四轴', options: ANGLE_ID_OPTIONS, showIf: (p) => p.pointKind === 'angle' },
			{ key: 'pointId', kind: 'body', label: '目标星', showIf: (p) => p.pointKind === 'planet' },
			{ key: 'pointLon', kind: 'number', label: '黄经°', min: 0, max: 360, step: 0.5, showIf: (p) => p.pointKind === 'fixedLon' },
			{ key: 'relation', kind: 'select', label: '关系', options: RELATION_OPTIONS },
			{ key: 'angles', kind: 'multiselect', label: '相位角', options: ASPECT_ANGLE_OPTIONS.map((a) => ({ value: a, label: `${a}°` })), showIf: (p) => p.relation === 'angles' },
			{ key: 'orb', kind: 'number', label: 'orb', min: 0.1, max: 15, step: 0.5 },
		],
		validate(p){
			if(!isBody(p.planet)){ return '需选择星体'; }
			if(p.pointKind === 'planet' && !isBody(p.pointId)){ return '需选择目标星'; }
			if(p.relation === 'angles' && !nonEmptyArr(p.angles)){ return '至少选一个相位角'; }
			return '';
		},
		compile(p){
			const point = { kind: p.pointKind };
			if(p.pointKind === 'angle' || p.pointKind === 'planet'){ point.id = p.pointId; }
			if(p.pointKind === 'lot'){ point.id = 'fortuna'; }
			if(p.pointKind === 'fixedLon'){ point.lon = Number(p.pointLon); }
			const out = { planet: p.planet, point, relation: p.relation, orb: Number(p.orb) };
			if(p.relation === 'angles'){ out.angles = (p.angles || []).map(Number); }
			return out;
		},
	},
	numeric: {
		category: 'continuous',
		label: '天文数值',
		defaults: { planet: 'Sun', field: 'Long', op: 'between', value: 0, value2: 30, altitudeKind: 'true' },
		fields: [
			{ key: 'planet', kind: 'body', label: '星体' },
			{ key: 'field', kind: 'select', label: '数值', options: NUMERIC_FIELD_OPTIONS },
			{ key: 'op', kind: 'select', label: '比较', options: [
				{ value: 'gt', label: '>' }, { value: 'gte', label: '≥' }, { value: 'lt', label: '<' },
				{ value: 'lte', label: '≤' }, { value: 'eq', label: '=' }, { value: 'between', label: '区间' },
			] },
			{ key: 'value', kind: 'number', label: '值', min: -360, max: 360, step: 0.1 },
			{ key: 'value2', kind: 'number', label: '值2', min: -360, max: 360, step: 0.1, showIf: (p) => p.op === 'between' },
			{ key: 'altitudeKind', kind: 'select', label: '高度口径', options: [{ value: 'true', label: '真高度' }, { value: 'apparent', label: '视高度' }], showIf: (p) => p.field === 'Altitude' },
		],
		validate(p){
			if(!isBody(p.planet)){ return '需选择星体'; }
			const spec = NUMERIC_FIELD_OPTIONS.find((o) => o.value === p.field);
			if(!spec){ return '需选择数值字段'; }
			if(spec.circular && p.op !== 'between' && p.op !== 'eq'){ return '角度型字段仅支持 区间/=(圆弧语义)'; }
			if(p.op === 'between' && (p.value2 === undefined || p.value2 === null || p.value2 === '')){ return '区间需要值2'; }
			return '';
		},
	},
	chart_shape: {
		category: 'boolean',
		label: '盘面形状',
		defaults: { shape: 'bowl', includeOuter: true },
		fields: [
			{ key: 'shape', kind: 'select', label: '形状', options: SHAPE_OPTIONS },
			{ key: 'includeOuter', kind: 'toggle', label: '含三王星' },
		],
		validate(p){
			if(SHAPE_OPTIONS.every((o) => o.value !== p.shape)){ return '需选择形状'; }
			return '';
		},
	},
	midpoint: {
		category: 'continuous',
		label: '中点',
		defaults: { a: 'Sun', b: 'Moon', targetKind: 'planet', targetId: 'Venus', targetPairA: 'Venus', targetPairB: 'Mars', targetLon: 0, modulus: 90, orb: 1.5 },
		fields: [
			{ key: 'a', kind: 'body', label: 'A星', pair: 'ab' },
			{ key: 'b', kind: 'body', label: 'B星', hint: '选与 A 相同的星=单星退化(直接用该星黄经)', pair: 'ab' },
			{ key: 'targetKind', kind: 'select', label: '目标', options: [{ value: 'planet', label: '星体' }, { value: 'midpoint', label: '另一中点' }, { value: 'angle', label: '四轴点' }, { value: 'fixedLon', label: '固定黄经' }] },
			{ key: 'targetId', kind: 'body', label: '目标星', showIf: (p) => p.targetKind === 'planet' },
			{ key: 'targetId', kind: 'select', label: '四轴', options: ANGLE_ID_OPTIONS, showIf: (p) => p.targetKind === 'angle' },
			{ key: 'targetPairA', kind: 'body', label: '中点甲', pair: 'tp', showIf: (p) => p.targetKind === 'midpoint' },
			{ key: 'targetPairB', kind: 'body', label: '中点乙', pair: 'tp', showIf: (p) => p.targetKind === 'midpoint' },
			{ key: 'targetLon', kind: 'number', label: '黄经°', min: 0, max: 360, step: 0.5, showIf: (p) => p.targetKind === 'fixedLon' },
			{ key: 'modulus', kind: 'select', label: 'modulus', options: MODULUS_OPTIONS.map((m) => ({ value: m, label: `${m}°盘` })) },
			{ key: 'orb', kind: 'number', label: 'orb', min: 0.1, max: 10, step: 0.25 },
		],
		validate(p){
			if(!isBody(p.a) || !isBody(p.b)){ return '需选择 A/B 星'; }
			if(p.targetKind === 'planet' && !isBody(p.targetId)){ return '需选择目标星'; }
			if(p.targetKind === 'midpoint' && (!isBody(p.targetPairA) || !isBody(p.targetPairB))){ return '需选择目标中点两星'; }
			if(!(Number(p.orb) > 0 && Number(p.orb) < Number(p.modulus) / 2)){ return 'orb 需小于 modulus 的一半'; }
			return '';
		},
		compile(p){
			let target;
			if(p.targetKind === 'midpoint'){
				target = { kind: 'midpoint', pair: [p.targetPairA, p.targetPairB] };
			}else if(p.targetKind === 'fixedLon'){
				target = { kind: 'fixedLon', lon: Number(p.targetLon) };
			}else{
				target = { kind: p.targetKind, id: p.targetId };
			}
			return { a: p.a, b: p.b, target, modulus: Number(p.modulus), orb: Number(p.orb) };
		},
	},
	day_window: {
		category: 'generative',
		label: '当日时间窗',
		defaults: { from: '09:00', to: '17:00' },
		fields: [
			{ key: 'from', kind: 'time', label: '从' },
			{ key: 'to', kind: 'time', label: '到(早于「从」=跨午夜)' },
		],
		validate(p){
			const re = /^\d{2}:\d{2}$/;
			if(!re.test(p.from || '') || !re.test(p.to || '')){ return '时间格式需为 HH:mm'; }
			if(p.from === p.to){ return '起止不能相同'; }
			return '';
		},
	},
	light_dynamics: {
		category: 'boolean',
		label: '相位动态',
		defaults: {
			item: 'translation', mover: 'any', from: 'any', to: 'any',
			collector: 'any', p1: 'any', p2: 'any', blocker: 'any', between: 'any',
			frustrated: 'any', via: 'any', planet: 'any', a: 'any', b: 'any',
			which: 'any', voidClassical: false,
		},
		fields: [
			{ key: 'item', kind: 'select', label: '学说', options: LIGHT_DYNAMICS_ITEM_OPTIONS },
			{ key: 'mover', kind: 'select', label: '传光星', options: SEVEN_ANY_OPTIONS, pair: 'ld1', showIf: (p) => p.item === 'translation' },
			{ key: 'from', kind: 'select', label: '自', options: SEVEN_ANY_OPTIONS, pair: 'ld1', showIf: (p) => p.item === 'translation' },
			{ key: 'to', kind: 'select', label: '至', options: SEVEN_ANY_OPTIONS, showIf: (p) => p.item === 'translation' },
			{ key: 'collector', kind: 'select', label: '聚光星', options: SEVEN_ANY_OPTIONS, showIf: (p) => p.item === 'collection' },
			{ key: 'p1', kind: 'select', label: '来星甲', options: SEVEN_ANY_OPTIONS, pair: 'ld2', showIf: (p) => p.item === 'collection' },
			{ key: 'p2', kind: 'select', label: '来星乙', options: SEVEN_ANY_OPTIONS, pair: 'ld2', showIf: (p) => p.item === 'collection' },
			{ key: 'blocker', kind: 'select', label: '阻止星', options: SEVEN_ANY_OPTIONS, showIf: (p) => p.item === 'prohibition' },
			{ key: 'between', kind: 'select', label: '被截星', options: SEVEN_ANY_OPTIONS, pair: 'ld3', showIf: (p) => p.item === 'prohibition' },
			{ key: 'to', kind: 'select', label: '受星', options: SEVEN_ANY_OPTIONS, pair: 'ld3', showIf: (p) => p.item === 'prohibition' },
			{ key: 'frustrated', kind: 'select', label: '受挫星', options: SEVEN_ANY_OPTIONS, pair: 'ld4', showIf: (p) => p.item === 'frustration' },
			{ key: 'via', kind: 'select', label: '经由星', options: SEVEN_ANY_OPTIONS, pair: 'ld4', showIf: (p) => p.item === 'frustration' },
			{ key: 'to', kind: 'select', label: '移情至', options: SEVEN_ANY_OPTIONS, showIf: (p) => p.item === 'frustration' },
			{ key: 'planet', kind: 'select', label: '收回星', options: SEVEN_ANY_OPTIONS, pair: 'ld5', showIf: (p) => p.item === 'refranation' },
			{ key: 'to', kind: 'select', label: '弃入相于', options: SEVEN_ANY_OPTIONS, pair: 'ld5', showIf: (p) => p.item === 'refranation' },
			{ key: 'a', kind: 'select', label: 'A星', options: SEVEN_ANY_OPTIONS, pair: 'ld6', showIf: (p) => p.item === 'aversion' },
			{ key: 'b', kind: 'select', label: 'B星', options: SEVEN_ANY_OPTIONS, pair: 'ld6', showIf: (p) => p.item === 'aversion' },
			{ key: 'planet', kind: 'select', label: '弯曲星', options: SEVEN_ANY_OPTIONS, pair: 'ld7', showIf: (p) => p.item === 'bending' },
			{ key: 'which', kind: 'select', label: '南北弯', options: [{ value: 'any', label: '任意' }, { value: 'north', label: '北弯(交点+90°)' }, { value: 'south', label: '南弯(交点−90°)' }], pair: 'ld7', showIf: (p) => p.item === 'bending' },
			{ key: 'voidClassical', kind: 'toggle', label: '空亡取古典义(30°窗)', showIf: (p) => p.item === 'void' },
		],
		validate(p){
			if(!p.item){ return '需选择学说'; }
			if(p.item === 'aversion' && p.a !== 'any' && p.a === p.b){ return 'A/B 星不能相同'; }
			return '';
		},
		compile(p){
			const roleKeys = {
				translation: ['mover', 'from', 'to'],
				collection: ['collector', 'p1', 'p2'],
				prohibition: ['blocker', 'between', 'to'],
				frustration: ['frustrated', 'via', 'to'],
				refranation: ['planet', 'to'],
				aversion: ['a', 'b'],
				bending: ['planet', 'which'],
				void: [],
			};
			const out = { item: p.item };
			(roleKeys[p.item] || []).forEach((k) => { out[k] = p[k] || 'any'; });
			if(p.item === 'void'){ out.voidClassical = !!p.voidClassical; }
			return out;
		},
	},
	royal_attendance: {
		category: 'boolean',
		label: '皇室伴寝',
		defaults: { ref: 'Moon', slot: 'first_occidental', companion: 'Venus' },
		fields: [
			{ key: 'ref', kind: 'select', label: '主星', options: SEVEN_OPTIONS, pair: 'ra1' },
			{ key: 'slot', kind: 'select', label: '侧位', options: ROYAL_SLOT_OPTIONS, pair: 'ra1' },
			{ key: 'companion', kind: 'select', label: '伴星', options: SEVEN_OPTIONS },
		],
		validate(p){
			if(p.companion === p.ref){ return '伴星不能与主星相同'; }
			return '';
		},
	},
	sect_joy: {
		category: 'boolean',
		label: '宗派喜乐',
		defaults: { item: 'of_sect', planet: 'Sun', hayyizLevels: ['Hayyiz'] },
		fields: [
			{ key: 'item', kind: 'select', label: '判定项', options: SECT_JOY_ITEM_OPTIONS },
			{ key: 'planet', kind: 'select', label: '星体', options: SEVEN_OPTIONS, showIf: (p) => p.item !== 'diurnal' },
			{ key: 'hayyizLevels', kind: 'multiselect', label: '得时档(命中任一)', options: HAYYIZ_LEVEL_OPTIONS, showIf: (p) => p.item === 'hayyiz' },
		],
		validate(p){
			if(p.item === 'hayyiz' && !(p.hayyizLevels || []).length){ return '需至少选一档'; }
			return '';
		},
		compile(p){
			const out = { item: p.item };
			if(p.item !== 'diurnal'){ out.planet = p.planet; }
			if(p.item === 'hayyiz'){ out.hayyizLevels = p.hayyizLevels; }
			return out;
		},
	},
	degree_state: {
		category: 'boolean',
		label: '度性查表',
		defaults: { planet: 'Moon', item: 'mansion', mansion: 1, ruler: 'Saturn', quality: 'B', special: 'pitted' },
		fields: [
			{ key: 'planet', kind: 'body', label: '星体', pair: 'dg1' },
			{ key: 'item', kind: 'select', label: '查表项', options: DEGREE_ITEM_OPTIONS, pair: 'dg1' },
			{ key: 'mansion', kind: 'select', label: '月宿', options: MANSION_OPTIONS, showIf: (p) => p.item === 'mansion' },
			{ key: 'ruler', kind: 'select', label: '主星', options: SEVEN_OPTIONS, showIf: (p) => p.item === 'monomoiria' || p.item === 'darijan' },
			{ key: 'quality', kind: 'select', label: '度质', options: DEGREE_QUALITY_OPTIONS, showIf: (p) => p.item === 'quality' },
			{ key: 'special', kind: 'select', label: '特殊度', options: SPECIAL_DEGREE_OPTIONS, showIf: (p) => p.item === 'special' },
		],
		compile(p){
			const out = { planet: p.planet, item: p.item };
			if(p.item === 'mansion'){ out.mansion = p.mansion; }
			if(p.item === 'monomoiria' || p.item === 'darijan'){ out.ruler = p.ruler; }
			if(p.item === 'quality'){ out.quality = p.quality; }
			if(p.item === 'special'){ out.special = p.special; }
			return out;
		},
	},
	decan_state: {
		category: 'boolean',
		label: '三十六旬',
		defaults: { mode: 'planet_in', planet: 'Moon', decans: [1], ruler: 'Mars' },
		fields: [
			{ key: 'mode', kind: 'select', label: '判定', options: DECAN_MODE_OPTIONS, pair: 'dc1' },
			{ key: 'planet', kind: 'body', label: '星体', pair: 'dc1', showIf: (p) => p.mode !== 'talisman' },
			{ key: 'decans', kind: 'multiselect', label: '旬(命中任一)', options: DECAN_OPTIONS, showIf: (p) => p.mode !== 'ruler_is' },
			{ key: 'ruler', kind: 'select', label: '旬主(迦勒底面)', options: SEVEN_OPTIONS, showIf: (p) => p.mode === 'ruler_is' },
		],
		validate(p){
			if(p.mode !== 'ruler_is' && !(p.decans || []).length){ return '需至少选一旬'; }
			return '';
		},
		compile(p){
			const out = { mode: p.mode };
			if(p.mode !== 'talisman'){ out.planet = p.planet; }
			if(p.mode !== 'ruler_is'){ out.decans = p.decans; }
			if(p.mode === 'ruler_is'){ out.ruler = p.ruler; }
			return out;
		},
	},
	pattern_overview: {
		category: 'boolean',
		label: '大势格局',
		defaults: { item: 'dragon_intercept', planet: 'any', which: 'any', minLit: 3, requireStrong: true, purity: 'any_pure' },
		fields: [
			{ key: 'item', kind: 'select', label: '格局项', options: OVERVIEW_ITEM_OPTIONS },
			{ key: 'planet', kind: 'select', label: '参与星', options: SEVEN_ANY_OPTIONS, showIf: (p) => ['dragon_intercept', 'apriori_power', 'eight_kill', 'afflicted_ruler', 'sentient_link'].includes(p.item) },
			{ key: 'which', kind: 'select', label: '联结型', options: APRIORI_WHICH_OPTIONS, showIf: (p) => p.item === 'apriori_power' || p.item === 'eight_kill' },
			{ key: 'minLit', kind: 'number', label: '照耀≥N星', min: 0, max: 6, step: 1, pair: 'po1', showIf: (p) => p.item === 'strong_jupiter' },
			{ key: 'requireStrong', kind: 'toggle', label: '须为强吉(不主凶宫)', showIf: (p) => p.item === 'strong_jupiter' },
			{ key: 'purity', kind: 'select', label: '纯粹档', options: PURITY_OPTIONS, showIf: (p) => p.item === 'sentient_link' },
		],
		compile(p){
			const out = { item: p.item };
			if(['dragon_intercept', 'apriori_power', 'eight_kill', 'afflicted_ruler', 'sentient_link'].includes(p.item)){ out.planet = p.planet || 'any'; }
			if(p.item === 'apriori_power' || p.item === 'eight_kill'){ out.which = p.which || 'any'; }
			if(p.item === 'strong_jupiter'){ out.minLit = p.minLit; out.requireStrong = !!p.requireStrong; }
			if(p.item === 'sentient_link'){ out.purity = p.purity; }
			return out;
		},
	},
	dispositor_cycle: {
		category: 'boolean',
		label: '主宰循环',
		defaults: { mode: 'final_is', planet: 'Sun' },
		fields: [
			{ key: 'mode', kind: 'select', label: '判定', options: DISPOSITOR_MODE_OPTIONS, pair: 'dp1' },
			{ key: 'planet', kind: 'select', label: '星体', options: SEVEN_OPTIONS, pair: 'dp1', showIf: (p) => p.mode === 'final_is' || p.mode === 'in_loop' },
		],
		compile(p){
			const out = { mode: p.mode };
			if(p.mode === 'final_is' || p.mode === 'in_loop'){ out.planet = p.planet; }
			return out;
		},
	},
	almuten_is: {
		category: 'boolean',
		label: '胜利星',
		defaults: { scope: 'chart', house: 1, planet: 'Sun' },
		fields: [
			{ key: 'scope', kind: 'select', label: '范围', options: [{ value: 'chart', label: '盘主(五要点+宫位分)' }, { value: 'topic', label: '逐题(单宫头)' }], pair: 'am1' },
			{ key: 'planet', kind: 'select', label: '胜者', options: SEVEN_OPTIONS, pair: 'am1' },
			{ key: 'house', kind: 'select', label: '题宫', options: HOUSE_OPTIONS, showIf: (p) => p.scope === 'topic' },
		],
		compile(p){
			const out = { scope: p.scope, planet: p.planet };
			if(p.scope === 'topic'){ out.house = p.house; }
			return out;
		},
	},
	distribution_state: {
		category: 'boolean',
		label: '分布权重',
		defaults: { axis: 'element', key: 'Fire', op: 'max', value: 4, includeOuter: true },
		fields: [
			{ key: 'axis', kind: 'select', label: '维度', options: [{ value: 'element', label: '元素(火土风水)' }, { value: 'mode', label: '模式(基本固定变动)' }, { value: 'hemisphere', label: '半球(轴制)' }], pair: 'ds1' },
			{ key: 'key', kind: 'select', label: '取值', pair: 'ds1', options: [
				{ value: 'Fire', label: '火象' }, { value: 'Earth', label: '土象' }, { value: 'Air', label: '风象' }, { value: 'Water', label: '水象' },
				{ value: 'Cardinal', label: '基本' }, { value: 'Fixed', label: '固定' }, { value: 'Mutable', label: '变动' },
				{ value: 'east', label: '东半球' }, { value: 'west', label: '西半球' }, { value: 'above', label: '地平上' }, { value: 'below', label: '地平下' },
			] },
			{ key: 'op', kind: 'select', label: '比较', options: [{ value: 'max', label: '严格最多' }, { value: 'gte', label: '≥N' }, { value: 'lte', label: '≤N' }, { value: 'eq', label: '=N' }], pair: 'ds2' },
			{ key: 'value', kind: 'number', label: 'N', min: 0, max: 10, step: 1, pair: 'ds2', showIf: (p) => p.op !== 'max' },
			{ key: 'includeOuter', kind: 'toggle', label: '计入三王星(十星制)' },
		],
		validate(p){
			const groups = { element: ['Fire', 'Earth', 'Air', 'Water'], mode: ['Cardinal', 'Fixed', 'Mutable'], hemisphere: ['east', 'west', 'above', 'below'] };
			if(!(groups[p.axis] || []).includes(p.key)){ return '取值与维度不匹配'; }
			return '';
		},
		compile(p){
			const out = { axis: p.axis, key: p.key, op: p.op, includeOuter: !!p.includeOuter };
			if(p.op !== 'max'){ out.value = p.value; }
			return out;
		},
	},
	temperament: {
		category: 'boolean',
		label: '气质评估',
		defaults: { kind: 'temperament', value: 'Choleric', op: 'dominant', count: 3 },
		fields: [
			{ key: 'kind', kind: 'select', label: '维度', options: [{ value: 'temperament', label: '气质' }, { value: 'quality', label: '性质' }], pair: 'tp1' },
			{ key: 'value', kind: 'select', label: '取值', pair: 'tp1', options: [
				{ value: 'Choleric', label: '胆汁质(热干)' }, { value: 'Melancholic', label: '抑郁质(冷干)' },
				{ value: 'Sanguine', label: '多血质(热湿)' }, { value: 'Phlegmatic', label: '黏液质(冷湿)' },
				{ value: 'Hot', label: '热' }, { value: 'Cold', label: '冷' }, { value: 'Dry', label: '干' }, { value: 'Humid', label: '湿' },
			] },
			{ key: 'op', kind: 'select', label: '比较', options: [{ value: 'dominant', label: '严格主导' }, { value: 'gte', label: '≥N' }, { value: 'lte', label: '≤N' }], pair: 'tp2' },
			{ key: 'count', kind: 'number', label: 'N', min: 0, max: 12, step: 1, pair: 'tp2', showIf: (p) => p.op !== 'dominant' },
		],
		validate(p){
			const groups = { temperament: ['Choleric', 'Melancholic', 'Sanguine', 'Phlegmatic'], quality: ['Hot', 'Cold', 'Dry', 'Humid'] };
			if(!(groups[p.kind] || []).includes(p.value)){ return '取值与维度不匹配'; }
			return '';
		},
		compile(p){
			const out = { kind: p.kind, value: p.value, op: p.op };
			if(p.op !== 'dominant'){ out.count = p.count; }
			return out;
		},
	},
	accidental_score: {
		category: 'boolean',
		label: '偶然尊贵分',
		defaults: { planet: 'Jupiter', op: 'gte', value: 5 },
		fields: [
			{ key: 'planet', kind: 'select', label: '星体', options: SEVEN_OPTIONS, pair: 'ac1' },
			{ key: 'op', kind: 'select', label: '比较', options: [{ value: 'gte', label: '≥分' }, { value: 'lte', label: '≤分' }, { value: 'top1', label: '全盘最高(严格)' }], pair: 'ac1' },
			{ key: 'value', kind: 'number', label: '分值', min: -30, max: 40, step: 1, showIf: (p) => p.op !== 'top1' },
		],
		compile(p){
			const out = { planet: p.planet, op: p.op };
			if(p.op !== 'top1'){ out.value = p.value; }
			return out;
		},
	},
	classical_pattern: {
		category: 'boolean',
		label: '古典格局',
		defaults: { pattern: 'doryphory', planet: 'any', over: 'any', under: 'any', aspectKind: 'any' },
		fields: [
			{ key: 'pattern', kind: 'select', label: '格局', options: CLASSICAL_PATTERN_OPTIONS },
			{ key: 'planet', kind: 'select', label: '护卫星', options: SEVEN_ANY_OPTIONS, showIf: (p) => p.pattern === 'doryphory' },
			{ key: 'over', kind: 'select', label: '压制星', options: SEVEN_ANY_OPTIONS, pair: 'cp1', showIf: (p) => p.pattern === 'overcoming' },
			{ key: 'under', kind: 'select', label: '被压星', options: SEVEN_ANY_OPTIONS, pair: 'cp1', showIf: (p) => p.pattern === 'overcoming' },
			{ key: 'aspectKind', kind: 'select', label: '压制相', options: [{ value: 'any', label: '任意' }, { value: 'trine', label: '三分压制' }, { value: 'square', label: '四分压制' }, { value: 'sextile', label: '六分压制' }], showIf: (p) => p.pattern === 'overcoming' },
			{ key: 'planet', kind: 'select', label: '被围星', options: SEVEN_ANY_OPTIONS, showIf: (p) => p.pattern === 'besieging_degree' },
		],
		validate(p){
			if(p.pattern === 'overcoming' && p.over !== 'any' && p.over === p.under){ return '压制/被压不能相同'; }
			return '';
		},
		compile(p){
			const out = { pattern: p.pattern };
			if(p.pattern === 'overcoming'){ out.over = p.over || 'any'; out.under = p.under || 'any'; out.aspectKind = p.aspectKind || 'any'; }
			else { out.planet = p.planet || 'any'; }
			return out;
		},
	},
	eminence_level: {
		category: 'boolean',
		label: '显赫程度',
		defaults: { op: 'band', band: 'eminent', value: 8 },
		fields: [
			{ key: 'op', kind: 'select', label: '比较', options: [{ value: 'band', label: '按档' }, { value: 'gte', label: '≥分' }, { value: 'lte', label: '≤分' }], pair: 'em1' },
			{ key: 'band', kind: 'select', label: '档位', options: EMINENCE_BAND_OPTIONS, pair: 'em1', showIf: (p) => p.op === 'band' },
			{ key: 'value', kind: 'number', label: '分值(0-10)', min: 0, max: 10, step: 0.5, showIf: (p) => p.op !== 'band' },
		],
		compile(p){
			const out = { op: p.op };
			if(p.op === 'band'){ out.band = p.band; } else { out.value = p.value; }
			return out;
		},
	},
	antiscia: {
		category: 'continuous',
		label: '映点',
		defaults: { planet: 'Moon', kind: 'antiscia', targetKind: 'planet', targetId: 'Venus', targetAngle: 'ASC', orb: 1 },
		fields: [
			{ key: 'planet', kind: 'body', label: 'A星', pair: 'an1' },
			{ key: 'kind', kind: 'select', label: '镜像', options: [{ value: 'antiscia', label: '映点(至点轴)' }, { value: 'contra', label: '反映点(分点轴)' }], pair: 'an1' },
			{ key: 'targetKind', kind: 'select', label: '目标', options: [{ value: 'planet', label: '星体' }, { value: 'angle', label: '四轴点' }], pair: 'an2' },
			{ key: 'targetId', kind: 'body', label: '目标星', pair: 'an2', showIf: (p) => p.targetKind === 'planet' },
			{ key: 'targetAngle', kind: 'select', label: '轴点', options: ANGLE_ID_OPTIONS, pair: 'an2', showIf: (p) => p.targetKind === 'angle' },
			{ key: 'orb', kind: 'number', label: 'orb', min: 0.05, max: 5, step: 0.05 },
		],
		compile(p){
			const target = p.targetKind === 'angle' ? { kind: 'angle', id: p.targetAngle } : { kind: 'planet', id: p.targetId };
			return { planet: p.planet, kind: p.kind, target, orb: p.orb };
		},
	},
	fixed_star: {
		category: 'continuous',
		label: '恒星触发',
		defaults: { star: 'Regulus', targetKind: 'planet', targetId: 'Moon', targetAngle: 'ASC', orb: 1 },
		fields: [
			{ key: 'star', kind: 'select', label: '恒星', options: STAR_OPTIONS, pair: 'fs1' },
			{ key: 'orb', kind: 'number', label: 'orb', min: 0.1, max: 5, step: 0.1, pair: 'fs1' },
			{ key: 'targetKind', kind: 'select', label: '触发点', options: [{ value: 'planet', label: '星体' }, { value: 'angle', label: '四轴点' }], pair: 'fs2' },
			{ key: 'targetId', kind: 'body', label: '星体', pair: 'fs2', showIf: (p) => p.targetKind === 'planet' },
			{ key: 'targetAngle', kind: 'select', label: '轴点', options: ANGLE_ID_OPTIONS, pair: 'fs2', showIf: (p) => p.targetKind === 'angle' },
		],
		compile(p){
			const target = p.targetKind === 'angle' ? { kind: 'angle', id: p.targetAngle } : { kind: 'planet', id: p.targetId };
			return { star: p.star, target, orb: p.orb };
		},
	},
	planetary_hour: {
		category: 'generative',
		label: '行星时',
		defaults: { kind: 'hour_ruler', planet: 'Jupiter' },
		fields: [
			{ key: 'kind', kind: 'select', label: '判定', options: [{ value: 'hour_ruler', label: '值时星(不等时)' }, { value: 'day_ruler', label: '值日星(日出至次日出)' }], pair: 'ph1' },
			{ key: 'planet', kind: 'select', label: '星体', options: SEVEN_OPTIONS, pair: 'ph1' },
		],
	},
	lifespan_state: {
		category: 'boolean',
		label: '寿命格局',
		defaults: { item: 'hyleg_is', method: 'ptolemy', point: 'sun', planet: 'Jupiter' },
		fields: [
			{ key: 'item', kind: 'select', label: '判定项', options: [
				{ value: 'hyleg_is', label: '生命主 Hyleg 是' },
				{ value: 'alcocoden_is', label: '寿主星 Alcocoden 是' },
				{ value: 'epikratetor_is', label: '占控星 Epikratetor 是' },
				{ value: 'oikodespotes_is', label: '家主星(船主)是' },
				{ value: 'kurios_is', label: '盘主星(舵手)是' },
				{ value: 'medical_crisis', label: '生命主受克(火土硬照)' },
			], pair: 'lf1' },
			{ key: 'method', kind: 'select', label: '取主法', options: [
				{ value: 'ptolemy', label: '托勒密' }, { value: 'alcabitius', label: '阿尔卡比修斯' }, { value: 'dorotheus', label: '多罗修斯' },
			], pair: 'lf1' },
			{ key: 'point', kind: 'select', label: '释放点', options: [
				{ value: 'sun', label: '太阳' }, { value: 'moon', label: '月亮' }, { value: 'asc', label: '上升' },
				{ value: 'fortune', label: '福点' }, { value: 'syzygy', label: '朔望点' }, { value: 'none', label: '无生命主' },
			], showIf: (p) => p.item === 'hyleg_is' || p.item === 'epikratetor_is' },
			{ key: 'planet', kind: 'select', label: '星体', options: [{ value: 'none', label: '无' }].concat(SEVEN_OPTIONS), showIf: (p) => ['alcocoden_is', 'oikodespotes_is', 'kurios_is'].includes(p.item) },
		],
		compile(p){
			const out = { item: p.item, method: p.method };
			if(p.item === 'hyleg_is' || p.item === 'epikratetor_is'){ out.point = p.point; }
			if(['alcocoden_is', 'oikodespotes_is', 'kurios_is'].includes(p.item)){ out.planet = p.planet; }
			return out;
		},
	},
};

export function newLeaf(type, joiner){
	const spec = CONDITION_TYPES[type];
	return {
		kind: 'leaf',
		type,
		negate: false,
		joiner: GROUP_TYPES.indexOf(joiner) >= 0 ? joiner : 'all',
		params: spec ? JSON.parse(JSON.stringify(spec.defaults)) : {},
	};
}

export function newGroup(joiner){
	return { kind: 'group', negate: false, joiner: GROUP_TYPES.indexOf(joiner) >= 0 ? joiner : 'all', children: [] };
}

function compileSelf(node){
	let compiled;
	if(node.kind === 'group' || Array.isArray(node.children)){
		compiled = compileChain(node.children, node.op);
	}else{
		const spec = CONDITION_TYPES[node.type];
		if(!spec){
			throw new Error(`未知条件类型:${node.type}`);
		}
		const msg = spec.validate ? spec.validate(node.params) : '';
		if(msg){
			throw new Error(`「${spec.label}」条件:${msg}`);
		}
		const params = spec.compile ? spec.compile(node.params) : { ...node.params };
		compiled = { type: node.type, params };
	}
	return node.negate ? { type: 'not', conditions: [compiled] } : compiled;
}

/** 行链 → 后端树:第 2 行起按各自 joiner 左折叠(同层自上而下依次结合,优先级用子分组表达)。
 * 兼容旧模型:行缺 joiner 时回退父组 legacyOp(载入老方案零迁移成本);连续同门扁平为多元组。 */
function compileChain(children, legacyOp){
	if(!Array.isArray(children) || !children.length){
		throw new Error('存在空的条件分组');
	}
	const fallback = GROUP_TYPES.indexOf(legacyOp) >= 0 ? legacyOp : 'all';
	let acc = compileSelf(children[0]);
	for(let i = 1; i < children.length; i++){
		const node = children[i];
		const joiner = GROUP_TYPES.indexOf(node.joiner) >= 0 ? node.joiner : fallback;
		const rhs = compileSelf(node);
		if(acc.type === joiner && Array.isArray(acc.conditions)){
			acc = { type: joiner, conditions: [...acc.conditions, rhs] };
		}else{
			acc = { type: joiner, conditions: [acc, rhs] };
		}
	}
	return acc;
}

/** UI 树 → 后端条件树(行首 joiner 链式左折叠;negate → not 包裹;compile 钩子折叠拍平字段)。 */
export function compileTree(uiTree){
	if(!uiTree || typeof uiTree !== 'object'){
		throw new Error('条件节点无效');
	}
	return compileSelf(uiTree);
}
