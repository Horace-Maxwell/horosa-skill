// 择日深化引擎 —— 用事十四事 · 紫白择日 · 三步选课（干支搭配自动检测）· 斗首法。
// 🔴 additive：由 zeri.js 在 showDeep 开启时调用；不改造命法本判。
// 🔴 传本两说并陈处（《宗镜》vs《诹吉述正》）本模块不判孰是，原样并列。
import {
	YONGSHI_JIANZAO_8, YONGSHI_SANGZANG_6, YONGSHI_NOTE,
	ZIBAI_JUE_4, ZIBAI_ZHONGYAO, ZIBAI_WUXING, ZIBAI_COMBO, ZIBAI_COMBO_NOTE,
	ZIBAI_SHIJIAN, ZIBAI_FU, ZIBAI_CHONG, ZIBAI_KONGJIAN, ZONGJING_YU, ZHUJI_SHUZHENG,
	YONGSHI_GONG_4, DONGXIANG_XIONG_COMBO, DONGXIANG_XIONG_XIAYUAN8, DONGXIANG_XIAYUAN8_NOTE,
	HUASHA_XUANXING, HUASHA_XUANXING_NOTE,
	SANBU_1_KEXING, SANBU_2_GANZHI, SANBU_3_GOUTONG, SANBU_NOTE,
	NUAN_GANZHI, SHI_GANZHI, TIANGAN_SANQI,
	DOUSHOU_SHAN_WUXING, DOUSHOU_SHAN_JUE, DOUSHOU_GAN_HUAQI, DOUSHOU_GAN_JUE,
	DOUSHOU_ZHI_ZHENGWUXING, DOUSHOU_ZHI_JUE, DOUSHOU_LIUQIN, DOUSHOU_DANGLING, DOUSHOU_NOTE,
	ZERI_DEEP_NOTE,
} from './fengshuiZeriDeepData.js';
import { ZHI_CHONG, POS_NAME } from './fengshuiData.js';

export const YONGSHI_ALL = YONGSHI_JIANZAO_8.map((x)=>({ ...x, cls: '建造类' }))
	.concat(YONGSHI_SANGZANG_6.map((x)=>({ ...x, cls: '丧葬类' })));

// ── 干支基础（择日用，自成一套，不动他处）──────────────────────────────────
const GAN = ['甲', '乙', '丙', '丁', '戊', '己', '庚', '辛', '壬', '癸'];
const ZHI = ['子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥'];
const GAN_WUHE = [['甲', '己'], ['乙', '庚'], ['丙', '辛'], ['丁', '壬'], ['戊', '癸']];
const ZHI_LIUHE = [['子', '丑'], ['寅', '亥'], ['卯', '戌'], ['辰', '酉'], ['巳', '申'], ['午', '未']];
const ZHI_SANHE = [['申', '子', '辰'], ['寅', '午', '戌'], ['亥', '卯', '未'], ['巳', '酉', '丑']];
const ZHI_SANHUI = [['寅', '卯', '辰'], ['巳', '午', '未'], ['申', '酉', '戌'], ['亥', '子', '丑']];
const SANHE_MID = { '申子辰': '子', '寅午戌': '午', '亥卯未': '卯', '巳酉丑': '酉' };
const SANHUI_MID = { '寅卯辰': '卯', '巳午未': '午', '申酉戌': '酉', '亥子丑': '子' };
const ZHI_XING = [['寅', '巳', '申'], ['丑', '戌', '未'], ['子', '卯'], ['辰'], ['午'], ['酉'], ['亥']];
const ZHI_HAI = [['子', '未'], ['丑', '午'], ['寅', '巳'], ['卯', '辰'], ['申', '亥'], ['酉', '戌']];
const WX_SHENG = { 木: '火', 火: '土', 土: '金', 金: '水', 水: '木' };
const WX_KE = { 木: '土', 土: '水', 水: '火', 火: '金', 金: '木' };

// 四柱（年月日时）拆干支；时柱可缺。
function splitPillars(pillars) {
	return (Array.isArray(pillars) ? pillars : []).filter(Boolean).map((gz)=>({
		gz, gan: gz.slice(0, gz.length - 1), zhi: gz.slice(-1),
	})).filter((p)=>GAN.indexOf(p.gan) >= 0 && ZHI.indexOf(p.zhi) >= 0);
}

