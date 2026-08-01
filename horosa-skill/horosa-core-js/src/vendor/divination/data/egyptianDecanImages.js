// divination/data/egyptianDecanImages.js
// 三十六旬像:每旬「所升之象」与「所主之事」。
//
// 性质与底本:
//   旬像是旬体系在护符一路上的落点 —— 古人不只给旬派主星,还给每旬一个可摹写的形象,
//   刻之为符。此处三十六条按公版古籍(十七世纪英译本,早已过版权期)逐条译出,形象与所主
//   均照原文,不增补、不合并、不替原文补缺。原文未给所主者照实留空(见 taurus1)。
//   古籍在此章开篇即言此系传自更早的星表传统,故与旬名录、旬主星同属一脉,可并观。
//
// 与既有 HERMES_TALISMAN(秘名/身体部位/主管疾病)互补:那是护符的「用」,这是护符的「象」。
// 纯数据 + 纯函数,零后端、零请求。

/**
 * 36 条,zodiacal(黄道序)第 1..36 旬。
 *   image   所升之象(译文)
 *   effect  所主之事(译文);原文未给者为空串
 * 检索标签不另手写,一律由 effect 程序化切分(decanImageKeys) —— 标签恒为译文切片,
 * 不会悄悄混入非原文的概括词。
 */
