// 印占流派 / 大运体系常量 —— **逐块抽自上游** `constants/AstroConst.js`（curated：上游全文件 1900+ 行、import 了
// headless 不存在的色板/主题模块，整文件 vendor 不可行）。manifest 的 upstream_sha256 看守源文件、extracts 断言
// 每个名字仍是上游顶层 export：源一动即红，逐块对过再 --restamp。消费方：india/jyotishSnapshot.js 的
// [起盘信息] 流派行（buildIndiaSnapshotText:1154-1178）与 [大运Dasha]（buildDashaSnapshotLines:429-494）。
// 块与块之间的上游代码（年长档 / 色板等）不在此文件；块内逐字（含注释）。

// ── AstroConst.js:1459-1470 ──

// 印度占星五大流派(预设包·软联动):切派写默认岁差/宫制/相位范式 + 可见右栏 tab 子集,
// 但用户仍可单独覆盖(软联动);默认 parashari = 现状零行为差异。tab key 见 13 TabPane(1-13)。
export const INDIA_SCHOOL_DEFAULT = 'parashari';
export const INDIA_SCHOOL_OPTIONS = [
    { value: 'parashari', label: 'Parāśarī 帕拉萨拉(默认)' },
    { value: 'jaimini', label: 'Jaimini 贾米尼' },
    { value: 'tajika', label: 'Tājika 塔吉卡(年盘)' },
    { value: 'kp', label: 'KP 系统' },
    { value: 'nadi', label: 'Nāḍī 纳迪' },
    { value: 'western_sidereal', label: 'Western Sidereal 西方恒星(对照)' },
];

// ── AstroConst.js:1648-1680 ──

