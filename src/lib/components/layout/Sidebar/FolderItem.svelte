<script lang="ts">
	import { getContext, onMount, tick, untrack } from 'svelte';

	import { saveAs } from '$lib/utils';

	import { goto } from '$app/navigation';
	import { toast } from 'svelte-sonner';

	import { mobile, selectedFolder, showSidebar } from '$lib/stores';

	import {
		deleteFolderById,
		updateFolderIsExpandedById,
		updateFolderById,
		getFolderById
	} from '$lib/apis/folders';
	import {
		getChatById,
		getChatsByFolderId,
		getChatListByFolderId,
		updateChatFolderIdById,
		importChats
	} from '$lib/apis/chats';

	import ChevronDown from '../../icons/ChevronDown.svelte';
	import ChevronRight from '../../icons/ChevronRight.svelte';
	import Collapsible from '../../common/Collapsible.svelte';
	import DragGhost from '$lib/components/common/DragGhost.svelte';

	import FolderOpen from '$lib/components/icons/FolderOpen.svelte';
	import EllipsisHorizontal from '$lib/components/icons/EllipsisHorizontal.svelte';

	import ChatItem from './ChatItem.svelte';
	import FolderMenu from './Folders/FolderMenu.svelte';
	import ConfirmDialog from '$lib/components/common/ConfirmDialog.svelte';
	import FolderModal from './Folders/FolderModal.svelte';
	import Emoji from '$lib/components/common/Emoji.svelte';
	import Spinner from '$lib/components/common/Spinner.svelte';

	const i18n = getContext('i18n');

	let {
		folderRegistry = $bindable({}),
		open = $bindable(false),
		folders,
		folderId,
		shiftKey = false,
		className = '',
		deleteFolderContents = $bindable(true),
		onDelete = (id: string) => {},
		onItemMove = (e: { originFolderId: string; targetFolderId: string; e: DragEvent }) => {},
		onchange = () => {}
	}: {
		folderRegistry?: Record<string, any>;
		open?: boolean;
		folders: Record<string, any>;
		folderId: string;
		shiftKey?: boolean;
		className?: string;
		deleteFolderContents?: boolean;
		onDelete?: (id: string) => void;
		onItemMove?: (e: { originFolderId: string; targetFolderId: string; e: DragEvent }) => void;
		onchange?: () => void;
	} = $props();

	let folderElement: HTMLDivElement;

	let showFolderModal = $state(false);
	let showDeleteConfirm = $state(false);
	let edit = $state(false);
	let draggedOver = $state(false);
	let dragged = $state(false);
	let name = $state('');
	let x = $state(0);
	let y = $state(0);

	let clickTimer: ReturnType<typeof setTimeout> | null = null;
	let isExpandedUpdateTimeout: ReturnType<typeof setTimeout>;

	/** @type {{id: string; title: string; created_at: number}[] | null} */
	let chats: { id: string; title: string; created_at: number }[] | null = $state(null);

	const setFolderItems = async () => {
		await tick();
		if (open) {
			chats = await getChatListByFolderId(localStorage.token, folderId).catch((error) => {
				toast.error(`${error}`);
				return [];
			});
		} else {
			chats = null;
		}
	};

	$effect(() => {
		if (open) {
			untrack(() => setFolderItems());
		}
	});

	// Drag-and-drop: accept chats dragged onto this folder
	const onDragOver = (e: DragEvent) => {
		e.preventDefault();
		e.stopPropagation();
		if (!dragged) draggedOver = true;
	};

	const onDrop = async (e: DragEvent) => {
		e.preventDefault();
		e.stopPropagation();
		if (dragged) return;

		if (!folderElement.contains(e.target as Node)) return;

		const raw = e.dataTransfer?.getData('text/plain');
		if (!raw) {
			draggedOver = false;
			return;
		}

		try {
			const data = JSON.parse(raw);
			if (data.type !== 'chat') return;

			open = true;
			let chat = await getChatById(localStorage.token, data.id).catch(() => null);

			if (!chat && data.item) {
				chat = await importChats(localStorage.token, [
					{
						chat: data.item.chat,
						meta: data.item?.meta ?? {},
						pinned: false,
						folder_id: null,
						created_at: data.item?.created_at ?? null,
						updated_at: data.item?.updated_at ?? null
					}
				]).catch((error) => {
					toast.error(`${error}`);
					return null;
				});
			}

			if (!chat) return;

			await updateChatFolderIdById(localStorage.token, chat.id, folderId).catch((error) => {
				toast.error(`${error}`);
			});

			onItemMove({ originFolderId: chat.folder_id, targetFolderId: folderId, e });
			onchange();
		} catch {
			// Not valid JSON
		} finally {
			setFolderItems();
			draggedOver = false;
		}
	};

	const onDragLeave = (e: DragEvent) => {
		e.preventDefault();
		if (!dragged) draggedOver = false;
	};

	// Drag ghost for visual feedback
	const transparentPixel = new Image();
	transparentPixel.src =
		'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=';

	const onDragStart = (event: DragEvent) => {
		event.stopPropagation();
		event.dataTransfer!.setDragImage(transparentPixel, 0, 0);
		event.dataTransfer!.setData('text/plain', JSON.stringify({ type: 'chat', id: folderId }));
		dragged = true;
		folderElement.style.opacity = '0.5';
	};

	const onDragMove = (event: DragEvent) => {
		event.stopPropagation();
		x = event.clientX;
		y = event.clientY;
	};

	const onDragEnd = (event: DragEvent) => {
		event.stopPropagation();
		folderElement.style.opacity = '1';
		dragged = false;
	};

	onMount(() => {
		open = folders[folderId].is_expanded;
		folderRegistry[folderId] = { setFolderItems };

		folderElement.addEventListener('dragover', onDragOver);
		folderElement.addEventListener('drop', onDrop);
		folderElement.addEventListener('dragleave', onDragLeave);
		folderElement.addEventListener('dragstart', onDragStart);
		folderElement.addEventListener('drag', onDragMove);
		folderElement.addEventListener('dragend', onDragEnd);

		if (folders[folderId]?.new) {
			delete folders[folderId].new;
			tick().then(() => renameHandler());
		}

		return () => {
			folderElement.removeEventListener('dragover', onDragOver);
			folderElement.removeEventListener('drop', onDrop);
			folderElement.removeEventListener('dragleave', onDragLeave);
			folderElement.removeEventListener('dragstart', onDragStart);
			folderElement.removeEventListener('drag', onDragMove);
			folderElement.removeEventListener('dragend', onDragEnd);
		};
	});

	const deleteHandler = async () => {
		const res = await deleteFolderById(localStorage.token, folderId, deleteFolderContents).catch(
			(error) => {
				toast.error(`${error}`);
				return null;
			}
		);

		if (res) {
			toast.success($i18n.t('Folder deleted successfully'));
			onDelete(folderId);
		}
	};

	const updateHandler = async ({ name, meta, data }: { name?: string; meta?: any; data?: any }) => {
		if (name === '') {
			toast.error($i18n.t('Folder name cannot be empty.'));
			return;
		}

		const currentName = folders[folderId].name;

		if (name) {
			name = name.trim();
			folders[folderId].name = name;
		}

		const res = await updateFolderById(localStorage.token, folderId, {
			...(name ? { name } : {}),
			...(meta ? { meta } : {}),
			...(data ? { data } : {})
		}).catch((error) => {
			toast.error(`${error}`);
			folders[folderId].name = currentName;
			return null;
		});

		if (res) {
			if (name) folders[folderId].name = name;
			if (data) folders[folderId].data = data;

			toast.success($i18n.t('Folder updated successfully'));

			if ($selectedFolder?.id === folderId) {
				const folder = await getFolderById(localStorage.token, folderId).catch(() => null);
				if (folder) await selectedFolder.set(folder);
			}
			onchange();
		}
	};

	const isExpandedUpdateDebounced = () => {
		clearTimeout(isExpandedUpdateTimeout);
		isExpandedUpdateTimeout = setTimeout(() => {
			updateFolderIsExpandedById(localStorage.token, folderId, open);
		}, 500);
	};

	const renameHandler = async () => {
		name = folders[folderId].name;
		edit = true;
		await tick();
		await tick();
		const input = document.getElementById(`folder-${folderId}-input`);
		if (input) {
			input.focus();
			(input as HTMLInputElement).select();
		}
	};

	const exportHandler = async () => {
		const chats = await getChatsByFolderId(localStorage.token, folderId).catch((error) => {
			toast.error(`${error}`);
			return null;
		});
		if (!chats) return;

		const blob = new Blob([JSON.stringify(chats)], { type: 'application/json' });
		saveAs(blob, `folder-${folders[folderId].name}-export-${Date.now()}.json`);
	};
