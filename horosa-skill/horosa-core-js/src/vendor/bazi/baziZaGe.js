// 杂格识别器（八字大全 §9.4，古格）。规约：正格能取者优先取正格，正格不成方论杂格；
//   逢填实/刑冲破多破格。第一组=「规则明确、可机械匹配」者（四干四支同气、日时柱专格）；
//   第二组=虚邀暗冲（飞天禄马/井栏叉/拱禄拱贵…）：判据已全部机械化——「多X」按局中
//   X 支≥2（含日支）取阈，破格条件（填实/冲/合绊/官杀明现）逐格枚举，每格带
//   quality: 真（判据成立无破）/假（判据成立但破条件命中，broken 列明）/待复核（库气未开类）。
//   全部只作候选提示（与变格同性质，不覆盖正格/用神），面板与 AI 标注真假。

function gz(p){ return p && p.stem && p.branch ? `${p.stem.cell || ''}${p.branch.cell || ''}` : ''; }

// 日柱专格（§9.4）
const RI_DE = new Set(['甲寅', '丙辰', '戊辰', '庚辰', '壬戌']);            // 日德格
const RI_GUI = new Set(['丁酉', '丁亥', '癸卯', '癸巳']);                  // 日贵格（日坐天乙）
const FU_DE_XIU = new Set(['乙巳', '乙酉', '乙丑']);                       // 福德秀气格
const JIN_SHEN = new Set(['癸酉', '己巳', '乙丑']);                        // 金神格（时柱）

const PILLARS = ['year', 'month', 'day', 'time'];

// ── 虚邀暗冲组数据（§9.4 后半）──
const ZHI_ORDER = '子丑寅卯辰巳午未申酉戌亥';
const LU_OF = { 甲: '寅', 乙: '卯', 丙: '巳', 丁: '午', 戊: '巳', 己: '午', 庚: '申', 辛: '酉', 壬: '亥', 癸: '子' };
// 天乙贵人（与上面日贵格 RI_GUI 同一口诀系：丙丁猪鸡位、壬癸兔蛇藏、庚辛逢马虎）
const GUI_OF = {
	甲: ['丑', '未'], 戊: ['丑', '未'], 乙: ['子', '申'], 己: ['子', '申'],
	丙: ['亥', '酉'], 丁: ['亥', '酉'], 壬: ['卯', '巳'], 癸: ['卯', '巳'], 庚: ['午', '寅'], 辛: ['午', '寅'],
};
const CHONG_OF = { 子: '午', 丑: '未', 寅: '申', 卯: '酉', 辰: '戌', 巳: '亥', 午: '子', 未: '丑', 申: '寅', 酉: '卯', 戌: '辰', 亥: '巳' };

