<script lang="ts">
	import DOMPurify from 'dompurify';
	import { onDestroy } from 'svelte';
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
	let tooltipEl: HTMLDivElement | null = null;

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

	const setTooltipContent = () => {
		if (!tooltipEl) return;
		if (elementId) {
			const el = document.getElementById(elementId);
			if (el) {
				tooltipEl.innerHTML = '';
				tooltipEl.appendChild(el.cloneNode(true));
			}
		} else if (allowHTML) {
			tooltipEl.innerHTML = DOMPurify.sanitize(content);
		} else {
			tooltipEl.textContent = content;
		}
	};

	const show = async () => {
		if (!content && !elementId) return;
		if (!tooltipEl) {
			tooltipEl = document.createElement('div');
			tooltipEl.className = `floating-tooltip${interactive ? '' : ' pointer-events-none'}`;
			tooltipEl.setAttribute('role', 'tooltip');
			tooltipEl.style.cssText = `position:fixed;z-index:9999;opacity:0;transition:opacity ${duration[0]}ms`;
			document.body.appendChild(tooltipEl);
		}
		setTooltipContent();
		updatePosition();
	};

	const hide = () => {
		if (tooltipEl) {
			tooltipEl.style.transition = `opacity ${duration[1]}ms`;
			tooltipEl.style.opacity = '0';
			const el = tooltipEl;
			setTimeout(() => {
				el.remove();
				if (tooltipEl === el) tooltipEl = null;
			}, duration[1]);
		}
	};

	onDestroy(() => {
		if (tooltipEl) {
			tooltipEl.remove();
			tooltipEl = null;
		}
	});
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
