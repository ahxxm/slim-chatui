<script lang="ts">
	import DOMPurify from 'dompurify';

	import { getContext, tick, untrack } from 'svelte';
	import * as FocusTrap from 'focus-trap';

	const i18n = getContext('i18n');

	import { fade } from 'svelte/transition';
	import { flyAndScale } from '$lib/utils/transitions';
	import { marked } from 'marked';
	import SensitiveInput from './SensitiveInput.svelte';

	let {
		title = '',
		message = '',
		cancelLabel = $i18n.t('Cancel'),
		confirmLabel = $i18n.t('Confirm'),
		onConfirm = (value?: string) => {},
		oncancel = () => {},
		input = false,
		inputPlaceholder = '',
		inputValue = $bindable(''),
		inputType = '',
		show = $bindable(false)
	}: {
		title?: string;
		message?: string;
		cancelLabel?: string;
		confirmLabel?: string;
		onConfirm?: (value?: string) => void;
		oncancel?: () => void;
		input?: boolean;
		inputPlaceholder?: string;
		inputValue?: string;
		inputType?: string;
		show?: boolean;
	} = $props();

	$effect(() => {
		if (show) {
			untrack(() => init());
		}
	});

	let modalElement: HTMLDivElement | null = $state(null);

	const init = () => {
		inputValue = '';
	};

	const confirmHandler = async () => {
		show = false;
		await tick();
		onConfirm(inputValue);
	};

	const handleKeyDown = (event: KeyboardEvent) => {
		if (event.key === 'Enter') {
			event.preventDefault();
			event.stopPropagation();
			confirmHandler();
		}
	};

	$effect(() => {
		if (!show || !modalElement) return;

		document.body.style.overflow = 'hidden';
		const trap = FocusTrap.createFocusTrap(modalElement, {
			escapeDeactivates: () => {
				show = false;
				return true;
			},
			allowOutsideClick: true
		});
		trap.activate();
		window.addEventListener('keydown', handleKeyDown);

		return () => {
			trap.deactivate();
			window.removeEventListener('keydown', handleKeyDown);
			document.body.style.overflow = 'unset';
		};
	});
</script>

{#if show}
	<!-- svelte-ignore a11y-click-events-have-key-events -->
	<!-- svelte-ignore a11y-no-static-element-interactions -->
	<div
		bind:this={modalElement}
		class=" fixed top-0 right-0 left-0 bottom-0 bg-black/60 w-full h-screen max-h-[100dvh] flex justify-center z-9999 overflow-hidden overscroll-contain"
		in:fade={{ duration: 10 }}
		onmousedown={() => {
			show = false;
		}}
	>
		<div
			class=" m-auto max-w-full w-[32rem] mx-2 bg-white/95 dark:bg-gray-950/95 backdrop-blur-sm rounded-4xl max-h-[100dvh] shadow-3xl border border-white dark:border-gray-900"
			in:flyAndScale
			onmousedown={(e) => {
				e.stopPropagation();
			}}
		>
			<div class="px-[1.75rem] py-6 flex flex-col">
				<div class=" text-lg font-medium dark:text-gray-200 mb-2.5">
					{#if title !== ''}
						{title}
					{:else}
						{$i18n.t('Confirm your action')}
					{/if}
				</div>

				<slot>
					<div class=" text-sm text-gray-500 flex-1">
						{#if message !== ''}
							{@const html = DOMPurify.sanitize(marked.parse(message))}
							{@html html}
						{:else}
							{$i18n.t('This action cannot be undone. Do you wish to continue?')}
						{/if}

						{#if input}
							{#if inputType === 'password'}
								<div
									class="w-full mt-2 rounded-lg px-4 py-2 text-sm dark:text-gray-300 dark:bg-gray-900"
								>
									<SensitiveInput
										id="event-confirm-input"
										placeholder={inputPlaceholder
											? inputPlaceholder
											: $i18n.t('Enter your message')}
										bind:value={inputValue}
										required={true}
									/>
								</div>
							{:else}
								<textarea
									bind:value={inputValue}
									placeholder={inputPlaceholder ? inputPlaceholder : $i18n.t('Enter your message')}
									class="w-full mt-2 rounded-lg px-4 py-2 text-sm dark:text-gray-300 dark:bg-gray-900 outline-hidden resize-none"
									rows="3"
									required
								/>
							{/if}
						{/if}
					</div>
				</slot>

				<div class="mt-6 flex justify-between gap-1.5">
					<button
						class="text-sm bg-gray-100 hover:bg-gray-200 text-gray-800 dark:bg-gray-850 dark:hover:bg-gray-800 dark:text-white font-medium w-full py-2 rounded-3xl transition"
						onclick={() => {
							show = false;
							oncancel();
						}}
						type="button"
					>
						{cancelLabel}
					</button>
					<button
						class="text-sm bg-gray-900 hover:bg-gray-850 text-gray-100 dark:bg-gray-100 dark:hover:bg-white dark:text-gray-800 font-medium w-full py-2 rounded-3xl transition"
						onclick={() => {
							confirmHandler();
						}}
						type="button"
					>
						{confirmLabel}
					</button>
				</div>
			</div>
		</div>
	</div>
{/if}

<style>
	.modal-content {
		animation: scaleUp 0.1s ease-out forwards;
	}

	@keyframes scaleUp {
		from {
			transform: scale(0.985);
			opacity: 0;
		}
		to {
			transform: scale(1);
			opacity: 1;
		}
	}
</style>
