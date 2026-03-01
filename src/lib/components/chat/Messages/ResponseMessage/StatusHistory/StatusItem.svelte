<script>
	import { getContext } from 'svelte';
	const i18n = getContext('i18n');

	export let status = null;
	export let done = false;
</script>

{#if !status?.hidden}
	<div class="status-description flex items-center gap-2 py-0.5 w-full text-left">
		<div class="flex flex-col justify-center -space-y-0.5">
			<div
				class="{(done || status?.done) === false
					? 'shimmer'
					: ''} text-gray-500 dark:text-gray-500 text-base line-clamp-1 text-wrap"
			>
				{#if status?.description?.includes('{{searchQuery}}')}
					{$i18n.t(status?.description, {
						searchQuery: status?.query
					})}
				{:else}
					{status?.description}
				{/if}
			</div>
		</div>
	</div>
{/if}
