// 起局选项表与流派口径(排盘 / 起局法 / 寄宫 / 暗干 / 神盘预设等下拉,以及按口径取值的小函数)
// 从 DunJiaCalc.js 按职责拆出(门面保留原导入路径与对外导出;读源码的检查读「子模块 + 门面」全集,见 scripts/source-sets.json)。
import { CLOCKWISE_EIGHTGUA, newList } from './tables.js';
import { getXunHead, normalizeJieqi } from './basics.js';

export const SEX_OPTIONS = [
	{ value: 1, label: '男' },
	{ value: 0, label: '女' },
];

export const DATE_TYPE_OPTIONS = [
	{ value: 0, label: '公历' },
	{ value: 1, label: '农历' },
];

export const LEAP_MONTH_OPTIONS = [
	{ value: 0, label: '不闰月' },
	{ value: 1, label: '使用闰月' },
];

export const XUSHI_OPTIONS = [
	{ value: 0, label: '虚岁' },
	{ value: 1, label: '实岁' },
];

export const JIEQI_OPTIONS = [
	{ value: 0, label: '节气按天' },
	{ value: 1, label: '节气按分' },
];

export const PAIPAN_OPTIONS = [
	{ value: 0, label: '年家奇门' },
	{ value: 1, label: '月家奇门' },
	{ value: 2, label: '日家奇门' },
	{ value: 3, label: '时家奇门' },
	{ value: 4, label: '刻家奇门' },   // 十分局本地引擎(一时辰十刻,初局=时家局,逐刻阳顺阴逆推移)
	{ value: 6, label: '日家·古籍金函系' },   // 六十干支占方全表(书表直录:八方星门+吉凶+喜神/吉时),独立体系不走局法
	// 综合(5):暂无确切算法,不暴露(引擎/后端分支保留,待校准后再开)。
];

// 刻家分遁两档:zihou=子后阳午后阴(时支子~巳=阳遁、午~亥=阴遁,与节气无关,默认)/jieqi=冬至后阳夏至后阴(沿时家节气分遁)。
// 古籍日家八门两档:book=书表直录(默认;阴阳盘各按原表);shun=全顺变体(休生伤杜景死惊开自北起顺布八方,星仍书表)。
export const JINHAN_MENPAI_OPTIONS = [
	{ value: 'book', label: '书表直录（默认）' },
	{ value: 'shun', label: '全顺变体（休门北起顺布）' },
];

export const KEJIA_FENDUN_OPTIONS = [
	{ value: 'zihou', label: '子后阳·午后阴（默认）' },
	{ value: 'jieqi', label: '按节气分遁（冬至后阳）' },
];

// 日家定局粒度三档:yiyuan=六十日一局(现行经典,默认)/shitian=十日一局(逐旬按符头换元)/yitian=一日一局(至甲子起逐日推局,阳顺阴逆)。
export const DAYJIA_JU_OPTIONS = [
	{ value: 'yiyuan', label: '六十日一局（默认）' },
	{ value: 'shitian', label: '十日一局（逐旬换元）' },
	{ value: 'yitian', label: '一日一局（逐日推移）' },
];

export const ZHISHI_OPTIONS = [
	{ value: 0, label: '天禽值符-死门' },
	{ value: 1, label: '天禽值符-阴阳遁' },
	{ value: 2, label: '天禽值符-节气' },
	{ value: 3, label: '天禽值符-阳遁死门·阴遁生门' },   // 与寄宫「阳遁寄坤·阴遁寄艮」配套(寄坤借死门、寄艮借生门)
];

export const YUEJIA_QIJU_OPTIONS = [
	{ value: 0, label: '年符头' },
	{ value: 1, label: '年支' },
	{ value: 2, label: '逐月换局（一月一局）', short: '逐月换局' },
];

export const YEAR_GZ_OPTIONS = [
	{ value: 0, label: '年干支-正月初一' },
	{ value: 1, label: '年干支-立春当天' },
	{ value: 2, label: '年干支-立春交接' },
];