// 虚邀暗冲十三格 + 月库杂气：全部机械判据；返回带 quality/broken 的候选数组。
function computeXuYao(four, stems, zhis, dayGz, timeGz){
	const dayGan = four.day && four.day.stem ? four.day.stem.cell : '';
	const out = [];
	const cnt = (z) => zhis.filter((x) => x === z).length;
	const hasZhi = (z) => zhis.indexOf(z) >= 0;
	const hasStem = (g) => stems.indexOf(g) >= 0;
	const push = (name, cond, broken, note) => {
		out.push({ name, cond, note, group: '虚邀暗冲', quality: broken.length ? '假' : '真', broken });
	};
	const brk = (pairs) => pairs.filter((p) => p[0]).map((p) => p[1]);

	// 飞天禄马：庚子/壬子日多子暗冲午官；辛亥/癸亥日多亥暗冲巳官
	if((dayGz === '庚子' || dayGz === '壬子') && cnt('子') >= 2){
		push('飞天禄马格', `日${dayGz}·${cnt('子')}子暗冲午中官星`,
			brk([[hasZhi('午'), '午填实'], [hasZhi('丑'), '子被丑合绊']]),
			'倒冲虚邀：忌午填实、丑合绊子。');
	}
	if((dayGz === '辛亥' || dayGz === '癸亥') && cnt('亥') >= 2){
		push('飞天禄马格', `日${dayGz}·${cnt('亥')}亥暗冲巳中官星`,
			brk([[hasZhi('巳'), '巳填实'], [hasZhi('寅'), '亥被寅合绊']]),
			'倒冲虚邀：忌巳填实、寅合绊亥。');
	}
	// 井栏叉：庚子/庚申/庚辰日 + 申子辰全
	if((dayGz === '庚子' || dayGz === '庚申' || dayGz === '庚辰') && hasZhi('申') && hasZhi('子') && hasZhi('辰')){
		push('井栏叉格', `日${dayGz}·地支申子辰全`,
			brk([[hasStem('丙') || hasStem('丁'), '丙丁显'], [hasZhi('巳') || hasZhi('午'), '巳午填实']]),
			'水局虚冲寅午戌官禄：忌丙丁巳午填实。');
	}
	// 壬骑龙背：壬辰日多辰（贵）多寅（富）
	if(dayGz === '壬辰' && (cnt('辰') >= 2 || cnt('寅') >= 2)){
		push('壬骑龙背格', `日壬辰·${cnt('辰')}辰${cnt('寅') ? `${cnt('寅')}寅` : ''}`,
			brk([[hasZhi('戌'), '辰戌冲破局']]),
			'辰多冲戌邀财官主贵，寅多合财主富；忌戌填实相冲。');
	}
	// 六乙鼠贵：乙日丙子时
	if(dayGan === '乙' && timeGz === '丙子'){
		push('六乙鼠贵格', '乙日丙子时·鼠邀贵气',
			brk([[hasStem('庚') || hasStem('辛') || hasZhi('申') || hasZhi('酉'), '官杀显'], [hasZhi('午'), '午冲子'], [hasZhi('丑'), '丑合子']]),
			'忌官杀（庚辛申酉）、午冲、丑合。');
	}
	// 六阴朝阳：辛日戊子时
	if(dayGan === '辛' && timeGz === '戊子'){
		push('六阴朝阳格', '辛日戊子时·子中癸邀丙官',
			brk([[hasStem('丙') || hasStem('丁'), '丙丁显'], [hasZhi('午'), '午冲填'], [hasZhi('申'), '申破局']]),
			'忌丙丁官杀显、午冲子、申泄局。');
	}
	// 子遥巳：甲子日甲子时
	if(dayGz === '甲子' && timeGz === '甲子'){
		push('子遥巳格', '甲子日甲子时·子遥合巳中戊丙',
			brk([[hasStem('庚') || hasStem('辛'), '庚辛官杀显'], [hasZhi('午'), '午冲子']]),
			'忌庚辛官杀、午冲。');
	}
	// 丑遥巳：辛丑/癸丑日多丑
	if((dayGz === '辛丑' || dayGz === '癸丑') && cnt('丑') >= 2){
		const guanXian = dayGan === '辛' ? (hasStem('丙') || hasStem('丁')) : (hasStem('戊') || hasStem('己'));
		push('丑遥巳格', `日${dayGz}·${cnt('丑')}丑遥合巳中官贵`,
			brk([[hasZhi('子'), '子合丑绊'], [hasZhi('巳'), '巳填实'], [guanXian, '官杀明现']]),
			'忌子合丑、巳填实、官杀明现。');
	}
	// 合禄：戊日/癸日庚申时
	if((dayGan === '戊' || dayGan === '癸') && timeGz === '庚申'){
		const guanMing = dayGan === '戊' ? hasStem('乙') : hasStem('戊');
		push('合禄格', `${dayGan}日庚申时·时禄暗合官星`,
			brk([[hasZhi('寅'), '寅冲申'], [hasStem('丙'), '丙伤庚'], [guanMing, '官星明现']]),
			'忌寅冲申、丙伤庚、官星填实。');
	}
	// 拱禄/拱贵：日时二支中间恰夹禄支/天乙支（隔位相拱）
	const dz = four.day && four.day.branch ? four.day.branch.cell : '';
	const tz = four.time && four.time.branch ? four.time.branch.cell : '';
	const iD = ZHI_ORDER.indexOf(dz), iT = ZHI_ORDER.indexOf(tz);
	if(iD >= 0 && iT >= 0 && dz !== tz){
		const diff = (iT - iD + 12) % 12;
		let mid = '';
		if(diff === 2){ mid = ZHI_ORDER[(iD + 1) % 12]; }
		else if(diff === 10){ mid = ZHI_ORDER[(iD + 11) % 12]; }
		if(mid && LU_OF[dayGan] === mid){
			push('拱禄格', `日支${dz}时支${tz}虚拱禄位${mid}`,
				brk([[hasZhi(mid), `${mid}填实`], [hasZhi(CHONG_OF[mid]), `${CHONG_OF[mid]}冲开拱口`]]),
				'虚拱贵在空处邀禄：忌填实、忌冲。');
		}
		if(mid && (GUI_OF[dayGan] || []).indexOf(mid) >= 0){
			push('拱贵格', `日支${dz}时支${tz}虚拱天乙${mid}`,
				brk([[hasZhi(mid), `${mid}填实`], [hasZhi(CHONG_OF[mid]), `${CHONG_OF[mid]}冲开拱口`]]),
				'虚拱天乙贵人：忌填实、忌冲。');
		}
	}
	// 刑合：癸日甲寅时（寅刑出巳中戊官）
	if(dayGan === '癸' && timeGz === '甲寅'){
		push('刑合格', '癸日甲寅时·寅刑巳邀戊官',
			brk([[hasZhi('申'), '申冲寅'], [hasZhi('巳'), '巳填实'], [hasStem('戊') || hasStem('己'), '官杀明现']]),
			'忌申冲寅、巳填实、官杀明现。');
	}
	// 趋乾：甲日多亥；趋艮：壬日多寅
	if(dayGan === '甲' && cnt('亥') >= 2){
		push('趋乾格', `甲日·${cnt('亥')}亥聚乾宫`,
			brk([[hasZhi('巳'), '巳冲亥']]), '甲趋乾贵：忌巳冲。');
	}
	if(dayGan === '壬' && cnt('寅') >= 2){
		push('趋艮格', `壬日·${cnt('寅')}寅聚艮宫`,
			brk([[hasZhi('申'), '申冲寅']]), '壬趋艮（寅中甲合己、暗邀亥禄）：忌申冲。');
	}
	// 月库杂气财官：辰戌丑未月，库藏（中气/余气）见财官印
	const mon = four.month || {};
	const monZhi = mon.branch ? mon.branch.cell : '';
	if('辰戌丑未'.indexOf(monZhi) >= 0 && Array.isArray(mon.stemInBranch)){
		const store = mon.stemInBranch.slice(1).filter((c) => c && ['财', '才', '官', '杀', '印', '枭'].indexOf(c.relative) >= 0);
		if(store.length){
			const tou = store.some((c) => stems.indexOf(c.cell) >= 0);
			const chong = PILLARS.some((k) => k !== 'month' && four[k] && four[k].branch && four[k].branch.cell === CHONG_OF[monZhi]);
			out.push({
				name: '杂气财官格', cond: `${monZhi}月库藏${store.map((c) => `${c.cell}(${c.relative})`).join('·')}`,
				note: tou ? '库物透出可用。' : (chong ? '库逢冲开，藏物可取。' : '喜刑冲开库或透出，库闭则待运。'),
				group: '虚邀暗冲', quality: (tou || chong) ? '真' : '待复核', broken: [],
			});
		}
	}
	return out;
}

