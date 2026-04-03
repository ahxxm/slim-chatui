<script lang="ts">
	import Sortable from 'sortablejs';

	import { onDestroy, tick } from 'svelte';

	import { chatId, mobile, models, settings, showSidebar } from '$lib/stores';
	import { updateUserSettings } from '$lib/apis/users';
	import PinnedModelItem from './PinnedModelItem.svelte';

	let { selectedChatId = $bindable(null), shiftKey = false } = $props();

	let pinnedModels: string[] = $state([]);
	let sortable: Sortable | null = $state(null);

	const destroyPinnedModelsSortable = () => {
		sortable?.destroy();
		sortable = null;
	};

	const initPinnedModelsSortable = () => {
		const pinnedModelsList = document.getElementById('pinned-models-list');
		destroyPinnedModelsSortable();

		if (pinnedModelsList && !$mobile) {
			sortable = new Sortable(pinnedModelsList, {
				animation: 150,
				onUpdate: async (event) => {
					const modelId = event.item.dataset.id;
					const newIndex = event.newIndex;
					const currentPinnedModels = (($settings?.pinnedModels ?? []) as string[]).slice();
					const oldIndex = currentPinnedModels.indexOf(modelId);

					if (oldIndex === -1 || newIndex == null) {
						return;
					}

					currentPinnedModels.splice(oldIndex, 1);
					currentPinnedModels.splice(newIndex, 0, modelId);

					const nextSettings = { ...$settings, pinnedModels: currentPinnedModels };
					settings.set(nextSettings);
					await updateUserSettings(localStorage.token, { ui: nextSettings });
				}
			});
		}
	};

	$effect(() => {
		pinnedModels = ($settings?.pinnedModels ?? []) as string[];
	});

	$effect(() => {
		pinnedModels.length;
		$mobile;

		(async () => {
			await tick();
			initPinnedModelsSortable();
		})();
	});

	onDestroy(() => {
		destroyPinnedModelsSortable();
	});
</script>

<div class="mt-0.5 pb-1.5" id="pinned-models-list">
	{#each pinnedModels as modelId (modelId)}
		{@const model = $models.find((model) => model.id === modelId)}
		{#if model}
			<PinnedModelItem
				{model}
				{shiftKey}
				onClick={() => {
					selectedChatId = null;
					chatId.set('');
					if ($mobile) {
						showSidebar.set(false);
					}
				}}
				onUnpin={(($settings?.pinnedModels ?? []) as string[]).includes(modelId)
					? () => {
							const pinnedModels = ($settings.pinnedModels as string[]).filter(
								(id: string) => id !== modelId
							);
							const nextSettings = { ...$settings, pinnedModels };
							settings.set(nextSettings);
							updateUserSettings(localStorage.token, { ui: nextSettings });
						}
					: null}
			/>
		{/if}
	{/each}
</div>
