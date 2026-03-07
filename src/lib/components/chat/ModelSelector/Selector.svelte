<script lang="ts">
	import { DropdownMenu } from 'bits-ui';
	import Fuse from 'fuse.js';

	import { getContext, tick } from 'svelte';
	import { untrack } from 'svelte';

	import { user, models, mobile, settings } from '$lib/stores';
	import { getModels } from '$lib/apis';

	import ChevronDown from '$lib/components/icons/ChevronDown.svelte';
	import Search from '$lib/components/icons/Search.svelte';
	import ModelItem from './ModelItem.svelte';

	const i18n = getContext('i18n');

	let {
		id = '',
		value = $bindable(''),
		placeholder = $i18n.t('Select a model'),
		searchEnabled = true,
		searchPlaceholder = $i18n.t('Search a model'),
		items = [],
		className = 'w-[32rem]',
		triggerClassName = 'text-lg',
		pinModelHandler = (modelId) => {}
	} = $props();

	let show = $state(false);

	let selectedModel = $derived(items.find((item) => item.value === value) ?? '');

	let searchValue = $state('');

	let selectedModelIdx = $state(0);

	const fuse = new Fuse(
		items.map((item) => ({
			...item,
			modelName: item.model?.name,
			desc: item.model?.info?.meta?.description
		})),
		{
			keys: ['value', 'modelName'],
			threshold: 0.4
		}
	);

	const updateFuse = () => {
		if (fuse) {
			fuse.setCollection(
				items.map((item) => ({
					...item,
					modelName: item.model?.name,
					desc: item.model?.info?.meta?.description
				}))
			);
		}
	};

	$effect(() => {
		if (items) {
			untrack(() => updateFuse());
		}
	});

	let filteredItems = $derived(
		(searchValue ? fuse.search(searchValue).map((e) => e.item) : items).filter(
			(item) => !(item.model?.info?.meta?.hidden ?? false)
		)
	);

	$effect(() => {
		if (searchValue !== undefined) {
			untrack(() => resetView());
		}
	});

	const resetView = async () => {
		await tick();

		const selectedInFiltered = filteredItems.findIndex((item) => item.value === value);

		if (selectedInFiltered >= 0) {
			selectedModelIdx = selectedInFiltered;
		} else {
			selectedModelIdx = 0;
		}

		const targetScrollTop = Math.max(0, selectedModelIdx * ITEM_HEIGHT - 128 + ITEM_HEIGHT / 2);
		listScrollTop = targetScrollTop;

		await tick();

		if (listContainer) {
			listContainer.scrollTop = targetScrollTop;
		}

		await tick();
		const item = document.querySelector(`[data-arrow-selected="true"]`);
		item?.scrollIntoView({ block: 'center', inline: 'nearest', behavior: 'instant' });
	};

	const ITEM_HEIGHT = 42;
	const OVERSCAN = 10;

	let listScrollTop = $state(0);
	let listContainer = $state();

	let visibleStart = $derived(Math.max(0, Math.floor(listScrollTop / ITEM_HEIGHT) - OVERSCAN));
	let visibleEnd = $derived(
		Math.min(filteredItems.length, Math.ceil((listScrollTop + 256) / ITEM_HEIGHT) + OVERSCAN)
	);
</script>

<DropdownMenu.Root
	bind:open={show}
	onOpenChange={async () => {
		searchValue = '';
		listScrollTop = 0;
		window.setTimeout(() => document.getElementById('model-search-input')?.focus(), 0);

		resetView();
	}}
