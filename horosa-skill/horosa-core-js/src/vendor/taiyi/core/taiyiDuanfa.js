// 太乙断法纯派生集:主客胜负(§11.4/§15.2)/九州分野(§6.3/§27.2)/太岁古名(§26.1)/诸神之算(§28)。
// 全部前端纯函数,据 kintaiyi pan 现成字段派生,零触碰后端立成表 golden。算法/表移植自文档「古法复原」引擎。
import { shuliLabel, palaceYinYang } from './taiyiShuli.js';

// —— 太乙九宫:门/九州/绝气/阴阳(§6.3,文档 TAIYI_GONG_INFO,键=太乙宫数) ——
export const TAIYI_GONG_INFO = {
	1: { gua: '乾', men: '天门', zhou: '冀州', qi: '绝阳', yy: '阳' },
	2: { gua: '离', men: '火门', zhou: '荆州', qi: '易气', yy: '阴' },
	3: { gua: '艮', men: '鬼门', zhou: '青州', qi: '和', yy: '阳' },
	4: { gua: '震', men: '日门', zhou: '徐州', qi: '绝气', yy: '阳' },
	5: { gua: '中', men: '中枢', zhou: '中原', qi: '枢纽', yy: '—' },
	6: { gua: '兑', men: '月门', zhou: '雍州', qi: '绝气', yy: '阴' },
	7: { gua: '坤', men: '人门', zhou: '益州', qi: '和', yy: '阴' },
	8: { gua: '坎', men: '水门', zhou: '兖州', qi: '易气', yy: '阴' },
	9: { gua: '巽', men: '风门', zhou: '扬州', qi: '绝阴', yy: '阳' },
};
// 分野主象(气→水旱疾疫,§27.2 通则)
const QI_OMEN = { 绝阳: '阳衰、君弱、旱厄', 绝阴: '阴极、水厄、阴疫', 绝气: '气塞、兵戈、阻滞', 易气: '变易、疾疫流行', 和: '和平、岁稔', 枢纽: '中枢、待时' };

// —— 十六神逐神含义·主事(§8.2,落点→主事) ——
export const SHEN_MEANING = {
	子: '动摇·言语', 丑: '施恩·育物', 艮: '和集·成就', 寅: '运用·主宰', 卯: '发挥·发展', 辰: '危会·兵戈',
	巽: '申命·号令', 巳: '毁拆·破废', 午: '光明·威烈', 未: '阴私', 坤: '刑罚', 申: '传送·迁移',
	酉: '更易·肃杀', 戌: '危期·兵丧', 乾: '命令', 亥: '计谋·废弃',
};
export function shenMeaning(luodian){ return SHEN_MEANING[luodian] || ''; }

// —— 三元(§3.1):太乙五元六纪之纪 → 上/中/下元(一四纪上、二五纪中、三六纪下) ——
export function computeSanyuan(pan){
	const s = pan && pan.jiyuan ? String(pan.jiyuan) : '';
	const m = s.match(/第\s*([一二三四五六1-6])\s*[纪紀]/);
	if(!m){ return ''; }
	const map = { 一: 1, 二: 2, 三: 3, 四: 4, 五: 5, 六: 6 };
	const ji = map[m[1]] || parseInt(m[1], 10);
	if(!ji){ return ''; }
	return ['上元', '中元', '下元'][(ji - 1) % 3];
}

// —— 太岁古名:岁阳(配干)/岁阴(配支)(§26.1) ——
const SUIYANG = { 甲: '阏逢', 乙: '旃蒙', 丙: '柔兆', 丁: '强圉', 戊: '著雍', 己: '屠维', 庚: '上章', 辛: '重光', 壬: '玄黓', 癸: '昭阳' };
const SUIYIN = { 寅: '摄提格', 卯: '单阏', 辰: '执徐', 巳: '大荒落', 午: '敦牂', 未: '协洽', 申: '涒滩', 酉: '作噩', 戌: '阉茂', 亥: '大渊献', 子: '困敦', 丑: '赤奋若' };

