<script lang="ts">
	import { type Snippet, setContext, untrack } from 'svelte';

	import { markdownDetailsScopeContextKey, type MarkdownDetailsScopeState } from './context';

	interface MarkdownDetailsScopeProps {
		scopeId: string;
		children?: Snippet;
	}

	let { scopeId, children = undefined }: MarkdownDetailsScopeProps = $props();

	let detailsScope = $state<MarkdownDetailsScopeState>({ id: untrack(() => scopeId) });

	setContext(markdownDetailsScopeContextKey, detailsScope);

	$effect(() => {
		detailsScope.id = scopeId;
	});
</script>

{@render children?.()}
