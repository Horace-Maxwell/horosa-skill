// 恒星中文名:细节页恒星相位与气象占共用。先取界面字典,再取这张表,都没有就保留原名。
import * as AstroText from '../../constants/AstroText.js';

export const STAR_NAME_CN = {
	Acamar: '天园六', Achernar: '水委一', Acubens: '柳宿增三', Adhafera: '轩辕十一', Adhara: '弧矢七', 'Al Jabhah': '轩辕十三', Alcyone: '昴宿六',
	Aldebaran: '毕宿五', Alderamin: '天钩五', Algedi: '牛宿二', Algenib: '壁宿一', Algenubi: '轩辕九', Algol: '大陵五', Algorab: '轸宿三',
	Alnilam: '参宿二', Alphard: '星宿一', Alphecca: '贯索四', Alpheratz: '壁宿二', Alrescha: '外屏七', Altair: '河鼓二', Antares: '心宿二',
	Arcturus: '大角', Arneb: '厕一', Ascella: '斗宿六', 'Asellus Australis': '鬼宿四', 'Asellus Borealis': '鬼宿三', Bellatrix: '参宿五',
	Betelgeuse: '参宿四', Bungula: '南门二', Canopus: '老人', Capella: '五车二', Castor: '北河二', Caph: '王良一', Dabih: '牛宿一',
	Deneb: '天津四', 'Deneb Algedi': '垒壁阵四', Denebola: '五帝座一', Diphda: '土司空', Dubhe: '天枢', Elnath: '五车五', Fomalhaut: '北落师门', Gienah: '轸宿一',
	Hamal: '娄宿三', Izar: '梗河一', Khambalia: '亢宿四', Kochab: '北极二', Lesath: '尾宿九', Menkalinan: '五车三', Menkent: '库楼三', Mintaka: '参宿三', Mirach: '奎宿九',
	Mirzam: '军市一', Nashira: '垒壁阵三', Nunki: '斗宿四', Pollux: '北河三', Porrima: '东上相', Praesepe: '积尸气', Procyon: '南河三',
	'Ras Algethi': '帝座', Rasalhague: '候', Regulus: '轩辕十四', Rigel: '参宿七', Rukbat: '天渊三', Sadalmelik: '危宿一', Sadalsuud: '虚宿一',
	Scheat: '室宿二', Shaula: '尾宿八', Sirius: '天狼', Spica: '角宿一', Toliman: '南门二', Vega: '织女一', Vindemiatrix: '太微左垣四',
	Zavijava: '右执法', Zosma: '西上相', Zubenelgenubi: '氐宿一', Zubeneschamali: '氐宿四',
};

export function starNameCn(name){
	return (AstroText.AstroMsg && AstroText.AstroMsg[name]) || STAR_NAME_CN[name] || `${name}`;
}
