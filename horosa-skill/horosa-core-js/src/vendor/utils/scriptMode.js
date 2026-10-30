// 界面简繁(全局显示层):设置 → 「切换繁体 / 切换简体」。
//
// 只改「看到的字」,不改任何数据:
//   · 页面上的文字节点与少数显示属性(title / placeholder / aria-label / alt / 按钮 value)在渲染后就地转繁体,
//     原文逐节点记住;切回简体 = 把记住的原文放回去(不做繁转简,繁转简一对多、回不准)。
//   · 存储、复制、发给 AI 的内容全部来自数据层(简体原文),不经过这里。
//   · 导出 / 截图(html2canvas / html-to-image 一类)一律经 withOriginalScript:期间暂停转换、canvas 补丁旁路,
//     导出内容永远是简体原文(护栏 scriptModeExportGuard.test.js)。
//   · 少数从页面读字做判断的地方(AI 导出按页签名认技法 / 子页)经 readOriginalText 读原文,繁体下判断不变。
//   · 搜索(下拉搜索 / 斜杠命令 / 报告内搜索)经 matchesUserQuery / scriptMatchIndex / scriptTextEquals 比对(算法在
//     scriptConvert/scriptMatch.js,逐位对齐的纯函数):照屏幕输入的繁体、直接输入的简体都能搜到简体数据。
//   · 不碰:输入框 / 多行输入的值、可编辑区、代码块(pre)、<script>/<style>(含 SVG 里的),以及标了 .horosa-script-keep 的子树。
//   · 画在 canvas 上的字(风水罗盘 / 天文馆 / 3D 标签)在绘制时转换;宿主经 subscribeScriptMode 在切换后重画。
//   · 逐字出图(一个字一个节点)的地方给节点标 data-hant-word(整词)+ data-hant-idx(位次),按整词转再取那一位
//     (「天后」逐字画仍是「天后」,缩写「后」带全称「天后」)。d3 逐字画字只走 GraphHelper.appendPerCharText
//     (静态守卫 perCharTextHelper.test.js);React 里单字成节点的(奇门九星 / 八门、天将缩写)展开 scriptWordAttrs(全名, 位次)。
// 设置存 localStorage「horosa.ui.script」(hans / hant,登记在 storageKeyRegistry,随备份);
// 开机回放:global.js 首帧前 prebootScriptMode(繁体先遮住页面、提前加载转换器),layouts/app.js 再 bootScriptMode。
import { safeLocalStorageSet } from '../gua/safeStorage.js';
import {
	matchAcrossScripts, indexAcrossScripts, equalsAcrossScripts, queryVariantsAcrossScripts,
} from './scriptConvert/scriptMatch.js';
import { spanAcrossScripts, mapUnitIndexBetween } from './scriptConvert/scriptMatch.js';

export const SCRIPT_HANS = 'hans';
export const SCRIPT_HANT = 'hant';
export const SCRIPT_LS_KEY = 'horosa.ui.script';
export const SCRIPT_APPLIED_EVENT = 'horosa:script-applied';
export const SCRIPT_KEEP_CLASS = 'horosa-script-keep';
export const SCRIPT_WORD_ATTR = 'data-hant-word';
export const SCRIPT_IDX_ATTR = 'data-hant-idx';

// 逐字出图时第 idx 位的整词定字属性(界面简繁按整词转换再取该位:「天后」逐字画仍是「天后」,不成「天後」)。
// word:整词;ch:这一位实际画的字(给了就要与整词该位相同才挂);整词不足两字 / 越位 / 对不上 → 空对象。
// d3 路径经 GraphHelper.appendPerCharText,JSX 路径 <text {...perCharTextProps(词, i, 字)}>,两者同一判据;
// 单字缩写(只画全称里的一个字)仍用下面的 scriptWordAttrs(全称, 位次)。
export function perCharTextProps(word, idx, ch){
	const chars = word === undefined || word === null ? [] : Array.from(`${word}`);
	const i = Number(idx);
	if(chars.length < 2 || !Number.isInteger(i) || i < 0 || i >= chars.length){ return {}; }
	if(ch !== undefined && ch !== null && `${ch}` !== chars[i]){ return {}; }
	return scriptWordAttrs(chars.join(''), i);   // 与单字缩写标全称同一份属性写法
}

const TEXT_ATTRS = ['title', 'placeholder', 'aria-label', 'alt'];
const VALUE_INPUT_TYPES = { button: 1, submit: 1, reset: 1 };
// 选择器里的类型名对 SVG 元素也按小写本地名匹配;可编辑区 = 带 contenteditable 且不是 "false"(含 plaintext-only);
// 富文本编辑面(.ql-editor)无论只读与否都按原样(它的内容是数据,编辑器会从页面读回去)。
// 文字跳过:以上全部 + 多行输入框(它的文字节点就是值);显示属性跳过:不含多行输入框 —— 占位符 / 提示照转,与单行输入框一致。
const EDIT_SURFACE = `[contenteditable]:not([contenteditable="false"]),.ql-editor`;
const SKIP_SELECTOR = `script,style,noscript,textarea,pre,${EDIT_SURFACE},.${SCRIPT_KEEP_CLASS}`;
const SKIP_ATTR_SELECTOR = `script,style,noscript,pre,${EDIT_SURFACE},.${SCRIPT_KEEP_CLASS}`;
const SKIP_LOCAL_NAMES = { script: 1, style: 1, noscript: 1, textarea: 1, pre: 1 };
// 开机为繁体时,转换器到位前先遮住页面(免得先闪一下简体);最多遮这么久,到点无论如何放开。
const PENDING_ATTR = 'data-horosa-script-pending';
const PENDING_MAX_MS = 2500;

export function normalizeScriptMode(mode){
	return mode === SCRIPT_HANT ? SCRIPT_HANT : SCRIPT_HANS;
}

export function getStoredScriptMode(){
	try{
		if(typeof window === 'undefined' || !window.localStorage){ return SCRIPT_HANS; }
		return normalizeScriptMode(window.localStorage.getItem(SCRIPT_LS_KEY));
	}catch(_){ return SCRIPT_HANS; }
}

