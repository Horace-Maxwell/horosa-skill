// divination/data/fixedStars.js
// 恒星表（择日清单 §2.6）。lon_1995 = 1995 回归黄经（绝对 0–360）；岁差 50.27″/年。
// 仅当恒星会合(≤1°,最多1.5°)命度/天顶/命主/用事星/日/月 时显示；关键点也要避开不利恒星。
// nature/meaning 与位置无关，长期可用。

export const PRECESSION_ARCSEC_PER_YEAR = 50.27;

export const FIXED_STARS = [
	// 主用 10 星（能平君常用集）
	{ name_cn: '大陵五', name_en: 'Algol', lon_1995: 56.17, declination: 40.95, nature: ['mars', 'saturn'], meaning: '困难/阻碍/失败/延迟/不幸', election: { avoid: true, good_for: [] } },
	{ name_cn: '昴宿六', name_en: 'Alcyone', lon_1995: 60.0, declination: 24.10, nature: ['moon', 'mars'], meaning: '同情/感伤/失望', election: { avoid: true, good_for: [] } },
	{ name_cn: '毕宿五', name_en: 'Aldebaran', lon_1995: 69.8, declination: 16.51, nature: ['mars'], meaning: '爆发/冲动/刑伤/精力/开创', election: { avoid: true, good_for: ['career'], conditional: '除非刻意取火星之力，否则避' } },
	{ name_cn: '轩辕十四', name_en: 'Regulus', lon_1995: 149.83, declination: 11.97, nature: ['mars', 'jupiter'], meaning: '荣耀/名声/权力/成功/骄傲', election: { avoid: false, good_for: ['career'], conditional: '利事业、不利婚姻' } },
	{ name_cn: '东次将', name_en: 'Vindemiatrix', lon_1995: 189.93, declination: 10.96, nature: ['saturn', 'mercury'], meaning: '困难/不幸/障碍/失望(寡居星)', election: { avoid: true, good_for: [] } },
	{ name_cn: '角宿一', name_en: 'Spica', lon_1995: 203.85, declination: -11.15, nature: ['venus', 'mars'], meaning: '成功/幸运/财富/繁荣', election: { avoid: false, good_for: ['career', 'marriage'] } },
	{ name_cn: '心宿二', name_en: 'Antares', lon_1995: 249.77, declination: -26.43, nature: ['mars', 'jupiter'], meaning: '暴力/冲突/自信/独断(皇室星)', election: { avoid: false, good_for: ['career'], conditional: '事业开创可用，婚姻勿用' } },
	{ name_cn: '织女星', name_en: 'Vega', lon_1995: 285.32, declination: 38.78, nature: ['venus', 'mercury'], meaning: '幸运/成功/财富/口才', election: { avoid: false, good_for: ['career', 'marriage'], conditional: '吉星会合可用，凶星会合避' } },
	{ name_cn: '北落师门', name_en: 'Fomalhaut', lon_1995: 333.87, declination: -29.62, nature: ['venus', 'mercury'], meaning: '改变/不定/适应/名声', election: { avoid: true, good_for: [], conditional: '不安定性强，最好不用' } },
	{ name_cn: '室宿二', name_en: 'Scheat', lon_1995: 359.37, declination: 28.08, nature: ['mars', 'mercury'], meaning: '困难/意外/失败/阻挠', election: { avoid: true, good_for: [] } },
	// 扩展星表（杨国正版，节选高频）
	{ name_cn: '壁宿二', name_en: 'Alpheratz', lon_1995: 14.30, declination: 29.08, nature: ['jupiter', 'venus'], meaning: '演艺/艺术名声·独立·声誉', election: { avoid: false, good_for: ['career'] } },
	{ name_cn: '奎宿九', name_en: 'Mirach', lon_1995: 30.40, declination: 35.60, nature: ['venus'], meaning: '顾家·由婚姻带来好运·美丽·才艺', election: { avoid: false, good_for: ['marriage'] } },
	{ name_cn: '娄宿三', name_en: 'Hamal', lon_1995: 37.67, declination: 23.45, nature: ['saturn', 'mars'], meaning: '暴力·残忍·犯罪·亦主治疗者', election: { avoid: true, good_for: [] } },
	{ name_cn: '五车二', name_en: 'Capella', lon_1995: 81.85, declination: 46.0, nature: ['mars', 'mercury'], meaning: '名誉·学习·好奇·物质成功', election: { avoid: false, good_for: ['career'] } },
	{ name_cn: '天狼星', name_en: 'Sirius', lon_1995: 104.08, declination: -16.70, nature: ['jupiter', 'mars'], meaning: '野心·热诚·财富·名誉(躔天顶主声誉卓著)', election: { avoid: false, good_for: ['career'] } },
	{ name_cn: '南河三', name_en: 'Procyon', lon_1995: 115.78, declination: 5.22, nature: ['mercury', 'mars'], meaning: '行动力·暴力·急躁·骤起骤落', election: { avoid: true, good_for: [] } },
	{ name_cn: '大角', name_en: 'Arcturus', lon_1995: 204.23, declination: 19.18, nature: ['jupiter', 'mars'], meaning: '进取·名誉·财富·因旅游获益·持久成功', election: { avoid: false, good_for: ['career'] } },
	{ name_cn: '河鼓二(牛郎)', name_en: 'Altair', lon_1995: 301.78, declination: 8.87, nature: ['jupiter', 'mars'], meaning: '突短运气·冲动·自信·野心；利法律/军事/占星', election: { avoid: false, good_for: ['career'] } },
	{ name_cn: '室宿一', name_en: 'Markab', lon_1995: 353.48, declination: 15.18, nature: ['mars', 'mercury'], meaning: '暴力·意外·手术·法律·名誉·心智', election: { avoid: true, good_for: [] } },
];

// 岁差修正：返回某年的黄经
export function starLonAt(lon1995, year){
	return ((lon1995 + (year - 1995) * PRECESSION_ARCSEC_PER_YEAR / 3600) % 360 + 360) % 360;
}

export default FIXED_STARS;
