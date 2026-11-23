// 断法层(下):行年、六神六亲、旺相分数与长生、阴盘、内外、合占、方位、四象、格局、四囚、应期、神煞说明
// 从 JinKouCalc.js 按职责拆出(门面保留原导入路径与对外导出;读源码的检查读「子模块 + 门面」全集,见 scripts/source-sets.json)。
import * as LRConst from '../../liureng/LRConst.js';
import { JINKOU_XINGNIAN_GE, JINKOU_LIUSHEN_DOC, JINKOU_LIUQIN_DOC, JINKOU_SIXIANG_SHU, JINKOU_SIXIANG_WUXING, JINKOU_TIANQI_TEXT, JINKOU_GEJU_DOC, JINKOU_DIZHI_DOC, JINKOU_SHENSHA_DOC } from '../JinKouDoc.js';
import { wuxingRelation, branchRelTypes } from './readings.js';
import { rowZhi, getElem } from './basics.js';
import { JINKOU_SANQI_SETS } from './tables.js';

// —— 行年旬法（按生年所在旬起一岁干支，男顺女逆，每岁进一位）——
// 六旬起例：甲子旬男丙寅女壬申、甲戌旬男丙子女壬午、甲申旬男丙戌女壬辰、
//           甲午旬男丙申女壬寅、甲辰旬男丙午女壬子、甲寅旬男丙辰女壬戌。
const JINKOU_XINGNIAN_START = {
	'甲子': { male: '丙寅', female: '壬申' },
	'甲戌': { male: '丙子', female: '壬午' },
	'甲申': { male: '丙戌', female: '壬辰' },
	'甲午': { male: '丙申', female: '壬寅' },
	'甲辰': { male: '丙午', female: '壬子' },
	'甲寅': { male: '丙辰', female: '壬戌' },
};

// 六十甲子序：由干支求序，供顺逆进位。
function ganZhiIndex(gz){
	const gan = `${gz || ''}`.charAt(0);
	const zhi = `${gz || ''}`.charAt(1);
	const gi = LRConst.GanList.indexOf(gan);
	const zi = LRConst.ZiList.indexOf(zhi);
	if(gi < 0 || zi < 0){ return -1; }
	for(let n = 0; n < 60; n++){
		if(n % 10 === gi && n % 12 === zi){ return n; }
	}
	return -1;
}

function ganZhiAt(n){
	const i = ((n % 60) + 60) % 60;
	return `${LRConst.GanList[i % 10]}${LRConst.ZiList[i % 12]}`;
}

// 生年干支 → 所在旬首（甲子/甲戌/…）。
function xunHeadOf(birthGanZi){
	const idx = ganZhiIndex(birthGanZi);
	if(idx < 0){ return ''; }
	return ganZhiAt(idx - (idx % 10));
}

export function buildJinKouXingNian(birthGanZi, gender, age){
	const head = xunHeadOf(birthGanZi);
	const start = JINKOU_XINGNIAN_START[head];
	const n = Math.floor(Number(age) || 0);
	if(!start || n < 1){ return null; }
	// gender：1/男 顺行，0/女 逆行（与全站 gender 口径一致）。
	const isMale = !(gender === 0 || gender === '0' || gender === '女');
	const startGz = isMale ? start.male : start.female;
	const si = ganZhiIndex(startGz);
	if(si < 0){ return null; }
	const cur = ganZhiAt(si + (isMale ? (n - 1) : -(n - 1)));
	const zhi = cur.charAt(1);
	return {
		birthGanZi: birthGanZi,
		xunHead: head,
		gender: isMale ? '男' : '女',
		age: n,
		startGanZi: startGz,
		ganZhi: cur,
		zhi: zhi,
		ge: JINKOU_XINGNIAN_GE[zhi] || '',
		note: `生年${birthGanZi}属${head}旬，${isMale ? '男顺行' : '女逆行'}，一岁起${startGz}，每岁进一位；取行年地支为地分可另立一课断该年灾福。`,
	};
}

// ══ 阴盘（旺衰派）公共框架：六神 / 六亲 / 旺衰量化 ══
// 只实现公开可复原的公共方法论；精细私传分值不臆造，分值表自定但前后一致，UI 明示。

// 六神（六兽）起例：按日干起第一位，自四位之下而上顺布 青龙→朱雀→勾陈→螣蛇→白虎→玄武。
const JINKOU_LIUSHEN_ORDER = ['青龙', '朱雀', '勾陈', '螣蛇', '白虎', '玄武'];

