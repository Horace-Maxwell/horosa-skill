// 希腊化占星 · 古典重建数据底座(前端单一真值源)。
// 数据移植自重建数据表(JSON);本模块只做导入+命名导出+便捷取值,纯数据零副作用、中性表述。
// 星座 0=白羊..11=双鱼;界/外观度数为座内 0-30;行星名 Sun/Moon/Mercury/Venus/Mars/Jupiter/Saturn/NorthNode/SouthNode。
import DATA from './hellenisticData.json' with { type: 'json' };
import EXT from './hellenisticDataExt.json' with { type: 'json' };
import * as __req0 from '../../utils/customCalibreStores.js';

export const HELLENISTIC = DATA;
export const HELLENISTIC_EXT = EXT;

// ── G17 行星年(小/中/大/极大,)。least 和=129;日月中年=39.5。──
export const PLANETARY_YEARS = DATA.planetary_years || {};

// ── G14 三分主星:Dorothean(3主)/ Ptolemaic(2主,含水象变体)。──
export const TRIPLICITY = DATA.triplicity || {};

// ── G5 Thema Mundi 世界盘:上升15°巨蟹,七政各居庙15°。──
export const THEMA_MUNDI = EXT.thema_mundi || {};

// ── G8 ZR 注记:峰期 major[1,10]/moderate[7]/minor[4]。──
export const ZR_NOTES = DATA.zr_notes || {};

// ── G7 七气候带 Klimata:带/城/纬度/最长昼/Valens 上升时度级数。──
export const KLIMATA = EXT.klimata || {};

// ── G16 单度主星:迦勒底连续序 / 三分序(system2)。──
export const MONOMOIRIA = EXT.monomoiria || {};

// ── G15 迦勒底界( 附F):宽度 [8,7,6,5,4]、按 sect 土水互换。──
export const CHALDEAN_BOUNDS = EXT.chaldean_bounds || {};

// ── 庙旺弱陷 / 界 / 外观 / joys / sect / lots / places(供各判读项)。──
export const DOMICILE = DATA.domicile || {};
export const EXALTATION = DATA.exaltation || {};
export const BOUNDS_EGYPTIAN = DATA.bounds_egyptian || {};
export const BOUNDS_PTOLEMAIC = DATA.bounds_ptolemaic || {};
export const FACES_CHALDEAN = DATA.faces_chaldean || {};
export const JOYS = DATA.joys || {};
export const SECT = DATA.sect || {};
export const LOTS = DATA.lots || {};
export const PLACES = DATA.places || {};

// 行星英文名 → 中文单字(七政四余口径)。
export const PLANET_CN = {
	Sun: '日', Moon: '月', Mercury: '水', Venus: '金', Mars: '火', Jupiter: '木', Saturn: '土',
	NorthNode: '罗', SouthNode: '计',
};

// 星座英文名/序 → 中文 + glyph(0=白羊..11=双鱼)。
export const SIGN_CN = ['白羊', '金牛', '双子', '巨蟹', '狮子', '处女', '天秤', '天蝎', '射手', '摩羯', '水瓶', '双鱼'];
export const SIGN_EN = ['Aries', 'Taurus', 'Gemini', 'Cancer', 'Leo', 'Virgo', 'Libra', 'Scorpio', 'Sagittarius', 'Capricorn', 'Aquarius', 'Pisces'];

// 迦勒底界(界系 3):由 CHALDEAN_BOUNDS(宽度 [8,7,6,5,4] + 元素昼序 + 夜规则土水互换)按座生成昼/夜两表,
// 结构同 EGYPTIAN_TERMS({座: [[星, 起度, 止度], ...]});供星盘界限环按所选界系 + 昼夜实绘(异于埃及/托勒密/莉莉)。
const _CHALD_ELEMENT_OF = {
	Aries: 'Fire', Leo: 'Fire', Sagittarius: 'Fire',
	Taurus: 'Earth', Virgo: 'Earth', Capricorn: 'Earth',
	Gemini: 'Air', Libra: 'Air', Aquarius: 'Air',
	Cancer: 'Water', Scorpio: 'Water', Pisces: 'Water',
};
function buildChaldeanTerms(night){
	const widths = (CHALDEAN_BOUNDS && CHALDEAN_BOUNDS.widths) || [8, 7, 6, 5, 4];
	const dayOrder = (CHALDEAN_BOUNDS && CHALDEAN_BOUNDS.day_order_by_element) || {};
	const out = {};
	SIGN_EN.forEach((sign) => {
		const order = (dayOrder[_CHALD_ELEMENT_OF[sign]] || []).slice();
		if(night){   // 夜盘:土↔水位置互换
			const si = order.indexOf('Saturn'), mi = order.indexOf('Mercury');
			if(si >= 0 && mi >= 0){ const t = order[si]; order[si] = order[mi]; order[mi] = t; }
		}
		const segs = [];
		let start = 0;
		for(let i = 0; i < order.length && i < widths.length; i++){
			segs.push([order[i], start, start + widths[i]]);
			start += widths[i];
		}
		out[sign] = segs;
	});
	return out;
}
export const CHALDEAN_TERMS_DAY = buildChaldeanTerms(false);
export const CHALDEAN_TERMS_NIGHT = buildChaldeanTerms(true);

