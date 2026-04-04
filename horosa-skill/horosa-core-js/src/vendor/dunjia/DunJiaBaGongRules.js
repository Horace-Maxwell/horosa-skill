const BAGONG_PALACE_ORDER = [9, 8, 7, 4, 1, 2, 3, 6];

const BAGONG_PALACE_NAME = {
	1: '巽',
	2: '离',
	3: '坤',
	4: '震',
	6: '兑',
	7: '艮',
	8: '坎',
	9: '乾',
};

const GOD_FULL_NAME = {
	符: '值符',
	蛇: '螣蛇',
	阴: '太阴',
	合: '六合',
	虎: '白虎',
	玄: '玄武',
	地: '九地',
	天: '九天',
};

const BASE_DOOR_BY_PALACE = {
	9: '开',
	8: '休',
	7: '生',
	4: '伤',
	1: '杜',
	2: '景',
	3: '死',
	6: '惊',
};

const BASE_STAR_BY_PALACE = {
	9: '心',
	8: '蓬',
	7: '任',
	4: '冲',
	1: '辅',
	2: '英',
	3: '芮',
	6: '柱',
};

const BASE_PALACE_BY_DOOR = Object.keys(BASE_DOOR_BY_PALACE).reduce((acc, key)=>{
	acc[BASE_DOOR_BY_PALACE[key]] = parseInt(key, 10);
	return acc;
}, {});

const OPPOSITE_PALACE = {
	1: 6,
	2: 8,
	3: 9,
	4: 7,
	6: 1,
	7: 4,
	8: 2,
	9: 3,
};

const PALACE_WUXING = {
	1: '木',
	2: '火',
	3: '土',
	4: '木',
	6: '金',
	7: '土',
	8: '水',
	9: '金',
};

const DOOR_WUXING = {
	开: '金',
	休: '水',
	生: '土',
	伤: '木',
	杜: '木',
	景: '火',
	死: '土',
	惊: '金',
};

const WUXING_SHENG = {
	木: '火',
	火: '土',
	土: '金',
	金: '水',
	水: '木',
};

const WUXING_KE = {
	木: '土',
	土: '水',
	水: '火',
	火: '金',
	金: '木',
};

const DOOR_SET = new Set(['开', '休', '生', '伤', '杜', '景', '死', '惊']);
const JI_MEN_SET = new Set(['开', '休', '生']);
const SAN_QI_SET = new Set(['乙', '丙', '丁']);

const WUBUYUSHI_TIME = {
	甲: '庚午',
	乙: '辛巳',
	丙: '壬辰',
	丁: '癸卯',
	戊: '甲寅',
	己: '乙丑',
	庚: '丙子',
	辛: '丁酉',
	壬: '戊申',
	癸: '己未',
};

const SHIGAN_RUMU_GANZHI_SET = new Set(['戊戌', '壬辰', '丙戌', '癸未', '丁丑']);

const TIAN_XIAN_TIME_RULE = {
	甲: ['甲子', '甲戌'],
	己: ['甲子', '甲戌'],
	乙: ['甲申'],
	庚: ['甲申'],
	丙: ['甲午'],
	辛: ['甲午'],
	戊: ['甲寅'],
	癸: ['甲寅'],
	丁: ['甲辰'],
	壬: ['甲辰'],
};

const TIAN_FU_TIME_RULE = {
	甲: ['己巳'],
	己: ['己巳'],
	乙: ['甲申'],
	庚: ['甲申'],
	丙: ['甲午'],
	辛: ['甲午'],
	丁: ['甲辰'],
	壬: ['甲辰'],
	戊: ['甲寅'],
	癸: ['甲寅'],
};

const LIUYI_JIXING_PALACE = {
	戊: 4,
	己: 3,
	庚: 7,
	辛: 2,
	壬: 1,
	癸: 1,
};

const STAR_RUMU_RULES = [
	{ doors: ['休'], stars: ['蓬'], palaces: [1] },
	{ doors: ['惊', '开'], stars: ['心', '柱'], palaces: [7] },
	{ doors: ['伤', '杜'], stars: ['冲', '辅'], palaces: [3] },
	{ doors: ['景'], stars: ['英'], palaces: [9] },
	{ doors: ['生', '死'], stars: ['任', '芮', '禽'], palaces: [1] },
];

const QIYI_XIANGHE_PAIRS = new Set(['乙庚', '庚乙', '丙辛', '辛丙', '丁壬', '壬丁', '戊癸', '癸戊', '甲己', '己甲']);
const SAN_QI_DESHI_BY_DAY_GAN = {
	甲: '丙',
	己: '丙',
	乙: '乙',
	庚: '乙',
	丙: '丙',
	辛: '丙',
	丁: '乙',
	壬: '乙',
	戊: '丁',
	癸: '丁',
};
const YUNU_SHOUMEN_BY_TIME_GAN = {
	甲: '丙',
	己: '丙',
	乙: '辛',
	庚: '辛',
	丙: '乙',
	辛: '乙',
	丁: '己',
	壬: '己',
	戊: '壬',
	癸: '壬',
};
const YUNU_EXTRA_TIME_GANZHI = new Set(['乙卯', '乙未', '丙午', '丁酉', '庚午', '庚子', '己卯', '戊子']);
const XUN_SHOU_TO_LIUYI = {
	甲子: '戊',
	甲戌: '己',
	甲申: '庚',
	甲午: '辛',
	甲辰: '壬',
	甲寅: '癸',
};

const DOOR_BAGUA = {
	休: '坎',
	生: '艮',
	伤: '震',
	杜: '巽',
	景: '离',
	死: '坤',
	惊: '兑',
	开: '乾',
};

const LIUSHISI_GUA_NAME = {
	'乾乾': '乾为天',
	'乾兑': '天泽履',
	'乾离': '天火同人',
	'乾震': '天雷无妄',
	'乾巽': '天风姤',
	'乾坎': '天水讼',
	'乾艮': '天山遯',
	'乾坤': '天地否',
	'兑乾': '泽天夬',
	'兑兑': '兑为泽',
	'兑离': '泽火革',
	'兑震': '泽雷随',
	'兑巽': '泽风大过',
	'兑坎': '泽水困',
	'兑艮': '泽山咸',
	'兑坤': '泽地萃',
	'离乾': '火天大有',
	'离兑': '火泽睽',
	'离离': '离为火',
	'离震': '火雷噬嗑',
	'离巽': '火风鼎',
	'离坎': '火水未济',
	'离艮': '火山旅',
	'离坤': '火地晋',
	'震乾': '雷天大壮',
	'震兑': '雷泽归妹',
	'震离': '雷火丰',
	'震震': '震为雷',
	'震巽': '雷风恒',
	'震坎': '雷水解',
	'震艮': '雷山小过',
	'震坤': '雷地豫',
	'巽乾': '风天小畜',
	'巽兑': '风泽中孚',
	'巽离': '风火家人',
	'巽震': '风雷益',
	'巽巽': '巽为风',
	'巽坎': '风水涣',
	'巽艮': '风山渐',
	'巽坤': '风地观',
	'坎乾': '水天需',
	'坎兑': '水泽节',
	'坎离': '水火既济',
	'坎震': '水雷屯',
	'坎巽': '水风井',
	'坎坎': '坎为水',
	'坎艮': '水山蹇',
	'坎坤': '水地比',
	'艮乾': '山天大畜',
	'艮兑': '山泽损',
	'艮离': '山火贲',
	'艮震': '山雷颐',
	'艮巽': '山风蛊',
	'艮坎': '山水蒙',
	'艮艮': '艮为山',
	'艮坤': '山地剥',
	'坤乾': '地天泰',
	'坤兑': '地泽临',
	'坤离': '地火明夷',
	'坤震': '地雷复',
	'坤巽': '地风升',
	'坤坎': '地水师',
	'坤艮': '地山谦',
	'坤坤': '坤为地',
};

