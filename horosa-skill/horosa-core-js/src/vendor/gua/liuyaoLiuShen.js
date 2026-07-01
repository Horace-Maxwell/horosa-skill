// 六爻六神取象 + 错综卦(WP-H)。六神按日干起(青龙序),取象忠于古典类象(§5.x);错卦=阴阳全变、综卦=上下颠倒。
import { littleEndian } from './guaHelper.js';
import { getGua64 } from './GuaConst.js';
import { LIUSHEN_CYCLE, LIUSHEN_START } from './LiuYaoConst.js';

// 六神取象(五行/静象/发动象)
export const LIUSHEN_XIANG = {
	青龙: { wuxing: '木', xiang: '吉庆、喜事、酒色、正财、端正、东方', fadong: '喜庆酒色财喜婚孕之吉(旺);酒色耗财(衰)' },
	朱雀: { wuxing: '火', xiang: '口舌、文书、信息、官非、南方', fadong: '口舌是非、文书信息、官非词讼' },
	勾陈: { wuxing: '土', xiang: '田土、房产、牵连、迟滞、中央', fadong: '田土房产、勾连牵缠、迟滞、牢狱之事' },
	螣蛇: { wuxing: '土', xiang: '虚惊、怪异、缠绕、噩梦、变化、心绪不宁', fadong: '虚惊怪梦、忧疑缠绕、心神不宁、怪异' },
	白虎: { wuxing: '金', xiang: '凶丧、疾病、血光、道路、刚猛、西方', fadong: '疾病丧服、血光道路、争斗、孝服(旺则威武)' },
	玄武: { wuxing: '水', xiang: '盗贼、暧昧、私情、阴私、暗昧、北方', fadong: '盗贼遗失、暧昧私情、阴私欺诈' },
};

// 按日干起六神(初爻→上爻,共6)
export function liuShenByDay(dayGan){
	const start = LIUSHEN_START[dayGan];
	if(!start){ return []; }
	const si = LIUSHEN_CYCLE.indexOf(start);
	return [0, 1, 2, 3, 4, 5].map((i) => LIUSHEN_CYCLE[(si + i) % 6]);
}

// 逐爻标注六神 + 取象
export function annotateLiuShen(yaos, dayGan){
	const six = liuShenByDay(dayGan);
	return (yaos || []).map((y, i) => {
		const name = six[i] || '';
		const meta = LIUSHEN_XIANG[name] || null;
		return { pos: y.pos != null ? y.pos : i + 1, liushen: name, xiang: meta ? meta.xiang : '', fadong: meta ? meta.fadong : '' };
	});
}

// ── 错卦(阴阳全变)/综卦(上下颠倒) ──
export function cuoGuaOf(gua){
	if(!gua || !gua.value){ return null; }
	return getGua64(littleEndian(gua.value.map((v) => (v ? 0 : 1))));
}
export function zongGuaOf(gua){
	if(!gua || !gua.value){ return null; }
	return getGua64(littleEndian(gua.value.slice().reverse()));
}
// 互卦(2-4 爻为下、3-5 爻为上)
export function huGuaOf(gua){
	if(!gua || !gua.value){ return null; }
	const v = gua.value;
	// 自下而上 [初,二,三,四,五,上];互卦下卦=二三四、上卦=三四五
	const hu = [v[1], v[2], v[3], v[2], v[3], v[4]];
	return getGua64(littleEndian(hu));
}
