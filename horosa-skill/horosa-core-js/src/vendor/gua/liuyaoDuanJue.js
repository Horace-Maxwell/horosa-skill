// 六爻断诀判定层:通例判定(暗动/绝处逢生/合处逢冲/随官入墓/助鬼伤身/无鬼)、碎金赋多动爻作用链、
// 飞伏生克与伏神可用、三层环境(太岁岁破/月建月破/日建日破)、承刚/穿害推导、真空口诀、灭没卦、
// 余气旺衰、金锁八要素(德合刑冲克旺墓空)、新派量化打分、长生鬼沐浴鬼、怪爻。
// 全部输出结构真值+古籍断义标签,吉凶综合交 AI。规则忠于《断易天机》《增删卜易》通行口径。
import { DIZHI, ZHI_WUXING, ZHI_YINYANG, WUXING_SHENG, WUXING_KE, LIUCHONG, LIUHE, HAI, shengKe, isXing,
	CHANGSHENG_START } from './LiuYaoConst.js';
import { changshengOf, wangShuaiByMonth } from './LiuYaoEngine.js';

// 六亲生克链(父母生兄弟…;父母克子孙…)
export const LIUQIN_SHENG = { 父母: '兄弟', 兄弟: '子孙', 子孙: '妻财', 妻财: '官鬼', 官鬼: '父母' };
export const LIUQIN_KE = { 父母: '子孙', 子孙: '官鬼', 官鬼: '兄弟', 兄弟: '妻财', 妻财: '父母' };
// 泄气链(《断易天机》论泄气:财动泄子孙气…即「被我生者动,泄我之气」的反查)
export const LIUQIN_XIE = { 妻财: '子孙', 子孙: '兄弟', 兄弟: '父母', 父母: '官鬼', 官鬼: '妻财' }; // 键动 → 泄值之气
// 六合化五行(午未合日月,今注以'日月'标注)
export const LIUHE_HUA = { 子丑: '土', 寅亥: '木', 卯戌: '火', 辰酉: '金', 巳申: '水', 午未: '日月' };
export function liuheHuaOf(a, b){
	if(!a || !b || LIUHE[a] !== b){ return null; }
	const key = Object.keys(LIUHE_HUA).find((k) => k.indexOf(a) >= 0 && k.indexOf(b) >= 0);
	return key ? LIUHE_HUA[key] : null;
}

