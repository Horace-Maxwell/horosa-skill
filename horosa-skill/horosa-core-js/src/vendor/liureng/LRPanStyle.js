import * as LRConst from './LRConst.js';

const TWELVE_PAN_STYLE_NAMES = [
	'伏吟式',
	'进连茹式',
	'进间传式',
	'生胎式',
	'顺三合式',
	'四墓覆生式',
	'反吟式',
	'四绝体式',
	'逆三合式',
	'病胎式',
	'退间传式',
	'退连茹式',
];

const TWELVE_PAN_STYLE_DISTANCE_LABELS = [
	'原位',
	'前一',
	'前二',
	'前三',
	'前四',
	'前五',
	'前六',
	'前七',
	'前八',
	'前九',
	'前十',
	'前十一',
];

function normalizeBranch(raw){
	const txt = `${raw || ''}`;
	for(let i=txt.length - 1; i>=0; i--){
		const ch = txt.substr(i, 1);
		if(LRConst.ZiList.indexOf(ch) >= 0){
			return ch;
		}
	}
	return '';
}

export function resolveLiuRengTwelvePanStyle(yueBranch, timeBranch){
	const yue = normalizeBranch(yueBranch);
	const time = normalizeBranch(timeBranch);
	if(!yue || !time){
		return null;
	}
	const yueIndex = LRConst.ZiList.indexOf(yue);
	const timeIndex = LRConst.ZiList.indexOf(time);
	if(yueIndex < 0 || timeIndex < 0){
		return null;
	}
	const distance = (yueIndex - timeIndex + 12) % 12;
	return {
		index: distance,
		name: TWELVE_PAN_STYLE_NAMES[distance] || '',
		distanceLabel: TWELVE_PAN_STYLE_DISTANCE_LABELS[distance] || '',
		yueBranch: yue,
		timeBranch: time,
	};
}

