// 择日条件树的取值预检（审计 S-01，P0）。
//
// 上游的条件值域靠页面下拉框兜着（注册表每个 select / multiselect 字段都带 options），判定函数对界外值一律落到缺省分支
// （taiyiZeriConditionTypes.js「阴阳遁」：`p.value === '阴' ? !isYang : isYang`）。headless 入口没有下拉框：
// 写成标签「阴遁」→ 拿到阳遁的 97 个时辰；黄历「宜」写用户原话「搬家」→ 零命中、不报错。AGENTS §4.4：上游靠页面兜住的值域，
// headless 入口一律自己兜。
//
// 规则（只读注册表，不手抄任何一张词表——上游加条件、改选项自动跟上）：
//   - 值是某个选项的 value → 照用；
//   - 不是 value、但唯一等于某个选项的 label（「阴遁」→「阴」）→ 读成该 value，并回一条说明；
//   - 其余 → 按字段报错，列出这个字段的可选值（黄历用事另给「是不是指」的建议，不替用户选）。
// 只查 select / multiselect；数字框、日期、自由文本不在此列（各条件自己的 validate 照旧在 compile 里跑）。

// 黄历用事：日常说法 → 通书用事词（只作「是不是指」提示，绝不自动替换；取不在选项里的项自动丢掉）。
const EVERYDAY_TERMS = {
  搬家: ['移徙', '入宅'], 乔迁: ['移徙', '入宅'], 入住: ['入宅'], 结婚: ['嫁娶'], 婚礼: ['嫁娶'], 领证: ['嫁娶'],
  订婚: ['纳采', '订盟'], 提亲: ['纳采'], 开业: ['开市'], 开张: ['开市'], 签约: ['立券', '交易'], 签合同: ['立券'],
  装修: ['修造', '动土'], 动工: ['动土', '修造'], 出门: ['出行'], 旅行: ['出行'], 下葬: ['安葬'], 落葬: ['安葬'],
  理发: ['理发', '剃头'], 求医: ['求医', '疗病'], 看病: ['求医', '疗病'], 买房: ['交易', '入宅'], 买车: ['交易'],
};

function optionList(field) {
  const raw = Array.isArray(field.options) ? field.options : null;
  if (!raw || !raw.length) return null;
  return raw.map((o) => (o && typeof o === 'object' ? { value: o.value, label: o.label === undefined ? o.value : o.label } : { value: o, label: o }));
}

function squash(text) {
  return `${text}`.replace(/\s+/g, '');
}

function resolveOne(raw, opts) {
  const key = `${raw}`;
  const byValue = opts.find((o) => `${o.value}` === key);
  if (byValue) return { ok: true, value: byValue.value };
  const byLabel = opts.filter((o) => squash(o.label) === squash(key));
  if (byLabel.length === 1) return { ok: true, value: byLabel[0].value, note: `${key} → ${byLabel[0].value}` };
  return { ok: false };
}

function suggestionsFor(bad, opts) {
  const values = new Set(opts.map((o) => `${o.value}`));
  const out = [];
  for (const word of bad) {
    for (const candidate of EVERYDAY_TERMS[`${word}`] || []) {
      if (values.has(candidate) && !out.includes(candidate)) out.push(candidate);
    }
  }
  return out;
}

export function checkConditionValues(registry, tree) {
  const notes = [];
  const invalid = [];
  const walk = (node, path) => {
    if (!node || typeof node !== 'object') return node;
    if (node.kind === 'group' || Array.isArray(node.children)) {
      return { ...node, children: (node.children || []).map((child, i) => walk(child, `${path}.children[${i}]`)) };
    }
    const spec = registry[node.type];
    if (!spec) return node; // 未知条件类型：交给 compile 报（它有现成的「未知条件类型」）
    const params = { ...(node.params || {}) };
    for (const field of spec.fields || []) {
      if (field.kind !== 'select' && field.kind !== 'multiselect') continue;
      // 按条件显示的字段（天星「中点」的 targetId：targetKind=planet 时是星体，=angle 时才是四轴下拉）只在页面显示它时才查——
      // 与页面同一条 showIf；隐藏着的字段，页面也不让它约束取值。
      if (typeof field.showIf === 'function') {
        let shown = true;
        try { shown = !!field.showIf(params); } catch (e) { shown = true; }
        if (!shown) continue;
      }
      const opts = optionList(field);
      if (!opts || !(field.key in params)) continue;
      const given = params[field.key];
      if (given === undefined || given === null || given === '') continue;
      const many = field.kind === 'multiselect';
      const items = many ? (Array.isArray(given) ? given : [given]) : [given];
      const fixed = [];
      const bad = [];
      for (const item of items) {
        const hit = resolveOne(item, opts);
        if (hit.ok) {
          fixed.push(hit.value);
          if (hit.note) notes.push(`「${spec.label}」的「${field.label || field.key}」${hit.note}（按选项标签读成规范值）`);
        } else {
          bad.push(item);
        }
      }
      if (bad.length) {
        const suggest = suggestionsFor(bad, opts);
        invalid.push({
          path, type: node.type, label: spec.label, field: field.key, field_label: field.label || field.key, given: bad,
          allowed: opts.map((o) => ({ value: o.value, label: o.label })),
          ...(suggest.length ? { did_you_mean: suggest } : {}),
        });
        continue;
      }
      if (many && !Array.isArray(given)) notes.push(`「${spec.label}」的「${field.label || field.key}」是多选，单个值已按一项读`);
      params[field.key] = many ? fixed : fixed[0];
    }
    return { ...node, params };
  };
  const out = walk(tree, 'conditions');
  return { tree: out, notes, invalid };
}

export function invalidValuesMessage(invalid) {
  return invalid.map((row) => {
    const shown = row.allowed.slice(0, 24).map((o) => (`${o.label}`.includes(`${o.value}`) ? `${o.label}` : `${o.value}(${o.label})`)).join('/');
    const more = row.allowed.length > 24 ? ` 等共 ${row.allowed.length} 项（全表见 details.invalid[].allowed）` : '';
    const hint = row.did_you_mean ? `；是不是指：${row.did_you_mean.join(' / ')}？` : '';
    return `「${row.label}」的「${row.field_label}」取值 ${row.given.map((g) => `「${g}」`).join('')} 不在可选值里（可选：${shown}${more}）${hint}`;
  }).join('；');
}
