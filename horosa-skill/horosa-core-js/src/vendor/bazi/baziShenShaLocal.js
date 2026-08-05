function dedupe(items){ return Array.from(new Set((items || []).filter(Boolean))); }
export const BAZI_DAY_YEAR_STEMS = {
    "甲丑": ["天乙贵人"],
    "甲未": ["天乙贵人"],
    "甲子": ["太极贵人"],
    "甲午": ["太极贵人"],
    "甲巳": ["文昌贵人"],
    "乙子": ["天乙贵人", "太极贵人"],
    "乙申": ["天乙贵人"],
    "乙午": ["太极贵人", "文昌贵人"],
    "丙亥": ["天乙贵人"],
    "丙酉": ["天乙贵人", "太极贵人"],
    "丙卯": ["太极贵人"],
    "丙申": ["文昌贵人"],
    "丁亥": ["天乙贵人"],
    "丁卯": ["太极贵人"],
    "丁酉": ["天乙贵人", "太极贵人", "文昌贵人"],
    "戊丑": ["天乙贵人", "太极贵人"],
    "戊未": ["天乙贵人", "太极贵人"],
    "戊辰": ["太极贵人"],
    "戊戌": ["太极贵人"],
    "戊申": ["文昌贵人"],
    "己子": ["天乙贵人"],
    "己申": ["天乙贵人"],
    "己辰": ["太极贵人"],
    "己戌": ["太极贵人"],
    "己丑": ["太极贵人"],
    "己未": ["太极贵人"],
    "己酉": ["文昌贵人"],
    "庚丑": ["天乙贵人"],
    "庚未": ["天乙贵人"],
    "庚寅": ["太极贵人"],
    "庚亥": ["太极贵人", "文昌贵人"],
    "辛午": ["天乙贵人"],
    "辛寅": ["天乙贵人", "太极贵人"],
    "辛亥": ["太极贵人"],
    "辛子": ["文昌贵人"],
    "壬卯": ["天乙贵人"],
    "壬巳": ["天乙贵人", "太极贵人"],
    "壬申": ["太极贵人"],
    "壬寅": ["文昌贵人"],
    "癸卯": ["天乙贵人", "文昌贵人"],
    "癸巳": ["天乙贵人", "太极贵人"],
    "癸申": ["太极贵人"],
};
export const BAZI_DAY_STEMS = {
    "甲亥": ["学堂", "暗禄"],
    "甲寅": ["词馆", "禄神", "八专"],
    "甲子": ["沐浴"],
    "甲卯": ["羊刃"],
    "甲午": ["红艳"],
    "甲酉": ["流霞"],
    "乙午": ["学堂"],
    "乙卯": ["词馆", "禄神", "八专"],
    "乙巳": ["沐浴"],
    "乙戌": ["暗禄", "流霞"],
    "乙辰": ["羊刃"],
    "乙申": ["红艳"],
    "丙寅": ["学堂", "红艳"],
    "丙巳": ["词馆", "禄神"],
    "丙卯": ["沐浴"],
    "丙申": ["暗禄"],
    "丙午": ["羊刃"],
    "丙未": ["流霞"],
    "丁酉": ["学堂"],
    "丁午": ["词馆", "禄神"],
    "丁申": ["沐浴", "流霞"],
    "丁未": ["暗禄", "羊刃", "红艳", "八专"],
    "戊寅": ["学堂"],
    "戊巳": ["词馆", "禄神", "流霞"],
    "戊卯": ["沐浴"],
    "戊申": ["暗禄"],
    "戊午": ["羊刃"],
    "戊辰": ["红艳"],
    "己酉": ["学堂"],
    "己午": ["词馆", "禄神", "流霞"],
    "己申": ["沐浴"],
    "己未": ["暗禄", "羊刃", "八专"],
    "己辰": ["红艳"],
    "庚巳": ["学堂", "暗禄"],
    "庚申": ["词馆", "八专", "禄神"],
    "庚午": ["沐浴"],
    "庚酉": ["羊刃"],
    "庚戌": ["红艳"],
    "庚辰": ["流霞"],
    // 🔴 辛/壬/癸 三行曾整体缺失(表止于庚)→ 三成日元的命盘八类日干系神煞恒不出。
    // 口径与甲-庚同源:学堂=长生、词馆=临官(与禄神同宫)、暗禄=禄之六合支、沐浴=长生次位
    // (阴干逆行)、羊刃=阳干帝旺/阴干按既有阴刃口径(乙辰/丁未/己未 同族)、红艳/禄按
    // Java 权威表 gods.json、流霞按通行口诀(甲酉乙戌丙未丁申戊巳己午庚辰辛卯壬亥癸寅)。
    // 八专不入本表新行(由独立 BAZI_BAZHUAN 按日柱判,避免扩大旧双登)。
    "辛子": ["学堂"],
    "辛酉": ["词馆", "禄神", "红艳"],
    "辛辰": ["暗禄"],
    "辛亥": ["沐浴"],
    "辛戌": ["羊刃"],
    "辛卯": ["流霞"],
    "壬申": ["学堂"],
    "壬亥": ["词馆", "禄神", "流霞"],
    "壬寅": ["暗禄"],
    "壬酉": ["沐浴"],
    "壬子": ["羊刃", "红艳"],
    "癸卯": ["学堂"],
    "癸子": ["词馆", "禄神"],
    "癸丑": ["暗禄", "羊刃"],
    "癸寅": ["沐浴", "流霞"],
    "癸申": ["红艳"],
};
export const BAZI_YEAR_DAY_BRANCH = {
    "子寅": ["驿马"],
    "子辰": ["华盖"],
    "子酉": ["桃花"],
    "子巳": ["劫煞"],
    "子亥": ["亡神"],
    "子子": ["将星"],
    "丑亥": ["驿马"],
    "丑丑": ["华盖"],
    "丑午": ["桃花"],
    "丑寅": ["劫煞"],
    "丑申": ["亡神"],
    "丑酉": ["将星"],
    "寅申": ["驿马"],
    "寅戌": ["华盖"],
    "寅卯": ["桃花"],
    "寅亥": ["劫煞"],
    "寅巳": ["亡神"],
    "寅午": ["将星"],
    "卯巳": ["驿马"],
    "卯未": ["华盖"],
    "卯子": ["桃花"],
    "卯申": ["劫煞"],
    "卯寅": ["亡神"],
    "卯卯": ["将星"],
    "辰寅": ["驿马"],
    "辰辰": ["华盖"],
    "辰酉": ["桃花"],
    "辰巳": ["劫煞"],
    "辰亥": ["亡神"],
    "辰子": ["将星"],
    "巳亥": ["驿马"],
    "巳丑": ["华盖"],
    "巳午": ["桃花"],
    "巳寅": ["劫煞"],
    "巳申": ["亡神"],
    "巳酉": ["将星"],
    "午申": ["驿马"],
    "午戌": ["华盖"],
    "午卯": ["桃花"],
    "午亥": ["劫煞"],
    "午巳": ["亡神"],
    "午午": ["将星"],
    "未巳": ["驿马"],
    "未未": ["华盖"],
    "未子": ["桃花"],
    "未申": ["劫煞"],
    "未寅": ["亡神"],
    "未卯": ["将星"],
    "申寅": ["驿马"],
    "申辰": ["华盖"],
    "申酉": ["桃花"],
    "申巳": ["劫煞"],
    "申亥": ["亡神"],
    "申子": ["将星"],
    "酉亥": ["驿马"],
    "酉丑": ["华盖"],
    "酉午": ["桃花"],
    "酉寅": ["劫煞"],
    "酉申": ["亡神"],
    "酉酉": ["将星"],
    "戌申": ["驿马"],
    "戌戌": ["华盖"],
    "戌卯": ["桃花"],
    "戌亥": ["劫煞"],
    "戌巳": ["亡神"],
    "戌午": ["将星"],
    "亥巳": ["驿马"],
    "亥未": ["华盖"],
    "亥子": ["桃花"],
    "亥申": ["劫煞"],
    "亥寅": ["亡神"],
    "亥卯": ["将星"],
};
export const BAZI_DAY_BRANCH = {
    "子巳": ["破碎"],
    "丑丑": ["破碎"],
    "寅酉": ["破碎"],
    "卯巳": ["破碎"],
    "辰丑": ["破碎"],
    "巳酉": ["破碎"],
    "午巳": ["破碎"],
    "未丑": ["破碎"],
    "申酉": ["破碎"],
    "酉巳": ["破碎"],
    "戌丑": ["破碎"],
    "亥酉": ["破碎"],
};
export const BAZI_YEAR_BRANCH = {
    "子卯": ["红鸾"],
    "子寅": ["孤辰", "丧门"],
    "子戌": ["寡宿", "吊客"],
    "子亥": ["病符"],
    "子子": ["太岁"],
    "子巳": ["小耗"],
    "子午": ["大耗"],
    "丑寅": ["红鸾", "孤辰"],
    "丑戌": ["寡宿"],
    "丑子": ["病符"],
    "丑丑": ["太岁"],
    "丑卯": ["丧门"],
    "丑亥": ["吊客"],
    "丑午": ["小耗"],
    "丑未": ["大耗"],
    "寅丑": ["红鸾", "寡宿", "病符"],
    "寅巳": ["孤辰"],
    "寅寅": ["太岁"],
    "寅辰": ["丧门"],
    "寅子": ["吊客"],
    "寅未": ["小耗"],
    "寅申": ["大耗"],
    "卯子": ["红鸾"],
    "卯巳": ["孤辰", "丧门"],
    "卯丑": ["寡宿", "吊客"],
    "卯寅": ["病符"],
    "卯卯": ["太岁"],
    "卯申": ["小耗"],
    "卯酉": ["大耗"],
    "辰亥": ["红鸾"],
    "辰巳": ["孤辰"],
    "辰丑": ["寡宿"],
    "辰卯": ["病符"],
    "辰辰": ["太岁"],
    "辰午": ["丧门"],
    "辰寅": ["吊客"],
    "辰酉": ["小耗"],
    "辰戌": ["大耗"],
    "巳戌": ["红鸾", "小耗"],
    "巳申": ["孤辰"],
    "巳辰": ["寡宿", "病符"],
    "巳巳": ["太岁"],
    "巳未": ["丧门"],
    "巳卯": ["吊客"],
    "巳亥": ["大耗"],
    "午酉": ["红鸾"],
    "午申": ["孤辰", "丧门"],
    "午辰": ["寡宿", "吊客"],
    "午巳": ["病符"],
    "午午": ["太岁"],
    "午亥": ["小耗"],
    "午子": ["大耗"],
    "未申": ["红鸾", "孤辰"],
    "未辰": ["寡宿"],
    "未午": ["病符"],
    "未未": ["太岁"],
    "未酉": ["丧门"],
    "未巳": ["吊客"],
    "未子": ["小耗"],
    "未丑": ["大耗"],
    "申未": ["红鸾", "寡宿", "病符"],
    "申亥": ["孤辰"],
    "申申": ["太岁"],
    "申戌": ["丧门"],
    "申午": ["吊客"],
    "申丑": ["小耗"],
    "申寅": ["大耗"],
    "酉午": ["红鸾"],
    "酉亥": ["孤辰", "丧门"],
    "酉未": ["寡宿", "吊客"],
    "酉申": ["病符"],
    "酉酉": ["太岁"],
    "酉寅": ["小耗"],
    "酉卯": ["大耗"],
    "戌巳": ["红鸾"],
    "戌亥": ["孤辰"],
    "戌未": ["寡宿"],
    "戌酉": ["病符"],
    "戌戌": ["太岁"],
    "戌子": ["丧门"],
    "戌申": ["吊客"],
    "戌卯": ["小耗"],
    "戌辰": ["大耗"],
    "亥辰": ["红鸾", "小耗"],
    "亥寅": ["孤辰"],
    "亥戌": ["寡宿", "病符"],
    "亥亥": ["太岁"],
    "亥丑": ["丧门"],
    "亥酉": ["吊客"],
    "亥巳": ["大耗"],
};
export const BAZI_MONTH_STEMS = {
    "子壬": ["月德贵人"],
    "丑庚": ["月德贵人"],
    "寅丙": ["月德贵人"],
    "卯申": ["月德贵人"],
    "辰壬": ["月德贵人"],
    "巳庚": ["月德贵人"],
    "午丙": ["月德贵人"],
    "未甲": ["月德贵人"],
    "申壬": ["月德贵人"],
    "酉庚": ["月德贵人"],
    "戌丙": ["月德贵人"],
    "亥甲": ["月德贵人"],
};
export const BAZI_MONTH_BRANCH = {
    "子巳": ["天德贵人"],
    "子寅": ["天马", "地医"],
    "子申": ["天医"],
    "子亥": ["血支"],
    "子子": ["月厌"],
    "子午": ["月破"],
    "丑庚": ["天德贵人"],
    "丑辰": ["天马"],
    "丑酉": ["天医"],
    "丑卯": ["地医"],
    "丑子": ["血支"],
    "丑亥": ["月厌"],
    "丑未": ["月破"],
    "寅丁": ["天德贵人"],
    "寅午": ["天马"],
    "寅戌": ["天医", "月厌"],
    "寅辰": ["地医"],
    "寅丑": ["血支"],
    "寅申": ["月破"],
    "卯申": ["天德贵人", "天马"],
    "卯亥": ["天医"],
    "卯巳": ["地医"],
    "卯寅": ["血支"],
    "卯酉": ["月厌", "月破"],
    "辰壬": ["天德贵人"],
    "辰戌": ["天马", "月破"],
    "辰子": ["天医"],
    "辰午": ["地医"],
    "辰卯": ["血支"],
    "辰申": ["月厌"],
    "巳辛": ["天德贵人"],
    "巳子": ["天马"],
    "巳丑": ["天医"],
    "巳未": ["地医", "月厌"],
    "巳辰": ["血支"],
    "巳亥": ["月破"],
    "午亥": ["天德贵人"],
    "午寅": ["天马", "天医"],
    "午申": ["地医"],
    "午巳": ["血支"],
    "午午": ["月厌"],
    "午子": ["月破"],
    "未甲": ["天德贵人"],
    "未辰": ["天马"],
    "未卯": ["天医"],
    "未酉": ["地医"],
    "未午": ["血支"],
    "未巳": ["月厌"],
    "未丑": ["月破"],
    "申癸": ["天德贵人"],
    "申午": ["天马"],
    "申辰": ["天医", "月厌"],
    "申戌": ["地医"],
    "申未": ["血支"],
    "申寅": ["月破"],
    "酉寅": ["天德贵人"],
    "酉申": ["天马", "血支"],
    "酉巳": ["天医"],
    "酉亥": ["地医"],
    "酉卯": ["月厌", "月破"],
    "戌丙": ["天德贵人"],
    "戌戌": ["天马"],
    "戌午": ["天医"],
    "戌子": ["地医"],
    "戌酉": ["血支"],
    "戌寅": ["月厌"],
    "戌辰": ["月破"],
    "亥乙": ["天德贵人"],
    "亥子": ["天马"],
    "亥未": ["天医"],
    "亥丑": ["地医", "月厌"],
    "亥戌": ["血支"],
    "亥巳": ["月破"],
};

