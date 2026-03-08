<script lang="ts">
	import { onMount, onDestroy, type Snippet } from 'svelte';

	let {
		onvisible = () => {},
		children
	}: {
		onvisible?: () => void;
		children?: Snippet;
	} = $props();

	let loaderElement: HTMLElement;
	let observer: IntersectionObserver;

	let rafId: number;

	const reobserve = () => {
		if (!loaderElement) return;
		observer.unobserve(loaderElement);
		observer.observe(loaderElement);
	};

	onMount(() => {
		observer = new IntersectionObserver(
			(entries) => {
				for (const entry of entries) {
					if (entry.isIntersecting) {
						onvisible();
						// Re-observe after a tick so that if the element is still
						// visible after the consumer loads more content, we fire again.
						rafId = requestAnimationFrame(reobserve);
					}
				}
			},
			{ threshold: 0.1 }
		);

		observer.observe(loaderElement);
	});

	onDestroy(() => {
		cancelAnimationFrame(rafId);
		observer?.disconnect();
	});
</script>

<div bind:this={loaderElement}>
	{@render children?.()}
</div>
