<script lang="ts">
	export let x: number;
	export let y: number;

	const portal = (element: HTMLDivElement) => {
		document.body.appendChild(element);
		document.body.style.overflow = 'hidden';

		return {
			destroy() {
				element.remove();
				document.body.style.overflow = 'unset';
			}
		};
	};
</script>

<!-- svelte-ignore a11y-click-events-have-key-events -->
<!-- svelte-ignore a11y-no-static-element-interactions -->

<div use:portal class="fixed top-0 left-0 w-screen h-[100dvh] z-50 touch-none pointer-events-none">
	<div class=" absolute text-white z-99999" style="top: {y + 10}px; left: {x + 10}px;">
		<slot></slot>
	</div>
</div>
