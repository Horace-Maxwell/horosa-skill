// divination/data/bodyParts.js
// 星座主管身体部位 + 度数定位（早/中/晚 = 上/中/下）。
// 来源：卜卦构建清单 §1.6。用于六宫受折磨部位、根本性痣验证、Dorotheus 手术避部位。
import { SIGNS } from './signs.js';

export function bodyPartsOf(signId){
	return (SIGNS[signId] || {}).body_parts || [];
}

// 座度数 → 部位上中下（早度=上方，中度=中间，晚度=下方）
export function degreePosition(deg){
	const d = ((deg % 30) + 30) % 30;
	if(d < 10) return '上方';
	if(d < 20) return '中间';
	return '下方';
}

// 阳右阴左（性别）+ 地平上前/下后（用于痣验证方位）
export function moleSide(signGender){ return signGender === 'masculine' ? '右侧' : '左侧'; }
export function moleFrontBack(aboveHorizon){ return aboveHorizon ? '身体前面' : '身体后面'; }

export default bodyPartsOf;