// —— Web 侧扩充条目（八字大全 §5.10 通行版）：国印/福星（干系）、天喜（年支系）、德秀（月令系）。
//    与上方生成表分离书写（不混入生成映射，便于对照校验）；运行时纯追加合并——既有键的
//    既有神煞一个不删不改，只补新名（三条消费链 calcPillarShenSha/calcFourPillarShenSha/
//    calcFlowShenSha 全走同表，自动生效）。童子煞/元辰/勾绞等原书表不全者仍不臆造。
function mergeShenSha(table, ext){
  Object.keys(ext).forEach((k) => {
    if(table[k]){ ext[k].forEach((n) => { if(table[k].indexOf(n) < 0){ table[k].push(n); } }); }
    else { table[k] = ext[k].slice(); }
  });
}
// 国印贵人（干→禄后顺数三位支）+ 福星贵人（干→支，通行两支/一支版）；按年干/日干起（进干系表）。
mergeShenSha(BAZI_DAY_YEAR_STEMS, {
  甲戌: ['国印贵人'], 乙亥: ['国印贵人', '福星贵人'], 丙丑: ['国印贵人'], 丁寅: ['国印贵人'],
  戊丑: ['国印贵人'], 己寅: ['国印贵人'], 庚辰: ['国印贵人'], 辛巳: ['国印贵人', '福星贵人'],
  壬未: ['国印贵人'], 癸申: ['国印贵人'],
  甲寅: ['福星贵人'], 甲子: ['福星贵人'], 丙寅: ['福星贵人'], 丙子: ['福星贵人'],
  乙丑: ['福星贵人'], 癸丑: ['福星贵人'], 癸亥: ['福星贵人'],
  戊申: ['福星贵人'], 己未: ['福星贵人'], 丁亥: ['福星贵人'], 庚午: ['福星贵人'], 壬辰: ['福星贵人'],
});
// 天喜（年支→红鸾对宫支；红鸾=卯起子年逆行，本表与上方红鸾条目严格对宫）。
mergeShenSha(BAZI_YEAR_BRANCH, {
  子酉: ['天喜'], 丑申: ['天喜'], 寅未: ['天喜'], 卯午: ['天喜'], 辰巳: ['天喜'], 巳辰: ['天喜'],
  午卯: ['天喜'], 未寅: ['天喜'], 申丑: ['天喜'], 酉子: ['天喜'], 戌亥: ['天喜'], 亥戌: ['天喜'],
});
// 德秀贵人（月支三合局→配干，德/秀并取一名；月令系恒查）。
mergeShenSha(BAZI_MONTH_STEMS, (function(){
  const m = {};
  const put = (months, gans) => { months.forEach((mz) => { gans.forEach((g) => { m[mz + g] = ['德秀贵人']; }); }); };
  put(['寅', '午', '戌'], ['丙', '丁', '戊', '癸']);
  put(['申', '子', '辰'], ['壬', '癸', '戊', '己', '丙', '辛', '甲']);
  put(['巳', '酉', '丑'], ['庚', '辛', '乙']);
  put(['亥', '卯', '未'], ['甲', '乙', '丁', '壬']);
  return m;
}()));

