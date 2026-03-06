<script lang="ts">
	import { createEventDispatcher, untrack } from 'svelte';
	const dispatch = createEventDispatcher();

	import RecursiveFolder from './RecursiveFolder.svelte';
	import { chatId, selectedFolder } from '$lib/stores';

	let {
		folderRegistry = $bindable({}),
		folders = {},
		shiftKey = false,
		onDelete = (folderId) => {}
	}: {
		folderRegistry?: Record<string, any>;
		folders?: Record<string, any>;
		shiftKey?: boolean;
		onDelete?: (folderId: string) => void;
	} = $props();

	let folderList = $derived(
		Object.keys(folders)
			.filter((key) => folders[key].parent_id === null)
			.sort((a, b) =>
				folders[a].name.localeCompare(folders[b].name, undefined, {
					numeric: true,
					sensitivity: 'base'
				})
			)
	);

	const onItemMove = (e) => {
		if (e.originFolderId) {
			folderRegistry[e.originFolderId]?.setFolderItems();
		}
	};

	const loadFolderItems = () => {
		for (const folderId of Object.keys(folders)) {
			folderRegistry[folderId]?.setFolderItems();
		}
	};

	$effect(() => {
		if (folders || ($selectedFolder && $chatId)) {
			untrack(() => loadFolderItems());
		}
	});
</script>

{#each folderList as folderId (folderId)}
	<RecursiveFolder
		className=""
		bind:folderRegistry
		{folders}
		{folderId}
		{shiftKey}
		{onDelete}
		{onItemMove}
		on:import={(e) => {
			dispatch('import', e.detail);
		}}
		on:update={(e) => {
			dispatch('update', e.detail);
		}}
		on:change={(e) => {
			dispatch('change', e.detail);
		}}
	/>
{/each}