export const MONTH_GZ_OPTIONS = [
	{ value: 0, label: '月干支-节交接当天' },
	{ value: 1, label: '月干支-节交接时刻' },
];

export const DAY_GZ_OPTIONS = [
	{ value: 0, label: '日干支-晚子时按当天' },
	{ value: 1, label: '日干支-晚子时按明天' },
];

// 用户语义(拍板,字面直觉版):
//   after23NewDay=1「23点算第二天」= 23点起日柱进位次日(壬寅)
//   after23NewDay=0「24点算第二天」= 23点仍守今、24点才换日柱(辛丑)
export const DAY_SWITCH_OPTIONS = [
	{ value: 1, label: '23点算第二天' },
	{ value: 0, label: '24点算第二天' },
];

export const QIJU_METHOD_OPTIONS = [
	{ value: 'zhirun', label: '置闰' },
	{ value: 'chaibu', label: '拆补' },
	{ value: 'maoshan', label: '茅山' },
	{ value: 'wurun', label: '无闰' },
	{ value: 'shuzi', label: '阴盘' },   // 阴盘奇门:报数各位和%9(余0作9)定局(数字起局);原「阴盘」盘式归此(取数定局),与盘式正交
];

// 起局下拉(非时家非刻家):年/月/日家有各自「本家默认」定局(三元/年符头/节气三元),节气四法(置闰/拆补/
// 茅山/无闰)与它们无关。故只给两项「本家默认 / 阴盘(报数)」——阴盘报数与排盘正交、可叠加任意家;
// 避免「选了阴盘后节气四法被禁→无法切回本家默认」的死锁。
export const QIJU_METHOD_NONSHI_OPTIONS = [
	{ value: 'zhirun', label: '本家默认' },   // 非时家忽略具体节气法→等同本家原生定局(zhirun 仅占位)
	{ value: 'shuzi', label: '阴盘' },
];

// 起局下拉的**单一真值源**:独立奇门页与三式合一页此前各写各的(合一页恒 5 档 + 非时家整个禁用
// → 年/月/日/刻家选不了阴盘,且在时家选了阴盘再切家就锁死在阴盘出不来)。现两页同走此二函数。
// 刻家(4)初局沿时家定局链(resolvePaiPanMeta 以 paiPanType:3 求初局),节气四法**真的生效** ——
// 故刻家与时家同给完整 5 档;此前刻家只显「本家默认」,而底下沿用着上次在时家选的拆补/茅山/无闰,看不见也改不掉。
export function qijuMethodUsesJieqiFa(paiPanType){
	const t = Number(paiPanType);
	return t === 3 || t === 4;
}

export function qijuMethodOptionsFor(paiPanType){
	return qijuMethodUsesJieqiFa(paiPanType) ? QIJU_METHOD_OPTIONS : QIJU_METHOD_NONSHI_OPTIONS;
}

// 中门飞宫 / 混合盘四层的档名:奇门页、三式合一页、AI 挂载齿轮同一份(此前三式页少括注、齿轮半角括号,各写一套)
export const FEI_MEN_ZHONG_CAN_LABELS = Object.freeze({ on: '参与(九门含中,默认)', off: '不参与(八门跳中)' });

export const MIX_LAYER_LABELS = Object.freeze({ zhuan: '转宫（排宫）', fei: '飞宫（飞泊）' });

export function mixLayerDefaultLabel(dft){ return `默认（${dft === 'fei' ? '飞宫' : '转宫'}）`; }

// 旧数据迁移(单源):阴盘曾为「盘式」(school='阴盘'),现为「起局法」(qijuMethod='shuzi',报数定局) ——
// 盘式回落转盘、起局切阴盘(报数保留)。奇门页 / 三式合一页载档、无头重算、挂载齿轮基线同用;非旧值原样返回同一对象
export function migrateLegacyQimenSchool(options){
	if(!options || typeof options !== 'object' || options.school !== '阴盘'){ return options; }
	return { ...options, school: '转盘', qijuMethod: 'shuzi' };
}

