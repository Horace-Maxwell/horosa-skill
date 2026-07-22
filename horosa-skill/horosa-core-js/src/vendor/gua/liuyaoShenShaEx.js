// 六爻神煞扩容(《断易天机》系):已知起例全集硬编码 + 月令神煞大表(抽取数据)合并注册。
// 与既有 liuyaoShenSha.js 并存:既有 10 种为「基础集」不动(零回归);本模块提供扩展集,facade 合并标注。
// 起例原语:月序顺行/逆行、四位循环、按季、按三合、按日干组、按年支、世前后位。正文与今注两套并存以 variant 区分。
import { YUELING_TABLE } from './data/tianjiShenSha.js'; // 抽取管线产物:模块加载即注入,同步可用
import { DIZHI, ZHI_WUXING, LIUCHONG } from './LiuYaoConst.js';

const zi = (i) => DIZHI[((i % 12) + 12) % 12];
const idx = (z) => DIZHI.indexOf(z);
const SEASON = { 寅: '春', 卯: '春', 辰: '春', 巳: '夏', 午: '夏', 未: '夏', 申: '秋', 酉: '秋', 戌: '秋', 亥: '冬', 子: '冬', 丑: '冬' };
const SANHE_GROUP = { 申: 'A', 子: 'A', 辰: 'A', 寅: 'B', 午: 'B', 戌: 'B', 巳: 'C', 酉: 'C', 丑: 'C', 亥: 'D', 卯: 'D', 未: 'D' };
const ganGroup = (g) => ('甲乙'.indexOf(g) >= 0 ? 0 : '丙丁'.indexOf(g) >= 0 ? 1 : '戊己'.indexOf(g) >= 0 ? 2 : '庚辛'.indexOf(g) >= 0 ? 3 : '壬癸'.indexOf(g) >= 0 ? 4 : -1);

// 孤辰寡宿(按年支三会方起):孤辰=会方末支下一位、寡宿=会方首支前一位。占婚忌,主孤独鳏寡。
// 亥子丑年孤辰寅寡宿戌 / 寅卯辰年孤辰巳寡宿丑 / 巳午未年孤辰申寡宿辰 / 申酉戌年孤辰亥寡宿未
const GUCHEN_GUASU = {
	亥: ['寅', '戌'], 子: ['寅', '戌'], 丑: ['寅', '戌'],
	寅: ['巳', '丑'], 卯: ['巳', '丑'], 辰: ['巳', '丑'],
	巳: ['申', '辰'], 午: ['申', '辰'], 未: ['申', '辰'],
	申: ['亥', '未'], 酉: ['亥', '未'], 戌: ['亥', '未'],
};

// 起例原语(均返回 支 数组;m=正月起月序 1-12)
const seq = (start, dir) => (m) => [zi(idx(start) + dir * (m - 1))];
const cyc4 = (list) => (m) => [list[(m - 1) % 4]];
const bySeason = (map) => (season) => (map[season] ? [].concat(map[season]) : []);

