import React from 'react';

export const h = { fontWeight: 700 };
export const p = { margin: 0 };
export const ul = { margin: 0 };
export const li = { margin: 0 };
export const card = { borderRadius: 10 };
export const ct = { fontWeight: 700, fontSize: 13.5 };
export const title = { fontWeight: 800 };

export function kv(k, v, key){
	return (
		<div key={key} className="horosa-help-kv">
			<span>{k}</span>
			<span>{v}</span>
		</div>
	);
}

export function Lead({ children }){
	return <p className="horosa-help-lead">{children}</p>;
}

export function Section({ title: sectionTitle, children }){
	return (
		<section>
			<div style={h}>{sectionTitle}</div>
			{children}
		</section>
	);
}

export function Tip({ tone = 'tip', label, children }){
	const labels = { tip: '提示', note: '说明', warn: '注意' };
	return (
		<div className="horosa-help-tip">
			<span>{label || labels[tone]}</span>{children}
		</div>
	);
}

export function Steps({ items }){
	return (
		<ol>
			{(items || []).map((item, i)=>(
				<li key={i}>
					<span className="horosa-help-step-no">{i + 1}</span>
					<span>{item}</span>
				</li>
			))}
		</ol>
	);
}

export function OptionTable({ rows }){
	const cols = [{ key: 'name', title: '选项' }, { key: 'values', title: '取值' }, { key: 'def', title: '缺省' }];
	return (
		<div>
			<table>
				<thead><tr>{cols.map((c)=><th key={c.key}>{c.title}</th>)}</tr></thead>
				<tbody>
					{(rows || []).map((row, i)=>(
						<tr key={i}>{cols.map((c)=><td key={c.key}>{row[c.key]}</td>)}</tr>
					))}
				</tbody>
			</table>
		</div>
	);
}

[Lead, Section, Tip, Steps, OptionTable].forEach((fn)=>{ fn.__helpPure = true; });
