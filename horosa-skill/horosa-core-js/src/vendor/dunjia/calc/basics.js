// 入参归一、干支与时辰、节气定位、三元与局名(各家起局共用的底层工具)
// 从 DunJiaCalc.js 按职责拆出(门面保留原导入路径与对外导出;读源码的检查读「子模块 + 门面」全集,见 scripts/source-sets.json)。
import { parseDateParts, civilWallMsOfStr, formatSignedDate, addDisplayYears } from '../../bazi/dateStrSafe.js';
import { buildLocalJieqiYearSeed } from '../../utils/localNongliAdapter.js';
import { GANZHI_INDEX_MAP, JIAZI, ZHI, GAN, JIEQI_CODE, SAN_YUAN_FU_TOU_SET, YANG_JIEQI, CNUMBER } from './tables.js';

export function normalizeNum(v, defVal = 0){
	const n = parseInt(v, 10);
	return Number.isNaN(n) ? defVal : n;
}

export function normalizeShiftPalace(v){
	const n = normalizeNum(v, 0);
	if(n < 0){
		return 0;
	}
	if(n > 7){
		return n % 8;
	}
	return n;
}

export function normalizeTimeAlg(value){
	return value === 1 ? 1 : 0;
}

export function getTimeAlgLabel(value){
	return normalizeTimeAlg(value) === 1 ? '直接时间' : '真太阳时';
}

export function normalizeText(s){
	if(!s){
		return '';
	}
	return `${s}`
		.replace(/穀/g, '谷')
		.replace(/滿/g, '满')
		.replace(/種/g, '种')
		.replace(/蟄/g, '蛰')
		.replace(/驚/g, '惊')
		.replace(/時/g, '时')
		.replace(/盤/g, '盘')
		.replace(/門/g, '门')
		.replace(/節/g, '节')
		.replace(/氣/g, '气')
		.replace(/閏/g, '闰')
		.replace(/馬/g, '马')
		.replace(/飛/g, '飞')
		.replace(/長/g, '长')
		.replace(/運/g, '运')
		.replace(/處/g, '处')
		.replace(/陰/g, '阴')
		.replace(/陽/g, '阳')
		.replace(/傷/g, '伤')
		.replace(/開/g, '开')
		.replace(/沖/g, '冲')
		.replace(/輔/g, '辅')
		.replace(/離/g, '离')
		.replace(/兌/g, '兑')
		.replace(/乾/g, '乾')
		.trim();
}

export function normalizeGanZhi(gz){
	const t = normalizeText(gz);
	return t.substring(0, 2);
}

export function normalizeJieqi(jieqi){
	return normalizeText(jieqi).substring(0, 2);
}

export function getOptionLabel(list, value){
	const one = list.find((item)=>item.value === value);
	// 缺省值兜底为空串:此前 `${undefined}` 字符串化成「undefined」脏字样直入快照(如「命式：undefined」),
	// 且 truthy 穿透一切 if 拦截——空串既能被 || 兜底又能被 if 拦。
	if(one){ return one.label; }
	return (value === undefined || value === null) ? '' : `${value}`;
}

export function getGanzhiGan(gz){
	return normalizeGanZhi(gz).substring(0, 1);
}

export function getGanzhiZhi(gz){
	return normalizeGanZhi(gz).substring(1, 2);
}

export function parseDateTime(fields){
	if(!fields || !fields.date || !fields.time){
		return null;
	}
	const dateStr = fields.date.value.format('YYYY-MM-DD');
	const timeStr = fields.time.value.format('HH:mm:ss');
	// 带符号年安全解析(单源 parseDateParts):公元前 '-500-06-15' 此前按 '-' 切成 ['', '500', '06', '15'] →
	// 年 0/月 500/日 6 → 年家恒中元阴四、置闰/无闰种子查不到退拆补、日家半年键非法。
	const dp = parseDateParts(dateStr);
	const tparts = timeStr.split(':');
	if(!dp || tparts.length < 2){
		return null;
	}
	const year = dp.year;
	const month = dp.month;
	const day = dp.day;
	const hour = normalizeNum(tparts[0], 0);
	const minute = normalizeNum(tparts[1], 0);
	const second = normalizeNum(tparts[2], 0);
	return {
		year,
		month,
		day,
		hour,
		minute,
		second,
		dateStr,
		timeStr,
	};
}

