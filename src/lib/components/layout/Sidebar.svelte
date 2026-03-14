<script lang="ts">
	import { toast } from 'svelte-sonner';
	import { v4 as uuidv4 } from 'uuid';

	import { goto } from '$app/navigation';
	import { browser } from '$app/environment';
	import { get } from 'svelte/store';
	import {
		user,
		chats,
		settings,
		chatId,
		folders as _folders,
		showSidebar,
		showSearch,
		mobile,
		pinnedChats,
		scrollPaginationEnabled,
		currentChatPage,
		temporaryChatEnabled,
		socket,
		models,
		selectedFolder,
		WEBUI_NAME,
		sidebarWidth,
		activeChatIds,
		refreshChatList,
		PAGE_SIZE
	} from '$lib/stores';
	import { onMount, getContext, tick, untrack } from 'svelte';

	const i18n = getContext('i18n');

	import {
		getChatList,
		getPinnedChatList,
		toggleChatPinnedStatusById,
		getChatById,
		updateChatFolderIdById,
		importChats
	} from '$lib/apis/chats';
	import { createNewFolder, getFolders } from '$lib/apis/folders';
	import { checkActiveChats } from '$lib/apis/tasks';
	import { WEBUI_BASE_URL } from '$lib/constants';

	import UserMenu from './Sidebar/UserMenu.svelte';
	import ChatItem from './Sidebar/ChatItem.svelte';
	import Spinner from '../common/Spinner.svelte';
	import Loader from '../common/Loader.svelte';
	import Folder from '../common/Folder.svelte';
	import Tooltip from '../common/Tooltip.svelte';
	import Folders from './Sidebar/Folders.svelte';
	import PencilSquare from '../icons/PencilSquare.svelte';
	import Search from '../icons/Search.svelte';
	import SearchModal from './SearchModal.svelte';
	import FolderModal from './Sidebar/Folders/FolderModal.svelte';
	import Sidebar from '../icons/Sidebar.svelte';
	import PinnedModelList from './Sidebar/PinnedModelList.svelte';
	import { slide } from 'svelte/transition';
	import HotkeyHint from '../common/HotkeyHint.svelte';

	let scrollTop = $state(0);

	let navElement = $state<HTMLElement | undefined>();
	let shiftKey = $state(false);

	let selectedChatId = $state<string | null>(null);
	let chatListLoading = $state(false);
	let allChatsLoaded = $state(false);

	let showCreateFolderModal = $state(false);

	let showPinnedModels = $derived(($settings?.pinnedModels ?? []).length > 0);
	let showFolders = $state(false);

	let folders = $state<Record<string, any>>({});
	let folderRegistry = $state<Record<string, any>>({});

	const initFolders = async () => {
		const folderList = await getFolders(localStorage.token).catch(() => []);
		_folders.set(folderList.sort((a, b) => b.updated_at - a.updated_at));

		folders = {};

		// First pass: Initialize all folder entries
		for (const folder of folderList) {
			folders[folder.id] = { ...(folders[folder.id] || {}), ...folder };
		}
	};

	const createFolder = async ({ name, data }) => {
		name = name?.trim();
		if (!name) {
			toast.error($i18n.t('Folder name cannot be empty.'));
			return;
		}

		const allFolders = Object.values(folders);
		if (allFolders.find((folder) => folder.name.toLowerCase() === name.toLowerCase())) {
			let i = 1;
			while (
				allFolders.find((folder) => folder.name.toLowerCase() === `${name} ${i}`.toLowerCase())
			) {
				i++;
			}

			name = `${name} ${i}`;
		}

		const tempId = uuidv4();
		folders = {
			...folders,
			tempId: {
				id: tempId,
				name: name,
				created_at: Date.now(),
				updated_at: Date.now()
			}
		};

		const res = await createNewFolder(localStorage.token, {
			name,
			data
		}).catch((error) => {
			toast.error(`${error}`);
			return null;
		});

		if (res) {
			await initFolders();
			showFolders = true;
		}
	};

	let chatListController: AbortController | null = null;

	const abortChatList = () => {
		chatListController?.abort();
	};

	const initChatList = async () => {
		abortChatList();
		const controller = new AbortController();
		chatListController = controller;
		scrollPaginationEnabled.set(false);

		initFolders();

		let refreshResult: boolean = false;
		await Promise.all([
			(async () => {
				pinnedChats.set(await getPinnedChatList(localStorage.token));
			})(),
			(async () => {
				refreshResult = await refreshChatList(localStorage.token, controller.signal);
			})()
		]);

		if (controller.signal.aborted) return;
		allChatsLoaded = refreshResult;
		scrollPaginationEnabled.set(true);
	};

	const loadMoreChats = async () => {
		if (chatListController?.signal.aborted) return;
		chatListLoading = true;

		const nextPage = $currentChatPage + 1;
		currentChatPage.set(nextPage);

		const newChatList = await getChatList(localStorage.token, nextPage);

		allChatsLoaded = newChatList.length < PAGE_SIZE;
		await chats.set([...$chats, ...newChatList]);

		chatListLoading = false;
	};

	const importChatHandler = async (items, pinned = false, folderId = null) => {
		console.log('importChatHandler', items, pinned, folderId);
		for (const item of items) {
			console.log(item);
			if (item.chat) {
				await importChats(localStorage.token, [
					{
						chat: item.chat,
						meta: item?.meta ?? {},
						pinned: pinned,
						folder_id: folderId,
						created_at: item?.created_at ?? null,
						updated_at: item?.updated_at ?? null
					}
				]);
			}
		}

		initChatList();
	};

	const inputFilesHandler = async (files) => {
		console.log(files);

		for (const file of files) {
			const reader = new FileReader();
			reader.onload = async (e) => {
				const content = e.target.result;

				try {
					const chatItems = JSON.parse(content);
					importChatHandler(chatItems);
				} catch {
					toast.error($i18n.t(`Invalid file format.`));
				}
			};

			reader.readAsText(file);
		}
	};

	const onDragOver = (e) => {
		e.preventDefault();
	};

	const onDragLeave = () => {};

	const onDrop = async (e) => {
		e.preventDefault();

		if (e.dataTransfer?.files) {
			const inputFiles = Array.from(e.dataTransfer?.files);

			if (inputFiles && inputFiles.length > 0) {
				inputFilesHandler(inputFiles);
			}
		}
	};

	let touchstart;
	let touchend;

	function checkDirection() {
		const screenWidth = window.innerWidth;
		const swipeDistance = Math.abs(touchend.screenX - touchstart.screenX);
		if (touchstart.clientX < 40 && swipeDistance >= screenWidth / 8) {
			if (touchend.screenX < touchstart.screenX) {
				showSidebar.set(false);
			}
			if (touchend.screenX > touchstart.screenX) {
				showSidebar.set(true);
			}
		}
	}

	const onTouchStart = (e) => {
		touchstart = e.changedTouches[0];
		console.log(touchstart.clientX);
	};

	const onTouchEnd = (e) => {
		touchend = e.changedTouches[0];
		checkDirection();
	};

	const syncShiftKey = (e) => {
		if (e.shiftKey !== shiftKey) {
			shiftKey = e.shiftKey;
		}
	};

	const onBlur = () => {
		shiftKey = false;
		selectedChatId = null;
	};

	const MIN_WIDTH = 220;
	const MAX_WIDTH = 480;

	let isResizing = $state(false);

	let startWidth = 0;
	let startClientX = 0;

	const resizeStartHandler = (e: MouseEvent) => {
		if ($mobile) return;
		isResizing = true;

		startClientX = e.clientX;
		startWidth = $sidebarWidth ?? 260;

		document.body.style.userSelect = 'none';
	};

	const resizeEndHandler = () => {
		if (!isResizing) return;
		isResizing = false;

		document.body.style.userSelect = '';
		localStorage.setItem('sidebarWidth', String($sidebarWidth));
	};

	const resizeSidebarHandler = (endClientX) => {
		const dx = endClientX - startClientX;
		const newSidebarWidth = Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, startWidth + dx));

		sidebarWidth.set(newSidebarWidth);
		document.documentElement.style.setProperty('--sidebar-width', `${newSidebarWidth}px`);
	};

	const chatActiveEventHandler = (event: {
		chat_id: string;
		message_id: string;
		data: { type: string; data: any };
	}) => {
		if (event.data?.type === 'chat:active') {
			const { active } = event.data.data;
			activeChatIds.update((ids) => {
				const newSet = new Set(ids);
				if (active) {
					newSet.add(event.chat_id);
				} else {
					newSet.delete(event.chat_id);
				}
				return newSet;
			});
		}
	};

	// Restore persisted state before effects run (script body executes before $effect)
	if (browser) {
		try {
			const width = Number(localStorage.getItem('sidebarWidth'));
			if (!Number.isNaN(width) && width >= MIN_WIDTH && width <= MAX_WIDTH) {
				sidebarWidth.set(width);
			}
		} catch {}
		showSidebar.set(!get(mobile) ? localStorage.sidebar === 'true' : false);
	}

	// ── Effects ──────────────────────────────────────────────────────────

	// Sync sidebar width to CSS custom property
	$effect(() => {
		document.documentElement.style.setProperty('--sidebar-width', `${$sidebarWidth}px`);
	});

	// Close sidebar when switching to mobile
	$effect(() => {
		const isMobile = $mobile;
		if (isMobile && untrack(() => $showSidebar)) {
			showSidebar.set(false);
		}
		if (!isMobile && untrack(() => $showSidebar)) {
			const nav = document.getElementsByTagName('nav')[0];
			if (nav) nav.style['-webkit-app-region'] = 'drag';
		}
	});

	// Sidebar open/close → localStorage, nav region, chat list init
	$effect(() => {
		const show = $showSidebar;
		localStorage.sidebar = show;

		const nav = document.getElementsByTagName('nav')[0];
		if (nav) {
			const isMobile = untrack(() => $mobile);
			if (isMobile) {
				nav.style['-webkit-app-region'] = show ? 'no-drag' : 'drag';
			} else {
				nav.style['-webkit-app-region'] = 'drag';
			}
		}

		if (!show) return;

		(async () => {
			await initChatList();
			if (chatListController?.signal.aborted) return;

			const allChatIds = [...get(chats).map((c) => c.id), ...get(pinnedChats).map((c) => c.id)];
			if (allChatIds.length > 0) {
				try {
					const res = await checkActiveChats(localStorage.token, allChatIds);
					activeChatIds.set(new Set(res.active_chat_ids || []));
				} catch (e) {
					console.debug('Failed to check active chats:', e);
				}
			}
		})();

		return () => abortChatList();
	});

	// Socket events
	$effect(() => {
		const s = $socket;
		if (!s) return;
		s.on('events', chatActiveEventHandler);
		return () => s.off('events', chatActiveEventHandler);
	});

	// ── Lifecycle ────────────────────────────────────────────────────────

	onMount(() => {
		window.addEventListener('keydown', syncShiftKey);
		window.addEventListener('keyup', syncShiftKey);
		window.addEventListener('mousemove', syncShiftKey, { passive: true });

		window.addEventListener('touchstart', onTouchStart);
		window.addEventListener('touchend', onTouchEnd);

		window.addEventListener('blur', onBlur);

		const dropZone = document.getElementById('sidebar');

		dropZone?.addEventListener('dragover', onDragOver);
		dropZone?.addEventListener('drop', onDrop);
		dropZone?.addEventListener('dragleave', onDragLeave);

		return () => {
			window.removeEventListener('keydown', syncShiftKey);
			window.removeEventListener('keyup', syncShiftKey);
			window.removeEventListener('mousemove', syncShiftKey);

			window.removeEventListener('touchstart', onTouchStart);
			window.removeEventListener('touchend', onTouchEnd);

			window.removeEventListener('blur', onBlur);

			dropZone?.removeEventListener('dragover', onDragOver);
			dropZone?.removeEventListener('drop', onDrop);
			dropZone?.removeEventListener('dragleave', onDragLeave);
		};
	});

	const newChatHandler = async () => {
		selectedChatId = null;
		selectedFolder.set(null);

		await temporaryChatEnabled.set(false);

		setTimeout(() => {
			if ($mobile) {
				showSidebar.set(false);
			}
		}, 0);
	};

	const isWindows = /Windows/i.test(navigator.userAgent);
