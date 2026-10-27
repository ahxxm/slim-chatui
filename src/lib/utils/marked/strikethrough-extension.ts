import type { MarkedExtension } from 'marked';

export const disableSingleTilde: MarkedExtension = {
	extensions: [
		{
			name: 'singleTilde',
			level: 'inline',
			start(src) {
				const index = src.indexOf('~');
				return index === -1 ? undefined : index;
			},
			tokenizer(src) {
				const match = /^~(?=\S)([\s\S]*?\S)~(?!~)/.exec(src);
				if (!match || match[0].startsWith('~~')) return;

				return {
					type: 'text',
					raw: match[0],
					text: match[0]
				};
			}
		}
	],
	tokenizer: {
		del(src) {
			const match = /^~~(?=\S)([\s\S]*?\S)~~/.exec(src);
			if (!match) return false;

			return {
				type: 'del',
				raw: match[0],
				text: match[1],
				tokens: this.lexer.inlineTokens(match[1])
			};
		}
	}
};
