// 逆位五种解法（古籍 3.3 + 6.11）：据模板从正位义动态生成逆位文案。
// settings.reversalMode 默认 'stored'（用预存逆位义，即牌义表里那一栏，零回归）；
// 其余五模式据正位义变换（opposite 用预存反义，其余在正位义上叠一层修饰）。
export const REVERSAL_MODES = ['stored', 'blocked', 'internal', 'opposite', 'reduced', 'excess'];

export const REVERSAL_TEMPLATES = {
	blocked: { label: '受阻/延迟', note: '正位能量受阻、延迟', tpl: (up) => `${up}——但能量受阻、延迟` },
	internal: { label: '内化/私密', note: '能量转向内在、私密', tpl: (up) => `${up}——转向内在、私密地体验` },
	opposite: { label: '相反/反义', note: '取正位反义（预存逆位义）', tpl: (up, down) => down },
	reduced: { label: '减弱', note: '正位能量变弱、程度变轻', tpl: (up) => `${up}（减弱、程度变轻）` },
	excess: { label: '过度/失衡', note: '正位能量过载、失衡', tpl: (up) => `${up}——过度、失衡、过犹不及` },
};

// 生成逆位文案。upText=正位义文案, storedRevText=预存逆位义文案, mode∈REVERSAL_MODES。
export function reversedText(upText, storedRevText, mode){
	if(!mode || mode === 'stored'){ return storedRevText; }
	const t = REVERSAL_TEMPLATES[mode];
	if(!t){ return storedRevText; }
	return t.tpl(upText || '', storedRevText || '');
}
