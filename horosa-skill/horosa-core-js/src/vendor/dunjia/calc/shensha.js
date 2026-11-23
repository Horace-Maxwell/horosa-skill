// 奇门神煞与金函日家盘
// 从 DunJiaCalc.js 按职责拆出(门面保留原导入路径与对外导出;读源码的检查读「子模块 + 门面」全集,见 scripts/source-sets.json)。
import * as LRConst from '../../liureng/LRConst.js';
import { JINHAN_TABLE, JINHAN_STAR_JI, JINHAN_DIRS, JINHAN_DOOR_JI } from '../jinhanRiJia.js';
import { leapPrefix } from '../../utils/lunarText.js';
import { jianChuRing } from '../../utils/jianChu.js';
import { QIMEN_GUIREN_DAY_NIGHT, QIMEN_SHENSHA_DAY_STEMS, QIMEN_SHENSHA_MONTH_BRANCH, QIMEN_SHENSHA_DAY_BRANCH, QIMEN_SHENSHA_YEAR_BRANCH, PALACE_GRID, PALACE_NAME } from './tables.js';
import { getGanzhiGan, getGanzhiZhi, parseDateTime, resolveCurrentJieqi, isYangDunJieqi, getOptionLabel } from './basics.js';
import { buildGanzhiForQimen } from './pan.js';
import { dayJiaHalfYear } from './juMeta.js';
import { JINHAN_MENPAI_OPTIONS } from './options.js';

export function joinList(list){
	if(!list || !list.length){
		return '无';
	}
	return list.join('、');
}

function getQimenShenShaValue(mapObj, name, key){
	if(!mapObj || !name || !key){
		return '';
	}
	const list = mapObj[name] && mapObj[name][key] ? mapObj[name][key] : [];
	return list.join('');
}

function resolveQimenGuiRen(dayGan, isDiurnal){
	const dayGui = LRConst.DayGuiDunJia[dayGan] || (QIMEN_GUIREN_DAY_NIGHT[dayGan] ? QIMEN_GUIREN_DAY_NIGHT[dayGan][0] : '');
	const nightGui = LRConst.NightGuiDunJia[dayGan] || (QIMEN_GUIREN_DAY_NIGHT[dayGan] ? QIMEN_GUIREN_DAY_NIGHT[dayGan][1] : '');
	if(!dayGui || !nightGui){
		return {
			dayGui,
			nightGui,
			trueGuiRen: '',
			muGuiRen: '',
			isDiurnal: null,
		};
	}
	const isDaytime = isDiurnal === true;
	const isNight = isDiurnal === false;
	const trueGuiRen = isDaytime ? dayGui : (isNight ? nightGui : '');
	const muGuiRen = isDaytime ? nightGui : (isNight ? dayGui : '');
	return {
		dayGui,
		nightGui,
		trueGuiRen,
		muGuiRen,
		isDiurnal,
	};
}

