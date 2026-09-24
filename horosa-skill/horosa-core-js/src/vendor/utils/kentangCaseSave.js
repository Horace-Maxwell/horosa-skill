// headless stub：上游 getStore() 取 dva 全局 store（读「当前载入的事盘」）。headless 无 store、也没有「载入的旧案」——
// 设置一律由每次调用显式传入，故恒 null → getKentangSavedCasePayload 回 null（与上游「未载入事盘」同一分支）。
const getStore = () => null;

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

// 🔴 事盘「显式载入代次」后缀 —— 读档去重键的单一真值源。
// 各技法读档都有 `!force && lastRestoredCaseId === caseVersion` 这道去重守卫,而
// lastRestoredCaseId 只在构造函数初始化、全仓无一处重置;子技法面板又常驻挂载
// (Tabs 无 destroyInactiveTabPane → componentDidMount 的 force 一个会话只跑一次)。
// 不带代次时:同一条记录第二次载入必被守卫拦掉,屏幕上仍是用户后来新起的卦
// ——「存了再读卦不一样」的根因,21 个技法同款守卫无一幸免。
// 代次只在 user/applyCase(用户在列表里点一条记录)时 +1:显式载入必还原,
// 而改时间等无关 fields 变化代次不变、守卫照旧拦住(守卫原意完整保留)。
// 自拼 caseVersion 的技法(遁甲/统摄法/奇门择日/六爻/三式合一)一律调本函数,不许另抄一份。
export function caseApplySeqSuffix(userState){
	const seq = userState && userState.caseApplySeq ? userState.caseApplySeq : 0;
	return `|${seq}`;
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
	const cid = `${currentCase.cid.value}`;
	const updateTime = currentCase.updateTime && currentCase.updateTime.value ? `${currentCase.updateTime.value}` : '';
	// caseVersion 必带载入代次后缀,理由见 caseApplySeqSuffix 头注(读档去重键单一真值源)。
	return {
		payload,
		caseVersion: `${module}|${cid}|${updateTime}${caseApplySeqSuffix(userState)}`,
	};
}
