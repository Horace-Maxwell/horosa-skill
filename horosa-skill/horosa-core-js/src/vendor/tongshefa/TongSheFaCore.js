// Vendored from 星阙 TongSheFaMain.js —— 统摄法（纳甲筮法）纯计算层：React 类之前的全部常量与
// 40 个函数，逐字取自上游，只剥掉 React/antd/网络/样式的 import 与随组件走的 UI 解构。
// 此前本仓这一支是**自建端口**（自己维护 BAGUA / 卦名表），只产 4 段；上游的计算分析层
// （世应 / 左右五行 / 五友 / 大局升降爻变 / 三十二观）整层没有搬。换成逐字 vendor 后 9 段齐全，
// 以后跟上游只需重跑 revendor。
import { littleEndian } from '../gua/littleEndian.js';
import { Gua8, Gua64, getGua64 } from '../gua/GuaConst.js';



const BAGUA_SYMBOL = {
	乾: '☰',
	兑: '☱',
	离: '☲',
	震: '☳',
	巽: '☴',
	坎: '☵',
	艮: '☶',
	坤: '☷',
};

const BAGUA_LIST = Gua8.map((item)=>{
	return {
		key: item.name,
		name: item.name,
		cname: item.abrname,
		elem: item.elem,
		value: item.value.slice(0),
		symbol: BAGUA_SYMBOL[item.name] || '',
	};
});

const BAGUA_MAP = new Map();
BAGUA_LIST.forEach((item)=>{
	BAGUA_MAP.set(item.key, item);
});

const DEFAULT_SELECTION = {
	taiyin: '巽',
	taiyang: '坤',
	shaoyang: '震',
	shaoyin: '震',
};

const POSITION_META = {
	taiyin: {
		label: '太阴·本体',
		observeKey: 'taiyin',
	},
	taiyang: {
		label: '太阳·方法',
		observeKey: 'taiyang',
	},
	shaoyang: {
		label: '少阳·认识',
		observeKey: 'shaoyang',
	},
	shaoyin: {
		label: '少阴·宇宙',
		observeKey: 'shaoyin',
	},
};
const POSITION_KEYS = ['taiyin', 'taiyang', 'shaoyang', 'shaoyin'];
const BAGUA_SANJIE_ORDER = ['坤', '乾', '离', '坎', '兑', '艮', '巽', '震'];

const ZHI_ELEM_MAP = {
	子: '水',
	丑: '土',
	寅: '木',
	卯: '木',
	辰: '土',
	巳: '火',
	午: '火',
	未: '土',
	申: '金',
	酉: '金',
	戌: '土',
	亥: '水',
};

const SHENG_MAP = {
	木: '火',
	火: '土',
	土: '金',
	金: '水',
	水: '木',
};

const KE_MAP = {
	木: '土',
	土: '水',
	水: '火',
	火: '金',
	金: '木',
};

const KIN_TO_REL = {
	兄弟: '同',
	父母: '义',
	官鬼: '鬼',
	子孙: '爱',
	妻财: '制',
	妻才: '制',
};

const MAIN_RELATION_LABEL = {
	思生实: '思想服务实践',
	思克实: '思想改造实践',
	思同实: '思想实践协调',
	实生思: '实践服务思想',
	实克思: '实践改造思想',
};

const LIUHE_SET = new Set([
	'子丑', '丑子',
	'寅亥', '亥寅',
	'卯戌', '戌卯',
	'辰酉', '酉辰',
	'巳申', '申巳',
	'午未', '未午',
]);

const LIUCHUAN_SET = new Set([
	'子未', '未子',
	'丑午', '午丑',
	'寅巳', '巳寅',
	'卯辰', '辰卯',
	'申亥', '亥申',
	'酉戌', '戌酉',
]);

const YAO_ORIGIN = [
	{ line: 6, name: '无上' },
	{ line: 5, name: '主宰' },
	{ line: 4, name: '超脱' },
	{ line: 3, name: '因果' },
	{ line: 2, name: '显现' },
	{ line: 1, name: '基础' },
];

const LEFT_YAO_META = [
	{ role: '感受', target: '感官体验' },
	{ role: '心魂', target: '心智与魂魄' },
	{ role: '灵性', target: '玄冥通灵' },
	{ role: '经验', target: '亲身经历' },
	{ role: '本真', target: '本质或真理' },
	{ role: '神明', target: '超然物外的神明' },
];

const RIGHT_YAO_META = [
	{ role: '变化', target: '事物的流变' },
	{ role: '现象', target: '森罗万象' },
	{ role: '命定', target: '不可抗力' },
	{ role: '欲望', target: '情欲和渴望' },
	{ role: '理性', target: '理性法则' },
	{ role: '规训', target: '规矩与训戒' },
];

const MATRIX_PANEL_META = {
	本卦: '当前四宫所成之象',
	互潜: '中爻互见，潜藏结构',
	错亲: '阴阳相反，亲和参照',
};

