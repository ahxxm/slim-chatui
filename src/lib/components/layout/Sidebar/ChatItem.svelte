<script lang="ts">
	import { toast } from 'svelte-sonner';
	import { goto } from '$app/navigation';
	import { onMount, getContext, tick, onDestroy } from 'svelte';
	const i18n = getContext('i18n');

	import {
		cloneChatById,
		deleteChatById,
		getChatById,
		updateChatById,
		updateChatFolderIdById
	} from '$lib/apis/chats';
	import {
		chatId,
		chatTitle as _chatTitle,
		mobile,
		showSidebar,
		selectedFolder,
		activeChatIds
	} from '$lib/stores';

	import ChatMenu from './ChatMenu.svelte';
	import DeleteConfirmDialog from '$lib/components/common/ConfirmDialog.svelte';
	import GarbageBin from '$lib/components/icons/GarbageBin.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import DragGhost from '$lib/components/common/DragGhost.svelte';
	import Document from '$lib/components/icons/Document.svelte';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import { generateTitle } from '$lib/apis';

	let {
		className = '',
		id,
		title,
		createdAt = null,
		selected = false,
		shiftKey = false,
		onDragEnd = () => {},
		onselect = () => {},
		onunselect = () => {},
		onchange = () => {}
	}: {
		className?: string;
		id: string;
		title: string;
		createdAt?: number | null;
		selected?: boolean;
		shiftKey?: boolean;
		onDragEnd?: (event: DragEvent) => void;
		onselect?: () => void;
		onunselect?: () => void;
		onchange?: () => void;
	} = $props();

	function formatTimeAgo(timestamp: number): string {
		const now = Date.now();
		const diff = now - timestamp * 1000; // timestamp is in seconds

		const seconds = Math.floor(diff / 1000);
		const minutes = Math.floor(seconds / 60);
		const hours = Math.floor(minutes / 60);
		const days = Math.floor(hours / 24);
		const weeks = Math.floor(days / 7);
		const years = Math.floor(days / 365);

		if (years > 0) return `${years}y`;
		if (weeks > 0) return `${weeks}w`;
		if (days > 0) return `${days}d`;
		if (hours > 0) return `${hours}h`;
		if (minutes > 0) return `${minutes}m`;
		return '1m';
	}

	let chat = $state(null);

	let mouseOver = $state(false);

	const cloneChatHandler = async (id) => {
		const res = await cloneChatById(
			localStorage.token,
			id,
			$i18n.t('Clone of {{TITLE}}', {
				TITLE: title
			})
		).catch((error) => {
			toast.error(`${error}`);
			return null;
		});

		if (res) {
			goto(`/c/${res.id}`);
			onchange();
		}
	};

	const deleteChatHandler = async (id) => {
		const res = await deleteChatById(localStorage.token, id).catch((error) => {
			toast.error(`${error}`);
			return null;
		});

		if (res) {
			if ($chatId === id) {
				await goto('/');

				await chatId.set('');
				await tick();
			}

			onchange();
		}
	};

	const moveChatHandler = async (chatId, folderId) => {
		if (chatId && folderId) {
			const res = await updateChatFolderIdById(localStorage.token, chatId, folderId).catch(
				(error) => {
					toast.error(`${error}`);
					return null;
				}
			);

			if (res) {
				onchange();
				toast.success($i18n.t('Chat moved successfully'));
			}
		} else {
			toast.error($i18n.t('Failed to move chat'));
		}
	};

	let itemElement = $state<HTMLElement>();

	let generating = false;

	let dragged = $state(false);
	let x = $state(0);
	let y = $state(0);

	const dragImage = new Image();
	dragImage.src =
		'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=';

	const onDragStart = (event) => {
		event.stopPropagation();

		event.dataTransfer.setDragImage(dragImage, 0, 0);

		// Set the data to be transferred
		event.dataTransfer.setData(
			'text/plain',
			JSON.stringify({
				type: 'chat',
				id: id
			})
		);

		dragged = true;
		itemElement.style.opacity = '0.5'; // Optional: Visual cue to show it's being dragged
	};

	const onDrag = (event) => {
		event.stopPropagation();

		x = event.clientX;
		y = event.clientY;
	};

	const onDragEndHandler = (event) => {
		event.stopPropagation();

		itemElement.style.opacity = '1'; // Reset visual cue after drag
		dragged = false;

		onDragEnd(event);
	};

	onMount(() => {
		if (itemElement) {
			itemElement.addEventListener('dragstart', onDragStart);
			itemElement.addEventListener('drag', onDrag);
			itemElement.addEventListener('dragend', onDragEndHandler);
		}
	});

	onDestroy(() => {
		if (itemElement) {
			itemElement.removeEventListener('dragstart', onDragStart);
			itemElement.removeEventListener('drag', onDrag);
			itemElement.removeEventListener('dragend', onDragEndHandler);
		}
	});

	let showDeleteConfirm = $state(false);

	const generateTitleHandler = async () => {
		if (generating) return;
		generating = true;

		if (!chat) {
			chat = await getChatById(localStorage.token, id);
		}

		const messages = (chat.chat?.messages ?? []).map((message) => ({
			role: message.role,
			content: message.content
		}));

		const model = chat.chat.models.at(0) ?? chat.models.at(0) ?? '';

		const generatedTitle = await generateTitle(localStorage.token, model, messages).catch(
			(error) => {
				toast.error(`${error}`);
				return null;
			}
		);

		if (generatedTitle && generatedTitle !== title) {
			await updateChatById(localStorage.token, id, { title: generatedTitle });
			if (id === $chatId) {
				_chatTitle.set(generatedTitle);
			}
			onchange();
		}

		generating = false;
	};
