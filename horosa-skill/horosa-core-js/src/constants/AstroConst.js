// 极简 AstroConst shim（headless 六壬/七政 vendor 依赖闭合用）。
// 上游 星阙 AstroConst.js 含 1100+ 行占星常量；headless 路径只需 LIST_SIGNS（星座顺序，
// 供 LRConst.getSignZi 把行星星座 → 地支）。AstroColor 是 UI 配色，headless 不渲染，给空 stub
// 仅为满足 import + getSigColor/getHouseColor 不抛（被调用时返回 undefined，无害）。

export const ARIES = 'Aries';
export const TAURUS = 'Taurus';
export const GEMINI = 'Gemini';
export const CANCER = 'Cancer';
export const LEO = 'Leo';
export const VIRGO = 'Virgo';
export const LIBRA = 'Libra';
export const SCORPIO = 'Scorpio';
export const SAGITTARIUS = 'Sagittarius';
export const CAPRICORN = 'Capricorn';
export const AQUARIUS = 'Aquarius';
export const PISCES = 'Pisces';

export const LIST_SIGNS = [
  ARIES, TAURUS, GEMINI, CANCER, LEO, VIRGO, LIBRA,
  SCORPIO, SAGITTARIUS, CAPRICORN, AQUARIUS, PISCES,
];

export const SUN = 'Sun';
export const MOON = 'Moon';
// 七政四余 政余格局 (guolaoMoira) 闭包 + AstroText 名表另需的对象 id（flatlib 标识，与排盘响应 objects[].id 一致）。
export const MERCURY = 'Mercury';
export const VENUS = 'Venus';
export const MARS = 'Mars';
export const JUPITER = 'Jupiter';
export const SATURN = 'Saturn';
export const NORTH_NODE = 'North Node';
export const SOUTH_NODE = 'South Node';
export const DARKMOON = 'Dark Moon';
export const PURPLE_CLOUDS = 'Purple Clouds';
export const ASC = 'Asc';
export const LIFEMASTERDEG74 = 'LifeMasterDeg74';
// 盘面对象 / 希腊点 / 宫 id —— 逐值抽自上游 constants/AstroConst.js:22-57（行星·小行星·虚点·中点）、:92-122（PARS_*）、
// :62-73（HOUSE1..12）、:84-86（黄道）。AstroText.js 的 AstroTxtMsg/AstroMsgCN 名表以这些常量为键：shim 缺它们时
// 键塌成字面 "undefined"，msg('Uranus') 就落回英文 id（七政 [相位]、三分主星/关键点等表曾因此印 Uranus/Chiron）。
export const URANUS = 'Uranus';
export const NEPTUNE = 'Neptune';
export const PLUTO = 'Pluto';
export const CHIRON = 'Chiron';
export const SYZYGY = 'Syzygy';
export const PHOLUS = 'Pholus';
export const CERES = 'Ceres';
export const PALLAS = 'Pallas';
export const JUNO = 'Juno';
export const VESTA = 'Vesta';
export const INTP_APOG = 'Intp_Apog';
export const INTP_PERG = 'Intp_Perg';
export const MOONSUN = 'MoonSun';
export const SATURNMARS = 'SaturnMars';
export const JUPITERVENUS = 'JupiterVenus';
export const HOUSE1 = 'House1';
export const HOUSE2 = 'House2';
export const HOUSE3 = 'House3';
export const HOUSE4 = 'House4';
export const HOUSE5 = 'House5';
export const HOUSE6 = 'House6';
export const HOUSE7 = 'House7';
export const HOUSE8 = 'House8';
export const HOUSE9 = 'House9';
export const HOUSE10 = 'House10';
export const HOUSE11 = 'House11';
export const HOUSE12 = 'House12';
export const TROPICAL = 'Tropical';
export const SIDEREAL = 'Sidereal';
export const PARS_SPIRIT = 'Pars Spirit';
export const PARS_FAITH = 'Pars Faith';
export const PARS_SUBSTANCE = 'Pars Substance';
export const PARS_WEDDING_MALE = 'Pars Wedding [Male]';
export const PARS_WEDDING_FEMALE = 'Pars Wedding [Female]';
export const PARS_SONS = 'Pars Sons';
export const PARS_FATHER = 'Pars Father';
export const PARS_MOTHER = 'Pars Mother';
export const PARS_BROTHERS = 'Pars Brothers';
export const PARS_DISEASES = 'Pars Diseases';
export const PARS_DEATH = 'Pars Death';
export const PARS_TRAVEL = 'Pars Travel';
export const PARS_FRIENDS = 'Pars Friends';
export const PARS_ENEMIES = 'Pars Enemies';
export const PARS_SATURN = 'Pars Saturn';
export const PARS_JUPITER = 'Pars Jupiter';
export const PARS_MARS = 'Pars Mars';
export const PARS_VENUS = 'Pars Venus';
export const PARS_MERCURY = 'Pars Mercury';
export const PARS_HORSEMANSHIP = 'Pars Horsemanship';
export const PARS_LIFE = 'Pars Life';
export const PARS_RADIX = 'Pars Radix';
export const PARS_EROS = 'Pars Eros';
export const PARS_NECESSITY = 'Pars Necessity';
export const PARS_COURAGE = 'Pars Courage';
export const PARS_VICTORY = 'Pars Victory';
export const PARS_NEMESIS = 'Pars Nemesis';
// 宿占快照（vendor/suzhan/suzhanSnapshot.js，v0.40 mingli F11）另需：四角 id / 福点 id、页面缺省星表
// DEFAULT_OBJECTS（models/app.js:201 planetDisplay 缺省）与 isTraditionPlanet —— 逐值抽自上游
// constants/AstroConst.js:41/80-82（id）与 :618-639（两张表 + 判定函数，函数体逐字）。
export const PARS_FORTUNA = 'Pars Fortuna';
// [古典·显赫计分]「四显赫点」（vendor/utils/astroClassicalDerived.js:381-386 EMINENCE_POINTS）按 AstroConst.PARS_SPIRIT 取精神点
// ——shim 缺它时该项 id 为 undefined，lotObj 取不到 → 静默少一点（上游「福点/精神点/根基点/擢升点」只剩三点）。逐值抽自上游
// constants/AstroConst.js:96。
export const DESC = 'Desc';
export const MC = 'MC';
export const IC = 'IC';