function fromMap(map, key){ return map && map[key] ? map[key] : []; }

// —— 神煞分组标签（G8 显示过滤用；通行粗分，仅控显示、不改任何计算/输出数组本体）——
// 维度可叠：ji 吉神 / xiong 凶煞（全覆盖）；yue 月令系 / ri 日柱系（叠加维度）。
// 未入表的新名恒显示（漏网安全，宁多勿漏）。
export const SHENSHA_GROUP_TAGS = {
	天乙贵人: ['ji'], 太极贵人: ['ji'], 文昌贵人: ['ji'], 国印贵人: ['ji'], 福星贵人: ['ji'],
	天德贵人: ['ji', 'yue'], 月德贵人: ['ji', 'yue'], 天德合: ['ji', 'yue'], 月德合: ['ji', 'yue'],
	德秀贵人: ['ji', 'yue'], 天医: ['ji', 'yue'], 地医: ['ji', 'yue'], 天马: ['ji', 'yue'],
	天喜: ['ji'], 红鸾: ['ji'], 金舆: ['ji'], 三奇: ['ji'],
	学堂: ['ji', 'ri'], 词馆: ['ji', 'ri'], 禄神: ['ji', 'ri'], 暗禄: ['ji', 'ri'],
	驿马: ['ji'], 将星: ['ji'], 华盖: ['ji'],
	羊刃: ['xiong', 'ri'], 红艳: ['xiong', 'ri'], 流霞: ['xiong', 'ri'], 沐浴: ['xiong', 'ri'], 八专: ['xiong', 'ri'],
	劫煞: ['xiong'], 灾煞: ['xiong'], 亡神: ['xiong'], 桃花: ['xiong'],
	孤辰: ['xiong'], 寡宿: ['xiong'], 病符: ['xiong'], 小耗: ['xiong'], 大耗: ['xiong'],
	太岁: ['xiong'], 丧门: ['xiong'], 吊客: ['xiong'], 破碎: ['xiong'],
	血支: ['xiong', 'yue'], 月厌: ['xiong', 'yue'], 月破: ['xiong', 'yue'],
	阴差阳错: ['xiong', 'ri'], 十恶大败: ['xiong', 'ri'], 九丑: ['xiong', 'ri'], 四废: ['xiong', 'ri'],
};