export function buildQimenShenSha(ganzhi, isDiurnal){
	const dayGan = getGanzhiGan(ganzhi && ganzhi.day ? ganzhi.day : '');
	const dayZhi = getGanzhiZhi(ganzhi && ganzhi.day ? ganzhi.day : '');
	const monthZhi = getGanzhiZhi(ganzhi && ganzhi.month ? ganzhi.month : '');
	const yearZhi = getGanzhiZhi(ganzhi && ganzhi.year ? ganzhi.year : '');
	const timeZhi = getGanzhiZhi(ganzhi && ganzhi.time ? ganzhi.time : '');
	const guiren = resolveQimenGuiRen(dayGan, isDiurnal);
	const byName = {};

	const defs = [
		{ group: '日干', name: '日禄', map: QIMEN_SHENSHA_DAY_STEMS, key: dayGan },
		{ group: '日干', name: '日德', map: QIMEN_SHENSHA_DAY_STEMS, key: dayGan },
		{ group: '月支', name: '天马', map: QIMEN_SHENSHA_MONTH_BRANCH, key: monthZhi },
		{ group: '日支', name: '日马', map: QIMEN_SHENSHA_DAY_BRANCH, key: dayZhi },
		{ group: '年支', name: '年马', map: QIMEN_SHENSHA_YEAR_BRANCH, key: yearZhi },
		{ group: '日支', name: '桃花', map: QIMEN_SHENSHA_DAY_BRANCH, key: dayZhi },
		{ group: '日支', name: '破碎', map: QIMEN_SHENSHA_DAY_BRANCH, key: dayZhi },
		{ group: '月支', name: '生气', map: QIMEN_SHENSHA_MONTH_BRANCH, key: monthZhi },
		{ group: '月支', name: '死气', map: QIMEN_SHENSHA_MONTH_BRANCH, key: monthZhi },
		{ group: '年支', name: '病符', map: QIMEN_SHENSHA_YEAR_BRANCH, key: yearZhi },
		{ group: '月支', name: '血支', map: QIMEN_SHENSHA_MONTH_BRANCH, key: monthZhi },
		{ group: '年支', name: '孤辰', map: QIMEN_SHENSHA_YEAR_BRANCH, key: yearZhi },
		{ group: '年支', name: '寡宿', map: QIMEN_SHENSHA_YEAR_BRANCH, key: yearZhi },
		{ group: '年支', name: '丧门', map: QIMEN_SHENSHA_YEAR_BRANCH, key: yearZhi },
		{ group: '年支', name: '吊客', map: QIMEN_SHENSHA_YEAR_BRANCH, key: yearZhi },
		{ group: '月支', name: '成神', map: QIMEN_SHENSHA_MONTH_BRANCH, key: monthZhi },
		{ group: '月支', name: '会神', map: QIMEN_SHENSHA_MONTH_BRANCH, key: monthZhi },
		{ group: '月支', name: '解神', map: QIMEN_SHENSHA_MONTH_BRANCH, key: monthZhi },
		{ group: '月支', name: '天目', map: QIMEN_SHENSHA_MONTH_BRANCH, key: monthZhi },
		{ group: '月支', name: '医星', map: QIMEN_SHENSHA_MONTH_BRANCH, key: monthZhi },
		{ group: '月支', name: '月厌', map: QIMEN_SHENSHA_MONTH_BRANCH, key: monthZhi },
		{ group: '月支', name: '月破', map: QIMEN_SHENSHA_MONTH_BRANCH, key: monthZhi },
		{ group: '月支', name: '贼神', map: QIMEN_SHENSHA_MONTH_BRANCH, key: monthZhi },
		{ group: '日干', name: '贵人', value: guiren.trueGuiRen },
		{ group: '日干', name: '游都', map: QIMEN_SHENSHA_DAY_STEMS, key: dayGan },
		{ group: '日干', name: '文昌', map: QIMEN_SHENSHA_DAY_STEMS, key: dayGan },
		{ group: '月支', name: '丧车', map: QIMEN_SHENSHA_MONTH_BRANCH, key: monthZhi },
		{ group: '日干', name: '幕贵', value: guiren.muGuiRen },
	];

	const allItems = defs.map((item)=>{
		const value = (item.value !== undefined ? item.value : getQimenShenShaValue(item.map, item.name, item.key)) || '—';
		const one = { group: item.group, name: item.name, value };
		byName[item.name] = one;
		return one;
	});

	const groups = ['日干', '日支', '月支', '年支'].map((group)=>({
		group,
		items: allItems.filter((item)=>item.group === group),
	}));

	const summaryNames = ['日禄', '日德', '天马', '日马', '年马'];
	const summary = summaryNames
		.map((name)=>byName[name])
		.filter((item)=>!!item);

	return {
		summary,
		groups,
		allItems,
		refs: {
			dayGan,
			dayZhi,
			monthZhi,
			yearZhi,
			timeZhi,
			dayGui: guiren.dayGui,
			nightGui: guiren.nightGui,
			isDiurnal: guiren.isDiurnal,
		},
	};
}

// 日家·古籍金函系独立盘:不走局法/三盘,直接查六十干支占方全表。
//   阴阳盘=冬至后阳/夏至后阴(与日家同源 half-year 判定,书文「冬至节始为阳/夏至节始为阴」);
//   八方星门按表列序(北东北东东南南西南西西北)落到九宫格;中宫=本干支之星;吉凶着色按书定分类。
const JINHAN_DIR_TO_POS = { 北: 8, 东北: 7, 东: 4, 东南: 1, 南: 2, 西南: 3, 西: 6, 西北: 9 };

