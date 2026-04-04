<script lang="ts">
	import { DropdownMenu } from 'bits-ui';
	import { getContext } from 'svelte';

	import Dropdown from '$lib/components/common/Dropdown.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import Link from '$lib/components/icons/Link.svelte';

	const i18n = getContext('i18n');

	export let copyLinkHandler: Function;

	export let onClose: Function;

	let show: boolean = false;
</script>

<Dropdown
	bind:show
	on:change={(e) => {
		if (e.detail === false) {
			onClose();
		}
	}}
>
	<Tooltip content={$i18n.t('More')}>
		<slot />
	</Tooltip>

	{#snippet content()}
		<DropdownMenu.Content
			class="bits-content w-full max-w-[170px] rounded-xl p-1 border border-gray-100  dark:border-gray-800 z-50 bg-white dark:bg-gray-850 dark:text-white shadow-sm"
			sideOffset={-2}
			side="bottom"
			align="start"
		>
			<DropdownMenu.Item
				class="select-none flex gap-2 items-center px-3 py-1.5 text-sm  font-medium cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800 rounded-md"
				onclick={() => {
					copyLinkHandler();
				}}
			>
				<Link />

				<div class="flex items-center">{$i18n.t('Copy Link')}</div>
			</DropdownMenu.Item>
		</DropdownMenu.Content>
	{/snippet}
</Dropdown>