// 按分组开关过滤神煞名（groups={ji,xiong,yue,ri}，缺省/全开=原数组引用直返=零开销零回归）。
// 语义：名字的标签集与「开着的组」有交集即显示；关组只隐藏「其全部标签都被关」的名字。
// 🔴 两个维度独立判定,不能一把 some 了事(2026-07-31 运行时死开关审计实证)。
//   四个分组其实是**两个正交维度**:性质(吉神/凶煞) 与 来源(月令系/日柱系)。
//   旧实现对全部标签做 tags.some(开),等于把两个维度并成一个「或」,后果是两头都失效:
//   ① 全表 49 条里没有任何一条是「仅月令系」或「仅日柱系」——yue/ri 恒与 ji/xiong 并存,
//      于是只要吉神或凶煞还开着,关掉月令系/日柱系**在任何盘、任何数据下都移除不了任何东西**,
//      这两个开关结构性恒真(实测点了盘面零变化)。
//   ② 反过来,关掉「吉神」时那 8 条 ji+yue 会被 yue「救活」而不消失,与用户预期相反。
//   正解:维度内取或(该维度任一所属组开着即通过),维度间取与(两个维度都要通过);
//   某维度无标签则该维度不设限。默认全开时提前返回,与改动前逐字节相同(零回归)。
const SHENSHA_NATURE_GROUPS = ['ji', 'xiong'];
const SHENSHA_SOURCE_GROUPS = ['yue', 'ri'];