const FIVE_FRIEND_EXPLANATIONS = [
	{ key: '鬼', title: '压力与拘束', definition: '它会钳制我，使我服从于它，不敢越雷池。' },
	{ key: '爱', title: '心之所向', definition: '它是我希望得到、希望成就、希望抵达的方向。' },
	{ key: '制', title: '我所欲控', definition: '它被我视为财产，或某种可支配的资源。' },
	{ key: '同', title: '竞争关系', definition: '希望共同目标、共同利益；若硬来乱来，也会变成冲突。' },
	{ key: '义', title: '恩人贵人', definition: '它保护我、助我、给我力量。' },
];

const OBSERVE_32 = {
	taiyin: {
		title: '本体（太阴）',
		intro: '怎样看待万物本质：',
		items: {
			坤: '事物像机械时钟，内含严密系统，皆在因循、皆被注定。不知其来，但知其在。',
			乾: '事物没有本质，也无规定，尽是幻象，尽皆虚无。',
			离: '心生万物，魂中有真。外物乃虚，唯心是实。心灵是本质。',
			坎: '因缘和合，条件变幻。心智非实，因缘为实。外物是本质。',
			兑: '上帝是本质，主宰一切。先验、神明、规律、第一因。',
			艮: '形而上者不可知，神而下者才是实。对神秘的探索，只是脱离现实的空想。',
			巽: '邂逅的一切，皆是鲜活的体验，它不可分析、无法言说。',
			震: '生活，受控于人心与规律。事物的本质，是社会关系与自然规律的统一体。',
		},
	},
	shaoyang: {
		title: '认识（少阳）',
		intro: '如何认识世界，怎样形成知识，如何求真：',
		items: {
			坤: '听天由命，顺从即可。顺应规律。和谐不逆，就是真。',
			乾: '没有真相。想怎么认识，就怎么认识，都是真，也都是假。',
			离: '心中有真知，魂内孕真理。求真应向内心探求。',
			坎: '规律在外界，真相心外求。求真应向外物追索。',
			兑: '非凡神力，可以得，可以悟，须扶摇直上。悟道可通神。',
			艮: '形而上者，不可知，不可说，须保持沉默。认知有局限。',
			巽: '除生活日常外，除既定事实外，一切理论知识，都必定失真。',
			震: '自然规律威压，社会关系禁锢，唯有逆流抗争，才可求真知。',
		},
	},
	taiyang: {
		title: '方法（太阳）',
		intro: '如何生活，如何实践，有何目的：',
		items: {
			坤: '统摄全局，以宏大理论约束万物。构筑精妙，庖丁解牛。',
			乾: '放任自流，包容多元且无所顾忌。随遇而安，游戏人间。',
			离: '为民立命，我入地狱，燃烧自己，当仁不让。人为自然立法，心智照亮黑暗。',
			坎: '因势利导，随机应变，左右逢缘，顺势而为。利用外部环境，不可与之为敌。',
			兑: '净化心神，挣脱羁绊，抵达终极彼岸。渴望化身为圣人或神明。',
			艮: '脚踏实地，专注世俗，实现社会价值。秩序与禁戒可和谐大同。',
			巽: '隐忍，等风来。培风积水，厚积薄发。唯有宁静方能致远。',
			震: '策动最贫弱者，与子同袍，逆天改命。鼓舞弱者推翻强者。',
		},
	},
	shaoyin: {
		title: '宇宙（少阴）',
		intro: '怎样设想整个世界：',
		items: {
			坤: '精密又庞大的机械，环环相扣，天衣无缝，这便是世界。',
			乾: '高远且湛寂的苍穹，晴明无垠，无限可能，这便是世界。',
			离: '宇宙犹如跃动的火焰。某物内燃以照亮其外，世界持续生成。',
			坎: '宇宙犹如顺势的流水。在既定的规则界限中，世界居中奔流。',
			兑: '有一至高主宰，创设世界。宇宙是祂的棋局，为祂存在。',
			艮: '社会秩序与日常生活，便是一切。鬼神无意义。',
			巽: '质朴的体验便是世界总体，平淡的日常乃是宇宙本身。',
			震: '辩证发展，阳破阴、新代旧，螺旋上升，永续前行。有种自由，发于质朴、闪现天地，它和阴云共成寰宇。',
		},
	},
};

const SANJIE_TEXT = [
	{
		title: '三爻（天界）',
		desc: '终极与超越。此爻代表【至高的存在】。某种神明信仰，或无上规律。',
	},
	{
		title: '二爻（人界）',
		desc: '理智与人心。此爻代表【自我的心智】。某种理性思考，或自由意志。',
	},
	{
		title: '一爻（地界）',
		desc: '平淡与日常。此爻代表【质朴的生活】。某种平淡无奇，或世事烟云。',
	},
];

