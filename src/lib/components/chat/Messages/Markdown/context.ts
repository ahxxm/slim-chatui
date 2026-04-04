import type { Links } from 'marked';
import type { SvelteMap } from 'svelte/reactivity';

export const markdownRenderContextKey = Symbol('markdown-render-context');

export interface MarkdownRenderContextState {
	done: boolean;
	save: boolean;
	paragraphTag: 'p' | 'span';
	editCodeBlock: boolean;
	topPadding: boolean;
	sourceIds: string[];
	onSave: (value: unknown) => void;
	onTaskClick: (value: unknown) => void;
	onSourceClick: (value: unknown) => void;
	links: Links;
	openStates: SvelteMap<string, boolean>;
	incremental: boolean;
}