function getPalaceBagua(palaceNum){
	return BAGONG_PALACE_NAME[palaceNum] || '';
}

function getHexagramName(upperBagua, lowerBagua){
	if(!upperBagua || !lowerBagua){
		return '';
	}
	return LIUSHISI_GUA_NAME[`${upperBagua}${lowerBagua}`] || '';
}

function buildFuShiYiGuaData(pan){
	const innerPalace = pan && pan.zhiFuPalace ? pan.zhiFuPalace : 0;
	const outerPalace = pan && pan.zhiShiPalace ? pan.zhiShiPalace : 0;
	const innerBagua = getPalaceBagua(innerPalace);
	const outerBagua = getPalaceBagua(outerPalace);
	const guaName = getHexagramName(outerBagua, innerBagua);
	const displayName = guaName ? `${guaName}卦` : '无';
	return {
		guaName,
		displayName,
		innerPalace,
		outerPalace,
		innerBagua,
		outerBagua,
		text: guaName
			? `${displayName}（外卦${outerBagua}，内卦${innerBagua}）`
			: '无',
	};
}

function buildMenFangYiGuaData(palaceNum, door){
	const palaceBagua = getPalaceBagua(palaceNum);
	const doorBagua = DOOR_BAGUA[door] || '';
	const guaName = getHexagramName(doorBagua, palaceBagua);
	const displayName = guaName ? `${guaName}卦` : '无';
	return {
		guaName,
		displayName,
		palaceBagua,
		doorBagua,
		text: guaName
			? `${displayName}（门卦${doorBagua}，方卦${palaceBagua}）`
			: '无',
	};
}

function buildMapFromText(text){
	const outMap = {};
	(`${text || ''}`).split(/\n/).forEach((line)=>{
		const one = `${line || ''}`.trim();
		if(!one){
			return;
		}
		const idx = one.indexOf('|');
		if(idx <= 0){
			return;
		}
		const key = one.substring(0, idx);
		outMap[key] = one.substring(idx + 1).replace(/｜/g, '|');
	});
	return outMap;
}

const QIMEN_JIGE_INTERPRETATION = buildMapFromText(`
天遁|丙加丁逢生门为天遁，其方得月精所蔽。此时宜修身、炼道、遁迹、隐形，可朝君王、祈福、求神、出师、征战自伏；凡上策献书、求官进职、剪恶除凶、商贾出行、婚姻入宅百事吉。
地遁|乙加己逢开门临九地、太阴、六合为地遁，其方得日精所蔽。宜设伏、藏兵、立寨、安营、建置、修造、出阵、攻城；出行、埋葬、冠婚、藏匿皆吉。
人遁|丁加乙逢休生门临太阴为人遁，其方得星精所蔽。宜选将求贤、说敌和仇、投策献书、隐藏伏匿，凡结姻交易全吉。
风遁|乙奇合开休生吉门临巽宫为风遁。宜祭神取气、喷旗建旌、呼风破敌、火攻飞砂走石，宜用于机密联络与遁伏之事。
云遁|乙加辛合开休生三吉门临坤为云遁。宜祷雨利农、建营修道、埋伏掩袭；冬月宜求雪、夏月宜求雨。
龙遁|乙加壬合开休生三吉门临坎为龙遁。宜祭龙祈雨、演习水战、密运机谋、开河通渠、计水冲阵，水军对敌尤宜。
虎遁|乙加辛逢休生门临艮为虎遁。宜招抚叛亡、据险守险、设计冲锋、镇邪捕射猎，安营伏兵可借虎威。
神遁|丙奇生门临九天为神遁。宜祭祀祈神、建坛驱神、阴谋密计、行兵作神将涂抹三军，祭祀与兵事多验。
鬼遁|辛加丁逢休生杜门临艮宫九地为鬼遁。宜采探贼情、偷营劫寨、行间谍布谣、驱神遣鬼、祭炼丁甲。
真诈|乙丙丁合开休生门临太阴为真诈，宜暗计、埋伏、布德、隐遁。
重诈|乙丙丁合开休生门临九地为重诈，宜选将、招兵、修筑、埋葬。
休诈|乙丙丁合开休生门临六合为休诈，宜祷祈、袪邪、合药、治疫、造葬、婚姻、交易、上官赴任、遗使破敌，万事皆吉。
天假|景门合乙、丙、丁临九天为天假，宜彰天威、奋武、谒贵求贤、上书献策、颁号令申盟约，使敌自伏。
地假|杜门同丁、己、癸临九地为地假，宜潜伏隐遁、私约交通、偃旗息鼓、暗地施为。
人假|惊门同壬临九天为人假，宜捕捉叛亡、搜擒匿寇、捕盗拿贼、暗计施行。
鬼假|死门同丁、己、癸临九地为鬼假，宜超亡荐度、安葬、埋伏、交战、筑堤积水、挖井通渠。
物假|伤门同丁、己、癸临六合为物假，宜索取、捕捉、返归故里、修葺旧垒、填塞古道、交易伏藏。
三奇得使|甲己日丙奇，乙庚日乙奇，丙辛日丙奇，丁壬日乙奇，戊癸日丁奇，阴阳二遁遇此诸事皆吉。
玉女守门|甲己时在丙，乙庚时在辛，丙辛时在乙，丁壬时在己，戊癸时在壬，凡营建宴会喜庆事皆吉。
青龙回首|戊加丙为青龙回首，此时宜举百事，多有欣悦称心之验，行军俱吉。
飞鸟跌穴|丙加戊为飞鸟跌穴，此时百事宜为，有显达易成之象，战阵皆吉。
三奇贵人升殿|乙奇到震，丙奇到离，丁奇到兑，此三奇升本宫之殿，百事皆吉。
天显时格|又时遇乙（卯、未）丙午丁酉之值使加临玉女合吉格，诸事大吉；庚（午、子）己卯戊子亦为守门时。
奇游禄位|乙奇到震，丙奇到巽，丁奇到离为本禄之位，合吉门谋为皆吉。
欢怡|乙丙丁三奇临六甲值符之宫为欢怡，凡百谋为无不和悦。
相佐|本旬值符加地盘三奇之上，百事皆宜，派兵调弁尤为效力。
天运昌气|六丁加六乙为昌气，遇吉门主客皆利，凡百谋为皆吉。
奇仪相合|天地奇仪相合：乙庚、丙辛、丁壬为奇，合戊癸、甲己为仪，得吉门则谋为多有和合之象。
交泰|乙奇加丁、丁奇加丙，遇吉门主客皆吉，谋为大利。
门宫和义|和者宫生门，义者门生宫；遇吉门吉格，万事皆宜。
天辅吉时|甲己之日己巳时，乙庚甲申，丙辛甲午，丁壬甲辰，戊癸甲寅，号为天辅大吉时。此时万事皆宜，行兵征战多获大胜。
`);

