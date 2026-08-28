// divination/engine/conditions.js
// 单星状态 → 统一结构 {key,value,polarity,weight,text_zh}（构建清单 §2.1）。
import { PLANETS } from '../data/planets.js';

import { marsSaturnAttacksOf } from './resultShapes.js';
import { benignSurroundsOf } from './resultShapes.js';
import { scoreAccidental } from '../data/accidentalDignity.js';

function cn(key){ return (PLANETS[key] || {}).cn || key; }

// 速度评估：月亮 <12°/日 偏慢；内行星明显慢于均速=事缓。
function speedNote(p){
	if(p.key === 'moon'){
		if(p.speed !== undefined && p.speed !== null && Math.abs(p.speed) < 12){
			return { polarity: 'negative', weight: 1, key: 'slow', text_zh: `${cn(p.key)} 行度缓慢（<12°/日），事缓力弱` };
		}
	}
	return null;
}

// 被夹（surround.attacks 含该星 chartId）
export function isBesieged(key, facts){
	// [H1c 死链根修] 旧读法期待 surround.attacks 为数组——后端真形状是按行星分桶的 dict,
	// 本函数恒 false → 判前考量#11/#16、单星 −2、1647 满分表围攻分四处全哑。
	// ⚠️ 语义陷阱:attacks 按型分桶,仅 MarsSaturn 桶是凶围(围攻);VenusJupiter=围荣(吉)、
	// SunMoon=围耀(贵)——「非空即被围」会把吉围判凶=反向错判。凶围恒走 marsSaturnAttacksOf。
	const cid = (facts && facts.planets && facts.planets[key] || {}).chartId;
	if(!cid) return false;
	return marsSaturnAttacksOf(facts.result, cid).length >= 2;   // 围=两侧夹击(火+土两攻方记录)
}

// opts（可选;不传=既有行为字节不变）:
//   accidentalMode='lilly' → 附带偶然尊贵满分表明细(accidental 字段,±38 域)供古典 Tab/AI 快照,
//   并把「合计分」聚合为一条 finding 入裁决(极性=合计符号,权重 2);默认 'heuristic' 不触发。
export function planetCondition(key, facts, opts){
	const p = facts.planets[key];
	if(!p) return { key, findings: [], score: 0 };
	const f = [];
	const name = cn(key);

	// 必备尊贵
	if(p.dignityScore >= 4){
		f.push({ key: 'dignity', value: p.dignityScore, polarity: 'positive', weight: 2, text_zh: `${name} 必备尊贵有力（+${p.dignityScore}）` });
	}else if(p.dignityScore <= -4){
		f.push({ key: 'dignity', value: p.dignityScore, polarity: 'negative', weight: 2, text_zh: `${name} 落陷/失势（${p.dignityScore}）` });
	}else if(p.peregrine){
		f.push({ key: 'peregrine', value: true, polarity: 'negative', weight: 1, text_zh: `${name} 游走（无任何必备尊贵），缺乏力量` });
	}

	// 燃烧 / 日心 / 光束下
	if(p.combustion === 'cazimi'){
		f.push({ key: 'cazimi', value: true, polarity: 'positive', weight: 2, text_zh: `${name} 居日心（cazimi），如登王座，力量极强` });
	}else if(p.combustion === 'combust'){
		f.push({ key: 'combust', value: true, polarity: 'negative', weight: 3, text_zh: `${name} 燃烧（与日 <8.5°），最严重受克` });
	}else if(p.combustion === 'under_beams'){
		f.push({ key: 'under_beams', value: true, polarity: 'negative', weight: 1, text_zh: `${name} 在日光束下，力量受限` });
	}

	// 逆行
	if(p.retro){
		f.push({ key: 'retrograde', value: true, polarity: 'negative', weight: 2, text_zh: `${name} 逆行，力弱/乖气（主管命宫或用事宫则标红）` });
	}

	// 角续果
	if(p.angularity === 'angular'){
		f.push({ key: 'angular', value: true, polarity: 'positive', weight: 1, text_zh: `${name} 落角宫，有力、应事快` });
	}else if(p.angularity === 'cadent'){
		f.push({ key: 'cadent', value: true, polarity: 'negative', weight: 1, text_zh: `${name} 落果宫，力弱、拖延` });
	}

	// 被夹
	if(isBesieged(key, facts)){
		f.push({ key: 'besieged', value: true, polarity: 'negative', weight: 2, text_zh: `${name} 被双凶夹击（besieged）` });
	}

	const sp = speedNote(p);
	if(sp) f.push(sp);

	// [H4b 门控] backendConditionNotes(default false=现状零回归;renaissance/medieval 绑 true):
	// 后端金矿字段入证词——留驻/度性/特殊度注记+围荣围耀正面证词(H4a 只映射,此处消费)。
	if(opts && opts.backendConditionNotes){
		if(p.stationState === 'S'){
			f.push({ key: 'station', value: 'S', polarity: 'negative', weight: 1, text_zh: `${name} 临留驻（将转向），事有停滞/转折` });
		}else if(p.stationState === 'D'){
			f.push({ key: 'station', value: 'D', polarity: 'neutral', weight: 0, text_zh: `${name} 刚回顺，停滞方过、事渐启动` });
		}
		if(p.degreeQuality){
			const DQ = { Bright: ['positive', '光明度，事显而顺'], Smoky: ['negative', '烟雾度，事晦暗不明'], Dark: ['negative', '暗黑度，事阻而暗'], Empty: ['neutral', '亏空度，事平淡少应'] };
			const dq = DQ[p.degreeQuality];
			if(dq){ f.push({ key: 'degree_quality', value: p.degreeQuality, polarity: dq[0], weight: dq[0] === 'neutral' ? 0 : 1, text_zh: `${name} 落${dq[1]}` }); }
		}
		if(p.specialDegree){
			f.push({ key: 'special_degree', value: p.specialDegree, polarity: 'neutral', weight: 0, text_zh: `${name} 临特殊度（${p.specialDegree}）` });
		}
		// 围荣(金木环护)/围耀(日月环护)正面证词——与凶围(isBesieged)互斥面,分桶读法恒不混
		const cid2 = p.chartId;   // chartFacts 映射恒带 chartId
		if(cid2){
			const bn = benignSurroundsOf(facts.result, cid2);
			if(bn.venusJupiter.length >= 2){
				f.push({ key: 'benign_vj', value: true, polarity: 'positive', weight: 2, text_zh: `${name} 围荣（金木两侧环护），得吉星卫拱` });
			}
			if(bn.sunMoon.length >= 2){
				f.push({ key: 'benign_sm', value: true, polarity: 'positive', weight: 1, text_zh: `${name} 围耀（日月两侧环护），得二曜辉映` });
			}
		}
	}

	let accidental = null;
	if(opts && opts.accidentalMode === 'lilly'){
		// 惰性 require 防模块环（data/accidentalDignity ← engine/conditions 互引仅函数级）。
		accidental = scoreAccidental(key, facts, opts);
		if(accidental && accidental.total !== 0){
			f.push({
				key: 'accidental_lilly', value: accidental.total,
				polarity: accidental.total > 0 ? 'positive' : 'negative', weight: 2,
				text_zh: `${name} 偶然尊贵满分表合计 ${accidental.total > 0 ? '+' : ''}${accidental.total}（±38 域）`,
			});
		}
	}

	const score = f.reduce((s, x) => s + (x.polarity === 'positive' ? x.weight : (x.polarity === 'negative' ? -x.weight : 0)), 0);
	const out = { key, name, findings: f, score };
	if(accidental) out.accidental = accidental;
	return out;
}

export default planetCondition;
