// [QA-9] 「王牌」判据的单一真值源 —— 零依赖叶子模块。
//
// 为什么单独成文件:牌组把大牌另名以标其体系(minchiate_trump / visconti_trump),于是「这张是不是王牌」
// 这一判断遍布 schema 层(cardSchema)、判读层(verdict)、牌义层(marseilleMeanings)、读法层(pairReading)。
// 此前各处各写一份 `arcana === 'major'` 字面量,漏一处那两副牌组就在该处静默失灵
// (显示层出「undefined of undefined」、计时法报「异常牌组」、马赛对读恒空)。
// 判据放在被所有层依赖、自身不依赖任何人的叶子上,才不会因为循环导入而被迫再复制一份。
export function isTrumpArcana(arcana){
	return arcana === 'major' || (typeof arcana === 'string' && arcana.endsWith('_trump'));
}
