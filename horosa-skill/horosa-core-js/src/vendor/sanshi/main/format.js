// 三式合一页:取值、格式化与缓存键(视口高、时间算法、时区、干支拆分、公历 / 农历 / 直接时间显示、字段键、奇门选项键、外圈盘键、分州野)。
// 从 SanShiUnitedMain.js 按职责拆出(门面保留原导入路径与对外导出;读源码的检查读「子模块 + 门面」全集,见 scripts/source-sets.json)。
// headless stub：shellZoom 直接量 fixed 铺满元素的布局高（DOM），只服务组件构造期的视口高度；headless 无视口。
// 定义同名函数让 stub 审计看到「已知且不可达」，真被调到时抛明确错误而不是 ReferenceError。
function getPageLayoutHeight(){ throw new Error('headless stub: utils/shellZoom is not vendored'); }
import { normalizeZone } from '../../utils/zoneText.js';
import { safe } from '../../dunjia/qimenPageShared.js';
import * as LRConst from '../../liureng/LRConst.js';
import { leapPrefix } from '../../utils/lunarText.js';
import * as AstroText from '../sanshiAstroText.js';
import * as AstroConst from '../sanshiAstroConst.js';
import { liurengFenZhouYeDiurnal } from '../../liureng/LiuRengMain.js';

export function getViewportHeight(){
	// 🔴 innerHeight/documentElement.clientHeight 恒报物理域;壳缩放≠1 时当布局高用会
	// 把整页配矮(底部死带)。走 getLayoutViewportHeight —— 它**直接量** fixed 铺满元素,
	// 不做任何缩放换算,故与引擎的 zoom 语义无关(2026-08-27 根修,见 zoomDomain)。
	if(typeof window !== 'undefined' && Number.isFinite(window.innerHeight) && window.innerHeight > 0){
		// 页面排版视口:地板到工作区包络高 560(工作区按下限排、外层可滚;不地板则盘按矮视口排、与工作区脱节)
		return getPageLayoutHeight();
	}
	if(typeof document !== 'undefined' && document.documentElement){
		return document.documentElement.clientHeight || 900;
	}
	return 900;
}

export function normalizeTimeAlg(value){
	return value === 1 ? 1 : 0;
}

export function getTimeAlgLabel(value){
	return normalizeTimeAlg(value) === 1 ? '直接时间' : '真太阳时';
}

// 时区串规范化单源 utils/zoneText.normalizeZone(与精确历法桥同一份)
export const normalizeZoneOffset = normalizeZone;

export function normalizeAdValue(ad, fallback = 1){
	const text = `${safe(ad, '')}`.trim().toUpperCase();
	if(text === 'BC' || text === 'BCE'){
		return -1;
	}
	if(text === 'AD' || text === 'CE'){
		return 1;
	}
	const n = parseInt(text, 10);
	if(!Number.isNaN(n) && n !== 0){
		return n > 0 ? 1 : -1;
	}
	return fallback === -1 ? -1 : 1;
}

export function timeoutResolve(ms, value = null){
	return new Promise((resolve)=>{
		setTimeout(()=>resolve(value), ms);
	});
}

// 天将缩写:与六壬页同一张表(liureng/LRConst.TIANJIANG_SHORT,三式合一同步铁律);三式盘空位显示「—」
export function shortTianJiang(name){
	return LRConst.shortTianJiang(name) || '—';
}

export function splitGanZhi(gz){
	const text = `${safe(gz, '')}`.trim();
	if(!text){
		return { gan: '', zhi: '—' };
	}
	const chars = text.split('');
	const first = chars[0] || '';
	const last = chars[chars.length - 1] || '';
	const hasGan = LRConst.GanList.indexOf(first) >= 0;
	return {
		gan: hasGan ? first : '',
		zhi: last || '—',
	};
}

export function getGanzhiParts(gz){
	return {
		gan: (gz || '').substring(0, 1) || ' ',
		zhi: (gz || '').substring(1, 2) || ' ',
	};
}

