import * as AstroConst from '../../constants/AstroConst.js';
import * as LRConst from './LRConst.js';
// headless stub：genCuangs(三传计算) 不用绘图/tooltip；randomStr 只产 this.id 占位串。
const randomStr = (n) => 'x'.repeat(Number(n) || 4);
const creatTooltip = () => {};
const drawPath = () => {}; const drawTextH = () => {}; const drawTextV = () => {};
const buildLiuRengHouseTipObj = () => ({}); const buildLiuRengShenTipObj = () => ({});

function extractBranch(value){
	const txt = `${value || ''}`;
	const match = txt.match(/[子丑寅卯辰巳午未申酉戌亥]/);
	return match ? match[0] : '';
}

class ChuangChart {
	constructor(option){
		this.owner = option.owner;
		this.chartObj = option.chartObj;
		this.nongli = option.nongli;
		this.liuRengChart = option.liuRengChart;
		this.ke = option.ke;
		this.upZi = option.liuRengChart.upZi;
		this.downZi = option.liuRengChart.downZi;
		this.tianJiang = option.liuRengChart.houseTianJiang;

		this.x = option.x;
		this.y = option.y;
		this.width = option.width;
		this.height = option.height;

		this.divTooltip = option.divTooltip;

		this.id = 'chart' + randomStr(8);

		this.svg = null;
		this.color = AstroConst.AstroColor.Stroke;
		this.bgColor = LRConst.getHouseColor(0);

	}

	buildChuanBranchTipObj(data){
		const gz = data && data[2] ? `${data[2]}` : '';
		const zhi = extractBranch(gz);
		return buildLiuRengShenTipObj(zhi);
	}

	buildChuanJiangTipObj(data){
		const gz = data && data[2] ? `${data[2]}` : '';
		const zhi = extractBranch(gz);
		const jiang = data && data[0] ? `${data[0]}` : '';
		const idx = this.upZi.indexOf(zhi);
		const di = idx >= 0 ? (this.downZi[idx] || '') : '';
		return buildLiuRengHouseTipObj(jiang, zhi, di || zhi);
	}

	draw(){
		this.owner.select('#' + this.id).remove();
		let container = this.owner.append('g').attr('id', this.id);
		this.svg = container;
		this.svg.append('rect')
			.attr('fill', AstroConst.AstroColor.ChartBackgroud)
			.attr('x', this.x).attr('y', this.y)
			.attr('width', this.width).attr('height', this.height);

		this.genCuangs();
		this.drawCuangs();
	}

	getCuangXY(){
		let x = this.x;
		let y = this.y;
		let houseW = this.width/3;
		let houseH = this.height;

		let aryXY = [];
		aryXY[0] = {x:x+houseW*2, y:y, w:houseW, h:houseH};
		aryXY[1] = {x:x+houseW, y:y, w:houseW, h:houseH};
		aryXY[2] = {x:x, y:y, w:houseW, h:houseH};
		return aryXY;
	}

	drawCuangs(){
		let data = [
			[this.cuangs.tianJiang[0], this.cuangs.liuQin[0], this.cuangs.cuang[0]],
			[this.cuangs.tianJiang[1], this.cuangs.liuQin[1], this.cuangs.cuang[1]],
			[this.cuangs.tianJiang[2], this.cuangs.liuQin[2], this.cuangs.cuang[2]]
		]
		let ords = this.getCuangXY();
		this.drawCuang(ords[0], '初传', data[0]);
		this.drawCuang(ords[1], '中传', data[1]);
		this.drawCuang(ords[2], '末传', data[2]);

		if(this.liuRengChart){
			this.liuRengChart.cuangName = this.cuangs.name;
		}
	}

