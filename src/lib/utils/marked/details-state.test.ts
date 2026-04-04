import { describe, expect, it } from 'vitest';

import {
	createIndexedDetailsStateIds,
	getDetailsIdentityBase,
	type DetailsIdentityToken
} from './details-state';

describe('details state identity', () => {
	it('ignores streaming summary and text changes', () => {
		const initialToken = {
			type: 'details',
			raw: '<details>',
			summary: 'Thinking',
			text: 'first step',
			attributes: {
				type: 'reasoning',
				done: 'false'
			}
		} as unknown as DetailsIdentityToken;

		const streamedToken = {
			type: 'details',
			raw: '<details>',
			summary: 'Thought for 1.3 seconds',
			text: 'first step with more text',
			attributes: {
				type: 'reasoning',
				done: 'true',
				duration: '1.3'
			}
		} as unknown as DetailsIdentityToken;

		expect(getDetailsIdentityBase(initialToken)).toBe(getDetailsIdentityBase(streamedToken));
	});

	it('uses stable attributes plus occurrence order for repeated details blocks', () => {
		const items = [
			{
				type: 'details',
				raw: '<details>',
				attributes: {
					type: 'web_search',
					query: 'cats'
				}
			},
			{
				type: 'paragraph'
			},
			{
				type: 'details',
				raw: '<details>',
				attributes: {
					type: 'web_search',
					query: 'cats'
				}
			}
		] as DetailsIdentityToken[];

		const ids = createIndexedDetailsStateIds(items, (token) => token, 'message-1');

		expect(ids.get(0)).toBe('message-1::type:web_search|query:cats::0');
		expect(ids.get(2)).toBe('message-1::type:web_search|query:cats::1');
	});

	it('keeps blocks distinct when stable attributes differ', () => {
		const catSearch = {
			type: 'details',
			raw: '<details>',
			attributes: {
				type: 'web_search',
				query: 'cats'
			}
		} as unknown as DetailsIdentityToken;

		const dogSearch = {
			type: 'details',
			raw: '<details>',
			attributes: {
				type: 'web_search',
				query: 'dogs'
			}
		} as unknown as DetailsIdentityToken;

		expect(getDetailsIdentityBase(catSearch)).not.toBe(getDetailsIdentityBase(dogSearch));
	});

	it('ignores bulky tool call arguments and files when deriving identity', () => {
		const initialToolCall = {
			type: 'details',
			raw: '<details>',
			attributes: {
				type: 'tool_calls',
				name: 'search_docs',
				arguments: '{"query":"render glitch"}',
				files: '[{"id":"file-1"}]'
			}
		} as unknown as DetailsIdentityToken;

		const streamedToolCall = {
			type: 'details',
			raw: '<details>',
			attributes: {
				type: 'tool_calls',
				name: 'search_docs',
				arguments: '{"query":"render glitch with more context"}',
				files: '[{"id":"file-2"},{"id":"file-3"}]'
			}
		} as unknown as DetailsIdentityToken;

		expect(getDetailsIdentityBase(initialToolCall)).toBe(
			getDetailsIdentityBase(streamedToolCall)
		);
	});
});