function parseSolarDateTime(rawText){
	const text = `${safe(rawText, '')}`.trim();
	if(!text){
		return null;
	}
	const normalized = text.replace('T', ' ').replace('Z', '').trim();
	const m = normalized.match(/([-+]?\d{1,6})[/-](\d{1,2})[/-](\d{1,2})\s+(\d{1,2}):(\d{2})(?::(\d{2}))?/);
	if(!m){
		return {
			date: text,
			hm: '',
			hms: '',
			raw: text,
			isSolar: true,
		};
	}
	const yyyy = m[1];
	const mm = `${m[2]}`.padStart(2, '0');
	const dd = `${m[3]}`.padStart(2, '0');
	const hh = `${m[4]}`.padStart(2, '0');
	const ss = `${m[6] || '00'}`.padStart(2, '0');
	return {
		date: `${yyyy}-${mm}-${dd}`,
		hm: `${hh}:${m[5]}`,
		hms: `${hh}:${m[5]}:${ss}`,
		raw: text,
		isSolar: true,
	};
}

export function fmtDirect(fields){
	if(!fields || !fields.date || !fields.time){
		return { date: '', hm: '', hms: '' };
	}
	return {
		date: fields.date.value.format('YYYY-MM-DD'),
		hm: fields.time.value.format('HH:mm'),
		hms: fields.time.value.format('HH:mm:ss'),
	};
}

export function fmtSolar(fields, pan, nongli, displaySolarTime){
	const solarParsed = parseSolarDateTime(
		safe(displaySolarTime, '') || safe(pan && pan.realSunTime, '') || safe(nongli && nongli.birth, '')
	);
	if(solarParsed){
		return solarParsed;
	}
	const direct = fmtDirect(fields);
	return {
		date: direct.date,
		hm: direct.hm,
		hms: direct.hms,
		raw: '',
		isSolar: false,
	};
}

export function fmtLunar(nongli){
	if(!nongli){
		return '';
	}
	return `农历${leapPrefix(nongli)}${safe(nongli.month)}${safe(nongli.day)}`;   // 闰:单源 leapPrefix(只在月名缺「闰」时补)
}

export function msg(key){
	return AstroText.AstroMsgCN[key] || key || '';
}

export function shortMainStarLabel(name){
	const text = `${safe(name, '')}`.trim();
	if(!text){
		return '';
	}
	if(text === '太阳'){
		return '日';
	}
	if(text === '上升'){
		return '升';
	}
	if(text === '天顶' || text === '中天'){
		return '顶';
	}
	return text.substring(0, 1);
}

export function getFieldKey(fields){
	if(!fields || !fields.date || !fields.time){
		return '';
	}
	return [
		fields.date.value.format('YYYY-MM-DD'),
		fields.time.value.format('HH:mm:ss'),
		safe(fields.zone && fields.zone.value),
		safe(fields.lon && fields.lon.value),
		safe(fields.lat && fields.lat.value),
		safe(fields.ad && fields.ad.value),
	].join('|');
}

export function getFieldSyncKey(fields){
	if(!fields){
		return '';
	}
	return [
		getFieldKey(fields),
		safe(fields.cid && fields.cid.value),
		safe(fields.name && fields.name.value),
		safe(fields.gender && fields.gender.value),
		safe(fields.zodiacal && fields.zodiacal.value),
		safe(fields.hsys && fields.hsys.value),
		safe(fields.timeAlg && fields.timeAlg.value),
	].join('|');
}

