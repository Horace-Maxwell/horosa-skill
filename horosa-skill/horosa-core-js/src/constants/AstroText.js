import * as AstroConst from './AstroConst.js'

export const Gender = {
	'-1': '未知',
	'0': '女',
	'1': '男',
};

export const CommBool = {
	'0': '否',
	'1': '是'
};

export const ChartOptionText = {
	'1': '行星',
	'2': '相位线',
	'4': '二十七宿',
	'8': '三分主星（仅经典）',
	'16': '行星与落座同色',
	'32': '显示宫头度数',
	'64': '信息在星盘中心',
	'128': '显示四角点连线',
	'256': '行星文本正向',
	'512': '星座入垣擢升星（仅经典）',
	'1024': '埃及界',
	'2048': '外刻度线',
	'4096': '内刻度线',
	'8192': '行星度数',
	'16384': '三王星间相位线',
	'32768': '行星二十八宿度数',
	'65536': '三维盘显示天球黄纬线',
	'131072': '三维盘显示赤纬线',
	'262144': '三维盘显示赤经线',
	'524288': '三维盘赤道盘半径与天球一致',
	'1048576': '三维盘显示地球',
	'2097152': '三维盘星体用符号展示',
};

export const PrettyAstroMsg = {};
PrettyAstroMsg[AstroConst.ARIES] = 'm';
PrettyAstroMsg[AstroConst.TAURUS] = 'n';
PrettyAstroMsg[AstroConst.GEMINI] = 'o';
PrettyAstroMsg[AstroConst.CANCER] = 'p';
PrettyAstroMsg[AstroConst.LEO] = 'q';
PrettyAstroMsg[AstroConst.VIRGO] = 'r';
PrettyAstroMsg[AstroConst.LIBRA] = 's';
PrettyAstroMsg[AstroConst.SCORPIO] = 't';
PrettyAstroMsg[AstroConst.SAGITTARIUS] = 'u';
PrettyAstroMsg[AstroConst.CAPRICORN] = 'v';
PrettyAstroMsg[AstroConst.AQUARIUS] = 'w';
PrettyAstroMsg[AstroConst.PISCES] = 'x';

export const AstroMsgCN = {
	House1: '1宫 - 命宫',
	House2: '2宫 - 财帛宫',
	House3: '3宫 - 兄弟宫',
	House4: '4宫 - 田宅宫',
	House5: '5宫 - 子女宫 / 男女宫',
	House6: '6宫 - 奴仆宫',
	House7: '7宫 - 夫妻宫',
	House8: '8宫 - 疾厄宫',
	House9: '9宫 - 迁移宫',
	House10: '10宫 - 官禄宫',
	House11: '11宫 - 福德宫',
	House12: '12宫 - 玄秘宫 / 相貌宫',
};
AstroMsgCN[AstroConst.ARIES] = '白羊';
AstroMsgCN[AstroConst.TAURUS] = '金牛';
AstroMsgCN[AstroConst.GEMINI] = '双子';
AstroMsgCN[AstroConst.CANCER] = '巨蟹';
AstroMsgCN[AstroConst.LEO] = '狮子';
AstroMsgCN[AstroConst.VIRGO] = '处女';
AstroMsgCN[AstroConst.LIBRA] = '天秤';
AstroMsgCN[AstroConst.SCORPIO] = '天蝎';
AstroMsgCN[AstroConst.SAGITTARIUS] = '射手';
AstroMsgCN[AstroConst.CAPRICORN] = '摩羯';
AstroMsgCN[AstroConst.AQUARIUS] = '水瓶';
AstroMsgCN[AstroConst.PISCES] = '双鱼';

