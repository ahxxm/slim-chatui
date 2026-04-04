import { describe, expect, it } from 'vitest';

import { toPreviewText } from './preview-text';

describe('toPreviewText', () => {
	it('strips heading markers without removing literal hash or comparison characters', () => {
		expect(toPreviewText('# Heading\nI use C# and F#\n10 > 5')).toBe(
			'Heading I use C# and F# 10 > 5'
		);
	});

	it('drops complete fenced code blocks and trailing unclosed fences without eating intervening prose', () => {
		const content = ['```python', 'print("one")', '```', 'kept text', '```more', 'stuff'].join(
			'\n'
		);

		expect(toPreviewText(content)).toBe('kept text');
	});

	it('keeps link labels and image alt text while stripping markdown syntax', () => {
		const content =
			'See [docs](https://example.com) and ![diagram](https://example.com/diagram.png)';

		expect(toPreviewText(content)).toBe('See docs and diagram');
	});

	it('keeps details summaries and strips raw html tags', () => {
		const content = [
			'<details type="reasoning">',
			'<summary>Thinking...</summary>',
			'<div>Hello <strong>world</strong></div>',
			'</details>'
		].join('\n');

		expect(toPreviewText(content)).toBe('Thinking... Hello world');
	});
});
