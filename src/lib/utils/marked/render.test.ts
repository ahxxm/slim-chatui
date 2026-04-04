import { describe, expect, it } from 'vitest';

import { chatMarked } from './chat-marked';
import { shouldRenderNestedLinkTokens } from './render';

const firstInlineToken = (source: string) => chatMarked.Lexer.lexInline(source)[0] as any;

describe('shouldRenderNestedLinkTokens', () => {
	it('skips nested rendering for simple markdown link text', () => {
		const token = firstInlineToken('[label](https://example.com)');

		expect(token.type).toBe('link');
		expect(shouldRenderNestedLinkTokens(token)).toBe(false);
	});

	it('skips nested rendering for autolink text that would recurse into itself', () => {
		const token = firstInlineToken('https://example.com/path');

		expect(token.type).toBe('link');
		expect(shouldRenderNestedLinkTokens(token)).toBe(false);
	});

	it('skips nested rendering for partial streamed links before the closing parenthesis arrives', () => {
		const token = chatMarked.Lexer.lexInline(
			'First point with a [link](https://example.com/doc'
		).find((candidate) => candidate.type === 'link') as any;

		expect(token?.text).toBe('https://example.com/doc');
		expect(shouldRenderNestedLinkTokens(token)).toBe(false);
	});

	it('keeps nested rendering for formatted link labels', () => {
		const token = firstInlineToken('[**label**](https://example.com)');

		expect(token.type).toBe('link');
		expect(shouldRenderNestedLinkTokens(token)).toBe(true);
	});
});