// ── 运行态 ────────────────────────────────────────────────────────────────────────────
let convert = null;          // 已加载的 toHant
let matchKeyFn = null;       // 已加载的 toMatchKey(繁体折回简体写法)
let matchConv = null;        // 检索比对用的转换器对象(scriptConvert/scriptMatch 的 conv;即转换器模块本身)
let loading = null;          // 加载中的 Promise
let active = false;          // 页面当前是否处于繁体
let wanted = SCRIPT_HANS;    // 最近一次请求的模式(加载期间来回切,以最后一次为准)
let observer = null;
let textRec = new WeakMap(); // 文字节点 → { orig, conv }
let attrRec = new WeakMap(); // 元素 → { 属性名: { orig, conv } }
// 自己写出去的改动会回来一条变动记录:逐节点记下待回的条数,回来时认领跳过(不把它当成框架的新原文)
let selfText = new WeakMap();
let selfAttr = new WeakMap();
let canvasOrig = null;
let pauseDepth = 0;          // withOriginalScript 嵌套深度(> 0:不挂在页面上的 canvas 不转换)
const holds = new Set();     // 进行中的 withOriginalScript(切换简繁时一并结束)
let holdBypassed = false;    // 暂停期间有不挂在页面上的 canvas 按原文画过(可能是 3D 标签纹理):结束后请订阅方重画
let holdActivity = 0;        // 暂停期间导出画布旁路画字的次数:看门狗据此判「还在干活」(在跑的长导出不被到点打断)
// 不挂在页面上的画布分两类:页面自己的离屏画布(图表库量宽用的那张、3D 标签纹理)在暂停之外也画字;导出新建的画布
// (html2canvas / html-to-image / 合成图)只在暂停期间画。暂停之外画过字的记为「页面的」:暂停期间照常转换、
// 不给看门狗续期 —— 否则页面上任何一次量字都给卡死的导出续一段,繁体界面一直解不开;导出期间图表量宽也会量成简体宽度
let pageOwnedCanvas = new WeakMap();
let rootLangOrig;            // <html lang> 的原始状态(undefined = 尚未记录;null = 原本没有)
const extraDocs = new Set(); // 同源 iframe 的文档(attachScriptDocument 挂进来,与主文档同一套转换)
const OBSERVE_OPTS = {
	childList: true, subtree: true, characterData: true,
	attributes: true, attributeFilter: TEXT_ATTRS.concat(['value', 'contenteditable']),
};

export function currentScriptMode(){
	return active ? SCRIPT_HANT : SCRIPT_HANS;
}

export function isHantActive(){
	return active;
}

// 交给网页之外去画的文字(系统通知横幅、原生窗口标题这类壳侧原生界面;显示层的 DOM / canvas 转换够不着)按当前档转:
// 繁体档且转换器已到位 → 转繁体,否则原样。只给「显示」用:存储、导出、发给 AI 的内容不经这里(数据层永远简体)。
export function toDisplayScript(text){
	const s = text === undefined || text === null ? '' : `${text}`;
	if(!active || !convert || !s){ return s; }
	try{ return convert(s); }catch(_){ return s; }
}

const importConverter = ()=>import(/* webpackChunkName: "script-hant" */ './scriptConvert/hantConverter.js');
let converterLoader = importConverter;

// 远端检索(库里简繁混存)不论界面简繁都要带上其它写法:先按需加载转换器(加载失败回 false,调用方照常只发原词)
export function ensureScriptConverter(){
	return loadConverter().then(()=>true, ()=>false);
}

function loadConverter(){
	if(convert){ return Promise.resolve(convert); }
	if(!loading){
		loading = converterLoader()
			.then((m)=>{
				convert = (m && (m.toHant || m.default)) || null;
				matchKeyFn = (m && typeof m.toMatchKey === 'function') ? m.toMatchKey : null;
				matchConv = convert ? { ...m, toHant: convert } : null;
				return convert;
			})
			.catch((e)=>{ loading = null; throw e; });
	}
	return loading;
}

function skippedElement(el){
	if(!el || el.nodeType !== 1){ return false; }
	try{ return !!el.closest(SKIP_SELECTOR); }catch(_){ return false; }
}

// 显示属性是否跳过(多行输入框的占位符照转;它里面的值不转)
function attrsSkipped(el){
	if(!el || el.nodeType !== 1){ return false; }
	try{ return !!el.closest(SKIP_ATTR_SELECTOR); }catch(_){ return false; }
}

function isEditable(n){
	const ce = n.getAttribute('contenteditable');
	return ce !== null && `${ce}`.toLowerCase() !== 'false';
}

function isEditSurface(n){
	return isEditable(n) || !!(n.classList && n.classList.contains('ql-editor'));
}

// 逐字出图:父元素带整词与位次 → 按整词转,取对应那几位(转换逐码点等长)
function convertInContext(node, v){
	const p = node.parentElement;
	if(p && p.hasAttribute(SCRIPT_WORD_ATTR)){
		const word = Array.from(p.getAttribute(SCRIPT_WORD_ATTR) || '');
		const idx = parseInt(p.getAttribute(SCRIPT_IDX_ATTR), 10);
		const part = Array.from(v);
		if(idx >= 0 && word.slice(idx, idx + part.length).join('') === v){
			const cw = Array.from(convert(word.join('')));
			if(cw.length === word.length){ return cw.slice(idx, idx + part.length).join(''); }
		}
	}
	return convert(v);
}

// 处理一批记录期间自己写出的改动,其记录要到下一批才回来:先记在 deferred,这批处理完再入账
// (否则同一批里后面那条框架写来的记录会被误认领)
let deferred = null;
function noteSelfText(node){
	if(deferred){ deferred.push([node, null]); return; }
	selfText.set(node, (selfText.get(node) || 0) + 1);
}
function noteSelfAttr(el, name){
	if(deferred){ deferred.push([el, name]); return; }
	let m = selfAttr.get(el);
	if(!m){ m = {}; selfAttr.set(el, m); }
	m[name] = (m[name] || 0) + 1;
}

