// 盘面细节:页签里的表、设置与 AI 快照正文。算法在 astropy/astrostudy/chart_details.py。
import * as AstroText from '../../constants/AstroText.js';
import { definePageSettings } from './pageSettingsStore.js';
import { starNameCn } from './starNamesCn.js';

export const CHART_DETAIL_TABLES = [
	{ value: 'topics', label: '专题主星', note: '灵魂、子女、职业等十九个专题,各点五种尊贵计分,分最高者为该题主星', fields: ['faces', 'variant'] },
	{ value: 'accidental', label: '偶然尊贵', note: '宫位、速度、顺逆、东西、日光、围攻、同度相位、恒星逐项计分,总分最高者是命主星', fields: ['faces', 'variant'] },
	{ value: 'persian', label: '波斯尊贵', note: '守 5、旺 4、界 3、三分 2、面 1,再加宫位分', fields: ['faces'] },
	{ value: 'sunPhases', label: '与日相位', note: '五星与太阳的十六相:距日、时位差、留、日光束,以及下一次留' },
	{ value: 'sect', label: '昼夜派', note: '地平上下、阴阳座、象限三项全合是喜乐之位,全不合是失位', fields: ['variant'] },
	{ value: 'dispositors', label: '定位星链', note: '沿座主逐星走,遇到自守星或走过的星就停' },
	{ value: 'receptions', label: '互容', note: '守护、擢升、三分、界、面、陷、落七类互容,以及同主、同光、同升', fields: ['faces'] },
	{ value: 'relations', label: '行星关系', note: '喜乐、前进后退、推进、相位互容、慷慨', fields: ['faces'] },
	{ value: 'hyleg', label: '寿主', note: '十一派寿主点与寿主星', fields: ['faces', 'variant'] },
	{ value: 'temperament', label: '气质', note: '上升座、月相、季节、上升主、命主五票定类型,星位定分数', fields: ['faces', 'variant'] },
	{ value: 'eminence', label: '名望判据', note: '福、灵、旺、基四点的主星落第十座、入本座、互相照应,共二十项' },
	{ value: 'hellenistic', label: '希腊化细节', note: '主星、三分主、界主、宫主' },
	{ value: 'considerations', label: '判前考量', note: '上升、月亮、七宫主十三项条件,成立的项提示此盘不宜直断' },
	{ value: 'slavery', label: '奴役判据', note: '日月与吉凶星的宫位和状态九项', fields: ['faces'] },
	{ value: 'patterns', label: '相位格局', note: '三到六点的几何格局,合相的星算一个角' },
	{ value: 'fertility', label: '受孕期', note: '从今天起一年里,日月角距回到出生时角距的各个时刻,约每月一次;当时月亮落阳性星座记男、阴性星座记女' },
	{ value: 'crisis', label: '危机日', note: '把本盘时刻当作起病时刻,月亮从当时的位置起每走 45° 一个节点:走 90°、180°、270°、360° 是危机日,45°、135°、225°、315° 是判断日' },
	{ value: 'lunarDays', label: '月亮日', note: '从出生前最近一次朔起逐日列出。传统:朔到月出为第 1 日,此后月出到月出;Tithi:日月每差 12° 一日;均分:整个朔望月分成 29.5 份;明暗线:按月面亮部在直径上的位置等分,盈 15 日、亏 15 日;朔居中:角距 354° 到 6° 为朔日,此后每 12° 一日', fields: ['lunar'] },
	{ value: 'perfections', label: '成相表', note: '盘时刻在容许度(两星半径之和)内的星对,往后推下一次正相位的时刻;离相位的星对要等下一轮,会排到很多年后。上升、天顶按本命位置不动;北交用盘上同一个交点(经典档为真交点)', fields: ['variant'] },
	{ value: 'inMundo', label: '世俗相位', note: '按宫位空间量两点距离:比例法把星在宫内按黄经线性折算(用盘面宫制),其余各法取该宫制下的真实世俗位置;上升 0°、天顶 270°。距离落在相位的两星半径之和内即成相。所选宫制在本纬度对某些点不成立时,表下写明缺哪些点', fields: ['mundo', 'variant'] },
	{ value: 'cuspAspects', label: '宫头相位', note: '各点到十二宫头的主相位,容许度按相位:合、冲 10°,拱 8°,刑 7°,六合 5.5°', fields: ['variant'] },
	{ value: 'starAspects', label: '恒星相位', note: '各点与二十五颗亮星的五种主相位,容许 1°', fields: ['variant'] },
	{ value: 'bindhu', label: '部分相位', note: '整座同度投照:星在座内第几度,就把六合、刑、拱、冲投到相应各座的同一度', fields: ['variant'] },
	{ value: 'astrodynes', label: 'AstroDynes', note: '相位力 = 表值 − 实际容许度,表值按相位、星类、宫类取两星中较大者;宫位力按星在宫内的位置递减。和谐 = 相位力乘相位性质与吉凶星修正,加本质尊贵与互容。宫与座再按落入的点和主星累计' },
	{ value: 'planetDetails', label: '行星细节', note: '亮面比例、距日、视径、星等,方位与高度(含大气折射的视高度),赤经赤纬,速度在增减,以及速度占极值与均值的比例' },
	{ value: 'degrees', label: '度数性质', note: '逐度定表。改进档按 Lilly 的表:阴阳度、明暗度、深陷(井)度、残缺度、增运度;经典档为两派并列的旧表。宫头另列界主、面、十二分、九分与月宿', fields: ['faces', 'variant'] },
	{ value: 'midpoints', label: '中点', note: '两点的短弧中点与和,坐标可选黄经、世俗位置、赤经、方位角、赤纬、黄纬;赤纬、黄纬取算术平均', fields: ['midpoint', 'variant'] },
	{ value: 'anatomy', label: '人体对应', note: '古典的身体对应:十二星座从白羊管头起依次往下到双鱼管足,七星各管器官与机能。列七星和上升落座对应的部位,以及第六宫头所在星座的部位' },
	{ value: 'stats', label: '统计', note: '十五个点按元素、模式、阴阳、宫类、象限、半球计数,七星的守、旺、陷、落' },
	{ value: 'hourAspects', label: '广义时位', note: '把昼夜半弧各分 12 时,每星得一个 0 到 24 的时位;两星时位差 0、4、6、8、12 对应合、六合、刑、拱、冲,容许 1 时。改进档按星自身半弧成比例,经典档沿用线性极角求解', fields: ['variant'] },
];