>
	<DropdownMenu.Trigger
		class="relative w-full {($settings?.highContrastMode ?? false)
			? ''
			: 'outline-hidden focus:outline-hidden'}"
		aria-label={selectedModel
			? $i18n.t('Selected model: {{modelName}}', { modelName: selectedModel.label })
			: placeholder}
		id="model-selector-{id}-button"
	>
		<div
			class="flex w-full text-left px-0.5 bg-transparent truncate {triggerClassName} justify-between {($settings?.highContrastMode ??
			false)
				? 'dark:placeholder-gray-100 placeholder-gray-800'
				: 'placeholder-gray-400'}"
			on:mouseenter={async () => {
				models.set(await getModels(localStorage.token));
			}}
		>
			{#if selectedModel}
				{selectedModel.label}
			{:else}
				{placeholder}
			{/if}
			<ChevronDown className=" self-center ml-2 size-3" strokeWidth="2.5" />
		</div>
	</DropdownMenu.Trigger>

	<DropdownMenu.Portal>
	<DropdownMenu.Content
		class="bits-content z-40 {$mobile
			? `w-full`
			: `${className}`} max-w-[calc(100vw-1rem)] justify-start rounded-2xl  bg-white dark:bg-gray-850 dark:text-white shadow-lg  outline-hidden"
		side="bottom"
		align={$mobile ? 'center' : 'start'}
		sideOffset={2}
		alignOffset={-1}
		onCloseAutoFocus={(e) => e.preventDefault()}
	>
					<slot>
						{#if searchEnabled}
							<div class="flex items-center gap-2.5 px-4.5 mt-3.5 mb-1.5">
								<Search className="size-4" strokeWidth="2.5" />

								<input
									id="model-search-input"
									bind:value={searchValue}
									class="w-full text-sm bg-transparent outline-hidden"
									placeholder={searchPlaceholder}
									autocomplete="off"
									aria-label={$i18n.t('Search In Models')}
									on:keydown={(e) => {
										e.stopPropagation();
										if (e.code === 'Enter' && filteredItems.length > 0) {
											value = filteredItems[selectedModelIdx].value;
											show = false;
											return;
										} else if (e.code === 'ArrowDown') {
											selectedModelIdx = Math.min(selectedModelIdx + 1, filteredItems.length - 1);
										} else if (e.code === 'ArrowUp') {
											selectedModelIdx = Math.max(selectedModelIdx - 1, 0);
										} else {
											selectedModelIdx = 0;
										}

										const item = document.querySelector(`[data-arrow-selected="true"]`);
										item?.scrollIntoView({ block: 'center', inline: 'nearest', behavior: 'instant' });
									}}
								/>
							</div>
						{/if}

						<div class="px-2.5 group relative">
							{#if filteredItems.length === 0}
								{#if items.length === 0 && $user?.role === 'admin'}
									<div class="flex flex-col items-start justify-center py-6 px-4 text-start">
										<div class="text-sm font-medium text-gray-900 dark:text-gray-100 mb-1">
											{$i18n.t('No models available')}
										</div>
										<div class="text-xs text-gray-500 dark:text-gray-400 mb-4">
											{$i18n.t('Connect to an AI provider to start chatting')}
										</div>
										<a
											href="/admin/settings/connections"
											class="px-4 py-1.5 rounded-xl text-xs font-medium bg-gray-900 dark:bg-white text-white dark:text-gray-900 hover:bg-gray-800 dark:hover:bg-gray-100 transition"
											on:click={() => {
												show = false;
											}}
										>
											{$i18n.t('Manage Connections')}
										</a>
									</div>
								{:else}
									<div class="">
										<div class="block px-3 py-2 text-sm text-gray-700 dark:text-gray-100">
											{$i18n.t('No results found')}
										</div>
									</div>
								{/if}
							{:else}
								<!-- svelte-ignore a11y-no-static-element-interactions -->
								<div
									class="max-h-64 overflow-y-auto"
									role="listbox"
									aria-label={$i18n.t('Available models')}
									bind:this={listContainer}
									on:scroll={() => {
										listScrollTop = listContainer.scrollTop;
									}}
								>
									<div style="height: {visibleStart * ITEM_HEIGHT}px;" />
									{#each filteredItems.slice(visibleStart, visibleEnd) as item, i (item.value)}
										{@const index = visibleStart + i}
										<ModelItem
											{selectedModelIdx}
											{item}
											{index}
											{value}
											{pinModelHandler}
											onClick={() => {
												value = item.value;
												selectedModelIdx = index;

												show = false;
											}}
										/>
									{/each}
									<div style="height: {(filteredItems.length - visibleEnd) * ITEM_HEIGHT}px;" />
								</div>
							{/if}
						</div>

						<div class="mb-2.5"></div>

						<div class="hidden w-[42rem]" />
						<div class="hidden w-[32rem]" />
					</slot>
	</DropdownMenu.Content>
	</DropdownMenu.Portal>
</DropdownMenu.Root>
