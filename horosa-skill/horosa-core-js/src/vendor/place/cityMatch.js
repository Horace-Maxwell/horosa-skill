// 城市检索纯函数(与 UI 解耦,便于单测):富化条目 + 繁简折叠 + 评分检索。
// 兼容两种条目形状:小库 {name,en,region,lat,lng,p} 与大库 {n,e,r,p,y,x};p=空格分隔无声调拼音。

// 就地补上检索字段(小写名/英文/去空格英文/全拼/首字母),只算一次并缓存到对象上(_idx 守卫)。
export function enrichCity(c){
	if(c._idx){
		return c;
	}
	const name = c.n !== undefined ? c.n : c.name;
	const en = (c.e !== undefined ? c.e : c.en) || '';
	const region = (c.r !== undefined ? c.r : c.region) || '';
	const py = `${c.p || ''}`;
	c._name = `${name}`;
	c._en = `${en}`;
	c._region = `${region}`;
	c._lat = c.y !== undefined ? c.y : c.lat;
	c._lng = c.x !== undefined ? c.x : c.lng;
	c._n = c._name.toLowerCase();
	c._e = c._en.toLowerCase();
	c._r = c._region.toLowerCase();
	c._ef = c._e.replace(/\s+/g, '');                                   // 去空格英文: "new york"→"newyork"
	c._ea = foldAscii(c._e);                                            // 去重音英文: "reykjavík"→"reykjavik"
	c._eaf = c._ea.replace(/\s+/g, '');                                 // 去重音去空格: "são paulo"→"saopaulo"
	c._pf = py ? py.replace(/\s+/g, '') : '';                           // 全拼: "bei jing"→"beijing"
	c._pi = py ? py.split(/\s+/).map((s)=>s[0] || '').join('') : '';    // 首字母: "bj"
	c._idx = true;
	return c;
}

// 拉丁重音折叠:NFD 拆分去组合符号 + 无法拆分的字母映射(ø/æ/ß/ł/đ 等),让 Reykjavik 命中 Reykjavík。
const ASCII_FOLD_MAP = { 'ø': 'o', 'æ': 'ae', 'ß': 'ss', 'ł': 'l', 'đ': 'd', 'ð': 'd', 'þ': 'th', 'œ': 'oe', 'ı': 'i' };
export function foldAscii(s){
	const text = `${s || ''}`;
	if(!text){
		return '';
	}
	try{
		return text.normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/[øæßłđðþœı]/g, (ch)=>ASCII_FOLD_MAP[ch] || ch);
	}catch(e){
		return text;
	}
}

// 把查询里的繁体字折叠成简体(只用城市名出现过的字映射,极小),让繁体输入也能命中简体库。
export function foldTrad(s, map){
	let out = '';
	for(const ch of `${s}`){
		out += ((map && map[ch]) || ch);
	}
	return out;
}

// 富化条目 → 渲染所需 {name,en,region,lat,lng}。
export function toCityItem(c){
	return { name: c._name, en: c._en, region: c._region, lat: c._lat, lng: c._lng };
}

// 专业级城市检索:简繁折叠 + 简体名 + 全拼/首字母 + 英文(含去空格) + 地区,四档评分排序。
// lists 为若干条目数组(小库优先);返回 {name,en,region,lat,lng}[]。
export function searchCities(rawQuery, lists, foldMap, limit){
	return searchCitiesScored(rawQuery, lists, foldMap, limit).map((h)=>toCityItem(h.c));
}

// 带评分版:返回 {c(富化条目), score}[](score 0=精确/1=名称前缀/2=拼音英文前缀/3=包含),
// 供 AI 助手地名解析做歧义判定;searchCities 委托本函数,行为逐字节不变(parity 测试锁)。
export function searchCitiesScored(rawQuery, lists, foldMap, limit){
	const RESULT_LIMIT = limit || 80;
	const raw = `${rawQuery || ''}`.trim();
	if(!raw){
		return [];
	}
	const q = foldTrad(raw, foldMap).toLowerCase();
	const qa = foldAscii(q);                                            // 重音折叠后的查询(只增命中,不改评分次序)
	const qaf = qa.replace(/\s+/g, '');
	const hits = [];          // {c, score}:score 越小越优先
	const seen = new Set();
	let strongCount = 0;      // score<=2(前缀级以上)的数量,用于提前停止全表扫描
	const scan = (list)=>{
		if(!Array.isArray(list)){
			return;
		}
		for(let i = 0; i < list.length; i++){
			if(strongCount >= RESULT_LIMIT || hits.length >= RESULT_LIMIT * 3){
				return;
			}
			const c = enrichCity(list[i]);
			let score = -1;
			if(c._n === q || c._pf === q || c._pi === q || c._ef === q || c._eaf === qaf){
				score = 0;                                              // 精确(名/全拼/首字母/英文/去重音英文)
			}else if(c._n.startsWith(q)){
				score = 1;                                              // 名称前缀
			}else if(c._pf.startsWith(q) || c._pi.startsWith(q) || c._e.startsWith(q) || c._ef.startsWith(q) || c._ea.startsWith(qa) || c._eaf.startsWith(qaf)){
				score = 2;                                              // 拼音/英文前缀(含去重音)
			}else if(c._n.indexOf(q) >= 0 || c._e.indexOf(q) >= 0 || c._r.indexOf(q) >= 0 || c._ea.indexOf(qa) >= 0){
				score = 3;                                              // 包含
			}else{
				continue;
			}
			const key = `${c._name}|${c._lat}|${c._lng}`;
			if(seen.has(key)){
				continue;
			}
			seen.add(key);
			hits.push({ c, score });
			if(score <= 2){
				strongCount++;
			}
		}
	};
	for(const list of lists){
		scan(list);
	}
	// 同档内按名称长度、再按全拼长度升序(更短/更核心的城市靠前,如 西安 先于 翔安)。
	hits.sort((a, b)=>(a.score - b.score) || (a.c._name.length - b.c._name.length) || (a.c._pf.length - b.c._pf.length));
	return hits.slice(0, RESULT_LIMIT);
}