AstroMsgCN[AstroConst.SUN] = '太阳';
AstroMsgCN[AstroConst.MOON] = '月亮';
AstroMsgCN[AstroConst.MERCURY] = '水星';
AstroMsgCN[AstroConst.VENUS] = '金星';
AstroMsgCN[AstroConst.MARS] = '火星';
AstroMsgCN[AstroConst.JUPITER] = '木星';
AstroMsgCN[AstroConst.SATURN] = '土星';
AstroMsgCN[AstroConst.URANUS] = '天王星';
AstroMsgCN[AstroConst.NEPTUNE] = '海王星';
AstroMsgCN[AstroConst.PLUTO] = '冥王星';
AstroMsgCN[AstroConst.CHIRON] = '凯龙星';
AstroMsgCN[AstroConst.CUPIDO] = '丘比特';
AstroMsgCN[AstroConst.HADES] = '哈迪斯';
AstroMsgCN[AstroConst.ZEUS] = '宙斯';
AstroMsgCN[AstroConst.KRONOS] = '克洛诺斯';
AstroMsgCN[AstroConst.APOLLON] = '阿波罗';
AstroMsgCN[AstroConst.ADMETOS] = '阿德墨托斯';
AstroMsgCN[AstroConst.VULCANUS] = '伏尔甘';
AstroMsgCN[AstroConst.POSEIDON] = '波塞冬';
AstroMsgCN[AstroConst.ARIES_POINT] = '白羊点';
AstroMsgCN[AstroConst.NORTH_NODE] = '北交';
AstroMsgCN[AstroConst.SOUTH_NODE] = '南交';
AstroMsgCN[AstroConst.SYZYGY] = '月亮朔望点';
AstroMsgCN[AstroConst.PARS_FORTUNA] = '福点';
AstroMsgCN[AstroConst.DARKMOON] = '莉莉丝(暗月)';
AstroMsgCN[AstroConst.PURPLE_CLOUDS] = '紫气-木余';
AstroMsgCN[AstroConst.PHOLUS] = '人龙星';
AstroMsgCN[AstroConst.CERES] = '谷神星';
AstroMsgCN[AstroConst.PALLAS] = '智神星';
AstroMsgCN[AstroConst.JUNO] = '婚神星';
AstroMsgCN[AstroConst.VESTA] = '灶神星';
AstroMsgCN[AstroConst.INTP_APOG] = '月亮平均远地点';
AstroMsgCN[AstroConst.INTP_PERG] = '月亮平均近地点';
AstroMsgCN[AstroConst.ASC] = '上升';
AstroMsgCN[AstroConst.DESC] = '下降';
AstroMsgCN[AstroConst.MC] = '天顶';
AstroMsgCN[AstroConst.IC] = '天底';
AstroMsgCN[AstroConst.MOONSUN] = '日月中点';
AstroMsgCN[AstroConst.SATURNMARS] = '火土中点';
AstroMsgCN[AstroConst.JUPITERVENUS] = '金木中点';
AstroMsgCN[AstroConst.LIFEMASTERDEG74] = '七政命度点';



export const AstroMsg = {
	Asp0: 'M',
	Asp60: 'P',
	Asp90: 'R',
	Asp120: 'S',
	Asp180: 'W',
	Asp45: 'O',
	Asp135: 'T',
	Asp30: 'N',
	Asp150: 'V',
	Retrograde: 'Z',
	Unknown: '{',
};

AstroMsg[AstroConst.ARIES] = 'a';
AstroMsg[AstroConst.TAURUS] = 'b';
AstroMsg[AstroConst.GEMINI] = 'c';
AstroMsg[AstroConst.CANCER] = 'd';
AstroMsg[AstroConst.LEO] = 'e';
AstroMsg[AstroConst.VIRGO] = 'f';
AstroMsg[AstroConst.LIBRA] = 'g';
AstroMsg[AstroConst.SCORPIO] = 'h';
AstroMsg[AstroConst.SAGITTARIUS] = 'i';
AstroMsg[AstroConst.CAPRICORN] = 'j';
AstroMsg[AstroConst.AQUARIUS] = 'k';
AstroMsg[AstroConst.PISCES] = 'l';


