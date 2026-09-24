// 跨技法「时间基准」自声明(单源):各技法 [起盘信息] 段追加一行,让 AI 与读者知道这张盘的日柱/宫位
// 是按哪种时间口径起的——八字默认真太阳时(经度+均时差校正),七政/占星按输入钟面时刻与时区换算,
// 同一个 23:40 出生在不同技法里日柱可差一柱(例:八字丁酉 vs 七政戊戌),这是口径差异而非计算错误。
// 只追加一行、不改既有字段顺序;消费方:cntradition/BaZi.js、guolao/GuoLaoChartMain.js、astroAiSnapshot.js。
const TIME_ALG_LABEL = Object.freeze({ '0': '真太阳时(经度+均时差校正)', '1': '钟表时(按输入钟面时刻,无真太阳时校正)', '2': '春分定卯时', '3': '平太阳时(仅经度校正,无均时差)' });

export function timeBasisLabel(timeAlg){
	if(timeAlg === undefined || timeAlg === null || `${timeAlg}` === ''){
		return TIME_ALG_LABEL['1'];
	}
	return TIME_ALG_LABEL[`${timeAlg}`] || `${timeAlg}`;
}

function yesNo(v, fallback){
	if(v === undefined || v === null || `${v}` === ''){
		return fallback;
	}
	return (v === 0 || v === '0' || v === false) ? '否' : '是';
}

// 返回单行文本;参数缺位按各技法惯例给缺省(晚子时归次日=否、23 点换日=否 与 BaZi.js 默认口径一致)。
// [Q-191/T-134] note:同一张盘里存在第二种时标时的补注(如七政:盘面按钟面时,四柱另按真太阳时)。
// 不传 = 旧行逐字节不变。
export function buildTimeBasisLine({ timeAlg, lateZiHourUseNextDay, after23NewDay, zone, note } = {}){
	const parts = [`时间基准：${timeBasisLabel(timeAlg)}`];
	parts.push(`晚子时归次日：${yesNo(lateZiHourUseNextDay, '否')}`);
	parts.push(`23 点换日：${yesNo(after23NewDay, '否')}`);
	if(zone !== undefined && zone !== null && `${zone}` !== ''){
		parts.push(`时区：${zone}`);
	}
	if(note !== undefined && note !== null && `${note}` !== ''){
		parts.push(`${note}`);
	}
	return parts.join('；');
}

// 七政专用补注:本页一张盘上真有两套时标 —— 盘面星体/宫位按输入钟面时刻换算,
// 而四柱由排盘服务按真太阳时(经度+均时差)查表另算,琴堂逢酉身宫的时支又按钟面时取。
// 只写一种会让读者/AI 以为四柱也是钟面时(同一时刻可差一柱)。
export const GUOLAO_TIME_BASIS_NOTE = '本页两套时标：盘面星体与宫位按上列基准；四柱由排盘服务按真太阳时(经度+均时差)另算；琴堂逢酉身宫的时支按钟面时刻取';
