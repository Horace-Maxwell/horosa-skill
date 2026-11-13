// A bound volume: its own chapter, the alpha chapters re-keyed one by one, and the whole alpha book laid out as one chapter.
import React, { Component } from 'react';
import HelpBook from './HelpBook';
import { p, title, Lead } from './helpDocStyle';
import { ALPHA_CHAPTERS } from './AlphaHelpDoc';

function combined(chapters){
	return ()=>(
		<div>
			{chapters.map((c, i)=>(
				<div key={c.key}>
					{i ? <div style={title}>{c.label}</div> : null}
					{c.render()}
				</div>
			))}
		</div>
	);
}

export const HELP_BOOK = {
	title: '乙术合订 · 操作手册',
	groups: [
		{ key: 'own', label: '本册', chapters: [
			{ key: 'own', label: '乙术本法', render: ()=>(<div><Lead>乙术自己的一章。</Lead><p style={p}>这一章只在合订本里,别册没有。</p></div>) },
			{ key: 'alphaAll', label: '甲术', aliases: ['alpha'], render: combined(ALPHA_CHAPTERS) },
		] },
		{ key: 'alpha', label: '甲术各法', chapters: ALPHA_CHAPTERS.map((c)=>({ ...c, key: `alpha.${c.key}`, aliases: undefined })) },
	],
};

class BetaHelpDoc extends Component{
	static book = HELP_BOOK;

	render(){
		return <HelpBook book={HELP_BOOK} />;
	}
}

export default BetaHelpDoc;
