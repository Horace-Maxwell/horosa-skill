// 宿占快照（vendored suzhan/SuZhanMain.js）用到的 AstroHelper 子集 —— **逐字抽自上游** components/astro/AstroHelper.js
// （signDegMin :185-198；SIMPLE_TOKEN_MAP / isEncodedToken / astroMsgPlainText :214-281，原序原文）。
// 为什么是子集：上游 AstroHelper.js 整份 import 上游 AstroConst / AstroText 全集（whichTerm / 相位 / 经纬度串等另外几十个函数要它们），
// 共享 shim 不全，headless 不整份 vendor（同 sanshi/sanshiAstroHelper.js）；SuZhanMain.js 的纯逻辑段只 import 这两件。
// curated：上游源 sha 由 contracts/vendor_manifest.json 的 upstream_sha256 看守，源一动即红、逐字对过再 --restamp。
// AstroText = 共享 shim src/constants/AstroText.js（AstroTxtMsg / AstroMsg 两张表，宿占星表所需键齐）。
import * as AstroText from '../../constants/AstroText.js';

// 座内度分:黄经(可负,先补 360)→ [座内整度, 整分](均向下取整);非数 → [0, 0]。
// 与上面的 splitDegree(把度数拆成度 / 分 / 秒)不是一回事。
export function signDegMin(degree){
	let d = Number(degree);
	if(Number.isNaN(d)){
		return [0, 0];
	}
	if(d < 0){
		d += 360;
	}
	const deg = Math.floor(d % 30);
	const min = Math.floor(((d % 30) - deg) * 60);
	return [deg, min];
}

// 字形字体的单字符码 → 中文名(AstroMsg 取到的是字形码时用,免得字形码混进纯文本)。
const SIMPLE_TOKEN_MAP = {
	A: '日',
	B: '月',
	C: '水',
	D: '金',
	E: '火',
	F: '木',
	G: '土',
	H: '天王',
	I: '海王',
	J: '冥王',
	K: '北交',
	L: '南交',
	p: '福点',
	v: '暗月',
	w: '紫气',
	y: '凯龙',
	z: '月亮朔望点',
	Y: '月亮平均远地点',
	$: '月亮平均近地点',
	a: '白羊',
	b: '金牛',
	c: '双子',
	d: '巨蟹',
	e: '狮子',
	f: '处女',
	g: '天秤',
	h: '天蝎',
	i: '射手',
	j: '摩羯',
	k: '水瓶',
	l: '双鱼',
	0: '上升',
	1: '天顶',
	2: '天底',
	3: '下降',
	4: '谷神星',
	5: '智神星',
	6: '婚神星',
	7: '灶神星',
	8: '人龙星',
};

function isEncodedToken(text){
	return /^[A-Za-z0-9${}]$/.test((text || '').trim());
}

// 同 astroMsgText,但 AstroMsg 取到单字符字形码时改出中文名(字形码表里没有就原样输出 id)。
export function astroMsgPlainText(id){
	if(id === undefined || id === null){
		return '';
	}
	if(AstroText.AstroTxtMsg[id]){
		return AstroText.AstroTxtMsg[id];
	}
	if(AstroText.AstroMsg[id]){
		const val = AstroText.AstroMsg[id];
		if(!isEncodedToken(val)){
			return `${val}`;
		}
	}
	const one = `${id}`.trim();
	if(one.length === 1 && SIMPLE_TOKEN_MAP[one]){
		return SIMPLE_TOKEN_MAP[one];
	}
	return `${id}`;
}