	drawCuang(ord, title, data){
		let x1 = ord.x;
		let y1 = ord.y;
		let w = ord.w;
		let h = ord.h/4;
		
		this.svg.append('rect')
			.attr('fill', this.bgColor)
			.attr('x', x1).attr('y', y1)
			.attr('width', w).attr('height', h);
		this.svg.append('rect')
			.attr('fill', AstroConst.AstroColor.ChartBackgroud)
			.attr('x', x1).attr('y', y1 + ord.h/4)
			.attr('width', w).attr('height', 3*h);

		let tw = w*3/4;
		let x = x1 + w/2 - tw/2;
		let txtdata = title.split('');
		h = h/2;
		let y = ord.y + h/2;
		drawTextH(this.svg, txtdata, x, y, tw, h, 2, this.color);

		y1 = ord.y + ord.h/4;
		h = (ord.h - ord.h/4) / 2;
		txtdata = data[2].split('');
		drawTextV(this.svg, txtdata, x1, y1, w, h, 5, this.color);
		const zhiTip = this.buildChuanBranchTipObj(data);
		if(this.divTooltip && zhiTip){
			const zhiHot = this.svg.append('g');
			zhiHot.append('rect')
				.attr('x', x1)
				.attr('y', y1 + h / 2)
				.attr('width', w)
				.attr('height', h / 2)
				.attr('fill', 'rgba(0,0,0,0.001)')
				.attr('stroke', 'none')
				.attr('stroke-width', 0)
				.style('pointer-events', 'all');
			creatTooltip(this.divTooltip, zhiHot, zhiTip, null, true, true);
		}

		y1 = y1 + h;
		h = h / 2;
		txtdata = data[0].split('');
		const jiangSvg = drawTextH(this.svg, txtdata, x, y1, tw, h, 2, LRConst.LRColor.tianJiangColor);
		const jiangTip = this.buildChuanJiangTipObj(data);
		if(this.divTooltip && jiangTip){
			creatTooltip(this.divTooltip, jiangSvg, jiangTip, null, true, true);
		}

		y1 = y1 + h;
		txtdata = data[1].split('');
		drawTextH(this.svg, txtdata, x, y1, tw, h, 2, LRConst.LRColor.liuQinColor);

	}

	genCuangs(){
		let cuang = this.getSangCuang();
		let tj = [];
		let liuqin = [];
		let gan = this.nongli.dayGanZi.substr(0, 1);
		let dayzi = this.nongli.dayGanZi.substr(1);
		let xun = LRConst.getXun(gan, dayzi);
		let xunGanMap = {};
		for(let i=0; i<xun.length && i<LRConst.GanList.length; i++){
			xunGanMap[xun[i]] = LRConst.GanList[i];
		}
		let gz = [];
		for(let i=0; i<3; i++){
			let zi = cuang.cuang[i];
			let idx = this.upZi.indexOf(zi);
			tj[i] = this.tianJiang[idx];
			liuqin[i] = LRConst.ZiLiuQin[zi][gan];
			if(xunGanMap[zi]){
				gz[i] = xunGanMap[zi] + zi;
			}else{
				gz[i] = '空' + zi;
			}
		}
		this.cuangs = cuang;
		this.cuangs.cuang = gz;
		this.cuangs.tianJiang = tj;
		this.cuangs.liuQin = liuqin;
	}

	getSangCuang(){
		// 发三传九法的判定顺序须严格按典籍(0.基石/2.九法)：
		// 伏吟/返吟(式) → 贼克(贼/摄) → [比用/涉害,见 isJinKe*] → 遥克 → 八专 → 别责 → 昴星。
		// 关键点：
		//  · 遥克必须在八专之前——八专(干支同位)若四课无近克但日干与他课上神有遥克,
		//    按九法应归遥克(第4法)而非八专(第9法)。原实现把 isBaZhuang 放在 isYaoKe 之前,
		//    会把"八专结构 + 遥克"误判为八专课,故此处下移。
		//  · 八专须在别责之前——八专(一课=三课)会令二课=四课,从而满足 isBieZe 的
		//    "某两课相同",若先判别责会被误吞,故八专优先于别责。
		//  · 昴星(isMaoXing)是无克且四课俱全的兜底(总会返回),必须最后判。
		let cuang = this.isFuYin();
		if(cuang){
			return cuang;
		}

		cuang = this.isFangYin();
		if(cuang){
			return cuang;
		}


		cuang = this.isJinKe0();
		if(cuang){
			return cuang;
		}

		cuang = this.isJinKe1();
		if(cuang){
			return cuang;
		}

		cuang = this.isYaoKe0();
		if(cuang){
			return cuang;
		}

		cuang = this.isYaoKe1();
		if(cuang){
			return cuang;
		}

		cuang = this.isBaZhuang();
		if(cuang){
			return cuang;
		}

		cuang = this.isBieZe();
		if(cuang){
			return cuang;
		}

		cuang = this.isMaoXing();
		return cuang;
	}