const QIMEN_XIONGGE_INTERPRETATION = buildMapFromText(`
青龙逃走|六乙加辛为青龙逃走，此时不宜举兵，主将士逃窜，谋为多凶。
白虎猖狂|六辛加乙为白虎猖狂，不宜行兵，主客皆伤，诸事不吉。
螣蛇夭矫|六癸加丁为螣蛇夭矫，此时百事不利主动，多主虚惊与错动。
朱雀投江|六丁加癸为朱雀投江，诸事不宜，文书泄漏，口舌频生。
太白火荧|六庚加丙为太白火荧，诸事多凶，尤防盗贼与营寨受扰。
荧入太白|六丙加庚为荧入太白，行兵主贼退去，宜追击，常见不战而胜。
飞宫格|六甲值符加地庚为飞宫格，诸事不吉，宜静不宜动，用兵尤忌。
伏宫格|六庚加地甲值符为伏宫格，此时进退多阻，行主逢盗，百事不宜。
飞干格|日干加庚为飞干格，战则主客皆伤，出行主飞灾横祸。
伏干格|庚加日干为伏干格，战必遭擒，主客两伤，出行尤忌。
大格|天庚加地癸为大格，谋为诸事不利，出行多阻，惟捕捉较利。
小格|天庚加地壬为小格，凡百谋为不利，行兵出行尤忌。
年格|六庚加本年岁干为年月日时格之一，百事不利，惟宜捕捉。
月格|六庚加本月干为年月日时格之一，百事不利，惟宜捕捉。
日格|六庚加本日干为年月日时格之一，百事不利，惟宜捕捉。
时格|六庚加本时干为年月日时格之一，百事不利，惟宜捕捉。
刑格|六庚加地己为刑格，行兵大凶，出行道途阻隔，诸事不利。
刑格返名|六己加地庚为刑格返名，词讼先动者不利，若临阴星则有谋害之情。
悖格|六丙加年月日时干为悖格，宜固守不可轻动，利主不利客，举事多紊乱无绪。
天网四张格|六甲值符加地癸为天网四张格，万事宜静，勉强妄动多有灾殃。
地罗遮格|天上六壬加时干为地罗遮格，出兵出行多受阻碍，不宜强进。
伏吟|星符门还加本宫为伏吟，凡百谋为只宜静守，不可妄动，急进则易遭围困。
返吟|星符门加对冲之宫为返吟，凡百谋为反复不定，宜积粮静守。
六仪击刑|甲子临震、甲戌临坤、甲申临艮、甲午临离、甲辰临巽、甲寅临巽。此时忌用兵，安营尤忌，出行谋为多不利。
五不遇时|时干克日干为五不遇时，出行主折损，百事凶，用兵尤忌，虽有奇门亦不可轻用。
时干入墓|戊戌、壬辰、丙戌、癸未、丁丑为时干入墓，百事不宜，出师出行尤忌。
三奇入墓|乙奇临坤，丙奇临乾，丁奇临艮为三奇入墓。凡百事吉者不吉，凶者不凶，多主无功。
门迫|门宫迫制之一：八门克宫为迫。吉门受迫则吉事不吉，凶门受迫则灾殃尤甚。
门受制|门宫迫制之一：宫克八门为制。吉门受制则吉事不吉，凶宫凶门并制则祸更甚。
三奇受制|九遁诸格虽吉，惟忌奇墓刑迫；三奇受制则吉格失力，宜守不宜攻。
星门入墓|休蓬入辰，惊开心柱入丑，伤杜冲辅入未，景英入戌，生死任芮禽入辰。此时凡百谋为多阻滞不通。
`);

function formatPatternInterpretation(name, type = 'ji'){
	const sourceMap = type === 'xiong' ? QIMEN_XIONGGE_INTERPRETATION : QIMEN_JIGE_INTERPRETATION;
	const note = `${sourceMap[name] || ''}`.trim();
	if(note){
		return `${name}：${note}`;
	}
	return `${name}：未附释义。`;
}

function buildPatternInterpretationList(patterns, type = 'ji'){
	if(!Array.isArray(patterns) || !patterns.length){
		return [];
	}
	return patterns.map((name)=>formatPatternInterpretation(name, type));
}

const QIMEN_TENGAN_RESPONSE = buildMapFromText(`
丙丙|月奇悖师，文书逼迫，破耗遗失，主单据、票证，不明遗失。
丙丁|星奇朱雀，贵人文书吉利，常人平静安乐，得三吉门为天遁。
丙庚|荧入太白，賊必去。
丙癸|月奇地网，阴人害事，灾祸频生，凡事暗昧不明。
丙己|火悖入刑，囚人刑杖，文书不行，吉门得吉，凶门转凶。
丙壬|火入天罗，为客不利，是非颇多。
丙戊|飞鸟跌穴，事业可为，可谋大事，对好事大吉大利，如求婚、求财、考试、求官等，不用费多大力气，就能成功。
丙辛|日月相会，谋事成就，病人不凶。
丙乙|日月并行，公谋私为皆为吉。
丁丙|星随月转，贵人越级高升，常人乐极生悲，要忍、不然因小的不忍，而引起大的不幸。
丁丁|星奇入太阴，文书证件即至，喜事从心、万事如意。
丁庚|星奇受阻，文书阻隔，行人必归。
丁癸|朱雀投江，文书口舌是非，经官动府、词诉不利，音信沉溺不到。
丁己|火入勾陈，奸私仇怨，事因女人。
丁壬|奇仪相合，贵人恩诏，诉狱公平。
丁戊|青龙转光，官人升迁，常人威昌。
丁辛|朱雀入狱，罪人失囚，官人失位。
丁乙|人遁吉格，贵人加官进爵，常人婚姻财帛有喜。
庚丙|太白入荧，贼必来，为客进利，为主破财。
庚丁|亭亭之格，因私匿或男女关系起官司是非，门吉有救；门凶，事必凶。
庚庚|太白同宫，又名战格，官灾横祸。
庚癸|大格，因寅申相冲，庚为道路，故多主车祸，行人不至，官司不止，生育母子具伤，婚姻易鳏寡孤独。
庚己|官府刑格，主有官司口舌，因官讼被判刑，住牢狱更凶，百事不利。
庚壬|移荡格，上格又名小格。
庚戊|天乙伏宫，百事不可谋，大凶。
庚辛|白虎干格，不宜远行，远行车折马伤，求财更为大凶，诸事有灾殃，时间越长越凶。
庚乙|太白逢星，退吉进凶，谋为不利。
癸丙|华盖悖师，贵贱逢之皆不利，唯上人见喜。
癸丁|腾蛇夭矫，文书官司，火焚也逃不掉，虚惊不宁。
癸庚|太白入网，主以暴力争讼，自邏罪责。
癸癸|天网四张，主行人失伴，病讼皆伤。
癸己|华盖地户，男女测之，音信皆阻，躲灾避难方为吉。
癸壬|复见腾蛇，癸水、壬水均为水蛇，主嫁娶重婚，后嫁无子，不保年华。
癸戊|天乙合会，吉门宜求财，婚姻喜美，吉人赞助成合。
癸辛|网盖天牢，主官司败诉，死罪难逃。
癸乙|华盖逢星，贵人禄位，常人平安。
己丙|火悖地户，己在天盘，丙在地盘，戌为火墓，己为地户，阴阳颠倒，所以叫火悖地户凶格。
己丁|朱雀入狱，天盘甲戌己，地盘丁奇，因戌/丑都为火墓，丁奇为南方火，又名朱雀，所以叫朱雀入狱。
己庚|刑格返名，词讼先动者不利，如临阴星（凶星）则有谋害之情。
己癸|地刑玄武，男女疾病垂危，有囚狱词讼之灾。
己己|地户逢鬼，病者发凶或必死，百事不遂，暂不谋为，谋为则凶。
己壬|地网高张，狡童佚女，奸情伤杀，凡事不吉，谋为不利。
己戊|犬遇青龙，戌为犬，甲为龙，故名犬遇青龙。
己辛|游魂入墓，易招阴邪鬼魅作祟。
己乙|墓神不明，戌为乙木之墓，己又为地户，故名墓神不明，地户逢星，宜遁迹隐形为利。
壬丙|水蛇入火，因为壬丙相冲克，故主官灾刑禁，络绎不绝，主两败俱伤，为客不利。
壬丁|干合蛇刑，文书牵连，贵人匆匆，男吉女凶。
壬庚|太白擒蛇，因庚为太白，壬为蛇，故名。
壬癸|幼女奸淫，主有家丑外扬之事发生；门吉星凶，反福为祸。
壬己|反吟蛇刑，主官司败诉，大祸将至，顺守为吉，妄动必凶。
壬壬|天狱自刑或蛇入地罗，壬为天罗又名天狱，辰辰自刑，故名。
壬戊|小蛇化龙，男人发达，女产婴童，做事要防耗散。
壬辛|腾蛇相缠，纵得吉门，亦不能安。
壬乙|小蛇得势，女人柔顺，男人通达。
戊丙|青龙返首，动作大吉，但若逢门迫、入墓、击刑，则吉事成凶。
戊丁|青龙耀明，宜见上级领导、贵人，求功名，为事吉利。
戊庚|值符飞宫，吉事不吉，凶事更凶，求财没利益，测病也主凶。
戊癸|青龙华盖，又戊癸相合，故逢吉门为吉，可招福临门；逢凶门，事多不利，为凶。
戊己|贵人入狱，公私皆不利。
戊壬|青龙入天牢，凡阴阳事皆不吉利。
戊戊|名为伏吟，凡事不利，道路闭塞，以守为好。
戊辛|青龙折足，吉门有生助，尚能谋事；若逢凶门，主招灾，失财或有足疾、折伤。
戊乙|青龙和会，门吉事吉，门凶事也凶。
辛丙|干合悖师，荧惑出现，占雨无，占晴旱，占事必因财致讼。
辛丁|狱神得奇，经商求财获利倍增，囚人逢天赦释免，办其他事，也会有意外的收获。
辛庚|白虎出力，刀刃相交，主客相残，逊让退步则安，强进血溅衣衫。
辛癸|天牢华盖，日月失明，误入天网，动止乖张。
辛己|入狱自刑，辛为罪人，戌为午火之墓，故为入狱自刑，主奴仆背主，有苦诉讼难伸。
辛壬|凶蛇入狱，因为壬为凶蛇，辛为牢狱，故名。
辛戊|困龙被伤，主官司破财，屈抑守分尚可，妄动则带来祸殃。
辛辛|伏吟天庭，公废私就，讼狱自羅罪名。
辛乙|白虎猖狂，家败人亡（分家、婚散、破产），出行有惊恐，远行多灾殃，尊长不喜，车船俱伤。
乙丙|奇仪顺遂，吉星加官尽职，凶星夫妻反目离别。
乙丁|奇仪相佐，最利文书、考试，百事可为。
乙庚|日奇被刑，为争讼财产，夫妻各怀私意。
乙癸|日奇入地网，宜退不宜进，隐匿藏形，躲灾避难为吉，此格局不利于进攻。
乙己|日奇入墓，被土暗昧、门凶事必凶。
乙壬|日奇入天罗，尊婢悖乱，官讼是非，有人谋害之事。
乙戊|阴害阳门，利于阴人阴事，不利于阳人阳事，就是说不利于公开的事情，利于女人/利于暗中行事。
乙辛|青龙逃走，人亡财破，奴仆拐带，六畜皆伤。
乙乙|日奇伏吟，不宜见上级领导、贵人；求名求利及进取事不可求，只宜安分守己。
`);

