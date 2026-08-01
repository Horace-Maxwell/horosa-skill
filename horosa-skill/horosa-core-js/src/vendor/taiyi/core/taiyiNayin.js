// 太乙·六十甲子纳音(表C)。纯派生:据 pan.ganzhi 按盘式取主柱 → 六十甲子序 → 纳音五行。
// 纳音表为公有领域术数通则(《三命通会》等古籍通载);前端纯函数,零触碰后端立成表 golden。

const GAN = '甲乙丙丁戊己庚辛壬癸'.split('');
const ZHI = '子丑寅卯辰巳午未申酉戌亥'.split('');

// 六十甲子纳音(每 2 支一组共 30 组,序 = 甲子起 60 位)
const NAYIN60 = [
	'海中金', '海中金', '炉中火', '炉中火', '大林木', '大林木', '路旁土', '路旁土', '剑锋金', '剑锋金',
	'山头火', '山头火', '涧下水', '涧下水', '城头土', '城头土', '白蜡金', '白蜡金', '杨柳木', '杨柳木',
	'泉中水', '泉中水', '屋上土', '屋上土', '霹雳火', '霹雳火', '松柏木', '松柏木', '长流水', '长流水',
	'沙中金', '沙中金', '山下火', '山下火', '平地木', '平地木', '壁上土', '壁上土', '金箔金', '金箔金',
	'覆灯火', '覆灯火', '天河水', '天河水', '大驿土', '大驿土', '钗钏金', '钗钏金', '桑柘木', '桑柘木',
	'大溪水', '大溪水', '沙中土', '沙中土', '天上火', '天上火', '石榴木', '石榴木', '大海水', '大海水',
];

// 干支字符串 → 六十甲子序号(0–59);非法返 -1。gan 与 zhi 步进同频,合法干支必有唯一序。
export function jiaziIndexOf(ganzhi){
	const s = String(ganzhi || '');
	if(s.length < 2){ return -1; }
	const g = GAN.indexOf(s.charAt(0)), z = ZHI.indexOf(s.charAt(1));
	if(g < 0 || z < 0){ return -1; }
	for(let i = 0; i < 60; i++){ if(i % 10 === g && i % 12 === z){ return i; } }
	return -1;   // 干支阴阳不配(如甲丑)
}

// 干支 → 纳音五行名(如「甲子」→「海中金」);非法返 ''。
export function nayinOf(ganzhi){
	const i = jiaziIndexOf(ganzhi);
	return i >= 0 ? NAYIN60[i] : '';
}

// 纳音末字 → 五行(金木水火土),供着色/断法。
export function nayinElement(nayin){
	const c = String(nayin || '').slice(-1);
	return '金木水火土'.indexOf(c) >= 0 ? c : '';
}

// 盘式 → 取纳音的主柱(0年計→年 / 1月計→月 / 2日計→日 / 3時計→时 / 4分計→分(缺回时) / 5命法→本命年柱)。
function pillarKeyByStyle(style){
	const st = Number(style);
	if(st === 0 || st === 5){ return 'year'; }
	if(st === 1){ return 'month'; }
	if(st === 2){ return 'day'; }
	if(st === 4){ return 'minute'; }
	return 'time';   // 3 時計(默认)
}

// 据 pan 计算主柱纳音:{ pillar:'年/月/日/时/分', ganzhi, nayin, element }。缺主柱回退年柱。
export function computeTaiyiNayin(pan){
	if(!pan || !pan.ganzhi){ return null; }
	const gz = pan.ganzhi;
	const style = pan.options && pan.options.style !== undefined ? pan.options.style
		: (pan.style !== undefined ? pan.style : 3);
	const key = pillarKeyByStyle(style);
	const KEY_CN = { year: '年', month: '月', day: '日', time: '时', minute: '分' };
	let pillarKey = key, ganzhi = gz[key];
	if(!ganzhi){ pillarKey = 'year'; ganzhi = gz.year; }   // 主柱缺(如分柱空)→ 回退年柱
	const nayin = nayinOf(ganzhi);
	if(!nayin){ return null; }
	return { pillar: KEY_CN[pillarKey] || '年', ganzhi, nayin, element: nayinElement(nayin) };
}