const BAGUA_DETAIL = {
	坤: {
		title: '☷ 地',
		subtitle: '绝对实体，全制无否',
		rows: [
			'阴无阳，万物实。',
			'【实】抹杀可能——譬如空杯，本可装各种液体（有无穷的可能），但若它选定了酒，装满了酒，这一刻，它实了，而曾经的无穷可能却死了。',
			'三爻皆阴，三界为实。人世的可能性完全死灭，毫无空隙，毫无自由。万物皆被注定、被命令、被因循，如同严密运转的机器。',
			'犹如厚实的土地：它所孕育的万物，皆遵从物候规律。因果与宿命，就源于此。',
		],
	},
	乾: {
		title: '☰ 天',
		subtitle: '纯粹虚无，全否无制',
		rows: [
			'阳无阴，境至虚。',
			'【虚】可容万有——接纳一切，尝试一切，抛弃一切。抗拒束缚，毁坏规定。极端的虚无主义。',
			'三爻皆阳，三界为虚。它极度叛逆，只为破坏而存在；同时又逍遥洒脱，不羁于物，不滞于心，不跪于神。',
			'犹如无垠的苍穹：它空无一物，却仿佛含容万有。威权与恐惧，就源于此。',
		],
	},
	离: {
		title: '☲ 火',
		subtitle: '内实外虚，内制外否',
		rows: [
			'阴陷阳，小自我。',
			'（二爻）人心是阴，与两阳对立。对立之中，自我为实、环境是虚。会向内心寻找某种“真实”。',
			'甚至认为，可以用这些【内在的真实】，去创生外物、改革环境。',
			'犹如炽燃的火焰：可燃物总是居中，而焰火总从两侧向外。文明与艺术，就源于此。',
		],
	},
	坎: {
		title: '☵ 水',
		subtitle: '内虚外实，内否外制',
		rows: [
			'阳陷阴，大他者。',
			'（二爻）人心是阳，被两阴围困。自我为虚，环境是实。向外寻找“真实”（物质、社会、客观、规律）。',
			'寄希望于这些外物，用外物改造思想。外物强大，称之为大他者。',
			'犹如奔流的江水：河岸总在两侧，江水总被夹于中间。舆论和科学，就源于此。',
		],
	},
	兑: {
		title: '☱ 泽',
		subtitle: '浮萍之实，认可超越',
		rows: [
			'阴摄阳，事鬼神。',
			'三爻乃至高无上，它是阴，其下两爻为阳。存在某种至高无上者，且真实存在。',
			'人的自我与日常生活无足轻重，应奉献给God。',
			'犹如泥泞的沼泽：抛弃现状，挣扎向上，脱出泥沼，便抵达彼岸。宗教与修行，来源于此。',
		],
	},
	艮: {
		title: '☶ 山',
		subtitle: '垒土之台，否定超越',
		rows: [
			'阳摄阴，顺人伦。',
			'三爻至高无上是阳，其下两爻为阴。反对至高无上者，常表现为不可知论、无神论。',
			'相比神秘超越，山把心血倾注于社会关系：人心与生活才最真实。',
			'犹如高耸山巅：可无限接近，却不能真正登天。道德与礼教，就源于此。',
		],
	},
	巽: {
		title: '☴ 风',
		subtitle: '苍天下尘，认可质朴',
		rows: [
			'阴逆阳，任自然。',
			'一爻质朴生活是阴，其上两爻为阳。人世是鲜活体验的整体，不能被分析、不可被复述。',
			'心智虚妄可笑，也没什么救世主。不如顺从自然，听凭本能。',
			'犹如恣意清风：来自天空，却卷起尘土。俗世与逍遥，来源于此。',
		],
	},
	震: {
		title: '☳ 雷',
		subtitle: '云雨下闪，否定质朴',
		rows: [
			'阳逆阴，斩邪龙。',
			'一爻是阳，其上两爻为阴。渴望扶摇直上，斩杀两阴。',
			'它通晓人心规则，也看透鬼神威压，但无法平息纯阳热情，定要直上九天。',
			'犹如闪怒奔雷：在激烈爆发中，僵持矛盾从内部崩塌，复归于一。正义与改革，即源于此。',
		],
	},
};

const HOUSE_CHANGE_CN = {
	0: '本',
	1: '一',
	2: '二',
	3: '三',
	4: '四',
	5: '五',
	6: '六',
	7: '七',
};

function arrEq(a, b){
	if(!(a instanceof Array) || !(b instanceof Array) || a.length !== b.length){
		return false;
	}
	for(let i=0; i<a.length; i++){
		if(a[i] !== b[i]){
			return false;
		}
	}
	return true;
}

function safeText(txt, def = '—'){
	const v = `${txt === undefined || txt === null ? '' : txt}`.trim();
	return v === '' ? def : v;
}

function normalizeSelection(raw){
	const base = { ...DEFAULT_SELECTION };
	if(!raw || typeof raw !== 'object'){
		return base;
	}
	Object.keys(base).forEach((key)=>{
		const val = raw[key];
		if(val && BAGUA_MAP.has(val)){
			base[key] = val;
		}
	});
	return base;
}

