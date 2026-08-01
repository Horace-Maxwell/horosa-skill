// 通书择日多流派注册表 + 设置默认/持久（模型照 gua/liuyaoSchools）。
// needs 声明各法所需参数，控件按需显隐：event=用事、zuoShan=坐山向、mingYear=主事仙命年。
export const TONGSHU_SCHOOLS = [
	{ key: 'donggong', label: '董公择日', needs: { event: true }, note: '金神七煞·煞贡直星人专·十二月建除逐日宜忌断语' },
	{ key: 'qimen', label: '奇门叠数（裴晋公·唐）', needs: {}, note: '天干地支配数叠加 13~27 吉凶，出行择时' },
	{ key: 'sanyuanliexiu', label: '三垣列宿加临（古法）', needs: { liexiuUse: true }, note: '十六吉曜节气加临·建宅安葬修造造命断语（约略版·精确须星历）' },
	{ key: 'wutu', label: '天元乌兔', needs: {}, note: '玉函天星诀九星飞星·太阳值日上吉·太阴值日次吉' },
	{ key: 'sanyuan', label: '三元玄空大卦', needs: { mingYear: true }, note: '六十甲子配六十四卦·五吉·日课吉凶·天人配合（坐向须天圆图）' },
];

export const TONGSHU_SCHOOL_MAP = (()=>{
	const m = {};
	TONGSHU_SCHOOLS.forEach((s)=>{ m[s.key] = s; });
	return m;
})();

// 三垣列宿断语四大用事类（对应曜条 建宅/安葬/修造/造命 字段），十六曜据此高亮。
export const LIEXIU_USE_OPTIONS = [
	{ value: '建宅', label: '建宅·营造' },
	{ value: '修造', label: '修造·安门灶' },
	{ value: '安葬', label: '安葬·丧事' },
	{ value: '造命', label: '造命·择时立命' },
];

// 用事默认（董公/三垣断语高亮用）；坐山（24 山）；仙命年（玄空用，干支年）。
export const DEFAULT_TONGSHU_SETTINGS = {
	school: 'donggong',
	event: '嫁娶',
	liexiuUse: '建宅',     // 三垣列宿用事类（断语高亮）
	zuoShan: '子',
	mingYear: '甲子',
	date: null,          // 'YYYY-MM-DD'（null=今日，由 Main 填当天）
};

export function getTongshuOptionsKey(s) {
	return [s.school, s.event, s.liexiuUse, s.zuoShan, s.mingYear, s.date].join('|');
}

export function schoolNeeds(schoolKey) {
	return (TONGSHU_SCHOOL_MAP[schoolKey] || {}).needs || {};
}
