
import * as AstroConst from '../../constants/AstroConst.js';

export const Su28 = [
	'角', '亢', '氐', '房', '心', '尾', '箕',
	'斗', '牛', '女', '虚', '危', '室', '壁',
	'奎', '娄', '胃', '昴', '毕', '觜', '参',
	'井', '鬼', '柳', '星', '张', '翼', '轸'
];


let suToSign = [
	AstroConst.LIBRA, AstroConst.LIBRA,
	AstroConst.SCORPIO, AstroConst.SCORPIO, AstroConst.SCORPIO,
	AstroConst.SAGITTARIUS, AstroConst.SAGITTARIUS,
	AstroConst.CAPRICORN, AstroConst.CAPRICORN, 
	AstroConst.AQUARIUS, AstroConst.AQUARIUS, AstroConst.AQUARIUS, 
	AstroConst.PISCES, AstroConst.PISCES,
	AstroConst.ARIES, AstroConst.ARIES,
	AstroConst.TAURUS, AstroConst.TAURUS, AstroConst.TAURUS,
	AstroConst.GEMINI, AstroConst.GEMINI,
	AstroConst.CANCER, AstroConst.CANCER,
	AstroConst.LEO, AstroConst.LEO, AstroConst.LEO,
	AstroConst.VIRGO, AstroConst.VIRGO, AstroConst.VIRGO
];

// 宿色 / 宿底色一律按访问时的调色板求值(getSu28Color / getSu28ColorCircle / getSu28FillColorCircle):此前四个模块级数组在 import 期
// 就把 AstroConst.AstroColor 读死,切明暗后永远是亮主题的色(FL-20260922-3),已删。
export function getSu28Color(i){
	let sig = suToSign[i];
	return AstroConst.AstroColor[sig];
}

export function getSu28ColorCircle(su){
	let sig = su.sign
	return AstroConst.AstroColor[sig];
}

export function getSu28PlanetColorCircle(planet, sumap, sigraList){
	let sn = planet.su28;
	let su = sumap.get(sn)					
	let suSig = su.sign;
	let sigidx = AstroConst.LIST_SIGNS.indexOf(suSig);
	let nxtsigidx = (sigidx + 1) % 12;
	let nxtsig = AstroConst.LIST_SIGNS[nxtsigidx];
	let sigra = sigraList[sigidx];
	let nxtsigra = sigraList[nxtsigidx];
	let prevra = sigra.ra;
	let nxtra = nxtsigra.ra;
	let chkra = planet.ra;
	if(nxtra < prevra){
		nxtra = nxtra + 360;
	}
	if(chkra < prevra){
		chkra  = chkra + 360
	}
	if(prevra <= chkra && chkra < nxtra){
		return AstroConst.AstroColor[suSig];
	}
	return AstroConst.AstroColor[nxtsig];
}

export function getSu28FillColorCircle(su){
	let sig = su.sign
	return AstroConst.AstroColor.SignFill[sig];
}

let suToSignMap = new Map();

export function getSu28Sign(su28){
	if(suToSignMap.size === 0){
		for(let i=0; i<Su28.length; i++){
			let su = Su28[i];
			let sign = suToSign[i];
			suToSignMap.set(su, sign);
		}
	}
	return suToSignMap.get(su28);
}

