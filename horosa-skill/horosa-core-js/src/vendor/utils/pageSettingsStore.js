// 技法页「排盘设置」跨会话保留 · 单源件。
//
// 为什么要有:各技法页左栏的排盘口径(贵人体系 / 换将 / 分昼夜 / 流派参数 …)历来只活在组件 state 里,
// 关掉软件再开就回到缺省,用户每次都要重设一遍。个别页各自手写过一份落盘(六爻 / 小六壬 / 灵棋 …),
// 写法不一、校验不一;新页又容易整页漏掉。这里收成一份:声明 schema → 得到 load / save / reset,
// 校验、配额兜底、坏数据回缺省都在这一处。
//
// 口径(全站一致):
//   · 只保留「设置」——口径 / 流派 / 算法 / 显示偏好。时间、地点、占事、起卦数字这类「输入」不进 schema。
//   · 只在**用户亲手改控件**时落盘。载入命盘 / 事盘回灌、宿主页下发口径、AI 助手改设置都不经这里
//     (否则打开一份旧案就把你的缺省悄悄改了)。
//   · 择日宿主里内嵌的那份技法页:只有宿主的扫描口径**取自内嵌盘**时才与独立页共用这份保存值(奇门择日);
//     扫描引擎另有钉死口径的(六壬 / 太乙 / 三式择日)内嵌盘既不读也不写 —— 否则点选命中行看到的盘就不是扫描判定的那一盘。
//   · 载入事盘 / 记录时,记录里**没有**的设置键回出厂值(fillMissing),不沿用保存值:旧案是按出厂口径存下的,
//     不能因为你后来改了缺省,打开它时就被按新口径重排。
//   · map 型(覆盖层 / 子开关表)只落亲手改的那一个子键(saveMapEntry):组件 state 里那张表可能刚被旧案回灌过。
//   · 离不开逐课输入的起法 / 模式不进候选(只留法不留数 = 重开后一个带空输入的起法);没有该控件的页不读共享保存值
//     (看不见的设置不许暗中改结果)。
//   · 读端永不抛:键不存在 / 不是 JSON / 字段类型不对 / 取值不在候选里 → 该字段回缺省,其它字段照常。
//   · 值形态严格:布尔就是布尔、数字就是数字(0 ≠ false、'1' ≠ 1),不做宽松转换 —— 宽松转换是死开关的温床。
import { safeLocalStorageGet, safeLocalStorageSet, safeLocalStorageRemove } from '../gua/safeStorage.js';

const FIELD_TYPES = ['boolean', 'number', 'string'];

function typeOfSpec(spec){
	if(spec && FIELD_TYPES.indexOf(spec.type) >= 0){ return spec.type; }
	return typeof (spec ? spec.def : undefined);
}

// 单字段校验:合法返回 { ok:true, value },否则 { ok:false }。
// 'map' 型 = 一组同族子开关收在一个对象里(如太乙流派六键):逐子键各自校验,坏的子键回该子键缺省、未知子键丢弃,
// 整体只有「不是对象」才算不合法 —— 一个子键坏了不连坐其它子键。
// 'map' + sparse = 覆盖层(如卜卦判读参数 / 地占逐项覆盖):只留显式改过且合法的子键,缺席即「跟随预设」。
export function validateSettingValue(spec, value){
	if(!spec){ return { ok: false }; }
	if(spec.type === 'map'){
		if(!value || typeof value !== 'object' || Array.isArray(value)){ return { ok: false }; }
		const out = {};
		Object.keys(spec.keys || {}).forEach((k)=>{
			const sub = spec.keys[k];
			const r = Object.prototype.hasOwnProperty.call(value, k) ? validateSettingValue(sub, value[k]) : { ok: false };
			// sparse = 「覆盖层」语义:只留用户显式改过的子键,缺席 = 跟随预设 / 缺省(不补缺省值,空对象也合法)。
			// 子键的 def 在 sparse 下只用来定类型。
			if(spec.sparse){
				if(r.ok){ out[k] = r.value; }
				return;
			}
			out[k] = r.ok ? r.value : sub.def;
		});
		return { ok: true, value: out };
	}
	// 'list' 型 = 从固定候选里勾选出的一组(如占星地图的主体线选集):不是数组 → 不收;候选外的项丢掉、重复项去重,
	// 其余照收(空数组合法 = 用户一项都没勾)。一项坏了不连坐整组。
	if(spec.type === 'list'){
		if(!Array.isArray(value)){ return { ok: false }; }
		const allowed = Array.isArray(spec.oneOf) ? spec.oneOf : null;
		const out = [];
		value.forEach((v)=>{
			if(allowed ? allowed.indexOf(v) < 0 : typeof v !== 'string'){ return; }
			if(out.indexOf(v) < 0){ out.push(v); }
		});
		return { ok: true, value: out };
	}
	const t = typeOfSpec(spec);
	if(typeof value !== t){ return { ok: false }; }
	if(t === 'number'){
		if(!isFinite(value)){ return { ok: false }; }
		if(spec.int && Math.floor(value) !== value){ return { ok: false }; }
		if(typeof spec.min === 'number' && value < spec.min){ return { ok: false }; }
		if(typeof spec.max === 'number' && value > spec.max){ return { ok: false }; }
	}
	if(t === 'string' && typeof spec.maxLen === 'number' && value.length > spec.maxLen){ return { ok: false }; }
	if(Array.isArray(spec.oneOf) && spec.oneOf.indexOf(value) < 0){ return { ok: false }; }
	return { ok: true, value };
}