export function filterShenShaByGroups(names, groups){
	if(!Array.isArray(names) || !names.length || !groups){ return names; }
	const off = ['ji', 'xiong', 'yue', 'ri'].filter((k) => groups[k] === false);
	if(!off.length){ return names; }
	const dimOk = (tags, dim) => {
		const own = tags.filter((t) => dim.indexOf(t) >= 0);
		if(!own.length){ return true; }              // 该维度无标签 → 不设限
		return own.some((t) => groups[t] !== false); // 维度内:任一所属组开着即通过
	};
	return names.filter((n) => {
		const tags = SHENSHA_GROUP_TAGS[n];
		if(!tags){ return true; }                     // 未入表者恒显(既有口径,不在本次改动范围)
		return dimOk(tags, SHENSHA_NATURE_GROUPS) && dimOk(tags, SHENSHA_SOURCE_GROUPS);
	});
}

// —— 补充神煞（全表见 八字大全 §5，仅收录原书给全对照表者，不臆造残表）——
// 金舆（§5.1 禄前二位，按日干/年干 → 支）：丙戊同未、丁己同申
const BAZI_JINYU = { 甲: '辰', 乙: '巳', 丙: '未', 戊: '未', 丁: '申', 己: '申', 庚: '戌', 辛: '亥', 壬: '丑', 癸: '寅' };
// 灾煞（§5.2 年/日支三合局 → 胎/旺前位）：申子辰→午、寅午戌→子、巳酉丑→卯、亥卯未→酉
const BAZI_ZAISHA = { 申: '午', 子: '午', 辰: '午', 寅: '子', 午: '子', 戌: '子', 巳: '卯', 酉: '卯', 丑: '卯', 亥: '酉', 卯: '酉', 未: '酉' };
// 三奇贵人（§5.6，年月日 或 日月时 三天干成一组，集合判定）
const BAZI_SANQI = [['甲', '戊', '庚'], ['乙', '丙', '丁'], ['壬', '癸', '辛']];
// 阴差阳错日（§5.8，特定日柱）
const BAZI_YINCHA = new Set(['丙子', '丁丑', '戊寅', '辛卯', '壬辰', '癸巳', '丙午', '丁未', '戊申', '辛酉', '壬戌', '癸亥']);
// 十恶大败日（§5.9，禄入空亡，特定日柱）
const BAZI_SHIE = new Set(['甲辰', '乙巳', '丙申', '丁亥', '戊戌', '己丑', '庚辰', '辛巳', '壬申', '癸亥']);
// 天医（§5.3，月支退一位）：所在柱地支命中即取
const BAZI_TIANYI_MED = { 寅: '丑', 卯: '寅', 辰: '卯', 巳: '辰', 午: '巳', 未: '午', 申: '未', 酉: '申', 戌: '酉', 亥: '戌', 子: '亥', 丑: '子' };
// 月德合（§5.3 衍生，月支三合局 → 合月德之干）：寅午戌→辛、申子辰→丁、亥卯未→己、巳酉丑→乙
const BAZI_YUEDEHE = { 寅: '辛', 午: '辛', 戌: '辛', 申: '丁', 子: '丁', 辰: '丁', 亥: '己', 卯: '己', 未: '己', 巳: '乙', 酉: '乙', 丑: '乙' };
// 天德合（§5.3 衍生，合天德之干/支，按月支）
const BAZI_TIANDEHE = { 寅: '壬', 卯: '巳', 辰: '丁', 巳: '丙', 午: '寅', 未: '己', 申: '戊', 酉: '亥', 戌: '辛', 亥: '庚', 子: '申', 丑: '乙' };
// 八专日（§5.10，干支同气特定日柱）
const BAZI_BAZHUAN = new Set(['甲寅', '乙卯', '己未', '丁未', '庚申', '辛酉', '戊戌', '癸丑']);
// 九丑日（§5.10，特定日柱）
const BAZI_JIUCHOU = new Set(['戊子', '戊午', '己卯', '己酉', '壬子', '壬午', '癸卯', '癸酉']);
// 四废日（§5.10，按季节衰绝之干支日）：春庚申辛酉、夏壬子癸亥、秋甲寅乙卯、冬丙午丁巳
const BAZI_SIFEI = { 春: new Set(['庚申', '辛酉']), 夏: new Set(['壬子', '癸亥']), 秋: new Set(['甲寅', '乙卯']), 冬: new Set(['丙午', '丁巳']) };
const SEASON_OF_MONTH = { 寅: '春', 卯: '春', 辰: '春', 巳: '夏', 午: '夏', 未: '夏', 申: '秋', 酉: '秋', 戌: '秋', 亥: '冬', 子: '冬', 丑: '冬' };

