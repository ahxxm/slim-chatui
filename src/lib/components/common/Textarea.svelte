<script lang="ts">
	let {
		value = $bindable(''),
		placeholder = '',
		rows = 1,
		minSize = null as number | null,
		maxSize = null as number | null,
		required = false,
		readonly = false,
		className = 'w-full rounded-lg px-3.5 py-2 text-sm bg-gray-50 dark:text-gray-300 dark:bg-gray-850 outline-hidden',
		ariaLabel = null as string | null
	} = $props();
</script>

<textarea
	bind:value
	{placeholder}
	aria-label={ariaLabel || placeholder}
	class={className}
	style="field-sizing:content;{minSize != null ? `min-height:${minSize}px;` : ''}{maxSize != null ? `max-height:${maxSize}px;` : ''}"
	{rows}
	{required}
	{readonly}
/>
