// @vitest-environment jsdom
/**
 * The backend html.escape()s markdown before embedding it in <details> tags
 * (so < > & in reasoning text don't break the HTML structure). The extension
 * should decode and render that content as proper markdown, not dump raw
 * html-encoded text.
 *
 * These tests render the Markdown component with backend-shaped content and
 * assert on the resulting DOM.
 */
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { writable } from 'svelte/store';
import { tick } from 'svelte';
import { render } from '@testing-library/svelte';

vi.mock('$app/environment', () => ({ browser: true, dev: false }));

import { settings, user } from '$lib/stores';
import Markdown from '$lib/components/chat/Messages/Markdown.svelte';

beforeEach(() => {
	user.set({ id: '1', name: 'Test', email: 'test@test', role: 'user' } as any);
	settings.set({ expandDetails: true } as any);
});

async function renderMarkdown(content: string) {
	const { container } = render(Markdown, {
		props: { content, id: 'test-md', done: true },
		context: new Map([['i18n', writable({ t: (k: string) => k })]])
	});
	await tick();
	return container;
}

describe('details: html-escaped markdown renders correctly', () => {
	it('html-escaped blockquotes render as <blockquote>', async () => {
		const container = await renderMarkdown(
			[
				'<details type="reasoning" done="true" duration="3.2">',
				'<summary>Thought for 3.2 seconds</summary>',
				'&gt; The user wants to know about `x &lt; 5`',
				'',
				'&gt; Let me think about this...',
				'</details>'
			].join('\n')
		);

		const blockquotes = container.querySelectorAll('blockquote');
		expect(blockquotes.length, 'decoded &gt; should render as blockquote').toBeGreaterThan(0);
	});

	it('html entities inside code spans are decoded', async () => {
		const container = await renderMarkdown(
			[
				'<details type="reasoning" done="true" duration="2.0">',
				'<summary>Thinking</summary>',
				'&gt; Check if `a &amp;&amp; b` or `x &lt; 5`',
				'</details>'
			].join('\n')
		);

		const codes = container.querySelectorAll('code');
		const codeTexts = [...codes].map((el) => el.textContent);
		expect(
			codeTexts.some((t) => t?.includes('a && b')),
			'should decode &amp;&amp; in code'
		).toBe(true);
		expect(
			codeTexts.some((t) => t?.includes('x < 5')),
			'should decode &lt; in code'
		).toBe(true);
	});

	it('multiple reasoning paragraphs render as separate blockquotes', async () => {
		const container = await renderMarkdown(
			[
				'<details type="reasoning" done="true" duration="1.0">',
				'<summary>Thought for 1.0 seconds</summary>',
				'&gt; First paragraph.',
				'',
				'&gt; Second paragraph.',
				'</details>'
			].join('\n')
		);

		const blockquotes = container.querySelectorAll('blockquote');
		expect(blockquotes.length, 'each paragraph block → separate blockquote').toBe(2);
	});

	it('empty details (web_search) renders without content', async () => {
		const container = await renderMarkdown(
			['<details type="web_search">', '<summary>Searched the web</summary>', '</details>'].join(
				'\n'
			)
		);

		const blockquotes = container.querySelectorAll('blockquote');
		expect(blockquotes.length, 'no content → no blockquotes').toBe(0);
	});

	it('summary tag never appears as visible text', async () => {
		const container = await renderMarkdown(
			[
				'<details type="reasoning" done="true" duration="1.8">',
				'<summary>Thought for 1.8 seconds</summary>',
				'&gt; some reasoning',
				'</details>'
			].join('\n')
		);

		const text = container.textContent ?? '';
		expect(text, '<summary> tag must not leak into rendered text').not.toContain('<summary>');
		expect(text).not.toContain('</summary>');
	});

	it('reasoning with bracket references and html entities does not crash', async () => {
		const container = await renderMarkdown(
			[
				'<details type="reasoning" done="true" duration="5.0">',
				'<summary>Thought for 5.0 seconds</summary>',
				'&gt; **Searching for clarification**',
				'&gt; ',
				'&gt; I need to find official documents. I&#x27;ll search for the &quot;MiniMax Agent&quot; product.',
				'&gt; It&#x27;s important to confirm whether the coding plan includes the agent.',
				'</details>'
			].join('\n')
		);

		const text = container.textContent ?? '';
		expect(text).toContain('Searching for clarification');
		expect(text).not.toContain('<summary>');
	});

	it('empty reasoning (no content after summary) does not leak summary tag', async () => {
		const container = await renderMarkdown(
			[
				'<details type="reasoning" done="true" duration="1.8">',
				'<summary>Thought for 1.8 seconds</summary>',
				'</details>'
			].join('\n')
		);

		const text = container.textContent ?? '';
		expect(text, '<summary> tag must not leak into rendered text').not.toContain('<summary>');
	});
});
