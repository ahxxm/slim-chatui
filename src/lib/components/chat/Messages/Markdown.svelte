<script>
	// @ts-nocheck
	import { replaceTokens, processResponseContent } from '$lib/utils';
	import {
		EMPTY_LINKS,
		createIncrementalTokenState,
		getRenderSegments,
		updateIncrementalTokenState
	} from '$lib/utils/marked/incremental';
	import { user } from '$lib/stores';

	import MarkdownTokens from './Markdown/MarkdownTokens.svelte';

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
	} = $props();

	let normalizedContent = $derived(
		content
			? replaceTokens(processResponseContent(content), model?.name ?? '', $user?.name ?? '')
			: ''
	);

	let blockState = createIncrementalTokenState('block');
	let currentMessageId = '';
	let renderSegments = $state(getRenderSegments(blockState));
	let links = $state(EMPTY_LINKS);

	const getSegmentIdentity = (messageId, segmentIndex, segment) => {
		const token = segment?.tokens?.[0];
		const detailType = token?.type === 'details' ? token?.attributes?.type ?? 'details' : token?.type;
		return `${messageId}-${segmentIndex}-${detailType ?? 'unknown'}`;
	};

	$effect(() => {
		const nextMessageId = id;
		const nextContent = normalizedContent;

		if (nextMessageId !== currentMessageId) {
			currentMessageId = nextMessageId;
			blockState = createIncrementalTokenState('block');
		}

		blockState = updateIncrementalTokenState(blockState, nextContent);
		renderSegments = getRenderSegments(blockState);
		links = blockState.links;
	});
</script>

{#key id}
	{#each renderSegments as segment, segmentIndex (getSegmentIdentity(id, segmentIndex, segment))}
		<MarkdownTokens
			id={getSegmentIdentity(id, segmentIndex, segment)}
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
			incremental={true}
		/>
	{/each}
{/key}
