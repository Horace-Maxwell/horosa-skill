// 西方28宿(Lunar Mansions)。源:Agrippa《Three Books of Occult Philosophy》II.33 / Picatrix / al-Biruni(公开古籍)。
// 每宿 12°51′25.7″(=360/28),自白羊 0° 连续均分(Agrippa 锚,本仓默认)。
// 变体注:部分 Picatrix 抄本与现代作者将第 1 宿锚定实星 Sheratan 使边界整体偏移数度——
// 原典诸本无统一精确偏移方案,按反臆造纪律不做该选项;如需扩展须先补权威源值。
export const MANSION_SPAN = 360 / 28; // 12.857142…

// name:Agrippa 名(变体名并注);nature:性质;use:护符/择日用途摘要;good:吉性(true 吉/false 凶/null 中)
export const LUNAR_MANSIONS = [
	{ n: 1, name: 'Alnath', alt: 'Al Sharatain', nature: '不和、旅行', use: '旅行航行(吉);致不和、敌意', good: null },
	{ n: 2, name: 'Allothaim', alt: 'Al Botein', nature: '寻宝、留囚', use: '寻宝、扣留囚徒', good: null },
	{ n: 3, name: 'Achaomazon', alt: '昴 Pleiades', nature: '恩惠、炼金、狩猎、航海', use: '利水手/猎人/炼金术士;致好感善意;航行平安', good: true },
	{ n: 4, name: 'Aldebaran', alt: '毕宿五', nature: '毁灭、不和(凶)', use: '毁灭建筑/井泉/矿;播不和', good: false },
	{ n: 5, name: 'Alchatay', alt: 'Al Hakah', nature: '归来、恩惠、健康', use: '旅途归来;教化学者;健康善意;固建筑', good: true },
	{ n: 6, name: 'Alhanna', alt: "Al Han'ah", nature: '狩猎、围攻、复仇', use: '利狩猎/围城/复仇;毁收成;阻医者', good: false },
	{ n: 7, name: 'Aldimiach', alt: 'Al Dhira', nature: '收益、友谊、爱', use: '收益友谊;利恋人;利旅行', good: true },
	{ n: 8, name: 'Alnaza', alt: '鬼宿 Praesepe', nature: '爱、友谊、社交', use: '爱、友谊、旅伴情谊', good: true },
	{ n: 9, name: 'Archaam', alt: 'Al Tarf', nature: '疾病、阻碍(凶)', use: '阻收成与旅人;播不和;主毁灭与疾病', good: false },
	{ n: 10, name: 'Algelioche', alt: 'Al Jabhah', nature: '力量、爱、恩惠', use: '力量、恩惠、爱;收益善意;固建筑;促男女之爱', good: true },
	{ n: 11, name: 'Azobra', alt: 'Al Zubrah/Zosma', nature: '航行、收益、释放', use: '利航行、商利、赎囚', good: true },
	{ n: 12, name: 'Alzarpha', alt: 'Denebola', nature: '收成、阻水手', use: '利收成种植、善待仆役;但阻水手', good: null },
	{ n: 13, name: 'Alhaire', alt: 'Al Awwa', nature: '仁慈、收益、旅行', use: '仁慈、收益、航行、收成、释囚;最佳宿之一', good: true },
	{ n: 14, name: 'Achureth', alt: '角宿 Spica', nature: '婚姻、疗愈、爱', use: '为婚姻与夫妻之爱;愈病;仁慈;利旅人', good: true },
	{ n: 15, name: 'Agrapha', alt: 'Al Ghafr', nature: '掘取、害术、分离', use: '掘宝凿井;亦恶意:分离、离婚;阻旅行', good: false },
	{ n: 16, name: 'Azubene', alt: 'Al Zubana', nature: '阻碍(凶)', use: '阻旅行、婚姻、收成、贸易', good: false },
	{ n: 17, name: 'Alchil', alt: 'Al Iklil', nature: '爱、忠诚、加固', use: '增运、固建筑;为爱与友谊;护旅人;防贼', good: true },
	{ n: 18, name: 'Alchas', alt: '心宿 Antares', nature: '不和、复仇(凶)', use: '为密谋、不和、复仇、恶意;拆建筑', good: false },
	{ n: 19, name: 'Allatha', alt: 'Al Shaulah', nature: '围攻、囚禁、毁灭', use: '为围城、驱逐;缚;囚徒丧亡', good: false },
	{ n: 20, name: 'Abnahaya', alt: "Al Na'am", nature: '驯兽、狩猎、友谊', use: '为驯野兽、固监狱;和解伙伴', good: null },
	{ n: 21, name: 'Abeda', alt: 'Al Baldah', nature: '收成、收益、旅行', use: '为收成、收益、建筑、旅人;致繁荣;吉', good: true },
	{ n: 22, name: 'Sadahacha', alt: "Sa'd al Dhabih", nature: '逃离、疗愈、释放', use: '为仆役/囚徒逃离、愈病;治愈', good: true },
	{ n: 23, name: 'Zabadola', alt: "Sa'd Bula", nature: '离婚、自由、疗愈', use: '为离婚分离、囚徒自由、愈病', good: null },
	{ n: 24, name: 'Sadabath', alt: "Sa'd al Su'ud", nature: '夫妻之爱、胜利、善意', use: '为夫妻之爱与善意;士兵胜利;恩惠', good: true },
	{ n: 25, name: 'Sadalabra', alt: "Sa'd al Akhbiya", nature: '围攻、复仇、离婚(凶)', use: '为围攻复仇、毁敌、离婚;助解毒', good: false },
	{ n: 26, name: 'Alpharg', alt: 'Al Fargh al Mukdim', nature: '结合、健康、善意', use: '为结合与爱、囚徒健康、善意', good: true },
	{ n: 27, name: 'Alcharya', alt: 'Al Fargh al Thani', nature: '收益、利润、逃者归来', use: '增收成与贸易、收益;护旅人;水上平安', good: true },
	{ n: 28, name: 'Albotham', alt: 'Al Batn al Hut', nature: '婚姻、旅行、收成、好运', use: '为婚姻、旅行、收成、商利;极吉', good: true },
];