// 返回 [{name, cond, note}] 或 null
export function computeZaGe(four){
	if(!four || !four.day){ return null; }
	const out = [];
	const stems = PILLARS.map((k) => four[k] && four[k].stem && four[k].stem.cell).filter(Boolean);
	const zhis = PILLARS.map((k) => four[k] && four[k].branch && four[k].branch.cell).filter(Boolean);
	const dayGz = gz(four.day);
	const timeGz = gz(four.time);

	if(stems.length === 4 && new Set(stems).size === 1){
		out.push({ name: '天元一气格', cond: '四天干相同', note: '纯而有用为贵，全看地支配合。' });
	}
	if(zhis.length === 4 && new Set(zhis).size === 1){
		out.push({ name: '地支一气格', cond: '四地支相同', note: '一气专纯，最忌冲破。' });
	}
	if(stems.length === 4 && new Set(stems).size === 2){
		out.push({ name: '两干不杂格', cond: '四柱天干仅两干交互', note: '清纯为贵。' });
	}
	const els = new Set();
	PILLARS.forEach((k) => {
		const p = four[k];
		if(!p){ return; }
		if(p.stem && p.stem.element){ els.add(p.stem.element); }
		if(p.branch && p.branch.element){ els.add(p.branch.element); }
	});
	if(els.size === 5){
		out.push({ name: '五行俱足格', cond: '五行齐全流通', note: '周流不滞为贵。' });
	}
	if(RI_DE.has(dayGz)){
		out.push({ name: '日德格', cond: `日柱${dayGz}`, note: '喜身旺，忌刑冲、忌叠魁罡。' });
	}
	if(RI_GUI.has(dayGz)){
		out.push({ name: '日贵格', cond: `日坐天乙（${dayGz}）`, note: '忌刑冲破害、空亡。' });
	}
	if(FU_DE_XIU.has(dayGz)){
		out.push({ name: '福德秀气格', cond: `日柱${dayGz}`, note: '喜身旺有制。' });
	}
	if(JIN_SHEN.has(timeGz)){
		out.push({ name: '金神格', cond: `时柱${timeGz}`, note: '需火制：喜火炼、忌水。' });
	}
	// 虚邀暗冲组追加在既有八格之后（既有条目字段与顺序逐字不变=零回归）
	computeXuYao(four, stems, zhis, dayGz, timeGz).forEach((it) => out.push(it));
	return out.length ? out : null;
}

export default computeZaGe;
