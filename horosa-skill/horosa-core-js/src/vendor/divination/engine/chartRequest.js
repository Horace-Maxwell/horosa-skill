// divination/engine/chartRequest.js
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
	};
	if(params.pdaspects && params.pdaspects instanceof String){
		params.pdaspects = JSON.parse(params.pdaspects);
	}
	return params;
}

export default buildChartParams;