export const DEFAULT_OBJECTS = [
    SUN, MOON, MERCURY, VENUS, MARS, JUPITER, SATURN,
    NORTH_NODE, SOUTH_NODE, PARS_FORTUNA,
    ASC, MC
]

export const TRADITION_OBJECTS = [
    SUN, MOON, MERCURY, VENUS, MARS, JUPITER, SATURN,
    NORTH_NODE, SOUTH_NODE, DARKMOON, PURPLE_CLOUDS,
    ASC, DESC, MC, IC
]

let TraditionPlanets = new Set();

export function isTraditionPlanet(id){
    if(TraditionPlanets.size === 0){
        for(let i=0; i<TRADITION_OBJECTS.length; i++){
            TraditionPlanets.add(TRADITION_OBJECTS[i]);
        }
    }
    return TraditionPlanets.has(id);
}

// UI 配色 stub（headless 不渲染）；SignFill / 按星座取色被调用时返回 undefined。
export const AstroColor = { SignFill: {} };

// 星座属性表（庙/旺/陷/落/三分主星）—— 三分主星推运(triplicityRulers) 用 SignsProp[sign].Trip/.Ruler/.Exalt/.Exile/.Fall。
// vendored verbatim from 星阙 AstroConst.SignsProp（只引用本文件已定义的 7 颗行星常量）。
export const SignsProp = {
    Aries:{
        Ruler: MARS,
        Exalt: SUN,
        Exile: VENUS,
        Fall: SATURN,
        Trip: [SUN, JUPITER, SATURN],
        FallDeg: 21,
        ExaltDeg: 19,
    },
    Taurus:{
        Ruler: VENUS,
        Exalt: MOON,
        Exile: MARS,
        Fall: null,
        Trip: [VENUS, MOON, MARS],
        FallDeg: null,
        ExaltDeg: 3,
    },
    Gemini:{
        Ruler: MERCURY,
        Exalt: null,
        Exile: JUPITER,
        Fall: null,
        Trip: [SATURN, MERCURY, JUPITER],
        FallDeg: 28,
        ExaltDeg: 15,
    },
    Cancer:{
        Ruler: MOON,
        Exalt: JUPITER,
        Exile: SATURN,
        Fall: MARS,
        Trip: [VENUS, MARS, MOON],
    },
    Leo:{
        Ruler: SUN,
        Exalt: null,
        Exile: SATURN,
        Fall: null,
        Trip: [SUN, JUPITER, SATURN],
        FallDeg: null,
        ExaltDeg: null,
    },
    Virgo:{
        Ruler: MERCURY,
        Exalt: MERCURY,
        Exile: JUPITER,
        Fall: VENUS,
        Trip: [VENUS, MOON, MARS],
        FallDeg: 27,
        ExaltDeg: 15,
    },
    Libra:{
        Ruler: VENUS,
        Exalt: SATURN,
        Exile: MARS,
        Fall: SUN,
        Trip: [SATURN, MERCURY, JUPITER],
        FallDeg: 19,
        ExaltDeg: 21,
    },
    Scorpio:{
        Ruler: MARS,
        Exalt: null,
        Exile: VENUS,
        Fall: MOON,
        Trip: [VENUS, MARS, MOON],
        FallDeg: 3,
        ExaltDeg: null,
    },
    Sagittarius:{
        Ruler: JUPITER,
        Exalt: null,
        Exile: MERCURY,
        Fall: null,
        Trip: [SUN, JUPITER, SATURN],
        FallDeg: null,
        ExaltDeg: null,
    },
    Capricorn:{
        Ruler: SATURN,
        Exalt: MARS,
        Exile: MOON,
        Fall: JUPITER,
        Trip: [VENUS, MOON, MARS],
        FallDeg: 15,
        ExaltDeg: 28,
    },
    Aquarius:{
        Ruler: SATURN,
        Exalt: null,
        Exile: SUN,
        Fall: null,
        Trip: [SATURN, MERCURY, JUPITER],
        FallDeg: null,
        ExaltDeg: null,
    },
    Pisces:{
        Ruler: JUPITER,
        Exalt: VENUS,
        Exile: MERCURY,
        Fall: MERCURY,
        Trip: [VENUS, MARS, MOON],
        FallDeg: 15,
        ExaltDeg: 27,
    },
};

