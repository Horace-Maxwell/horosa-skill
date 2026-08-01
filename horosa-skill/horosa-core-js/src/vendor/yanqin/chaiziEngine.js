// 演禽 · 拆字演禽(八门演禽)独立起盘引擎(WP-20)。纯函数,不碰四禽主引擎。
// 古籍(太古演禽/八门禽遁):七星拆字法——笔画配七政,报数起遇星、逐笔配政得流星、末笔得主星,配八门断。
import { MANSIONS, mansionByIdx } from './yanqinConst.js';

// —— 笔画 → 七政曜 ✅ 古籍 ——:「撇为金,竖为木,点为水,捺为火,横为土,日为日,月为月」。
export const STROKE_TO_YAO = { 撇: '金', 竖: '木', 点: '水', 捺: '火', 横: '土', 日: '日', 月: '月' };
export const STROKE_LABELS = { 撇: '丿撇·金', 竖: '丨竖·木', 点: '丶点·水', 捺: '㇏捺·火', 横: '一横·土', 日: '日部·日', 月: '月部·月' };

// 从 startIdx(1-28) 顺数,到下一个曜==targetYao 的宿,返回其 idx(不含起点)。
function nextMansionOfYao(startIdx, targetYao) {
	for (let k = 1; k <= 28; k += 1) {
		const idx = ((startIdx - 1 + k) % 28) + 1;
		if (MANSIONS[idx - 1].yao === targetYao) { return idx; }
	}
	return startIdx;
}

// 报数 → 遇星(彼/对方):数 mod28,从角(1)顺数到余数。
export function yuXingByNumber(num) {
	const n = (((Math.round(num) % 28) + 28) % 28) || 28; // 1..28(0→28)
	return mansionByIdx(n);
}

// 拆字起盘。num=所报数;strokeYaos=笔顺的七政曜数组(如 '木'字=['土','木','金','火'])。
// 返回 { yuXing 遇星(彼), liuXing 流星(过程,逐笔), zhuXing 主星(我·末笔) }。
// 断法:主星=我/体、遇星=彼/用、日禽=彼我共用、流星=过程;看三星五行生克 + 禽性吞啖锁泊格局。
export function chaiziChart(num, strokeYaos) {
	const yu = yuXingByNumber(num);
	let cur = yu.idx;
	const liu = [];
	(strokeYaos || []).forEach((yao) => {
		cur = nextMansionOfYao(cur, yao);
		liu.push(mansionByIdx(cur));
	});
	const zhu = liu.length ? liu[liu.length - 1] : yu;
	return { yuXing: yu, liuXing: liu, zhuXing: zhu };
}

// —— 八门(结合事类方向与吉凶加权)✅ 古籍 ——:开休生三吉、死惊伤三凶、杜景中性。
export const BAMEN = [
	{ name: '开', ji: '吉', use: '求官 / 远行 / 见贵 / 开张' },
	{ name: '休', ji: '吉', use: '休憩 / 婚姻 / 和合 / 交友' },
	{ name: '生', ji: '吉', use: '求财 / 生产 / 种作 / 谒贵' },
	{ name: '伤', ji: '凶', use: '捕猎 / 索债 / 争斗 / 追逃' },
	{ name: '杜', ji: '中', use: '藏隐 / 闭塞 / 避难 / 遁形' },
	{ name: '景', ji: '中', use: '文书 / 宴乐 / 音信 / 考试' },
	{ name: '死', ji: '凶', use: '丧葬 / 刑狱 / 田猎 / 吊问' },
	{ name: '惊', ji: '凶', use: '词讼 / 惊恐 / 口舌 / 擒捕' },
];
