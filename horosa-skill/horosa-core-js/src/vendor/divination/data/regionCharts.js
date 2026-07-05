// divination/data/regionCharts.js
// 「地区盘」预置数据 + 用户自定义存取。只放中性历史建置时刻作示例；以用户自定义为主。
// 不预置任何政治敏感现代实体；坐标用 App 既有「度分」串式（如 '0w07' / '51n30'）+ 数值 gps。

export const REGION_CHARTS = {
	london_1066: {
		cn: '伦敦 · 加冕建置（历史示例）',
		date: '1066-12-25', time: '12:00:00', zone: '+00:00',
		lon: '0w07', lat: '51n30', gpsLon: -0.12, gpsLat: 51.50,
		note: '西敏寺加冕，世俗占星经典历史盘例。',
	},
	philadelphia_1776: {
		cn: '费城 · 建置（历史示例）',
		date: '1776-07-04', time: '17:10:00', zone: '-05:00',
		lon: '75w09', lat: '39n57', gpsLon: -75.15, gpsLat: 39.95,
		note: '世俗占星常用历史盘例之一。',
	},
	paris_1792: {
		cn: '巴黎 · 共和建置（历史示例）',
		date: '1792-09-22', time: '12:00:00', zone: '+00:09',
		lon: '2e21', lat: '48n51', gpsLon: 2.35, gpsLat: 48.85,
		note: '历史建置时刻示例。',
	},
};

// 一国/一地多「候选建置时刻」：史上对确切时刻有不同主张时，对比哪个盘更合事件走势。
// 纯占星技术变体（只换 time，共享日期/坐标），无政治断言；以最通行者居首。
export const REGION_CANDIDATES = {
	philadelphia_1776: [
		{ key: 'a', label: '通行盘 17:10', time: '17:10:00', note: '最通行的下午建置时刻，上升天蝎。' },
		{ key: 'b', label: '晨盘 02:13', time: '02:13:00', note: '主张清晨签署的变体，上升双子。' },
		{ key: 'c', label: '正午 12:00', time: '12:00:00', note: '无确切时刻时的惯用正午盘。' },
	],
	paris_1792: [
		{ key: 'a', label: '正午盘 12:00', time: '12:00:00', note: '共和宣告日的惯用正午盘。' },
		{ key: 'b', label: '上午盘 09:00', time: '09:00:00', note: '上午议会时段变体。' },
		{ key: 'c', label: '午后盘 15:00', time: '15:00:00', note: '午后议程变体。' },
	],
	london_1066: [
		{ key: 'a', label: '正午加冕 12:00', time: '12:00:00', note: '西敏寺加冕的惯用正午盘。' },
		{ key: 'b', label: '午后 13:30', time: '13:30:00', note: '部分史料推定的午后时刻。' },
	],
};

// 返回某预置盘的候选时刻数组(无候选→null)。
export function regionCandidates(key){ return REGION_CANDIDATES[key] || null; }

// 中性首都坐标库(仅地理坐标,无任何建置时刻/政治断言):速填地点后用户自定建置时刻起地区盘。
export const MUNDANE_CAPITALS = [
	{ cn: '伦敦', lon: '0w07', lat: '51n30', gpsLon: -0.12, gpsLat: 51.50 },
	{ cn: '巴黎', lon: '2e21', lat: '48n51', gpsLon: 2.35, gpsLat: 48.85 },
	{ cn: '柏林', lon: '13e24', lat: '52n31', gpsLon: 13.40, gpsLat: 52.52 },
	{ cn: '罗马', lon: '12e29', lat: '41n54', gpsLon: 12.48, gpsLat: 41.90 },
	{ cn: '马德里', lon: '3w42', lat: '40n25', gpsLon: -3.70, gpsLat: 40.42 },
	{ cn: '莫斯科', lon: '37e37', lat: '55n45', gpsLon: 37.62, gpsLat: 55.75 },
	{ cn: '华盛顿', lon: '77w02', lat: '38n54', gpsLon: -77.04, gpsLat: 38.90 },
	{ cn: '东京', lon: '139e41', lat: '35n41', gpsLon: 139.69, gpsLat: 35.69 },
	{ cn: '新德里', lon: '77e12', lat: '28n36', gpsLon: 77.20, gpsLat: 28.60 },
	{ cn: '开罗', lon: '31e14', lat: '30n02', gpsLon: 31.24, gpsLat: 30.04 },
	{ cn: '维也纳', lon: '16e22', lat: '48n13', gpsLon: 16.37, gpsLat: 48.21 },
	{ cn: '雅典', lon: '23e43', lat: '37n59', gpsLon: 23.73, gpsLat: 37.98 },
	{ cn: '伊斯坦布尔', lon: '28e59', lat: '41n01', gpsLon: 28.98, gpsLat: 41.01 },
];

const USER_KEY = 'horosa.mundane.region.user.v1';

// 读用户自定义地区盘（对象 map，键为用户输入或自动键）。失败返回 {}。
export function loadUserRegions(){
	try{
		if(typeof localStorage === 'undefined'){ return {}; }
		const raw = localStorage.getItem(USER_KEY);
		if(!raw){ return {}; }
		const obj = JSON.parse(raw);
		return (obj && typeof obj === 'object') ? obj : {};
	}catch(e){ return {}; }
}

// 写入一条用户自定义地区盘。返回新的用户 map。
export function saveUserRegion(key, rec){
	try{
		if(typeof localStorage === 'undefined' || !key || !rec){ return loadUserRegions(); }
		const cur = loadUserRegions();
		cur[key] = rec;
		localStorage.setItem(USER_KEY, JSON.stringify(cur));
		return cur;
	}catch(e){ return loadUserRegions(); }
}

export function removeUserRegion(key){
	try{
		if(typeof localStorage === 'undefined' || !key){ return loadUserRegions(); }
		const cur = loadUserRegions();
		delete cur[key];
		localStorage.setItem(USER_KEY, JSON.stringify(cur));
		return cur;
	}catch(e){ return loadUserRegions(); }
}

// 合并预置 + 用户。用户同键覆盖预置。
export function allRegions(){
	return { ...REGION_CHARTS, ...loadUserRegions() };
}

export default { REGION_CHARTS, REGION_CANDIDATES, regionCandidates, loadUserRegions, saveUserRegion, removeUserRegion, allRegions };
