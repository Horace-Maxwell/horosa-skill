// 神数正传 · 六亲属相姓氏断 —— 前端本地确定性引擎（零后端 / 零随机 / 全整数）。
//
// 本支配合十二宫与遁甲盘演六亲之属相、妻室之姓氏，含三法：
//   ① 旬遁断生肖：十二宫定六亲宫 → 宫之天干入地盘 → 起旬首顺数至该宫 → 落宫之干 → 旬中同干者之支
//   ② 范围秘音断妻姓氏：四柱配先后天数 → 演连山卦与动爻 → 动爻纳甲之支遁仪 → 两盘定先后天五行
//      → 入姓氏谱定表号 → 先天五行取干行、后天五行取偏旁 → 姓氏
//   ③ 玄机卦动爻：年上起月、月上起日、日上起时得宫位 → 演算时辰与环境定四象 → 四象配宫位得动爻
//
// 数表见 data/zhengchuanLiuqinTables.json（由古籍机读录入，附不变式自证：
//   地四象动爻位 = 7 − 天四象动爻位 48/48；动爻位取值恒 1..6 96/96；两盘各配八卦一卦）。
//
// 已对古籍算例逐步验证：
//   · 旬遁 例一乾造(乙未甲申己酉己巳)：年干乙五虎遁起戊寅 → 命宫卯 → 夫妻宫己丑(古籍同)、
//     父母宫庚辰(古籍同) → 己入地盘坤2 → 起甲申顺数至己丑落兑7 → 丁 → 甲申旬中丁者丁亥 → 猪
//   · 旬遁 例二乾造(乙巳辛巳乙亥壬午)：妻宫乙酉 → 乙入地盘离9 → 甲申顺数至乙酉落坎1 → 戊 → 戊子 → 鼠
//   · 秘音 例(庚戌庚辰己未丁卯)：先天基数1393、后天基数328、合1721 → 上艮下震、五爻动纳甲丙子
//     → 子遁甲子戊 → 先天盘艮土、后天盘巽木 → 表号(甲9+子亥1、6=16)÷6余4 → 第四表戊己行
//     偏旁带木者全表唯一「林」（在巳栏）
//   · 玄机 例(1978年三月初三午时·阳男)：宫位辰 → 白天午时逢阴 → 天四象「日」→ [日][辰]=6 → 六爻动
import TABLES from './data/zhengchuanLiuqinTables.json' with { type: 'json' };
import { najiaOf } from './zhengchuanShaoziLocal.js';

export const LIUQIN_META = TABLES._meta || { gaps: [], ambiguous: [], corrections: [] };

const GAN = ['甲', '乙', '丙', '丁', '戊', '己', '庚', '辛', '壬', '癸'];
const ZHI = ['子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥'];
const SHENGXIAO = ['鼠', '牛', '虎', '兔', '龍', '蛇', '馬', '羊', '猴', '雞', '狗', '豬'];
// 先天八卦数（本表用繁体卦名，与数据文件一致；仓内同名常量为简繁混排且未导出，不复用以免键错配）
const XIANTIAN_GUA_NUM = { 乾: 1, 兌: 2, 離: 3, 震: 4, 巽: 5, 坎: 6, 艮: 7, 坤: 8 };
// 九宫序（洛书）：坎1 坤2 震3 巽4 中5 乾6 兌7 艮8 離9
const GONG_OF_GUA = { 坎: 1, 坤: 2, 震: 3, 巽: 4, 中: 5, 乾: 6, 兌: 7, 艮: 8, 離: 9 };
// 阳遁一局地盘：六仪三奇各居一宫（甲遁不上盘）
const DIPAN = { 1: '戊', 2: '己', 3: '庚', 4: '辛', 5: '壬', 6: '癸', 7: '丁', 8: '丙', 9: '乙' };
const GONG_OF_GAN = Object.keys(DIPAN).reduce((m, g) => { m[DIPAN[g]] = Number(g); return m; }, {});
// 六甲旬首及其所遁之仪
const XUN_SHOU = ['甲子', '甲戌', '甲申', '甲午', '甲辰', '甲寅'];
const XUN_YI = { 甲子: '戊', 甲戌: '己', 甲申: '庚', 甲午: '辛', 甲辰: '壬', 甲寅: '癸' };
// 三卦纯阳纳阳支、纯阴纳阴支 → 动爻落阴卦时其支无「甲X」可配（见 gaps）
const YANG_ZHI = new Set(['子', '寅', '辰', '午', '申', '戌']);

