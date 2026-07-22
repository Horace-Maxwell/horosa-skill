// 小六壬 AI 段表 builder（自 星阙 XiaoLiuRenMain.buildXiaoLiuRenSnapshotText 逐字提取，headless）。
// 段表与 aiExport 逐字一致：问事/起课/三传/生克/九神/化解。主流六宫无五行生克（shengke 段如实标注）。
import { teLi } from './xiaoliurenKe.js';
import {
	MAIN_RING, DAO_RING, DAO_NINE, DAO_YI,
	STAGE_ROLES, ACROSS_NOTE, BING_FU_DISCREPANCY_NOTE,
} from './xiaoliurenConst.js';

export function buildXiaoLiuRenSnapshotText(ke, askEvent, snapOpts) {
	if (!ke || !Array.isArray(ke.chuan)) { return ''; }
	const a = ke.analysis || {};
	const out = [];
	out.push('[问事]');
	out.push(askEvent ? `所问:${askEvent}` : '(未录问事)');
	out.push('');
	out.push('[起课]');
	((snapOpts && snapOpts.timeLines) || []).forEach((l) => out.push(l));
	out.push(`流派:${ke.school === 'dao' ? '道门九宫' : '主流六宫'};三数:${(ke.nums || []).join('、')}(月/日/时,作一顺数自大安起)`);
	out.push('');
	out.push('[三传]');
	ke.chuan.forEach((c, i) => {
		const nine = DAO_NINE[c];
		const extra = ke.school === 'dao' && nine ? `(${nine.gua}${nine.wuxing})` : '';
		out.push(`第${['一', '二', '三'][i]}传 ${c}${extra} —— ${STAGE_ROLES[i]}`);
	});
	out.push('');
	out.push('[生克]');
	if (ke.school !== 'dao') {
		out.push('主流六宫不调取五行生克(判读以各宫吉凶直断)。');
	} else if ((a.pairs || []).length) {
		a.pairs.forEach((p) => { out.push(`${p.relText} → ${p.duan || p.rel}`); });
		if (a.across && !(snapOpts && snapOpts.showOneThree === false)) { out.push(`一↔三:${a.across.rel}(${ACROSS_NOTE})`); }
	} else {
		out.push('相邻两传无生克(比和或无关)。');
	}
	out.push('');
	out.push('[九神]');
	const ring = ke.school === 'dao' ? DAO_RING : MAIN_RING;
	ring.forEach((n) => {
		const nine = DAO_NINE[n];
		const yi = DAO_YI[n];
		out.push(`${n}${ke.school === 'dao' && nine ? `(${nine.gua}${nine.wuxing})` : ''}:${yi || '—'}`);
	});
	if (ke.school === 'dao') { out.push(BING_FU_DISCREPANCY_NOTE); }
	out.push('');
	out.push('[化解]');
	const bj = (a.baiJie || []);
	if (bj.length) { bj.forEach((b) => { out.push(`${b.victim}被${b.aggressor}克 → 拜${b.bai}化解`); }); }
	else { out.push('本课无被克之传,无需拜解。'); }
	const tl = teLi(ke.chuan);
	if (tl.length) { out.push(...tl.map((t) => `特例:${t.text}`)); }
	return out.join('\n').trim();
}
