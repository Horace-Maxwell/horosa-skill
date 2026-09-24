// 紫微快照主 builder —— 自上游 components/ziwei/ZiWeiMain.js **逐字**抽出（bespoke，derived_from 由
// contracts/vendor_manifest.json 的 derived_sha256 看守：上游 ZiWeiMain.js 一动即红，复核本文件后 --restamp）。
// 与 ziweiSnapshotLayers.js（运限概览/运限/流派叠层，同源同文件）互补，这里是其余部分：
//   · normalizeGan / pickYearGan / collectHouseStars / formatStarSiHua / getLifeHouse（ZiWeiMain.js:55-169）
//   · buildZiWeiSnapshotText —— 整份紫微 AI 快照（ZiWeiMain.js:407-614；[起盘信息] 的四化流派/传本设置行、
//     [宫位总览] GFM 表的星曜四化括注与庙旺档都在这里）
// 函数体逐字未改；只有下方 import 按 vendor 树改了路径（上游是 ../../constants/xxx、./ZWLuckPanel 等）。
// ⚠ 读可变单例 ZWEngineOptions（传本/流派开关）与 ZWConst.ZWSchool（四化流派）：调用方负责按调用覆盖/还原
//   （上游 buildZiweiSnapshotForParams 同式，见 tools/ziweiBirth.js）。
import * as ZiWeiHelper from './ZiWeiHelper.js';
import * as ZWText from '../constants/ZWText.js';
import * as ZWConst from '../bazi/ZWConst.js';
import { isLaiyinPalace } from './ziweiSchools.js';
import { ZWEngineOptions } from './ziweiOptions.js';
import { starLightOf } from './data/ziweiTables.js';
import {
	buildZiweiPeriodOverviewLines,
	buildZiweiPeriodLines,
	buildZiweiOverlayLines,
} from './ziweiSnapshotLayers.js';

function normalizeGan(value){
	if(!value){
		return '';
	}
	return `${value}`.trim().charAt(0);
}

function pickYearGan(chart){
	if(!chart){
		return '';
	}
	if(chart.yearGan){
		return normalizeGan(chart.yearGan);
	}
	if(chart.nongli && chart.nongli.yearGanZi){
		return normalizeGan(chart.nongli.yearGanZi);
	}
	if(chart.nongli && chart.nongli.year){
		return normalizeGan(chart.nongli.year);
	}
	return '';
}

function collectHouseStars(house){
	const groups = [
		'starsMain',
		'starsAssist',
		'starsEvil',
		'starsOthersGood',
		'starsOthersBad',
		'starsSmall',
		'stars',
	];
	const out = [];
	const seen = new Set();
	// 星曜亮度传导:星名→庙旺档(盘数据基础值+非默认亮度源经 starLightOf 覆盖,与渲染层
	// effStarLight 同口径)。字符串星(旧夹具/降级形状)无亮度=不出档,快照照旧(零回归)。
	const lightOf = {};
	const houseZhi = (((house && house.ganzi) || '') + '').charAt(1);
	groups.forEach((key)=>{
		const arr = house && house[key] ? house[key] : [];
		arr.forEach((item)=>{
			let name = '';
			if(typeof item === 'string'){
				name = item;
			}else{
				name = item && (item.name || item.id) ? (item.name || item.id) : '';
			}
			name = `${name || ''}`.trim();
			if(!name || seen.has(name)){
				return;
			}
			seen.add(name);
			out.push(name);
			let sl = (item && typeof item === 'object' && item.starlight) ? `${item.starlight}` : '';
			const src = ZWEngineOptions.brightnessSource;
			if(src && src !== 'zi_jian' && houseZhi){
				const base = name.charAt(0) === '副' ? name.slice(1) : name;
				const v = starLightOf(base, houseZhi, src);
				if(v != null){ sl = v; }
			}
			if(sl){ lightOf[name] = sl; }
		});
	});
	return { list: out, lightOf };
}

