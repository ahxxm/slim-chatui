<script lang="ts">
	import { fade } from 'svelte/transition';

	let { token, done = true } = $props();
	let rawText = $derived(token?.raw ?? '');
</script>

{#if done}
	{rawText}
{:else}
	<span transition:fade={{ duration: 100 }}>{rawText}</span>
{/if}
