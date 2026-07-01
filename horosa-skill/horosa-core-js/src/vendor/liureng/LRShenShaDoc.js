// 六壬「常用神煞」前端补算 + 释义（解读层，纯前端，零回归——仅为后端未直接给出的常用神煞补一份按日干/日支可确定的起例与释义）。
// 起例忠于《众煞》原文，三合局 / 孟仲季 已全展开为 12 支映射，可直接查表。
// 渲染层只列示 + 吉凶色，不下断语（"传统视为吉/凶，须合盘"）。

// luck → 颜色（明暗双色下均可读）。
export const SHENSHA_LUCK_COLOR = {
	good: '#3fa45b',
	bad: '#e2574c',
	neutral: 'var(--horosa-muted, #9a8f7d)',
};

// 每条：{ name, by('dayZhi'|'dayGan'), luck, brief, rule{支或干→所临地支} }
export const SHENSHA_LIST = [
	{ name: '日德', by: 'dayGan', luck: 'good', brief: '避凶中正、逢凶化吉', rule: { '甲': '寅', '己': '寅', '乙': '申', '庚': '申', '丙': '巳', '辛': '巳', '戊': '巳', '癸': '巳', '丁': '亥', '壬': '亥' } },
	{ name: '日禄', by: 'dayGan', luck: 'good', brief: '食禄、身体、力量', rule: { '甲': '寅', '乙': '卯', '丙': '巳', '丁': '午', '戊': '巳', '己': '午', '庚': '申', '辛': '酉', '壬': '亥', '癸': '子' } },
	{ name: '驿马', by: 'dayZhi', luck: 'neutral', brief: '变动、远行、车驾', rule: { '亥': '巳', '卯': '巳', '未': '巳', '巳': '亥', '酉': '亥', '丑': '亥', '寅': '申', '午': '申', '戌': '申', '申': '寅', '子': '寅', '辰': '寅' } },
	{ name: '咸池', by: 'dayZhi', luck: 'bad', brief: '桃花、沐浴、情欲', rule: { '亥': '子', '卯': '子', '未': '子', '巳': '午', '酉': '午', '丑': '午', '寅': '卯', '午': '卯', '戌': '卯', '申': '酉', '子': '酉', '辰': '酉' } },
	{ name: '华盖', by: 'dayZhi', luck: 'neutral', brief: '遮蔽、阴沉、孤高', rule: { '亥': '未', '卯': '未', '未': '未', '巳': '丑', '酉': '丑', '丑': '丑', '寅': '戌', '午': '戌', '戌': '戌', '申': '辰', '子': '辰', '辰': '辰' } },
	{ name: '亡神', by: 'dayZhi', luck: 'bad', brief: '城府、阴谋、暗失', rule: { '亥': '寅', '卯': '寅', '未': '寅', '巳': '申', '酉': '申', '丑': '申', '寅': '巳', '午': '巳', '戌': '巳', '申': '亥', '子': '亥', '辰': '亥' } },
	{ name: '劫杀', by: 'dayZhi', luck: 'bad', brief: '刚烈、放肆、凶夺', rule: { '亥': '申', '卯': '申', '未': '申', '巳': '寅', '酉': '寅', '丑': '寅', '寅': '亥', '午': '亥', '戌': '亥', '申': '巳', '子': '巳', '辰': '巳' } },
	{ name: '破碎', by: 'dayZhi', luck: 'bad', brief: '分离、零落、琐碎', rule: { '寅': '酉', '申': '酉', '巳': '酉', '亥': '酉', '子': '巳', '午': '巳', '卯': '巳', '酉': '巳', '辰': '丑', '戌': '丑', '丑': '丑', '未': '丑' } },
	{ name: '游都', by: 'dayGan', luck: 'bad', brief: '贼寇、危险、定盗', rule: { '甲': '丑', '己': '丑', '乙': '子', '庚': '子', '丙': '寅', '辛': '寅', '丁': '巳', '壬': '巳', '戊': '申', '癸': '申' } },
	// 日干起(§19.4):羊刃=刚暴刑伤夺财(阴干立刃派,出全表)、墓神=日墓闭藏停滞(逢冲则发)。
	{ name: '羊刃', by: 'dayGan', luck: 'bad', brief: '刚暴、刑伤、夺财', rule: { '甲': '卯', '乙': '辰', '丙': '午', '丁': '未', '戊': '午', '己': '未', '庚': '酉', '辛': '戌', '壬': '子', '癸': '丑' } },
	{ name: '墓神', by: 'dayGan', luck: 'bad', brief: '闭藏、停滞、逢冲发', rule: { '甲': '未', '乙': '未', '丙': '戌', '丁': '戌', '戊': '辰', '己': '辰', '庚': '丑', '辛': '丑', '壬': '辰', '癸': '辰' } },
	// 三合局标准神煞(补全 §19.1 十神之缺):将星=帝旺(仲)、灾煞=旺神之冲、岁煞=灾煞后一、攀鞍=驿马后一、六厄=驿马前一。
	// 按日支(或年支)所属三合局:申子辰水 / 寅午戌火 / 巳酉丑金 / 亥卯未木。⚠️将星=帝旺位(申子辰见子),勿误作华盖。
	{ name: '将星', by: 'dayZhi', luck: 'good', brief: '权柄、中坚、领袖', rule: { '申': '子', '子': '子', '辰': '子', '寅': '午', '午': '午', '戌': '午', '巳': '酉', '酉': '酉', '丑': '酉', '亥': '卯', '卯': '卯', '未': '卯' } },
	{ name: '灾煞', by: 'dayZhi', luck: 'bad', brief: '血光、灾厄、急难', rule: { '申': '午', '子': '午', '辰': '午', '寅': '子', '午': '子', '戌': '子', '巳': '卯', '酉': '卯', '丑': '卯', '亥': '酉', '卯': '酉', '未': '酉' } },
	{ name: '岁煞', by: 'dayZhi', luck: 'bad', brief: '耗损、阻滞、小耗', rule: { '申': '未', '子': '未', '辰': '未', '寅': '丑', '午': '丑', '戌': '丑', '巳': '辰', '酉': '辰', '丑': '辰', '亥': '戌', '卯': '戌', '未': '戌' } },
	{ name: '攀鞍', by: 'dayZhi', luck: 'good', brief: '进身、晋擢、佐助', rule: { '申': '卯', '子': '卯', '辰': '卯', '寅': '酉', '午': '酉', '戌': '酉', '巳': '子', '酉': '子', '丑': '子', '亥': '午', '卯': '午', '未': '午' } },
	{ name: '六厄', by: 'dayZhi', luck: 'bad', brief: '险阻、留难、厄会', rule: { '申': '丑', '子': '丑', '辰': '丑', '寅': '未', '午': '未', '戌': '未', '巳': '戌', '酉': '戌', '丑': '戌', '亥': '辰', '卯': '辰', '未': '辰' } },
];

