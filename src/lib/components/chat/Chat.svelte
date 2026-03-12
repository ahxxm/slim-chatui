<script lang="ts">
	import { v4 as uuidv4 } from 'uuid';
	import { toast } from 'svelte-sonner';

	import { getContext, onMount, tick, untrack } from 'svelte';
	import { fade } from 'svelte/transition';
	const i18n: Writable<i18nType> = getContext('i18n');

	import { goto, replaceState } from '$app/navigation';
	import { page } from '$app/stores';

	import { type Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';
	import { WEBUI_BASE_URL } from '$lib/constants';
	import type { ChatHistory } from '$lib/types';

	import {
		activeChatIds,
		chatId,
		config,
		type Model,
		models,
		settings,
		showSidebar,
		WEBUI_NAME,
		socket,
		temporaryChatEnabled,
		chatTitle,
		selectedFolder,
		pinnedChats,
		refreshChatList
	} from '$lib/stores';

	import {
		convertMessagesToHistory,
		copyToClipboard,
		createMessagesList,
		processDetails
	} from '$lib/utils';

	import {
		createNewChat,
		getChatById,
		getPinnedChatList,
		updateChatById,
		updateChatFolderIdById
	} from '$lib/apis/chats';
	import { generateOpenAIChatCompletion } from '$lib/apis/openai';
	import { stopTask, getTaskIdsByChatId } from '$lib/apis';
	import { updateFolderById } from '$lib/apis/folders';

	import MessageInput from '$lib/components/chat/MessageInput.svelte';
	import Messages from '$lib/components/chat/Messages.svelte';
	import Navbar from '$lib/components/chat/Navbar.svelte';
	import EventConfirmDialog from '../common/ConfirmDialog.svelte';
	import Placeholder from './Placeholder.svelte';
	import Spinner from '../common/Spinner.svelte';

	let { chatIdProp = '' } = $props();

	let loading = $state(true);

	const eventTarget = new EventTarget();

	let messageInput = $state<any>(null);

	let autoScroll = $state(true);
	let messagesContainerElement = $state<HTMLDivElement | undefined>();

	let navbarElement = $state<any>(null);

	let showEventConfirmation = $state(false);
	let eventConfirmationTitle = $state('');
	let eventConfirmationMessage = $state('');
	let eventConfirmationInput = $state(false);
	let eventConfirmationInputPlaceholder = $state('');
	let eventConfirmationInputValue = $state('');
	let eventConfirmationInputType = $state('');
	let eventCallback = $state<((value?: any) => void) | null>(null);

	let selectedModels = $state(['']);

	let generating = $state(false);
	let generationController: AbortController | null = null;

	let chat: Record<string, any> | null = null;

	let history = $state<ChatHistory>({
		messages: {},
		currentId: null
	});

	let taskIds = $state<string[] | null>(null);

	// Typewriter throttle: batch streaming tokens, emit to DOM N times per second.
	// At 10 emits/sec (100ms): DeepSeek R1 (~24 t/s) batches ~2 tokens/emit,
	// Opus 4.6 (~43 t/s) ~4, GPT-5.4 (~78 t/s) ~8, Gemini 3.1 Pro (~100 t/s) ~10.
	// All land as unified/natural word-chunks like typewriter output.
	// Technically, streamingBuffers holds plain (non-proxy) message objects
	// so mutations don't trigger Svelte reactivity until we explicitly flush.
	const TYPEWRITER_EMITS_PER_SEC = 23;
	const EMIT_INTERVAL_MS = Math.round(1000 / TYPEWRITER_EMITS_PER_SEC);
	const streamingBuffers: Map<string, any> = new Map();
	let renderTimer: ReturnType<typeof setTimeout> | null = null;

	const getStreamingMessage = (messageId: string): any => {
		let buf = streamingBuffers.get(messageId);
		if (!buf) {
			buf = $state.snapshot(history.messages[messageId]);
			streamingBuffers.set(messageId, buf);
		}
		return buf;
	};

	const flushPendingRender = () => {
		renderTimer = null;
		for (const [id, message] of streamingBuffers) {
			history.messages[id] = message;
		}
		if (autoScroll) scrollToBottom();
	};

	const scheduleRender = () => {
		if (!renderTimer) {
			renderTimer = setTimeout(flushPendingRender, EMIT_INTERVAL_MS);
		}
	};

	const flushRenderNow = (id: string) => {
		if (renderTimer) {
			clearTimeout(renderTimer);
			renderTimer = null;
		}
		const buf = streamingBuffers.get(id);
		if (buf) history.messages[id] = buf;
		streamingBuffers.delete(id);
	};

	// Chat Input
	let prompt = $state('');
	let chatFiles: any[] = [];
	let files = $state<any[]>([]);

	// Message queue for storing messages while generating
	let messageQueue = $state<{ id: string; prompt: string; files: any[] }[]>([]);

	$effect(() => {
		if (!chatIdProp) return;
		const controller = new AbortController();
		untrack(() => navigateHandler(controller.signal));
		return () => controller.abort();
	});

	const navigateHandler = async (signal?: AbortSignal) => {
		console.log('[navigateHandler] chatIdProp:', chatIdProp);
		loading = true;

		// Save current queue to sessionStorage before navigating away
		if (messageQueue.length > 0 && $chatId) {
			sessionStorage.setItem(`chat-queue-${$chatId}`, JSON.stringify(messageQueue));
		}

		prompt = '';
		messageInput?.setText('');

		files = [];
		messageQueue = [];

		const storageChatInput = sessionStorage.getItem(
			`chat-input${chatIdProp ? `-${chatIdProp}` : ''}`
		);

		if (chatIdProp && (await loadChat())) {
			if (signal?.aborted) return;
			await tick();
			if (signal?.aborted) return;
			loading = false;
			window.setTimeout(() => scrollToBottom(), 0);

			await tick();
			if (signal?.aborted) return;

			// Restore queue from sessionStorage
			const storedQueueData = sessionStorage.getItem(`chat-queue-${chatIdProp}`);
			if (storedQueueData) {
				try {
					const restoredQueue = JSON.parse(storedQueueData);

					if (restoredQueue.length > 0) {
						sessionStorage.removeItem(`chat-queue-${chatIdProp}`);
						// Check if there are pending tasks (still generating)
						const hasPendingTask = taskIds !== null && taskIds.length > 0;
						if (!hasPendingTask) {
							// No pending tasks - process the queue
							files = restoredQueue.flatMap((m) => m.files);
							await tick();
							const combinedPrompt = restoredQueue.map((m) => m.prompt).join('\n\n');
							await submitPrompt(combinedPrompt);
						} else {
							messageQueue = restoredQueue;
						}
					}
				} catch {}
			}

			if (storageChatInput) {
				try {
					const input = JSON.parse(storageChatInput);

					if (!$temporaryChatEnabled) {
						messageInput?.setText(input.prompt);
						files = input.files;
					}
				} catch {}
			}

			const chatInput = document.getElementById('chat-input');
			chatInput?.focus();
		} else {
			await goto('/');
		}
	};

	const onSelect = async (e: any) => {
		const { type, data } = e;

		if (type === 'prompt') {
			// Handle prompt selection
			messageInput?.setText(data, async () => {
				if (!($settings?.insertSuggestionPrompt ?? false)) {
					await tick();
					submitPrompt(prompt);
				}
			});
		}
	};

	$effect(() => {
		if (selectedModels && chatIdProp !== '') {
			untrack(() => saveSessionSelectedModels());
		}
	});

	const saveSessionSelectedModels = () => {
		if (!selectedModels[0] || sessionStorage.selectedModels === JSON.stringify(selectedModels)) {
			return;
		}
		sessionStorage.selectedModels = JSON.stringify(selectedModels);
		console.log('saveSessionSelectedModels', selectedModels);
	};

	const showMessage = async (message: any) => {
		const _chatId = $chatId;
		let _messageId = message.id;

		let messageChildrenIds = [];
		if (_messageId === null) {
			messageChildrenIds = Object.keys(history.messages).filter(
				(id) => history.messages[id].parentId === null
			);
		} else {
			messageChildrenIds = history.messages[_messageId].childrenIds;
		}

		while (messageChildrenIds.length !== 0) {
			_messageId = messageChildrenIds.at(-1);
			messageChildrenIds = history.messages[_messageId].childrenIds;
		}

		history.currentId = _messageId;

		await tick();
		saveChatHandler(_chatId, history);
	};

	const chatEventHandler = async (event: any, cb: any) => {
		console.log(event);

		if (event.chat_id === $chatId) {
			await tick();
			const messageExists = !!history.messages[event.message_id];

			if (messageExists) {
				const type = event?.data?.type ?? null;
				const data = event?.data?.data ?? null;

				if (type === 'status') {
					let message = history.messages[event.message_id];
					if (message?.statusHistory) {
						message.statusHistory.push(data);
					} else {
						message.statusHistory = [data];
					}
				} else if (type === 'chat:completion') {
					chatCompletionEventHandler(data, getStreamingMessage(event.message_id), event.chat_id);
					return;
				} else if (type === 'chat:tasks:cancel') {
					taskIds = null;
					const responseMessage = history.messages[history.currentId];
					// Set all response messages to done
					for (const messageId of history.messages[responseMessage.parentId].childrenIds) {
						history.messages[messageId].done = true;
					}
				} else if (type === 'chat:message:delta' || type === 'message') {
					const msg = getStreamingMessage(event.message_id);
					msg.content += data.content;
					scheduleRender();
					return;
				} else if (type === 'chat:message' || type === 'replace') {
					let message = history.messages[event.message_id];
					message.content = data.content;
				} else if (type === 'chat:message:files' || type === 'files') {
					history.messages[event.message_id].files = data.files;
				} else if (type === 'chat:message:error') {
					history.messages[event.message_id].error = data.error;
				} else if (type === 'chat:message:follow_ups') {
					history.messages[event.message_id].followUps = data.follow_ups;

					if (autoScroll) {
						scrollToBottom('smooth');
					}
				} else if (type === 'chat:message:favorite') {
					history.messages[event.message_id].favorite = data.favorite;
				} else if (type === 'chat:title') {
					chatTitle.set(data);
					await refreshChatList(localStorage.token);
				} else if (type === 'source' || type === 'citation') {
					const msg = history.messages[event.message_id];
					if (msg?.sources) {
						msg.sources.push(data);
					} else {
						msg.sources = [data];
					}
				} else if (type === 'notification') {
					if ($settings?.notificationEnabled ?? false) {
						const toastType = data?.type ?? 'info';
						const toastContent = data?.content ?? '';
						const toastOpts = { id: `stream-${event.message_id}-${toastType}` };

						if (toastType === 'success') {
							toast.success(toastContent, toastOpts);
						} else if (toastType === 'error') {
							toast.error(toastContent, toastOpts);
						} else if (toastType === 'warning') {
							toast.warning(toastContent, toastOpts);
						} else {
							toast.info(toastContent, toastOpts);
						}
					}
				} else if (type === 'confirmation') {
					eventCallback = cb;

					eventConfirmationInput = false;
					showEventConfirmation = true;

					eventConfirmationTitle = data.title;
					eventConfirmationMessage = data.message;
				} else if (type === 'execute') {
					eventCallback = cb;

					try {
						// Use Function constructor to evaluate code in a safer way
						const asyncFunction = new Function(`return (async () => { ${data.code} })()`);
						const result = await asyncFunction(); // Await the result of the async function

						if (cb) {
							cb(result);
						}
					} catch (error) {
						console.error('Error executing code:', error);
					}
				} else if (type === 'input') {
					eventCallback = cb;

					eventConfirmationInput = true;
					showEventConfirmation = true;

					eventConfirmationTitle = data.title;
					eventConfirmationMessage = data.message;
					eventConfirmationInputPlaceholder = data.placeholder;
					eventConfirmationInputValue = data?.value ?? '';
					eventConfirmationInputType = data?.type ?? '';
				} else if (type === 'chat:active') {
					// status indicator — ignored
				} else {
					console.log('Unknown message type', data);
				}
			}
		}
	};

	const onMessageHandler = async (event: {
		origin: string;
		data: { type: string; text: string };
	}) => {
		if (event.origin !== window.origin) {
			return;
		}

		if (event.data.type === 'action:submit') {
			console.debug(event.data.text);

			if (prompt !== '') {
				await tick();
				submitPrompt(prompt);
			}
		}

		// Replace with your iframe's origin
		if (event.data.type === 'input:prompt') {
			console.debug(event.data.text);

			const inputElement = document.getElementById('chat-input');

			if (inputElement) {
				messageInput?.setText(event.data.text);
				inputElement.focus();
			}
		}

		if (event.data.type === 'input:prompt:submit') {
			console.debug(event.data.text);

			if (event.data.text !== '') {
				await tick();
				submitPrompt(event.data.text);
			}
		}
	};

	const savedModelIds = async () => {
		if (
			$selectedFolder &&
			selectedModels[0] &&
			JSON.stringify($selectedFolder?.data?.model_ids) !== JSON.stringify(selectedModels)
		) {
			await updateFolderById(localStorage.token, $selectedFolder.id, {
				data: {
					model_ids: selectedModels
				}
			});
		}
	};

	$effect(() => {
		if (selectedModels !== null) {
			untrack(() => savedModelIds());
		}
	});

	$effect(() => {
		const folder = $selectedFolder;
		if (
			folder?.data?.model_ids &&
			JSON.stringify(untrack(() => selectedModels)) !== JSON.stringify(folder.data.model_ids)
		) {
			selectedModels = folder.data.model_ids;
		}
	});

	$effect(() => {
		if (
			$models.length > 0 &&
			selectedModels[0] &&
			!$models.find((m) => m.id === selectedModels[0])
		) {
			selectedModels = [''];
		}
	});

	let activeChatEmitter: ReturnType<typeof setInterval> | null = null;

	const instanceId = Math.random().toString(36).slice(2, 6);
	onMount(() => {
		console.log('[Chat mount]', instanceId, 'chatIdProp:', chatIdProp);
		loading = true;
		window.addEventListener('message', onMessageHandler);
		$socket?.on('events', chatEventHandler);

		if (!chatIdProp) {
			initNewChat();
		}

		let pageSubscribeFirst = true;
		const pageUnsubscribe = page.subscribe(() => {
			if (pageSubscribeFirst) {
				pageSubscribeFirst = false;
				return;
			}
			if (window.location.pathname === '/') {
				initNewChat();
			}
		});

		const storageChatInput = sessionStorage.getItem(
			`chat-input${chatIdProp ? `-${chatIdProp}` : ''}`
		);

		if (!chatIdProp) {
			loading = false;
		}

		if (storageChatInput) {
			prompt = '';
			messageInput?.setText('');

			files = [];

			try {
				const input = JSON.parse(storageChatInput);

				if (!$temporaryChatEnabled) {
					messageInput?.setText(input.prompt);
					files = input.files;
				}
			} catch {}
		}

		const chatInput = document.getElementById('chat-input');
		chatInput?.focus();

		return () => {
			if (renderTimer) {
				clearTimeout(renderTimer);
				renderTimer = null;
			}
			if (activeChatEmitter) {
				clearInterval(activeChatEmitter);
				activeChatEmitter = null;
			}
			if (saveDraftTimeout) {
				clearTimeout(saveDraftTimeout);
				saveDraftTimeout = null;
			}
			pageUnsubscribe();
			window.removeEventListener('message', onMessageHandler);
			$socket?.off('events', chatEventHandler);
		};
	});

	// File upload functions

	//////////////////////////
	// Web functions
	//////////////////////////

	const initNewChat = async () => {
		console.log('initNewChat');

		if ($settings?.temporaryChatByDefault ?? false) {
			if ($temporaryChatEnabled === false) {
				await temporaryChatEnabled.set(true);
			} else if ($temporaryChatEnabled === null) {
				// if set to null set to false; refer to temp chat toggle click handler
				await temporaryChatEnabled.set(false);
			}
		}

		const availableModels = $models
			.filter((m) => !(m?.info?.meta?.hidden ?? false))
			.map((m) => m.id);

		const defaultModels = $config?.default_models ? $config?.default_models.split(',') : [];

		if ($page.url.searchParams.get('models') || $page.url.searchParams.get('model')) {
			const urlModels = (
				$page.url.searchParams.get('models') ||
				$page.url.searchParams.get('model') ||
				''
			)?.split(',');

			if ($models.find((m) => m.id === urlModels[0])) {
				selectedModels = [urlModels[0]];
			} else {
				// Model not found; open model selector and prefill with search
				selectedModels = [''];
				const modelSelectorButton = document.getElementById('model-selector-0-button');
				if (modelSelectorButton) {
					modelSelectorButton.click();
					await tick();

					const modelSelectorInput = document.getElementById('model-search-input');
					if (modelSelectorInput) {
						modelSelectorInput.focus();
						modelSelectorInput.value = urlModels[0];
						modelSelectorInput.dispatchEvent(new Event('input'));
					}
				}
			}
		} else {
			if ($selectedFolder?.data?.model_ids) {
				// Set from folder model IDs
				selectedModels = $selectedFolder?.data?.model_ids;
			} else {
				if (sessionStorage.selectedModels) {
					// Set from session storage (temporary selection)
					selectedModels = JSON.parse(sessionStorage.selectedModels);
					sessionStorage.removeItem('selectedModels');
				} else {
					if ($settings?.models) {
						// Set from user settings
						selectedModels = $settings?.models;
					} else if (defaultModels && defaultModels.length > 0) {
						// Set from default models
						selectedModels = defaultModels;
					}
				}
			}

			// Clear if selected model is unavailable or hidden
			if (selectedModels[0] && !availableModels.includes(selectedModels[0])) {
				selectedModels = [''];
			}
		}

		// Ensure a model is selected
		if (!selectedModels[0]) {
			if (availableModels.length > 0) {
				const defaultMatch = defaultModels.filter((id) => availableModels.includes(id));
				selectedModels = defaultMatch[0] ? [defaultMatch[0]] : [availableModels[0]];
			} else {
				selectedModels = [''];
			}
		}

		if ($page.url.pathname.includes('/c/')) {
			replaceState('/', history.state);
		}

		autoScroll = true;

		await chatId.set('');
		await chatTitle.set('');

		console.log(
			'[initNewChat] resetting history',
			new Error().stack.split('\n').slice(1, 4).join(' <- ')
		);
		history = {
			messages: {},
			currentId: null
		};

		chatFiles = [];
		taskIds = null;
		messageQueue = [];

		if ($page.url.searchParams.get('q')) {
			const q = $page.url.searchParams.get('q') ?? '';
			messageInput?.setText(q);

			if (q) {
				if (($page.url.searchParams.get('submit') ?? 'true') === 'true') {
					await tick();
					submitPrompt(q);
				}
			}
		}

		const chatInput = document.getElementById('chat-input');
		setTimeout(() => chatInput?.focus(), 0);
	};

	const loadChat = async () => {
		console.log('[loadChat] chatIdProp:', chatIdProp);
		chatId.set(chatIdProp);

		if ($temporaryChatEnabled) {
			temporaryChatEnabled.set(false);
		}

		chat = await getChatById(localStorage.token, $chatId).catch(async () => {
			await goto('/');
			return null;
		});

		if (chat) {
			const chatContent = chat.chat;

			if (chatContent) {
				console.log(chatContent);

				const savedModels = chatContent?.models ?? [];
				selectedModels = [savedModels[0] ?? ''];

				history =
					(chatContent?.history ?? undefined) !== undefined
						? chatContent.history
						: convertMessagesToHistory(chatContent.messages);

				chatTitle.set(chatContent.title);

				chatFiles = chatContent?.files ?? [];

				autoScroll = true;
				await tick();

				if (history.currentId) {
					for (const message of Object.values(history.messages)) {
						if (message && message.role === 'assistant') {
							message.done = true;
						}
					}
				}

				const taskRes = await getTaskIdsByChatId(localStorage.token, $chatId).catch(() => {
					return null;
				});

				if (taskRes) {
					taskIds = taskRes.task_ids;
				}

				await tick();

				return true;
			} else {
				return null;
			}
		}
	};

	const scrollToBottom = async (behavior: ScrollBehavior = 'auto') => {
		if (messagesContainerElement) {
			await tick();
			messagesContainerElement.scrollTo({
				top: messagesContainerElement.scrollHeight,
				behavior
			});
		}
	};

	const saveAndProcessQueue = async (_chatId: string, messages: any[]) => {
		await tick();

		if ($chatId == _chatId && !$temporaryChatEnabled) {
			chat = await updateChatById(localStorage.token, _chatId, {
				models: selectedModels,
				messages: messages,
				history: history,
				files: chatFiles
			});
		}

		taskIds = null;

		if (messageQueue.length > 0) {
			const combinedPrompt = messageQueue.map((m) => m.prompt).join('\n\n');
			const combinedFiles = messageQueue.flatMap((m) => m.files);
			messageQueue = [];

			files = combinedFiles;
			await tick();
			await submitPrompt(combinedPrompt);
		}
	};

	const getChatEventEmitter = async (modelId: string, chatId: string = '') => {
		return setInterval(() => {
			$socket?.emit('usage', {
				action: 'chat',
				model: modelId,
				chat_id: chatId
			});
		}, 1000);
	};

	const createMessagePair = async (userPrompt) => {
		messageInput?.setText('');

		const modelId = selectedModels[0];
		const model = $models.find((m) => m.id === modelId);

		if (!model) {
			toast.error($i18n.t('Model not selected'));
			return;
		}

		const messages = createMessagesList(history, history.currentId);
		const parentMessage = messages.length !== 0 ? messages.at(-1) : null;

		const userMessageId = uuidv4();
		const responseMessageId = uuidv4();

		const userMessage = {
			id: userMessageId,
			parentId: parentMessage ? parentMessage.id : null,
			childrenIds: [responseMessageId],
			role: 'user',
			content: userPrompt ? userPrompt : `[PROMPT] ${userMessageId}`,
			timestamp: Math.floor(Date.now() / 1000)
		};

		const responseMessage = {
			id: responseMessageId,
			parentId: userMessageId,
			childrenIds: [],
			role: 'assistant',
			content: `[RESPONSE] ${responseMessageId}`,
			done: true,

			model: modelId,
			modelName: model.name ?? model.id,
			timestamp: Math.floor(Date.now() / 1000)
		};

		if (parentMessage) {
			parentMessage.childrenIds.push(userMessageId);
			history.messages[parentMessage.id] = parentMessage;
		}
		history.messages[userMessageId] = userMessage;
		history.messages[responseMessageId] = responseMessage;

		history.currentId = responseMessageId;

		await tick();

		if (autoScroll) {
			scrollToBottom();
		}

		if (messages.length === 0) {
			await initChatHandler(history);
		} else {
			await saveChatHandler($chatId, history);
		}
	};

	const addMessages = async ({ modelId, parentId, messages }) => {
		const model = $models.find((m) => m.id === modelId);

		let parentMessage = history.messages[parentId];
		let currentParentId = parentMessage ? parentMessage.id : null;
		for (const message of messages) {
			let messageId = uuidv4();

			if (message.role === 'user') {
				const userMessage = {
					id: messageId,
					parentId: currentParentId,
					childrenIds: [],
					timestamp: Math.floor(Date.now() / 1000),
					...message
				};

				if (parentMessage) {
					parentMessage.childrenIds.push(messageId);
					history.messages[parentMessage.id] = parentMessage;
				}

				history.messages[messageId] = userMessage;
				parentMessage = userMessage;
				currentParentId = messageId;
			} else {
				const responseMessage = {
					id: messageId,
					parentId: currentParentId,
					childrenIds: [],
					done: true,
					model: model.id,
					modelName: model.name ?? model.id,
					timestamp: Math.floor(Date.now() / 1000),
					...message
				};

				if (parentMessage) {
					parentMessage.childrenIds.push(messageId);
					history.messages[parentMessage.id] = parentMessage;
				}

				history.messages[messageId] = responseMessage;
				parentMessage = responseMessage;
				currentParentId = messageId;
			}
		}

		history.currentId = currentParentId;
		await tick();

		if (autoScroll) {
			scrollToBottom();
		}

		if (messages.length === 0) {
			await initChatHandler(history);
		} else {
			await saveChatHandler($chatId, history);
		}
	};

	const chatCompletionEventHandler = async (data, message, chatId) => {
		const { done, choices, content, output, sources, selected_model_id, error, usage } = data;

		// Store raw OR-aligned output items from backend
		if (output) {
			message.output = output;
		}

		if (error) {
			await handleOpenAIError(error, message);
		}

		if (sources && !message?.sources) {
			message.sources = sources;
		}

		if (choices) {
			if (choices[0]?.message?.content) {
				// Non-stream response
				message.content += choices[0]?.message?.content;
			} else {
				// Stream response
				let value = choices[0]?.delta?.content ?? '';
				if (message.content == '' && value == '\n') {
					console.log('Empty response');
				} else {
					message.content += value;

					if (navigator.vibrate && ($settings?.hapticFeedback ?? false)) {
						navigator.vibrate(5);
					}
				}
			}
		}

		if (content) {
			// REALTIME_CHAT_SAVE is disabled
			message.content = content;

			if (navigator.vibrate && ($settings?.hapticFeedback ?? false)) {
				navigator.vibrate(5);
			}
		}

		if (selected_model_id) {
			message.selectedModelId = selected_model_id;
		}

		if (usage) {
			message.usage = usage;
		}

		if (done) {
			message.done = true;

			if ($settings.responseAutoCopy) {
				copyToClipboard(message.content);
			}

			eventTarget.dispatchEvent(
				new CustomEvent('chat:finish', {
					detail: {
						id: message.id,
						content: message.content
					}
				})
			);

			flushRenderNow(message.id);

			await tick();
			if (autoScroll) {
				scrollToBottom();
			}

			await saveAndProcessQueue(chatId, createMessagesList(history, message.id));
		} else {
			scheduleRender();
		}

		console.log(data);
	};

	//////////////////////////
	// Chat functions
	//////////////////////////

	const submitPrompt = async (userPrompt) => {
		console.log('submitPrompt', userPrompt, $chatId);

		if (userPrompt === '' && files.length === 0) {
			toast.error($i18n.t('Please enter a prompt'));
			return;
		}
		if (!selectedModels[0] || !$models.find((m) => m.id === selectedModels[0])) {
			toast.error($i18n.t('Model not selected'));
			return;
		}

		if (
			files.length > 0 &&
			files.filter((file) => file.type !== 'image' && file.status === 'uploading').length > 0
		) {
			toast.error(
				$i18n.t(`Oops! There are files still uploading. Please wait for the upload to complete.`)
			);
			return;
		}

		// Check if there are pending tasks (more reliable than lastMessage.done)
		if (taskIds !== null && taskIds.length > 0) {
			if ($settings?.enableMessageQueue ?? true) {
				// Queue the message
				const _files = $state.snapshot(files);
				messageQueue = [
					...messageQueue,
					{
						id: uuidv4(),
						prompt: userPrompt,
						files: _files
					}
				];
				// Clear input
				messageInput?.setText('');
				prompt = '';
				files = [];
				return;
			} else {
				// Interrupt: stop current generation and proceed
				await stopResponse();
				await tick();
			}
		}

		if (history?.currentId) {
			const lastMessage = history.messages[history.currentId];

			if (lastMessage.error && !lastMessage.content) {
				// Error in response
				toast.error($i18n.t(`Oops! There was an error in the previous response.`));
				return;
			}
		}

		messageInput?.setText('');
		prompt = '';

		const messages = createMessagesList(history, history.currentId);
		const _files = $state.snapshot(files);

		chatFiles.push(
			..._files.filter(
				(item) =>
					['text', 'chat', 'folder'].includes(item.type) ||
					(item.type === 'file' && !(item?.content_type ?? '').startsWith('image/'))
			)
		);
		chatFiles = chatFiles.filter(
			// Remove duplicates
			(item, index, array) =>
				array.findIndex((i) => JSON.stringify(i) === JSON.stringify(item)) === index
		);

		files = [];
		messageInput?.setText('');

		// Create user message
		let userMessageId = uuidv4();
		let userMessage = {
			id: userMessageId,
			parentId: messages.length !== 0 ? messages.at(-1).id : null,
			childrenIds: [],
			role: 'user',
			content: userPrompt,
			files: _files.length > 0 ? _files : undefined,
			timestamp: Math.floor(Date.now() / 1000), // Unix epoch
			models: selectedModels
		};

		// Add message to history and Set currentId to messageId
		history.messages[userMessageId] = userMessage;
		history.currentId = userMessageId;

		// Append messageId to childrenIds of parent message
		if (messages.length !== 0) {
			history.messages[messages.at(-1).id].childrenIds.push(userMessageId);
		}

		// focus on chat input
		const chatInput = document.getElementById('chat-input');
		chatInput?.focus();

		saveSessionSelectedModels();

		// newChat triggers initChatHandler + replaceState; skip for existing chats
		await sendMessage(history, userMessageId, { newChat: $chatId === '' });
	};

	const sendMessage = async (
		_history,
		parentId: string,
		{
			messages = null,
			modelId = null,
			newChat = false
		}: {
			messages?: any[] | null;
			modelId?: string | null;
			newChat?: boolean;
		} = {}
	) => {
		if (autoScroll) {
			scrollToBottom();
		}

		let _chatId = $chatId;
		_history = $state.snapshot(_history);

		const resolvedModelId = modelId ?? selectedModels[0];

		const model = $models.find((m) => m.id === resolvedModelId);

		if (!model) {
			toast.error($i18n.t(`Model {{modelId}} not found`, { modelId: resolvedModelId }));
			return;
		}

		let responseMessageId = uuidv4();
		let responseMessage = {
			parentId: parentId,
			id: responseMessageId,
			childrenIds: [],
			role: 'assistant',
			content: '',
			model: model.id,
			modelName: model.name ?? model.id,
			timestamp: Math.floor(Date.now() / 1000)
		};

		history = {
			...history,
			currentId: responseMessageId,
			messages: {
				...history.messages,
				[responseMessageId]: responseMessage,
				...(parentId !== null && history.messages[parentId]
					? {
							[parentId]: {
								...history.messages[parentId],
								childrenIds: [...history.messages[parentId].childrenIds, responseMessageId]
							}
						}
					: {})
			}
		};

		if (newChat && _history.messages[_history.currentId].parentId === null) {
			console.log(
				'[sendMessage] before initChatHandler, history keys:',
				Object.keys(history.messages)
			);
			_chatId = await initChatHandler(_history);
			console.log(
				'[sendMessage]',
				instanceId,
				'after initChatHandler, history keys:',
				Object.keys(history.messages)
			);
		}

		await tick();

		_history = $state.snapshot(history);
		console.log(
			'[sendMessage] after tick+copy, _history has responseMessageId:',
			!!_history.messages[responseMessageId]
		);
		await saveChatHandler(_chatId, _history);

		const hasImages = createMessagesList(_history, parentId).some((message) =>
			message.files?.some(
				(file) => file.type === 'image' || (file?.content_type ?? '').startsWith('image/')
			)
		);

		if (hasImages && !(model.info?.meta?.capabilities?.vision ?? true)) {
			toast.error(
				$i18n.t('Model {{modelName}} is not vision capable', {
					modelName: model.name ?? model.id
				})
			);
		}

		if (activeChatEmitter) clearInterval(activeChatEmitter);
		activeChatEmitter = await getChatEventEmitter(model.id, _chatId);

		scrollToBottom();
		await sendMessageSocket(
			model,
			messages && messages.length > 0 ? messages : createMessagesList(_history, responseMessageId),
			_history,
			responseMessageId
		);

		if (activeChatEmitter) {
			clearInterval(activeChatEmitter);
			activeChatEmitter = null;
		}

		if (newChat && _chatId) {
			replaceState(`/c/${_chatId}`, {});
		}
	};

	const sendMessageSocket = async (model, _messages, _history, responseMessageId) => {
		const responseMessage = _history.messages[responseMessageId];
		const userMessage = _history.messages[responseMessage.parentId];

		const chatMessageFiles = _messages
			.filter((message) => message.files)
			.flatMap((message) => message.files);

		// Filter chatFiles to only include files that are in the chatMessageFiles
		chatFiles = chatFiles.filter((item) => {
			const fileExists = chatMessageFiles.some((messageFile) => messageFile.id === item.id);
			return fileExists;
		});

		let files = structuredClone(chatFiles);
		files.push(
			...(userMessage?.files ?? []).filter(
				(item) =>
					['text', 'chat'].includes(item.type) ||
					(item.type === 'file' && !(item?.content_type ?? '').startsWith('image/'))
			)
		);
		// Remove duplicates
		files = files.filter(
			(item, index, array) =>
				array.findIndex((i) => JSON.stringify(i) === JSON.stringify(item)) === index
		);

		scrollToBottom();
		eventTarget.dispatchEvent(
			new CustomEvent('chat:start', {
				detail: {
					id: responseMessageId
				}
			})
		);
		await tick();

		let messages = [
			$settings?.system
				? {
						role: 'system',
						content: $settings.system
					}
				: undefined,
			..._messages.map((message) => ({
				...message,
				content: processDetails(message.content),
				// Include output for temp chats (backend will use it and strip before LLM)
				...(message.output ? { output: message.output } : {})
			}))
		].filter((message) => message);

		messages = messages
			.map((message) => {
				const imageFiles = (message?.files ?? []).filter(
					(file) => file.type === 'image' || (file?.content_type ?? '').startsWith('image/')
				);

				return {
					role: message.role,
					...(message.role === 'user' && imageFiles.length > 0
						? {
								content: [
									{
										type: 'text',
										text: message?.merged?.content ?? message.content
									},
									...imageFiles.map((file) => ({
										type: 'image_url',
										image_url: {
											url: file.url
										}
									}))
								]
							}
						: {
								content: message?.merged?.content ?? message.content
							})
				};
			})
			.filter((message) => message?.role === 'user' || message?.content?.trim());

		const res = await generateOpenAIChatCompletion(
			localStorage.token,
			{
				model: model.id,
				messages: messages,
				files: (files?.length ?? 0) > 0 ? files : undefined,

				session_id: $socket?.id,
				chat_id: $chatId,

				id: responseMessageId,
				parent_id: userMessage?.id ?? null,
				parent_message: userMessage,

				background_tasks: {
					...(!$temporaryChatEnabled &&
					(messages.length == 1 ||
						(messages.length == 2 &&
							messages.at(0)?.role === 'system' &&
							messages.at(1)?.role === 'user')) &&
					selectedModels[0] === model.id
						? {
								title_generation: $settings?.title?.auto ?? true
							}
						: {}),
					follow_up_generation: $settings?.autoFollowUps ?? true
				},

				...((model.info?.meta?.capabilities?.usage ?? true)
					? {
							stream_options: {
								include_usage: true
							}
						}
					: {})
			},
			`${WEBUI_BASE_URL}/api`
		).catch(async (error) => {
			console.log(error);

			let errorMessage = error;
			if (error?.error?.message) {
				errorMessage = error.error.message;
			} else if (error?.message) {
				errorMessage = error.message;
			}

			if (typeof errorMessage === 'object') {
				errorMessage = $i18n.t(`Uh-oh! There was an issue with the response.`);
			}

			toast.error(`${errorMessage}`);
			responseMessage.error = {
				content: error
			};

			responseMessage.done = true;

			history.messages[responseMessageId] = responseMessage;
			history.currentId = responseMessageId;

			return null;
		});

		if (res) {
			if (res.error) {
				await handleOpenAIError(res.error, responseMessage);
			} else {
				if (taskIds) {
					taskIds.push(res.task_id);
				} else {
					taskIds = [res.task_id];
				}
			}
		}

		await tick();
		scrollToBottom();
	};

	const handleOpenAIError = async (error, responseMessage) => {
		let errorMessage = '';
		let innerError;

		if (error) {
			innerError = error;
		}

		console.error(innerError);
		if ('detail' in innerError) {
			// FastAPI error
			toast.error(innerError.detail);
			errorMessage = innerError.detail;
		} else if ('error' in innerError) {
			// OpenAI error
			if ('message' in innerError.error) {
				toast.error(innerError.error.message);
				errorMessage = innerError.error.message;
			} else {
				toast.error(innerError.error);
				errorMessage = innerError.error;
			}
		} else if ('message' in innerError) {
			// OpenAI error
			toast.error(innerError.message);
			errorMessage = innerError.message;
		}

		responseMessage.error = {
			content: $i18n.t(`Uh-oh! There was an issue with the response.`) + '\n' + errorMessage
		};
		responseMessage.done = true;

		history.messages[responseMessage.id] = responseMessage;
	};

	const stopResponse = async () => {
		if (taskIds) {
			for (const taskId of taskIds) {
				await stopTask(localStorage.token, taskId);
			}

			taskIds = null;

			const responseMessage = history.messages[history.currentId];
			// Set all response messages to done
			if (responseMessage.parentId && history.messages[responseMessage.parentId]) {
				for (const messageId of history.messages[responseMessage.parentId].childrenIds) {
					history.messages[messageId].done = true;
				}
			}

			history.messages[history.currentId] = responseMessage;

			if (autoScroll) {
				scrollToBottom();
			}
		}

		if (generating) {
			generating = false;
			generationController?.abort();
			generationController = null;
		}

		if ($chatId) {
			activeChatIds.update((ids) => {
				const next = new Set(ids);
				next.delete($chatId);
				return next;
			});
		}
	};

	const submitMessage = async (parentId, prompt) => {
		let userPrompt = prompt;
		let userMessageId = uuidv4();

		let userMessage = {
			id: userMessageId,
			parentId: parentId,
			childrenIds: [],
			role: 'user',
			content: userPrompt,
			models: selectedModels,
			timestamp: Math.floor(Date.now() / 1000) // Unix epoch
		};

		if (parentId !== null) {
			history.messages[parentId].childrenIds = [
				...history.messages[parentId].childrenIds,
				userMessageId
			];
		}

		history.messages[userMessageId] = userMessage;
		history.currentId = userMessageId;

		await tick();

		if (autoScroll) {
			scrollToBottom();
		}

		await sendMessage(history, userMessageId);
	};

	const regenerateResponse = async (message, suggestionPrompt = null) => {
		console.log('regenerateResponse');

		if (history.currentId) {
			let userMessage = history.messages[message.parentId];

			if (!userMessage) {
				toast.error($i18n.t('Parent message not found'));
				return;
			}

			if (autoScroll) {
				scrollToBottom();
			}

			await sendMessage(history, userMessage.id, {
				...(suggestionPrompt
					? {
							messages: [
								...createMessagesList(history, message.id),
								{
									role: 'user',
									content: suggestionPrompt
								}
							]
						}
					: {})
			});
		}
	};

	const continueResponse = async () => {
		console.log('continueResponse');
		const _chatId = $chatId;

		if (history.currentId && history.messages[history.currentId].done == true) {
			const responseMessage = history.messages[history.currentId];
			responseMessage.done = false;
			await tick();

			const model = $models.find(
				(m) => m.id === (responseMessage?.selectedModelId ?? responseMessage.model)
			);

			if (model) {
				await sendMessageSocket(
					model,
					createMessagesList(history, responseMessage.id),
					history,
					responseMessage.id
				);
			}
		}
	};

	const initChatHandler = async (history) => {
		let _chatId = $chatId;

		if (!$temporaryChatEnabled) {
			chat = await createNewChat(
				localStorage.token,
				{
					id: _chatId,
					title: $i18n.t('New Chat'),
					models: selectedModels,
					system: $settings.system ?? undefined,
					history: history,
					messages: createMessagesList(history, history.currentId),
					timestamp: Date.now()
				},
				$selectedFolder?.id
			);

			_chatId = chat.id;
			console.log('[initChatHandler] chat created, setting chatId to', _chatId);
			await chatId.set(_chatId);

			await refreshChatList(localStorage.token);

			selectedFolder.set(null);
		} else {
			_chatId = `local:${$socket?.id}`; // Use socket id for temporary chat
			await chatId.set(_chatId);
		}
		await tick();

		return _chatId;
	};

	const saveChatHandler = async (_chatId, history) => {
		if ($chatId == _chatId) {
			if (!$temporaryChatEnabled) {
				chat = await updateChatById(localStorage.token, _chatId, {
					models: selectedModels,
					history: history,
					messages: createMessagesList(history, history.currentId),
					files: chatFiles
				});
			}
		}
	};

	const MAX_DRAFT_LENGTH = 5000;
	let saveDraftTimeout: ReturnType<typeof setTimeout> | null = null;

	const saveDraft = async (draft, chatId = null) => {
		if (saveDraftTimeout) {
			clearTimeout(saveDraftTimeout);
		}

		if (draft.prompt !== null && draft.prompt.length < MAX_DRAFT_LENGTH) {
			saveDraftTimeout = setTimeout(async () => {
				await sessionStorage.setItem(
					`chat-input${chatId ? `-${chatId}` : ''}`,
					JSON.stringify(draft)
				);
			}, 500);
		} else {
			sessionStorage.removeItem(`chat-input${chatId ? `-${chatId}` : ''}`);
		}
	};

	const clearDraft = async (chatId = null) => {
		if (saveDraftTimeout) {
			clearTimeout(saveDraftTimeout);
		}
		await sessionStorage.removeItem(`chat-input${chatId ? `-${chatId}` : ''}`);
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
				await refreshChatList(localStorage.token);
				await pinnedChats.set(await getPinnedChatList(localStorage.token));

				toast.success($i18n.t('Chat moved successfully'));
			}
		} else {
			toast.error($i18n.t('Failed to move chat'));
		}
	};