AstroMsg[AstroConst.SUN] = 'A';
AstroMsg[AstroConst.MOON] = 'B';
AstroMsg[AstroConst.MERCURY] = 'C';
AstroMsg[AstroConst.VENUS] = 'D';
AstroMsg[AstroConst.MARS] = 'E';
AstroMsg[AstroConst.JUPITER] = 'F';
AstroMsg[AstroConst.SATURN] = 'G';
AstroMsg[AstroConst.URANUS] = 'H';
AstroMsg[AstroConst.NEPTUNE] = 'I';
AstroMsg[AstroConst.PLUTO] = 'J';
AstroMsg[AstroConst.NORTH_NODE] = 'K';
AstroMsg[AstroConst.SOUTH_NODE] = 'L';
AstroMsg[AstroConst.DARKMOON] = 'v';
AstroMsg[AstroConst.PURPLE_CLOUDS] = 'w';
AstroMsg[AstroConst.PARS_FORTUNA] = 'p';
AstroMsg[AstroConst.SYZYGY] = 'z';
AstroMsg[AstroConst.CHIRON] = 'y';

AstroMsg[AstroConst.ASC] = '0';
AstroMsg[AstroConst.DESC] = '3';
AstroMsg[AstroConst.MC] = '1';
AstroMsg[AstroConst.IC] = '2';

AstroMsg[AstroConst.PARS_SPIRIT] = 'o';
AstroMsg[AstroConst.PARS_FAITH] = '{';
AstroMsg[AstroConst.PARS_SUBSTANCE] = '{';
AstroMsg[AstroConst.PARS_WEDDING_MALE] = '{';
AstroMsg[AstroConst.PARS_WEDDING_FEMALE] = '{';
AstroMsg[AstroConst.PARS_SONS] = '{';
AstroMsg[AstroConst.PARS_FATHER] = '{';
AstroMsg[AstroConst.PARS_MOTHER] = '{';
AstroMsg[AstroConst.PARS_BROTHERS] = '{';
AstroMsg[AstroConst.PARS_DISEASES] = '{';
AstroMsg[AstroConst.PARS_DEATH] = '{';
AstroMsg[AstroConst.PARS_TRAVEL] = '{';
AstroMsg[AstroConst.PARS_FRIENDS] = '{';
AstroMsg[AstroConst.PARS_ENEMIES] = '{';
AstroMsg[AstroConst.PARS_SATURN] = 'u';
AstroMsg[AstroConst.PARS_JUPITER] = 't';
AstroMsg[AstroConst.PARS_MARS] = 's';
AstroMsg[AstroConst.PARS_VENUS] = 'r';
AstroMsg[AstroConst.PARS_MERCURY] = 'q';
AstroMsg[AstroConst.PARS_HORSEMANSHIP] = '{';
AstroMsg[AstroConst.PARS_LIFE] = '{';
AstroMsg[AstroConst.PARS_RADIX] = '{';
AstroMsg[AstroConst.PARS_EROS] = '{';
AstroMsg[AstroConst.PARS_NECESSITY] = '{';
AstroMsg[AstroConst.PARS_COURAGE] = '{';
AstroMsg[AstroConst.PARS_VICTORY] = '{';
AstroMsg[AstroConst.PARS_NEMESIS] = '{';
AstroMsg[AstroConst.PHOLUS] = '8';
AstroMsg[AstroConst.CERES] = '4';
AstroMsg[AstroConst.PALLAS] = '5';
AstroMsg[AstroConst.JUNO] = '6';
AstroMsg[AstroConst.VESTA] = '7';
AstroMsg[AstroConst.INTP_APOG] = 'Y';
AstroMsg[AstroConst.INTP_PERG] = '$';
AstroMsg[AstroConst.MOONSUN] = 'Q';
AstroMsg[AstroConst.SATURNMARS] = 'X';
AstroMsg[AstroConst.JUPITERVENUS] = 'U';
AstroMsg[AstroConst.LIFEMASTERDEG74] = '{';


AstroMsg['ruler'] = '本垣';
AstroMsg['exalt'] = '擢升';
AstroMsg['dayTrip'] = '日三分';
AstroMsg['nightTrip'] = '夜三分';
AstroMsg['partTrip'] = '共管三分';
AstroMsg['term'] = '界';
AstroMsg['face'] = '十度';
AstroMsg['exile'] = '陷';
AstroMsg['fall'] = '落';

