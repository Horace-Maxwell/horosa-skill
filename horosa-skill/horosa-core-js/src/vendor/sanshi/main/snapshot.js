// 三式合一页:AI 挂载 / 导出快照文本。
// 从 SanShiUnitedMain.js 按职责拆出(门面保留原导入路径与对外导出;读源码的检查读「子模块 + 门面」全集,见 scripts/source-sets.json)。
import { safe } from '../../dunjia/qimenPageShared.js';
import { buildTaiyiSnapshotLines } from '../../taiyi/core/TaiYiCore.js';
import { SANSHI_TAIYI_SECTION_TITLES, parseSnapshotSections, SANSHI_LIURENG_DUANGUA_SECTIONS, SANSHI_QIMEN_EXTRA_SECTIONS } from '../sanshiSnapshotSections.js';
import { buildTaiyiSnapshotText } from '../../taiyi/TaiYiCalc.js';
import { sanChuanRelationSnapshotLines } from '../../liureng/LRSanChuanRelationMini.js';   // 三传递生递克/徽记单源(三式同步)
import { XIAO_JU_REFERENCE_TAB_KEYS, buildOverviewReferenceText, buildReferenceDocumentText, buildLiuRengSnapshotText } from '../../liureng/LiuRengMain.js';
import { BAGONG_PALACE_ORDER, buildQimenBaGongPanelData, BAGONG_PALACE_NAME } from '../../dunjia/DunJiaBaGongRules.js';
import { buildDunJiaSnapshotText, jiGanLines, tuiYanLines } from '../../dunjia/DunJiaCalc.js';
import { jianChuLines } from '../../utils/jianChu.js';
import { buildSanShiZiweiSihuaSnapshotLines } from '../SanShiZiWeiSihua.js';
import { normalizeTimeAlg, getTimeAlgLabel, fmtDirect, fmtSolar, fmtLunar } from './format.js';
import { SANSHI_TRUE_SOLAR_FALLBACK_NOTE, computeSanshiXun } from './liureng.js';
import { appendSection, appendPickedSections, buildSanshiPalaceSections } from './outerRing.js';