	getCuang(cuang0){
		let idx = this.downZi.indexOf(cuang0);
		let cuang1 = this.upZi[idx];
		idx = this.downZi.indexOf(cuang1);
		let cuang2 = this.upZi[idx];
		return [cuang0, cuang1, cuang2]
	}

	uniqueZiList(cuangs){
		const seen = new Set();
		const res = [];
		for(let i=0; i<cuangs.length; i++){
			const zi = cuangs[i];
			if(!zi || seen.has(zi)){
				continue;
			}
			seen.add(zi);
			res.push(zi);
		}
		return res;
	}

	getSeHais(cuangs){
		const ziList = this.uniqueZiList(cuangs || []);
		if(ziList.length === 0){
			return null;
		}
		let maxcuang = 0;
		let stack = [];
		for(let i=0; i<ziList.length; i++){
			let cnt = this.getSeHaiCount(ziList[i]);
			if(cnt > maxcuang){
				maxcuang = cnt;
				stack = [];
				stack.push(ziList[i]);
			}else if(cnt === maxcuang){
				stack.push(ziList[i]);
			}
		}
		let res = {};
		if(stack.length === 1){
			res.cuang = this.getCuang(stack[0]);
			res.name = '涉害课';
			return res;
		}else{
			let dt = [];
			for(let i=0; i<stack.length; i++){
				let idx = this.upZi.indexOf(stack[i]);
				let zi = this.downZi[idx];
				if(LRConst.ZiMeng.indexOf(zi) >= 0){
					dt.push(stack[i]);
				}
			}
			if(dt.length === 1){
				res.cuang = this.getCuang(dt[0]);
				res.name = '见机课';
				return res;	
			}

			dt = [];
			for(let i=0; i<stack.length; i++){
				let idx = this.upZi.indexOf(stack[i]);
				let zi = this.downZi[idx];
				if(LRConst.ZiZong.indexOf(zi) >= 0){
					dt.push(stack[i]);
				}
			}
			if(dt.length === 1){
				res.cuang = this.getCuang(dt[0]);
				res.name = '察微课';
				return res;	
			}
			
			let  daygan = this.nongli.dayGanZi.substr(0, 1);
			let ke = null;
			if(LRConst.YangGan.indexOf(daygan) >= 0){
				ke = this.ke[0];
			}else{
				ke = this.ke[2];
			}
			res.cuang = this.getCuang(ke[1]);
			res.name = '缀瑕课';
			return res;	

		}
	}

	getSeHaiCount(cuang){
		let cnt = 0;
		let upidx = this.upZi.indexOf(cuang);
		let downidx = this.downZi.indexOf(cuang);
		downidx = downidx >= upidx ? downidx : downidx + 12;
		for(let i=upidx; i<downidx; i++){
			let idx = i % 12;
			let zi = this.downZi[idx];
			if(LRConst.isRestrain(zi, cuang)){
				cnt = cnt + 1;
			}
			let gan = LRConst.ZiHanGan[zi];
			if(gan){
				let ganary = gan.split('');
				for(let i=0; i<ganary.length; i++){
					if(LRConst.isRestrain(ganary[i], cuang)){
						cnt = cnt + 1;
					}		
				}
			}
		}
		return cnt;
	}

	isJinKe0(){
		let flag = true;
		let stack = [];
		for(let i=0; i<4; i++){
			let ke = this.ke[i];
			flag = LRConst.isRestrain(ke[2], ke[1]);
			if(flag){
				stack.push(ke[1]);
			}
		}
		stack = this.uniqueZiList(stack);
		if(stack.length === 1){
			let res = {};
			res.cuang = this.getCuang(stack[0]);
			res.name = '重审课';
			return res;
		}else if(stack.length > 1){
			let gan = this.nongli.dayGanZi.substr(0, 1);
			let yinyang = LRConst.sameYingYang(gan, stack);
			const yinyangData = this.uniqueZiList(yinyang.data);
			if(yinyang.cnt === 1){
				let res = {};
				res.cuang = this.getCuang(yinyangData[0]);
				res.name = '比用课';	
				return res;
			}else{
				return this.getSeHais(yinyangData);
			}
		}
		return null;
	}