const QIMEN_DOOR_BASE_RESPONSE = buildMapFromText(`
杜杜|主因父母疾病、田宅出脱事，凶。
杜惊|主门户内忧疑、惊恐、词讼事。
杜景|主文书、印信阻隔，阳人小口疾病。
杜开|主见贵人、官长谋事，先破财后吉。
杜伤|主兄弟田产破财。
杜生|主阳人小口破财，田宅求财不利。
杜死|主田宅、文书失落，官司破财小凶。
杜休|主求财小益。
惊杜|失脱破财事，惊恐，不凶。
惊惊|主疾病、忧虑、惊疑、惊恐。
惊景|主讼词不息，小口疾病，凶。
惊开|主忧疑，官事惊恐，见喜贵则不凶。
惊伤|主因商议同谋害人事泄，惹讼凶。
惊生|主因妇人生产或求财而生惊忧，皆吉。
惊死|因田宅中怪异而生是非，凶。
惊休|求财事或口舌事，迟吉。
景杜|文中未列此组合，通常参看杜加景断。
景惊|文中未列此组合，通常参看惊加景断。
景景|主文状未动，有预先见之意，内有阳人、小口忧患。
景开|官人升迁，求文印事皆吉。
景伤|主亲眷口舌，败财后平。
景生|主阴人生产大喜，更主求财旺利，行人大吉。
景死|主官讼，争田宅事，多啾唧。
景休|主文书遗失，争讼不休。
开杜|主失脱文印、书契等，小凶。
开惊|词讼、惊疑之事。
开景|见贵人，因文书事不利。
开开|主贵人、宝物、财喜、官运、事业皆吉。
开伤|主变动、更改、移徙等事，皆不吉。
开生|见贵人，谋望所求遂意。
开死|官司、惊忧、恶事，先忧后喜。
开休|主见贵人、财喜、开张店铺、贸易大利。
伤杜|主变动、失聪、官司、刑狱、百事凶。
伤惊|主亲人疾病、惊忧，谋为不利，凶。
伤景|主文书、印信、口舌、惹是生非。
伤开|主见贵人、开张、走失、变动等事不利。
伤伤|主变动、远行皆主折伤。
伤生|主房产、种植业等变动。
伤死|主官司、印信凶，出行大忌，占病凶。
伤休|主男人变动或托人谋事，财名不利。
生杜|主阴谋、阴人损财，不利。
生惊|主尊长财产、词讼，病迟愈，吉。
生景|主阴人、小口不宁及文书事。
生开|主见贵人，求财大发。
生伤|主亲友变动，道路不吉。
生生|主远行，求财，吉。
生死|主田宅官司，病则主难救。
生休|主阴人处，谋财利。
死杜|破财，妇人风疾，腹肿。
死惊|因官司事不结，忧疑患病凶。
死景|因文信、书契、财产事见官，先怒后喜不凶。
死开|见贵人求文书、印信事利。
死伤|官司变动遭刑杖凶。
死生|主丧事，求财则得，占病死者复生。
死死|主官事，无气、凶。
死休|主求财物事不吉，向僧道求方吉。
休杜|主破财、失物难寻。
休惊|主损财、招非并疾病惊恐事。
休景|主谋望文书印信等事不成，反招口舌。
休开|主开张店铺及见贵，求财等事大吉。
休伤|上官主喜庆；求财则不易得；其它分产、变动等事亦不吉。
休生|得阴人财物；于贵谋望，虽迟应吉。
休死|主文印官事不吉，远行，僧道事不吉，占病凶。
休休|求才进人口，谒贵吉，朝见上官，修造大利。
`);