const JINKOU_LIUSHEN_START = { '甲': '青龙', '乙': '青龙', '丙': '朱雀', '丁': '朱雀', '戊': '勾陈', '己': '螣蛇', '庚': '白虎', '辛': '白虎', '壬': '玄武', '癸': '玄武' };

function buildJinKouLiuShen(rows, dayGan){
	const start = JINKOU_LIUSHEN_START[dayGan];
	if(!start){ return []; }
	const base = JINKOU_LIUSHEN_ORDER.indexOf(start);
	// 爻位自下而上：地分→将神→贵神→人元（rows 是自上而下，故反序取位次）。
	const bottomUp = (rows || []).slice().reverse();
	const out = bottomUp.map((r, i)=>{
		const name = JINKOU_LIUSHEN_ORDER[(base + i) % 6];
		return { wei: r.label, name: name, desc: JINKOU_LIUSHEN_DOC[name] || '' };
	});
	// 回到自上而下的四位序，与其余卡片一致。
	return out.reverse();
}

// 六亲：以日干为「我」（阴盘派常用口径），按五行生克给四位贴六亲标签。
function buildJinKouLiuQin(rows, selfElem){
	if(!selfElem){ return []; }
	return (rows || []).map((r)=>{
		const e = r.elem || '';
		let qin = '';
		if(!e){ qin = ''; }
		else if(e === selfElem){ qin = '兄弟'; }
		else if(wuxingRelation(e, selfElem) === '生'){ qin = '父母'; }      // 生我者父母
		else if(wuxingRelation(selfElem, e) === '生'){ qin = '子孙'; }      // 我生者子孙
		else if(wuxingRelation(e, selfElem) === '克'){ qin = '官鬼'; }      // 克我者官鬼
		else if(wuxingRelation(selfElem, e) === '克'){ qin = '妻财'; }      // 我克者妻财
		return { wei: r.label, elem: e, qin: qin, zhu: JINKOU_LIUQIN_DOC[qin] || '' };
	});
}

// 旺衰量化：月令旺相休囚死 + 十二长生宫 + 课内生克，三项合一打分。
// ⚠ 分值为公共框架下自定的一致表（非私传精细值），三项权重固定、全模块单一引用。
const JINKOU_WANGSCORE_TABLE = {
	season: { '旺': 4, '相': 2, '休': -1, '囚': -2, '死': -3 },
	changsheng: { '长生': 2, '沐浴': 0, '冠带': 2, '临官': 3, '帝旺': 3, '衰': -1, '病': -1, '死': -2, '墓': -2, '绝': -3, '胎': 0, '养': 1 },
	inner: { '受生': 1, '受克': -2, '同气': 1 },
	levels: [
		{ min: 5, level: '旺' },
		{ min: 2, level: '相' },
		{ min: -1, level: '平' },
		{ min: -4, level: '衰' },
		{ min: -99, level: '绝' },
	],
};

// 十二长生宫：五行寄十二宫（土从水，多数派「土长生在申」；寅长生为少数派，Batch 6 开关）。
const JINKOU_CHANGSHENG_ORDER = ['长生', '沐浴', '冠带', '临官', '帝旺', '衰', '病', '死', '墓', '绝', '胎', '养'];

const JINKOU_CHANGSHENG_START = { '木': '亥', '火': '寅', '金': '巳', '水': '申', '土': '申' };

// —— 土之十二长生两派（B6·P2）——
// 「水土同宫」（默认 shen）：土随水，长生在申；「火土同宫」（少数派 yin）：土随火，长生在寅。
// 仅作用于金口诀页的十二长生表与阴盘长生打分；共用的 LRZhangSheng.wxphase 一字不动
// （六壬/演禽等页读同一张表，改它即改别页 → 违「加新功能别改坏旧功能」）。
export const JINKOU_SOIL_PHASE_START = { shen: '申', yin: '寅' };

export function jinKouSoilStart(mode){
	return JINKOU_SOIL_PHASE_START[mode] || JINKOU_SOIL_PHASE_START.shen;
}

// 某五行的十二长生落支表 {长生:'申', 沐浴:'酉', …}；土随流派，其余四行恒定。
export function jinKouPhaseTable(elem, soilMode){
	// 五行取值非法（外部传了错值/空值）时回落默认「土」，而不是吐一张空表 ——
	// 空表会让右栏十二长生整列变「—」、快照 [十二长生] 段全为「无」，是静默降级。
	const key = JINKOU_CHANGSHENG_START[elem] !== undefined || elem === '土' ? elem : '土';
	const start = key === '土' ? jinKouSoilStart(soilMode) : JINKOU_CHANGSHENG_START[key];
	const s = LRConst.ZiList.indexOf(start);
	const out = {};
	if(s < 0){ return out; }
	JINKOU_CHANGSHENG_ORDER.forEach((name, i)=>{
		out[name] = LRConst.ZiList[(s + i) % 12];
	});
	return out;
}

