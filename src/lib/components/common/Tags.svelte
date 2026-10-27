<script lang="ts">
	import TagList from './Tags/TagList.svelte';
	import { getContext } from 'svelte';

	const i18n = getContext('i18n');

	export let tags: { name: string }[] = [];
	export let disabled = false;
	export let onAdd: (name: string) => void = () => {};
	export let onDelete: (name: string) => void = () => {};

	let inputValue = '';

	const addTag = () => {
		const value = inputValue.trim();
		if (value !== '') {
			onAdd(value);
			inputValue = '';
		}
	};
</script>

<div class="flex flex-wrap items-center gap-1 w-full">
	<TagList {tags} {disabled} {onDelete} />

	{#if !disabled}
		<input
			bind:value={inputValue}
			class="flex-1 min-w-24 {tags.length > 0
				? 'px-0.5'
				: ''} text-xs bg-transparent outline-hidden placeholder:text-gray-400 dark:placeholder:text-gray-500"
			placeholder={$i18n.t('Add a tag...')}
			onkeydown={(event) => {
				if (event.key === 'Enter' || event.key === ' ') {
					event.preventDefault();
					addTag();
				}
			}}
		/>
	{/if}
</div>
