<script lang="ts">
	import Sortable from 'sortablejs';

	import { onMount, tick } from 'svelte';

	import { chatId, config, mobile, models, settings, showSidebar } from '$lib/stores';
	import { WEBUI_BASE_URL } from '$lib/constants';
	import { updateUserSettings } from '$lib/apis/users';
	import PinnedModelItem from './PinnedModelItem.svelte';

	let { selectedChatId = $bindable(null), shiftKey = false } = $props();

	let pinnedModels: string[] = $state([]);

	const initPinnedModelsSortable = () => {
		const pinnedModelsList = document.getElementById('pinned-models-list');
		if (pinnedModelsList && !$mobile) {
			new Sortable(pinnedModelsList, {
				animation: 150,
				onUpdate: async (event) => {
					const modelId = event.item.dataset.id;
					const newIndex = event.newIndex;

					const pinnedModels = ($settings.pinnedModels ?? []) as string[];
					const oldIndex = pinnedModels.indexOf(modelId);

					pinnedModels.splice(oldIndex, 1);
					pinnedModels.splice(newIndex, 0, modelId);

					settings.set({ ...$settings, pinnedModels: pinnedModels });
					await updateUserSettings(localStorage.token, { ui: $settings });
				}
			});
		}
	};

	$effect(() => {
		pinnedModels = ($settings?.pinnedModels ?? []) as string[];
	});

	onMount(async () => {
		if (pinnedModels.length === 0 && $config?.default_pinned_models) {
			const defaultPinnedModels = ($config?.default_pinned_models).split(',').filter((id) => id);
			pinnedModels = defaultPinnedModels.filter((id: string) =>
				$models.find((model) => model.id === id)
			);

			settings.set({ ...$settings, pinnedModels });
			await updateUserSettings(localStorage.token, { ui: $settings });
		}

		await tick();
		initPinnedModelsSortable();
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
							settings.set({ ...$settings, pinnedModels });
							updateUserSettings(localStorage.token, { ui: $settings });
						}
					: null}
			/>
		{/if}
	{/each}
</div>
