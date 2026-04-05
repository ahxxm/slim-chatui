<script lang="ts">
	import { settings } from '$lib/stores';
	import type { ChatHistory } from '$lib/types';

	import ResponseMessage from './ResponseMessage.svelte';
	import UserMessage from './UserMessage.svelte';

	let {
		chatId,
		idx = 0,
		history = { messages: {}, currentId: null } as ChatHistory,
		streamingMessages,
		messageId,
		user,
		setInputText = () => {},
		showPreviousMessage,
		showNextMessage,
		editMessage,
		deleteMessage,
		submitMessage,
		regenerateResponse,
		continueResponse,
		addMessages,
		readOnly = false,
		topPadding = false
	} = $props();

	let userSiblings = $derived.by(() => {
		const msg = history.messages[messageId];
		if (!msg) return [];
		if (msg.parentId !== null) {
			return history.messages[msg.parentId]?.childrenIds ?? [];
		}
		const rootIds: string[] = [];
		for (const id in history.messages) {
			if (history.messages[id].parentId === null) rootIds.push(id);
		}
		return rootIds;
	});
</script>

<div
	role="listitem"
	class="flex flex-col justify-between px-5 mb-3 w-full {($settings?.widescreenMode ?? null)
		? 'max-w-full'
		: 'max-w-5xl'} mx-auto rounded-lg group"
>
	{#if history.messages[messageId]}
		{#if history.messages[messageId].role === 'user'}
			<UserMessage
				{user}
				{chatId}
				{history}
				{messageId}
				isFirstMessage={idx === 0}
				siblings={userSiblings}
				{showPreviousMessage}
				{showNextMessage}
				{editMessage}
				{deleteMessage}
				{readOnly}
				{topPadding}
			/>
		{:else}
			<ResponseMessage
				{chatId}
				{history}
				{streamingMessages}
				{messageId}
				isLastMessage={messageId === history.currentId}
				// always children of a user message
				siblings={history.messages[history.messages[messageId].parentId!]?.childrenIds ?? []}
				{setInputText}
				{showPreviousMessage}
				{showNextMessage}
				{editMessage}
				{submitMessage}
				{deleteMessage}
				{continueResponse}
				{regenerateResponse}
				{addMessages}
				{readOnly}
				{topPadding}
			/>
		{/if}
	{/if}
</div>
