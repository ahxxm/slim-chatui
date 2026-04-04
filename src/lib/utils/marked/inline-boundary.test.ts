import type { Token } from 'marked';
import { describe, expect, it } from 'vitest';

import { getInlineMutableTokenStartIndex, isUnsafeInlineBoundary } from './inline-boundary';

const createTextToken = (raw: string): Token =>
	({
		type: 'text',
		raw,
		text: raw
	}) as unknown as Token;

const createStrongToken = (raw: string): Token =>
	({
		type: 'strong',
		raw,
		text: raw
	}) as unknown as Token;

const createLinkToken = (raw: string, text: string, href: string): Token =>
	({
		type: 'link',
		raw,
		text,
		href,
		tokens: []
	}) as unknown as Token;

describe('inline markdown boundary detection', () => {
	it('keeps the mutable window open when an earlier token starts an unfinished bracketed construct', () => {
		const tokens = [
			createTextToken('prefix ['),
			createTextToken('label'),
			createTextToken(' tail')
		];

		expect(getInlineMutableTokenStartIndex(tokens)).toBe(0);
	});

	it('treats plain completed inline runs as safe frozen-prefix boundaries', () => {
		const tokens = [
			createTextToken('alpha '),
			createStrongToken('**beta**'),
			createTextToken(' gamma')
		];

		expect(getInlineMutableTokenStartIndex(tokens)).toBe(2);
	});

	it('treats autolink-looking link boundaries as unsafe when the next text could extend the url', () => {
		const previousToken = createLinkToken(
			'https://example.com',
			'https://example.com',
			'https://example.com'
		);
		const nextToken = createTextToken('/docs');

		expect(isUnsafeInlineBoundary(previousToken, nextToken)).toBe(true);
	});

	it('treats emphasis delimiters as unsafe when the next text begins with a matching delimiter', () => {
		const previousToken = createStrongToken('**bold**');
		const nextToken = createTextToken('*more');

		expect(isUnsafeInlineBoundary(previousToken, nextToken)).toBe(true);
	});
});
