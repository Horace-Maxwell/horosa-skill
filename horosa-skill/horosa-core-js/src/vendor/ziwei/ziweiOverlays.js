// 紫微 · 流派招牌「后处理 overlay」纯函数(从已起好的 chart 计算,零碰安星)。
//   · 河洛派 qiShuWei:气数位(官禄宫)+ 其宫干四化回照 + 一六共宗(§9.10)
//   · 中州派 borrowedStars:空宫借对宫十四正曜、庙旺按借入宫(§9.2.4)
//   · 紫云派 taiSuiRuGua:关系人生肖落同支宫、南斗男北斗女(§9.3)
// 皆读 chart.houses[i].{ganzi,starsMain...},四化取 ZWConst.getActiveSiHuaGan()(随流派)、亮度取 starLightOf。
import { getActiveSiHuaGan } from '../bazi/ZWConst.js';
import { starLightOf } from './data/ziweiTables.js';
import { ZWEngineOptions } from './ziweiOptions.js';

const HUA = ['禄', '权', '科', '忌'];
const STAR_FIELDS = ['starsMain', 'starsAssist', 'starsEvil', 'starsOthersGood', 'starsOthersBad', 'starsSmall'];
const stripFu = (nm)=>(nm && nm.charAt(0) === '副' ? nm.slice(1) : nm);

// star 名 → 落宫 index(去「副」前缀;同名多处取最后,对齐 ziweiPatterns.buildCtx)。
function buildStarIndex(chart){
	const idx = {};
	for(let i = 0; i < 12; i++){
		STAR_FIELDS.forEach((f)=>{ (chart.houses[i][f] || []).forEach((s)=>{ const nm = stripFu(s.name); if(nm){ idx[nm] = i; } }); });
	}
	return idx;
}

// 河洛派:气数位(命逆数官禄=第9宫,(life-8)%12)+ 其宫干四化回照本宫 + 一六共宗宫位映射。
export function qiShuWei(chart){
	if(!chart || chart.lifeHouseIndex == null || chart.lifeHouseIndex < 0){ return null; }
	const life = chart.lifeHouseIndex;
	const qiShuIdx = ((life - 8) % 12 + 12) % 12;   // 官禄宫=逆数第9=气数位
	const stem = ((chart.houses[qiShuIdx] || {}).ganzi || '').charAt(0);
	const starIdx = buildStarIndex(chart);
	const hua4 = (getActiveSiHuaGan()[stem]) || [];
	const huaLanding = {};
	const backToLife = [];
	hua4.forEach((star, i)=>{
		const at = starIdx[star] == null ? -1 : starIdx[star];
		huaLanding[HUA[i]] = { star, houseIndex: at, backToLife: at === life };
		if(at === life){ backToLife.push(HUA[i]); }
	});
	// 一六共宗:命(1)↔疾厄(6);推广一八奴仆/一九官禄(气数位)/一十田宅(逆数序 k)。
	const yiLiuGongZong = {
		'命(1)': life,
		'疾厄(6)': ((life - 5) % 12 + 12) % 12,
		'奴仆(8)': ((life - 7) % 12 + 12) % 12,
		'官禄(9·气数位)': qiShuIdx,
		'田宅(10)': ((life - 9) % 12 + 12) % 12,
	};
	return { qiShuIdx, stem, huaLanding, backToLife, yiLiuGongZong };
}

// 中州派:空宫(无正曜)借对宫十四正曜整组,庙旺按【借入宫】(本宫 i)地支重查。返回借入星数组([]=本宫有正曜/非空)。
export function borrowedStars(chart, i){
	const h = chart && chart.houses ? chart.houses[i] : null;
	if(!h || (h.starsMain || []).length > 0){ return []; }
	const opp = (i + 6) % 12;
	const src = (chart.houses[opp] || {}).starsMain || [];
	const zhi = (h.ganzi || '').charAt(1);   // 借入宫地支
	return src.map((s)=>{
		const base = stripFu(s.name);
		return { name: s.name, sihua: s.sihua, borrowed: true, fromIndex: opp, starlight: starLightOf(base, zhi, ZWEngineOptions.brightnessSource) };
	});
}
// 全盘各宫借宫结果(空宫才有值)。
export function allBorrowedStars(chart){
	const out = new Array(12).fill(null);
	if(!chart || !chart.houses){ return out; }
	for(let i = 0; i < 12; i++){ const b = borrowedStars(chart, i); if(b.length){ out[i] = b; } }
	return out;
}

// 紫云派:关系人生肖(地支)落本命同支宫=「太岁入卦宫」;南斗为男、北斗为女(§9.3)。
// relatives: [{branch, role, sex}];返回逐关系人 {branch, role, sex, houseIndex, dou}。
const MALE_TOKENS = ['m', '男', 'male', 'man', 'boy'];
export function taiSuiRuGua(chart, relatives){
	if(!chart || !chart.houses){ return []; }
	return (relatives || []).filter((r)=>r && r.branch).map((r)=>{
		const houseIndex = chart.houses.findIndex((h)=>((h || {}).ganzi || '').charAt(1) === r.branch);
		const male = MALE_TOKENS.indexOf(String(r.sex).toLowerCase()) >= 0;
		return { branch: r.branch, role: r.role || '', sex: r.sex, houseIndex, dou: male ? '南斗(男)' : '北斗(女)' };
	});
}