</script>

<ConfirmDialog
	bind:show={showDeleteConfirm}
	title={$i18n.t('Delete folder?')}
	onConfirm={() => deleteHandler()}
>
	<div class="text-sm text-gray-700 dark:text-gray-300 flex-1 line-clamp-3 mb-2">
		{$i18n.t(`Are you sure you want to delete "{{NAME}}"?`, {
			NAME: folders[folderId].name
		})}
	</div>

	<div class="flex items-center gap-1.5">
		<input type="checkbox" bind:checked={deleteFolderContents} />
		<div class="text-xs text-gray-500">
			{$i18n.t('Delete all contents inside this folder')}
		</div>
	</div>
</ConfirmDialog>

<FolderModal bind:show={showFolderModal} edit={true} {folderId} onSubmit={updateHandler} />

{#if dragged && x && y}
	<DragGhost {x} {y}>
		<div class="bg-black/80 backdrop-blur-2xl px-2 py-1 rounded-lg w-fit max-w-40">
			<div class="flex items-center gap-1">
				<FolderOpen className="size-3.5" strokeWidth="2" />
				<div class="text-xs text-white line-clamp-1">
					{folders[folderId].name}
				</div>
			</div>
		</div>
	</DragGhost>
{/if}

<div bind:this={folderElement} class="relative {className}" draggable="true">
	{#if draggedOver}
		<div
			class="absolute top-0 left-0 w-full h-full rounded-xs bg-gray-100/50 dark:bg-gray-700/20 bg-opacity-50 dark:bg-opacity-10 z-50 pointer-events-none touch-none"
		></div>
	{/if}

	<Collapsible bind:open className="w-full" buttonClassName="w-full">
		<!-- svelte-ignore a11y-no-static-element-interactions -->
		<div class="w-full group">
			<div
				id="folder-{folderId}-button"
				class="relative w-full py-1 px-1.5 rounded-xl flex items-center gap-1.5 hover:bg-gray-100 dark:hover:bg-gray-900 transition {$selectedFolder?.id ===
				folderId
					? 'bg-gray-100 dark:bg-gray-900 selected'
					: ''}"
				ondblclick={() => {
					if (clickTimer) {
						clearTimeout(clickTimer);
						clickTimer = null;
					}
					renameHandler();
				}}
				onclick={(e) => {
					e.stopPropagation();
					if (clickTimer) {
						clearTimeout(clickTimer);
						clickTimer = null;
					}

					clickTimer = setTimeout(async () => {
						const folder = await getFolderById(localStorage.token, folderId).catch(() => null);
						if (folder) await selectedFolder.set(folder);
						await goto('/');
						if ($mobile) showSidebar.set(!$showSidebar);
						clickTimer = null;
					}, 100);
				}}
				onpointerup={(e) => e.stopPropagation()}
			>
				<button
					class="text-gray-500 dark:text-gray-500 transition-all p-1 hover:bg-gray-200 dark:hover:bg-gray-850 rounded-lg"
					onclick={(e) => {
						e.stopPropagation();
						e.stopImmediatePropagation();
						open = !open;
						isExpandedUpdateDebounced();
					}}
				>
					{#if folders[folderId]?.meta?.icon}
						<div class="flex group-hover:hidden transition-all">
							<Emoji className="size-3.5" shortCode={folders[folderId].meta.icon} />
						</div>

						<div class="hidden group-hover:flex transition-all p-[1px]">
							{#if open}
								<ChevronDown className="size-3" strokeWidth="2.5" />
							{:else}
								<ChevronRight className="size-3" strokeWidth="2.5" />
							{/if}
						</div>
					{:else}
						<div class="p-[1px]">
							{#if open}
								<ChevronDown className="size-3" strokeWidth="2.5" />
							{:else}
								<ChevronRight className="size-3" strokeWidth="2.5" />
							{/if}
						</div>
					{/if}
				</button>

				<div class="translate-y-[0.5px] flex-1 justify-start text-start line-clamp-1">
					{#if edit}
						<input
							id="folder-{folderId}-input"
							type="text"
							bind:value={name}
							onblur={() => {
								updateHandler({ name });
								edit = false;
							}}
							onclick={(e) => e.stopPropagation()}
							onmousedown={(e) => e.stopPropagation()}
							onkeydown={(e) => {
								if (e.key === 'Enter') {
									updateHandler({ name });
									edit = false;
								}
							}}
							class="w-full h-full bg-transparent outline-hidden"
						/>
					{:else}
						{folders[folderId].name}
					{/if}
				</div>

				<button
					class="absolute z-10 right-2 invisible group-hover:visible self-center flex items-center dark:text-gray-300"
				>
					<FolderMenu
						onEdit={() => {
							showFolderModal = true;
						}}
						onDelete={() => {
							showDeleteConfirm = true;
						}}
						onExport={() => {
							exportHandler();
						}}
					>
						<div class="p-1 dark:hover:bg-gray-850 rounded-lg touch-auto">
							<EllipsisHorizontal className="size-4" strokeWidth="2.5" />
						</div>
					</FolderMenu>
				</button>
			</div>
		</div>

		<div slot="content" class="w-full">
			{#if (chats ?? []).length > 0}
				<div
					class="ml-3 pl-1 mt-[1px] flex flex-col overflow-y-auto scrollbar-hidden border-s border-gray-100 dark:border-gray-900"
				>
					{#each chats ?? [] as chat (chat.id)}
						<ChatItem
							id={chat.id}
							title={chat.title}
							createdAt={chat.created_at}
							{shiftKey}
							on:change={() => onchange()}
						/>
					{/each}
				</div>
			{/if}

			{#if chats === null}
				<div class="flex justify-center items-center p-2">
					<Spinner className="size-4 text-gray-500" />
				</div>
			{/if}
		</div>
	</Collapsible>
</div>
