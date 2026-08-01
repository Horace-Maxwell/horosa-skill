// divination/election/considerations.js
// 择前考量三清单(1647 印本十考量 / 1653 复原本「月之十损」/ 13 世纪考量书要点)
// + 第 7 宫＝占星师单独高亮 + 可判性总结。纯提示层:默认不计入总分(零 golden 影响,由 UI 单页呈现)。
// 逐条给「原意一句话 + 本盘实测值」;不可判定的条目如实标 unavailable,不臆造。
import { SIGNS } from '../data/signs.js';
import { PLANETS } from '../data/planets.js';
import { viaCombustaRange, hourAgreementTest } from '../engine/radicality.js';
import { moonReport } from '../engine/moon.js';
import { applyingAspects, aspectBetween } from '../engine/aspectsEngine.js';
import { isBesieged } from '../engine/conditions.js';
import { norm360, angularDist } from '../engine/utils.js';

const cn = (k) => (PLANETS[k] || {}).cn || k;
const MAL = ['mars', 'saturn'];

function lord1Of(facts){
	const s = facts.meta.ascSign;
	return s && SIGNS[s] ? SIGNS[s].domicile : null;
}
function vocOf(facts, eff){
	if(!eff || !eff.vocMode || eff.vocMode === 'classic') return !!(facts.planets.moon && facts.planets.moon.isVOC);
	return !!moonReport(facts, { vocMode: eff.vocMode, vocIncludeOuter: !!eff.vocIncludeOuter }).voc;
}
function mk(key, title, hit, detail, meaning, extra){
	return { key, title, hit: !!hit, detail: detail || '', meaning: meaning || '', ...(extra || {}) };
}

// ── 甲·十考量(1647 印本「判断前的考量」,依《基督教占星学》卷一)────────────────
export function lillyConsiderations(facts, eff){
	const out = [];
	const meta = facts.meta;
	const moon = facts.planets.moon;
	const lord1 = lord1Of(facts);
	const lp = lord1 && facts.planets[lord1];

	const ha = hourAgreementTest(facts, {});
	out.push(mk('radical_hour', '时主与上升主相合(同星/同三分/同性质)则盘可托', ha.available && !ha.agree,
		ha.available ? (ha.agree ? `相合:${ha.hits.map((h) => h.text).join('；')}` : `时主 ${cn(ha.hourRuler)} 与命主 ${cn(ha.lord1)} 不相合`) : '本盘未回传时主',
		'相合＝盘真实映事,适宜托付判断;不合是首要警示', { positiveWhenMiss: true }));
	const ad = meta.ascDegree;
	out.push(mk('asc_early', '上升度数过早(<3°)', ad !== null && ad !== undefined && ad < 3,
		ad !== null && ad !== undefined ? `上升 ${ad.toFixed(1)}°` : '—', '事尚未成熟,太早不可判'));
	out.push(mk('asc_late', '上升度数过晚(27–29°)', ad !== null && ad !== undefined && ad > 27,
		ad !== null && ad !== undefined ? `上升 ${ad.toFixed(1)}°` : '—', '事已太晚/已定局,判断不安全'));
	const vcr = viaCombustaRange(eff && eff.viaCombustaVariant);
	const inVC = moon && norm360(moon.lon) >= vcr[0] && norm360(moon.lon) <= vcr[1];
	out.push(mk('via_combusta', '月在燃烧之路', inVC,
		moon ? `月黄经 ${moon.lon.toFixed(1)}°(火道界 ${vcr[0]}°–${vcr[1]}°)` : '—', '月受克受扰,事态不稳、盘不可靠(合角宿一者除)'));
	out.push(mk('moon_voc', '月亮空亡', vocOf(facts, eff),
		'', '诸事艰难推进——除非主星极强,或月空于金牛/巨蟹/人马/双鱼仍稍有成'));
	out.push(mk('moon_late', '月在星座末度(尤双子/天蝎/摩羯)', moon && moon.signlon !== undefined && moon.signlon >= 27,
		moon ? `月 ${SIGNS[moon.sign] ? SIGNS[moon.sign].cn : ''} ${moon.signlon !== undefined ? moon.signlon.toFixed(1) : ''}°${['gemini', 'scorpio', 'capricorn'].indexOf(moon.sign) >= 0 ? '(正在尤忌之座)' : ''}` : '—',
		'月与事态已至强弩之末,结果不定'));
	const sat = facts.planets.saturn;
	out.push(mk('saturn_asc', '土星在上升(逆行尤甚)', sat && sat.house === 1,
		sat ? `土星落 ${sat.house} 宫${sat.retro ? '·逆行' : ''}` : '—', '土在一宫败坏事态与问者;逆行更甚'));
	out.push(mk('saturn_7th', '土星(或凶星)在第 7 宫', sat && sat.house === 7,
		sat ? `土星落 ${sat.house} 宫` : '—', '第 7 宫＝占星师;凶星在此表判读易误'));
	const l7 = facts.houses[7] && facts.houses[7].ruler;
	const p7 = l7 && facts.planets[l7];
	out.push(mk('l7_afflicted', '第 7 宫头/宫主受克(所问非七宫事时)', p7 && (p7.retro || p7.combustion === 'combust' || p7.dignityScore <= -4),
		l7 ? `7 宫主 ${cn(l7)}${p7 && p7.retro ? '·逆行' : ''}${p7 && p7.combustion === 'combust' ? '·燃烧' : ''}${p7 && p7.dignityScore <= -4 ? '·陷弱' : ''}` : '—',
		'七宫总司术者:其主受损预示占星师将被误导'));
	const combustHits = [lord1, 'moon', 'mercury'].filter((k) => k && facts.planets[k] && facts.planets[k].combustion === 'combust');
	out.push(mk('sig_combust', '上升主/月亮/水星燃烧', combustHits.length > 0,
		combustHits.length ? combustHits.map(cn).join('、') + ' 燃烧' : '', '主星被烧尽——人或事被压倒、隐藏,强烈警示无善果'));
	if(lp){
		out.push(mk('l1_peregrine', '并列旗标:上升主外来/落陷、被围攻、南交在上升', !!(lp.peregrine || lp.dignityScore <= -4 || isBesieged(lord1, facts)),
			`${cn(lord1)}${lp.peregrine ? '·外来' : ''}${lp.dignityScore <= -4 ? '·陷弱' : ''}${isBesieged(lord1, facts) ? '·被围攻' : ''}`,
			'传统并列补充旗标(不单独否决)'));
	}
	return out;
}

