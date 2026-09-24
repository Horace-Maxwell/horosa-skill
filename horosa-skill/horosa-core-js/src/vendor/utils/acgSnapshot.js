// 占星地图(ACG)AI 导出专属真值快照。
// AstroAcg 每次 /location/acg 响应后调 setAcgSnapshot 存"最近一次地图状态"(模块级,零持久化);
// aiExport 在导出键为 astrochart_like 且当前上下文为占星地图时,经 buildAcgSectionText 拼入
//【占星地图】段(受导出段开关控制)。单一真值源:全部数字来自后端 ACGraph 响应,不在此重算。

const PLANET_CN = {
	Sun: '太阳', Moon: '月亮', Mercury: '水星', Venus: '金星', Mars: '火星',
	Jupiter: '木星', Saturn: '土星', Uranus: '天王星', Neptune: '海王星', Pluto: '冥王星',
	'North Node': '北交点', 'South Node': '南交点', Chiron: '凯龙星',
	'Dark Moon': '莉莉丝', 'Purple Clouds': '紫炁',
	Ceres: '谷神星', Pallas: '智神星', Juno: '婚神星', Vesta: '灶神星', Eris: '阋神星',
};
const MODE_CN = { mundo: '本体(in-mundo·真黄纬)', zodiac: '黄道度(β=0)' };
const COORD_CN = { geo: '地心', helio: '日心', topo: '站心' };   // [Q-151/AX-15⑥] UI 有站心档,快照曾直出「topo」
const REL_CN = { davison: '戴维森时空中点盘', composite: '中点合盘', synastry: '双人叠加' };
const KIND_CN = { transit: '行运', progressed: '二次推运' };
// [Q-440] 本地空间画法 / 地理等价流派·取数·流派缺省 0°♈ 子午线(镜像后端 GEODETIC_ZERO;自定义值走 uiState.geodeticZero)
const LS_MODE_CN = { great: '大圆', rhumb: '等角航线' };
const GEODETIC_CN = { sepharial: '塞法里尔', mcrae: '麦克雷', johndro: '约翰德罗' };
const GEODETIC_VAR_CN = { longitude: '黄经法', ra: '赤经法' };
const GEODETIC_ZERO_DEFAULT = { sepharial: 0, mcrae: 0, johndro: -30 };
// 交映事件中文(后端 PARAN_EVENTS:rise/set/mc/ic = 两星同时角化的各自事件)
const PARAN_EVENT_CN = { rise: '升', set: '落', mc: '中天', ic: '天底' };

let latest = null;

export function setAcgSnapshot(data, uiState){
	if(!data || !data.planets){
		return;
	}
	latest = { data, uiState: uiState || {}, at: Date.now() };
}

export function clearAcgSnapshot(){
	latest = null;
}

function fmtLon(v){
	if(v === undefined || v === null || !isFinite(v)){
		return '—';
	}
	const abs = Math.abs(v).toFixed(2);
	return `${abs}°${v >= 0 ? 'E' : 'W'}`;
}

function fmtLat(v){
	if(v === undefined || v === null || !isFinite(v)){
		return '—';
	}
	const abs = Math.abs(v).toFixed(2);
	return `${abs}°${v >= 0 ? 'N' : 'S'}`;
}

function ascAnchor(pts){
	// 升/降线是曲线:取 |纬度| 最小点(赤道附近)作代表经度
	if(!Array.isArray(pts) || !pts.length){
		return null;
	}
	let best = pts[0];
	for(let i = 1; i < pts.length; i++){
		if(Math.abs(pts[i].lat) < Math.abs(best.lat)){
			best = pts[i];
		}
	}
	return best;
}

