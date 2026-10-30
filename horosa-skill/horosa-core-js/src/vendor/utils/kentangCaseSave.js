// headless stub：上游 getStore() 取 dva 全局 store（读「当前载入的事盘」）。headless 无 store、也没有「载入的旧案」——
// 设置一律由每次调用显式传入，故恒 null → getKentangSavedCasePayload 回 null（与上游「未载入事盘」同一分支）。
const getStore = () => null;
// headless stub：DateTime 只在 UI 草稿恢复链（deserializeBirthDraft → buildBirthFields → cloneDateTimeSafe）里用，
// 该链不被任何 headless 导出调用；真被调到时构造即抛明确错误，而不是被 try/catch 吞掉的 ReferenceError。
class DateTime { constructor(){ throw new Error('headless stub: components/comp/DateTime is not vendored'); } }
import { isCaseDivTimeText, parseCaseDivTimeParts, caseDivTimeDateOnly } from './caseDivTime.js';
// headless stub：utils/constants.js 混着后端地址（ServerRoot 读 window / localStorage），不 vendor；
// 这里只要四个缺省坐标常量，值与上游 constants.js 逐字相同。
const DefLat = '26n04';
const DefLon = '119e19';
const DefGpsLat = 26.076417371316914;
const DefGpsLon = 119.31516153077507;

function getFieldValue(fields, key, fallback = ''){
	if(!fields || !fields[key]){
		return fallback;
	}
	const value = fields[key].value;
	return value === undefined || value === null ? fallback : value;
}

function getCaseDateTime(fields){
	const dateValue = getFieldValue(fields, 'date', null);
	const timeValue = getFieldValue(fields, 'time', null);
	if(dateValue && timeValue && dateValue.format && timeValue.format){
		return `${dateValue.format('YYYY-MM-DD')} ${timeValue.format('HH:mm:ss')}`;
	}
	return '';
}

// 🔴「非字面坐标」口径快照 —— 存案必带的第二真值源,单一出处。
// after23NewDay(日界点)/lateZiHourUseNextDay(晚子时)/guaAfter23NewDay(卦日界)/timeAlg(时间算法)
// 这四项不写进 record 顶层,而是塞进 payload.fieldSnapshot;载档时 user.js applyCase 的
// pickCaseField 正是从这里回灌 —— 取不到就跳过、沿用全局当前值,于是「存档时把日界点设成非默认、
// 载回来日柱/时柱直接算错」。凡是自建 record 的存案入口都必须调本函数,不许另抄一份。
export function caseFieldSnapshot(fields){
	const snap = {};
	['after23NewDay', 'lateZiHourUseNextDay', 'guaAfter23NewDay', 'timeAlg'].forEach((key)=>{
		const v = getFieldValue(fields, key, null);
		if(v !== null && v !== ''){ snap[key] = v; }
	});
	return snap;
}

// 性别随档(applyCase 读 record.gender 还原;无则 null → 载入跳过、不改现状)。
// 性别影响取用神等判读(如六爻占婚男取妻财/女取官鬼),不随档则载回来用神错位。
export function caseGenderValue(fields){
	return getFieldValue(fields, 'gender', null);
}

function caseCidOf(userState){
	const c = userState && userState.currentCase ? userState.currentCase : null;
	return c && c.cid && c.cid.value !== undefined && c.cid.value !== null && c.cid.value !== '' ? `${c.cid.value}` : '';
}

function currentUserState(){
	try{
		const store = getStore();
		return store && store.user ? store.user : null;
	}catch(e){ return null; }
}

export function openKentangCaseDrawer({ dispatch, fields, module, label, payload }){
	if(!dispatch || !module){
		return;
	}
	const divTime = getCaseDateTime(fields);
	const extraFieldSnapshot = caseFieldSnapshot(fields);
	dispatch({
		type: 'astro/openDrawer',
		payload: {
			key: 'caseadd',
			record: {
				event: `${label || module}占断${divTime ? ` ${divTime}` : ''}`,
				caseType: module,
				divTime,
				zone: getFieldValue(fields, 'zone'),
				lat: getFieldValue(fields, 'lat'),
				lon: getFieldValue(fields, 'lon'),
				gpsLat: getFieldValue(fields, 'gpsLat'),
				gpsLon: getFieldValue(fields, 'gpsLon'),
				pos: getFieldValue(fields, 'pos'),
				gender: caseGenderValue(fields),
				payload: {
					module,
					version: 1,
					savedAt: new Date().toISOString(),
					fieldSnapshot: extraFieldSnapshot,
					...(payload || {}),
				},
				sourceModule: module,
			},
		},
	});
}