// ── 干支搭配自动检测（三步选课之二）────────────────────────────────────────
export function ganZhiCheck(pillars, season) {
	const ps = splitPillars(pillars);
	if (!ps.length) { return null; }
	const gans = ps.map((p)=>p.gan); const zhis = ps.map((p)=>p.zhi);
	const labs = ['年', '月', '日', '时'].slice(0, ps.length);
	const has = (arr, set)=>set.every((x)=>arr.indexOf(x) >= 0);
	// 团结项
	const tuan = [];
	GAN_WUHE.forEach((p)=>{ if (has(gans, p)) { tuan.push({ kind: '天干五合', text: `${p.join('')}合` }); } });
	TIANGAN_SANQI.forEach((q)=>{ if (has(gans, q)) { tuan.push({ kind: '天干三奇', text: `${q.join('')}三奇` }); } });
	ZHI_SANHE.forEach((t)=>{
		const k = t.join('');
		if (has(zhis, t)) { tuan.push({ kind: '地支三合', text: `${k}三合` }); return; }
		const got = t.filter((z)=>zhis.indexOf(z) >= 0);
		if (got.length === 2 && got.indexOf(SANHE_MID[k]) >= 0) { tuan.push({ kind: '半三合(有中神)', text: `${got.join('')}半三合` }); }
	});
	ZHI_SANHUI.forEach((t)=>{
		const k = t.join('');
		if (has(zhis, t)) { tuan.push({ kind: '地支三会', text: `${k}三会` }); return; }
		const got = t.filter((z)=>zhis.indexOf(z) >= 0);
		if (got.length === 2 && got.indexOf(SANHUI_MID[k]) >= 0) { tuan.push({ kind: '半三会(有中神)', text: `${got.join('')}半三会` }); }
	});
	ZHI_LIUHE.forEach((p)=>{ if (has(zhis, p)) { tuan.push({ kind: '地支六合', text: `${p.join('')}六合` }); } });
	// 相战项（地支为重；贴冲＝相邻两柱）
	const zhan = [];
	for (let i = 0; i < zhis.length; i++) {
		for (let j = i + 1; j < zhis.length; j++) {
			if (ZHI_CHONG[zhis[i]] === zhis[j]) {
				const tie = (j - i === 1);
				const key = `${labs[i]}${labs[j]}`;
				zhan.push({ kind: '地支冲', text: `${labs[i]}${zhis[i]}冲${labs[j]}${zhis[j]}${tie ? '（贴冲）' : ''}`,
					weight: tie ? ((key === '月日' || key === '日时') ? 3 : 2) : 1 });
			}
			if (ZHI_HAI.some((p)=>(p[0] === zhis[i] && p[1] === zhis[j]) || (p[1] === zhis[i] && p[0] === zhis[j]))) {
				zhan.push({ kind: '地支害', text: `${labs[i]}${zhis[i]}害${labs[j]}${zhis[j]}`, weight: 1 });
			}
		}
	}
	ZHI_XING.forEach((t)=>{
		if (t.length >= 2 && t.every((z)=>zhis.indexOf(z) >= 0)) { zhan.push({ kind: '地支刑', text: `${t.join('')}相刑`, weight: 1 }); }
		if (t.length === 1 && zhis.filter((z)=>z === t[0]).length >= 2) { zhan.push({ kind: '地支自刑', text: `${t[0]}自刑`, weight: 1 }); }
	});
	GAN_WUHE.forEach(()=>{});   // 天干之战稍可，不计权
	// 寒暖（冬取暖干支、夏取湿干支）
	const all = gans.concat(zhis);
	const nuan = NUAN_GANZHI.filter((c)=>all.indexOf(c) >= 0);
	const shi = SHI_GANZHI.filter((c)=>all.indexOf(c) >= 0);
	let hanNuan = null;
	if (season === 'dong') { hanNuan = { need: '暖干支（丙丁寅巳午未戌）', got: nuan, ok: nuan.length > 0 }; }
	else if (season === 'xia') { hanNuan = { need: '湿干支（壬癸申亥子丑辰）', got: shi, ok: shi.length > 0 }; }
	const zhanWeight = zhan.reduce((a, x)=>a + x.weight, 0);
	return {
		pillars: ps.map((p)=>p.gz), gans, zhis,
		tuanJie: tuan, xiangZhan: zhan, zhanWeight,
		hanNuan, nuanGot: nuan, shiGot: shi,
		verdict: zhanWeight === 0
			? (tuan.length ? { text: `八字团结（${tuan.map((t)=>t.text).join('、')}），无相战`, jx: 'good' }
				: { text: '无相战，但亦无合会之团结', jx: 'neutral' })
			: (zhanWeight >= 3 ? { text: `地支相战较重（${zhan.map((z)=>z.text).join('、')}）`, jx: 'bad' }
				: { text: `有轻度相战（${zhan.map((z)=>z.text).join('、')}），须权衡`, jx: 'neutral' }),
		rules: SANBU_2_GANZHI,
	};
}

