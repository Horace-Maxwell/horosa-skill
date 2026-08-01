// 演禽「演法」AI 快照:把右栏演法结果(起禽四禽/择日值日/占卜我彼/投胎 + 当前流派)
// 序列化成文本,追加到 xianqin 挂载快照,供 AI 分析/导出消费(单一真值源=引擎+store,所见即所得)。
import { Solar } from 'lunar-javascript';
import { isLunarJsYearReliable } from '../bazi/lunarDomainGuard.js';
import { DIZHI } from './yanqinConst.js';
import { castQinChart, monthQin, toutaiDu, qinKeByWuxing, wuxingOfMansion } from './yanqinEngine.js';
import { YANQIN_PRESETS, resolveWoBi } from './yanqinSchools.js';
import { getYanqinSettings } from './yanqinStore.js';
import { ZHIRI_JIXIONG } from './yanqinData.js';

function mod(n, m) { return ((n % m) + m) % m; }
const KE_TEXT = { meWin: '我克彼→吉(我胜)', theyWin: '彼克我→凶(彼胜)', meSheng: '我生彼→泄', theySheng: '彼生我→受助', peace: '比和→相持' };

// payload = parseFieldsDateTime 结果 {year,month,day,hour,...}
export function buildYanqinYanfaSnapshot(payload) {
	// 全年份域:年可为公元前(负,无 0 年);旧 `year > 0` 把 BC 演法快照整段吞成 ''。
	if (!payload || !Number.isFinite(payload.year) || payload.year === 0) { return ''; }
	const s = getYanqinSettings();
	const hourBranch = Math.floor((((payload.hour || 0) + 1) % 24) / 2);
	// 农历月(月禽/投胎):域外(BC/万年后)由调用方经远程桥注入 payload.lunarMonth(lunar-js 域外静默错);
	// 域内走 lunar-js;两者皆缺则退公历月兜底不崩。
	let lunarMonth = (payload.lunarMonth && payload.lunarMonth > 0) ? payload.lunarMonth : payload.month;
	if (!(payload.lunarMonth > 0) && isLunarJsYearReliable(payload.year)) {
		try { lunarMonth = mod(Math.abs(Solar.fromYmd(payload.year, payload.month, payload.day).getLunar().getMonth()) - 1, 12) + 1; } catch (e) { /* fallback */ }
	}
	const cast = castQinChart(payload.year, payload.month, payload.day, hourBranch, { useXun: s.xunOffset, huoYaoVariant: s.huoYaoVariant });
	if (!cast || !cast.dayQin) { return ''; }
	const mq = monthQin(payload.year, lunarMonth, s.monthVerse);
	const di = ZHIRI_JIXIONG.find((x) => x.head === cast.dayQin.name[0]) || {};
	const r = resolveWoBi(s);
	const ent = { shi: cast.hourQin, fan: cast.fanQin, dao: cast.daoJiang ? cast.daoJiang.zhuJiang : null };
	const me = ent[r.me]; const they = ent[r.they];
	const ke = (me && they) ? KE_TEXT[qinKeByWuxing(wuxingOfMansion(me), wuxingOfMansion(they))] : '—';
	const bird = toutaiDu(lunarMonth, hourBranch);
	const school = (YANQIN_PRESETS[s.school] || {}).label || s.school;
	const lines = [
		`[演法·流派] ${school};${r.note};月禽口诀${s.monthVerse}版、旬头位移${s.xunOffset ? '加' : '不加'}、活曜${s.huoYaoVariant}`,
		`[演法·起禽] ${cast.ganzhi}日 · ${cast.yuan}元${cast.jiang}将 · ${cast.weekday}曜;年禽${cast.yearQin.name}、月禽${mq.name}、日禽${cast.dayQin.name}、时禽${cast.hourQin.name}、翻禽${cast.fanQin.name}${cast.daoJiang ? '、倒将' + cast.daoJiang.zhuJiang.name : ''}${cast.huoYao ? '、活曜' + cast.huoYao.name : ''}`,
		`[演法·择日] 值日宿 ${cast.dayQin.name}(${di.nature || '—'});宜${di.yi || '—'}/忌${di.ji || '—'}`,
		`[演法·占卜] 三传:日${cast.dayQin.name}/时${cast.hourQin.name}/翻${cast.fanQin.name};我${me ? me.name : '—'}/彼${they ? they.name : '—'} → ${ke}`,
		`[演法·投胎] 农历${lunarMonth}月${DIZHI[hourBranch]}时 → ${bird}`,
	];
	return lines.join('\n');
}
