// Mirrors backend ChatTitleIdResponse + frontend time_range augmentation
export type AdminConfig = {
	DEFAULT_USER_ROLE: 'pending' | 'user' | 'admin';
	ENABLE_SIGNUP: boolean;
	ADMIN_EMAIL: string;
	JWT_EXPIRES_IN: string;
	WEBUI_URL: string;
};

export type TaskConfig = {
	ENABLE_TITLE_GENERATION: boolean;
	TITLE_GENERATION_PROMPT_TEMPLATE: string;
	ENABLE_FOLLOW_UP_GENERATION: boolean;
	FOLLOW_UP_GENERATION_PROMPT_TEMPLATE: string;
};

export type Connection = {
	url: string;
	key: string;
	config: {
		enable?: boolean;
		[key: string]: unknown;
	};
};

export type ChatListItem = {
	id: string;
	title: string;
	updated_at: number;
	created_at: number;
	time_range?: string;
};

export type CitationMetadata = {
	source?: string;
	name?: string;
	file_id?: string;
	page?: number;
	[key: string]: unknown;
};

export type CitationSource = {
	id?: string;
	name?: string;
	url?: string;
	embed_url?: string;
};

export type CitationInput = {
	document?: string[];
	metadata?: CitationMetadata[];
	distances?: number[];
	source?: CitationSource;
};

export type Citation = {
	id: string;
	source: CitationSource & { name: string };
	document: string[];
	metadata: CitationMetadata[];
	distances: number[];
};

// Structural fields every message has; streaming adds arbitrary fields on top.
export type ChatMessage = {
	id: string;
	parentId: string | null;
	childrenIds: string[];
	role: 'user' | 'assistant' | 'system';
	content: string;
	timestamp: number;
	[key: string]: any;
};

// Chat blob internals (stored in chat.chat JSON column)
export type ChatHistory = {
	messages: Record<string, ChatMessage>;
	currentId: string | null;
};

// Mirrors backend FolderNameIdResponse (what GET /folders/ returns)
export type FolderItem = {
	id: string;
	name: string;
	meta?: Record<string, any> | null;
	is_expanded: boolean;
	created_at: number;
	updated_at: number;
	// Frontend-only: enriched by Sidebar from full folder data
	data?: Record<string, any> | null;
	items?: { chat_ids?: string[]; file_ids?: string[] } | null;
};