// [Q-432/T-395①] dayGan:显示开关「日干四化徽」(缺省关)开启后盘面逐星加「日禄/日权…」徽,
// 而快照星曜括注只有 生年/命宫/自化 三类 → 开了也进不了 AI。开关开启时才传入,缺省态括注逐字不变。
function formatStarSiHua(starName, yearGan, lifeGan, palaceGan, dayGan){
	const tags = [];
	if(yearGan){
		const yearHua = ZiWeiHelper.getSiHua(starName, yearGan);
		if(yearHua){
			tags.push(`生年${yearHua}`);
		}
	}
	if(lifeGan){
		const lifeHua = ZiWeiHelper.getSiHua(starName, lifeGan);
		if(lifeHua){
			tags.push(`命宫${lifeHua}`);
		}
	}
	// 宫干自化（飞星紫微核心，Mac issue #11：用户反馈挂载缺自化信息）：星曜被「所落宫位本身天干」
	// 引动的四化。用所落宫干复算，getSiHua 自动按当前流派四化表取值（与生年/命宫四化同口径）。
	if(palaceGan){
		const selfHua = ZiWeiHelper.getSiHua(starName, palaceGan);
		if(selfHua){
			tags.push(`自化${selfHua}`);
		}
	}
	if(dayGan){
		const dayHua = ZiWeiHelper.getSiHua(starName, dayGan);
		if(dayHua){
			tags.push(`日干${dayHua}`);
		}
	}
	if(tags.length === 0){
		return starName;
	}
	return `${starName}（${tags.join('，')}）`;
}

function getLifeHouse(chart, houses){
	if(!chart || !houses || houses.length === 0){
		return null;
	}
	if(chart.lifeHouseIndex !== undefined && chart.lifeHouseIndex !== null){
		const idx = Number(chart.lifeHouseIndex);
		if(!Number.isNaN(idx) && houses[idx]){
			return houses[idx];
		}
	}
	return houses.find((house)=>`${house.name || ''}`.includes('命')) || null;
}

