// [Z6·三式择日] 三式合一 options 单源拆分器(定案:工作台/扫描共用,防第二处手抄)。
// merged 平铺形与三式合一主页存档同律(techniqueMountSettings SANSHI_UNITED_FIELDS:
// 六壬/奇门键原名·太乙键改名 taiyiStyle/taiyiAccum/taiyiSchool_*·共享时间键一份)——
// 此处按同一改名规则反向拆回三家引擎各自的 options 形;jest 对拍 SANSHI_UNITED_FIELDS
// 键集并集恒等(主页 schema 加键时此处被强制表态)。
// 🔴 择日扫描增补键(非主页 schema 面):六壬 yueMode/guirengType/yinyangSystem(Z5 扫描
// 参数)+太乙 tn(Z3)——它们不在 SANSHI_UNITED_FIELDS,拆分白名单显式登记。

// 共享时间键(与 techniqueMountSettings.SANSHI_SHARED_TIME_KEYS 同值;jest 对拍锚)。
export const SANSHI_SHARED_TIME_KEYS = ['timeAlg', 'after23NewDay', 'lateZiHourUseNextDay'];
// 太乙改名(与 techniqueMountSettings.SANSHI_TAIYI_RENAME 同值;jest 对拍锚)。
export const SANSHI_TAIYI_RENAME_BACK = { taiyiStyle: 'style', taiyiAccum: 'tn' };

// 六壬家扫描消费键(liurengZeriScanEngine/buildLrChartLite 读):
const LR_KEYS = ['guirengType', 'yueMode', 'yinyangSystem', 'after23NewDay', 'lateZiHourUseNextDay'];
// 奇门家扫描消费键(QimenZeriWorkbench PARAM_FIELDS 同子集;「综合(5)」等后端专属模式不入):
// [Q-271/ZC-14] 此前只取 13 键 → 暗干/暗支/八神取神/中宫寄宫/移星值符等三式合一页左栏也有的档不进扫描,
// 「暗干/暗支」类在三式择日恒空而奇门择日(取遁甲页全部 options)能命中。补齐为 QIMEN_FIELDS 全消费键;
// 值由宿主(SanshiZeriMain.startScan)从内嵌三式页 hook.getQimenOptions() 播种,工作台 13 键覆盖其上。
export const QM_SEED_KEYS = ['godsPreset', 'anGanMode', 'showAnZhi', 'jiGongMode', 'shiftZhiFuMode', 'kongMarkBoth', 'showAllKong',
	'feiXingShun', 'feiMenShun', 'feiShenShun', 'feiMenZhongCan', 'feiMenZhongShow', 'mixTian', 'mixXing', 'mixMen', 'mixShen',
	'yearJiaJu', 'dayJiaJu', 'keJiaFenDun', 'keZiZhengHuanShi', 'jinhanMenPai', 'chartCategory', 'fengJu'];
const QM_KEYS = ['paiPanType', 'qijuMethod', 'zhirunLeapDays', 'shuziReportNumber', 'school', 'zhiShiType', 'yueJiaQiJuType', 'kongMode', 'yimaMode', 'shiftPalace', 'timeAlg', 'after23NewDay', 'lateZiHourUseNextDay', ...QM_SEED_KEYS];
// 太乙家扫描消费键(Z3 定谳仅 tn 有判别;style 恒 3 引擎内钉):
const TY_MERGED_KEYS = ['taiyiAccum'];

export function splitSanshiOptions(merged){
	const m = merged || {};
	const pick = (keys)=>{
		const out = {};
		keys.forEach((k)=>{
			if(m[k] !== undefined){ out[k] = m[k]; }
		});
		return out;
	};
	const liureng = pick(LR_KEYS);
	const qimen = pick(QM_KEYS);
	const taiyi = {};
	TY_MERGED_KEYS.forEach((k)=>{
		if(m[k] !== undefined){ taiyi[SANSHI_TAIYI_RENAME_BACK[k] || k] = m[k]; }
	});
	// 共享日界键三家同吃(太乙对判定面零效果[Z3 dump 定谳]但透传无害且保持同源形)。
	SANSHI_SHARED_TIME_KEYS.forEach((k)=>{
		if(m[k] === undefined){ return; }
		if(k !== 'timeAlg'){ taiyi[k] = m[k]; }	// 太乙无 timeAlg 自由度(恒钟表)
	});
	return { liureng, qimen, taiyi };
}

// 拆分白名单全集(金标对拍消费:并集必须被 SANSHI_UNITED_FIELDS ∪ 择日增补键覆盖)。
export const SANSHI_SPLIT_ALL_KEYS = Array.from(new Set([...LR_KEYS, ...QM_KEYS, ...TY_MERGED_KEYS]));
// 择日扫描增补键(不在主页 schema;金标豁免清单)。
export const SANSHI_ZERI_EXTRA_KEYS = ['guirengType', 'yueMode', 'yinyangSystem'];
