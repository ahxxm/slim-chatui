import type { Links } from 'marked';
import type { SvelteMap } from 'svelte/reactivity';

export const markdownDetailsScopeContextKey = Symbol('markdown-details-scope-context');
export const markdownRenderContextKey = Symbol('markdown-render-context');

export interface MarkdownDetailsScopeState {
	id: string;
}

export interface MarkdownRenderContextState {
	done: boolean;
	paragraphTag: 'p' | 'span';
	topPadding: boolean;
	sourceIds: string[];
	onTaskClick: (value: unknown) => void;
	onSourceClick: (value: unknown) => void;
	links: Links;
	openStates: SvelteMap<string, boolean>;
}
