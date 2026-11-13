// 经纬度查找(GeoCoordSelector/GeoCoordModal)选点后,把回传的地名(rec.name)并入命盘/事盘的 pos 字段
// —— 显示于左栏「地点」+ 随盘储存(localcharts/localcases)+ 进 AI 快照(aiAnalysisContext)。
//
// 语义(据实,单一真值):
//   rec.name === undefined  → 本次仅改时区(未重选坐标),不动 pos(保留原地名);
//   rec.name === ''         → 坐标类操作但无可读地名(地图裸点逆地理失败 / 手输经纬),据实清空(显示「未命名地点」);
//   rec.name === '上海市'    → 正常回填。
//
// 坐标类操作(选城市 / 搜地名 / 地图点选)在 GeoCoordSelector 里【一律】带 name 键(可为空串),
// 故 pos 与坐标始终同步;唯有纯改时区不带 name,借此保住旧地名。

function hasName(rec){
	return !!rec && rec.name !== undefined;
}

function normName(rec){
	return `${(rec && rec.name) || ''}`;
}

// fields 形态补丁({ key: { value } }):供 onFieldsChange({...}) 家族。返回 { pos: { value } } 或 {}。
export function geoNameFieldPatch(rec){
	if(!hasName(rec)){ return {}; }
	return { pos: { value: normName(rec) } };
}

// raw 形态补丁({ key: value }):供 changeCond / patchFields 等 raw 家族。返回 { pos } 或 {}。
export function geoNameRawPatch(rec){
	if(!hasName(rec)){ return {}; }
	return { pos: normName(rec) };
}

// 直改 fields 对象(flds.pos.value = …)家族:就地写入,flds.pos 缺失则跳过(不新建、不抛)。
export function applyGeoNameToFields(flds, rec){
	if(!hasName(rec) || !flds || !flds.pos){ return; }
	flds.pos.value = normName(rec);
}
