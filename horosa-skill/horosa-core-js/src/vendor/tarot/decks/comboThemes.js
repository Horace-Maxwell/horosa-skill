// 组合征象检索(TP4):多书传统组合规则的合并转述(原创中文)。只收高信号组合,避免噪声。
// 规则 schema:{ key, theme, minHits, pool:[{sid, rev?}], needAll?:[sid], hint, guard? }
//   pool 命中计数(rev 指定时须朝向匹配;不指定=任意朝向);needAll=必须全部在场(任意朝向);
//   guard:'transform' 重大转化类(≥4 门槛+固定免责)/'health' 健康类(附非医疗建议)。
export const COMBO_THEMES = [
	{
		key: 'transform', theme: '重大转化/彻底了结', minHits: 4, guard: 'transform',
		pool: [{ sid: 'death' }, { sid: 'the_tower' }, { sid: 'judgement' }, { sid: 'swords_10' }, { sid: 'swords_06' }, { sid: 'swords_04' }, { sid: 'swords_03' }, { sid: 'cups_10' }],
		hint: '多张终结/转化牌同现——一段结构性了断与更替之征(须四张以上同现方论;绝不作死亡预言)。',
	},
	{
		key: 'marriage', theme: '缔结/婚约之征', minHits: 2,
		pool: [{ sid: 'justice' }, { sid: 'cups_02' }, { sid: 'cups_03' }, { sid: 'cups_10' }, { sid: 'the_hierophant' }],
		hint: '结盟诸牌聚首——契约、婚约或正式结合的势头。',
	},
	{
		key: 'pregnancy', theme: '孕育之征', minHits: 2, guard: 'health',
		pool: [{ sid: 'the_empress' }, { sid: 'pentacles_09' }, { sid: 'cups_03' }, { sid: 'wands_page' }, { sid: 'cups_page' }, { sid: 'swords_page' }, { sid: 'pentacles_page' }],
		needAll: ['the_empress'],
		hint: '皇后携丰成之牌——孕育/新生命或新作品的征象(侍从在侧更强)。',
	},
	{
		key: 'lawsuit', theme: '讼务之征', minHits: 2,
		pool: [{ sid: 'swords_king' }, { sid: 'justice' }, { sid: 'swords_05' }],
		hint: '裁断者与天平同现——文书、仲裁或诉讼之事将近。',
	},
	{
		key: 'promotion', theme: '晋升/受认之征', minHits: 2,
		pool: [{ sid: 'justice' }, { sid: 'wands_06' }, { sid: 'the_sun' }],
		hint: '公断与凯旋并见——名分获正、位阶得进。',
	},
	{
		key: 'triangle', theme: '三角/抉择张力', minHits: 2,
		pool: [{ sid: 'the_lovers' }, { sid: 'the_chariot' }, { sid: 'swords_07' }, { sid: 'cups_03', rev: true }],
		needAll: ['the_lovers'],
		hint: '恋人牌携争驰/暗行之牌——关系里有抉择或第三方张力。',
	},
	{
		key: 'air_travel', theme: '远行/航空之征', minHits: 2,
		pool: [{ sid: 'swords_page' }, { sid: 'wands_08' }, { sid: 'wands_03' }, { sid: 'swords_06' }, { sid: 'temperance' }, { sid: 'the_world' }],
		hint: '信使与迅捷之牌同现——远行(尤指跨海/航空)在途。',
	},
	{
		key: 'move_house', theme: '迁居之征', minHits: 2,
		pool: [{ sid: 'wands_knight' }, { sid: 'wands_04' }, { sid: 'wands_03' }, { sid: 'the_tower' }],
		hint: '动身与家宅之牌并见——搬迁、易地或住所更替。',
	},
	{
		key: 'study', theme: '进学之征', minHits: 2,
		pool: [{ sid: 'pentacles_03' }, { sid: 'pentacles_08' }, { sid: 'swords_01' }, { sid: 'high_priestess' }, { sid: 'the_hierophant' }, { sid: 'temperance' }],
		hint: '技艺与教习之牌聚——学习、进修或考较之事。',
	},
	{
		key: 'money_lack', theme: '资财吃紧之征', minHits: 2,
		pool: [{ sid: 'pentacles_01', rev: true }, { sid: 'pentacles_02', rev: true }, { sid: 'pentacles_09', rev: true }, { sid: 'pentacles_10', rev: true }, { sid: 'pentacles_05' }],
		hint: '钱币诸牌失位——入不敷出或周转承压,宜先止漏。',
	},
	{
		key: 'vivid_dreams', theme: '梦扰之征', minHits: 2,
		pool: [{ sid: 'the_moon' }, { sid: 'swords_09' }],
		hint: '月与不寐同现——梦境纷纭、夜思过载;宜安神缓虑。',
	},
	{
		key: 'wish', theme: '许愿牌', minHits: 1,
		pool: [{ sid: 'cups_09' }],
		hint: '心愿之牌在场(正位尤吉)——所求有成的传统吉征。',
	},
	{
		key: 'bad_news', theme: '滞讯之征', minHits: 2,
		pool: [{ sid: 'swords_08' }, { sid: 'swords_page' }, { sid: 'wands_08', rev: true }],
		hint: '讯息受阻诸牌并见——消息延误或来讯不顺,勿急下断。',
	},
];

export const COMBO_GUARD_NOTES = {
	transform: '护栏:转化类征象只论「结构性了断与更替」,不作死亡/灾祸预言。',
	health: '护栏:健康/孕育类征象仅为传统占验视角,非医疗建议;相关事宜请以医检为准。',
};

// 扫描 draws → 命中的征象列表。牌可复用于多条规则;每条规则内一张牌只计一次。
export function comboHints(draws){
	const list = (draws || []).filter((d) => d && d.card);
	if(!list.length){ return []; }
	const bySid = {};
	list.forEach((d) => { (bySid[d.card.sid] = bySid[d.card.sid] || []).push(d); });
	const out = [];
	COMBO_THEMES.forEach((rule) => {
		if(rule.needAll && !rule.needAll.every((sid) => bySid[sid])){ return; }
		const matched = [];
		rule.pool.forEach((p) => {
			const cands = bySid[p.sid] || [];
			const hit = cands.find((d) => (p.rev === undefined ? true : !!d.isReversed === !!p.rev));
			if(hit){ matched.push(`${hit.card.name_cn}${p.rev !== undefined ? (p.rev ? '(逆)' : '(正)') : ''}`); }
		});
		if(matched.length >= rule.minHits){
			out.push({ key: rule.key, theme: rule.theme, matched, hint: rule.hint, guard: rule.guard || null });
		}
	});
	return out;
}
