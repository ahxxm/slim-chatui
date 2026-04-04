<script lang="ts">
	let { token, done = true } = $props();
	let rawText = $derived(token?.raw ?? '');
</script>

{#if done}
	{rawText}
{:else}
	<span>{rawText}</span>
{/if}