function parseDateTimeText(rawText){
	const text = normalizeText(rawText);
	if(!text){
		return null;
	}
	const normalized = text.replace('T', ' ').replace('Z', ' ').trim();
	const m = normalized.match(/([-+]?\d{1,6})[/-](\d{1,2})[/-](\d{1,2})\s+(\d{1,2}):(\d{2})(?::(\d{2}))?/);
	if(!m){
		return null;
	}
	return {
		year: normalizeNum(m[1], 0),
		month: normalizeNum(m[2], 1),
		day: normalizeNum(m[3], 1),
		hour: normalizeNum(m[4], 0),
		minute: normalizeNum(m[5], 0),
		second: normalizeNum(m[6], 0),
	};
}

export function resolveCalcDateTime(dateParts, nongli, opts, context){
	if(normalizeTimeAlg(opts && opts.timeAlg) === 0){
		const solarParsed = parseDateTimeText(
			(nongli && nongli.birth) || (context && context.displaySolarTime) || ''
		);
		if(solarParsed){
			return {
				...dateParts,
				...solarParsed,
			};
		}
	}
	return dateParts;
}

export function getGanzhiIndex(gz){
	const key = normalizeGanZhi(gz);
	const idx = GANZHI_INDEX_MAP[key];
	return idx >= 0 ? idx : 0;
}

export function getXunHead(gz){
	const idx = getGanzhiIndex(gz);
	return JIAZI[Math.floor(idx / 10) * 10] || '甲子';
}

export function prevGanZhi(gz){
	const idx = getGanzhiIndex(gz);
	return JIAZI[(idx + 59) % 60];
}

function getHourBranch(hour){
	if(hour === 23 || hour === 0){
		return '子';
	}
	const idx = Math.floor((hour + 1) / 2) % 12;
	return ZHI[idx];
}

export function getHourGanZhi(dayGanZhi, hour){
	const dayGan = normalizeGanZhi(dayGanZhi).substring(0, 1);
	const branch = getHourBranch(hour);
	const startGan = (function getStartGan(){
		if('甲己'.includes(dayGan)) return '甲';
		if('乙庚'.includes(dayGan)) return '丙';
		if('丙辛'.includes(dayGan)) return '戊';
		if('丁壬'.includes(dayGan)) return '庚';
		return '壬';
	})();
	const ganIdx = GAN.indexOf(startGan);
	const zhiIdx = ZHI.indexOf(branch);
	return `${GAN[(ganIdx + zhiIdx) % 10]}${branch}`;
}

function getCurrentJieqi(nongli){
	const jq = normalizeJieqi(nongli && nongli.jieqi ? nongli.jieqi : '');
	if(jq){
		return jq;
	}
	const delta = `${(nongli && nongli.jiedelta) || ''}`;
	const idxAfter = delta.indexOf('后第');
	if(idxAfter > 0){
		return normalizeJieqi(delta.substring(0, idxAfter));
	}
	const idxBefore = delta.indexOf('前第');
	if(idxBefore > 0){
		return normalizeJieqi(delta.substring(0, idxBefore));
	}
	return '';
}

// 起盘时刻 / 节气种子时刻 → 同一条民用历墙钟轴的毫秒(dateStrSafe.civilWallMsOfStr 单源;与择日扫描同轴)。
// 种子 time 串与此刻都是民用历标签(1582 以前儒略历、历史纪年):按外推格里历解析时,儒略闰日 02-29 与 03-01
// 落在同一毫秒(02-29 12:00 会把 03-01 05:00 才交的节气当成已交);按本机钟面解析还随机器夏令时差一小时。
// 不用 new Date(年, …):公元 1–99 年会被当成 19xx。
function seedAxisMsOfText(text){
	return civilWallMsOfStr(`${text === undefined || text === null ? '' : text}`);
}

export function seedAxisMsOf(dateParts){
	const pad = (n)=>String(normalizeNum(n, 0)).padStart(2, '0');
	const date = formatSignedDate(Number(dateParts.year), normalizeNum(dateParts.month, 1), normalizeNum(dateParts.day, 1));
	return seedAxisMsOfText(`${date} ${pad(dateParts.hour)}:${pad(dateParts.minute)}:00`);
}

