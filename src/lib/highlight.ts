import hljsCore from 'highlight.js/lib/core';
import bash from 'highlight.js/lib/languages/bash';
import c from 'highlight.js/lib/languages/c';
import cpp from 'highlight.js/lib/languages/cpp';
import css from 'highlight.js/lib/languages/css';
import diff from 'highlight.js/lib/languages/diff';
import go from 'highlight.js/lib/languages/go';
import javascript from 'highlight.js/lib/languages/javascript';
import json from 'highlight.js/lib/languages/json';
import less from 'highlight.js/lib/languages/less';
import markdown from 'highlight.js/lib/languages/markdown';
import plaintext from 'highlight.js/lib/languages/plaintext';
import python from 'highlight.js/lib/languages/python';
import shell from 'highlight.js/lib/languages/shell';
import typescript from 'highlight.js/lib/languages/typescript';

export const grammars = {
	bash,
	c,
	cpp,
	css,
	diff,
	go,
	javascript,
	json,
	less,
	markdown,
	plaintext,
	python,
	shell,
	typescript
};

for (const [name, grammar] of Object.entries(grammars)) {
	hljsCore.registerLanguage(name, grammar);
}

export default hljsCore;
