<script lang="ts">
	import { DropdownMenu } from 'bits-ui';
	import { createEventDispatcher, getContext } from 'svelte';

	const i18n = getContext('i18n');

	let {
		show = $bindable(false),
		side = 'bottom',
		align = 'start',
		children,
		content
	}: {
		show?: boolean;
		side?: string;
		align?: string;
		children?: any;
		content?: any;
	} = $props();

	const dispatch = createEventDispatcher();
</script>

<DropdownMenu.Root
	bind:open={show}
	onOpenChange={(state) => {
		dispatch('change', state);
	}}
>
	<DropdownMenu.Trigger>
		{#snippet child({ props })}
			<div {...props}>
				{@render children?.()}
			</div>
		{/snippet}
	</DropdownMenu.Trigger>

	<DropdownMenu.Portal>
		{#if content}
			{@render content()}
		{:else}
			<DropdownMenu.Content
				class="bits-content w-full max-w-[130px] rounded-lg p-1 border border-gray-900 z-50 bg-gray-850 text-white"
				sideOffset={8}
				{side}
				{align}
				onCloseAutoFocus={(e) => e.preventDefault()}
			>
				<DropdownMenu.Item class="select-none flex items-center px-3 py-2 text-sm  font-medium">
					<div class="flex items-center">{$i18n.t('Profile')}</div>
				</DropdownMenu.Item>
			</DropdownMenu.Content>
		{/if}
	</DropdownMenu.Portal>
</DropdownMenu.Root>