export function parseKentangCasePayload(raw){
	if(!raw){
		return null;
	}
	if(typeof raw === 'string'){
		try{
			return JSON.parse(raw);
		}catch(e){
			return null;
		}
	}
	if(typeof raw === 'object'){
		return raw;
	}
	return null;
}

// 🔴 读档去重键 —— 单一真值源:**只认显式载入**。
// 各技法读档都有 `!force && lastRestoredCaseId === caseVersion` 这道去重守卫(lastRestoredCaseId 只在构造函数初始化、
// 子技法面板常驻挂载)。当前事盘(currentCase)除了「在列表里点载入」(user/applyCase)之外还会被三条路径换掉:
// 点「编辑」(setCurrentCase 设成被编辑的那条)、「存为事盘」(addCase → setCurrentCase 设成刚存的那条)、
// 「保存编辑」(updateCase 换掉更新时间)。键若跟着当前事盘的 cid / 更新时间走,这三条都被各页当成一次载入:
// 把列表里那条的卦盖到屏幕上、自己还原自己、在途扫描被取消。
// 所以键只由显式载入决定:applyCase 同一次写下 appliedCaseCid 与载入代次 caseApplySeq(+1);
// 当前事盘不是显式载入的那条 → null(不还原);是 → `模块|载入的 cid|载入代次`(不含更新时间)。
// 同一条记录再点一次载入 → 代次变 → 必还原;改时间等无关变化 → 键不变 → 守卫照旧拦住。
// 界面之外改了已载入事盘的内容要重显时,显式推进载入代次,不靠更新时间隐式触发。推进只在一处:user 模型的
// reloadCurrentCaseFromStore(经 user/syncRecordFromStore),来源清单 = 采纳 / 撤销采纳 AI 提案、别的窗口、单库导入整条替换、影子并回、恢复;
// 只改不影响起课的键(展示 / 管理 / 记账 / 关联字段,localRecordStore.RECORD_NON_CAST_FIELDS)不推进。设当前事盘的全部位点登记在 caseRestoreExplicitLoadOnly.test.js(载入类 / 非载入类),
// 改本键的输入集合时须逐个过一遍。
// 凡读档去重键一律调本函数,不许另拼一份。
export function caseRestoreKey(module, userState){
	const us = userState === undefined ? currentUserState() : userState;
	const cid = caseCidOf(us);
	if(!cid){ return null; }
	const applied = us && us.appliedCaseCid !== undefined && us.appliedCaseCid !== null ? `${us.appliedCaseCid}` : '';
	if(!applied || applied !== cid){ return null; }
	const seq = us.caseApplySeq ? us.caseApplySeq : 0;
	return `${module || ''}|${applied}|${seq}`;
}

// 载入的这条事盘的时间 / 地点 / 性别 / 日界口径 → fields 补丁(与 models/user applyCase 写主盘同一份映射)。
// 择日宿主里内嵌的六壬 / 太乙 / 三式载入存案时交给宿主覆盖层:左栏与之后的重排都回到存案那一刻(此前左栏停在择日页当前时刻)。
// 不是这一模块的事盘 / 没有起课时刻 → null。时间算法不在里面(各页只作用本页)。
export function getKentangSavedCaseFieldsPatch(module){
	if(!getKentangSavedCasePayload(module)){ return null; }
	return currentCaseFieldsPatch();
}

// 经纬串 → 十进制度(与 AstroHelper.convertLonStrToDegree / convertLatStrToDegree 同一公式 度 + 分 / 60);只认形如 116e23 / 39n54 的串,其余 null
export function geoStrToDegree(str, axis){
	if(typeof str !== 'string'){ return null; }
	const m = str.trim().toLowerCase().match(axis === 'lat' ? /^(\d+)([ns])(\d*)$/ : /^(\d+)([ew])(\d*)$/);
	if(!m){ return null; }
	const v = parseInt(m[1], 10) + (m[3] ? parseInt(m[3], 10) : 0) / 60;
	return (m[2] === 's' || m[2] === 'w') ? -v : v;
}
const blankGeoValue = (x)=>x === undefined || x === null || x === '';

