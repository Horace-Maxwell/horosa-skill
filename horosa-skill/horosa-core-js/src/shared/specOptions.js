// 判读层覆写值的值域检查（v0.50.0）：引擎词表（HORARY_PARAM_SPEC / ELECTION_PARAM_SPEC）里 select 键的档、switch 键的布尔。
// 上游页面只写得进档内值；headless 请求体可以写任何东西，而引擎对认不出的值静默按缺省算（options.vocMode='bogus' 照出盘、
// 判读按缺省口径）。认得的写法换成档值（'2' → 2、'true' → true），认不出的交给调用方进 invalid 回执。
// legacy = 引擎 / runner 另行兼容的旧存档值（如择日 pdTimeKey 的 Cardan / Placidus，见 runners/horary_election.py
// _ELECTION_PD_TIME_KEY_COMPAT）：原样放行。空值（''/null）= 「随流派」，原样放行（resolveElectionParams 同口径）。
export function checkSpecValue(spec, value, legacy = []) {
  if (value === '' || value === null || value === undefined || legacy.indexOf(value) >= 0) return { ok: true, value };
  if (spec && spec.type === 'select' && Array.isArray(spec.options) && spec.options.length) {
    // 档值正好是 1 / 0 的开关式 select（如卜卦 tradition）：JSON 布尔照读（true → 1、false → 0）。合并深审时 live 抓到：
    // 样例与客户端都写 `tradition: true`，按字符串比 'true' ≠ '1' 被拒。
    const binary = spec.options.length === 2 && spec.options.every((o) => o.value === 0 || o.value === 1);
    const probe = binary && typeof value === 'boolean' ? (value ? 1 : 0) : value;
    const hit = spec.options.find((o) => o.value === probe || `${o.value}` === `${probe}`);
    return hit ? { ok: true, value: hit.value } : { ok: false, allowed: spec.options.map((o) => o.value) };
  }
  if (spec && spec.type === 'switch') {
    if (value === true || value === 1 || value === '1' || value === 'true') return { ok: true, value: true };
    if (value === false || value === 0 || value === '0' || value === 'false') return { ok: true, value: false };
    return { ok: false, allowed: [true, false] };
  }
  return { ok: true, value };
}