AstroMsg['Hayyiz'] = '得时得地';
AstroMsg['DemiHayyiz'] = '得时不得地';
AstroMsg['InWrongPos'] = '失时';
AstroMsg['Cazimi'] = '日熔';
AstroMsg['Combust'] = '灼伤';
AstroMsg['Sunbeams'] = '日光蔽匿';

AstroMsg[AstroConst.HOUSE1] = '第一宫';
AstroMsg[AstroConst.HOUSE2] = '第二宫';
AstroMsg[AstroConst.HOUSE3] = '第三宫';
AstroMsg[AstroConst.HOUSE4] = '第四宫';
AstroMsg[AstroConst.HOUSE5] = '第五宫';
AstroMsg[AstroConst.HOUSE6] = '第六宫';
AstroMsg[AstroConst.HOUSE7] = '第七宫';
AstroMsg[AstroConst.HOUSE8] = '第八宫';
AstroMsg[AstroConst.HOUSE9] = '第九宫';
AstroMsg[AstroConst.HOUSE10] = '第十宫';
AstroMsg[AstroConst.HOUSE11] = '第十一宫';
AstroMsg[AstroConst.HOUSE12] = '第十二宫';

AstroMsg[AstroConst.MOON_FIRST_QUARTER] = '第一象限';
AstroMsg[AstroConst.MOON_SECOND_QUARTER] = '第二象限';
AstroMsg[AstroConst.MOON_THIRD_QUARTER] = '第三象限';
AstroMsg[AstroConst.MOON_LAST_QUARTER] = '第四象限';

AstroMsg[AstroConst.STAR_ALGENIB] = '壁宿一';
AstroMsg[AstroConst.STAR_ALPHERATZ] = '壁宿二';
AstroMsg[AstroConst.STAR_ZAUR] = '天苑一';
AstroMsg[AstroConst.STAR_ALGOL] = '大陵五';
AstroMsg[AstroConst.STAR_ALCYONE] = '昴宿六';
AstroMsg[AstroConst.STAR_ALDEBARAN] = '毕宿五';
AstroMsg[AstroConst.STAR_RIGEL] = '参宿七';
AstroMsg[AstroConst.STAR_CAPELLA] = '五车二';
AstroMsg[AstroConst.STAR_BETELGEUSE] = '参宿四';
AstroMsg[AstroConst.STAR_SIRIUS] = '天狼星';
AstroMsg[AstroConst.STAR_CANOPUS] = '老人星';
AstroMsg[AstroConst.STAR_CASTOR] = '北河二';
AstroMsg[AstroConst.STAR_POLLUX] = '北河三';
AstroMsg[AstroConst.STAR_PROCYON] = '南河三';
AstroMsg[AstroConst.STAR_ASELLUS_BOREALIS] = '鬼宿三';
AstroMsg[AstroConst.STAR_ASELLUS_AUSTRALIS] = '鬼宿四';
AstroMsg[AstroConst.STAR_ALPHARD] = '星宿一';
AstroMsg[AstroConst.STAR_REGULUS] = '狮心轩辕十四';
AstroMsg[AstroConst.STAR_DENEBOLA] = '五帝座一';
AstroMsg[AstroConst.STAR_ALGORAB] = '轸宿三';
AstroMsg[AstroConst.STAR_SPICA] = '角宿一';
AstroMsg[AstroConst.STAR_ARCTURUS] = '大角';
AstroMsg[AstroConst.STAR_ALPHECCA] = '贯索四';
AstroMsg[AstroConst.STAR_ZUBEN_ELGENUBI] = '氐宿一';
AstroMsg[AstroConst.STAR_ZUBEN_ELSCHEMALI] = '氐宿四';
AstroMsg[AstroConst.STAR_UNUKALHAI] = '天市右垣七';
AstroMsg[AstroConst.STAR_AGENA] = '马腹一';
AstroMsg[AstroConst.STAR_RIGEL_CENTAURUS] = '南門二';
AstroMsg[AstroConst.STAR_ANTARES] = '蝎心心宿二';
AstroMsg[AstroConst.STAR_LESATH] = '尾宿九';
AstroMsg[AstroConst.STAR_VEGA] = '织女星';
AstroMsg[AstroConst.STAR_ALTAIR] = '牛郎星';
AstroMsg[AstroConst.STAR_DENEB_ALGEDI] = '垒壁阵四';
AstroMsg[AstroConst.STAR_FOMALHAUT] = '北落师门';
AstroMsg[AstroConst.STAR_DENEB_ADIGE] = '天津四';
AstroMsg[AstroConst.STAR_ACHERNAR] = '水委一';


