import * as AstroConst from '../constants/AstroConst.js';
import {
  EXALT_DEGREE as GL_EXALT_DEG,
  starDignityStatuses as glStarDignity,
  starMotionState as glStarMotion,
  starCombust as glStarCombust,
} from '../vendor/guolao/guolaoData.js';

/**
 * 七政四余 [星曜庙旺与星点动态（殿垣庙旺乐喜怒 · 顺逆留伏迟速）] 段。
 *
 * 函数体逐字取自上游 GuoLaoChartMain.js::buildStarDignityMotionSection —— 它是导出的纯函数，
 * 只吃 /chart 七政四余响应，不需要 Moira 规则服务。
 *
 * ⚠️ 同一批的另外三段（[虚实] / [本命化曜] / [流年流曜]）读的是 `moiraRules.weakSolid` 与
 * `moiraRules.yearStars`，二者只来自后端 `/qizheng/moira`。开源 astropy 只挂了
 * webqizhengelectionsrv / webqizhengkinsrv，**没有该路由**（仓内 vendored 实例实测 500），
 * 而本地回退 `buildLocalMoiraRules` 只产 houses/patterns/godHits，不产这两个字段。
 * 所以那三段在开源栈上不可得 —— 属带理由的欠账，不是待办。
 *
 * payload: { chart: <七政四余 /chart 响应>, fields?: {} }
 * return : { text }
 */
function buildStarDignityMotionSection(result, fields){
	const chart = result && result.chart ? result.chart : {};
	const objects = Array.isArray(chart.objects) ? chart.objects : [];
	if(!objects.length){ return ''; }
	const ecl = chart.displayCoord === 'ecliptic';
	const ZLIST = ['子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥'];
	const ziOf = (lon)=>{ const n = ((lon % 360) + 360) % 360; const s = Math.floor(n / 30) % 12; return ZLIST[(10 - s + 12) % 12] || ''; };
	const lonOf = (obj)=>{ const raw = obj && (ecl && obj.lon !== undefined ? obj.lon : (obj.ra !== undefined ? obj.ra : obj.lon)); return Number(raw); };
	const sun = objects.find((o)=>o && o.id === AstroConst.SUN);
	const sunLon = sun ? lonOf(sun) : NaN;
	const STAR_POINTS = [
		['日', AstroConst.SUN], ['月', AstroConst.MOON], ['金', AstroConst.VENUS], ['木', AstroConst.JUPITER],
		['水', AstroConst.MERCURY], ['火', AstroConst.MARS], ['土', AstroConst.SATURN],
		['计', AstroConst.SOUTH_NODE], ['罗', AstroConst.NORTH_NODE], ['炁', AstroConst.PURPLE_CLOUDS], ['孛', AstroConst.DARKMOON],
		['天', AstroConst.URANUS], ['海', AstroConst.NEPTUNE], ['冥', AstroConst.PLUTO],
	];
	const ANGLE_POINTS = [['升', AstroConst.ASC], ['顶', AstroConst.MC]];
	const rows = [];
	STAR_POINTS.forEach(([name, id])=>{
		const obj = objects.find((o)=>o && o.id === id);
		if(!obj){ return; }
		const lon = lonOf(obj);
		if(!Number.isFinite(lon)){ return; }
		const zhi = ziOf(lon);
		const ex = GL_EXALT_DEG[name];
		const atPeak = !!(ex && Math.floor((((lon % 360) + 360) % 360) / 30) % 12 === ex.signIndex && Math.abs((((lon % 360) + 360) % 360) % 30 - ex.deg) <= 1);
		const combust = glStarCombust(name, lon, sunLon);   // Moira 合日 3°(单一真值,与右栏星点动态同源)
		const belong = glStarDignity(name, zhi, atPeak).join('·') || '-';
		const motion = glStarMotion(name, Number(obj.lonspeed), combust) || '-';
		rows.push(`| ${name} | ${zhi} | ${belong} | ${motion} |`);
	});
	ANGLE_POINTS.forEach(([name, id])=>{
		const obj = objects.find((o)=>o && o.id === id);
		if(!obj){ return; }
		const lon = lonOf(obj);
		if(!Number.isFinite(lon)){ return; }
		rows.push(`| ${name} | ${ziOf(lon)} | - | - |`);
	});
	if(!rows.length){
		return '';
	}
	return ['| 曜 | 地支 | 所属 | 速度态 |', '| --- | --- | --- | --- |'].concat(rows).join('\n');
}

export function runGuolaoStarDignity(payload) {
  const source = payload && typeof payload === 'object' ? payload : {};
  const result = source.chart && typeof source.chart === 'object' ? source.chart : source;
  try {
    const body = buildStarDignityMotionSection(result, source.fields || {}) || '';
    if (!body) {
      return { text: '', error: { code: 'empty_star_dignity', message: '星曜庙旺/动态段为空（盘里没有可判的星点）。' } };
    }
    return { text: `[星曜庙旺与星点动态（殿垣庙旺乐喜怒 · 顺逆留伏迟速）]\n${body}` };
  } catch (error) {
    return { text: '', error: { code: 'star_dignity_build_failed', message: error instanceof Error ? error.message : `${error}` } };
  }
}

export default runGuolaoStarDignity;
