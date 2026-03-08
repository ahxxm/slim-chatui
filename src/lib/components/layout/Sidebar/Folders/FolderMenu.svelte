<script lang="ts">
	import { DropdownMenu } from 'bits-ui';
	import { getContext } from 'svelte';

	const i18n = getContext('i18n');

	import Dropdown from '$lib/components/common/Dropdown.svelte';
	import GarbageBin from '$lib/components/icons/GarbageBin.svelte';
	import Pencil from '$lib/components/icons/Pencil.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import Download from '$lib/components/icons/Download.svelte';

	let {
		align = 'start',
		onEdit = () => {},
		onExport = () => {},
		onDelete = () => {}
	}: {
		align?: 'start' | 'end';
		onEdit: () => void;
		onExport: () => void;
		onDelete: () => void;
	} = $props();

	let show = $state(false);
</script>

<Dropdown bind:show>
	<Tooltip content={$i18n.t('More')}>
		<button>
			<slot />
		</button>
	</Tooltip>

	{#snippet content()}
		<DropdownMenu.Content
			class="bits-content w-full max-w-[170px] rounded-2xl px-1 py-1 border border-gray-100  dark:border-gray-800   z-50 bg-white dark:bg-gray-850 dark:text-white shadow-lg"
			sideOffset={-2}
			side="bottom"
			{align}
		>
			<DropdownMenu.Item
				class="flex gap-2 items-center px-3 py-1.5 text-sm select-none cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800 rounded-xl"
				onclick={() => onEdit()}
			>
				<Pencil />
				<div class="flex items-center">{$i18n.t('Edit')}</div>
			</DropdownMenu.Item>

			<DropdownMenu.Item
				class="flex gap-2 items-center px-3 py-1.5 text-sm select-none cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800 rounded-xl"
				onclick={() => onExport()}
			>
				<Download />
				<div class="flex items-center">{$i18n.t('Export')}</div>
			</DropdownMenu.Item>

			<DropdownMenu.Item
				class="flex gap-2 items-center px-3 py-1.5 text-sm select-none cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800 rounded-xl"
				onclick={() => onDelete()}
			>
				<GarbageBin />
				<div class="flex items-center">{$i18n.t('Delete')}</div>
			</DropdownMenu.Item>
		</DropdownMenu.Content>
	{/snippet}
</Dropdown>