AstroMsg[AstroConst.SIDEREAL] = '恒星黄道';
AstroMsg[AstroConst.TROPICAL] = '回归黄道';

AstroMsg[AstroConst.HSYS_Whole_Sign] = '整宫制';
AstroMsg[AstroConst.HSYS_Alcabitus] = 'Alcabitus';
AstroMsg[AstroConst.HSYS_Regiomontanus] = 'Regiomontanus';
AstroMsg[AstroConst.HSYS_Placidus] = 'Placidus';
AstroMsg[AstroConst.HSYS_Koch] = 'Koch';
AstroMsg[AstroConst.HSYS_Vehlow_Equal] = 'Vehlow Equal';
AstroMsg[AstroConst.HSYS_PolichPage] = 'Polich Page';
AstroMsg[AstroConst.HSYS_Sripati] = 'Sripati';
AstroMsg[AstroConst.HSYS_Porphyry] = 'Porphyry';
AstroMsg[AstroConst.HSYS_Campanus] = 'Campanus';
AstroMsg[AstroConst.HSYS_Equal] = 'Equal';
AstroMsg[AstroConst.HSYS_Equal_MC] = 'Equal MC';
AstroMsg[AstroConst.HSYS_Meridian] = 'Meridian';
AstroMsg[AstroConst.HSYS_Horizontal] = 'Horizontal';
AstroMsg[AstroConst.HSYS_Morinus] = 'Morinus';
AstroMsg[AstroConst.HSYS_Carter_Poli_Equatorial] = 'Carter Poli-Equatorial';
AstroMsg[AstroConst.HSYS_Sunshine] = 'Sunshine';
AstroMsg[AstroConst.HSYS_Sunshine_Alt] = 'Sunshine Alternate';
AstroMsg[AstroConst.HSYS_Krusinski] = 'Krusinski-Pisa-Goelzer';
AstroMsg[AstroConst.HSYS_Pullen_SD] = 'Pullen SD';
AstroMsg[AstroConst.HSYS_Pullen_SR] = 'Pullen SR';
AstroMsg[AstroConst.HSYS_APC] = 'APC Houses';
AstroMsg[AstroConst.HSYS_Savard_A] = 'Savard-A';
AstroMsg[AstroConst.HSYS_Fortuna_Whole] = '福点整宫制';

export const AstroZiMsg = {};
AstroZiMsg[AstroConst.ARIES] = '戌';
AstroZiMsg[AstroConst.TAURUS] = '酉';
AstroZiMsg[AstroConst.GEMINI] = '申';
AstroZiMsg[AstroConst.CANCER] = '未';
AstroZiMsg[AstroConst.LEO] = '午';
AstroZiMsg[AstroConst.VIRGO] = '巳';
AstroZiMsg[AstroConst.LIBRA] = '辰';
AstroZiMsg[AstroConst.SCORPIO] = '卯';
AstroZiMsg[AstroConst.SAGITTARIUS] = '寅';
AstroZiMsg[AstroConst.CAPRICORN] = '丑';
AstroZiMsg[AstroConst.AQUARIUS] = '子';
AstroZiMsg[AstroConst.PISCES] = '亥';

