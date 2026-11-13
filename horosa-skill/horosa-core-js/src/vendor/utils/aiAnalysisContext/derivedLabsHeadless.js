// 辅盘「变换盘」「黄道制」的无头复算:辅盘页没对这张盘出过图时(或出的是别的命主),AI 挂载 / 外部智能体按
// 辅盘页保存的设置(变换种类与其选项 / 黄道版本)直接请求后端,正文与页面出盘即存的快照同一份构建函数。
// 页面侧模块按需动态载入:不把辅盘页的依赖拉进 AI 上下文的静态链。




export const DERIVED_LAB_HEADLESS_KEYS = ['transformchart', 'zodiacsystems'];

// 变换盘只发这种变换真正用到的选项(与辅盘页 AstroTransformLab.requestOptions 同口径)
export function transformRequestOptions(settings, kindDef){
	const { kind, planet, shift, house, variant } = settings || {};
	const options = (kindDef && kindDef.options) || [];
	const out = { transformKind: kind };
	if(options.indexOf('planet') >= 0){ out.transformPlanet = planet; }
	if(options.indexOf('shift') >= 0){ out.transformShift = shift ? 1 : 0; }
	if(options.indexOf('house') >= 0){ out.transformHouse = house; }
	if(options.indexOf('variant') >= 0){ out.transformVariant = variant; }
	return out;
}
