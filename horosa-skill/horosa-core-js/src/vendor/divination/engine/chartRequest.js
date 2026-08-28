// divination/engine/chartRequest.js
import { classicalBackendOverridesFromFields } from '../../utils/classicalChartGlobals.js';
import { userAyanParamsFrom } from '../../utils/customCalibreStores.js';
// 把 fields-like 对象（{key:{value,name}}，date.value/time.value 为 comp/DateTime 实例）
// 转成 /chart 请求体。复刻 models/astro.js 的 fieldsToParams 西洋盘子集，
// 使卜卦盘/择日盘算出的盘与「占星」页完全一致。本函数只读 fields，不修改。

export function buildChartParams(fields){
	const v = (k, d) => (
		fields && fields[k] && fields[k].value !== undefined && fields[k].value !== null
			? fields[k].value : d
	);
	const date = v('date', null);
	const time = v('time', null);
	const params = {
		cid: v('cid', null),
		ad: date && date.ad,
		date: (date && date.format) ? date.format('YYYY/MM/DD') : null,
		time: (time && time.format) ? time.format('HH:mm:ss') : null,
		zone: date ? date.zone : v('zone', null),
		lat: v('lat', null),
		lon: v('lon', null),
		gpsLat: v('gpsLat', null),
		gpsLon: v('gpsLon', null),
		hsys: v('hsys', 0),
		southchart: v('southchart', 0),
		zodiacal: v('zodiacal', 0),
		siderealAyanamsa: v('siderealAyanamsa', ''),
		// [F9] 自定义恒星黄道('user' 槽):附历元两参,缺参后端静默回落 Lahiri 与主盘分叉。
		...(`${v('siderealAyanamsa', '')}` === 'user' ? (()=>{
			try{
				return userAyanParamsFrom((k)=>(fields && fields[k] ? fields[k].value : undefined)) || {};
			}catch(e){ return {}; }
		})() : {}),
		tradition: v('tradition', 1),
		doubingSu28: v('doubingSu28', 0),
		strongRecption: v('strongRecption', 0),
		simpleAsp: v('simpleAsp', 0),
		virtualPointReceiveAsp: v('virtualPointReceiveAsp', 1),
		predictive: 0,
		pdaspects: [0, 60, 90, 120, 180],
		name: v('name', null),
		pos: v('pos', null),
		after23NewDay: v('after23NewDay', 1),
		lateZiHourUseNextDay: v('lateZiHourUseNextDay', 0),
		// 界系(bounds)：默认 0/缺省 不下发(同主盘 fieldsToParams 口径,零回归);仅非 0 才传 → /chart 已按界算尊贵/界主。
		...((fields && fields.termsVariant && fields.termsVariant.value) ? { termsVariant: fields.termsVariant.value } : {}),
		// 双子界序开关(卜卦 2b 口径;仅经典传本受影响):默认/0 不下发=忠原书零回归;1 才传 → 后端换双子校勘行。
		...((fields && fields.geminiBoundEmended && fields.geminiBoundEmended.value) ? { geminiBoundEmended: 1 } : {}),
		// 古典占星参数五键(交点真平/昼夜缓冲/狮子首星/三分集/福点反转):与主盘 fieldsToParams 同款条件透传——
		// 默认不下发=请求体/缓存键零回归;非默认才传。值来源=父级 fields 种子(getFields 已播全局仓偏好)
		// 或卜卦流派 patch(lotReversal 随档);使「设置→星盘设置」全局偏好透传到卜卦/择日盘。
		...((fields && fields.westNodeType && fields.westNodeType.value === 'true') ? { westNodeType: 'true' } : {}),
		...((fields && fields.sectBuffer && fields.sectBuffer.value === 'ptolemy5') ? { sectBuffer: 'ptolemy5' } : {}),
		...((fields && fields.leoBoundFirst && (fields.leoBoundFirst.value === 1 || fields.leoBoundFirst.value === '1')) ? { leoBoundFirst: 1 } : {}),
		...((fields && fields.triplicity && fields.triplicity.value && fields.triplicity.value !== 'Dorothean') ? { triplicity: fields.triplicity.value } : {}),
		...((fields && fields.lotReversal && (fields.lotReversal.value === 0 || fields.lotReversal.value === '0')) ? { lotReversal: 0 } : {}),
		// 2026-07 二批九键(落宫前移/三态/空亡口径/恒星轨/映点容许度):共享 helper,默认不下发零回归。
		...classicalBackendOverridesFromFields(fields),
	};
	// [R2-11] 头键 spread 先写 termsVariant;overrides 的「无表降级删 4」撤不回 → 4 而无表体=不发(等效埃及,显式化)。
	if(Number(params.termsVariant) === 4 && !params.customTermsDay){ delete params.termsVariant; }
	if(params.pdaspects && params.pdaspects instanceof String){
		params.pdaspects = JSON.parse(params.pdaspects);
	}
	return params;
}

export default buildChartParams;