// 宫制表 —— 逐值抽自上游 `constants/AstroConst.js:939-965`（v3.13.0 行号；v3.11.3 时为 :1045-1071，值未变）（v0.26.0 天星择日入册时补）。
// tianxingSnapshot 的 [征象搜索配置] 段按 cfg.hsys 查这张表出中文/拉丁宫制名；缺它该行恒空。
// 顺序即 value，勿重排：上游用下标当 value 语义，重排会让宫制串位。
export const HOUSE_SYSTEM_OPTIONS = [
    { value: 0, label: '整宫制' },
    { value: 1, label: 'Alcabitus' },
    { value: 2, label: 'Regiomontanus' },
    { value: 3, label: 'Placidus' },
    { value: 4, label: 'Koch' },
    { value: 5, label: 'Vehlow Equal' },
    { value: 6, label: 'Polich Page' },
    { value: 7, label: 'Sripati' },
    { value: 8, label: '天顶为10宫中点等宫制' },
    { value: 9, label: 'Porphyry' },
    { value: 10, label: 'Campanus' },
    { value: 11, label: 'Equal' },
    { value: 12, label: 'Equal MC' },
    { value: 13, label: 'Meridian' },
    { value: 14, label: 'Horizontal' },
    { value: 15, label: 'Morinus' },
    { value: 16, label: 'Carter Poli-Equatorial' },
    { value: 17, label: 'Sunshine' },
    { value: 18, label: 'Sunshine Alternate' },
    { value: 19, label: 'Krusinski-Pisa-Goelzer' },
    { value: 20, label: 'Pullen SD' },
    { value: 21, label: 'Pullen SR' },
    { value: 22, label: 'APC Houses' },
    { value: 23, label: 'Savard-A' },
    { value: 24, label: '福点整宫制' },
];

