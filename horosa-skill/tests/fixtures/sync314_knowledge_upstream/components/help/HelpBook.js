import React, { Component } from 'react';
import { XQSelect as Select } from '../xq-ui';

export function bookChapters(book){
	const out = [];
	((book && book.groups) || []).forEach((g)=>((g && g.chapters) || []).forEach((c)=>{ if(c && c.key){ out.push({ ...c, groupKey: g.key, groupLabel: g.label, groupHint: g.hint }); } }));
	return out;
}

class HelpBook extends Component{
	render(){
		const chapters = bookChapters(this.props.book);
		return <div><Select value={chapters[0].key} />{chapters[0].render()}</div>;
	}
}

export default HelpBook;
