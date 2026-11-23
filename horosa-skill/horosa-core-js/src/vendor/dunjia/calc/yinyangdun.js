// 阴阳遁局表与置闰诸法(拆补 / 置闰 / 无闰 / 茅山)
// 从 DunJiaCalc.js 按职责拆出(门面保留原导入路径与对外导出;读源码的检查读「子模块 + 门面」全集,见 scripts/source-sets.json)。
import { dayNumOfDateKey, dateKeyOfDayNum, parseDateKey, dateKeyOf } from '../../bazi/dateStrSafe.js';
import { JIEQI_NAME, YINYANGDUN_CACHE, JIAZI, MAX_YINYANGDUN_CACHE, JIEQI2JU, YANG_JIEQI, JIEQI_CODE } from './tables.js';
import { normalizeNum, normalizeGanZhi, getGanzhiIndex, qimenJuNameChaibu, findYuan, seedAxisMsOf, latestSeedTermAt } from './basics.js';

// 紧凑日期键 ⇄ 日序数:经 dateStrSafe 民用历单源(公元前前导负号、1–6 位年;1582 以前儒略历)。
// 公元 1583–9999 年与旧 Date.UTC 算法逐值相同;旧算法对公元前 / 0–99 年 / 五位年键会折叠或越界。
export function keyToUtcDay(key){
	return dayNumOfDateKey(key);
}

function utcDayToKey(daynum){
	return dateKeyOfDayNum(daynum);
}

function nextJieqi(name){
	const idx = JIEQI_NAME.indexOf(name);
	if(idx < 0){
		return '冬至';
	}
	return JIEQI_NAME[(idx + 1) % JIEQI_NAME.length];
}

