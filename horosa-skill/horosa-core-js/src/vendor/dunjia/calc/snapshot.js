// AI 快照正文(buildDunJiaSnapshotText)
// 从 DunJiaCalc.js 按职责拆出(门面保留原导入路径与对外导出;读源码的检查读「子模块 + 门面」全集,见 scripts/source-sets.json)。
import { JINHAN_STAR_JI } from '../jinhanRiJia.js';
import { buildQimenOverviewSummary, buildQimenFuShiYiGua, buildQimenBaGongSnapshotLines, buildQimenBaGongKeYingSnapshotLines } from '../DunJiaBaGongRules.js';
import { LUOSHU_NUM } from '../DunJiaFaDoc.js';
import { buildFaQimenAnalysis } from '../DunJiaFaCalc.js';
import { QIMEN_WU_HE, buildQimenWangShuai } from './tables.js';
import { joinList } from './shensha.js';
import { jiGanLines, tuiYanLines } from './overlay.js';
import { jianChuLines } from '../../utils/jianChu.js';

// GFM 表化同构数据行(空 cell → —),供 AI 导出/挂载可读化;数据层零变化——表行可逆变换逐字复原旧格式行。
const MD_DASH = '—';

function pushMdRows(lines, header, rows){
	lines.push(`| ${header.join(' | ')} |`);
	lines.push(`| ${header.map(()=>'---').join(' | ')} |`);
	rows.forEach((cells)=>{
		lines.push(`| ${cells.map((c)=>(c === undefined || c === null || c === '' ? MD_DASH : `${c}`)).join(' | ')} |`);
	});
}