function jinKouChangShengPhase(elem, zhi, soilMode){
	const start = elem === '土' ? jinKouSoilStart(soilMode) : JINKOU_CHANGSHENG_START[elem];
	if(!start || !zhi){ return ''; }
	const si = LRConst.ZiList.indexOf(start);
	const zi = LRConst.ZiList.indexOf(zhi);
	if(si < 0 || zi < 0){ return ''; }
	return JINKOU_CHANGSHENG_ORDER[(zi - si + 12) % 12];
}

function buildJinKouWangScore(rows, seasonMap, soilMode){
	const T = JINKOU_WANGSCORE_TABLE;
	// 逐行同下标遍历(不 filter)——先前用 filter(Boolean) 压缩过的数组去索引 rows，
	// 只要有一行 elem 为空，其后各行下标即整体前移，「排除自己」就排到了别人头上。
	const list = rows || [];
	return list.map((r)=>{
		const elem = r.elem || '';
		if(!elem){ return { wei: r.label, elem: '', score: 0, level: '', detail: [] }; }
		const detail = [];
		let score = 0;
		// ① 月令旺相休囚死（沿用后端 season 表，与右栏旺衰卡同源）
		const sea = seasonMap && seasonMap[elem] ? seasonMap[elem] : '';
		if(sea && T.season[sea] !== undefined){ score += T.season[sea]; detail.push(`月令${sea} ${T.season[sea] > 0 ? '+' : ''}${T.season[sea]}`); }
		// ② 十二长生宫（以本位地支论；人元无支则跳过）
		const zhi = rowZhi(r);
		const phase = zhi ? jinKouChangShengPhase(elem, zhi, soilMode) : '';
		if(phase && T.changsheng[phase] !== undefined){ score += T.changsheng[phase]; detail.push(`坐${phase} ${T.changsheng[phase] > 0 ? '+' : ''}${T.changsheng[phase]}`); }
		// ③ 课内生克：他位对本位的生/克/同气累计
		let inner = 0;
		list.forEach((otherRow)=>{
			if(otherRow === r){ return; }
			const other = otherRow.elem || '';
			if(!other){ return; }
			if(other === elem){ inner += T.inner['同气']; return; }
			if(wuxingRelation(other, elem) === '生'){ inner += T.inner['受生']; }
			else if(wuxingRelation(other, elem) === '克'){ inner += T.inner['受克']; }
		});
		if(inner){ score += inner; detail.push(`课内生克 ${inner > 0 ? '+' : ''}${inner}`); }
		const hit = T.levels.find((lv)=>score >= lv.min);
		return { wei: r.label, elem: elem, score: score, level: hit ? hit.level : '平', detail: detail };
	});
}

// 阴盘断法三层聚合（panShi==='yin' 时产出；阳盘恒 null，零回归）。
export function buildJinKouYinPan(rows, dayGan, seasonMap, soilMode){
	const selfElem = getElem(dayGan);
	return {
		self: dayGan || '',
		selfElem: selfElem,
		liushen: buildJinKouLiuShen(rows, dayGan),
		liuqin: buildJinKouLiuQin(rows, selfElem),
		wangScore: buildJinKouWangScore(rows, seasonMap, soilMode),
		scoreNote: '分值为公共框架下自定的一致表（月令＋十二长生＋课内生克三项合一），非某家私传精细值；用于横向比较四位强弱，不作绝对判据。',
	};
}

// 课分内外（§3.9）：四位以中线分内外——贴地分一侧为内（自身、近、家内），
// 贴人元一侧为外（他人、远、外出）；将神贵神分居其间，用以断事在内在外、宜主宜客。
export function buildJinKouNeiWai(rows, yongLabel){
	const order = ['人元', '贵神', '将神', '地分'];
	const side = { '人元': '外', '贵神': '外', '将神': '内', '地分': '内' };
	const list = order.map((label)=>{
		const row = (rows || []).find((r)=>r.label === label);
		return {
			label: label,
			side: side[label],
			yong: yongLabel === label,
			content: row ? `${row.gan && row.gan !== '-' ? row.gan : ''}${row.content && row.content !== '—' ? row.content : ''}` : '',
		};
	});
	const yongSide = yongLabel ? side[yongLabel] : '';
	const text = yongSide === '内'
		? '用爻居内（近地分一侧）：事在自身、家内、近处，宜主不宜客、宜守不宜远行。'
		: (yongSide === '外'
			? '用爻居外（近人元一侧）：事在他人、外部、远处，宜客不宜主，谋事须向外求。'
			: '');
	return { rows: list, yongSide: yongSide, text: text };
}