// ── 扩展神煞注册表(已知起例全集;calc(ctx) → 支[]) ──
// ctx:{ monthNum, monthZhi, dayGan, dayZhi, yearZhi, shiZhi }
export const SHENSHA_EX = [
	// —— 吉神 ——
	{ name: '天喜(季)', group: 'ji', duan: '喜庆临门', calc: (c) => bySeason({ 春: '戌', 夏: '丑', 秋: '辰', 冬: '未' })(SEASON[c.monthZhi]) },
	{ name: '天喜(月序)', group: 'ji', variant: '《断易天机》月序', duan: '喜庆临门', calc: (c) => (c.monthNum ? seq('戌', 1)(c.monthNum) : []) },
	{ name: '天医', group: 'ji', duan: '占病良医良药', calc: (c) => (c.monthZhi ? [zi(idx(c.monthZhi) - 1)] : []) }, // 月建退一辰(通行取法)
	{ name: '学堂', group: 'ji', duan: '聪明文学', calc: (c) => { const g = ganGroup(c.dayGan); return g < 0 ? [] : [['亥', '寅', '申', '巳', '申'][g]]; } },
	{ name: '唐苻国印', group: 'ji', duan: '官鬼临之旺相,主朝廷重臣;发动诏书至', calc: (c) => {
		const y = c.yearZhi; if(!y){ return []; }
		if('寅申'.indexOf(y) >= 0){ return ['巳', '亥']; } if('巳亥'.indexOf(y) >= 0){ return ['寅', '申']; }
		if('子午'.indexOf(y) >= 0){ return ['卯', '酉']; } if('卯酉'.indexOf(y) >= 0){ return ['子', '午']; }
		if('辰戌'.indexOf(y) >= 0){ return ['丑', '未']; } if('丑未'.indexOf(y) >= 0){ return ['辰', '戌']; }
		return [];
	} },
	{ name: '生气', group: 'ji', duan: '生气临用,生发;财临生气为活物', calc: (c) => (c.monthNum ? seq('子', 1)(c.monthNum) : []) },
	// —— 凶神 ——
	{ name: '死气', group: 'xiong', duan: '死气临之,衰死之象', calc: (c) => (c.monthNum ? seq('午', 1)(c.monthNum) : []) },
	{ name: '雷火杀', group: 'xiong', duan: '仕宦忌之', calc: (c) => (c.monthNum ? seq('寅', -1)(c.monthNum) : []) },
	{ name: '天刑', group: 'xiong', duan: '词讼动主自刑', calc: (c) => (c.monthNum ? seq('辰', -1)(c.monthNum) : []) },
	{ name: '大刑(虎刑)', group: 'xiong', duan: '词讼刑伤', calc: (c) => (c.monthNum ? seq('辰', 1)(c.monthNum) : []) },
	{ name: '天狱杀', group: 'xiong', variant: '今注引卜筮全书', duan: '占讼忌,主禁系', calc: (c) => (c.monthNum ? [['亥', '申', '巳', '寅'][(c.monthNum - 1) % 4]] : []) },
	{ name: '关锁杀(世位)', group: 'xiong', variant: '正文:世前二为锁、世后三为关', duan: '占讼主关锁禁系', calc: (c) => (c.shiZhi ? [zi(idx(c.shiZhi) - 2), zi(idx(c.shiZhi) + 3)] : []) },
	{ name: '关锁杀(四季)', group: 'xiong', variant: '今注:春丑关巳锁/夏辰申/秋未亥/冬戌寅', duan: '占讼主关锁禁系', calc: (c) => bySeason({ 春: ['丑', '巳'], 夏: ['辰', '申'], 秋: ['未', '亥'], 冬: ['戌', '寅'] })(SEASON[c.monthZhi]) },
	{ name: '折伤杀', group: 'xiong', duan: '行人归途防跌扑', calc: (c) => (c.monthNum ? cyc4(['酉', '午', '卯', '子'])(c.monthNum) : []) },
	{ name: '丧门杀(月系)', group: 'xiong', duan: '占病忌', calc: (c) => (c.monthNum ? cyc4(['戌', '未', '辰', '丑'])(c.monthNum) : []) },
	{ name: '丧门(太岁)', group: 'xiong', duan: '太岁前二辰,主孝服', calc: (c) => (c.yearZhi ? [zi(idx(c.yearZhi) + 2)] : []) },
	{ name: '吊客(太岁)', group: 'xiong', duan: '太岁后二辰,主孝服', calc: (c) => (c.yearZhi ? [zi(idx(c.yearZhi) - 2)] : []) },
	{ name: '五墓杀', group: 'xiong', duan: '占病忌,坟墓事', calc: (c) => bySeason({ 春: '未', 夏: '戌', 秋: '丑', 冬: '辰' })(SEASON[c.monthZhi]) },
	{ name: '暗金杀', group: 'xiong', duan: '占产忌动,主产厄', calc: (c) => (c.monthNum ? [['巳', '酉', '丑'][(c.monthNum - 1) % 3]] : []) },
	{ name: '天寡杀', group: 'xiong', duan: '占婚忌', calc: (c) => bySeason({ 春: '酉', 夏: '午', 秋: '卯', 冬: '子' })(SEASON[c.monthZhi]) },
	{ name: '鳏寡杀', group: 'xiong', duan: '占婚忌,主鳏寡', calc: (c) => bySeason({ 春: '丑', 夏: '辰', 秋: '未', 冬: '戌' })(SEASON[c.monthZhi]) },
	{ name: '孤辰', group: 'xiong', variant: '按年支三会方', duan: '占婚忌,主孤独不谐(男忌孤辰)', calc: (c) => (c.yearZhi && GUCHEN_GUASU[c.yearZhi] ? [GUCHEN_GUASU[c.yearZhi][0]] : []) },
	{ name: '寡宿', group: 'xiong', variant: '按年支三会方', duan: '占婚忌,主孤寡独处(女忌寡宿)', calc: (c) => (c.yearZhi && GUCHEN_GUASU[c.yearZhi] ? [GUCHEN_GUASU[c.yearZhi][1]] : []) },
	{ name: '天贼', group: 'xiong', duan: '主盗贼、失脱', calc: (c) => (c.monthNum ? [zi(4 + 5 * (c.monthNum - 1))] : []) },
	{ name: '天烛杀', group: 'xiong', duan: '主火烛', calc: (c) => (c.monthNum ? seq('巳', 1)(c.monthNum) : []) },
	{ name: '勾陈杀', group: 'xiong', duan: '家宅旺则官灾', calc: (c) => (c.monthNum ? seq('辰', -1)(c.monthNum) : []) },
	{ name: '天罡杀', group: 'xiong', duan: '渔猎动主多获;他占忌', calc: (c) => (c.monthNum ? cyc4(['寅', '卯', '辰', '巳'])(c.monthNum) : []) },
	{ name: '刀砧杀', group: 'xiong', duan: '六畜忌;金为刀、木为砧', calc: (c) => bySeason({ 春: ['亥', '子'], 夏: ['寅', '卯'], 秋: ['巳', '午'], 冬: ['申', '酉'] })(SEASON[c.monthZhi]) },
	{ name: '日下大杀', group: 'xiong', duan: '临财妻灾、临兄分张、临父子哭泣', calc: (c) => { const g = ganGroup(c.dayGan); return g < 0 ? [] : [['亥', '未', '戌', '寅', '巳'][g]]; } },
	{ name: '亡神杀(月系)', group: 'xiong', variant: '国朝章:正月从亥顺行', duan: '主失亡', calc: (c) => (c.monthNum ? seq('亥', 1)(c.monthNum) : []) },
];