// 🔴 事盘记录的地点一组(经纬串 / 数值经纬 / 地名)—— 四路载入(主盘 applyCase / 六爻补取 / 择日宿主覆盖层 / 卜卦类盘壳)唯一的地点出口,
// 别处不许按 lon / lat 逐键写字段(合同 caseLoadPlaceSingleSource.test.js)。
// 经纬串缺或空 = 坏档 → null(调用方整组沿用自己现有的地点,不拼出混搭,也不把左栏清成空纬度);
// 串有效时数值经纬缺 / 空由串换算(后端算盘只用串,数值经纬只作地图中心与时区提示),换算不出就不给这一项;地名照写(空串也写)。
// 时区不在这一组里:时区是记录时刻的一部分(绝对瞬间),地点坏了时刻照样按记录的时区。
export function casePlaceGroup(values){
	const v = values && typeof values === 'object' ? values : {};
	if(blankGeoValue(v.lon) || blankGeoValue(v.lat)){ return null; }
	const out = { lon: v.lon, lat: v.lat, pos: v.pos === undefined || v.pos === null ? '' : v.pos };
	const gl = !blankGeoValue(v.gpsLon) ? v.gpsLon : geoStrToDegree(`${v.lon}`, 'lon');
	const ga = !blankGeoValue(v.gpsLat) ? v.gpsLat : geoStrToDegree(`${v.lat}`, 'lat');
	if(gl !== null && gl !== undefined){ out.gpsLon = gl; }
	if(ga !== null && ga !== undefined){ out.gpsLat = ga; }
	return out;
}

// 不经左栏、直接拿记录起盘的一方(AI 挂载重算 / 无头重算 / 签名)用的地点:记录的地点一组好就用它,
// 坏档(经纬串缺 / 空 / 只坏一项)整组换成默认坐标(与「未给地点按默认坐标起盘」同一组),绝不拼出「经度有、纬度空」的半组。
export function recordPlaceGroupOrDefault(record){
	return casePlaceGroup(record) || { lon: DefLon, lat: DefLat, gpsLon: DefGpsLon, gpsLat: DefGpsLat, pos: '' };
}

// 事盘记录(列表里派发的那条原样记录)→ 左栏字段补丁:载入事盘(models/user applyCase 写主盘)与 currentCaseFieldsPatch 共用这一份映射。
// baseFields = 载入前的左栏字段:时区缺 / 空时回落它;条目照它的形状写新值(不就地改共享条目)。
// 日界 / 晚子时 / 六爻日界 / 时间算法:记录顶层优先(旧档兼容),回落 payload.fieldSnapshot;payload 落库恒为 JSON 串,先解析、坏串回退
export function caseRecordFieldsPatch(values, baseFields){
	const v = values && typeof values === 'object' ? values : {};
	const flds = baseFields && typeof baseFields === 'object' ? baseFields : {};
	const out = {};
	const setF = (key, value)=>{ out[key] = { ...(flds[key] || { name: [key] }), value }; };
	let tm = new DateTime();
	const zone = v.zone ? v.zone : (flds.zone ? flds.zone.value : '+08:00');
	tm.setZone(zone);
	const divTime = v.divTime;
	if(divTime instanceof DateTime){
		tm = divTime.clone ? divTime.clone() : divTime;
	}else if(caseDivTimeUsable(v)){
		tm = parseCaseDivTimeInto(tm, divTime) || tm;
	}
	// 没有起课时间(空 / 写法认不出):按此刻(applyCase 给一条提示)
	setF('date', tm.clone());
	setF('time', tm.clone());
	setF('ad', tm.ad);
	setF('zone', zone);
	// 地点当一组(casePlaceGroup):坏档(经纬串缺 / 空)整组不写 —— 左栏留着载入前的地点(applyCase 给一条提示),
	// 此前逐键照写,空纬度把左栏清空、再存一次就固化;数值经纬缺 / 空由串换算(否则左栏是「记录的串 + 载入前的数值经纬」)
	const place = casePlaceGroup(v);
	if(place){ Object.keys(place).forEach((k)=>{ setF(k, place[k]); }); }
	let casePayloadObj = v.payload;
	if(typeof casePayloadObj === 'string' && casePayloadObj){
		try{ casePayloadObj = JSON.parse(casePayloadObj); }catch(e){ casePayloadObj = null; }
	}
	const snap = (casePayloadObj && casePayloadObj.fieldSnapshot && typeof casePayloadObj.fieldSnapshot === 'object') ? casePayloadObj.fieldSnapshot : {};
	const pick = (k)=>{
		const x = v[k] !== undefined && v[k] !== null && v[k] !== '' ? v[k] : snap[k];
		return x === undefined || x === null || x === '' ? null : x;
	};
	// 性别空串 = 未指定(与 setCurrentCase 同):此前照写 parseInt('') = NaN 进左栏
	if(v.gender !== undefined && v.gender !== null && v.gender !== ''){ setF('gender', parseInt(`${v.gender}`, 10)); }
	['after23NewDay', 'lateZiHourUseNextDay', 'guaAfter23NewDay', 'timeAlg'].forEach((k)=>{
		if(pick(k) !== null){ setF(k, parseInt(`${pick(k)}`, 10)); }
	});
	if(v.orbs && typeof v.orbs === 'object'){ setF('orbs', v.orbs); }
	if(v.orbScale !== undefined && v.orbScale !== null){ setF('orbScale', v.orbScale); }
	return out;
}