export const CHART_DETAIL_DEFAULTS = { table: 'topics', faces: 'chaldean', variant: 'improved', lunar: 'traditional', mundo: 'proportional', midpoint: 'ecliptic' };

export const CHART_DETAIL_OPTIONS = {
	faces: [{ value: 'chaldean', label: '迦勒底面' }, { value: 'element', label: '元素面' }],
	variant: [{ value: 'improved', label: '改进' }, { value: 'classic', label: '经典' }],
	lunar: [{ value: 'traditional', label: '传统' }, { value: 'tithi', label: 'Tithi' }, { value: 'equal', label: '均分' }, { value: 'angle', label: '明暗线' }, { value: 'centered', label: '朔居中' }],
	mundo: [
		{ value: 'proportional', label: '比例' }, { value: 'placidus', label: 'Placidus' }, { value: 'koch', label: 'Koch' }, { value: 'porphyry', label: 'Porphyry' },
		{ value: 'regiomontanus', label: 'Regiomontanus' }, { value: 'campanus', label: 'Campanus' }, { value: 'alcabitius', label: 'Alcabitius' },
		{ value: 'meridian', label: '子午' }, { value: 'horizontal', label: '地平' }, { value: 'topocentric', label: '站心' }, { value: 'morinus', label: 'Morinus' },
		{ value: 'krusinski', label: 'Krusinski' },
	],
	midpoint: [
		{ value: 'ecliptic', label: '黄经' }, { value: 'mundane', label: '世俗位置' }, { value: 'ra', label: '赤经' }, { value: 'azimuth', label: '方位角' },
		{ value: 'declination', label: '赤纬' }, { value: 'latitude', label: '黄纬' },
	],
};