const QIMEN_DOOR_TIANGAN_RESPONSE = buildMapFromText(`
杜丙|主文契遗失。
杜丁|主阳人讼狱。
杜庚|因女人词讼被刑。
杜癸|主百事皆阻，病者不食。
杜己|主私谋取、害人、招非。
杜壬|主奸盗事凶。
杜戊|主谋事不易成，密处求财可得。
杜辛|主打伤人至词讼，阳人小口凶。
杜乙|主暗求财物，后则不明至讼。
惊丙|主文书印信惊恐。
惊丁|词讼牵连。
惊庚|道路损伤、遇盗贼，凶。
惊癸|主被贼盗，失物不获。
惊己|恶犬伤人成讼。
惊壬|官司囚禁、病者大凶。
惊戊|损财、信阻。
惊辛|因女人成讼，凶。
惊乙|主谋财不得。
景丙|文书急迫、火速不利。
景丁|主因文书、印状招非。
景庚|讼人自讼。
景癸|因奴婢受刑伤。
景己|官司牵连。
景壬|因贼牵连。
景辛|阴人词讼。
景乙|讼事不成。
开丙|贵人印绶。
开丁|远信必至。
开庚|道路词讼，谋为两歧。
开癸|失财小凶。
开己|事绪不定。
开壬|远行有失。
开戊|财名俱得。
开辛|阴人道路。
开乙|小财可求。
伤丙|道路损失。
伤丁|印信不实。
伤庚|讼狱被刑杖。
伤癸|讼狱被冤，有理难伸。
伤己|财散人病。
伤壬|囚盗牵连。
伤戊|失脱难获。
伤辛|夫妻怀私怨怒。
伤乙|求财不得，反盗耗失财。
生丙|贵人，印绶、婚姻、书信等喜事。
生丁|词讼、婚姻、财利，出行大吉。
生庚|财产争讼、破耗遗失。
生癸|主婚姻难成，余事皆吉。
生己|得贵人维护支持，吉。
生壬|遗失财物，后得，捕盗易获。
生戊|嫁娶、谒贵，求财皆吉。
生辛|主产妇疾病，后吉。
生乙|主阴人生产迟，吉。
死丙|信息忧疑。
死丁|老阳人疾病。
死庚|主女人生产、子母并凶。
死癸|主妇女嫁娶事凶。
死己|主病讼牵连凶。
死壬|主讼人自讼自招。
死戊|主作伪财。
死辛|主遭盗贼，失脱难获。
死乙|求事不成。
休丙|文书和合喜庆。
休丁|百讼休歇。
休庚|文书词讼先结后解。
休癸|阴人词讼牵连。
休己|暗昧不宁。
休壬|阴人词讼牵连。
休戊|财物和合。
休辛|疾病退愈，失物不得。
休乙|求谋重，不得；求轻，可得。
`);

const QIMEN_GOD_DOOR_RESPONSE = buildMapFromText(`
白虎杜|白虎加杜必死亡，六蓄相争坟道桑。五里逢人相斗讼，求谋谨慎莫轻信。
白虎惊|白虎加惊有异云，行兵有险不可进。伤亡病死忧愁事，暗昧不明有灾殃。
白虎景|白虎加景凶孝事，官灾病患宅难居。事多反复防女色，求谋做事北方宜。
白虎开|白虎临开贵出兵，远行事凶出难逃。征战诛伐有人助，追捕掩捉不出营。
白虎伤|白虎伤兮死伤起，人口不知休门己。官司贼人杀伤害，遇事严厉莫宽容。
白虎生|白虎临生主杀伤，远行凶死病须亡。求谋在天莫强取，行兵险阻防火攻。
白虎死|白虎死兮主孤军，竞妇争婚病难痊。行人须防贼来偷，灾星频频忧患缠。
白虎休|白虎休兮主争张，占病难安官讼长。谋事求官皆不遂，行兵防诈有虚惊。
九地杜|九地临杜小女忧，井灶钱财防散丢。占病难安终难断，远行求谋消息求。
九地惊|九地惊兮风云幻，主将变化几多端。客将生疑事见凶，贼人躲藏捕捉难。
九地景|九地会景门无奇，宜在舟中破顽敌。功成名就声大震，遇捕盗贼尚在巢。
九地开|九地开兮太阳红，用兵宜守不宜攻。君子行事须三思，众人同心百事成。
九地伤|九地临伤酒席宴，路途奔波行程连。牛羊须防多遭损，卯木克土妇难安。
九地生|九地生兮见水灾，用兵进退莫轻裁。朝廷颂恩显荣耀，贤人助我捕盗贼。
九地死|九地死兮天晴朗，行兵险阴虎道挡。综有贤人来相助，弱不从心主有伤。
九地休|九地休兮晴反雨，行兵地险山火名。西北方位见天使，捕捉不利勿轻敌。
九天杜|九天杜兮得天时，用兵登舟渡江吉。贼通术数难捕获，客占祥瑞百事遂。
九天惊|九天惊门多危难，不宜轻进得助吉。捕捉应在西山下，主将褒封客多谋。
九天景|九天景门主天时，行兵北阻南方利。主将功成褒封至。客将出师法之制。
九天开|九天开门比合星，用兵水火西北吉。夫妻双至立交通，主将火灾客避锋。
九天伤|九天伤兮天大睛，外亲相见吉事多。掩捕贼人东方觅，进退荣耀步云梯。
九天生|九天生门多连雨，行兵险阻出可击。贼逃可捉西方位，求谋诸事莫轻心。
九天死|九天死兮阴晦风，诸事逢之又小吉。行兵亦主小破敌，忌害贤良易生疑。
九天休|九天临休云雨散，出兵越境有忧难。功成上级来奖赏，贼逃人报定可捉。
六合杜|六合杜兮契约交，争讼阴私六畜逃。立将家忧三九日，九地天伏利出兵。
六合惊|六合会惊大旱生，成就交关多虚诈。城中空兮伏兵悍，破关徙河防被捉。
六合景|六合景兮天有雷，三人同心擒贼人。颜色赤红斑斓物，出行多厄不顺心。
六合开|六合开兮雷电生，捕贼官司囚禁身。百人可阻万人路，四时宜守不宜攻。
六合伤|六合伤兮风雨疾，事故起于西南禺。高山峻岭有骑兵，将防火灾客酒色。
六合生|六合生兮雷无雨，守战皆宜西南地。艰难险阻消除尽，更宜上梁盖新居。
六合死|六合死兮和会亲，酒宴钱谷会相邻。谋求诸事多欢畅，多顺少逆好天时。
六合休|六合休兮寻人难，求物投参事亦然。行兵水阻贤人至，求谋不成事不遂。
太阴杜|太阴杜兮恶人斯，事事难成又主迟。行兵受阻水难渡，金石之物带怀中。
太阴惊|太阴惊兮甘雨降，进兵征战必有功。占事民亡谋计好，刀还钱物镜中晴。
太阴景|太阴临景主喧争，官司阴私口舌频。刑讼牢狱多愁事，风波阵阵几时停。
太阴开|太阴开兮远行人，居家恐被贼兵惊。天空晴朗兵可进，凶死龙虎石金形。
太阴伤|太阴会伤暗阴和，女子阴私盗贼多。追捕逃亡亦无功，先喜后忧终无措。
太阴生|太阴临生文字交，财帛金银有虚耗。天雨逢伐路边树，行兵败北损财宝。
太阴死|太阴死兮欲谋财，和合婚姻求祝谋。八里可见三孝子，金银财帛藏于怀。
太阴休|太阴临休天长阴，忧失财产盗贼临。相邻欺侮文字匿，文士阴谋将丙侵。
螣蛇杜|蛇遇杜兮莫捕贼，贼已远去不可追。仪见戊己官司起，不见天蓬不息宁。
螣蛇惊|蛇会惊兮阴私多，遇己方才凑三合。不然多生暧昧事，桃花从中起风波。
螣蛇景|蛇遇景兮远信来，火光惊忧惧官灾。路遇矮人并雀叫，少报喜来多报灾。
螣蛇开|蛇遇开兮祀神坛，路遇常是妄论仙。不然多遭小人戏，时结冤仇夜难眠。
螣蛇伤|蛇遇伤兮飓风狂，门上不安有纷张。阴人于家多邪事，盗心不息恶名扬。
螣蛇生|蛇会生兮两相刑，来人必定有威名。遇奇方知贤人至，见英可断讼事兴。
螣蛇死|蛇会死兮病面容，居家有人外逃行。灶上炊烟断已久，铁器时时自发声。
螣蛇休|蛇会休兮晴见少，妇人有灾是非忧。问病多是眼目疾，近水河边难匿逃。
玄武杜|玄武临杜争斗起，恶人牵引酒迷失。兵出奇谋必全胜，贼人已远无消息。
玄武惊|玄武惊兮贼上门，死亡官司总缠身。行兵有险休轻进，捕贼远遁不须寻。
玄武景|玄武景兮六畜亡，官司口舌防见伤。行兵征战无险阻，掩捕盗贼在东方。
玄武开|玄武临开主逃亡，官司纷争起田宅。行兵险阻宜坚守，盗贼藏匿在震方。
玄武伤|玄武伤兮贼即至，求事难成官讼灾。行兵山中有埋伏，商贾之人报贼来。
玄武生|玄武生兮论文状，鬼着人身争讼多。征战主吉客不利，掩捕东方则可获。
玄武死|玄武死兮井坟院，多耗财帛鬼神惊。行兵两难思进退，主吉客凶要分清。
玄武休|玄武休兮守战休，鬼贼投井产妇厄。求谋难成不宜进，逃亡已远不可捉。
值符杜|值符杜门艳阳天，主客相交两不欢。往来只为酒食事，相见不曾露良言。
值符惊|符惊相会两难晴，天盘逢英利出行。惊虚多因子女起，交易败于露言行。
值符景|符景相会云雨收，谋望多依小人筹。文章异彩衣丝缕，君子嘉爵亦封侯。
值符开|值符开门两相排，相约不见有人来。空谈几多虚空事，捕贼需求术士猜。
值符伤|值符伤门卦象阴，险途不测莫寻人。如问居家多不利，换庄移家须急论。
值符生|符会生门两相宜，兄弟二人悦财喜。文书应侯逢酒色，禄马相逢定不移。
值符死|符死相见阴雨加，秋风习习路难拔。来问只为灾祸事，为谋多被小人辖。
值符休|符会休兮昼见晴，时有财帛到门庭。壮汉携妇并见齐，虚情假意辩详情。
`);