function buildYinyangdunMap(year, yearSeeds, noLeap, leapThresholdDays){
	const prev = yearSeeds ? yearSeeds[year - 1] : null;
	const curr = yearSeeds ? yearSeeds[year] : null;
	if(!prev || !curr || !prev.大雪 || !curr.芒种 || !curr.大雪){
		return null;
	}
	const leapDays = normalizeNum(leapThresholdDays, 9);   // 置闰超神天数阈值(可配,默认9=现行口径,字节不漂)
	// WP-C 无闰法:同超神接气但永不置闰。noLeap/非默认 leapDays 进缓存键 → 默认(置闰·9日)路径键不变、字节不漂。
	// 至点种子直捡(2026-08-02 二次修):lunar-javascript 年表键「冬至」属上年12月(本年12月冬至
	// 在表里键作 'DONG_ZHI',种子未采)——不赌表语义,按「目标公历年+月份窗」从三年种子里直捡:
	// 冬至=目标年12月、夏至=目标年6月。捡不到(域外等)时各判定点回退旧法。
	const pickSolstice = (term, targetYear, monthWant)=>{
		for(let k=-1; k<=1; k++){
			const ys = yearSeeds ? yearSeeds[targetYear + k] : null;
			const s = ys && ys[term];
			const dk = s && s.dateKey ? parseDateKey(s.dateKey) : null;
			if(dk && dk.year === targetYear && dk.month === monthWant){
				return s;
			}
		}
		return null;
	};
	const dzPrevSeed = pickSolstice('冬至', year - 1, 12);   // 上年12月冬至(管链首·上年大雪段)
	const xzSeed = pickSolstice('夏至', year, 6);            // 本年6月夏至(管芒种段)
	const dzCurrSeed = pickSolstice('冬至', year, 12);       // 本年12月冬至(管本年大雪段)
	const seedSig = [
		year,
		prev.大雪.dateKey || '',
		prev.大雪.dayGanzhi || '',
		curr.芒种.dateKey || '',
		curr.芒种.dayGanzhi || '',
		curr.大雪.dateKey || '',
		curr.大雪.dayGanzhi || '',
		/* 至点锚种子(2026-08-02 二次修)进缓存键:置闰判定改锚二至后,键必须随至点种子变 */
		(dzPrevSeed && dzPrevSeed.dateKey) || '',
		(dzPrevSeed && dzPrevSeed.dayGanzhi) || '',
		(xzSeed && xzSeed.dateKey) || '',
		(xzSeed && xzSeed.dayGanzhi) || '',
		(dzCurrSeed && dzCurrSeed.dateKey) || '',
		(dzCurrSeed && dzCurrSeed.dayGanzhi) || '',
	].join('|') + (noLeap ? '|noleap' : '') + (leapDays !== 9 ? `|leap${leapDays}` : '');
	if(YINYANGDUN_CACHE.has(seedSig)){
		return YINYANGDUN_CACHE.get(seedSig);
	}
	const ret = {};

	const daxueStart = prev.大雪.dateKey;
	const daxueRizhu = normalizeGanZhi(prev.大雪.dayGanzhi || '甲子');
	let daxueIndex = getGanzhiIndex(daxueRizhu);
	let futouIndex = Math.floor(daxueIndex / 15) * 15;
	let tday = keyToUtcDay(daxueStart);
	let rizhuIndex = daxueIndex;

	for(let i=daxueIndex; i<futouIndex + 15; i++){
		ret[utcDayToKey(tday)] = `大雪${JIAZI[rizhuIndex]}`;
		tday += 1;
		rizhuIndex = (rizhuIndex + 1) % 60;
	}

	// 至锚置闰(2026-08-02 二次修,对齐 kinqimen fork jieqi.py zhirun_jieqi 的「至点锚」框架):
	// dgap = 二至日 − 其前最近上元符头(严格在前;即至日日柱序%15,0 作 15);dgap≥阈值 → 该至前
	// 插入闰(重复大雪/芒种三元)。链上表现为:至的上元块起 = F*(至) + (闰?15:0),默认步进若未到位
	// 则补一块重复节气。旧法在上年大雪/芒种/本年大雪三点各自量距(且比较符 >=/>/> 不一),与至点
	// 锚在节气间距≠15天的年份差±1天:1996芒种类临界年漏闰(阴七/应阴八·客诉案),1950/1956 类
	// 临界年与 Python 真值整段错一节气块(全域平价扫描 720+ 差异)。三处判定必须永远同锚同阈。
	const solsticeAnchorStart = (seed)=>{
		if(!seed || !seed.dateKey || !seed.dayGanzhi){ return null; }
		const day = keyToUtcDay(seed.dateKey);
		if(!Number.isFinite(day)){ return null; }
		const off = getGanzhiIndex(normalizeGanZhi(seed.dayGanzhi)) % 15;
		const dgap = off === 0 ? 15 : off;
		return day - dgap + ((!noLeap && dgap >= leapDays) ? 15 : 0);
	};

	let jieqiCur = '冬至';
	const dzPrevStart = solsticeAnchorStart(dzPrevSeed);
	if(dzPrevStart !== null){
		if(!noLeap && tday < dzPrevStart){ jieqiCur = '大雪'; }
	}else if(!noLeap && daxueIndex - futouIndex >= leapDays){   // 冬至种子缺失时的旧法兜底
		jieqiCur = '大雪';
	}

	let jieqiDays = 0;
	let mangzhongDay = null;
	for(let i=0; i<300; i++){
		ret[utcDayToKey(tday)] = `${jieqiCur}${JIAZI[rizhuIndex]}`;
		tday += 1;
		rizhuIndex = (rizhuIndex + 1) % 60;
		jieqiDays += 1;
		if(jieqiDays === 15){
			jieqiDays = 0;
			jieqiCur = nextJieqi(jieqiCur);
			if(jieqiCur === '芒种'){
				mangzhongDay = tday;
				for(let j=0; j<15; j++){
					ret[utcDayToKey(tday)] = `${jieqiCur}${JIAZI[rizhuIndex]}`;
					tday += 1;
					rizhuIndex = (rizhuIndex + 1) % 60;
				}
				break;
			}
		}
	}

	jieqiCur = '夏至';
	const xzStart = solsticeAnchorStart(xzSeed);   // 至点锚:夏至上元块应起于此(2026-08-02 二次修)
	if(xzStart !== null){
		if(!noLeap && tday < xzStart){ jieqiCur = '芒种'; }
	}else{
		const mangzhongStartDay = keyToUtcDay(curr.芒种.dateKey);   // 夏至种子缺失时的旧法兜底
		if(!noLeap && Number.isFinite(mangzhongStartDay) && mangzhongDay !== null && mangzhongStartDay >= mangzhongDay + leapDays){
			jieqiCur = '芒种';
		}
	}

	jieqiDays = 0;
	let daxueDay = null;
	for(let i=0; i<300; i++){
		ret[utcDayToKey(tday)] = `${jieqiCur}${JIAZI[rizhuIndex]}`;
		tday += 1;
		rizhuIndex = (rizhuIndex + 1) % 60;
		jieqiDays += 1;
		if(jieqiDays === 15){
			jieqiDays = 0;
			jieqiCur = nextJieqi(jieqiCur);
			if(jieqiCur === '大雪'){
				daxueDay = tday;
				for(let j=0; j<15; j++){
					ret[utcDayToKey(tday)] = `${jieqiCur}${JIAZI[rizhuIndex]}`;
					tday += 1;
					rizhuIndex = (rizhuIndex + 1) % 60;
				}
				break;
			}
		}
	}

	jieqiCur = '冬至';
	const dzStart = solsticeAnchorStart(dzCurrSeed);   // 至点锚:本年冬至上元块应起于此(2026-08-02 二次修)
	if(dzStart !== null){
		if(!noLeap && tday < dzStart){ jieqiCur = '大雪'; }
	}else{
		const daxueStartDay = keyToUtcDay(curr.大雪.dateKey);   // 冬至种子缺失时的旧法兜底
		if(!noLeap && Number.isFinite(daxueStartDay) && daxueDay !== null && daxueStartDay >= daxueDay + leapDays){
			jieqiCur = '大雪';
		}
	}

	jieqiDays = 0;
	for(let i=0; i<300; i++){
		ret[utcDayToKey(tday)] = `${jieqiCur}${JIAZI[rizhuIndex]}`;
		tday += 1;
		rizhuIndex = (rizhuIndex + 1) % 60;
		jieqiDays += 1;
		if(jieqiDays === 15){
			jieqiDays = 0;
			jieqiCur = nextJieqi(jieqiCur);
			if(jieqiCur === '立春'){
				ret[utcDayToKey(tday)] = `${jieqiCur}${JIAZI[rizhuIndex]}`;
				break;
			}
		}
	}
	if(YINYANGDUN_CACHE.has(seedSig)){
		YINYANGDUN_CACHE.delete(seedSig);
	}
	YINYANGDUN_CACHE.set(seedSig, ret);
	if(YINYANGDUN_CACHE.size > MAX_YINYANGDUN_CACHE){
		const firstKey = YINYANGDUN_CACHE.keys().next().value;
		if(firstKey){
			YINYANGDUN_CACHE.delete(firstKey);
		}
	}
	return ret;
}

