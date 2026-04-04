import * as LRConst from '../liureng/LRConst.js';

function normalizeZiFromText(text){
	const txt = `${text || ''}`;
	for(let i=0; i<txt.length; i++){
		const one = txt.substr(i, 1);
		if(LRConst.ZiList.indexOf(one) >= 0){
			return one;
		}
	}
	return '';
}

export function resolveJinKouDiFen(currentDiFen, diFenAuto, timeZi, hasExistingPan){
	const currentZi = normalizeZiFromText(currentDiFen);
	const timeBranch = normalizeZiFromText(timeZi);
	if(!diFenAuto){
		return currentZi || timeBranch || LRConst.ZiList[0];
	}
	if(!hasExistingPan){
		return timeBranch || currentZi || LRConst.ZiList[0];
	}
	return currentZi || timeBranch || LRConst.ZiList[0];
}
