<script lang="ts">
	import DOMPurify from 'dompurify';

	import { onDestroy } from 'svelte';

	import tippy from 'tippy.js';

	let {
		elementId = '',
		as = 'div',
		className = 'flex',
		placement = 'top',
		content = `I'm a tooltip!`,
		touch = true,
		theme = '',
		offset = [0, 4],
		allowHTML = true,
		tippyOptions = {},
		interactive = false,
		onClick = () => {}
	} = $props();

	let tooltipElement = $state();
	let tooltipInstance;

	const destroyInstance = () => {
		if (tooltipInstance) {
			tooltipInstance.destroy();
			tooltipInstance = null;
		}
	};

	$effect(() => {
		if (tooltipElement && (content || elementId)) {
			let tooltipContent = null;

			if (elementId) {
				tooltipContent = document.getElementById(`${elementId}`);
			} else {
				tooltipContent = DOMPurify.sanitize(content);
			}

			if (tooltipInstance && tooltipInstance.reference !== tooltipElement) {
				destroyInstance();
			}

			if (tooltipInstance) {
				tooltipInstance.setContent(tooltipContent);
			} else {
				if (content) {
					tooltipInstance = tippy(tooltipElement, {
						content: tooltipContent,
						placement: placement,
						allowHTML: allowHTML,
						touch: touch,
						...(theme !== '' ? { theme } : { theme: 'dark' }),
						arrow: false,
						offset: offset,
						...(interactive ? { interactive: true } : {}),
						...tippyOptions
					});
				}
			}
		} else if (tooltipInstance && content === '') {
			destroyInstance();
		}
	});

	onDestroy(() => {
		destroyInstance();
	});
</script>

<!-- svelte-ignore a11y-no-static-element-interactions -->
<svelte:element this={as} bind:this={tooltipElement} class={className} on:click={onClick}>
	<slot />
</svelte:element>

<slot name="tooltip"></slot>
