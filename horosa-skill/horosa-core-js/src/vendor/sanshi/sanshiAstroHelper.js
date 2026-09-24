// 三式合一外圈「星盘」行的度分拆分子集 —— **逐字抽自上游** components/astro/AstroHelper.js:34-87
// （splitDegree / convertLatToStr / convertLonToStr 三个纯函数，原序原文）。
// 为什么是子集：上游 AstroHelper.js（1400+ 行）顶层 import d3 与 utils/helper（DOM / tooltip），且模块加载期即调
// detectOS()，headless 不可整份 vendor；SanShiUnitedMain.js 纯逻辑段只用 splitDegree（buildOuterData 的宫内度分），
// 另两个与它同一条 import 语句，一并照抄以满足具名导入。curated：上游源 sha 由 manifest 的 upstream_sha256 看守。
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
	// 方向按【原始值符号】判:|值|<1 时 splitDegree 的度部分=0、负号会丢(-0 === 0),
	// 若用 deg[0]>=0 判向会把 -0.12° 误判成北/东。度分一律取绝对值,补两位。
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
