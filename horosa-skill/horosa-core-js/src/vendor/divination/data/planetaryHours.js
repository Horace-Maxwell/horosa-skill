// divination/data/planetaryHours.js
// 行星小时的象征意义（按起卦小时主星预判问题主题）。
// 来源：Sahl §13.18 / 补充清单 A.2（7×3 完整数据，直接录入）。每行星小时分三段。
export const PLANETARY_HOURS = {
	sun: ['国王/主人/大恐惧', '恐惧/病人', '生计/商业'],
	venus: ['妻子/女人烦恼', '女装/装饰', '新原因/未果友谊'],
	mercury: ['法律/财富/雕刻', '合身衣物/灵魂', '损失'],
	moon: ['搬家/病人/瑕疵物', '失去之物/路人/野兽/垂死者', '将完成之事/土中物'],
	saturn: ['逃奴', '强人/结社/旅行/请求', '逃脱的坏事'],
	jupiter: ['特定名字/公事', '合身衣物/治愈病人', '赚钱后亏损者'],
	mars: ['被盗红/金/铜/衣物', '病人/热伤', '欺骗/火中物'],
};

// 值日星（择日清单 §10.3 辅助）：周一月·周二火·周三水·周四木·周五金·周六土·周日日
export const DAY_RULERS = ['sun', 'moon', 'mars', 'mercury', 'jupiter', 'venus', 'saturn']; // 周日..周六

export function hourThemes(planetId){ return PLANETARY_HOURS[planetId] || null; }

export default PLANETARY_HOURS;
