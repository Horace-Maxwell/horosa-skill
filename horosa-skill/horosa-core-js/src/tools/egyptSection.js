import { SIGNS } from '../vendor/divination/data/signs.js';
import { TAROT_SUIT_CN, TAROT_SUIT_ELEMENT, SOTHIC_CYCLE_YEARS } from '../vendor/divination/data/egyptianData.js';
import { deriveEgyptView } from '../vendor/divination/data/egyptianSchools.js';

/**
 * [埃及历] 一段：各点落旬 / 上升旬详情 / 埃及民用历 + Sothic 周期。
 *
 * 上游这段的构建函数 `buildEgyptSectionLines` 长在 React 组件 `components/astro/AstroEgypt.js` 里，
 * 但它本身是纯函数——真正的算法在纯数据模块 `divination/data/egyptianSchools.js::deriveEgyptView`。
 * 所以这里只把该函数体与它用到的两个模块级小助手逐字搬过来，不动 React 那层。
 *
 * chartObj 需要带 `egyptianCalendar`（后端 `/astroextra/analysis` 的字段，天狼偕日升由 Python 算，
 * 本段只回显与对差，见上游 deriveEgyptView 内注释）。
 *
 * payload: { chart: <盘对象，含 egyptianCalendar>, school?: <埃及历七轴设置> }
 * return : { text }
 */

// 以下两个助手逐字取自上游 AstroEgypt.js（模块级常量，非组件状态）。
const sn = (s) => (SIGNS[s] && SIGNS[s].cn) || s || '-';
const POINT_CN = { Asc: '上升', Sun: '日', Moon: '月', Mercury: '水', Venus: '金', Mars: '火', Jupiter: '木', Saturn: '土', MC: '中天' };

export function buildEgyptSectionLines(chartObj, school){
	const lines = [];
	const v = deriveEgyptView(chartObj, school);
	if(!v.points.length){
		return lines;
	}
	// ◆ 所用口径:仅非默认档才写(默认档下本段与流派功能上线前逐字节一致)
	if(!v.isDefault){
		lines.push(`◆ 所用口径：${v.diff.map((d) => `${d.label}=${d.valueLabel}`).join('；')}`);
	}
	// ◆ 各行星落旬:逐点 旬序/旬位/埃及名/面主 + 旬星塔罗(与 renderDecanRing/renderTarot 本盘列同源同算)
	lines.push('◆ 各行星落旬');
	v.points.forEach((p) => {
		const d = p.decan;
		if(!d) return;
		lines.push(`${POINT_CN[p.id] || p.id}：第${d.number}旬 ${sn(d.signId)}${d.decanInSign}(${d.range})·埃及名 ${d.primaryName}·面主${POINT_CN[d.ruler] || d.ruler}·塔罗${TAROT_SUIT_CN[d.tarotSuit]}${d.tarotPip}「${d.tarotTitle}」`);
	});
	// ◆ 上升旬详情:上升所落旬完整派生(跨流派旬名/原位序/星认定/塔罗含义/护符 melothesia),
	// 与页首「当前上升旬」卡 + 名录/护符高亮行同源(deriveEgyptView 单一真值源)。
	const ad = v.ascDecan;
	if(ad){
		lines.push('◆ 上升旬详情');
		lines.push(`第${ad.number}旬 ${sn(ad.signId)}${ad.decanInSign}(${ad.range})·原位(古代恒星序)第${ad.ancient}旬·星认定 ${ad.star}`);
		lines.push(`旬名：埃及名 ${ad.egyptName} / 科普特-希腊名 ${ad.copticGreek} / 赫尔墨斯名 ${ad.hermesName};面主${POINT_CN[ad.ruler] || ad.ruler}`);
		lines.push(`塔罗：${TAROT_SUIT_CN[ad.tarotSuit]}${ad.tarotPip}(${TAROT_SUIT_ELEMENT[ad.tarotSuit]})「${ad.tarotTitle}」——${ad.tarotMeaning}`);
		const tal = v.ascTalisman;
		if(tal){
			lines.push(`护符：秘名 ${tal.secretName};身体部位 ${tal.bodyPart};主管疾病 ${tal.disease}`);
		}
	}
	// ◆ 民用历/Sothic:本盘出生日的埃及游移历日期 + 周期定位(锚点必随同输出,否则不可复现)
	if(v.civil){
		lines.push('◆ 埃及民用历');
		lines.push(`${v.civil.text}(锚点：${v.anchor.label})${v.civil.decade === null ? '' : `·第${v.civil.decade + 1}旬列`}`);
		if(v.sothic){
			lines.push(`Sothic 周期：距锚点 ${v.sothic.julianYears.toFixed(1)} 年,周期内位置 ${v.sothic.position.toFixed(1)}/${SOTHIC_CYCLE_YEARS} 年(${v.sothic.percent.toFixed(1)}%);民用历较锚点已漂 ${v.sothic.driftDays.toFixed(1)} 日`);
		}
		if(v.sirius.date){
			lines.push(`天狼偕日升：${v.sirius.date}${v.sirius.deltaDays === null ? '' : `(本盘生日距其 ${v.sirius.deltaDays} 日)`}`);
		}
	}
	return lines;
}

export function runEgyptSection(payload) {
  const source = payload || {};
  const chart = source.chart && typeof source.chart === 'object' ? source.chart : null;
  if (!chart) {
    return { text: '' };
  }
  const lines = buildEgyptSectionLines(chart, source.school) || [];
  if (!lines.length) {
    return { text: '' };
  }
  return { text: ['[埃及历]', ...lines].join('\n') };
}
