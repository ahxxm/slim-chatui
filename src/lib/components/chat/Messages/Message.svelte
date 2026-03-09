<script lang="ts">
	import { settings } from '$lib/stores';
	import type { ChatHistory } from '$lib/types';

	import ResponseMessage from './ResponseMessage.svelte';
	import UserMessage from './UserMessage.svelte';

	let {
		chatId,
		idx = 0,
		history = { messages: {}, currentId: null } as ChatHistory,
		messageId,
		user,
		setInputText = () => {},
		showPreviousMessage,
		showNextMessage,
		updateChat,
		editMessage,
		deleteMessage,
		submitMessage,
		regenerateResponse,
		continueResponse,
		addMessages,
		readOnly = false,
		editCodeBlock = true,
		topPadding = false
	} = $props();
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
				siblings={history.messages[messageId].parentId !== null
					? (history.messages[history.messages[messageId].parentId]?.childrenIds ?? [])
					: (Object.values(history.messages)
							.filter((message) => message.parentId === null)
							.map((message) => message.id) ?? [])}
				{showPreviousMessage}
				{showNextMessage}
				{editMessage}
				{deleteMessage}
				{readOnly}
				{editCodeBlock}
				{topPadding}
			/>
		{:else}
			<ResponseMessage
				{chatId}
				{history}
				{messageId}
				isLastMessage={messageId === history.currentId}
				// always children of a user message
				siblings={history.messages[history.messages[messageId].parentId!]?.childrenIds ?? []}
				{setInputText}
				{showPreviousMessage}
				{showNextMessage}
				{updateChat}
				{editMessage}
				{submitMessage}
				{deleteMessage}
				{continueResponse}
				{regenerateResponse}
				{addMessages}
				{readOnly}
				{editCodeBlock}
				{topPadding}
			/>
		{/if}
	{/if}
</div>