function writeText(node, val){
	if(observer){ noteSelfText(node); }
	node.nodeValue = val;
}

function writeAttr(el, name, val){
	if(observer){ noteSelfAttr(el, name); }
	el.setAttribute(name, val);
}

function claimSelfText(node){
	const n = selfText.get(node);
	if(!n){ return false; }
	if(n <= 1){ selfText.delete(node); }else{ selfText.set(node, n - 1); }
	return true;
}

function claimSelfAttr(el, name){
	const m = selfAttr.get(el);
	if(!m || !m[name]){ return false; }
	m[name] -= 1;
	return true;
}

// fresh = 这是框架写来的新值(即使恰好等于上次转出的结果,也当新原文)
function convertTextNode(node, fresh){
	const v = node.nodeValue;
	if(!v){ return; }
	const rec = textRec.get(node);
	if(!fresh && rec && v === rec.conv){ return; }
	const conv = convertInContext(node, v);
	if(conv === v){
		if(rec){ textRec.delete(node); }
		return;
	}
	textRec.set(node, { orig: v, conv });
	writeText(node, conv);
}

function convertAttr(el, name, fresh){
	const v = el.getAttribute(name);
	let map = attrRec.get(el);
	const rec = map ? map[name] : null;
	if(v === null || v === undefined || v === ''){
		if(rec){ delete map[name]; }
		return;
	}
	if(!fresh && rec && v === rec.conv){ return; }
	const conv = convert(v);
	if(conv === v){
		if(rec){ delete map[name]; }
		return;
	}
	if(!map){ map = {}; attrRec.set(el, map); }
	map[name] = { orig: v, conv };
	writeAttr(el, name, conv);
}

function convertElementAttrs(el){
	for(let i = 0; i < TEXT_ATTRS.length; i += 1){
		if(el.hasAttribute(TEXT_ATTRS[i])){ convertAttr(el, TEXT_ATTRS[i]); }
	}
	if(el.tagName === 'INPUT' && VALUE_INPUT_TYPES[`${el.type}`.toLowerCase()] && el.hasAttribute('value')){
		convertAttr(el, 'value');
	}
}

// 子树:文字节点 + 元素显示属性;跳过不该碰的子树(整棵不进)
function convertSubtree(root){
	if(!root){ return; }
	if(root.nodeType === 3){
		if(!skippedElement(root.parentElement)){ convertTextNode(root); }
		return;
	}
	if(root.nodeType !== 1 && root.nodeType !== 9 && root.nodeType !== 11){ return; }
	if(root.nodeType === 1 && skippedElement(root)){
		if(`${root.localName || ''}`.toLowerCase() === 'textarea' && !attrsSkipped(root)){ convertElementAttrs(root); }
		return;
	}
	const doc = root.ownerDocument || root;
	const walker = doc.createTreeWalker(root, 1 | 4, {
		acceptNode(n){
			if(n.nodeType === 1){
				const ln = `${n.localName || ''}`.toLowerCase();
				if(SKIP_LOCAL_NAMES[ln]){
					if(ln === 'textarea'){ convertElementAttrs(n); }   // 多行输入框:占位符 / 提示照转,值(文字节点)不进
					return 2;                                          // REJECT:整棵子树不进
				}
				if(isEditSurface(n)){ return 2; }
				if(n.classList && n.classList.contains(SCRIPT_KEEP_CLASS)){ return 2; }
			}
			return 1;
		},
	});
	if(root.nodeType === 1){ convertElementAttrs(root); }
	let n = walker.nextNode();
	while(n){
		if(n.nodeType === 3){ convertTextNode(n); }
		else{ convertElementAttrs(n); }
		n = walker.nextNode();
	}
}

function handleRecords(records){
	if(!active || !convert){ return; }
	const outer = deferred === null;
	if(outer){ deferred = []; }
	try{
		handleBatch(records);
	}finally{
		if(outer){
			const list = deferred;
			deferred = null;
			if(observer){ list.forEach(([n, name])=>{ if(name === null){ noteSelfText(n); }else{ noteSelfAttr(n, name); } }); }
		}
	}
}

function handleBatch(records){
	const doneText = new Set();     // 同一批里同一节点只按它此刻的值处理一次
	for(let i = 0; i < records.length; i += 1){
		const r = records[i];
		if(!inManagedDoc(r.target)){ continue; }
		if(r.type === 'characterData'){
			const t = r.target;
			if(!t || claimSelfText(t) || doneText.has(t)){ continue; }
			if(t.parentElement && !skippedElement(t.parentElement)){ doneText.add(t); convertTextNode(t, true); }
		}else if(r.type === 'childList'){
			const added = r.addedNodes;
			for(let k = 0; k < added.length; k += 1){
				const node = added[k];
				if(node.nodeType === 3){
					if(!doneText.has(node) && node.parentElement && !skippedElement(node.parentElement)){ doneText.add(node); convertTextNode(node); }
				}else if(node.nodeType === 1){
					convertSubtree(node);   // 跳过的子树在里面判(多行输入框只转占位符)
				}
			}
		}else if(r.type === 'attributes'){
			const el = r.target;
			const name = r.attributeName;
			if(!el || el.nodeType !== 1 || claimSelfAttr(el, name)){ continue; }
			if(name === 'contenteditable'){
				// 可编辑性是动态的(富文本由只读改成可编辑):变成可编辑区 → 放回原文、不再管它(编辑器会从页面读回去当数据);
				// 由可编辑改回不可编辑 → 当新内容转换
				if(isEditable(el)){ releaseSubtree(el); }
				else if(!skippedElement(el)){ convertSubtree(el); }
				continue;
			}
			if(!attrsSkipped(el)){
				if(name === 'value'){
					if(el.tagName === 'INPUT' && VALUE_INPUT_TYPES[`${el.type}`.toLowerCase()]){ convertAttr(el, 'value', true); }
				}else{
					convertAttr(el, name, true);
				}
			}
		}
	}
}