const gzIndex = (gz) => {
	const gi = GAN.indexOf(gz[0]);
	const zi = ZHI.indexOf(gz[1]);
	if (gi < 0 || zi < 0) return -1;
	for (let n = 0; n < 60; n += 1) if (n % 10 === gi && n % 12 === zi) return n;
	return -1;
};
/** 干支所属之旬（旬首）与其中位次 k（1..10） */
export function xunOf(gz) {
	const n = gzIndex(gz);
	if (n < 0) return null;
	const head = Math.floor(n / 10) * 10;
	return { shou: GAN[head % 10] + ZHI[head % 12], k: n - head + 1 };
}
/** 五虎遁：年干 → 正月（建寅）之干 → 十二宫干支（寅起） */
export function twelvePalaces(yearGan) {
	const yi = GAN.indexOf(yearGan);
	if (yi < 0) return null;
	const yinGan = ((yi % 5) * 2 + 2) % 10; // 甲己之年丙作首…
	const out = {};
	for (let i = 0; i < 12; i += 1) {
		const zhi = ZHI[(2 + i) % 12]; // 寅起
		out[zhi] = GAN[(yinGan + i) % 10] + zhi;
	}
	return out;
}

/**
 * 命宫：寅上起正月顺数至生月，得支上起子时逆数至生时。
 * 阳男阴女顺、阴男阳女逆（古籍于本法之演例皆顺数取月、逆数取时）。
 */
export function mingGong({ lunarMonth, hourZhi }) {
	const m = Number(lunarMonth);
	const hi = ZHI.indexOf(hourZhi);
	if (!(m >= 1 && m <= 12) || hi < 0) return null;
	const monthPalace = (2 + (m - 1)) % 12;          // 寅起正月，顺数至生月
	const gong = ((monthPalace - hi) % 12 + 12) % 12; // 该支起子时，逆数至生时
	return ZHI[gong];
}

/** 六亲宫：天逆地顺 —— 乾造 夫妻=命−2 / 父母=命+1；坤造 夫妻=命+2 / 父母=命−1 */
export function liuqinGong(mingZhi, gender) {
	const i = ZHI.indexOf(mingZhi);
	if (i < 0) return null;
	const male = Number(gender) === 1;
	const at = (d) => ZHI[((i + d) % 12 + 12) % 12];
	return { ming: mingZhi, spouse: at(male ? -2 : 2), parent: at(male ? 1 : -1) };
}

/**
 * 旬遁：由六亲宫之干支求其属相。
 * P0 = 地盘中该宫天干所居之宫（甲不上盘 → 取其旬之仪）；自 P0 起该宫所属旬之旬首，
 * 顺数 k−1 宫得 P（含中五，九宫回绕）；取地盘[P] 之干 D；该旬中天干为 D 者，其支即属相。
 */
export function xunDun(palaceGz) {
	const xun = xunOf(palaceGz);
	if (!xun) return null;
	let gan = palaceGz[0];
	let ganNote = '';
	if (gan === '甲') { gan = XUN_YI[xun.shou]; ganNote = `甲不上盘，取本旬之仪 ${gan}`; }
	const p0 = GONG_OF_GAN[gan];
	if (!p0) return null;
	const p = ((p0 - 1 + xun.k - 1) % 9 + 9) % 9 + 1;
	const d = DIPAN[p];
	// 该旬中天干为 D 者
	const headIdx = gzIndex(xun.shou);
	let hit = null;
	for (let j = 0; j < 10; j += 1) {
		const n = headIdx + j;
		if (GAN[n % 10] === d) { hit = GAN[n % 10] + ZHI[n % 12]; break; }
	}
	if (!hit) return null;
	const zhi = hit[1];
	return {
		palaceGz, xunShou: xun.shou, k: xun.k, ganUsed: gan, ganNote,
		p0, p0Gua: Object.keys(GONG_OF_GUA).find((g) => GONG_OF_GUA[g] === p0),
		p, pGua: Object.keys(GONG_OF_GUA).find((g) => GONG_OF_GUA[g] === p),
		dunGan: d, hitGz: hit, zhi, shengxiao: SHENGXIAO[ZHI.indexOf(zhi)],
	};
}