export const DECAN_IMAGES = [
	{ greek: 1, sign: 'aries', n: 1, image: '一黑肤男子挺立,着白衣束带,身形壮硕,目泛赤色,力大而似含怒。', effect: '主胆气、刚毅、志高,亦主无所顾忌。' },
	{ greek: 2, sign: 'aries', n: 2, image: '一女子之形,外着红衣、内衬白衣,衣裾曳地。', effect: '主尊贵、位极、权柄之广。' },
	{ greek: 3, sign: 'aries', n: 3, image: '一白肤男子,面色苍白、发泛赤,着红衣;一手持金镯,一手举木杖,躁动似含怒——因所欲之善不得成。', effect: '主才思、温和、欢悦与美。' },
	{ greek: 4, sign: 'taurus', n: 1, image: '一裸身男子,或射者、或刈者、或耕者,出而播种、耕作、营建、聚落,按几何之法划分土地。', effect: '' },
	{ greek: 5, sign: 'taurus', n: 2, image: '一裸身男子,手中持钥。', effect: '主权能、显位、治众之权。' },
	{ greek: 6, sign: 'taurus', n: 3, image: '一男子,手中有蛇与镖。', effect: '主必然与获利,亦主困厄与役属。' },
	{ greek: 7, sign: 'gemini', n: 1, image: '一男子手中持杖,状如事人者。', effect: '主智慧,及数与技艺之学——然于此中无所得利。' },
	{ greek: 8, sign: 'gemini', n: 2, image: '一男子手中持管乐,另一人俯身掘地。', effect: '主不名誉、不端正之机巧(如伶人幻士之流),亦主劳苦与苦寻。' },
	{ greek: 9, sign: 'gemini', n: 3, image: '一男子寻求兵器;一愚者右手持鸟、左手持管乐。', effect: '主健忘、忿怒、鲁莽、戏谑、粗鄙与无益之言。' },
	{ greek: 10, sign: 'cancer', n: 1, image: '一少女之形,盛服而首戴冠。', effect: '主感觉之敏、心思之细,及为众所爱。' },
	{ greek: 11, sign: 'cancer', n: 2, image: '一男子衣冠端整;或一男一女对坐案前博戏。', effect: '主财富、欢乐、喜庆,及为女子所爱。' },
	{ greek: 12, sign: 'cancer', n: 3, image: '一猎者持矛与号角,纵犬出猎。', effect: '主人之争竞、追逐逃者,及以兵争与讼争取物。' },
	{ greek: 13, sign: 'leo', n: 1, image: '一男子骑狮。', effect: '主胆气、暴烈、酷虐、恶行、纵欲,及当受之劳。' },
	{ greek: 14, sign: 'leo', n: 2, image: '一像举手向上;一男子首戴冠,状若含怒而作威胁,右手拔剑出鞘,左手持圆盾。', effect: '主隐伏之争、不为人知之胜,主卑下之人,及争斗之由。' },
	{ greek: 15, sign: 'leo', n: 3, image: '一少年手中持鞭;一男子甚忧,面色不善。', effect: '主爱与交游,亦主为避争而失己之权。' },
	{ greek: 16, sign: 'virgo', n: 1, image: '一贤淑少女之形;一男子播撒种子。', effect: '主积财、调摄饮食、耕耘播种与聚落之兴。' },
	{ greek: 17, sign: 'virgo', n: 2, image: '一黑肤男子披兽皮;一男子须发丛生,手提袋囊。', effect: '主得利、敛财与悭贪。' },
	{ greek: 18, sign: 'virgo', n: 3, image: '一白肤女子而失聪;或一老者倚杖而立。', effect: '主衰弱、疾病、肢体之损、树木之毁与土地之荒。' },
	{ greek: 19, sign: 'libra', n: 1, image: '一含怒男子之形,手中持管乐;一男子之形,正读书卷。', effect: '主为微弱可怜者伸直、助其抗强梁与恶人。' },
	{ greek: 20, sign: 'libra', n: 2, image: '二男子暴怒;一男子衣饰端整,坐于椅上。', effect: '主对恶之愤,及生活之安宁稳固、诸善丰足。' },
	{ greek: 21, sign: 'libra', n: 3, image: '一强横男子持弓,前有一裸身男子;又一男子一手持面包、一手持酒杯。', effect: '主邪欲、歌唱、游乐与饕餮。' },
	{ greek: 22, sign: 'scorpio', n: 1, image: '一女子面貌仪态皆美,二男子击之。', effect: '主端丽与美,亦主争斗、背弃、欺诈、诋毁与败亡。' },
	{ greek: 23, sign: 'scorpio', n: 2, image: '一裸身男子、一裸身女子;一男子坐地,身前二犬相咬。', effect: '主厚颜、欺诈与不实之交,亦主播弄祸端、构人争斗。' },
	{ greek: 24, sign: 'scorpio', n: 3, image: '一男子屈膝俯身,一女子以杖击之。', effect: '主沉湎、淫佚、忿怒、暴力与争斗。' },
	{ greek: 25, sign: 'sagittarius', n: 1, image: '一男子之形,披锁子甲,手持出鞘之剑。', effect: '主胆气、恶意与放任。' },
	{ greek: 26, sign: 'sagittarius', n: 2, image: '一女子哭泣,以衣覆身。', effect: '主忧伤,及为己身之惧。' },
	{ greek: 27, sign: 'sagittarius', n: 3, image: '一男子色如黄金;或一闲人执杖游戏。', effect: '主自任己意而固执不改,及趋恶事、生争端与可怖之事。' },
	{ greek: 28, sign: 'capricorn', n: 1, image: '一女子之形;一男子负满囊而行。', effect: '主出行与欢欣、得亦复失,兼带衰弱与卑下。' },
	{ greek: 29, sign: 'capricorn', n: 2, image: '二女子;一男子仰望飞鸟。', effect: '主求所不能成之事、寻所不可知之理。' },
	{ greek: 30, sign: 'capricorn', n: 3, image: '一女子身持贞洁、作事有智;一钱商于案上敛聚其钱。', effect: '主以审慎治事,及贪财之心与吝啬。' },
	{ greek: 31, sign: 'aquarius', n: 1, image: '一审慎男子之形;一女子纺绩。', effect: '主为求利而思虑劳作,处贫困卑微之中。' },
	{ greek: 32, sign: 'aquarius', n: 2, image: '一长须男子之形。', effect: '主明达、温和、谦抑、自在与善良风仪。' },
	{ greek: 33, sign: 'aquarius', n: 3, image: '一黑肤而含怒之男子。', effect: '主骄横与厚颜。' },
	{ greek: 34, sign: 'pisces', n: 1, image: '一男子肩负重物,衣着整好。', effect: '主行旅、迁徙,及经营衣食之资的操心。' },
	{ greek: 35, sign: 'pisces', n: 2, image: '一女子容色端好,妆饰齐整。', effect: '主有意于高远大事而身自趋之。' },
	{ greek: 36, sign: 'pisces', n: 3, image: '一裸身男子或少年,近旁一美貌少女,首饰以花。', effect: '主安逸、闲散、欢愉、淫佚与男女之亲。' },
];