function startObserver(){
	if(observer || typeof MutationObserver === 'undefined' || typeof document === 'undefined'){ return; }
	observer = new MutationObserver(handleRecords);
	observer.observe(document.documentElement, OBSERVE_OPTS);
	extraDocs.forEach((d)=>{ try{ observer.observe(d.documentElement, OBSERVE_OPTS); }catch(_){ /* 文档已卸载 */ } });
}

// 记录是否属于在管的文档(主文档或已挂的同源 iframe;摘掉的 iframe 之后的变动不再处理)
function inManagedDoc(node){
	const d = node && node.ownerDocument;
	return !d || d === document || extraDocs.has(d);
}

function stopObserver(){
	if(!observer){ return; }
	try{ observer.disconnect(); }catch(_){ /* noop */ }
	observer = null;
	selfText = new WeakMap();
	selfAttr = new WeakMap();
}

// 把 root 子树里记住的原文放回去;回放回的 [节点, 记录] 清单(供之后换回)
function swapToOriginal(root, swapped){
	const doc = root.ownerDocument || root;
	const visit = (n)=>{
		if(n.nodeType === 3){
			const rec = textRec.get(n);
			if(rec && n.nodeValue === rec.conv){ writeText(n, rec.orig); swapped.push([n, null, rec]); }
		}else if(n.nodeType === 1){
			const map = attrRec.get(n);
			if(map){
				Object.keys(map).forEach((name)=>{
					if(n.getAttribute(name) === map[name].conv){ writeAttr(n, name, map[name].orig); swapped.push([n, name, map[name]]); }
				});
			}
		}
	};
	if(root.nodeType === 3){ visit(root); return swapped; }
	if(root.nodeType === 1){ visit(root); }
	const walker = doc.createTreeWalker(root, 1 | 4);
	let n = walker.nextNode();
	while(n){ visit(n); n = walker.nextNode(); }
	return swapped;
}

// 子树变成可编辑区:记住的原文放回去并忘掉记录(之后观察者不再进这棵子树)
function releaseSubtree(root){
	const back = swapToOriginal(root, []);
	back.forEach(([n, name])=>{
		if(name === null){ textRec.delete(n); }
		else{ const m = attrRec.get(n); if(m){ delete m[name]; } }
	});
	const doc = root.ownerDocument || root;
	const walker = doc.createTreeWalker(root, 1 | 4);
	let n = root;
	while(n){
		if(n.nodeType === 3){ textRec.delete(n); }else{ attrRec.delete(n); }
		n = walker.nextNode();
	}
}

// 把整页记住的原文放回去(切回简体)
function restoreAll(){
	if(typeof document === 'undefined'){ return; }
	swapToOriginal(document.documentElement, []);
	extraDocs.forEach((d)=>{ try{ swapToOriginal(d.documentElement, []); }catch(_){ /* 文档已卸载 */ } });
	textRec = new WeakMap();
	attrRec = new WeakMap();
}

// 画布是否挂在页面上(导出用的画布都是新建、不挂文档的;OffscreenCanvas 没有 isConnected = 不挂)
function canvasOnPage(ctx){
	const c = ctx && ctx.canvas;
	return !!(c && c.isConnected === true);
}

// canvas 上画的字:绘制 / 量宽时转繁体(量宽与绘制同一份字,版面不变)。
// withOriginalScript 期间只旁路不挂在页面上的画布(html2canvas / html-to-image / 导出合成图都是这种);
// 页面上的画布(天文馆 / 罗盘 / echarts)照常转换 —— 此前全局暂停,导出那几秒里重画的页面画布画成简体、一直不回来。
function patchCanvas(){
	if(canvasOrig || typeof window === 'undefined' || !window.CanvasRenderingContext2D){ return; }
	const proto = window.CanvasRenderingContext2D.prototype;
	canvasOrig = { fillText: proto.fillText, strokeText: proto.strokeText, measureText: proto.measureText };
	const wrap = (fn)=>function wrapped(text, ...rest){
		if(active && convert && typeof text === 'string'){
			if(!canvasOnPage(this)){
				const key = (this && this.canvas) || this;
				if(pauseDepth === 0){
					if(key && typeof key === 'object' && !pageOwnedCanvas.has(key)){ pageOwnedCanvas.set(key, true); }
				}else if(!(key && typeof key === 'object' && pageOwnedCanvas.has(key))){
					holdBypassed = true;
					holdActivity += 1;
					return fn.call(this, text, ...rest);
				}
			}
			return fn.call(this, convert(text), ...rest);
		}
		return fn.call(this, text, ...rest);
	};
	proto.fillText = wrap(canvasOrig.fillText);
	proto.strokeText = wrap(canvasOrig.strokeText);
	proto.measureText = wrap(canvasOrig.measureText);
}

function unpatchCanvas(){
	if(!canvasOrig || typeof window === 'undefined' || !window.CanvasRenderingContext2D){ return; }
	const proto = window.CanvasRenderingContext2D.prototype;
	proto.fillText = canvasOrig.fillText;
	proto.strokeText = canvasOrig.strokeText;
	proto.measureText = canvasOrig.measureText;
	canvasOrig = null;
}

// 根属性:data-horosa-script 标当前档;lang 只在繁体时写 zh-Hant,简体档恢复模板原状(原本没有就去掉)
function setRootAttrs(mode){
	if(typeof document === 'undefined' || !document.documentElement){ return; }
	const root = document.documentElement;
	root.setAttribute('data-horosa-script', mode);
	if(mode === SCRIPT_HANT){
		if(rootLangOrig === undefined){ rootLangOrig = root.getAttribute('lang'); }
		root.setAttribute('lang', 'zh-Hant');
	}else if(rootLangOrig !== undefined){
		if(rootLangOrig === null){ root.removeAttribute('lang'); }else{ root.setAttribute('lang', rootLangOrig); }
		rootLangOrig = undefined;
	}
}

