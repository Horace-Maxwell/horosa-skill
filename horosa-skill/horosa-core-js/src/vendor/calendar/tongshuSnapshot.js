// 通书择日 AI 快照 builder（纯函数）。按流派分派；随各法实现逐步补全。
import { TONGSHU_SCHOOL_MAP } from './tongshuSchools.js';
import { buildHuangliDay } from './huangliDay.js';
import { yongshiVerdict } from './tongshuData.js';
import { donggongDay } from '../tongshu/donggong.js';
import { qimenDieShuDay } from '../tongshu/qimenDieShu.js';
import { sanyuanLiexiuDay } from '../tongshu/sanyuanLiexiu.js';
import { wutuForDate, wutuMonth } from '../tongshu/wutu.js';
import { xuankongForHour, xuankongDay } from '../tongshu/xuankong.js';

// 各法 section builder 注册表（tasks 13/14 各法模块经 registerTongshuSection 接线）。
const SECTION_BUILDERS = { qimen: null, sanyuanliexiu: null, wutu: null, sanyuan: null };
export function registerTongshuSection(school, fn) {
	if (school in SECTION_BUILDERS) { SECTION_BUILDERS[school] = fn; }
}

function parseYmd(ymd) {
	const [y, m, d] = `${ymd}`.split('-').map((n)=> parseInt(n, 10));
	return { y, m, d };
}

function donggongSection(settings, ymd) {
	const { y, m, d } = parseYmd(ymd);
	const r = donggongDay({ y, m, d });
	const lines = [];
	lines.push(`日干支：${r.dayGZ}　${r.monthName}·${r.jianchu}${r.zhi}日`);
	if (settings && settings.event) {
		const yv = yongshiVerdict(buildHuangliDay(y, m, d), settings.event);
		lines.push(`用事「${settings.event}」：${yv.level === 'yi' ? `通书宜（宜 ${yv.hits.join('、')}）`
			: (yv.level === 'ji' ? `通书忌（忌 ${yv.hits.join('、')}）`
				: (yv.level === 'conflict' ? `通书宜忌相冲（命中 ${yv.hits.join('、')}）——按凶优先`
					: '通书无明确宜忌，参酌董公断语与建除'))}`);
	}
	lines.push(`综断：${r.verdict.text}`);
	if (r.jinshen.hit) { lines.push(`⚠ 金神七煞：${r.jinshen.full}值日，切不可犯（三吉星亦不能解）`); }
	if (r.sanxing) { lines.push(`三吉星：${r.sanxing}值日（最吉，能解凶星）`); }
	lines.push(`三煞方：${r.sansha.dir || '—'}（${(r.sansha.zhi || []).join('')}${r.sansha.ju ? '·' + r.sansha.ju : ''}）忌修造动土`);
	lines.push(`董公断语：${r.text}`);
	if ((r.notes || []).length) { lines.push(`节气：${r.notes.join('；')}`); }
	return lines;
}

export function buildTongshuSnapshotText(settings, ymd) {
	if (!settings || !ymd) { return ''; }
	const school = TONGSHU_SCHOOL_MAP[settings.school] || {};
	const lines = [];
	lines.push('[通书择日]');
	lines.push(`流派：${school.label || settings.school}`);
	lines.push(`用事：${settings.event || '—'}`);
	lines.push(`用事日期：${ymd}`);

	lines.push('');
	if (settings.school === 'donggong') {
		lines.push(...donggongSection(settings, ymd));
	} else {
		const fn = SECTION_BUILDERS[settings.school];
		lines.push(...(fn ? fn(settings, ymd) : ['（该流派待实现）']));
	}

	lines.push('');
	lines.push('[方法说明]');
	lines.push(`${school.note || ''}`);
	lines.push('通书择日须与老黄历日课、坐向、主事年命合参；本地历算引擎推得。');
	return lines.join('\n');
}