// 检索标签:由所主之事按顿号/与/及/亦主 等切分而来,恒为译文切片(不另造概括词)。
export function decanImageKeys(effect){
	// 只认字符串:数字/对象等非文本入参一律回空(否则 `${0}`、`${{}}` 会被切成假标签)
	if(typeof effect !== 'string' || !effect){ return []; }
	const t = effect.replace(/^主/, '');
	if(!t){ return []; }
	return t
		.split(/[、,，;；。]|亦主|及为|及其|及|与|兼带/)
		.map((x) => x.replace(/^[之其所]+/, '').trim())
		// 不设长度上限:个别所主是一整句不可再分(如「有意于高远大事而身自趋之」),
		// 加上限会把它整条筛掉、变成空标签 —— 宁可保留长切片,也不丢原文。
		.filter((x) => x.length >= 1);
}

export const DECAN_IMAGE_BY_GREEK = DECAN_IMAGES.reduce((acc, d) => { acc[d.greek] = d; return acc; }, {});

export function decanImageAt(greekIdx){
	return DECAN_IMAGE_BY_GREEK[Number(greekIdx)] || null;
}

// 原文未给所主者(照实留空,不代为补)
export const DECAN_IMAGE_EFFECT_MISSING = DECAN_IMAGES.filter((d) => !d.effect).map((d) => d.greek);

export const DECAN_IMAGE_NOTE = '三十六旬像按公版古籍逐条译出:每旬有其「所升之象」与「所主之事」,象可摹写、刻之为符,'
	+ '与旬秘名、身体部位同为护符一路之用。个别旬原文只给象而未给所主,此处照实留空,不代为补缀。'
	+ '旬像随旬序锚定而重排,但象与所主系于旬本身,不随主星制改变。';

// 黄道外星座之效验(同章末所附;非旬像,单列以免混淆)
export const EXTRA_ZODIAC_FIGURES = [
	{ cn: '飞马', en: 'Pegasus', effect: '御马疾,护骑者于战阵。' },
	{ cn: '仙女', en: 'Andromeda', effect: '生夫妇之爱,言能和已离之偶。' },
	{ cn: '仙后', en: 'Cassiopeia', effect: '复衰弱之体,强其肢节。' },
	{ cn: '蛇夫', en: 'Serpentarius', effect: '驱毒,疗毒虫之螫。' },
	{ cn: '武仙', en: 'Hercules', effect: '与人战胜。' },
	{ cn: '天龙与二熊', en: 'Draco & the Bears', effect: '使人机敏、有才、勇武,见悦于神人。' },
	{ cn: '长蛇', en: 'Hydra', effect: '与智与富,能拒毒。' },
	{ cn: '半人马', en: 'Centaurus', effect: '与康健及长寿。' },
	{ cn: '天坛', en: 'Ara', effect: '存仁爱,使人见悦于神。' },
	{ cn: '鲸鱼', en: 'Cetus', effect: '使人可亲、审慎,水陆俱吉,助复失物。' },
	{ cn: '南船', en: 'Argo (the Ship)', effect: '与人涉水之安。' },
	{ cn: '天兔', en: 'Lepus (the Hare)', effect: '拒欺诳与狂乱。' },
];
export const EXTRA_ZODIAC_NOTE = '同章末另附黄道外星座之效验,系星座本身而非旬,故单列;此类不参与本盘旬像派生。';