// 合占·扣题直断（§10.8 界定范围 + §10.9 八步收束）：
//   ① 取事分类——问财取财爻(将神)、问官取贵神、其余取用爻；
//   ② 时间范围——问日时以日时干支为参、问年以年干支为参；
//   ③ 汇聚已算之五动三动/相关神煞/用爻旺衰/内外，串成一条结论链。
// askKey 取自分类用神的 key（起课时所问事项），缺省走「用爻为主」的通则。
export const JINKOU_HEZHAN_FOCUS = {
	qiucai: { label: '财', position: '将神', note: '问财以财爻为主，财爻多在将神，地分为副财。' },
	guantu: { label: '官', position: '贵神', note: '问官以贵神为主，看其旺衰与日月生克。' },
	guansi: { label: '官司', position: '贵神', note: '问官司以贵神为我方之主、人元为对方之客。' },
	xueye: { label: '功名', position: '贵神', note: '问功名以贵神为禄位之主，人元为外部环境。' },
	jibing: { label: '病', position: '', note: '问病以受克之位定病所：人元头、贵神胸、将神腹、地分腿足。' },
	hunyue: { label: '婚', position: '将神', note: '问婚以将神定男女（阳支主男、阴支主女），看六合刑冲。' },
	huaiyun: { label: '孕', position: '将神', note: '问孕以将神（相爻）阳支主男、阴支主女。' },
};

export const JINKOU_HEZHAN_TIME = {
	day: { label: '日内', note: '问当日成否，以用爻结合日、时干支断，不取年月。' },
	year: { label: '一年', note: '问一年之事，以用爻结合太岁年干支断。' },
	default: { label: '常规', note: '未限定时段者，以用爻结合日辰为主、旁参月建太岁。' },
};

export function buildJinKouHezhan(ctx){
	const rows = ctx.rows || [];
	const yongLabel = ctx.yongLabel || '';
	const askKey = ctx.askKey || '';
	const timeScope = ctx.timeScope || 'default';
	const focus = JINKOU_HEZHAN_FOCUS[askKey] || null;
	// 取用位：扣题优先（问财→将神/问官→贵神），无扣题则回落用爻位。
	const usePosition = (focus && focus.position) ? focus.position : yongLabel;
	const useRow = rows.find((r)=>r.label === usePosition) || null;
	const timeDef = JINKOU_HEZHAN_TIME[timeScope] || JINKOU_HEZHAN_TIME.default;
	// 与取用位相关的五动三动（扣题第 4 步：问什么答什么）。
	const dong = ctx.dong || { wu: [], san: [] };
	const relatedDong = [].concat(dong.wu || [], dong.san || [])
		.filter((d)=>!usePosition || d.from === usePosition || d.to === usePosition);
	// 与取用位相关的神煞（地支类神煞须用爻临之，此处按位过滤即同一口径）。
	const relatedGods = (ctx.relevantShensha || []).filter((g)=>!usePosition || g.position === usePosition);
	const chain = [];
	if(focus){ chain.push(`取事：${focus.note}`); }
	else if(yongLabel){ chain.push(`取事：未限定类别，以用爻（${yongLabel}）为事之主体。`); }
	chain.push(`时段：${timeDef.note}`);
	if(useRow){
		const power = useRow.power ? `（${useRow.power}）` : '';
		chain.push(`取用：${usePosition}${useRow.content && useRow.content !== '—' ? ` ${useRow.gan && useRow.gan !== '-' ? useRow.gan : ''}${useRow.content}` : ''}${power}${useRow.kong ? '，落空亡' : ''}。`);
	}
	if(relatedDong.length){
		chain.push(`动象：${relatedDong.map((d)=>`${d.type}动（${d.from}→${d.to}${d.kong ? '·落空' : ''}）`).join('、')}。`);
	}else{
		chain.push('动象：取用之位无五动三动直接牵动，事体平缓、须待外引。');
	}
	if(relatedGods.length){
		chain.push(`神煞：${relatedGods.slice(0, 6).map((g)=>g.name).join('、')}临之。`);
	}
	if(ctx.neiwai && ctx.neiwai.text){ chain.push(`内外：${ctx.neiwai.text}`); }
	return {
		askKey: askKey,
		askLabel: focus ? focus.label : '',
		usePosition: usePosition,
		useRow: useRow ? { label: useRow.label, content: useRow.content, gan: useRow.gan, power: useRow.power, kong: useRow.kong } : null,
		timeScope: timeScope,
		timeLabel: timeDef.label,
		relatedDong: relatedDong,
		relatedGods: relatedGods.slice(0, 8),
		chain: chain,
	};
}