/** ① 旬遁断生肖：由本命四柱与性别，出夫妻、父母之属相 */
export function calcShengxiao({ pillars, gender, lunarMonth }) {
	if (!Array.isArray(pillars) || pillars.length < 4 || pillars.some((x) => !x || `${x}`.length < 2)) return null;
	const palaces = twelvePalaces(pillars[0][0]);
	if (!palaces) return null;
	const hourZhi = pillars[3][1];
	const m = Number(lunarMonth) || (ZHI.indexOf(pillars[1][1]) - 2 + 12) % 12 + 1; // 无农历月时以月支还原（寅为正月）
	const ming = mingGong({ lunarMonth: m, hourZhi });
	if (!ming) return null;
	const gongs = liuqinGong(ming, gender);
	const items = {};
	['spouse', 'parent'].forEach((k) => {
		const gz = palaces[gongs[k]];
		items[k] = { gong: gongs[k], gz, dun: xunDun(gz) };
	});
	return {
		palaces, mingGong: ming, mingGz: palaces[ming], gongs, items,
		steps: [
			{ label: '十二宫干支', detail: `年干 ${pillars[0][0]} 五虎遁起 ${palaces['寅']}`, value: `寅${palaces['寅']} … 丑${palaces['丑']}` },
			{ label: '命宫', detail: `寅上起正月顺数至 ${m} 月，得支上起子时逆数至 ${hourZhi} 时`, value: `${ming}（${palaces[ming]}）` },
			{ label: '夫妻宫', detail: Number(gender) === 1 ? '乾造：命宫逆二位' : '坤造：命宫顺二位', value: `${gongs.spouse}（${palaces[gongs.spouse]}）` },
			{ label: '父母宫', detail: Number(gender) === 1 ? '乾造：命宫顺一位' : '坤造：命宫逆一位', value: `${gongs.parent}（${palaces[gongs.parent]}）` },
		],
	};
}

