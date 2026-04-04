<script lang="ts">
	import { getEmojiForShortCode } from '$lib/utils/emoji';

	let { shortCode, className = 'size-4' }: { shortCode: string; className?: string } = $props();

	let emoji = $derived(getEmojiForShortCode(shortCode));
</script>

{#if emoji}
	<span class={className} aria-label={shortCode}>{emoji}</span>
{:else}
	<div>
		{shortCode}
	</div>
{/if}
