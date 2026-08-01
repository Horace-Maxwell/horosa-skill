// divination/babylon/horoscope.js —— 个人星盘装配器(P1)。
// 铁律:无十二宫位、无相位、无(希腊式)上升点(§见帮助——巴比伦星盘是数据清单)。
// 七曜固定序:月、日、木、金、水、土、火(吉→中→凶的排序,非空间序)。
// 双源:swiss(现代实位,恒星黄道 Aldebaran=金牛15° 框架,由上游星盘数据供给)
//       systemA/B(数理复原:以现代现象锚 + 阶梯/锯齿推进,呈现算法差异)。

import { lonToSignDeg } from './units.js';
import { jdnToBabylonian, urukSchemeOf, formatSchematic, formatBabylonianDate } from './calendar.js';
import {
	babylonSign, babylonPlanet, exaltationOf, triplicityOfSign, triplicityOfMonth,
	daySegmentLord, termLordOfDeg, landOfMonth,
} from '../divination/data/babylonianData.js';
import { dodeca12 } from './microzodiac.js';

export const PLANET_ORDER = ['moon', 'sun', 'jupiter', 'venus', 'mercury', 'saturn', 'mars'];

// 与日合而不可见的图式判据(°;近似值,显示层注明「图式判据」)
export const COMBUST_ORB = 15;

// 输入:
//   lons: { moon, sun, jupiter, venus, mercury, saturn, mars } 恒星黄道黄经(度;来自上游 sidereal 盘)
//   jdn:  出生儒略日号(整);
//   opts: { dodecaVariant:'B'|'A' }
export function buildHoroscope(lons, jdn, opts){
	const o = opts || {};
	const bd = jdnToBabylonian(jdn);
	const uruk = urukSchemeOf(bd.seYear);
	const rows = PLANET_ORDER.map((key) => {
		const lon = lons ? lons[key] : undefined;
		if(lon === undefined || lon === null || isNaN(lon)){ return { key, missing: true }; }
		const { sign, deg } = lonToSignDeg(lon);
		const p = babylonPlanet(key);
		const sunLon = lons.sun;
		let combust = false;
		if(key !== 'sun' && key !== 'moon' && sunLon !== undefined){
			const d = Math.abs(((lon - sunLon + 540) % 360) - 180);
			combust = d <= COMBUST_ORB;
		}
		const ex = exaltationOf(key);
		const inExalt = ex && ex.sign === sign;
		const trip = triplicityOfSign(sign);
		const inOwnTrip = trip && trip.lord.indexOf(key) >= 0;
		const dd = dodeca12(lon, o.dodecaVariant === 'A' ? 'A' : 'B');
		return {
			key, cn: p ? p.cn : key, lon, sign, deg,
			signInfo: babylonSign(sign),
			nature: p ? p.nature : '',
			god: p ? p.god : '',
			number: p ? p.number : null,
			combust,               // 「已没 ŠÚ」
			inExalt,               // 在其「秘密之屋」(旺宫)
			trip, inOwnTrip,
			term: termLordOfDeg(deg),
			dodeca: dd,
		};
	});

	// bīt niṣirti / KI 三法(星盘解读装置)
	const solsticeMonthTrip = triplicityOfMonth(nearestSolsticeMonth(bd, uruk));
	const daySeg = daySegmentLord(Math.max(1, Math.min(30, Math.round(bd.day))));

	return {
		babylonianDate: bd,
		babylonianDateText: formatBabylonianDate(bd),
		monthLen: bd.monthLen,                    // 前月满/缺显示基础
		rows,
		uruk: {
			...uruk,
			text: {
				ve: formatSchematic(uruk.vernalEquinox), ss: formatSchematic(uruk.summerSolstice),
				ae: formatSchematic(uruk.autumnEquinox), ws: formatSchematic(uruk.winterSolstice),
				siriusRise: formatSchematic(uruk.siriusRise), siriusSet: formatSchematic(uruk.siriusSet),
			},
		},
		bitNisirti: {
			bySolsticeMonth: solsticeMonthTrip,
			byDaySegment: daySeg,
		},
		land: landOfMonth(Math.floor(bd.month.n)),
	};
}

// 最近分至所在月号(以 Uruk 图式月号;方法①用)
function nearestSolsticeMonth(bd, uruk){
	const m = Math.floor(bd.month.n);
	const cands = [uruk.vernalEquinox, uruk.summerSolstice, uruk.autumnEquinox, uruk.winterSolstice];
	let best = cands[0], bestD = 99;
	cands.forEach((c) => {
		let d = Math.abs(c.m - m);
		if(d > 6){ d = 12 - d; }
		if(d < bestD){ bestD = d; best = c; }
	});
	return best.m;
}

// 行星在其三分组的「位」判语(星盘用语风格,原创中文)
export function kiVerdict(row){
	if(!row || row.missing){ return ''; }
	if(row.inExalt){ return '在其秘密之屋——吉兆之位,所事兴旺'; }
	if(row.inOwnTrip){ return '在其本三分之宫——兴旺、平安'; }
	return '';
}