	isJinKe1(){
		let flag = true;
		let stack = [];
		for(let i=0; i<4; i++){
			let ke = this.ke[i];
			flag = LRConst.isRestrain(ke[1], ke[2]);
			if(flag){
				stack.push(ke[1]);
			}
		}
		stack = this.uniqueZiList(stack);
		if(stack.length === 1){
			let res = {};
			res.cuang = this.getCuang(stack[0]);
			res.name = '元首课';
			return res;
		}else if(stack.length > 1){
			let gan = this.nongli.dayGanZi.substr(0, 1);
			let yinyang = LRConst.sameYingYang(gan, stack);
			const yinyangData = this.uniqueZiList(yinyang.data);
			if(yinyang.cnt === 1){
				let res = {};
				res.cuang = this.getCuang(yinyangData[0]);
				res.name = '知一课';	
				return res;
			}else{
				return this.getSeHais(yinyangData);
			}
		}
		return null;
	}

	isYaoKe0(){
		let flag = true;
		let stack = [];
		let gan = this.ke[0][2];
		for(let i=1; i<4; i++){
			let ke = this.ke[i];
			flag = LRConst.isRestrain(ke[1], gan);
			if(flag){
				stack.push(ke[1]);
			}
		}
		stack = this.uniqueZiList(stack);
		if(stack.length === 1){
			let res = {};
			res.cuang = this.getCuang(stack[0]);
			res.name = '蒿矢课';
			return res;
		}else if(stack.length > 1){
			let yinyang = LRConst.sameYingYang(gan, stack);
			const yinyangData = this.uniqueZiList(yinyang.data);
			if(yinyang.cnt === 1){
				let res = {};
				res.cuang = this.getCuang(yinyangData[0]);
				res.name = '蒿矢课';	
				return res;
			}else{
				return this.getSeHais(yinyangData);
			}
		}

		return null;
	}

	isYaoKe1(){
		let flag = true;
		let stack = [];
		let gan = this.ke[0][2];
		for(let i=1; i<4; i++){
			let ke = this.ke[i];
			flag = LRConst.isRestrain(gan, ke[1]);
			if(flag){
				stack.push(ke[1]);
			}
		}
		stack = this.uniqueZiList(stack);
		if(stack.length === 1){
			let res = {};
			res.cuang = this.getCuang(stack[0]);
			res.name = '弹射课';
			return res;
		}else if(stack.length > 1){
			let yinyang = LRConst.sameYingYang(gan, stack);
			const yinyangData = this.uniqueZiList(yinyang.data);
			if(yinyang.cnt === 1){
				let res = {};
				res.cuang = this.getCuang(yinyangData[0]);
				res.name = '弹射课';	
				return res;
			}else{
				return this.getSeHais(yinyangData);
			}
		}

		return null;
	}

	isMaoXing(){
		let gan = this.ke[0][2];
		let cuang0 = null; 
		let cuang1 = null; 
		let cuang2 = null;
		let res = {};
		if(LRConst.YangGan.indexOf(gan) >= 0){
			let idx = this.downZi.indexOf('酉');
			cuang0 = this.upZi[idx];
			cuang1 = this.ke[2][1];
			cuang2 = this.ke[0][1];
			res.name = '虎视课';
		}else{
			let idx = this.upZi.indexOf('酉');
			cuang0 = this.downZi[idx];
			cuang1 = this.ke[0][1];
			cuang2 = this.ke[2][1];
			res.name = '掩目课';
		}
		res.cuang = [cuang0, cuang1, cuang2];
		return res;
	}