function getBagua(key){
	if(key && BAGUA_MAP.has(key)){
		return BAGUA_MAP.get(key);
	}
	return BAGUA_MAP.get(DEFAULT_SELECTION.taiyin);
}

function getBaguaByLines(lines){
	for(let i=0; i<BAGUA_LIST.length; i++){
		const item = BAGUA_LIST[i];
		if(arrEq(item.value, lines)){
			return item;
		}
	}
	return null;
}

function shortGuaName(name){
	const txt = `${name || ''}`.trim();
	for(let i=0; i<BAGUA_LIST.length; i++){
		const item = BAGUA_LIST[i];
		if(txt === `${item.name}为${item.cname}`){
			return item.name;
		}
	}
	if(txt.length <= 2){
		return txt || '—';
	}
	return txt.substring(2);
}

function linePattern(val){
	return val === 1 ? '—' : '--';
}

function linePolarity(val){
	return val === 1 ? '阳' : '阴';
}

function lineAdmit(val){
	return val === 1 ? '否' : '认';
}

function lineVerb(val){
	return val === 1 ? '蔑视' : '看重';
}

function buildHexByLines(lines, upperHint, lowerHint){
	const bits = lines.slice(0);
	const key = littleEndian(bits);
	const gua = getGua64(key);
	const lowerLines = bits.slice(0, 3);
	const upperLines = bits.slice(3, 6);
	const lower = lowerHint || getBaguaByLines(lowerLines) || BAGUA_LIST[0];
	const upper = upperHint || getBaguaByLines(upperLines) || BAGUA_LIST[0];
	return {
		key,
		lines: bits,
		gua,
		upper,
		lower,
	};
}

function buildHex(upper, lower){
	return buildHexByLines([
		lower.value[0], lower.value[1], lower.value[2],
		upper.value[0], upper.value[1], upper.value[2],
	], upper, lower);
}

function buildMutualHex(hex){
	const bits = hex.lines;
	return buildHexByLines([
		bits[1], bits[2], bits[3],
		bits[2], bits[3], bits[4],
	]);
}

function buildOppositeHex(hex){
	const bits = hex.lines.map((item)=>item === 1 ? 0 : 1);
	return buildHexByLines(bits);
}

function parseYaoName(raw){
	const text = `${raw || ''}`;
	const branch = text.substring(0, 1);
	const elem = text.substring(1, 2) || ZHI_ELEM_MAP[branch] || '';
	let tail = text.substring(2);
	let shiYing = '';
	if(tail.endsWith('世') || tail.endsWith('应')){
		shiYing = tail.substring(tail.length - 1);
		tail = tail.substring(0, tail.length - 1);
	}
	let kin = '';
	if(tail.indexOf('兄弟') >= 0){
		kin = '兄弟';
	}else if(tail.indexOf('父母') >= 0){
		kin = '父母';
	}else if(tail.indexOf('官鬼') >= 0){
		kin = '官鬼';
	}else if(tail.indexOf('子孙') >= 0){
		kin = '子孙';
	}else if(tail.indexOf('妻财') >= 0){
		kin = '妻财';
	}else if(tail.indexOf('妻才') >= 0){
		kin = '妻才';
	}
	return {
		branch,
		elem,
		kin,
		shiYing,
	};
}

function relationByElem(mainElem, otherElem){
	const main = `${mainElem || ''}`;
	const other = `${otherElem || ''}`;
	if(main === '' || other === ''){
		return '';
	}
	if(main === other){
		return '同';
	}
	if(SHENG_MAP[other] === main){
		return '义';
	}
	if(KE_MAP[other] === main){
		return '鬼';
	}
	if(SHENG_MAP[main] === other){
		return '爱';
	}
	if(KE_MAP[main] === other){
		return '制';
	}
	return '';
}

function buildLineInfos(hex){
	const elem = hex && hex.gua && hex.gua.house ? hex.gua.house.elem : '';
	const infos = [];
	for(let i=0; i<6; i++){
		const bits = hex.lines[i];
		const raw = hex && hex.gua && hex.gua.yaoname ? hex.gua.yaoname[i] : '';
		const parsed = parseYaoName(raw);
		const lineElem = parsed.elem || ZHI_ELEM_MAP[parsed.branch] || '';
		const ownRel = parsed.kin ? (KIN_TO_REL[parsed.kin] || '') : relationByElem(elem, lineElem);
		infos.push({
			line: i + 1,
			value: bits,
			pattern: linePattern(bits),
			branch: parsed.branch || '',
			elem: lineElem,
			kin: parsed.kin,
			ownRel,
			shiYing: parsed.shiYing || '',
		});
	}
	return infos;
}

function getHexElem(hex){
	if(hex && hex.gua && hex.gua.house && hex.gua.house.elem){
		return hex.gua.house.elem;
	}
	return hex && hex.upper ? hex.upper.elem : '';
}

