// 六爻《断易天机》断语库(tianjiDoctrine 469KB,古籍抽取件)访问层:记忆化动态 import + 同步取缓存 +
// 占类门映射 + 按占测事项【有界摘要】。显示层(LiuYaoZhanLeiView)与 AI 快照(liuyaoSnapshotEx)共用一份,
// 防口径分叉(WP-2/WP-6)。数据一字不改,只加访问/摘要层。结构契约:DOCTRINE = { [占类门]: Array<{source,text}> }。

// askType → 《断易天机》占类门匹配词(门名从抽取件原书写法:遁亡/斗欧/咒咀)。UI 与快照单一真值源。
export const ASK_TO_DOCTRINE = {
	lost: ['遗失', '盗贼', '遁亡'], travel: ['出行', '行人', '音信', '觅人'], lawsuit: ['词讼', '斗欧'],
	home: ['家宅', '迁移', '香火', '地理'], guishen: ['鬼神', '怪异', '咒咀', '祈禳'], study: ['学问', '求事'],
	guochao: ['国朝'], self: ['身命', '求事'], opponent: ['趋谒'], wealth: ['求财', '买卖'],
	career: ['仕宦', '词讼'], marriage_m: ['婚姻', '分娩'], marriage_f: ['婚姻', '分娩'],
	illness: ['疾病', '医药'], parents: ['家宅', '田禾'], children: ['六畜', '春蚕'], doctor: ['医药'],
	sibling: ['斗欧'], thief: ['盗贼', '遗失', '遁亡'], weather_rain: ['天时'], weather_sun: ['天时'],
};

let _doctrine = null;   // 缓存 DOCTRINE 对象
let _loading = null;    // 在途 promise(并发合流)

// 异步载入(记忆化):首次触发动态 import(异步 chunk),后续复用缓存/在途 promise。
export function loadDoctrine(){
	if(_doctrine){ return Promise.resolve(_doctrine); }
	if(_loading){ return _loading; }
	_loading = import('./tianjiDoctrine')
		.then((m) => { _doctrine = m.DOCTRINE || null; _loading = null; return _doctrine; })
		.catch(() => { _loading = null; return null; });
	return _loading;
}
// 同步取缓存(未载返 null)——同步路径(AI 快照)用,配合 mount 预热。
export function getDoctrine(){ return _doctrine; }
// 外部回填缓存(显示层若已自载,可同步给缓存,避免二次 import)。
export function setDoctrine(d){ if(d){ _doctrine = d; } }

// 按 askType 从 DOCTRINE 取【有界摘要】:总断门(纲领)top-N + 每命中门 top-N,硬上限 cap 条(防 token 膨胀),每条带出处。
export function doctrineSummaryFor(askType, doctrine, opts){
	const d = doctrine || _doctrine;
	if(!d){ return []; }
	const perMen = (opts && opts.perMen) || 4;
	const cap = (opts && opts.cap) || 20;
	const kws = ASK_TO_DOCTRINE[askType] || [];
	const keys = Object.keys(d);
	const zong = keys.filter((k) => k.indexOf('总断') >= 0).slice(0, 1);
	const hit = keys.filter((k) => k.indexOf('总断') < 0 && kws.some((w) => k.indexOf(w) >= 0));
	const out = [];
	const take = (k) => {
		(d[k] || []).slice(0, perMen).forEach((r) => { if(r && r.text){ out.push({ men: k, source: r.source || '', text: r.text }); } });
	};
	zong.forEach(take);
	hit.forEach(take);
	return out.slice(0, cap);
}
