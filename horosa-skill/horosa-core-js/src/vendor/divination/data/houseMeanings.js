// divination/data/houseMeanings.js
// 宫位含义 + 共同征象星 + 角续果 + 转宫（派生宫）规则。
// 来源：卜卦构建清单 §1.9 + 择日清单 §2.3。
// turnedHouse 在 §3 选征象星、痣验证被问之人处大量使用（如兄弟的财产 = 3 宫起的 2 宫 = 本盘 4 宫）。

export const HOUSE_MEANINGS = {
	1: { natural: ['生命', '身体', '外形', '行动力', '事项本身/发起者'], co_sig: ['saturn', 'mars'], angularity: 'angular' },
	2: { natural: ['财产', '金钱', '有形资源', '赚钱花钱能力'], co_sig: ['jupiter', 'venus'], angularity: 'succedent' },
	3: { natural: ['兄弟', '邻居', '短途旅行', '沟通', '初级教育', '交通'], co_sig: ['mars', 'moon'], angularity: 'cadent' },
	4: { natural: ['父', '田宅', '不动产', '土地', '坟墓', '根源/结局'], co_sig: ['sun', 'moon'], angularity: 'angular' },
	5: { natural: ['子女', '欢愉', '恋爱', '创作', '赌博', '运动', '表演'], co_sig: ['venus', 'sun'], angularity: 'succedent' },
	6: { natural: ['疾病', '仆人', '部属', '服务', '劳工', '小家畜', '宠物'], co_sig: ['mercury'], angularity: 'cadent' },
	7: { natural: ['配偶', '婚姻', '合伙', '公开的敌人', '契约', '诉讼', '交涉'], co_sig: ['moon', 'venus'], angularity: 'angular' },
	8: { natural: ['死亡', '遗产', '配偶财产', '性', '租税', '商业', '玄秘'], co_sig: ['saturn', 'mars'], angularity: 'succedent' },
	9: { natural: ['宗教', '远行', '学问', '哲学', '法律', '出版', '国外'], co_sig: ['jupiter'], angularity: 'cadent' },
	10: { natural: ['母', '职业', '荣誉', '名望', '地位', '掌权'], co_sig: ['mars', 'saturn'], angularity: 'angular' },
	11: { natural: ['朋友', '愿望', '希望', '社会关系', '团体'], co_sig: ['sun', 'saturn'], angularity: 'succedent' },
	12: { natural: ['私敌', '大牲畜', '监禁', '秘密', '隐退', '自我毁灭', '心灵'], co_sig: ['venus', 'jupiter'], angularity: 'cadent' },
};

export const ANGULAR_HOUSES = [1, 4, 7, 10];
export const SUCCEDENT_HOUSES = [2, 5, 8, 11];
export const CADENT_HOUSES = [3, 6, 9, 12];

export function angularityOf(house){
	if(ANGULAR_HOUSES.indexOf(house) >= 0) return 'angular';
	if(SUCCEDENT_HOUSES.indexOf(house) >= 0) return 'succedent';
	return 'cadent';
}

// 转宫：以 baseHouse 为「他的第 1 宫」，顺数第 offset 宫，返回本盘宫位号(1..12)。
// 例：兄弟(3宫)的财产(其2宫) → turnedHouse(3,2) = 4。
export function turnedHouse(baseHouse, offset){
	const b = ((baseHouse - 1) % 12 + 12) % 12;
	const o = ((offset - 1) % 12 + 12) % 12;
	return ((b + o) % 12) + 1;
}

// 公司开业各宫象征（择日事业盘，择日清单 §2.3）
export const COMPANY_HOUSE = {
	1: '公司成员/股东/员工士气·企业文化(外显)', 2: '流动资产/金钱收入', 3: '内部沟通/内部文化',
	4: '办公室/厂房/固定资产', 5: '中级主管/创新力', 6: '员工/劳工', 7: '对外关系/竞争者/法律/合作',
	8: '会计/固定资产/税务', 9: '广告/顾问', 10: '最高管理者(总经理/总裁)', 11: '公司获利/合作', 12: '暗中的敌人/隐藏竞争者',
};

// 汽车各宫部位（购车/交车盘可类推任意「物」，择日清单 §2.3）
export const CAR_HOUSE = {
	1: '车头/驾驶座/点火', 2: '内装/音响', 3: '风扇/油泵/进气/轮圈', 4: '油管/后座/安全带/水箱',
	5: '底盘/引擎/前灯/活塞', 6: '滤油器/备胎', 7: '避震/悬吊/雨刷', 8: '排气/消音/散热',
	9: '顶棚/油箱', 10: '离合/煞车/变速箱', 11: '胎压/电池/化油器/电线', 12: '轮胎/行李箱',
};

export default HOUSE_MEANINGS;