// —— 各法 section 注册（董公在 buildTongshuSnapshotText 内直连；其余在此登记）——
registerTongshuSection('qimen', (settings, ymd)=>{
	const { y, m, d } = parseYmd(ymd);
	const r = qimenDieShuDay({ y, m, d });
	const lines = [`日干支：${r.dayGZ}（裴晋公叠数法·出行择时）`];
	lines.push(`出行吉时：${r.bestHours.join('、') || '（本日无吉时，宜静守）'}`);
	r.rows.forEach((row)=>{ lines.push(`${row.hourZhi}时(${row.range})：叠数${row.sum}·${row.jx}${row.shi ? '　' + row.shi : ''}`); });
	return lines;
});

registerTongshuSection('sanyuanliexiu', (settings, ymd)=>{
	const { y, m, d } = parseYmd(ymd);
	const r = sanyuanLiexiuDay({ y, m, d });
	const USE_FIELDS = ['建宅', '安葬', '修造', '造命'];
	const useField = USE_FIELDS.includes(settings.liexiuUse) ? settings.liexiuUse : '建宅';
	const lines = [];
	if (r.hitStars.length) {
		r.hitStars.forEach((s)=>{
			lines.push(`⭐ 天帝加临（${s.hitInfo}）·制煞解厄百事吉`);
			USE_FIELDS.forEach((k)=>{ if (s[k]) { lines.push(`　${k}：${s[k]}`); } });
		});
	} else {
		lines.push('本日非天帝加临（古法仅天帝有节气定位：芒种+4日 / 大雪+3日；余十五曜精确加临须七政星历，本地不臆造）。');
	}
	lines.push(`用事类：${useField} —— 十六吉曜该用事断语：`);
	r.stars.forEach((s)=>{ if (s[useField]) { lines.push(`　${s.name}：${s[useField]}`); } });
	return lines;
});

registerTongshuSection('wutu', (settings, ymd)=>{
	const { y, m, d } = parseYmd(ymd);
	const r = wutuForDate({ y, m, d });
	const M = wutuMonth({ y, m, d });
	const lines = [];
	if (r) {
		lines.push(`日干支：${r.dayGZ}（农历${r.dayInMonth}日）`);
		lines.push(`乌兔值星：${r.star}（${r.jx === 'good' ? '吉' : '凶'}）${r.isSun ? '·太阳值日上吉' : (r.isMoon ? '·太阴值日次吉' : '')}`);
	}
	lines.push(`本月太阳日：${M.sunDays.map((x)=> x.dayGZ).join('、') || '—'}`);
	lines.push(`本月太阴日：${M.moonDays.map((x)=> x.dayGZ).join('、') || '—'}`);
	return lines;
});

registerTongshuSection('sanyuan', (settings, ymd)=>{
	const { y, m, d } = parseYmd(ymd);
	const D = xuankongDay({ y, m, d }, settings.mingYear);
	const lines = [];
	lines.push(`日课四柱：年${D.year.gz}(${D.year.gua}·${D.year.wxNum}·${D.year.yun}运) 月${D.month.gz}(${D.month.gua}) 日${D.day.gz}(${D.day.gua}·${D.day.wxNum}·${D.day.yun}运)`);
	if (D.ming) { lines.push(`主事仙命：${D.ming.gz}（${D.ming.gua}·${D.ming.wxNum}）`); }
	lines.push(`宜用时辰（上吉+）：${D.bestHours.join('、') || '（本日无上吉时）'}`);
	const noon = xuankongForHour({ y, m, d, hourZhi: '午' }, settings.mingYear);
	lines.push(`午时日课：${noon.level.name}（时对日${noon.wuji.timeVsDay || '—'}/月对日${noon.wuji.monthVsDay || '—'}/年对日${noon.wuji.yearVsDay || '—'}）${noon.geju ? '·' + noon.geju.name : ''}`);
	lines.push('坐向卦须六十四卦天圆图（源未载 24 山→64 卦，本法从缺）。');
	return lines;
});

export default buildTongshuSnapshotText;
