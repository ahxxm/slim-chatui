<script lang="ts">
	import { getContext } from 'svelte';
	const i18n = getContext('i18n');

	import { saveAs } from '$lib/utils';

	import { toast } from 'svelte-sonner';

	import { selectedFolder } from '$lib/stores';

	import { deleteFolderById, getFolderById, updateFolderById } from '$lib/apis/folders';
	import { getChatsByFolderId } from '$lib/apis/chats';

	import Folder from '$lib/components/icons/Folder.svelte';
	import FolderMenu from '$lib/components/layout/Sidebar/Folders/FolderMenu.svelte';
	import EllipsisHorizontal from '$lib/components/icons/EllipsisHorizontal.svelte';
	import DeleteConfirmDialog from '$lib/components/common/ConfirmDialog.svelte';
	import Emoji from '$lib/components/common/Emoji.svelte';

	import type { FolderItem } from '$lib/types';

	interface FolderTitleProps {
		folder?: FolderItem | null;
		onUpdate?: (folder: FolderItem | null) => void;
		onDelete?: (folder: FolderItem | null) => void;
	}

	interface FolderUpdatePayload {
		name: string;
		meta?: FolderItem['meta'];
		data?: FolderItem['data'];
	}

	type FolderModalComponentType =
		typeof import('$lib/components/layout/Sidebar/Folders/FolderModal.svelte').default;

	let { folder = null, onUpdate = () => {}, onDelete = () => {} }: FolderTitleProps = $props();

	let showFolderModal = $state(false);
	let showDeleteConfirm = $state(false);
	let deleteFolderContents = $state(true);
	let FolderModalComponent = $state<FolderModalComponentType | null>(null);
	let folderModalLoadPromise: Promise<void> | null = null;

	const loadFolderModal = async () => {
		if (FolderModalComponent) {
			return;
		}

		if (!folderModalLoadPromise) {
			folderModalLoadPromise = import('$lib/components/layout/Sidebar/Folders/FolderModal.svelte')
				.then(({ default: FolderModal }) => {
					FolderModalComponent = FolderModal;
				})
				.finally(() => {
					folderModalLoadPromise = null;
				});
		}

		await folderModalLoadPromise;
	};

	const openFolderModal = async () => {
		await loadFolderModal();
		showFolderModal = true;
	};

	const updateHandler = async ({ name, meta, data }: FolderUpdatePayload) => {
		const activeFolder = folder!;

		if (name === '') {
			toast.error($i18n.t('Folder name cannot be empty.'));
			return;
		}

		const currentName = activeFolder.name;

		name = name.trim();
		activeFolder.name = name;

		const res = await updateFolderById(localStorage.token, activeFolder.id, {
			name,
			...(meta ? { meta } : {}),
			...(data ? { data } : {})
		}).catch((error) => {
			toast.error(`${error}`);

			activeFolder.name = currentName;
			return null;
		});

		if (res) {
			activeFolder.name = name;
			if (meta) {
				activeFolder.meta = meta;
			}
			if (data) {
				activeFolder.data = data;
			}

			toast.success($i18n.t('Folder updated successfully'));

			const _folder = await getFolderById(localStorage.token, activeFolder.id).catch((error) => {
				toast.error(`${error}`);
				return null;
			});

			await selectedFolder.set(_folder);
			onUpdate(_folder);
		}
	};

	const deleteHandler = async () => {
		const activeFolder = folder!;

		const res = await deleteFolderById(
			localStorage.token,
			activeFolder.id,
			deleteFolderContents
		).catch((error) => {
			toast.error(`${error}`);
			return null;
		});

		if (res) {
			toast.success($i18n.t('Folder deleted successfully'));
			onDelete(activeFolder);
		}
	};

	const exportHandler = async () => {
		const activeFolder = folder!;

		const chats = await getChatsByFolderId(localStorage.token, activeFolder.id).catch((error) => {
			toast.error(`${error}`);
			return null;
		});
		if (!chats) {
			return;
		}

		const blob = new Blob([JSON.stringify(chats)], {
			type: 'application/json'
		});

		saveAs(blob, `folder-${activeFolder.name}-export-${Date.now()}.json`);
	};
</script>

{#if folder}
	{#if showFolderModal && FolderModalComponent}
		<FolderModalComponent
			bind:show={showFolderModal}
			edit={true}
			folderId={folder.id}
			onSubmit={updateHandler}
		/>
	{/if}

	<DeleteConfirmDialog
		bind:show={showDeleteConfirm}
		title={$i18n.t('Delete folder?')}
		onConfirm={() => {
			deleteHandler();
		}}
	>
		<div class=" text-sm text-gray-700 dark:text-gray-300 flex-1 line-clamp-3 mb-2">
			{$i18n.t(`Are you sure you want to delete "{{NAME}}"?`, {
				NAME: folder?.name
			})}
		</div>

		<div class="flex items-center gap-1.5">
			<input type="checkbox" bind:checked={deleteFolderContents} />

			<div class="text-xs text-gray-500">
				{$i18n.t('Delete all contents inside this folder')}
			</div>
		</div>
	</DeleteConfirmDialog>

	<div class="mb-3 px-6 @md:max-w-3xl justify-between w-full flex relative group items-center">
		<div class="text-center flex gap-3.5 items-center">
			<div
				class="rounded-full bg-gray-50 dark:bg-gray-800 size-11 flex justify-center items-center"
			>
				{#if folder?.meta?.icon}
					<Emoji className="size-6" shortCode={folder.meta.icon} />
				{:else}
					<Folder className="size-4.5" strokeWidth="2" />
				{/if}
			</div>

			<div class="text-3xl line-clamp-1">
				{folder.name}
			</div>
		</div>

		<div class="flex items-center translate-x-2.5">
			<FolderMenu
				align="end"
				onEdit={() => {
					void openFolderModal();
				}}
				onDelete={() => {
					showDeleteConfirm = true;
				}}
				onExport={() => {
					exportHandler();
				}}
			>
				<div class="p-1.5 dark:hover:bg-gray-850 rounded-full touch-auto">
					<EllipsisHorizontal className="size-4" strokeWidth="2.5" />
				</div>
			</FolderMenu>
		</div>
	</div>
{/if}
