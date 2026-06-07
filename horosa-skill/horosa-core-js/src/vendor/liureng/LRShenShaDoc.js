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
];

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
	return out;
}