function getGan(ganzhi){
	const str = `${ganzhi || ''}`;
	return str ? str.substring(0, 1) : '';
}

function getDoorChar(door){
	const str = `${door || ''}`;
	if(!str){
		return '';
	}
	const head = str.substring(0, 1);
	return DOOR_SET.has(head) ? head : '';
}

function getStarChar(star){
	const str = `${star || ''}`;
	if(!str){
		return '';
	}
	const STAR_SET = ['蓬', '任', '冲', '辅', '英', '芮', '柱', '心', '禽'];
	for(let i=0; i<STAR_SET.length; i++){
		if(str.indexOf(STAR_SET[i]) >= 0){
			return STAR_SET[i];
		}
	}
	return str.substring(0, 1);
}

function getGodFull(god){
	const head = `${god || ''}`.substring(0, 1);
	return GOD_FULL_NAME[head] || `${god || ''}`;
}

function findCell(pan, palaceNum){
	if(!pan || !pan.cells || !pan.cells.length){
		return null;
	}
	for(let i=0; i<pan.cells.length; i++){
		if(pan.cells[i].palaceNum === palaceNum){
			return pan.cells[i];
		}
	}
	return null;
}

function isMenShengGong(door, palaceNum){
	const doorWx = DOOR_WUXING[door];
	const palaceWx = PALACE_WUXING[palaceNum];
	if(!doorWx || !palaceWx){
		return false;
	}
	return WUXING_SHENG[doorWx] === palaceWx;
}

function isGongShengMen(door, palaceNum){
	const doorWx = DOOR_WUXING[door];
	const palaceWx = PALACE_WUXING[palaceNum];
	if(!doorWx || !palaceWx){
		return false;
	}
	return WUXING_SHENG[palaceWx] === doorWx;
}

function isMenKeGong(door, palaceNum){
	const doorWx = DOOR_WUXING[door];
	const palaceWx = PALACE_WUXING[palaceNum];
	if(!doorWx || !palaceWx){
		return false;
	}
	return WUXING_KE[doorWx] === palaceWx;
}

function isGongKeMen(door, palaceNum){
	const doorWx = DOOR_WUXING[door];
	const palaceWx = PALACE_WUXING[palaceNum];
	if(!doorWx || !palaceWx){
		return false;
	}
	return WUXING_KE[palaceWx] === doorWx;
}

function isStarDoorRuMu(star, door, palaceNum){
	if(!star || !door){
		return false;
	}
	for(let i=0; i<STAR_RUMU_RULES.length; i++){
		const rule = STAR_RUMU_RULES[i];
		if(rule.doors.indexOf(door) >= 0 && rule.stars.indexOf(star) >= 0 && rule.palaces.indexOf(palaceNum) >= 0){
			return true;
		}
	}
	return false;
}

function addPattern(arr, name){
	if(!name){
		return;
	}
	if(arr.indexOf(name) < 0){
		arr.push(name);
	}
}

function isBeiGe(pan, palaceNum, tianGan, diGan, dayGan, monthGan, yearGan, timeGan){
	if(tianGan === '丙' && [yearGan, monthGan, dayGan, timeGan].indexOf(diGan) >= 0){
		return true;
	}
	if(tianGan === '丙' && palaceNum === (pan && pan.zhiFuPalace)){
		return true;
	}
	if(palaceNum === (pan && pan.zhiFuPalace) && diGan === '丙'){
		return true;
	}
	return false;
}

function getXunShouLiuYi(pan){
	const xunShou = `${pan && pan.xunShou ? pan.xunShou : ''}`;
	return XUN_SHOU_TO_LIUYI[xunShou] || '';
}

