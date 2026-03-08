<script lang="ts">
	let {
		checked = 'unchecked',
		indeterminate = false,
		disabled = false,
		disabledClassName = 'opacity-50 cursor-not-allowed',
		onchange
	}: {
		checked?: string;
		indeterminate?: boolean;
		disabled?: boolean;
		disabledClassName?: string;
		onchange: (value: string) => void;
	} = $props();

	let current = $state('unchecked');

	$effect(() => {
		current = checked;
	});
</script>

<button
	class=" outline -outline-offset-1 outline-[1.5px] outline-gray-200 dark:outline-gray-600 {current !==
	'unchecked'
		? 'bg-black outline-black '
		: 'hover:outline-gray-500 hover:bg-gray-50 dark:hover:bg-gray-800'} text-white transition-all rounded-sm inline-block w-3.5 h-3.5 relative {disabled
		? disabledClassName
		: ''}"
	onclick={() => {
		if (disabled) return;

		if (current === 'unchecked') {
			current = 'checked';
			onchange(current);
		} else if (current === 'checked') {
			current = 'unchecked';
			if (!indeterminate) {
				onchange(current);
			}
		} else if (indeterminate) {
			current = 'checked';
			onchange(current);
		}
	}}
	type="button"
	{disabled}
>
	<div class="top-0 left-0 absolute w-full flex justify-center">
		{#if current === 'checked'}
			<svg
				class="w-3.5 h-3.5"
				aria-hidden="true"
				xmlns="http://www.w3.org/2000/svg"
				fill="none"
				viewBox="0 0 24 24"
			>
				<path
					stroke="currentColor"
					stroke-linecap="round"
					stroke-linejoin="round"
					stroke-width="3"
					d="m5 12 4.7 4.5 9.3-9"
				/>
			</svg>
		{:else if indeterminate}
			<svg
				class="w-3 h-3.5 text-gray-800 dark:text-white"
				aria-hidden="true"
				xmlns="http://www.w3.org/2000/svg"
				fill="none"
				viewBox="0 0 24 24"
			>
				<path
					stroke="currentColor"
					stroke-linecap="round"
					stroke-linejoin="round"
					stroke-width="3"
					d="M5 12h14"
				/>
			</svg>
		{/if}
	</div>

	<!-- {checked} -->
</button>