</script>

<svelte:head>
	<title>
		{$settings.showChatTitleInTab !== false && $chatTitle
			? `${$chatTitle.length > 30 ? `${$chatTitle.slice(0, 30)}...` : $chatTitle} • ${$WEBUI_NAME}`
			: `${$WEBUI_NAME}`}
	</title>
</svelte:head>

<EventConfirmDialog
	bind:show={showEventConfirmation}
	title={eventConfirmationTitle}
	message={eventConfirmationMessage}
	input={eventConfirmationInput}
	inputPlaceholder={eventConfirmationInputPlaceholder}
	inputValue={eventConfirmationInputValue}
	inputType={eventConfirmationInputType}
	onConfirm={(value) => {
		if (value) {
			eventCallback(value);
		} else {
			eventCallback(true);
		}
	}}
	oncancel={() => {
		eventCallback(false);
	}}
/>

<div
	class="h-screen max-h-[100dvh] transition-width duration-200 ease-in-out {$showSidebar
		? '  md:max-w-[calc(100%-var(--sidebar-width))]'
		: ' '} w-full max-w-full flex flex-col"
	id="chat-container"
>
	{#if !loading}
		<div in:fade={{ duration: 50 }} class="w-full h-full flex flex-col">
			<div class="w-full h-full flex relative max-w-full flex-col">
				<Navbar
					bind:this={navbarElement}
					chat={{
						id: $chatId,
						chat: {
							title: $chatTitle,
							models: selectedModels,
							system: $settings.system ?? undefined,
							history: history,
							timestamp: Date.now()
						}
					}}
					bind:selectedModels
					{initNewChat}
					{moveChatHandler}
					onSaveTempChat={async () => {
						try {
							if (!history?.currentId || !Object.keys(history.messages).length) {
								toast.error($i18n.t('No conversation to save'));
								return;
							}
							const messages = createMessagesList(history, history.currentId);
							const title = messages.find((m) => m.role === 'user')?.content ?? $i18n.t('New Chat');

							const savedChat = await createNewChat(
								localStorage.token,
								{
									id: uuidv4(),
									title: title.length > 50 ? `${title.slice(0, 50)}...` : title,
									models: selectedModels,
									history: history,
									messages: messages,
									timestamp: Date.now()
								},
								null
							);

							if (savedChat) {
								temporaryChatEnabled.set(false);
								chatId.set(savedChat.id);
								await refreshChatList(localStorage.token);

								await goto(`/c/${savedChat.id}`);
								toast.success($i18n.t('Conversation saved successfully'));
							}
						} catch (error) {
							console.error('Error saving conversation:', error);
							toast.error($i18n.t('Failed to save conversation'));
						}
					}}
				/>

				<div class="flex flex-col flex-auto w-full overflow-auto">
					{#if ($settings?.landingPageMode === 'chat' && !$selectedFolder) || createMessagesList(history, history.currentId).length > 0}
						<div
							class=" pb-2.5 flex flex-col justify-between w-full flex-auto overflow-auto h-0 max-w-full scrollbar-hidden"
							id="messages-container"
							bind:this={messagesContainerElement}
							onscroll={() => {
								autoScroll =
									messagesContainerElement.scrollHeight - messagesContainerElement.scrollTop <=
									messagesContainerElement.clientHeight + 5;
							}}
						>
							<div class=" h-full w-full flex flex-col">
								<Messages
									chatId={$chatId}
									bind:history
									bind:autoScroll
									setInputText={(text) => {
										messageInput?.setText(text);
									}}
									{selectedModels}
									{sendMessage}
									{showMessage}
									{submitMessage}
									{continueResponse}
									{regenerateResponse}
									{addMessages}
									topPadding={true}
									bottomPadding={files.length > 0}
									{onSelect}
									{scrollToBottom}
								/>
							</div>
						</div>

						<div class=" pb-2 z-10">
							<MessageInput
								bind:this={messageInput}
								{history}
								{taskIds}
								{selectedModels}
								bind:files
								bind:prompt
								bind:autoScroll
								{generating}
								{stopResponse}
								{createMessagePair}
								{scrollToBottom}
								{messageQueue}
								onQueueSendNow={async (id) => {
									const item = messageQueue.find((m) => m.id === id);
									if (item) {
										// Remove from queue
										messageQueue = messageQueue.filter((m) => m.id !== id);
										// Stop current generation first
										await stopResponse();
										await tick();
										// Set files and submit
										files = item.files;
										await tick();
										await submitPrompt(item.prompt);
									}
								}}
								onQueueEdit={(id) => {
									const item = messageQueue.find((m) => m.id === id);
									if (item) {
										// Remove from queue
										messageQueue = messageQueue.filter((m) => m.id !== id);
										// Set files and restore prompt to input
										files = item.files;
										messageInput?.setText(item.prompt);
									}
								}}
								onQueueDelete={(id) => {
									messageQueue = messageQueue.filter((m) => m.id !== id);
								}}
								onChange={(data) => {
									if (!$temporaryChatEnabled) {
										saveDraft(data, $chatId);
									}
								}}
								onSubmit={async (prompt) => {
									clearDraft();
									if (prompt || files.length > 0) {
										await tick();
										submitPrompt(prompt.replaceAll('\n\n', '\n'));
									}
								}}
							/>

							<div
								class="absolute bottom-1 text-xs text-gray-500 text-center line-clamp-1 right-0 left-0"
							>
								<!-- {$i18n.t('LLMs can make mistakes. Verify important information.')} -->
							</div>
						</div>
					{:else}
						<div class="flex items-center h-full">
							<Placeholder
								{history}
								{selectedModels}
								bind:messageInput
								bind:files
								bind:prompt
								bind:autoScroll
								{stopResponse}
								{createMessagePair}
								{onSelect}
								onChange={(data) => {
									if (!$temporaryChatEnabled) {
										saveDraft(data);
									}
								}}
								onSubmit={async (prompt) => {
									clearDraft();
									if (prompt || files.length > 0) {
										await tick();
										submitPrompt(prompt.replaceAll('\n\n', '\n'));
									}
								}}
							/>
						</div>
					{/if}
				</div>
			</div>
		</div>
	{:else if loading}
		<div class=" flex items-center justify-center h-full w-full">
			<div class="m-auto">
				<Spinner className="size-5" />
			</div>
		</div>
	{/if}
</div>

<style>
	::-webkit-scrollbar {
		height: 0.5rem;
		width: 0.5rem;
	}
</style>
