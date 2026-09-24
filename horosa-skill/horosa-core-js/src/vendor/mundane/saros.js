// Saros 食族(古籍食族篇)。可计算部分:交点性质(North/South 按食时月亮所近交点,
// 非地理半球)+三周期数据+族生命周期结构;族号↔日期对照表与逐族主题关键词系文档缺口
// (古籍只给编号规则,未给对照表)→ 明确标注「须权威族表」,绝不臆造。

export const SAROS_CONST = {
	sarosSynodicMonths: 223,
	sarosDays: 6585.32,
	sarosLabel: '18 年 11 天 8 小时（地理西移 120°）',
	metonicYears: 19,
	metonicSynodicMonths: 235,
	metonicNote: '同历日同黄经',
	inexSynodicMonths: 358,
	inexDays: 10571.95,
	inexNote: '约 29 年 − 20 天,标连续编号食族之间隔',
};

export const SAROS_LIFECYCLE = {
	membersRange: [71, 73],
	stepYears: '每 18 年 11 天一员',
	eclipticShiftDeg: '食点黄经每次东移约 10–11°（6585.32 日 = 18.030 回归年，余 0.030×360°）；地理经度则西移约 120°（余 1/3 日）',
	phases: [
		{ key: 'early', cn: '族早期', note: '自一极的微小偏食生,渐强' },
		{ key: 'mid', cn: '族中期', note: '约 650 年达交点——全食/最强' },
		{ key: 'late', cn: '族晚期', note: '渐离至另一极偏食终(全寿约 1200–1300 年)' },
	],
};

// 编号规则(可算部分=交点性质;年序 1–19 与 New/Old 需族表对照):
export const SAROS_NUMBERING_NOTE = '编号规则:North/South 按食所在交点(非地理半球);按当前出食的年序编 1–19(非天文族号);新生/衰亡同号以 New/Old 区分。';
export const SAROS_TABLE_TODO = '族号↔日期对照表与逐族首食主题关键词需权威族表底本——本卡仅出可计算部分;可用下方「首食盘」入口按已知首食日期自行起盘读主题。';

const norm360 = (x) => (((x % 360) + 360) % 360);
const angDist = (a, b) => { const d = Math.abs(norm360(a) - norm360(b)); return Math.min(d, 360 - d); };

// 交点性质:食时月亮更近北交 → North 族;更近南交 → South 族。
export function sarosNodeType(facts){
	if(!facts || !facts.planets){ return null; }
	const m = facts.planets.moon;
	const nn = facts.planets.north_node;
	const sn = facts.planets.south_node;
	const nnLon = nn && nn.lon != null ? nn.lon : (sn && sn.lon != null ? norm360(sn.lon + 180) : null);
	if(!m || m.lon == null || nnLon == null){ return null; }
	const dN = angDist(m.lon, nnLon);
	return {
		type: dN <= 90 ? 'north' : 'south',
		cn: dN <= 90 ? 'North（北交族）' : 'South（南交族）',
		distToNode: Math.min(dN, 180 - dN),
	};
}

// 判读四步(古籍口径,orb 2–3°)。
export const SAROS_READING_STEPS = [
	'① 查该食属哪一族（需族表对照,或以首食日期起盘）',
	'② 读该族首食之盘的主题——首食盘=整族「出生盘」,其相位/中点主题贯穿全族',
	'③ 看本次食是否落本命/事件盘关键点（容许 2–3°）及其宫位与相位',
	'④ 产前食所属族 = 毕生动机母题',
];

export function describeSarosFamily(facts, orb){
	const node = sarosNodeType(facts);
	if(!node){ return null; }
	return {
		node,
		orb: orb || 2.5,
		constTable: SAROS_CONST,
		lifecycle: SAROS_LIFECYCLE,
		numberingNote: SAROS_NUMBERING_NOTE,
		tableTodo: SAROS_TABLE_TODO,
		steps: SAROS_READING_STEPS,
	};
}

export default { SAROS_CONST, SAROS_LIFECYCLE, sarosNodeType, describeSarosFamily };
