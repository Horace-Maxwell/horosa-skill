// 判读层覆写值的值域检查（v0.50.0）：引擎词表（HORARY_PARAM_SPEC / ELECTION_PARAM_SPEC）里 select 键的档、switch 键的布尔。
// 上游页面只写得进档内值；headless 请求体可以写任何东西，而引擎对认不出的值静默按缺省算（options.vocMode='bogus' 照出盘、
// 判读按缺省口径）。认得的写法换成档值（'2' → 2、'true' → true），认不出的交给调用方进 invalid 回执。
export function checkSpecValue(spec, value) {
  if (spec && spec.type === 'select' && Array.isArray(spec.options) && spec.options.length) {
    const hit = spec.options.find((o) => o.value === value || `${o.value}` === `${value}`);
    return hit ? { ok: true, value: hit.value } : { ok: false, allowed: spec.options.map((o) => o.value) };
  }
  if (spec && spec.type === 'switch') {
    if (value === true || value === 1 || value === '1' || value === 'true') return { ok: true, value: true };
    if (value === false || value === 0 || value === '0' || value === 'false') return { ok: true, value: false };
    return { ok: false, allowed: [true, false] };
  }
  return { ok: true, value };
}