function setPending(){
	const root = document.documentElement;
	if(root.hasAttribute(PENDING_ATTR)){ return; }
	root.setAttribute(PENDING_ATTR, '1');
	root.style.visibility = 'hidden';
	setTimeout(clearPending, PENDING_MAX_MS);
}

function clearPending(){
	if(typeof document === 'undefined' || !document.documentElement){ return; }
	const root = document.documentElement;
	if(root.hasAttribute(PENDING_ATTR)){
		root.removeAttribute(PENDING_ATTR);
		root.style.visibility = '';
	}
}

function broadcast(mode, extra){
	try{
		if(typeof window !== 'undefined' && typeof window.dispatchEvent === 'function' && typeof CustomEvent === 'function'){
			window.dispatchEvent(new CustomEvent(SCRIPT_APPLIED_EVENT, { detail: { mode, ...(extra || {}) } }));
		}
	}catch(_){ /* noop */ }
}

// 结束全部进行中的 withOriginalScript(切换简繁时):暂停计数归零、去掉 keep 类;接着由切换本身整页转换 / 还原
function releaseAllHolds(){
	Array.from(holds).forEach((h)=>{ try{ h.release(false); }catch(_){ /* noop */ } });
	holds.clear();
	pauseDepth = 0;
	holdBypassed = false;
}

function enableNow(){
	releaseAllHolds();
	if(active){ return; }
	active = true;
	patchCanvas();
	convertSubtree(document.documentElement);
	extraDocs.forEach((d)=>{ try{ convertSubtree(d.documentElement); }catch(_){ /* 文档已卸载 */ } });
	startObserver();
	setRootAttrs(SCRIPT_HANT);
	broadcast(SCRIPT_HANT);
}

function disableNow(){
	releaseAllHolds();
	if(!active){ setRootAttrs(SCRIPT_HANS); return; }
	stopObserver();
	active = false;
	restoreAll();
	unpatchCanvas();
	setRootAttrs(SCRIPT_HANS);
	broadcast(SCRIPT_HANS);
}

// 应用模式(不写存储);回 Promise<实际模式>。转换器加载失败 → 留在简体,不遮页面,并广播实际模式(菜单文字跟着对)。
export function applyScriptMode(mode, { boot = false } = {}){
	const want = normalizeScriptMode(mode);
	wanted = want;
	if(typeof document === 'undefined' || !document.documentElement){ return Promise.resolve(SCRIPT_HANS); }
	if(want === SCRIPT_HANS){
		clearPending();
		disableNow();
		return Promise.resolve(SCRIPT_HANS);
	}
	if(convert){
		enableNow();
		clearPending();
		return Promise.resolve(SCRIPT_HANT);
	}
	if(boot){ setPending(); }
	return loadConverter().then(()=>{
		if(wanted === SCRIPT_HANT && convert){ enableNow(); }
		clearPending();
		return currentScriptMode();
	}).catch(()=>{
		clearPending();
		const actual = currentScriptMode();
		broadcast(actual, { failed: true });
		return actual;
	});
}

// 用户切换:应用 + 写存储(只在真正生效后写,失败不留下「设了却没变」的存档)。
// 回 Promise<{ mode: 实际模式, persisted: 是否写进了存储 }>;没写进去 = 这次生效、下次开机会回到原样(调用方要提示)。
export function setScriptMode(mode){
	return applyScriptMode(mode).then((actual)=>{
		const persisted = safeLocalStorageSet(SCRIPT_LS_KEY, actual) === true;
		return { mode: actual, persisted };
	});
}

export function toggleScriptMode(){
	return setScriptMode(active ? SCRIPT_HANS : SCRIPT_HANT);
}

// 首帧前(global.js 里同步调用):存的是繁体就先遮住页面、提前加载转换器;bootScriptMode 再接手。
export function prebootScriptMode(){
	if(typeof window === 'undefined' || typeof document === 'undefined' || !document.documentElement){ return; }
	if(getStoredScriptMode() !== SCRIPT_HANT){ return; }
	setPending();
	loadConverter().catch(()=>{ clearPending(); });
}

// 开机回放 + 跟随别的窗口改了设置(同源多窗口共用 localStorage;别处整个清空存储 = 复位到简体)
let bootDone = false;
export function bootScriptMode(){
	if(bootDone || typeof window === 'undefined'){ return; }
	bootDone = true;
	const stored = getStoredScriptMode();
	if(stored === SCRIPT_HANT){ applyScriptMode(SCRIPT_HANT, { boot: true }); }
	else{ setRootAttrs(SCRIPT_HANS); }
	try{
		window.addEventListener('storage', (e)=>{
			if(!e){ return; }
			if(e.key === SCRIPT_LS_KEY){ applyScriptMode(normalizeScriptMode(e.newValue)); }
			else if(e.key === null){ applyScriptMode(SCRIPT_HANS); }
		});
	}catch(_){ /* noop */ }
}

// 从页面读字做判断的地方用它:繁体下先把 root 子树里的原文临时放回,读完再换回繁体。
// read(root) 必须同步。读期间被换回的节点产生的变动记录随后照常处理(自产记录认领跳过),不丢别的真实变动。
export function readOriginalText(root, read){
	if(!active || !root || typeof root !== 'object' || typeof document === 'undefined'){ return read(root); }
	const swapped = [];
	try{
		if(root.nodeType === 3 || root.nodeType === 1 || root.nodeType === 9 || root.nodeType === 11){
			swapToOriginal(root, swapped);
		}
		return read(root);
	}finally{
		swapBack(swapped);
		if(observer){ handleRecords(observer.takeRecords()); }
	}
}

// 文字节点的简体原文(只读,不动 DOM):繁体期间被转换过的节点回记住的原文,其余回节点当前文字。
// 逐节点扫页面字做检索 / 高亮一类用它;要整棵子树的原文用 readOriginalText。
// 转换逐码点等长、UTF-16 不一定等长(扩展区字),原文上的下标落回节点要经 scriptNodeOffset 换算,不能直接用。
export function scriptOriginalNodeText(node){
	if(!node || node.nodeType !== 3){ return ''; }
	const v = node.nodeValue || '';
	const rec = active ? textRec.get(node) : null;
	return rec && v === rec.conv ? rec.orig : v;
}