// ── 三层环境:太岁/岁破/月建/月破/日建/日破 + 逐爻标注 ──
export function sanCengEnv(ctx){
	const c = ctx || {};
	return {
		taiSui: c.yearZhi || '', suiPo: c.yearZhi ? LIUCHONG[c.yearZhi] : '',
		yueJian: c.monthZhi || '', yuePo: c.monthZhi ? LIUCHONG[c.monthZhi] : '',
		riZhi: c.dayZhi || '', riPo: c.dayZhi ? LIUCHONG[c.dayZhi] : '',
	};
}
// ── 日月生克:5.4「月建、日辰对爻的作用(最重要的外力)」逐爻明细 ──
// 月日为卦外之天/君,单方面作用于爻:生扶/克制/冲(暗动·冲散·月破)/合/刑/值临/入墓。
// 铁律:爻不反作用于月日(故「爻克月日」不记为对月日之克)。墓库:金墓丑·木墓未·水土墓辰·火墓戌。
const RIYUE_MU = { 金: '丑', 木: '未', 水: '辰', 土: '辰', 火: '戌' };
function riYueRelOne(yaoZhi, yaoWx, srcZhi, isMonth){
	const tags = [];
	if(!srcZhi || !yaoZhi){ return { tags }; }
	const srcWx = ZHI_WUXING[srcZhi];
	const who = isMonth ? '月建' : '日辰';
	if(yaoZhi === srcZhi){ tags.push({ t: isMonth ? '临月建' : '临日建', tone: 'good', why: who + '临爻(力极旺)' }); }
	if(srcWx && yaoWx){
		if(srcWx === yaoWx){ tags.push({ t: '比和', tone: 'good', why: who + '比和(帮扶)' }); }
		else if(WUXING_SHENG[srcWx] === yaoWx){ tags.push({ t: '得生', tone: 'good', why: who + '生爻' }); }
		else if(WUXING_KE[srcWx] === yaoWx){ tags.push({ t: '受克', tone: 'bad', why: who + '克爻' }); }
		else if(WUXING_SHENG[yaoWx] === srcWx){ tags.push({ t: '泄气', tone: 'bad', why: '爻生' + who + '(泄气)' }); }
		// 爻克月日:月日免克,不记(铁律)
	}
	if(LIUCHONG[srcZhi] === yaoZhi){
		if(isMonth){ tags.push({ t: '月破', tone: 'bad', why: '月冲为月破' }); }
		else { tags.push({ t: '日冲', tone: 'warn', why: '日冲(旺爻暗动·衰空冲散)' }); }
	}
	if(LIUHE[srcZhi] === yaoZhi){ tags.push({ t: '合', tone: 'good', why: (isMonth ? '月' : '日') + '合起(绊住/助起)' }); }
	if(isXing(srcZhi, yaoZhi) && srcZhi !== yaoZhi){ tags.push({ t: '刑', tone: 'bad', why: (isMonth ? '月' : '日') + '刑爻' }); }
	if(RIYUE_MU[yaoWx] === srcZhi){ tags.push({ t: isMonth ? '入月墓' : '入日墓', tone: 'bad', why: '爻逢墓库入墓(暂无力,待冲开而应)' }); }
	return { tags };
}
// yaos: base.yaos(含 zhi/wuxing/liuqin);gans: 逐爻天干;ctx: { dayGan, dayZhi, monthGan, monthZhi }
export function riYueYinDong(yaos, gans, ctx){
	const c = ctx || {};
	const dayZhi = c.dayZhi || '', monthZhi = c.monthZhi || '';
	const perYao = (yaos || []).map((y, i) => ({
		pos: y.pos, gan: (gans && gans[i]) || '', zhi: y.zhi, wuxing: y.wuxing, liuqin: y.liuqin,
		day: riYueRelOne(y.zhi, y.wuxing, dayZhi, false),
		month: riYueRelOne(y.zhi, y.wuxing, monthZhi, true),
	}));
	return { dayGan: c.dayGan || '', dayZhi, monthGan: c.monthGan || '', monthZhi, perYao };
}

export function sanCengOnYaos(yaos, ctx){
	const env = sanCengEnv(ctx);
	const perYao = (yaos || []).map((y) => {
		const tags = [];
		if(env.taiSui && y.zhi === env.taiSui){ tags.push('临太岁'); }
		if(env.suiPo && y.zhi === env.suiPo){ tags.push('岁破'); }
		if(env.yueJian && y.zhi === env.yueJian){ tags.push('临月建'); }
		if(env.riZhi && y.zhi === env.riZhi){ tags.push('临日建'); }
		if(env.riPo && y.zhi === env.riPo){ tags.push('日破'); }
		return { pos: y.pos, tags };
	});
	return { env, perYao };
}

// ── 暗动/日破细分:六爻安静,静爻旺相被日辰冲=暗动;休囚死被日冲=日破(冲散) ──
export function anDongOf(y){
	if(!y || y.moving || !y.dayRel || !y.dayRel.chong){ return ''; }
	const strong = (y.wangShuai === '旺' || y.wangShuai === '相');
	return strong ? '暗动' : '冲散(日破)';
}

// ── 绝处逢生:爻五行绝于日支,而卦中动爻生之(用爻遇之凶转吉;鬼爻遇之病复作) ──
export function jueChuFengSheng(yaos, movingSet, ctx, tuMode){
	const c = ctx || {}, moving = movingSet || new Set();
	const out = [];
	(yaos || []).forEach((y) => {
		if(!c.dayZhi || changshengOf(y.wuxing, c.dayZhi, tuMode || 'water') !== '绝'){ return; }
		const savers = (yaos || []).filter((o) => moving.has(o.pos) && o.pos !== y.pos && WUXING_SHENG[o.wuxing] === y.wuxing).map((o) => o.pos);
		if(savers.length){ out.push({ pos: y.pos, liuqin: y.liuqin, savers, duan: '绝处逢生:先难后济' }); }
	});
	return out;
}