// ── 上游 constants/AstroText.js 三张名表（AstroMsg / AstroTxtMsg / AstroMsgCN）用作键的其余 id（v0.50.x 上游 v3.14.0 同步补齐）。
// 名表以 `AstroConst.X` 为键：这里缺一个常量，名表里那一行就落到 `undefined` 键上——查不到、不报错（AGENTS §5 闭包提取陷阱③）。
// 此前缺 49 颗恒星 / 24 个宫制 / 月相四象限 / 八颗汉堡虚星 / 白羊点 / 宿命点等：v3.14.0 [盘面细节] 的恒星相位经
// vendor/utils/starNamesCn.js 查 `AstroMsg[星名]`，查不到就回落次一级的表（「狮心轩辕十四」印成「轩辕十四」、「天狼星」印成「天狼」）。
// 逐值取自上游 constants/AstroConst.js（tests/test_sync314_western_shims.py 对上游源逐值比对；上游原序）。
export const CUPIDO = 'Cupido';
export const HADES = 'Hades';
export const ZEUS = 'Zeus';
export const KRONOS = 'Kronos';
export const APOLLON = 'Apollon';
export const ADMETOS = 'Admetos';
export const VULCANUS = 'Vulcanus';
export const POSEIDON = 'Poseidon';
export const ARIES_POINT = 'AriesPoint';
export const VERTEX = 'Vertex';
export const ANTIVERTEX = 'Antivertex';
export const EAST_POINT = 'EastPoint';
export const ERIS = 'Eris';
export const MOON_FIRST_QUARTER = 'First Quarter';
export const MOON_SECOND_QUARTER = 'Second Quarter';
export const MOON_THIRD_QUARTER = 'Third Quarter';
export const MOON_LAST_QUARTER = 'Last Quarter';
export const PARS_BASIS = 'Pars Basis';
export const PARS_EXALTATION = 'Pars Exaltation';
export const PARS_SONS_VALENS = 'Pars Sons Valens';
export const PARS_DAUGHTERS = 'Pars Daughters';
export const PARS_PRAXIS = 'Pars Praxis';
export const PARS_WEDDING_DOROTHEAN = 'Pars Wedding Dorothean';
export const HSYS_Whole_Sign = 'Whole Sign';
export const HSYS_Alcabitus = 'Alcabitus';
export const HSYS_Regiomontanus = 'Regiomontanus';
export const HSYS_Placidus = 'Placidus';
export const HSYS_Koch = 'Koch';
export const HSYS_Vehlow_Equal = 'Vehlow Equal';
export const HSYS_PolichPage = 'Polich Page';
export const HSYS_Sripati = 'Sripati';
export const HSYS_Porphyry = 'Porphyrius';
export const HSYS_Campanus = 'Campanus';
export const HSYS_Equal = 'Equal';
export const HSYS_Equal_MC = 'Equal MC';
export const HSYS_Meridian = 'Meridian';
export const HSYS_Horizontal = 'Azimuthal';
export const HSYS_Morinus = 'Morinus';
export const HSYS_Carter_Poli_Equatorial = 'Carter Poli-Equatorial';
export const HSYS_Sunshine = 'Sunshine';
export const HSYS_Sunshine_Alt = 'Sunshine Alternate';
export const HSYS_Krusinski = 'Krusinski-Pisa-Goelzer';
export const HSYS_Pullen_SD = 'Pullen SD';
export const HSYS_Pullen_SR = 'Pullen SR';
export const HSYS_APC = 'APC Houses';
export const HSYS_Savard_A = 'Savard-A';
export const HSYS_Fortuna_Whole = 'Fortuna_Whole';
export const STAR_ALGENIB = 'Algenib';
export const STAR_ALPHERATZ = 'Alpheratz';
export const STAR_ZAUR = 'Zaur';
export const STAR_ALGOL = 'Algol';
export const STAR_ALCYONE = 'Alcyone';
export const STAR_ALDEBARAN = 'Aldebaran';
export const STAR_RIGEL = 'Rigel';
export const STAR_CAPELLA = 'Capella';
export const STAR_BETELGEUSE = 'Betelgeuse';
export const STAR_SIRIUS = 'Sirius';
export const STAR_CANOPUS = 'Canopus';
export const STAR_CASTOR = 'Castor';
export const STAR_POLLUX = 'Pollux';
export const STAR_PROCYON = 'Procyon';
export const STAR_ASELLUS_BOREALIS = 'Asellus Borealis';
export const STAR_ASELLUS_AUSTRALIS = 'Asellus Australis';
export const STAR_ALPHARD = 'Alphard';
export const STAR_REGULUS = 'Regulus';
export const STAR_DENEBOLA = 'Denebola';
export const STAR_ALGORAB = 'Algorab';
export const STAR_SPICA = 'Spica';
export const STAR_ARCTURUS = 'Arcturus';
export const STAR_ALPHECCA = 'Alphecca';
export const STAR_ZUBEN_ELGENUBI = 'Zuben Elgenubi';
export const STAR_ZUBEN_ELSCHEMALI = 'Zuben Eshamali';
export const STAR_UNUKALHAI = 'Unukalhai';
export const STAR_AGENA = 'Agena';
export const STAR_RIGEL_CENTAURUS = 'Rigel Kentaurus';
export const STAR_ANTARES = 'Antares';
export const STAR_LESATH = 'Lesath';
export const STAR_VEGA = 'Vega';
export const STAR_ALTAIR = 'Altair';
export const STAR_DENEB_ALGEDI = 'Deneb Algedi';
export const STAR_FOMALHAUT = 'Fomalhaut';
export const STAR_DENEB_ADIGE = 'Deneb';
export const STAR_ACHERNAR = 'Achernar';
