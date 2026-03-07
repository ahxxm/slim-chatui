<script lang="ts">
	import { DropdownMenu } from 'bits-ui';
	import { getContext } from 'svelte';

	import { user, models, mobile, settings } from '$lib/stores';
	import { getModels } from '$lib/apis';

	import ChevronDown from '$lib/components/icons/ChevronDown.svelte';
	import Check from '$lib/components/icons/Check.svelte';

	const i18n = getContext('i18n');

	let {
		id = '',
		value = $bindable(''),
		placeholder = $i18n.t('Select a model'),
		items = [],
		className = 'w-[32rem]',
		triggerClassName = 'text-lg'
	} = $props();

	let show = $state(false);

	let selectedModel = $derived(items.find((item) => item.value === value));

	let visibleItems = $derived(items.filter((item) => !(item.model?.info?.meta?.hidden ?? false)));
</script>

<DropdownMenu.Root bind:open={show}>
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
			onmouseenter={async () => {
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
				: `${className}`} max-w-[calc(100vw-1rem)] justify-start rounded-2xl bg-white dark:bg-gray-850 dark:text-white shadow-lg outline-hidden"
			side="bottom"
			align={$mobile ? 'center' : 'start'}
			sideOffset={2}
			alignOffset={-1}
			onCloseAutoFocus={(e) => e.preventDefault()}
		>
			<div class="px-2.5">
				{#if visibleItems.length === 0}
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
								onclick={() => {
									show = false;
								}}
							>
								{$i18n.t('Manage Connections')}
							</a>
						</div>
					{:else}
						<div class="block px-3 py-2 text-sm text-gray-700 dark:text-gray-100">
							{$i18n.t('No results found')}
						</div>
					{/if}
				{:else}
					<div class="max-h-64 overflow-y-auto py-1">
						{#each visibleItems as item (item.value)}
							<DropdownMenu.Item
								class="flex w-full items-center rounded-xl py-2 pl-3 pr-2 text-sm text-gray-700 dark:text-gray-100 outline-hidden hover:bg-gray-100 dark:hover:bg-gray-800 cursor-pointer {value === item.value ? 'bg-gray-100 dark:bg-gray-800' : ''}"
								onclick={() => {
									value = item.value;
									show = false;
								}}
							>
								<span class="truncate flex-1">{item.label}</span>
								{#if value === item.value}
									<Check className="size-3 ml-2 shrink-0" />
								{/if}
							</DropdownMenu.Item>
						{/each}
					</div>
				{/if}
			</div>
			<div class="mb-2.5"></div>
			<div class="hidden w-[42rem]" />
			<div class="hidden w-[32rem]" />
		</DropdownMenu.Content>
	</DropdownMenu.Portal>
</DropdownMenu.Root>
