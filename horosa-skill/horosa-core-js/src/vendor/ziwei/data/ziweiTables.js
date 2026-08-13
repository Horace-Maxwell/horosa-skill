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
import starLightQuanshuFullJson from './tables/ziweistarlight_quanshu_full.json' with { type: 'json' };
import geJson from './tables/ziweige.json' with { type: 'json' };
import liuChangQuJson from './tables/ziweiliuchangqu.json' with { type: 'json' };

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

// 命主表(取支两法:默认生年支=Java 同源,ming_branch 档=命宫支经典法) / 身主(恒生年支)
export const LIFE_MASTER = zuJson.life;
export const BODY_MASTER = zuJson.body;
// 斗君：{月名:{时支:zi}}
export const DOUJUN = douJson;
// 庙旺亮度：{星:{支:亮度}}。默认 zi_jian(=中州五档口径,血统金标 ziweiBrightnessLineage 钉死);
// quanshu=《全书》煞星篇 delta 覆盖(擎羊子酉旺/铃星独立表/亥卯未火星得)。
export const STAR_LIGHT = starLightJson;
export const STAR_LIGHT_QUANSHU = starLightQuanshuJson;
// 亮度源注册表:key=brightnessSource 枚举值;'zi_jian'(默认)不注册=直落基表;
// 未知 key(旧版本 LS 残值/降级场景)同样 miss 落基表=安全降级。新增派系只在此加一行。
export const STAR_LIGHT_SOURCES = {
	quanshu: starLightQuanshuJson,
	// 《全书》七档全表(庙旺得利平不陷;通行整理表谱系,2026-08-07 考据签字版):
	// 20 星=十四正曜+昌曲+火铃+羊陀;未载之曜(魁钺/天马/空劫/四化等)回落基表——七档表
	// 考据源实有行仅此,绝不臆造补行。null 格=该星结构上不可落之宫(与基表 34 空格同惯例)。
	quanshu_full: starLightQuanshuFullJson,
};
// ===== [B14] 自定义亮度表('custom' 档) =====
// 取值层级=随盘注入单例 > 本机 LS 全量快照('ziweiBrightnessCustom') > 基表。
// 挂载/导出侧临时注入走单例(builder set→finally 清,绝不写 LS);本机编辑器保存写 LS 后必须
// resetBrightnessCustomCache() 失效缓存,否则渲染仍读旧表。绝不进 needsLocalEngine(纯显示层)。
export const ZWBrightnessCustom = { override: null };
export const BRIGHTNESS_GRADES = ['庙', '旺', '得', '地', '利', '平', '闲', '不', '陷'];
let brightnessCustomCache;   // undefined=未读; null=无有效表
export function resetBrightnessCustomCache(){ brightnessCustomCache = undefined; }
// 归一/校验:接受对象或 JSON 字符串,形状={星:{支:档}};档限 9 值域,非法格丢弃;空表返 null。
export function normalizeBrightnessCustomTable(raw){
	let obj = raw;
	if(typeof raw === 'string'){
		if(!raw.trim()){ return null; }
		try{ obj = JSON.parse(raw); }catch(e){ return null; }
	}
	if(!obj || typeof obj !== 'object' || Array.isArray(obj)){ return null; }
	const out = {};
	Object.keys(obj).forEach((star)=>{
		const row = obj[star];
		if(!row || typeof row !== 'object' || Array.isArray(row)){ return; }
		const clean = {};
		Object.keys(row).forEach((zhi)=>{
			if('子丑寅卯辰巳午未申酉戌亥'.indexOf(zhi) >= 0 && BRIGHTNESS_GRADES.indexOf(row[zhi]) >= 0){
				clean[zhi] = row[zhi];
			}
		});
		if(Object.keys(clean).length){ out[star] = clean; }
	});
	return Object.keys(out).length ? out : null;
}
function brightnessCustomTable(){
	if(ZWBrightnessCustom.override){ return ZWBrightnessCustom.override; }
	if(brightnessCustomCache === undefined){
		try{ brightnessCustomCache = normalizeBrightnessCustomTable(localStorage.getItem('ziweiBrightnessCustom')); }
		catch(e){ brightnessCustomCache = null; }
	}
	return brightnessCustomCache;
}

// 按亮度源取某星在某支的亮度：源表命中用其值，缺格回落基表(零回归;辅曜未载之星同此语义)。
// custom 档同律:自定义表命中格用其值,缺格/无表回落基表=安全降级。
export function starLightOf(star, zhi, source){
	if(source === 'custom'){
		const ct = brightnessCustomTable();
		if(ct){
			const co = ct[star];
			if(co && co[zhi] != null){ return co[zhi]; }
		}
		const cb = STAR_LIGHT[star];
		return cb ? cb[zhi] : undefined;
	}
	const t = STAR_LIGHT_SOURCES[source];
	if(t){
		const o = t[star];
		if(o && o[zhi] != null){ return o[zhi]; }
	}
	const b = STAR_LIGHT[star];
	return b ? b[zhi] : undefined;
}
// 流昌/流曲位置表(运限流曜用,{流昌:{干:支},流曲:{干:支}})
export const STARS_LIU_CHANGQU = liuChangQuJson;
// 格局库（WP-G 用）
export const GE_PATTERNS = geJson;

// 月名(正月..腊月) ↔ 月数(1..12)
export const MONTH_CN = ['正月', '二月', '三月', '四月', '五月', '六月', '七月', '八月', '九月', '十月', '冬月', '腊月'];
export function monthCnOf(monthInt){ return MONTH_CN[((monthInt - 1) % 12 + 12) % 12]; }