const _ZHI12 = ['子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥'];
function _z(i){ return _ZHI12[((i % 12) + 12) % 12]; }
function _zi(z){ return _ZHI12.indexOf(`${z || ''}`.trim().substring(0, 1)); }
// 月序:正月=寅=1 … 十二月=丑=12
function _monthOrder(monthZhi){ const i = _zi(monthZhi); if(i < 0){ return 0; } return ((i - 2 + 12) % 12) + 1; }

// 年神煞(以流年/占年地支起·§19.2)。sort: 'sanyuan'(四利三元序·默认) / 'suigui'(太岁排轮·太阴落宫异)。
// 返回 [{name, branch, luck, brief, color, inCourse}]
export function computeYearShenSha(yearZhi, sort, courseBranches){
	const yi = _zi(yearZhi);
	if(yi < 0){ return []; }
	const course = Array.isArray(courseBranches) ? courseBranches : [];
	// 四利三元顺数:①太岁②太阳③丧门④太阴⑤官符⑥死符⑦岁破⑧龙德⑨白虎⑩福德⑪吊客⑫病符
	const off = { 太岁: 0, 太阳: 1, 丧门: 2, 太阴: 3, 官符: 4, 死符: 5, 岁破: 6, 龙德: 7, 白虎: 8, 福德: 9, 吊客: 10, 病符: 11 };
	if(sort === 'suigui'){ off.太阴 = 10; } // 太岁排轮:太阴=岁后二辰(⚠️⑨ 流派分歧,仅太阴落宫明确不同)
	const luck = { 太岁: 'neutral', 太阳: 'good', 丧门: 'bad', 太阴: 'good', 官符: 'bad', 死符: 'bad', 岁破: 'bad', 龙德: 'good', 白虎: 'bad', 福德: 'good', 吊客: 'bad', 病符: 'bad' };
	const brief = { 太岁: '一岁主宰', 太阳: '解厄扶助', 丧门: '孝服丧事', 太阴: '阴贵暗助', 官符: '官司词讼', 死符: '死丧旧灾', 岁破: '破耗大凶', 龙德: '逢凶化吉', 白虎: '血光凶丧', 福德: '福庆扶助', 吊客: '吊丧疾忧', 病符: '疾病旧灾' };
	return Object.keys(off).map((name)=>{
		const branch = _z(yi + off[name]);
		return { name, branch, luck: luck[name], brief: brief[name], color: SHENSHA_LUCK_COLOR[luck[name]] || SHENSHA_LUCK_COLOR.neutral, inCourse: course.indexOf(branch) >= 0 };
	});
}

