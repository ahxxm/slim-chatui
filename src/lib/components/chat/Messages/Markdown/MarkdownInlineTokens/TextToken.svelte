<script lang="ts">
	import { fade } from 'svelte/transition';

	let { token, done = true } = $props();

	let texts = $derived((token?.raw ?? '').split(' '));
</script>

{#if done}
	{token?.raw}
{:else}
	{#each texts as text}
		<span class="" transition:fade={{ duration: 100 }}>
			{text}{' '}
		</span>
	{/each}
{/if}