export const AstroTxtMsg = {
	Asp0: '0º',
	Asp60: '60º',
	Asp90: '90º',
	Asp120: '120º',
	Asp180: '180º',
	Asp45: '45º',
	Asp135: '135º',
	Asp30: '30º',
	Asp150: '150º',
};
AstroTxtMsg[AstroConst.ARIES] = '牡羊';
AstroTxtMsg[AstroConst.TAURUS] = '金牛';
AstroTxtMsg[AstroConst.GEMINI] = '双子';
AstroTxtMsg[AstroConst.CANCER] = '巨蟹';
AstroTxtMsg[AstroConst.LEO] = '狮子';
AstroTxtMsg[AstroConst.VIRGO] = '室女';
AstroTxtMsg[AstroConst.LIBRA] = '天秤';
AstroTxtMsg[AstroConst.SCORPIO] = '天蝎';
AstroTxtMsg[AstroConst.SAGITTARIUS] = '射手';
AstroTxtMsg[AstroConst.CAPRICORN] = '摩羯';
AstroTxtMsg[AstroConst.AQUARIUS] = '宝瓶';
AstroTxtMsg[AstroConst.PISCES] = '双鱼';


AstroTxtMsg[AstroConst.SUN] = '日';
AstroTxtMsg[AstroConst.MOON] = '月';
AstroTxtMsg[AstroConst.MERCURY] = '水';
AstroTxtMsg[AstroConst.VENUS] = '金';
AstroTxtMsg[AstroConst.MARS] = '火';
AstroTxtMsg[AstroConst.JUPITER] = '木';
AstroTxtMsg[AstroConst.SATURN] = '土';
AstroTxtMsg[AstroConst.URANUS] = '天';
AstroTxtMsg[AstroConst.NEPTUNE] = '海';
AstroTxtMsg[AstroConst.PLUTO] = '冥';
AstroTxtMsg[AstroConst.NORTH_NODE] = '北交';
AstroTxtMsg[AstroConst.SOUTH_NODE] = '南交';
AstroTxtMsg[AstroConst.DARKMOON] = '暗月';
AstroTxtMsg[AstroConst.PURPLE_CLOUDS] = '紫气';
AstroTxtMsg[AstroConst.PARS_FORTUNA] = '福点';
AstroTxtMsg[AstroConst.CHIRON] = '凯龙';
AstroTxtMsg[AstroConst.SYZYGY] = '月亮朔望点';
AstroTxtMsg[AstroConst.INTP_APOG] = '月亮平均远地点';
AstroTxtMsg[AstroConst.INTP_PERG] = '月亮平均近地点';
AstroTxtMsg[AstroConst.PHOLUS] = '人龙星';
AstroTxtMsg[AstroConst.CERES] = '谷神星';
AstroTxtMsg[AstroConst.PALLAS] = '智神星';
AstroTxtMsg[AstroConst.JUNO] = '婚神星';
AstroTxtMsg[AstroConst.VESTA] = '灶神星';

AstroTxtMsg[AstroConst.MOONSUN] = '日月中点';
AstroTxtMsg[AstroConst.SATURNMARS] = '火土中点';
AstroTxtMsg[AstroConst.JUPITERVENUS] = '金木中点';
AstroTxtMsg[AstroConst.LIFEMASTERDEG74] = '七政命度点';

AstroTxtMsg[AstroConst.ASC] = '上升';
AstroTxtMsg[AstroConst.DESC] = '下降';
AstroTxtMsg[AstroConst.MC] = '中天';
AstroTxtMsg[AstroConst.IC] = '天底';

// 不再硬编码岁差 Lahiri(现支持 47 ayanāṃśa);具体岁差由各处用 AstroConst.zodiacalDisplayText(zodiacal, siderealAyanamsa) 拼接。
AstroTxtMsg[AstroConst.SIDEREAL] = '恒星黄道';