// 月神煞(以月建/月支起·正月=寅·§19.3)。天德值含干/支(原表如此)。
export function computeMonthShenSha(monthZhi, courseBranches){
	const mi = _zi(monthZhi);
	const ord = _monthOrder(monthZhi);
	if(mi < 0 || !ord){ return []; }
	const course = Array.isArray(courseBranches) ? courseBranches : [];
	const TIANDE = { '寅': '丁', '卯': '申', '辰': '壬', '巳': '辛', '午': '亥', '未': '甲', '申': '癸', '酉': '寅', '戌': '丙', '亥': '乙', '子': '巳', '丑': '庚' };
	const YUEDE = { '寅': '丙', '午': '丙', '戌': '丙', '亥': '甲', '卯': '甲', '未': '甲', '申': '壬', '子': '壬', '辰': '壬', '巳': '庚', '酉': '庚', '丑': '庚' };
	const TIANMA6 = ['午', '申', '戌', '子', '寅', '辰']; // 正月起午,六阳辰循环
	const TIANXI = { '寅': '戌', '卯': '戌', '辰': '戌', '巳': '丑', '午': '丑', '未': '丑', '申': '辰', '酉': '辰', '戌': '辰', '亥': '未', '子': '未', '丑': '未' }; // 春戌夏丑秋辰冬未
	const mz = _ZHI12[mi];
	const rows = [
		{ name: '月建', branch: mz, luck: 'neutral', brief: '当月当令' },
		{ name: '月破', branch: _z(mi + 6), luck: 'bad', brief: '破坏离散' },
		{ name: '天德', branch: TIANDE[mz] || '', luck: 'good', brief: '上吉化凶' },
		{ name: '月德', branch: YUEDE[mz] || '', luck: 'good', brief: '福德化解' },
		{ name: '天医', branch: _z(4 + (ord - 1)), luck: 'good', brief: '求医得救' }, // 正月起辰顺行
		{ name: '天喜', branch: TIANXI[mz] || '', luck: 'good', brief: '婚庆添喜' },
		{ name: '天马', branch: TIANMA6[(ord - 1) % 6], luck: 'good', brief: '驿动信息' },
		{ name: '月厌', branch: _z(10 - (ord - 1)), luck: 'bad', brief: '阻滞妨婚' }, // 正月起戌逆行
	];
	return rows.filter((r)=>r.branch).map((r)=>({ ...r, color: SHENSHA_LUCK_COLOR[r.luck] || SHENSHA_LUCK_COLOR.neutral, inCourse: course.indexOf(r.branch) >= 0 }));
}

// 按日干、日支补算常用神煞所临之支。courseBranches 用于标注"是否入课传"。
// 返回 [{ name, branch, luck, brief, color, inCourse }]
export function computeFrontendShenSha(dayGan, dayZhi, courseBranches){
	const gan = `${dayGan || ''}`.trim().substring(0, 1);
	const zhi = `${dayZhi || ''}`.trim().substring(0, 1);
	const course = Array.isArray(courseBranches) ? courseBranches : [];
	const out = [];
	SHENSHA_LIST.forEach((s)=>{
		const key = s.by === 'dayGan' ? gan : zhi;
		if(!key){ return; }
		const branch = s.rule[key] || '';
		if(!branch){ return; }
		out.push({
			name: s.name,
			branch,
			luck: s.luck,
			brief: s.brief,
			color: SHENSHA_LUCK_COLOR[s.luck] || SHENSHA_LUCK_COLOR.neutral,
			inCourse: course.indexOf(branch) >= 0,
		});
	});
	// 丁神(遁丁,按日所在旬·§19.4):旬首地支 → 丁X 之支。动神/文书急速。
	const GAN10 = ['甲', '乙', '丙', '丁', '戊', '己', '庚', '辛', '壬', '癸'];
	const ZHI12 = ['子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥'];
	const gi = GAN10.indexOf(gan); const zi = ZHI12.indexOf(zhi);
	if(gi >= 0 && zi >= 0){
		const xunHead = ZHI12[((zi - gi) % 12 + 12) % 12]; // 旬首地支(甲X)
		const DING_BY_XUNHEAD = { '子': '卯', '戌': '丑', '申': '亥', '午': '酉', '辰': '未', '寅': '巳' };
		const dingZhi = DING_BY_XUNHEAD[xunHead];
		if(dingZhi){
			out.push({
				name: '丁神', branch: dingZhi, luck: 'neutral', brief: '动神、文书、急速',
				color: SHENSHA_LUCK_COLOR.neutral, inCourse: course.indexOf(dingZhi) >= 0,
			});
		}
	}
	return out;
}
