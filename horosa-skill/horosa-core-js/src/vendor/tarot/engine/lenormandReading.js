// Lenormand 读法(与塔罗完全不同):名词×修饰成句 + 9 宫盒 + Grand Tableau(宫位/镜像/跳马/远近/连线/四角)。
// 36 张固定宫位:位置 i(0基)的宫义 = 第 (i+1) 张牌名(位置1=骑士宫…位置36=十字宫)。

const LENORMAND_HOUSES = ['骑士', '三叶草', '船', '房子', '树', '云', '蛇', '棺材', '花束', '镰刀', '鞭', '鸟', '孩子', '狐狸', '熊', '星', '鹳', '狗', '塔', '花园', '山', '岔路', '老鼠', '心', '戒指', '书', '信', '男人', '女人', '百合', '太阳', '月亮', '钥匙', '鱼', '锚', '十字'];

// 各神谕牌组的「指示牌锚」sid（男问者本人 / 女问者本人）。不同牌组本人牌 sid 编号不同:
// Lenormand 男人=28/女人=29;Kipper 主牌·男=01/主牌·女=02;Sibilla 默认无 GT(此处仅备)。
// grandTableau 不写死单一牌组,改按当前牌组取对应锚 sid——Lenormand 行为不变,Kipper 等取对各自本人牌。
const SIGNIFICATOR_ANCHORS = {
	lenormand: { man: 'lenormand_28', woman: 'lenormand_29' },
	kipper: { man: 'kipper_01', woman: 'kipper_02' },
};

// 从牌阵已抽出的卡片推断牌组(取首张含 arcana 的卡的 arcana),回退 lenormand。
function resolveAnchors(grid){
	const sample = grid.find((g) => g.card && g.card.arcana);
	const family = sample ? sample.card.arcana : 'lenormand';
	return SIGNIFICATOR_ANCHORS[family] || SIGNIFICATOR_ANCHORS.lenormand;
}

// 成对成句(小串):第一张主题(名词),其后修饰。draws=[{card}]
export function pairString(draws){
	const names = draws.map((d) => (d.card ? d.card.name_cn : '?'));
	if(names.length < 2){ return names[0] || ''; }
	return `${names[0]}（主题）× ${names.slice(1).join('·')}（修饰)`;
}

// 9 宫盒(3×3):中心焦点 + 周围 8 张。draws 长度 9。
export function box9(draws){
	if(draws.length < 9){ return { center: draws[4] && draws[4].card, around: [] }; }
	const center = draws[4].card;
	const around = [0, 1, 2, 3, 5, 6, 7, 8].map((i) => draws[i].card);
	return { center, around };
}

// Grand Tableau(36):cols 默认 8(8×4+末4)。返回 man/woman 行列、宫位叠读、镜像、跳马、四角、远近。
export function grandTableau(draws, cols){
	const C = cols || 8;
	const n = draws.length;
	const grid = draws.map((d, i) => ({ ...d, row: Math.floor(i / C), col: i % C, idx: i }));
	const find = (sid) => grid.find((g) => g.card && g.card.sid === sid);
	const anchors = resolveAnchors(grid);
	const man = find(anchors.man);
	const woman = find(anchors.woman);

	// 宫位叠读:每张牌"住"在其位置宫,牌义×宫义。
	// Lenormand 有标准 36 宫名(骑士…十字);Kipper 等无此宫名体系,只按位置编号读,避免误套 Lenormand 专有宫名。
	const sample = grid.find((g) => g.card && g.card.arcana);
	const useLenormandHouses = !sample || sample.card.arcana === 'lenormand';
	const houseName = (i) => (useLenormandHouses ? (LENORMAND_HOUSES[i] || `位置${i + 1}`) : `位置${i + 1}`);
	const houses = grid.map((g) => ({
		pos: g.idx + 1, house: houseName(g.idx),
		card: g.card ? g.card.name_cn : '?',
		read: g.card ? `${g.card.name_cn} 落于「${houseName(g.idx)}」` : '',
	}));

	// 指示牌行/列(贯穿生活的事 / 纵向影响),右=未来 左=过去 上=显意 下=潜意
	const lineFor = (anchor) => {
		if(!anchor){ return null; }
		const rowCards = grid.filter((g) => g.row === anchor.row).sort((a, b) => a.col - b.col);
		const colCards = grid.filter((g) => g.col === anchor.col).sort((a, b) => a.row - b.row);
		const past = rowCards.filter((g) => g.col < anchor.col).map((g) => g.card && g.card.name_cn);
		const future = rowCards.filter((g) => g.col > anchor.col).map((g) => g.card && g.card.name_cn);
		const above = colCards.filter((g) => g.row < anchor.row).map((g) => g.card && g.card.name_cn);
		const below = colCards.filter((g) => g.row > anchor.row).map((g) => g.card && g.card.name_cn);
		return {
			row: rowCards.map((g) => g.card && g.card.name_cn),
			col: colCards.map((g) => g.card && g.card.name_cn),
			past, future, above, below,
		};
	};

	// 镜像(以牌阵中心对称位置互照)
	const mirroring = grid.slice(0, Math.floor(n / 2)).map((g) => {
		const m = grid[n - 1 - g.idx];
		return { a: g.card && g.card.name_cn, b: m && m.card && m.card.name_cn };
	});

	// 跳马(国际象棋马步 L 形:±1行±2列 / ±2行±1列)从指示牌跳出
	const knightFrom = (anchor) => {
		if(!anchor){ return []; }
		const moves = [[1, 2], [1, -2], [-1, 2], [-1, -2], [2, 1], [2, -1], [-2, 1], [-2, -1]];
		return moves.map(([dr, dc]) => grid.find((g) => g.row === anchor.row + dr && g.col === anchor.col + dc))
			.filter(Boolean).map((g) => g.card && g.card.name_cn);
	};

	// 四角(全局概览/结论)
	const lastRowStart = Math.floor((n - 1) / C) * C;
	const corners = [grid[0], grid[C - 1], grid[lastRowStart], grid[n - 1]].filter(Boolean).map((g) => g.card && g.card.name_cn);

	return {
		cols: C, man, woman, houses,
		manName: man && man.card ? man.card.name_cn : '', womanName: woman && woman.card ? woman.card.name_cn : '',
		manLines: lineFor(man), womanLines: lineFor(woman),
		mirroring, manKnight: knightFrom(man), womanKnight: knightFrom(woman), corners,
	};
}

export default grandTableau;