export function definePageSettings(storageKey, schema){
	const fields = Object.keys(schema || {});
	function defOf(spec){
		if(spec.type === 'map' && spec.sparse){ return {}; }
		if(spec.type === 'list'){ return (spec.def || []).slice(); }   // 每次新建,不共享引用
		if(spec.type === 'map'){
			const o = {};
			Object.keys(spec.keys || {}).forEach((k)=>{ o[k] = spec.keys[k].def; });
			return o;
		}
		return spec.def;
	}
	function defaults(){
		const out = {};
		fields.forEach((f)=>{ out[f] = defOf(schema[f]); });
		return out;
	}
	function readRaw(){
		try{
			const raw = safeLocalStorageGet(storageKey);
			if(!raw){ return {}; }
			const obj = JSON.parse(raw);
			const vals = obj && typeof obj === 'object' && obj.values && typeof obj.values === 'object' ? obj.values : null;
			return vals || {};
		}catch(e){
			return {};
		}
	}
	// 缺省 + 已保存的合法值。永不抛。
	function load(){
		const out = defaults();
		const vals = readRaw();
		fields.forEach((f)=>{
			if(Object.prototype.hasOwnProperty.call(vals, f)){
				const r = validateSettingValue(schema[f], vals[f]);
				if(r.ok){ out[f] = r.value; }
			}
		});
		return out;
	}
	// 只返回**确实保存过**且合法的字段(不补缺省)。给「缺省值另有来源」的页用:
	// 比如某键没保存过时要跟随跨页共享字段 / 全局设置的现值,而不是 schema 里的静态缺省。永不抛。
	function loadSaved(){
		const out = {};
		const vals = readRaw();
		fields.forEach((f)=>{
			if(Object.prototype.hasOwnProperty.call(vals, f)){
				const r = validateSettingValue(schema[f], vals[f]);
				if(r.ok){ out[f] = r.value; }
			}
		});
		return out;
	}
	// 只收 schema 里有、且校验通过的字段;其余一概忽略(通用 handler 可以放心把任何 field 丢进来)。
	// 返回本次真正写进去的字段名数组。
	function save(partial){
		if(!partial || typeof partial !== 'object'){ return []; }
		// 先看这次有没有要写的:通用 handler 会把输入类键(文本框每次击键)也丢进来,那种调用不该去读 / 解析存储。
		const incoming = {};
		const written = [];
		Object.keys(partial).forEach((f)=>{
			if(fields.indexOf(f) < 0){ return; }
			const r = validateSettingValue(schema[f], partial[f]);
			if(!r.ok){ return; }
			incoming[f] = r.value;
			written.push(f);
		});
		if(!written.length){ return written; }
		const vals = readRaw();
		const kept = {};
		fields.forEach((f)=>{
			if(!Object.prototype.hasOwnProperty.call(vals, f)){ return; }
			const r0 = validateSettingValue(schema[f], vals[f]);
			if(r0.ok){ kept[f] = r0.value; }   // 存校验后的值(map 型顺手清掉未知子键)
		});
		written.forEach((f)=>{ kept[f] = incoming[f]; });
		try{
			safeLocalStorageSet(storageKey, JSON.stringify({ v: 1, values: kept }));
		}catch(e){ /* 配额 / 隐私模式:静默,设置留在内存里,本次会话照常用 */ }
		return written;
	}
	// map 型字段只落**这一次亲手改的那个子键**:以库里已保存的那份为底,不以组件当前 state 为底。
	// 组件 state 里那张表可能刚被一份旧案回灌过 —— 整张存下去,旧案里其余子项也就成了你的缺省
	// (正是文件头说的「打开一份旧案就把你的缺省悄悄改了」)。value === undefined = 撤销该子键:
	// 稀疏覆盖层 = 删掉(回到「跟随预设」),整张表 = 回该子键缺省。未知子键 / 值不合法 → 不写。
	function saveMapEntry(field, subKey, value){
		const spec = schema[field];
		if(!spec || spec.type !== 'map' || !spec.keys || !Object.prototype.hasOwnProperty.call(spec.keys, subKey)){ return []; }
		const base = spec.sparse ? (loadSaved()[field] || {}) : load()[field];
		const next = { ...base };
		if(value === undefined){
			if(spec.sparse){ delete next[subKey]; }else{ next[subKey] = spec.keys[subKey].def; }
		}else{
			const r = validateSettingValue(spec.keys[subKey], value);
			if(!r.ok){ return []; }
			next[subKey] = r.value;
		}
		return save({ [field]: next });
	}
	// 载入事盘 / 记录时用:记录里**没有**的设置键回出厂值,而不是留着本机保存的偏好。
	// 这些键现在跨会话保留,页面一打开 state 里就是你的偏好;而存案只记「当时有的键」—— 按出厂口径存下的旧案不带后来才有的键,
	// 「只还原记录里有的键」就等于让旧案沿用你现在的偏好:盘被重排、与存档里的快照对不上。返回新对象,不改入参。
	function fillMissing(obj){
		const out = { ...(obj || {}) };
		fields.forEach((f)=>{ if(out[f] === undefined){ out[f] = defOf(schema[f]); } });
		return out;
	}
	function reset(){
		try{ safeLocalStorageRemove(storageKey); }catch(e){ /* noop */ }
		return defaults();
	}
	// 从一个 state 形状里摘出 schema 字段(比如存案 / 快照要带上当前口径时用)。
	function pick(obj){
		const out = {};
		if(!obj || typeof obj !== 'object'){ return out; }
		fields.forEach((f)=>{ if(Object.prototype.hasOwnProperty.call(obj, f)){ out[f] = obj[f]; } });
		return out;
	}
	return { key: storageKey, fields: fields.slice(), schema, defaults, load, loadSaved, save, saveMapEntry, fillMissing, reset, pick, has: (f)=>fields.indexOf(f) >= 0 };
}