// 方位类神煞（§9.7）：飞天八方五鬼与喜神方位，按日干取八卦之位。
// 不入四位行（无支可临），单列一组；出行趋避用。
const JINKOU_BAGUA_FANGWEI = { '巽': '东南', '艮': '东北', '乾': '西北', '坎': '正北', '坤': '西南', '离': '正南', '震': '正东', '兑': '正西' };

const JINKOU_WUGUI_FANG = { '甲': '巽', '己': '巽', '乙': '艮', '庚': '艮', '丙': '乾', '辛': '乾', '丁': '坎', '壬': '坎', '戊': '坤', '癸': '坤' };

const JINKOU_XISHEN_FANG = { '甲': '艮', '己': '艮', '乙': '乾', '庚': '乾', '丙': '坤', '辛': '坤', '丁': '离', '壬': '离', '戊': '巽', '癸': '巽' };

export function buildJinKouFangWei(dayGan){
	if(!dayGan){ return []; }
	const out = [];
	const wg = JINKOU_WUGUI_FANG[dayGan];
	const xs = JINKOU_XISHEN_FANG[dayGan];
	if(wg){
		out.push({ name: '飞天五鬼', gua: wg, fang: JINKOU_BAGUA_FANGWEI[wg] || '', jx: 'xiong', text: '飞天八方五鬼所在，出行主损财损车、多口舌是非，宜避其方。' });
	}
	if(xs){
		out.push({ name: '喜神', gua: xs, fang: JINKOU_BAGUA_FANGWEI[xs] || '', jx: 'ji', text: '喜神所在之方，出行谒贵、求谋议事宜向此方，主逢喜遇助。' });
	}
	return out;
}

// 四象所属图：把静态四位所属(亲属/君臣主客/天地/官禄财/内外/身体)与当前四位实况并排，
// 供右栏 6 列表与分类用神引用——四位类象自此单一取数，勿在文案里重复硬写。
export function buildJinKouSixiangShu(rows){
	return (rows || []).map((r)=>{
		const attr = JINKOU_SIXIANG_SHU[r.label] || {};
		const zhi = rowZhi(r);
		return {
			label: r.label,
			// 干支实况：人元只有干、地分只有支、将神贵神干支俱全。
			ganzhi: `${r.gan && r.gan !== '-' ? r.gan : ''}${zhi || (r.content && r.content !== '—' ? r.content : '')}`,
			shenjiang: r.shenjiang && r.shenjiang !== '-' ? r.shenjiang : '',
			elem: r.elem || '',
			power: r.power || '',
			qinshu: attr.qinshu || '—',
			junchen: attr.junchen || '—',
			tiandi: attr.tiandi || '—',
			guanlucai: attr.guanlucai || '—',
			neiwai: attr.neiwai || '—',
			shenti: attr.shenti || '—',
		};
	});
}

// 四象五行取象：四位五行各取天时/地理/人事/病源之象，并以课中「旺」之五行为主象
// (旺之五行沿用课内旺衰 calcJinKouWangElem 的结果，不另立判据)。逢空破者标注象变。
export function buildJinKouSixiangWuxing(rows, wangElem){
	const list = (rows || []).map((r)=>{
		const elem = r.elem || '';
		const doc = JINKOU_SIXIANG_WUXING[elem] || {};
		const kong = !!(r.kong && `${r.kong}`.indexOf('空') >= 0);
		return {
			label: r.label,
			elem: elem,
			kong: kong,
			tianshi: doc.tianshi || '—',
			dili: doc.dili || '—',
			renshi: doc.renshi || '—',
			bingyuan: doc.bingyuan || '—',
		};
	});
	const mainElem = wangElem || '';
	const tianqiText = mainElem && JINKOU_TIANQI_TEXT[mainElem] ? JINKOU_TIANQI_TEXT[mainElem] : '';
	// 病源以受克之位为患处(与分类用神「人体疾病」同口径)，此处只据四位五行给病源象与虚实。
	const bingList = list.filter((it)=>it.elem && it.bingyuan !== '—');
	const bingText = bingList.length
		? bingList.map((it)=>`${it.label}${it.elem}主${it.bingyuan}`).join('；')
		: '';
	return {
		rows: list,
		mainElem: mainElem,
		tianqiText: tianqiText,
		bingText: bingText,
		hasKong: list.some((it)=>it.kong),
	};
}

