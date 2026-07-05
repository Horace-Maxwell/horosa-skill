// divination/horary/horarySchools.js
// 卜卦（西洋 Horary）流派轴（五档）。单一真值源：排盘请求（宫制/界/三分制/星表）与判读引擎
// （可判性阈值/完成破坏/月空模式/福点反转/恒星容许）共用。
//
// 设计约束：
//  - 默认 classical = 主流经典口径；它决定「无流派选择时」的既有基线行为（见 HoraryMain defaults）。
//  - backend.* 经 patchFields 下发 /chart（hsys/termsVariant/tradition/westNodeType 后端已支持，零改；
//    tripSystem 为三分制变体注记，前端判读消费）。
//  - judge.* 经 runHorary(result, category, opts) 贯通判读引擎（可判性/完成/月亮/点/恒星）。
//  - 术语依据均为「宫制/时代/星历口径」等公有方法名（Regiomontanus/Alcabitius/Placidus/整宫制、
//    Ptolemy/Dorotheus 三分制、Egyptian 界），显示层零内部溯源引用、零在世作者名。

export const HORARY_SCHOOL_ORDER = ['classical', 'strict', 'hellenistic', 'medieval', 'modern'];

// hsys: 0=整宫 1=Alcabitius 2=Regiomontanus 3=Placidus（null=不联动，保持用户当前值）
// termsVariant: 0=埃及界 1=托勒密界 2=经典混合界 3=迦勒底界
// tripSystem: 'ptolemaic'（水象三分主=火星）| 'dorothean'（三主含参与、水象日主=金星）
// tradition: 1=七曜 0=七曜+三王星
export const HORARY_SCHOOLS = {
	classical: {
		id: 'classical', cn: '经典主流', short: '经典',
		backend: { hsys: 2, termsVariant: 2, tripSystem: 'ptolemaic', tradition: 1, westNodeType: null },
		judge: {
			ascEarlyDeg: 3, ascLateDeg: 27, considerationsMode: 'warn',
			vocMode: 'classic', vocMitigateSigns: false, combustMitigateSameSign: true,
			pofReversal: false, fixedStarOrb: 2, perfectionStrict: 'standard', includeOuter: false,
		},
		desc: 'Regiomontanus 宫制、经典混合界、Ptolemy 三分制；可判性以警示为主，福点不按昼夜反转。',
	},
	strict: {
		id: 'strict', cn: '当代严谨', short: '严谨',
		backend: { hsys: 2, termsVariant: 0, tripSystem: 'dorothean', tradition: 1, westNodeType: null },
		judge: {
			ascEarlyDeg: 3, ascLateDeg: 27, considerationsMode: 'strict',
			vocMode: 'classic', vocMitigateSigns: false, combustMitigateSameSign: true,
			pofReversal: true, fixedStarOrb: 2, perfectionStrict: 'strict', includeOuter: false,
		},
		desc: 'Regiomontanus 宫制、埃及界、Dorotheus 三分制；紧容许度、严格可判性门槛，福点按昼夜反转。',
	},
	hellenistic: {
		id: 'hellenistic', cn: '希腊化', short: '希腊化',
		backend: { hsys: 0, termsVariant: 0, tripSystem: 'dorothean', tradition: 1, westNodeType: null },
		judge: {
			ascEarlyDeg: 2, ascLateDeg: 28, considerationsMode: 'lenient',
			vocMode: 'kenodromia', vocMitigateSigns: false, combustMitigateSameSign: false,
			pofReversal: true, fixedStarOrb: 1.5, perfectionStrict: 'standard', includeOuter: false,
		},
		desc: '整宫制、埃及界、宗派为纲；月空按 30° 内无准确相位（不拘星座界），福点按昼夜反转。',
	},
	medieval: {
		id: 'medieval', cn: '中世纪', short: '中世纪',
		backend: { hsys: 1, termsVariant: 0, tripSystem: 'dorothean', tradition: 1, westNodeType: null },
		judge: {
			ascEarlyDeg: 3, ascLateDeg: 27, considerationsMode: 'warn',
			vocMode: 'exempt4', vocMitigateSigns: true, combustMitigateSameSign: true,
			pofReversal: true, fixedStarOrb: 3, perfectionStrict: 'standard', includeOuter: false,
		},
		desc: 'Alcabitius 宫制、埃及界、Dorotheus 三分制；月在金牛/巨蟹/射手/双鱼豁免空相，恒星容许放宽。',
	},
	modern: {
		id: 'modern', cn: '现代心理', short: '现代',
		backend: { hsys: 3, termsVariant: 2, tripSystem: 'ptolemaic', tradition: 0, westNodeType: null },
		judge: {
			ascEarlyDeg: 0, ascLateDeg: 30, considerationsMode: 'ignore',
			vocMode: 'classic', vocMitigateSigns: false, combustMitigateSameSign: true,
			pofReversal: false, fixedStarOrb: 5, perfectionStrict: 'lenient', includeOuter: true,
		},
		desc: 'Placidus 宫制、含三王星；不以命度早晚拒判，恒星容许放宽，福点不反转。',
	},
};

// 星座键 → 中世纪「月不空」豁免（Moon in Taurus/Cancer/Sagittarius/Pisces）。
export const VOC_EXEMPT_SIGNS = ['taurus', 'cancer', 'sagittarius', 'pisces'];

export function schoolOf(id){
	return HORARY_SCHOOLS[id] || HORARY_SCHOOLS.classical;
}

// 取某档下发 /chart 的字段补丁（仅含非 null 后端字段；tripSystem 仅前端消费不下发）。
export function horaryBackendFields(id){
	const b = schoolOf(id).backend || {};
	const out = {};
	if(b.hsys !== null && b.hsys !== undefined) out.hsys = b.hsys;
	if(b.termsVariant !== null && b.termsVariant !== undefined) out.termsVariant = b.termsVariant;
	if(b.tradition !== null && b.tradition !== undefined) out.tradition = b.tradition;
	if(b.westNodeType !== null && b.westNodeType !== undefined) out.westNodeType = b.westNodeType;
	return out;
}

// 取某档传入 runHorary 的判读 opts（含 tripSystem 供尊贵注记 + judge 全量）。
export function horaryJudgeOpts(id){
	const sc = schoolOf(id);
	return { school: sc.id, tripSystem: sc.backend.tripSystem, ...sc.judge };
}

// 反查：给定当前 fields（后端字段）反推最贴合的档（用于「档与手动改动不一致」时的显示回落）。
// 仅按 hsys 主键匹配；匹配不到回落 classical。
export function presetOf(fields){
	const hsys = fields && fields.hsys && fields.hsys.value !== undefined ? fields.hsys.value : null;
	if(hsys === null) return 'classical';
	const hit = HORARY_SCHOOL_ORDER.find((id) => HORARY_SCHOOLS[id].backend.hsys === hsys);
	return hit || 'classical';
}

// 选择器 options（antd Select）。
export function horarySchoolSelectOptions(){
	return HORARY_SCHOOL_ORDER.map((id) => ({ label: HORARY_SCHOOLS[id].cn, value: id }));
}

export default HORARY_SCHOOLS;
