// 金色黎明四色阶之 King 阶(王阶,Atziluth/火界):22 大牌主色(路径主色)。色名为公有领域体系事实(Liber 777/Regardie),
// hex 为按色名的渲染近似。键=sid。BOTA/金色黎明 牌可显此色点;其余色阶(Queen/Prince/Princess)为 128 格大表,按需扩。
export const KING_SCALE = {
	the_fool: { name: '亮淡黄', hex: '#F3EDA6' },
	the_magician: { name: '黄', hex: '#F2DE2B' },
	high_priestess: { name: '蓝', hex: '#2F66E0' },
	the_empress: { name: '翠绿', hex: '#2FBE6E' },
	the_emperor: { name: '猩红', hex: '#E0241C' },
	the_hierophant: { name: '红橙', hex: '#E0531C' },
	the_lovers: { name: '橙', hex: '#E0881C' },
	the_chariot: { name: '琥珀', hex: '#E0AE1C' },
	strength: { name: '偏绿之黄', hex: '#C6D52B' },
	the_hermit: { name: '偏黄之绿', hex: '#8AC62B' },
	wheel_of_fortune: { name: '紫', hex: '#7B2CD6' },
	justice: { name: '翠绿', hex: '#2FBE6E' },
	hanged_man: { name: '深蓝', hex: '#16308A' },
	death: { name: '绿蓝', hex: '#1C9C9C' },
	temperance: { name: '蓝', hex: '#2F66E0' },
	the_devil: { name: '靛', hex: '#3B2C8A' },
	the_tower: { name: '猩红', hex: '#E0241C' },
	the_star: { name: '紫', hex: '#7B2CD6' },
	the_moon: { name: '绯红', hex: '#C81C4E' },
	the_sun: { name: '橙', hex: '#E0881C' },
	judgement: { name: '炽橙猩红', hex: '#F0461C' },
	the_world: { name: '靛/青黑', hex: '#2B2C5C' },
};

export function kingScaleColor(card){
	if(!card || card.arcana !== 'major'){ return null; }
	return KING_SCALE[card.sid] || null;
}
