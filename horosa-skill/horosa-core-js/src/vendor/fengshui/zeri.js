// 择日（选择）· 年家凶煞方位(9.1) + 建除十二神(9.3) + 黄道黑道(9.4) + 二十八宿值日(10.6) + 杨公造命(9.5)。
// 干支/节气月/值宿用 lunar-javascript;年神/建除/黄黑道用 fengshuiData 表。
import { Solar } from 'lunar-javascript';
import { yearZhiOf, yearGanZhi, zibaiYearCenter, mingGua, mingGroup, nayinOf } from './liqiCore.js';
import { zeriDeep } from './zeriDeep.js';
import {
	DIZHI, ZHI_TO_GONG, ZHI_CHONG, ZHI_SANHE_JU, SANSHA_BY_JU, TWELVE_YEAR_GODS, YEAR_GOD_JX,
	JIANCHU_12, JIANCHU_JX, HUANG_HEI_ORDER, HUANGDAO_SET, QINGLONG_START, XIU_28,
	ZIBAI_STAR, POS_NAME, GONG_NAME, GONG_GUA, BA_YAO_SHA, SHAN_24, SANHE_SHUANGSHAN,
	GUA8_WUXING, WUXING_SHENG, WUXING_KE,
} from './fengshuiData.js';

const zi = (z)=>DIZHI.indexOf(z);
function flyStar(center) { const pan = {}; const f = (n)=>(n - 5 + 9) % 9; for (let g = 1; g <= 9; g++) { pan[g] = (center - 1 + f(g)) % 9 + 1; } return pan; }

// ── 年家凶煞方位（9.1）：太岁/岁破/三煞/年五黄/十二岁君神 → 忌动方。──
export function yearGods(year) {
	const yz = yearZhiOf(year);
	const taisuiGong = ZHI_TO_GONG[yz];
	const suipoZhi = ZHI_CHONG[yz]; const suipoGong = ZHI_TO_GONG[suipoZhi];
	const ju = ZHI_SANHE_JU[yz];
	const sanshaZhi = SANSHA_BY_JU[ju] || [];
	const sanshaLabel = ['劫煞', '灾煞', '岁煞'];
	const sansha = sanshaZhi.map((z, i)=>({ name: sanshaLabel[i], zhi: z, gong: ZHI_TO_GONG[z] }));
	// 年五黄飞宫。
	const yc = zibaiYearCenter(year); const pan = flyStar(yc);
	let wuHuangGong = null; for (let g = 1; g <= 9; g++) { if (pan[g] === 5) { wuHuangGong = g; break; } }
	// 十二岁君神（自太岁支顺行）。
	const twelve = TWELVE_YEAR_GODS.map((name, i)=>{ const z = DIZHI[(zi(yz) + i) % 12]; return { name, zhi: z, gong: ZHI_TO_GONG[z], jx: YEAR_GOD_JX[name] }; });
	// 忌动方位（岁破/三煞/五黄=忌动土;太岁可向不宜坐犯）。
	const jiDong = new Set([suipoGong, wuHuangGong, ...sansha.map((s)=>s.gong)].filter(Boolean));
	return {
		year, yearGanZhi: yearGanZhi(year), yearZhi: yz,
		taisui: { zhi: yz, gong: taisuiGong, dir: POS_NAME[taisuiGong], note: '可向不宜坐犯，忌妄动' },
		suipo: { zhi: suipoZhi, gong: suipoGong, dir: POS_NAME[suipoGong], note: '太岁正冲·大凶忌修造动土' },
		sansha: { ju: `${ju}局`, list: sansha, note: '可向不可坐，忌坐三煞、忌动土' },
		wuHuang: { gong: wuHuangGong, dir: wuHuangGong ? POS_NAME[wuHuangGong] : null, note: '流年五黄飞临·忌动土兴修(最毒)' },
		twelveGods: twelve,
		jiDongGongs: Array.from(jiDong),
		jiDongDirs: Array.from(jiDong).map((g)=>POS_NAME[g]),
	};
}

// ── 日课：建除十二神(9.3) + 黄道黑道(9.4) + 二十八宿值日(10.6)。──
export function dayCourse(y, m, d) {
	const lunar = Solar.fromYmd(y, m, d).getLunar();
	const monthZhi = lunar.getMonthInGanZhi().slice(-1);   // 节气月建支
	const dayGZ = lunar.getDayInGanZhi(); const dayZhi = dayGZ.slice(-1);
	// 建除：建=日支==月建支，顺布。
	const jcIdx = ((zi(dayZhi) - zi(monthZhi)) % 12 + 12) % 12;
	const jianChu = JIANCHU_12[jcIdx];
	// 黄黑道：青龙起支(按月支)，12值神顺布。
	const qlStart = QINGLONG_START[monthZhi];
	const hhIdx = ((zi(dayZhi) - zi(qlStart)) % 12 + 12) % 12;
	const shen = HUANG_HEI_ORDER[hhIdx];
	const isHuang = HUANGDAO_SET.has(shen);
	// 二十八宿值日（lunar getXiu 可靠）。
	const xiuName = lunar.getXiu();
	const xiu = XIU_28.find((x)=>x.n === xiuName) || { n: xiuName, jx: 'neutral' };
	return {
		date: `${y}-${m}-${d}`, dayGanZhi: dayGZ, monthZhi,
		jianChu: { name: jianChu, jx: JIANCHU_JX[jianChu] },
		huangHei: { shen, dao: isHuang ? '黄道' : '黑道', jx: isHuang ? 'good' : 'bad' },
		xiu: { name: xiu.n, xiang: xiu.x || '', jx: xiu.jx },
	};
}