// ── 合处逢冲:爻与日辰(或爻间)成六合,又被日辰冲/害 → 事将成而复散;「吉神合处不可冲,凶神合处喜逢冲」 ──
export function heChuFengChong(yaos, ctx){
	const c = ctx || {};
	if(!c.dayZhi){ return []; }
	const out = [];
	(yaos || []).forEach((y) => {
		const heWithDay = LIUHE[y.zhi] === c.dayZhi;
		const heInGua = (yaos || []).some((o) => o.pos !== y.pos && LIUHE[o.zhi] === y.zhi);
		const chong = LIUCHONG[c.dayZhi] === y.zhi;
		const hai = HAI[c.dayZhi] === y.zhi;
		if((heWithDay || heInGua) && (chong || hai)){
			out.push({ pos: y.pos, liuqin: y.liuqin, by: chong ? '冲' : '害', duan: '合处逢冲:将成而散;久病逢冲死、近病逢冲生' });
		}
	});
	return out;
}

// ── 随官入墓(三式)+杀墓:①世身临鬼入墓 ②世临鬼入墓 ③本命爻临鬼入墓;墓=该爻五行墓于日支;杀墓日=丁未/戊戌 ──
export function suiGuanRuMu(yaos, opts){
	const o = opts || {};
	const dayZhi = o.dayZhi, tuMode = o.tuMode || 'water';
	if(!dayZhi){ return null; }
	const hits = [];
	const check = (pos, kind) => {
		if(!pos){ return; }
		const y = (yaos || [])[pos - 1];
		if(!y || y.liuqin !== '官鬼'){ return; }
		if(changshengOf(y.wuxing, dayZhi, tuMode) === '墓'){ hits.push({ kind, pos, zhi: y.zhi }); }
	};
	check(o.shiShenPos, '身随鬼入墓');
	check(o.shiPos, '世随鬼入墓');
	if(o.benmingZhi){
		(yaos || []).forEach((y) => {
			if(y.liuqin === '官鬼' && y.zhi === o.benmingZhi && changshengOf(y.wuxing, dayZhi, tuMode) === '墓'){
				hits.push({ kind: '命随鬼入墓', pos: y.pos, zhi: y.zhi });
			}
		});
	}
	const shaMu = (o.dayGan && dayZhi && ((o.dayGan === '丁' && dayZhi === '未') || (o.dayGan === '戊' && dayZhi === '戌')));
	return hits.length ? { hits, shaMu, duan: shaMu ? '入杀墓(丁未/戊戌):能入不能出,尤凶' : '随鬼入墓,主昏滞凶危' } : null;
}

// ── 助鬼伤身:妻财发动生官鬼,官鬼克世(或克卦身)。例外:子孙与财同动,反成子→财→鬼接续相生,不作解救论 ──
export function zhuGuiShangShen(yaos, movingSet, shiPos, guaShenZhi){
	const moving = movingSet || new Set();
	const caiMoving = (yaos || []).filter((y) => moving.has(y.pos) && y.liuqin === '妻财');
	if(!caiMoving.length){ return null; }
	const shiY = shiPos ? (yaos || [])[shiPos - 1] : null;
	const guiYaos = (yaos || []).filter((y) => y.liuqin === '官鬼');
	if(!guiYaos.length){ return null; }
	const keShi = shiY && guiYaos.some((g) => WUXING_KE[g.wuxing] === shiY.wuxing);
	const keShen = guaShenZhi && guiYaos.some((g) => WUXING_KE[g.wuxing] === ZHI_WUXING[guaShenZhi]);
	if(!keShi && !keShen){ return null; }
	const ziAlsoMoving = (yaos || []).some((y) => moving.has(y.pos) && y.liuqin === '子孙');
	return {
		caiPos: caiMoving.map((y) => y.pos), target: keShi ? '世' : '卦身',
		ziAlsoMoving,
		duan: ziAlsoMoving ? '子财同动:子生财、财生鬼,接续相生,不作制鬼解救论' : '助鬼伤身:财动生鬼克世(身),凶',
	};
}

