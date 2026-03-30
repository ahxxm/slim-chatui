<script lang="ts">
	import { tick } from 'svelte';
	import Markdown from './Markdown.svelte';
	import { mobile, settings } from '$lib/stores';
	import FloatingButtons from '../ContentRenderer/FloatingButtons.svelte';

	let {
		id,
		content,
		history,
		messageId,
		done = true,
		model = null as any,
		sources = null as any[] | null,
		save = false,
		floatingButtons = true,
		editCodeBlock = true,
		topPadding = false,
		onSave = (e) => {},
		onSourceClick = (e) => {},
		onTaskClick = (e) => {},
		onAddMessages = (e) => {}
	} = $props();

	let contentContainerElement = $state<HTMLDivElement>();
	let floatingButtonsElement = $state<FloatingButtons>();

	let sourceIds = $derived.by(() => {
		if (!sources) return [];
		const seen = new Set<string>();
		const ids: string[] = [];
		for (const source of sources) {
			for (let i = 0; i < (source.document?.length ?? 0); i++) {
				if (model?.info?.meta?.capabilities?.citations == false) {
					if (!seen.has('N/A')) {
						seen.add('N/A');
						ids.push('N/A');
					}
					continue;
				}
				const metadata = source.metadata?.[i];
				const rawId = metadata?.source ?? 'N/A';
				const id = metadata?.name
					? metadata.name
					: rawId.startsWith('http://') || rawId.startsWith('https://')
						? rawId
						: (source?.source?.name ?? rawId);
				if (!seen.has(id)) {
					seen.add(id);
					ids.push(id);
				}
			}
		}
		return ids;
	});

	const updateButtonPosition = (event) => {
		const buttonsContainerElement = document.getElementById(`floating-buttons-${id}`);
		if (
			!contentContainerElement?.contains(event.target) &&
			!buttonsContainerElement?.contains(event.target)
		) {
			closeFloatingButtons();
			return;
		}

		setTimeout(async () => {
			await tick();

			if (!contentContainerElement?.contains(event.target)) return;

			let selection = window.getSelection();

			if (selection.toString().trim().length > 0) {
				const range = selection.getRangeAt(0);
				const rect = range.getBoundingClientRect();

				const parentRect = contentContainerElement.getBoundingClientRect();

				// Adjust based on parent rect
				const top = rect.bottom - parentRect.top;
				const left = rect.left - parentRect.left;

				if (buttonsContainerElement) {
					buttonsContainerElement.style.display = 'block';

					// Calculate space available on the right
					const spaceOnRight = parentRect.width - left;
					let halfScreenWidth = $mobile ? window.innerWidth / 2 : window.innerWidth / 3;

					if (spaceOnRight < halfScreenWidth) {
						const right = parentRect.right - rect.right;
						buttonsContainerElement.style.right = `${right}px`;
						buttonsContainerElement.style.left = 'auto'; // Reset left
					} else {
						// Enough space, position using 'left'
						buttonsContainerElement.style.left = `${left}px`;
						buttonsContainerElement.style.right = 'auto'; // Reset right
					}
					buttonsContainerElement.style.top = `${top + 5}px`; // +5 to add some spacing
				}
			} else {
				closeFloatingButtons();
			}
		}, 0);
	};

	const closeFloatingButtons = () => {
		const buttonsContainerElement = document.getElementById(`floating-buttons-${id}`);
		if (buttonsContainerElement) {
			buttonsContainerElement.style.display = 'none';
		}

		if (floatingButtonsElement) {
			if (typeof floatingButtonsElement?.closeHandler === 'function') {
				floatingButtonsElement?.closeHandler();
			}
		}
	};

	const keydownHandler = (e) => {
		if (e.key === 'Escape') {
			closeFloatingButtons();
		}
	};

	$effect(() => {
		if (!floatingButtons || !contentContainerElement) return;
		contentContainerElement.addEventListener('mouseup', updateButtonPosition);
		document.addEventListener('mouseup', updateButtonPosition);
		document.addEventListener('keydown', keydownHandler);
		return () => {
			contentContainerElement.removeEventListener('mouseup', updateButtonPosition);
			document.removeEventListener('mouseup', updateButtonPosition);
			document.removeEventListener('keydown', keydownHandler);
		};
	});
</script>

<div bind:this={contentContainerElement}>
	<Markdown
		{id}
		{content}
		{model}
		{save}
		{done}
		{editCodeBlock}
		{topPadding}
		{sourceIds}
		{onSourceClick}
		{onTaskClick}
		{onSave}
	/>
</div>

{#if floatingButtons && model}
	<FloatingButtons
		bind:this={floatingButtonsElement}
		{id}
		{messageId}
		actions={$settings?.floatingActionButtons ?? []}
		model={model?.id}
		{history}
		onAdd={({ modelId, parentId, messages }) => {
			console.log(modelId, parentId, messages);
			onAddMessages({ modelId, parentId, messages });
			closeFloatingButtons();
		}}
	/>
{/if}