export function buildDunJiaSnapshotText(pan){
	// 古籍金函系日家专段(独立体系,与常规盘快照结构不同)
	if(pan && pan.isJinhan && pan.jinhan){
		const L = [];
		L.push('【日家占方（古籍金函系）】');
		L.push(`日期：${pan.dateStr || ''} ${pan.timeStr || ''}（${pan.lunarText || ''}）`);
		L.push(`日干支：${pan.jinhan.dayGz}（${pan.jinhan.pantype}盘·冬至后为阳/夏至后为阴）`);
		L.push(`八门排法：${pan.options.jinhanMenPaiLabel || '书表直录'}`);
		L.push(`中宫星：${pan.jinhan.center}（${JINHAN_STAR_JI[pan.jinhan.center] || ''}）`);
		const parts = [];
		(pan.cells || []).forEach((c)=>{
			if(!c || c.isCenter){ return; }
			parts.push(`${c.jinhanDir}:${c.tianXing}(${c.jinhanStarJi})${c.door}门(${c.jinhanDoorJi})${c.isXiShen ? '·喜神' : ''}${c.isDaJi ? '·大吉' : ''}`);
		});
		L.push(`八方星门：${parts.join('；')}`);
		L.push(`喜神方：${pan.jinhan.xiShen}；大吉方：${pan.jinhan.daJiFang || '—'}`);
		L.push(`大吉时：${pan.jinhan.jiShi}`);
		L.push(`十二时辰黄黑道：${pan.jinhan.shiText}`);
		L.push('吉凶判则（书定）：门重于星；开休生=吉门，杜景=平，死惊伤=凶门；天乙太乙太阴青龙=吉星，轩辕招摇=平，摄提咸池天符=凶星。');
		if(pan.jianChu){ L.push(...jianChuLines(pan.ganzhi, pan.dateStr)); }
		return L.join('\n');
	}

	if(!pan){
		return '';
	}
	const timeAlgLabel = pan.options && pan.options.timeAlgLabel ? pan.options.timeAlgLabel : '真太阳时';
	const directDateTime = `${pan.dateStr || ''} ${pan.timeStr || ''}`.trim();
	const lines = [];
	lines.push('[起盘信息]');
	lines.push(`日期：${directDateTime}`);
	lines.push(`直接时间：${directDateTime || '—'}`);
	lines.push(`真太阳时：${pan.realSunTime || '—'}`);
	lines.push(`计算基准：${timeAlgLabel}`);
	if(pan.lunarText){
		lines.push(`农历：${pan.lunarText}`);
	}
	if(pan.jiedelta){
		lines.push(`${pan.jiedelta}`);
	}
	lines.push(`干支：年${pan.ganzhi.year || ''} 月${pan.ganzhi.month || ''} 日${pan.ganzhi.day || ''} 时${pan.ganzhi.time || ''}`);
	lines.push(`空亡：${pan.kongWang}`);
	lines.push(`旬首：${pan.xunShou}`);
	lines.push('');

	lines.push('[盘型]');
	lines.push(`奇门遁甲方盘（${pan.options.paiPanLabel}）`);
	// sexLabel 缺(直调链未传 sex)时不出此行——零信息优于「命式：undefined」脏行。
	if(pan.options.sexLabel){ lines.push(`命式：${pan.options.sexLabel}`); }
	lines.push(`移星：${pan.options.shiftLabel || '原宫'}`);
	lines.push(`奇门封局：${pan.options.fengJuLabel || (pan.fengJu ? '已封局' : '未封局')}`);
	lines.push(`换日：${pan.options.daySwitchLabel || '23点算第二天'}`);
	lines.push(`时间算法：${timeAlgLabel}`);
	lines.push(`节气：${pan.jieqiText}`);
	if(pan.lifaJieqi && pan.dingjuJieqi && pan.lifaJieqi !== pan.dingjuJieqi){
		lines.push(`历法节气：${pan.lifaJieqi}（置闰超神，定局取${pan.dingjuJieqi}）`);
	}
	lines.push(`局数：${pan.juText}`);
	lines.push(`定局法：${pan.options.dingFaLabel || pan.options.qijuMethodLabel}`);
	lines.push(`盘式：${pan.options.schoolLabel || '转盘（排宫）'}`);
	// 非默认档才出注记(默认字节稳)
	if(pan.options.godsPresetLabel && (pan.options.godsPreset && pan.options.godsPreset !== 'baihu_xuanwu')){ lines.push(`八神取神：${pan.options.godsPresetLabel}`); }
	// 中宫寄宫非默认档注记(默认恒坤=零注记字节稳)
	if(pan.options.jiGongModeLabel && pan.options.jiGongMode && pan.options.jiGongMode !== 'kun'){ lines.push(`中宫寄宫：${pan.options.jiGongModeLabel}`); }
	// 值使取法非默认档注记(默认零注记字节稳;飞盘 / 混合盘取法不适用,不出)
	if(pan.options.zhiShiType && pan.options.zhiShiLabel){ lines.push(`值使取法：${pan.options.zhiShiLabel}`); }
	// 飞盘细项/混合装配非默认注记(默认零注记字节稳)
	(function(){
		const o = pan.options;
		const shun = [o.feiXingShun ? '九星' : '', o.feiMenShun ? '九门' : '', o.feiShenShun ? '九神' : ''].filter(Boolean);
		if(shun.length){ lines.push(`飞宫顺飞：${shun.join('、')}（阴阳遁皆顺）`); }
		if(o.feiMenZhongCan === false){ lines.push(`门层跳中：八门不入中宫${o.feiMenZhongShow ? '（中宫标「中」）' : ''}`); }
		const mixParts = [];
		if(o.mixTian){ mixParts.push(`天盘${o.mixTian === 'fei' ? '飞' : '转'}`); }
		if(o.mixXing){ mixParts.push(`九星${o.mixXing === 'fei' ? '飞' : '转'}`); }
		if(o.mixMen){ mixParts.push(`八门${o.mixMen === 'fei' ? '飞' : '转'}`); }
		if(o.mixShen){ mixParts.push(`九神${o.mixShen === 'fei' ? '飞' : '转'}`); }
		if(mixParts.length){ lines.push(`混合装配：${mixParts.join('、')}`); }
		if(o.kongMarkBoth){ lines.push('空亡标注：日空＋时空并标'); }
		if(o.dayJiaJuLabel && o.dayJiaJu && o.dayJiaJu !== 'yiyuan'){ lines.push(`日家定局：${o.dayJiaJuLabel}`); }
		if(o.yearJiaJu === 'yinian'){ lines.push(`年家定局：${o.yearJiaJuLabel}`); }
		if(o.shiftZhiFuMode === 'recalc'){ lines.push('移星值符：移后重定值符值使'); }
	})();
	if(pan.allKong){
		lines.push(`四柱空亡：年空${pan.allKong.年空}、月空${pan.allKong.月空}、日空${pan.allKong.日空}、时空${pan.allKong.时空}`);
	}
	if(pan.keIndex){
		lines.push(`刻序：本时辰第${pan.keIndex}刻${pan.keGanZhi ? `（刻柱${pan.keGanZhi}）` : ''}（十二分钟一局，${pan.options.keJiaFenDunLabel || '子后阳·午后阴'}${pan.options.keZiZhengHuanShi ? `，子正换时·时辰${pan.keTimeGanZhi || ''}` : ''}）`);   // 子正换时开时注明所用时辰
	}
	if(pan.anGan){
		lines.push(`暗干：${pan.options.anGanModeLabel || ''}`);
		const parts = [];
		'坎坤震巽中乾兑艮离'.split('').forEach((gua)=>{
			if(pan.anGan[gua]){ parts.push(`${gua}${pan.anGan[gua]}${pan.anZhi && pan.anZhi[gua] ? pan.anZhi[gua] : ''}`); }
		});
		if(parts.length){ lines.push(`暗干分布：${parts.join('、')}`); }
	}
	// 寄干 / 天禽 / 推演(翻宫·转宫):开关开才有,缺省快照逐字不变
	if(pan.jiGan){ lines.push(...jiGanLines(pan.jiGan)); }
	if(pan.tuiYan){ lines.push(...tuiYanLines(pan.tuiYan)); }
	if(pan.jianChu){ lines.push(...jianChuLines(pan.ganzhi, pan.dateStr)); }   // 十二建星(开关开才有;三式合一另在概览段出,不经这里)
	if(pan.shuziInfo){
		lines.push(`阴盘起局：报数 ${pan.shuziInfo.digits}，各位求和 ${pan.shuziInfo.sum}，除9(余0作9)定局数；用神宫 ${pan.shuziInfo.gong} 宫（${pan.shuziInfo.gua}·${pan.shuziInfo.direction}）。阴阳遁按节气、局已据报数置换；阴盘奇门取数与余数映射各家有别，断盘侧重用神宫象意。`);
	}
	if(pan.school === '飞盘'){
		lines.push('飞盘体系：洛书飞布九星九门九神（含中宫），九神为符蛇阴合勾常雀地天。');
	} else if(pan.school === '混合'){
		lines.push('飞转混合：九星=排宫(转盘·星寄坤2不入中、天禽)，八门=飞宫(飞盘·可入中5)，九神=飞泊(含中宫)。');
	}
	lines.push(`空亡方式：${pan.options.kongModeLabel}`);
	lines.push(`驿马方式：${pan.options.yimaModeLabel}`);
	lines.push(`值符：${pan.zhiFu}`);
	lines.push(`值使：${pan.zhiShi}`);
	lines.push('');

	// [全局速览]：九遁/三奇得使/吉凶格品级 + 命事局，一眼看全局格局（与概览页「全局速览」同源）。
	const overview = buildQimenOverviewSummary(pan);
	if(overview){
		const catText = pan.options && pan.options.chartCategory === 'ming' ? '命局（日干＝内心 / 时干＝外在）' : '事局（日干＝实质 / 时干＝表象）';
		// 飞盘 / 混合盘值符值使可落中五宫:中宫不在八卦宫名表里,单写「中五宫」
		const posShort = (it)=>(it && it.palace ? (LUOSHU_NUM[it.palaceName] === undefined ? '中五宫' : `${it.palaceName}${LUOSHU_NUM[it.palaceName]}宫·${it.dir}`) : '未现');
		// x.palace 是内部九宫序号,宫号一律走洛书
		const patTag = (x)=>`${x.name}(${x.palaceName}${LUOSHU_NUM[x.palaceName]}宫)`;
		const patShort = (arr)=>(arr && arr.length ? arr.slice(0, 3).map(patTag).join('、') + (arr.length > 3 ? ` 等${arr.length}例` : '') : '无');
		lines.push('[全局速览]');
		lines.push(`盘类：${catText}`);
		lines.push(`九遁：${overview.dun.length ? overview.dun.map(patTag).join('、') : '无'}`);
		lines.push(`三奇得使：${overview.sanQiDeshi ? posShort(overview.sanQiDeshi) : '无'}`);
		lines.push(`吉格 ${overview.ji.length} 例：${patShort(overview.ji)}`);
		lines.push(`凶格 ${overview.xiong.length} 例：${patShort(overview.xiong)}`);
		const harm = overview.sixHarm;
		const harmCount = harm.jiXing.length + harm.ruMu.length + harm.menPo.length + harm.kongWang.length + harm.gengHu.length;
		lines.push(`六害分布：${harmCount ? `击刑${harm.jiXing.length}·入墓${harm.ruMu.length}·门迫${harm.menPo.length}·空亡${harm.kongWang.length}·庚虎${harm.gengHu.length}` : '本局未现'}`);
		lines.push(`值符落宫：${posShort(overview.zhiFu)}（${overview.zhiFu.star || '—'}）　值使落宫：${posShort(overview.zhiShi)}（${overview.zhiShi.door || '—'}）`);
		lines.push('');
	}

	lines.push('[盘面要素]');
	lines.push(`符头：${pan.fuTou}`);
	lines.push(`地盘：${pan.diPanList.join(' ')}`);
	lines.push(`天盘：${pan.tianPanList.join(' ')}`);
	// 五合配干(盘面每宫恒画的十干合注记,快照曾恒缺):判据与盘面同源=cell.tianGan||cell.diGan 经 QIMEN_WU_HE。
	const wuHeParts = (pan.cells || []).map((cell)=>{
		const g = (cell && (cell.tianGan || cell.diGan)) || '';
		return g && QIMEN_WU_HE[g] ? `${cell.palaceName}${LUOSHU_NUM[cell.palaceName] || ''}宫${g}合${QIMEN_WU_HE[g]}` : '';
	}).filter(Boolean);
	if(wuHeParts.length){
		lines.push(`五合配干：${wuHeParts.join('、')}`);
	}
	lines.push(`人盘：${pan.renPanList.join(' ')}`);
	lines.push(`神盘：${pan.shenPanList.join(' ')}`);
	lines.push(`六仪击刑：${joinList(pan.liuYiJiXing)}`);
	lines.push(`奇仪入墓：${joinList(pan.qiYiRuMu)}`);
	lines.push(`门迫：${joinList(pan.menPo && pan.menPo.list ? pan.menPo.list : [])}`);
	lines.push(`空亡宫：${joinList(pan.kongWangDesc)}`);
	lines.push(`${pan.yiMa ? pan.yiMa.text : '日马：无'}`);
	if(pan.shenSha && pan.shenSha.summary && pan.shenSha.summary.length){
		lines.push(`神煞概览：${pan.shenSha.summary.map((item)=>`${item.name}-${item.value}`).join('  ')}`);
	}
	// 神煞全量(右栏「神煞」tab 渲染 allItems 30+ 条,快照曾只有概览 5 条;与三式合一同口径)。
	if(pan.shenSha && Array.isArray(pan.shenSha.allItems) && pan.shenSha.allItems.length){
		lines.push(`神煞全量：${pan.shenSha.allItems.map((item)=>`${item.name}-${item.value}`).join('  ')}`);
	}
	lines.push('');

	const fushiYiGua = buildQimenFuShiYiGua(pan);
	lines.push('[奇门演卦]');
	lines.push(`值符值使演卦：${fushiYiGua.text || '无'}`);
	lines.push('门方演卦：见[八宫详解]各宫“奇门演卦（门方）”。');
	lines.push('');

	const bagongLines = buildQimenBaGongSnapshotLines(pan);
	if(bagongLines && bagongLines.length){
		lines.push(...bagongLines);
		lines.push('');
	}

	// [八宫克应] doctrine 段(默认关段:builder 恒产,导出层按设置控)——克应/主应释义原文,可独立于[八宫详解]勾选。
	const bagongKeYingLines = buildQimenBaGongKeYingSnapshotLines(pan);
	if(bagongKeYingLines && bagongKeYingLines.length){
		lines.push(...bagongKeYingLines);
		lines.push('');
	}

	lines.push('[九宫方盘]');
	// 九宫 → GFM 表:宫/天干/神/门/天星/地干(空位源即 —,逐字保留)。
	pushMdRows(lines, ['宫', '天干', '神', '门', '天星', '地干'], pan.cells.map((cell)=>[
		`${cell.palaceName}${LUOSHU_NUM[cell.palaceName]}宫`, cell.tianGan || '—', cell.god || '—', cell.door || '—', cell.tianXing || '—', cell.diGan || '—',
	]));

	// 旺相休囚死(§17.1):以月令五行定各符号能量,供「看旺衰」断盘——旺相则吉力大凶有挡,休囚死则吉力弱凶更凶。
	const wangShuai = buildQimenWangShuai(pan);
	if(wangShuai && wangShuai.monthElem){
		lines.push('');
		lines.push('[旺相休囚死·月令能量]');
		lines.push(`月令：${wangShuai.monthBranch}（${wangShuai.monthElem}令）。当令者旺、我生者相、生我者休、克我者囚、我克者死；旺相有力，休囚死无力。`);
		// 各宫 → GFM 表:宫/星/星五行/星旺衰/门/门五行/门旺衰/宫五行/宫旺衰(空位源即 —)。
		pushMdRows(lines, ['宫', '星', '星五行', '星旺衰', '门', '门五行', '门旺衰', '宫五行', '宫旺衰'], wangShuai.palaces.map((p)=>[
			`${p.palaceName}${LUOSHU_NUM[p.palaceName]}宫`, p.star || '—', p.starWuxing || '—', p.starWangShuai || '—', p.door || '—', p.doorWuxing || '—', p.doorWangShuai || '—', p.gongWuxing || '—', p.gongWangShuai || '—',
		]));
	}

	// —— 法奇门叠加层（六害 / 化解 / 八门化气大阵 / 用神分论 / 七要 / 孤辰寡宿）；全量输出供 AI 导出·挂载·储存 ——
	const fa = buildFaQimenAnalysis(pan, { faceToFace: true, chartCategory: pan.options && pan.options.chartCategory });
	if(fa){
		const posTxt = (it)=>(it && it.palaceNum ? `${it.palaceName}${LUOSHU_NUM[it.palaceName]}宫` : '未现');
		lines.push('');
		lines.push('[六害总览]');
		if(fa.dangers.length){
			lines.push('危害递减：击刑＞入墓＞庚＞白虎＞门迫＞空亡；天干＞一切，先解击刑天干。');
			// 六害 → GFM 表:危害/宫位/符号。
			pushMdRows(lines, ['危害', '宫位', '符号'], fa.dangers.map((d)=>[d.type, `${d.palaceName}${LUOSHU_NUM[d.palaceName]}宫(${d.direction})`, d.symbol]));
		}else{
			lines.push('本局四纲八宫未现六害。');
		}
		if(fa.panType.type){ lines.push(`盘型：${fa.panType.type}局——${fa.panType.text}`); }

		lines.push('');
		lines.push('[化解方案]');
		if(fa.jieHua.length){
			// 化解 → GFM 表:宫位/危害/天盘干/化解(灭象·布阵·时机·备注合并;还原时补回 「：」后单空格)。
			pushMdRows(lines, ['宫位', '危害', '天盘干', '化解'], fa.jieHua.map((j)=>{
				const dz = j.dangers.map((x)=>x.type).join('+');
				const mieTxt = j.mie.length ? ' 灭象：' + j.mie.join(' ') : '';
				const buTxt = j.placements.length ? ' 布阵：' + j.placements.map((p)=>p.where + p.text).join('；') : '';
				const shiTxt = ` 时机:本宫${j.benZhi || ''}日/${j.ben || ''} 对宫${j.duiZhi || ''}日/${j.dui || ''}`;
				const notesTxt = j.notes.length ? '｜' + j.notes.join(' ') : '';
				return [`${j.palaceName}${LUOSHU_NUM[j.palaceName]}宫·${j.direction}`, dz, j.tianGan, `${mieTxt}${buTxt}${shiTxt}${notesTxt}`.trim()];
			}));
		}else{
			lines.push('无需化解。');
		}

		lines.push('');
		lines.push('[八门化气大阵]');
		// 八门保护 → GFM 表:门/落宫/状态。
		pushMdRows(lines, ['门', '落宫', '状态'], fa.protect.map((r)=>[
			`${r.label}${r.gan ? '(' + r.gan + ')' : ''}`, r.palaceNum ? r.palaceName + LUOSHU_NUM[r.palaceName] + '宫·' + r.direction : '未现', r.hazards.length ? '[' + r.hazards.join('/') + ']' : '[平稳]',
		]));

		lines.push('');
		lines.push('[用神分论]');
		if(fa.yongShen){
			lines.push(fa.yongShen.yongShenText);
			lines.push(`日干:${fa.yongShen.dayGan.symbol}(${posTxt(fa.yongShen.dayGan)})　时干:${fa.yongShen.timeGan.symbol}(${posTxt(fa.yongShen.timeGan)})${fa.yongShen.ganHe ? '　干合/配偶:' + fa.yongShen.ganHe.symbol + '(' + posTxt(fa.yongShen.ganHe) + ')' : ''}`);
			lines.push(`符使:值符${posTxt(fa.yongShen.zhiFu)}/值使${posTxt(fa.yongShen.zhiShi)}`);
			lines.push(`六亲:${fa.yongShen.liuQin.map((r)=>r.rel.split('·')[1] + r.symbol + posTxt(r)).join(' ')}`);
		}

		lines.push('');
		lines.push('[财富七要]');
		if(fa.wealth){
			// 财富用神 → GFM 表:用神/落宫/危害(无危害 → —)。月令/干财为汇总散文,保持原样。
			pushMdRows(lines, ['用神', '落宫', '危害'], fa.wealth.items.map((it)=>[it.name, posTxt(it), it.hazards && it.hazards.length ? '[' + it.hazards.join('/') + ']' : '']));
			lines.push(`月令:${fa.wealth.month.zhi}(${fa.wealth.month.wuxing}) ${fa.wealth.month.relation}`);
			if(fa.wealth.ganCai.length){ lines.push(`干财:${fa.wealth.ganCai.map((c)=>c.src + c.symbol + posTxt(c)).join(' ')}`); }
			// 行业取象(渲染有快照无;事业段同款字段早有,财富段曾独漏)。
			if(fa.wealth.industryHint){ lines.push(fa.wealth.industryHint); }
		}

		lines.push('');
		lines.push('[事业七要]');
		if(fa.career){
			// 事业用神 → GFM 表:用神/落宫/危害(无危害 → —)。符使/诸干/行业取象为汇总散文,保持原样。
			pushMdRows(lines, ['用神', '落宫', '危害'], fa.career.items.map((it)=>[it.name, posTxt(it), it.hazards && it.hazards.length ? '[' + it.hazards.join('/') + ']' : '']));
			lines.push(`符使:${fa.career.fuShi.map((r)=>r.rel + posTxt(r)).join(' ')}`);
			lines.push(`诸干:${fa.career.zhuGan.map((r)=>r.rel.split('·')[1] + r.symbol + posTxt(r)).join(' ')}`);
			if(fa.career.industryHint){ lines.push(fa.career.industryHint); }
		}

		lines.push('');
		lines.push('[恋爱姻缘]');
		if(fa.romance){
			fa.romance.zhengYuan.forEach((z)=>lines.push(`${z.name}:${z.symbol || ''}${posTxt(z)}`));
			lines.push(`三奇桃花:${fa.romance.taoHua.sanQi.map((s)=>s.gan + posTxt(s)).join(' ')}`);
			lines.push(`沐浴位:${fa.romance.taoHua.muYu.zhi}(${fa.romance.taoHua.muYu.palaceNum ? fa.romance.taoHua.muYu.palaceName + LUOSHU_NUM[fa.romance.taoHua.muYu.palaceName] + '宫' : '—'})`);
			if(fa.romance.trouble.length){ lines.push(`情感不顺:${fa.romance.trouble.join(' ')}`); }
			if(fa.romance.zhanTaoHua){ lines.push(fa.romance.zhanTaoHua); }
		}

		lines.push('');
		lines.push('[孤辰寡宿]');
		lines.push(fa.guGua.length ? fa.guGua.map((g)=>`${g.name}(${g.zhi}):${g.jie}`).join('；') : '无');
	}

	return lines.join('\n');
}