export function computeTaisuiAlias(pan){
	const gz = pan && pan.ganzhi && pan.ganzhi.year ? String(pan.ganzhi.year) : '';
	if(gz.length < 2){ return ''; }
	const ya = SUIYANG[gz.charAt(0)] || '';
	const yi = SUIYIN[gz.charAt(1)] || '';
	return (ya && yi) ? ya + yi : '';
}

// —— 诸神之算:通用几何法 _suan_from(§10.1/§28) ——
const ZHENG_POS = ['子', '艮', '卯', '巽', '午', '坤', '酉', '乾'];        // 八正宫顺行环
const ZHENG_VAL = { 子: 8, 艮: 3, 卯: 4, 巽: 9, 午: 2, 坤: 7, 酉: 6, 乾: 1 }; // 各正宫太乙宫数
const RING16 = '子丑艮寅卯辰巽巳午未坤申酉戌乾亥'.split('');
const NUM2ZHENGPOS = { 1: '乾', 2: '午', 3: '艮', 4: '卯', 6: '酉', 7: '坤', 8: '子', 9: '巽' }; // 太乙宫数→正宫落点

// 自 startPos(正宫或间神落点)起,顺行累加八正宫太乙宫数,至太乙前一宫止。间神起点取后一正宫且 base=1。
// jianChen=false 时关闭「间辰加一」(流派开关:客算间辰加一 有/无),间神起点 base 仍取后一正宫但不+1。
export function suanFrom(startPos, taiyiZhengPos, jianChen){
	if(!startPos || !taiyiZhengPos){ return null; }
	const useJianChen = jianChen === undefined ? true : !!jianChen;
	const ti = ZHENG_POS.indexOf(taiyiZhengPos);
	if(ti < 0){ return null; }
	let base = 0, si;
	if(ZHENG_POS.indexOf(startPos) >= 0){
		si = ZHENG_POS.indexOf(startPos);
	}else{
		let i = RING16.indexOf(startPos);
		if(i < 0){ return null; }
		while(ZHENG_POS.indexOf(RING16[i]) < 0){ i = (i + 1) % 16; }
		si = ZHENG_POS.indexOf(RING16[i]);
		base = useJianChen ? 1 : 0;
	}
	let total = base, k = si;
	for(let n = 0; n < 8; n++){
		total += ZHENG_VAL[ZHENG_POS[k]];
		const nxt = (k + 1) % 8;
		if(nxt === ti){ break; }
		k = nxt;
	}
	return total;
}

// 君基算/臣基算/民基算/五福算/始击算(§28)。每算带数理标签。
export function computeShenSuan(pan){
	if(!pan || !pan.taiyiPalace){ return null; }
	const t = pan.taiyiPalace; // 太乙正宫落点
	const yy = palaceYinYang(t);
	const wufuPos = NUM2ZHENGPOS[Number(pan.wufuNum)] || '';
	const mk = (pos) => { const v = suanFrom(pos, t); return v == null ? null : { value: v, tags: shuliLabel(v, yy) }; };
	const out = {};
	if(pan.kingbase){ out['君基算'] = mk(pan.kingbase); }
	if(pan.officerbase){ out['臣基算'] = mk(pan.officerbase); }
	if(pan.pplbase){ out['民基算'] = mk(pan.pplbase); }
	if(wufuPos){ out['五福算'] = mk(wufuPos); }
	if(pan.sf){ out['始击算'] = mk(pan.sf); }
	return out;
}

