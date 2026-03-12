<script lang="ts">
	import { onDestroy } from 'svelte';
	import { fly } from 'svelte/transition';

	let { show = $bindable(false), className = '', onClose = () => {} } = $props();

	let modalElement = $state(null);

	const handleKeyDown = (event: KeyboardEvent) => {
		if (event.key === 'Escape' && isTopModal()) {
			console.log('Escape');
			show = false;
		}
	};

	const isTopModal = () => {
		const modals = document.getElementsByClassName('modal');
		return modals.length && modals[modals.length - 1] === modalElement;
	};

	$effect(() => {
		if (show && modalElement) {
			document.body.appendChild(modalElement);
			window.addEventListener('keydown', handleKeyDown);
			document.body.style.overflow = 'hidden';
		} else if (modalElement) {
			onClose();
			window.removeEventListener('keydown', handleKeyDown);

			if (document.body.contains(modalElement)) {
				modalElement.remove();
				document.body.style.overflow = 'unset';
			}
		}
	});

	onDestroy(() => {
		show = false;
		if (modalElement) {
			if (document.body.contains(modalElement)) {
				modalElement.remove();
				document.body.style.overflow = 'unset';
			}
		}
	});
</script>

<!-- svelte-ignore a11y-click-events-have-key-events -->
<!-- svelte-ignore a11y-no-static-element-interactions -->
{#if show}
	<div
		bind:this={modalElement}
		class="modal fixed right-0 bottom-0 left-0 z-999 flex h-screen max-h-[100dvh] w-full justify-center overflow-hidden overscroll-contain bg-black/60"
		in:fly={{ y: 100, duration: 100 }}
		onmousedown={() => {
			show = false;
		}}
	>
		<div
			class=" mt-auto w-full bg-gray-50 dark:bg-gray-900 dark:text-gray-100 {className} scrollbar-hidden max-h-[100dvh] overflow-y-auto"
			onmousedown={(e) => {
				e.stopPropagation();
			}}
		>
			<slot />
		</div>
	</div>
{/if}