AstroTxtMsg[AstroConst.PARS_SPIRIT] = '灵点';
AstroTxtMsg[AstroConst.PARS_FAITH] = '信心点';
AstroTxtMsg[AstroConst.PARS_SUBSTANCE] = '占有点';
AstroTxtMsg[AstroConst.PARS_WEDDING_MALE] = '婚姻点（男性）';
AstroTxtMsg[AstroConst.PARS_WEDDING_FEMALE] = '婚姻点（女性）';
AstroTxtMsg[AstroConst.PARS_SONS] = '子嗣点';
AstroTxtMsg[AstroConst.PARS_FATHER] = '父权点';
AstroTxtMsg[AstroConst.PARS_MOTHER] = '母爱点';
AstroTxtMsg[AstroConst.PARS_BROTHERS] = '友情点';
AstroTxtMsg[AstroConst.PARS_DISEASES] = '灾厄点';
AstroTxtMsg[AstroConst.PARS_DEATH] = '死亡点';
AstroTxtMsg[AstroConst.PARS_TRAVEL] = '旅行点';
AstroTxtMsg[AstroConst.PARS_FRIENDS] = '朋友点';
AstroTxtMsg[AstroConst.PARS_ENEMIES] = '宿敌点';
AstroTxtMsg[AstroConst.PARS_SATURN] = '罪点';
AstroTxtMsg[AstroConst.PARS_JUPITER] = '赢点';
AstroTxtMsg[AstroConst.PARS_MARS] = '勇点';
AstroTxtMsg[AstroConst.PARS_VENUS] = '爱点';
AstroTxtMsg[AstroConst.PARS_MERCURY] = '弱点';
AstroTxtMsg[AstroConst.PARS_HORSEMANSHIP] = '驾驭点';
AstroTxtMsg[AstroConst.PARS_LIFE] = '生命点';
AstroTxtMsg[AstroConst.PARS_RADIX] = '光耀点';
AstroTxtMsg[AstroConst.PARS_EROS] = '爱欲点';
AstroTxtMsg[AstroConst.PARS_NECESSITY] = '必然点';
AstroTxtMsg[AstroConst.PARS_COURAGE] = '勇气点';
AstroTxtMsg[AstroConst.PARS_VICTORY] = '胜利点';
AstroTxtMsg[AstroConst.PARS_NEMESIS] = '报应点';

// 汉堡学派 8 颗虚星 TNP。自带星图字体无虚星字形 → 盘面/列表用 2 字母拉丁缩写 + 中文名 tooltip。
AstroTxtMsg[AstroConst.CUPIDO] = '丘比特';
AstroTxtMsg[AstroConst.HADES] = '哈迪斯';
AstroTxtMsg[AstroConst.ZEUS] = '宙斯';
AstroTxtMsg[AstroConst.KRONOS] = '克洛诺斯';
AstroTxtMsg[AstroConst.APOLLON] = '阿波罗';
AstroTxtMsg[AstroConst.ADMETOS] = '阿德墨托斯';
AstroTxtMsg[AstroConst.VULCANUS] = '伏尔甘';
AstroTxtMsg[AstroConst.POSEIDON] = '波塞冬';

AstroTxtMsg[AstroConst.ARIES_POINT] = '白羊点';
export const UranianAbbr = {
	[AstroConst.CUPIDO]: 'Cu', [AstroConst.HADES]: 'Ha', [AstroConst.ZEUS]: 'Ze', [AstroConst.KRONOS]: 'Kr',
	[AstroConst.APOLLON]: 'Ap', [AstroConst.ADMETOS]: 'Ad', [AstroConst.VULCANUS]: 'Vu', [AstroConst.POSEIDON]: 'Po',
	[AstroConst.ARIES_POINT]: '♈',
};
export function isUranian(id){ return UranianAbbr[id] !== undefined; }
export function uranianGlyph(id){ return UranianAbbr[id] || AstroMsg[id] || id; }
// 实义据 Witte《Rules for Planetary Pictures》本源典籍（汉堡学派源头文献）。
export const URANIAN_MEANING = {
	[AstroConst.CUPIDO]: '社群·家庭·婚姻·艺术·团体/法人',
	[AstroConst.HADES]: '衰朽·匮乏·污秽·隐秘·过去·疾病',
	[AstroConst.ZEUS]: '受控之火·创造·领导·导向能量·生育',
	[AstroConst.KRONOS]: '权威·高位·政府·卓越·独立',
	[AstroConst.APOLLON]: '扩展·成功·科学贸易·众多·广远',
	[AstroConst.ADMETOS]: '凝滞·原料·收缩·专注·死亡·原始',
	[AstroConst.VULCANUS]: '强力·能量·支配·巨大势能',
	[AstroConst.POSEIDON]: '精神·理念·启迪·灵性·光',
};