// 神煞主位（godKeyPos：'年' / '日' / '年日'）→ 允许的「主位基组」集合。
// 对齐 Java GodsHelper.findGods(fourCols, zhu)：rule.keyZhu 非空者（月令系：天德/月德/月破/天医/天马/
// 月厌/血支/地医 等）恒以月支为基、与主位无关恒查；rule.keyZhu 空者（主位系：天乙/桃花/华盖/驿马/红鸾…）
// 才按主位用「年柱」或「日柱」当查神煞的基（'年日' = 年基∪日基）。月柱基组（月令系）任何档恒含。
function allowedBases(godKeyPos){
  if(godKeyPos === '日'){ return { Y: false, D: true }; }
  if(godKeyPos === '年日'){ return { Y: true, D: true }; }
  return { Y: true, D: false }; // 默认 '年'：年主位基组 + 月令（恒）；不含日主位基组。
}

export function calcPillarShenSha(base, target, godKeyPos){
  const yearGan = base && base.yearGan ? base.yearGan : '';
  const yearZhi = base && base.yearZhi ? base.yearZhi : '';
  const monthZhi = base && base.monthZhi ? base.monthZhi : '';
  const dayGan = base && base.dayGan ? base.dayGan : '';
  const dayZhi = base && base.dayZhi ? base.dayZhi : '';
  const gan = target && target.gan ? target.gan : '';
  const zhi = target && target.zhi ? target.zhi : '';
  const allow = allowedBases(godKeyPos);
  // 年主位基组（以年柱干/支为基）
  const yearBase = [
    ...fromMap(BAZI_DAY_YEAR_STEMS, yearGan + zhi),
    ...fromMap(BAZI_YEAR_DAY_BRANCH, yearZhi + zhi),
    ...fromMap(BAZI_YEAR_BRANCH, yearZhi + zhi),
    (zhi && BAZI_JINYU[yearGan] === zhi) ? '金舆' : null,
    (zhi && BAZI_ZAISHA[yearZhi] === zhi) ? '灾煞' : null,
  ];
  // 日主位基组（以日柱干/支为基）
  const dayBase = [
    ...fromMap(BAZI_DAY_YEAR_STEMS, dayGan + zhi),
    ...fromMap(BAZI_DAY_STEMS, dayGan + zhi),
    ...fromMap(BAZI_YEAR_DAY_BRANCH, dayZhi + zhi),
    ...fromMap(BAZI_DAY_BRANCH, dayZhi + zhi),
    (zhi && BAZI_JINYU[dayGan] === zhi) ? '金舆' : null,
    (zhi && BAZI_ZAISHA[dayZhi] === zhi) ? '灾煞' : null,
  ];
  // 月令基组（以月支为基，恒含）
  const monthBase = [
    ...fromMap(BAZI_MONTH_BRANCH, monthZhi + zhi),
    ...fromMap(BAZI_MONTH_STEMS, monthZhi + gan),
  ];
  return dedupe([
    ...(allow.Y ? yearBase : []),
    ...(allow.D ? dayBase : []),
    ...monthBase,
  ]);
}