</script>

<DeleteConfirmDialog
	bind:show={showDeleteConfirm}
	title={$i18n.t('Delete chat?')}
	onConfirm={() => {
		deleteChatHandler(id);
	}}
>
	<div class=" text-sm text-gray-500 flex-1 line-clamp-3">
		{$i18n.t('This will delete')} <span class="  font-semibold">{title}</span>.
	</div>
</DeleteConfirmDialog>

{#if dragged && x && y}
	<DragGhost {x} {y}>
		<div class=" bg-black/80 backdrop-blur-2xl px-2 py-1 rounded-lg w-fit max-w-40">
			<div class="flex items-center gap-1">
				<Document className=" size-[18px]" strokeWidth="2" />
				<div class=" text-xs text-white line-clamp-1">
					{title}
				</div>
			</div>
		</div>
	</DragGhost>
{/if}

<div
	id="sidebar-chat-group"
	bind:this={itemElement}
	class=" w-full {className} relative group"
	draggable={true}
>
	<a
		id="sidebar-chat-item"
		class=" w-full flex justify-between rounded-xl px-[11px] py-[6px] {id === $chatId
			? 'bg-gray-100 dark:bg-gray-900 selected'
			: selected
				? 'bg-gray-100 dark:bg-gray-950 selected'
				: ' group-hover:bg-gray-100 dark:group-hover:bg-gray-950'}  whitespace-nowrap text-ellipsis"
		href="/c/{id}"
		onclick={() => {
			onselect();

			if ($selectedFolder) {
				selectedFolder.set(null);
			}

			if ($mobile) {
				showSidebar.set(false);
			}
		}}
		onmouseenter={() => {
			mouseOver = true;
		}}
		onmouseleave={() => {
			mouseOver = false;
		}}
		onfocus={() => {}}
		draggable="false"
	>
		{#if $activeChatIds.has(id)}
			<div class="shrink-0 self-center pr-2">
				<Spinner className="size-3" />
			</div>
		{/if}

		<div class="flex self-center flex-1 w-full min-w-0">
			<div dir="auto" class="text-left self-center overflow-hidden w-full h-[20px] truncate">
				{title}
			</div>
		</div>

		{#if createdAt && !mouseOver}
			<div class="shrink-0 self-center text-[10px] text-gray-400 dark:text-gray-500 pl-2">
				{formatTimeAgo(createdAt)}
			</div>
		{/if}
	</a>

	<!-- svelte-ignore a11y-no-static-element-interactions -->
	<div
		id="sidebar-chat-item-menu"
		class="
        {id === $chatId
			? 'from-gray-100 dark:from-gray-900 selected'
			: selected
				? 'from-gray-100 dark:from-gray-950 selected'
				: 'invisible group-hover:visible from-gray-100 dark:from-gray-950'}
            absolute {className === 'pr-2'
			? 'right-[8px]'
			: 'right-1'} top-[4px] py-1 pr-0.5 mr-1.5 pl-5 bg-linear-to-l from-80%

              to-transparent"
		onmouseenter={() => {
			mouseOver = true;
		}}
		onmouseleave={() => {
			mouseOver = false;
		}}
	>
		{#if shiftKey && mouseOver}
			<div class=" flex items-center self-center space-x-1.5">
				<Tooltip content={$i18n.t('Delete')}>
					<button
						class=" self-center dark:hover:text-white transition"
						aria-label="Delete chat"
						onclick={() => {
							deleteChatHandler(id);
						}}
						type="button"
					>
						<GarbageBin strokeWidth="2" />
					</button>
				</Tooltip>
			</div>
		{:else}
			<div class="flex self-center z-10 items-end">
				<ChatMenu
					chatId={id}
					cloneChatHandler={() => {
						cloneChatHandler(id);
					}}
					{moveChatHandler}
					renameHandler={generateTitleHandler}
					deleteHandler={() => {
						showDeleteConfirm = true;
					}}
					onClose={() => {
						onunselect();
					}}
					{onchange}
				>
					<button
						aria-label="Chat Menu"
						class=" self-center dark:hover:text-white transition m-0"
						onclick={() => {
							onselect();
						}}
					>
						<svg
							xmlns="http://www.w3.org/2000/svg"
							viewBox="0 0 16 16"
							fill="currentColor"
							class="w-4 h-4"
						>
							<path
								d="M2 8a1.5 1.5 0 1 1 3 0 1.5 1.5 0 0 1-3 0ZM6.5 8a1.5 1.5 0 1 1 3 0 1.5 1.5 0 0 1-3 0ZM12.5 6.5a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3Z"
							/>
						</svg>
					</button>
				</ChatMenu>

				{#if id === $chatId}
					<!-- Shortcut support using "delete-chat-button" id -->
					<button
						id="delete-chat-button"
						class="hidden"
						onclick={() => {
							showDeleteConfirm = true;
						}}
					>
						<svg
							xmlns="http://www.w3.org/2000/svg"
							viewBox="0 0 16 16"
							fill="currentColor"
							class="w-4 h-4"
						>
							<path
								d="M2 8a1.5 1.5 0 1 1 3 0 1.5 1.5 0 0 1-3 0ZM6.5 8a1.5 1.5 0 1 1 3 0 1.5 1.5 0 0 1-3 0ZM12.5 6.5a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3Z"
							/>
						</svg>
					</button>
				{/if}
			</div>
		{/if}
	</div>
</div>
