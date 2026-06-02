// divination/data/castMoments.js
// 起盘时刻主表（择日清单 §8）：选定 topic 后告诉用户「哪一刻 = 这张盘」，据此确定 datetime。
export const CAST_MOMENTS = {
	marriage: '戴戒指 + 互相宣示成为夫妻（西式/公证，误差<10分钟）；中式：迎娶入门 / 宴客放鞭炮（最迟不晚于宴客之中）。',
	business: '实体店=开始营业；办公企业=公司创立时刻；大型=剪彩+放鞭炮；以「第一人进入场所」为准。',
	organization: '对外正式公开，或申请表寄出。',
	move_in: '第一件私人物品搬进（尽量白天）；中式可用主卧床位安置时刻。',
	completion: '落成典礼 + 开始正式使用。',
	buy_property: '开始查报纸广告/打电话/具体行动的时刻；签约=代表人签名时刻。',
	buy_land: '签约付款 / 破土开始挖土的时刻。',
	renovation: '开始敲打/动工；破土=开始挖土。',
	trade: '成交/交付时刻；签约=签名时刻。',
	buy_car: '签约付订金的时刻。',
	deliver_car: '启动车子驶离的瞬间（=该车次级本命盘）。',
	contract: '代表人签名的时刻。',
	registration: '完成并送出登记的时刻。',
	application: '申请书寄出/当面送出的时刻（常即组织/活动本命盘）。',
	diet: '对自己下定决心的那一刹那（自我期许，无需仪式）。',
	quit_habit: '对自己下定决心戒断的那一刹那。',
	pursue_love: '实际行动：打电话邀约。',
	job_hunt: '实际行动：查阅/投递求职广告。',
	team_departure: '接旗时刻（有授旗）；或集合完成即将出发。',
	publishing: '书籍装订完成 / 正式申请该节目。',
	medication: '服药时刻。',
	surgery: '第一刀（开始动刀）。难点：需医师配合。',
	banquet: '宴会正式开始（中式可以放鞭炮为基准）。',
	inauguration: '典礼正式开始。',
	funeral: '葬礼正式举行时刻。',
	bed_setting: '床位安置完成。',
	travel: '双脚踏上交通工具 / 正式出发的瞬间。',
	blessing: '正式祈福/上香的时刻。',
	altar: '安神位/安香完成的时刻。',
	ritual: '法会/建醮正式开始的时刻。',
	general_day: '当日主要活动开始的时刻。',
};

export function castMoment(topicId){ return CAST_MOMENTS[topicId] || '该用事最具象征意义的初始动作的时刻。'; }

export default CAST_MOMENTS;
