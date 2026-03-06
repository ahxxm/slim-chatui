<script>
	import { chatMarked } from '$lib/utils/marked/chat-marked';
	import { replaceTokens, processResponseContent } from '$lib/utils';
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

	let tokens = $derived(
		content
			? chatMarked.lexer(replaceTokens(processResponseContent(content), model?.name, $user?.name))
			: []
	);
</script>

{#key id}
	<MarkdownTokens
		{tokens}
		{id}
		{done}
		{save}
		{paragraphTag}
		{editCodeBlock}
		{sourceIds}
		{topPadding}
		{onTaskClick}
		{onSourceClick}
		{onSave}
	/>
{/key}
