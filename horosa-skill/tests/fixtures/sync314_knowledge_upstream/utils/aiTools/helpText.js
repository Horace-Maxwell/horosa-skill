// The reference walker: element tree → plain text. Class components are instantiated, widgets marked __helpPure are
// called, any other function component is NOT called (only its children are walked) — the same three rules as upstream.
import React from 'react';

const BLOCK = { div: 1, p: 1, li: 1, ul: 1, ol: 1, table: 1, tr: 1, section: 1 };

function walk(node, out){
	if(node === null || node === undefined || typeof node === 'boolean'){ return; }
	if(typeof node === 'string' || typeof node === 'number'){ out.push(`${node}`); return; }
	if(Array.isArray(node)){ node.forEach((n)=>walk(n, out)); return; }
	if(!React.isValidElement(node)){ return; }
	const type = node.type;
	const props = node.props || {};
	if(typeof type === 'function'){
		if(type.__helpPure){ walk(type(props), out); return; }
		if(type.prototype && type.prototype.isReactComponent){
			const inst = new type(props);
			inst.props = props;
			walk(inst.render(), out);
			return;
		}
		walk(props.children, out);
		return;
	}
	const cls = typeof props.className === 'string' ? props.className : '';
	if(type === 'div' && /horosa-help-kv/.test(cls)){
		out.push('\n');
		React.Children.toArray(props.children).forEach((child, i)=>{ if(i > 0){ out.push(':'); } walk(child, out); });
		out.push('\n');
		return;
	}
	if(/horosa-help-step-no/.test(cls)){ walk(props.children, out); out.push('. '); return; }
	if(type === 'td' || type === 'th'){ walk(props.children, out); out.push(' | '); return; }
	if(type === 'mark'){ walk(props.children, out); out.push('(只有参考文本里有的字)'); return; }
	const block = typeof type === 'string' && BLOCK[type];
	if(block){ out.push('\n'); }
	if(type === 'li'){ out.push('· '); }
	if(type === 'br'){ out.push('\n'); return; }
	walk(props.children, out);
	if(block){ out.push('\n'); }
}

export function helpElementToText(element){
	const out = [];
	walk(element, out);
	return out.join('').replace(/[ \t]+\n/g, '\n').replace(/\n[ \t]+/g, '\n').replace(/\n{3,}/g, '\n\n').trim();
}
