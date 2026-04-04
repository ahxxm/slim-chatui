<script lang="ts">
	import { type Snippet, getContext } from 'svelte';

	import { markdownRenderContextKey, type MarkdownRenderContextState } from './context';
	import DetailsHeader from './DetailsHeader.svelte';

	import Collapsible from '$lib/components/common/Collapsible.svelte';
	import { settings } from '$lib/stores';

	interface MarkdownDetailsBlockProps {
		openStateId: string;
		title?: string | null;
		attributes?: Record<string, string | undefined> | null;
		hasContent?: boolean;
		content?: Snippet;
	}

	let {
		openStateId,
		title = null,
		attributes = null,
		hasContent = false,
		content: body = undefined
	}: MarkdownDetailsBlockProps = $props();

	const markdownRenderContext = getContext<MarkdownRenderContextState | null>(
		markdownRenderContextKey
	);

	if (!markdownRenderContext) {
		throw new Error('MarkdownDetailsBlock requires markdown render context');
	}

	let renderDone = $derived(markdownRenderContext.done);
	let renderOpenStates = $derived(markdownRenderContext.openStates);
	let resolvedAttributes = $derived(
		renderDone && attributes?.done !== 'true' ? { ...attributes, done: 'true' } : attributes
	);

	const getOpenState = (defaultOpen: boolean): boolean =>
		renderOpenStates.get(openStateId) ?? defaultOpen;

	const setOpenState = (nextOpen: boolean) => {
		if (renderOpenStates.get(openStateId) !== nextOpen) {
			renderOpenStates.set(openStateId, nextOpen);
		}
	};
</script>

{#if hasContent}
	<Collapsible
		open={getOpenState($settings?.expandDetails ?? false)}
		chevron={true}
		className="w-full space-y-1"
		onChange={setOpenState}
	>
		<DetailsHeader {title} attributes={resolvedAttributes} />

		{#snippet content()}
			{@render body?.()}
		{/snippet}
	</Collapsible>
{:else}
	<Collapsible
		open={getOpenState(false)}
		chevron={true}
		disabled={true}
		className="w-full space-y-1"
		onChange={setOpenState}
	>
		<DetailsHeader {title} attributes={resolvedAttributes} />
	</Collapsible>
{/if}
