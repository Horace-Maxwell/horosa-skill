import { Component } from 'react';
import HelpBook from './HelpBook';
import { ALPHA_CHAPTERS } from './alpha/chapters';

// Other books take this book's chapters from here (as upstream's bound volume imports YANQIN_CHAPTERS from YanqinHelpDoc).
export { ALPHA_CHAPTERS };

export const HELP_BOOK = {
	title: '甲术 · 操作手册',
	groups: [
		{ key: 'methods', label: '两法', hint: '甲术的两种算法。', chapters: ALPHA_CHAPTERS },
	],
};

class AlphaHelpDoc extends Component{
	static book = HELP_BOOK;

	render(){
		return <HelpBook book={HELP_BOOK} />;
	}
}

export default AlphaHelpDoc;
