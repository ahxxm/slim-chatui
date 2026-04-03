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
});