// 置闰/无闰查表单源:算 dkey(含 after23NewDay=1 的 23 时进位)→ 查 buildYinyangdunMap 逐日表,
// 返回「节气+日柱」标签(如「小暑己酉」)或 null。qimenJuNameZhirun 与 qimenDingjuJieqi 共用,
// 保证"定局所用节气"与"对外报的定局节气"永远同一次查表口径(2026-08-02 缺陷②修)。
function lookupYinyangdunLabel(dateParts, yearSeeds, after23NewDay, noLeap, leapThresholdDays){
	const yyd = buildYinyangdunMap(dateParts.year, yearSeeds, noLeap, leapThresholdDays);
	if(!yyd){
		return null;
	}
	let dkey = dateKeyOf(dateParts.year, dateParts.month, dateParts.day);
	// 用户语义(拍板,字面直觉版): after23NewDay=1「23点算第二天」时 hour==23 进位到次日;after23NewDay=0 守今。
	if(dateParts.hour === 23 && (after23NewDay === 1 || after23NewDay === '1' || after23NewDay === true)){
		dkey = utcDayToKey(keyToUtcDay(dkey) + 1);
	}
	const jqrz = yyd[dkey];
	if(!jqrz || jqrz.length < 4){
		return null;
	}
	return jqrz;
}