// 格局判定（§9.5）：由四位地支/五行结构判连茹/三合全身/四位俱比/四墓(清晰可判者)。
const JINKOU_SANHE_JU = [['申', '子', '辰', '水'], ['寅', '午', '戌', '火'], ['巳', '酉', '丑', '金'], ['亥', '卯', '未', '木']];

const JINKOU_MU_ZHI = ['辰', '戌', '丑', '未'];

export function buildJinKouGeju(rows){
	const zhis = rows.map((r)=>rowZhi(r)).filter(Boolean);
	const elems = rows.map((r)=>r.elem).filter(Boolean);
	const zhiSet = {};
	zhis.forEach((z)=>{ zhiSet[z] = true; });
	const out = [];
	// 四位俱比：四位五行俱同
	if(elems.length === 4 && elems.every((e)=>e === elems[0])){
		out.push({ name: `四位俱比·${elems[0]}`, kind: '俱比', jx: 'zhong', text: JINKOU_GEJU_DOC['俱比'] });
	}
	// 三合全身：四位含某三合局三支
	JINKOU_SANHE_JU.forEach((ju)=>{
		if(ju[0] && zhiSet[ju[0]] && zhiSet[ju[1]] && zhiSet[ju[2]]){
			out.push({ name: `三合全身·${ju[3]}局`, kind: '三合', jx: 'ji', text: JINKOU_GEJU_DOC['三合全身'] });
		}
	});
	// 连茹：去重地支中存在 3 支于地支环上前后相连
	const idxSet = {};
	zhis.forEach((z)=>{ const i = LRConst.ZiList.indexOf(z); if(i >= 0){ idxSet[i] = true; } });
	let lianru = false;
	for(let i = 0; i < 12; i++){
		if(idxSet[i] && idxSet[(i + 1) % 12] && idxSet[(i + 2) % 12]){ lianru = true; break; }
	}
	if(lianru){ out.push({ name: '连茹', kind: '连茹', jx: 'zhong', text: JINKOU_GEJU_DOC['连茹'] }); }
	// 三支(贵神/将神/地分)皆临墓库 → 墓库格(四位干无支，故以三地支判)
	if(zhis.length >= 3 && zhis.every((z)=>JINKOU_MU_ZHI.indexOf(z) >= 0)){
		out.push({ name: '墓库格', kind: '墓库', jx: 'xiong', text: JINKOU_GEJU_DOC['四墓'] });
	}
	// 一类朝元：某天干见其本属之支重叠（甲见寅、乙见卯…戊见辰戌、己见未丑）。
	// 古法以「一干见三支」为格；金口诀四位仅三地支，故以「课中所见地支全为该干本属」为判据
	// （与四位俱比同一处理原则），并在断辞标明支数。
	const gans = (rows || []).map((r)=>(r.gan && r.gan !== '-' ? r.gan : (r.label === '人元' ? r.content : ''))).filter(Boolean);
	Object.keys(JINKOU_CHAOYUAN_ZHI).forEach((gan)=>{
		if(gans.indexOf(gan) < 0){ return; }
		const own = JINKOU_CHAOYUAN_ZHI[gan];
		const hits = zhis.filter((z)=>own.indexOf(z) >= 0);
		if(hits.length >= 3){
			out.push({ name: `一类朝元·${gan}`, kind: '朝元', jx: 'zhong', text: JINKOU_GEJU_DOC['一类朝元'] });
		}
	});
	return out;
}

// 十干本属之支（一类朝元用）：土干各辖二库支。
const JINKOU_CHAOYUAN_ZHI = {
	'甲': ['寅'], '乙': ['卯'], '丙': ['午'], '丁': ['巳'], '戊': ['辰', '戌'],
	'己': ['未', '丑'], '庚': ['申'], '辛': ['酉'], '壬': ['子'], '癸': ['亥'],
};

// 四丘（季支）：春丑、夏辰、秋未、冬戌 —— 主争田土坟地、丧事争讼病死，问病主凶。
const JINKOU_SIQIU_BY_SEASON = { '春': '丑', '夏': '辰', '秋': '未', '冬': '戌' };