// 四利三元(年支顺轮十二神):单列(一次产 12 名→支)
export const SILI_SANYUAN = ['太岁', '太阳', '丧门', '太阴', '官苻', '死苻', '岁破', '龙德', '白虎', '福德', '吊客', '病苻'];
export function siLiSanYuan(yearZhi){
	if(!yearZhi){ return null; }
	const s = idx(yearZhi);
	const out = {};
	SILI_SANYUAN.forEach((nm, i) => { out[nm] = zi(s + i); });
	return out;
}

// 进神/退神(干支定名,天玄赋身命章):甲子甲午己卯己酉为进神;壬戌壬辰丁丑丁未为退神(以爻纳干支论)
export const JINSHEN_GZ = ['甲子', '甲午', '己卯', '己酉'];
export const TUISHEN_GZ = ['壬戌', '壬辰', '丁丑', '丁未'];
export function jinTuiGZOf(gan, zhiC){
	const gz = (gan || '') + (zhiC || '');
	if(JINSHEN_GZ.indexOf(gz) >= 0){ return '进神(干支)'; }
	if(TUISHEN_GZ.indexOf(gz) >= 0){ return '退神(干支)'; }
	return '';
}

// 分组元数据(UI 勾选用)
export const SHENSHA_EX_GROUPS = [
	{ key: 'ji', label: '断易天机·吉神' },
	{ key: 'xiong', label: '断易天机·凶神' },
	{ key: 'yueling', label: '月令神煞大表' }, // 抽取数据注入
];

// 抽取数据注入口:tianjiShenSha.js 的 YUELING_TABLE 形如
// [{name, months:[12 支], jixiong:'吉'|'凶', duan}],由 WP-0 生成后 registerYueLing 注入
let YUELING = YUELING_TABLE || [];
export function registerYueLing(rows){ YUELING = rows || []; }
export function yueLingNames(){ return YUELING.map((r) => r.name); }

export function computeShenShaEx(ctx, selectedNames){
	const c = ctx || {};
	const sel = selectedNames ? new Set(selectedNames) : null;
	const res = {}; // name → { zhis, group, duan, variant }
	SHENSHA_EX.forEach((m) => {
		if(sel && !sel.has(m.name)){ return; }
		const zhis = (m.calc(c) || []).filter(Boolean);
		if(zhis.length){ res[m.name] = { zhis, group: m.group, duan: m.duan, variant: m.variant || '' }; }
	});
	YUELING.forEach((r) => {
		if(sel && !sel.has(r.name)){ return; }
		if(res[r.name]){ return; } // 同名(天医/生气/天刑/天贼四例):既有起例版优先,月令表版只补位
		if(!c.monthNum || !r.months || !r.months[c.monthNum - 1]){ return; }
		res[r.name] = { zhis: [r.months[c.monthNum - 1]], group: 'yueling', duan: r.duan || '', variant: r.jixiong || '' };
	});
	return res;
}
export function annotateShenShaEx(yaos, ctx, selectedNames){
	const map = computeShenShaEx(ctx, selectedNames);
	const perYao = (yaos || []).map((y) => ({
		pos: y.pos, zhi: y.zhi,
		shensha: Object.keys(map).filter((nm) => map[nm].zhis.indexOf(y.zhi) >= 0),
	}));
	return { shaMap: map, perYao };
}
