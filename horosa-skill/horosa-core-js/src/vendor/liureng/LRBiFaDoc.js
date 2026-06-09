// 六壬《毕法赋》100 法库 + A 档自动匹配引擎（解读层，纯前端）。
// 设计原则（宁缺勿滥）：只有「凭旬空 / 三传四课地支生克 / 遁干 / 天将所乘之支 / 课名」即可机械确定的法，才写 matcher 自动命中（tier='A' 且本文件登记了 matcher）；
// 其余只作文献浏览（不自动命中）。渲染层不标出处；凶吉断语在 UI 统一加"须合盘"尾注。
//
// matcher 只读 context（buildLiuRengReferenceContext 的产物），返回 null 或 { evidence:[...] }。

import * as LRConst from './LRConst.js';
import { ZhangSheng } from './LRZhangSheng.js';

// 全 100 法：{ no, name, verse, explain, tier:'A'|'B'|'C' }。tier 仅标注性质；是否自动命中以 BIFA_MATCHERS 是否登记为准。
export const BIFA_LIST = [
	{ no: 1, name: '前后引从升迁吉', verse: '前后引从升迁吉', explain: '初传居干(支)前为引、末传居后为从，主升官或迁宅', tier: 'A' },
	{ no: 2, name: '首尾相见始终宜', verse: '首尾相见始终宜', explain: '干上见旬尾、支上见旬首(或反之)成周遍格，所谋皆成', tier: 'A' },
	{ no: 3, name: '帘幕贵人高甲第', verse: '帘幕贵人高甲第', explain: '昼占夜贵、夜占昼贵临年命或日干，占试必高中', tier: 'B' },
	{ no: 4, name: '催官使者赴官期', verse: '催官使者赴官期', explain: '日鬼乘白虎加临日干或年命，赴任必速', tier: 'A' },
	{ no: 5, name: '六阳数足须公用', verse: '六阳数足须公用', explain: '四课三传地支皆居六阳，利公干不利私谋', tier: 'A' },
	{ no: 6, name: '六阴相继尽昏迷', verse: '六阴相继尽昏迷', explain: '四课三传地支皆居六阴，利阴谋私干不利公闻', tier: 'A' },
	{ no: 7, name: '旺禄临身徒妄作', verse: '旺禄临身徒妄作', explain: '日禄又作旺神临干上，宜守不宜别谋', tier: 'A' },
	{ no: 8, name: '权摄不正禄临支', verse: '权摄不正禄临支', explain: '日禄加临日支上，占事不自尊大、受屈于人', tier: 'A' },
	{ no: 9, name: '避难逃生须弃旧', verse: '避难逃生须弃旧', explain: '三传于日干无益(空/鬼/脱)，唯就干上受生，宜弃旧', tier: 'B' },
	{ no: 10, name: '朽木难雕别作为', verse: '朽木难雕别作为', explain: '斫轮课中卯为空亡，宜改业别图', tier: 'A' },
	{ no: 11, name: '众鬼虽彰全不畏', verse: '众鬼虽彰全不畏', explain: '三传皆日鬼但有救神制之，鬼不能害', tier: 'B' },
	{ no: 12, name: '虽忧狐假虎威仪', verse: '虽忧狐假虎威仪', explain: '干上神本克日，却赖支属之神制之，如狐假虎威', tier: 'B' },
	{ no: 13, name: '鬼贼当时无畏忌', verse: '鬼贼当时无畏忌', explain: '三传日鬼当令旺极贪荣不克日，防过时祸发', tier: 'B' },
	{ no: 14, name: '传财太旺反财亏', verse: '传财太旺反财亏', explain: '三传财在生旺之月反贪生，求之反费己财', tier: 'B' },
	{ no: 15, name: '脱上逢脱防虚诈', verse: '脱上逢脱防虚诈', explain: '日干生上神、上神又生天将，重重脱耗多虚诈', tier: 'A' },
	{ no: 16, name: '空上乘空事莫追', verse: '空上乘空事莫追', explain: '发用既旬空又乘天空，指空说空全无实象', tier: 'A' },
	{ no: 17, name: '进茹空亡宜退步', verse: '进茹空亡宜退步', explain: '三传连茹进而俱旬空，宜退步抽身就支干', tier: 'A' },
	{ no: 18, name: '踏脚空亡进用宜', verse: '踏脚空亡进用宜', explain: '三传连茹退而俱空(踏脚空亡)，宜进不宜退', tier: 'A' },
	{ no: 19, name: '胎财生气妻怀孕', verse: '胎财生气妻怀孕', explain: '日之胎神兼妻财又逢月内生气，占妻必孕', tier: 'C' },
	{ no: 20, name: '胎财死气损胎推', verse: '胎财死气损胎推', explain: '日之胎神兼妻财却逢月内死气，妇孕不育', tier: 'C' },
	{ no: 21, name: '交车相合交关利', verse: '交车相合交关利', explain: '日干与支上神合、日支与干上神合，宜交易', tier: 'A' },
	{ no: 22, name: '上下皆合两心齐', verse: '上下皆合两心齐', explain: '支干上神作六合、地盘亦六合，主客同心', tier: 'A' },
	{ no: 23, name: '彼求我事支传干', verse: '彼求我事支传干', explain: '初传从支上起、末传归干上，主他人来求我', tier: 'A' },
	{ no: 24, name: '我求彼事干传支', verse: '我求彼事干传支', explain: '初传从干上起、末传归支上，主我俯求于人', tier: 'A' },
	{ no: 25, name: '金日逢丁凶祸动', verse: '金日逢丁凶祸动', explain: '庚辛日三传年命日辰逢旬内丁神，必主凶动', tier: 'A' },
	{ no: 26, name: '水日逢丁财动之', verse: '水日逢丁财动之', explain: '壬癸日三传年命日辰逢旬内丁神，必主财动', tier: 'A' },
	{ no: 27, name: '传财化鬼财休觅', verse: '传财化鬼财休觅', explain: '三传皆财却生起干上日鬼伤干，取财致祸', tier: 'A' },
	{ no: 28, name: '传鬼化财钱险危', verse: '传鬼化财钱险危', explain: '三合皆鬼两课空、独存一字为财，财从险中出', tier: 'A' },
	{ no: 29, name: '眷属丰盈居狭宅', verse: '眷属丰盈居狭宅', explain: '三传生日干却脱日支，人口丰而居宅窄', tier: 'A' },
	{ no: 30, name: '屋宅宽广致人衰', verse: '屋宅宽广致人衰', explain: '三传脱盗日干反生日支，宅宽而人渐衰', tier: 'A' },
	{ no: 31, name: '三传递生人举荐', verse: '三传递生人举荐', explain: '三传递相生并生日干，主有人于上位举荐', tier: 'A' },
	{ no: 32, name: '三传互克众人欺', verse: '三传互克众人欺', explain: '三传递相克并克日干，主众人递互欺凌', tier: 'A' },
	{ no: 33, name: '有始无终难变易', verse: '有始无终难变易', explain: '初为干长生末为干墓则有始无终；初墓末生则先难后易', tier: 'A' },
	{ no: 34, name: '苦去甘来乐里悲', verse: '苦去甘来乐里悲', explain: '末克中所伤之初鬼则苦去甘来；互生反脱则乐里悲', tier: 'B' },
	{ no: 35, name: '人宅受脱俱招盗', verse: '人宅受脱俱招盗', explain: '干支上皆乘脱气(或互脱)，人被脱、宅招盗', tier: 'A' },
	{ no: 36, name: '干支皆败势倾颓', verse: '干支皆败势倾颓', explain: '干支上皆逢败气，身气血衰、宅崩颓', tier: 'A' },
	{ no: 37, name: '末助初兮三等论', verse: '末助初兮三等论', explain: '末传助初传，分助生日 / 助克干 / 助为财三等', tier: 'A' },
	{ no: 38, name: '闭口卦体两般推', verse: '闭口卦体两般推', explain: '旬尾加旬首乘元武为闭口，气塞于中，宜捕亡', tier: 'A' },
	{ no: 39, name: '太阳照武宜擒贼', verse: '太阳照武宜擒贼', explain: '元武坐太阳月将之上，贼形显露不劳捕捉', tier: 'B' },
	{ no: 40, name: '玄武加丁主失脱', verse: '玄武加丁主失脱', explain: '元武乘神加临丁神，主失脱逃亡', tier: 'A' },
	{ no: 41, name: '富贵干支逢禄马', verse: '富贵干支逢禄马', explain: '干上有支驿马、支上有干禄神，名真富贵卦', tier: 'A' },
	{ no: 42, name: '尊崇传内遇三奇', verse: '尊崇传内遇三奇', explain: '三传全遇甲戊庚或乙丙丁(遁干)，主封拜消灾', tier: 'A' },
	{ no: 43, name: '害贵讼直作屈断', verse: '害贵讼直作屈断', explain: '所用贵人被发用相害，占讼理直反屈断', tier: 'A' },
	{ no: 44, name: '课传俱贵转无依', verse: '课传俱贵转无依', explain: '四课三传皆昼夜贵人所聚，贵多反无依', tier: 'A' },
	{ no: 45, name: '昼夜贵加求两贵', verse: '昼夜贵加求两贵', explain: '六处有昼夜贵人相加，告贵须干涉两贵人', tier: 'A' },
	{ no: 46, name: '贵人差迭事参差', verse: '贵人差迭事参差', explain: '昼贵临夜地、夜贵临昼方，告贵不归一', tier: 'A' },
	{ no: 47, name: '贵虽在狱宜临干', verse: '贵虽在狱宜临干', explain: '贵人临辰戌(入狱)，乙辛日反名贵人临身宜投贵', tier: 'A' },
	{ no: 48, name: '鬼乘天乙乃神祗', verse: '鬼乘天乙乃神祗', explain: '日鬼乘天乙贵人临身，非鬼祟而为神祗为害', tier: 'A' },
	{ no: 49, name: '两贵受克难干贵', verse: '两贵受克难干贵', explain: '昼夜贵人皆立于受克之方，告贵不成', tier: 'A' },
	{ no: 50, name: '二贵皆空虚喜期', verse: '二贵皆空虚喜期', explain: '昼夜贵人皆值旬空，告贵虚喜而反有费', tier: 'A' },
	{ no: 51, name: '魁度天门关隔定', verse: '魁度天门关隔定', explain: '戌(天魁)加亥(天门)为用，谋用皆被阻隔', tier: 'A' },
	{ no: 52, name: '罡塞鬼户任谋为', verse: '罡塞鬼户任谋为', explain: '辰(天罡)加寅(鬼户)塞鬼门，众鬼不出任谋为', tier: 'A' },
	{ no: 53, name: '两蛇夹墓凶难免', verse: '两蛇夹墓凶难免', explain: '墓神覆日且上下皆螣蛇夹之，凶难免', tier: 'A' },
	{ no: 54, name: '虎视逢虎力难施', verse: '虎视逢虎力难施', explain: '柔日虎视课中天将又乘白虎，至惊至危', tier: 'A' },
	{ no: 55, name: '所谋多拙逢罗网', verse: '所谋多拙逢罗网', explain: '干上乘干前一辰、支上乘支前一辰(罗网)，谋事多拙', tier: 'A' },
	{ no: 56, name: '天网自裹己招非', verse: '天网自裹己招非', explain: '墓神覆日又占人本命作日墓，自招其祸', tier: 'B' },
	{ no: 57, name: '费有余而得不足', verse: '费有余而得不足', explain: '长生生气逢空、脱气鬼贼坐实，所得不偿所费', tier: 'B' },
	{ no: 58, name: '用破身心无所归', verse: '用破身心无所归', explain: '发用之财禄逢空被克、引入鬼乡，身心无所归', tier: 'B' },
	{ no: 59, name: '华盖覆日人昏晦', verse: '华盖覆日人昏晦', explain: '日干墓神(华盖)临干上发用，身位昏晦', tier: 'A' },
	{ no: 60, name: '太阳射宅屋光辉', verse: '太阳射宅屋光辉', explain: '太阳月将照临日支宅上，屋向阳明朗', tier: 'B' },
	{ no: 61, name: '干乘墓虎无占病', verse: '干乘墓虎无占病', explain: '日干墓神乘白虎临干，除占病外诸占昏迷凶恶', tier: 'A' },
	{ no: 62, name: '支乘墓虎有伏尸', verse: '支乘墓虎有伏尸', explain: '墓神乘白虎临日支并克支，宅有伏尸丧吊', tier: 'A' },
	{ no: 63, name: '彼此全伤防两损', verse: '彼此全伤防两损', explain: '日干日支各被其上神克伤，主两边俱损', tier: 'A' },
	{ no: 64, name: '夫妇芜淫各有私', verse: '夫妇芜淫各有私', explain: '干被支上神克、支被干上神克(芜淫)，各有私意', tier: 'A' },
	{ no: 65, name: '干墓并关人宅废', verse: '干墓并关人宅废', explain: '日干墓兼作四季关神发用，主人衰宅废', tier: 'A' },
	{ no: 66, name: '支坟财并旅程稽', verse: '支坟财并旅程稽', explain: '日支墓神作日干财发用，主商贩折本、在路阻程', tier: 'A' },
	{ no: 67, name: '受虎克神为病证', verse: '受虎克神为病证', explain: '白虎所乘之神被克，依其五行定所病脏腑', tier: 'C' },
	{ no: 68, name: '制鬼之位乃良医', verse: '制鬼之位乃良医', explain: '能制日鬼之神(日食神)即良医、救神，主解祸', tier: 'C' },
	{ no: 69, name: '虎乘遁鬼殃非浅', verse: '虎乘遁鬼殃非浅', explain: '白虎所加之神遁出旬干为日鬼，咎深难除', tier: 'A' },
	{ no: 70, name: '鬼临三四讼灾随', verse: '鬼临三四讼灾随', explain: '日鬼临于第三第四课，官词病患继至', tier: 'A' },
	{ no: 71, name: '病符克宅全家患', verse: '病符克宅全家患', explain: '病符(旧太岁)临日支又克支，主阖家病患', tier: 'A' },
	{ no: 72, name: '丧吊全逢挂缟衣', verse: '丧吊全逢挂缟衣', explain: '干支上全逢丧门吊客二煞，主披孝送亲', tier: 'A' },
	{ no: 73, name: '前后逼迫难进退', verse: '前后逼迫难进退', explain: '三传空不可进、脱气与鬼夹于后，宜守', tier: 'B' },
	{ no: 74, name: '空空如也事休追', verse: '空空如也事休追', explain: '三传皆旬空，占事指空话空全无实象', tier: 'A' },
	{ no: 75, name: '宾主不投刑在上', verse: '宾主不投刑在上', explain: '支干上神乘刑，宾主不投各有异心', tier: 'A' },
	{ no: 76, name: '彼此猜忌害相随', verse: '彼此猜忌害相随', explain: '干支上下或三传作六害，彼此猜忌相戾', tier: 'A' },
	{ no: 77, name: '互生俱生凡事益', verse: '互生俱生凡事益', explain: '干上生支、支上生干(互生)或各自生，凡事有益', tier: 'A' },
	{ no: 78, name: '互旺皆旺坐谋宜', verse: '互旺皆旺坐谋宜', explain: '干上为支旺神、支上为干旺神(互旺)，宜坐谋', tier: 'A' },
	{ no: 79, name: '干支值绝凡谋决', verse: '干支值绝凡谋决', explain: '干支上皆乘绝神，宜结绝凶事、释解官讼', tier: 'A' },
	{ no: 80, name: '人宅皆死各衰羸', verse: '人宅皆死各衰羸', explain: '干支上互乘死气(或全乘死气)，人宅皆衰', tier: 'A' },
	{ no: 81, name: '传墓入墓分憎爱', verse: '传墓入墓分憎爱', explain: '三传后传墓前传，吉神入墓为憎、凶神入墓为爱', tier: 'A' },
	{ no: 82, name: '不行传者考初时', verse: '不行传者考初时', explain: '中末传俱空亡(不行传)，但以初传断吉凶', tier: 'A' },
	{ no: 83, name: '万事喜忻三六合', verse: '万事喜忻三六合', explain: '三合成局又与中神作六合，凡谋皆遂', tier: 'A' },
	{ no: 84, name: '合中犯杀蜜中砒', verse: '合中犯杀蜜中砒', explain: '三合局而干支上犯刑冲害，恩中变怨', tier: 'A' },
	{ no: 85, name: '初遭夹克不由己', verse: '初遭夹克不由己', explain: '初传坐克方又被天将所伤(夹克)，身不由己', tier: 'A' },
	{ no: 86, name: '将逢内战所谋危', verse: '将逢内战所谋危', explain: '天将与所乘之神五行相战发用，所谋危', tier: 'A' },
	{ no: 87, name: '人宅坐墓甘招晦', verse: '人宅坐墓甘招晦', explain: '天盘干支皆坐地盘墓上，情愿受暗昧自招祸', tier: 'A' },
	{ no: 88, name: '干支乘墓各昏迷', verse: '干支乘墓各昏迷', explain: '干支上神全为墓神(墓覆日辰)，人宅昏沉', tier: 'A' },
	{ no: 89, name: '任信丁马须言动', verse: '任信丁马须言动', explain: '伏吟卦中传或干支见旬丁、天马驿马，须静中求动', tier: 'A' },
	{ no: 90, name: '来去俱空岂动宜', verse: '来去俱空岂动宜', explain: '返吟卦三传皆旬空，虽有动意实不动', tier: 'A' },
	{ no: 91, name: '虎临干鬼凶速速', verse: '虎临干鬼凶速速', explain: '日干之鬼上乘白虎，凶祸速中又速', tier: 'A' },
	{ no: 92, name: '龙加生气吉迟迟', verse: '龙加生气吉迟迟', explain: '青龙乘生干之神又作月内生气，徐徐发福', tier: 'A' },
	{ no: 93, name: '妄用三传灾福异', verse: '妄用三传灾福异', explain: '起三传若错则灾福不验，戒精核课式', tier: 'B' },
	{ no: 94, name: '喜惧空亡乃妙机', verse: '喜惧空亡乃妙机', explain: '克盗墓鬼宜空亡、生救财官忌空亡，分喜惧而断', tier: 'B' },
	{ no: 95, name: '六爻现卦防其克', verse: '六爻现卦防其克', explain: '三传成某六亲爻局，须防其所克之亲', tier: 'C' },
	{ no: 96, name: '旬内空亡逐类推', verse: '旬内空亡逐类推', explain: '按本旬空亡所落六亲逐类推其得失', tier: 'B' },
	{ no: 97, name: '所筮不入仍凭类', verse: '所筮不入仍凭类', explain: '所占类神不在六处，仍凭该类象推方所色目', tier: 'C' },
	{ no: 98, name: '非占现类勿言之', verse: '非占现类勿言之', explain: '课现之象若非所占之事，不可妄言', tier: 'C' },
	{ no: 99, name: '常问不应逢吉象', verse: '常问不应逢吉象', explain: '贵泰吉卦利贵人，常人无故占得反招灾咎', tier: 'B' },
	{ no: 100, name: '已灾凶逃返无疑', verse: '已灾凶逃返无疑', explain: '已见病讼灾后占得凶否卦，其灾反可消除', tier: 'B' },
];

