// 农历月前的「闰」字(单源):历法服务回的 month 不带「闰」(另给 leap 标志),本地历算(lunar-javascript)回的
// month 已带「闰」(如「闰六月」)且 leap 也为真 —— 照旧「leap ? '闰' : ''」拼在前面会写成「闰闰六月」。
// 只在 month 自己没带「闰」时补。
export function leapPrefix(nongli){
	if(!nongli || !nongli.leap){ return ''; }
	return `${nongli.month || ''}`.indexOf('闰') === 0 ? '' : '闰';
}

// 农历月名(带「月」与闰):本地历算的月名已是「闰六月」「二月」,远端可能只给「六」;两种都排成「闰六月」/「六月」
export function lunarMonthLabel(nongli){
	const m = `${(nongli && nongli.month) || ''}`;
	if(!m){ return '?月'; }
	return `${leapPrefix(nongli)}${/月$/.test(m) ? m : `${m}月`}`;
}