const CASE_PATCH_KEYS = ['date', 'time', 'ad', 'zone', 'lon', 'lat', 'gpsLon', 'gpsLat', 'pos', 'gender', 'after23NewDay', 'lateZiHourUseNextDay'];

// 事盘记录的起课时刻串 → DateTime(setCurrentCase 建 currentCase 与补取比对时刻共用这一种解析:时区缺 = +08:00)
// 起课时刻认得出(写法判据单一出处 caseDivTime.isCaseDivTimeText)。空串 / 缺 / 认不出 = 坏档(没有起课时间)
export function caseDivTimeUsable(values){
	const v = values && typeof values === 'object' ? values : {};
	if(v.divTime instanceof DateTime){ return true; }
	return isCaseDivTimeText(v.divTime);
}

// 载入这条事盘时要告诉用户的坏档情形(主盘 applyCase 弹一次):没有可用地点 → 沿用当前地点;没有起课时间 → 按此刻
export function caseLoadNotices(values){
	const out = [];
	if(!casePlaceGroup(values)){ out.push('这条事盘没有可用地点，沿用当前地点'); }
	if(!caseDivTimeUsable(values)){ out.push('这条事盘没有起课时间，按此刻起课'); }
	else if(values && caseDivTimeDateOnly(values.divTime)){ out.push('这条事盘的起课时间只有日期，按当天 12:00 起课'); }
	return out;
}

// 起课时刻串 → 写进给定的 DateTime(按判据同一次匹配出的规范写法解析:T / 多空白 / 前后空白一律归一,只有日期 = 12:00)。
// 认不出 = null。载入事盘 / 补取比对 / 盘壳还原都经它,不再各自把原串直接交给 DateTime.parse
// (此前「T」分隔静默按 12:00 起课、前导空格解析成 NaN 年却当作有起课时间)
export function parseCaseDivTimeInto(dt, text){
	if(!dt || typeof dt.parse !== 'function'){ return null; }
	// 已是 DateTime(当前事盘表单态的起课时刻):照旧整份接过来
	if(text instanceof DateTime){
		try{ return dt.parse(text); }catch(e){ return null; }
	}
	const p = parseCaseDivTimeParts(text);
	if(!p){ return null; }
	try{ return dt.parse(p.canonical, 'YYYY-MM-DD HH:mm:ss'); }catch(e){ return null; }
}

export function parseCaseRecordDivTime(values){
	const v = values && typeof values === 'object' ? values : {};
	if(v.divTime instanceof DateTime){ return v.divTime; }
	if(!caseDivTimeUsable(v)){ return null; }
	try{
		const t = new DateTime();
		t.setZone(v.zone !== undefined && v.zone !== null ? v.zone : '+08:00');
		return parseCaseDivTimeInto(t, v.divTime);
	}catch(e){ return null; }
}