function buildZiWeiSnapshotText(params, result){
	const chart = result && result.chart ? result.chart : {};
	const houses = chart.houses || [];
	const yearGan = pickYearGan(chart);
	const lifeHouse = getLifeHouse(chart, houses);
	const lifeGan = lifeHouse && lifeHouse.ganzi ? normalizeGan(lifeHouse.ganzi) : '';
	const lines = [];

	lines.push('[起盘信息]');
	lines.push(`日期：${params.date} ${params.time}`);
	lines.push(`时区：${params.zone}`);
	lines.push(`经纬度：${params.lon} ${params.lat}`);
	// [Q-193/T-139] 「未知」在紫微是按男排(引擎 male = gender !== 0):快照只写「未知」会与下一行「命局：阳男」自相矛盾。
	lines.push(`性别：${`${params.gender}` === '1' ? '男' : (`${params.gender}` === '0' ? '女' : '未知（按男排）')}`);
	lines.push(`时间算法：${params.timeAlg === 1 ? '直接时间' : '真太阳时'}`);
	// 换算后时刻(审计补缺:此前只写算法名、无换算结果):双时刻并列与八字快照同款,换算关系一眼可见;
	// 后端盘缺 clockTime/solarTime 双字段时回落单行 nongli.birth(盘心 ZWCenterHouse 同款取数),全缺不产行。
	const tmNl = chart.nongli || {};
	if(tmNl.clockTime && tmNl.solarTime){
		lines.push(`直接时间：${tmNl.clockTime}　真太阳时：${tmNl.solarTime}`);
	}else if(tmNl.birth){
		lines.push(`${params.timeAlg === 1 ? '直接时间：' : '真太阳时：'}${tmNl.birth}`);
	}
	const schoolLabel = { beipai: '通用·飞星', zhongzhou: '中州派', quanshu: '全书系', beixiang: '北派(天相忌)', custom: '自定义' }[ZWConst.ZWSchool.school] || '通用·飞星';
	lines.push(`四化流派：${schoolLabel}`);
	// 传本/排盘开关(非默认才注记,供 AI 知悉本盘用了哪套传本)。
	const tbNotes = [];
	if(ZWEngineOptions.daxianSpan !== 10){ tbNotes.push('大限跨度=局数年(钦天)'); }
	if(ZWEngineOptions.tianmaBasis !== 'month'){ tbNotes.push('天马=年支三合马'); }
	if(ZWEngineOptions.starSet !== 'full'){ tbNotes.push('星集=精简18星(河洛)'); }
	if(ZWEngineOptions.sanPan && ZWEngineOptions.sanPan !== 'tian'){ tbNotes.push(`观察盘=${ZWEngineOptions.sanPan === 'di' ? '地盘(身宫起)' : '人盘(福德起)'}`); }
	if(ZWEngineOptions.shangShi === 'yinyang'){ tbNotes.push('天伤天使=阴阳互换(中州)'); }
	const leapLabel = { next: '整月归下月', prev: '整月归上月', split_days: '前后半分割(按实际天数取中点)', split_star_month: '命身下月·月系上月(存疑)', solar_term: '按节气分界(过节归下月)' };
	if(ZWEngineOptions.leapMonth && ZWEngineOptions.leapMonth !== 'mid_split'){ tbNotes.push(`闰月=${leapLabel[ZWEngineOptions.leapMonth] || ZWEngineOptions.leapMonth}`); }
	const lateZiLabel = { zi_chu: '子初换日(强制)', midnight_split: '夜子折中', zi_zheng: '子正换日', dual: '双盘(当日/次日)' };
	if(ZWEngineOptions.lateZi && ZWEngineOptions.lateZi !== 'global'){ tbNotes.push(`晚子时=${lateZiLabel[ZWEngineOptions.lateZi] || ZWEngineOptions.lateZi}`); }
	if(ZWEngineOptions.yearBoundary === 'lichun'){ tbNotes.push('定年界线=立春(八字口径)'); }
	if(ZWEngineOptions.huoling === 'nanpai'){ tbNotes.push('火铃=南派(忽略生时)'); }
	if(ZWEngineOptions.kongNaming === 'book'){ tbNotes.push('空劫=天空/地劫(古本)'); }
	if(ZWEngineOptions.lifeMasterBy === 'ming_branch'){ tbNotes.push('命主取法=命宫支(经典法)'); }
	if(ZWEngineOptions.changshengStart === 'huo_tu'){ tbNotes.push('长生十二神=火土同宫(土五起寅)'); }
	if(ZWEngineOptions.changshengDirection === 'always_forward'){ tbNotes.push('长生十二神=一律顺行(不分阴阳)'); }
	if(ZWEngineOptions.kongwangStyle === 'single'){ tbNotes.push('截空旬空=只安正空(单星)'); }
	const kuiYueLabel = { geng_ma_hu: '庚辛逢马虎(庚年魁午钺寅)', liu_xin_hu_ma: '六辛逢虎马(辛年魁寅钺午)', geng_xin_hu_ma: '庚辛逢虎马(庚辛年魁寅钺午)' };
	if(ZWEngineOptions.kuiYue && ZWEngineOptions.kuiYue !== 'jia_wu_geng'){ tbNotes.push(`魁钺歌诀=${kuiYueLabel[ZWEngineOptions.kuiYue] || ZWEngineOptions.kuiYue}`); }
	if(ZWEngineOptions.liuYueBasis === 'taisui'){ tbNotes.push('流月=太岁宫起正月'); }
	if(ZWEngineOptions.liunianSihuaGan === 'ming_gong_gan'){ tbNotes.push('流年四化=依流年命宫天干'); }
	if(ZWEngineOptions.flowLuanXi){ tbNotes.push('流曜含流鸾/流喜'); }
	if(ZWEngineOptions.flowHuoLing){ tbNotes.push('流曜含流火/流铃'); }
	if(ZWEngineOptions.flowShenshaOnChart){ tbNotes.push('流年神煞上盘(将前/岁前随流年)'); }
	if(ZWEngineOptions.brightnessSource === 'quanshu'){ tbNotes.push('星曜亮度=《全书》版(擎羊子酉旺/铃星独立表/亥卯未火星得)'); }
	else if(ZWEngineOptions.brightnessSource === 'quanshu_full'){ tbNotes.push('星曜亮度=《全书》七档全表(庙旺得利平不陷;未载之曜按默认表)'); }
	if(ZWEngineOptions.childLimit){ tbNotes.push('童限(上大限前逐岁本命宫)'); }
	if(ZWEngineOptions.zhongxian){ tbNotes.push('沈氏三限(大限细分2.5年中限)'); }
	if(ZWEngineOptions.huoPan){ tbNotes.push('活盘(太极点可转移重排宫名)'); }
	if(ZWEngineOptions.qishuWei){ tbNotes.push('河洛气数位(官禄宫干四化回照)'); }
	if(ZWEngineOptions.borrowPalace){ tbNotes.push('中州借宫(空宫借对宫正曜)'); }
	if(ZWEngineOptions.taiSuiRuGua){ tbNotes.push('紫云太岁入卦(关系人生肖落宫)'); }
	if(tbNotes.length){ lines.push(`传本设置：${tbNotes.join('、')}`); }
	if(yearGan){
		lines.push(`生年天干：${yearGan}`);
	}
	if(lifeHouse && lifeHouse.name){
		lines.push(`命宫：${lifeHouse.name}${lifeHouse.ganzi ? `（${lifeHouse.ganzi}）` : ''}`);
	}
	if(lifeGan){
		lines.push(`命宫天干：${lifeGan}`);
	}
	// [v2 试点·补硬缺] 左栏「基本信息/四柱」卡内容并入起盘信息(审计:显示了但快照没有)。
	// 全部 best-effort 纯增行(数据缺省不产行 → 既有夹具/挂载字节不变);同 buildZiWeiInfoData 取数口径。
	const infoBz = chart.bazi && chart.bazi.bazi ? chart.bazi.bazi : null;
	if(infoBz){
		const pillars = ['year', 'month', 'day', 'time']
			.map((k)=>(infoBz[k] && infoBz[k].ganzi ? infoBz[k].ganzi : ''))
			.filter(Boolean);
		if(pillars.length === 4){
			lines.push(`四柱：${pillars.join(' ')}`);
		}
	}
	if(chart.lifeMaster){ lines.push(`命主：${chart.lifeMaster}`); }
	if(chart.bodyMaster){ lines.push(`身主：${chart.bodyMaster}`); }
	if(chart.zidou){ lines.push(`子斗：${chart.zidou}`); }
	if(chart.doujun){ lines.push(`斗君：${chart.doujun}`); }
	const infoJu = `${ZWText.ZWMsg[chart.yearPolar] || ''}${ZWText.ZWMsg[chart.gender] || ''} ${chart.wuxingJuText || ''}`.trim();
	if(infoJu){ lines.push(`命局：${infoJu}`); }
	const infoNl = chart.nongli || {};
	if(infoNl.year){
		lines.push(`农历：${`${infoNl.year}年 ${infoNl.leap ? '闰' : ''}${infoNl.month || ''}${infoNl.day || ''}${infoNl.time ? ` ${`${infoNl.time}`.charAt(1)}时` : ''}`.trim()}`);
	}
	// [Q-432/T-395③] 正月初一口径年柱 ≠ 立春口径年柱时,中宫会多画一行「初一口径年柱」,而快照两处
	// (「农历」行是数字年、「四柱」行是立春口径)都看不出这一年的分歧 —— 与页面同判据补一行。
	// 该字段只有走本地历算的盘才带(任一传本开关非缺省),缺省后端盘无此字段 → 零增行。
	const infoYearLunar = infoNl.yearGZByLunar;
	if(infoYearLunar && infoBz && infoBz.year && infoBz.year.ganzi && `${infoYearLunar}` !== `${infoBz.year.ganzi}`){
		lines.push(`初一口径年柱：${infoYearLunar}（四柱行的年柱按立春口径）`);
	}

	lines.push('');
	// [v2 试点·表化] 12 宫同构数据改 GFM 表(宫/干支/大限/星曜四列;值口径与旧键值行逐字同源:
	// name/ganzi/direction/formatStarSiHua 全复用)。表块经 v1/v2 归一器直通、docx/PDF 渲染真表。
	lines.push('[宫位总览]');
	// [Q-432/T-395①] 日干四化徽:开关开启(缺省关)时才取日干,缺省态括注与旧快照逐字节相同。
	const daySihuaGan = ZiWeiHelper.zwShowDaySihua && ZiWeiHelper.zwShowDaySihua() ? (ZiWeiHelper.dayGanOf(chart) || '') : '';
	// [Q-432/T-395②] 流年岁列 / 小限岁列(两开关缺省关)在宫底画岁数条,而 [宫位总览] 一个岁数都没有 →
	// 开了也进不了 AI。开关开启时才加一列(缺省关 = 表头四列、正文逐字节不变,preflight[121] 表头断言零触)。
	const showYearAges = !!(ZiWeiHelper.zwShowYearAges && ZiWeiHelper.zwShowYearAges());
	const showXiaoxianAges = !!(ZiWeiHelper.zwShowXiaoxianAges && ZiWeiHelper.zwShowXiaoxianAges());
	const withAgeCol = showYearAges || showXiaoxianAges;
	const ageCellOf = (house)=>{
		const gz = house && house.ganzi ? `${house.ganzi}` : '';
		const zhi = gz ? gz.charAt(1) : '';
		const parts = [];
		if(showYearAges && zhi && chart.yearZi){
			const ages = ZiWeiHelper.yearAgesOf(zhi, chart.yearZi);
			if(ages && ages.length){ parts.push(`流年 ${ZiWeiHelper.formatAgeStrip(ages)}`); }
		}
		if(showXiaoxianAges && zhi){
			const xx = ZiWeiHelper.xiaoxianAgesOf(chart, zhi)
				|| (Array.isArray(house && house.smallDirection) ? house.smallDirection : []);
			if(xx && xx.length){ parts.push(`小限 ${ZiWeiHelper.formatAgeStrip(xx)}`); }
		}
		return parts.join('；') || '无';
	};
	lines.push(`| 宫位 | 干支 | 大限 | 星曜（四化括注）${withAgeCol ? ' | 岁列（虚岁）' : ''} |`);
	lines.push(`| --- | --- | --- | ---${withAgeCol ? ' | ---' : ''} |`);
	houses.forEach((house, idx)=>{
		// 长生十二神内联宫位格(三合盘恒画的 house.phase,快照曾恒缺;不加表列,表头断言零触;缺省不产)。
		const name = `${house.name || house.id || `宫位${idx + 1}`}${house.phase ? `·${house.phase}` : ''}`;
		const ganzi = house.ganzi || '';
		const palaceGan = ganzi ? normalizeGan(ganzi) : '';
		const direction = house.direction && house.direction.length === 2 ? `${house.direction[0]}~${house.direction[1]}` : '';
		const collected = collectHouseStars(house);
		const stars = collected.list;
		// 星文本内联庙旺档「星名(四化)·档」—— AI 分析判读要求「依庙旺论强弱」,快照必须真给庙旺
		// (曾恒缺失=让模型臆造);不加表列,preflight[121] 表头断言零触。
		const starText = stars.length > 0
			? stars.map((starName)=>{
				const sl = collected.lightOf[starName];
				return `${formatStarSiHua(starName, yearGan, lifeGan, palaceGan, daySihuaGan)}${sl ? `·${sl}` : ''}`;
			}).join('、')
			: '无';
		lines.push(`| ${name} | ${ganzi || '无'} | ${direction || '无'} | ${starText}${withAgeCol ? ` | ${ageCellOf(house)}` : ''} |`);
	});
	lines.push('');

	// 身宫判据钉死引擎输出 house.isBody(与盘面 ZWHouse/ZWHouseSangHe 身宫标记同源;本地/后端两引擎皆保证,
	// bodyHouseIndex 仅本地引擎有故禁走该旁路)。找不到整段不产(best-effort,与来因宫同范式)。
	const bodyHouse = houses.find((house)=> house && house.isBody);
	if(bodyHouse && bodyHouse.name){
		lines.push('[身宫]');
		lines.push(`身宫落${bodyHouse.name}${bodyHouse.ganzi ? `（${bodyHouse.ganzi}）` : ''}`);
		lines.push('');
	}

	if(yearGan){
		// 来因宫判据走 isLaiyinPalace 单源(排除子丑借干宫;与盘面 drawLaiYing 同口径)
		const laiyin = houses.filter((house)=> isLaiyinPalace(house.ganzi, yearGan))
			.map((house)=> `${house.name || ''}（${house.ganzi}）`);
		if(laiyin.length > 0){
			lines.push('[来因宫]');
			lines.push(laiyin.join('、'));
			lines.push('');
		}
	}

	// [八字大运] 盘心十列(起运虚岁+大运干支+起始年,ZWCenterHouse 恒画)快照曾恒缺;
	// 数据与盘心/info 面板同源 chart.bazi.direct.direction,缺省(本地引擎无 direct)整段不产。
	const bzDirect = chart.bazi && chart.bazi.direct && Array.isArray(chart.bazi.direct.direction)
		? chart.bazi.direct.direction : [];
	if(bzDirect.length){
		lines.push('[八字大运]');
		lines.push('| 起运虚岁 | 起始年份 | 大运干支 |');
		lines.push('| --- | --- | --- |');
		bzDirect.forEach((item)=>{
			const gz = item && item.mainDirect && item.mainDirect.ganzi ? item.mainDirect.ganzi : '';
			if(!gz){ return; }
			lines.push(`| ${(item.age || 0) + 1} | ${item.startYear || '无'} | ${gz} |`);
		});
		lines.push('');
	}

	const patterns = result && result.patterns ? result.patterns : [];
	if(patterns.length > 0){
		lines.push('[命中格局]');
		patterns.forEach((p)=>{
			lines.push(`${p.name}（${p.category || ''}${p.broken ? '·破' : ''}）：${p.duanyi || ''}`);
		});
		lines.push('');
	}

	// [#80] 运限概览:无条件段(与八字 [大运]/[流年行运概略] 对称)。可在「纳入内容」里取消勾选。
	const overviewLines = buildZiweiPeriodOverviewLines(chart);
	if(overviewLines.length){ lines.push(...overviewLines); }

	// 运限层（仅挂载「每技法设置」显式选了运限时追加；缺省不追加 → 快照与现状逐字一致）。
	if(params && params.period){
		const periodLines = buildZiweiPeriodLines(chart, params.period);
		if(periodLines.length > 0){
			lines.push(...periodLines);
		}
	}

	// 流派叠层 ground-truth（代码计算·禁 AI 编造；仅开关开时注入 → 全关时快照逐字不变）。
	const overlayLines = buildZiweiOverlayLines(chart);
	if(overlayLines.length){ lines.push(...overlayLines); }

	return lines.join('\n');
}

export { normalizeGan, pickYearGan, collectHouseStars, formatStarSiHua, getLifeHouse, buildZiWeiSnapshotText };