// ── 紫白：组合宜忌查检 ────────────────────────────────────────────────────
export function zibaiCombo(a, b, yun) {
	if (!a || !b) { return null; }
	const k = `${a}${b}`; const rk = `${b}${a}`;
	const hit = (arr)=>arr.indexOf(k) >= 0 || arr.indexOf(rk) >= 0;
	if (hit(ZIBAI_COMBO.jinji)) {
		if (hit(ZIBAI_COMBO.wuYunOnly) && Number(yun) === 5) { return { k, jx: 'neutral', text: `${k} 只有五运时可以组合` }; }
		return { k, jx: 'bad', text: `${k} 虽相生仍不宜，尤忌` };
	}
	if (hit(ZIBAI_COMBO.lingLun)) { return { k, jx: 'neutral', text: `${k} 因各运不同而另论` }; }
	if (hit(ZIBAI_COMBO.shengBuYi)) { return { k, jx: 'bad', text: `${k} 虽相生仍不宜` }; }
	if (hit(ZIBAI_COMBO.xiong)) { return { k, jx: 'bad', text: `${k} 相战·不宜` }; }
	if (hit(ZIBAI_COMBO.ji)) { return { k, jx: 'good', text: `${k} 相生·宜` }; }
	return { k, jx: 'neutral', text: `${k} 传本未列此组，不臆断` };
}
// 紫白：某星到某宫之冲伏。
export function zibaiChongFu(star, gong) {
	const s = Math.trunc(Number(star)); const g = Math.trunc(Number(gong));
	if (!(s >= 1 && s <= 9) || !(g >= 1 && g <= 9)) { return null; }
	if (ZIBAI_FU[s] === g) { return { kind: '伏', jx: 'good', text: `${s}到${g === 5 ? '中宫' : POS_NAME[g]}为伏——助旺` }; }
	if (ZIBAI_CHONG[s] === g) { return { kind: '冲', jx: 'bad', text: `${s}到${POS_NAME[g]}为冲——减力` }; }
	return { kind: '常', jx: 'neutral', text: `${s}到${g === 5 ? '中宫' : POS_NAME[g]}非冲非伏` };
}
// 动象宫凶组合 → 宜加临之化煞星。
export function huaShaStar(comboKey) {
	if (!comboKey) { return null; }
	const rev = String(comboKey).split('').reverse().join('');
	const hit = HUASHA_XUANXING.find((h)=>h.combos.indexOf(String(comboKey)) >= 0 || h.combos.indexOf(rev) >= 0);
	return hit ? { star: hit.star, why: hit.why, note: HUASHA_XUANXING_NOTE } : null;
}