function getHouseChangeLabel(hex){
	if(!(hex && hex.gua && hex.gua.house && hex.gua.house.name)){
		return '—';
	}
	const houseName = hex.gua.house.name;
	let order = 0;
	for(let i=0; i<Gua64.length; i++){
		const item = Gua64[i];
		if(!(item && item.house && item.house.name === houseName)){
			continue;
		}
		if(item.name === hex.gua.name && arrEq(item.value, hex.gua.value)){
			return `${houseName}${HOUSE_CHANGE_CN[order] || order}`;
		}
		order++;
	}
	return `${houseName}—`;
}

function getMainRelationCode(leftElem, rightElem){
	if(leftElem === '' || rightElem === ''){
		return '思同实';
	}
	if(leftElem === rightElem){
		return '思同实';
	}
	if(SHENG_MAP[leftElem] === rightElem){
		return '思生实';
	}
	if(KE_MAP[leftElem] === rightElem){
		return '思克实';
	}
	if(SHENG_MAP[rightElem] === leftElem){
		return '实生思';
	}
	if(KE_MAP[rightElem] === leftElem){
		return '实克思';
	}
	return '思同实';
}

function analyzeBigPattern(lines){
	const pairs = [
		{ from: 1, to: 4 },
		{ from: 2, to: 5 },
		{ from: 3, to: 6 },
	];
	const details = pairs.map((item)=>{
		const a = lines[item.from - 1] ? lines[item.from - 1].branch : '';
		const b = lines[item.to - 1] ? lines[item.to - 1].branch : '';
		const key = `${a}${b}`;
		let status = '无';
		if(LIUCHUAN_SET.has(key)){
			status = '穿';
		}else if(LIUHE_SET.has(key)){
			status = '合';
		}
		return {
			...item,
			branchPair: `${a}${b}`,
			status,
		};
	});
	const allChuan = details.every((item)=>item.status === '穿');
	const allHe = details.every((item)=>item.status === '合');
	return {
		type: allChuan ? '六穿' : (allHe ? '六合' : '无'),
		details,
	};
}

function analyzeRise(lines){
	const attacks = [];
	for(let i=0; i<6; i++){
		if(lines[i] !== 1 || i === 5){
			continue;
		}
		let j = i + 1;
		while(j < 6 && lines[j] !== 1){
			j++;
		}
		const end = j < 6 ? j - 1 : 5;
		if(end < i + 1){
			continue;
		}
		const targets = [];
		for(let k=i + 1; k<=end; k++){
			targets.push(k + 1);
		}
		attacks.push({
			from: i + 1,
			targets,
		});
	}
	return attacks;
}

function analyzeYaoChanges(leftLines, rightLines){
	const list = [];
	for(let i=5; i>=0; i--){
		const lineNum = i + 1;
		list.push({
			line: lineNum,
			changed: leftLines[i] !== rightLines[i],
		});
	}
	return list;
}

function uniqBagua(list){
	const seen = new Set();
	const out = [];
	list.forEach((item)=>{
		if(!item || seen.has(item.key)){
			return;
		}
		seen.add(item.key);
		out.push(item);
	});
	return out;
}

function buildTongSheFaModel(selection){
	const selected = normalizeSelection(selection);
	const taiyin = getBagua(selected.taiyin);
	const taiyang = getBagua(selected.taiyang);
	const shaoyang = getBagua(selected.shaoyang);
	const shaoyin = getBagua(selected.shaoyin);

	const baseLeft = buildHex(taiyin, shaoyang);
	const baseRight = buildHex(taiyang, shaoyin);
	const mutualLeft = buildMutualHex(baseLeft);
	const mutualRight = buildMutualHex(baseRight);
	const oppositeLeft = buildOppositeHex(baseLeft);
	const oppositeRight = buildOppositeHex(baseRight);

	const leftElem = getHexElem(baseLeft);
	const rightElem = getHexElem(baseRight);
	const leftLines = buildLineInfos(baseLeft);
	const rightLines = buildLineInfos(baseRight);

	const mainRelation = getMainRelationCode(leftElem, rightElem);

	return {
		selected,
		taiyin,
		taiyang,
		shaoyang,
		shaoyin,
		baseLeft,
		baseRight,
		mutualLeft,
		mutualRight,
		oppositeLeft,
		oppositeRight,
		leftElem,
		rightElem,
		leftLines,
		rightLines,
		leftHouseLabel: getHouseChangeLabel(baseLeft),
		rightHouseLabel: getHouseChangeLabel(baseRight),
		mainRelation,
		mainRelationLabel: MAIN_RELATION_LABEL[mainRelation] || '',
		leftBigPattern: analyzeBigPattern(leftLines),
		rightBigPattern: analyzeBigPattern(rightLines),
		leftRise: analyzeRise(baseLeft.lines),
		rightRise: analyzeRise(baseRight.lines),
		yaoChanges: analyzeYaoChanges(baseLeft.lines, baseRight.lines),
		baguaPicked: uniqBagua([taiyin, taiyang, shaoyang, shaoyin]),
	};
}