export function buildSanShiUnitedSnapshotText(data){
	const {
		fields,
		options,
		nongli,
		displaySolarTime,
		liureng,
		dunjia,
		taiyi,
		keData,
		sanChuan,
		lrLayout,
		liurengRefBundle,
		outerData,
		// 六壬断卦层(复用独立 buildLiuRengSnapshotText)所需的原始入参;缺任一则跳过断卦层(零回归)。
		guirengType,
		liurengChartForLr,
		lrCastOverride,
		lrCastOpts,
		liurengRunYear,
		// 紫微四化 tab 上报的 {chart,daxianIdx,liunianIdx};缺省(旧调用/tab 未开)不产段。
		ziweiSihua,
	} = data || {};
	if(!dunjia || !keData || !sanChuan || !lrLayout){
		return '';
	}
	const lines = [];
	const timeAlg = normalizeTimeAlg(options && options.timeAlg);
	// 历法服务与本地都给不出、退回主盘农历(恒按真太阳时)时如实标注(与太乙「本次按直接时间立局」同做法)
	const timeAlgLabel = `${getTimeAlgLabel(timeAlg)}${nongli && nongli.__trueSolarFallback ? SANSHI_TRUE_SOLAR_FALLBACK_NOTE : ''}`;
	const direct = fmtDirect(fields);
	const solar = fmtSolar(fields, dunjia, nongli, displaySolarTime);
	const directText = `${safe(direct.date, '—')} ${safe(direct.hm, '—')}`.trim();
	const solarText = `${safe(solar.date, '—')} ${safe(solar.hm, '—')}`.trim();
	const lunarText = safe(dunjia.lunarText, fmtLunar(nongli) || '—');
	const pillars = dunjia.ganzhi || {};
	const yuejiang = safe((liureng && liureng.yue) || (lrLayout && lrLayout.yue), '—');
	const nianming = safe(
		liureng && liureng.nianMing,
		(pillars.year && pillars.year.length > 1) ? pillars.year.substring(1, 2) : '—'
	);
	const daySwitchLabel = options && options.after23NewDay === 1 ? '23点算第二天' : '24点算第二天';
	appendSection(lines, '起盘信息', [
		`农历：${lunarText || '—'}`,
		`直接时间：${directText || '—'}`,
		`真太阳时：${solarText || '—'}`,
		`四柱：${safe(pillars.year, '—')}年/${safe(pillars.month, '—')}月/${safe(pillars.day, '—')}日/${safe(pillars.time, '—')}时`,
		`时间算法：${timeAlgLabel}`,
		`换日：${daySwitchLabel}`,
		`月将：${yuejiang}`,
		`年命：${nianming}`,
	]);
	// 旬:与盘面 renderBottom / 概览同源(computeSanshiXun):旬首=时柱旬首 / 旬仪=时柱旬首+六仪 /
	// 本旬=日柱旬首 / 旬空=日空 / 时空=时柱旬空,避免旧 xunShou/fuTou(=六仪)/繁简键失配错值。
	const _xun = computeSanshiXun(dunjia);
	appendSection(lines, '概览', [
		`局数：${safe(dunjia.juText, '—')}`,
		`旬首：${_xun.xunShou}`,
		`旬仪：${_xun.xunYi}`,
		`值符：${safe(dunjia.zhiFu, '—')}`,
		`值使：${safe(dunjia.zhiShi, '—')}`,
		`本旬：${_xun.benXun}`,
		`旬空：${_xun.riKong}`,
		`时空：${_xun.shiKong}`,
		// yiMa.text 本身已带「日马:」/「时马:」前缀(驿马取法可选日马/时马),此处再加一层
		// → 快照与导出出现「日马:日马:申(坤二宫)」,选时马时更成「日马:时马:…」自相矛盾。直接用其自带前缀。
		`${dunjia.yiMa && dunjia.yiMa.text ? dunjia.yiMa.text : '日马：无'}`,
		`阴阳遁：${safe(dunjia.yinYangDun, '—')}`,
		`月将：${yuejiang}`,
		// 封局 / 四柱空亡随开关入快照(缺省关=不产行,字节不变)
		...(dunjia.fengJu ? ['奇门封局：已封局'] : []),
		// 寄干 / 推演 / 十二建星随开关入快照(缺省关=不产行,字节不变;行与奇门页同一份)
		...jiGanLines(dunjia.jiGan),
		...tuiYanLines(dunjia.tuiYan),
		...(options && options.showJianChu ? jianChuLines(dunjia.ganzhi, dunjia.dateStr) : []),
		...(dunjia.allKong ? [`四柱空亡：年空${safe(dunjia.allKong.年空, '—')}、月空${safe(dunjia.allKong.月空, '—')}、日空${safe(dunjia.allKong.日空, '—')}、时空${safe(dunjia.allKong.时空, '—')}`] : []),
	]);
	if(taiyi){
		appendSection(lines, '太乙', buildTaiyiSnapshotLines(taiyi));
		// 太乙动态派生段(主客定算/八门与宿曜/断法/七大兵法/博弈/命法/命宫行限):复用独立 buildTaiyiSnapshotText,
		// 切其按 pan.sections 产出的段(单一真值源,同 formatSnapshotValue 口径),以「太乙」前缀重发(三式合一缺这些 → 导出/挂载贫)。
		const taiyiSectionTitles = Array.isArray(taiyi.sections)
			? SANSHI_TAIYI_SECTION_TITLES.filter((title)=>taiyi.sections.some((section)=>section && section.title === title))
			: [];
		if(taiyiSectionTitles.length){
			const taiyiSectionMap = parseSnapshotSections(buildTaiyiSnapshotText(taiyi));
			appendPickedSections(lines, taiyiSectionMap, taiyiSectionTitles, '太乙');
		}
		appendSection(lines, '太乙十六宫', (taiyi.palace16 || []).map((item)=>{
			const txt = item.items && item.items.length ? item.items.join('、') : '—';
			return `${item.palace}：${txt}`;
		}));
	}
	const keRaw = keData && Array.isArray(keData.raw) ? keData.raw : [];
	const formatKe = (idx)=>{ 
		const item = keRaw[idx] || [];
		return `${safe(item[2], '—')}${safe(item[1], '—')}${safe(item[0], '—')}`;
	};
	const formatChuan = (idx)=>{
		const gz = safe(sanChuan && sanChuan.cuang && sanChuan.cuang[idx], '—');
		const god = safe(sanChuan && sanChuan.tianJiang && sanChuan.tianJiang[idx], '');
		return god ? `${gz}（${god}）` : gz;
	};
	// raw[0]=一课(日干上神)…raw[3]=四课,与盘面 SanshiUnitedBoard、独立六壬页、帮助文同序(此前 3→0 颠倒)。
	// 三传递生递克 + 逐传空/禄/马徽记(与独立六壬页、右栏小图同一纯函数;三式同步铁律)。
	const _ssCtx = (liurengRefBundle && liurengRefBundle.context) || null;
	const _ssRelLines = (_ssCtx && Array.isArray(_ssCtx.sanChuanBranches) && _ssCtx.sanChuanBranches.length >= 3)
		? sanChuanRelationSnapshotLines({
			branches: _ssCtx.sanChuanBranches,
			gans: _ssCtx.sanChuanGans || [],
			dayGan: _ssCtx.dayGan || '',
			dayZhi: _ssCtx.dayZhi || '',
			xunKong: _ssCtx.xunKongBranches || [],
		})
		: [];
	appendSection(lines, '大六壬', [
		`一课：${formatKe(0)}`,
		`二课：${formatKe(1)}`,
		`三课：${formatKe(2)}`,
		`四课：${formatKe(3)}`,
		'',
		`初传：${formatChuan(0)}`,
		`中传：${formatChuan(1)}`,
		`末传：${formatChuan(2)}`,
		..._ssRelLines,
	]);
	const refBundle = liurengRefBundle || {};
	const xiaojuAllItems = Array.isArray(refBundle.xiaoju) ? refBundle.xiaoju : [];
	const xiaojuMainItems = xiaojuAllItems.filter((item)=>!XIAO_JU_REFERENCE_TAB_KEYS.has(item.key));
	const xiaojuReferenceItems = xiaojuAllItems.filter((item)=>XIAO_JU_REFERENCE_TAB_KEYS.has(item.key));
	const appendRefSection = (title, items, type)=>{
		if(!items || !items.length){
			appendSection(lines, title, ['无']);
			return;
		}
		const body = [];
		items.forEach((item, idx)=>{
			body.push(`${idx + 1}. ${safe(item.name, '未命名')}`);
			const docText = type === 'overview'
				? buildOverviewReferenceText(item)
				: buildReferenceDocumentText(item, type);
			if(docText){
				docText.split('\n').forEach((line)=>body.push(line));
			}
			if(item.evidence && item.evidence.length){
				body.push(`依据：${item.evidence.join('；')}`);
			}
			body.push('');
		});
		if(body.length && body[body.length - 1] === ''){
			body.pop();
		}
		appendSection(lines, title, body);
	};
	appendRefSection('六壬大格', refBundle.dage || [], 'dage');
	appendRefSection('六壬小局', xiaojuMainItems, 'xiaoju');
	appendRefSection('六壬参考', xiaojuReferenceItems, 'xiaoju');
	appendRefSection('六壬概览', refBundle.overview || [], 'overview');
	// 六壬断卦层(十二盘式/常用神煞/年月神煞/课体结构/三传旺衰/空亡真假/旬空落点/陷空/遁干特殊/年命上神/毕法/占断向导):
	// 复用独立 buildLiuRengSnapshotText(单一真值源),用三式合一同源入参重跑后切断卦段——独立页有、三式合一此前缺。
	// 入参齐备才跑(零回归);params=null 跳过起盘信息行,zhangshengElem='' 不影响断卦层(其只依赖 refs.context)。
	if(liureng && liurengChartForLr){
		let liurengFull = '';
		try{
			liurengFull = buildLiuRengSnapshotText(
				null,
				liureng,
				liurengRunYear || null,
				liurengChartForLr,
				guirengType,
				'',
				options && options.sex,
				{ ...(lrCastOpts || {}), castOverride: lrCastOverride || undefined }
			);
		}catch(e){
			liurengFull = '';
		}
		if(liurengFull){
			const liurengSectionMap = parseSnapshotSections(liurengFull);
			// 段单补「七政」:独立六壬快照有 [七政] 段、三式合一也有「七政」页签,此前挑段单漏它 → 该段被丢
			appendPickedSections(lines, liurengSectionMap, SANSHI_LIURENG_DUANGUA_SECTIONS, '');
		}
	}
	buildSanshiPalaceSections({ dunjia, lrLayout, outerData }).forEach((sec)=>appendSection(lines, sec.title, sec.body));
	const shenshaItems = dunjia.shenSha && Array.isArray(dunjia.shenSha.allItems) ? dunjia.shenSha.allItems : [];
	appendSection(lines, '神煞', shenshaItems.length
		? shenshaItems.map((item)=>`${item.name}：${item.value}`)
		: ['暂无神煞']);
	const bagongLines = [];
	BAGONG_PALACE_ORDER.forEach((palaceNum)=>{
		const item = buildQimenBaGongPanelData(dunjia, palaceNum);
		const palaceName = item.palaceName || BAGONG_PALACE_NAME[palaceNum] || '';
		bagongLines.push(`${palaceName}宫：`);
		if(item.jiPatternDetails && item.jiPatternDetails.length){
			bagongLines.push('奇门吉格：');
			item.jiPatternDetails.forEach((txt)=>bagongLines.push(`- ${txt}`));
		}else{
			bagongLines.push('奇门吉格：无');
		}
		if(item.xiongPatternDetails && item.xiongPatternDetails.length){
			bagongLines.push('奇门凶格：');
			item.xiongPatternDetails.forEach((txt)=>bagongLines.push(`- ${txt}`));
		}else{
			bagongLines.push('奇门凶格：无');
		}
		bagongLines.push(`十干克应（天${item.tianGan || '—'}加地${item.diGan || '—'}）：${item.tenGanText}`);
		bagongLines.push(`八门克应（人${item.renDoor || '—'}加地${item.baseDoor || '—'}）：${item.doorBaseText}`);
		bagongLines.push(`奇仪主应（人${item.renDoor || '—'}加天${item.tianGan || '—'}）：${item.doorTianText}`);
		bagongLines.push(`八神加八门（${item.godFull || '—'}加${item.renDoor || '—'}门）：${item.godDoorText}`);
		bagongLines.push(`奇门演卦（门方）：${item.menFangYiGuaText || '无'}`);
		bagongLines.push('');
	});
	if(bagongLines.length && bagongLines[bagongLines.length - 1] === ''){
		bagongLines.pop();
	}
	appendSection(lines, '八宫详解', bagongLines);
	// 奇门派生/法奇门段(九宫方盘/旺相休囚死·月令能量/六害总览/化解方案/八门化气大阵/用神分论/财富七要/事业七要/
	// 恋爱姻缘/孤辰寡宿):复用独立 buildDunJiaSnapshotText(单一真值源),切其对应段以「奇门」前缀重发
	// (避免与六壬「概览」等碰撞)——独立遁甲页有、三式合一此前缺这 ~9 段。
	const qimenSectionMap = parseSnapshotSections(buildDunJiaSnapshotText(dunjia));
	appendPickedSections(lines, qimenSectionMap, SANSHI_QIMEN_EXTRA_SECTIONS, '奇门');
	// A 类硬缺:紫微四化叠加 tab(SanShiZiWeiSihua 独立计算)显示了却不入快照。
	// 复用该组件导出的同源纯函数取数(单一真值源,与 tab 同一套 getLayerSihua/ZWLuckPanel 计算);
	// 无盘/无四化不产段(零回归——旧调用不带 ziweiSihua 时输出与此前逐字节一致)。
	if(ziweiSihua && ziweiSihua.chart){
		const ziweiSihuaLines = buildSanShiZiweiSihuaSnapshotLines(ziweiSihua.chart, ziweiSihua.daxianIdx, ziweiSihua.liunianIdx);
		if(ziweiSihuaLines.length){
			appendSection(lines, '紫微四化', ziweiSihuaLines);
		}
	}
	return lines.join('\n').trim();
}