// 原文(scriptOriginalNodeText 给的那份)上的 UTF-16 下标 → 节点当前文字上同一码点的下标(Range.setStart / setEnd 用);
// 截到节点文字长度以内,永不越界
export function scriptNodeOffset(node, origIndex){
	if(!node || node.nodeType !== 3){ return 0; }
	const cur = node.nodeValue || '';
	return mapUnitIndexBetween(scriptOriginalNodeText(node), cur, origIndex);
}

// 命中位置与长度 { index, length }(hay 的 UTF-16 量;无命中 index = -1)。与 scriptMatchIndex 同一方案(matchPlan,含放宽一档),
// 另给命中在 hay 上占的长度(扩展区字使它不一定等于 query.length):高亮与「找下一处」用它
export function scriptMatchSpan(hay, query, { ci = true, from = 0, anyScript = false } = {}){
	const q = query === undefined || query === null ? '' : `${query}`;
	const h = hay === undefined || hay === null ? '' : `${hay}`;
	const plan = matchPlan(anyScript);
	if(!plan){
		if(!q){ return { index: 0, length: 0 }; }
		const i = ci ? h.toLowerCase().indexOf(q.toLowerCase(), from) : h.indexOf(q, from);
		return { index: i, length: i >= 0 ? q.length : 0 };
	}
	return spanAcrossScripts(h, q, plan.conv, { ci, from, relaxFold: plan.relaxFold });
}

function swapBack(swapped){
	for(let i = 0; i < swapped.length; i += 1){
		const [n, name, rec] = swapped[i];
		if(name === null){
			if(n.nodeValue === rec.orig){ writeText(n, rec.conv); }
		}else if(n.getAttribute(name) === rec.orig){
			writeAttr(n, name, rec.conv);
		}
	}
}

// 导出 / 截图用:fn 执行期间(含其中的 await)导出内容是简体原文 ——
//   · 不挂在页面上的画布旁路 canvas 补丁(html2canvas 一类新建画布用 fillText 画字,画出来是原文);页面上的画布照常转换;
//   · roots(已在页面上、要截的元素):先把原文放回、挂 .horosa-script-keep 让观察者跳过,结束后去掉并重新转换;
//   · 导出时新建的隐藏宿主由调用方挂 .horosa-script-keep(SCRIPT_KEEP_CLASS),观察者不进。
// 看门狗 maxHoldMs(缺省 60 秒,计的是空闲时长):整整一个 maxHoldMs 里没有任何导出画布按原文画字 = 判挂起,
//   到点结束、恢复 roots 与转换;一直在画字的长导出(分段截图)每画一次就续上,不会半途被打断
//   (此前固定 60 秒到点:超过 60 秒的导出后半段离屏画布按繁体画字,同一份 PDF 简繁混杂)。切换简繁时一并结束。
//   只有导出画布(暂停之外从没画过字的离屏画布)的画字算续期;页面自己的离屏画布(图表量宽等)不算。
//   另有总时长上限 maxTotalMs(缺省 30 个 maxHoldMs):续得再久也到点解开,不让任何续期源把繁体界面永久钉住。
// 暂停期间有不挂在页面上的画布按原文画过 → 结束后广播一次重画(那可能是页面的 3D 标签纹理,画完不会自己再画)。
// 简体模式下等于直接执行 fn。回 Promise<fn 的结果>。
export const ORIGINAL_SCRIPT_MAX_HOLD_MS = 60000;
export const ORIGINAL_SCRIPT_MAX_TOTAL_HOLDS = 30;
export function withOriginalScript(fn, { roots, maxHoldMs = ORIGINAL_SCRIPT_MAX_HOLD_MS, maxTotalMs } = {}){
	const list = (Array.isArray(roots) ? roots : (roots ? [roots] : [])).filter((r)=>r && r.nodeType === 1);
	pauseDepth += 1;
	const marked = [];
	if(active){
		list.forEach((r)=>{
			if(!r.classList.contains(SCRIPT_KEEP_CLASS)){ r.classList.add(SCRIPT_KEEP_CLASS); marked.push(r); }
			swapToOriginal(r, []);
		});
	}
	let released = false;
	let timer = null;
	const hold = {
		release(reconvert){
			if(released){ return; }
			released = true;
			if(timer){ clearTimeout(timer); timer = null; }
			holds.delete(hold);
			pauseDepth = Math.max(0, pauseDepth - 1);
			marked.forEach((r)=>{ r.classList.remove(SCRIPT_KEEP_CLASS); });
			if(reconvert && active && convert){ marked.forEach((r)=>{ if(r.isConnected){ convertSubtree(r); } }); }
			if(reconvert && pauseDepth === 0 && holdBypassed){
				holdBypassed = false;
				if(active){ broadcast(SCRIPT_HANT, { repaint: true }); }
			}
		},
	};
	holds.add(hold);
	if(typeof maxHoldMs === 'number' && maxHoldMs > 0 && Number.isFinite(maxHoldMs)){
		let seen = holdActivity;
		const cap = (typeof maxTotalMs === 'number' && maxTotalMs > 0 && Number.isFinite(maxTotalMs)) ? maxTotalMs : maxHoldMs * ORIGINAL_SCRIPT_MAX_TOTAL_HOLDS;
		let elapsed = 0;
		let wait = Math.min(maxHoldMs, cap);
		const watch = ()=>{
			timer = null;
			if(released){ return; }
			elapsed += wait;
			if(holdActivity !== seen && elapsed < cap){   // 这一段里导出画布画过字:还在干活,续上(总时长封顶)
				seen = holdActivity;
				wait = Math.min(maxHoldMs, cap - elapsed);
				timer = setTimeout(watch, wait);
				return;
			}
			hold.release(true);
		};
		timer = setTimeout(watch, wait);
	}
	const done = ()=>hold.release(true);
	let out;
	try{
		out = fn();
	}catch(e){
		done();
		return Promise.reject(e);
	}
	return Promise.resolve(out).then((v)=>{ done(); return v; }, (e)=>{ done(); throw e; });
}