export function buildJinKouSiQiu(rows, seasonName){
	const zhi = JINKOU_SIQIU_BY_SEASON[seasonName] || '';
	if(!zhi){ return null; }
	const hitRow = (rows || []).find((r)=>rowZhi(r) === zhi);
	if(!hitRow){ return null; }
	return { name: '四丘', kind: '四丘', jx: 'xiong', zhi: zhi, position: hitRow.label, text: JINKOU_GEJU_DOC['四丘'] };
}

export function buildJinKouBranchRelations(rows, dayZi){
	const points = [];
	rows.forEach((r)=>{ const zhi = rowZhi(r); if(zhi){ points.push({ label: r.label, branch: zhi }); } });
	if(dayZi){ points.push({ label: '日辰', branch: dayZi }); }
	const out = [];
	const seen = {};
	for(let i=0; i<points.length; i++){
		for(let j=i + 1; j<points.length; j++){
			const types = branchRelTypes(points[i].branch, points[j].branch);
			types.forEach((type)=>{
				const k = `${type}_${points[i].branch}_${points[j].branch}`;
				if(seen[k]){ return; }
				seen[k] = true;
				out.push({ type: type, a: points[i].branch, b: points[j].branch, aLabel: points[i].label, bLabel: points[j].label, desc: JINKOU_DIZHI_DOC[type] || '' });
			});
		}
	}
	return out;
}

export function buildJinKouTaixuan(rows){
	return rows.map((r)=>{
		const tokens = [];
		if(r.gan && r.gan !== '-' && LRConst.TaiXuanNum[r.gan] !== undefined){ tokens.push(r.gan); }
		if(r.content && LRConst.TaiXuanNum[r.content] !== undefined && tokens.indexOf(r.content) < 0){ tokens.push(r.content); }
		const nums = tokens.map((t)=>LRConst.TaiXuanNum[t]);
		const sum = nums.reduce((s, n)=>s + n, 0);
		return { label: r.label, tokens: tokens.join(''), nums: nums, num: sum };
	});
}

export function buildJinKouYongStrength(yongYao, rows, wangShuaiMap){
	if(!yongYao || !yongYao.label){ return null; }
	const row = rows.find((r)=>r.label === yongYao.label);
	const elem = row ? row.elem : '';
	const state = elem && wangShuaiMap ? wangShuaiMap[elem] : '';
	let level = '中';
	if(state === '旺' || state === '相'){ level = '强'; }
	else if(state === '囚' || state === '死'){ level = '弱'; }
	const tail = level === '强' ? '所谋易成' : (level === '弱' ? '力弱难成' : '平平');
	const text = `用神${yongYao.label}（${elem || '—'}）当令${state || '—'}，主${tail}。`;
	return { label: yongYao.label, elem: elem, state: state, level: level, text: text };
}