// 下拉回显值:非时家/非刻家时,除「阴盘」外一律显示为「本家默认」(zhirun 占位)。
export function qijuMethodSelectValue(paiPanType, qijuMethod){
	if(qijuMethodUsesJieqiFa(paiPanType)){ return qijuMethod; }
	return qijuMethod === 'shuzi' ? 'shuzi' : 'zhirun';
}

// 置闰天数(传本差异·设置面板可调):超神累计阈值,至点超神距(dgap=二至日−其前最近上元符头)
//   ≥该值即置闰。默认9=主流口径(满9天即闰)。修(2026-08-02 置闰事故复盘):旧实现三处检查点在
//   上年大雪/芒种/本年大雪各自量距且比较符不一(>=/>/>),与 kinqimen fork 的「至点锚」在节气
//   间距≠15天的年份差±1天,临界年整段错一节气块——现统一按至点锚判闰(见 buildYinyangdunMap)。
export const ZHIRUN_LEAP_OPTIONS = [
	// short = 下拉闭合时框里显示的短名(字段名已是「置闰天数」,窄栏里全文要折三行);展开的列表里仍是全文
	{ value: 9, label: '置闰·超神满9天即闰（默认·主流）', short: '满9天即闰（默认）' },
	{ value: 8, label: '置闰·超神满8天即闰（从宽）', short: '满8天即闰（从宽）' },
	{ value: 10, label: '置闰·超神满10天才闰（从严）', short: '满10天才闰（从严）' },   // 第三口径:超神须超过 9 天(即≥10)才置闰
];

// 暗干六法(通行诸法;默认关=零回归):
//   dipan=八门对应地盘干(每宫暗干=本宫之门「本位宫」的地盘干);
//   zhishi_fei=时干加值使宫,十干自然序洛书飞布(阳顺阴逆;时干与值使宫地盘干相同=伏吟,时干入中再飞);
//   zhishi_zhuan=同起点同序,改八卦轮转布(中宫不入);
//   manpan_fei=满盘旋转飞(自地盘戊所在宫起「甲」,十干自然序洛书飞满盘);
//   tianpan_zhuan=时干加值使宫,按本局天盘干在八宫的实际排列整圈转(不按十干序重排;寄宫两干随宫一起走,甲时取旬首遁仪)。
export const ANGAN_MODE_OPTIONS = [
	{ value: 'off', label: '不用暗干（默认）' },
	{ value: 'dipan', label: '八门对应地盘干' },
	{ value: 'zhishi_fei', label: '时干加值使·飞布' },
	{ value: 'zhishi_zhuan', label: '时干加值使·转布' },
	{ value: 'manpan_fei', label: '满盘旋转飞' },
	{ value: 'tianpan_zhuan', label: '时干加值使·按天盘干序转' },
];

const TEN_GAN = '甲乙丙丁戊己庚辛壬癸'.split('');

const DOOR_HOME = { 休: '坎', 生: '艮', 伤: '震', 杜: '巽', 景: '离', 死: '坤', 惊: '兑', 开: '乾' };

const LUOSHU_GONG_SEQ = '坎坤震巽中乾兑艮离'.split('');   // 洛书 1-9 宫序(=EIGHT_GUA)