// 当前事盘(store.user.currentCase)的时间地点 → 左栏字段补丁:时刻 / 时区 / 经纬 / 地名 / 性别 + 日界 / 晚子时
// (payload.fieldSnapshot)。opts.timeAlg:另带时间算法,与载入事盘时 models/user.js applyCase 同口径(有原样记录时记录顶层优先、快照兜底)。
// 载入事盘时左栏要等最后一步才换成事盘时刻,组件还原那一刻读 props.fields 拿到的还是载入前的 —— 要事盘自己的时刻就用它。
export function currentCaseFieldsPatch(opts){
	const store = getStore();
	const cur = store && store.user ? store.user.currentCase : null;
	// 有原样记录(setCurrentCase 存下的那条,cid 与时刻对得上)→ 与载入事盘同一份映射(caseRecordFieldsPatch):顶层时间算法、空时区回落左栏、
	// 地点当一组(坏档整组不写,与主盘载入后左栏所示逐键相同)。表单字段形态的 currentCase 丢了记录顶层的口径键,只作没有原样记录时的兜底。
	// 时刻按 setCurrentCase 同一种解析(parseCaseRecordDivTime)再比
	const raw = store && store.user ? store.user.currentCaseRecord : null;
	const fmt = (x)=>(x instanceof DateTime ? x.format('YYYY-MM-DD HH:mm:ss') : '');
	const curDiv = cur && cur.divTime ? cur.divTime.value : null;
	const rawDiv = raw && typeof raw === 'object' ? parseCaseRecordDivTime(raw) : null;
	if(rawDiv && cur && cur.cid && cur.cid.value && `${cur.cid.value}` === `${raw.cid}`
		&& curDiv instanceof DateTime && fmt(curDiv) === fmt(rawDiv)){
		const full = caseRecordFieldsPatch(raw, store.astro && store.astro.fields ? store.astro.fields : {});
		const out = {};
		CASE_PATCH_KEYS.concat(opts && opts.timeAlg ? ['timeAlg'] : []).forEach((k)=>{
			if(full[k]){ out[k] = { value: full[k].value, name: [k] }; }
		});
		return out;
	}
	const val = (k)=>(cur && cur[k] && cur[k].value !== undefined && cur[k].value !== null && cur[k].value !== '' ? cur[k].value : undefined);
	const div = val('divTime');
	if(!div || typeof div.clone !== 'function'){ return null; }
	const out = {
		date: { value: div.clone(), name: ['date'] },
		time: { value: div.clone(), name: ['time'] },
		ad: { value: div.ad, name: ['ad'] },
		zone: { value: val('zone') || div.zone || '+08:00', name: ['zone'] },
	};
	// 与原样记录那一路同一判据:地点当一组(经纬串缺或空 → 整组沿用宿主的;地名空串照写,不留宿主的地名配记录的坐标)
	const rawVal = (k)=>(cur && cur[k] ? cur[k].value : undefined);
	const place = casePlaceGroup({ lon: rawVal('lon'), lat: rawVal('lat'), gpsLon: rawVal('gpsLon'), gpsLat: rawVal('gpsLat'), pos: rawVal('pos') });
	if(place){ Object.keys(place).forEach((k)=>{ out[k] = { value: place[k], name: [k] }; }); }
	const g = val('gender');
	if(g !== undefined){ out.gender = { value: parseInt(`${g}`, 10), name: ['gender'] }; }
	const payload = parseKentangCasePayload(val('payload'));
	const snap = payload && payload.fieldSnapshot && typeof payload.fieldSnapshot === 'object' ? payload.fieldSnapshot : {};
	['after23NewDay', 'lateZiHourUseNextDay'].forEach((k)=>{
		const v = snap[k];
		if(v !== undefined && v !== null && v !== ''){ out[k] = { value: parseInt(`${v}`, 10), name: [k] }; }
	});
	// 兜底只有快照里的时间算法(表单字段形态的 currentCase 不带记录顶层的口径键)
	if(opts && opts.timeAlg){
		const ta = snap.timeAlg;
		if(ta !== undefined && ta !== null && ta !== ''){ out.timeAlg = { value: parseInt(`${ta}`, 10), name: ['timeAlg'] }; }
	}
	return out;
}

export function getKentangSavedCasePayload(module){
	const store = getStore();
	const userState = store && store.user ? store.user : null;
	const currentCase = userState && userState.currentCase ? userState.currentCase : null;
	if(!currentCase || !currentCase.cid || !currentCase.cid.value){
		return null;
	}
	const sourceModule = currentCase.sourceModule ? currentCase.sourceModule.value : null;
	const caseType = currentCase.caseType ? currentCase.caseType.value : null;
	const payload = parseKentangCasePayload(currentCase.payload ? currentCase.payload.value : null);
	const payloadModule = payload && payload.module ? payload.module : null;
	if(sourceModule !== module && caseType !== module && payloadModule !== module){
		return null;
	}
	// 去重键只认显式载入(caseRestoreKey 头注):编辑 / 存为事盘 / 保存编辑换掉的当前事盘不算载入 → 不还原
	const caseVersion = caseRestoreKey(module, userState);
	if(!caseVersion){ return null; }
	return { payload, caseVersion };
}