// ── 杨公造命择日（9.5）：坐山 + 候选日 → 补龙 / 扶山 / 相主 / 避煞 四纲。──
// 坐山 → 其三合局支组（扶山：四柱支入局为扶、冲坐山为破）。
function zuoShanZhiSet(zuoShan) {
	// 找坐山所在双山之支（山名本身是支，或在某双山串内）。
	let baseZhi = null;
	if (DIZHI.indexOf(zuoShan) >= 0) { baseZhi = zuoShan; }
	else { Object.keys(SANHE_SHUANGSHAN).forEach((z)=>{ if (SANHE_SHUANGSHAN[z].indexOf(zuoShan) >= 0) { baseZhi = z; } }); }
	if (!baseZhi) { return null; }
	const ju = ZHI_SANHE_JU[baseZhi];
	const juZhi = Object.keys(ZHI_SANHE_JU).filter((z)=>ZHI_SANHE_JU[z] === ju);   // 同局三支
	return { baseZhi, ju, juZhi, chong: ZHI_CHONG[baseZhi] };
}
// 五行生克判读：相对「我」（来龙/主命）看某五行之作用。
function wuxingEffect(my, other) {
	if (!my || !other) { return null; }
	if (my === other) { return { rel: '比和', dir: 'help' }; }
	if (WUXING_SHENG[other] === my) { return { rel: '生我', dir: 'help' }; }
	if (WUXING_KE[other] === my) { return { rel: '克我', dir: 'harm' }; }
	if (WUXING_SHENG[my] === other) { return { rel: '我生(泄)', dir: 'harm' }; }
	return { rel: '我克(耗)', dir: 'neutral' };
}
// 月 → 季（寒暖调候用：冬＝亥子丑月即公历 11-1 月；夏＝巳午未月即公历 5-7 月）。
function seasonOf(m) {
	const n = Math.trunc(Number(m)) || 0;
	if (n === 11 || n === 12 || n === 1) { return 'dong'; }
	if (n >= 5 && n <= 7) { return 'xia'; }
	return '';
}