// 界内变体两张(与后端 perchart _TETRABIBLOS_LEO_SATURN_FIRST / _LILLY_GEMINI_EMENDED 逐字节同构;
// 双实现漂移曾致「设置开了狮子土星优先/双子校勘,后端尊贵按变体算、行星 tab『位于 X 界』仍按基表显示」):
// 惰性浅拷贝基表+覆写单座,以 baseTables 引用为 memo 键(AstroConst 表模块级恒定,实际只建一次)。
const _LEO_SATURN_FIRST_ROW = [['Saturn', 0, 6], ['Mercury', 6, 13], ['Jupiter', 13, 19], ['Venus', 19, 25], ['Mars', 25, 30]];
const _GEMINI_EMENDED_ROW = [['Mercury', 0, 7], ['Jupiter', 7, 14], ['Venus', 14, 21], ['Mars', 21, 25], ['Saturn', 25, 30]];
let _leoVariantCache = null;   // { base, table }
let _geminiVariantCache = null;

// 界系变体 → 界主表:0 埃及 / 1 托勒密 / 2 莉莉(三套由 AstroConst 传入)/ 3 迦勒底(本模块昼夜表,按 isDiurnal)。
// opts(可选):{ leoBoundFirst, geminiBoundEmended } —— 与后端 push_request_terms 同语义:
// 仅 v==1 且 leoBoundFirst 时换狮子土星优先变体、v==2 且 geminiBoundEmended 时换双子校勘变体;
// 不传/默认恒基表(零回归)。truthy 判定与请求键形态(1/'1'/true)兼容。
export function termsTableForVariant(variant, isDiurnal, baseTables, egyptianFallback, opts){
	const v = Number(variant) || 0;
	if(v === 3){ return isDiurnal ? CHALDEAN_TERMS_DAY : CHALDEAN_TERMS_NIGHT; }
	// [F5] 4=自定义界表:显示层与后端同表(否则界环/行星表按埃及画、尊贵按自定义算,同屏矛盾);
	// 无合法表回落埃及=与后端降级同语义。
	if(v === 4){
		try{
			// [R2-3] 随盘/回显表体优先(opts=chartObj.params,后端算的就是这份表);无则回落本机编辑器仓。
			const custom = __req0.customTermsDisplayTables(
				isDiurnal, opts && opts.customTermsDay, opts && opts.customTermsNight);
			if(custom && custom.upper){ return custom.upper; }
		}catch(e){ /* 回落埃及 */ }
		return (baseTables && baseTables[0]) || egyptianFallback;
	}
	const base = (baseTables && baseTables[v]) || egyptianFallback;
	if(v === 1 && opts && opts.leoBoundFirst && base){
		if(!_leoVariantCache || _leoVariantCache.base !== base){
			_leoVariantCache = { base, table: { ...base, Leo: _LEO_SATURN_FIRST_ROW } };
		}
		return _leoVariantCache.table;
	}
	if(v === 2 && opts && opts.geminiBoundEmended && base){
		if(!_geminiVariantCache || _geminiVariantCache.base !== base){
			_geminiVariantCache = { base, table: { ...base, Gemini: _GEMINI_EMENDED_ROW } };
		}
		return _geminiVariantCache.table;
	}
	return base;
}

// "15 Cancer" → { signIndex, deg, lon }(thema_mundi 等英文度位解析)。
export function parseSignDegree(str){
	const m = String(str || '').trim().match(/^(\d+(?:\.\d+)?)\s+([A-Za-z]+)$/);
	if(!m){ return null; }
	const deg = parseFloat(m[1]);
	const si = SIGN_EN.indexOf(m[2]);
	if(si < 0){ return null; }
	return { signIndex: si, deg, lon: (si * 30 + deg) % 360 };
}

// 行星年取档:band ∈ least/mean/greater/greatest。
export function planetYears(planetEn, band){
	const row = PLANETARY_YEARS[planetEn];
	if(!row){ return null; }
	const b = ['least', 'mean', 'greater', 'greatest'].indexOf(band) >= 0 ? band : 'least';
	return row[b];
}