export const CHART_DETAIL_SETTINGS = definePageSettings('horosa.astro.details.v1', {
	detailTable: { label: '盘面细节·当前表', def: CHART_DETAIL_DEFAULTS.table, oneOf: CHART_DETAIL_TABLES.map((item)=>item.value) },
	detailFaces: { label: '盘面细节·面的算法', def: CHART_DETAIL_DEFAULTS.faces, oneOf: CHART_DETAIL_OPTIONS.faces.map((item)=>item.value) },
	detailVariant: { label: '盘面细节·算法', def: CHART_DETAIL_DEFAULTS.variant, oneOf: CHART_DETAIL_OPTIONS.variant.map((item)=>item.value) },
	detailLunar: { label: '盘面细节·月亮日算法', def: CHART_DETAIL_DEFAULTS.lunar, oneOf: CHART_DETAIL_OPTIONS.lunar.map((item)=>item.value) },
	detailMundo: { label: '盘面细节·世俗位置', def: CHART_DETAIL_DEFAULTS.mundo, oneOf: CHART_DETAIL_OPTIONS.mundo.map((item)=>item.value) },
	detailMidpoint: { label: '盘面细节·中点坐标', def: CHART_DETAIL_DEFAULTS.midpoint, oneOf: CHART_DETAIL_OPTIONS.midpoint.map((item)=>item.value) },
});
// 盘面细节各项改了(页面 CHART_DETAIL_SETTINGS.save 之后)就广播:按这些口径另取过「盘面细节」的派生页(重置盘)据此重取,快照不留旧口径
export const CHART_DETAIL_SETTINGS_EVENT = 'horosa:chart-detail-settings-changed';
export function notifyChartDetailSettingsChanged(patch){
	if(typeof window !== 'undefined' && typeof window.dispatchEvent === 'function'){
		try{ window.dispatchEvent(new CustomEvent(CHART_DETAIL_SETTINGS_EVENT, { detail: { ...(patch || {}) } })); }catch(e){ /* 广播失败只影响派生页及时重取 */ }
	}
}


// AI 挂载取数用的细节设置:细节页本机保存值,挂载齿轮写在记录上的五项(合法值)再覆盖
const DETAIL_GEAR_KEYS = { detailFaces: 'faces', detailVariant: 'variant', detailLunar: 'lunar', detailMundo: 'mundo', detailMidpoint: 'midpoint' };
export function chartDetailSettingsFor(record){
	const out = { ...CHART_DETAIL_SETTINGS.load() };
	const r = record && typeof record === 'object' ? record : {};
	Object.keys(DETAIL_GEAR_KEYS).forEach((k)=>{
		const v = r[k];
		if(v !== undefined && v !== null && v !== '' && CHART_DETAIL_OPTIONS[DETAIL_GEAR_KEYS[k]].some((item)=>item.value === v)){ out[k] = v; }
	});
	// 按表取全表(挂载齿轮 detailFullTables):点名的表另出页面同列的全表;缺省空 = 只出摘要(与此前同)
	const full = Array.isArray(r.detailFullTables) ? r.detailFullTables.filter((k)=>CHART_DETAIL_TABLES.some((t)=>t.value === k)) : [];
	if(full.length){ out.detailFullTables = [...new Set(full)]; }
	return out;
}

// 这张表受哪些选项影响;不受影响的选项不显示
export function chartDetailFields(table){
	const def = CHART_DETAIL_TABLES.find((item)=>item.value === table);
	return (def && def.fields) || [];
}

