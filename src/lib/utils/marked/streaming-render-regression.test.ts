// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { writable } from 'svelte/store';
import { tick } from 'svelte';
import { fireEvent, render } from '@testing-library/svelte';

vi.mock('$app/environment', () => ({ browser: true, dev: false }));

import { settings, user } from '$lib/stores';
import Markdown from '$lib/components/chat/Messages/Markdown.svelte';

const createContext = () => new Map([['i18n', writable({ t: (key: string) => key })]]);

beforeEach(() => {
	user.set({ id: '1', name: 'Test', email: 'test@test', role: 'user' } as any);
	settings.set({ expandDetails: false } as any);

	Element.prototype.animate ??= (() => ({
		finished: Promise.resolve(),
		cancel() {},
		play() {}
	})) as any;
});

describe('streaming markdown render regressions', () => {
	it('keeps a manually opened reasoning block open across streaming updates', async () => {
		const initialContent = [
			'<details type="reasoning" done="false" duration="0">',
			'<summary>Thinking</summary>',
			'&gt; one',
			'</details>',
			'',
			'tail'
		].join('\n');

		const updatedContent = [
			'<details type="reasoning" done="true" duration="1.3">',
			'<summary>Thought for 1.3 seconds</summary>',
			'&gt; one',
			'',
			'&gt; two',
			'</details>',
			'',
			'tail plus more'
		].join('\n');

		const view = render(Markdown, {
			props: { content: initialContent, id: 'reasoning-md', done: false },
			context: createContext()
		});
		await tick();

		const toggle = view.container.querySelector('.cursor-pointer');
		expect(toggle).toBeTruthy();
		await fireEvent.pointerUp(toggle!);
		await tick();

		expect(view.container.querySelectorAll('blockquote')).toHaveLength(1);

		await view.rerender({ content: updatedContent, id: 'reasoning-md', done: true });
		await tick();

		const blockquotes = [...view.container.querySelectorAll('blockquote')].map(
			(element) => element.textContent?.trim() ?? ''
		);

		expect(blockquotes).toEqual(['one', 'two']);
	});

	it('keeps a manually opened reasoning block open when earlier content reparses and shifts segment positions', async () => {
		const initialContent = [
			'prefix stays one paragraph before the reasoning block',
			'',
			'<details type="reasoning" done="false" duration="0">',
			'<summary>Thinking</summary>',
			'&gt; one',
			'</details>'
		].join('\n');

		const updatedContent = [
			'prefix becomes two paragraphs',
			'',
			'before the reasoning block',
			'',
			'<details type="reasoning" done="true" duration="1.3">',
			'<summary>Thought for 1.3 seconds</summary>',
			'&gt; one',
			'',
			'&gt; two',
			'</details>'
		].join('\n');

		const view = render(Markdown, {
			props: { content: initialContent, id: 'shifted-reasoning-md', done: false },
			context: createContext()
		});
		await tick();

		const toggle = view.container.querySelector('.cursor-pointer');
		expect(toggle).toBeTruthy();
		await fireEvent.pointerUp(toggle!);
		await tick();

		expect(view.container.querySelectorAll('blockquote')).toHaveLength(1);

		await view.rerender({
			content: updatedContent,
			id: 'shifted-reasoning-md',
			done: true
		});
		await tick();

		const blockquotes = [...view.container.querySelectorAll('blockquote')].map(
			(element) => element.textContent?.trim() ?? ''
		);

		expect(blockquotes).toEqual(['one', 'two']);
	});

	it('keeps a manually opened tool call block open when earlier content reparses and shifts segment positions', async () => {
		const initialContent = [
			'prefix stays one paragraph before the tool call block',
			'',
			'<details type="tool_calls" name="search_docs" arguments="{&quot;query&quot;:&quot;render glitch&quot;}" result="{&quot;status&quot;:&quot;ok&quot;}" done="true">',
			'</details>'
		].join('\n');

		const updatedContent = [
			'prefix becomes two paragraphs',
			'',
			'before the tool call block',
			'',
			'<details type="tool_calls" name="search_docs" arguments="{&quot;query&quot;:&quot;render glitch&quot;}" result="{&quot;status&quot;:&quot;ok&quot;}" done="true">',
			'</details>'
		].join('\n');

		const view = render(Markdown, {
			props: { content: initialContent, id: 'shifted-tool-call-md', done: true },
			context: createContext()
		});
		await tick();

		const toggle = view.container.querySelector('.cursor-pointer');
		expect(toggle).toBeTruthy();
		await fireEvent.pointerUp(toggle!);
		await tick();

		expect(view.container.textContent).toContain('Input');

		await view.rerender({
			content: updatedContent,
			id: 'shifted-tool-call-md',
			done: true
		});
		await tick();

		expect(view.container.textContent).toContain('Input');
		expect(view.container.textContent).toContain('render glitch');
	});

	it('re-renders a streamed partial markdown link into the final link instead of keeping stale text', async () => {
		const view = render(Markdown, {
			props: {
				content: 'Start [link](https://example.com/do',
				id: 'link-md',
				done: false
			},
			context: createContext()
		});
		await tick();

		await view.rerender({
			content: 'Start [link](https://example.com/docs) end',
			id: 'link-md',
			done: false
		});
		await tick();

		const link = view.container.querySelector('a');
		expect(link?.textContent).toBe('link');
		expect(link?.getAttribute('href')).toBe('https://example.com/docs');
		expect(view.container.textContent?.replace(/\s+/g, ' ').trim()).toBe('Start link end');
	});

	it('re-renders a streamed formatted markdown link label into the final link', async () => {
		const view = render(Markdown, {
			props: {
				content: 'combo [**label**](https://example.com/do',
				id: 'formatted-link-md',
				done: false
			},
			context: createContext()
		});
		await tick();

		await view.rerender({
			content: 'combo [**label**](https://example.com/docs)',
			id: 'formatted-link-md',
			done: false
		});
		await tick();

		const link = view.container.querySelector('a');
		expect(link?.textContent).toBe('label');
		expect(link?.getAttribute('href')).toBe('https://example.com/docs');
		expect(view.container.textContent?.replace(/\s+/g, ' ').trim()).toBe('combo label');
	});

	it('keeps the streamed text tail node stable while its content grows', async () => {
		const view = render(Markdown, {
			props: {
				content: 'alpha',
				id: 'text-tail-md',
				done: false
			},
			context: createContext()
		});
		await tick();

		const firstSpan = view.container.querySelector('span');
		expect(firstSpan?.textContent).toBe('alpha');

		await view.rerender({
			content: 'alpha beta',
			id: 'text-tail-md',
			done: false
		});
		await tick();

		const secondSpan = view.container.querySelector('span');
		expect(secondSpan).toBe(firstSpan);
		expect(secondSpan?.textContent).toBe('alpha beta');
	});
});
