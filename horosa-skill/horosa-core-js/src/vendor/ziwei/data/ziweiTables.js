// 紫微斗数排盘数据表 loader（镜像 Java ZiWeiHelper 的载入/拆表逻辑）。
// 原始 JSON 自 astrostudycn 后端资源逐字节迁来(byte-exact)，此处 import + 必要变换：
//   - 火铃/将前/小限：原始用三合组键"寅午戌" → 拆成 子..亥 每支一项。
//   - 四化：不在此(复用 ZWConst.getActiveSiHuaGan，单一真值源、随流派切换)。
import starsMainJson from './tables/ziweistarsmain.json' with { type: 'json' };
import yearGanJson from './tables/ziweiyeargan.json' with { type: 'json' };
import yearZiJson from './tables/ziweiyearzi.json' with { type: 'json' };
import monthJson from './tables/ziweimonth.json' with { type: 'json' };
import timeZiJson from './tables/ziweitimezi.json' with { type: 'json' };
import huoLinJson from './tables/ziweihuolin.json' with { type: 'json' };
import smallStarsJson from './tables/ziweismallstars.json' with { type: 'json' };
import jiangJson from './tables/ziweijiang.json' with { type: 'json' };
import zuJson from './tables/ziweizu.json' with { type: 'json' };
import douJson from './tables/ziweidou.json' with { type: 'json' };
import xiaoXianJson from './tables/ziweixiaoxian.json' with { type: 'json' };
import starLightJson from './tables/ziweistarlight.json' with { type: 'json' };
import starLightQuanshuJson from './tables/ziweistarlight_quanshu.json' with { type: 'json' };
import geJson from './tables/ziweige.json' with { type: 'json' };

// 把三合组键(如"寅午戌")的表拆成每个地支单独一项。
function expandSanHe(obj){
	const out = {};
	Object.keys(obj || {}).forEach((key)=>{
		const val = obj[key];
		for(let i = 0; i < key.length; i++){ out[key.charAt(i)] = val; }
	});
	return out;
}

// 十四主星步长（紫微系逆 / 天府系顺）
export const NORTH_MAIN_STEP = starsMainJson.north;
export const SOUTH_MAIN_STEP = starsMainJson.south;

// 年干系（禄存/羊陀/魁钺/天官天福天厨/截空）：{name:{type, pos:{干:zi}}};截空 pos 为 2 字(双星)。
export const STARS_YEAR_GAN = yearGanJson;
// 年支系：{name:{type, pos:{支:zi}}}
export const STARS_YEAR_ZI = yearZiJson;
// 生月系：{name:{type, pos:{月名:zi}}}（月名 正月..腊月）
export const STARS_MONTH = monthJson;
// 生时系：{name:{type, pos:{时支:zi}}}
export const STARS_TIME_ZI = timeZiJson;
// 火铃：年支 → {火星:{时支:zi}, 铃星:{时支:zi}}
export const STARS_HUOLIN = expandSanHe(huoLinJson);
// 将前十二神：年支 → {将星:zi,...}
export const STARS_JIANG = expandSanHe(jiangJson);
// 小限起宫：年支 → zi
export const XIAOXIAN_START = expandSanHe(xiaoXianJson);

// 小星组（十二宫名 / 长生12 / 博士12 / 太岁12）
export const HOUSES = smallStarsJson.houses;
export const CHANGSHENG_12 = smallStarsJson.changsheng;
export const STARS_BOSI = smallStarsJson.bosi;
export const STARS_TAISUI = smallStarsJson.taisui;

// 命主(命宫支) / 身主(生年支)
export const LIFE_MASTER = zuJson.life;
export const BODY_MASTER = zuJson.body;
// 斗君：{月名:{时支:zi}}
export const DOUJUN = douJson;
// 庙旺亮度：{星:{支:亮度}}。默认 zi_jian(自建≈通行);quanshu=《全书》delta 覆盖(擎羊子酉旺/铃星独立表/亥卯未火星得)。
export const STAR_LIGHT = starLightJson;
export const STAR_LIGHT_QUANSHU = starLightQuanshuJson;
// 按亮度源取某星在某支的亮度：quanshu 源命中 delta 用《全书》值，缺格回落自建默认表(零回归)。
export function starLightOf(star, zhi, source){
	if(source === 'quanshu'){
		const o = STAR_LIGHT_QUANSHU[star];
		if(o && o[zhi] != null){ return o[zhi]; }
	}
	const b = STAR_LIGHT[star];
	return b ? b[zhi] : undefined;
}
// 格局库（WP-G 用）
export const GE_PATTERNS = geJson;

// 月名(正月..腊月) ↔ 月数(1..12)
export const MONTH_CN = ['正月', '二月', '三月', '四月', '五月', '六月', '七月', '八月', '九月', '十月', '冬月', '腊月'];
export function monthCnOf(monthInt){ return MONTH_CN[((monthInt - 1) % 12 + 12) % 12]; }
