import { marked } from 'marked';
import { afterAll, describe, expect, it, vi } from 'vitest';

vi.stubGlobal('Image', class {});
vi.stubGlobal('location', { hostname: 'localhost' });
const { processResponseContent } = await import('./index');

afterAll(() => {
	vi.unstubAllGlobals();
});

// Workaround for marked: processResponseContent adds spaces so CJK-adjacent emphasis parses.
describe('processResponseContent Chinese Markdown delimiters', () => {
	it.each([
		[
			'bold text with Chinese parentheses',
			'中文**加粗（说明）**文字',
			'中文 <strong>加粗（说明）</strong> 文字'
		],
		[
			'italic text with Chinese parentheses',
			'中文*斜体（说明）*文字',
			'中文 <em>斜体（说明）</em> 文字'
		],
		['bold text with Chinese quotes', '中文**“引用”**文字', '中文 <strong>“引用”</strong> 文字'],
		['italic text with Chinese quotes', '中文*“引用”*文字', '中文 <em>“引用”</em> 文字']
	])('requires preprocessing for marked to render %s', (_case, input, expected) => {
		expect(marked.parseInline(input)).toBe(input);
		expect(marked.parseInline(processResponseContent(input))).toBe(expected);
	});
});
