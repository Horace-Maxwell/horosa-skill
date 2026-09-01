// [Z5·六壬择日] 本地供数层:chartObj-lite 合成(替代后端 /liureng 响应的排盘消费面)。
// 判定单源:排盘=LiuRengMain 加性导出的 buildLiuRengLayout/buildKeData/buildSanChuanData
// (与主六壬页同一函数,涉害 byte-perfect 三传在 ChuangChart);此处只产它们的输入:
// ①四柱 nongli(buildLocalNongliLite 同源) ②月将(两档:中气=太阳过宫,与主页日躔星历
// 同定义,lunar-js 中气时刻天文精确,仅换将时刻分钟级窗差;节气=按节提前换将流派)
// ③昼夜(标准日出方程,与后端星历地平判秒级差;|lat|≥65° 高纬/极圈回退卯酉并标注)
// ④神煞(fillLrGods/fillLrXun=Java LiuReng.fillGods/fillXun 逐构 JS 化,表=liurengGodsData
//   生成物,liurengGodsParity 直读 Java 资源机械同源)。
import { buildLocalNongliLite } from '../../bazi/baziLunarLocal.js';
import { zoneOffsetMinutes } from './hourlyScanEngine.js';
import { defaultAfter23NewDay } from '../../bazi/dayBoundary.js';
import { LR_GODS_RULES, LR_TAISUI_GODS } from './liurengGodsData.js';

export const LR_ZHI12 = ['子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥'];
const STEMS = ['甲', '乙', '丙', '丁', '戊', '己', '庚', '辛', '壬', '癸'];

// ── 神煞(Java LiuReng.fillGods/fillXun 同构) ──
export function findLrGods(key, names){
	const res = {};
	names.forEach((n)=>{
		const rule = LR_GODS_RULES[n];
		res[n] = (rule && rule[key]) ? rule[key].slice(0) : null;
	});
	return res;
}
export function findLrTaiSuiGods(yearZhi){
	const yi = LR_ZHI12.indexOf(yearZhi);
	const out = { taisui1: {}, taisui2: {}, taisui3: {} };
	if(yi < 0){ return out; }
	for(let i = 0; i < 12; i++){
		const zi = LR_ZHI12[i];
		const idx = ((i - yi) % 12 + 12) % 12;
		[['taisui1', LR_TAISUI_GODS.gods1], ['taisui2', LR_TAISUI_GODS.gods2], ['taisui3', LR_TAISUI_GODS.gods3]].forEach(([k, arr])=>{
			if(arr[idx]){ out[k][arr[idx]] = zi; }
		});
	}
	return out;
}
export function fillLrXun(dayGanZi){
	const gan = dayGanZi.charAt(0);
	const zhi = dayGanZi.charAt(1);
	const gi = STEMS.indexOf(gan);
	const zi = LR_ZHI12.indexOf(zhi);
	if(gi < 0 || zi < 0){ return null; }
	let n = -1;
	for(let i = 0; i < 60; i++){ if(i % 10 === gi && i % 12 === zi){ n = i; break; } }
	if(n < 0){ return null; }
	const xunIdx = Math.floor(n / 10);
	const first = xunIdx * 10;
	const jz = (k)=>`${STEMS[k % 10]}${LR_ZHI12[k % 12]}`;
	const dingIdx = n + (3 - gi);	// 丁=STEMS[3]
	const kong1 = LR_ZHI12[(first + 10) % 12];
	const kong2 = LR_ZHI12[(first + 11) % 12];
	return {
		旬丁: jz(dingIdx),
		遁丁: jz(dingIdx).charAt(1),
		旬空: `${kong1}${kong2}`,
		旬首: jz(first),
		旬尾: jz(first + 9),
	};
}
// LiuReng.fillGods 同构:五组神煞(年支太岁环/月支二德一破/日干三神/日支七煞/日干二德+日支驿马)。
export function fillLrGods(fc){
	const gz = (k)=>(fc[k] && (fc[k].ganzi || fc[k].ganZhi)) || '';
	const dayGan = gz('day').charAt(0);
	const dayZhi = gz('day').charAt(1);
	const godsYear = findLrTaiSuiGods(gz('year').charAt(1));
	const godsMonth = findLrGods(gz('month').charAt(1), ['天德', '月德', '月破']);
	const godsGan = findLrGods(dayGan, ['长生(水土同)', '干墓(水土同)', '游都']);
	const godsZi = findLrGods(dayZhi, ['金神', '亡神', '劫煞', '咸池', '华盖', '支将', '日破']);
	const gods = findLrGods(dayGan, ['日德', '禄勋']);
	Object.assign(gods, findLrGods(dayZhi, ['驿马']));
	return { gods, godsZi, godsGan, godsMonth, godsYear };
}