// ── 乙·月之十损(1653 复原本;月受损十式,择日凡月损必避)────────────────────
export function rameseyMoonImpediments(facts, eff){
	const out = [];
	const moon = facts.planets.moon;
	if(!moon) return out;
	const apps = applyingAspects(facts, 'moon');
	out.push(mk('m1_combust', '① 焦伤/日光束下(入相更损)', !!moon.combustion,
		moon.combustion ? ({ cazimi: '日心(反吉)', combust: '燃烧', under_beams: '日下光' })[moon.combustion] : '', '月近日则力被吞'));
	out.push(mk('m2_fall', '② 居落(天蝎;弱点 3°)', moon.sign === 'scorpio',
		moon.sign === 'scorpio' ? `月天蝎 ${moon.signlon !== undefined ? moon.signlon.toFixed(1) : ''}°` : '', '月落陷,鲜有善终'));
	const nn = facts.planets.north_node; const sn = facts.planets.south_node;
	const nodeLon = nn ? nn.lon : (sn ? norm360(sn.lon + 180) : null);
	const nodeHit = nodeLon !== null && (angularDist(moon.lon, nodeLon) <= 12 || angularDist(moon.lon, norm360(nodeLon + 180)) <= 12);
	out.push(mk('m3_nodes', '③ 近交点/食处(首尾 12° 内)', nodeHit,
		nodeLon !== null ? `距交点轴 ${Math.min(angularDist(moon.lon, nodeLon), angularDist(moon.lon, norm360(nodeLon + 180))).toFixed(1)}°` : '', '近食蚀之地,光受蚀'));
	out.push(mk('m4_voc', '④ 空亡', vocOf(facts, eff), '', '入新座前不结任何相位'));
	const vcr = viaCombustaRange(eff && eff.viaCombustaVariant);
	out.push(mk('m5_via', '⑤ 居燃烧之路', norm360(moon.lon) >= vcr[0] && norm360(moon.lon) <= vcr[1], '',
		'婚姻及一切女人之事、买卖、旅行最忌'));
	out.push(mk('m6_besieged', '⑥ 被火土围合', isBesieged('moon', facts), '', '腹背受敌'));
	const hardMal = apps.filter((a) => MAL.indexOf(a.other) >= 0 && [0, 90, 180].indexOf(a.angle) >= 0);
	out.push(mk('m7_applying_mal', '⑦ 入相火/土之合刑冲', hardMal.length > 0,
		hardMal.map((a) => `月→${cn(a.other)} ${a.angle}°`).join('、'), '月之下一步引向凶星'));
	out.push(mk('m8_slow', '⑧ 行迟(低于均速 13°10′)', moon.speed !== undefined && moon.speed !== null && Math.abs(moon.speed) < 13 + 10 / 60,
		moon.speed !== undefined && moon.speed !== null ? `月速 ${Math.abs(moon.speed).toFixed(2)}°/日` : '', '迟则力弱事缓'));
	out.push(mk('m9_bad_house', '⑨ 居 6/8/12 宫', [6, 8, 12].indexOf(moon.house) >= 0,
		moon.house ? `月落 ${moon.house} 宫` : '', '果宫暗处,力不得出'));
	out.push(mk('m10_late', '⑩ 居座末', moon.signlon !== undefined && moon.signlon >= 28,
		moon.signlon !== undefined ? `座内 ${moon.signlon.toFixed(1)}°` : '', '气质已移,事将他属'));
	return out;
}