export function panAnGan(mode, ctx){
	const c = ctx || {};
	if(!mode || mode === 'off'){ return null; }
	const out = {};
	if(mode === 'dipan'){
		Object.keys(c.menGua || {}).forEach((g)=>{
			const door = String(c.menGua[g] || '').charAt(0);
			const home = DOOR_HOME[door];
			if(home && c.dipanGua && c.dipanGua[home]){ out[g] = c.dipanGua[home]; }
		});
		return out;
	}
	const isYang = c.yy === '阳';
	const step = isYang ? 1 : -1;
	if(mode === 'manpan_fei'){
		// 起宫=地盘戊所在宫;自「甲」起十干自然序,洛书飞满盘(含中),第十干与首宫重合成环。
		let startGong = '坎';
		Object.keys(c.dipanGua || {}).forEach((g)=>{ if(c.dipanGua[g] === '戊'){ startGong = g; } });
		const si = LUOSHU_GONG_SEQ.indexOf(startGong);
		for(let i = 0; i < 9; i++){
			const g = LUOSHU_GONG_SEQ[((si + step * i) % 9 + 9) % 9];
			out[g] = TEN_GAN[i % 10];
		}
		return out;
	}
	if(mode === 'tianpan_zhuan'){
		// 时干加值使门落宫为起点,依本局八宫天盘干的实际排列整圈转动:各宫暗干 = 天盘圈上对应位置那一宫的天盘干(寄宫连寄干)。
		//   例(阴三局,值使生门落坎,时干辛):天盘圈 坎己丙·艮癸·震丁·巽庚·离壬·坤戊·兑乙·乾辛 → 辛落坎,其后依次 己丙 / 癸 / 丁 …
		//   时干为甲 → 取旬首遁仪;值使落中 → 从寄宫起;时干只在中宫(飞盘)→ 按寄宫找。八卦轮按实际方位(不分阴阳顺逆:圈的排列本身已含遁向)。
		const tp = c.tianpanGua || {};
		const cellOf = (g)=>`${tp[g] || ''}${c.jiTian && c.jiTian.gua === g ? (c.jiTian.gan || '') : ''}`;
		let target = String(c.shiGan || '').charAt(0);
		if(target === '甲'){ target = String(c.shiDun || '').charAt(0); }
		if(!target){ return null; }
		const ring = CLOCKWISE_EIGHTGUA;
		let i0 = ring.findIndex((g)=>cellOf(g).indexOf(target) >= 0);
		if(i0 < 0 && String(tp['中'] || '').indexOf(target) >= 0){ i0 = ring.indexOf(c.jiGong || '坤'); }
		const zg = (c.zhishiGong && c.zhishiGong !== '中') ? c.zhishiGong : (c.jiGong || '坤');
		const z = ring.indexOf(zg);
		if(i0 < 0 || z < 0){ return null; }
		for(let k = 0; k < 8; k++){ out[ring[(z + k) % 8]] = cellOf(ring[(i0 + k) % 8]); }
		return out;
	}
	// zhishi_fei / zhishi_zhuan:时干加值使宫起,十干自然序续布
	const shiGan = String(c.shiGan || '').charAt(0);
	if(!shiGan){ return null; }
	let startGong = (c.zhishiGong && c.zhishiGong !== '中') ? c.zhishiGong : '中';
	// 伏吟判:值使宫地盘干===时干 → 时干入中宫再布
	if(c.dipanGua && c.dipanGua[startGong] === shiGan){ startGong = '中'; }
	const gi = TEN_GAN.indexOf(shiGan);
	if(mode === 'zhishi_fei'){
		const si = LUOSHU_GONG_SEQ.indexOf(startGong === '中' ? '中' : startGong);
		for(let i = 0; i < 9; i++){
			const g = LUOSHU_GONG_SEQ[((si + step * i) % 9 + 9) % 9];
			out[g] = TEN_GAN[(gi + i) % 10];
		}
		return out;
	}
	// 转布:八卦轮转(中不入);起宫若中则从寄宫起(ctx.jiGong,缺省坤=历史默认)
	const ring = isYang ? CLOCKWISE_EIGHTGUA : [...CLOCKWISE_EIGHTGUA].reverse();
	const ringStart = startGong === '中' ? (c.jiGong || '坤') : startGong;
	const seq = newList(ring, ringStart);
	for(let i = 0; i < 8; i++){ out[seq[i]] = TEN_GAN[(gi + i) % 10]; }
	return out;
}