export function buildJinKouYingQi(ctx){
	const yongRow = ctx.yongRow;
	if(!yongRow){ return null; }
	const yBranch = yongRow.branch || (LRConst.ZiList.indexOf(yongRow.content) >= 0 ? yongRow.content : '');
	const yGan = (yongRow.gan && yongRow.gan !== '-') ? yongRow.gan : (LRConst.GanList.indexOf(yongRow.content) >= 0 ? yongRow.content : '');
	// —— 基础口径（临日/月/时/年 + 旺衰 + 空）——
	let scope = '月内';
	if(yGan && yGan === ctx.dayGan){ scope = '旬内'; }
	else if(yBranch && yBranch === ctx.dayZi){ scope = '月内'; }
	else if(yBranch && yBranch === ctx.timeZi){ scope = '即刻'; }
	else if(yBranch && yBranch === ctx.yearZi){ scope = '年内'; }
	if(ctx.guiGan && ctx.guiZi && ctx.guiGan === ctx.dayGan && ctx.guiZi === ctx.dayZi){ scope = '即日'; }
	const state = ctx.wangShuaiMap && yongRow.elem ? ctx.wangShuaiMap[yongRow.elem] : '';
	const empty = yBranch && ctx.xunKongBranches && ctx.xunKongBranches.indexOf(yBranch) >= 0;
	let text = scope === '即日' ? '贵神与日柱相同，可即日得验。' : `用神所临，约主${scope}应。`;
	if(state === '旺' || state === '相'){ text += '用神旺相，应之宜速（取近）。'; }
	else if(state === '休' || state === '囚' || state === '死'){ text += '用神休囚，应之多迟（取远）。'; }
	if(empty){ scope = '出空后'; text += '用神逢空，须俟出空之日方应。'; }

	// —— 合德六法 ——
	const rows = ctx.rows || [];
	const fourBranches = rows.map((r)=>rowZhi(r)).filter(Boolean);
	const fourGans = rows.map((r)=>((r.gan && r.gan !== '-') ? r.gan : (LRConst.GanList.indexOf(r.content) >= 0 ? r.content : ''))).filter(Boolean);
	const jiangRow = rows.find((r)=>r.label === '将神');
	const jiangGan = jiangRow && jiangRow.gan && jiangRow.gan !== '-' ? jiangRow.gan : '';
	const fast = (state === '旺' || state === '相');
	const methods = [];
	// 1 天地合德：用爻干支之干合+支合俱全
	if(yGan && yBranch && LRConst.GanHe[yGan] && LRConst.ZiHe[yBranch]){
		methods.push({ fa: '天地合德', when: `${LRConst.GanHe[yGan]}${LRConst.ZiHe[yBranch]}`, text: `用爻(${yGan}${yBranch})干合支合俱全者，逢「${LRConst.GanHe[yGan]}${LRConst.ZiHe[yBranch]}」之期应（合处为妙）。` });
	}
	// 2 将干近合：将干五合之日
	if(jiangGan && LRConst.GanHe[jiangGan]){
		methods.push({ fa: '将干近合', when: `${LRConst.GanHe[jiangGan]}日`, text: `取将干(${jiangGan})之五合，逢「${LRConst.GanHe[jiangGan]}」日为应。` });
	}
	// 3 三奇合：课中三奇缺一字，逢所缺之干日时应
	JINKOU_SANQI_SETS.forEach((set)=>{
		const present = set.filter((g)=>fourGans.indexOf(g) >= 0);
		const missing = set.filter((g)=>fourGans.indexOf(g) < 0);
		if(present.length === 2 && missing.length === 1){
			methods.push({ fa: '三奇合', when: `${missing[0]}日`, text: `课见三奇(${set.join('')})之${present.join('')}，缺「${missing[0]}」，逢之日时为应。` });
		}
	});
	// 4 三合补字：用爻三合局缺一字，逢虚字透出为应
	if(yBranch && LRConst.ZiSangHe[yBranch]){
		const group = [yBranch].concat(LRConst.ZiSangHe[yBranch]);
		const present = group.filter((z)=>fourBranches.indexOf(z) >= 0);
		const missing = group.filter((z)=>fourBranches.indexOf(z) < 0);
		if(present.length >= 2 && missing.length === 1){
			methods.push({ fa: '三合补字', when: `${missing[0]}`, text: `三合局(${group.join('')})已见${present.join('')}，缺「${missing[0]}」，逢之透出为应。` });
		}
	}
	// 5 支六合：用爻六合之支
	if(yBranch && LRConst.ZiHe[yBranch]){
		methods.push({ fa: '支六合', when: `${LRConst.ZiHe[yBranch]}`, text: `取用爻(${yBranch})之六合，逢「${LRConst.ZiHe[yBranch]}」之期应。` });
	}
	// 6 旺相逢冲：用爻逢冲为动（旺相远应年月、休囚近应日时）
	if(yBranch && LRConst.ZiCong[yBranch]){
		methods.push({ fa: '旺相逢冲', when: `${LRConst.ZiCong[yBranch]}`, text: `用爻逢冲(${LRConst.ZiCong[yBranch]})为动，${fast ? '旺相远应年月' : '休囚近应日时'}（冲为动、合为止）。` });
	}
	return { scope: scope, text: text, methods: methods };
}

export function buildJinKouShenshaDoc(shenshaRows, yongLabel){
	const rows = [];
	const relevant = [];
	(shenshaRows || []).forEach((r)=>{
		const position = `${r.label || ''}`.replace(/神煞$/, '');
		const names = `${r.value || ''}`.split(/[、，,\s]+/).filter((n)=>n && n !== '无');
		const items = names.map((name)=>{
			const doc = JINKOU_SHENSHA_DOC[name];
			return { name: name, jx: doc ? doc.jx : 'zhong', desc: doc ? doc.desc : '' };
		});
		rows.push({ label: r.label, position: position, items: items });
		items.forEach((it)=>relevant.push({ name: it.name, jx: it.jx, desc: it.desc, position: position }));
	});
	if(yongLabel){
		relevant.sort((a, b)=>(a.position === yongLabel ? 0 : 1) - (b.position === yongLabel ? 0 : 1));
	}
	return { rows: rows, relevant: relevant };
}
