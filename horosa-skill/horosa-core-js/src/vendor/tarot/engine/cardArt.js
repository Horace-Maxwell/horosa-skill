// 真实牌面美术(可选)。仅用公有领域牌面。
// 简约符号美术为默认;用户可切「真实牌面」。<img> onError 优雅回退符号(离线/失败/无图不崩)。
// 已接入(均公有领域),全部本地打包(public/tarot-art/),桌面离线可用:
//   · RWS(Pamela Colman Smith,1909)— 全 78 张(按 rwsCode 命名)。
//   · 马赛 TdM(Nicolas Conver,1760)— 22 大牌(按 sid)。
//   · 维尔特(Oswald Wirth,1889)— 22 大牌(按 sid;本即 22 张大牌牌组,完整)。
//   · 埃及式(Falconnier,1896)— 22 大牌(按 sid;大陆序 Fool=21,已逐图视觉核验)。
// 上述 22 大牌制牌组的「78 张」变体只接大牌,花色小牌无成套 PD 单卡扫描 → 回退符号。
// 托特(1944)/BOTA/现代金色黎明牌仍在版权保护期,不接入真实牌面。

const SUIT_CODE = { wands: 'wa', cups: 'cu', swords: 'sw', pentacles: 'pe' };
const COURT_CODE = { page: 'pa', knight: 'kn', queen: 'qu', king: 'ki' };

function rwsCode(card){
	if(card.arcana === 'major'){ return `ar${String(card.number).padStart(2, '0')}`; }
	const sc = SUIT_CODE[card.suit];
	if(!sc){ return null; }
	if(card.court){ return COURT_CODE[card.court] ? `${sc}${COURT_CODE[card.court]}` : null; }
	if(card.number === 1){ return `${sc}ac`; }
	if(card.number >= 2 && card.number <= 10){ return `${sc}${String(card.number).padStart(2, '0')}`; }
	return null;
}

// 本地打包牌面清单(public/tarot-art/<deck>/);相对路径(同 planetarium 资源,兼容 web /static 与桌面 ./)。
// major: 大牌按 card.sid 出图(规避马赛序与 RWS 序的编号差异);minorPips/minorCourts: 小牌是否有本地图(无则回退符号)。
const LOCAL_ART = {
	tdm: { base: 'tarot-art/tdm/', majors: true, minorPips: false, minorCourts: false },     // Conver 1760,22 大牌
	wirth: { base: 'tarot-art/wirth/', majors: true, minorPips: false, minorCourts: false }, // Oswald Wirth 1889,22 大牌(本即 22 张)
	egyptian: { base: 'tarot-art/egyptian/', majors: true, minorPips: false, minorCourts: false }, // Falconnier 1896,22 大牌(大陆序 Fool=21)
};

// 牌面图片 URL;无真实牌面则返回 null(渲染回退符号)。
export function cardImageUrl(deckId, card){
	if(!card){ return null; }
	if(deckId === 'rws'){
		const code = rwsCode(card);
		return code ? `tarot-art/rws/${code}.jpg` : null;
	}
	const local = LOCAL_ART[deckId];
	if(local){
		if(card.arcana === 'major'){ return (local.majors && card.sid) ? `${local.base}${card.sid}.jpg` : null; }
		if(card.court){ return local.minorCourts && card.sid ? `${local.base}${card.sid}.jpg` : null; }
		return local.minorPips && card.sid ? `${local.base}${card.sid}.jpg` : null;
	}
	return null;
}

// 该牌组是否提供真实牌面(决定是否显示「牌面样式」切换)。部分牌组仅大牌有图,小牌回退符号。
export function deckHasRealArt(deckId){
	return deckId === 'rws' || !!LOCAL_ART[deckId];
}

// 该牌组的真实牌面是否「仅大牌」(花色小牌无图、回退符号)。RWS=全 78 张,非仅大牌。
// 用于在含小牌的牌组(如 78 张马赛)上提示用户:真实牌面只覆盖大牌。
export function deckArtIsMajorsOnly(deckId){
	const local = LOCAL_ART[deckId];
	return !!(local && local.majors && !local.minorPips && !local.minorCourts);
}
