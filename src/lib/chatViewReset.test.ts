// @vitest-environment jsdom
/**
 * The live Chat instance must reset its view when the router keeps it
 * mounted instead of remounting. That happens after a new chat's first
 * message does goto('/c/{id}', { shallow: true }): the URL moves, the
 * '/'-page's instance stays, and a later goto('/') lands on the same page
 * component class, so onMount/initNewChat never run. Two flows enter that
 * state: shift-deleting the open chat (deleteChatHandler clears $chatId
 * after its goto) and "New Chat" (the sidebar fires goto('/') unawaited,
 * so the URL still shows /c/{id} when the handler runs). The store
 * transition is the only signal the live instance gets.
 *
 * The send flow needs an LLM, so the tests load the seeded chat through
 * chatIdProp instead and park the URL at /c/{id} with pushState — the
 * instance is live and holds the conversation either way.
 */
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';
import { writable } from 'svelte/store';
import type { Mock } from 'vitest';
import { signIn, installFetchProxy, flushFetches } from '#lib/test/backend.js';

vi.mock('$app/env', () => ({ browser: true, dev: false, building: false, version: 'test' }));
vi.mock('$app/navigation', () => ({ goto: vi.fn(), afterNavigate: vi.fn() }));
vi.mock('$app/state', () => ({
	page: { url: new URL('http://localhost/'), params: {}, state: {}, data: {}, route: { id: null } }
}));

import { render, cleanup, fireEvent } from '@testing-library/svelte';
import { waitFor } from '#lib/test/async.js';
import { goto } from '$app/navigation';
import {
	chatId,
	pinnedChats,
	currentChatPage,
	scrollPaginationEnabled,
	showSidebar,
	user
} from '#lib/stores/index.js';

const gotoMock = goto as unknown as Mock;
const REPLY = 'repro reply visible on screen';

async function seedChat() {
	const now = Math.floor(Date.now() / 1000);
	const res = await fetch('/api/v1/chats/new', {
		method: 'POST',
		body: JSON.stringify({
			chat: {
				title: 'Repro delete-me',
				history: {
					messages: {
						u1: { id: 'u1', parentId: null, childrenIds: ['a1'], role: 'user', content: 'hello repro', timestamp: now },
						a1: {
							id: 'a1', parentId: 'u1', childrenIds: [], role: 'assistant',
							content: REPLY, modelName: 'mock', timestamp: now
						}
					},
					currentId: 'a1'
				}
			}
		})
	});
	return (await res.json()) as { id: string };
}

// Minimal store state for the component trees to render.
function seedStores() {
	user.set({ id: '1', name: 'Admin', email: 'admin@localhost', role: 'admin' } as any);
	showSidebar.set(true);
	pinnedChats.set([]);
	currentChatPage.set(1);
	scrollPaginationEnabled.set(true);
}

const i18nContext = () => new Map([['i18n', writable({ t: (k: string) => k })]]);

describe('Chat: live view reset', () => {
	beforeEach(async () => {
		Element.prototype.animate ??= function () {
			return { onfinish: null, cancel() {}, finished: Promise.resolve() } as any;
		};
		Element.prototype.scrollTo ??= function () {};

		const token = await signIn();
		localStorage.setItem('token', token);
		installFetchProxy(token);

		await fetch('/api/v1/chats/', { method: 'DELETE' });

		chatId.set('');
		gotoMock.mockClear();
	});

	afterEach(async () => {
		await flushFetches();
		cleanup();
		vi.restoreAllMocks();
		history.pushState({}, '', '/');
	});

	it('chatId cleared on a mounted Chat clears the conversation from the screen', async () => {
		const chat = await seedChat();

		const { default: Chat } = await import('#lib/components/chat/Chat.svelte');
		const { container } = render(Chat, {
			props: { chatIdProp: chat.id },
			context: i18nContext()
		});

		await waitFor(() => container.textContent?.includes(REPLY) ?? false, 15000);

		// Exactly what deleteChatHandler does after goto('/').
		await chatId.set('');

		await waitFor(() => !(container.textContent?.includes(REPLY) ?? true), 5000);
		expect(container.textContent).not.toContain(REPLY);
	}, 30000);

	it('New Chat from an open chat clears the conversation from the screen', async () => {
		const chat = await seedChat();

		// The URL the shallow goto left behind: /c/{id} while the
		// '/'-page's Chat instance holds the conversation.
		history.pushState({}, '', `/c/${chat.id}`);

		const { default: Chat } = await import('#lib/components/chat/Chat.svelte');
		const { container: chatContainer } = render(Chat, {
			props: { chatIdProp: chat.id },
			context: i18nContext()
		});

		await waitFor(() => chatContainer.textContent?.includes(REPLY) ?? false, 15000);

		seedStores();
		localStorage.setItem('sidebar', 'true');
		// The Loader only paginates here; one chat needs no sentinel.
		vi.stubGlobal(
			'IntersectionObserver',
			class {
				observe() {}
				unobserve() {}
				disconnect() {}
			}
		);

		const { default: Sidebar } = await import('#lib/components/layout/Sidebar.svelte');
		render(Sidebar, { context: i18nContext() });

		// The hidden button the NEW_CHAT shortcut clicks: goto('/') then
		// newChatHandler(), with the goto still in flight.
		const newChatButton = document.getElementById('sidebar-new-chat-button');
		expect(newChatButton).toBeTruthy();
		await fireEvent.click(newChatButton!);

		expect(gotoMock).toHaveBeenCalledWith('/');

		await waitFor(() => !(chatContainer.textContent?.includes(REPLY) ?? true), 5000);
		expect(chatContainer.textContent).not.toContain(REPLY);
	}, 30000);
});
