// @vitest-environment jsdom
/**
 * Regression test for chat list disappearing after rapid deletes.
 *
 * Bug: user has 10 chats, shift-deletes 2 in quick succession, all chats
 * vanish from the sidebar until page refresh. Backend is fine — it returns
 * the correct 8 chats. The problem is entirely in the frontend.
 *
 * How it happens:
 *   1. Each delete triggers initChatList(), which refetches the full chat list.
 *   2. initChatList sets currentChatPage=1 up front, but reads $currentChatPage
 *      much later (after two sequential awaits for tags and pinned chats).
 *   3. When the first initChatList completes, it sets scrollPaginationEnabled=true.
 *      The infinite-scroll Loader sees this, fires loadMoreChats(), which bumps
 *      currentChatPage to 2.
 *   4. The second initChatList then reads $currentChatPage=2 for its getChatList
 *      call. Page 2 is empty (all 8 chats fit on page 1). chats.set([]).
 *
 * This test renders the real Sidebar component, proxies fetch to the real
 * FastAPI backend, and clicks real trash buttons. No application logic is
 * reimplemented.
 */
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';
import { writable, get } from 'svelte/store';
import { signIn, installFetchProxy } from '$lib/test/backend';

// ── SvelteKit stubs (virtual modules not available in vitest) ────────────────

vi.mock('$app/environment', () => ({ browser: true, dev: false }));
vi.mock('$app/navigation', () => ({ goto: vi.fn(), afterNavigate: vi.fn() }));
vi.mock('$app/stores', () => ({
	page: {
		subscribe: vi.fn((cb: any) => {
			cb({ url: new URL('http://localhost'), params: {} });
			return () => {};
		})
	},
	navigating: {
		subscribe: vi.fn((cb: any) => {
			cb(null);
			return () => {};
		})
	}
}));

// Sidebar imports these but they're not relevant to the chat list race
vi.mock('$lib/apis/folders', () => ({
	createNewFolder: vi.fn(),
	getFolders: vi.fn().mockResolvedValue([]),
	updateFolderParentIdById: vi.fn()
}));
vi.mock('$lib/apis/tasks', () => ({
	checkActiveChats: vi.fn().mockResolvedValue({ active_chat_ids: [] })
}));

import { render, fireEvent, cleanup } from '@testing-library/svelte';
import {
	chats,
	pinnedChats,
	tags,
	currentChatPage,
	scrollPaginationEnabled,
	showSidebar,
	user
} from '$lib/stores';

// Artificial per-request delay so initChatList's multi-fetch chain takes
// long enough for IntersectionObserver ticks (100ms) to interleave
const NET = 50;
const SETTLE = NET * 8;
const CLICK_GAP = NET * 2;

const delay = (ms: number) => new Promise((r) => setTimeout(r, ms));

// ── Store setup ──────────────────────────────────────────────────────────────
// Minimal store state so the component renders: user logged in, sidebar open.
// Chat list is NOT seeded — Sidebar's initChatList fetches from the real backend.

function seedStores() {
	user.set({
		id: '1',
		name: 'Admin',
		email: 'admin@localhost',
		role: 'admin',
		profile_image_url: ''
	} as any);
	showSidebar.set(true);
	pinnedChats.set([]);
	tags.set([]);
	currentChatPage.set(1);
	scrollPaginationEnabled.set(true);
}

// ── Tests ────────────────────────────────────────────────────────────────────

describe('Sidebar: shift-delete race', () => {
	beforeEach(async () => {
		// The Loader component uses IntersectionObserver to repeatedly dispatch
		// on:visible every 100ms while it's in the viewport. This mock assumes
		// the Loader is always visible (10 chats easily fit on screen).
		vi.stubGlobal(
			'IntersectionObserver',
			class {
				cb: any;
				iv: any;
				constructor(cb: any) {
					this.cb = cb;
				}
				observe(el: Element) {
					this.iv = setInterval(() => {
						this.cb([{ isIntersecting: true, target: el }]);
					}, 100);
				}
				unobserve() {
					clearInterval(this.iv);
				}
				disconnect() {
					clearInterval(this.iv);
				}
			}
		);

		// jsdom lacks Web Animations API
		Element.prototype.animate ??= function () {
			return { onfinish: null, cancel() {}, finished: Promise.resolve() } as any;
		};

		// Sidebar's onMount reads this to decide whether to show + call initChatList
		localStorage.setItem('sidebar', 'true');

		const token = await signIn();
		localStorage.setItem('token', token);
		installFetchProxy(token, NET);

		// Clean slate: delete all chats, then seed 10
		await fetch('/api/v1/chats/', { method: 'DELETE' });
		for (let i = 0; i < 10; i++) {
			await fetch('/api/v1/chats/new', {
				method: 'POST',
				body: JSON.stringify({ chat: { title: `Chat ${i}`, messages: [] } })
			});
		}

		seedStores();
	});

	afterEach(() => {
		cleanup();
		vi.restoreAllMocks();
	});

	it('shift-delete 2 of 10 → should still show 8 chats', async () => {
		const { default: Sidebar } = await import('$lib/components/layout/Sidebar.svelte');
		const { container } = render(Sidebar, {
			context: new Map([['i18n', writable({ t: (k: string) => k })]])
		});

		// Sidebar's showSidebar subscription calls initChatList on mount;
		// wait for that plus loadMoreChats to fully settle
		await delay(SETTLE);

		const chatLinks = container.querySelectorAll('a[href^="/c/"]');
		expect(chatLinks.length, `expected 10 chats after mount, got ${chatLinks.length}`).toBe(10);

		// Sidebar syncs shiftKey from window keydown/mousemove events;
		// ChatItem shows the trash button only when shiftKey && mouseOver
		await fireEvent.keyDown(window, { key: 'Shift', shiftKey: true });
		await fireEvent.mouseMove(window, { shiftKey: true });

		const allChatLinks = () => [...container.querySelectorAll('a[href^="/c/"]')];

		const shiftDeleteChat = async (index: number) => {
			const links = allChatLinks();
			const link = links[index];
			expect(link, `chat at index ${index} should be in the DOM`).toBeTruthy();
			await fireEvent.mouseEnter(link!);
			const trash = link!.closest('li, div')?.querySelector('[aria-label="Delete chat"]');
			expect(trash, `shift+hover should reveal trash on chat ${index}`).toBeTruthy();
			await fireEvent.click(trash!);
		};

		await shiftDeleteChat(0);
		await delay(CLICK_GAP);
		await shiftDeleteChat(0); // after first delete, next chat is now index 0
		await delay(SETTLE);

		const result = get(chats) as any[] | null;
		expect(result).not.toBeNull();
		expect(result!.length, `expected 8 chats, got ${result!.length}`).toBe(8);
	}, 15000);
});
