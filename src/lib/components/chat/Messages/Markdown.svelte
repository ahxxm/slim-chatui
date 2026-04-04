<script lang="ts">
	import type { Links } from 'marked';
	import { SvelteMap } from 'svelte/reactivity';

	import { replaceTokens, processResponseContent } from '$lib/utils';
	import {
		EMPTY_LINKS,
		createIncrementalTokenState,
		getRenderSegments,
		updateIncrementalTokenState,
		type IncrementalTokenSegment
	} from '$lib/utils/marked/incremental';
	import { createIndexedDetailsStateIds } from '$lib/utils/marked/details-state';
	import { user } from '$lib/stores';

	import MarkdownTokens from './Markdown/MarkdownTokens.svelte';

	interface MarkdownModel {
		name?: string | null;
	}

	interface RenderSegmentMetadata {
		key: string;
		rootDetailsStateId: string | null;
	}

	interface MarkdownProps {
		id?: string;
		content?: string | null;
		done?: boolean;
		model?: MarkdownModel | null;
		save?: boolean;
		paragraphTag?: 'p' | 'span';
		editCodeBlock?: boolean;
		topPadding?: boolean;
		sourceIds?: string[];
		onSave?: (value: unknown) => void;
		onSourceClick?: (value: unknown) => void;
		onTaskClick?: (value: unknown) => void;
	}

	let {
		id = '',
		content,
		done = true,
		model = null,
		save = false,
		paragraphTag = 'p',
		editCodeBlock = true,
		topPadding = false,
		sourceIds = [],
		onSave = () => {},
		onSourceClick = () => {},
		onTaskClick = () => {}
	}: MarkdownProps = $props();

	let normalizedContent = $derived(
		content
			? replaceTokens(processResponseContent(content), model?.name ?? '', $user?.name ?? '')
			: ''
	);

	let blockState = createIncrementalTokenState('block');
	let currentMessageId = '';
	let openStates = new SvelteMap<string, boolean>();
	let renderSegments = $state<IncrementalTokenSegment[]>(getRenderSegments(blockState));
	let renderSegmentMetadata = $state<RenderSegmentMetadata[]>([]);
	let links = $state<Links>(EMPTY_LINKS);

	const createRenderSegmentMetadata = (
		messageId: string,
		segments: IncrementalTokenSegment[]
	): RenderSegmentMetadata[] => {
		if (!segments.some((segment) => segment.tokens[0]?.type === 'details')) {
			return segments.map((segment) => ({
				key: `${messageId}-${segment.id}`,
				rootDetailsStateId: null
			}));
		}

		const detailsStateIds = createIndexedDetailsStateIds(
			segments,
			(segment) => segment.tokens[0],
			messageId
		);

		return segments.map((segment, segmentIndex) => {
			const rootDetailsStateId = detailsStateIds.get(segmentIndex) ?? null;

			return {
				key: rootDetailsStateId ?? `${messageId}-${segment.id}`,
				rootDetailsStateId
			};
		});
	};

	$effect(() => {
		const nextMessageId = id;
		const nextContent = normalizedContent;

		if (nextMessageId !== currentMessageId) {
			currentMessageId = nextMessageId;
			blockState = createIncrementalTokenState('block');
			openStates.clear();
		}

		blockState = updateIncrementalTokenState(blockState, nextContent);
		const nextRenderSegments = getRenderSegments(blockState);
		renderSegments = nextRenderSegments;
		renderSegmentMetadata = createRenderSegmentMetadata(nextMessageId, nextRenderSegments);
		links = blockState.links;
	});
</script>

{#key id}
	{#each renderSegments as segment, segmentIndex (renderSegmentMetadata[segmentIndex]?.key ?? `${id}-${segmentIndex}`)}
		<MarkdownTokens
			id={renderSegmentMetadata[segmentIndex]?.key ?? `${id}-${segmentIndex}`}
			tokens={segment.tokens}
			{done}
			{save}
			{paragraphTag}
			{editCodeBlock}
			{sourceIds}
			{topPadding}
			{onTaskClick}
			{onSourceClick}
			{onSave}
			{links}
			{openStates}
			detailsScopeId={id}
			rootDetailsStateId={renderSegmentMetadata[segmentIndex]?.rootDetailsStateId ?? null}
			incremental={true}
		/>
	{/each}
{/key}