// ── 无鬼无气(天玄赋通例):卦中六爻无官鬼 ──
export function wuGuiOf(yaos){
	const has = (yaos || []).some((y) => y.liuqin === '官鬼');
	return has ? null : { duan: '无鬼无气:卦无官鬼,谋事无主;占产/出行/行人/田蚕反吉' };
}

// ── 碎金赋多动爻作用链(对用神):连续相生/原神被克/连续相克/忌神受制/贪生忘克/贪合忘克 ──
export function suiJinFuChain(yaos, movingSet, yongLiuqin, ctx){
	const moving = movingSet || new Set();
	const movers = (yaos || []).filter((y) => moving.has(y.pos) && ['父母', '兄弟', '子孙', '妻财', '官鬼'].indexOf(y.liuqin) >= 0);
	if(!movers.length || !yongLiuqin || !LIUQIN_SHENG[yongLiuqin]){ return []; }
	const c = ctx || {};
	const out = [];
	const movingLiuqin = new Set(movers.map((m) => m.liuqin));
	movers.forEach((m) => {
		if(LIUQIN_SHENG[m.liuqin] === yongLiuqin){ // 原神动生用
			const chain = { kind: '原神动生用', from: m.pos, liuqin: m.liuqin, notes: [] };
			const shengYuan = Object.keys(LIUQIN_SHENG).find((k) => LIUQIN_SHENG[k] === m.liuqin); // 生原神者
			const keYuan = Object.keys(LIUQIN_KE).find((k) => LIUQIN_KE[k] === m.liuqin);           // 克原神者
			if(shengYuan && movingLiuqin.has(shengYuan)){ chain.notes.push('生原神者同动:接续相生,生力更大'); }
			if(keYuan && movingLiuqin.has(keYuan)){ chain.notes.push('克原神者同动:原神被克,生用无力'); }
			out.push(chain);
		}
		if(LIUQIN_KE[m.liuqin] === yongLiuqin){ // 忌神动克用
			const chain = { kind: '忌神动克用', from: m.pos, liuqin: m.liuqin, notes: [] };
			if(movingLiuqin.has(Object.keys(LIUQIN_SHENG).find((k) => LIUQIN_SHENG[k] === m.liuqin))){ chain.notes.push('生忌神者同动:接续相克,克力更大'); }
			if(movingLiuqin.has(Object.keys(LIUQIN_KE).find((k) => LIUQIN_KE[k] === m.liuqin))){ chain.notes.push('克忌神者同动:忌神受制,克用无力'); }
			if(movingLiuqin.has(LIUQIN_SHENG[m.liuqin])){ chain.notes.push('忌神所生者同动:贪生忘克,反成接续生用'); }
			const heTarget = LIUHE[m.zhi];
			const heByYao = (yaos || []).some((o) => moving.has(o.pos) && o.pos !== m.pos && o.zhi === heTarget);
			const heByDay = c.dayZhi === heTarget;
			if(heByYao || heByDay){ chain.notes.push(`贪合忘克(${heByDay ? '日辰' : '动爻'}合住忌神)`); }
			out.push(chain);
		}
	});
	return out;
}