// zaoMing({ zuoShan, y, m, d, laiLong, zhuMing:{year,isMale} })
//   laiLong / zhuMing 缺省时行为与旧版完全一致（补龙、相主两纲不产出、不计分）。
export function zaoMing({ zuoShan = '子', y, m, d, laiLong, zhuMing,
	showDeep = false, yongShi = '', hourGanZhi = '', zibaiA = 0, zibaiB = 0,
	chongFuStar = 0, chongFuGong = 0, dongCombo = '', yun = 9 } = {}) {
	if (y == null) { return { available: false }; }
	const lunar = Solar.fromYmd(y, m, d).getLunar();
	const pillars = [lunar.getYearInGanZhi(), lunar.getMonthInGanZhi(), lunar.getDayInGanZhi()];
	const zhis = pillars.map((p)=>p.slice(-1));
	const labs = ['年', '月', '日'];
	const zss = zuoShanZhiSet(zuoShan);
	const year = lunar.getSolar().getYear();
	const yg = yearGods(year);
	const items = [];
	let score = 0;
	// ① 补龙：来龙山 → 双山三合局五行；四柱纳音生扶来龙 +1、克泄 −1。
	let longInfo = null;
	if (laiLong) {
		const lss = zuoShanZhiSet(laiLong);
		if (lss) {
			const longWx = lss.ju;   // 三合局即龙之五行（水/火/木/金）
			longInfo = { shan: laiLong, ju: `${longWx}局`, wuxing: longWx };
			pillars.forEach((gz, i)=>{
				const ny = nayinOf(gz);
				if (!ny) { return; }
				const eff = wuxingEffect(longWx, ny.wuxing);
				if (!eff) { return; }
				if (eff.dir === 'help') { items.push({ gang: '补龙', pillar: labs[i], zhi: gz, effect: `${ny.name}(${ny.wuxing})${eff.rel}来龙${longWx}·补龙`, jx: 'good' }); score += 1; }
				else if (eff.dir === 'harm') { items.push({ gang: '补龙', pillar: labs[i], zhi: gz, effect: `${ny.name}(${ny.wuxing})${eff.rel}来龙${longWx}·伤龙`, jx: 'bad' }); score -= 1; }
			});
		}
	}
	// ② 扶山（旧有口径不变）。
	if (zss) {
		zhis.forEach((z, i)=>{
			if (zss.juZhi.indexOf(z) >= 0) { items.push({ gang: '扶山', pillar: labs[i], zhi: z, effect: `${z}入坐山三合局·扶山`, jx: 'good' }); score += 1; }
			else if (z === zss.chong) { items.push({ gang: '扶山', pillar: labs[i], zhi: z, effect: `${z}冲坐山·大忌`, jx: 'bad' }); score -= 2; }
		});
	}
	// ③ 相主：主命年 → 命卦五行；四柱纳音生扶 +1、克主命 −2、支冲主命年支 −2。
	let zhuInfo = null;
	if (zhuMing && zhuMing.year != null && zhuMing.year !== '') {
		const mYear = Math.trunc(Number(zhuMing.year));
		if (!Number.isNaN(mYear)) {
			const g = mingGua(mYear, zhuMing.isMale !== false);
			const gua = GONG_GUA[g];
			const mWx = GUA8_WUXING[gua];
			const mZhi = yearZhiOf(mYear);
			zhuInfo = { year: mYear, isMale: zhuMing.isMale !== false, gua, group: mingGroup(g), wuxing: mWx, yearZhi: mZhi };
			pillars.forEach((gz, i)=>{
				const ny = nayinOf(gz);
				const eff = ny ? wuxingEffect(mWx, ny.wuxing) : null;
				if (eff && eff.dir === 'help') { items.push({ gang: '相主', pillar: labs[i], zhi: gz, effect: `${ny.name}(${ny.wuxing})${eff.rel}主命${gua}${mWx}·相主`, jx: 'good' }); score += 1; }
				else if (eff && eff.rel === '克我') { items.push({ gang: '相主', pillar: labs[i], zhi: gz, effect: `${ny.name}(${ny.wuxing})克主命${gua}${mWx}·伤主`, jx: 'bad' }); score -= 2; }
				if (zhis[i] === ZHI_CHONG[mZhi]) { items.push({ gang: '相主', pillar: labs[i], zhi: gz, effect: `${zhis[i]}冲主命${mZhi}·大忌`, jx: 'bad' }); score -= 2; }
			});
		}
	}
	// ④ 避煞：四柱支犯 三煞/岁破/坐山八曜煞。
	const sanshaZhi = (yg.sansha.list || []).map((s)=>s.zhi);
	const zuoGua = zss ? GONG_GUA[SHAN_24[zss.baseZhi] ? SHAN_24[zss.baseZhi][0] : null] : null;
	const baYao = zuoGua ? BA_YAO_SHA[zuoGua] : null;
	zhis.forEach((z, i)=>{
		const lab = labs[i];
		if (sanshaZhi.indexOf(z) >= 0) { items.push({ gang: '避煞', pillar: lab, zhi: z, effect: `${z}犯年三煞·避`, jx: 'bad' }); score -= 1; }
		if (z === yg.suipo.zhi) { items.push({ gang: '避煞', pillar: lab, zhi: z, effect: `${z}犯岁破·避`, jx: 'bad' }); score -= 2; }
		if (baYao && z === baYao) { items.push({ gang: '避煞', pillar: lab, zhi: z, effect: `${z}犯坐山八曜煞·避`, jx: 'bad' }); score -= 1; }
	});
	const grade = score >= 2 ? { text: '扶山避煞·吉课', jx: 'good' } : score >= 0 ? { text: '平课·可用', jx: 'neutral' } : { text: '冲坐犯煞·凶课不宜', jx: 'bad' };
	const done = ['补龙', '扶山', '相主', '避煞'].filter((g)=>(g === '补龙' ? !!longInfo : (g === '相主' ? !!zhuInfo : true)));
	return {
		available: true, zuoShan, date: `${y}-${m}-${d}`, pillars, zuoJu: zss ? `${zss.ju}局` : null,
		items, score, grade, laiLong: longInfo, zhuMing: zhuInfo, gangDone: done,
		// 深化层（additive）：不开 showDeep 时为 null，其余字段逐字段零回归。
		deep: showDeep ? zeriDeep({
			zuoShan, yongShi, yun,
			pillars: hourGanZhi ? pillars.concat([hourGanZhi]) : pillars,
			season: seasonOf(Number(m)),
			zibaiA, zibaiB, chongFuStar, chongFuGong, dongCombo,
		}) : null,
		note: `造命四纲=补龙·扶山·相主·避煞；本课已评 ${done.join('·')}`
			+ (longInfo ? '' : '；未填来龙则不评补龙')
			+ (zhuInfo ? '' : '；未填主命则不评相主'),
	};
}
