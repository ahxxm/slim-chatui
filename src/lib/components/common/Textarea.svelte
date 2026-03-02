<script lang="ts">
	import { onMount, tick } from 'svelte';

	export let value = '';
	export let placeholder = '';
	export let rows = 1;
	export let minSize = null;
	export let maxSize = null;
	export let required = false;
	export let readonly = false;
	export let className =
		'w-full rounded-lg px-3.5 py-2 text-sm bg-gray-50 dark:text-gray-300 dark:bg-gray-850 outline-hidden  h-full';
	export let ariaLabel = null;

	export let onInput = () => {};
	export let onBlur = () => {};

	let textareaElement;

	onMount(() => {
		let pollInterval: ReturnType<typeof setInterval> | null = null;

		(async () => {
			await tick();
			resize();
		})();

		requestAnimationFrame(() => {
			pollInterval = setInterval(() => {
				if (textareaElement) {
					clearInterval(pollInterval!);
					pollInterval = null;
					resize();
				}
			}, 100);
		});

		return () => {
			if (pollInterval) clearInterval(pollInterval);
		};
	});

	const resize = () => {
		if (textareaElement) {
			textareaElement.style.height = '';

			let height = textareaElement.scrollHeight;
			if (maxSize && height > maxSize) {
				height = maxSize;
			}
			if (minSize && height < minSize) {
				height = minSize;
			}

			textareaElement.style.height = `${height}px`;
		}
	};
</script>

<textarea
	bind:this={textareaElement}
	bind:value
	{placeholder}
	aria-label={ariaLabel || placeholder}
	class={className}
	style="field-sizing: content;"
	{rows}
	{required}
	{readonly}
	on:input={(e) => {
		resize();

		onInput(e);
	}}
	on:focus={() => {
		resize();
	}}
	on:blur={onBlur}
/>
