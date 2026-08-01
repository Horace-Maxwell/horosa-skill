// divination/data/fixedStars.js
// 恒星表（择日清单 §2.6）。lon_1995 = 1995 回归黄经（绝对 0–360）；岁差 50.27″/年。
// 仅当恒星会合(≤1°,最多1.5°)命度/天顶/命主/用事星/日/月 时显示；关键点也要避开不利恒星。
// nature/meaning 与位置无关，长期可用。

export const PRECESSION_ARCSEC_PER_YEAR = 50.27;

export const FIXED_STARS = [
	// 主用 10 星（常用集）
	{ name_cn: '大陵五', name_en: 'Algol', magnitude: 2.1, lon_1995: 56.17, declination: 40.95, nature: ['mars', 'saturn'], meaning: '困难/阻碍/失败/延迟/不幸', election: { avoid: true, good_for: [] }, behenian: { order: '1', gem: '钻石', herb: '黑藜芦、艾', use: '使人勇敢豪迈,护身防巫术;强而危险' } },
	{ name_cn: '昴宿六', name_en: 'Alcyone', magnitude: 2.9, lon_1995: 60.0, declination: 24.10, nature: ['moon', 'mars'], meaning: '同情/感伤/失望', election: { avoid: true, good_for: [] }, behenian: { order: '2', gem: '水晶', herb: '茴香、乳香', use: '增视力,召灵召风,揭秘' } },
	{ name_cn: '毕宿五', name_en: 'Aldebaran', magnitude: 0.9, isRoyal: true, lon_1995: 69.8, declination: 16.51, nature: ['mars'], meaning: '爆发/冲动/刑伤/精力/开创', election: { avoid: true, good_for: ['career'], conditional: '除非刻意取火星之力，否则避' }, behenian: { order: '3', gem: '红宝石', herb: '乳蓟、乳香脂', use: '赐财富荣誉;口才正直,受克则暴烈' }, royal: { watcher: '东', persian: 'Tascheter', angel: '米迦勒 Michael' } },
	{ name_cn: '轩辕十四', name_en: 'Regulus', magnitude: 1.4, isRoyal: true, lon_1995: 149.83, declination: 11.97, nature: ['mars', 'jupiter'], meaning: '荣耀/名声/权力/成功/骄傲', election: { avoid: false, good_for: ['career'], conditional: '利事业、不利婚姻' }, behenian: { order: '7', gem: '花岗石(或榴石)', herb: '白屈菜、艾、乳香脂', use: '勇气豪迈胜敌,驱忧郁,使人节制受敬' }, royal: { watcher: '北', persian: 'Venant', angel: '拉斐尔 Raphael' } },
	{ name_cn: '东次将', name_en: 'Vindemiatrix', magnitude: 2.8, lon_1995: 189.93, declination: 10.96, nature: ['saturn', 'mercury'], meaning: '困难/不幸/障碍/失望(寡居星)', election: { avoid: true, good_for: [] } },
	{ name_cn: '角宿一', name_en: 'Spica', magnitude: 1.0, lon_1995: 203.85, declination: -11.15, nature: ['venus', 'mars'], meaning: '成功/幸运/财富/繁荣', election: { avoid: false, good_for: ['career', 'marriage'] }, behenian: { order: '10', gem: '祖母绿', herb: '鼠尾草、三叶草、长春花', use: '赐财富、学术艺术之成功;最吉护佑' }, natureVariants: [['venus','mercury'],['mercury','mars']] },
	{ name_cn: '心宿二', name_en: 'Antares', magnitude: 1.0, isRoyal: true, lon_1995: 249.77, declination: -26.43, nature: ['mars', 'jupiter'], meaning: '暴力/冲突/自信/独断(皇室星)', election: { avoid: false, good_for: ['career'], conditional: '事业开创可用，婚姻勿用' }, behenian: { order: '13', gem: '紫水晶(或缠丝玛瑙)', herb: '马兜铃、藏红花', use: '赐胆魄军功胜敌;鲁莽有中毒失宠之险' }, royal: { watcher: '西', persian: 'Satevis', angel: '乌列尔 Uriel' } },
	{ name_cn: '织女星', name_en: 'Vega', magnitude: 0.03, lon_1995: 285.32, declination: 38.78, nature: ['venus', 'mercury'], meaning: '幸运/成功/财富/口才', election: { avoid: false, good_for: ['career', 'marriage'], conditional: '吉星会合可用，凶星会合避' }, behenian: { order: '14', gem: '橄榄石', herb: '冬香薄荷、球果堇', use: '使人庄重有望受爱;助符咒揭秘' } },
	{ name_cn: '北落师门', name_en: 'Fomalhaut', magnitude: 1.2, isRoyal: true, lon_1995: 333.87, declination: -29.62, nature: ['venus', 'mercury'], meaning: '改变/不定/适应/名声', election: { avoid: true, good_for: [], conditional: '不安定性强，最好不用' }, behenian: { order: '15*', gem: '红榴石/橄榄石', herb: '金盏花、芸香、艾', use: '赐名声荣誉与神秘之运(末位异本之二)' }, royal: { watcher: '南', persian: 'Haftorang', angel: '加百列 Gabriel' } },
	{ name_cn: '室宿二', name_en: 'Scheat', magnitude: 2.4, lon_1995: 359.37, declination: 28.08, nature: ['mars', 'mercury'], meaning: '困难/意外/失败/阻挠', election: { avoid: true, good_for: [] } },
	// 扩展星表（节选高频）
	{ name_cn: '壁宿二', name_en: 'Alpheratz', magnitude: 2.1, lon_1995: 14.30, declination: 29.08, nature: ['jupiter', 'venus'], meaning: '演艺/艺术名声·独立·声誉', election: { avoid: false, good_for: ['career'] } },
	{ name_cn: '奎宿九', name_en: 'Mirach', magnitude: 2.1, lon_1995: 30.40, declination: 35.60, nature: ['venus'], meaning: '顾家·由婚姻带来好运·美丽·才艺', election: { avoid: false, good_for: ['marriage'] } },
	{ name_cn: '娄宿三', name_en: 'Hamal', magnitude: 2.0, lon_1995: 37.67, declination: 23.45, nature: ['saturn', 'mars'], meaning: '暴力·残忍·犯罪·亦主治疗者', election: { avoid: true, good_for: [] } },
	{ name_cn: '五车二', name_en: 'Capella', magnitude: 0.1, lon_1995: 81.85, declination: 46.0, nature: ['mars', 'mercury'], meaning: '名誉·学习·好奇·物质成功', election: { avoid: false, good_for: ['career'] }, behenian: { order: '4', gem: '蓝宝石', herb: '夏枯草、薄荷、曼德拉草', use: '得贵人之助、荣誉;助学问、寻回失物' } },
	{ name_cn: '天狼星', name_en: 'Sirius', magnitude: -1.5, lon_1995: 104.08, declination: -16.70, nature: ['jupiter', 'mars'], meaning: '野心·热诚·财富·名誉(躔天顶主声誉卓著)', election: { avoid: false, good_for: ['career'] }, behenian: { order: '5', gem: '绿柱石', herb: '圆柏、艾、龙木', use: '带荣誉善意;安抚统治者' } },
	{ name_cn: '南河三', name_en: 'Procyon', magnitude: 0.4, lon_1995: 115.78, declination: 5.22, nature: ['mercury', 'mars'], meaning: '行动力·暴力·急躁·骤起骤落', election: { avoid: true, good_for: [] }, behenian: { order: '6', gem: '玛瑙', herb: '唇萼薄荷、毛茛', use: '赐善意护佑;助抗病但运速来速去' } },
	{ name_cn: '大角', name_en: 'Arcturus', magnitude: -0.05, lon_1995: 204.23, declination: 19.18, nature: ['jupiter', 'mars'], meaning: '进取·名誉·财富·因旅游获益·持久成功', election: { avoid: false, good_for: ['career'] }, behenian: { order: '11', gem: '碧玉', herb: '车前草、艾', use: '为繁荣、旅行获利;诉讼得助' } },
	{ name_cn: '河鼓二(牛郎)', name_en: 'Altair', magnitude: 0.8, lon_1995: 301.78, declination: 8.87, nature: ['jupiter', 'mars'], meaning: '突短运气·冲动·自信·野心；利法律/军事/占星', election: { avoid: false, good_for: ['career'] } },
	{ name_cn: '室宿一', name_en: 'Markab', magnitude: 2.5, lon_1995: 353.48, declination: 15.18, nature: ['mars', 'mercury'], meaning: '暴力·意外·手术·法律·名誉·心智', election: { avoid: true, good_for: [] } },
	// 补充高频星（双子—宝瓶段，卜卦常触及征象星/命度）
	{ name_cn: '参宿七', name_en: 'Rigel', magnitude: 0.1, lon_1995: 76.62, declination: -8.20, nature: ['jupiter', 'mars'], meaning: '技术·教育·荣显·持久成就', election: { avoid: false, good_for: ['career'] }, natureVariants: [['jupiter','saturn'],['jupiter','mars']] },
	{ name_cn: '参宿四', name_en: 'Betelgeuse', magnitude: 0.5, lon_1995: 88.60, declination: 7.40, nature: ['mars', 'mercury'], meaning: '武勇·荣誉·骤起之运·竞争', election: { avoid: false, good_for: ['career'] } },
	{ name_cn: '北河二', name_en: 'Castor', magnitude: 1.6, lon_1995: 110.10, declination: 31.90, nature: ['mercury'], meaning: '心智·写作·机变·亦主伤病', election: { avoid: false, good_for: ['travel'] } },
	{ name_cn: '北河三', name_en: 'Pollux', magnitude: 1.1, lon_1995: 113.20, declination: 28.03, nature: ['mars'], meaning: '强势·竞争·权谋·凶暴一面', election: { avoid: true, good_for: [] } },
	{ name_cn: '五帝座一', name_en: 'Denebola', magnitude: 2.1, lon_1995: 171.42, declination: 14.57, nature: ['saturn', 'venus'], meaning: '时运升沉·不合流俗·改革', election: { avoid: true, good_for: [] } },
	{ name_cn: '垒壁阵四', name_en: 'Deneb Algedi', magnitude: 2.9, lon_1995: 323.43, declination: -16.13, nature: ['saturn', 'jupiter'], meaning: '公正·立法·善恶两面·守护', election: { avoid: false, good_for: ['lawsuit', 'career'] }, behenian: { order: '15', gem: '玉髓', herb: '墨角兰、艾、曼德拉草、龙葵', use: '为法律行政之权、持久智慧仁慈' } },
	// 卜卦 04§9.1 补齐（2026-07 补录;lon_1995 由 ≈2000 黄经回推 5 年岁差）
	{ name_cn: '鬼宿星团', name_en: 'Praesepe', lon_1995: 127.26, declination: 19.67, nature: ['mars', 'moon'], meaning: '朦胧致盲·热病·耻辱(合受克发光体损视力)', election: { avoid: true, good_for: [] }, magnitude: 3.7, natureVariants: [['mars','moon'],['mars','sun']] },
	{ name_cn: '星宿一', name_en: 'Alphard', lon_1995: 147.21, declination: -8.66, nature: ['saturn', 'venus'], meaning: '智慧而缺自制·中毒/窒息之险', election: { avoid: true, good_for: [] }, magnitude: 2.0 },
	{ name_cn: '西上相', name_en: 'Zosma', lon_1995: 161.25, declination: 20.52, nature: ['saturn', 'venus'], meaning: '忧郁·代罪羔羊·惧中毒', election: { avoid: true, good_for: [] }, magnitude: 2.6 },
	{ name_cn: '尾宿蜂巢(M6)', name_en: 'Aculeus', lon_1995: 265.68, declination: -32.22, nature: ['mars', 'moon'], meaning: '朦胧·损视力(合受克发光体则失明)', election: { avoid: true, good_for: [] }, magnitude: 4.2 },
	{ name_cn: '尾宿托勒密团(M7)', name_en: 'Acumen', lon_1995: 268.68, declination: -34.80, nature: ['mars', 'moon'], meaning: '朦胧·视力问题·慢性顽疾', election: { avoid: true, good_for: [] }, magnitude: 3.3 },
	{ name_cn: '斗宿人马团(M22)', name_en: 'Facies', lon_1995: 278.21, declination: -23.90, nature: ['sun', 'mars'], meaning: '冷酷·暴力·失明·事故', election: { avoid: true, good_for: [] }, magnitude: 5.1 },
	// R2 补星(择日增补卷 §9.2 全表缺口;lon_1995 由 J2000 回推 5 年岁差)
	{ name_cn: '参宿五', name_en: 'Bellatrix', magnitude: 1.6, lon_1995: 80.88, declination: 6.35, nature: ['mars', 'mercury'], meaning: '女战士星:苦斗得成、骤荣骤辱', election: { avoid: true, good_for: [] } },
	{ name_cn: '轸宿一', name_en: 'Algorab', magnitude: 3.0, lon_1995: 193.36, declination: -16.52, nature: ['mars', 'saturn'], meaning: '乌鸦之翼:食腐可憎、破坏;压抑后突破', election: { avoid: true, good_for: [] }, behenian: { order: '9', gem: '缟玛瑙', herb: '天仙子、聚合草、牛蒡', use: '驱逐恶灵与恶意;凶星慎用' } },
	{ name_cn: '贯索四', name_en: 'Alphecca', magnitude: 2.2, lon_1995: 222.23, declination: 26.71, nature: ['venus', 'mars'], meaning: '北冕之珠:荣誉尊严,尤利爱情友谊', election: { avoid: false, good_for: ['marriage'] }, behenian: { order: '12', gem: '黄玉', herb: '迷迭香、三叶草、常春藤', use: '为荣誉尊严,尤利爱情友谊' } },
	{ name_cn: '氐宿一', name_en: 'Zuben Elgenubi', magnitude: 2.7, lon_1995: 225.01, declination: -16.05, nature: ['saturn', 'mars'], meaning: '南秤盘·不足之价:损失、疾、恶意', election: { avoid: true, good_for: [] } },
	{ name_cn: '氐宿四', name_en: 'Zuben Eschamali', magnitude: 2.6, lon_1995: 229.30, declination: -9.38, nature: ['jupiter', 'mercury'], meaning: '北秤盘·足价:好运、野心、荣誉、久乐', election: { avoid: false, good_for: ['career', 'lawsuit'] } },
	{ name_cn: '南门二', name_en: 'Bungula', magnitude: -0.27, lon_1995: 239.15, declination: -60.83, nature: ['venus', 'jupiter'], meaning: '半人马之足(Toliman):精致、友谊、荣誉而复杂', election: { avoid: false, good_for: [] } },
	{ name_cn: '候星', name_en: 'Ras Alhague', magnitude: 2.1, lon_1995: 262.10, declination: 12.56, nature: ['saturn', 'venus'], meaning: '蛇夫之首:医与毒、乖戾、因女致祸', election: { avoid: true, good_for: [] } },
	{ name_cn: '尾宿九', name_en: 'Lesath', magnitude: 2.6, lon_1995: 263.63, declination: -37.30, nature: ['mercury', 'mars'], meaning: '天蝎之螫:危险、铤而走险、毒、意外', election: { avoid: true, good_for: [] } },
	{ name_cn: '水委一', name_en: 'Achernar', magnitude: 0.46, lon_1995: 344.96, declination: -57.24, nature: ['jupiter'], meaning: '波江之末:王者之荣、公职之成、信仰', election: { avoid: false, good_for: ['career'] } },
	{ name_cn: '摇光', name_en: 'Alkaid', magnitude: 1.86, lon_1995: 177.16, declination: 49.31, nature: ['mars'], meaning: '大熊之尾(Behenian 末位异本;性质诸本互异)', election: { avoid: false, good_for: [], conditional: '仅作护符位参考' }, behenian: { order: '8', use: 'Behenian 末位异本之一(与北落师门互见);宝石草药待核' } },
];