// 暗支:暗干在「时柱所在旬」内的配支(旬内干支一一对应,确定映射;甲=旬首支)。
export function anZhiOf(anGan, timeGz){
	const head = getXunHead(timeGz || '甲子');
	if(!head || !anGan){ return ''; }
	const GAN10 = TEN_GAN;
	const ZHI12 = '子丑寅卯辰巳午未申酉戌亥'.split('');
	const hz = ZHI12.indexOf(head.charAt(1));
	const gidx = GAN10.indexOf(String(anGan).charAt(0));
	if(hz < 0 || gidx < 0){ return ''; }
	return ZHI12[(hz + gidx) % 12];
}

// 转盘八神预设:基串本为正统(阳遁勾陈朱雀/阴遁白虎玄武);现状默认=两遁恒虎玄(历史行为,零回归默认)。
export const GODS_PRESET_OPTIONS = [
	{ value: 'baihu_xuanwu', label: '两遁恒白虎玄武（默认）' },
	{ value: 'system', label: '按遁取神（阳勾陈朱雀·阴白虎玄武）' },
	{ value: 'gouchen_zhuque', label: '两遁恒勾陈朱雀' },
];

// 转盘八神名替换分派:baihu_xuanwu=勾雀→虎玄(默认=现状) / system=保基串(阳勾雀阴虎玄) / gouchen_zhuque=虎玄→勾雀。
export function applyGodsPreset(name, preset){
	const v = String(name || '');
	if(preset === 'system'){ return v; }
	if(preset === 'gouchen_zhuque'){ return v.replace(/虎/g, '勾').replace(/玄/g, '雀'); }
	return v.replace(/勾/g, '虎').replace(/雀/g, '玄');
}

// 中宫寄宫六档:转盘系当值符/值使落中宫时,从寄宫起排(飞盘九星含中宫,不受辖)。
//   kun=恒寄坤二(历史默认,零回归) / yang_gen_yin_kun=阳遁寄艮八·阴遁寄坤二 / yang_kun_yin_gen=阳遁寄坤二·阴遁寄艮八
//   (随遁寄宫古籍两说并存:一说阳艮阴坤,一说阳坤阴艮 ——「一本阳遁寄坤宫阴遁寄艮宫」「寄生西南,阴寄东北」)/ gen=恒寄艮八 /
//   siwei=按季寄四维(四立分界:立春起艮·立夏起巽·立秋起坤·立冬起乾,各领一季六气) /
//   bajie=按八节寄八宫(每节领三气:立春艮/春分震/立夏巽/夏至离/立秋坤/秋分兑/立冬乾/冬至坎)。
export const JIGONG_MODE_OPTIONS = [
	{ value: 'kun', label: '恒寄坤二宫（默认）' },
	{ value: 'yang_gen_yin_kun', label: '阳遁寄艮·阴遁寄坤' },
	{ value: 'yang_kun_yin_gen', label: '阳遁寄坤·阴遁寄艮' },
	{ value: 'gen', label: '恒寄艮八宫' },
	{ value: 'siwei', label: '按季寄四维（四立分界）' },
	{ value: 'bajie', label: '按八节寄八宫（一节三气）' },
];

const BAJIE_JIGONG = {
	立春: '艮', 雨水: '艮', 惊蛰: '艮',
	春分: '震', 清明: '震', 谷雨: '震',
	立夏: '巽', 小满: '巽', 芒种: '巽',
	夏至: '离', 小暑: '离', 大暑: '离',
	立秋: '坤', 处暑: '坤', 白露: '坤',
	秋分: '兑', 寒露: '兑', 霜降: '兑',
	立冬: '乾', 小雪: '乾', 大雪: '乾',
	冬至: '坎', 小寒: '坎', 大寒: '坎',
};

const SIWEI_JIGONG = {
	立春: '艮', 雨水: '艮', 惊蛰: '艮', 春分: '艮', 清明: '艮', 谷雨: '艮',
	立夏: '巽', 小满: '巽', 芒种: '巽', 夏至: '巽', 小暑: '巽', 大暑: '巽',
	立秋: '坤', 处暑: '坤', 白露: '坤', 秋分: '坤', 寒露: '坤', 霜降: '坤',
	立冬: '乾', 小雪: '乾', 大雪: '乾', 冬至: '乾', 小寒: '乾', 大寒: '乾',
};

