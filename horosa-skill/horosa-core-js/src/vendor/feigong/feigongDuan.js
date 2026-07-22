// 飞宫小奇门 · 论断层 —— 主客定位 / 宫面聚合 / 门星神论断取文 / 五行生克·旺相休囚 / 冲合。
// 纯函数,零 UI 零接线。
import {
	GAN_WUXING, ZHI_WUXING, GUA_WUXING, BA_MEN_WUXING,
	WUXING_SHENG, WUXING_KE, WANG_XIANG_TABLE,
	LIU_HE, LIU_CHONG, GONG_ZHI, GONG_GUA,
	MEN_DUAN, SHEN_DUAN, XING_DUAN,
	YUAN_SHEN_JI_XIONG, BA_MEN_JI_XIONG, TIAN_XING_ALIAS, TUI_DUAN, HEKUI_KOUJING,
} from './feigongConst.js';

// ── 五行工具 ───────────────────────────────────────────
/** 取干/支/卦/门之五行 */
export function wuXingOf(x) {
	return GAN_WUXING[x] || ZHI_WUXING[x] || GUA_WUXING[x] || BA_MEN_WUXING[x] || null;
}
/**
 * subject 相对 me 之生克关系(推断四「以命宫为我」口径):
 * 生我 / 克我 / 我生 / 我克 / 比和。传入五行或可查五行之名。
 */
export function shengKeRel(subject, me) {
	const a = WUXING_SHENG[subject] ? subject : wuXingOf(subject);
	const b = WUXING_SHENG[me] ? me : wuXingOf(me);
	if (!a || !b) return null;
	if (a === b) return '比和';
	if (WUXING_SHENG[a] === b) return '生我';
	if (WUXING_KE[a] === b) return '克我';
	if (WUXING_SHENG[b] === a) return '我生';
	if (WUXING_KE[b] === a) return '我克';
	return null;
}
/** 推断四:吉星生我大吉/克我小吉;凶星生我小凶/克我大凶。 */
export function xingShenSunYi(jiXiong, rel) {
	const ji = /吉/.test(jiXiong || '');
	if (rel === '生我') return ji ? '大吉' : '小凶';
	if (rel === '克我') return ji ? '小吉' : '大凶';
	return null;
}
/** 五行旺相休囚死:elem 于 season(春/夏/秋/冬/四季末)之状态 */
export function wangXiang(elem, season) {
	const row = WANG_XIANG_TABLE[elem];
	if (!row) return null;
	const hit = Object.keys(row).find((state) => row[state] === season);
	return hit || null;
}

// ── 冲合 ───────────────────────────────────────────────
export function liuHeOf(zhi) { return LIU_HE[zhi] || null; }
export function liuChongOf(zhi) { return LIU_CHONG[zhi] || null; }

// ── 论断取文 ───────────────────────────────────────────
export function menDuan(men) {
	if (!MEN_DUAN[men]) return null;
	return { men, jiXiong: BA_MEN_JI_XIONG[men], ...MEN_DUAN[men] };
}
export function shenDuan(shen) {
	if (!SHEN_DUAN[shen]) return null;
	return { shen, jiXiong: YUAN_SHEN_JI_XIONG[shen], text: SHEN_DUAN[shen] };
}
// 十二天星取文;koujing='zheng'(正传,默认)/'yi'(异文):仅 收/开 之河魁·贵人归属两说互换,余星不变。
export function xingDuan(xing, koujing = 'zheng') {
	if (!XING_DUAN[xing]) return null;
	const ko = HEKUI_KOUJING[koujing] || HEKUI_KOUJING.zheng;
	const alias = (ko.alias && ko.alias[xing]) || TIAN_XING_ALIAS[xing] || null;
	const text = (ko.duan && ko.duan[xing]) || XING_DUAN[xing];
	return { xing, alias, text };
}
export function tuiDuanText(n) {
	return TUI_DUAN[n - 1] || null; // n = 1..12
}