// ── 飞伏生克四断 + 伏神可用判据 ──
// fly:{zhi,wuxing}(本卦该位之爻=飞) fu:{zhi,wuxing}(本宫首卦同位=伏)
export function feiFuShengKe(fly, fu){
	if(!fly || !fu || !fly.wuxing || !fu.wuxing){ return null; }
	const sk = shengKe(fly.wuxing, fu.wuxing); // 飞 对 伏
	if(sk === '生'){ return { rel: '飞来生伏', duan: '伏得长生,可出' }; }
	if(sk === '泄'){ return { rel: '伏去生飞', duan: '泄气,伏神力减' }; }
	if(sk === '克'){ return { rel: '飞来克伏', duan: '伏受制,不宁;须日月生扶引出' }; }
	if(sk === '耗'){ return { rel: '伏去克飞', duan: '出暴,伏神可自出' }; }
	return { rel: '飞伏比和', duan: '比和有助' };
}
// 伏神可用:伏旺相/长生帝旺临官、或伏克飞、或飞生伏、或飞衰弱(旬空/休囚死)→可用;伏空破墓绝且飞旺克伏→不可用
export function fushenUsable(fuYao, flyYao, ctx, tuMode){
	if(!fuYao || !flyYao){ return null; }
	const c = ctx || {};
	const reasons = [];
	let score = 0;
	const fuWang = wangShuaiByMonth(fuYao.wuxing, c.monthZhi);
	if(fuWang === '旺' || fuWang === '相'){ score += 2; reasons.push(`伏神${fuWang}`); }
	const cs = c.dayZhi ? changshengOf(fuYao.wuxing, c.dayZhi, tuMode || 'water') : '';
	if(cs === '长生' || cs === '帝旺' || cs === '临官'){ score += 1; reasons.push(`伏临${cs}`); }
	const rel = feiFuShengKe({ wuxing: flyYao.wuxing, zhi: flyYao.zhi }, { wuxing: fuYao.wuxing, zhi: fuYao.zhi });
	if(rel && rel.rel === '飞来生伏'){ score += 2; reasons.push('飞生伏'); }
	if(rel && rel.rel === '伏去克飞'){ score += 2; reasons.push('伏克飞'); }
	if(rel && rel.rel === '飞来克伏'){ score -= 2; reasons.push('飞克伏'); }
	const flyWeak = (flyYao.xunKong || flyYao.wangShuai === '休' || flyYao.wangShuai === '囚' || flyYao.wangShuai === '死');
	if(flyWeak){ score += 1; reasons.push('飞神衰弱(壳薄易出)'); }
	const fuBroken = (fuYao.xunKong || fuYao.yuePo || cs === '墓' || cs === '绝');
	if(fuBroken){ score -= 2; reasons.push('伏神空破墓绝'); }
	return { usable: score >= 1, score, reasons, rel: rel ? rel.rel : '' };
}

// ── 承刚:相邻两爻,阴爻居阳爻之下,该阴爻为「承刚」 ──
export function chengGangOf(yaos){
	const out = [];
	for(let i = 0; i < 5; i++){
		const a = (yaos || [])[i], b = (yaos || [])[i + 1];
		if(a && b && a.yin && !b.yin){ out.push(a.pos); }
	}
	return out;
}

// ── 穿害推导(害=破合):b 害 a ⇔ b 冲掉 a 的六合之神。返回推导三元组供展示 ──
export function chuanHaiExplain(aZhi){
	if(!aZhi || !LIUHE[aZhi]){ return null; }
	const he = LIUHE[aZhi];
	return { zhi: aZhi, he, chuan: LIUCHONG[he] }; // chuan 即害 aZhi 之支
}

// ── 真空口诀(《断易天机》):春土夏金秋木、三冬逢火,旬空临之为真空;日辰生助不为空 ──
const ZHENKONG_WX = { 春: '土', 夏: '金', 秋: '木', 冬: '火' };
const SEASON_BY_MONTH = { 寅: '春', 卯: '春', 辰: '春', 巳: '夏', 午: '夏', 未: '夏', 申: '秋', 酉: '秋', 戌: '秋', 亥: '冬', 子: '冬', 丑: '冬' };
export function seasonOfMonth(monthZhi){ return SEASON_BY_MONTH[monthZhi] || ''; }
export function zhenKongJueOf(yaoWx, monthZhi, dayRelSheng){
	const season = seasonOfMonth(monthZhi);
	if(!season){ return null; }
	const hit = ZHENKONG_WX[season] === yaoWx && !dayRelSheng;
	return { season, jueWx: ZHENKONG_WX[season], hit, jue: '春土夏金秋见木,三冬逢火是真空;日辰生助不为空' };
}