// —— 九州分野占(§27.2):太乙/始击所临宫→州·气·主象 ——
function gongOfPos(pos){
	// 正宫落点→太乙宫数(经 NUM2ZHENGPOS 反查)
	for(const k of Object.keys(NUM2ZHENGPOS)){ if(NUM2ZHENGPOS[k] === pos){ return Number(k); } }
	return null;
}
export function computeFenye(pan){
	if(!pan){ return null; }
	const out = {};
	const tNum = Number(pan.taiyiNum) || gongOfPos(pan.taiyiPalace);
	if(tNum && TAIYI_GONG_INFO[tNum]){ const g = TAIYI_GONG_INFO[tNum]; out.taiyi = { gong: tNum, gua: g.gua, men: g.men, zhou: g.zhou, qi: g.qi, omen: QI_OMEN[g.qi] || '' }; }
	const sjNum = gongOfPos(pan.sf); // 始击在正宫才有分野;间神则无
	if(sjNum && TAIYI_GONG_INFO[sjNum]){ const g = TAIYI_GONG_INFO[sjNum]; out.shiji = { gong: sjNum, gua: g.gua, men: g.men, zhou: g.zhou, qi: g.qi, omen: QI_OMEN[g.qi] || '' }; }
	return out;
}

// —— 八门吉凶(§12.1 玄女经断辞) ——
export const BAMEN_JIXIONG = { 开: '大吉', 開: '大吉', 休: '大吉', 生: '大吉', 景: '小吉', 惊: '小凶', 驚: '小凶', 死: '大凶', 伤: '大凶', 傷: '大凶', 杜: '大凶' };
// 据 pan.eightDoorDuty(八门值事)取当前值使门 + 吉凶
export function activeDoorJixiong(pan){
	const str = pan && pan.eightDoorDuty ? String(pan.eightDoorDuty) : '';
	for(const d of ['开', '開', '休', '生', '伤', '傷', '杜', '景', '死', '惊', '驚']){
		if(str.indexOf(d) >= 0){ return { door: d.replace('開', '开').replace('傷', '伤').replace('驚', '惊'), jixiong: BAMEN_JIXIONG[d] || '' }; }
	}
	return null;
}

// —— 厄会(§23):主/客/定算 触重阳/重阴/无门 → 厄 ——
export function computeEhui(pan){
	if(!pan){ return []; }
	const yy = palaceYinYang(pan.taiyiPalace);
	const out = [];
	const chk = (label, n) => {
		const v = typeof n === 'number' ? n : parseInt(n, 10);
		if(isNaN(v)){ return; }
		const tags = shuliLabel(v, yy);
		// ⚠️ 只认「重阳数/重阴数」灾级全标,不认「阴中重阳/阳中重阴」子类(含相同子串,属微妙转化非厄)。
		if(tags.some((t) => t.indexOf('重阳数') >= 0)){ out.push(`${label}重阳厄(${v})`); }
		if(tags.some((t) => t.indexOf('重阴数') >= 0)){ out.push(`${label}重阴厄(${v})`); }
		if(tags.some((t) => t.indexOf('无门') >= 0)){ out.push(`${label}无门厄(${v})`); }
	};
	chk('主算', pan.homeCal); chk('客算', pan.awayCal); chk('定算', pan.setCal);
	return out;
}

// —— 国运限运(§15.3/§23.3):大限=太乙每行一宫管3年、小限=文昌每宫1年、二限=大游/小游 ——
export function computeLimitYun(pan){
	if(!pan){ return null; }
	const gongGua = (n) => (n != null && TAIYI_GONG_INFO[Number(n)] ? `${n}宫·${TAIYI_GONG_INFO[Number(n)].gua}` : (n != null ? `${n}` : ''));
	return {
		daxian: { who: '太乙', at: pan.taiyiPalace || '', span: '每宫3年' },
		xiaoxian: { who: '文昌', at: pan.skyeyes || '', span: '每宫1年' },
		erxian: { dayou: gongGua(pan.bigyoNum), xiaoyou: gongGua(pan.smyoNum) },
	};
}

