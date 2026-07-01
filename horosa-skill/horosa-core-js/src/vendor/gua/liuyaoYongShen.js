// 六爻用神体系(WP-E):占测事项→用神六亲/世/应 取用表 + 原神/忌神/仇神 推导 + 用神爻定位(多现取舍)。
// 取用表忠于古典通用口径(§5.1);原忌仇按生克链(§5.2)。断结构真值,吉凶交 AI。

// 六亲相生链(X 生 next):父母→兄弟→子孙→妻财→官鬼→父母
const SHENG_NEXT = { 父母: '兄弟', 兄弟: '子孙', 子孙: '妻财', 妻财: '官鬼', 官鬼: '父母' };
// 六亲相克链(X 克 next):父母→子孙→官鬼→兄弟→妻财→父母
const KE_NEXT = { 父母: '子孙', 子孙: '官鬼', 官鬼: '兄弟', 兄弟: '妻财', 妻财: '父母' };
function invert(map){ const o = {}; Object.keys(map).forEach((k) => { o[map[k]] = k; }); return o; }
const SHENG_PREV = invert(SHENG_NEXT); // 生 X 者(原神)
const KE_PREV = invert(KE_NEXT);       // 克 X 者(忌神)

export const LIUQIN_LIST = ['父母', '兄弟', '子孙', '妻财', '官鬼'];

// ── 原神/忌神/仇神(用神为六亲时;世/应 用神返回 null) ──
export function relativeRoles(yong){
	if(!SHENG_PREV[yong]){ return null; }
	const yuan = SHENG_PREV[yong];   // 生用神
	const ji = KE_PREV[yong];        // 克用神
	const chou = SHENG_PREV[ji];     // 克原神而生忌神
	return { yuan, ji, chou };
}

// ── §5.1 通用取用表:occasion → 用神(六亲或「世」「应」)+ 可选次用神 + 说明 ──
export const YONGSHEN_CATEGORIES = [
	{ key: 'self', label: '自身/综合运势', yong: '世', note: '凡测己身、综合运势以世为用' },
	{ key: 'opponent', label: '对方/敌方/合作方/所往之地', yong: '应', note: '与世相对' },
	{ key: 'wealth', label: '求财/买卖/价格/雇员', yong: '妻财', note: '财为养命之源' },
	{ key: 'career', label: '功名/官职/工作/考试/名声', yong: '官鬼', note: '官与鬼同位' },
	{ key: 'marriage_m', label: '婚姻(男测)', yong: '妻财', secondary: '世', note: '男以妻财为妻、世为己、应为对方' },
	{ key: 'marriage_f', label: '婚姻(女测)', yong: '官鬼', secondary: '世', note: '女以官鬼为夫、世为己、应为对方' },
	{ key: 'illness', label: '疾病', yong: '官鬼', secondary: '子孙', note: '官鬼为病症、子孙为医药、用神为患者' },
	{ key: 'parents', label: '父母/长辈/文书/契约/房产/车船', yong: '父母', note: '一切庇护、凭证类' },
	{ key: 'children', label: '子女/晚辈/下属/六畜/解忧', yong: '子孙', note: '福德解忧之神' },
	{ key: 'doctor', label: '求医/药物/僧道', yong: '子孙', note: '子孙为医药福神' },
	{ key: 'sibling', label: '兄弟/朋友/同辈/合伙/竞争', yong: '兄弟', note: '劫财阻隔之神' },
	{ key: 'thief', label: '盗贼/鬼祟/官非', yong: '官鬼', note: '官鬼亦主盗贼鬼祟' },
	{ key: 'weather_rain', label: '天气·雨/消息', yong: '父母', note: '雨、消息属父母' },
	{ key: 'weather_sun', label: '天气·晴', yong: '子孙', note: '晴天属子孙' },
];

export function getYongShenCategory(key){
	return YONGSHEN_CATEGORIES.find((c) => c.key === key) || YONGSHEN_CATEGORIES[0];
}

// ── 解析某占测事项的完整用神角色 ──
export function resolveYongShen(key){
	const cat = getYongShenCategory(key);
	const roles = relativeRoles(cat.yong); // 世/应 → null
	return { key: cat.key, label: cat.label, yong: cat.yong, secondary: cat.secondary || null, note: cat.note, roles };
}

// ── 在六爻中定位 target(六亲名 或 '世'/'应')所临爻位(1-6) ──
// yaos 为 analyzeGua().yaos(含 liuqin / shiYing / zhi)
export function locateYaos(yaos, target){
	if(!Array.isArray(yaos)){ return []; }
	if(target === '世' || target === '应'){
		return yaos.filter((y) => y.shiYing === target).map((y) => y.pos);
	}
	return yaos.filter((y) => y.liuqin === target).map((y) => y.pos);
}

// ── 用神多现取舍(§5.1 注):临日月者、动者、临世应者、独发者优先。返回 {candidates, primary} ──
// ctx:{ dayZhi, monthZhi, movingPositions:[..] }(movingPositions 为动爻位集,可选)
export function pickYongShenYao(yaos, target, ctx){
	const c = ctx || {};
	const positions = locateYaos(yaos, target);
	if(positions.length === 0){ return { candidates: [], primary: null, multiple: false }; }
	const moving = new Set(c.movingPositions || []);
	const onlyOneMoving = (c.movingPositions || []).length === 1;
	const scored = positions.map((pos) => {
		const y = yaos[pos - 1] || {};
		let score = 0;
		const flags = [];
		if(y.shiYing === '世' || y.shiYing === '应'){ score += 8; flags.push('临世应'); }
		if(moving.has(pos)){ score += 4; flags.push('发动'); if(onlyOneMoving){ score += 2; flags.push('独发'); } }
		if(c.dayZhi && y.zhi === c.dayZhi){ score += 3; flags.push('临日'); }
		if(c.monthZhi && y.zhi === c.monthZhi){ score += 3; flags.push('临月'); }
		if(y.xunKong){ flags.push('旬空'); } // 空者亦为取舍要点,标记不加权
		return { pos, score, flags };
	});
	scored.sort((a, b) => b.score - a.score || a.pos - b.pos);
	return { candidates: scored, primary: scored[0].pos, multiple: positions.length > 1 };
}

// ── 汇总:对一卦给出用神/原忌仇 的定位 + 旺衰摘要(供右栏 + AI 快照) ──
export function analyzeYongShen(yaos, key, ctx){
	const r = resolveYongShen(key);
	const c = ctx || {};
	const out = { key: r.key, label: r.label, note: r.note, yong: r.yong, secondary: r.secondary, roles: r.roles, located: {} };
	const pickOne = (target) => {
		if(!target){ return null; }
		const p = pickYongShenYao(yaos, target, c);
		return { target, ...p };
	};
	out.located.yong = pickOne(r.yong);
	out.located.secondary = pickOne(r.secondary);
	if(r.roles){
		out.located.yuan = pickOne(r.roles.yuan);
		out.located.ji = pickOne(r.roles.ji);
		out.located.chou = pickOne(r.roles.chou);
	}
	return out;
}