// ── 四卦灭例/没例:灭=春蒙夏蛊秋剥冬旅;没=春需夏观秋节冬临(诸事无吉神扶助则凶) ──
const MIE = { 春: '山水蒙', 夏: '山风蛊', 秋: '山地剥', 冬: '火山旅' };
const MO = { 春: '水天需', 夏: '风地观', 秋: '水泽节', 冬: '地泽临' };
export function mieMoOf(guaName, monthZhi){
	const season = seasonOfMonth(monthZhi);
	if(!season || !guaName){ return null; }
	if(MIE[season] === guaName){ return { kind: '灭', season, duan: '四卦灭例:诸事不吉' }; }
	if(MO[season] === guaName){ return { kind: '没', season, duan: '四卦没例:无吉神扶助主凶' }; }
	return null;
}

// ── 生克力量比较(反神类):旺相克得休囚,休囚克不得旺相;动克得静,静克不得动 ──
export function powerCanKe(attacker, defender){
	if(!attacker || !defender){ return null; }
	const aStrong = attacker.moving || attacker.wangShuai === '旺' || attacker.wangShuai === '相';
	const dStrong = defender.wangShuai === '旺' || defender.wangShuai === '相';
	if(!attacker.moving && !aStrong){ return { can: false, why: '静而休囚,克不得' }; }
	if(!attacker.moving && dStrong){ return { can: false, why: '静爻克不得旺相爻' }; }
	return { can: true, why: attacker.moving ? '动爻克得安静爻' : '旺相爻克得休囚爻' };
}

// ── 余气(四墓月):辰月木、未月火、戌月金、丑月水,本季余气之行加强(不改主状态,附标) ──
const YUQI = { 辰: '木', 未: '火', 戌: '金', 丑: '水' };
export function yuqiOf(monthZhi){ return YUQI[monthZhi] || ''; }
export function wangShuaiWithYuqi(yaoWx, monthZhi, on){
	const state = wangShuaiByMonth(yaoWx, monthZhi);
	const strongByYuqi = !!on && YUQI[monthZhi] === yaoWx;
	return { state, strongByYuqi };
}

// ── 金锁玄关八要素(德合刑冲克旺墓空):对某爻逐项判读 ──
export function jinSuoBaYao(y, ctx, tuMode, deZhis){
	if(!y){ return null; }
	const c = ctx || {};
	const cs = c.dayZhi ? changshengOf(y.wuxing, c.dayZhi, tuMode || 'water') : '';
	return [
		{ k: '德', on: !!(deZhis && deZhis.indexOf(y.zhi) >= 0), note: '天月德临之,凶中有救' },
		{ k: '合', on: !!(c.dayZhi && LIUHE[y.zhi] === c.dayZhi), note: '合主成、绊' },
		{ k: '刑', on: !!(c.dayZhi && isXing(c.dayZhi, y.zhi)), note: '刑主伤、讼' },
		{ k: '冲', on: !!(y.dayRel && y.dayRel.chong) || !!y.yuePo, note: '冲主动、散' },
		{ k: '克', on: !!(y.dayRel && y.dayRel.ke), note: '受日克,伤' },
		{ k: '旺', on: y.wangShuai === '旺' || y.wangShuai === '相', note: '旺相有气' },
		{ k: '墓', on: cs === '墓', note: '入墓主藏、滞' },
		{ k: '空', on: !!y.xunKong, note: y.voidKind === '真空' ? '真空到底空' : '空待填实' },
	];
}

