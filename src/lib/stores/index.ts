import { APP_NAME } from '$lib/constants';
import { type Writable, writable, get } from 'svelte/store';
import type { ModelConfig } from '$lib/apis';
import type { ChatListItem, FolderItem } from '$lib/types';
import type { Socket } from 'socket.io-client';
import { getChatList } from '$lib/apis/chats';

// Backend
export const WEBUI_NAME = writable(APP_NAME);

export const config: Writable<Config | undefined> = writable(undefined);
export const user: Writable<SessionUser | undefined> = writable(undefined);

// Frontend
export const mobile = writable(false);

export const socket: Writable<null | Socket> = writable(null);
export const activeChatIds: Writable<Set<string>> = writable(new Set());
export const theme = writable('system');

export const chatId = writable('');
export const chatTitle = writable('');

export const chats: Writable<ChatListItem[]> = writable([]);
export const pinnedChats: Writable<ChatListItem[]> = writable([]);
export const folders: Writable<FolderItem[]> = writable([]);

export const selectedFolder: Writable<FolderItem | null> = writable(null);

export const models: Writable<Model[]> = writable([]);

export const settings: Writable<Settings> = writable({});

export const sidebarWidth = writable(260);

export const showSidebar = writable(false);
export const showSearch = writable(false);
export const showSettings = writable(false);
export const showShortcuts = writable(false);
export const temporaryChatEnabled = writable(false);
export const scrollPaginationEnabled = writable(false);
export const currentChatPage = writable(1);

export const PAGE_SIZE = 60;

let activeRefreshChatList: Promise<boolean> | null = null;
let queuedRefreshChatList = false;
let queuedRefreshToken: string | null = null;

const runRefreshChatList = async (token: string, signal?: AbortSignal): Promise<boolean> => {
	const throughPage = get(currentChatPage);
	const allChats: ChatListItem[] = [];
	let lastPage = 0;
	let allLoaded = false;

	for (let p = 1; p <= throughPage; p++) {
		const batch = await getChatList(token, p);
		if (signal?.aborted) return false;
		allChats.push(...batch);
		lastPage = p;
		if (batch.length < PAGE_SIZE) {
			allLoaded = true;
			break;
		}
	}

	chats.set(allChats);
	currentChatPage.set(lastPage || 1);
	return allLoaded;
};

/** Refetch pages 1..currentChatPage, stopping early on a short page.
 *  Deflates currentChatPage to the actual last page with data.
 *  Returns true if all data was loaded (last fetched page was short). */
export async function refreshChatList(token: string, signal?: AbortSignal): Promise<boolean> {
	if (signal) {
		return runRefreshChatList(token, signal);
	}

	queuedRefreshToken = token;

	if (activeRefreshChatList) {
		queuedRefreshChatList = true;
		return activeRefreshChatList;
	}

	activeRefreshChatList = (async () => {
		let allLoaded = await runRefreshChatList(queuedRefreshToken ?? token);

		while (queuedRefreshChatList) {
			queuedRefreshChatList = false;
			allLoaded = await runRefreshChatList(queuedRefreshToken ?? token);
		}

		return allLoaded;
	})();

	try {
		return await activeRefreshChatList;
	} finally {
		activeRefreshChatList = null;
		queuedRefreshChatList = false;
	}
}

export const isLastActiveTab = writable(true);
export const playingNotificationSound = writable(false);

export type Model = {
	id: string;
	name: string;
	info?: ModelConfig;
	owned_by: string;
};

type Settings = {
	collapseCodeBlocks?: boolean;
	expandDetails?: boolean;
	notificationSound?: boolean;
	notificationSoundAlways?: boolean;
	notifications?: any;
	imageCompression?: boolean;
	imageCompressionSize?: any;
	textScale?: number;
	widescreenMode?: null;
	largeTextAsFile?: boolean;
	autoFollowUps?: boolean;
	splitLargeChunks?: boolean;
	landingPageMode?: string;
	iframeSandboxAllowForms?: boolean;
	iframeSandboxAllowSameOrigin?: boolean;
	chatBubble?: boolean;
	copyFormatted?: boolean;
	models?: string[];
	showUsername?: boolean;
	notificationEnabled?: boolean;
	highContrastMode?: boolean;
	title?: TitleSettings;
	showChatTitleInTab?: boolean;
	splitLargeDeltas?: boolean;
	chatDirection?: 'LTR' | 'RTL' | 'auto';
	cjkFont?: string;
	ctrlEnterToSend?: boolean;
	renderMarkdownInPreviews?: boolean;

	system?: string;
	temporaryChatByDefault?: boolean;
	insertSuggestionPrompt?: boolean;
	insertFollowUpPrompt?: boolean;
	keepFollowUpPrompts?: boolean;
	enableMessageQueue?: boolean;
	chatFadeStreamingText?: boolean;
	floatingActionButtons?: boolean;
	showFloatingActionButtons?: boolean;
	regenerateMenu?: boolean;
};

type TitleSettings = {
	auto?: boolean;
	model?: string;
	prompt?: string;
};

type Config = {
	status: boolean;
	name: string;
	version: string;
	features: {
		auth: boolean;
		enable_signup: boolean;
		enable_signup_password_confirmation?: boolean;
		enable_websocket?: boolean;
	};
	metadata?: {
		auth_logo_position?: string;
		login_footer?: string;
	};
	file?: {
		image_compression?: {
			width?: number;
			height?: number;
		};
	};
	user_count?: number;
};

type SessionUser = {
	id: string;
	email: string;
	name: string;
	role: string;
	expires_at?: number;
};