// ── 斗首法 ────────────────────────────────────────────────────────────────
//   以坐山斗首五行为「我」，四课天干化气五行为「他」→ 六亲。
export function doushou(zuoShan, pillars) {
	const my = DOUSHOU_SHAN_WUXING[zuoShan];
	if (!my) { return null; }
	const relOf = (other)=>{
		if (other === my) { return 'yuanchen'; }
		if (WX_KE[my] === other) { return 'wucai'; }
		if (WX_SHENG[my] === other) { return 'lianzi'; }
		if (WX_SHENG[other] === my) { return 'tanlang'; }
		if (WX_KE[other] === my) { return 'pogui'; }
		return null;
	};
	const ps = splitPillars(pillars);
	const labs = ['年', '月', '日', '时'].slice(0, ps.length);
	const rows = ps.map((p, i)=>{
		const hq = DOUSHOU_GAN_HUAQI[p.gan] || null;
		const key = hq ? relOf(hq) : null;
		const meta = key ? DOUSHOU_LIUQIN.find((x)=>x.key === key) : null;
		return { pillar: labs[i], gz: p.gz, gan: p.gan, huaQi: hq,
			zhiWuxing: DOUSHOU_ZHI_ZHENGWUXING[p.zhi] || null,
			liuQin: meta ? meta.name : null, liuQinKey: key, rel: meta ? meta.rel : null };
	});
	const count = {};
	rows.forEach((r)=>{ if (r.liuQinKey) { count[r.liuQinKey] = (count[r.liuQinKey] || 0) + 1; } });
	const checks = DOUSHOU_LIUQIN.map((q)=>{
		const n = count[q.key] || 0;
		let ok = null; let text = '';
		if (q.key === 'yuanchen') { ok = n > 0; text = n > 0 ? `元辰见 ${n} 位——须再验当令` : '四课天干中无元辰'; }
		else if (q.key === 'lianzi') { ok = n <= 1; text = n <= 1 ? `廉子 ${n} 位——合「只宜一位」` : `廉子重见 ${n} 位——不宜`; }
		else if (q.key === 'tanlang') { ok = n === 0; text = n === 0 ? '贪狼不现——合「宜失令失位」' : `贪狼见 ${n} 位——须验其失令失位与否`; }
		else if (q.key === 'pogui') { ok = n === 0; text = n === 0 ? '破鬼不现——合' : `破鬼见 ${n} 位——宜用武财关鬼，忌有位有气`; }
		else { ok = null; text = n > 0 ? `武财见 ${n} 位——宜生入克入，不宜生出克出` : '武财不现'; }
		return { ...q, n, ok, text };
	});
	return {
		zuoShan, myWuxing: my, rows, checks,
		jue: { shan: DOUSHOU_SHAN_JUE, gan: DOUSHOU_GAN_JUE, zhi: DOUSHOU_ZHI_JUE },
		dangLing: DOUSHOU_DANGLING, note: DOUSHOU_NOTE,
	};
}

// ── 深化层主入口 ──────────────────────────────────────────────────────────
export function zeriDeep({ zuoShan = '', pillars = [], yongShi = '', season = '', yun = 9,
	zibaiA = 0, zibaiB = 0, chongFuStar = 0, chongFuGong = 0, dongCombo = '' } = {}) {
	const ys = YONGSHI_ALL.find((x)=>x.key === yongShi) || null;
	return {
		yongShi: ys, yongShiAll: YONGSHI_ALL, yongShiNote: YONGSHI_NOTE,
		zibai: {
			jue4: ZIBAI_JUE_4, zhongYao: ZIBAI_ZHONGYAO, wuXing: ZIBAI_WUXING,
			comboNote: ZIBAI_COMBO_NOTE, combo: zibaiCombo(zibaiA, zibaiB, yun),
			shiJian: ZIBAI_SHIJIAN, kongJian: ZIBAI_KONGJIAN,
			chongFu: zibaiChongFu(chongFuStar, chongFuGong),
			liangShuo: { zongJing: ZONGJING_YU, zhuJi: ZHUJI_SHUZHENG },
			gong4: YONGSHI_GONG_4,
			dongXiong: DONGXIANG_XIONG_COMBO, dongXiongXiaYuan8: DONGXIANG_XIONG_XIAYUAN8,
			dongXiongNote: DONGXIANG_XIAYUAN8_NOTE,
			huaSha: huaShaStar(dongCombo), huaShaAll: HUASHA_XUANXING,
		},
		sanBu: { keXing: SANBU_1_KEXING, ganZhi: ganZhiCheck(pillars, season), gouTong: SANBU_3_GOUTONG, note: SANBU_NOTE },
		douShou: doushou(zuoShan, pillars),
		note: ZERI_DEEP_NOTE,
	};
}

export default zeriDeep;
