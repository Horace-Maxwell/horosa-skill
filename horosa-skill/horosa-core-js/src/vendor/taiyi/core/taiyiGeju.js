// 太乙格局判定(§14)。纯派生:据 kintaiyi pan 的太乙/文昌/始击落点 + 主客大将宫,识别 掩/迫(内外)/囚/格/对。
// 断辞为公有领域术数通则,移植自文档「古法复原」引擎 detect_geju(以 kintaiyi 现成落点为输入,非重算)。

// 16 神环落点序(= 文档 POS2INDEX;与 TaiYiCore GONG16_ORDER 一致)。偶数索引=八正宫,奇数索引=八间神。
const RING16 = '子丑艮寅卯辰巽巳午未坤申酉戌乾亥'.split('');
// 太乙九宫方位对冲(乾1↔坤7、离2↔坎8、艮3↔兑6、震4↔巽9)
const OPPO_GONG = { 1: 7, 7: 1, 2: 8, 8: 2, 3: 6, 6: 3, 4: 9, 9: 4 };
// 正宫落点字符→太乙宫数(与 taiyiDuanfa NUM2ZHENGPOS 反向;离宫落点="午"非"离")
const POS2NUM = { 乾: 1, 午: 2, 艮: 3, 卯: 4, 酉: 6, 坤: 7, 子: 8, 巽: 9 };
// 和数集(上和/次和/下和;用于「关」判据「算长而和」)
const HE_NUMS = new Set([1, 4, 8, 2, 3, 6, 9, 12, 16, 21, 27, 34, 38]);

function ringIdx(pos){ return pos ? RING16.indexOf(pos) : -1; }
function isJianShen(idx){ return idx >= 0 && idx % 2 === 1; }   // 间神=奇数索引

// 据 pan 判格局。返回 [{ name, text, kind }]。kind 用于盘面连线/着色(掩/迫/囚/格/对)。
export function computeGeju(pan){
	if(!pan || !pan.taiyiPalace){ return []; }
	const taiyiPos = pan.taiyiPalace;          // 太乙落点(正宫)
	const taiyiIdx = ringIdx(taiyiPos);
	const taiyiNum = Number(pan.taiyiNum);     // 太乙宫数
	const wcPos = pan.skyeyes, sjPos = pan.sf;
	const wcIdx = ringIdx(wcPos), sjIdx = ringIdx(sjPos);
	const zhuDj = Number(pan.homeGeneral), keDj = Number(pan.awayGeneral);
	const out = [];
	// 掩:文昌/始击与太乙同落点
	if(wcPos && wcPos === taiyiPos){ out.push({ name: '掩(文昌掩太乙)', text: '阴盛阳衰,主将不得力、权移他手。', kind: 'yan', from: '文昌', to: '太乙' }); }
	if(sjPos && sjPos === taiyiPos){ out.push({ name: '掩(始击掩太乙)', text: '客方掩我,谋窃倾夺之象。', kind: 'yan', from: '始击', to: '太乙' }); }
	// 迫:文昌/始击在太乙前后一位(环上相邻)
	[['文昌', wcIdx, '文昌'], ['始击', sjIdx, '始击']].forEach(([nm, idx, src]) => {
		if(idx < 0 || taiyiIdx < 0){ return; }
		if((idx - taiyiIdx + 16) % 16 === 1){ out.push({ name: `迫(${nm}在太乙后一位)`, text: '外迫,外来不利。', kind: 'po', from: src, to: '太乙' }); }
		if((taiyiIdx - idx + 16) % 16 === 1){ out.push({ name: `迫(${nm}在太乙前一位)`, text: '内迫,事由内起。', kind: 'po', from: src, to: '太乙' }); }
	});
	// 囚:主大将与太乙同宫
	if(zhuDj && taiyiNum && zhuDj === taiyiNum){ out.push({ name: '囚(主大将同太乙)', text: '在绝阳之地君灾,在四/九/一/七宫辅相灾。', kind: 'qiu', from: '主大将', to: '太乙' }); }
	// 格:主大将与太乙对宫
	if(zhuDj && taiyiNum && zhuDj === OPPO_GONG[taiyiNum]){ out.push({ name: '格(主大将对太乙)', text: '君臣背离。', kind: 'ge', from: '主大将', to: '太乙' }); }
	// 对:太乙与始击隔宫相对
	if(sjIdx >= 0 && taiyiIdx >= 0 && (sjIdx - taiyiIdx + 16) % 16 === 8){ out.push({ name: '对(太乙始击相对)', text: '太乙与始击隔宫相对,彼此牵制。', kind: 'dui', from: '始击', to: '太乙' }); }
	// —— 补九式(提/挟/关/击)。判据依骨架明文,精断以排盘复核(文档偏松处已注) ——
	// 挟:文昌与始击分居太乙两侧相邻间神位(奇数索引)相夹 → 挟持之象。
	if(wcIdx >= 0 && sjIdx >= 0 && taiyiIdx >= 0){
		const before = (taiyiIdx - 1 + 16) % 16, after = (taiyiIdx + 1) % 16;
		if(isJianShen(before) && isJianShen(after)
			&& ((wcIdx === before && sjIdx === after) || (wcIdx === after && sjIdx === before))){
			out.push({ name: '挟(二目夹太乙)', text: '文昌始击分居两侧、夹持太乙,进退受制、多牵掣之象。', kind: 'xie', from: '文昌', to: '始击' });
		}
	}
	// 提:二目(文昌/始击)与太乙同象限(16 神四分),且主客大将皆在正宫(非中五) → 提挈之象。
	if(wcIdx >= 0 && sjIdx >= 0 && taiyiIdx >= 0){
		const quad = (i) => Math.floor(i / 4);
		if(quad(wcIdx) === quad(taiyiIdx) && quad(sjIdx) === quad(taiyiIdx) && zhuDj && keDj && zhuDj !== 5 && keDj !== 5){
			out.push({ name: '提(二目提太乙)', text: '二目与太乙同临一方、大将得正,提挈有援、事有主持。', kind: 'ti', from: '文昌', to: '太乙' });
		}
	}
	// 关:主客算皆「长」(≥11)且同属和数 → 断「算长而和者胜」，两强相持之关。
	const homeCal = Number(pan.homeCal), awayCal = Number(pan.awayCal);
	if(homeCal >= 11 && awayCal >= 11 && HE_NUMS.has(homeCal) && HE_NUMS.has(awayCal)){
		out.push({ name: '关(算长而和)', text: `主算 ${homeCal}、客算 ${awayCal} 皆长而和,两强相持、胜负在时,得先者利。`, kind: 'guan', from: '主算', to: '客算' });
	}
	// 击:始击(在正宫)与主大将或客大将同宫或对宫 → 击犯之象(客方相犯)。
	const sjNum = POS2NUM[sjPos];
	if(sjNum){
		const hit = [['主大将', zhuDj], ['客大将', keDj]].filter(([, dj]) => dj && (dj === sjNum || OPPO_GONG[sjNum] === dj));
		hit.forEach(([nm, dj]) => {
			out.push({ name: `击(始击犯${nm})`, text: `始击与${nm}${dj === sjNum ? '同宫' : '对宫'}相犯,主兵动、冲击、争夺之应。`, kind: 'ji', from: '始击', to: nm });
		});
	}
	return out;
}
