<script>
	import { getContext } from 'svelte';
	const i18n = getContext('i18n');

	import StatusItem from './StatusHistory/StatusItem.svelte';
	let { statusHistory = [], expand = false } = $props();

	let showHistory = $state(true);

	$effect(() => {
		if (expand) {
			showHistory = true;
		} else {
			showHistory = false;
		}
	});

	let status = $derived(statusHistory && statusHistory.length > 0 ? statusHistory.at(-1) : null);
</script>

{#if statusHistory && statusHistory.length > 0}
	{#if status?.hidden !== true}
		<div class="text-sm flex flex-col w-full">
			<button
				class="w-full"
				aria-label={$i18n.t('Toggle status history')}
				aria-expanded={showHistory}
				onclick={() => {
					showHistory = !showHistory;
				}}
			>
				<div class="flex items-start gap-2">
					<StatusItem {status} />
				</div>
			</button>

			{#if showHistory}
				<div class="flex flex-row">
					{#if statusHistory.length > 1}
						<div class="w-full">
							{#each statusHistory as status, idx}
								<div class="flex items-stretch gap-2 mb-1">
									<div class=" ">
										<div class="pt-3 px-1 mb-1.5">
											<span class="relative flex size-1.5 rounded-full justify-center items-center">
												<span
													class="relative inline-flex size-1.5 rounded-full bg-gray-500 dark:bg-gray-400"
												></span>
											</span>
										</div>
										{#if idx !== statusHistory.length - 1}
											<div
												class="w-[0.5px] ml-[6.5px] h-[calc(100%-14px)] bg-gray-300 dark:bg-gray-700"
											/>
										{/if}
									</div>

									<StatusItem {status} done={true} />
								</div>
							{/each}
						</div>
					{/if}
				</div>
			{/if}
		</div>
	{/if}
{/if}