/** ② 范围秘音断妻姓氏 */
export function calcQiziXingshi({ pillars }) {
	if (!Array.isArray(pillars) || pillars.length < 4 || pillars.some((x) => !x || `${x}`.length < 2)) return null;
	const XT = TABLES.xianTianNum;
	const HT = TABLES.houTianNum;
	const num = (gz, t) => (t[gz[0]] || 0) + (t[gz[1]] || 0);
	// 先天基数 = 时干支数×100 + 日干支数×10 + 月干支数×1
	const shi = num(pillars[3], XT);
	const ri = num(pillars[2], XT);
	const yue = num(pillars[1], XT);
	const xianTianBase = shi * 100 + ri * 10 + yue;
	// 后天基数 = 四干和×10 + 四支和
	const ganSum = pillars.reduce((s, gz) => s + (HT[gz[0]] || 0), 0);
	const zhiSum = pillars.reduce((s, gz) => s + (HT[gz[1]] || 0), 0);
	const houTianBase = ganSum * 10 + zhiSum;
	const total = xianTianBase + houTianBase;

	// 演卦：千百÷8 余=连山卦(上)、十个÷8 余=连山卦(下)、四位相加÷6=动爻
	const d = String(total).padStart(4, '0').split('').map(Number);
	const qianBai = d[0] * 10 + d[1];
	const shiGe = d[2] * 10 + d[3];
	const rUp = qianBai % 8 || 8;
	const rDown = shiGe % 8 || 8;
	const LS = TABLES.lianshanGua;
	const up = LS[rUp];
	const down = LS[rDown];
	const digitSum = d.reduce((a, b) => a + b, 0);
	const dongYao = digitSum % 6 || 6;

	// 动爻纳甲
	const TRI = { 乾: [1, 1, 1], 兌: [1, 1, 0], 離: [1, 0, 1], 震: [1, 0, 0], 巽: [0, 1, 1], 坎: [0, 1, 0], 艮: [0, 0, 1], 坤: [0, 0, 0] };
	const lines = [...(TRI[down] || []), ...(TRI[up] || [])];
	const najia = najiaOf(lines);
	const yaoGz = najia && najia[dongYao - 1];
	const yaoZhi = yaoGz ? yaoGz[1] : null;

	const out = {
		input: { pillars }, xianTianBase, houTianBase, total, upGua: up, downGua: down, dongYao, yaoGz, yaoZhi,
		steps: [
			{ label: '先天基数', detail: `时 ${pillars[3]}=${shi} ×100 + 日 ${pillars[2]}=${ri} ×10 + 月 ${pillars[1]}=${yue}`, value: xianTianBase },
			{ label: '后天基数', detail: `四干和 ${ganSum} ×10 + 四支和 ${zhiSum}`, value: houTianBase },
			{ label: '合先后天数', detail: `${xianTianBase} + ${houTianBase}`, value: total },
			{ label: '连山卦（上）', detail: `千百 ${qianBai} ÷8 余 ${rUp}`, value: up },
			{ label: '连山卦（下）', detail: `十个 ${shiGe} ÷8 余 ${rDown}`, value: down },
			{ label: '动爻', detail: `四位相加 ${d.join('+')}=${digitSum} ÷6 余 ${dongYao}`, value: `${dongYao} 爻动（纳甲 ${yaoGz || '—'}）` },
		],
	};

	// 动爻纳甲之支遁仪 → 两盘定先后天五行
	if (!yaoZhi) return { ...out, missing: '动爻纳甲不可得' };
	if (!YANG_ZHI.has(yaoZhi)) {
		// 六甲旬首之支皆阳；动爻落阴卦则其支无「甲X」可配，古籍未载此格之遁法 → 显式标缺，不臆补
		return { ...out, missing: `动爻纳甲为 ${yaoGz}，其支属阴。古籍此法只载阳支配甲之例（如「地支子遁为甲子戊」），阴支之遁法未载 → 本格不推。` };
	}
	const xunShou = `甲${yaoZhi}`;
	const yi = XUN_YI[xunShou];
	const xtGua = TABLES.dunjiaXianTian[yi];
	const htGua = TABLES.dunjiaHouTian[yi];
	const xtWx = TABLES.guaWuxing[xtGua];
	const htWx = TABLES.guaWuxing[htGua];
	out.steps.push(
		{ label: '动爻之支遁仪', detail: `地支 ${yaoZhi} 遁为 ${xunShou}${yi}`, value: yi },
		{ label: '先天五行', detail: `${xunShou}${yi} 临先天盘 ${xtGua}`, value: xtWx },
		{ label: '后天五行', detail: `${xunShou}${yi} 临后天盘 ${htGua}`, value: htWx },
	);

	// 表号 = (旬首干先天数 + 该支后天数同组两数) ÷6 之余
	const pair = TABLES.houTianPair[yaoZhi] || [];
	const sum = (TABLES.xianTianNum['甲'] || 0) + pair.reduce((a, b) => a + b, 0);
	const tableNo = sum % 6 || 6;
	out.steps.push({ label: '入姓氏谱表号', detail: `甲 ${TABLES.xianTianNum['甲']} + ${yaoZhi}${pair.join('、')} 共 ${sum}，÷6 余 ${sum % 6}`, value: `第 ${tableNo} 表` });

	// 第N表中：先天五行取干行，后天五行取偏旁 → 姓氏
	const table = TABLES.xingshiPu[tableNo - 1] || {};
	const ganRow = Object.keys(TABLES.ganWuxing).find((k) => TABLES.ganWuxing[k] === xtWx);
	const row = table[ganRow] || [];
	const cands = [];
	row.forEach((name, i) => {
		if (!name) return;
		if (radicalElement(name) === htWx) cands.push({ name, zhi: ZHI[i] });
	});
	out.tableNo = tableNo; out.ganRow = ganRow; out.xianTianWuxing = xtWx; out.houTianWuxing = htWx;
	out.candidates = cands;
	out.steps.push({ label: '取姓氏', detail: `第 ${tableNo} 表 ${ganRow} 行（先天五行 ${xtWx}）中，偏旁属后天五行 ${htWx} 者`, value: cands.length ? cands.map((c) => `${c.name}（${c.zhi} 栏）`).join('、') : '此格无合者' });
	if (cands.length === 1) { out.xingshi = cands[0].name; out.xingshiZhi = cands[0].zhi; }
	// 成数序须查六十四卦谱（姓氏所入之卦），此谱古籍未载 → 条文号不推
	out.chengShuNote = '成数序须由姓氏所入之卦起算（支序×1000 + 下卦先天数×100 + 先天五行卦先天数×10 + 上卦先天数），其「姓氏入卦」之谱古籍未载 → 条文号不推。';
	return out;
}

// 姓氏偏旁五行（古籍以偏旁取五行；此处依字形部首归类，只覆盖姓氏谱所出之字）
const RADICAL = {
	木: '林朱李杨楊柳杜梅栗桂柴東东本朴權权樊樑梁楚桑相查栢柯松柏梓楠榮荣椿桐棠杞枚枝格檀櫻樱橋桥權宋末未术',
	火: '火炎焦煥焕燕熊耿煒炜灼炳炤照烈燈灯爍烁炅赤丹朱夏南离離',
	土: '土地圭堯尧培基垣城域塘坤墨黃黄圓圆均坊坂圻埃塵尘',
	金: '金鐘钟鑫銀银鋼钢鍾钅劉刘釗钊鑑鉉铉鏡镜錢钱鋒锋鈴铃鍇锴銘铭鎮镇釘钉',
	水: '水江河海湖溪洪汪池沈潘淳游泳浩涂塗清溫温湯汤沙洛泰澤泽濟济漢汉洲滿满渠潭澄浚滕淩凌冰冷凍冻',
};
export function radicalElement(name) {
	const ch = String(name || '')[0];
	if (!ch) return null;
	// 先按整字命中，再按左偏旁命中
	const hit = Object.keys(RADICAL).find((k) => RADICAL[k].indexOf(ch) >= 0);
	return hit || null;
}