export function calcFourPillarShenSha(four, godKeyPos){
  const getGan = (item)=>item && item.stem ? item.stem.cell || '' : '';
  const getZhi = (item)=>item && item.branch ? item.branch.cell || '' : '';
  const Yg = getGan(four && four.year), Yz = getZhi(four && four.year);
  const Mg = getGan(four && four.month), Mz = getZhi(four && four.month);
  const Dg = getGan(four && four.day), Dz = getZhi(four && four.day);
  const Tg = getGan(four && four.time), Tz = getZhi(four && four.time);
  const fm = fromMap;
  const allow = allowedBases(godKeyPos);
  // 主位敏感的补充神煞（金舆/灾煞）按基柱拆：年基只看 Yg/Yz、日基只看 Dg/Dz；
  // 月令系补充神煞（天医/月德合/天德合，以月支 Mz 为基）恒含。
  const augJinyuYear = (zhi)=>(zhi && BAZI_JINYU[Yg] === zhi) ? '金舆' : null;
  const augZaishaYear = (zhi)=>(zhi && BAZI_ZAISHA[Yz] === zhi) ? '灾煞' : null;
  const augJinyuDay = (zhi)=>(zhi && BAZI_JINYU[Dg] === zhi) ? '金舆' : null;
  const augZaishaDay = (zhi)=>(zhi && BAZI_ZAISHA[Dz] === zhi) ? '灾煞' : null;
  const augTianyi = (zhi)=>(zhi && BAZI_TIANYI_MED[Mz] === zhi) ? '天医' : null;
  const augYuedehe = (gan)=>(gan && BAZI_YUEDEHE[Mz] === gan) ? '月德合' : null;
  const augTiandehe = (gan, zhi)=>(BAZI_TIANDEHE[Mz] && (BAZI_TIANDEHE[Mz] === gan || BAZI_TIANDEHE[Mz] === zhi)) ? '天德合' : null;

  // 逐柱查法（年/月/日/时 各自的干支组合，非统一查法）。
  // 每个 token 形如 [base, ...values]，base∈{'Y'年主位 / 'D'日主位 / 'M'月令}。token 顺序严格保留旧版，
  // 按 godKeyPos 过滤掉不允许的 base 后 flatten+dedupe：
  //   · godKeyPos='年日' → Y/D/M 全保留 → 与旧版逐字一致（旧默认即恒并年+日，是本地 bug）。
  //   · godKeyPos='年'（新默认）→ 仅 Y+M（剔除 D 段），与 Java GodsHelper(zhu='年') 一致。
  //   · godKeyPos='日' → 仅 D+M。
  // 旧版 aug(基,zhi) 整块（[金舆,灾煞,天医,月德合,天德合]）在每柱末尾，这里将其拆回各自 base 并保持「在该柱末」
  // 的相对位置（金舆/灾煞按年/日基拆，天医/月德合/天德合归月令），故 '年日' 档 token 序与旧版完全一致。
  const flat = (tokens)=>dedupe(tokens.filter((t)=>allow[t[0]] !== false).reduce((arr, t)=>arr.concat(t.slice(1)), []));
  const acc = {
    year: flat([
      ['Y', ...fm(BAZI_DAY_YEAR_STEMS, Yg + Yz)],
      ['D', ...fm(BAZI_DAY_STEMS, Dg + Yz)],
      ['D', ...fm(BAZI_YEAR_DAY_BRANCH, Dz + Yz)],
      ['D', ...fm(BAZI_DAY_BRANCH, Dz + Yg)],
      ['M', ...fm(BAZI_MONTH_STEMS, Mz + Yg)],
      ['M', ...fm(BAZI_MONTH_BRANCH, Mz + Yz)],
      ['Y', augJinyuYear(Yz)], ['D', augJinyuDay(Yz)],
      ['Y', augZaishaYear(Yz)], ['D', augZaishaDay(Yz)],
      ['M', augTianyi(Yz)], ['M', augYuedehe(Yg)], ['M', augTiandehe(Yg, Yz)],
    ]),
    month: flat([
      ['Y', ...fm(BAZI_DAY_YEAR_STEMS, Yg + Mz)],
      ['D', ...fm(BAZI_DAY_YEAR_STEMS, Dg + Mz)], ['D', ...fm(BAZI_DAY_STEMS, Dg + Mz)],
      ['Y', ...fm(BAZI_YEAR_DAY_BRANCH, Yz + Mz)], ['Y', ...fm(BAZI_YEAR_BRANCH, Yz + Mz)],
      ['D', ...fm(BAZI_YEAR_DAY_BRANCH, Dz + Mz)], ['D', ...fm(BAZI_DAY_BRANCH, Dz + Mz)],
      ['M', ...fm(BAZI_MONTH_STEMS, Mz + Mg)],
      ['Y', augJinyuYear(Mz)], ['D', augJinyuDay(Mz)],
      ['Y', augZaishaYear(Mz)], ['D', augZaishaDay(Mz)],
      ['M', augTianyi(Mz)], ['M', augYuedehe(Mg)], ['M', augTiandehe(Mg, Mz)],
    ]),
    day: flat([
      ['Y', ...fm(BAZI_DAY_YEAR_STEMS, Yg + Dz)], ['Y', ...fm(BAZI_YEAR_BRANCH, Yg + Dz)],
      ['D', ...fm(BAZI_DAY_YEAR_STEMS, Dg + Dz)], ['D', ...fm(BAZI_DAY_STEMS, Dg + Dz)],
      ['Y', ...fm(BAZI_YEAR_DAY_BRANCH, Yz + Dz)], ['Y', ...fm(BAZI_YEAR_BRANCH, Yz + Dz)],
      ['M', ...fm(BAZI_MONTH_STEMS, Mz + Dg)], ['M', ...fm(BAZI_MONTH_BRANCH, Mz + Dz)],
      ['Y', augJinyuYear(Dz)], ['D', augJinyuDay(Dz)],
      ['Y', augZaishaYear(Dz)], ['D', augZaishaDay(Dz)],
      ['M', augTianyi(Dz)], ['M', augYuedehe(Dg)], ['M', augTiandehe(Dg, Dz)],
    ]),
    time: flat([
      ['Y', ...fm(BAZI_DAY_YEAR_STEMS, Yg + Tz)], ['D', ...fm(BAZI_DAY_YEAR_STEMS, Dg + Tz)],
      ['D', ...fm(BAZI_DAY_BRANCH, Dz + Tz)],
      ['Y', ...fm(BAZI_YEAR_DAY_BRANCH, Yz + Tz)], ['Y', ...fm(BAZI_YEAR_BRANCH, Yz + Tz)],
      ['D', ...fm(BAZI_YEAR_DAY_BRANCH, Dz + Tz)], ['D', ...fm(BAZI_DAY_BRANCH, Dz + Tz)],
      ['M', ...fm(BAZI_MONTH_BRANCH, Mz + Tz)], ['M', ...fm(BAZI_MONTH_STEMS, Mz + Tg)],
      ['Y', augJinyuYear(Tz)], ['D', augJinyuDay(Tz)],
      ['Y', augZaishaYear(Tz)], ['D', augZaishaDay(Tz)],
      ['M', augTianyi(Tz)], ['M', augYuedehe(Tg)], ['M', augTiandehe(Tg, Tz)],
    ]),
  };

  // —— 整盘级神煞（新增项，§5.6/§5.8/§5.9）——
  const gm = Mg;
  const gt = Tg;
  const trios = [
    [[Yg, gm, Dg], ['year','month','day']],
    [[Dg, gm, gt], ['day','month','time']],
  ];
  trios.forEach(([stems, keys])=>{
    const set = new Set(stems.filter(Boolean));
    if(set.size === 3 && BAZI_SANQI.some((t)=>t.every((g)=>set.has(g)))){
      keys.forEach((k)=>{ if(acc[k]){ acc[k] = dedupe([...acc[k], '三奇']); } });
    }
  });
  // 日柱专断（§5.8 / §5.9 / §5.10）
  const dayGz = (Dg || '') + (Dz || '');
  if(BAZI_YINCHA.has(dayGz) && acc.day){ acc.day = dedupe([...acc.day, '阴差阳错']); }
  if(BAZI_SHIE.has(dayGz) && acc.day){ acc.day = dedupe([...acc.day, '十恶大败']); }
  if(BAZI_BAZHUAN.has(dayGz) && acc.day){ acc.day = dedupe([...acc.day, '八专']); }
  if(BAZI_JIUCHOU.has(dayGz) && acc.day){ acc.day = dedupe([...acc.day, '九丑']); }
  const season = SEASON_OF_MONTH[Mz];
  if(season && BAZI_SIFEI[season] && BAZI_SIFEI[season].has(dayGz) && acc.day){ acc.day = dedupe([...acc.day, '四废']); }

  return acc;
}