function formatHexName(hex){
	return hex && hex.gua && hex.gua.name ? hex.gua.name : '—';
}

function formatBaguaLabel(bagua){
	if(!bagua){
		return '—';
	}
	return safeText(bagua.cname || bagua.name);
}

function buildHexSnapshotSection(title, leftHex, rightHex){
	const lines = [];
	lines.push(`【${title}】`);
	lines.push('');
	lines.push(`左卦（${formatHexName(leftHex)}）：`);
	lines.push(`上卦（太阴·本体）：${formatBaguaLabel(leftHex ? leftHex.upper : null)}`);
	lines.push(`下卦（少阳·认识）：${formatBaguaLabel(leftHex ? leftHex.lower : null)}`);
	lines.push('');
	lines.push(`右卦（${formatHexName(rightHex)}）：`);
	lines.push(`上卦（太阳·方法）：${formatBaguaLabel(rightHex ? rightHex.upper : null)}`);
	lines.push(`下卦（少阴·宇宙）：${formatBaguaLabel(rightHex ? rightHex.lower : null)}`);
	return lines;
}

function buildYaoRowsByMain(lines, mainElem){
	const rows = [];
	for(let line=6; line>=1; line--){
		const info = lines[line - 1] || {};
		const polarity = linePolarity(info.value === 1 ? 1 : 0);
		const rel = relationByElem(mainElem, info.elem) || '';
		const relationTag = `${info.branch || ''}${rel}` || '—';
		rows.push(`${line}爻：${polarity}·${relationTag}`);
	}
	return rows;
}

function buildSixYaoMainSection(title, leftLines, rightLines, mainElem){
	const lines = [];
	lines.push(`「${title}」`);
	lines.push('左卦：');
	lines.push(...buildYaoRowsByMain(leftLines, mainElem));
	lines.push('');
	lines.push('右卦：');
	lines.push(...buildYaoRowsByMain(rightLines, mainElem));
	return lines;
}

function buildTongSheFaSnapshot(model){
	const parts = [];
	parts.push(...buildHexSnapshotSection('本卦', model.baseLeft, model.baseRight));
	parts.push('');
	parts.push('【六爻】');
	parts.push('');
	parts.push(...buildSixYaoMainSection(
		`左卦（${safeText(model.leftElem)}；思想；${safeText(model.leftHouseLabel)}）为主`,
		model.leftLines,
		model.rightLines,
		model.leftElem
	));
	parts.push('');
	parts.push(...buildSixYaoMainSection(
		`右卦（${safeText(model.rightElem)}；实践；${safeText(model.rightHouseLabel)}）为主`,
		model.leftLines,
		model.rightLines,
		model.rightElem
	));
	parts.push('');
	parts.push(...buildHexSnapshotSection('潜藏', model.mutualLeft, model.mutualRight));
	parts.push('');
	parts.push(...buildHexSnapshotSection('亲和', model.oppositeLeft, model.oppositeRight));
	// [YA v42] A 类硬缺(全场最薄):纳甲筮法 tab 的整个计算分析层(世应/左右五行/五友/大局升降爻变)
	// UI 已显示(renderNaJiaTab 系列卡片)却此前不入快照。段名已登记 AI_EXPORT_PRESET_SECTIONS.tongshefa;
	// 取数与 UI 严格同源(同 model 派生、同 relationByElem/groupFiveFriendItems/fmtRise 等函数);空数据不产段。
	[
		buildObserve32Section(model),
		buildShiYingSection(model),
		buildWuXingRelationSection(model),
		buildFiveFriendSection(model),
		buildBigPatternChangeSection(model),
	].forEach((sectionLines)=>{
		if(sectionLines.length){
			parts.push('');
			parts.push(...sectionLines);
		}
	});
	return parts.join('\n').replace(/\n{3,}/g, '\n\n').trim();
}

function fmtRise(attacks){
	if(!attacks || attacks.length === 0){
		return '无';
	}
	return attacks.map((item)=>{
		return `${item.from}爻击${item.targets.join('、')}爻`;
	}).join('；');
}

function fmtPatternDetail(pattern){
	if(!pattern || !pattern.details){
		return '—';
	}
	return pattern.details.map((item)=>`${item.from}/${item.to}:${item.branchPair || '—'}${item.status === '无' ? '' : item.status}`).join('，');
}

function groupFiveFriendItems(mainElem, leftLines, rightLines){
	const list = [];
	leftLines.forEach((info, idx)=>{
		list.push({
			relation: relationByElem(mainElem, info.elem),
			label: `左${idx + 1}`,
			role: LEFT_YAO_META[idx] ? LEFT_YAO_META[idx].role : `${idx + 1}爻`,
			branch: info.branch || '',
			elem: info.elem || '',
		});
	});
	rightLines.forEach((info, idx)=>{
		list.push({
			relation: relationByElem(mainElem, info.elem),
			label: `右${idx + 1}`,
			role: RIGHT_YAO_META[idx] ? RIGHT_YAO_META[idx].role : `${idx + 1}爻`,
			branch: info.branch || '',
			elem: info.elem || '',
		});
	});
	return list.reduce((acc, item)=>{
		const key = item.relation || '—';
		if(!acc[key]){
			acc[key] = [];
		}
		acc[key].push(item);
		return acc;
	}, {});
}

