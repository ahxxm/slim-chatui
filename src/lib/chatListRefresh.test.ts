// @vitest-environment jsdom
/**
 * Tests that refreshChatList fetches the right pages regardless of
 * what currentChatPage was inflated to.
 *
 * The bug: ad-hoc call sites did getChatList(token, $currentChatPage),
 * fetching a single stale page. loadMoreChats could inflate currentChatPage
 * beyond actual data (e.g., 3 with only 10 chats), and refreshChatList
 * would then waste requests on empty pages.
 */
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';
import { get } from 'svelte/store';
import { signIn, installFetchProxy } from '$lib/test/backend';

vi.mock('$app/environment', () => ({ browser: true, dev: false }));

import { chats, currentChatPage, refreshChatList } from '$lib/stores';
import { getChatList } from '$lib/apis/chats';

async function seedChats(n: number): Promise<void> {
	for (let i = 0; i < n; i++) {
		await fetch('/api/v1/chats/new', {
			method: 'POST',
			body: JSON.stringify({ chat: { title: `Chat ${i}`, messages: [] } })
		});
	}
}

describe('refreshChatList', () => {
	let token: string;
	beforeEach(async () => {
		token = await signIn();
		installFetchProxy(token);
		await fetch('/api/v1/chats/', { method: 'DELETE' });
		currentChatPage.set(1);
		chats.set([]);
	});

	afterEach(() => {
		vi.restoreAllMocks();
	});

	it('old buggy single-page fetch loses chats when currentChatPage > 1', async () => {
		await seedChats(62);
		currentChatPage.set(2);

		chats.set(await getChatList(token, get(currentChatPage)));

		expect(get(chats).length, 'only page 2 results').toBe(2);
	});

	it('fetches all chats across 2 pages', async () => {
		await seedChats(62);
		currentChatPage.set(2);

		await refreshChatList(token);

		expect(get(chats).length).toBe(62);
		expect(get(currentChatPage)).toBe(2);
	});

	it('deflates inflated currentChatPage to actual data boundary', async () => {
		await seedChats(10);
		currentChatPage.set(3);

		await refreshChatList(token);

		expect(get(chats).length).toBe(10);
		expect(get(currentChatPage), 'all fit on page 1').toBe(1);
	});

	it('handles empty chat list', async () => {
		currentChatPage.set(5);

		await refreshChatList(token);

		expect(get(chats).length).toBe(0);
		expect(get(currentChatPage)).toBe(1);
	});
}, 30000);
