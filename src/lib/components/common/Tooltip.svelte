<script lang="ts">
	import DOMPurify from 'dompurify';
	import { tick, onDestroy } from 'svelte';
	import { computePosition, flip, shift, offset as offsetMiddleware } from '@floating-ui/dom';

	let {
		elementId = '',
		as = 'div',
		className = 'flex',
		placement = 'top',
		content = `I'm a tooltip!`,
		touch = true,
		offset = [0, 4],
		allowHTML = true,
		interactive = false,
		duration = [150, 150] as [number, number],
		onClick = () => {}
	} = $props();

	let triggerEl: HTMLElement | undefined = $state();
	let tooltipEl: HTMLDivElement | undefined = $state();

	function portal(node: HTMLElement) {
		document.body.appendChild(node);
		return {
			destroy() {
				node.remove();
			}
		};
	}

	const updatePosition = async () => {
		if (!triggerEl || !tooltipEl) return;
		const { x, y } = await computePosition(triggerEl, tooltipEl, {
			placement: placement as any,
			middleware: [
				offsetMiddleware({ mainAxis: offset[1], crossAxis: offset[0] }),
				flip(),
				shift({ padding: 8 })
			]
		});
		if (!tooltipEl) return;
		tooltipEl.style.left = `${x}px`;
		tooltipEl.style.top = `${y}px`;
		tooltipEl.style.opacity = '1';
	};

	let visible = $state(false);

	const show = async () => {
		if (!content && !elementId) return;
		visible = true;
		await tick();
		updatePosition();
	};

	const hide = () => {
		visible = false;
	};
</script>

<!-- svelte-ignore a11y-no-static-element-interactions -->
<svelte:element
	this={as}
	bind:this={triggerEl}
	class={className}
	onclick={onClick}
	onmouseenter={show}
	onmouseleave={hide}
	onfocus={show}
	onblur={hide}
	ontouchstart={touch ? show : undefined}
>
	<slot />
</svelte:element>

{#if visible}
	<div
		bind:this={tooltipEl}
		use:portal
		class="floating-tooltip"
		class:pointer-events-none={!interactive}
		style="position:fixed;z-index:9999;opacity:0;transition:opacity {duration[0]}ms"
		role="tooltip"
	>
		{#if elementId}
			{@const el = document.getElementById(elementId)}
			{#if el}
				{@html el.innerHTML}
			{/if}
		{:else if allowHTML}
			{@html DOMPurify.sanitize(content)}
		{:else}
			{content}
		{/if}
	</div>
{/if}
