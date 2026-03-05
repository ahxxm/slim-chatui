export type Banner = {
	id: string;
	type: string;
	title?: string;
	content: string;
	url?: string;
	dismissible?: boolean;
	timestamp: number;
};

// Mirrors backend ChatTitleIdResponse + frontend time_range augmentation
export type ChatListItem = {
	id: string;
	title: string;
	updated_at: number;
	created_at: number;
	time_range?: string;
};

// Mirrors backend TagModel
export type TagItem = {
	id: string;
	name: string;
	user_id: string;
	meta?: Record<string, unknown> | null;
};

// Chat blob internals (stored in chat.chat JSON column)
// Messages are open-ended (streaming adds arbitrary fields), so values are `any`.
export type ChatHistory = {
	messages: Record<string, any>;
	currentId: string | null;
};

// Mirrors backend FolderNameIdResponse (what GET /folders/ returns)
export type FolderItem = {
	id: string;
	name: string;
	meta?: Record<string, any> | null;
	parent_id?: string | null;
	is_expanded: boolean;
	created_at: number;
	updated_at: number;
	// Frontend-only: enriched by Sidebar from full folder data
	data?: Record<string, any> | null;
	items?: { chat_ids?: string[]; file_ids?: string[] } | null;
};