// ── 搜索比对(单源):只用于比对,不改任何数据 ───────────────────────────────────────────
// 简体模式与原先逐字节等价(原样比);繁体模式按「看到的字」比:算法在 scriptConvert/scriptMatch.js
// (纯函数,不依赖界面档位):被搜文字逐位接受 原文字 / 显示字 / 繁体专用字的简体写法 —— 照屏幕输入、直接输入简体、
// 混着输入都能命中,而不会因整串繁 → 简切词不同而漏命中 / 乱命中(「乾」不命中「天干地支」、「坐」命中「坐标」)。
// 含(matchesUserQuery)/ 命中位置(scriptMatchIndex)/ 整名相等(scriptTextEquals)三个入口(连同给高亮用的 scriptMatchSpan)同读一份比对方案(matchPlan),
// anyScript 时三者都带「放宽一档」(scriptMatch 的 relaxFold),口径一致:含 ⇔ 命中位置 ≥ 0(折回改了长度的除外),整名相等 ⇒ 含。
// 工具层 / 计算层不直接用本文件,也不直接调 scriptMatch 的纯函数:一律经 scriptNeutralMatch(恒 anyScript,与界面档位无关)。

// 比对方案:null = 原样比(简体界面且不带 anyScript,或什么转换器都没装);否则 { conv, relaxFold }。
// 只装了归一函数(无头空壳 / 测试桩)时,三个入口都退回两边归一(= 放宽一档、没有显示空间)
function matchPlan(anyScript){
	if(!active && !anyScript){ return null; }
	if(matchConv){ return { conv: matchConv, relaxFold: !!anyScript }; }
	if(matchKeyFn){ return { conv: { toMatchKey: matchKeyFn }, relaxFold: true }; }
	return null;
}

// 把用户照屏幕输入的繁体折回简体写法(存检索条件 / 按名查表用)。简体模式原样;只改繁体专用字。
// 子串检索不要用它两边各折一次再 indexOf(整串折回在子串上不稳定),用 matchesUserQuery / scriptMatchIndex。
// anyScript:不看界面简繁、只要转换器已加载就按同一算法比 —— 给不对着屏幕检索的调用方(AI 工具 / 无头 / 命令行:
// 检索词可能是繁体也可能是简体,与界面当前显示无关;调用前先 await ensureScriptConverter())。
export function scriptMatchKey(s, { anyScript = false } = {}){
	const str = s === undefined || s === null ? '' : `${s}`;
	if((!active && !anyScript) || !matchKeyFn){ return str; }
	return matchKeyFn(str);
}

// hay 里是否含 query。ci:不分大小写(缺省是);prefix:只认开头;anyScript 见 scriptMatchKey。
// 不对着屏幕检索(anyScript:AI 工具 / 无头 / 命令行)放宽一档:两边的繁体专用字都折回简体后再比 ——
// 检索词来自史料 / 别处,写法未必是屏幕上的显示写法(「張三豐」要命中「张三丰」,而「丰」显示时不换字)。
// 折回只改繁体专用字,「乾」这类本身也是简体的字不折,所以「乾」仍不命中「天干地支」;繁体专用字「幹」折成「干」会命中「天干」
// (偏召回的设计口径,见 AGENTS 第 6 条)。屏幕上的检索仍只认「看到的字」,不放宽。
export function matchesUserQuery(hay, query, { ci = true, prefix = false, anyScript = false } = {}){
	const plan = matchPlan(anyScript);
	if(!plan){
		let q = query === undefined || query === null ? '' : `${query}`;
		if(!q){ return true; }
		let h = hay === undefined || hay === null ? '' : `${hay}`;
		if(ci){ q = q.toLowerCase(); h = h.toLowerCase(); }
		return prefix ? h.startsWith(q) : h.indexOf(q) >= 0;
	}
	return matchAcrossScripts(hay, query, plan.conv, { ci, prefix, relaxFold: plan.relaxFold });
}

// 命中位置(hay 的 UTF-16 下标,命中长度 = query.length;无命中回 -1)。from:从第几位起找(找下一处)。
// 与 matchesUserQuery 同一方案(含放宽一档);折回改了长度、下标落不回原文的那类命中不计。
export function scriptMatchIndex(hay, query, { ci = true, from = 0, anyScript = false } = {}){
	const q = query === undefined || query === null ? '' : `${query}`;
	const h = hay === undefined || hay === null ? '' : `${hay}`;
	const plan = matchPlan(anyScript);
	if(!plan){
		if(!q){ return 0; }
		return ci ? h.toLowerCase().indexOf(q.toLowerCase(), from) : h.indexOf(q, from);
	}
	return indexAcrossScripts(h, q, plan.conv, { ci, from, relaxFold: plan.relaxFold });
}

// 整名相等(按名找命令 / 星体 / 天体一类):简体模式原样比;繁体模式看到的字 / 原文 / 混写都算同名;anyScript 同带放宽一档
export function scriptTextEquals(hay, query, { ci = true, anyScript = false } = {}){
	const q = query === undefined || query === null ? '' : `${query}`;
	const h = hay === undefined || hay === null ? '' : `${hay}`;
	const plan = matchPlan(anyScript);
	if(!plan){ return ci ? h.toLowerCase() === q.toLowerCase() : h === q; }
	return equalsAcrossScripts(h, q, plan.conv, { ci, relaxFold: plan.relaxFold });
}