	isFuYin(){
		if(this.downZi[0] !== this.upZi[0]){
			return null;
		}

		let res0 = this.isJinKe0();
		let res1 = this.isJinKe1();
		if(res0 || res1){
			let cuang0 = this.ke[0][1];
			let cuang1 = null;
			let cuang2 = null;
			let zixings = LRConst.ZiXing[cuang0];
			if(zixings === cuang0){
				cuang1 = this.ke[2][1];
			}else{
				cuang1 = zixings;
			}
			zixings = LRConst.ZiXing[cuang1];
			if(zixings === cuang1){
				cuang2 = LRConst.ZiCong[cuang1];
			}else{
				cuang2 = zixings;
			}
			let res = {};
			res.cuang = [cuang0, cuang1, cuang2];
			res.name = '不虞课';
			return res;
		}

		let gan = this.ke[0][2];
		if(LRConst.YangGan.indexOf(gan) >= 0){
			let cuang0 = this.ke[0][1];
			let cuang1 = null;
			let cuang2 = null;
			let zixings = LRConst.ZiXing[cuang0];
			if(zixings === cuang0){
				cuang1 = this.ke[2][1];
			}else{
				cuang1 = zixings;
			}
			zixings = LRConst.ZiXing[cuang1];
			if(zixings === cuang1){
				cuang2 = LRConst.ZiCong[cuang1];
			}else{
				cuang2 = zixings;
			}
			let res = {};
			res.cuang = [cuang0, cuang1, cuang2];
			res.name = '自任课';
			return res;
		}

		let cuang0 = this.ke[2][1];
		let cuang1 = null;
		let cuang2 = null;
		let zixings = LRConst.ZiXing[cuang0];
		if(zixings === cuang0){
			cuang1 = this.ke[0][1];
		}else{
			cuang1 = zixings;
		}
		zixings = LRConst.ZiXing[cuang1];
		if(zixings === cuang1){
			cuang2 = LRConst.ZiCong[cuang1];
		}else{
			cuang2 = zixings;
		}
		let res = {};
		res.cuang = [cuang0, cuang1, cuang2];
		res.name = '杜传课';
		return res;
	}

	isFangYin(){
		if(this.downZi[0] !== LRConst.ZiCong[this.upZi[0]]){
			return null;
		}

		let res = this.isJinKe0();
		if(res){
			res.name = '无依课';
			return res;
		}
		res = this.isJinKe1();
		if(res){
			res.name = '无依课';
			return res;
		}

		let dayzi = this.nongli.dayGanZi.substr(1);
		let cuang0 = LRConst.ZiYiMa[dayzi];
		let cuang1 = this.ke[2][1];
		let cuang2 = this.ke[0][1];
		res = {
			cuang: [cuang0, cuang1, cuang2],
			name: '无亲课'
		};
		return res;
	}

	isBieZe(){
		if(this.ke[0][1] === this.ke[1][1] || this.ke[0][1] === this.ke[3][1] ||
			this.ke[1][1] === this.ke[2][1] || this.ke[1][1] === this.ke[3][1] ||
			this.ke[2][1] === this.ke[3][1]){
			let res = this.isJinKe0();
			if(res){
				return res;
			}
			res = this.isJinKe1();
			if(res){
				return res;
			}
			res = this.isYaoKe0();
			if(res){
				return res;
			}
			res = this.isYaoKe1();
			if(res){
				return res;
			}
			let gan = this.ke[0][2];
			let dayzi = this.nongli.dayGanZi.substr(1);
			let cuang0 = null;
			if(LRConst.YangGan.indexOf(gan) >= 0){
				let hegan = LRConst.GanHe[gan];
				let hezi = LRConst.GanJiZi[hegan];
				let idx = this.downZi.indexOf(hezi);
				cuang0 = this.upZi[idx];
			}else{
				let sanghe = LRConst.ZiSangHe[dayzi];
				cuang0 = sanghe[1];
			}
			let cuang1 = this.ke[0][1];
			let cuang2 = this.ke[0][1];
			return {
				cuang: [cuang0, cuang1, cuang2],
				name: '芜淫课',
			}

		}
		return null;
	}

	isBaZhuang(){
		let ke1 = this.ke[0];
		let ke3 = this.ke[2];
		if(ke1[1] === ke3[1]){
			let res = this.isJinKe0();
			if(res){
				return res;
			}
			res = this.isJinKe1();
			if(res){
				return res;
			}
			let gan = ke1[2];
			let idx = 0;
			if(LRConst.YangGan.indexOf(gan) >= 0){
				idx = (this.upZi.indexOf(ke1[1]) + 2) % 12;
			}else{
				idx = (this.upZi.indexOf(this.ke[3][1]) + 10) % 12;
			}
			let cuang0 = this.upZi[idx];
			let cuang1 = ke1[1];
			let cuang2 = ke1[1];
			return {
				cuang: [cuang0, cuang1, cuang2],
				name: '八专课',
			}
		}
		return null;
	}

}

export default ChuangChart;