// ── 月将(两档) ──
// 中气档(默认;=主页日躔太阳过宫的本地精确实现):中气名→月将支(太阳入宫)。
export const YUE_BY_ZHONGQI = {
	雨水: '亥', 春分: '戌', 谷雨: '酉', 小满: '申', 夏至: '未', 大暑: '午',
	处暑: '巳', 秋分: '辰', 霜降: '卯', 小雪: '寅', 冬至: '丑', 大寒: '子',
};
// 节气档(流派:按节提前换将):节名→月将支。
export const YUE_BY_JIEQI = {
	立春: '亥', 惊蛰: '戌', 清明: '酉', 立夏: '申', 芒种: '未', 小暑: '午',
	立秋: '巳', 白露: '辰', 寒露: '卯', 立冬: '寅', 大雪: '丑', 小寒: '子',
};

// ── 昼夜(标准日出方程;分昼夜=日出后~日落前) ──
// 与后端星历地平判同定义(几何日出,太阳中心过地平);大气折射差≈2-3 分钟窗。
export function isDiurnalLocal(dateStr, timeStr, gpsLat, gpsLon, zoneHours){
	const lat = Number(gpsLat);
	const lon = Number(gpsLon);
	// 🔴 回退阈值 65°(曾 66.5°=极圈线):65.7-66.5° 带夏至前后夜长 <1h(66.1°N 实测
	// ≈24 分钟),小时采样两端同「昼」→夜窗整段被吞、贵人环错(外壳明文迁移前提
	// 「昼或夜短于 1 小时须强制卯酉档」,审查实抓未强制)。65° 以内夜恒 >1h。
	if(!Number.isFinite(lat) || !Number.isFinite(lon) || Math.abs(lat) >= 65.0){
		// 高纬/极圈:回退卯酉近似(卯05-酉19 边界按当地钟表;工作台标注)
		const hh = Number(`${timeStr}`.slice(0, 2));
		return hh >= 5 && hh < 19;
	}
	const [y, m, d] = `${dateStr}`.split('-').map(Number);
	const [hh, mm] = `${timeStr}`.split(':').map(Number);
	// 当日太阳赤纬(简化 Cooper 公式,±0.5° 内)+均时差(分)
	const n0 = Math.floor((Date.UTC(y, m - 1, d) - Date.UTC(y, 0, 1)) / 86400000) + 1;
	const gamma = 2 * Math.PI / 365 * (n0 - 1 + (hh - 12) / 24);
	const decl = 0.006918 - 0.399912 * Math.cos(gamma) + 0.070257 * Math.sin(gamma)
		- 0.006758 * Math.cos(2 * gamma) + 0.000907 * Math.sin(2 * gamma)
		- 0.002697 * Math.cos(3 * gamma) + 0.00148 * Math.sin(3 * gamma);
	const eot = 229.18 * (0.000075 + 0.001868 * Math.cos(gamma) - 0.032077 * Math.sin(gamma)
		- 0.014615 * Math.cos(2 * gamma) - 0.040849 * Math.sin(2 * gamma));
	const latR = lat * Math.PI / 180;
	// 标准日出角 zenith=90.833°(太阳上边缘+大气折射)——与民用/星历日出对齐(几何中心版偏晚 ~4 分)
	const zen = 90.833 * Math.PI / 180;
	const cosH = (Math.cos(zen) - Math.sin(latR) * Math.sin(decl)) / (Math.cos(latR) * Math.cos(decl));
	if(cosH <= -1){ return true; }	// 极昼
	if(cosH >= 1){ return false; }	// 极夜
	const ha = Math.acos(cosH) * 180 / Math.PI;	// 半昼弧(度)
	const solarNoonMin = 720 - 4 * (lon - zoneHours * 15) - eot;	// 当地钟表分
	const riseMin = solarNoonMin - ha * 4;
	const setMin = solarNoonMin + ha * 4;
	const nowMin = hh * 60 + mm;
	return nowMin >= riseMin && nowMin < setMin;
}