// ── 新派量化打分(代表性框架):月令基础分+日辰加减+动变加减 → 五档 ──
export function xinpaiScoreOf(y, dongbianMove){
	if(!y){ return null; }
	let score = ({ 旺: 2, 相: 1, 休: 0, 囚: -1, 死: -2 })[y.wangShuai] != null ? ({ 旺: 2, 相: 1, 休: 0, 囚: -1, 死: -2 })[y.wangShuai] : 0;
	const parts = [`月令${y.wangShuai || '—'}`];
	if(y.dayRel){
		if(y.dayRel.sheng || y.dayRel.same){ score += 1; parts.push('日辰生扶+1'); }
		if(y.dayRel.he){ score += 1; parts.push('日辰合+1'); }
		if(y.dayRel.ke){ score -= 1; parts.push('日辰克-1'); }
		if(y.dayRel.chong){ score -= 1; parts.push('日辰冲-1'); }
		if(y.dayRel.xing){ score -= 1; parts.push('日辰刑-1'); }
	}
	if(y.yuePo){ score -= 2; parts.push('月破-2'); }
	if(y.xunKong){ score -= 1; parts.push('旬空-1'); }
	if(dongbianMove){
		if(dongbianMove.huiTou && dongbianMove.huiTou.sheng){ score += 1; parts.push('化回头生+1'); }
		if(dongbianMove.jinShen){ score += 1; parts.push('化进神+1'); }
		if(dongbianMove.huiTou && dongbianMove.huiTou.ke){ score -= 2; parts.push('化回头克-2'); }
		if(dongbianMove.tuiShen){ score -= 1; parts.push('化退神-1'); }
		if(dongbianMove.huaKong || dongbianMove.huaPo || dongbianMove.huaMu || dongbianMove.huaJue){ score -= 1; parts.push('化空破墓绝-1'); }
	}
	const grade = score >= 3 ? '旺' : score >= 1 ? '相' : score >= -1 ? '休' : score >= -3 ? '囚' : '死';
	return { score, grade, parts, note: '新派旺衰量化为代表性框架,各家细则不一' };
}

// ── 长生鬼/沐浴鬼(占病):鬼五行长生之日「男怕长生」;长生+1 位=沐浴,「女怕沐浴」 ──
export function changShengGuiOf(guiWx, dayZhi){
	if(!guiWx || !dayZhi){ return null; }
	const start = CHANGSHENG_START[guiWx];
	if(!start){ return null; }
	const s = DIZHI.indexOf(start);
	const muYu = DIZHI[(s + 1) % 12];
	if(dayZhi === start){ return { kind: '长生鬼', duan: '男怕长生日得病' }; }
	if(dayZhi === muYu){ return { kind: '沐浴鬼', duan: '女怕沐浴日得病' }; }
	return null;
}

// ── 怪爻(占怪异):季月(辰戌丑未月)怪在初/上爻,仲月(子午卯酉)二五爻,孟月(寅申巳亥)三四爻;动为怪、静无 ──
export function guaiYaoOf(monthZhi){
	if('辰戌丑未'.indexOf(monthZhi) >= 0){ return [1, 6]; }
	if('子午卯酉'.indexOf(monthZhi) >= 0){ return [2, 5]; }
	if('寅申巳亥'.indexOf(monthZhi) >= 0){ return [3, 4]; }
	return [];
}

// ── 进退神土路径开关:'chain'(丑辰未戌首尾连环,含戌→丑)/'break'(戌丑断开,土至戌为止) ──
export function jinShenBy(benZhi, bianZhi, mode){
	const JIN = { 寅: '卯', 巳: '午', 申: '酉', 亥: '子', 丑: '辰', 辰: '未', 未: '戌', 戌: '丑' };
	if(mode === 'break' && benZhi === '戌'){ return false; }
	return JIN[benZhi] === bianZhi;
}
export function tuiShenBy(benZhi, bianZhi, mode){
	const TUI = { 卯: '寅', 午: '巳', 酉: '申', 子: '亥', 戌: '未', 未: '辰', 辰: '丑', 丑: '戌' };
	if(mode === 'break' && benZhi === '丑'){ return false; }
	return TUI[benZhi] === bianZhi;
}