// 每派默认:ayanamsa / hsys(分宫数) / aspectParadigm(中栏相位范式) / tabs(可见右栏 tab key 集)。
export const INDIA_SCHOOL_DEFAULTS = {
    // '14' 问事 Praśna(parashari/tajika/kp 三派;jaimini/nadi 不设,§16.3 适用矩阵)
    // '15' 校时 Rectification(五派全开:定盘是所有流派之前置)
    // dashaFocus:该派主 dasha 取向(∈ 大运体系值集则切 dashaSystem;否则仅作面板定位/摘要显示);
    // primaryTab:切派后落地主场 tab;positioning:一句定位(选择器 tooltip+摘要,五支手册定位表)。
    parashari: { ayanamsa: 'lahiri', hsys: 0, aspectParadigm: 'graha', dashaFocus: 'vimshottari', primaryTab: '3',
        positioning: '全局本命·性格·事业·财富·整体人生',
        tabs: ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12', '13', '14', '15', '16'] },
    jaimini: { ayanamsa: 'lahiri', hsys: 0, aspectParadigm: 'rasi', dashaFocus: 'chara', primaryTab: '9',
        positioning: '寿命·出身·灵性·事件本质(星座逻辑)',
        tabs: ['1', '2', '3', '4', '7', '9', '13', '15'] },
    tajika: { ayanamsa: 'lahiri', hsys: 0, aspectParadigm: 'tajika', dashaFocus: 'mudda', primaryTab: '11',
        positioning: '流年·一年内事件·应期(太阳回归年盘)',
        tabs: ['1', '2', '3', '11', '14', '15'] },
    kp: { ayanamsa: 'krishnamurti', hsys: 3, aspectParadigm: 'kp', dashaFocus: 'vimshottari', primaryTab: '6',
        positioning: '精准择时·是否判定·卜卦(sub-lord 细分)',
        tabs: ['1', '3', '5', '6', '10', '14', '15'] },
    nadi: { ayanamsa: 'lahiri', hsys: 0, aspectParadigm: 'nadi', dashaFocus: 'jupiterProgression', primaryTab: '16',
        positioning: '事件细节·世代·配偶父母信息(D150 极细分·木星 karaka)',
        tabs: ['16', '1', '3', '4', '8', '15'] },
    // 第 6 派 Western Sidereal(Fagan/Bradley 恒星黄道 + Placidus):严格说非印度本土,
    // 但共享恒星黄道、常被并列比较 → 对照用途;经度相位范式现无 → 退到 graha(面板标注)。
    // tabs 去 Jaimini/Tājika/KP/Nāḍī 专属页;'15' 校时全派恒开(定盘是一切流派之前置)。
    western_sidereal: { ayanamsa: 'fagan_bradley', hsys: 3, aspectParadigm: 'graha', dashaFocus: 'vimshottari', primaryTab: '1',
        positioning: '西方恒星占星(对照档,共享恒星黄道)',
        tabs: ['1', '2', '3', '4', '13', '15'] },
};

export function normalizeIndiaSchool(value){
    return INDIA_SCHOOL_OPTIONS.find((item)=>item.value === value) ? value : INDIA_SCHOOL_DEFAULT;
}

// ── AstroConst.js:1682-1793 ──
// ── 印占·大运流派开关(22 枚举键;引擎 dasha_variants.VARIANT_SPECS 同源镜像;[Q-135/T-43 (g)] 旧注写 21,实为 22)──
// 🔴 默认值=现状行为字节零回归;文献另荐口径以「(文献…)」标注,绝不作缺省。标签中性化零作者名。
export const INDIA_DASHA_VARIANT_GROUPS = [
    { key: 'nakshatra', label: '星宿大运' },
    { key: 'jaimini', label: '座运 Jaimini' },
    { key: 'kalachakra', label: 'Kālachakra' },
    { key: 'graha', label: '行星运' },
    { key: 'ayus', label: '寿命与年盘' },
];
export const INDIA_DASHA_VARIANT_SPECS = [
    { key: 'vedhaBlockers', label: '过运 Vedha 遮蔽者', group: 'graha', default: 'all',
      options: [{ value: 'all', label: '罗计计入(默认)' }, { value: 'exclude_nodes', label: '罗计不作遮蔽者' }],
      tip: 'Vedha(遮蔽)由落于对应宫的他曜实施;罗睺/计都是否可作遮蔽者各家不一,默认计入=既有口径' },
    { key: 'ashtottariReckoning', label: 'Aṣṭottarī 子型', group: 'nakshatra', default: 'ardradi',
      options: [{ value: 'ardradi', label: 'Ārdrā 起(默认)' }, { value: 'krittikadi', label: 'Kṛttikā 起' },
                { value: 'auto_by_rahu', label: '依罗睺位自动(文献推荐)' }],
      tip: '宿→曜映射锚:同块序自 Ārdrā 或 Kṛttikā 起;自动=罗睺自上升三角位取 Kṛttikā 型' },
    { key: 'charaDirection', label: 'Chara 方向', group: 'jaimini', default: 'lagna_parity_sign',
      options: [{ value: 'lagna_parity_sign', label: '上升奇偶象(默认)' }, { value: 'ninth_foot', label: '第9座足性(主流)' }],
      tip: '主流口径按自上升第 9 座奇足/偶足定全序方向,期长亦按全序方向计数' },
    { key: 'charaDignity', label: 'Chara 尊位修正', group: 'jaimini', default: 'plus_minus_one',
      options: [{ value: 'plus_minus_one', label: '庙旺±1(默认)' }, { value: 'none', label: '不施(主流)' }],
      tip: '座主庙旺 +1 年/落陷 −1 年;主流实践多不施' },
    { key: 'jaiminiStrengthOrder', label: '强弱判据序', group: 'jaimini', default: 'standard',
      options: [{ value: 'standard', label: '标准链(默认)' }, { value: 'ak_first', label: 'AK 优先' }],
      tip: '座运种子/双主取强的逐级判据次序;AK 优先=含 Ātmakāraka 者径强' },
    { key: 'rasiAntarFirst', label: '座运中运首座', group: 'jaimini', default: 'dasa_sign_first',
      options: [{ value: 'dasa_sign_first', label: '大运座先(默认)' }, { value: 'dasa_sign_last', label: '次座起·大运座末' }],
      tip: '中运自大运座本身起,或自次座起而大运座排最后' },
    { key: 'rasiAntarSplit', label: 'Chara 中运分割', group: 'jaimini', default: 'proportional',
      options: [{ value: 'proportional', label: '按主期比例(默认)' }, { value: 'equal', label: '12 等分(文献默认)' }],
      tip: '仅作用于 Chara 座运的中运期长显示分割:按各座自身期长占比,或均分为 12 份' },
    { key: 'chakraDayStart', label: 'Chakra 昼夜起座', group: 'jaimini', default: 'bphs',
      options: [{ value: 'bphs', label: '古典(夜=上升座/昼=上升主座)' }, { value: 'reversed', label: '反转变体' }],
      tip: 'Chakra(每座 10 年)的起座规则;黄昏窗权威未详按昼夜二分' },
    { key: 'varnadaPeriodRule', label: 'Varṇada 期长', group: 'jaimini', default: 'count_to_lord',
      options: [{ value: 'count_to_lord', label: '数到座主(默认)' }, { value: 'equal_nine', label: '等长(文献分歧)' }],
      tip: '等长派:每座恒 9 年(首轮总 108,二轮 12−9=3);数到座主派:数至宫主为期(与 Nārāyaṇa 同核)。两派文献分歧,各自真算' },   // [Q-135/T-43 (a)] 旧文案「选中亦按数到座主」已过期,引擎早已真算等长
    { key: 'kalachakraCycle', label: '周期换接法', group: 'kalachakra', default: 'carry',
      options: [{ value: 'carry', label: '进位(默认)' }, { value: 'repeat', label: '循环' },
                { value: 'same_nak_carry', label: '同宿进位' }, { value: 'reset', label: '归零（现与「循环」同果）' }],   // [Q-136/T-44] 两档同分支
      tip: 'paramāyus 用尽后如何续轮;进位绝不跨 savya/apasavya 组;差异仅首轮后显现' },
    { key: 'kalachakraApplicability', label: '适用条件', group: 'kalachakra', default: 'universal',
      options: [{ value: 'universal', label: '普适(默认)' }, { value: 'navamsa_stronger', label: '月 navāṁśa 强才主用' }],
      tip: '变体仅标注适用性,不禁算' },
    { key: 'naisargikaOrder', label: 'Naisargika 排序', group: 'graha', default: 'fixed_natural',
      options: [{ value: 'fixed_natural', label: '固定自然序(默认)' }, { value: 'kendra_strength', label: 'kendra 强度序' }],
      tip: '成长-衰老固定序,或自月亮起按 kendra→panaphara→apoklima;年数不变' },
    { key: 'ayurdayaMethod', label: '寿命法选定', group: 'ayus', default: 'auto',
      options: [{ value: 'auto', label: '自动(最强定法,默认)' }, { value: 'pindayu', label: 'Piṇḍāyu' },
                { value: 'nisargayu', label: 'Nisargāyu' }, { value: 'amsayu', label: 'Aṁśāyu' }],
      tip: '{上升,日,月}最强者定法:日强→Piṇḍāyu/月强→Nisargāyu/上升强→Aṁśāyu;可手动指定' },
    // [Q-139 裁决 2026-09-18] 缺省改「同 Piṇḍāyu 施减」(Jātaka Pārijāta 5.6 / 5.12–13:Nisargāyu 与 Piṇḍāyu 同法);「全期不减」与盘无关,改非缺省
    { key: 'nisargayuHarana', label: 'Nisargāyu 减算', group: 'ayus', default: 'pindayu_like',
      options: [{ value: 'pindayu_like', label: '同 Piṇḍāyu 施减(默认)' }, { value: 'none', label: '全期不减(与盘无关,仅参考)' }],
      tip: '施与 Piṇḍāyu 相同的弧缩放与减算(默认);「全期不减」只按自然寿表原样合计,与行星位置无关' },
    { key: 'amsayuMultiplier', label: 'Aṁśāyu 倍数', group: 'ayus', default: 'majority_highest',
      options: [{ value: 'majority_highest', label: '多数派取最高(默认)' }, { value: 'bphs_literal', label: '古典逐字' },
                { value: 'saravali_multiply', label: '相乘合并' }],
      tip: '庙旺/逆×3·自座/vargottama×2 的组合口径(重算总值)' },
    { key: 'krurodayaDenominator', label: 'Krurodaya 减式', group: 'ayus', default: 'zodiac21600',
      options: [{ value: 'zodiac21600', label: '式 A:命宫座内角分/21600(默认)' }, { value: 'nav108', label: '式 B:全周 navāṁśa 序/108(文献推荐)' }],
      // [Q-129/T-37·IN-11 ①] 两档不是同一量的两种分母:式 A 分子=命宫座内角分(0–1800),最多减总和的 1/12;式 B 分子=自白羊起的 navāṁśa 序(1–108),可减至近全额;量级差 1–23 倍
      tip: '凶星升上升时对总和一次减的算式。两档不是同一量的两种分母:式 A=命宫座内角分(0–1800)/21600,最多减 1/12;式 B=自白羊起的 navāṁśa 序(1–108)/108,可减至近全额。改档即改判读总值' },
    { key: 'ayuClassBoundaries', label: '寿命档边界', group: 'ayus', default: 'bphs_32_64_120',
      options: [{ value: 'bphs_32_64_120', label: '32/64/120(默认)' }, { value: 'popular_32_70', label: '32/70' }],
      tip: '短/中/长寿分档锚点' },
    { key: 'satruksetraExemption', label: '敌座豁免', group: 'ayus', default: 'retrograde',
      options: [{ value: 'retrograde', label: '逆行豁免(默认)' }, { value: 'mars', label: '火星豁免' }],
      tip: '敌座减 1/3 的豁免条件两读' },
    { key: 'annualNakYearBasis', label: 'Mudda/年 Yoginī 年基', group: 'ayus', default: 'classical360',
      options: [{ value: 'classical360', label: '360 古典(默认)' }, { value: 'julian365_25', label: '365.25' }],
      tip: '年内宿系运的总日基;比例不变' },
    { key: 'patyayiniYearConstant', label: 'Patyāyinī 年常量', group: 'ayus', default: 'gregorian365_2425',
      options: [{ value: 'gregorian365_2425', label: '365.2425(默认)' }, { value: 'd365', label: '365(文献默认)' },
                { value: 'sidereal365_2563', label: '365.2563' }, { value: 'savana360', label: '360' }],
      tip: 'Patyāyinī 总日数常量' },
    { key: 'patyayiniLagnaPoint', label: 'Patyāyinī 上升取点', group: 'ayus', default: 'degree',
      options: [{ value: 'degree', label: '座内度数(默认)' }, { value: 'cusp', label: '宫首(文献默认)' }],
      tip: '上升的 krisamsa 取实际座内度或宫首 0°' },
    { key: 'haddaScheme', label: 'Hadda 界法', group: 'ayus', default: 'egyptian',
      options: [{ value: 'egyptian', label: '埃及界(默认)' }, { value: 'equal6', label: '等 6° 五分' }],
      tip: '界主分法:埃及不等界(日月永不为界主)或等 6° 五分' },
];
export const INDIA_DASHA_VARIANT_DEFAULTS = INDIA_DASHA_VARIANT_SPECS.reduce((m, it)=>{ m[it.key] = it.default; return m; }, {});
export function normalizeIndiaDashaVariants(raw){
    // dict/JSON 双收;只留「合法键+合法值+非默认」;解析失败/空 → {}(=全默认零 churn)。
    let data = raw;
    if(typeof raw === 'string'){
        try{ data = JSON.parse(raw); }catch(e){ return {}; }
    }
    if(!data || typeof data !== 'object' || Array.isArray(data)){ return {}; }
    const out = {};
    INDIA_DASHA_VARIANT_SPECS.forEach((spec)=>{
        const v = data[spec.key];
        if(v === undefined || v === null){ return; }
        const sv = `${v}`;
        if(sv !== spec.default && spec.options.some((o)=>o.value === sv)){
            out[spec.key] = sv;
        }
    });
    return out;
}
export function serializeIndiaDashaVariants(map){
    // 键序稳定的 JSON(缓存键/下发共用);空 map → ''(不下发)。
    const m = normalizeIndiaDashaVariants(map);
    const keys = Object.keys(m).sort();
    if(!keys.length){ return ''; }
    const stable = {};
    keys.forEach((k)=>{ stable[k] = m[k]; });
    return JSON.stringify(stable);
}

// ── AstroConst.js:1795-1824 ──
export function getIndiaSchoolDefaults(school){
    return INDIA_SCHOOL_DEFAULTS[normalizeIndiaSchool(school)] || INDIA_SCHOOL_DEFAULTS[INDIA_SCHOOL_DEFAULT];
}

// 大运体系:vimshottari(120 年,默认)/ yogini(36 年 8 女神)/ ashtottari(108 年 Ardradi)。
export const INDIA_DASHA_SYSTEM_DEFAULT = 'vimshottari';
export const INDIA_DASHA_SYSTEM_OPTIONS = [
    { value: 'vimshottari', label: 'Vimshottari' },
    { value: 'yogini', label: 'Yogini' },
    { value: 'ashtottari', label: 'Ashtottari' },
    { value: 'tribhagi', label: 'Tribhāgī（÷3）' },
    { value: 'shodashottari', label: 'Shodashottari' },
    { value: 'dvadashottari', label: 'Dvadashottari' },
    { value: 'panchottari', label: 'Panchottari' },
    { value: 'shatabdika', label: 'Shatabdika' },
    { value: 'chaturashitiSama', label: 'Chaturashiti' },
    { value: 'dwisaptatiSama', label: 'Dwisaptati' },
    { value: 'shashtihayani', label: 'Shashtihayani' },
    { value: 'shattrimshaSama', label: 'Shattrimsha' },
    { value: 'chara', label: 'Chara' },
    { value: 'taraDasha', label: 'Tāra(强度序)' },
    { value: 'akkg', label: 'AKKG(AK 播种)' },
];
// 前端展示体系(数据恒在响应 dasha 块;不下发 dashaSystem 参数 → 与默认同缓存键零请求)。
export const INDIA_DASHA_DISPLAY_ONLY_SYSTEMS = ['taraDasha', 'akkg'];

export function normalizeIndiaDashaSystem(value){
    const found = INDIA_DASHA_SYSTEM_OPTIONS.find((item)=>item.value === value);
    return found ? found.value : INDIA_DASHA_SYSTEM_DEFAULT;
}