function calcJiPatterns(pan, palaceNum, cell){
	const out = [];
	const tianGan = `${cell && cell.tianGan ? cell.tianGan : ''}`;
	const diGan = `${cell && cell.diGan ? cell.diGan : ''}`;
	const door = getDoorChar(cell && cell.door);
	const godFull = getGodFull(cell && cell.god);
	const dayGan = getGan(pan && pan.ganzhi && pan.ganzhi.day);
	const timeGan = getGan(pan && pan.ganzhi && pan.ganzhi.time);
	const timeGanzhi = `${pan && pan.ganzhi && pan.ganzhi.time ? pan.ganzhi.time : ''}`;
	const zhiShiDoor = getDoorChar(pan && pan.zhiShi);
	const zhiShiBasePalace = BASE_PALACE_BY_DOOR[zhiShiDoor] || 0;
	const sanQiDeshiGan = SAN_QI_DESHI_BY_DAY_GAN[dayGan] || '';
	const yuNuTimeGan = YUNU_SHOUMEN_BY_TIME_GAN[timeGan] || '';
	if(sanQiDeshiGan && tianGan === sanQiDeshiGan && palaceNum === zhiShiBasePalace){ addPattern(out, '三奇得使'); }
	if(door && zhiShiDoor && door === zhiShiDoor && ((yuNuTimeGan && tianGan === yuNuTimeGan) || YUNU_EXTRA_TIME_GANZHI.has(timeGanzhi))){ addPattern(out, '玉女守门'); }
	if(tianGan === '戊' && diGan === '丙'){ addPattern(out, '青龙回首'); }
	if(tianGan === '丙' && diGan === '戊'){ addPattern(out, '飞鸟跌穴'); }
	if(((tianGan === '乙' && palaceNum === 4) || (tianGan === '丙' && palaceNum === 2) || (tianGan === '丁' && palaceNum === 6)) && JI_MEN_SET.has(door) && !cell.hasMenPo && !cell.hasRuMu){ addPattern(out, '三奇贵人升殿'); }
	if((TIAN_XIAN_TIME_RULE[dayGan] || []).indexOf(timeGanzhi) >= 0){ addPattern(out, '天显时格'); }
	if((tianGan === '乙' && palaceNum === 4) || (tianGan === '丙' && palaceNum === 1) || (tianGan === '丁' && palaceNum === 2)){ addPattern(out, '奇游禄位'); }
	if(SAN_QI_SET.has(tianGan) && palaceNum === (pan && pan.zhiFuPalace)){ addPattern(out, '欢怡'); }
	if(((tianGan === '乙' && diGan === '丁') || (tianGan === '丁' && diGan === '丙')) && JI_MEN_SET.has(door)){ addPattern(out, '交泰'); }
	if(palaceNum === (pan && pan.zhiFuPalace) && SAN_QI_SET.has(diGan)){ addPattern(out, '相佐'); }
	if(tianGan === '丁' && diGan === '乙' && JI_MEN_SET.has(door)){ addPattern(out, '天运昌气'); }
	if(QIYI_XIANGHE_PAIRS.has(`${tianGan}${diGan}`) && JI_MEN_SET.has(door)){ addPattern(out, '奇仪相合'); }
	if(JI_MEN_SET.has(door) && (isMenShengGong(door, palaceNum) || isGongShengMen(door, palaceNum))){ addPattern(out, '门宫和义'); }
	if((TIAN_FU_TIME_RULE[dayGan] || []).indexOf(timeGanzhi) >= 0){ addPattern(out, '天辅吉时'); }
	if(SAN_QI_SET.has(tianGan) && JI_MEN_SET.has(door) && godFull === '太阴'){ addPattern(out, '真诈'); }
	if(SAN_QI_SET.has(tianGan) && JI_MEN_SET.has(door) && godFull === '九地'){ addPattern(out, '重诈'); }
	if(SAN_QI_SET.has(tianGan) && JI_MEN_SET.has(door) && godFull === '六合'){ addPattern(out, '休诈'); }
	if(door === '景' && SAN_QI_SET.has(tianGan) && godFull === '九天'){ addPattern(out, '天假'); }
	if(door === '杜' && ['丁', '己', '癸'].indexOf(tianGan) >= 0 && godFull === '九地'){ addPattern(out, '地假'); }
	if(door === '伤' && ['丁', '己', '癸'].indexOf(tianGan) >= 0 && godFull === '六合'){ addPattern(out, '物假'); }
	if(door === '死' && ['丁', '己', '癸'].indexOf(tianGan) >= 0 && godFull === '九地'){ addPattern(out, '鬼假'); }
	if(door === '惊' && tianGan === '壬' && godFull === '九天'){ addPattern(out, '人假'); }
	if(tianGan === '丙' && diGan === '丁' && door === '生'){ addPattern(out, '天遁'); }
	if(tianGan === '乙' && diGan === '己' && door === '开' && ['九地', '太阴', '六合'].indexOf(godFull) >= 0){ addPattern(out, '地遁'); }
	if(tianGan === '丁' && diGan === '乙' && (door === '休' || door === '生') && godFull === '太阴'){ addPattern(out, '人遁'); }
	if(tianGan === '丙' && door === '生' && godFull === '九天'){ addPattern(out, '神遁'); }
	if(tianGan === '辛' && diGan === '丁' && (door === '休' || door === '生' || door === '杜') && godFull === '九地' && palaceNum === 7){ addPattern(out, '鬼遁'); }
	if(tianGan === '乙' && JI_MEN_SET.has(door) && palaceNum === 1){ addPattern(out, '风遁'); }
	if(tianGan === '乙' && diGan === '辛' && JI_MEN_SET.has(door) && palaceNum === 3){ addPattern(out, '云遁'); }
	if(tianGan === '乙' && diGan === '壬' && JI_MEN_SET.has(door) && palaceNum === 8){ addPattern(out, '龙遁'); }
	if(tianGan === '乙' && diGan === '辛' && (door === '休' || door === '生') && palaceNum === 7){ addPattern(out, '虎遁'); }
	return out;
}

function calcXiongPatterns(pan, palaceNum, cell){
	const out = [];
	const tianGan = `${cell && cell.tianGan ? cell.tianGan : ''}`;
	const diGan = `${cell && cell.diGan ? cell.diGan : ''}`;
	const door = getDoorChar(cell && cell.door);
	const star = getStarChar(cell && cell.tianXing);
	const baseDoor = BASE_DOOR_BY_PALACE[palaceNum] || "";
	const baseStar = BASE_STAR_BY_PALACE[palaceNum] || "";
	const oppositeDoor = BASE_DOOR_BY_PALACE[OPPOSITE_PALACE[palaceNum]] || "";
	const oppositeStar = BASE_STAR_BY_PALACE[OPPOSITE_PALACE[palaceNum]] || "";
	const dayGan = getGan(pan && pan.ganzhi && pan.ganzhi.day);
	const monthGan = getGan(pan && pan.ganzhi && pan.ganzhi.month);
	const yearGan = getGan(pan && pan.ganzhi && pan.ganzhi.year);
	const timeGan = getGan(pan && pan.ganzhi && pan.ganzhi.time);
	const timeGanzhi = `${pan && pan.ganzhi && pan.ganzhi.time ? pan.ganzhi.time : ''}`;
	const xunShouLiuYi = getXunShouLiuYi(pan);
	const liuyiJiXing = LIUYI_JIXING_PALACE[tianGan] === palaceNum;
	const sanqiRuMu = (tianGan === '乙' && palaceNum === 3) || (tianGan === '丙' && palaceNum === 9) || (tianGan === '丁' && palaceNum === 7);
	const menPo = door ? isMenKeGong(door, palaceNum) : false;
	const menShouZhi = door ? isGongKeMen(door, palaceNum) : false;
	if(tianGan === '乙' && diGan === '辛'){ addPattern(out, '青龙逃走'); }
	if(tianGan === '辛' && diGan === '乙'){ addPattern(out, '白虎猖狂'); }
	if(tianGan === '癸' && diGan === '丁'){ addPattern(out, '螣蛇夭矫'); }
	if(tianGan === '丁' && diGan === '癸'){ addPattern(out, '朱雀投江'); }
	if(tianGan === '庚' && diGan === '丙'){ addPattern(out, '太白火荧'); }
	if(tianGan === '丙' && diGan === '庚'){ addPattern(out, '荧入太白'); }
	if(xunShouLiuYi && tianGan === xunShouLiuYi && diGan === '庚'){ addPattern(out, '飞宫格'); }
	if(xunShouLiuYi && tianGan === '庚' && diGan === xunShouLiuYi){ addPattern(out, '伏宫格'); }
	if(dayGan && tianGan === dayGan && diGan === '庚'){ addPattern(out, '飞干格'); }
	if(dayGan && tianGan === '庚' && diGan === dayGan){ addPattern(out, '伏干格'); }
	if(tianGan === '庚' && diGan === '癸'){ addPattern(out, '大格'); }
	if(tianGan === '庚' && diGan === '壬'){ addPattern(out, '小格'); }
	if(tianGan === '庚' && yearGan && diGan === yearGan){ addPattern(out, '年格'); }
	if(tianGan === '庚' && monthGan && diGan === monthGan){ addPattern(out, '月格'); }
	if(tianGan === '庚' && dayGan && diGan === dayGan){ addPattern(out, '日格'); }
	if(tianGan === '庚' && timeGan && diGan === timeGan){ addPattern(out, '时格'); }
	if(tianGan === '庚' && diGan === '己'){ addPattern(out, '刑格'); }
	if(tianGan === '己' && diGan === '庚'){ addPattern(out, '刑格返名'); }
	if(isBeiGe(pan, palaceNum, tianGan, diGan, dayGan, monthGan, yearGan, timeGan)){ addPattern(out, "悖格"); }
	if(xunShouLiuYi && tianGan === xunShouLiuYi && diGan === '癸'){ addPattern(out, '天网四张格'); }
	if(timeGan && tianGan === '壬' && diGan === timeGan){ addPattern(out, '地罗遮格'); }
	if(door && baseDoor && star && baseStar && door === baseDoor && star === baseStar){ addPattern(out, "伏吟"); }
	if(door && oppositeDoor && star && oppositeStar && door === oppositeDoor && star === oppositeStar){ addPattern(out, "返吟"); }
	if(liuyiJiXing){ addPattern(out, "六仪击刑"); }
	if(dayGan && WUBUYUSHI_TIME[dayGan] === timeGanzhi){ addPattern(out, "五不遇时"); }
	if(timeGan && tianGan === timeGan && SHIGAN_RUMU_GANZHI_SET.has(timeGanzhi)){ addPattern(out, "时干入墓"); }
	if(sanqiRuMu){ addPattern(out, '三奇入墓'); }
	if(menPo){ addPattern(out, "门迫"); }
	if(menShouZhi){ addPattern(out, "门受制"); }
	if(SAN_QI_SET.has(tianGan) && (sanqiRuMu || liuyiJiXing || menPo || menShouZhi)){ addPattern(out, '三奇受制'); }
	if(isStarDoorRuMu(star, door, palaceNum)){ addPattern(out, "星门入墓"); }
	return out;
}