// ---- A 档 matcher 工具 ----
const Z = LRConst.ZiList;
const zi = (b)=>`${b || ''}`.trim().substring(0, 1);
// 日禄（干→支）、五行墓（五行→墓支，火土同墓戌）。
const LU = { '甲': '寅', '乙': '卯', '丙': '巳', '丁': '午', '戊': '巳', '己': '午', '庚': '申', '辛': '酉', '壬': '亥', '癸': '子' };
const MU_BY_WX = { '木': '未', '火': '戌', '土': '戌', '金': '丑', '水': '辰' };
function inKong(ctx, b){ return ctx.xunKongBranches && ctx.xunKongBranches.indexOf(zi(b)) >= 0; }
function godOf(ctx, b){ return (ctx.branchGodMap && ctx.branchGodMap[zi(b)]) || ''; }
function godBranch(ctx, name){ if(!ctx.branchGodMap || !name){ return ''; } const ks = Object.keys(ctx.branchGodMap); for(let i=0; i<ks.length; i++){ if(ctx.branchGodMap[ks[i]] === name){ return ks[i]; } } return ''; }
// 🔒 branchGodMap 键＝地盘支；某天盘神之天将＝四课该课的天将(keRaw[i][0])，不可用 godOf(天盘神)（那查的是地盘格之将）。
function keUpGod(ctx, i){ const k = ctx.keRaw && ctx.keRaw[i]; return (k && k[0]) ? `${k[0]}` : ''; }
// 某天将所乘之「天盘神」＝该天将所在地盘格(godBranch)的天盘(branchUpMap[地盘])。
function godRideShen(ctx, name){ const gb = godBranch(ctx, name); return (gb && ctx.branchUpMap) ? (ctx.branchUpMap[zi(gb)] || '') : ''; }
function allIn(list, pool){ return list.length > 0 && list.every((b)=>pool.indexOf(zi(b)) >= 0); }
// A 生 B（我生者）：LRConst.isAccrue；A 克 B：LRConst.isRestrain。
function gen(a, b){ return !!(a && b) && LRConst.isAccrue(zi(a), zi(b)); }
function ke(a, b){ return !!(a && b) && LRConst.isRestrain(zi(a), zi(b)); }
function idxDelta(a, b){ const ia = Z.indexOf(zi(a)); const ib = Z.indexOf(zi(b)); if(ia < 0 || ib < 0){ return -99; } return (ib - ia + 12) % 12; }
function nextZhi(b){ const i = Z.indexOf(zi(b)); return i < 0 ? '' : Z[(i + 1) % 12]; }
function ganMu(ctx){ return MU_BY_WX[ctx.dayGanWuXing] || ''; }
function zhiMu(ctx){ return MU_BY_WX[ctx.dayZhiWuXing] || ''; }
function ganLu(ctx){ return LU[zi(ctx.dayGan)] || ''; }
// 日干在某支的十二长生名（ZhangSheng.ganzi 键＝「干_支」）。
function ganPhase(ctx, b){ try{ return (ZhangSheng && ZhangSheng.ganzi) ? (ZhangSheng.ganzi[`${zi(ctx.dayGan)}_${zi(b)}`] || '') : ''; }catch(e){ return ''; } }
// 天盘 top 加于 地盘 bottom（用真排盘 layout，方向无歧义）。
function branchOver(ctx, top, bottom){ const L = ctx.layout; if(!L || !Array.isArray(L.downZi) || !Array.isArray(L.upZi)){ return false; } const i = L.downZi.indexOf(zi(bottom)); return i >= 0 && zi(L.upZi[i]) === zi(top); }
function isFuYin(ctx){ const L = ctx.layout; return !!(L && Array.isArray(L.upZi) && Array.isArray(L.downZi) && L.upZi.length === 12 && L.upZi.every((b, i)=>zi(b) === zi(L.downZi[i]))); }
function isFanYin(ctx){ const L = ctx.layout; if(!(L && Array.isArray(L.upZi) && Array.isArray(L.downZi) && L.upZi.length === 12)){ return false; } return L.upZi.every((b, i)=>{ const di = Z.indexOf(zi(L.downZi[i])); return di >= 0 && Z.indexOf(zi(b)) === (di + 6) % 12; }); }
// 三合局集、天将五行、五行生克、六亲。
const SAN_HE_SETS = [['申', '子', '辰'], ['亥', '卯', '未'], ['寅', '午', '戌'], ['巳', '酉', '丑']];
const TIANJIANG_WX = { '贵人': '土', '螣蛇': '火', '朱雀': '火', '六合': '木', '勾陈': '土', '青龙': '木', '天空': '土', '白虎': '金', '太常': '土', '玄武': '水', '太阴': '金', '天后': '水' };
const WX_SHENG = { '木': '火', '火': '土', '土': '金', '金': '水', '水': '木' };
const WX_KE = { '木': '土', '土': '水', '水': '火', '火': '金', '金': '木' };
function wxOf(b){ return LRConst.GanZiWuXing[zi(b)] || ''; }
function isSanHeSet(list){ const s = (list || []).map(zi); if(s.length < 3) return false; const set = new Set(s); return SAN_HE_SETS.some((g)=>g.every((x)=>set.has(x))); }
function liuqinOf(ctx, b){ return (ctx.dayGan && LRConst.ZiLiuQin[zi(b)]) ? (LRConst.ZiLiuQin[zi(b)][zi(ctx.dayGan)] || '') : ''; }
function prevZhi(b){ const i = Z.indexOf(zi(b)); return i < 0 ? '' : Z[(i + 11) % 12]; }
function chongZhi(b){ const i = Z.indexOf(zi(b)); return i < 0 ? '' : Z[(i + 6) % 12]; }
const SEASON_WANG_WX = { spring: '木', summer: '火', autumn: '金', winter: '水' };
function seasonWangWx(ctx){ return SEASON_WANG_WX[ctx.season] || '土'; } // 四季月近似归并，偏严
function inCourse(ctx, b){ return (ctx.courseBranches || []).indexOf(zi(b)) >= 0; }
// 读 dayGodMap 子表（year/month/gan/zi/base）里某神煞所临支（值取末两位的支字）。
function shenshaBranch(ctx, mapName, key){ const m = ctx.dayGodMap && ctx.dayGodMap[mapName]; if(!m){ return ''; } if(m[key] !== undefined){ return zi(`${m[key]}`.slice(-2)); } const ks = Object.keys(m); for(let i=0; i<ks.length; i++){ if(ks[i].indexOf(key) >= 0){ return zi(`${m[ks[i]]}`.slice(-2)); } } return ''; }
// 日支天干在某支的十二长生名（用于支上神之旺/绝/死/沐浴）。
function zhiPhase(ctx, b){ try{ const zg = zi(ctx.dayZhiGan); return (zg && ZhangSheng && ZhangSheng.ganzi) ? (ZhangSheng.ganzi[`${zg}_${zi(b)}`] || '') : ''; }catch(e){ return ''; } }
function muOf(b){ return MU_BY_WX[wxOf(b)] || ''; }

