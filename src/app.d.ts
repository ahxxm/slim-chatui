import type { i18n } from 'i18next';
import type { Writable } from 'svelte/store';

// See https://kit.svelte.dev/docs/types#app
// for information about these interfaces
declare global {
	namespace App {
		// interface Error {}
		// interface Locals {}
		// interface PageData {}
		// interface Platform {}
	}

	interface Window {
		applyTheme?: () => void;
		electronAPI?: {
			send(data: Record<string, unknown>): Promise<any>;
		};
	}
}

declare module 'svelte' {
	export function getContext(key: 'i18n'): Writable<i18n>;
}

export {};