// 查询词的其它写法(单源):给没法两边都归一的检索端用(后端检索、iframe 里的 SQL LIKE)——
// 那边的库简繁混存,发「原词 + 这些写法」,任一写法命中即算。
// 简体模式回 [](只发原词,与原先逐字节等价);繁体模式或 anyScript(远端库简繁混存,不论界面档位都要)回:
// 显示写法 + 一简多繁逐位展开的各繁体写法(历 → 曆 / 歷,钟 → 鐘 / 鍾)+ 查询含繁体专用字时的简体写法,至多 8 条。
// 不发「整串繁 → 简」(那会把「乾」变成「干」、「著」变成「着」,远端结果凭空扩张)。
export function scriptQueryVariants(query, { anyScript = false } = {}){
	const raw = `${query === undefined || query === null ? '' : query}`.trim();
	if(!raw || (!active && !anyScript) || !matchKeyFn || !matchConv){ return []; }
	return queryVariantsAcrossScripts(raw, matchConv);
}

function nodeText(v){
	if(v === undefined || v === null || typeof v === 'boolean'){ return ''; }
	if(typeof v === 'string' || typeof v === 'number'){ return `${v}`; }
	if(Array.isArray(v)){ return v.map(nodeText).join(''); }
	if(typeof v === 'object' && v.props){ return nodeText(v.props.children); }
	return '';
}

// antd Select 的 filterOption(单源):与组件缺省同口径(取 prop 那一栏、不分大小写),只多一步简繁归一。
// prop 缺省按组件缺省:选项组看 label,其余看 value;'children' / 'label' 是 React 节点时取其中文字。
const filterCache = {};
export function scriptFilterBy(prop){
	const k = prop || '';
	if(!filterCache[k]){
		filterCache[k] = function scriptFilterOption(input, option){
			if(!option){ return false; }
			const key = prop || (option.options ? 'label' : 'value');
			return matchesUserQuery(nodeText(option[key]), input);
		};
	}
	return filterCache[k];
}
export const scriptFilterOption = scriptFilterBy();

// ── 订阅切换(单源;与 appearance.subscribeAppearance 同范式:合帧、同值不回调)─────────────────
// canvas 上的字(天文馆标签 / 3D 标签 / 风水罗盘 / echarts)画好后不会自己变,宿主在这里订阅后重画。
export function subscribeScriptMode(fn){
	if(typeof fn !== 'function' || typeof window === 'undefined'){ return ()=>{}; }
	let detached = false;
	let pending = false;
	let last = currentScriptMode();
	const schedule = (typeof requestAnimationFrame === 'function') ? requestAnimationFrame : (cb)=>setTimeout(cb, 16);
	let force = false;   // 导出结束后的重画请求(档位没变也回调一次)
	const kick = (ev)=>{
		if(ev && ev.detail && ev.detail.repaint){ force = true; }
		if(detached || pending){ return; }
		pending = true;
		schedule(()=>{
			pending = false;
			if(detached){ return; }
			const now = currentScriptMode();
			if(now === last && !force){ return; }
			force = false;
			last = now;
			try{ fn(now); }catch(e){ /* 订阅方重画失败不上抛:下一次真实更新仍会画 */ }
		});
	};
	window.addEventListener(SCRIPT_APPLIED_EVENT, kick);
	return ()=>{
		detached = true;
		window.removeEventListener(SCRIPT_APPLIED_EVENT, kick);
	};
}

// 逐字出图时给每个字的节点带上整词与位次(React:展开到元素属性上;d3:attr 逐个设)
export function scriptWordAttrs(word, idx){
	if(!word || idx === undefined || idx === null || idx < 0){ return {}; }
	return { [SCRIPT_WORD_ATTR]: `${word}`, [SCRIPT_IDX_ATTR]: `${idx}` };
}

// 同源 iframe(名人库页一类)的文档挂进来,与主文档同一套转换;回摘除函数(iframe 换页 / 卸载时调)。
// 跨源或拿不到文档的静默跳过。iframe 自己的 canvas 不在补丁范围内(另一个窗口的原型)。
export function attachScriptDocument(doc){
	if(typeof document === 'undefined' || !doc || doc === document || !doc.documentElement){ return ()=>{}; }
	extraDocs.add(doc);
	if(active && convert){
		convertSubtree(doc.documentElement);
		if(observer){ try{ observer.observe(doc.documentElement, OBSERVE_OPTS); }catch(_){ /* noop */ } }
	}
	return ()=>{
		if(!extraDocs.has(doc)){ return; }
		if(active){ try{ swapToOriginal(doc.documentElement, []); }catch(_){ /* 文档已卸载 */ } }
		extraDocs.delete(doc);
	};
}

// 测试用:复位运行态(不碰存储)
export function __resetScriptModeForTest(){
	stopObserver();
	unpatchCanvas();
	clearPending();
	active = false;
	wanted = SCRIPT_HANS;
	textRec = new WeakMap();
	attrRec = new WeakMap();
	pauseDepth = 0;
	holds.forEach((h)=>{ try{ h.release(false); }catch(_){ /* noop */ } });
	holds.clear();
	holdBypassed = false;
	pageOwnedCanvas = new WeakMap();
	extraDocs.clear();
	if(typeof document !== 'undefined' && document.documentElement && rootLangOrig !== undefined){
		if(rootLangOrig === null){ document.documentElement.removeAttribute('lang'); }else{ document.documentElement.setAttribute('lang', rootLangOrig); }
	}
	rootLangOrig = undefined;
	bootDone = false;
}

// 测试用:换掉转换器。extra = 转换器的其余导出(isTradOnlyChar / hansCandidatesOf / hantCandidatesOf / matchFormsOf …;
// 传真转换器模块即可),缺省只有 toHant / toMatchKey 两样
export function __setConverterForTest(fn, keyFn, extra){
	convert = fn;
	matchKeyFn = keyFn === undefined ? null : keyFn;
	matchConv = fn ? { ...(extra || {}), toHant: fn, ...(matchKeyFn ? { toMatchKey: matchKeyFn } : {}) } : null;
}

// 测试用:换掉转换器的加载方式(缺省 = 动态 import 分包);传空复原
export function __setConverterLoaderForTest(loader){
	converterLoader = typeof loader === 'function' ? loader : importConverter;
	loading = null;
}