function fiveFriendDynamicText(key, items){
	if(!items || items.length === 0){
		return '当前未见此类关系。';
	}
	const positions = items.map((item)=>`${item.label}（${item.role}·${item.branch}${item.elem}）`).join('、');
	const roles = items.map((item)=>item.role).join('、');
	switch(key){
		case '鬼':
			return `${positions}为鬼；这些层面会形成压力与拘束，使人服从、顾忌，难以轻易越界。`;
		case '爱':
			return `${positions}为爱；这些层面是心之所向，显示人希望得到、亲近或成就的方向。`;
		case '制':
			return `${positions}为制；这些层面容易被看作可掌控、可支配、可调用的资源。`;
		case '同':
			return `${positions}为同；这些层面与自身目标相近，既可共利同行，也可能因同类相争而冲突。`;
		case '义':
			return `${positions}为义；${roles}会成为助力、保护与恩惠之源，给人力量。`;
		default:
			return positions;
	}
}

function patternExplanation(context, type){
	if(type === '六穿'){
		return `${context}上见全局相穿：心智的不同层面互相战斗，互不相让，互相否定，为的是分出一个胜者。穿，是锋芒、战斗与一击致命的意象。`;
	}
	if(type === '六合'){
		return `${context}上见全局相合：有混元一切的倾向。对于事实、行为、遭遇，一口吞下，平等看待，认为万物一体，混同你我。`;
	}
	return '';
}

// [X1·P1-1] 三十二观(右栏默认首 tab 的核心观文层)入快照 —— 与 renderObserveTab 严格同源
// (同 POSITION_KEYS/META、同 OBSERVE_32 取文);此前 AI 只见卦名不见本法核心解读。
function buildObserve32Section(model){
	const out = [];
	if(!model || !model.selected){ return out; }
	out.push('【三十二观】');
	POSITION_KEYS.forEach((posKey)=>{
		const meta = POSITION_META[posKey];
		const trigram = model.selected[posKey];
		const bagua = getBagua(trigram);
		if(!meta || !bagua){ return; }
		const observe = OBSERVE_32[meta.observeKey];
		const desc = observe && observe.items ? observe.items[bagua.key] : '';
		if(desc){ out.push(`${meta.label}·${bagua.symbol || ''}${bagua.cname || ''}:${observe.intro || ''}${desc}`); }
	});
	return out.length > 1 ? out : [];
}

// ——以下四个函数为 AI 快照新增段(纳甲筮法 tab 的计算分析层),供 buildTongSheFaSnapshot 调用——
// 与 UI 严格同源:世应/五行展开取 model.leftLines/rightLines(renderShiYingCard/renderNaJiaTab 同一数据),
// 五友取 groupFiveFriendItems+fiveFriendDynamicText(renderFiveFriendsCard 同一函数),
// 大局/升降/爻变取 leftBigPattern/leftRise/yaoChanges(renderBigPatternDetailCard/renderRiseDetailCard/renderYaoChangeDetailCard 同一数据)。

// [世应] 单侧行:与 renderShiYingSide 同构(idx+1 爻·爻位角色·地支五行+本卦关系),无标记时与 UI 同文案。
function buildShiYingSideLines(title, lines, metas){
	const out = [];
	out.push(`◆ ${title}`);
	const items = [];
	(lines || []).forEach((info, idx)=>{
		if(!info || !info.shiYing){
			return;
		}
		const meta = metas[idx] || {};
		const rel = info.ownRel || '';
		items.push(`| ${info.shiYing} | ${idx + 1}爻 | ${meta.role || `${idx + 1}爻`} | ${info.branch || ''}${info.elem || ''}${rel} |`);
	});
	if(items.length === 0){
		out.push('未标出世应');
	}else{
		out.push('| 世应 | 爻 | 爻位 | 地支五行 |');
		out.push('| --- | --- | --- | --- |');
		out.push(...items);
	}
	return out;
}

export function buildShiYingSection(model){
	const leftLines = model && model.leftLines ? model.leftLines : [];
	const rightLines = model && model.rightLines ? model.rightLines : [];
	const hasAny = leftLines.some((info)=>info && info.shiYing) || rightLines.some((info)=>info && info.shiYing);
	if(!hasAny){
		return [];
	}
	const parts = [];
	parts.push('【世应】');
	parts.push('世爻=着眼点；应爻=吸引点。');
	parts.push(...buildShiYingSideLines('左卦 · 思想', leftLines, LEFT_YAO_META));
	parts.push(...buildShiYingSideLines('右卦 · 实践', rightLines, RIGHT_YAO_META));
	return parts;
}

