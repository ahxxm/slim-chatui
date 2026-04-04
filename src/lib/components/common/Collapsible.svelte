<script lang="ts">
	import { type Snippet, untrack } from 'svelte';
	import { slide } from 'svelte/transition';
	import { quintOut } from 'svelte/easing';

	import ChevronUp from '../icons/ChevronUp.svelte';
	import ChevronDown from '../icons/ChevronDown.svelte';

	interface CollapsibleProps {
		open?: boolean;
		className?: string;
		buttonClassName?: string;
		chevron?: boolean;
		disabled?: boolean;
		onChange?: (open: boolean) => void;
		children?: Snippet;
		content?: Snippet;
	}

	let {
		open = $bindable(false),
		className = '',
		buttonClassName = 'w-fit text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 transition',
		chevron = false,
		disabled = false,
		onChange = () => {},
		children = undefined,
		content = undefined
	}: CollapsibleProps = $props();

	$effect(() => {
		const currentOpen = open;
		untrack(() => onChange(currentOpen));
	});

	const toggleOpen = () => {
		if (!disabled) {
			open = !open;
		}
	};

	const onTriggerKeydown = (event: KeyboardEvent) => {
		if (event.key !== 'Enter' && event.key !== ' ') {
			return;
		}

		event.preventDefault();
		toggleOpen();
	};
</script>

<div class={className}>
	<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
	<div
		data-collapsible-trigger
		class="{buttonClassName} {disabled ? '' : 'cursor-pointer'}"
		role={disabled ? undefined : 'button'}
		tabindex={disabled ? undefined : 0}
		aria-expanded={disabled ? undefined : open}
		onkeydown={onTriggerKeydown}
		onpointerup={toggleOpen}
	>
		<div class="flex items-start justify-between">
			<div class="min-w-0 flex-1">
				{@render children?.()}
			</div>

			{#if chevron && !disabled}
				<div class="flex self-start translate-y-1">
					{#if open}
						<ChevronUp strokeWidth="3.5" className="size-3.5" />
					{:else}
						<ChevronDown strokeWidth="3.5" className="size-3.5" />
					{/if}
				</div>
			{/if}
		</div>
	</div>

	{#if open}
		<div transition:slide={{ duration: 300, easing: quintOut, axis: 'y' }}>
			{@render content?.()}
		</div>
	{/if}
</div>