// 生成【占星地图】导出段。无快照(用户没开过占星地图 tab)返回 ''(优雅降级,不报错)。
export function buildAcgSectionText(){
	if(!latest || !latest.data || !latest.data.planets){
		return '';
	}
	const d = latest.data;
	const meta = d.meta || {};
	const lines = [];
	lines.push('【占星地图】');
	const head = [];
	head.push(`口径 ${MODE_CN[meta.mode] || meta.mode || '本体'}`);
	head.push(`坐标系 ${COORD_CN[meta.coord] || meta.coord || '地心'}`);
	if(meta.draconic){ head.push(`龙黄道 ${meta.draconic === 'true' ? '真交点' : '平交点'}`); }
	if(meta.harmonic){ head.push(`谐波 H${meta.harmonic}`); }
	if(meta.vibration){ head.push('振动线 5/7/9'); }
	if(meta.nodeType === 'true'){ head.push('真交点'); }
	if(meta.lilithType && meta.lilithType !== 'mean'){ head.push(`Lilith ${({ true: '真', intp: '插值', body: '星体' })[meta.lilithType] || meta.lilithType}`); }
	if(meta.asteroids){ head.push('含小行星'); }
	if(meta.posType && meta.posType !== 'apparent'){ head.push(meta.posType === 'true' ? '真位置' : 'J2000读数'); }
	if(meta.horizon === 'apparent'){ head.push('折射地平'); }
	if(meta.ayanLabel){
		head.push(`恒星黄道读数 ${meta.ayanLabel}(岁差 ${meta.ayanVal}°)`);
	}
	if(meta.relMode){
		let rel = `关系盘 ${REL_CN[meta.relMode] || meta.relMode}`;
		if(meta.davison){
			rel += `(合成 ${meta.davison.date} ${meta.davison.time} UT @ ${meta.davison.lat}°, ${meta.davison.lon}°)`;
		}
		head.push(rel);
	}
	lines.push(head.join(' · '));
	lines.push('主要行星角化线(中天/天底=经线;上升/下降取赤道附近代表点):');
	Object.keys(d.planets).forEach((pk) => {
		const p = d.planets[pk];
		const L = p.lines || {};
		const asc = ascAnchor(L.asc);
		const desc = ascAnchor(L.desc);
		const parts = [
			`MC ${fmtLon(L.mc && L.mc.lon)}`,
			`IC ${fmtLon(L.ic && L.ic.lon)}`,
			`ASC ${asc ? fmtLon(asc.lon) : '—'}`,
			`DSC ${desc ? fmtLon(desc.lon) : '—'}`,
		];
		let extra = '';
		if(p.oob){
			extra += ' · 超界OOB';
		}
		if(typeof p.sidLon === 'number'){
			extra += ` · 恒星黄经 ${p.sidLon.toFixed(2)}°`;
		}
		lines.push(`- ${PLANET_CN[pk] || pk}:${parts.join(' / ')}${extra}`);
	});
	if(d.ccg && d.ccg.planets){
		lines.push(`CCG 时间地图(${d.ccg.date} ${d.ccg.time || ''} · ${d.ccg.mix === 'mixed' ? '内二推/外行运' : (d.ccg.mix === 'transit' ? '全行运' : '全二次推运')}):`);
		Object.keys(d.ccg.planets).forEach((pk) => {
			const p = d.ccg.planets[pk];
			lines.push(`- ${KIND_CN[p.kind] || p.kind}${PLANET_CN[pk] || pk}:MC ${fmtLon(p.lines && p.lines.mc && p.lines.mc.lon)}(黄经 ${p.lon}°)`);
		});
	}
	if(d.second && d.second.planets){
		const bs = Object.keys(d.second.planets).slice(0, 10).map((pk) => {
			const p = d.second.planets[pk];
			return `${PLANET_CN[pk] || pk} MC ${fmtLon(p.lines && p.lines.mc && p.lines.mc.lon)}`;
		});
		lines.push(`B 盘(双人叠加)四轴 MC:${bs.join(';')}`);
	}
	if(Array.isArray(d.stars) && d.stars.length){
		lines.push(`固定星线(${d.stars.length} 恒星):${d.stars.map((s) => `${s.name} MC ${fmtLon(s.lines && s.lines.mc && s.lines.mc.lon)}`).join(';')}`);
	}
	const point = latest.uiState && latest.uiState.pointReport;
	if(point && Array.isArray(point.hits)){
		lines.push(`落点分析(${Math.abs(point.lat).toFixed(2)}°${point.lat >= 0 ? 'N' : 'S'} ${fmtLon(point.lon)},orb ${point.orb}°):` + (point.hits.length
			? point.hits.map((h) => `${PLANET_CN[h.planet] || h.planet}${({ Asc: '上升', Desc: '下降', MC: '中天', IC: '天底' })[h.angle] || h.angle}线(偏差 ${h.orb}°)`).join('、')
			: '无行星线经过'));
	}
	// [Q-440/T-403] ◆ 本地空间线 / ◆ 地理等价线:两图层开启时才进快照(纯渲染开关,数据恒在响应里),
	// 数据=后端 lines.lsAz(方位/高度)与 lines.geodetic(地理 MC/IC 经度),口径行写画法/流派/取数/子午线。
	const uiLayers = latest.uiState || {};
	if(uiLayers.showLS){
		const rows = [];
		Object.keys(d.planets).forEach((pk) => {
			const la = d.planets[pk].lines && d.planets[pk].lines.lsAz;
			if(!la || typeof la.az !== 'number'){ return; }
			rows.push(`| ${PLANET_CN[pk] || pk} | ${la.az.toFixed(1)}° | ${typeof la.alt === 'number' ? la.alt.toFixed(1) + '°' : '—'} |`);
		});
		if(rows.length){
			lines.push(`◆ 本地空间线(画法 ${LS_MODE_CN[meta.lsMode] || meta.lsMode || '大圆'};自出生地沿各星罗盘方位角延伸,方位角=正北起顺时针,高度角=出生时刻该星地平高度):`);
			lines.push('| 星 | 方位角 | 高度角 |');
			lines.push('| --- | --- | --- |');
			lines.push(...rows);
		}
	}
	if(uiLayers.showGeodetic){
		const rows = [];
		Object.keys(d.planets).forEach((pk) => {
			const g = d.planets[pk].lines && d.planets[pk].lines.geodetic;
			if(!g || !g.mc || typeof g.mc.lon !== 'number'){ return; }
			rows.push(`| ${PLANET_CN[pk] || pk} | ${fmtLon(g.mc.lon)} | ${fmtLon(g.ic && g.ic.lon)} |`);
		});
		if(rows.length){
			const school = meta.geodetic || 'sepharial';
			const zeroRaw = `${uiLayers.geodeticZero || ''}`.trim();
			const zero = zeroRaw !== '' && Number.isFinite(Number(zeroRaw)) ? Number(zeroRaw) : (GEODETIC_ZERO_DEFAULT[school] || 0);
			lines.push(`◆ 地理等价线(流派 ${GEODETIC_CN[school] || school} · 取数 ${GEODETIC_VAR_CN[meta.geodeticVar] || meta.geodeticVar || '黄经法'} · 0°♈ 子午线 ${fmtLon(zero)}${zeroRaw !== '' ? '(自定义)' : '(流派缺省)'};黄道度↔地理经度的时间无关映射,与角化线不同源):`);
			lines.push('| 星 | 地理MC | 地理IC |');
			lines.push('| --- | --- | --- |');
			lines.push(...rows);
		}
	}
	// ◆ 行星交映 Parans:条件子块(仅当图层开关开启且后端有数据;与「落点分析」同风格)。
	// 数据=后端响应 d.parans(两行星同时角化的纬度线);过滤(lum=仅日月对)与 1° 去重口径同 AcgD3Map 图面。
	const ui = latest.uiState || {};
	if(ui.paranMode && ui.paranMode !== 'off' && Array.isArray(d.parans) && d.parans.length){
		const isLum = (p) => p.a === 'Sun' || p.b === 'Sun' || p.a === 'Moon' || p.b === 'Moon';
		const list = ui.paranMode === 'all' ? d.parans : d.parans.filter(isLum);
		const seen = new Set();
		const rows = [];
		list.forEach((p) => {
			const k = Math.round(p.lat);   // 同图面:重叠纬线 1° 去重,首见者代表
			if(seen.has(k)) return;
			seen.add(k);
			rows.push(`| ${PLANET_CN[p.a] || p.a} | ${PARAN_EVENT_CN[p.aEvent] || p.aEvent} | ${PLANET_CN[p.b] || p.b} | ${PARAN_EVENT_CN[p.bEvent] || p.bEvent} | ${fmtLat(p.lat)} |`);
		});
		if(rows.length){
			lines.push(`◆ 行星交映(${ui.paranMode === 'all' ? '全部行星对' : '仅日月对'},同图 1° 去重,共 ${rows.length} 条纬线):`);
			lines.push('| 星A | 事件 | 星B | 事件 | 纬度 |');
			lines.push('| --- | --- | --- | --- | --- |');
			lines.push(...rows);
		}
	}
	// ◆ 固定星交映:恒星×行星同时角化纬线;双 opt-in(固定星线+交映开关)同 AcgD3Map;星名取 d.stars key→name。
	if(ui.showStarParans && Array.isArray(d.starParans) && d.starParans.length){
		const starCN = {};
		(Array.isArray(d.stars) ? d.stars : []).forEach((s) => { starCN[s.key] = s.name; });
		const seen = new Set();
		const rows = [];
		d.starParans.forEach((p) => {
			const k = Math.round(p.lat);   // 同图面 1° 去重
			if(seen.has(k)) return;
			seen.add(k);
			rows.push(`| ${starCN[p.star] || p.star} | ${PARAN_EVENT_CN[p.sEvent] || p.sEvent} | ${PLANET_CN[p.planet] || p.planet} | ${PARAN_EVENT_CN[p.pEvent] || p.pEvent} | ${fmtLat(p.lat)} |`);
		});
		if(rows.length){
			lines.push(`◆ 固定星交映(同图 1° 去重,共 ${rows.length} 条纬线):`);
			lines.push('| 星A | 事件 | 星B | 事件 | 纬度 |');
			lines.push('| --- | --- | --- | --- | --- |');
			lines.push(...rows);
		}
	}
	return lines.join('\n');
}