export function getQimenOptionsKey(options){
	if(!options){
		return '';
	}
	return [
		safe(options.sex),
		safe(options.dateType),
		safe(options.leapMonthType),
		safe(options.xuShiSuiType),
		safe(options.jieQiType),
		safe(options.paiPanType),
		safe(options.zhiShiType),
		safe(options.yueJiaQiJuType),
		safe(options.yearGanZhiType),
		safe(options.monthGanZhiType),
		safe(options.dayGanZhiType),
		safe(options.after23NewDay),
		safe(options.lateZiHourUseNextDay),
		safe(options.qijuMethod),
		safe(options.kongMode),
		safe(options.yimaMode),
		safe(options.shiftPalace),
		options.fengJu ? 1 : 0,
		safe(options.school),
		safe(options.shuziReportNumber),
		safe(options.zhirunLeapDays),
		// 🔴 同独立页:缓存键维度完备,新引擎键全入(漏=三式改档死开关)。哨兵测试守。
		safe(options.godsPreset),
		safe(options.jiGongMode),
		safe(options.anGanMode),
		options.showAnZhi ? 1 : 0,
		options.showJiGan ? 1 : 0,
		options.showTianQin ? 1 : 0,
		safe(options.tuiYanView),
		safe(options.tuiYanGong),
		options.fullNameTips ? 1 : 0,
		options.feiXingShun ? 1 : 0,
		options.feiMenShun ? 1 : 0,
		options.feiShenShun ? 1 : 0,
		options.feiMenZhongCan === false ? 0 : 1,
		options.feiMenZhongShow ? 1 : 0,
		safe(options.mixTian),
		safe(options.mixXing),
		safe(options.mixMen),
		safe(options.mixShen),
		options.kongMarkBoth ? 1 : 0,
		options.showAllKong ? 1 : 0,
		safe(options.shiftZhiFuMode),
		safe(options.dayJiaJu),
		safe(options.keJiaFenDun),
		options.keZiZhengHuanShi ? 1 : 0,
		safe(options.jinhanMenPai),
		safe(options.yearJiaJu),
		// 三式把盘类 / 相关人员 / 时间算法也交给起盘(法奇门读 pan.options.chartCategory 定日干内心↔实质);
		// 曾漏入键 → 切「盘类」命中旧盘,判读口径纹丝不动(独立页这两项走组件 ctx,不经此键)
		safe(options.timeAlg),
		safe(options.chartCategory),
		safe(options.faRelatedPeople),
	].join('|');
}

export function extractIsDiurnalFromChartWrap(chartWrap){
	if(!chartWrap){
		return null;
	}
	const chart = chartWrap.chart ? chartWrap.chart : chartWrap;
	if(chart && chart.isDiurnal !== undefined && chart.isDiurnal !== null){
		return !!chart.isDiurnal;
	}
	return null;
}

export function getChartYue(chartObj){
	if(!chartObj || !chartObj.objects){
		return '';
	}
	for(let i=0; i<chartObj.objects.length; i++){
		const obj = chartObj.objects[i];
		if(obj.id === AstroConst.SUN){
			return LRConst.getSignZi(obj.sign);
		}
	}
	return '';
}

export function getOuterChartKey(chartWrap){
	if(!chartWrap){
		return '';
	}
	const chart = chartWrap.chart ? chartWrap.chart : chartWrap;
	if(!chart){
		return '';
	}
	// 🔴 **绝不纳入 chartId**:它是 model 里 `Result.chartId = randomStr(8)` 每次取盘现生成的随机值,
	// 拿它当「盘内容是否变化」的判据两头不讨好——同一时刻重复回流也判「变了」(每次都全量重算,
	// 含 /qimen/pan 与 /taiyi/pan,性能白掉),而真正该判变的维度反而没被表征。
	// 内容判据用下面几项就够且稳:ASC/SUN 的 sign|signlon|lon(逐分钟即变,四分钟步进必变)
	// + 日干支 + 时辰 + 天体数。配合 componentDidUpdate 里去掉 awaitingChartSync 闸门,才形成
	// 「chartObj 一变就校正、没实质变就 no-op」的闭环(horosa_sanshi_outer_follow_time_v1)。
	const objs = chart.objects || [];
	let ascKey = '';
	let sunKey = '';
	for(let i=0; i<objs.length; i++){
		const obj = objs[i];
		if(!obj){
			continue;
		}
		if(!ascKey && obj.id === AstroConst.ASC){
			ascKey = `${safe(obj.sign)}|${safe(obj.signlon)}|${safe(obj.lon)}`;
		}
		if(!sunKey && obj.id === AstroConst.SUN){
			sunKey = `${safe(obj.sign)}|${safe(obj.signlon)}|${safe(obj.lon)}`;
		}
		if(ascKey && sunKey){
			break;
		}
	}
	return [
		ascKey,
		sunKey,
		safe(chart.nongli && chart.nongli.dayGanZi),
		safe(chart.nongli && chart.nongli.time),
		`${objs.length}`,
	].join('|');
}

// 与六壬页同一实现(三式同步:六壬页修了分昼夜口径,三式合一与两个择日扫描自动跟上)
export function computeSanshiFenZhouYe(fenZhouYe, chartObj){
	return liurengFenZhouYeDiurnal(fenZhouYe, chartObj);
}
