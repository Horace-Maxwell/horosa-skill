// 飞宫小奇门 AI 段表 builder（自 星阙 FeiGongMain.buildFeiGongSnapshotText 逐字提取，headless）。
// 段表与 aiExport 逐字一致：问事/起局/干支/命宫/宫位/运气/应期。
import { mingGong, liuNian, liuYue } from './feigongJu.js';
import { zhuKe, gongDuan, menDuan, shenDuan, xingDuan, wuXingOf, shengKeRel, xingShenSunYi, yingQi, shiXiangKey } from './feigongDuan.js';
import { GAN, GONG_GUA, FANG_WEI_RING, BA_MEN_JI_XIONG, YUAN_SHEN_JI_XIONG } from './feigongConst.js';

export function buildFeiGongSnapshotText(ju, opts) {
	if (!ju) { return ''; }
	const o = opts || {};
	const out = [];
	out.push('[问事]');
	out.push(o.askEvent ? `所问:${o.askEvent}` : '(未录问事)');
	out.push('');
	out.push('[起局]');
	((o.timeLines) || []).forEach((l) => out.push(l));
	out.push(`起支:${ju.qiZhi};建星起于${ju.jianZhi};青龙(甲)落 ${ju.longGong} 宫`);
	out.push('');
	out.push('[干支]');
	out.push(`甲乘龙飞九宫:${GAN.map((g) => `${g}${ju.tianGan.ganGong[g] != null ? ju.tianGan.ganGong[g] : '中'}`).join(' ')}`);
	out.push(`中宫双干:${(ju.tianGan.zhongGong || []).join('')}(五十居中)`);
	out.push(`八门:休门起 ${ju.baMen.xiuMenGong} 宫;${Object.keys(ju.baMen.menGong || {}).map((m) => `${m}${ju.baMen.menGong[m]}`).join(' ')}`);
	out.push('');
	out.push('[命宫]');
	let mgSaved = null;
	if (o.mingAge) {
		const mg = mingGong({ age: o.mingAge, gender: o.mingGender || 'male', ju });
		mgSaved = mg;
		if (mg.gong != null) {
			out.push(`年龄 ${o.mingAge}(${o.mingGender === 'female' ? '女' : '男'}):调整数 ${mg.adjusted},命宫 ${mg.gong}(${GONG_GUA[mg.gong] || '中'})${mg.zhiWu && mg.via ? `,值五宫看${mg.via.join('转')}` : ''}`);
		} else {
			out.push(`年龄 ${o.mingAge}:${(mg.flags || []).join(';') || '不可定宫'}`);
		}
		(mg.flags || []).forEach((f) => { if (mg.gong != null) { out.push(`注:${f}`); } });
	} else {
		out.push('(未录年龄,不定命宫)');
	}
	out.push('');
	out.push('[宫位]');
	const zk = zhuKe(ju);
	if (zk && (zk.zhuGong != null || zk.keGong != null)) {
		out.push(`主(日干${ju.dayGan || '—'})落 ${zk.zhuGong != null ? zk.zhuGong : '—'} 宫;客(日支${ju.dayZhi || '—'})落 ${zk.keGong != null ? zk.keGong : '—'} 宫`);
	} else {
		out.push('(未录日干支,主客不定)');
	}
	FANG_WEI_RING.forEach((g) => {
		const gd = gongDuan(ju, g);
		if (!gd) { return; }
		out.push(`${g}${gd.gua}宫 门${gd.men || '—'} 干${(gd.gan || []).join('') || '—'} | ${gd.zhis.map((z) => `${z.zhi}·${z.shen}·${z.xing}`).join(' ')}`);
	});
	out.push('');
	out.push('[运气]');
	if (zk && zk.zhuGong != null && zk.keGong != null) {
		const zg = gongDuan(ju, zk.zhuGong); const kg = gongDuan(ju, zk.keGong);
		if (zg && zg.men) { out.push(`主宫${zk.zhuGong} 得${zg.men}门(${BA_MEN_JI_XIONG[zg.men] || ''}):${(menDuan(zg.men) || {}).ti || ''}`); }
		if (kg && kg.men) { out.push(`客宫${zk.keGong} 得${kg.men}门(${BA_MEN_JI_XIONG[kg.men] || ''}):${(menDuan(kg.men) || {}).ti || ''}`); }
	} else { out.push('—'); }
	if (ju.dayZhi) {
		const ln = liuNian({ dayZhi: ju.dayZhi, gender: o.mingGender || 'male', maxAge: 12, ju });
		if (ln.length) { out.push(`流年(日支${ju.dayZhi}起·${o.mingGender === 'female' ? '女逆' : '男顺'}):${ln.map((y) => `${y.age}岁${y.zhi}(${y.gong}宫·${y.shen}·${y.xing}·${y.men}门)`).join(' ')}`); }
	}
	{
		const lm = o.liuYueMonth || 1;
		const ly = liuYue({ ju, monthNum: lm });
		if (ly) {
			let rel = null; let sunyi = null;
			if (mgSaved && mgSaved.gong != null) {
				rel = shengKeRel(wuXingOf(ly.zhi), wuXingOf(GONG_GUA[mgSaved.gong]));
				if (rel) { sunyi = xingShenSunYi(YUAN_SHEN_JI_XIONG[ly.shen], rel); }
			}
			out.push(`流月(${['正', '二', '三', '四', '五', '六', '七', '八', '九', '十', '十一', '十二'][lm - 1]}月建${ly.zhi}):${ly.gong}宫·${ly.shen}·${ly.xing}·${ly.men}门${rel ? `;月对命宫:${rel}${sunyi ? `(${sunyi})` : ''}` : ''}`);
		}
	}
	out.push('');
	out.push('[应期]');
	out.push(`建星:${ju.jianZhi} 起建,建除十二神随支顺布(以天星所临断应期缓急)。`);
	if (ju.dayZhi && ju.yuanShen[ju.dayZhi]) {
		const sd = shenDuan(ju.yuanShen[ju.dayZhi]) || {};
		out.push(`日支${ju.dayZhi} 原神${ju.yuanShen[ju.dayZhi]}(${YUAN_SHEN_JI_XIONG[ju.yuanShen[ju.dayZhi]] || ''}):${sd.text || ''}`);
	}
	if (ju.dayZhi && ju.tianXing[ju.dayZhi]) {
		const xd = xingDuan(ju.tianXing[ju.dayZhi], o.koujing) || {};
		out.push(`日支${ju.dayZhi} 临 ${ju.tianXing[ju.dayZhi]}${xd.alias ? `(${xd.alias})` : ''}:${xd.text || ''}`);
	}
	const yq = yingQi(ju);
	if (yq) { out.push(`中宫${yq.zhongGong.join('')} → ${yq.shi}${yq.yiMa ? '(驿马·动)' : yq.dingShi ? '(定时·合)' : ''};${yq.note}`); }
	if (o.askEvent) { const sx = shiXiangKey(o.askEvent, { heKuiKoujing: o.koujing }); if (sx) { out.push(`事项:${sx.hint}`); } }
	return out.join('\n').trim();
}