// 「≤ 此刻的最晚节气」(扫 y-1/y/y+1 三年种子,含中气;时刻感知)。种子 time 为 'YYYY-MM-DD HH:mm:ss'(后端 /jieqi/year 与本地
// buildLocalJieqiYearSeed 同形),与 dateParts 同按本机墙钟解析比较(茅山链原有口径,抽为共用)。无种子/无命中 → null。
export function latestSeedTermAt(dateParts, yearSeeds){
	if(!yearSeeds || !dateParts || !Number.isFinite(Number(dateParts.year))){ return null; }
	const now = seedAxisMsOf(dateParts);
	if(!Number.isFinite(now)){ return null; }
	let bestJq = null;
	let bestTime = null;
	[addDisplayYears(dateParts.year, -1), Number(dateParts.year), addDisplayYears(dateParts.year, 1)].forEach((y)=>{
		const ys = yearSeeds[y];
		if(!ys){ return; }
		Object.keys(ys).forEach((term)=>{
			const s = ys[term];
			if(s && s.time){
				const t = seedAxisMsOfText(s.time);
				if(Number.isFinite(t) && t <= now && (bestTime === null || t > bestTime)){
					bestTime = t;
					bestJq = term;
				}
			}
		});
	});
	return (bestJq !== null && bestTime !== null) ? { term: bestJq, time: bestTime } : null;
}

// 当前节气(二十四节气·含中气)解析单源。后端 /nongli/time 的 nongli.jieqi 只在「当日交节」那天有值(NongliHelper
// byDate),其余日子为 null;jiedelta「立夏后第19天」只给节令(节),不含中气 → 旧 getCurrentJieqi 在每个节的后半(过中气后)
// 把节当节气用,拆补/报数/无种子回退的局与阴阳遁整段错(如 2026-05-24 出「立夏上元」实为「小满上元」)。此前转盘恒走后端
// 被遮蔽,飞盘/混合/刻家与三式本地路由一直受影响。解析序:上下文种子(后端精算)→ 本地种子(lunar-javascript,确定性)→
// nongli.jieqi(当日交节)→ jiedelta 节令(最末兜底,仅在种子不可得时)。
export function resolveCurrentJieqi(nongli, dateParts, context, zone){
	const seeds = context && context.jieqiYearSeeds ? context.jieqiYearSeeds : null;
	let hit = latestSeedTermAt(dateParts, seeds);
	if(!hit && dateParts && Number.isFinite(Number(dateParts.year))){
		const local = {};
		[addDisplayYears(dateParts.year, -1), Number(dateParts.year), addDisplayYears(dateParts.year, 1)].forEach((y)=>{
			let one = null;
			try{ one = buildLocalJieqiYearSeed(y, zone); }catch(e){ one = null; }
			if(one){ local[y] = one; }
		});
		hit = latestSeedTermAt(dateParts, local);
	}
	if(hit && hit.term){
		const term = normalizeJieqi(hit.term);
		if(JIEQI_CODE[term]){ return term; }
	}
	return getCurrentJieqi(nongli || {});
}

export function resolveFuTouByBacktrack(dayGanZhi){
	let current = normalizeGanZhi(dayGanZhi || '甲子');
	for(let i=0; i<60; i++){
		if(SAN_YUAN_FU_TOU_SET.has(current)){
			return current;
		}
		current = prevGanZhi(current);
	}
	return getXunHead(dayGanZhi || '甲子');
}

export function findYuan(dayGanZhi){
	const idx = getGanzhiIndex(dayGanZhi) % 15;
	if(idx < 5){
		return '上元';
	}
	if(idx < 10){
		return '中元';
	}
	return '下元';
}

export function qimenJuNameChaibu(jieqi, dayGanZhi){
	const jq = normalizeJieqi(jieqi);
	const yy = YANG_JIEQI.includes(jq) ? '阳遁' : '阴遁';
	const yuan = findYuan(dayGanZhi);
	const code = JIEQI_CODE[jq] || '一七四';
	const yuanIdx = yuan === '上元' ? 0 : (yuan === '中元' ? 1 : 2);
	return `${yy}${code[yuanIdx]}局${yuan}`;
}

export function juNumberToCn(num){
	const idx = Math.min(9, Math.max(1, normalizeNum(num, 1))) - 1;
	return CNUMBER[idx];
}

export function buildQmjuByMeta(yinYangDun, juShu, sanYuan){
	const yy = `${yinYangDun || ''}`.indexOf('阴') >= 0 ? '阴遁' : '阳遁';
	return `${yy}${juNumberToCn(juShu)}局${sanYuan || '上元'}`;
}

export function isYangDunJieqi(jieqi){
	return YANG_JIEQI.indexOf(normalizeJieqi(jieqi)) >= 0;
}