// 仅登记「高置信度、纯机械可判」的法（凭旬空/三传四课地支生克/遁干/天将所乘之支/禄墓/课式 即可确定）。
// 键＝法 no。每个 matcher 只读 ctx，返回 null 或 {evidence:[...]}。其余法只浏览、不自动命中。
export const BIFA_MATCHERS = {
	5: (ctx)=>{ const all = ctx.courseBranches || []; return allIn(all, LRConst.YangZi) ? { evidence: ['四课三传地支全为阳支'] } : null; },
	6: (ctx)=>{ const all = ctx.courseBranches || []; return allIn(all, LRConst.YingZi) ? { evidence: ['四课三传地支全为阴支'] } : null; },
	7: (ctx)=>{ const lu = ganLu(ctx); return (lu && ctx.ke1Up === lu && !inKong(ctx, lu)) ? { evidence: [`日禄${lu}临日干上（不空）`] } : null; },
	8: (ctx)=>{ const lu = ganLu(ctx); return (lu && ctx.ke3Up === lu) ? { evidence: [`日禄${lu}临日支上`] } : null; },
	16: (ctx)=>{ const f = ctx.firstBranch; return (f && inKong(ctx, f) && ctx.firstGod === '天空') ? { evidence: [`初传${f}值旬空`, '初传乘天空'] } : null; },
	17: (ctx)=>{ const s = ctx.sanChuanBranches || []; if(s.length < 3) return null; const prog = idxDelta(s[0], s[1]) === 1 && idxDelta(s[1], s[2]) === 1; const allK = s.every((b)=>inKong(ctx, b)); return (prog && allK) ? { evidence: [`三传${s.join('→')}进连茹且俱旬空`] } : null; },
	18: (ctx)=>{ const s = ctx.sanChuanBranches || []; if(s.length < 3) return null; const retro = idxDelta(s[1], s[0]) === 1 && idxDelta(s[2], s[1]) === 1; const allK = s.every((b)=>inKong(ctx, b)); return (retro && allK) ? { evidence: [`三传${s.join('→')}退连茹且俱旬空`] } : null; },
	23: (ctx)=>{ return (ctx.firstBranch && ctx.ke1Up && ctx.ke3Up && ctx.ke1Up !== ctx.ke3Up && ctx.firstBranch === ctx.ke3Up && ctx.lastBranch === ctx.ke1Up) ? { evidence: ['初传发自日支上神、末传归日干上神（彼求我）'] } : null; },
	24: (ctx)=>{ return (ctx.firstBranch && ctx.ke1Up && ctx.ke3Up && ctx.ke1Up !== ctx.ke3Up && ctx.firstBranch === ctx.ke1Up && ctx.lastBranch === ctx.ke3Up) ? { evidence: ['初传发自日干上神、末传归日支上神（我求彼）'] } : null; },
	25: (ctx)=>{ const dg = zi(ctx.dayGan); if(dg !== '庚' && dg !== '辛') return null; const dh = (ctx.dingHorseBranches || []).filter((b)=>(ctx.courseBranches || []).indexOf(zi(b)) >= 0); return dh.length ? { evidence: [`${dg}日，课传见丁神：${dh.join('、')}`] } : null; },
	26: (ctx)=>{ const dg = zi(ctx.dayGan); if(dg !== '壬' && dg !== '癸') return null; const dh = (ctx.dingHorseBranches || []).filter((b)=>(ctx.courseBranches || []).indexOf(zi(b)) >= 0); return dh.length ? { evidence: [`${dg}日，课传见丁神：${dh.join('、')}`] } : null; },
	31: (ctx)=>{ const s = ctx.sanChuanBranches || []; const dg = ctx.dayGan; if(s.length < 3 || !dg) return null; const fwd = gen(s[0], s[1]) && gen(s[1], s[2]) && gen(s[2], dg); const rev = gen(s[2], s[1]) && gen(s[1], s[0]) && gen(s[0], dg); return (fwd || rev) ? { evidence: [`三传${s.join('→')}递生并生日干${zi(dg)}`] } : null; },
	32: (ctx)=>{ const s = ctx.sanChuanBranches || []; const dg = ctx.dayGan; if(s.length < 3 || !dg) return null; const fwd = ke(s[0], s[1]) && ke(s[1], s[2]) && ke(s[2], dg); const rev = ke(s[2], s[1]) && ke(s[1], s[0]) && ke(s[0], dg); return (fwd || rev) ? { evidence: [`三传${s.join('→')}递克并克日干${zi(dg)}`] } : null; },
	33: (ctx)=>{ const mu = ganMu(ctx); const f = ctx.firstBranch, l = ctx.lastBranch; if(!mu || !f || !l) return null; if(ganPhase(ctx, f) === '长生' && l === mu) return { evidence: [`初传${f}为日干长生、末传${l}为日干墓（有始无终）`] }; if(f === mu && ganPhase(ctx, l) === '长生') return { evidence: [`初传${f}为日干墓、末传${l}为日干长生（难变易）`] }; return null; },
	35: (ctx)=>{ return (gen(ctx.dayGan, ctx.ke1Up) && gen(ctx.dayZhi, ctx.ke3Up)) ? { evidence: ['日干生干上神、日支生支上神（人宅俱脱）'] } : null; },
	38: (ctx)=>{ const vb = godBranch(ctx, '玄武'); return (vb && ctx.xunHeadBranch && vb === zi(ctx.xunHeadBranch)) ? { evidence: [`旬首${zi(ctx.xunHeadBranch)}乘玄武（闭口）`] } : null; },
	41: (ctx)=>{ const lu = ganLu(ctx); const ma = ctx.dayZhi ? (LRConst.ZiYiMa[zi(ctx.dayZhi)] || '') : ''; return (lu && ma && ctx.ke1Up === ma && ctx.ke3Up === lu) ? { evidence: [`干上${ma}为日支驿马、支上${lu}为日干禄`] } : null; },
	42: (ctx)=>{ const g = (ctx.sanChuanGans || []).map(zi).filter(Boolean); if(g.length < 3) return null; const set = new Set(g); const a = ['甲', '戊', '庚'].every((x)=>set.has(x)); const b = ['乙', '丙', '丁'].every((x)=>set.has(x)); return (a || b) ? { evidence: [`三传遁干成三奇（${g.join('')}）`] } : null; },
	47: (ctx)=>{ const g = zi(ctx.guizi), dg = zi(ctx.dayGan); return ((g === '辰' || g === '戌') && (dg === '乙' || dg === '辛')) ? { evidence: [`贵人临${g}（狱），乙辛日宜临干投贵`] } : null; },
	48: (ctx)=>{ return (ctx.guizi && ke(ctx.guizi, ctx.dayGan)) ? { evidence: [`贵人所临${zi(ctx.guizi)}为日鬼（鬼乘天乙）`] } : null; },
	51: (ctx)=>{ return (ctx.firstBranch === '戌' && branchOver(ctx, '戌', '亥')) ? { evidence: ['戌加亥为发用（魁度天门，关隔）'] } : null; },
	52: (ctx)=>{ return branchOver(ctx, '辰', '寅') ? { evidence: ['辰加寅（罡塞鬼户，任谋为）'] } : null; },
	55: (ctx)=>{ const n1 = nextZhi(ctx.dayGanBranch), n3 = nextZhi(ctx.dayZhi); return (n1 && n3 && ctx.ke1Up === n1 && ctx.ke3Up === n3) ? { evidence: ['干上乘干前一辰、支上乘支前一辰（天罗地网）'] } : null; },
	59: (ctx)=>{ const mu = ganMu(ctx); return (mu && ctx.ke1Up === mu && ctx.firstBranch === mu) ? { evidence: [`日干墓${mu}临干上发用（华盖覆日）`] } : null; },
	61: (ctx)=>{ const mu = ganMu(ctx); return (mu && ctx.ke1Up === mu && keUpGod(ctx, 0) === '白虎') ? { evidence: [`日干墓${mu}乘白虎临干`] } : null; },
	62: (ctx)=>{ const m1 = ganMu(ctx), m3 = zhiMu(ctx); const t = ctx.ke3Up; return (t && (t === m1 || t === m3) && keUpGod(ctx, 2) === '白虎') ? { evidence: [`墓神${t}乘白虎临日支`] } : null; },
	63: (ctx)=>{ return (ke(ctx.ke1Up, ctx.dayGan) && ke(ctx.ke3Up, ctx.dayZhi)) ? { evidence: ['干被干上神克、支被支上神克（彼此全伤）'] } : null; },
	64: (ctx)=>{ return (ke(ctx.ke3Up, ctx.dayGan) && ke(ctx.ke1Up, ctx.dayZhi)) ? { evidence: ['干被支上神克、支被干上神克（夫妇芜淫）'] } : null; },
	69: (ctx)=>{ const shen = godRideShen(ctx, '白虎'); if(!shen) return null; const dun = ctx.xunGanMap ? ctx.xunGanMap[zi(shen)] : ''; return (dun && ke(dun, ctx.dayGan)) ? { evidence: [`白虎乘${zi(shen)}、其遁干${dun}为日鬼`] } : null; },
	70: (ctx)=>{ const k = ctx.keUpBranches || []; return (k.length >= 4 && ke(k[2], ctx.dayGan) && ke(k[3], ctx.dayGan)) ? { evidence: ['日鬼临第三、四课上神（讼灾随）'] } : null; },
	74: (ctx)=>{ const s = ctx.sanChuanBranches || []; return (s.length === 3 && s.every((b)=>inKong(ctx, b))) ? { evidence: [`三传${s.join('、')}全值旬空`] } : null; },
	76: (ctx)=>{ const h1 = ctx.dayGanBranch ? (LRConst.ZiHai[zi(ctx.dayGanBranch)] || '') : ''; const h3 = ctx.dayZhi ? (LRConst.ZiHai[zi(ctx.dayZhi)] || '') : ''; if((h1 && ctx.ke1Up === h1) || (h3 && ctx.ke3Up === h3)) return { evidence: ['干支与其上神作六害（彼此猜忌）'] }; return null; },
	77: (ctx)=>{ if(gen(ctx.ke1Up, ctx.dayZhi) && gen(ctx.ke3Up, ctx.dayGan)) return { evidence: ['干上生支、支上生干（互生，凡事益）'] }; if(gen(ctx.ke1Up, ctx.dayGan) && gen(ctx.ke3Up, ctx.dayZhi)) return { evidence: ['干上生干、支上生支（俱生）'] }; return null; },
	82: (ctx)=>{ const s = ctx.sanChuanBranches || []; if(s.length < 3) return null; return (inKong(ctx, s[1]) && inKong(ctx, s[2]) && !inKong(ctx, s[0])) ? { evidence: [`中传${s[1]}、末传${s[2]}俱旬空，独取初传${s[0]}`] } : null; },
	88: (ctx)=>{ const m1 = ganMu(ctx), m3 = zhiMu(ctx); return (m1 && m3 && ctx.ke1Up === m1 && ctx.ke3Up === m3) ? { evidence: ['干上为日干墓、支上为日支墓（墓覆日辰）'] } : null; },
	89: (ctx)=>{ if(!isFuYin(ctx)) return null; const cb = ctx.courseBranches || []; const dm = (ctx.dingHorseBranches || []).filter((b)=>cb.indexOf(zi(b)) >= 0); const ma = (ctx.yiMaBranches || []).filter((b)=>cb.indexOf(zi(b)) >= 0); return (dm.length || ma.length) ? { evidence: ['伏吟课见丁神 / 驿马（任信丁马须言动）'] } : null; },
	90: (ctx)=>{ if(!isFanYin(ctx)) return null; const s = ctx.sanChuanBranches || []; return (s.length === 3 && s.every((b)=>inKong(ctx, b))) ? { evidence: ['返吟课三传俱空（来去俱空）'] } : null; },
	91: (ctx)=>{ return (ke(ctx.ke1Up, ctx.dayGan) && keUpGod(ctx, 0) === '白虎') ? { evidence: ['日鬼乘白虎临干（虎临干鬼凶速速）'] } : null; },
	2: (ctx)=>{ const h = zi(ctx.xunHeadBranch), t = zi(ctx.xunTailBranch); if(!h || !t || !ctx.ke1Up || !ctx.ke3Up) return null; return ((ctx.ke1Up === t && ctx.ke3Up === h) || (ctx.ke1Up === h && ctx.ke3Up === t)) ? { evidence: ['干上见旬尾、支上见旬首（或反之，首尾相见）'] } : null; },
	4: (ctx)=>{ const y = zi(ctx.runYearBranch); return (y && godOf(ctx, y) === '白虎' && ke(y, ctx.dayGan)) ? { evidence: [`年命${y}乘白虎且为日鬼（催官使者）`] } : null; },
	15: (ctx)=>{ const u = ctx.ke1Up; if(!u || !gen(ctx.dayGan, u)) return null; const g = keUpGod(ctx, 0); return (g && TIANJIANG_WX[g] && WX_SHENG[wxOf(u)] === TIANJIANG_WX[g]) ? { evidence: ['日干生干上神、干上神又生其天将（脱上逢脱）'] } : null; },
	21: (ctx)=>{ return (ctx.dayGanBranch && ctx.dayZhi && ctx.ke1Up && ctx.ke3Up && LRConst.ZiHe[zi(ctx.dayGanBranch)] === ctx.ke3Up && LRConst.ZiHe[zi(ctx.dayZhi)] === ctx.ke1Up) ? { evidence: ['干与支上神合、支与干上神合（交车相合）'] } : null; },
	22: (ctx)=>{ return (ctx.ke1Up && ctx.ke3Up && LRConst.ZiHe[zi(ctx.ke1Up)] === zi(ctx.ke3Up)) ? { evidence: ['干上神与支上神作六合（上下皆合，两心齐）'] } : null; },
	27: (ctx)=>{ const s = ctx.sanChuanBranches || []; if(s.length < 3) return null; const allCai = s.every((b)=>liuqinOf(ctx, b) === '妻财'); return (allCai && ke(ctx.ke1Up, ctx.dayGan)) ? { evidence: ['三传皆财、干上神克日干（传财化鬼，取财致祸）'] } : null; },
	37: (ctx)=>{ return (ctx.lastBranch && ctx.firstBranch && gen(ctx.lastBranch, ctx.firstBranch)) ? { evidence: ['末传生助初传（末助初，三等论）'] } : null; },
	40: (ctx)=>{ const vb = godBranch(ctx, '玄武'); return (vb && (ctx.dingHorseBranches || []).indexOf(zi(vb)) >= 0) ? { evidence: [`玄武乘${vb}加丁神（主失脱逃亡）`] } : null; },
	43: (ctx)=>{ return (ctx.guizi && ctx.firstBranch && LRConst.ZiHai[zi(ctx.guizi)] === ctx.firstBranch) ? { evidence: [`贵人${zi(ctx.guizi)}与发用${ctx.firstBranch}六害（害贵，讼直反屈）`] } : null; },
	53: (ctx)=>{ const mu = ganMu(ctx); return (mu && ctx.ke1Up === mu && keUpGod(ctx, 0) === '螣蛇') ? { evidence: [`日干墓${mu}乘螣蛇（两蛇夹墓之象）`] } : null; },
	66: (ctx)=>{ const mu = zhiMu(ctx); return (mu && ctx.firstBranch === mu && liuqinOf(ctx, mu) === '妻财') ? { evidence: [`日支墓${mu}作日干财发用（支坟财并，旅程稽迟）`] } : null; },
	75: (ctx)=>{ const a = ctx.ke1Up, b = ctx.ke3Up; if(!a || !b) return null; const sx = (x)=>['辰', '午', '酉', '亥'].indexOf(zi(x)) >= 0; return (LRConst.ZiXing[zi(a)] === zi(b) || LRConst.ZiXing[zi(b)] === zi(a) || sx(a) || sx(b)) ? { evidence: ['干支上神见刑（宾主不投，各有异心）'] } : null; },
	83: (ctx)=>{ const s = ctx.sanChuanBranches || []; if(!isSanHeSet(s)) return null; const king = (s.map(zi).filter((x)=>['子', '午', '卯', '酉'].indexOf(x) >= 0)[0]) || ''; const he = king ? LRConst.ZiHe[king] : ''; return (he && (he === ctx.ke1Up || he === ctx.ke3Up)) ? { evidence: [`三传成三合（旺神${king}）、其六合${he}见于干支上神（三六合，万事喜忻）`] } : null; },
	86: (ctx)=>{ const g = ctx.firstGod; const bw = wxOf(ctx.firstBranch); const gw = TIANJIANG_WX[g]; return (g && bw && gw && WX_KE[bw] === gw) ? { evidence: [`发用所乘${ctx.firstBranch}(${bw})克天将${g}(${gw})（神克将，将逢内战，所谋危）`] } : null; },
	1: (ctx)=>{ const dg = ctx.dayGanBranch, dz = ctx.dayZhi, f = ctx.firstBranch, l = ctx.lastBranch; if(!f || !l) return null; const after = (base, x)=>{ const d = idxDelta(base, x); return d >= 1 && d <= 5; }; const before = (base, x)=>{ const d = idxDelta(x, base); return d >= 1 && d <= 5; }; if(dg && before(dg, f) && after(dg, l)) return { evidence: [`初传${f}居日干${dg}前为引、末传${l}居后为从（升迁）`] }; if(dz && before(dz, f) && after(dz, l)) return { evidence: [`初传${f}居日支${dz}前为引、末传${l}居后为从（迁宅）`] }; return null; },
	9: (ctx)=>{ const s = ctx.sanChuanBranches || []; if(s.length < 3) return null; const useless = (b)=>inKong(ctx, b) || ke(b, ctx.dayGan) || gen(ctx.dayGan, b); return (s.every(useless) && gen(ctx.ke1Up, ctx.dayGan)) ? { evidence: ['三传于日干皆空/鬼/脱、唯干上受生（避难逃生宜弃旧）'] } : null; },
	10: (ctx)=>{ return (inKong(ctx, '卯') && inCourse(ctx, '卯') && (branchOver(ctx, '卯', '申') || branchOver(ctx, '申', '卯'))) ? { evidence: ['斫轮（卯申互加）而卯木值旬空（朽木难雕，宜改业）'] } : null; },
	11: (ctx)=>{ const s = ctx.sanChuanBranches || []; if(s.length < 3) return null; if(!s.every((b)=>ke(b, ctx.dayGan))) return null; return s.every((b)=>ke(ctx.ke1Up, b)) ? { evidence: ['三传皆日鬼、干上神制之为救（众鬼虽彰全不畏）'] } : null; },
	12: (ctx)=>{ return (ke(ctx.ke1Up, ctx.dayGan) && ke(ctx.dayZhi, ctx.ke1Up)) ? { evidence: ['干上神克日、赖日支制之（狐假虎威，宜守）'] } : null; },
	13: (ctx)=>{ const s = ctx.sanChuanBranches || []; if(s.length < 3) return null; if(!s.every((b)=>ke(b, ctx.dayGan))) return null; return (wxOf(ctx.firstBranch) === seasonWangWx(ctx)) ? { evidence: ['三传皆鬼且当令旺极贪荣、当时不克日（防过时祸发）'] } : null; },
	14: (ctx)=>{ const s = ctx.sanChuanBranches || []; if(s.length < 3) return null; if(!s.every((b)=>liuqinOf(ctx, b) === '妻财')) return null; return (wxOf(ctx.firstBranch) === seasonWangWx(ctx)) ? { evidence: ['三传皆财、当生旺月、财贪自旺反不为用（求财反亏）'] } : null; },
	19: (ctx)=>{ const tai = (Z.filter((b)=>ganPhase(ctx, b) === '胎')[0]) || ''; if(!tai) return null; const sheng = shenshaBranch(ctx, 'month', '生气'); return (inCourse(ctx, tai) && liuqinOf(ctx, tai) === '妻财' && sheng && zi(tai) === sheng && !inKong(ctx, tai)) ? { evidence: [`胎神${tai}兼妻财、值月内生气（妻怀孕）`] } : null; },
	20: (ctx)=>{ const tai = (Z.filter((b)=>ganPhase(ctx, b) === '胎')[0]) || ''; if(!tai) return null; const si = shenshaBranch(ctx, 'month', '死气'); return (inCourse(ctx, tai) && liuqinOf(ctx, tai) === '妻财' && si && zi(tai) === si) ? { evidence: [`胎神${tai}兼妻财、值月内死气（孕不育）`] } : null; },
	28: (ctx)=>{ const s = ctx.sanChuanBranches || []; if(s.length < 3 || !isSanHeSet(s)) return null; const kong = s.filter((b)=>inKong(ctx, b)); const cai = s.filter((b)=>liuqinOf(ctx, b) === '妻财' && !inKong(ctx, b)); const ghost = s.filter((b)=>ke(b, ctx.dayGan)); return (ghost.length >= 2 && kong.length === 2 && cai.length === 1) ? { evidence: [`三合鬼局两字空、独存${cai[0]}为财（财从险中出）`] } : null; },
	29: (ctx)=>{ const s = ctx.sanChuanBranches || []; if(s.length < 3) return null; return (s.every((b)=>gen(b, ctx.dayGan)) && s.every((b)=>gen(ctx.dayZhi, b))) ? { evidence: ['三传生日干、又泄日支（人口丰盈居狭宅）'] } : null; },
	30: (ctx)=>{ const s = ctx.sanChuanBranches || []; if(s.length < 3) return null; return (s.every((b)=>gen(ctx.dayGan, b)) && s.every((b)=>gen(b, ctx.dayZhi))) ? { evidence: ['三传泄日干、反生日支（屋宅宽广致人衰）'] } : null; },
	34: (ctx)=>{ const s = ctx.sanChuanBranches || []; if(s.length >= 3 && ke(s[2], s[0]) && ke(s[0], ctx.dayGan) && gen(s[2], ctx.dayGan)) return { evidence: ['初传鬼克日、末传克初鬼又生日（苦去甘来）'] }; if(ganPhase(ctx, ctx.ke1Up) === '长生' && gen(ctx.dayGan, ctx.ke1Up) && gen(ctx.dayZhi, ctx.ke3Up)) return { evidence: ['干支虽乘长生意、却递互脱盗（乐里悲）'] }; return null; },
	36: (ctx)=>{ return (ganPhase(ctx, ctx.ke1Up) === '沐浴' && zhiPhase(ctx, ctx.ke3Up) === '沐浴') ? { evidence: ['干支上神皆临败气(沐浴)（干支皆败，势倾颓）'] } : null; },
	39: (ctx)=>{ const shen = godRideShen(ctx, '玄武'); const yj = zi(ctx.yueGeneralBranch); return (shen && yj && zi(shen) === yj) ? { evidence: ['玄武所乘之神为太阳月将（太阳照武宜擒贼；须昼占方验）'] } : null; },
	44: (ctx)=>{ return [ctx.firstGod, ctx.midGod, ctx.lastGod].every((g)=>g === '贵人') ? { evidence: ['三传天将皆乘贵人（遍地贵人，贵多反无依）'] } : null; },
	54: (ctx)=>{ if(!(ctx.courseName && ctx.courseName.indexOf('虎视') >= 0)) return null; const hasHu = [ctx.firstGod, ctx.midGod, ctx.lastGod].indexOf('白虎') >= 0; return hasHu ? { evidence: ['虎视课三传乘白虎（虎视逢虎，至惊至危）'] } : null; },
	56: (ctx)=>{ const mu = ganMu(ctx); const ming = zi(ctx.runYearBranch); return (mu && ctx.ke1Up === mu && ctx.firstBranch === mu && ming && ming === mu) ? { evidence: [`日干墓${mu}覆日发用、本命亦作日墓（天网自裹，自招非）`] } : null; },
	57: (ctx)=>{ const lifeKong = ganPhase(ctx, ctx.ke1Up) === '长生' && inKong(ctx, ctx.ke1Up); const tuoReal = gen(ctx.dayGan, ctx.ke3Up) && !inKong(ctx, ctx.ke3Up); return (lifeKong && tuoReal) ? { evidence: ['干上长生逢空(见生不生)、支上脱气坐实（费有余得不足）'] } : null; },
	58: (ctx)=>{ const f = ctx.firstBranch; if(!f) return null; const isCaiLu = liuqinOf(ctx, f) === '妻财' || f === ganLu(ctx); const broken = inKong(ctx, f) || ke(ctx.midBranch, f) || ke(ctx.ke1Up, f); const endGhost = ke(ctx.lastBranch, ctx.dayGan); return (isCaiLu && broken && endGhost) ? { evidence: ['财禄发用破空被克、引入末传鬼乡（用破身心无所归）'] } : null; },
	60: (ctx)=>{ const yj = zi(ctx.yueGeneralBranch); if(!yj) return null; return (ctx.ke3Up === yj || branchOver(ctx, yj, ctx.dayZhi)) ? { evidence: [`太阳月将${yj}照临日支宅上（屋光辉，向阳明朗）`] } : null; },
	65: (ctx)=>{ const GUAN = { spring: '丑', summer: '辰', autumn: '未', winter: '戌' }; const mu = ganMu(ctx); const guan = GUAN[ctx.season]; if(!mu || !guan || mu !== guan || ctx.firstBranch !== mu) return null; if(ctx.ke1Up === mu) return { evidence: [`日干墓${mu}兼四季关神临干发用（人衰）`] }; if(ctx.ke3Up === mu) return { evidence: [`日干墓${mu}兼四季关神临支发用（宅废）`] }; return { evidence: [`日干墓${mu}兼四季关神发用（人宅废）`] }; },
	67: (ctx)=>{ const HU = { '金': '肝经', '木': '脾经', '水': '心经', '火': '肺经', '土': '肾经' }; const shen = godRideShen(ctx, '白虎'); if(!shen) return null; const down = ctx.upDownMap ? ctx.upDownMap[zi(shen)] : ''; const struck = (down && ke(down, shen)) || ke(ctx.dayGan, shen); if(!struck) return null; const m = HU[wxOf(shen)]; return m ? { evidence: [`白虎乘${zi(shen)}(${wxOf(shen)})受克：主${m}病（依五行论治）`] } : null; },
	68: (ctx)=>{ const ghosts = (ctx.courseBranches || []).filter((b)=>ke(b, ctx.dayGan)); if(!ghosts.length) return null; const meds = (ctx.courseBranches || []).filter((b)=>ghosts.some((g)=>ke(b, g)) && !inKong(ctx, b)); return meds.length ? { evidence: [`课中${meds.join('、')}能制日鬼（制鬼之位为良医）`] } : null; },
	71: (ctx)=>{ const bf = prevZhi(ctx.yearBranch); if(!bf) return null; return (ctx.ke3Up === bf && ke(bf, ctx.dayZhi)) ? { evidence: [`病符${bf}临日支宅上又克支（全家患）`] } : null; },
	72: (ctx)=>{ const yi = Z.indexOf(zi(ctx.yearBranch)); if(yi < 0) return null; const sang = Z[(yi + 2) % 12]; const diao = Z[(yi + 10) % 12]; const pair = [zi(ctx.ke1Up), zi(ctx.ke3Up)]; return (pair.indexOf(sang) >= 0 && pair.indexOf(diao) >= 0) ? { evidence: [`干支上神全逢丧门${sang}、吊客${diao}（丧吊全逢，挂缟衣）`] } : null; },
	73: (ctx)=>{ const s = ctx.sanChuanBranches || []; if(s.length < 3) return null; const prog = idxDelta(s[0], s[1]) === 1 && idxDelta(s[1], s[2]) === 1; if(!(prog && s.every((b)=>inKong(ctx, b)))) return null; const back = prevZhi(ctx.firstBranch); return (gen(ctx.dayGan, back) || ke(back, ctx.dayGan)) ? { evidence: ['三传进连茹俱空(不可进)、退逢脱/鬼(不可退)（前后逼迫，宜守）'] } : null; },
	78: (ctx)=>{ const zg = zi(ctx.dayZhiGan); const get = (a, b)=>(ZhangSheng && ZhangSheng.ganzi) ? (ZhangSheng.ganzi[`${a}_${zi(b)}`] || '') : ''; if(get(zg, ctx.ke1Up) === '帝旺' && ganPhase(ctx, ctx.ke3Up) === '帝旺') return { evidence: ['干上为日支旺神、支上为日干旺神（互旺，坐谋宜）'] }; if(ganPhase(ctx, ctx.ke1Up) === '帝旺' && get(zg, ctx.ke3Up) === '帝旺' && !inKong(ctx, ctx.ke1Up) && !inKong(ctx, ctx.ke3Up)) return { evidence: ['干支上神皆乘旺神（皆旺，宜坐待）'] }; return null; },
	79: (ctx)=>{ return (ganPhase(ctx, ctx.ke1Up) === '绝' && zhiPhase(ctx, ctx.ke3Up) === '绝') ? { evidence: ['干上为日干绝、支上为日支绝（干支值绝，宜结绝凶事）'] } : null; },
	80: (ctx)=>{ return (ganPhase(ctx, ctx.ke1Up) === '死' && zhiPhase(ctx, ctx.ke3Up) === '死') ? { evidence: ['干上、支上皆临死气（人宅皆死，各衰羸）'] } : null; },
	81: (ctx)=>{ const f = ctx.firstBranch, m = ctx.midBranch, l = ctx.lastBranch; if(!f) return null; const midMuF = m && zi(m) === muOf(f); const lastMuM = l && zi(l) === muOf(m); if(!midMuF && !lastMuM) return null; const lq = liuqinOf(ctx, f); const good = (lq === '妻财' || lq === '父母' || f === ganLu(ctx) || ganPhase(ctx, f) === '长生'); const isGhost = ke(f, ctx.dayGan); const tone = good ? '吉神入墓为憎(不利)' : (isGhost ? '凶神入墓为爱(反吉)' : '传墓入墓'); return { evidence: [`三传后墓前(${f}入墓)：${tone}`] }; },
	84: (ctx)=>{ const s = ctx.sanChuanBranches || []; if(!isSanHeSet(s)) return null; const ups = [zi(ctx.ke1Up), zi(ctx.ke3Up)].filter(Boolean); const sset = s.map(zi); const bad = ups.filter((u)=>sset.some((y)=>LRConst.ZiXing[y] === u || chongZhi(y) === u || LRConst.ZiHai[y] === u)); return bad.length ? { evidence: [`三合局而干支上${bad.join('、')}犯刑/冲/害（合中犯杀，蜜中砒）`] } : null; },
	85: (ctx)=>{ const f = ctx.firstBranch; if(!f) return null; const down = ctx.upDownMap ? ctx.upDownMap[zi(f)] : ''; const lowerKe = down && ke(down, f); const gw = TIANJIANG_WX[ctx.firstGod]; const upperKe = gw && WX_KE[gw] === wxOf(f); return (lowerKe && upperKe) ? { evidence: [`初传${f}下被地盘克、上被天将克（夹克，身不由己）`] } : null; },
	87: (ctx)=>{ const m1 = ganMu(ctx), m3 = zhiMu(ctx); if(!m1 || !m3) return null; const ganOnMu = branchOver(ctx, ctx.dayGanBranch, m1); const zhiOnMu = branchOver(ctx, ctx.dayZhi, m3); return (ganOnMu && zhiOnMu) ? { evidence: [`日干寄宫坐地盘${m1}墓、日支坐地盘${m3}墓（人宅坐墓，甘招晦）`] } : null; },
	92: (ctx)=>{ const shen = godRideShen(ctx, '青龙'); if(!shen) return null; const sheng = shenshaBranch(ctx, 'month', '生气'); return (gen(shen, ctx.dayGan) && sheng && zi(shen) === sheng && !inKong(ctx, shen)) ? { evidence: [`青龙乘${zi(shen)}生日干、值月内生气（龙加生气，吉迟迟）`] } : null; },
	95: (ctx)=>{ const LQK = { '妻财': '父母', '父母': '子孙', '子孙': '官鬼', '官鬼': '兄弟', '兄弟': '妻财' }; const s = ctx.sanChuanBranches || []; if(s.length < 3) return null; const lq = liuqinOf(ctx, s[0]); if(!lq) return null; if(!s.every((b)=>liuqinOf(ctx, b) === lq)) return null; const victim = LQK[lq]; const upHas = [ctx.ke1Up, ctx.ke3Up].some((u)=>liuqinOf(ctx, u) === victim); return upHas ? { evidence: [`三传皆${lq}爻、干支上见所克之${victim}爻（防其克）`] } : null; },
	3: (ctx)=>{ const other = ctx.dayNight === '昼' ? ctx.nightGuiBranch : ctx.dayGuiBranch; if(!other) return null; const y = zi(ctx.runYearBranch), dgz = zi(ctx.dayGanBranch); return (((y && zi(other) === y) || (dgz && zi(other) === dgz)) && !inKong(ctx, other)) ? { evidence: [`帘幕贵人${zi(other)}临${zi(other) === y ? '年命' : '日干'}（占试高中）`] } : null; },
	45: (ctx)=>{ const a = zi(ctx.dayGuiBranch), b = zi(ctx.nightGuiBranch); const up = ctx.branchUpMap || {}; if(!a || !b) return null; return ((up[a] && zi(up[a]) === b) || (up[b] && zi(up[b]) === a)) ? { evidence: ['昼夜两贵相加（求事须涉两贵人）'] } : null; },
	46: (ctx)=>{ const a = zi(ctx.dayGuiBranch), b = zi(ctx.nightGuiBranch); if(!a || !b) return null; return (LRConst.SummerZiList.indexOf(a) >= 0 && LRConst.WinnerZiList.indexOf(b) >= 0) ? { evidence: ['昼贵临夜地、夜贵临昼方（贵人差迭，告贵不归一）'] } : null; },
	49: (ctx)=>{ const a = zi(ctx.dayGuiBranch), b = zi(ctx.nightGuiBranch); const up = ctx.branchUpMap || {}; if(!a || !b) return null; const struck = (g)=>up[g] && ke(up[g], g); return (struck(a) && struck(b)) ? { evidence: ['昼夜两贵皆居受克之方（难干贵）'] } : null; },
	50: (ctx)=>{ const a = ctx.dayGuiBranch, b = ctx.nightGuiBranch; return (a && b && inKong(ctx, a) && inKong(ctx, b)) ? { evidence: ['昼夜两贵人皆值旬空（虚喜有费）'] } : null; },
};

// 运行 A 档匹配，返回命中项（含 evidence）。绝不命中未登记 matcher 的法（宁缺勿滥）。
export function matchBiFa(context){
	if(!context){ return []; }
	const hits = [];
	BIFA_LIST.forEach((item)=>{
		const m = BIFA_MATCHERS[item.no];
		if(!m){ return; }
		let res = null;
		try{ res = m(context); }catch(e){ res = null; }
		if(res){ hits.push({ ...item, evidence: res.evidence || [] }); }
	});
	return hits;
}
