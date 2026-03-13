<script lang="ts">
	import { shortCodesToEmojis, codePointToEmoji } from '$lib/stores';

	let { shortCode, className = 'size-4' }: { shortCode: string; className?: string } = $props();
</script>

{#if $shortCodesToEmojis[shortCode]}
	<span class={className} aria-label={shortCode}
		>{codePointToEmoji($shortCodesToEmojis[shortCode])}</span
	>
{:else}
	<div>
		{shortCode}
	</div>
{/if}
