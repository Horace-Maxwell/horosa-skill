// divination/data/topicMaster.js
// 用事项目主表（择日清单 §2.9 索引）。引擎按用户选的 topic_id 加载规则包（§6 细则在 election/rulePacks.js）。
// 字段：natural_significators / key_houses(首为主) / preferred_asc_modality / moon_phase_pref(waxing|waning|any)
//       / must_avoid[] / must_have[] / special_aspect / notes

export const TOPIC_MASTER = {
	marriage: {
		topic_id: 'marriage', cn: '结婚/订婚', natural_significators: ['venus', 'moon'], key_houses: [7, 5],
		preferred_asc_modality: ['fixed', 'cardinal'],
		preferred_asc_signs: ['leo', 'aquarius', 'taurus', 'scorpio', 'libra', 'cancer', 'capricorn', 'aries'],
		moon_phase_pref: 'waxing',
		must_avoid: ['venus_retro', 'mercury_retro', 'moon_in_scorpio', 'moon_29deg', 'saturn_on_angle_1_7', 'uranus_on_angle_1_7', 'mars_in_1_or_7'],
		must_have: ['sun_moon_good_aspect', 'venus_moon_good_aspect', 'l1_l7_good_aspect', 'venus_in_1_or_7'],
		special_aspect: 'Moon conj/trine/sextile Venus',
		notes: '固定宫坐命象征长久；婚姻两造合盘 > 择日盘。',
	},
	business: {
		topic_id: 'business', cn: '创业/开业/开市', natural_significators: ['jupiter', 'venus', 'sun'], key_houses: [1, 2, 8, 10, 11],
		preferred_asc_modality: ['fixed'], preferred_asc_signs: ['taurus'], moon_phase_pref: 'waxing',
		must_avoid: ['mercury_retro_for_contract', 'malefic_on_angle', 'saturn_on_career_houses'],
		must_have: ['l10_strong', 'sun_in_career_house', 'venus_jupiter_aspect'],
		special_aspect: '2宫内星/金/2主与木 120°最佳',
		notes: '首次开业影响最强；先看主事者本命 10 宫主推运不可受剋；命宫尤 Taurus 第一。',
	},
	organization: { topic_id: 'organization', cn: '团体组织成立', natural_significators: ['mercury', 'jupiter'], key_houses: [11, 10], preferred_asc_modality: ['air'], moon_phase_pref: 'any', must_avoid: [], must_have: [], notes: '诉求沟通+服务，风象坐命更重要；火金木大三角于 3/7/11 利组织扩展。' },
	move_in: { topic_id: 'move_in', cn: '入宅/迁居', natural_significators: ['moon'], key_houses: [4], preferred_asc_modality: ['fixed'], moon_phase_pref: 'any', must_avoid: ['malefic_on_angle', 'uranus_on_angle'], must_have: ['l1_l4_good_aspect'], notes: '搬家入宅不受逆行影响（买屋才避金/水逆）；喜日月金木升地平上。' },
	completion: { topic_id: 'completion', cn: '落成', natural_significators: ['moon', 'venus'], key_houses: [4], preferred_asc_modality: ['fixed'], moon_phase_pref: 'any', must_avoid: [], must_have: [], notes: '住宅看月、商用看金。' },
	buy_property: { topic_id: 'buy_property', cn: '购屋/租屋', natural_significators: ['moon'], key_houses: [4, 2], preferred_asc_modality: ['fixed'], moon_phase_pref: 'waxing', must_avoid: ['mercury_retro_for_contract'], must_have: ['moon_l4_good_aspect'], notes: '月落 Cancer 最佳；月-4主吉相；避截夺宫。' },
	buy_land: { topic_id: 'buy_land', cn: '购地', natural_significators: ['saturn', 'moon'], key_houses: [4], preferred_asc_modality: ['fixed'], moon_phase_pref: 'waxing', must_avoid: ['saturn_in_12_property'], must_have: ['moon_saturn_trine'], notes: '加 Saturn+Capricorn；月-土 120°有利；配金看实质收入。' },
	renovation: { topic_id: 'renovation', cn: '整修/动土/破土', natural_significators: ['saturn'], key_houses: [4], preferred_asc_modality: [], moon_phase_pref: 'any', must_avoid: [], must_have: ['saturn_well_aspected'], notes: '重 4 宫+土星；破土尤重土星吉兆；避火/土所在座对沖方位动土。' },
	trade: { topic_id: 'trade', cn: '买卖交易', natural_significators: ['moon'], key_houses: [1, 7, 2, 4], preferred_asc_modality: ['fixed', 'cardinal'], moon_phase_pref: 'waxing', must_avoid: ['moon_voc', 'mercury_retro_for_contract'], must_have: ['moon_good_aspect'], notes: '1=买家7=卖家；买物偏固定宫，卖物偏本位宫；喜月在 Cancer/Taurus。' },
	buy_car: { topic_id: 'buy_car', cn: '购车(签约付订)', natural_significators: ['mercury'], key_houses: [1, 3, 2, 7], preferred_asc_modality: ['fixed'], moon_phase_pref: 'any', must_avoid: ['mars_retro', 'mercury_retro_for_contract', 'venus_retro_for_luxury'], must_have: ['moon_good_aspect_fixed'], notes: '1>7（买家强）；3宫(车)/2宫(车款)与1宫吉相；火逆勿购任何机械车辆。' },
	deliver_car: { topic_id: 'deliver_car', cn: '交车(驶离)', natural_significators: [], key_houses: [1, 3], preferred_asc_modality: [], moon_phase_pref: 'any', must_avoid: ['malefic_in_1_3_9'], must_have: ['moon_no_hard_aspect'], notes: '凶星不入 1(车/车主)/3(短途)/9(长途)；尤忌逢火(车祸)/土/天/海。' },
	contract: { topic_id: 'contract', cn: '签约/承诺', natural_significators: ['venus', 'mercury', 'jupiter'], key_houses: [7, 11, 3, 9], preferred_asc_modality: [], moon_phase_pref: 'any', must_avoid: ['mercury_retro_for_contract'], must_have: [], notes: '非法律突显金星+7/11宫；法律突显水星+木星+3/9宫；起盘=代表人签名时刻。' },
	registration: { topic_id: 'registration', cn: '登记', natural_significators: ['sun', 'mars', 'jupiter'], key_houses: [], preferred_asc_modality: ['fire'], moon_phase_pref: 'any', must_avoid: [], must_have: [], notes: '短期成效→火象坐命+太阳/火星/木星吉兆；政治参选尤突显太阳。' },
	application: { topic_id: 'application', cn: '申请', natural_significators: [], key_houses: [], preferred_asc_modality: [], moon_phase_pref: 'any', must_avoid: [], must_have: [], notes: '起盘=申请书寄出/送出时刻（常即组织/活动本命盘）；按目的宫位考量。' },
	diet: { topic_id: 'diet', cn: '节食/减肥', natural_significators: ['uranus', 'pluto'], key_houses: [6], preferred_asc_modality: [], moon_phase_pref: 'waning', must_avoid: ['moon_square', 'moon_voc'], must_have: ['uranus_pluto_good_aspect'], notes: '起盘=下定决心一刹那；强调月亏（精神深化）；可善用土星入始宫但必有充分吉相。' },
	quit_habit: { topic_id: 'quit_habit', cn: '戒烟/戒毒', natural_significators: ['uranus', 'pluto', 'neptune'], key_houses: [12], preferred_asc_modality: [], moon_phase_pref: 'waning', must_avoid: ['neptune_afflicted'], must_have: ['neptune_well_aspected'], notes: '与 12宫/Pisces/海王有关；强调海王吉兆、不被凶星刑剋；意志力作用有限。' },
	pursue_love: { topic_id: 'pursue_love', cn: '追求爱情', natural_significators: ['mars', 'mercury', 'venus'], key_houses: [5], preferred_asc_modality: ['fire', 'air'], moon_phase_pref: 'any', must_avoid: [], must_have: ['jupiter_in_5'], notes: '起盘=实际行动(打电话邀约)；速成→火/风象坐命+火/水吉相；木星务必落 5 宫。' },
	job_hunt: { topic_id: 'job_hunt', cn: '求职', natural_significators: ['mars', 'mercury'], key_houses: [6, 10], preferred_asc_modality: ['fire', 'air'], moon_phase_pref: 'any', must_avoid: [], must_have: ['jupiter_in_6'], notes: '起盘=查求职广告/实际行动；木星务必落 6 宫；金星为第二吉星。' },
	team_departure: { topic_id: 'team_departure', cn: '队伍出发/比赛', natural_significators: [], key_houses: [5, 11], preferred_asc_modality: ['cardinal'], moon_phase_pref: 'any', must_avoid: [], must_have: ['angular_benefic'], notes: '起盘=接旗/集合完成；比赛本位宫坐命(攻击力)；本地赛突显5宫,客场突显11宫。' },
	publishing: { topic_id: 'publishing', cn: '出版/节目开播', natural_significators: [], key_houses: [], preferred_asc_modality: [], moon_phase_pref: 'any', must_avoid: ['sun_in_12'], must_have: [], notes: '以个人魅力为重→结合本命盘；太阳勿落12宫；突显内容相关吉兆。' },
	medication: { topic_id: 'medication', cn: '用药', natural_significators: ['moon'], key_houses: [], preferred_asc_modality: [], moon_phase_pref: 'any', must_avoid: [], must_have: ['moon_in_disease_sign_well_aspected'], notes: '简单原则=月落主管该疾病的星座、月吉相越多越好。' },
	surgery: { topic_id: 'surgery', cn: '手术', natural_significators: ['mars'], key_houses: [8], preferred_asc_modality: [], moon_phase_pref: 'avoid_new_full', must_avoid: ['near_new_or_full_moon', 'moon_voc', 'mercury_retro', 'mars_retro', 'station_day', 'moon_in_surgery_part_sign', 'moon_in_scorpio', 'moon_mars_hard', 'asc_mars_hard'], must_have: ['mars_dignified', 'l8_well_aspected', 'asc_strong'], notes: '命度与月所落座=主管手术部位,吉相越多越好；火星入廟旺、避与土/天/海/冥凶相；美容手术避金逆。' },
	banquet: { topic_id: 'banquet', cn: '宴会/盛会', natural_significators: ['mercury', 'venus'], key_houses: [1, 3, 5, 7, 11], preferred_asc_modality: ['mutable'], moon_phase_pref: 'any', must_avoid: [], must_have: ['venus_mercury_dignified'], notes: '变动宫坐命；水星+金星吉兆落 1/3/5/7/11 入廟旺；多在晚上6–8点假日。' },
	inauguration: { topic_id: 'inauguration', cn: '就职典礼', natural_significators: ['sun'], key_houses: [1, 7, 10, 11], preferred_asc_modality: [], moon_phase_pref: 'any', must_avoid: [], must_have: [], notes: '依盛会法则；政治性突显太阳。注：示例一律用中性「就职典礼」，不写任何政治人物名。' },
	funeral: { topic_id: 'funeral', cn: '葬礼(活人)', natural_significators: [], key_houses: [], preferred_asc_modality: [], moon_phase_pref: 'any', must_avoid: [], must_have: [], notes: '通用法则；提示家属本命火/土与当天 Transits 刑剋者宜避免/缩短参与。' },
	bed_setting: { topic_id: 'bed_setting', cn: '安床', natural_significators: [], key_houses: [4, 12, 5], preferred_asc_modality: [], moon_phase_pref: 'any', must_avoid: [], must_have: [], notes: '通用+4宫(家庭)/12宫(睡眠)；新婚/求子加 5 宫。' },
	travel: { topic_id: 'travel', cn: '出行', natural_significators: ['mercury'], key_houses: [3, 9], preferred_asc_modality: [], moon_phase_pref: 'any', must_avoid: ['moon_in_6_or_12'], must_have: ['mercury_well_aspected'], notes: '3宫(短)/9宫(长)+水星吉化；月不可在1宫起算的6/12宫。' },
	blessing: { topic_id: 'blessing', cn: '祈福', natural_significators: ['jupiter', 'neptune'], key_houses: [9, 11], preferred_asc_modality: [], moon_phase_pref: 'any', must_avoid: [], must_have: [], notes: '9宫(宗教)/11宫(愿望)+木星/海王；按所求加对应宫。' },
	altar: { topic_id: 'altar', cn: '安香/安神位', natural_significators: ['jupiter'], key_houses: [9, 4, 8], preferred_asc_modality: [], moon_phase_pref: 'any', must_avoid: [], must_have: [], notes: '9/4/8 宫+木星。' },
	ritual: { topic_id: 'ritual', cn: '法会/建醮', natural_significators: ['jupiter', 'neptune'], key_houses: [9, 11, 10, 4], preferred_asc_modality: [], moon_phase_pref: 'any', must_avoid: [], must_have: [], notes: '9(宗教)/11(团体)/10(地方形象)/4(区域)+木星/海王。' },
	general_day: { topic_id: 'general_day', cn: '大众吉日(简)', natural_significators: [], key_houses: [], preferred_asc_modality: [], moon_phase_pref: 'any', must_avoid: [], must_have: [], notes: '小事，仅看月落星座（见 §6.17 月落十二座事务）。' },
};

export const TOPIC_LIST = Object.keys(TOPIC_MASTER);

export function topicInfo(id){ return TOPIC_MASTER[id] || null; }

export default TOPIC_MASTER;
