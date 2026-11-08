// AI 助手·经纬度十进制 ↔ 罗盘串('39n54' / '116e24')换算。
// 抄本自 components/astro/AstroHelper.js(splitDegree / convertLatToStr / convertLonToStr /
// convertLatStrToDegree / convertLonStrToDegree),逐字同构——AstroHelper 顶层 import d3,
// 工具层(可被 jest/MCP 桥引用)不得依赖它;jest 抄本切片锁保证两处不漂移。

export function splitDegree(degree){
	let res = [];
	let degstr = degree + '';
	degstr = degstr.toLowerCase();
	let parts = degstr.split('e');
	let deg = parseFloat(degree + '');
	res[0] = parseInt(degree + '');
	let neg = false;
	if(deg < 0){
		neg = true;
		deg = Math.abs(deg);
		res[0] = Math.abs(res[0]);
	}

	if(parts.length === 2 && parseInt(parts[1]) < 0){
		res[0] = 0;
		deg = 0;
	}
	let minute = (deg - res[0]) * 60;
	res[1] = parseInt(Math.floor(minute) + '');
	let sec = (minute - res[1]) * 60;
	res[2] = parseInt(Math.round(sec) + '');
	if(res[2] === 60){
		res[1] = res[1] + 1;
		res[2] = 0;
	}
	if(res[1] === 60){
		res[0] = res[0] + 1;
		res[1] = 0;
	}
	if(neg){
		res[0] = 0 - res[0];
		res[3] = ['-'];
	}
	return res;
}

export function convertLatToStr(degree){
	const v = parseFloat(degree + '');
	const dir = (Number.isFinite(v) && v < 0) ? 's' : 'n';
	const deg = splitDegree(Math.abs(Number.isFinite(v) ? v : 0));
	const min = Math.abs(deg[1] || 0);
	return (Math.abs(deg[0] || 0)) + dir + (min >= 10 ? min : '0' + min);
}

export function convertLonToStr(degree){
	const v = parseFloat(degree + '');
	const dir = (Number.isFinite(v) && v < 0) ? 'w' : 'e';
	const deg = splitDegree(Math.abs(Number.isFinite(v) ? v : 0));
	const min = Math.abs(deg[1] || 0);
	return (Math.abs(deg[0] || 0)) + dir + (min >= 10 ? min : '0' + min);
}



// 十进制经纬 → 存档四键(lat/lon 罗盘串 + gpsLat/gpsLon 十进制)。
export function geoPairToRecordFields(gpsLat, gpsLon){
	const la = Number(gpsLat);
	const lo = Number(gpsLon);
	if(!Number.isFinite(la) || !Number.isFinite(lo)){
		return null;
	}
	return { lat: convertLatToStr(la), lon: convertLonToStr(lo), gpsLat: la, gpsLon: lo };
}
