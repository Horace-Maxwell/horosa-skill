// 三式合一快照·段单与段工具(单一真值源,零组件依赖)。
// 🔴 独立轻文件的原因:aiAnalysisContext(AI 核)与 SanShiUnitedMain(三式组件树)都要消费——
// AI 核直接 import 组件文件会把整棵三式组件树吃进自己的 chunk(46/47 回灌案),故抽此零依赖文件。
// live 页(buildSanShiUnitedSnapshotText)与挂载重算(regenerateSanshiUnifiedSnapshot)同源消费:
// 两条链的挑段/前缀规则由此保持同构,段名恒 ⊆ AI_EXPORT_PRESET_SECTIONS.sanshiunited(哨兵看死)。

// 太乙:复用独立 buildTaiyiSnapshotText 的动态派生段;段名加「太乙」前缀。
export const SANSHI_TAIYI_SECTION_TITLES = [
	'主客定算',
	'八门与宿曜',
	'断法',
	'七大兵法',
	'博弈',
	'命法',
	'命宫行限',
];
// 奇门:复用独立遁甲 buildDunJiaSnapshotText 的派生/法奇门段(段名加「奇门」前缀,避免与六壬「概览」等碰撞)。
export const SANSHI_QIMEN_EXTRA_SECTIONS = [
	'九宫方盘',
	'旺相休囚死·月令能量',
	'六害总览',
	'化解方案',
	'八门化气大阵',
	'用神分论',
	'财富七要',
	'事业七要',
	'恋爱姻缘',
	'孤辰寡宿',
];
// 六壬:复用独立大六壬 buildLiuRengSnapshotText 的断卦层段(前缀留空:段名与三式合一既有段不碰)。
export const SANSHI_LIURENG_DUANGUA_SECTIONS = [
	'十二盘式',
	'常用神煞',
	'年月神煞',
	'课体结构',
	'三传旺衰',
	'空亡真假',
	'旬空落点',
	'陷空',
	'遁干特殊',
	'年命上神',
	'毕法（已命中）',
	'占断向导',
	// [Q-451/T-414] 独立六壬快照有 [七政] 段、三式合一页也有「七政」页签,此前挑段单漏它 → 段被丢(preset 同步补名)
	'七政',
];

// 把「[段头]\n正文…」全文解析为 {段名: 正文行数组}(段外前导行丢弃;段尾空行剥净)。
export function parseSnapshotSections(text){
	const map = {};
	let current = null;
	`${text || ''}`.split('\n').forEach((rawLine)=>{
		const line = `${rawLine || ''}`;
		const m = line.trim().match(/^\[(.+)\]$/);
		if(m && m[1]){
			current = m[1];
			if(!map[current]){
				map[current] = [];
			}
			return;
		}
		if(current){
			map[current].push(line);
		}
	});
	Object.keys(map).forEach((key)=>{
		const arr = map[key];
		while(arr.length && arr[arr.length - 1] === ''){
			arr.pop();
		}
	});
	return map;
}