// 流运（大运/流年/流月/流日）某柱神煞：以本命年/月/日干支为基，查流运柱干支。
export function calcFlowShenSha(four, gan, zhi){
  if(!four || !zhi){ return []; }
  const getGan = (item)=>item && item.stem ? item.stem.cell || '' : '';
  const getZhi = (item)=>item && item.branch ? item.branch.cell || '' : '';
  const Yg = getGan(four.year), Yz = getZhi(four.year);
  const Mz = getZhi(four.month);
  const Dg = getGan(four.day), Dz = getZhi(four.day);
  const fm = fromMap;
  const aug = [];
  if(zhi && (BAZI_JINYU[Yg] === zhi || BAZI_JINYU[Dg] === zhi)){ aug.push('金舆'); }
  if(zhi && (BAZI_ZAISHA[Yz] === zhi || BAZI_ZAISHA[Dz] === zhi)){ aug.push('灾煞'); }
  if(zhi && BAZI_TIANYI_MED[Mz] === zhi){ aug.push('天医'); }
  if(gan && BAZI_YUEDEHE[Mz] === gan){ aug.push('月德合'); }
  if(BAZI_TIANDEHE[Mz] && (BAZI_TIANDEHE[Mz] === gan || BAZI_TIANDEHE[Mz] === zhi)){ aug.push('天德合'); }
  return dedupe([
    ...fm(BAZI_DAY_YEAR_STEMS, Yg + zhi),
    ...fm(BAZI_DAY_YEAR_STEMS, Dg + zhi),
    ...fm(BAZI_DAY_BRANCH, Dz + zhi),
    ...fm(BAZI_YEAR_DAY_BRANCH, Yz + zhi),
    ...fm(BAZI_YEAR_BRANCH, Yz + zhi),
    ...fm(BAZI_YEAR_DAY_BRANCH, Dz + zhi),
    ...fm(BAZI_DAY_BRANCH, Dz + zhi),
    ...fm(BAZI_MONTH_BRANCH, Mz + zhi),
    ...fm(BAZI_MONTH_STEMS, Mz + (gan || '')),
    ...aug,
  ]);
}
