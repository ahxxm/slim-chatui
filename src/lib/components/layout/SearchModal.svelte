<script lang="ts">
	import { toast } from 'svelte-sonner';
	import { getContext, onDestroy, onMount, tick, type ComponentType, untrack } from 'svelte';
	const i18n = getContext('i18n');

	import Modal from '$lib/components/common/Modal.svelte';
	import SearchInput from './Sidebar/SearchInput.svelte';
	import { getChatById, getChatList, getChatListBySearchText } from '$lib/apis/chats';
	import Spinner from '../common/Spinner.svelte';

	import dayjs from '$lib/dayjs';
	import localizedFormat from 'dayjs/plugin/localizedFormat';
	import calendar from 'dayjs/plugin/calendar';
	import Loader from '../common/Loader.svelte';
	import { createMessagesList } from '$lib/utils';
	import { toPreviewText } from '$lib/utils/preview-text';
	import { PAGE_SIZE } from '$lib/stores';
	import { goto } from '$app/navigation';
	import PencilSquare from '../icons/PencilSquare.svelte';
	import type { ChatListItem } from '$lib/types';
	dayjs.extend(calendar);
	dayjs.extend(localizedFormat);

	type SearchAction = {
		label: string;
		onClick: () => Promise<void>;
		icon: ComponentType;
	};

	type ChatPreviewMessage = {
		id: string;
		role: string;
		modelName?: string;
		text: string;
	};

	type ChatPreviewHistory = {
		messages: Record<string, any>;
		currentId: string | null;
	};

	type ChatPreviewResponse = {
		chat?: {
			history?: ChatPreviewHistory | null;
		} | null;
	};

	let { show = $bindable(false), onClose = () => {} }: { show?: boolean; onClose?: () => void } =
		$props();

	let actions: SearchAction[] = [
		{
			label: $i18n.t('Start a new conversation'),
			onClick: async () => {
				await goto(`/${query ? `?q=${query}` : ''}`);
				show = false;
				onClose();
			},
			icon: PencilSquare
		}
	];

	let query = $state('');
	let page = $state(1);

	let chatList = $state<ChatListItem[] | null>(null);

	let chatListLoading = $state(false);
	let allChatsLoaded = $state(false);

	let searchDebounceTimeout: ReturnType<typeof setTimeout> | null = null;

	let selectedIdx = $state<number | null>(null);
	let previewMessages = $state<ChatPreviewMessage[] | null>(null);
	let previewLoading = $state(false);
	let previewRequestId = 0;

	const getSearchInput = () => document.getElementById('search-input') as HTMLInputElement | null;
	const getSelectedItem = () => document.querySelector<HTMLElement>(`[data-arrow-selected="true"]`);
	const getMaxSelectableIndex = () => Math.max(actions.length + (chatList?.length ?? 0) - 1, 0);
	const getNextSelectedIdx = (offset: number) => {
		const baseIndex = selectedIdx ?? (offset > 0 ? -1 : 0);
		return Math.min(Math.max(baseIndex + offset, 0), getMaxSelectableIndex());
	};
	const scrollSelectedItemIntoView = () => {
		getSelectedItem()?.scrollIntoView({ block: 'center', inline: 'nearest', behavior: 'instant' });
	};
	const clearSearchDebounce = () => {
		if (searchDebounceTimeout) {
			clearTimeout(searchDebounceTimeout);
			searchDebounceTimeout = null;
		}
	};
	const loadChatPage = async (searchQuery: string, pageNumber: number): Promise<ChatListItem[]> => {
		if (searchQuery) {
			return await getChatListBySearchText(localStorage.token, searchQuery, pageNumber);
		}

		return await getChatList(localStorage.token, pageNumber);
	};
	const buildPreviewMessages = (chat: ChatPreviewResponse): ChatPreviewMessage[] => {
		const history = chat.chat?.history;
		if (!history) {
			return [];
		}

		return createMessagesList(history, history.currentId)
			.slice(-12)
			.map((message) => ({
				id: message.id,
				role: message.role,
				modelName: message.modelName,
				text: toPreviewText(message?.merged?.content ?? message?.content ?? '')
			}));
	};

	$effect(() => {
		if (!chatListLoading && chatList) {
			untrack(() => loadChatPreview(selectedIdx));
		}
	});

	const loadChatPreview = async (selectedIdx: number | null) => {
		if (!chatList || chatList.length === 0 || selectedIdx === null) {
			previewMessages = null;
			previewLoading = false;
			return;
		}

		const selectedChatIdx = selectedIdx - actions.length;
		if (selectedChatIdx < 0 || selectedChatIdx >= chatList.length) {
			previewMessages = null;
			previewLoading = false;
			return;
		}

		const chatId = chatList[selectedChatIdx].id;
		const requestId = ++previewRequestId;
		previewLoading = true;

		const chat = await getChatById(localStorage.token, chatId).catch(() => null);

		if (requestId !== previewRequestId) {
			return;
		}

		if (chat) {
			previewMessages = chat?.chat?.history ? buildPreviewMessages(chat) : [];

			await tick();
			const messagesContainerElement = document.getElementById('chat-preview');
			if (messagesContainerElement) {
				messagesContainerElement.scrollTop = messagesContainerElement.scrollHeight;
			}
		} else {
			toast.error($i18n.t('Failed to load chat preview'));
			previewMessages = null;
			previewLoading = false;
			return;
		}

		previewLoading = false;
	};

	const searchHandler = async () => {
		if (!show) {
			return;
		}

		clearSearchDebounce();

		page = 1;
		chatList = null;
		allChatsLoaded = false;
		previewMessages = null;
		previewLoading = false;

		if (query === '') {
			const nextChatList = await loadChatPage('', 1);
			chatList = nextChatList;
			allChatsLoaded = nextChatList.length < PAGE_SIZE;
			return;
		}

		const nextQuery = query;
		searchDebounceTimeout = setTimeout(async () => {
			if (!show) {
				searchDebounceTimeout = null;
				return;
			}

			const nextChatList = await loadChatPage(nextQuery, 1);
			chatList = nextChatList;
			allChatsLoaded = nextChatList.length < PAGE_SIZE;
			searchDebounceTimeout = null;
		}, 500);
	};

	const loadMoreChats = async () => {
		chatListLoading = true;
		const nextPage = page + 1;
		page = nextPage;

		const newChatList = await loadChatPage(query, nextPage);

		allChatsLoaded = newChatList.length < PAGE_SIZE;

		if (newChatList.length > 0) {
			chatList = [...(chatList ?? []), ...newChatList];
		}

		chatListLoading = false;
	};

	$effect(() => {
		if (show) {
			untrack(() => searchHandler());
		}
	});

	const onKeyDown = (e: KeyboardEvent) => {
		const searchOptions = document.getElementById('search-options-container');
		if (searchOptions || !show) {
			return;
		}

		if (e.code === 'Escape') {
			show = false;
			onClose();
		} else if (e.code === 'Enter') {
			const item = getSelectedItem();
			if (item) {
				item.click();
				show = false;
			}

			return;
		} else if (e.code === 'ArrowDown') {
			const searchInput = getSearchInput();

			if (searchInput) {
				// check if focused on the search input
				if (document.activeElement === searchInput) {
					searchInput.blur();
					selectedIdx = 0;
					return;
				}
			}

			selectedIdx = getNextSelectedIdx(1);
		} else if (e.code === 'ArrowUp') {
			if (selectedIdx === 0) {
				const searchInput = getSearchInput();

				if (searchInput) {
					// check if focused on the search input
					if (document.activeElement !== searchInput) {
						searchInput.focus();
						selectedIdx = 0;
						return;
					}
				}
			}

			selectedIdx = getNextSelectedIdx(-1);
		}

		scrollSelectedItemIntoView();
	};

	onMount(() => {
		document.addEventListener('keydown', onKeyDown);
	});

	onDestroy(() => {
		clearSearchDebounce();
		document.removeEventListener('keydown', onKeyDown);
	});