export function buildJinhanRiJiaPan(fields, nongli, opts, context){
	const dateParts = parseDateTime(fields);
	if(!dateParts){ return null; }
	// 🔴 四柱必须走 buildGanzhiForQimen 同源(年界档/晚子时/字段别名兜底全语义)——
	// 曾手写简版只读 nongli.yearGanZi,后端农历字段别名下年柱空(用户实机抓)。
	const ganzhi = buildGanzhiForQimen(nongli || {}, dateParts, opts || {}, context || {});
	const dayGz = ganzhi.day;
	const rec = JINHAN_TABLE[dayGz];
	if(!rec){ return null; }
	const jieqi = resolveCurrentJieqi(nongli || {}, dateParts, context || {}, fields && fields.zone ? fields.zone.value : undefined);
	const seeds = context && context.jieqiYearSeeds ? context.jieqiYearSeeds : null;
	const half = dayJiaHalfYear(seeds, dateParts);
	const yang = half ? half.yang : isYangDunJieqi(jieqi);
	const doorsBook = yang ? rec.yangDoors : rec.yinDoors;
	const stars = yang ? rec.yangStars : rec.yinStars;
	const menPai = (opts && opts.jinhanMenPai) === 'shun' ? 'shun' : 'book';
	const doors = menPai === 'shun' ? '休生伤杜景死惊开'.split('') : doorsBook;
	const daJi = yang ? rec.daJiYang : rec.daJiYin;
	const daJiNote = yang ? (rec.daJiYangNote || '') : (rec.daJiYinNote || '');
	const cells = PALACE_GRID.map((palaceNum)=>{
		if(palaceNum === 5){
			return {
				palaceNum, palaceName: '中', isCenter: true,
				diGan: '', tianGan: '', god: '',
				door: '', tianXing: rec.center,
				jinhanStarJi: JINHAN_STAR_JI[rec.center] || '',
				jinhanDoorJi: '',
				isJinhan: true,
			};
		}
		const dirIdx = JINHAN_DIRS.findIndex((d)=>JINHAN_DIR_TO_POS[d] === palaceNum);
		const dir = JINHAN_DIRS[dirIdx];
		const door = doors[dirIdx] || '';
		const star = stars[dirIdx] || '';
		return {
			palaceNum, palaceName: PALACE_NAME[palaceNum] || '', isCenter: false,
			diGan: '', tianGan: '', god: '',
			door, tianXing: star,
			jinhanDir: dir,
			jinhanDoorJi: JINHAN_DOOR_JI[door] || '',
			jinhanStarJi: JINHAN_STAR_JI[star] || '',
			isXiShen: rec.xiShen === dir,
			isDaJi: (daJi || []).indexOf(dir) >= 0,
			isJinhan: true,
		};
	});
	return {
		isJinhan: true,
		dateStr: dateParts.dateStr,
		timeStr: dateParts.timeStr,
		lunarText: nongli ? `${nongli.year || ''}年${leapPrefix(nongli)}${nongli.month || ''}${nongli.day || ''}` : '',
		ganzhi,
		cells,
		...(opts && opts.showJianChu ? { jianChu: jianChuRing(ganzhi, dateParts.dateStr) } : {}),   // 十二建星外环(与常规盘同一份)
		juText: `古籍日家·${yang ? '阳盘' : '阴盘'}`,
		jinhan: {
			dayGz,
			pantype: yang ? '阳' : '阴',
			menPai,
			center: rec.center,
			xiShen: rec.xiShen,
			jiShi: rec.jiShi,
			daJiFang: (daJi || []).join('、') + (daJiNote ? `（${daJiNote}）` : ''),
			shiText: rec.shiText,
		},
		options: {
			paiPanType: 6,
			paiPanLabel: '日家·古籍金函系',
			jinhanMenPai: menPai,
			jinhanMenPaiLabel: getOptionLabel(JINHAN_MENPAI_OPTIONS, menPai),
		},
	};
}