// [五行关系] = 左右卦主关系(mainRelation) + 左右卦五行展开表(renderNaJiaTab baseRows 同构:
// 逐爻 阴阳画 + 地支五行 + 对本卦五行关系 + 世应标记),含 UI 同款图例行。
export function buildWuXingRelationSection(model){
	const leftLines = model && model.leftLines ? model.leftLines : [];
	const rightLines = model && model.rightLines ? model.rightLines : [];
	if(leftLines.length === 0 && rightLines.length === 0){
		return [];
	}
	const parts = [];
	parts.push('【五行关系】');
	parts.push(`主关系：${model.mainRelation}（${model.mainRelationLabel || ''}）`);
	parts.push(`左卦：${model.leftElem || '—'}（思想） · ${model.leftHouseLabel}`);
	parts.push(`右卦：${model.rightElem || '—'}（实践） · ${model.rightHouseLabel}`);
	parts.push('◆ 左右卦五行展开');
	parts.push('| 爻 | 左 | 右 |');
	parts.push('| --- | --- | --- |');
	for(let line=6; line>=1; line--){
		const idx = line - 1;
		const left = leftLines[idx] || {};
		const right = rightLines[idx] || {};
		const leftOwn = relationByElem(model.leftElem, left.elem);
		const rightOwn = relationByElem(model.rightElem, right.elem);
		const leftFive = `${safeText(left.branch, '')}${safeText(left.elem, '')}${leftOwn || ''}` || '—';
		const rightFive = `${safeText(right.branch, '')}${safeText(right.elem, '')}${rightOwn || ''}` || '—';
		const leftSY = left.shiYing ? `（${left.shiYing}）` : '';
		const rightSY = right.shiYing ? `（${right.shiYing}）` : '';
		parts.push(`| ${line}爻 | ${left.pattern || '—'} ${leftFive}${leftSY} | ${right.pattern || '—'} ${rightFive}${rightSY} |`);
	}
	parts.push('鬼=压力与拘束；爱=心之所向；制=我所欲控；同=竞争关系；义=恩人贵人。');
	parts.push('世爻=着眼点；应爻=吸引点。');
	return parts;
}

// [五友] = 左卦为主/右卦为主 两侧五类关系分组(鬼/爱/制/同/义),判语用 fiveFriendDynamicText
// (含爻位归组即计算结果本体;长静态定义文案不重复导出)。
function buildFiveFriendSection(model){
	const leftLines = model && model.leftLines ? model.leftLines : [];
	const rightLines = model && model.rightLines ? model.rightLines : [];
	if(leftLines.length === 0 && rightLines.length === 0){
		return [];
	}
	const parts = [];
	parts.push('【五友】');
	[
		{ title: '左卦为主', context: '思想', mainElem: model.leftElem },
		{ title: '右卦为主', context: '实践', mainElem: model.rightElem },
	].forEach((side)=>{
		parts.push(`◆ ${side.title}（${side.mainElem || '—'}·${side.context}）`);
		const groups = groupFiveFriendItems(side.mainElem, leftLines, rightLines);
		FIVE_FRIEND_EXPLANATIONS.forEach((item)=>{
			const rows = groups[item.key] || [];
			parts.push(`${item.key}（${item.title}）：${fiveFriendDynamicText(item.key, rows)}`);
		});
	});
	return parts;
}

// [大局与动变] = 六穿/六合大局(fmtPatternDetail 逐对明细+成局判语) + 升降(fmtRise) + 逐爻爻变。
function buildBigPatternChangeSection(model){
	if(!model){
		return [];
	}
	const yaoChanges = model.yaoChanges || [];
	const hasCore = model.leftBigPattern || model.rightBigPattern
		|| (model.leftRise && model.leftRise.length) || (model.rightRise && model.rightRise.length)
		|| yaoChanges.length;
	if(!hasCore){
		return [];
	}
	const parts = [];
	parts.push('【大局与动变】');
	parts.push('◆ 大局');
	[
		{ title: '左卦（思想）', context: '思想', pattern: model.leftBigPattern },
		{ title: '右卦（实践）', context: '实践', pattern: model.rightBigPattern },
	].forEach((side)=>{
		const type = side.pattern && side.pattern.type ? side.pattern.type : '无';
		parts.push(`${side.title}：${type}；${fmtPatternDetail(side.pattern)}`);
		const explanation = patternExplanation(side.context, type);
		if(explanation){
			parts.push(explanation);
		}
	});
	parts.push('◆ 升降');
	parts.push(`左卦（思想）：${fmtRise(model.leftRise)}`);
	parts.push(`右卦（实践）：${fmtRise(model.rightRise)}`);
	parts.push('◆ 爻变');
	if(yaoChanges.length){
		parts.push(yaoChanges.map((item)=>`${item.line}爻${item.changed ? '有变' : '不变'}`).join('；'));
	}else{
		parts.push('无');
	}
	return parts;
}

export { buildTongSheFaModel, buildTongSheFaSnapshot };