</script>

<Modal size="xl" bind:show>
	<div class="py-3 dark:text-gray-300 text-gray-700">
		<div class="px-4 pb-1.5">
			<SearchInput
				bind:value={query}
				onSearchInput={searchHandler}
				placeholder={$i18n.t('Search')}
				showClearButton={true}
				onFocus={() => {
					selectedIdx = null;
					previewMessages = null;
					previewLoading = false;
				}}
				onKeydown={(e: KeyboardEvent) => {
					if (e.code === 'Enter' && (chatList ?? []).length > 0) {
						const item = getSelectedItem();
						if (item) {
							item.click();
						}

						show = false;
						return;
					} else if (e.code === 'ArrowDown') {
						selectedIdx = getNextSelectedIdx(1);
					} else if (e.code === 'ArrowUp') {
						selectedIdx = getNextSelectedIdx(-1);
					} else {
						selectedIdx = 0;
					}

					scrollSelectedItemIntoView();
				}}
			/>
		</div>

		<!-- <hr class="border-gray-50 dark:border-gray-850/30 my-1" /> -->

		<div class="flex px-4 pb-1">
			<div
				class="flex flex-col overflow-y-auto h-96 md:h-[40rem] max-h-full scrollbar-hidden w-full flex-1 pr-2"
			>
				<div class="w-full text-xs text-gray-500 dark:text-gray-500 font-medium pb-2 px-2">
					{$i18n.t('Actions')}
				</div>

				{#each actions as action, idx (action.label)}
					<button
						class=" w-full flex items-center rounded-xl text-sm py-2 px-3 hover:bg-gray-50 dark:hover:bg-gray-850 {selectedIdx ===
						idx
							? 'bg-gray-50 dark:bg-gray-850'
							: ''}"
						data-arrow-selected={selectedIdx === idx ? 'true' : undefined}
						draggable="false"
						onmouseenter={() => {
							selectedIdx = idx;
						}}
						onclick={async () => {
							await action.onClick();
						}}
					>
						<div class="pr-2">
							<action.icon />
						</div>
						<div class=" flex-1 text-left">
							<div class="text-ellipsis line-clamp-1 w-full">
								{$i18n.t(action.label)}
							</div>
						</div>
					</button>
				{/each}

				{#if chatList}
					<hr class="border-gray-50 dark:border-gray-850/30 my-3" />

					{#if chatList.length === 0}
						<div class="text-xs text-gray-500 dark:text-gray-400 text-center px-5 py-4">
							{$i18n.t('No results found')}
						</div>
					{/if}

					{#each chatList as chat, idx (chat.id)}
						{#if idx === 0 || (idx > 0 && chat.time_range !== chatList[idx - 1].time_range)}
							{@const timeRange = chat.time_range ?? ''}
							<div
								class="w-full text-xs text-gray-500 dark:text-gray-500 font-medium {idx === 0
									? ''
									: 'pt-5'} pb-2 px-2"
							>
								{$i18n.t(timeRange)}
								<!-- localisation keys for time_range to be recognized from the i18next parser (so they don't get automatically removed):
							{$i18n.t('Today')}
							{$i18n.t('Yesterday')}
							{$i18n.t('Previous 7 days')}
							{$i18n.t('Previous 30 days')}
							{$i18n.t('January')}
							{$i18n.t('February')}
							{$i18n.t('March')}
							{$i18n.t('April')}
							{$i18n.t('May')}
							{$i18n.t('June')}
							{$i18n.t('July')}
							{$i18n.t('August')}
							{$i18n.t('September')}
							{$i18n.t('October')}
							{$i18n.t('November')}
							{$i18n.t('December')}
							-->
							</div>
						{/if}

						<a
							class=" w-full flex justify-between items-center rounded-xl text-sm py-2 px-3 hover:bg-gray-50 dark:hover:bg-gray-850 {selectedIdx ===
							idx + actions.length
								? 'bg-gray-50 dark:bg-gray-850'
								: ''}"
							href="/c/{chat.id}"
							draggable="false"
							data-arrow-selected={selectedIdx === idx + actions.length ? 'true' : undefined}
							onmouseenter={() => {
								selectedIdx = idx + actions.length;
							}}
							onclick={async () => {
								await goto(`/c/${chat.id}`);
								show = false;
								onClose();
							}}
						>
							<div class=" flex-1">
								<div class="text-ellipsis line-clamp-1 w-full">
									{chat?.title}
								</div>
							</div>

							<div class=" pl-3 shrink-0 text-gray-500 dark:text-gray-400 text-xs">
								{$i18n.t(
									dayjs(chat?.updated_at * 1000).calendar(null, {
										sameDay: '[Today]',
										nextDay: '[Tomorrow]',
										nextWeek: 'dddd',
										lastDay: '[Yesterday]',
										lastWeek: '[Last] dddd',
										sameElse: 'L' // use localized format, otherwise dayjs.calendar() defaults to DD/MM/YYYY
									})
								)}
							</div>
						</a>
					{/each}

					{#if !allChatsLoaded}
						<Loader
							onvisible={() => {
								if (!chatListLoading) {
									loadMoreChats();
								}
							}}
						>
							<div class="w-full flex justify-center py-4 text-xs animate-pulse items-center gap-2">
								<Spinner className=" size-4" />
								<div class=" ">{$i18n.t('Loading...')}</div>
							</div>
						</Loader>
					{/if}
				{:else}
					<div class="w-full h-full flex justify-center items-center">
						<Spinner className="size-5" />
					</div>
				{/if}
			</div>
			<div
				id="chat-preview"
				class="hidden md:flex md:flex-1 w-full overflow-y-auto h-96 md:h-[40rem] scrollbar-hidden"
			>
				{#if previewLoading}
					<div class="w-full h-full flex justify-center items-center">
						<Spinner className="size-5" />
					</div>
				{:else if previewMessages === null}
					<div
						class="w-full h-full flex justify-center items-center text-gray-500 dark:text-gray-400 text-sm"
					>
						{$i18n.t('Select a conversation to preview')}
					</div>
				{:else}
					<div class="w-full h-full flex flex-col gap-2 pr-2 py-1">
						{#if previewMessages.length === 0}
							<div
								class="w-full h-full flex justify-center items-center text-gray-500 dark:text-gray-400 text-sm"
							>
								{$i18n.t('No messages')}
							</div>
						{:else}
							{#each previewMessages as message (message.id)}
								<div
									class="rounded-2xl border border-gray-100 bg-white px-3 py-2 text-sm dark:border-gray-800 dark:bg-gray-900"
								>
									<div class="text-[11px] font-medium text-gray-500 dark:text-gray-400">
										{message.role === 'user'
											? $i18n.t('You')
											: message.modelName || $i18n.t('Assistant')}
									</div>
									<div
										class="mt-1 whitespace-pre-wrap break-words text-gray-700 dark:text-gray-200"
									>
										{message.text || $i18n.t('No text content')}
									</div>
								</div>
							{/each}
						{/if}
					</div>
				{/if}
			</div>
		</div>
	</div>
</Modal>
