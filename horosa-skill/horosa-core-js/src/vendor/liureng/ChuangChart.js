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

		// 涉害取舍流派(默认 app:仅下贼上方向数克·计起点不计本家;已固定)
		//   method: 'app'(默认) | 'standard'(深浅两向:贼数被克/克数主克) | 'mengzhongji'(直取孟仲季,不数克)
		//   boundary: 'app'(计起点不计本家·默认) | 'both'(两端皆计) | 'neither'(皆不计)
		//   shiRuKe: true → 单一下贼上发用单列「始入课」(并入重审=false 默认)
		this.seHaiOpts = option.seHaiOpts || {};

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
		// 发三传九法的判定顺序(课经条文口径,#46 修正)：
		// 伏吟/返吟(盘体) → 贼克(贼/摄) → [比用/涉害,见 isJinKe*] → 八专 → 遥克 → 别责 → 昴星。
		// 关键点：
		//  · 八专(干支同位,四课止两课)必须在遥克之前——课经明训:八专「有克照常以克贼比涉论,
		//    如无克贼比涉,不复取遥克」;「遥者远也」,干支同处一位无远可言,故两课无克径入八专。
		//    🔴 历史教训(#46):曾把古籍「九法」章的列举序号(遥克第4/八专第9)误读为判定
		//    优先级,将八专下移到遥克之后并用金标锁死,致甲寅日戌将丑/午时等两课无近克而带遥克
		//    的课式被误发蒿矢/弹射。列举序≠判定序;判定序只认「八专不取遥、别责须无遥」等条文本身。
		//  · 遥克在别责/昴星之前——三课备(别责)与四课全(昴星)须先问遥克,课经「无遥无克别责例」。
		//  · 八专须在别责之前——八专(一课=三课)会令二课=四课,从而满足 isBieZe 的
		//    "某两课相同",若先判别责会被误吞,故八专优先于别责。
		//  · 昴星(isMaoXing)是无克无遥且四课俱全的兜底(总会返回),必须最后判。
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

		cuang = this.isBaZhuang();
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

	getSeHais(cuangs, mode){
		const ziList = this.uniqueZiList(cuangs || []);
		if(ziList.length === 0){
			return null;
		}
		const method = (this.seHaiOpts && this.seHaiOpts.method) || 'app';
		let stack = [];
		if(method === 'mengzhongji'){
			// 直取孟仲季法(陈公献/邵彦和古案):不数克,全部候选直接进孟仲季裁决
			stack = ziList.slice(0);
		}else{
			let maxcuang = 0;
			for(let i=0; i<ziList.length; i++){
				let cnt = this.getSeHaiCount(ziList[i], mode);
				if(cnt > maxcuang){
					maxcuang = cnt;
					stack = [];
					stack.push(ziList[i]);
				}else if(cnt === maxcuang){
					stack.push(ziList[i]);
				}
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

	getSeHaiCount(cuang, mode){
		const method = (this.seHaiOpts && this.seHaiOpts.method) || 'app';
		const boundary = (this.seHaiOpts && this.seHaiOpts.boundary) || 'app';
		// 主克方向仅在「标准深浅两向」且候选来自上克下(mode==='克')时启用;否则恒数「被克」(=标准之贼)
		const zhuKe = method === 'standard' && mode === '克';
		let cnt = 0;
		let seat = this.upZi.indexOf(cuang);      // 起点:候选天盘支所临地盘宫
		let home = this.downZi.indexOf(cuang);    // 本家:候选地支本宫
		if(home < seat){ home += 12; }
		// 默认 app=[seat, home):含起点、不含本家(已固定);both=[seat,home];neither=(seat,home)
		const lo = boundary === 'neither' ? seat + 1 : seat;
		const hi = boundary === 'both' ? home + 1 : home;
		for(let i=lo; i<hi; i++){
			let zi = this.downZi[i % 12];
			if(zhuKe ? LRConst.isRestrain(cuang, zi) : LRConst.isRestrain(zi, cuang)){
				cnt = cnt + 1;
			}
			let gan = LRConst.ZiHanGan[zi];
			if(gan){
				let ganary = gan.split('');
				for(let j=0; j<ganary.length; j++){
					if(zhuKe ? LRConst.isRestrain(cuang, ganary[j]) : LRConst.isRestrain(ganary[j], cuang)){
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
			// 始入课:单一下贼上,开关启则单列(九法变十法),默认并入重审
			res.name = (this.seHaiOpts && this.seHaiOpts.shiRuKe) ? '始入课' : '重审课';
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
				return this.getSeHais(yinyangData, '贼');
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
				return this.getSeHais(yinyangData, '克');
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

	// 伏吟末传通则:中传所刑为末;中传自刑(辰午酉亥)取中传所冲。
	// #62 勘正:初中两传恰为子卯互刑(刑表唯一二环,刑还初传、传行杜塞)时,
	// 末传亦取中传所冲——丁卯/己卯/辛卯日伏吟由「卯子卯」勘正为「卯子午」(全域仅此 3/720 课变)。
	// 仅此子卯一对特判(用户定谳,明令不作更泛抽象);其余刑链(寅巳申/丑戌未)三支各异,不在此列。
	getFuYinLastCuang(cuang0, cuang1){
		let zixings = LRConst.ZiXing[cuang1];
		if(zixings === cuang1){
			return LRConst.ZiCong[cuang1];
		}
		if((cuang0 === '子' && cuang1 === '卯') || (cuang0 === '卯' && cuang1 === '子')){
			return LRConst.ZiCong[cuang1];
		}
		return zixings;
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
			cuang2 = this.getFuYinLastCuang(cuang0, cuang1);
			let res = {};
			res.cuang = [cuang0, cuang1, cuang2];
			res.name = '不虞课';
			return res;
		}

		// 伏吟无克四格名(课经口径,2026-07-04 词汇增强):刚日=自任/柔日=自信;
		// 初传自刑(转取三课/一课上神)= 杜传;有克=不虞(上方分支,不变)。三传内容零变更。
		let gan = this.ke[0][2];
		if(LRConst.YangGan.indexOf(gan) >= 0){
			let cuang0 = this.ke[0][1];
			let cuang1 = null;
			let cuang2 = null;
			let selfXing = false;
			let zixings = LRConst.ZiXing[cuang0];
			if(zixings === cuang0){
				cuang1 = this.ke[2][1];
				selfXing = true;
			}else{
				cuang1 = zixings;
			}
			cuang2 = this.getFuYinLastCuang(cuang0, cuang1);
			let res = {};
			res.cuang = [cuang0, cuang1, cuang2];
			res.name = selfXing ? '杜传课' : '自任课';
			return res;
		}

		let cuang0 = this.ke[2][1];
		let cuang1 = null;
		let cuang2 = null;
		let selfXing = false;
		let zixings = LRConst.ZiXing[cuang0];
		if(zixings === cuang0){
			cuang1 = this.ke[0][1];
			selfXing = true;
		}else{
			cuang1 = zixings;
		}
		cuang2 = this.getFuYinLastCuang(cuang0, cuang1);
		let res = {};
		res.cuang = [cuang0, cuang1, cuang2];
		res.name = selfXing ? '杜传课' : '自信课';
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
			// 别责两名(2026-07-04 词汇增强):刚日=不备/柔日=芜淫;三传内容零变更。
			return {
				cuang: [cuang0, cuang1, cuang2],
				name: LRConst.YangGan.indexOf(gan) >= 0 ? '不备课' : '芜淫课',
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