// 择日速查(Agrippa 传统分类):宿号集合
export const MANSION_ELECTION_SETS = {
	travel_good: [1, 5, 11, 13, 21, 28],   // 助旅行(最佳 13、28)
	travel_bad: [9, 15, 16],               // 阻旅行
	love: [7, 8, 10, 14, 17, 20, 24, 26, 28],  // 爱/婚姻/友谊
	destructive: [1, 4, 6, 9, 15, 16, 18, 19, 25], // 毁灭/不和/复仇/分离(凶,专此意或回避)
	gain: [2, 12, 13, 21, 22, 23, 27],     // 收益/收成/建筑/宝藏
	heal: [14, 22, 23],                    // 疗愈(自性质列派生)
};

// 用事 topic → 相关速查集(good=宜集,bad=忌集)
export const TOPIC_MANSION_MAP = {
	travel: { good: 'travel_good', bad: 'travel_bad' },
	team_departure: { good: 'travel_good', bad: 'travel_bad' },
	marriage: { good: 'love', bad: 'destructive' },
	pursue_love: { good: 'love', bad: 'destructive' },
	banquet: { good: 'love', bad: 'destructive' },
	business: { good: 'gain', bad: 'destructive' },
	trade: { good: 'gain', bad: 'destructive' },
	buy_property: { good: 'gain', bad: 'destructive' },
	buy_land: { good: 'gain', bad: 'destructive' },
	renovation: { good: 'gain', bad: 'destructive' },
	registration: { good: 'gain', bad: 'destructive' },
	contract: { good: 'gain', bad: 'destructive' },
	buy_car: { good: 'gain', bad: 'destructive' },
	surgery: { good: 'heal', bad: 'destructive' },
	diet: { good: 'heal', bad: 'destructive' },
	move_in: { good: 'gain', bad: 'destructive' },
	organization: { good: 'gain', bad: 'destructive' },
	blessing: { good: 'love', bad: 'destructive' },
	general_day: { good: null, bad: 'destructive' },
};

export function mansionOf(lon){
	const L = ((Number(lon) % 360) + 360) % 360;
	const idx = Math.min(27, Math.floor(L / MANSION_SPAN));
	return LUNAR_MANSIONS[idx];
}

export default LUNAR_MANSIONS;