// ── 丙·考量书要点(13 世纪 146 考量精粹,择日直接相关者)──────────────────────
export function bonattiHighlights(facts, eff){
	const out = [];
	const moon = facts.planets.moon;
	// 45:凶星在角且以刑冲损他星
	const malAngular = MAL.filter((k) => {
		const p = facts.planets[k];
		if(!p || p.angularity !== 'angular') return false;
		return applyingAspects(facts, k).concat([]).some((a) => a.angle === 90 || a.angle === 180);
	});
	out.push(mk('b45_mal_angle', '凶星在角且刑冲他星(为害更甚)', malAngular.length > 0,
		malAngular.map(cn).join('、'), '凶星居显位又出恶光,其害倍增'));
	// 53:主星在日焰下则效微(12°–15° 离焰口径注记)
	const lord1 = lord1Of(facts);
	const lp = lord1 && facts.planets[lord1];
	out.push(mk('b53_beams', '主星在日焰下(12°档,离焰渐愈)', !!(lp && lp.combustion),
		lp && lp.combustion ? `${cn(lord1)} ${({ cazimi: '日心(强)', combust: '燃烧', under_beams: '日下光' })[lp.combustion]}` : '',
		'焰下效微;「向日比离日损更甚」——离焰如病者初愈'));
	// 62:月空亡
	out.push(mk('b62_voc', '月空亡(除非上升主/主星甚得力)', vocOf(facts, eff), '',
		'事难善终或多劳苦'));
	// 5:月之特重(恒注记)
	out.push(mk('b5_moon_first', '月为万事万择必参之枢', false,
		moon ? `月落 ${SIGNS[moon.sign] ? SIGNS[moon.sign].cn : ''}${moon.house ? ` ${moon.house} 宫` : ''}` : '',
		'月轨最近地,与下界相似最大', { severity: 'info' }));
	// 125:数事择成(告知性)
	out.push(mk('b125_multi', '数事并举时,择其征象最强之一途而行', false, '',
		'当事者有数途,判何途兴——择日即为所择之途铸最强之盘', { severity: 'info' }));
	return out;
}

// ── 总装:三清单 + 第7宫=占星师高亮 + 可判性总结 ─────────────────────────────
export function buildConsiderations(facts, eff){
	const lilly = lillyConsiderations(facts, eff);
	const ramesey = rameseyMoonImpediments(facts, eff);
	const bonatti = bonattiHighlights(facts, eff);
	const astrologer7th = lilly.filter((x) => (x.key === 'saturn_7th' || x.key === 'l7_afflicted') && x.hit);
	const hitCount = lilly.filter((x) => x.hit).length + ramesey.filter((x) => x.hit).length
		+ bonatti.filter((x) => x.hit && x.severity !== 'info').length;
	let verdict = 'good';
	if(hitCount >= 6) verdict = 'poor';
	else if(hitCount >= 3) verdict = 'caution';
	const verdictCn = verdict === 'good' ? '良好' : (verdict === 'caution' ? '需留意' : '建议另择');
	return { lilly, ramesey, bonatti, astrologer7th, hitCount, verdict, verdictCn };
}

export default buildConsiderations;