</script>

<FolderModal
	bind:show={showCreateFolderModal}
	onSubmit={async (folder) => {
		await createFolder(folder);
		showCreateFolderModal = false;
	}}
/>

<!-- svelte-ignore a11y-no-static-element-interactions -->

{#if $showSidebar}
	<div
		class="fixed md:hidden z-40 top-0 right-0 left-0 bottom-0 bg-black/60 w-full min-h-screen h-screen flex justify-center overflow-hidden overscroll-contain"
		onmousedown={() => {
			showSidebar.set(!$showSidebar);
		}}
	/>
{/if}

<SearchModal
	bind:show={$showSearch}
	onClose={() => {
		if ($mobile) {
			showSidebar.set(false);
		}
	}}
/>

<button
	id="sidebar-new-chat-button"
	class="hidden"
	onclick={() => {
		goto('/');
		newChatHandler();
	}}
/>

<svelte:window
	onmousemove={(e) => {
		if (!isResizing) return;
		resizeSidebarHandler(e.clientX);
	}}
	onmouseup={() => {
		resizeEndHandler();
	}}
/>

{#if !$mobile && !$showSidebar}
	<div
		class=" pt-[7px] pb-2 px-2 flex flex-col justify-between text-black dark:text-white hover:bg-gray-50/30 dark:hover:bg-gray-950/30 h-full z-10 transition-all border-e-[0.5px] border-gray-50 dark:border-gray-850/30"
		id="sidebar"
	>
		<button
			class="flex flex-col flex-1 {isWindows ? 'cursor-pointer' : 'cursor-[e-resize]'}"
			onclick={async () => {
				showSidebar.set(!$showSidebar);
			}}
		>
			<div class="pb-1.5">
				<Tooltip
					content={$showSidebar ? $i18n.t('Close Sidebar') : $i18n.t('Open Sidebar')}
					placement="right"
				>
					<button
						class="flex rounded-xl hover:bg-gray-100 dark:hover:bg-gray-850 transition group {isWindows
							? 'cursor-pointer'
							: 'cursor-[e-resize]'}"
						aria-label={$showSidebar ? $i18n.t('Close Sidebar') : $i18n.t('Open Sidebar')}
					>
						<div class=" self-center flex items-center justify-center size-9">
							<img
								src="{WEBUI_BASE_URL}/static/favicon.png"
								class="sidebar-new-chat-icon size-6 rounded-full group-hover:hidden"
								alt=""
							/>

							<Sidebar className="size-5 hidden group-hover:flex" />
						</div>
					</button>
				</Tooltip>
			</div>

			<div class="-mt-[0.5px]">
				<div class="">
					<Tooltip content={$i18n.t('New Chat')} placement="right">
						<a
							class=" cursor-pointer flex rounded-xl hover:bg-gray-100 dark:hover:bg-gray-850 transition group"
							href="/"
							draggable="false"
							onclick={async (e) => {
								e.stopImmediatePropagation();
								e.preventDefault();

								goto('/');
								newChatHandler();
							}}
							aria-label={$i18n.t('New Chat')}
						>
							<div class=" self-center flex items-center justify-center size-9">
								<PencilSquare className="size-4.5" />
							</div>
						</a>
					</Tooltip>
				</div>

				<div>
					<Tooltip content={$i18n.t('Search')} placement="right">
						<button
							class=" cursor-pointer flex rounded-xl hover:bg-gray-100 dark:hover:bg-gray-850 transition group"
							onclick={(e) => {
								e.stopImmediatePropagation();
								e.preventDefault();

								showSearch.set(true);
							}}
							draggable="false"
							aria-label={$i18n.t('Search')}
						>
							<div class=" self-center flex items-center justify-center size-9">
								<Search className="size-4.5" />
							</div>
						</button>
					</Tooltip>
				</div>
			</div>
		</button>

		<div>
			<div>
				<div class=" py-2 flex justify-center items-center">
					{#if $user !== undefined && $user !== null}
						<UserMenu role={$user?.role}>
							<div
								class=" cursor-pointer flex rounded-xl hover:bg-gray-100 dark:hover:bg-gray-850 transition group"
							>
								<div class="self-center">
									<img
										src={`${WEBUI_BASE_URL}/user.png`}
										class=" size-7 object-cover rounded-full"
										alt={$i18n.t('Open User Profile Menu')}
										aria-label={$i18n.t('Open User Profile Menu')}
									/>
								</div>
							</div>
						</UserMenu>
					{/if}
				</div>
			</div>
		</div>
	</div>
{/if}

<!-- {$i18n.t('New Folder')} -->
<!-- {$i18n.t('Pinned')} -->

{#if $showSidebar}
	<div
		bind:this={navElement}
		id="sidebar"
		class="h-screen max-h-[100dvh] min-h-screen select-none {$showSidebar
			? `${$mobile ? 'bg-gray-50 dark:bg-gray-950' : 'bg-gray-50/70 dark:bg-gray-950/70'} z-50`
			: ' bg-transparent z-0 '} transition-all duration-300 shrink-0 text-gray-900 dark:text-gray-200 text-sm fixed top-0 left-0 overflow-x-hidden
        "
		transition:slide={{ duration: 250, axis: 'x' }}
		data-state={$showSidebar}
	>
		<div
			class=" my-auto flex flex-col justify-between h-screen max-h-[100dvh] w-[var(--sidebar-width)] overflow-x-hidden scrollbar-hidden z-50 {$showSidebar
				? ''
				: 'invisible'}"
		>
			<div
				class="sidebar px-[0.5625rem] pt-2 pb-1.5 flex justify-between space-x-1 text-gray-600 dark:text-gray-400 sticky top-0 z-10 -mb-3"
			>
				<a
					class="flex items-center rounded-xl size-8.5 h-full justify-center hover:bg-gray-100/50 dark:hover:bg-gray-850/50 transition no-drag-region"
					href="/"
					draggable="false"
					onclick={newChatHandler}
				>
					<img
						crossorigin="anonymous"
						src="{WEBUI_BASE_URL}/static/favicon.png"
						class="sidebar-new-chat-icon size-6 rounded-full"
						alt=""
					/>
				</a>

				<a href="/" class="flex flex-1 px-1.5" onclick={newChatHandler}>
					<div
						id="sidebar-webui-name"
						class=" self-center font-medium text-gray-850 dark:text-white font-primary"
					>
						{$WEBUI_NAME}
					</div>
				</a>
				<Tooltip
					content={$showSidebar ? $i18n.t('Close Sidebar') : $i18n.t('Open Sidebar')}
					placement="bottom"
				>
					<button
						class="flex rounded-xl size-8.5 justify-center items-center hover:bg-gray-100/50 dark:hover:bg-gray-850/50 transition {isWindows
							? 'cursor-pointer'
							: 'cursor-[w-resize]'}"
						onclick={() => {
							showSidebar.set(!$showSidebar);
						}}
						aria-label={$showSidebar ? $i18n.t('Close Sidebar') : $i18n.t('Open Sidebar')}
					>
						<div class=" self-center p-1.5">
							<Sidebar />
						</div>
					</button>
				</Tooltip>

				<div
					class="{scrollTop > 0
						? 'visible'
						: 'invisible'} sidebar-bg-gradient-to-b bg-linear-to-b from-gray-50 dark:from-gray-950 to-transparent from-50% pointer-events-none absolute inset-0 -z-10 -mb-6"
				></div>
			</div>

			<div
				class="relative flex flex-col flex-1 overflow-y-auto scrollbar-hidden pt-3 pb-3"
				onscroll={(e) => {
					if (e.target.scrollTop === 0) {
						scrollTop = 0;
					} else {
						scrollTop = e.target.scrollTop;
					}
				}}
			>
				<div class="pb-1.5">
					<div class="px-[0.4375rem] flex justify-center text-gray-800 dark:text-gray-200">
						<a
							id="sidebar-new-chat-button"
							class="group grow flex items-center space-x-3 rounded-2xl px-2.5 py-2 hover:bg-gray-100 dark:hover:bg-gray-900 transition outline-none"
							href="/"
							draggable="false"
							onclick={newChatHandler}
							aria-label={$i18n.t('New Chat')}
						>
							<div class="self-center">
								<PencilSquare className=" size-4.5" strokeWidth="2" />
							</div>

							<div class="flex flex-1 self-center translate-y-[0.5px]">
								<div class=" self-center text-sm font-primary">{$i18n.t('New Chat')}</div>
							</div>

							<HotkeyHint name="newChat" className=" group-hover:visible invisible" />
						</a>
					</div>

					<div class="px-[0.4375rem] flex justify-center text-gray-800 dark:text-gray-200">
						<button
							id="sidebar-search-button"
							class="group grow flex items-center space-x-3 rounded-2xl px-2.5 py-2 hover:bg-gray-100 dark:hover:bg-gray-900 transition outline-none"
							onclick={() => {
								showSearch.set(true);
							}}
							draggable="false"
							aria-label={$i18n.t('Search')}
						>
							<div class="self-center">
								<Search strokeWidth="2" className="size-4.5" />
							</div>

							<div class="flex flex-1 self-center translate-y-[0.5px]">
								<div class=" self-center text-sm font-primary">{$i18n.t('Search')}</div>
							</div>
							<HotkeyHint name="search" className=" group-hover:visible invisible" />
						</button>
					</div>
				</div>

				{#if ($models ?? []).length > 0 && ($settings?.pinnedModels ?? []).length > 0}
					<Folder
						id="sidebar-models"
						bind:open={showPinnedModels}
						className="px-2 mt-0.5"
						name={$i18n.t('Models')}
						chevron={false}
						dragAndDrop={false}
					>
						<PinnedModelList bind:selectedChatId {shiftKey} />
					</Folder>
				{/if}

				<Folder
					id="sidebar-folders"
					bind:open={showFolders}
					className="px-2 mt-0.5"
					name={$i18n.t('Folders')}
					chevron={false}
					onAdd={() => {
						showCreateFolderModal = true;
					}}
					onAddLabel={$i18n.t('New Folder')}
				>
					<Folders
						bind:folderRegistry
						{folders}
						{shiftKey}
						onDelete={() => {
							selectedFolder.set(null);
							initChatList();
						}}
						onchange={() => initChatList()}
					/>
				</Folder>

				<Folder
					id="sidebar-chats"
					className="px-2 mt-0.5"
					name={$i18n.t('Chats')}
					chevron={false}
					onchange={async () => {
						selectedFolder.set(null);
					}}
					ondrop={async (data) => {
						const { type, id } = data;

						if (type === 'chat') {
							const chat = await getChatById(localStorage.token, id).catch(() => null);

							if (chat) {
								console.log(chat);
								if (chat.folder_id) {
									await updateChatFolderIdById(localStorage.token, chat.id, null).catch((error) => {
										toast.error(`${error}`);
										return null;
									});

									folderRegistry[chat.folder_id]?.setFolderItems();
								}

								if (chat.pinned) {
									await toggleChatPinnedStatusById(localStorage.token, chat.id);
								}

								initChatList();
							}
						}
					}}
				>
					{#if $pinnedChats.length > 0}
						<div class="mb-1">
							<div class="flex flex-col space-y-1 rounded-xl">
								<Folder
									id="sidebar-pinned-chats"
									buttonClassName=" text-gray-500"
									ondrop={async (data) => {
										const { type, id } = data;

										if (type === 'chat') {
											const chat = await getChatById(localStorage.token, id).catch(() => null);

											if (chat) {
												console.log(chat);
												if (chat.folder_id) {
													await updateChatFolderIdById(localStorage.token, chat.id, null).catch(
														(error) => {
															toast.error(`${error}`);
															return null;
														}
													);
												}

												if (!chat.pinned) {
													await toggleChatPinnedStatusById(localStorage.token, chat.id);
												}

												initChatList();
											}
										}
									}}
									name={$i18n.t('Pinned')}
								>
									<div
										class="ml-3 pl-1 mt-[1px] flex flex-col overflow-y-auto scrollbar-hidden border-s border-gray-100 dark:border-gray-900 text-gray-900 dark:text-gray-200"
									>
										{#each $pinnedChats as chat, idx (`pinned-chat-${chat?.id ?? idx}`)}
											<ChatItem
												className=""
												id={chat.id}
												title={chat.title}
												createdAt={chat.created_at}
												{shiftKey}
												selected={selectedChatId === chat.id}
												onselect={() => {
													selectedChatId = chat.id;
												}}
												onunselect={() => {
													selectedChatId = null;
												}}
												onchange={() => {
													initChatList();
												}}
											/>
										{/each}
									</div>
								</Folder>
							</div>
						</div>
					{/if}

					<div class=" flex-1 flex flex-col overflow-y-auto scrollbar-hidden">
						<div class="pt-1.5">
							{#if !chatListLoading || $chats.length > 0}
								{#each $chats as chat, idx (`chat-${chat?.id ?? idx}`)}
									{#if idx === 0 || (idx > 0 && chat.time_range !== $chats[idx - 1].time_range)}
										<div
											class="w-full pl-2.5 text-xs text-gray-500 dark:text-gray-500 font-medium {idx ===
											0
												? ''
												: 'pt-5'} pb-1.5"
										>
											{$i18n.t(chat.time_range)}
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

									<ChatItem
										className=""
										id={chat.id}
										title={chat.title}
										createdAt={chat.created_at}
										{shiftKey}
										selected={selectedChatId === chat.id}
										onselect={() => {
											selectedChatId = chat.id;
										}}
										onunselect={() => {
											selectedChatId = null;
										}}
										onchange={() => {
											initChatList();
										}}
									/>
								{/each}

								{#if $scrollPaginationEnabled && !allChatsLoaded}
									<Loader
										onvisible={() => {
											if (!chatListLoading) {
												loadMoreChats();
											}
										}}
									>
										<div
											class="w-full flex justify-center py-1 text-xs animate-pulse items-center gap-2"
										>
											<Spinner className=" size-4" />
											<div class=" ">{$i18n.t('Loading...')}</div>
										</div>
									</Loader>
								{/if}
							{:else}
								<div
									class="w-full flex justify-center py-1 text-xs animate-pulse items-center gap-2"
								>
									<Spinner className=" size-4" />
									<div class=" ">{$i18n.t('Loading...')}</div>
								</div>
							{/if}
						</div>
					</div>
				</Folder>
			</div>

			<div class="px-1.5 pt-1.5 pb-2 sticky bottom-0 z-10 -mt-3 sidebar">
				<div
					class=" sidebar-bg-gradient-to-t bg-linear-to-t from-gray-50 dark:from-gray-950 to-transparent from-50% pointer-events-none absolute inset-0 -z-10 -mt-6"
				></div>
				<div class="flex flex-col font-primary">
					{#if $user !== undefined && $user !== null}
						<UserMenu role={$user?.role}>
							<div
								class=" flex items-center rounded-2xl py-2 px-1.5 w-full hover:bg-gray-100/50 dark:hover:bg-gray-900/50 transition"
							>
								<div class=" self-center mr-3">
									<img
										src={`${WEBUI_BASE_URL}/user.png`}
										class=" size-7 object-cover rounded-full"
										alt={$i18n.t('Open User Profile Menu')}
										aria-label={$i18n.t('Open User Profile Menu')}
									/>
								</div>
								<div class=" self-center font-medium">{$user?.name}</div>
							</div>
						</UserMenu>
					{/if}
				</div>
			</div>
		</div>
	</div>

	{#if !$mobile}
		<div
			class="relative flex items-center justify-center group border-l border-gray-50 dark:border-gray-850/30 hover:border-gray-200 dark:hover:border-gray-800 transition z-20"
			id="sidebar-resizer"
			onmousedown={resizeStartHandler}
			role="separator"
		>
			<div
				class=" absolute -left-1.5 -right-1.5 -top-0 -bottom-0 z-20 cursor-col-resize bg-transparent"
			/>
		</div>
	{/if}
{/if}
