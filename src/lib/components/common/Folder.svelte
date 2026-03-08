<script lang="ts">
	import { onMount, onDestroy, type Snippet } from 'svelte';

	import ChevronDown from '../icons/ChevronDown.svelte';
	import ChevronRight from '../icons/ChevronRight.svelte';
	import Collapsible from './Collapsible.svelte';
	import Tooltip from './Tooltip.svelte';
	import Plus from '../icons/Plus.svelte';

	let {
		open = $bindable(true),
		id = '',
		name = '',
		collapsible = true,
		className = '',
		buttonClassName = 'text-gray-600 dark:text-gray-400',
		chevron = true,
		onAddLabel = '',
		onAdd = null as null | (() => void),
		dragAndDrop = true,
		ondrop = (data: any) => {},
		onchange = (state: boolean) => {},
		children
	}: {
		open?: boolean;
		id?: string;
		name?: string;
		collapsible?: boolean;
		className?: string;
		buttonClassName?: string;
		chevron?: boolean;
		onAddLabel?: string;
		onAdd?: null | (() => void);
		dragAndDrop?: boolean;
		ondrop?: (data: any) => void;
		onchange?: (state: boolean) => void;
		children?: Snippet;
	} = $props();

	let folderElement: HTMLDivElement;
	let loaded = $state(false);
	let draggedOver = $state(false);

	const onDragOver = (e: DragEvent) => {
		e.preventDefault();
		e.stopPropagation();
		draggedOver = true;
	};

	const onDrop = (e: DragEvent) => {
		e.preventDefault();
		e.stopPropagation();

		if (folderElement.contains(e.target as Node)) {
			try {
				const dataTransfer = e.dataTransfer?.getData('text/plain');
				if (dataTransfer) {
					const data = JSON.parse(dataTransfer);
					open = true;
					ondrop(data);
				}
			} catch {
				// Not valid JSON — ignore
			} finally {
				draggedOver = false;
			}
		}
	};

	const onDragLeave = (e: DragEvent) => {
		e.preventDefault();
		e.stopPropagation();
		draggedOver = false;
	};

	onMount(() => {
		const state = localStorage.getItem(`${id}-folder-state`);
		if (state !== null) {
			open = state === 'true';
		}
		loaded = true;

		if (!dragAndDrop) return;
		folderElement.addEventListener('dragover', onDragOver);
		folderElement.addEventListener('drop', onDrop);
		folderElement.addEventListener('dragleave', onDragLeave);
	});

	onDestroy(() => {
		if (!dragAndDrop) return;
		folderElement?.removeEventListener('dragover', onDragOver);
		folderElement?.removeEventListener('drop', onDrop);
		folderElement?.removeEventListener('dragleave', onDragLeave);
	});
</script>

<div bind:this={folderElement} class="relative {className}">
	{#if loaded}
		{#if draggedOver}
			<div
				class="absolute top-0 left-0 w-full h-full rounded-xs bg-gray-100/50 dark:bg-gray-700/20 bg-opacity-50 dark:bg-opacity-10 z-50 pointer-events-none touch-none"
			></div>
		{/if}

		{#if collapsible}
			<Collapsible
				bind:open
				className="w-full "
				buttonClassName="w-full"
				onChange={(state: boolean) => {
					onchange(state);
					localStorage.setItem(`${id}-folder-state`, `${state}`);
				}}
			>
				<!-- svelte-ignore a11y-no-static-element-interactions -->
				<div
					id="sidebar-folder-button"
					class=" w-full group rounded-xl relative flex items-center justify-between hover:bg-gray-100 dark:hover:bg-gray-900 transition {buttonClassName}"
				>
					<button class="w-full py-1.5 pl-2 flex items-center gap-1.5 text-xs font-medium">
						{#if chevron}
							<div class=" p-[1px]">
								{#if open}
									<ChevronDown className=" size-3" strokeWidth="2" />
								{:else}
									<ChevronRight className=" size-3" strokeWidth="2" />
								{/if}
							</div>
						{/if}

						<div class="translate-y-[0.5px] {chevron ? '' : 'pl-0.5'}">
							{name}
						</div>
					</button>

					{#if onAdd}
						<button
							class="absolute z-10 right-2 invisible group-hover:visible self-center flex items-center dark:text-gray-300"
							onpointerup={(e) => {
								e.stopPropagation();
							}}
							onclick={(e) => {
								e.stopPropagation();
								onAdd();
							}}
						>
							<Tooltip content={onAddLabel}>
								<button
									class="p-0.5 dark:hover:bg-gray-850 rounded-lg touch-auto"
									onclick={() => {}}
								>
									<Plus className=" size-3" strokeWidth="2.5" />
								</button>
							</Tooltip>
						</button>
					{/if}
				</div>

				<div slot="content" class="w-full">
					{@render children?.()}
				</div>
			</Collapsible>
		{:else}
			{@render children?.()}
		{/if}
	{/if}
</div>
