import { Marked } from 'marked';
import markedKatexExtension from './katex-extension';
import markedExtension from './extension';
import citationExtension from './citation-extension';
import footnoteExtension from './footnote-extension';
import { disableSingleTilde } from './strikethrough-extension';
import { mentionExtension } from './mention-extension';

const chatMarked = new Marked();

const options = { throwOnError: false };

chatMarked.use(markedKatexExtension(options));
chatMarked.use(markedExtension(options));
chatMarked.use(citationExtension(options));
chatMarked.use(footnoteExtension(options));
chatMarked.use(disableSingleTilde);
chatMarked.use({
	breaks: true,
	extensions: [
		mentionExtension({ triggerChar: '@' }),
		mentionExtension({ triggerChar: '#' }),
		mentionExtension({ triggerChar: '$' })
	]
});

export { chatMarked };