/** ③ 玄机卦动爻：宫位 → 四象 → 动爻 */
export function calcXuanjiDongyao({ yearZhi, lunarMonth, lunarDay, hourZhi, isLeapMonth, gender, yangYear, askHourZhi, env }) {
	const yi = ZHI.indexOf(yearZhi);
	const hi = ZHI.indexOf(hourZhi);
	let m = Number(lunarMonth);
	const dnum = Number(lunarDay);
	if (yi < 0 || hi < 0 || !(m >= 1 && m <= 12) || !(dnum >= 1 && dnum <= 30)) return null;
	// 闰月：初一至十五作前月，十六至三十作后月
	let leapNote = '';
	if (isLeapMonth) {
		if (dnum >= 16) { m += 1; leapNote = '闰月十六日后作后月'; }
		else leapNote = '闰月十五日前作前月';
		if (m > 12) m = 1;
	}
	// 阳男阴女顺数、阴男阳女逆数
	const male = Number(gender) === 1;
	const fwd = (male && yangYear) || (!male && !yangYear);
	const step = fwd ? 1 : -1;
	const at = (from, n) => ((from + step * n) % 12 + 12) % 12;
	const p1 = at(yi, m - 1);                 // 年上起月
	const p2 = at(p1, dnum - 1);              // 月上起日
	const p3 = at(p2, hi);                    // 日上起时
	const gong = ZHI[p3];

	// 演算时辰定四象：卯–申白天走天四象、酉–寅昼夜走地四象
	const ai = ZHI.indexOf(askHourZhi);
	const isDay = ai >= 3 && ai <= 8;
	const table = isDay ? TABLES.tianSiXiang : TABLES.diSiXiang;
	const row = table[env];
	const sixiang = row ? row[`${askHourZhi}時`] : null;
	const dyTable = isDay ? TABLES.tianDongYao : TABLES.diDongYao;
	const dongYao = sixiang && dyTable[sixiang] ? dyTable[sixiang][p3] : null;

	return {
		gong, sixiang, dongYao, isDay, env, askHourZhi, direction: fwd ? '顺数' : '逆数',
		steps: [
			{ label: '年上起月', detail: `${yearZhi} 上起正月${step > 0 ? '顺' : '逆'}数至 ${m} 月${leapNote ? `（${leapNote}）` : ''}`, value: ZHI[p1] },
			{ label: '月上起日', detail: `${ZHI[p1]} 上起初一${step > 0 ? '顺' : '逆'}数至 ${dnum} 日`, value: ZHI[p2] },
			{ label: '日上起时', detail: `${ZHI[p2]} 上起子时${step > 0 ? '顺' : '逆'}数至 ${hourZhi} 时`, value: gong },
			{ label: '四象', detail: `${isDay ? '白天（卯–申）取天四象' : '昼夜（酉–寅）取地四象'}：${askHourZhi} 时逢「${env}」`, value: sixiang || '—' },
			{ label: '动爻', detail: sixiang ? `${isDay ? '天' : '地'}四象「${sixiang}」配宫位「${gong}」` : '四象不可得', value: dongYao ? `${dongYao} 爻动` : '—' },
		],
	};
}

/** 铁算心法各时辰之序列（演卦须秘咒定上卦，秘咒古籍未载 → 只供查阅） */
export function xinFaSeq(hourZhi) {
	return (TABLES.xinFaSeq || {})[hourZhi] || [];
}

export function calcLiuqin(input) {
	const { pillars, gender, lunarMonth } = input || {};
	if (!Array.isArray(pillars) || pillars.length < 4 || pillars.some((x) => !x || `${x}`.length < 2)) return null;
	return {
		school: 'liuqin', input,
		shengxiao: calcShengxiao({ pillars, gender, lunarMonth }),
		xingshi: calcQiziXingshi({ pillars }),
		xuanji: input.askHourZhi && input.env ? calcXuanjiDongyao(input) : null,
		meta: LIUQIN_META,
	};
}

export default calcLiuqin;
