<script lang="ts">
	import { untrack } from 'svelte';

	import FolderItem from './FolderItem.svelte';
	import { chatId, selectedFolder } from '$lib/stores';

	let {
		folderRegistry = $bindable({}),
		folders = {},
		shiftKey = false,
		onDelete = (folderId: string) => {},
		onchange = () => {}
	}: {
		folderRegistry?: Record<string, any>;
		folders?: Record<string, any>;
		shiftKey?: boolean;
		onDelete?: (folderId: string) => void;
		onchange?: () => void;
	} = $props();

	let folderList = $derived(
		Object.keys(folders).sort((a, b) =>
			folders[a].name.localeCompare(folders[b].name, undefined, {
				numeric: true,
				sensitivity: 'base'
			})
		)
	);

	const onItemMove = (e: { originFolderId: string }) => {
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
	<FolderItem
		className=""
		bind:folderRegistry
		{folders}
		{folderId}
		{shiftKey}
		{onDelete}
		{onItemMove}
		{onchange}
	/>
{/each}
