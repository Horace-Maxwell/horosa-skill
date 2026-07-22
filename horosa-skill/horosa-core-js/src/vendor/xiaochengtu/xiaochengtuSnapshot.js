// 小成图 AI 段表 builder（自 星阙 XiaoChengTuMain.buildXiaoChengTuSnapshotText 逐字提取，headless）。
// 段表：问事/起卦/佈局/推导/四象/应期（+股市，仅 qi.mode==='stock' 出）。LUOSHU_ROWS 为 Main.js
// 模块级 const（洛书九宫排布），须一并提取（闭包陷阱①）。
import { zhengTuiText, tuiDao, shuZhan, siXiangOfHex, fuDu, zhangDie, sanFen, liangFen, klineYongGong } from './xiaochengtuPan.js';
import { DI_PAN, ZHONG_GONG_NOTE, SI_XIANG_BASE, GONG_INFO } from './xiaochengtuConst.js';

const LUOSHU_ROWS = [[4, 9, 2], [3, 5, 7], [8, 1, 6]]; // 洛书九宫排布(5 中宫无卦)

export function buildXiaoChengTuSnapshotText(pan, qi, opts) {
	if (!pan || !qi) { return ''; }
	const o = opts || {};
	const g0 = Number(o.yongGong) || 1;
	const out = [];
	out.push('[问事]');
	out.push(o.askEvent ? `所问:${o.askEvent}` : '(未录问事)');
	out.push('');
	out.push('[起卦]');
	((o.timeLines) || []).forEach((l) => out.push(l));
	out.push(`本卦:${qi.ben.name};之卦:${qi.zhi.name};动爻:${(qi.dongYaos || []).join('、') || '无'}`);
	(qi.steps || []).forEach((s) => { out.push(`${s.label}:${s.detail} → ${s.value}`); });
	out.push('');
	out.push('[佈局]');
	LUOSHU_ROWS.forEach((row) => {
		out.push(row.map((g) => (g === 5 ? '五(中)' : `${g}${pan.tianPan[g] || '—'}`)).join(' | '));
	});
	out.push(ZHONG_GONG_NOTE);
	out.push('');
	out.push('[推导]');
	if (GONG_INFO[g0]) { out.push(`用宫所主:${g0}宫${GONG_INFO[g0].gua}(${GONG_INFO[g0].fangwei}·${GONG_INFO[g0].yue}),宫主${GONG_INFO[g0].zhu}`); }
	const td = tuiDao(pan, g0);
	if (td) {
		out.push(`用宫 ${g0}(${DI_PAN[g0]}):${zhengTuiText(td)}`);
		if (td.pang) { out.push(`伏位旁推:${zhengTuiText(td.pang) || '—'}`); }
	} else { out.push('用宫非法,不可推导。'); }
	out.push('');
	out.push('[四象]');
	const sxB = siXiangOfHex(qi.ben);
	const sxZ = siXiangOfHex(qi.zhi);
	if (sxB) { out.push(`本卦${qi.ben.name}:${sxB.type}(${SI_XIANG_BASE[sxB.type] || ''}·${sxB.yi};${sxB.dePei ? '得配' : '失配'}:${sxB.ci})`); }
	if (sxZ) { out.push(`之卦${qi.zhi.name}:${sxZ.type}(${SI_XIANG_BASE[sxZ.type] || ''}·${sxZ.yi};${sxZ.dePei ? '得配' : '失配'}:${sxZ.ci})`); }
	out.push('');
	out.push('[应期]');
	const sz = shuZhan(pan, g0);
	if (sz && sz.sum != null) { out.push(`数占:正推链宫数相加 = ${sz.sum}(问数以数应)`); }
	else if (sz && sz.fuWei) { out.push('伏位不动,数占无链和;参旁推。'); }
	else { out.push('—'); }
	const ygGua = pan.tianPan[g0];
	const sf = ygGua ? sanFen(ygGua) : null;
	const lf = ygGua ? liangFen(ygGua) : null;
	if (sf) { out.push(`三分定旬:用宫得${ygGua}卦 → ${sf.xun}旬`); }
	if (lf) { out.push(`两分定半月:用宫得${ygGua}卦 → ${lf.ban}月(${lf.yy})`); }
	if (qi.mode === 'stock') {
		out.push('');
		out.push('[股市]');
		const openGua = pan.tianPan[g0];
		const tdS = tuiDao(pan, g0);
		const closeGua = tdS && !tdS.fuWei && tdS.steps && tdS.steps.length ? tdS.steps[tdS.steps.length - 1].tianGua : (tdS && tdS.pang ? tdS.pang.gua : openGua);
		if (openGua) { out.push(`研判·开盘:用宫天盘${openGua} → ${zhangDie(openGua) || '—'}(幅度${(fuDu(openGua) || {}).fudu || '—'})`); }
		if (closeGua) { out.push(`研判·收盘:正推末卦${closeGua} → ${zhangDie(closeGua) || '—'}(幅度${(fuDu(closeGua) || {}).fudu || '—'})`); }
		const fd = fuDu(qi.ben.up);
		const zd = zhangDie(qi.ben.up);
		if (fd) { out.push(`幅度三分:${fd.gua} 主爻位 ${fd.zhuYao} · 幅度${fd.fudu}`); }
		if (zd) { out.push(`涨跌两分:上卦${qi.ben.up} → ${zd}`); }
		if (o.kline && o.kline.body) {
			const ky = klineYongGong(o.kline);
			out.push(ky ? `K线定用宫:${ky.key} → ${ky.gua}宫(${ky.gong})` : 'K线十字星判空,不定用宫。');
		}
	}
	return out.join('\n').trim();
}