// 岁差修正：返回某年的黄经
export function starLonAt(lon1995, year){
	return ((lon1995 + (year - 1995) * PRECESSION_ARCSEC_PER_YEAR / 3600) % 360 + 360) % 360;
}

// 恒星容许度取档（只取合相铁律不变）：
//  'school'(默认零回归) = 按流派平轨 opts.fixedStarOrb（现行行为，缺省 1°）；
//  'byMagnitude'(Robson) = 1等 7°30′ / 2等 5°30′ / 3等 3°40′ / 4等及以下 1°30′；
//    王者之星(isRoyal)按传统实务封顶 5°。
export function starOrbFor(star, opts){
	opts = opts || {};
	const mode = opts.fixedStarOrbMode || 'school';
	if(mode === 'byMagnitude'){
		const m = (star && star.magnitude !== undefined) ? star.magnitude : 2.5;
		let orb;
		if(m <= 1.49) orb = 7.5;
		else if(m <= 2.49) orb = 5.5;
		else if(m <= 3.49) orb = 3 + 40 / 60;
		else orb = 1.5;
		if(star && star.isRoyal) orb = Math.min(orb, 5);
		return orb;
	}
	return (typeof opts.fixedStarOrb === 'number' && opts.fixedStarOrb > 0) ? opts.fixedStarOrb : 1;
}

export default FIXED_STARS;