export function chartDetailRequestFields(settings){
	const s = settings || {};
	const fields = {};
	if(s.detailFaces === 'element'){ fields.detailFaces = 'element'; }
	if(s.detailVariant === 'classic'){ fields.variant = 'classic'; }
	if(s.detailLunar && s.detailLunar !== CHART_DETAIL_DEFAULTS.lunar){ fields.lunarMethod = s.detailLunar; }
	if(s.detailMundo && s.detailMundo !== CHART_DETAIL_DEFAULTS.mundo){ fields.mundoSystem = s.detailMundo; }
	if(s.detailMidpoint && s.detailMidpoint !== CHART_DETAIL_DEFAULTS.midpoint){ fields.midpointCoord = s.detailMidpoint; }
	return fields;
}

const POINT_NAMES = { Asc: '上升', MC: '天顶', 'North Node': '北交', 'South Node': '南交', 'Pars Fortuna': '福点', Syzygy: '产前朔望' };

export function detailPointName(id){
	if(id === null || id === undefined || id === ''){ return '无'; }
	if(POINT_NAMES[id]){ return POINT_NAMES[id]; }
	return (AstroText.AstroTxtMsg && AstroText.AstroTxtMsg[id]) || `${id}`;
}

export const detailPointList = (ids)=>(ids || []).map(detailPointName).join('、');
export const detailPairs = (items)=>(items || []).map((item)=>(Array.isArray(item) ? item.map(detailPointName).join('→') : detailPointName(item))).join('、');

const signed = (v)=>(Number(v) > 0 ? `+${v}` : `${v}`);
const dateOnly = (v)=>`${v || '-'}`.trim().split(' ')[0];

const ASPECT_NAMES = { 0: '合', 30: '半六合', 45: '半刑', 60: '六合', 90: '刑', 120: '拱', 135: '补八分', 150: '梅花', 180: '冲', parallel: '平行', contraparallel: '反平行' };
export const detailAspectName = (v)=>ASPECT_NAMES[v] || `${v}`;
const SIGN_NAMES = ['白羊', '金牛', '双子', '巨蟹', '狮子', '处女', '天秤', '天蝎', '射手', '摩羯', '水瓶', '双鱼'];
export const detailStarName = (v)=>starNameCn(v);

// 统计表的分组与名称(页面与快照同一份)
export const STAT_GROUPS = [
	['element', '元素', { fire: '火', earth: '土', air: '风', water: '水' }], ['mode', '模式', { cardinal: '本位', fixed: '固定', mutable: '变动' }],
	['polarity', '阴阳', { masculine: '阳', feminine: '阴' }], ['houseType', '宫类', { angular: '角宫', succedent: '续宫', cadent: '果宫' }],
	['quadrant', '象限', { 1: '第一象限', 2: '第二象限', 3: '第三象限', 4: '第四象限' }], ['hemisphereNS', '南北半球', { above: '地平上', below: '地平下' }],
	['hemisphereEW', '东西半球', { east: '东', west: '西' }], ['dignity', '尊贵', { ruler: '守', exalt: '旺', detriment: '陷', fall: '落' }],
];
export const MIDPOINT_CONTACT_ORB = 1.5;

export const HOUR_ASPECT_NAMES = { 0: '合', 60: '六合', 90: '刑', 120: '拱', 180: '冲' };

const SACRED = { sacred: '神圣', profane: '亵渎' };
const BEAMS = { emerges: '将出光束', enters: '将入光束' };
const MOTION = { direct: '顺行', retrograde: '逆行', station: '留' };

export const detailSacredName = (v)=>SACRED[v] || '';
export const detailBeamsName = (v)=>BEAMS[v] || '';
export const detailMotionName = (v)=>MOTION[v] || '';

function hitsOf(rows){
	return (rows || []).filter((row)=>row.hit).map((row)=>row.test);
}