// 定局节气(置闰/无闰):超神时定局节气≠曆法节气,展示/快照必须用它,否则出现「阳遁七局中元+
// 大雪中元」式矛盾串(缺陷②)。查不到返回 ''(调用方回退曆法节气,与 qimenJuNameZhirun 退拆补对齐)。
export function qimenDingjuJieqi(dateParts, yearSeeds, after23NewDay, noLeap, leapThresholdDays){
	const jqrz = lookupYinyangdunLabel(dateParts, yearSeeds, after23NewDay, noLeap, leapThresholdDays);
	return jqrz ? jqrz.substring(0, 2) : '';
}

export function qimenJuNameZhirun(dateParts, dayGanzhi, yearSeeds, fallbackJieqi, after23NewDay, noLeap, leapThresholdDays){
	const jqrz = lookupYinyangdunLabel(dateParts, yearSeeds, after23NewDay, noLeap, leapThresholdDays);
	if(!jqrz){
		return qimenJuNameChaibu(fallbackJieqi || '', dayGanzhi);
	}
	const jieqi = jqrz.substring(0, 2);
	const yuan = findYuan(dayGanzhi);
	const yuanId = yuan === '上元' ? 0 : (yuan === '中元' ? 1 : 2);
	const code = JIEQI2JU[jieqi] || '一七四阳';
	const yy = code.substring(code.length - 1);
	return `${yy}遁${code.substring(yuanId, yuanId + 1)}局${yuan}`;
}

// WP-C 无闰法(资料§5.4):同超神接气但 noLeap=true 永不置闰(置闰天数对无闰无效,透传仅为签名一致)。
export function qimenJuNameWurun(dateParts, dayGanzhi, yearSeeds, fallbackJieqi, after23NewDay, leapThresholdDays){
	return qimenJuNameZhirun(dateParts, dayGanzhi, yearSeeds, fallbackJieqi, after23NewDay, true, leapThresholdDays);
}

// WP-C 茅山布局法(资料§5.3):交节时刻为唯一锚点,足时辰顺推三元,不问符头、不置闰。
// shichen=floor((now−交节时刻)/2时);yuanIdx=min(floor((shichen mod180)/60),2)。缺交节种子→退拆补。
// WP-C 茅山布局法(专题§2.1):以「交节时刻」为唯一锚,何时交节即从该刻起用该节气上元,足60时辰(=5日)进一元,
//   满3元(下元足60时辰)即接下一节气上元(即便下一节气交节尚差零点几日也照接);不用符头、不置闰。
//   须任意节气的精确交节时刻——故扫全24种子取「≤now 的最晚节气」为当前节气(非用节令jq,否则中气如冬至取不到、退拆补)。
export function qimenJuNameMaoshan(dateParts, jieqi, yearSeeds, dayGanzhi){
	if(yearSeeds && dateParts){
		const now = seedAxisMsOf(dateParts);
		const hit = latestSeedTermAt(dateParts, yearSeeds);   // 抽为共用 helper(与 T-548 节气解析同源),逐字同义
		const bestJq = hit ? hit.term : null;
		const bestTime = hit ? hit.time : null;
		if(bestJq !== null && bestTime !== null){
			const shichen = Math.floor((now - bestTime) / (2 * 60 * 60 * 1000));
			if(shichen >= 0){
				const yuanRaw = Math.floor(shichen / 60);          // 60时辰=5日=一元
				let jqCur = bestJq;
				let yuanIdx = yuanRaw;
				if(yuanRaw >= 3){ jqCur = nextJieqi(bestJq); yuanIdx = 0; }   // 满3元→进下一节气上元
				const yy = YANG_JIEQI.indexOf(jqCur) >= 0 ? '阳遁' : '阴遁';
				const code = JIEQI_CODE[jqCur] || '一七四';
				return `${yy}${code[yuanIdx]}局${['上元', '中元', '下元'][yuanIdx]}`;
			}
		}
	}
	return qimenJuNameChaibu(jieqi, dayGanzhi);
}