// ── 主客(推断一:日干之宫为主,日支之宫为客) ─────────────
export function zhuKe(ju) {
	if (!ju) return null;
	// 注:日干飞入中宫时 zhuGong 保留 '中' 是古籍实例的正确状态(壬辰日「丁壬相冲千里之外,故有动象」),
	// 与命宫「值五宫看同五行」不同法——主客不作同五行重定向(feigongGolden 金标⑥ 求财局锚定)。
	return {
		zhuGong: ju.dayGanGong != null ? ju.dayGanGong : null,
		keGong: ju.dayZhiGong != null ? ju.dayZhiGong : null,
		text: TUI_DUAN[0],
	};
}

// ── 应期(中宫二干定时·丁壬驿马·其余冲;取日支之六冲六合位为缓急) ──
export function yingQi(ju) {
	if (!ju || !ju.tianGan || !Array.isArray(ju.tianGan.zhongGong)) return null;
	const zg = ju.tianGan.zhongGong; // 中宫两干(五合对)
	const has = (g) => zg.indexOf(g) >= 0;
	let shi; let note;
	if (has('戊') && has('癸')) { shi = '定时'; note = '中宫戊癸合,为定时,主缓成、合则事就'; }
	else if (has('丁') && has('壬')) { shi = '驿马'; note = '中宫丁壬,为驿马,主动、应于千里之外'; }
	else { shi = '冲'; note = '中宫二干余合化对,主冲动,取地支冲位应期'; }
	const dayZhi = ju.dayZhi || null;
	const chongZhi = dayZhi ? liuChongOf(dayZhi) : null;
	const heZhi = dayZhi ? liuHeOf(dayZhi) : null;
	return {
		zhongGong: zg.slice(), shi, dingShi: shi === '定时', yiMa: shi === '驿马',
		dayZhi, chongZhi, heZhi,
		note: `${note}${dayZhi ? `;日支${dayZhi},冲位${chongZhi || '—'}(冲事不吉/凶事减凶)、合位${heZhi || '—'}(合则缓、主成)` : ''}`,
	};
}

// ── 事项路由(求财看金匮/官非看白虎/盗贼失物看玄武/男看危天罡/女看河魁,随口径) ──
export function shiXiangKey(askEvent, settings = {}) {
	const s = String(askEvent || '');
	if (!s.trim()) return null;
	const nvXing = settings.heKuiKoujing === 'yi' ? '开' : '收'; // 女事看河魁:正传在收、异文在开
	if (/财|钱|买卖|生意|求利|经营/.test(s)) return { key: 'wealth', shen: '金匮', hint: '求财看金匮' };
	if (/官非|官司|词讼|诉讼|讼事|打官司/.test(s)) return { key: 'lawsuit', shen: '白虎', hint: '官非看白虎' };
	if (/盗|贼|失物|遗失|丢失|寻物/.test(s)) return { key: 'thief', shen: '玄武', hint: '盗贼失物看玄武' };
	if (/女|妻|母|婚|嫁|娶|姻|产/.test(s)) return { key: 'female', xing: nvXing, hint: `女人之事看${nvXing}(河魁)` };
	if (/男|夫|父|子嗣|功名/.test(s)) return { key: 'male', xing: '危', hint: '男人之事看危(天罡男星)' };
	return null;
}

// ── 宫面聚合:一宫之卦/干/门 + 所辖地支之原神天星 ─────────
export function gongDuan(ju, gong) {
	if (!ju || !GONG_ZHI[gong]) return null;
	const zhis = GONG_ZHI[gong].map((z) => ({
		zhi: z,
		shen: ju.yuanShen[z],
		xing: ju.tianXing[z],
		shenDuan: shenDuan(ju.yuanShen[z]),
		xingDuan: xingDuan(ju.tianXing[z]),
		he: liuHeOf(z),
		chong: liuChongOf(z),
	}));
	const men = ju.baMen.gongMen[gong] || null;
	return {
		gong,
		gua: GONG_GUA[gong],
		wuxing: wuXingOf(GONG_GUA[gong]),
		gan: ju.tianGan.gongGan[gong] ? ju.tianGan.gongGan[gong].slice() : [],
		men,
		menDuan: men ? menDuan(men) : null,
		zhis,
	};
}