// 结果 → 快照正文(段头登记在 aiExport preset)。挑判读用得上的结论,逐格明细留在页面上。
export function buildChartDetailsText(d){
	if(!d || typeof d !== 'object' || !Array.isArray(d.persian)){ return ''; }
	const lines = ['[盘面细节]'];
	const acc = d.accidental || {};
	const faces = CHART_DETAIL_OPTIONS.faces.find((item)=>item.value === d.faces);
	const variant = CHART_DETAIL_OPTIONS.variant.find((item)=>item.value === d.variant);
	if(faces || variant){ lines.push(`口径：${[faces && faces.label, variant && variant.label].filter(Boolean).join(' · ')}`); }
	const temperament = d.temperament || {};
	lines.push(`命主星：${detailPointName(acc.geniture)}`);
	lines.push(`气质：${temperament.name || '-'}(热冷 ${signed(temperament.warm)},湿干 ${signed(temperament.moist)})`);
	lines.push(`最终定位星：${d.dispositors && d.dispositors.final ? detailPointName(d.dispositors.final) : '无'}`);
	lines.push(`偶然尊贵总分：${(acc.rows || []).map((row)=>`${detailPointName(row.planet)} ${signed(row.sum)}`).join('、')}`);
	lines.push(`波斯尊贵总分：${d.persian.map((row)=>`${detailPointName(row.planet)} ${row.sum}`).join('、')}`);
	lines.push(`与日相位：${(d.sunPhases || []).map((row)=>`${detailPointName(row.planet)} ${row.phaseName}`).join('、')}`);
	const sect = d.sect || [];
	lines.push(`喜乐之位：${detailPointList(sect.filter((row)=>row.hayz).map((row)=>row.planet)) || '无'}`);
	lines.push(`失位：${detailPointList(sect.filter((row)=>row.ex).map((row)=>row.planet)) || '无'}`);
	const receptions = (d.receptions || []).filter((row)=>row.type <= 7);
	lines.push(`互容：${receptions.map((row)=>`${row.name} ${detailPointName(row.a)}、${detailPointName(row.b)}`).join(';') || '无'}`);
	const topics = d.topics || [];
	lines.push(`专题主星：${topics.map((row)=>`${row.topic} ${detailPointList(row.winners)}`).join(';')}`);
	const hyleg = d.hyleg || [];
	lines.push(`寿主：${hyleg.map((row)=>`${row.label} ${detailPointName(row.hyleg)}(寿主星 ${detailPointName(row.alcocoden)})`).join(';')}`);
	lines.push(`名望判据成立：${hitsOf(d.eminence).join('、') || '无'}`);
	lines.push(`判前考量成立：${hitsOf(d.considerations).join('、') || '无'}`);
	const slavery = (d.slavery || []).filter((row)=>row.planets && row.planets.length);
	lines.push(`奴役判据成立：${slavery.map((row)=>`${row.test}(${detailPointList(Array.from(new Set(row.planets)))})`).join('、') || '无'}`);
	const hel = d.hellenistic || {};
	lines.push(`希腊化主星：${detailPointName(hel.predominator)},三分主 ${detailPointList(hel.triplicity)},界主 ${detailPointName(hel.oversight)}`);
	const patterns = d.patterns || [];
	lines.push(`相位格局：${patterns.map((row)=>`${row.name}(${row.corners.map((corner)=>corner.map(detailPointName).join('+')).join(' / ')})`).join(';') || '无'}`);
	const hourPairs = ((d.hourAspects && d.hourAspects.pairs) || []).filter((row)=>row.aspect !== null && row.aspect !== undefined);
	lines.push(`广义时位相位：${hourPairs.map((row)=>`${detailPointName(row.a)}、${detailPointName(row.b)} ${HOUR_ASPECT_NAMES[row.aspect] || row.aspect}(差 ${Number(row.gap).toFixed(2)} 时)`).join(';') || '无'}`);
	const optionLabel = (group, value)=>{ const item = CHART_DETAIL_OPTIONS[group].find((x)=>x.value === value); return item ? item.label : value; };
	const lunar = d.lunarDays || {};
	if(Array.isArray(lunar.rows) && lunar.rows.length){
		const cur = lunar.rows.find((row)=>row.current);
		lines.push(`月亮日(${optionLabel('lunar', lunar.method)}):出生在第 ${cur ? cur.day : '-'} 日${cur && cur.phase ? `(${cur.phase})` : ''}${cur ? `,${cur.start} 至 ${cur.end}` : ''}`);
	}
	const perfections = d.perfections || [];
	if(Array.isArray(d.perfections)){ lines.push(`成相表:${perfections.slice(0, 12).map((row)=>`${detailPointName(row.a)}${detailAspectName(row.aspect)}${detailPointName(row.b)} ${dateOnly(row.datetime)}${row.applying ? '' : '(离相后下一轮)'}`).join('、') || '无'}`); }
	const mundo = d.inMundo || {};
	if(Array.isArray(mundo.aspects)){ lines.push(`世俗相位(${optionLabel('mundo', mundo.system)}):${mundo.aspects.map((row)=>`${detailPointName(row.a)}${detailAspectName(row.aspect)}${detailPointName(row.b)}(差 ${Number(row.orb).toFixed(2)}°)`).join('、') || '无'}`); }
	if(Array.isArray(d.starAspects)){ lines.push(`恒星相位:${d.starAspects.map((row)=>`${detailPointName(row.planet)}${detailAspectName(row.aspect)}${detailStarName(row.star)}(${Number(row.orb).toFixed(2)}°)`).join('、') || '无'}`); }
	const dynes = d.astrodynes || {};
	if(Array.isArray(dynes.rows)){
		const total = dynes.rows.reduce((sum, row)=>sum + Number(row.power || 0), 0) || 1;
		lines.push(`AstroDynes 力量:${dynes.rows.slice().sort((a, b)=>b.power - a.power).map((row)=>`${detailPointName(row.planet)} ${Number(row.power).toFixed(1)}(${(row.power / total * 100).toFixed(1)}%)`).join('、')}`);
		lines.push(`AstroDynes 和谐:${dynes.rows.map((row)=>`${detailPointName(row.planet)} ${signed(Number(row.harmony).toFixed(1))}`).join('、')}`);
	}
	if(Array.isArray(d.cuspAspects)){
		const close = d.cuspAspects.filter((row)=>row.orb <= 2 && !(row.planet === 'Asc' || row.planet === 'MC'));
		lines.push(`近宫头相位(2° 内):${close.map((row)=>`${detailPointName(row.planet)}${detailAspectName(row.aspect)}${row.house}宫头`).join('、') || '无'}`);
	}
	if(Array.isArray(mundo.missing) && mundo.missing.length){ lines.push(`世俗相位缺点:${detailPointList(mundo.missing)}(所选宫制在本纬度对这些点不成立)`); }
	if(Array.isArray(d.relations)){
		const items = (row)=>(row.items || []).map((x)=>(Array.isArray(x) ? x.map(detailPointName).join('→') : detailPointName(x))).join('、');
		lines.push(`行星关系:${d.relations.filter((row)=>(row.items || []).length).map((row)=>`${row.name} ${items(row)}`).join(';') || '无'}`);
	}
	if(Array.isArray(d.planetDetails)){
		lines.push(`行星细节:${d.planetDetails.map((row)=>`${detailPointName(row.planet)} 高度 ${Number(row.altitude).toFixed(1)}°、速度为均值 ${Number(row.speedMeanPct).toFixed(0)}%${row.accelerating ? '(在加速)' : '(在减速)'}`).join(';')}`);
	}
	const degrees = d.degrees || {};
	if(Array.isArray(degrees.points)){
		const marks = degrees.points.map((row)=>{
			const tags = row.school === 'lilly'
				? [row.lame && '残缺度', row.deep && '深陷(井)度', row.fortune && '增运度'].filter(Boolean)
				: [row.lame && '残缺度', row.deep && '深陷度', row.wells && `井度(${row.wells} 派)`, row.fortune && `增运度(${row.fortune} 派)`].filter(Boolean);
			return tags.length ? `${detailPointName(row.point)} ${tags.join('、')}` : '';
		}).filter(Boolean);
		lines.push(`度数性质:${marks.join(';') || '无特殊度数'}`);
	}
	// 部分相位(整座同度投照):某点按六合 / 刑 / 拱 / 冲投到相应各座的同一度,正好落在另一点上(同座同整度)即为命中
	if(Array.isArray(d.bindhu)){
		const ASP = [[60, '六合'], [90, '刑'], [120, '拱'], [180, '冲']];
		// 投照两向对称(甲投到乙即乙投到甲),按「两点排序 + 相位」去重,每对只列一次
		const seen = new Set();
		const uniq = [];
		d.bindhu.forEach((row)=>{
			ASP.forEach(([angle, name])=>{
				(row[`a${angle}`] || []).forEach((sign)=>{
					d.bindhu.forEach((other)=>{
						if(other === row || other.sign !== sign || other.degree !== row.degree){ return; }
						const pair = [`${row.point}`, `${other.point}`].sort().join('|') + `|${angle}`;
						if(seen.has(pair)){ return; }
						seen.add(pair);
						uniq.push(`${detailPointName(row.point)}${name}${detailPointName(other.point)}(同在第 ${row.degree} 度)`);
					});
				});
			});
		});
		lines.push(`部分相位(整座同度投照):${uniq.join('、') || '无同度命中'}`);
	}
	const mid = d.midpoints || {};
	// 中点坐标选黄经以外(世俗位置 / 赤经 / 方位角 / 赤纬 / 黄纬)时,盘上各点没有同坐标的值可比 → 列前若干组中点本身
	if(Array.isArray(mid.rows) && mid.coord && mid.coord !== 'ecliptic'){
		const coordLabel = optionLabel('midpoint', mid.coord);
		lines.push(`中点(${coordLabel},前 15 组):${mid.rows.slice(0, 15).map((row)=>`${detailPointName(row.a)}/${detailPointName(row.b)} ${Number(row.midpoint).toFixed(2)}°`).join('、') || '无'}`);
	}
	if(Array.isArray(mid.rows) && mid.coord === 'ecliptic' && Array.isArray(d.planetDetails)){
		const lons = d.planetDetails.map((row)=>[row.planet, Number(row.lon)]);
		const near = [];
		mid.rows.forEach((row)=>{
			lons.forEach(([id, lon])=>{
				if(id === row.a || id === row.b){ return; }
				const gap = Math.abs((((Number(row.midpoint) - lon) % 360) + 540) % 360 - 180);
				if(gap <= MIDPOINT_CONTACT_ORB){ near.push(`${detailPointName(id)}=${detailPointName(row.a)}/${detailPointName(row.b)}(${gap.toFixed(2)}°)`); }
			});
		});
		lines.push(`中点合星(黄经 ${MIDPOINT_CONTACT_ORB}° 内):${near.join('、') || '无'}`);
	}
	if(d.stats && typeof d.stats === 'object'){
		const parts = STAT_GROUPS.filter(([group])=>group !== 'dignity' && d.stats[group]).map(([group, label, names])=>
			`${label} ${Object.keys(d.stats[group]).map((k)=>`${names[k] || k} ${(d.stats[group][k] || []).length}`).join('、')}`);
		lines.push(`统计:${parts.join(';')}`);
	}
	const anatomy = d.anatomy || {};
	if(Array.isArray(anatomy.rows)){
		lines.push(`人体对应(星座管部位):${anatomy.rows.map((row)=>`${detailPointName(row.point)}落${SIGN_NAMES[row.sign]}(${row.region})`).join('、')};六宫头在${SIGN_NAMES[anatomy.sixthCusp.sign]}(${anatomy.sixthCusp.region})`);
	}
	const fert = d.fertility || {};
	if(Array.isArray(fert.rows)){ lines.push(`受孕期(日月角距 ${Number(fert.elongation).toFixed(2)}°):${fert.rows.map((row)=>`${row.datetime} ${row.male ? '男' : '女'}`).join('、') || '无'}`); }
	const crisis = d.crisis || {};
	if(Array.isArray(crisis.rows)){ lines.push(`危机日(月亮每走 45°):${crisis.rows.map((row)=>`${row.arc}° ${row.datetime}${row.critical ? '(危机)' : '(判断)'}`).join('、')}`); }
	return lines.join('\n');
}