// —— 十精(今义):二目 + 八将,从 pan 现成落点组装成有序 10 项 ——
// 今义十精 = 文昌·始击(二目) + 计神 + 主大将·主参将 + 客大将·客参将 + 君基·臣基·民基。
// 《癸巳类稿》古义星名(天皇/帝符/天时/太尊/飞鸟/五行/八风/五风/三风/太一)只入帮助文档,不混今义计算。
export function computeShiJing(pan){
	if(!pan){ return null; }
	const at = (pos, gong) => {
		const p = pos ? String(pos) : '';
		const g = (gong !== undefined && gong !== null && String(gong) !== '') ? `${gong}宫` : '';
		return (p && g) ? `${p}(${g})` : (p || g || '—');
	};
	const items = [
		{ name: '文昌', at: at(pan.skyeyes), role: '目' },
		{ name: '始击', at: at(pan.sf), role: '目' },
		{ name: '计神', at: at(pan.jigod), role: '将' },
		{ name: '主大将', at: at(pan.homeGeneralPalace, pan.homeGeneral), role: '将' },
		{ name: '主参将', at: at(pan.homeVGenPalace, pan.homeVGen), role: '将' },
		{ name: '客大将', at: at(pan.awayGeneralPalace, pan.awayGeneral), role: '将' },
		{ name: '客参将', at: at(pan.awayVGenPalace, pan.awayVGen), role: '将' },
		{ name: '君基', at: at(pan.kingbase), role: '基' },
		{ name: '臣基', at: at(pan.officerbase), role: '基' },
		{ name: '民基', at: at(pan.pplbase), role: '基' },
	];
	return items;
}

// —— 五子元(§3.2):(积年 % 360) // 72 → 甲子/丙子/戊子/庚子/壬子元 ——
const WUZIYUAN = ['甲子元', '丙子元', '戊子元', '庚子元', '壬子元'];
export function computeWuziyuan(pan){
	if(!pan){ return ''; }
	const acc = Number(pan.accNum);
	if(!Number.isFinite(acc) || acc <= 0){ return ''; }
	const idx = Math.floor(((acc % 360) + 360) % 360 / 72);
	return WUZIYUAN[idx] || '';
}

// —— 地支六合表(§ 合神):子丑/寅亥/卯戌/辰酉/巳申/午未 ——
export const LIUHE = { 子: '丑', 丑: '子', 寅: '亥', 亥: '寅', 卯: '戌', 戌: '卯', 辰: '酉', 酉: '辰', 巳: '申', 申: '巳', 午: '未', 未: '午' };
// 合神(后端 hegod 已产)→ 其六合对象;取合神支的六合。返回 { hegod, he }。
export function computeHeShen(pan){
	const hg = pan && pan.hegod ? String(pan.hegod).charAt(0) : '';
	if(!hg){ return null; }
	return { hegod: pan.hegod, he: LIUHE[hg] || '' };
}

// —— 主客胜负(§11.4 总则 + §15.2 综合判据) ——
export function computeVictory(pan, geju){
	if(!pan){ return null; }
	const home = Number(pan.homeCal), away = Number(pan.awayCal);
	let side = '势均', verdict = '主客算相等,势均力敌、宜静待时。';
	if(home > away){ side = '主胜'; verdict = `主算 ${home} > 客算 ${away},主方得算、利主(先动/我方)。`; }
	else if(away > home){ side = '客胜'; verdict = `客算 ${away} > 主算 ${home},客方得算、利客(后应/彼方)。`; }
	else { verdict = `主算 ${home} = 客算 ${away},势均力敌、宜静待时。`; }
	const reasons = [`主客算总则:${verdict}`];
	// 太乙宫气(旺衰底色)
	const tNum = Number(pan.taiyiNum);
	if(tNum && TAIYI_GONG_INFO[tNum]){ const g = TAIYI_GONG_INFO[tNum]; reasons.push(`太乙临${g.gua}·${g.qi}(${g.men}),${QI_OMEN[g.qi] || ''}。`); }
	// 格局压制
	const gj = geju || [];
	const yanQiu = gj.filter((x) => x.kind === 'yan' || x.kind === 'qiu' || x.kind === 'ge');
	if(yanQiu.length){ reasons.push(`格局压制:${yanQiu.map((x) => x.name).join('、')} — 主势受掩/囚/格之制,胜负打折。`); }
	return { side, verdict, reasons };
}
