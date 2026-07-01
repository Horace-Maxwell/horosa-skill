// 八字 盲派结构分析（八字大全 §6.4，象法·做功）。
// best-effort，全标「结构·参考」：盲派弃旺衰废用忌，看宾主/体用/做功/废神，与扶抑/格局体系不同。
//   宾主：主 = 日柱(日干+日支，自己)；宾 = 年/月/时柱(他人/外物)。
//   体用：体 = 日主/比劫/印枭/食(我及我用的工具)；用 = 财/官/伤(我追求的目标)。
//   做功：主位之「体」去取宾位之「用」(生用/克取)，参与者为用功神，未参与者为废神。
//   刑冲合害为「动」之开关（此处仅结构标注，动的细判归关系层）。

const EL = { Wood: '木', Fire: '火', Earth: '土', Metal: '金', Water: '水' };
const GEN = { Wood: 'Fire', Fire: 'Earth', Earth: 'Metal', Metal: 'Water', Water: 'Wood' };
const KE = { Wood: 'Earth', Fire: 'Metal', Earth: 'Water', Metal: 'Wood', Water: 'Fire' };
const TI_GODS = new Set(['比', '劫', '印', '枭', '食', '禄']);
const YONG_GODS = new Set(['财', '才', '官', '杀', '伤']);

function relKind(a, b){
	if(!a || !b){ return ''; }
	if(GEN[a] === b){ return '生'; }
	if(KE[a] === b){ return '克'; }
	return '';
}

function catOf(god){
	if(god === '日元' || god === '日主'){ return '体'; }
	if(TI_GODS.has(god)){ return '体'; }
	if(YONG_GODS.has(god)){ return '用'; }
	return '';
}

export function computeMangPai(four){
	if(!four || !four.day || !four.day.stem){ return null; }
	const POS = [['year', '年'], ['month', '月'], ['day', '日'], ['time', '时']];
	const cells = POS.map(([k, label]) => {
		const p = four[k] || {};
		const stem = p.stem || {};
		const ben = (p.stemInBranch && p.stemInBranch[0]) || {};
		const role = k === 'day' ? '主' : '宾';
		const ganGod = k === 'day' ? '日元' : (stem.relative || '');
		const zhiGod = ben.relative || '';
		return {
			key: k, label, role,
			gan: stem.cell || '', ganEl: stem.element || '', ganGod,
			zhi: (p.branch && p.branch.cell) || '', zhiEl: ben.element || '', zhiGod,
		};
	});

	// 体用清单（按出现去重）
	const tiyong = [];
	const seen = new Set();
	cells.forEach((c) => {
		[c.ganGod, c.zhiGod].forEach((g) => {
			const cat = catOf(g);
			if(cat && !seen.has(g)){ seen.add(g); tiyong.push({ god: g === '日元' ? '日主' : g, cat }); }
		});
	});

	// 主位之体（日干、日支本气）
	const day = cells[2];
	const zhuTi = [];
	[[day.ganGod, day.ganEl, '日干'], [day.zhiGod, day.zhiEl, '日支']].forEach(([g, el, where]) => {
		if(catOf(g) === '体'){ zhuTi.push({ god: g === '日元' ? '日主' : g, el, where }); }
	});

	// 做功：主位体 → 宾位用（生/克）
	const zuogong = [];
	const gongGods = new Set();
	cells.filter((c) => c.role === '宾').forEach((c) => {
		[[c.ganGod, c.ganEl, `${c.label}干`], [c.zhiGod, c.zhiEl, `${c.label}支`]].forEach(([g, el, where]) => {
			if(catOf(g) !== '用'){ return; }
			zhuTi.forEach((t) => {
				const k = relKind(t.el, el);
				if(k){
					gongGods.add(t.god); gongGods.add(g);
					zuogong.push({
						from: `${t.where}·${t.god}`, to: `${where}·${g}`, kind: k,
						text: k === '克'
							? `${t.where}${t.god}(${EL[t.el]})克取${where}${g}(${EL[el]}) — 取用做功`
							: `${t.where}${t.god}(${EL[t.el]})生${where}${g}(${EL[el]}) — 生用做功`,
					});
				}
			});
		});
	});

	// 废神 = 出现的体/用十神中未参与做功者（非日主）
	const feishen = tiyong.filter((t) => t.god !== '日主' && !gongGods.has(t.god)).map((t) => `${t.god}(${t.cat})`);

	return {
		cells: cells.map((c) => ({ label: c.label, role: c.role, gan: c.gan, zhi: c.zhi, ganGod: c.ganGod === '日元' ? '日元' : c.ganGod, zhiGod: c.zhiGod })),
		tiyong,
		zuogong,
		feishen: Array.from(new Set(feishen)),
		note: '盲派结构·象法（参考）：主=日柱、宾=年月时；体=日主/比劫/印枭/食、用=财官伤；做功=主位之体取宾位之用。与扶抑/格局体系不同，刑冲合害为「动」之开关。',
	};
}

export default computeMangPai;