function getFallbackText(value, fallback){
	const text = `${value || ''}`.trim();
	return text || fallback;
}

export function buildQimenBaGongPanelData(pan, palaceNum){
	const targetPalace = BAGONG_PALACE_NAME[palaceNum] ? palaceNum : BAGONG_PALACE_ORDER[0];
	const cell = findCell(pan, targetPalace);
	if(!pan || !cell){
		return {
			palaceNum: targetPalace,
			palaceName: BAGONG_PALACE_NAME[targetPalace] || "",
			tianGan: "",
			diGan: "",
			renDoor: "",
			baseDoor: BASE_DOOR_BY_PALACE[targetPalace] || "",
			godFull: "",
			jiPatterns: [],
			jiPatternDetails: [],
			xiongPatterns: [],
			xiongPatternDetails: [],
			tenGanText: '暂无盘式数据。',
			doorBaseText: '暂无盘式数据。',
			doorTianText: '暂无盘式数据。',
			godDoorText: '暂无盘式数据。',
			menFangYiGua: '',
			menFangYiGuaText: '无',
		};
	}
	const tianGan = `${cell.tianGan || ''}`;
	const diGan = `${cell.diGan || ''}`;
	const renDoor = getDoorChar(cell.door);
	const baseDoor = BASE_DOOR_BY_PALACE[targetPalace] || "";
	const godFull = getGodFull(cell.god);
	const tenGanText = getFallbackText(QIMEN_TENGAN_RESPONSE[`${tianGan}${diGan}`], '文中未列该十干组合。');
	const doorBaseText = getFallbackText(QIMEN_DOOR_BASE_RESPONSE[`${renDoor}${baseDoor}`], '文中未列该八门组合。');
	const doorTianText = getFallbackText(QIMEN_DOOR_TIANGAN_RESPONSE[`${renDoor}${tianGan}`], '文中未列该奇仪组合。');
	const godDoorText = getFallbackText(QIMEN_GOD_DOOR_RESPONSE[`${godFull}${renDoor}`], '文中未列该八神八门组合。');
	const jiPatterns = calcJiPatterns(pan, targetPalace, cell);
	const xiongPatterns = calcXiongPatterns(pan, targetPalace, cell);
	const menFangYiGuaData = buildMenFangYiGuaData(targetPalace, renDoor);
	return {
		palaceNum: targetPalace,
		palaceName: cell.palaceName || BAGONG_PALACE_NAME[targetPalace] || "",
		tianGan,
		diGan,
		renDoor,
		baseDoor,
		godFull,
		jiPatterns,
		jiPatternDetails: buildPatternInterpretationList(jiPatterns, 'ji'),
		xiongPatterns,
		xiongPatternDetails: buildPatternInterpretationList(xiongPatterns, 'xiong'),
		tenGanText,
		doorBaseText,
		doorTianText,
		godDoorText,
		menFangYiGua: menFangYiGuaData.displayName,
		menFangYiGuaText: menFangYiGuaData.text,
	};
}

export function buildQimenFuShiYiGua(pan){
	if(!pan){
		return {
			guaName: '',
			displayName: '无',
			innerPalace: 0,
			outerPalace: 0,
			innerBagua: '',
			outerBagua: '',
			text: '无',
		};
	}
	return buildFuShiYiGuaData(pan);
}

export function buildQimenBaGongSnapshotLines(pan){
	if(!pan){
		return [];
	}
	const lines = ['[八宫详解]'];
	BAGONG_PALACE_ORDER.forEach((palaceNum)=>{
		const item = buildQimenBaGongPanelData(pan, palaceNum);
		const palaceName = item.palaceName || BAGONG_PALACE_NAME[palaceNum] || '';
		lines.push(`${palaceName}宫：`);
		if(item.jiPatternDetails && item.jiPatternDetails.length){
			lines.push('奇门吉格：');
			item.jiPatternDetails.forEach((text)=>lines.push(`- ${text}`));
		}else{
			lines.push('奇门吉格：无');
		}
		if(item.xiongPatternDetails && item.xiongPatternDetails.length){
			lines.push('奇门凶格：');
			item.xiongPatternDetails.forEach((text)=>lines.push(`- ${text}`));
		}else{
			lines.push('奇门凶格：无');
		}
		lines.push(`十干克应（天${item.tianGan || "—"}加地${item.diGan || "—"}）：${item.tenGanText}`);
		lines.push(`八门克应（人${item.renDoor || "—"}加地${item.baseDoor || "—"}）：${item.doorBaseText}`);
		lines.push(`奇仪主应（人${item.renDoor || "—"}加天${item.tianGan || "—"}）：${item.doorTianText}`);
		lines.push(`八神加八门（${item.godFull || "—"}加${item.renDoor || "—"}门）：${item.godDoorText}`);
		lines.push(`奇门演卦（门方）：${item.menFangYiGuaText || '无'}`);
		lines.push('');
	});
	if(lines[lines.length - 1] === ''){
		lines.pop();
	}
	return lines;
}

export {
	BAGONG_PALACE_ORDER,
	BAGONG_PALACE_NAME,
};
