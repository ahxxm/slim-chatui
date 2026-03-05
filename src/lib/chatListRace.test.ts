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
 * This test renders the real Sidebar component, mocks fetch with realistic
 * latency, and clicks real trash buttons. No application logic is reimplemented.
 */
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';
import { writable, get } from 'svelte/store';

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

// ── Timing constants ─────────────────────────────────────────────────────────

// Simulated network latency per request
const NET = 50;

// Backend returns 60 chats per page; with 10 chats, page 2 is always empty
const PAGE_SIZE = 60;

// Time for async chains to fully resolve (delete + tags + initChatList's 3 fetches + buffer)
const SETTLE = NET * 8;

// Delay between the two delete clicks. Must exceed NET so the first initChatList
// completes (and triggers loadMoreChats) before the second one reads currentChatPage.
const CLICK_GAP = NET * 2;

const delay = (ms: number) => new Promise((r) => setTimeout(r, ms));

// ── Mock server ──────────────────────────────────────────────────────────────
// Minimal in-memory backend: holds chats, handles DELETE and paginated GET.
// Every response is delayed by NET to simulate real network round-trips.

const serverChats = new Map<string, any>();

function seedServer(n: number) {
	serverChats.clear();
	for (let i = 0; i < n; i++) {
		serverChats.set(`chat-${i}`, {
			id: `chat-${i}`,
			title: `Chat chat-${i}`,
			updated_at: Math.floor(Date.now() / 1000) - i * 60
		});
	}
}

function handleRequest(url: string, method: string): { status: number; body: any } {
	if (method === 'DELETE') {
		const id = url.split('/chats/')[1];
		serverChats.delete(id);
		return { status: 200, body: true };
	}
	if (url.includes('/tags')) return { status: 200, body: [] };
	if (url.includes('/pinned') || url.includes('include_pinned')) return { status: 200, body: [] };
	if (url.includes('/folders')) return { status: 200, body: [] };
	if (url.includes('/active')) return { status: 200, body: { active_chat_ids: [] } };
	if (url.includes('/chats')) {
		const params = new URL(url, 'http://localhost').searchParams;
		const page = params.get('page') ? parseInt(params.get('page')!) : null;
		const items = [...serverChats.values()];
		if (page !== null) {
			const skip = (page - 1) * PAGE_SIZE;
			return { status: 200, body: items.slice(skip, skip + PAGE_SIZE) };
		}
		return { status: 200, body: items };
	}
	return { status: 404, body: { detail: 'not found' } };
}

function installMockFetch() {
	vi.stubGlobal(
		'fetch',
		vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
			const url = typeof input === 'string' ? input : input.toString();
			const { status, body } = handleRequest(url, init?.method ?? 'GET');
			return delay(NET).then(
				() =>
					new Response(JSON.stringify(body), {
						status,
						headers: { 'content-type': 'application/json' }
					})
			);
		})
	);
}

// ── Store setup ──────────────────────────────────────────────────────────────
// Mimics the app state after initial page load: user logged in, sidebar open,
// 10 chats visible, pagination enabled.

function seedStores() {
	user.set({
		id: '1',
		name: 'Admin',
		email: 'a@test.com',
		role: 'admin',
		profile_image_url: ''
	} as any);
	showSidebar.set(true);
	chats.set([...serverChats.values()].map((c) => ({ ...c, time_range: 'Today' })));
	pinnedChats.set([]);
	tags.set([]);
	currentChatPage.set(1);
	scrollPaginationEnabled.set(true);
}

// ── Tests ────────────────────────────────────────────────────────────────────

describe('Sidebar: shift-delete race', () => {
	beforeEach(() => {
		seedServer(10);

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

		localStorage.setItem('token', 'test-token');
		localStorage.setItem('sidebar', 'true');

		installMockFetch();
		seedStores();
	});

	afterEach(() => {
		cleanup();
		vi.restoreAllMocks();
	});

	it(
		'shift-delete 2 of 10 → should still show 8 chats',
		async () => {
			const { default: Sidebar } = await import('$lib/components/layout/Sidebar.svelte');
			const { container } = render(Sidebar, {
				context: new Map([['i18n', writable({ t: (k: string) => k })]])
			});

			// Sidebar's showSidebar subscription calls initChatList on mount;
			// wait for that plus loadMoreChats to fully settle
			await delay(SETTLE);

			const findChatLink = (id: string) => container.querySelector(`a[href="/c/${id}"]`);
			expect(findChatLink('chat-0'), 'chat-0 should be rendered').toBeTruthy();
			expect(findChatLink('chat-9'), 'chat-9 should be rendered').toBeTruthy();

			// Sidebar syncs shiftKey from window keydown/mousemove events;
			// ChatItem shows the trash button only when shiftKey && mouseOver
			await fireEvent.keyDown(window, { key: 'Shift', shiftKey: true });
			await fireEvent.mouseMove(window, { shiftKey: true });

			const shiftDeleteChat = async (id: string) => {
				const link = findChatLink(id);
				expect(link, `${id} should be in the DOM`).toBeTruthy();
				await fireEvent.mouseEnter(link!);
				const trash = link!.closest('li, div')?.querySelector('[aria-label="Delete chat"]');
				expect(trash, `shift+hover should reveal trash on ${id}`).toBeTruthy();
				await fireEvent.click(trash!);
			};

			await shiftDeleteChat('chat-0');
			await delay(CLICK_GAP);
			await shiftDeleteChat('chat-1');
			await delay(SETTLE);

			const result = get(chats) as any[] | null;
			expect(result).not.toBeNull();
			expect(result!.length, `expected 8 chats, got ${result!.length}`).toBe(8);
		},
		15000
	);
});