// 移星换宫后的值符/值使标记两档:follow=标记随几何平移(历史默认);recalc=移后盘视为新局重解(星门名+落宫)。
export const SHIFT_ZHIFU_OPTIONS = [
	{ value: 'follow', label: '随盘平移（默认）' },
	{ value: 'recalc', label: '移后重定值符值使' },
];

// 寄宫解析:未知模式/未知节气一律回落坤二(历史默认=诚实兜底,绝不臆造)。yy 收 '阳'/'阴'(或 '阳遁'/'阴遁')。
export function resolveJiGong(mode, yy, jieqi){
	if(mode === 'gen'){ return '艮'; }
	if(mode === 'yang_gen_yin_kun'){ return String(yy || '').charAt(0) === '阳' ? '艮' : '坤'; }
	if(mode === 'yang_kun_yin_gen'){ return String(yy || '').charAt(0) === '阳' ? '坤' : '艮'; }
	if(mode === 'siwei'){ return SIWEI_JIGONG[normalizeJieqi(jieqi)] || '坤'; }
	if(mode === 'bajie'){ return BAJIE_JIGONG[normalizeJieqi(jieqi)] || '坤'; }
	return '坤';
}

export function jiGongOf(ext, yy){
	return resolveJiGong(ext && ext.jiGongMode, yy, ext && ext.jieqi);
}

// WP-A 盘式(排盘法):转盘=排宫(八神,八卦轮转,默认) / 飞盘=飞宫(九神,洛书飞泊含中宫) / 飞转=混合(星转·门飞·九神)。
// 锚点规则三派一致(值符随时干、值使随时辰、神随值符、阳顺阴逆),差别只在转环 vs 飞宫 vs 飞转结合。
export const SCHOOL_OPTIONS = [
	{ value: '转盘', label: '转盘（排宫）' },
	{ value: '飞盘', label: '飞盘（飞宫）' },
	{ value: '混合', label: '飞转（混合）' },
];

// 混合(飞转结合,专题§4.2):九星=转盘排宫(星寄坤2不入中、天禽)、八门=飞盘飞宫(可入中5)、神=飞盘九神(含中宫)。
// 旧数据 school='阴盘' 已改作「起局·数字(报数)」→ 盘式归 转盘(阴盘排盘≈转盘);载入时另把 qijuMethod 迁为 shuzi。
export function normalizeSchool(school){
	if(school === '飞盘' || school === '飛盤'){
		return '飞盘';
	}
	if(school === '混合' || school === '飞转' || school === '飛轉'){
		return '混合';
	}
	return '转盘';
}

export const KONG_MODE_OPTIONS = [
	{ value: 'day', label: '日空' },
	{ value: 'time', label: '时空' },
];

export const MA_MODE_OPTIONS = [
	{ value: 'day', label: '日马' },
	{ value: 'time', label: '时马' },
];

export const TIME_ALG_OPTIONS = [
	{ value: 0, label: '真太阳时' },
	{ value: 1, label: '直接时间' },
];

export const YIXING_OPTIONS = [
	{ value: 0, label: '原宫' },
	{ value: 1, label: '顺转一宫' },
	{ value: 2, label: '顺转二宫' },
	{ value: 3, label: '顺转三宫' },
	{ value: 4, label: '顺转四宫' },
	{ value: 5, label: '顺转五宫' },
	{ value: 6, label: '顺转六宫' },
	{ value: 7, label: '顺转七宫' },
];

// 命盘 / 事盘：保存去向。事盘→案例库 localCases（现状）；命盘→命盘库 localCharts（完整人命盘，跨技法自由使用，奇门设置存 payload.qimen）。
export const CHART_CATEGORY_OPTIONS = [
	{ value: 'shi', label: '事盘' },
	{ value: 'ming', label: '命盘' },
];
