// 逆位解读模式(五书补齐 TP1:6→13)。据模板从正位义动态生成逆位文案;'retreat' 为引擎型(需查前一号牌,实现在 cardSchema.retreatText)。
// settings.reversalMode 默认 'stored'(用预存逆位义,零回归);其余模式在正位义上叠一层解读透镜。
// 模式谱系=古典逆位方法学的合并去重:阻碍/内向/反义/减弱/过度(原五式,blocked 原兼「延迟」义现拆出)+延迟时机/投射/误用/否定/突破解脱/回撤重审/回退前课(新七式)。
export const REVERSAL_MODES = [
	'stored', 'blocked', 'internal', 'opposite', 'reduced', 'excess',
	'delayed', 'projection', 'misuse', 'negation', 'breakthrough', 're_words', 'retreat',
];

export const REVERSAL_TEMPLATES = {
	blocked: { label: '受阻/压抑', note: '正位能量受阻、被压抑或否认', tpl: (up) => `${up}——但能量受阻、被压抑或否认` },
	internal: { label: '内化/私密', note: '能量转向内在、私密', tpl: (up) => `${up}——转向内在、私密地体验` },
	// [QA-1] 原 tpl 直接返回预存逆位义 → 与 'stored' 档逐字全等 = 死开关(切了无反应)。
	// 两档实为不同取义路径:stored=照牌义表既有的逆位栏读;opposite=宣告「把正位反过来」并与正位并陈以便对照,
	// 且在牌义表无预存逆位栏时(如马赛数字度轨的部分牌)仍可成文,而 stored 会落空。
	opposite: { label: '相反/反义', note: '把正位义反过来读(与正位并陈对照)', tpl: (up, down) => (down ? `反于正位「${up}」:${down}` : `反于正位「${up}」`) },
	reduced: { label: '减弱', note: '正位能量变弱、程度变轻', tpl: (up) => `${up}（减弱、程度变轻）` },
	excess: { label: '过度/失衡', note: '正位能量过载、失衡', tpl: (up) => `${up}——过度、失衡、过犹不及` },
	delayed: { label: '延迟/时机', note: '方向不变,时机未熟、进程放缓', tpl: (up) => `${up}——但延迟、时机未熟:门将开未开,需等待与额外一把力` },
	projection: { label: '投射', note: '把此能量投射到了别人身上', tpl: (up) => `${up}——此能量或正被投射于他人:先在对方身上认出它,再收回自身` },
	misuse: { label: '误用/错向', note: '能量对准了错误的目标或方向', tpl: (up) => `${up}——但用错了方向或对象:力没少出,靶子错了,需校准` },
	negation: { label: '不是/没有', note: '在正位义前加「不是/没有」', tpl: (up) => `不是/没有:${up}` },
	breakthrough: { label: '突破/解脱', note: '正在挣脱、颠覆、离开此处境', tpl: (up) => `正在挣脱与转向:与「${up}」相关的处境松动、消融或告一段落` },
	re_words: { label: '回撤/重审', note: '回顾、重考、收回、再来一次(类比行星逆行)', tpl: (up) => `${up}——转入回撤与重审:回顾、重新考虑、收回、再做一次` },
	// retreat 回退前课:逆位=未修完「前一号牌」的正位课题(数字牌回同花色前一号;王牌回同花色十;大牌回前一号;宫廷不入链)。
	// 文案由 cardSchema.retreatText 按当前牌义体系动态生成;此处仅登记 label/note 供 UI。
	retreat: { label: '回退前课', note: '逆位=未修完前一号牌的课题(王牌回十;宫廷不入链)', tpl: null },
};

// UI 分组(逆位读法下拉):通行六式 / 进阶七式。
export const REVERSAL_MODE_GROUPS = [
	{ group: '通行', items: ['stored', 'blocked', 'internal', 'opposite', 'reduced', 'excess'] },
	{ group: '进阶', items: ['delayed', 'projection', 'misuse', 'negation', 'breakthrough', 're_words', 'retreat'] },
];

// 生成逆位文案(模板型)。upText=正位义, storedRevText=预存逆位义, mode∈REVERSAL_MODES。
// 'retreat' 属引擎型,不在此处理(cardSchema.cardMeaning 分派);tpl 缺失时回落预存义,恒不抛。
export function reversedText(upText, storedRevText, mode){
	if(!mode || mode === 'stored'){ return storedRevText; }
	const t = REVERSAL_TEMPLATES[mode];
	if(!t || !t.tpl){ return storedRevText; }
	return t.tpl(upText || '', storedRevText || '');
}
