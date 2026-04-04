<script lang="ts">
	import { getContext, type Snippet, untrack } from 'svelte';
	const i18n = getContext('i18n');

	import dayjs from '$lib/dayjs';
	import duration from 'dayjs/plugin/duration';
	import relativeTime from 'dayjs/plugin/relativeTime';

	dayjs.extend(duration);
	dayjs.extend(relativeTime);

	import { slide } from 'svelte/transition';
	import { quintOut } from 'svelte/easing';

	import ChevronUp from '../icons/ChevronUp.svelte';
	import ChevronDown from '../icons/ChevronDown.svelte';
	import Spinner from './Spinner.svelte';

	interface CollapsibleProps {
		open?: boolean;
		className?: string;
		buttonClassName?: string;
		id?: string;
		title?: string | null;
		attributes?: Record<string, string | undefined> | null;
		chevron?: boolean;
		grow?: boolean;
		disabled?: boolean;
		hide?: boolean;
		onChange?: (open: boolean) => void;
		children?: Snippet;
		content?: Snippet;
	}

	let {
		open = $bindable(false),
		className = '',
		buttonClassName = 'w-fit text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 transition',
		id = '',
		title = null,
		attributes = null,
		chevron = false,
		grow = false,
		disabled = false,
		hide = false,
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

<div {id} class={className}>
	{#if title !== null}
		<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
		<div
			class="{buttonClassName} {disabled ? '' : 'cursor-pointer'}"
			role={disabled ? undefined : 'button'}
			tabindex={disabled ? undefined : 0}
			aria-expanded={disabled ? undefined : open}
			onkeydown={onTriggerKeydown}
			onpointerup={toggleOpen}
		>
			<div
				class=" w-full font-medium flex items-center justify-between gap-2 {attributes?.done &&
				attributes?.done !== 'true'
					? 'shimmer'
					: ''}
			"
			>
				{#if attributes?.done && attributes?.done !== 'true'}
					<div>
						<Spinner className="size-4" />
					</div>
				{/if}

				<div class="">
					{#if attributes?.type === 'reasoning'}
						{@const seconds = parseFloat(attributes?.duration ?? '0')}
						{#if attributes?.done === 'true' && seconds > 0}
							{#if seconds < 60}
								{$i18n.t('Thought for {{DURATION}} seconds', {
									DURATION: seconds
								})}
							{:else}
								{$i18n.t('Thought for {{DURATION}}', {
									DURATION: dayjs.duration(seconds, 'seconds').humanize()
								})}
							{/if}
						{:else if attributes?.done === 'true'}
							{$i18n.t('Thought shortly')}
						{:else}
							{$i18n.t('Thinking...')}
						{/if}
					{:else if attributes?.type === 'web_search'}
						{#if attributes?.done === 'true'}
							{#if attributes?.action === 'open_page'}
								{$i18n.t('Opened')} "{attributes?.url || ''}"
							{:else if attributes?.action === 'find_in_page'}
								{$i18n.t('Looked for')} "{attributes?.pattern || ''}" on {attributes?.url || ''}
							{:else}
								{$i18n.t('Searched')} "{attributes?.query || ''}"
							{/if}
						{:else}
							{$i18n.t('Searching...')}
						{/if}
					{:else}
						{title}
					{/if}
				</div>

				{#if !disabled}
					<div class="flex self-center translate-y-[1px]">
						{#if open}
							<ChevronUp strokeWidth="3.5" className="size-3.5" />
						{:else}
							<ChevronDown strokeWidth="3.5" className="size-3.5" />
						{/if}
					</div>
				{/if}
			</div>
		</div>
	{:else}
		<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
		<div
			class="{buttonClassName} cursor-pointer"
			role={disabled ? undefined : 'button'}
			tabindex={disabled ? undefined : 0}
			aria-expanded={disabled ? undefined : open}
			onclick={(e) => {
				e.stopPropagation();
			}}
			onkeydown={(e) => {
				e.stopPropagation();
				onTriggerKeydown(e);
			}}
			onpointerup={(e) => {
				e.stopPropagation();
				toggleOpen();
			}}
		>
			<div>
				<div class="flex items-start justify-between">
					{@render children?.()}

					{#if chevron}
						<div class="flex self-start translate-y-1">
							{#if open}
								<ChevronUp strokeWidth="3.5" className="size-3.5" />
							{:else}
								<ChevronDown strokeWidth="3.5" className="size-3.5" />
							{/if}
						</div>
					{/if}
				</div>

				{#if grow}
					{#if open && !hide}
						<!-- svelte-ignore a11y_no_static_element_interactions -->
						<div
							transition:slide={{ duration: 300, easing: quintOut, axis: 'y' }}
							onpointerup={(e) => {
								e.stopPropagation();
							}}
						>
							{@render content?.()}
						</div>
					{/if}
				{/if}
			</div>
		</div>
	{/if}

	{#if !grow}
		{#if open && !hide}
			<div transition:slide={{ duration: 300, easing: quintOut, axis: 'y' }}>
				{@render content?.()}
			</div>
		{/if}
	{/if}
</div>
