// 从上游 utils/helper.js 逐字取出的单个纯函数。整份 helper.js 是 984 行的大杂烩，还牵
// msg/errmsg/gps/request 四个不可 headless 的依赖 —— 为一个位运算把它整棵搬进来不划算。
export function littleEndian(bits){
	let n = 0;
	for(let i=0; i<bits.length; i++){
		let v = bits[i];
		if(v < 0){
			return -1;
		}

		n = n | (v<<i);
	}

	return n;
}
