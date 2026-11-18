// @vitest-environment jsdom
/**
 * Deleting the chat you're currently in (new chat's first conversation, or
 * clicked into from the sidebar) must send you home: goto('/') + chatId
 * cleared + the sidebar list refreshed. Deleting some other chat must not
 * navigate. The chatListRace test covers the list race with no active chat;
 * it can't see this because $chatId is never the deleted chat there.
 */
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';
import { writable, get } from 'svelte/store';
import { signIn, installFetchProxy, flushFetches } from '#lib/test/backend.js';
import type { Mock } from 'vitest';

// ── SvelteKit stubs (virtual modules not available in vitest) ────────────────

vi.mock('$app/env', () => ({ browser: true, dev: false, building: false, version: 'test' }));
vi.mock('$app/navigation', () => ({ goto: vi.fn(), afterNavigate: vi.fn() }));

// Sidebar imports these; irrelevant to delete navigation.
// The mock must provide every named export the component tree imports.
vi.mock('#lib/apis/folders/index.js', () => ({
	createNewFolder: vi.fn(),
	getFolders: vi.fn().mockResolvedValue([]),
	getFolderById: vi.fn(),
	updateFolderById: vi.fn(),
	updateFolderIsExpandedById: vi.fn(),
	deleteFolderById: vi.fn()
}));
vi.mock('#lib/apis/tasks/index.js', () => ({
	checkActiveChats: vi.fn().mockResolvedValue({ active_chat_ids: [] })
}));

import { render, fireEvent, cleanup } from '@testing-library/svelte';
import { waitFor } from '#lib/test/async.js';
import { goto } from '$app/navigation';
import {
	chats,
	chatId,
	pinnedChats,
	currentChatPage,
	scrollPaginationEnabled,
	showSidebar,
	user
} from '#lib/stores/index.js';

const gotoMock = goto as unknown as Mock;

function seedStores() {
	user.set({
		id: '1',
		name: 'Admin',
		email: 'admin@localhost',
		role: 'admin'
	} as any);
	showSidebar.set(true);
	pinnedChats.set([]);
	currentChatPage.set(1);
	scrollPaginationEnabled.set(true);
}

describe('Sidebar: delete active chat', () => {
	beforeEach(async () => {
		// The Loader only paginates here; three chats fit one page, so no
		// sentinel callback is needed.
		vi.stubGlobal(
			'IntersectionObserver',
			class {
				observe() {}
				unobserve() {}
				disconnect() {}
			}
		);
		Element.prototype.animate ??= function () {
			return { onfinish: null, cancel() {}, finished: Promise.resolve() } as any;
		};

		localStorage.setItem('sidebar', 'true');

		const token = await signIn();
		localStorage.setItem('token', token);
		installFetchProxy(token);

		await fetch('/api/v1/chats/', { method: 'DELETE' });
		for (const title of ['Alpha', 'Beta', 'Gamma']) {
			await fetch('/api/v1/chats/new', {
				method: 'POST',
				body: JSON.stringify({ chat: { title } })
			});
		}

		gotoMock.mockClear();
		seedStores();
	});

	afterEach(async () => {
		await flushFetches();
		cleanup();
		vi.restoreAllMocks();
	});

	const shiftDelete = async (chatLink: Element) => {
		await fireEvent.keyDown(window, { key: 'Shift', shiftKey: true });
		await fireEvent.mouseMove(window, { shiftKey: true });
		await fireEvent.mouseEnter(chatLink);
		const trash = chatLink.closest('li, div')?.querySelector('[aria-label="Delete chat"]');
		expect(trash, 'shift+hover should reveal trash button').toBeTruthy();
		await fireEvent.click(trash!);
	};

	const chatLinks = (container: HTMLElement) => [...container.querySelectorAll('a[href^="/c/"]')];
	const chatIdOf = (link: Element) => link.getAttribute('href')!.replace('/c/', '');

	it('deleting the active chat goes home: goto("/"), chatId cleared, list refreshed', async () => {
		const { default: Sidebar } = await import('#lib/components/layout/Sidebar.svelte');
		const { container } = render(Sidebar, {
			context: new Map([['i18n', writable({ t: (k: string) => k })]])
		});

		await waitFor(() => chatLinks(container).length === 3);
		const [alpha] = chatLinks(container);
		const activeId = chatIdOf(alpha);

		// Being "inside" Alpha: the state after clicking into a chat or after
		// a new chat's first message completes.
		await chatId.set(activeId);

		await shiftDelete(alpha);

		await waitFor(() => {
			const c = get(chats) as any[] | null;
			return c !== null && !c.some((chat: any) => chat.id === activeId);
		});

		expect(get(chatId), 'chatId store must be cleared').toBe('');
		expect(gotoMock).toHaveBeenCalledWith('/');

		const remaining = (get(chats) as any[]).map((c: any) => c.id);
		expect(remaining.length, 'other two chats survive').toBe(2);
		expect(remaining).not.toContain(activeId);
	}, 30000);

	it('deleting an inactive chat does not navigate', async () => {
		const { default: Sidebar } = await import('#lib/components/layout/Sidebar.svelte');
		const { container } = render(Sidebar, {
			context: new Map([['i18n', writable({ t: (k: string) => k })]])
		});

		await waitFor(() => chatLinks(container).length === 3);
		const [alpha, beta] = chatLinks(container);

		// Inside Alpha, deleting Beta must not touch the route.
		await chatId.set(chatIdOf(alpha));

		await shiftDelete(beta);

		await waitFor(() => {
			const c = get(chats) as any[] | null;
			return c !== null && !c.some((chat: any) => chat.id === chatIdOf(beta));
		});

		expect(gotoMock, 'must not navigate').not.toHaveBeenCalled();
		expect(get(chatId), 'chatId untouched').toBe(chatIdOf(alpha));
	}, 30000);
});
