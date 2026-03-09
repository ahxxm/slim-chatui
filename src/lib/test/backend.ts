import { vi } from 'vitest';

const BACKEND = 'http://localhost:8081';

export async function signIn(): Promise<string> {
	const res = await globalThis.fetch(`${BACKEND}/api/v1/auths/signin`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ email: 'admin@localhost', password: 'admin' })
	});
	if (!res.ok) throw new Error(`signin failed: ${res.status} ${await res.text()}`);
	const { token } = await res.json();
	return token;
}

const delay = (ms: number) => new Promise((r) => setTimeout(r, ms));

let pending = new Set<Promise<unknown>>();

/** Wait for all in-flight proxied fetches (and any they spawn) to settle. */
export async function flushFetches() {
	const tick = () => new Promise((r) => setTimeout(r, 0));
	while (pending.size > 0) {
		await Promise.allSettled([...pending]);
		// Fetches completing can trigger new fetches via setTimeout (e.g.
		// IntersectionObserver → loadMoreChats). Give macrotasks a chance to fire.
		await tick();
	}
}

export function installFetchProxy(token: string, networkDelay = 0) {
	const realFetch = globalThis.fetch;
	pending = new Set();

	vi.stubGlobal(
		'fetch',
		vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
			let url = typeof input === 'string' ? input : input.toString();

			if (url.startsWith('/')) url = `${BACKEND}${url}`;

			const headers = new Headers(init?.headers);
			if (!headers.has('Authorization')) {
				headers.set('Authorization', `Bearer ${token}`);
			}
			if (!headers.has('Content-Type') && init?.body) {
				headers.set('Content-Type', 'application/json');
			}

			const promise = realFetch(url, { ...init, headers });
			const tracked =
				networkDelay > 0 ? promise.then((res) => delay(networkDelay).then(() => res)) : promise;

			const settled = tracked.finally(() => pending.delete(settled));
			pending.add(settled);
			return tracked;
		})
	);
}