// ── chartObj-lite 合成:主六壬页排盘函数(buildLiuRengLayout/buildKeData/buildSanChuanData/
//    ChuangChart)的消费面最小闭包。月将经 castOverride.yue 旁路注入(零需 objects 行星表)。──
export function buildLrChartLite(geoParams, options, dateStr, timeStr){
	const o = options || {};
	const lite = buildLocalNongliLite({
		...geoParams,
		date: dateStr,
		time: timeStr,
		gender: 1,
		// 🔴 恒真太阳(0):主六壬页 gods 请求不带 timeAlg=后端恒真太阳口径(真机实抓),
		// 扫描对齐主页所见;此档不入工作台参数区(拨了主页不跟=假自由度,死开关律)
		timeAlg: 0,
		after23NewDay: o.after23NewDay !== undefined ? o.after23NewDay : defaultAfter23NewDay(),	// 🔴 默认=全局日界**现值**(主六壬页同源;曾写死 0/1 两轮各错半边,复审 F8 定谳动态读)
		lateZiHourUseNextDay: o.lateZiHourUseNextDay !== undefined ? o.lateZiHourUseNextDay : 1,
	});
	if(!lite || !lite.bazi){ return null; }
	const fc = lite.bazi.fourColumns || {};
	const nl = lite.bazi.nongli || {};
	const gz = (k)=>(fc[k] && (fc[k].ganzi || fc[k].ganZhi)) || '';
	// 月将:lunar-js 上一个「气/节」名→映射表(中气档跳过节名取上一中气;节气档反之)。
	const mode = o.yueMode === 'jieqi' ? 'jieqi' : 'zhongqi';
	const table = mode === 'jieqi' ? YUE_BY_JIEQI : YUE_BY_ZHONGQI;
	let yue = table[nl.jieqi] || '';
	if(!yue){
		// nl.jieqi 是「上一节令名」——若属另一族(中气档遇节名/节气档遇中气名),按节序表回退一位取本族。
		const seq = ['小寒', '大寒', '立春', '雨水', '惊蛰', '春分', '清明', '谷雨', '立夏', '小满', '芒种', '夏至', '小暑', '大暑', '立秋', '处暑', '白露', '秋分', '寒露', '霜降', '立冬', '小雪', '大雪', '冬至'];
		const i = seq.indexOf(nl.jieqi);
		if(i >= 0){
			const prev = seq[(i + 23) % 24];
			yue = table[prev] || '';
		}
	}
	// 🔴 zone 解析走外壳 zoneOffsetMinutes(兼容 8/8.5/-3/'8' 历史数字形态——外壳明文
	// 承诺支持;曾自带正则强制「符号+两位」,数字 zone 静默回落 +8 → 昼夜界整小时偏移,
	// 四柱对而昼夜贵错,审查实抓)。
	const zoneHours = zoneOffsetMinutes((geoParams && geoParams.zone)) / 60;
	const diurnal = isDiurnalLocal(dateStr, timeStr, geoParams && geoParams.gpsLat, geoParams && geoParams.gpsLon, zoneHours);
	const chartLite = {
		nongli: {
			yearGanZi: gz('year'),
			monthGanZi: gz('month'),
			dayGanZi: gz('day'),
			time: gz('time'),
			year: gz('year'),
			month: gz('month'),
			day: gz('day'),
		},
		isDiurnal: diurnal,
	};
	const lrGods = fillLrGods(fc);
	const xun = fillLrXun(gz('day'));
	return { chartLite, yue, diurnal, fourColumns: fc, nongli: nl, lrGods, xun };
}
