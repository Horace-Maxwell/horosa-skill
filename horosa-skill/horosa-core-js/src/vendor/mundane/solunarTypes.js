// 恒星派世运八盘种(纯数据,无取数依赖:挂载设置表等处只要盘种清单时引这里,不必拉起求根模块)。
// 8 盘种:太阳/月亮 各入恒星 摩羯/白羊/巨蟹/天秤。approxMonthDay=迭代初值(恒星入境
// 比回归晚约 24–25 日,取古籍常值近似作种子;收敛由迭代保证,种子仅省步数)。
export const SOLUNAR_TYPES = [
	{ key: 'capsolar', cn: 'Capsolar（太阳入恒星摩羯）', body: 'sun', target: 270, approx: '01-14', span: '年主盘 · 强 12 个月(首季最强)', weightIdx: 0 },
	{ key: 'arisolar', cn: 'Arisolar（太阳入恒星白羊）', body: 'sun', target: 0, approx: '04-14', span: '其后约 3 个月(收束/定时器)', weightIdx: 1 },
	{ key: 'cansolar', cn: 'Cansolar（太阳入恒星巨蟹）', body: 'sun', target: 90, approx: '07-16', span: '次强(约 ¾ 力),前 3 个月', weightIdx: 2 },
	{ key: 'libsolar', cn: 'Libsolar（太阳入恒星天秤）', body: 'sun', target: 180, approx: '10-17', span: '其后约 3 个月(收束/定时器)', weightIdx: 3 },
	{ key: 'caplunar', cn: 'Caplunar（月入恒星摩羯）', body: 'moon', target: 270, approx: null, span: '月主盘 · 4 周(首周最强)', weightIdx: 0 },
	{ key: 'arilunar', cn: 'Arilunar（月入恒星白羊）', body: 'moon', target: 0, approx: null, span: '实务约 1 周', weightIdx: 1 },
	{ key: 'canlunar', cn: 'Canlunar（月入恒星巨蟹）', body: 'moon', target: 90, approx: null, span: '实务约 1 周', weightIdx: 2 },
	{ key: 'liblunar', cn: 'Liblunar（月入恒星天秤）', body: 'moon', target: 180, approx: null, span: '实务约 1 周', weightIdx: 3 },
];
